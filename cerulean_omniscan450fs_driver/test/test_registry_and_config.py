"""Every method is registered, configured the same way, and the YAML matches the defaults."""

from pathlib import Path

import pytest
import yaml

from cerulean_omniscan450fs_driver.range_detection import (
    DETECTORS, FinderConfig, FirstReturnDetector, RangeFinder, default_flat)

METHODS = ['threshold', 'peak', 'cfar', 'rise']
YAML = Path(__file__).parents[1] / 'config' / 'omniscan450fs_driver.yaml'


def test_the_four_methods_are_registered():
    assert sorted(DETECTORS) == sorted(METHODS)


@pytest.mark.parametrize('name', METHODS)
def test_each_method_follows_the_interface(name):
    cls = DETECTORS[name]
    assert issubclass(cls, FirstReturnDetector) and cls.name == name
    assert cls.__doc__ and cls.__module__.endswith(f'.{name}')      # one module per method
    cls(cls.Params())                                               # defaults are valid


def test_default_flat_round_trips():
    flat = default_flat()
    cfg = FinderConfig.from_flat(flat)
    assert default_flat() == flat
    assert cfg.method == 'threshold' and cfg.reference == 'leading_edge'
    RangeFinder(cfg)


def test_default_flat_names_every_methods_settings():
    flat = default_flat()
    for name, cls in DETECTORS.items():
        for field in cls.Params.__dataclass_fields__:
            assert f'{name}.{field}' in flat


def test_unknown_settings_are_an_error_not_ignored():
    for bad in ('nope', 'cfar.nope', 'nomethod.pfa', 'cfar_pfa'):
        with pytest.raises(ValueError):
            FinderConfig.from_flat({bad: 1})


@pytest.mark.parametrize('flat', [
    {'method': 'nope'}, {'reference': 'nope'}, {'smoothing': 'nope'},
    {'min_width_samples': 0}, {'min_range_m': -1.0}, {'max_range_m': -1.0},
    {'smooth_samples': 0}, {'tvg_ref_range_m': 0.0},
    {'peak.background_samples': 0}, {'peak.margin_db': -1.0},
    {'cfar.train_cells': 3}, {'cfar.guard_cells': -1}, {'cfar.pfa': 0.0}, {'cfar.pfa': 1.0},
    {'rise.rise_db': 0.0},
])
def test_invalid_settings_are_rejected(flat):
    with pytest.raises(ValueError):
        FinderConfig.from_flat(flat)


def test_settings_of_a_method_that_is_not_selected_are_still_checked():
    """So a bad value is refused when it is set, not later when that method is chosen."""
    with pytest.raises(ValueError):
        FinderConfig.from_flat({'method': 'threshold', 'cfar.pfa': 5.0})


def flatten(d, prefix=''):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flatten(v, f'{prefix}{k}.'))
        else:
            out[f'{prefix}{k}'] = v
    return out


def test_yaml_lists_exactly_the_defaults():
    """The documented config must not drift from the code's defaults."""
    params = yaml.safe_load(YAML.read_text())['omniscan450fs_driver']['ros__parameters']
    in_yaml = flatten(params['detection'])
    node_level = {'median_pings': 1, 'field_of_view_rad': pytest.approx(0.01396, abs=1e-5)}
    expected = {**default_flat(), **node_level}
    assert set(in_yaml) == set(expected)
    for key, value in expected.items():
        assert in_yaml[key] == value, key
    FinderConfig.from_flat({k: v for k, v in in_yaml.items() if k not in node_level})
