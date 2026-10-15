"""First-return range from one Omniscan 450 FS power profile.

The sonar only reports echo strength, so the range is found on the profile. Each method is a
class in its own module and carries the short citation of its source:

  threshold  threshold.py   amplitude detection, IHO C-13
  peak       peak.py        Ferretti et al., single beam seabed pick
  cfar       cfar.py        CFAR principle, Abu & Diamant 2020
  rise       rise.py        Al-Rawi et al. 2017, moving-average method

Around them: preprocessing.py (range correction, smoothing), reference.py (where inside the
return the range is placed, IHO C-13), tracker.py (median over pings), finder.py (puts them
together).
"""

# Importing the detector modules registers them.
from . import cfar, peak, rise, threshold  # noqa: F401
from .base import DETECTORS, CommonConfig, Detection, FirstReturnDetector, Region, register
from .finder import FinderConfig, RangeFinder, default_flat, sample_range
from .preprocessing import SMOOTHING, Preprocessing, smooth_profile, tvg_correction_db
from .reference import REFERENCES, reference_range
from .tracker import RangeTracker

__all__ = [
    'DETECTORS', 'REFERENCES', 'SMOOTHING', 'CommonConfig', 'Detection', 'FinderConfig',
    'FirstReturnDetector', 'Preprocessing', 'RangeFinder', 'RangeTracker', 'Region',
    'default_flat', 'reference_range', 'register', 'sample_range', 'smooth_profile',
    'tvg_correction_db',
]
