"""First-return detection on a single Omniscan 450 FS power profile.

Pure numpy, no ROS and no sonar dependency, so it can be tested on synthetic or
recorded profiles.

Method (version 1):
  1. Estimate the ping's noise floor as the median power inside the range gate.
  2. Threshold = max(noise floor + min_snr_db, min_power_db).
  3. The first return is the first run of at least `min_width_samples` consecutive
     samples at or above the threshold, inside the range gate. Its range is the
     leading edge of the run, the usual way to time a bottom or target return.

Not handled yet: range-dependent gain compensation, adaptive (CFAR) thresholds and
tracking across pings. Those need real profiles to tune against.

Sample i of a profile with `num_samples` samples lies at
    start_m + i * length_m / num_samples
(nearest sample first). This follows the SDK description of "even intervals across
the scan region"; whether the first sample sits at the start or the centre of its bin
is not documented and should be checked on hardware.
"""

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class DetectorConfig:
    min_range_m: float = 1.0      # ignore anything closer (near field, ringing)
    max_range_m: float = 0.0      # ignore anything farther, 0 = no limit
    min_snr_db: float = 10.0      # first return must exceed the noise floor by this much
    min_power_db: float = -math.inf   # and be at least this strong in absolute terms
    min_width_samples: int = 2    # reject isolated single-sample spikes


@dataclass
class Detection:
    detected: bool = False
    range_m: float = math.nan
    peak_power_db: float = math.nan
    threshold_db: float = math.nan
    snr_db: float = math.nan
    width_m: float = math.nan


def sample_range(index, start_m, length_m, num_samples):
    """Range of sample `index` in metres."""
    return start_m + index * length_m / num_samples


def detect_first_return(power_db, start_m, length_m, config=None):
    """Find the first return in one profile.

    power_db: sequence of echo strengths in dB, nearest sample first.
    start_m, length_m: scanned window, in metres from the transducer.
    """
    config = config or DetectorConfig()
    power = np.asarray(power_db, dtype=float)
    n = power.size
    if n == 0 or length_m <= 0.0:
        return Detection()

    res = length_m / n
    idx = np.arange(n)
    ranges = start_m + idx * res

    gate = np.isfinite(power) & (ranges >= config.min_range_m)
    if config.max_range_m > 0.0:
        gate &= ranges <= config.max_range_m
    if not gate.any():
        return Detection()

    noise_floor = float(np.median(power[gate]))
    threshold = max(noise_floor + config.min_snr_db, config.min_power_db)
    above = gate & (power >= threshold)

    min_width = max(1, int(config.min_width_samples))
    i = 0
    while i < n:
        if not above[i]:
            i += 1
            continue
        j = i
        while j < n and above[j]:
            j += 1
        if j - i >= min_width:
            peak = float(power[i:j].max())
            return Detection(
                detected=True,
                range_m=float(ranges[i]),
                peak_power_db=peak,
                threshold_db=threshold,
                snr_db=peak - noise_floor,
                width_m=(j - i) * res,
            )
        i = j

    return Detection(threshold_db=threshold)
