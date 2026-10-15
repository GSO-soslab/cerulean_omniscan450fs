import pytest

from helpers import RES, detect, profile


def test_picks_the_first_of_two_returns():
    p = profile([(12.0, 0.5, -40.0), (20.0, 1.0, -30.0)])
    assert detect(p).range_m == pytest.approx(12.0, abs=RES)


def test_a_weak_return_below_min_snr_is_rejected():
    weak = profile([(10.0, 0.5, -75.0)])                      # about 5 dB above the noise
    assert not detect(weak, **{'threshold.min_snr_db': 10.0}).detected
    assert detect(weak, **{'threshold.min_snr_db': 3.0}).detected


def test_threshold_is_noise_floor_plus_min_snr():
    d = detect(profile([(12.0, 0.5, -40.0)], jitter=0.0), **{'threshold.min_snr_db': 12.0})
    assert d.threshold_db == pytest.approx(-80.0 + 12.0)
    assert d.snr_db == pytest.approx(40.0)
