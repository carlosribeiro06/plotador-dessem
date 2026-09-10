"""Tests for dessem_dashboard.models.store."""

from __future__ import annotations

from datetime import date
from types import MappingProxyType

import pandas as pd
import pytest

from dessem_dashboard.data.registries import Registries
from dessem_dashboard.errors import StoreError
from dessem_dashboard.models.store import DashboardData, EntityRef, TimeAxis

_SCENARIOS: tuple[str, ...] = ("caso_a", "caso_b")
_REFERENCE = "caso_a"
_DECK_DATE = date(2024, 3, 3)
_DECK_AXIS_LENGTH = 4
_CHAINED_AXIS_LENGTH = 8
_BASE = pd.Timestamp("2024-03-03T00:00:00", tz="UTC")


def _empty_registries() -> Registries:
    """Build a Registries with every mapping empty: the store never inspects its contents."""
    return Registries(
        hydro=MappingProxyType({}),
        thermal=MappingProxyType({}),
        submarkets=MappingProxyType({}),
        rees=MappingProxyType({}),
        variables=MappingProxyType({}),
    )


def _axis(key: str, length: int) -> TimeAxis:
    """Build a length-stage half-hourly TimeAxis starting at _BASE."""
    starts = tuple(_BASE + pd.Timedelta(hours=0.5 * position) for position in range(length))
    durations = tuple(0.5 for _ in range(length))
    return TimeAxis(key=key, starts=starts, durations_hours=durations)


def _store() -> DashboardData:
    """Build a two-scenario store with a length-4 deck axis and a length-8 chained axis."""
    data = DashboardData(
        scenarios=_SCENARIOS,
        reference=_REFERENCE,
        deck_dates=(_DECK_DATE,),
        registries=_empty_registries(),
    )
    data.set_deck_axis(_DECK_DATE, _axis("deck", _DECK_AXIS_LENGTH))
    data.set_chained_axis(_axis("chained", _CHAINED_AXIS_LENGTH))
    return data


# --- TimeAxis ----------------------------------------------------------------------------


def test_time_axis_length_returns_number_of_starts() -> None:
    axis = _axis("deck", _DECK_AXIS_LENGTH)
    assert axis.length == _DECK_AXIS_LENGTH


def test_time_axis_mismatched_lengths_raises_naming_both_lengths() -> None:
    starts = (_BASE, _BASE + pd.Timedelta(hours=0.5), _BASE + pd.Timedelta(hours=1.0))
    with pytest.raises(StoreError) as exc_info:
        TimeAxis(key="eixo", starts=starts, durations_hours=(0.5, 0.5))

    message = str(exc_info.value)
    assert "3" in message
    assert "2" in message


# --- DashboardData construction -----------------------------------------------------------


def test_dashboard_data_empty_scenarios_raises() -> None:
    with pytest.raises(StoreError):
        DashboardData(
            scenarios=(), reference="caso_a", deck_dates=(), registries=_empty_registries()
        )


def test_dashboard_data_duplicate_scenarios_raises_naming_duplicate() -> None:
    with pytest.raises(StoreError) as exc_info:
        DashboardData(
            scenarios=("caso_a", "caso_a"),
            reference="caso_a",
            deck_dates=(),
            registries=_empty_registries(),
        )

    assert "caso_a" in str(exc_info.value)


def test_dashboard_data_reference_not_in_scenarios_raises_naming_reference() -> None:
    with pytest.raises(StoreError) as exc_info:
        DashboardData(
            scenarios=("caso_a", "caso_b"),
            reference="caso_z",
            deck_dates=(),
            registries=_empty_registries(),
        )

    assert "caso_z" in str(exc_info.value)


# --- deck axis and chained axis -----------------------------------------------------------


def test_set_deck_axis_and_deck_axis_round_trip() -> None:
    data = _store()
    assert data.deck_axis(_DECK_DATE).length == _DECK_AXIS_LENGTH


def test_set_chained_axis_and_chained_axis_round_trip() -> None:
    data = _store()
    assert data.chained_axis().length == _CHAINED_AXIS_LENGTH


def test_deck_axis_unset_raises() -> None:
    data = _store()
    with pytest.raises(StoreError):
        data.deck_axis(date(2024, 3, 4))


def test_chained_axis_unset_raises() -> None:
    data = DashboardData(
        scenarios=_SCENARIOS,
        reference=_REFERENCE,
        deck_dates=(_DECK_DATE,),
        registries=_empty_registries(),
    )
    with pytest.raises(StoreError):
        data.chained_axis()


# --- add_series happy path ----------------------------------------------------------------


def test_add_series_deck_axis_stores_values_and_value_count() -> None:
    data = _store()

    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        values=[1.0, 2.0, None, 4.0],
    )

    assert data.series("GHID_SIN", "", "caso_a", _DECK_DATE) == (1.0, 2.0, None, 4.0)
    assert data.value_count() == 4


def test_add_series_chained_axis_with_deck_date_none_stores_values() -> None:
    data = _store()

    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=None,
        values=[float(position) for position in range(_CHAINED_AXIS_LENGTH)],
    )

    assert data.series("GHID_SIN", "", "caso_a", None) == tuple(
        float(position) for position in range(_CHAINED_AXIS_LENGTH)
    )


# --- add_series error paths ---------------------------------------------------------------


def test_add_series_duplicate_key_raises_naming_chart_and_scenario() -> None:
    data = _store()
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        values=[1.0, 2.0, 3.0, 4.0],
    )

    with pytest.raises(StoreError) as exc_info:
        data.add_series(
            chart_key="GHID_SIN",
            entity_id="",
            scenario="caso_a",
            deck_date=_DECK_DATE,
            values=[1.0, 2.0, 3.0, 4.0],
        )

    message = str(exc_info.value)
    assert "GHID_SIN" in message
    assert "caso_a" in message


def test_add_series_length_mismatch_raises_naming_both_lengths() -> None:
    data = _store()

    with pytest.raises(StoreError) as exc_info:
        data.add_series(
            chart_key="GHID_SIN",
            entity_id="",
            scenario="caso_a",
            deck_date=_DECK_DATE,
            values=[1.0, 2.0, 3.0],
        )

    message = str(exc_info.value)
    assert "3" in message
    assert "4" in message


def test_add_series_unknown_scenario_raises_naming_scenario() -> None:
    data = _store()

    with pytest.raises(StoreError) as exc_info:
        data.add_series(
            chart_key="GHID_SIN",
            entity_id="",
            scenario="caso_desconhecido",
            deck_date=_DECK_DATE,
            values=[1.0, 2.0, 3.0, 4.0],
        )

    assert "caso_desconhecido" in str(exc_info.value)


def test_add_series_unset_axis_raises() -> None:
    data = _store()

    with pytest.raises(StoreError):
        data.add_series(
            chart_key="GHID_SIN",
            entity_id="",
            scenario="caso_a",
            deck_date=date(2024, 3, 4),
            values=[1.0, 2.0, 3.0, 4.0],
        )


def test_add_series_none_values_survive_round_trip_and_count_towards_value_count() -> None:
    data = _store()

    data.add_series(
        chart_key="GHID_UHE",
        entity_id="1",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        values=[None, None, None, None],
    )

    assert data.series("GHID_UHE", "1", "caso_a", _DECK_DATE) == (None, None, None, None)
    assert data.value_count() == 4


# --- series / has_series --------------------------------------------------------------------


def test_series_absent_key_raises() -> None:
    data = _store()
    with pytest.raises(StoreError):
        data.series("GHID_SIN", "", "caso_a", _DECK_DATE)


def test_has_series_absent_key_returns_false_without_raising() -> None:
    data = _store()
    assert data.has_series("GHID_SIN", "", "caso_a", _DECK_DATE) is False


def test_has_series_present_key_returns_true() -> None:
    data = _store()
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        values=[1.0, 2.0, 3.0, 4.0],
    )
    assert data.has_series("GHID_SIN", "", "caso_a", _DECK_DATE) is True


def test_series_returns_tuple_that_rejects_item_assignment() -> None:
    data = _store()
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        values=[1.0, 2.0, 3.0, 4.0],
    )

    stored = data.series("GHID_SIN", "", "caso_a", _DECK_DATE)
    with pytest.raises(TypeError):
        stored[0] = 99.0  # type: ignore[index]


# --- set_entities / entities ----------------------------------------------------------------


def test_set_entities_sorts_by_sort_key() -> None:
    data = _store()
    entity_high = EntityRef(entity_id="30", label="Usina C", sort_key=(30,))
    entity_low = EntityRef(entity_id="10", label="Usina A", sort_key=(10,))
    entity_mid = EntityRef(entity_id="20", label="Usina B", sort_key=(20,))

    data.set_entities("GHID_UHE", [entity_high, entity_low, entity_mid])

    assert data.entities("GHID_UHE") == (entity_low, entity_mid, entity_high)


def test_entities_unknown_chart_returns_empty_tuple() -> None:
    data = _store()
    assert data.entities("GHID_UHE") == ()


# --- add_scalar / scalars -------------------------------------------------------------------


def test_add_scalar_and_scalars_round_trip_for_two_series_and_two_decks() -> None:
    data = _store()
    second_deck = date(2024, 3, 4)

    data.add_scalar(
        chart_key="CUSTOS",
        series_name="PRESENTE",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        value=100.0,
    )
    data.add_scalar(
        chart_key="CUSTOS",
        series_name="FUTURO",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        value=200.0,
    )
    data.add_scalar(
        chart_key="CUSTOS",
        series_name="PRESENTE",
        scenario="caso_a",
        deck_date=second_deck,
        value=110.0,
    )
    data.add_scalar(
        chart_key="CUSTOS",
        series_name="FUTURO",
        scenario="caso_a",
        deck_date=second_deck,
        value=210.0,
    )

    stored = data.scalars("CUSTOS")
    assert len(stored) == 4
    assert stored[("PRESENTE", "caso_a", _DECK_DATE)] == 100.0
    assert stored[("FUTURO", "caso_a", _DECK_DATE)] == 200.0
    assert stored[("PRESENTE", "caso_a", second_deck)] == 110.0
    assert stored[("FUTURO", "caso_a", second_deck)] == 210.0


def test_add_scalar_unknown_scenario_raises_naming_scenario() -> None:
    data = _store()
    with pytest.raises(StoreError) as exc_info:
        data.add_scalar(
            chart_key="CUSTOS",
            series_name="PRESENTE",
            scenario="caso_desconhecido",
            deck_date=_DECK_DATE,
            value=100.0,
        )
    assert "caso_desconhecido" in str(exc_info.value)


def test_add_scalar_repeated_key_overwrites_earlier_value() -> None:
    data = _store()
    data.add_scalar(
        chart_key="CUSTOS",
        series_name="PRESENTE",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        value=100.0,
    )
    data.add_scalar(
        chart_key="CUSTOS",
        series_name="PRESENTE",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        value=150.0,
    )

    assert data.scalars("CUSTOS")[("PRESENTE", "caso_a", _DECK_DATE)] == 150.0


def test_scalars_unknown_chart_returns_empty_mapping() -> None:
    data = _store()
    assert dict(data.scalars("CUSTOS")) == {}


# --- add_warning / warnings -----------------------------------------------------------------


def test_add_warning_deduplicates_identical_messages_preserves_order() -> None:
    data = _store()
    data.add_warning("aviso um")
    data.add_warning("aviso dois")
    data.add_warning("aviso um")

    assert data.warnings() == ("aviso um", "aviso dois")


# --- value_count -------------------------------------------------------------------------


def test_value_count_equals_sum_of_series_lengths_plus_scalar_count() -> None:
    data = _store()
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        values=[1.0, 2.0, 3.0, 4.0],
    )
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=None,
        values=[float(position) for position in range(_CHAINED_AXIS_LENGTH)],
    )
    data.add_scalar(
        chart_key="CUSTOS",
        series_name="PRESENTE",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        value=100.0,
    )
    data.add_scalar(
        chart_key="CUSTOS",
        series_name="FUTURO",
        scenario="caso_a",
        deck_date=_DECK_DATE,
        value=200.0,
    )

    assert data.value_count() == _DECK_AXIS_LENGTH + _CHAINED_AXIS_LENGTH + 2


def test_value_count_zero_for_freshly_built_store() -> None:
    data = _store()
    assert data.value_count() == 0
