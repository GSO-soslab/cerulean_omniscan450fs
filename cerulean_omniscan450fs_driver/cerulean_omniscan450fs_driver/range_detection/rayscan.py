"""A first-return detection as a one-ray sensor_msgs/LaserScan.

The sonar has one fixed beam, so there is one bearing and one range per ping. A LaserScan
holds one range per bearing, so this is a scan with a single ray. A fan of rays needs the
beam to sweep, with the bearing of each ping taken from outside the sonar (vehicle yaw or a
pan mount).

The scan uses angle_min = angle_max = 0 and angle_increment = the beam width, so the usual
count (angle_max - angle_min) / angle_increment + 1 is one. ranges[0] is the first-return
range, or inf when nothing was detected; intensities[0] is that return's peak power in dB
(LaserScan intensities have no fixed unit), or 0 when nothing was detected.
"""

import math
from dataclasses import dataclass
from typing import List


@dataclass
class RayScan:
    angle_min: float
    angle_max: float
    angle_increment: float
    range_min: float
    range_max: float
    ranges: List[float]
    intensities: List[float]


def single_ray_scan(detection, range_min, range_max, beam_width_rad):
    """One-ray scan for a Detection."""
    return RayScan(
        angle_min=0.0, angle_max=0.0, angle_increment=float(beam_width_rad),
        range_min=float(range_min), range_max=float(range_max),
        ranges=[float(detection.range_m) if detection.detected else math.inf],
        intensities=[float(detection.peak_power_db) if detection.detected else 0.0])
