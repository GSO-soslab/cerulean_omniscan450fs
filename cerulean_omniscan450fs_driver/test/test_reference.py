import numpy as np
import pytest

from cerulean_omniscan450fs_driver.range_detection import Region, reference_range
from helpers import N, RES, detect


def wide_return():
    """A slow rise to a peak, then a long fall."""
    p = np.full(N, -90.0)
    p[200:280] = np.concatenate([np.linspace(-60.0, -30.0, 20), np.linspace(-30.0, -60.0, 60)])
    return p


def test_reference_places_the_range_inside_a_wide_return():
    p = wide_return()
    base = dict(min_range_m=0.0)
    lead = detect(p, reference='leading_edge', **base).range_m
    peak = detect(p, reference='peak', **base).range_m
    cent = detect(p, reference='centroid', **base).range_m
    assert lead == pytest.approx(200 * RES, abs=RES)
    assert peak == pytest.approx(219 * RES, abs=RES)
    assert lead < peak < cent < 280 * RES


def test_centroid_of_a_flat_return_is_its_middle():
    i0 = 240
    p = np.full(N, -90.0)
    p[i0:i0 + 20] = -40.0
    d = detect(p, reference='centroid', min_range_m=0.0)
    assert d.range_m == pytest.approx((i0 + 9.5) * RES, abs=1e-6)


def test_centroid_weights_by_amplitude_so_a_louder_sample_pulls_it():
    ranges = np.arange(10.0)
    p = np.full(10, -60.0)
    p[8] = -40.0                                   # 20 dB louder, 10x the amplitude
    c = reference_range(p, ranges, Region(0, 10, -70.0), 'centroid')
    assert c == pytest.approx((sum(range(10)) - 8 + 80) / 19)   # weights 1 everywhere, 10 at 8


def test_unknown_reference_is_an_error():
    with pytest.raises(ValueError):
        reference_range(np.zeros(4), np.arange(4.0), Region(0, 4, 0.0), 'nope')
