"""CFAR detector.

Source: the constant false alarm rate principle for sonar, Abu & Diamant, "CFAR detection
algorithm for objects in sonar images", IET Radar, Sonar & Navigation 14(11):1757, 2020. This
is the textbook 1-D cell-averaging form, not their K-distribution estimator, which works on
2-D image blocks.

Each sample is tested against alpha times the mean of the reference cells before it. The
reference cells are on the nearer side only: a cell-averaging threshold that also uses the
far side is raised by the return itself and misses it.
"""

from dataclasses import dataclass

import numpy as np

from .base import FirstReturnDetector, Region, first_run, register

CFAR_MIN_CELLS = 4   # a threshold from fewer valid reference cells is not trusted


@dataclass
class CfarParams:
    train_cells: int = 20      # reference cells, taken from the nearer side
    guard_cells: int = 2       # cells skipped next to the cell under test
    pfa: float = 1e-3          # design false-alarm probability per cell

    def validate(self):
        if self.train_cells < CFAR_MIN_CELLS:
            raise ValueError(f'cfar train_cells must be >= {CFAR_MIN_CELLS}')
        if self.guard_cells < 0:
            raise ValueError('cfar guard_cells must be >= 0')
        if not 0.0 < self.pfa < 1.0:
            raise ValueError('cfar pfa must be between 0 and 1')


def cfar_alpha(num_cells, pfa):
    """Threshold multiplier of cell-averaging CFAR for exponential (square-law) noise."""
    n = np.asarray(num_cells, dtype=float)
    return n * (pfa ** (-1.0 / n) - 1.0)


def cfar_mask(power_db, gate, params, min_power_db=-1000.0):
    """Per-sample CFAR decision, with the local threshold and noise level (both in dB).

    Reference cells are averaged on linear power. The false-alarm probability is exact for
    exponentially distributed noise power; real backgrounds are not, so `pfa` is a design
    value to tune and not a guarantee. A cell with fewer than CFAR_MIN_CELLS valid reference
    cells (the start of the profile) is not tested.
    """
    p = np.asarray(power_db, dtype=float)
    n = p.size
    finite = np.isfinite(p)
    lin = np.where(finite, 10.0 ** (np.where(finite, p, 0.0) / 10.0), 0.0)
    csum = np.concatenate(([0.0], np.cumsum(lin)))
    ccnt = np.concatenate(([0], np.cumsum(finite)))

    i = np.arange(n)
    lo = np.clip(i - params.guard_cells - params.train_cells, 0, n)
    hi = np.clip(i - params.guard_cells, 0, n)
    total = csum[hi] - csum[lo]
    count = (ccnt[hi] - ccnt[lo]).astype(float)

    testable = count >= CFAR_MIN_CELLS
    safe_count = np.where(testable, count, 1.0)
    mean = total / safe_count
    threshold_lin = cfar_alpha(safe_count, params.pfa) * mean
    with np.errstate(divide='ignore'):
        threshold_db = 10.0 * np.log10(threshold_lin)
        noise_db = 10.0 * np.log10(mean)
    above = testable & gate & finite & (lin >= threshold_lin) & (p >= min_power_db)
    return above, threshold_db, noise_db


@register
class CfarDetector(FirstReturnDetector):
    """First run of samples above their local CFAR threshold."""

    name = 'cfar'
    Params = CfarParams

    def find(self, prepared, common):
        above, threshold_db, _ = cfar_mask(prepared.power_db, prepared.gate, self.params,
                                           common.min_power_db)
        run = first_run(above, common.min_width_samples)
        if run is None:
            return None
        start = run[0]
        threshold = float(threshold_db[start])
        # The return's own samples soon enter the reference window and raise the local
        # threshold, which would cut a strong return short. Its extent is taken against the
        # threshold at its first sample, before that happened.
        p, gate = prepared.power_db, prepared.gate
        end = start
        while end < p.size and gate[end] and p[end] >= threshold:
            end += 1
        return Region(start, end, threshold)
