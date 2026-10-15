"""Shared by the tests: synthetic profiles and a short way to build a RangeFinder."""

import numpy as np

from cerulean_omniscan450fs_driver.range_detection import FinderConfig, RangeFinder

START, LENGTH, N = 0.0, 30.0, 600     # 5 cm per sample
RES = LENGTH / N


def profile(bumps=(), noise_db=-80.0, jitter=1.0, seed=0):
    """Noise plus flat-topped returns given as (range_m, width_m, level_db)."""
    rng = np.random.default_rng(seed)
    p = noise_db + rng.normal(0.0, jitter, N)
    for range_m, width_m, level_db in bumps:
        i0 = int(round(range_m / RES))
        p[i0:i0 + max(1, int(round(width_m / RES)))] = level_db
    return p


def finder(method='threshold', **flat):
    """A RangeFinder from flat settings, for example finder('cfar', **{'cfar.pfa': 1e-2})."""
    return RangeFinder(FinderConfig.from_flat({'method': method, **flat}))


def detect(p, method='threshold', start_m=START, length_m=LENGTH, **flat):
    return finder(method, **flat).detect(p, start_m, length_m)
