"""Median of the first-return range over the last few pings.

After Al-Rawi et al., OCEANS 2017, who median-filter the along-track first returns to
remove spikes from objects in the water column. (Bourguignon et al., ICES J. Mar. Sci.
66:1015, 2009 use a particle filter on a seabed model for the same purpose, which is not
done here.)
"""

import math
from collections import deque
from dataclasses import replace

import numpy as np


class RangeTracker:
    """Median of the first-return range over the last `window` pings.

    A ping with no detection counts as a miss. The median is reported when more than half
    of the window detected something, so a single spike (a fish, debris) is rejected and a
    single dropout is bridged. When the current ping itself has no detection but the
    window still qualifies, the median range is reported and the other fields stay NaN.
    The output lags the true range by about window/2 pings. window=1 passes through.
    """

    def __init__(self, window=1):
        self.window = max(1, int(window))
        self._history = deque(maxlen=self.window)

    def update(self, detection):
        self._history.append(detection.raw_range_m if detection.detected else math.nan)
        if self.window == 1:
            return detection
        seen = [r for r in self._history if not math.isnan(r)]
        if len(seen) < self.window // 2 + 1:
            return replace(detection, detected=False, range_m=math.nan)
        return replace(detection, detected=True, range_m=float(np.median(seen)))
