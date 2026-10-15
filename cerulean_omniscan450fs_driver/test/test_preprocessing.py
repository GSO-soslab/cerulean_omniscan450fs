import numpy as np
import pytest

from cerulean_omniscan450fs_driver.range_detection import smooth_profile, tvg_correction_db
from helpers import N, RES, START, detect, profile


def test_tvg_matches_the_formula():
    r = np.array([1.0, 10.0, 100.0])
    assert tvg_correction_db(r, 20.0, 0.0, 1.0) == pytest.approx([0.0, 20.0, 40.0])
    assert tvg_correction_db(r, 20.0, 0.1, 1.0) == pytest.approx([0.2, 22.0, 60.0])
    assert tvg_correction_db(r, 40.0, 0.0, 10.0) == pytest.approx([-40.0, 0.0, 40.0])
    assert np.isfinite(tvg_correction_db([0.0], 20.0, 0.0, 1.0)).all()


def test_tvg_recovers_a_far_return_lost_to_range_loss():
    r = START + np.arange(N) * RES
    loss = -20.0 * np.log10(np.maximum(r, RES))                 # echo falls with range
    p = profile(jitter=0.3) + loss
    p[500:510] = -80.0 + loss[500:510] + 25.0                   # 25 dB above the local noise
    off = detect(p, min_range_m=2.0)
    assert not off.detected or off.range_m < 24.0               # without TVG it is lost or wrong
    on = detect(p, min_range_m=2.0, tvg_enabled=True)
    assert on.detected and on.range_m == pytest.approx(25.0, abs=RES)


def test_smoothing_keeps_length_nan_and_mean_level():
    p = profile(jitter=2.0)
    p[10] = np.nan
    for kind in ('moving_average', 'hann'):
        s = smooth_profile(p, kind, 7)
        assert s.shape == p.shape and np.isnan(s[10]) and np.isfinite(np.delete(s, 10)).all()
        assert np.nanstd(s) < np.nanstd(p)
        assert np.nanmean(s) == pytest.approx(np.nanmean(p), abs=0.3)
    np.testing.assert_array_equal(smooth_profile(p, 'none', 7), p)
    np.testing.assert_array_equal(smooth_profile(p, 'moving_average', 1), p)


def test_smoothing_a_constant_is_the_constant_including_the_edges():
    for kind in ('moving_average', 'hann'):
        np.testing.assert_allclose(smooth_profile(np.full(50, -60.0), kind, 9), -60.0)


def test_smoothing_moves_a_threshold_crossing_by_at_most_half_the_window():
    p = profile([(12.0, 1.0, -40.0)], jitter=0.0)
    raw = detect(p).range_m
    for w in (3, 5, 9):
        smooth = detect(p, smoothing='moving_average', smooth_samples=w).range_m
        assert abs(smooth - raw) <= (w // 2 + 1) * RES


def test_smoothing_moves_the_crossing_earlier_for_a_low_threshold_and_later_for_a_high_one():
    p = profile([(12.0, 1.0, -40.0)], jitter=0.0)
    raw = detect(p, **{'threshold.min_snr_db': 5.0}).range_m
    low = detect(p, smoothing='moving_average', smooth_samples=5, **{'threshold.min_snr_db': 5.0})
    high = detect(p, smoothing='moving_average', smooth_samples=5, **{'threshold.min_snr_db': 38.0})
    assert low.range_m < raw < high.range_m
