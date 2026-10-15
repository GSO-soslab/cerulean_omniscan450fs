"""Preprocessing, a detector and a reference, put together.

Profiles are echo strength in dB, nearest sample first. Sample i lies at
    start_m + i * length_m / num_samples
which follows the SDK's "even intervals across the scan region". Whether the first sample
sits at the start or the centre of its bin is not documented; check it on hardware.

Reported powers are after preprocessing.
"""

from dataclasses import asdict, dataclass, field, fields
from typing import Dict

import numpy as np

from .base import DETECTORS, CommonConfig, Detection, Prepared
from .preprocessing import Preprocessing
from .reference import REFERENCES, reference_range


def sample_range(index, start_m, length_m, num_samples):
    """Range of sample `index` in metres."""
    return start_m + index * length_m / num_samples


@dataclass
class FinderConfig:
    method: str = 'threshold'
    reference: str = 'leading_edge'
    common: CommonConfig = field(default_factory=CommonConfig)
    preprocessing: Preprocessing = field(default_factory=Preprocessing)
    # settings of each method by name, a method that is absent uses its defaults
    method_params: Dict[str, object] = field(default_factory=dict)

    def params_for(self, name):
        return self.method_params.get(name, DETECTORS[name].Params())

    def validate(self):
        """Raise ValueError if anything is unusable, including methods that are not selected."""
        if self.method not in DETECTORS:
            raise ValueError(f'method must be one of {sorted(DETECTORS)}, got {self.method!r}')
        if self.reference not in REFERENCES:
            raise ValueError(f'reference must be one of {REFERENCES}, got {self.reference!r}')
        self.common.validate()
        self.preprocessing.validate()
        for name in DETECTORS:
            self.params_for(name).validate()

    @classmethod
    def from_flat(cls, flat):
        """Build from a flat dict, the way the node's parameters arrive.

        Keys: `method`, `reference`, the fields of CommonConfig and Preprocessing by name,
        and `<method>.<field>` for a method's own settings, for example `cfar.pfa`. Unknown
        keys are an error, so a typo is not silently ignored.
        """
        common_keys = {f.name for f in fields(CommonConfig)}
        pre_keys = {f.name for f in fields(Preprocessing)}
        common, pre, own = {}, {}, {name: {} for name in DETECTORS}
        method, reference = None, None
        for key, value in flat.items():
            if key == 'method':
                method = value
            elif key == 'reference':
                reference = value
            elif key in common_keys:
                common[key] = value
            elif key in pre_keys:
                pre[key] = value
            elif '.' in key and key.split('.', 1)[0] in DETECTORS:
                name, param = key.split('.', 1)
                own[name][param] = value
            else:
                raise ValueError(f'unknown detection setting {key!r}')
        method_params = {}
        for name, values in own.items():
            try:
                method_params[name] = DETECTORS[name].Params(**values)
            except TypeError as e:
                raise ValueError(f'{name}: {e}') from None
        cfg = cls(method=method or cls.method, reference=reference or cls.reference,
                  common=CommonConfig(**common), preprocessing=Preprocessing(**pre),
                  method_params=method_params)
        cfg.validate()
        return cfg


def default_flat():
    """Every detection setting with its default, in the flat form `from_flat` reads."""
    flat = {'method': FinderConfig.method, 'reference': FinderConfig.reference}
    flat.update(asdict(CommonConfig()))
    flat.update(asdict(Preprocessing()))
    for name, detector in DETECTORS.items():
        for param, value in asdict(detector.Params()).items():
            flat[f'{name}.{param}'] = value
    return flat


class RangeFinder:
    """Finds the first-return range in one profile at a time."""

    def __init__(self, config=None):
        self.config = config or FinderConfig()
        self.config.validate()
        self.detector = DETECTORS[self.config.method](self.config.params_for(self.config.method))

    def detect(self, power_db, start_m, length_m):
        """First return in one profile.

        power_db: sequence of echo strengths in dB, nearest sample first.
        start_m, length_m: scanned window, in metres from the transducer.
        """
        cfg = self.config
        raw = np.asarray(power_db, dtype=float)
        n = raw.size
        if n == 0 or length_m <= 0.0:
            return Detection()

        res = length_m / n
        ranges = start_m + np.arange(n) * res
        p = cfg.preprocessing.apply(raw, ranges)

        gate = np.isfinite(p) & (ranges >= cfg.common.min_range_m)
        if cfg.common.max_range_m > 0.0:
            gate &= ranges <= cfg.common.max_range_m
        if not gate.any():
            return Detection()
        prepared = Prepared(p, ranges, gate, float(np.median(p[gate])))

        region = self.detector.find(prepared, cfg.common)
        if region is None:
            return Detection()

        peak = float(p[region.start:region.end].max())
        range_m = reference_range(p, ranges, region, cfg.reference)
        return Detection(detected=True, range_m=range_m, raw_range_m=range_m,
                         peak_power_db=peak, threshold_db=float(region.threshold_db),
                         snr_db=peak - prepared.noise_db, width_m=(region.end - region.start) * res)
