"""Peak detector.

Source: Ferretti, Fumagalli, Caccia, Bruzzone, "Seabed classification using a single beam
echosounder" (CNR-ISSIA), bottom-pick algorithm: find the maximum between the minimum and
maximum range, average the data in an interval before and after it, take the smaller average
as the threshold, count the samples around the maximum above it, accept if wide enough.

It finds the strongest return, not the nearest one.
"""

from dataclasses import dataclass

import numpy as np

from .base import FirstReturnDetector, Region, db_mean, register


@dataclass
class PeakParams:
    # Not in the paper: the strongest sample of a profile with no target is noise, so the
    # peak must also stand this far above its background to count.
    min_snr_db: float = 10.0
    # Samples averaged on each side of the maximum. The paper does not give a size.
    background_samples: int = 20
    # Not in the paper. The threshold is the background average, so about half of the
    # neighbouring noise samples sit above it and the return can grow a few samples into the
    # noise. A margin above the average stops that, 0 keeps the paper's behaviour.
    margin_db: float = 0.0

    def validate(self):
        if self.background_samples < 1:
            raise ValueError('peak background_samples must be >= 1')
        if self.margin_db < 0.0:
            raise ValueError('peak margin_db must be >= 0')


@register
class PeakDetector(FirstReturnDetector):
    """Strongest peak in the gate, with a threshold from the level on each side of it."""

    name = 'peak'
    Params = PeakParams

    def find(self, prepared, common):
        p, gate = prepared.power_db, prepared.gate
        idx = np.flatnonzero(gate)
        m = int(idx[np.argmax(p[idx])])

        b = self.params.background_samples
        lo, hi = max(0, m - b), min(p.size, m + 1 + b)
        before = p[lo:m][gate[lo:m]]
        after = p[m + 1:hi][gate[m + 1:hi]]
        means = [db_mean(v) for v in (before, after) if v.size]
        if not means:
            return None
        background = min(means)
        if p[m] - background < self.params.min_snr_db or p[m] < common.min_power_db:
            return None

        threshold = background + self.params.margin_db
        above = gate & (p > threshold)         # "greater than the threshold" in the paper
        start = m
        while start > 0 and above[start - 1]:
            start -= 1
        end = m + 1
        while end < p.size and above[end]:
            end += 1
        if end - start < common.min_width_samples:
            return None
        return Region(start, end, threshold)
