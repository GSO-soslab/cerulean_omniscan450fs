"""Optional preprocessing applied to a profile before detection.

TVG: Ferretti et al., "Seabed classification using a single beam echosounder", eq. (2).
Smoothing: moving average (Al-Rawi et al., OCEANS 2017) or Hanning window (Bourguignon et
al., ICES J. Mar. Sci. 66:1015, 2009).

Smoothing spreads an edge over its window in both directions, so a threshold crossing on a
smoothed profile differs from the raw one by up to about half the window: earlier for a low
threshold, later for one near the top of the return.
"""

from dataclasses import dataclass

import numpy as np

SMOOTHING = ('none', 'moving_average', 'hann')


def tvg_correction_db(ranges_m, spreading_db=20.0, absorption_db_per_m=0.0, ref_range_m=1.0):
    """Gain in dB that compensates spreading and absorption loss.

    spreading_db * log10(R / R_ref) + 2 * alpha * R, Ferretti et al. eq. (2) with their
    20 dB per decade for spreading. A target echo travels out and back, which can call for
    a larger spreading term (40); it is left as a setting.
    """
    r = np.maximum(np.asarray(ranges_m, dtype=float), 1e-6)
    return spreading_db * np.log10(r / ref_range_m) + 2.0 * absorption_db_per_m * r


def smooth_profile(power_db, kind, n):
    """Smooth a profile, same length, edges extended. NaN samples stay NaN."""
    p = np.asarray(power_db, dtype=float)
    if kind == 'none' or n <= 1 or p.size == 0:
        return p
    finite = np.isfinite(p)
    if not finite.any():
        return p
    filled = p.copy()
    if not finite.all():
        idx = np.arange(p.size)
        filled[~finite] = np.interp(idx[~finite], idx[finite], p[finite])
    if kind == 'moving_average':
        kernel = np.ones(n)
    else:   # hann, without the zero end weights
        kernel = np.hanning(n + 2)[1:-1]
    kernel = kernel / kernel.sum()
    padded = np.pad(filled, (n // 2, n - 1 - n // 2), mode='edge')
    out = np.convolve(padded, kernel, mode='valid')
    out[~finite] = np.nan
    return out


@dataclass
class Preprocessing:
    tvg_enabled: bool = False
    tvg_spreading_db: float = 20.0         # dB per decade of range
    tvg_absorption_db_per_m: float = 0.0   # alpha, one-way
    tvg_ref_range_m: float = 1.0
    smoothing: str = 'none'
    smooth_samples: int = 5

    def validate(self):
        if self.smoothing not in SMOOTHING:
            raise ValueError(f'smoothing must be one of {SMOOTHING}, got {self.smoothing!r}')
        if self.smooth_samples < 1:
            raise ValueError('smooth_samples must be >= 1')
        if self.tvg_ref_range_m <= 0.0:
            raise ValueError('tvg_ref_range_m must be > 0')

    def apply(self, power_db, ranges_m):
        p = np.asarray(power_db, dtype=float)
        if self.tvg_enabled:
            p = p + tvg_correction_db(ranges_m, self.tvg_spreading_db,
                                      self.tvg_absorption_db_per_m, self.tvg_ref_range_m)
        return smooth_profile(p, self.smoothing, self.smooth_samples)
