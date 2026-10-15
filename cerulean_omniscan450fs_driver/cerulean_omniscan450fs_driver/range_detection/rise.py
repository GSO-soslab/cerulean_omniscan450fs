"""Rise detector.

Source: Al-Rawi, Elmgren, Frasheri, Curuklu, Yuan, Martinez, Bastos, Rodriguez, Pinto,
"Algorithms for the Detection of First Bottom Returns and Objects in the Water Column in
Sidescan Sonar Images", OCEANS 2017, doi:10.1109/OCEANSE.2017.8084587 (moving-average
method): filter the signal, take the difference between consecutive points, and report the
first return where it exceeds a threshold. The paper uses a 50-point window on sidescan
data; use the `smoothing` setting here, a smoothed profile spreads a rise over the window.
"""

from dataclasses import dataclass

import numpy as np

from .base import FirstReturnDetector, Region, register


@dataclass
class RiseParams:
    rise_db: float = 6.0    # minimum rise between consecutive (smoothed) samples

    def validate(self):
        if self.rise_db <= 0.0:
            raise ValueError('rise rise_db must be > 0')


@register
class RiseDetector(FirstReturnDetector):
    """First sample where the profile rises by rise_db over the previous sample."""

    name = 'rise'
    Params = RiseParams

    def find(self, prepared, common):
        p, gate = prepared.power_db, prepared.gate
        finite = np.isfinite(p)
        step = np.diff(p)        # step[i] = p[i + 1] - p[i], NaN where either sample is NaN
        with np.errstate(invalid='ignore'):
            starts = np.flatnonzero((step >= self.params.rise_db) & gate[1:] & finite[1:]
                                    & finite[:-1] & (p[1:] >= common.min_power_db)) + 1
        for start in starts:
            baseline = p[start - 1]
            # Not in the paper: the return lasts while the signal stays above half the
            # detection step over the level it rose from.
            keep = finite & gate & (p >= baseline + self.params.rise_db / 2.0)
            end = start
            while end < p.size and keep[end]:
                end += 1
            if end - start >= common.min_width_samples:
                return Region(int(start), int(end), float(baseline + self.params.rise_db))
        return None
