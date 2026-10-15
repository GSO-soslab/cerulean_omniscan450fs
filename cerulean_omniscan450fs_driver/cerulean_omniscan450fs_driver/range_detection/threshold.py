"""Threshold detector.

Source: amplitude detection, IHO publication C-13 ch. 3 (v1.05, Dec. 2010); Bourguignon et
al., ICES J. Mar. Sci. 66:1015, 2009. The 10 dB default follows the value reported for
water-column and bottom echoes once transmission loss is compensated (de Moustier, OCEANS
2013, as cited by Al-Rawi et al., OCEANS 2017; the original was not read).
"""

from dataclasses import dataclass

from .base import FirstReturnDetector, Region, first_run, register


@dataclass
class ThresholdParams:
    min_snr_db: float = 10.0    # a return must be this far above the ping's noise floor

    def validate(self):
        pass


@register
class ThresholdDetector(FirstReturnDetector):
    """First run of samples above the noise floor (median power) plus min_snr_db."""

    name = 'threshold'
    Params = ThresholdParams

    def find(self, prepared, common):
        threshold = max(prepared.noise_db + self.params.min_snr_db, common.min_power_db)
        run = first_run(prepared.gate & (prepared.power_db >= threshold), common.min_width_samples)
        return None if run is None else Region(run[0], run[1], threshold)
