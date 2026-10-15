import math

from cerulean_omniscan450fs_driver.range_detection import Detection, RangeTracker


def det(range_m):
    return Detection(detected=not math.isnan(range_m), range_m=range_m, raw_range_m=range_m,
                     peak_power_db=-40.0, threshold_db=-70.0, snr_db=30.0, width_m=0.5)


def test_window_one_is_a_pass_through():
    t = RangeTracker(1)
    d = det(12.0)
    assert t.update(d) is d


def test_rejects_a_single_spike_and_keeps_the_raw_value():
    t = RangeTracker(5)
    out = [t.update(det(r)) for r in (12.0, 12.0, 12.0, 3.0, 12.0, 12.0, 12.0)]
    assert [o.range_m for o in out[3:]] == [12.0, 12.0, 12.0, 12.0]
    assert out[3].raw_range_m == 3.0


def test_bridges_a_dropout_and_gives_up_on_a_long_one():
    t = RangeTracker(5)
    for _ in range(5):
        t.update(det(12.0))
    bridged = t.update(det(math.nan))
    assert bridged.detected and bridged.range_m == 12.0 and math.isnan(bridged.raw_range_m)
    results = [t.update(det(math.nan)).detected for _ in range(4)]
    assert results == [True, False, False, False]              # fewer than 3 of 5 remain


def test_needs_a_majority_before_reporting():
    t = RangeTracker(5)
    assert not t.update(det(12.0)).detected                    # 1 of 5 seen
    assert not t.update(det(12.0)).detected
    assert t.update(det(12.0)).detected                        # 3 of 5


def test_follows_a_real_change_after_about_half_a_window():
    t = RangeTracker(5)
    for _ in range(5):
        t.update(det(12.0))
    out = [t.update(det(8.0)).range_m for _ in range(5)]
    assert out == [12.0, 12.0, 8.0, 8.0, 8.0]
