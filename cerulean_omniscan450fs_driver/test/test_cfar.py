import numpy as np
import pytest

from cerulean_omniscan450fs_driver.range_detection.cfar import (
    CFAR_MIN_CELLS, CfarParams, cfar_alpha, cfar_mask)
from helpers import N, RES, detect, profile


def test_alpha_matches_the_closed_form():
    assert cfar_alpha(40, 1e-3) == pytest.approx(40 * (1e-3 ** (-1 / 40) - 1))
    assert cfar_alpha(40, 1e-6) > cfar_alpha(40, 1e-3) > cfar_alpha(40, 1e-1)


def test_false_alarm_rate_matches_the_design_value_for_exponential_noise():
    """On exponentially distributed noise power the per-cell false alarm rate is Pfa."""
    params = CfarParams(pfa=1e-2)
    rng = np.random.default_rng(1)
    gate = np.ones(N, dtype=bool)
    alarms = cells = 0
    for _ in range(400):
        above, _, _ = cfar_mask(10.0 * np.log10(rng.exponential(1.0, N)), gate, params)
        alarms += int(above.sum())
        cells += N - (params.guard_cells + CFAR_MIN_CELLS)    # the first cells are not tested
    assert alarms / cells == pytest.approx(1e-2, rel=0.15)


def test_follows_a_rising_background_where_a_global_threshold_does_not():
    """Noise rises 40 dB over the window. A weak early target is under the global threshold,
    which then fires on the noise much farther out. CFAR finds the target."""
    p = profile(jitter=0.5) + np.linspace(0.0, 40.0, N)
    p[200:210] += 12.0                                         # 12 dB over the local noise, 10 m
    glob = detect(p, 'threshold', **{'threshold.min_snr_db': 10.0})
    assert glob.detected and glob.range_m > 20.0               # false detection on rising noise
    cf = detect(p, 'cfar', **{'cfar.pfa': 1e-2})
    assert cf.detected and cf.range_m == pytest.approx(10.0, abs=0.2)


def test_extent_is_not_cut_short_by_the_return_raising_its_own_threshold():
    p = profile([(12.0, 3.0, -40.0)], jitter=0.5)              # 3 m wide, 40 dB over the noise
    d = detect(p, 'cfar', **{'cfar.pfa': 1e-4})
    assert d.range_m == pytest.approx(12.0, abs=RES)
    assert d.width_m == pytest.approx(3.0, abs=0.2)


def test_cells_without_enough_reference_are_not_tested():
    p = np.full(N, -80.0)
    p[2] = -20.0                                               # too early for a threshold
    above, _, _ = cfar_mask(p, np.ones(N, dtype=bool), CfarParams(guard_cells=2))
    assert not above[:CFAR_MIN_CELLS + 2].any()


def test_reference_cells_that_are_nan_are_skipped_not_counted():
    p = np.full(N, -80.0) + np.random.default_rng(2).normal(0, 0.5, N)
    p[100:110] = np.nan
    p[200] = -40.0
    above, thr, _ = cfar_mask(p, np.isfinite(p), CfarParams())
    assert above[200] and not above[100:110].any() and np.isfinite(thr[200])


def test_lower_pfa_needs_a_stronger_return():
    p = profile([(12.0, 0.5, -66.0)], jitter=0.5)              # 14 dB over the noise
    assert detect(p, 'cfar', **{'cfar.pfa': 1e-2}).detected
    assert not detect(p, 'cfar', **{'cfar.pfa': 1e-9}).detected
