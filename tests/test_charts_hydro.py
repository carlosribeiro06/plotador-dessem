"""End-to-end tests for the hydro plant chart rendering (ticket-027).

Epic decision E3-1 forbids executing any JavaScript in this suite (`node` and `npm` are not
installed), so the unit-literal half of this ticket is verified the same way
`tests/test_charts_sin.py` verifies ticket-025: as static text over the `dashboard.js` asset. The
`payload.py`/`builder.py` half is verified against real payloads and documents built from
`tests.conftest.scenario_tree` and from trees regenerated through
`fixtures_sintese.make_sintese_dir`, following the settings-copy-in-`tmp_path` pattern of
`tests/test_builder.py`.

Every heading and option-list assertion is scoped to one chart's own `<section class="chart">`
slice, through the shared helpers of `tests/dashboard_document.py`: `Geração` is the curated
title of both `GHID_UHE` and `GTER_UTE`, and `Volume Armazenado` is a substring of both UHE
volume titles and the exact title of `VARMF_SIN` and `VARMF_SBM`, so an unscoped assertion could
be satisfied by the wrong chart.
"""

from __future__ import annotations

import importlib.resources
import json
import logging
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pandas as pd
import pytest

from dashboard_document import (
    entity_label_text,
    entity_options,
    entity_selector_id,
    opening_tag,
    section_heading,
    sections_by_chart_key,
    sections_by_group,
)
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import build_html
from dessem_dashboard.dashboard.payload import build_payload
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.data.registries import Registries
from dessem_dashboard.models.store import DashboardData, EntityRef, TimeAxis
from fixtures_sintese import make_sintese_dir

_ASSETS_PACKAGE = "dessem_dashboard.dashboard.assets"
_JS_ASSET = "dashboard.js"
_PAYLOAD_LOGGER_NAME = "dessem_dashboard.dashboard.payload"

_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# The eight hydro-plant chart keys, in dessem_dashboard.charts.specs.SPECS (== enabled_specs)
# order, paired with the Current State table's curated titles, units and fixture entity counts.
_UHE_CHART_KEYS_IN_ORDER: tuple[str, ...] = (
    "GHID_UHE",
    "QTUR_UHE",
    "QVER_UHE",
    "VARMF_UHE",
    "VARPF_UHE",
    "QDEF_UHE",
    "QAFL_UHE",
    "QINC_UHE",
)
_UHE_TITLES_IN_ORDER: tuple[str, ...] = (
    "Geração",
    "Turbinamento",
    "Vertimento",
    "Volume Armazenado (hm3)",
    "Volume Armazenado (%)",
    "Defluência",
    "Vazão Afluente",
    "Vazão Incremental",
)
_UHE_UNITS_IN_ORDER: tuple[str, ...] = ("MW", "m3/s", "m3/s", "hm3", "%", "m3/s", "m3/s", "m3/s")
_UHE_ENTITY_COUNTS_IN_ORDER: tuple[int, ...] = (3, 3, 3, 2, 2, 3, 3, 3)
_FOUR_DISTINCT_UHE_UNITS: frozenset[str] = frozenset({"MW", "m3/s", "hm3", "%"})

# Measured on the scenario_tree fixture: three plant labels, sorted alphabetically like the
# codes 1, 2, 3, so the first N labels are also the labels of any N-entity chart's selector.
_THREE_PLANT_LABELS: tuple[str, ...] = ("USINA_1", "USINA_2", "USINA_3")

# Deck-key and chained-key value counts, reused from tests/test_charts_sin.py's own constant.
_DECK_KEYS_AND_LENGTHS: tuple[tuple[str, int], ...] = (
    ("03/03/2024", 50),
    ("04/03/2024", 50),
    ("encadeado", 96),
)

_FORBIDDEN_UNIT_LITERALS: tuple[str, ...] = ('"MW"', '"MWh"', '"hm3"', '"m3/s"', '"%"')

# The per-scenario hydro-coverage tree's deck names, starts and base seed, mirroring
# tests/conftest.py's build_scenario_tree exactly except for hydro_codes, which
# build_scenario_tree never forwards.
_COVERAGE_DECK_NAMES: tuple[str, str] = ("deck_um", "deck_dois")
_COVERAGE_DECK_STARTS: tuple[datetime, datetime] = (
    datetime(2024, 3, 3, tzinfo=UTC),
    datetime(2024, 3, 4, tzinfo=UTC),
)
_COVERAGE_BASE_SEED = 42

_HAND_BUILT_DATE = date(2024, 3, 3)
_HAND_BUILT_DECK_KEY = "03/03/2024"
_HAND_BUILT_CHAINED_KEY = "encadeado"


# --- settings/data/document/payload builders, following tests/test_builder.py's pattern -------


def _settings_dict(*, disabled: Sequence[str] = ()) -> dict[str, Any]:
    """Build a settings.json-shaped dict matching the repository's own values, with a knob."""
    return {
        "project": "dessem-dashboard",
        "paths": {
            "output_dir": "output",
            "log_dir": "logs",
            "logo_file": str(_REPO_LOGO),
        },
        "logging": {
            "level": "INFO",
            "file": "logs/dashboard.log",
            "rotate_max_bytes": 5242880,
            "rotate_backups": 5,
            "use_rich": True,
        },
        "discovery": {"sintese_dirname": "sintese"},
        "chaining": {"stages_per_deck": 48},
        "costs": {"total_parcels": ["PRESENTE", "FUTURO"]},
        "time": {"stage_groups": {"PL": ["PL"]}, "unit_divisor": 60.0},
        "submarkets": {"include_fictitious": False, "fictitious_codes": [11, 99]},
        "dashboard": {
            "title": "Comparação de Resultados do DESSEM",
            "footer_text": "Gerência de Ferramentas Energéticas - FEN",
            "date_format": "%d/%m/%Y %H:%M",
        },
        "output": {
            "default_filename": "dashboard_dessem.html",
            "decimals": 2,
            "size_warning_mb": 50,
        },
        "charts": {"disabled": list(disabled)},
    }


def _build_settings(tmp_path: Path, *, disabled: Sequence[str] = ()) -> Settings:
    """Write settings.json under tmp_path and load it, exercising the real config path."""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(_settings_dict(disabled=disabled)), encoding="utf-8")
    return load_settings(target)


def _build_data(paths: Sequence[Path], *, settings: Settings, reference: str) -> DashboardData:
    """Discover scenarios at paths and consolidate them into one DashboardData."""
    scenarios = discover_scenarios(list(paths))
    return build_dashboard_data(scenarios, settings=settings, reference=reference)


def _build_document(
    paths: Sequence[Path], tmp_path: Path, *, reference: str, disabled: Sequence[str] = ()
) -> str:
    settings = _build_settings(tmp_path, disabled=disabled)
    data = _build_data(paths, settings=settings, reference=reference)
    return build_html(data, settings=settings)


def _build_payload_dict(
    paths: Sequence[Path], tmp_path: Path, *, reference: str, disabled: Sequence[str] = ()
) -> dict[str, object]:
    settings = _build_settings(tmp_path, disabled=disabled)
    data = _build_data(paths, settings=settings, reference=reference)
    return build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})


# --- the per-scenario hydro-coverage tree: caso_b's hydro_codes omit plant 3 --------------------


def _build_hydro_coverage_tree(
    tmp_path: Path, *, caso_b_hydro_codes: tuple[int, ...] = (1, 2)
) -> dict[str, Path]:
    """Two scenarios sharing build_scenario_tree's shape, but with distinct hydro_codes per
    scenario, reproducing E4-3's real coverage gap: consolidate._load_series's all_entity_ids is
    the union over every scenario, so a plant stored for caso_a and absent from caso_b gets a
    full-length all-None array in caso_b, which requirement 1 must then omit.

    build_scenario_tree forwards no code set at all, so this calls make_sintese_dir directly,
    once per (scenario, deck), mirroring ticket-026's regenerate-the-fixture pattern; it is not
    built against the default scenario_tree fixture, whose two scenarios share one hydro_codes
    value and would make any coverage-gap assertion vacuous (Epic 2 learnings section 7).
    """
    hydro_codes_by_scenario: Mapping[str, tuple[int, ...]] = {
        "caso_a": (1, 2, 3),
        "caso_b": caso_b_hydro_codes,
    }
    tree: dict[str, Path] = {}
    seed_offset = 0
    for scenario_name in ("caso_a", "caso_b"):
        scenario_dir = tmp_path / scenario_name
        hydro_codes = hydro_codes_by_scenario[scenario_name]
        for deck_name, deck_start in zip(_COVERAGE_DECK_NAMES, _COVERAGE_DECK_STARTS, strict=True):
            make_sintese_dir(
                scenario_dir / deck_name / "sintese",
                first_stage_start=deck_start,
                n_stages=50,
                half_hour_stages=48,
                long_stage_hours=6.0,
                hydro_codes=hydro_codes,
                seed=_COVERAGE_BASE_SEED + seed_offset,
            )
            seed_offset += 1
        tree[scenario_name] = scenario_dir
    return tree


def _assert_ghid_uhe_coverage(charts: Mapping[str, object]) -> None:
    """Assert GHID_UHE keeps three plants, entity "3" is caso_a-only, and no array is all-None."""
    entry = charts["GHID_UHE"]  # type: ignore[index]
    entities = entry["entities"]  # type: ignore[index]
    assert len(entities) == 3  # type: ignore[arg-type]

    series = entry["series"]  # type: ignore[index]
    assert set(series["3"]) == {"caso_a"}  # type: ignore[index]
    assert set(series["1"]) == {"caso_a", "caso_b"}  # type: ignore[index]

    for by_scenario in series.values():  # type: ignore[union-attr]
        for by_axis in by_scenario.values():
            for values in by_axis.values():
                assert not all(value is None for value in values)


# --- the hand-built two-entity store: one real array, one all-None array -----------------------


def _empty_registries() -> Registries:
    """Build a Registries with every mapping empty, for a hand-built store that reads no file."""
    return Registries(
        hydro=MappingProxyType({}),
        thermal=MappingProxyType({}),
        submarkets=MappingProxyType({}),
        rees=MappingProxyType({}),
        variables=MappingProxyType({}),
    )


def _hand_built_two_entity_store(
    *, dropped_deck_values: tuple[float | None, float | None] = (None, None)
) -> DashboardData:
    """One chart ("GHID_UHE"), two entities: "1" fully covered, "2" all-None by default.

    dropped_deck_values lets the non-vacuity test below give entity "2" one real value on its
    deck array, proving the omission tracks the stored data rather than the entity's position or
    id. Both the deck and the chained axis are registered for both entities, so the omission is
    exercised at both axis levels. Mirrors tests/test_payload.py's _hand_built_data pattern
    locally: private test helpers are duplicated per module by this plan's convention, and only
    the document-slicing helpers of requirement 5 are shared through tests/dashboard_document.py.
    """
    data = DashboardData(
        scenarios=("caso_a",),
        reference="caso_a",
        deck_dates=(_HAND_BUILT_DATE,),
        registries=_empty_registries(),
    )
    start = pd.Timestamp("2024-03-03T00:00:00", tz="UTC")
    starts = (start, start + pd.Timedelta(hours=0.5))
    durations_hours = (0.5, 0.5)
    axis = TimeAxis(key=_HAND_BUILT_DECK_KEY, starts=starts, durations_hours=durations_hours)
    data.set_deck_axis(_HAND_BUILT_DATE, axis)
    data.set_chained_axis(
        TimeAxis(key=_HAND_BUILT_CHAINED_KEY, starts=starts, durations_hours=durations_hours)
    )

    kept = EntityRef(entity_id="1", label="USINA_1", sort_key=("USINA_1",))
    dropped = EntityRef(entity_id="2", label="USINA_2", sort_key=("USINA_2",))
    data.set_entities("GHID_UHE", [kept, dropped])

    data.add_series(
        chart_key="GHID_UHE",
        entity_id="1",
        scenario="caso_a",
        deck_date=_HAND_BUILT_DATE,
        values=[10.0, 20.0],
    )
    data.add_series(
        chart_key="GHID_UHE", entity_id="1", scenario="caso_a", deck_date=None, values=[10.0, 20.0]
    )
    data.add_series(
        chart_key="GHID_UHE",
        entity_id="2",
        scenario="caso_a",
        deck_date=_HAND_BUILT_DATE,
        values=list(dropped_deck_values),
    )
    data.add_series(
        chart_key="GHID_UHE", entity_id="2", scenario="caso_a", deck_date=None, values=[None, None]
    )
    return data


# --- acceptance criterion 1: entity counts, labels, units and series shape ---------------------


def test_fixture_payload_uhe_charts_entity_counts_units_and_series_shape(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    charts = payload["charts"]  # type: ignore[index]

    observed_units: list[str] = []
    for chart_key, expected_count, expected_unit in zip(
        _UHE_CHART_KEYS_IN_ORDER, _UHE_ENTITY_COUNTS_IN_ORDER, _UHE_UNITS_IN_ORDER, strict=True
    ):
        entry = charts[chart_key]  # type: ignore[index]
        entities = entry["entities"]  # type: ignore[index]
        expected_labels = list(_THREE_PLANT_LABELS[:expected_count])
        observed_labels = [entity["label"] for entity in entities]  # type: ignore[union-attr]
        assert len(entities) == expected_count  # type: ignore[arg-type]
        assert observed_labels == expected_labels
        assert entry["unit"] == expected_unit  # type: ignore[index]
        observed_units.append(entry["unit"])  # type: ignore[index]

        series = entry["series"]  # type: ignore[index]
        for entity in entities:  # type: ignore[union-attr]
            series_for_entity = series[entity["id"]]  # type: ignore[index]
            for scenario in ("caso_a", "caso_b"):
                for axis_key, expected_length in _DECK_KEYS_AND_LENGTHS:
                    assert len(series_for_entity[scenario][axis_key]) == expected_length

    assert observed_units == list(_UHE_UNITS_IN_ORDER)
    assert frozenset(observed_units) == _FOUR_DISTINCT_UHE_UNITS


# --- acceptance criterion 2: per-scenario hydro coverage, and no all-None array -----------------


def test_payload_per_scenario_hydro_coverage_ghid_uhe_keeps_three_plants_and_omits_all_none_arrays(
    tmp_path: Path,
) -> None:
    tree = _build_hydro_coverage_tree(tmp_path / "coverage_tree")
    payload = _build_payload_dict([tree["caso_a"], tree["caso_b"]], tmp_path, reference="caso_a")
    _assert_ghid_uhe_coverage(payload["charts"])  # type: ignore[index]


# --- acceptance criterion 3: the hand-built all-None entity, dropped, with one INFO line --------


def test_hand_built_two_entity_store_drops_all_none_entity_and_logs_one_info_line(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    data = _hand_built_two_entity_store()
    settings = _build_settings(tmp_path)

    caplog.set_level(logging.INFO, logger=_PAYLOAD_LOGGER_NAME)
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    entry = payload["charts"]["GHID_UHE"]  # type: ignore[index]

    assert entry["entities"] == [{"id": "1", "label": "USINA_1"}]  # type: ignore[index]
    assert set(entry["series"]) == {"1"}  # type: ignore[index]
    assert entry["series"]["1"]["caso_a"]["03/03/2024"] == [10.0, 20.0]  # type: ignore[index]

    matching = [
        record
        for record in caplog.records
        if record.name == _PAYLOAD_LOGGER_NAME and "GHID_UHE" in record.getMessage()
    ]
    assert len(matching) == 1
    # Asserted against the LogRecord's raw args, not the rendered message: "1" as a substring
    # of the message would also match incidentally (a stray digit elsewhere in the sentence),
    # while args is exactly (chart_key, dropped_count) before formatting.
    assert matching[0].args == ("GHID_UHE", 1)

    # Requirement 3 has two directions, and this is the negative one: no line for a chart that
    # lost nothing. Matched on the drop line's own message template rather than on "every INFO
    # record of this logger", because `build_payload`'s timed-step helper in `logging_setup`
    # also emits an INFO record under this module's logger name ("Payload JSON construido") and
    # would be counted with it. GHID_UHE is the only one of the 23 charts that drops anything
    # here, so the surviving list must hold exactly one entry. Without this assertion, removing
    # the `if dropped:` guard -- a drop line for all 23 charts, 22 of them reporting zero --
    # passes the whole suite.
    drop_records = [
        record
        for record in caplog.records
        if record.name == _PAYLOAD_LOGGER_NAME
        and isinstance(record.msg, str)
        and record.msg.startswith("Gráfico '%s' omitiu")
    ]
    assert [record.args for record in drop_records] == [("GHID_UHE", 1)]


# --- acceptance criterion 4: UHE section selector, hidden state, heading and scoped options -----


def test_document_uhe_sections_carry_selector_hidden_label_heading_and_scoped_options(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    sections = sections_by_chart_key(document)

    titles_by_key = zip(_UHE_CHART_KEYS_IN_ORDER, _UHE_TITLES_IN_ORDER, strict=True)
    for chart_key, expected_title in titles_by_key:
        section = sections[chart_key]
        assert 'data-selector="HYDRO_PLANT"' in section
        assert opening_tag(section).endswith(" hidden>")
        assert entity_label_text(section) == "Usina hidrelétrica"
        assert section.count("<h2>") == 1
        assert section_heading(section) == expected_title
        assert "chart-subtitle" not in section
        assert entity_selector_id(section) == chart_key

    varmf_options = entity_options(sections["VARMF_UHE"])
    assert varmf_options == [("1", "USINA_1"), ("2", "USINA_2")]

    ghid_options = entity_options(sections["GHID_UHE"])
    assert ghid_options == [("1", "USINA_1"), ("2", "USINA_2"), ("3", "USINA_3")]


# --- acceptance criterion 5: no forbidden unit literal in dashboard.js, including "%" -----------


def _read_js_asset() -> str:
    return (
        importlib.resources.files(_ASSETS_PACKAGE).joinpath(_JS_ASSET).read_text(encoding="utf-8")
    )


def _check_no_unit_literal(text: str, literal: str) -> None:
    assert literal not in text, f"forbidden unit literal {literal} found in dashboard.js"


@pytest.mark.parametrize("literal", _FORBIDDEN_UNIT_LITERALS)
def test_dashboard_js_contains_no_hardcoded_unit_literal_including_percent(literal: str) -> None:
    text = _read_js_asset()
    _check_no_unit_literal(text, literal)


# --- additional Testing Requirements: data-group key set, disabled chart, subset, rounding -----


def test_document_uhe_data_group_key_set_equals_the_eight_expected_keys(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    sections = sections_by_group(document, "UHE")

    observed_keys: set[str] = set()
    for section in sections:
        match = re.search(r'data-chart="([^"]+)"', section)
        assert match is not None
        observed_keys.add(match.group(1))
    assert observed_keys == set(_UHE_CHART_KEYS_IN_ORDER)


def test_document_and_payload_with_varpf_disabled_keep_seven_sections_and_unchanged_units(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """Disabling VARPF_UHE proves the level is registry-driven and that "%" belongs to it alone."""
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]],
        tmp_path,
        reference="caso_a",
        disabled=["VARPF_UHE"],
    )
    sections = sections_by_group(document, "UHE")
    assert len(sections) == 7
    assert 'id="chart-VARPF_UHE"' not in document

    remaining_keys = [key for key in _UHE_CHART_KEYS_IN_ORDER if key != "VARPF_UHE"]
    remaining_titles = [
        title
        for key, title in zip(_UHE_CHART_KEYS_IN_ORDER, _UHE_TITLES_IN_ORDER, strict=True)
        if key != "VARPF_UHE"
    ]
    by_key = sections_by_chart_key(document)
    for key, expected_title in zip(remaining_keys, remaining_titles, strict=True):
        assert section_heading(by_key[key]) == expected_title

    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]],
        tmp_path,
        reference="caso_a",
        disabled=["VARPF_UHE"],
    )
    charts = payload["charts"]  # type: ignore[index]
    remaining_units = [
        unit
        for key, unit in zip(_UHE_CHART_KEYS_IN_ORDER, _UHE_UNITS_IN_ORDER, strict=True)
        if key != "VARPF_UHE"
    ]
    observed_units = [charts[key]["unit"] for key in remaining_keys]  # type: ignore[index]
    assert observed_units == remaining_units
    assert "%" not in observed_units


def test_fixture_payload_varmf_and_varpf_entity_lists_equal_and_strict_subset_of_ghid(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """decision 16 made observable: both reservoir-driven charts share coverage, which is a
    strict subset of the hydro_codes-driven GHID_UHE coverage on the fixture."""
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    charts = payload["charts"]  # type: ignore[index]

    varmf_ids = {entity["id"] for entity in charts["VARMF_UHE"]["entities"]}  # type: ignore[index]
    varpf_ids = {entity["id"] for entity in charts["VARPF_UHE"]["entities"]}  # type: ignore[index]
    ghid_ids = {entity["id"] for entity in charts["GHID_UHE"]["entities"]}  # type: ignore[index]

    assert varmf_ids == varpf_ids
    assert varmf_ids < ghid_ids


def test_fixture_payload_ghid_uhe_values_are_none_or_rounded_to_two_decimals(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    series = payload["charts"]["GHID_UHE"]["series"]  # type: ignore[index]

    for by_scenario in series.values():  # type: ignore[union-attr]
        for by_axis in by_scenario.values():
            for values in by_axis.values():
                for value in values:
                    assert value is None or value == round(value, 2)


def test_deleting_one_deck_ghid_uhe_file_keeps_the_other_deck_key_and_the_chained_key(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """requirement 1 omits an all-None axis entry, not a partially covered array: deleting one
    deck's source file leaves the other deck's key and the (partially real) chained key intact."""
    (scenario_tree["caso_b"] / "deck_dois" / "sintese" / "GHID_UHE.parquet").unlink()
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    series = payload["charts"]["GHID_UHE"]["series"]["1"]  # type: ignore[index]

    assert "04/03/2024" not in series["caso_b"]  # type: ignore[operator]
    assert "03/03/2024" in series["caso_b"]  # type: ignore[operator]
    assert len(series["caso_b"]["encadeado"]) == 96  # type: ignore[index]


def test_hand_built_store_and_fixture_payload_entities_series_id_sets_are_in_lockstep(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    data = _hand_built_two_entity_store()
    settings = _build_settings(tmp_path)
    hand_built_payload = build_payload(
        data, settings=settings, scenario_colors={}, plotly_layout={}
    )
    hand_built_entry = hand_built_payload["charts"]["GHID_UHE"]  # type: ignore[index]
    hand_built_ids = {entity["id"] for entity in hand_built_entry["entities"]}  # type: ignore[index]
    assert hand_built_ids == set(hand_built_entry["series"])  # type: ignore[index]

    fixture_payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    charts = fixture_payload["charts"]  # type: ignore[index]
    for entry in charts.values():  # type: ignore[union-attr]
        if entry["kind"] != "SERIES":
            continue
        surviving_ids = {entity["id"] for entity in entry["entities"]}
        assert surviving_ids == set(entry["series"])


# --- non-vacuity proof: each mutation of Suggested Approach step 7, confirmed to fail first ------


@pytest.mark.parametrize("literal", _FORBIDDEN_UNIT_LITERALS)
def test_no_unit_literal_check_is_not_vacuous(literal: str) -> None:
    text = _read_js_asset()
    _check_no_unit_literal(text, literal)

    mutated = text + "\n// " + literal + "\n"
    with pytest.raises(AssertionError):
        _check_no_unit_literal(mutated, literal)


def test_hand_built_two_entity_store_entity_survives_once_one_slot_is_no_longer_none(
    tmp_path: Path,
) -> None:
    """Proves the omission tracks real data: giving entity "2" one real value on its deck array
    is enough for it to survive in both entities and series, unlike the all-None default."""
    data = _hand_built_two_entity_store(dropped_deck_values=(0.0, None))
    settings = _build_settings(tmp_path)

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    entry = payload["charts"]["GHID_UHE"]  # type: ignore[index]

    surviving_ids = {entity["id"] for entity in entry["entities"]}  # type: ignore[index]
    assert surviving_ids == {"1", "2"}
    assert entry["series"]["2"]["caso_a"]["03/03/2024"] == [0.0, None]  # type: ignore[index]


def test_ghid_uhe_coverage_assertion_is_not_vacuous_without_the_coverage_gap(
    tmp_path: Path,
) -> None:
    """Without a real coverage gap -- both scenarios sharing hydro_codes=(1, 2, 3) -- the
    series["3"] single-key assertion of _assert_ghid_uhe_coverage fails, proving acceptance
    criterion 2's test is not satisfied by incidental fixture shape (Epic 2 learnings section 7)."""
    tree = _build_hydro_coverage_tree(tmp_path / "vacuous_tree", caso_b_hydro_codes=(1, 2, 3))
    payload = _build_payload_dict([tree["caso_a"], tree["caso_b"]], tmp_path, reference="caso_a")

    with pytest.raises(AssertionError):
        _assert_ghid_uhe_coverage(payload["charts"])  # type: ignore[index]
