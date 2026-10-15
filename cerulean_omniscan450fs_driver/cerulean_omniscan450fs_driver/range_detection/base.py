"""Types shared by the first-return detectors, and the registry they add themselves to.

A detector looks at one preprocessed profile and says where the first return starts and
ends (a `Region`, as sample indices). It does not choose the reported range inside that
region, that is `reference.py`.

To add a method: write a class in its own module that subclasses `FirstReturnDetector`,
give it a `name`, a `Params` dataclass and a `find()`, decorate it with `@register`, and
import the module in `__init__.py`.
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Dict, Optional, Type

import numpy as np


@dataclass
class CommonConfig:
    """Settings every method honours."""
    min_range_m: float = 1.0       # ignore anything closer (near field, ringing)
    max_range_m: float = 0.0       # ignore anything farther, 0 = no limit
    min_power_db: float = -1000.0  # absolute floor for a detection, very low = off
    min_width_samples: int = 2     # a return must be at least this wide

    def validate(self):
        if self.min_range_m < 0.0 or self.max_range_m < 0.0:
            raise ValueError('range gates must be >= 0')
        if self.min_width_samples < 1:
            raise ValueError('min_width_samples must be >= 1')


@dataclass
class Prepared:
    """One profile after preprocessing, with the range gate applied."""
    power_db: np.ndarray       # echo strength [dB]
    ranges_m: np.ndarray       # range of each sample
    gate: np.ndarray           # True where a detection is allowed (finite, inside the gate)
    noise_db: float            # median power inside the gate


@dataclass
class Region:
    """The first return: samples start..end-1."""
    start: int
    end: int                   # exclusive
    threshold_db: float        # the level the method applied at the first sample


@dataclass
class Detection:
    detected: bool = False
    range_m: float = math.nan         # after the optional median over pings
    raw_range_m: float = math.nan     # this ping alone
    peak_power_db: float = math.nan   # strongest sample of the first return
    threshold_db: float = math.nan    # threshold the method applied at the first return
    snr_db: float = math.nan          # peak power minus the ping's noise floor
    width_m: float = math.nan         # extent of the first return


class FirstReturnDetector(ABC):
    """Finds the first return in a prepared profile."""

    name: ClassVar[str]
    Params: ClassVar[Type]     # a dataclass with defaults and a validate() method

    def __init__(self, params=None):
        self.params = params if params is not None else self.Params()
        self.params.validate()

    @abstractmethod
    def find(self, prepared: Prepared, common: CommonConfig) -> Optional[Region]:
        """The first return, or None."""


DETECTORS: Dict[str, Type[FirstReturnDetector]] = {}


def register(cls):
    """Class decorator that makes a detector available by name."""
    DETECTORS[cls.name] = cls
    return cls


def runs(mask):
    """Yield (start, end) of each run of True in `mask`, end exclusive."""
    padded = np.concatenate(([False], mask, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    for a, b in zip(edges[0::2], edges[1::2]):
        yield int(a), int(b)


def first_run(mask, min_width):
    """First run of True at least `min_width` long, as (start, end), or None."""
    for a, b in runs(mask):
        if b - a >= min_width:
            return a, b
    return None


def db_mean(values_db):
    """Mean of dB values, taken on linear power."""
    return 10.0 * math.log10(np.mean(10.0 ** (np.asarray(values_db) / 10.0)))
