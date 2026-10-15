import numpy as np
import pytest

from helpers import N, RES, detect, profile


def test_ignores_a_slow_ramp_but_finds_a_step():
    p = profile(jitter=0.2) + np.linspace(0.0, 30.0, N)        # 0.05 dB per sample
    slow = dict(smoothing='moving_average', **{'rise.rise_db': 6.0})
    assert not detect(p, 'rise', **slow).detected
    p[350:360] += 25.0
    d = detect(p, 'rise', **{'rise.rise_db': 6.0})
    assert d.detected and d.range_m == pytest.approx(350 * RES, abs=RES)


def test_with_smoothing_the_edge_is_placed_within_the_window():
    p = profile([(12.0, 1.0, -40.0)], jitter=0.2)
    w = 5
    d = detect(p, 'rise', smoothing='moving_average', smooth_samples=w, **{'rise.rise_db': 2.0})
    assert d.detected
    assert abs(d.range_m - 12.0) <= (w // 2 + 1) * RES


def test_the_return_extends_while_it_stays_above_half_the_step():
    p = np.full(N, -80.0)
    p[300:320] = -40.0
    d = detect(p, 'rise', min_range_m=0.0, **{'rise.rise_db': 10.0})
    assert d.range_m == pytest.approx(300 * RES)
    assert d.width_m == pytest.approx(20 * RES)


def test_a_rise_that_does_not_last_min_width_is_skipped_for_the_next_one():
    p = np.full(N, -80.0)
    p[100] = -40.0                    # one-sample spike
    p[300:320] = -40.0                # a real return
    d = detect(p, 'rise', min_range_m=0.0, min_width_samples=3, **{'rise.rise_db': 10.0})
    assert d.range_m == pytest.approx(300 * RES)
