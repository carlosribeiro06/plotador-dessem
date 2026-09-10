"""Tests for dessem_dashboard.charts.registry."""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError

import pytest

from dessem_dashboard.charts.registry import (
    ChartGroup,
    ChartKind,
    ChartRegistry,
    ChartSpec,
    EntitySelector,
    all_specs,
    enabled_specs,
    spec,
)
from dessem_dashboard.data.schemas import AggregationLevel
from dessem_dashboard.errors import RegistryError


def _spec(key: str, **overrides: object) -> ChartSpec:
    """Build a valid ChartSpec for key, applying overrides on top of sane defaults."""
    fields: dict[str, object] = {
        "key": key,
        "source_file": f"{key}.parquet",
        "level": AggregationLevel.SIN,
        "group": ChartGroup.SIN,
        "kind": ChartKind.SERIES,
        "selector": EntitySelector.NONE,
        "title": f"Título {key}",
        "unit": "MW",
        "enabled": True,
        "notes": "",
    }
    fields.update(overrides)
    return ChartSpec(**fields)  # type: ignore[arg-type]


def test_chart_kind_members_equal_names() -> None:
    assert ChartKind.SERIES == "SERIES"
    assert ChartKind.SCALAR_BY_DECK == "SCALAR_BY_DECK"


def test_entity_selector_members_equal_names() -> None:
    assert EntitySelector.NONE == "NONE"
    assert EntitySelector.SUBMARKET == "SUBMARKET"
    assert EntitySelector.SUBMARKET_PAIR == "SUBMARKET_PAIR"
    assert EntitySelector.HYDRO_PLANT == "HYDRO_PLANT"
    assert EntitySelector.THERMAL_PLANT == "THERMAL_PLANT"


def test_chart_group_members_equal_names() -> None:
    assert ChartGroup.SIN == "SIN"
    assert ChartGroup.SBM == "SBM"
    assert ChartGroup.SBP == "SBP"
    assert ChartGroup.UHE == "UHE"
    assert ChartGroup.UTE == "UTE"
    assert ChartGroup.EXECUCAO == "EXECUCAO"


def test_register_duplicate_key_raises_naming_key() -> None:
    registry = ChartRegistry()
    registry.register(_spec("X"))
    with pytest.raises(RegistryError, match=re.escape("X")):
        registry.register(_spec("X"))


def test_all_specs_returns_specs_in_registration_order() -> None:
    registry = ChartRegistry()
    registry.register(_spec("A"))
    registry.register(_spec("B", enabled=False))
    registry.register(_spec("C"))
    assert tuple(item.key for item in registry.all_specs()) == ("A", "B", "C")


def test_enabled_specs_excludes_disabled_flag_specs_in_order() -> None:
    registry = ChartRegistry()
    registry.register(_spec("A"))
    registry.register(_spec("B", enabled=False))
    registry.register(_spec("C"))
    assert tuple(item.key for item in registry.enabled_specs()) == ("A", "C")


def test_enabled_specs_disabled_argument_excludes_named_key() -> None:
    registry = ChartRegistry()
    registry.register(_spec("A"))
    registry.register(_spec("B", enabled=False))
    registry.register(_spec("C"))
    assert tuple(item.key for item in registry.enabled_specs(disabled=("C",))) == ("A",)


def test_enabled_specs_unknown_disabled_key_raises_naming_key() -> None:
    registry = ChartRegistry()
    registry.register(_spec("A"))
    registry.register(_spec("B", enabled=False))
    registry.register(_spec("C"))
    with pytest.raises(RegistryError, match=re.escape("Z")):
        registry.enabled_specs(disabled=("Z",))


def test_spec_returns_registered_instance() -> None:
    registry = ChartRegistry()
    registered = _spec("A")
    registry.register(registered)
    assert registry.spec("A") is registered


def test_spec_unknown_key_raises_naming_key() -> None:
    registry = ChartRegistry()
    with pytest.raises(RegistryError, match=re.escape("Z")):
        registry.spec("Z")


def test_register_series_kind_without_level_raises_naming_key() -> None:
    registry = ChartRegistry()
    with pytest.raises(RegistryError, match=re.escape("X")):
        registry.register(_spec("X", kind=ChartKind.SERIES, level=None))


def test_register_empty_source_file_raises_naming_key() -> None:
    registry = ChartRegistry()
    with pytest.raises(RegistryError, match=re.escape("X")):
        registry.register(_spec("X", source_file=""))


def test_register_scalar_by_deck_without_level_is_allowed() -> None:
    registry = ChartRegistry()
    registry.register(_spec("CUSTOS", kind=ChartKind.SCALAR_BY_DECK, level=None))
    assert registry.spec("CUSTOS").level is None


def test_chart_spec_is_frozen() -> None:
    frozen = _spec("A")
    with pytest.raises(FrozenInstanceError):
        frozen.enabled = False


def test_chart_spec_unknown_field_raises_type_error() -> None:
    with pytest.raises(TypeError):
        ChartSpec(
            key="A",
            source_file="A.parquet",
            level=AggregationLevel.SIN,
            group=ChartGroup.SIN,
            kind=ChartKind.SERIES,
            selector=EntitySelector.NONE,
            title="Título A",
            unit="MW",
            nots="",
        )


# The three read-only module-level delegates are safe to call directly: they mutate nothing, so no
# registration can leak into the process-wide singleton. `register` is deliberately left untested
# here, because a real call would leak an entry for the rest of the session. The assertions below
# stay valid once ticket-011 populates the singleton at import time.
_UNKNOWN_KEY = "CHAVE_QUE_NUNCA_SERA_REGISTRADA"


def test_module_all_specs_delegate_returns_a_tuple() -> None:
    assert isinstance(all_specs(), tuple)


def test_module_enabled_specs_delegate_rejects_unknown_disabled_key() -> None:
    with pytest.raises(RegistryError, match=re.escape(_UNKNOWN_KEY)):
        enabled_specs(disabled=(_UNKNOWN_KEY,))


def test_module_spec_delegate_raises_on_unknown_key() -> None:
    with pytest.raises(RegistryError, match=re.escape(_UNKNOWN_KEY)):
        spec(_UNKNOWN_KEY)
