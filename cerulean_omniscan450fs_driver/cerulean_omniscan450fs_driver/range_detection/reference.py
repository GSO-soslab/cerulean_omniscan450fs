"""Where inside the first return the range is placed.

The three amplitude detection methods of IHO publication C-13, chapter 3 (version 1.05,
Dec. 2010): leading edge (first arrival), maximum amplitude, centre of mass. The IHO text
notes the leading edge degrades as the incidence angle grows and the rise becomes less
sharp, which is likely for a 50 deg tall beam at grazing incidence.
"""

import numpy as np

REFERENCES = ('leading_edge', 'peak', 'centroid')


def reference_range(power_db, ranges_m, region, kind):
    """Range in metres of `region` (start..end-1) for the chosen reference."""
    if kind == 'leading_edge':
        return float(ranges_m[region.start])
    if kind == 'peak':
        return float(ranges_m[region.start + int(np.argmax(power_db[region.start:region.end]))])
    if kind == 'centroid':
        w = 10.0 ** (power_db[region.start:region.end] / 20.0)      # amplitude weights
        return float(np.sum(w * ranges_m[region.start:region.end]) / np.sum(w))
    raise ValueError(f'reference must be one of {REFERENCES}, got {kind!r}')
