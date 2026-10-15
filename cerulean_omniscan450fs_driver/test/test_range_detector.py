import math

import numpy as np
import pytest

from cerulean_omniscan450fs_driver.range_detector import (
    DetectorConfig, detect_first_return, sample_range)

START, LENGTH, N = 0.0, 30.0, 600     # 5 cm per sample


def profile(bumps=(), noise_db=-80.0, jitter=1.0, seed=0):
    rng = np.random.default_rng(seed)
    p = noise_db + rng.normal(0.0, jitter, N)
    for range_m, width_m, level_db in bumps:
        i0 = int(round(range_m / (LENGTH / N)))
        i1 = i0 + max(1, int(round(width_m / (LENGTH / N))))
        p[i0:i1] = level_db
    return p


def test_detects_first_of_two_returns_within_one_sample():
    p = profile([(12.0, 0.5, -40.0), (20.0, 1.0, -30.0)])
    d = detect_first_return(p, START, LENGTH)
    assert d.detected
    assert d.range_m == pytest.approx(12.0, abs=LENGTH / N)
    assert d.peak_power_db == pytest.approx(-40.0)
    assert d.width_m == pytest.approx(0.5, abs=LENGTH / N)
    assert d.snr_db > 30.0


def test_no_return_is_not_detected():
    d = detect_first_return(profile(), START, LENGTH)
    assert not d.detected
    assert math.isnan(d.range_m)


def test_near_return_inside_blanking_is_ignored():
    p = profile([(0.4, 0.3, -30.0), (15.0, 0.5, -45.0)])
    d = detect_first_return(p, START, LENGTH, DetectorConfig(min_range_m=1.0))
    assert d.detected
    assert d.range_m == pytest.approx(15.0, abs=LENGTH / N)


def test_far_gate_limits_detection():
    p = profile([(25.0, 0.5, -40.0)])
    assert not detect_first_return(p, START, LENGTH, DetectorConfig(max_range_m=20.0)).detected
    assert detect_first_return(p, START, LENGTH, DetectorConfig(max_range_m=0.0)).detected


def test_single_sample_spike_is_rejected():
    p = profile([(10.0, 0.05, -20.0), (18.0, 0.5, -45.0)])
    d = detect_first_return(p, START, LENGTH, DetectorConfig(min_width_samples=2))
    assert d.detected
    assert d.range_m == pytest.approx(18.0, abs=LENGTH / N)
    d1 = detect_first_return(p, START, LENGTH, DetectorConfig(min_width_samples=1))
    assert d1.range_m == pytest.approx(10.0, abs=LENGTH / N)


def test_weak_return_below_snr_is_rejected_and_absolute_floor_applies():
    p = profile([(10.0, 0.5, -75.0)])                       # only ~5 dB above noise
    assert not detect_first_return(p, START, LENGTH, DetectorConfig(min_snr_db=10.0)).detected
    strong = profile([(10.0, 0.5, -50.0)])
    assert detect_first_return(strong, START, LENGTH).detected
    assert not detect_first_return(strong, START, LENGTH, DetectorConfig(min_power_db=-45.0)).detected


def test_window_offset_is_respected():
    p = profile([(10.0, 0.5, -40.0)])
    d = detect_first_return(p, 5.0, LENGTH, DetectorConfig(min_range_m=0.0))
    assert d.range_m == pytest.approx(5.0 + 10.0, abs=LENGTH / N)


def test_empty_nan_and_bad_inputs():
    assert not detect_first_return([], START, LENGTH).detected
    assert not detect_first_return(profile(), START, 0.0).detected
    p = profile([(10.0, 0.5, -40.0)])
    p[:50] = np.nan
    assert detect_first_return(p, START, LENGTH).detected


def test_sample_range():
    assert sample_range(0, 2.0, 30.0, 600) == 2.0
    assert sample_range(100, 0.0, 30.0, 600) == pytest.approx(5.0)
