"""Tests for dessem_dashboard.charts.specs."""

from __future__ import annotations

import importlib
from collections import Counter

import dessem_dashboard.charts as charts_pkg
from dessem_dashboard.charts.registry import ChartGroup, ChartKind, ChartRegistry, EntitySelector
from dessem_dashboard.charts.specs import SPECS, register_default_specs
from dessem_dashboard.data.schemas import FALLBACK_UNITS

_ENABLED_KEYS_IN_ORDER = (
    "GTER_SIN",
    "GHID_SIN",
    "GUNS_SIN",
    "EARMF_SIN",
    "VARMF_SIN",
    "MER_SBM",
    "GHID_SBM",
    "GTER_SBM",
    "GUNS_SBM",
    "CMO_SBM",
    "VARMF_SBM",
    "INT_SBP",
    "GHID_UHE",
    "QTUR_UHE",
    "QVER_UHE",
    "VARMF_UHE",
    "VARPF_UHE",
    "QDEF_UHE",
    "QAFL_UHE",
    "QINC_UHE",
    "GTER_UTE",
    "CUSTOS",
    "TEMPO",
)

_AMBIGUITY_PAIR_KEYS = ("VARMF_UHE", "VARPF_UHE", "QAFL_UHE", "QINC_UHE")


def _fresh_registry() -> ChartRegistry:
    registry = ChartRegistry()
    register_default_specs(registry)
    return registry


def test_enabled_specs_returns_exact_key_tuple_in_appendix_order() -> None:
    registry = _fresh_registry()
    assert tuple(item.key for item in registry.enabled_specs()) == _ENABLED_KEYS_IN_ORDER


def test_all_specs_has_forty_two_entries_with_nineteen_disabled() -> None:
    registry = _fresh_registry()
    all_specs = registry.all_specs()
    assert len(all_specs) == 42
    assert sum(1 for item in all_specs if not item.enabled) == 19


def test_every_spec_unit_matches_fallback_units_for_its_source_file() -> None:
    for chart_spec in SPECS:
        assert chart_spec.unit == FALLBACK_UNITS[chart_spec.source_file]


def test_enabled_specs_group_sizes_match_appendix_a6() -> None:
    registry = _fresh_registry()
    counts = Counter(item.group for item in registry.enabled_specs())
    assert counts == Counter(
        {
            ChartGroup.SIN: 5,
            ChartGroup.SBM: 6,
            ChartGroup.SBP: 1,
            ChartGroup.UHE: 8,
            ChartGroup.UTE: 1,
            ChartGroup.EXECUCAO: 2,
        }
    )


def test_only_execucao_specs_are_scalar_by_deck_with_no_level() -> None:
    registry = _fresh_registry()
    all_specs = registry.all_specs()
    scalar_specs = [item for item in all_specs if item.kind is ChartKind.SCALAR_BY_DECK]
    assert {item.key for item in scalar_specs} == {"CUSTOS", "TEMPO"}
    assert all(item.level is None for item in scalar_specs)
    assert all(item.group is ChartGroup.EXECUCAO for item in scalar_specs)
    other_specs = [item for item in all_specs if item.key not in {"CUSTOS", "TEMPO"}]
    assert all(item.kind is ChartKind.SERIES for item in other_specs)
    assert all(item.level is not None for item in other_specs)


def test_every_uhe_spec_uses_hydro_plant_selector() -> None:
    registry = _fresh_registry()
    uhe_specs = [item for item in registry.all_specs() if item.group is ChartGroup.UHE]
    assert len(uhe_specs) == 12
    assert all(item.selector is EntitySelector.HYDRO_PLANT for item in uhe_specs)


def test_gter_ute_uses_thermal_plant_selector() -> None:
    registry = _fresh_registry()
    assert registry.spec("GTER_UTE").selector is EntitySelector.THERMAL_PLANT


def test_every_enabled_series_source_file_equals_its_key() -> None:
    registry = _fresh_registry()
    series_specs = [item for item in registry.enabled_specs() if item.kind is ChartKind.SERIES]
    assert all(item.source_file == item.key for item in series_specs)


def test_ambiguity_pair_specs_carry_non_empty_notes() -> None:
    registry = _fresh_registry()
    for key in _AMBIGUITY_PAIR_KEYS:
        assert registry.spec(key).notes != ""


def test_enabled_specs_disabled_argument_excludes_both_ambiguity_candidates() -> None:
    registry = _fresh_registry()
    remaining = registry.enabled_specs(disabled=("VARPF_UHE", "QINC_UHE"))
    assert len(remaining) == 21
    assert "VARPF_UHE" not in {item.key for item in remaining}
    assert "QINC_UHE" not in {item.key for item in remaining}


def test_register_default_specs_called_twice_on_singleton_does_not_raise() -> None:
    register_default_specs()
    register_default_specs()
    from dessem_dashboard.charts.registry import all_specs

    assert len(all_specs()) == 42


def test_reloading_charts_package_twice_keeps_forty_two_specs() -> None:
    importlib.reload(charts_pkg)
    importlib.reload(charts_pkg)
    from dessem_dashboard.charts.registry import all_specs

    assert len(all_specs()) == 42
