"""Behaviour every first-return method must have, checked on each registered method."""

import math

import numpy as np
import pytest

from cerulean_omniscan450fs_driver.range_detection import DETECTORS
from helpers import N, RES, detect, profile

METHODS = sorted(DETECTORS)


@pytest.mark.parametrize('method', METHODS)
def test_finds_a_clean_return(method):
    d = detect(profile([(12.0, 0.5, -40.0)]), method)
    assert d.detected
    assert d.range_m == pytest.approx(12.0, abs=RES)
    assert d.raw_range_m == d.range_m
    assert d.peak_power_db == pytest.approx(-40.0)
    assert d.width_m == pytest.approx(0.5, abs=0.2)        # peak can grow into the noise
    assert d.snr_db > 30.0


@pytest.mark.parametrize('method', METHODS)
def test_reports_nothing_in_pure_noise(method):
    d = detect(profile(), method)
    assert not d.detected
    assert math.isnan(d.range_m) and math.isnan(d.raw_range_m)


@pytest.mark.parametrize('method', METHODS)
def test_blanking_distance_and_far_gate(method):
    near = profile([(0.4, 0.3, -30.0), (15.0, 0.5, -45.0)])
    d = detect(near, method)
    assert d.detected and d.range_m == pytest.approx(15.0, abs=RES)   # 0.4 m is inside min_range
    far = profile([(25.0, 0.5, -40.0)])
    assert not detect(far, method, max_range_m=20.0).detected
    assert detect(far, method).detected


@pytest.mark.parametrize('method', METHODS)
def test_window_offset_and_bad_inputs(method):
    d = detect(profile([(10.0, 0.5, -40.0)]), method, start_m=5.0, min_range_m=0.0)
    assert d.range_m == pytest.approx(15.0, abs=RES)
    assert not detect([], method).detected
    assert not detect(profile(), method, length_m=0.0).detected


@pytest.mark.parametrize('method', METHODS)
def test_nan_samples_do_not_break_detection(method):
    p = profile([(12.0, 0.5, -40.0)])
    p[:30] = np.nan
    p[300:305] = np.nan
    d = detect(p, method)
    assert d.detected and d.range_m == pytest.approx(12.0, abs=RES)
    assert not detect(np.full(N, np.nan), method).detected


@pytest.mark.parametrize('method', METHODS)
def test_absolute_power_floor(method):
    p = profile([(12.0, 0.5, -50.0)])
    assert detect(p, method).detected
    assert not detect(p, method, min_power_db=-45.0).detected


@pytest.mark.parametrize('method', METHODS)
def test_a_single_sample_spike_needs_min_width_one(method):
    # peak grows into the noise above its average, so it needs its margin for this
    extra = {'peak.margin_db': 6.0} if method == 'peak' else {}
    p = profile([(10.0, 0.05, -20.0)])
    assert not detect(p, method, min_width_samples=2, **extra).detected
    assert detect(p, method, min_width_samples=1, **extra).detected


@pytest.mark.parametrize('method', METHODS)
def test_smoothing_and_tvg_run_with_every_method(method):
    p = profile([(12.0, 1.0, -40.0)])
    for flat in ({'smoothing': 'moving_average', 'smooth_samples': 3},
                 {'smoothing': 'hann', 'smooth_samples': 5}, {'tvg_enabled': True}):
        d = detect(p, method, **flat)
        assert d.detected and abs(d.range_m - 12.0) < 0.5


@pytest.mark.parametrize('method', METHODS)
@pytest.mark.parametrize('reference', ['leading_edge', 'peak', 'centroid'])
def test_every_reference_works_with_every_method(method, reference):
    d = detect(profile([(12.0, 1.0, -40.0)]), method, reference=reference)
    assert d.detected and 11.7 <= d.range_m <= 13.1
