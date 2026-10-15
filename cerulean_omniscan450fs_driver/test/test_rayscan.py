import math

import pytest

from cerulean_omniscan450fs_driver.range_detection import Detection, single_ray_scan

BEAM = math.radians(0.8)


def detection():
    return Detection(detected=True, range_m=12.0, raw_range_m=12.0, peak_power_db=-40.0,
                     threshold_db=-70.0, snr_db=40.0, width_m=0.5)


def test_a_detection_is_one_ray_with_its_range_and_peak_power():
    s = single_ray_scan(detection(), 1.0, 30.0, BEAM)
    assert s.ranges == [12.0] and s.intensities == [-40.0]
    assert (s.range_min, s.range_max) == (1.0, 30.0)


def test_no_detection_is_inf_with_zero_intensity():
    s = single_ray_scan(Detection(), 1.0, 30.0, BEAM)
    assert s.ranges == [math.inf] and s.intensities == [0.0]


def test_the_ray_count_formula_gives_one():
    """LaserScan consumers count rays as (angle_max - angle_min) / angle_increment + 1."""
    s = single_ray_scan(detection(), 1.0, 30.0, BEAM)
    assert s.angle_increment == pytest.approx(BEAM) and s.angle_increment > 0.0
    assert round((s.angle_max - s.angle_min) / s.angle_increment) + 1 == len(s.ranges) == 1
