import numpy as np
import pytest

from helpers import N, RES, detect, profile


def test_finds_the_strongest_return_not_the_nearest():
    p = profile([(12.0, 0.5, -50.0), (20.0, 1.0, -30.0)])
    d = detect(p, 'peak')
    assert d.range_m == pytest.approx(20.0, abs=0.2)          # paper threshold: edge can be early
    assert d.peak_power_db == pytest.approx(-30.0)
    tight = detect(p, 'peak', **{'peak.margin_db': 3.0})
    assert tight.range_m == pytest.approx(20.0, abs=RES)


def test_threshold_is_the_smaller_of_the_two_background_averages():
    p = np.full(N, -80.0)
    p[300:310] = -40.0
    p[310:330] = -70.0        # the tail after the peak is louder than the noise before it
    d = detect(p, 'peak', min_range_m=0.0, **{'peak.background_samples': 10})
    assert d.threshold_db == pytest.approx(-80.0)             # the quiet side, not the tail
    assert d.width_m == pytest.approx(30 * RES)


def test_background_is_averaged_on_linear_power_not_as_a_mean_of_db():
    p = np.full(N, -80.0)
    p[300] = -40.0
    p[290:300] = [-80.0] * 9 + [-50.0]          # one loud sample in each background interval
    p[301:311] = [-50.0] + [-80.0] * 9
    d = detect(p, 'peak', min_range_m=0.0, min_width_samples=1,
               **{'peak.background_samples': 10})
    linear = 10.0 * np.log10((9 * 1e-8 + 1e-5) / 10.0)         # about -59.6 dB
    assert d.threshold_db == pytest.approx(linear)
    assert abs(d.threshold_db - np.mean([-80.0] * 9 + [-50.0])) > 10.0     # the dB mean is -77


def test_margin_stops_the_return_growing_into_the_noise():
    p = profile([(12.0, 0.5, -40.0)])
    paper = detect(p, 'peak')
    tight = detect(p, 'peak', **{'peak.margin_db': 3.0})
    assert paper.width_m > 0.5 + RES                          # noise above the average joins in
    assert tight.width_m == pytest.approx(0.5, abs=RES)
    assert tight.range_m == pytest.approx(12.0, abs=RES)


def test_peak_must_stand_above_its_background():
    """The strongest sample of a profile with no target is noise and must not count."""
    assert not detect(profile(), 'peak').detected
    p = profile([(10.0, 0.5, -75.0)])
    assert not detect(p, 'peak', **{'peak.min_snr_db': 10.0}).detected
