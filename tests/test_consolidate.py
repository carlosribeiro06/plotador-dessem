"""Tests for dessem_dashboard.data.consolidate."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from dessem_dashboard.charts.registry import ChartKind, enabled_specs
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.data.schemas import AggregationLevel
from dessem_dashboard.errors import SchemaError
from fixtures_sintese import make_sintese_dir

# tests.conftest.scenario_tree overrides (n_stages=50, half_hour_stages=48, long_stage_hours=6.0),
# and acceptance criterion 1's chaining.stages_per_deck.
_STAGES_PER_DECK = 4
_CHAINED_AXIS_LENGTH = _STAGES_PER_DECK * 2
_DECK_STAGE_COUNT = 50
_DECK_STARTS: tuple[datetime, datetime] = (
    datetime(2024, 3, 3, tzinfo=UTC),
    datetime(2024, 3, 4, tzinfo=UTC),
)
_DECK_DATES: tuple[date, date] = (date(2024, 3, 3), date(2024, 3, 4))

# fixtures_sintese._CUSTOS_PARCELAS has four distinct rows; _TEMPO_ETAPAS has nine rows over
# five distinct names ("PL" three times, "PL.Int.Fix" and "PL.CalcCMO" twice each), and
# add_scalar overwrites a repeated (series_name, scenario, deck) key rather than raising.
_CUSTOS_PARCEL_COUNT = 4
_TEMPO_DISTINCT_ETAPA_COUNT = 5
_RESERVOIR_ONLY_UHE_KEYS = frozenset({"VARMF_UHE", "VARPF_UHE"})

_CONSOLIDATE_LOGGER_NAME = "dessem_dashboard.data.consolidate"


def _settings_dict(
    *, stages_per_deck: int, include_fictitious: bool, disabled: Sequence[str]
) -> dict[str, Any]:
    return {
        "project": "dessem-dashboard",
        "paths": {
            "output_dir": "output",
            "log_dir": "logs",
            "logo_file": "logo/logo.png",
        },
        "logging": {
            "level": "INFO",
            "file": "logs/dashboard.log",
            "rotate_max_bytes": 5242880,
            "rotate_backups": 5,
            "use_rich": True,
        },
        "discovery": {"sintese_dirname": "sintese"},
        "chaining": {"stages_per_deck": stages_per_deck},
        "costs": {"total_parcels": ["PRESENTE", "FUTURO"]},
        "time": {"stage_groups": {"PL": ["PL"]}, "unit_divisor": 60.0},
        "submarkets": {"include_fictitious": include_fictitious, "fictitious_codes": [11, 99]},
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


def _build_settings(
    tmp_path: Path,
    *,
    stages_per_deck: int = _STAGES_PER_DECK,
    include_fictitious: bool = False,
    disabled: Sequence[str] = (),
) -> Settings:
    """Write settings.json under tmp_path and load it, so tests exercise the real config path."""
    target = tmp_path / "settings.json"
    settings_content = _settings_dict(
        stages_per_deck=stages_per_deck, include_fictitious=include_fictitious, disabled=disabled
    )
    target.write_text(json.dumps(settings_content), encoding="utf-8")
    return load_settings(target)


def _rewrite_parquet(path: Path, transform: Callable[[pd.DataFrame], pd.DataFrame]) -> None:
    """Read path, apply transform, write the result back to path."""
    raw = pd.read_parquet(path, engine="pyarrow")
    transform(raw).to_parquet(path, index=False)


def _build_partial_scenario_tree(tmp_path: Path) -> dict[str, Path]:
    """Two decks for caso_a, only the first deck for caso_b: a deck missing from a scenario."""
    tree: dict[str, Path] = {}
    deck_names_by_scenario = {"caso_a": ("deck_um", "deck_dois"), "caso_b": ("deck_um",)}
    for scenario_name, deck_names in deck_names_by_scenario.items():
        scenario_dir = tmp_path / scenario_name
        for deck_name, deck_start in zip(deck_names, _DECK_STARTS[: len(deck_names)], strict=True):
            make_sintese_dir(
                scenario_dir / deck_name / "sintese",
                first_stage_start=deck_start,
                n_stages=_DECK_STAGE_COUNT,
                half_hour_stages=48,
                long_stage_hours=6.0,
            )
        tree[scenario_name] = scenario_dir
    return tree


def _build_mismatched_hydro_tree(tmp_path: Path) -> Path:
    """One scenario, two decks: the second deck's GHID_UHE lacks the first deck's plant 3."""
    scenario_dir = tmp_path / "caso_unico"
    make_sintese_dir(
        scenario_dir / "deck_1" / "sintese",
        first_stage_start=_DECK_STARTS[0],
        hydro_codes=(1, 2, 3),
    )
    make_sintese_dir(
        scenario_dir / "deck_2" / "sintese",
        first_stage_start=_DECK_STARTS[1],
        hydro_codes=(1, 2),
    )
    return scenario_dir


def _expected_series_value_count(
    *,
    deck_axis_length: int,
    n_decks: int,
    chained_axis_length: int,
    n_scenarios: int,
    submarket_count: int,
    hydro_count: int,
    reservoir_count: int,
    thermal_count: int,
    pair_count: int,
) -> int:
    """Independently derive the SERIES contribution to value_count from enabled_specs()."""
    per_entity_per_scenario = deck_axis_length * n_decks + chained_axis_length
    total = 0
    for spec in enabled_specs():
        if spec.kind is not ChartKind.SERIES:
            continue
        if spec.level is AggregationLevel.SIN:
            entity_count = 1
        elif spec.level is AggregationLevel.SBM:
            entity_count = submarket_count
        elif spec.level is AggregationLevel.SBP:
            entity_count = pair_count
        elif spec.level is AggregationLevel.UHE:
            entity_count = reservoir_count if spec.key in _RESERVOIR_ONLY_UHE_KEYS else hydro_count
        else:
            entity_count = thermal_count
        total += entity_count * per_entity_per_scenario
    return total * n_scenarios


def _expected_scalar_value_count(
    *, n_scenarios: int, n_decks: int, custos_parcel_count: int, tempo_distinct_etapa_count: int
) -> int:
    return n_scenarios * n_decks * (custos_parcel_count + tempo_distinct_etapa_count)


# --- happy path and chained axis --------------------------------------------------------------


def test_build_dashboard_data_happy_path_two_scenarios_two_decks_returns_expected_shape(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    assert data.scenarios == ("caso_a", "caso_b")
    assert len(data.deck_dates) == 2
    assert data.deck_dates == _DECK_DATES
    for chart_key, entity_id in (
        ("GHID_SIN", ""),
        ("CMO_SBM", "1"),
        ("INT_SBP", "1-2"),
        ("GHID_UHE", "1"),
        ("GTER_UTE", "1"),
    ):
        values = data.series(chart_key, entity_id, "caso_a", data.deck_dates[0])
        assert len(values) == _DECK_STAGE_COUNT


def test_build_dashboard_data_chained_axis_length_and_monotonic_starts(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    chained_axis = data.chained_axis()
    assert chained_axis.length == _CHAINED_AXIS_LENGTH
    starts = chained_axis.starts
    assert all(earlier < later for earlier, later in pairwise(starts))
    assert len(data.series("GHID_SIN", "", "caso_a", None)) == _CHAINED_AXIS_LENGTH


# --- missing source file: series chart and CUSTOS ----------------------------------------------


def test_build_dashboard_data_missing_series_source_file_yields_one_warning_and_no_series(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    (scenario_tree["caso_b"] / "deck_dois" / "sintese" / "GTER_UTE.parquet").unlink()
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    matching = [w for w in data.warnings() if "GTER_UTE" in w and "caso_b" in w]
    assert len(matching) == 1
    assert data.has_series("GTER_UTE", "1", "caso_b", data.deck_dates[1]) is False
    assert data.has_series("GTER_UTE", "1", "caso_a", data.deck_dates[1]) is True


def test_build_dashboard_data_missing_custos_file_yields_one_warning_and_no_scalars(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    (scenario_tree["caso_b"] / "deck_dois" / "sintese" / "CUSTOS.parquet").unlink()
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    matching = [w for w in data.warnings() if "CUSTOS" in w and "caso_b" in w]
    assert len(matching) == 1
    stored = data.scalars("CUSTOS")
    assert not [key for key in stored if key[1] == "caso_b" and key[2] == data.deck_dates[1]]
    assert [key for key in stored if key[1] == "caso_b" and key[2] == data.deck_dates[0]]


# --- deck missing from one scenario -------------------------------------------------------------


def test_build_dashboard_data_deck_missing_from_scenario_pads_chained_array_with_none(
    tmp_path: Path,
) -> None:
    tree = _build_partial_scenario_tree(tmp_path)
    scenarios = discover_scenarios([tree["caso_a"], tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    assert any("caso_b" in w and "04/03/2024" in w for w in data.warnings())
    assert data.has_series("GHID_SIN", "", "caso_b", date(2024, 3, 4)) is False
    assert data.has_series("GHID_SIN", "", "caso_b", date(2024, 3, 3)) is True

    chained = data.series("GHID_SIN", "", "caso_b", None)
    assert len(chained) == _CHAINED_AXIS_LENGTH
    assert all(value is not None for value in chained[:_STAGES_PER_DECK])
    assert all(value is None for value in chained[_STAGES_PER_DECK:])


# --- per-chart entity lists ----------------------------------------------------------------------


def test_build_dashboard_data_entity_lists_differ_between_ghid_uhe_and_varmf_uhe(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    assert {e.entity_id for e in data.entities("VARMF_UHE")} == {"1", "2"}
    assert {e.entity_id for e in data.entities("GHID_UHE")} == {"1", "2", "3"}


# --- entity labels from registries ----------------------------------------------------------------


def test_build_dashboard_data_entity_labels_come_from_registries(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path, include_fictitious=True)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    hydro = {e.entity_id: e.label for e in data.entities("GHID_UHE")}
    thermal = {e.entity_id: e.label for e in data.entities("GTER_UTE")}
    submarket = {e.entity_id: e.label for e in data.entities("CMO_SBM")}
    pair = {e.entity_id: e.label for e in data.entities("INT_SBP")}

    assert hydro["1"] == "USINA_1"
    assert thermal["1"] == "TERMICA_1"
    assert submarket["1"] == "SE (SUDESTE)"
    assert pair["1-2"] == "SE (SUDESTE) para S (SUL)"


# --- entity order follows sort_key ----------------------------------------------------------------


def test_build_dashboard_data_entity_order_follows_sort_key_alphabetical_by_plant_name(
    tmp_path: Path,
) -> None:
    scenario_dir = tmp_path / "caso_unico"
    make_sintese_dir(
        scenario_dir / "deck_um" / "sintese",
        first_stage_start=_DECK_STARTS[0],
        hydro_codes=(1, 2, 3, 10),
    )
    scenarios = discover_scenarios([scenario_dir])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_unico")

    # "USINA_1" < "USINA_10" < "USINA_2" < "USINA_3" alphabetically, unlike numeric code order.
    assert [e.entity_id for e in data.entities("GHID_UHE")] == ["1", "10", "2", "3"]


# --- fictitious submarket filtering ---------------------------------------------------------------


def test_build_dashboard_data_fictitious_submarket_excluded_when_include_fictitious_false(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path, include_fictitious=False)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    assert "11" not in {e.entity_id for e in data.entities("CMO_SBM")}
    assert data.has_series("CMO_SBM", "11", "caso_a", data.deck_dates[0]) is False


def test_build_dashboard_data_fictitious_submarket_included_when_include_fictitious_true(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path, include_fictitious=True)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    assert "11" in {e.entity_id for e in data.entities("CMO_SBM")}
    assert data.has_series("CMO_SBM", "11", "caso_a", data.deck_dates[0]) is True


def test_build_dashboard_data_int_sbp_keeps_pair_with_code_11_regardless_of_include_fictitious(
    tmp_path: Path,
) -> None:
    scenario_dir = tmp_path / "caso_unico"
    make_sintese_dir(
        scenario_dir / "deck_um" / "sintese",
        first_stage_start=_DECK_STARTS[0],
        pair_codes=((1, 2), (2, 1), (1, 11)),
    )
    scenarios = discover_scenarios([scenario_dir])

    for include_fictitious in (False, True):
        settings = _build_settings(tmp_path, include_fictitious=include_fictitious)
        data = build_dashboard_data(scenarios, settings=settings, reference="caso_unico")
        assert "1-11" in {e.entity_id for e in data.entities("INT_SBP")}


# --- scalars: CUSTOS and TEMPO ------------------------------------------------------------------


def test_build_dashboard_data_custos_stores_four_parcels_per_scenario_and_deck(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    stored = data.scalars("CUSTOS")
    assert len(stored) == _CUSTOS_PARCEL_COUNT * 2 * 2


def test_build_dashboard_data_tempo_stores_raw_stage_times_without_dividing_by_sixty(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)
    deck_path = scenario_tree["caso_a"] / "deck_dois" / "sintese" / "TEMPO.parquet"
    raw = pd.read_parquet(deck_path, engine="pyarrow")
    expected_milp = float(raw.loc[raw["etapa"] == "MILP", "tempo"].iloc[0])

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    stored = data.scalars("TEMPO")
    assert len(stored) == _TEMPO_DISTINCT_ETAPA_COUNT * 2 * 2
    assert stored[("MILP", "caso_a", data.deck_dates[0])] == pytest.approx(expected_milp)


# --- entity present in one deck, absent from the other -----------------------------------------


def test_build_dashboard_data_plant_present_in_one_deck_absent_from_other_fills_none_and_warns(
    tmp_path: Path,
) -> None:
    scenario_dir = _build_mismatched_hydro_tree(tmp_path)
    scenarios = discover_scenarios([scenario_dir])
    settings = _build_settings(tmp_path, stages_per_deck=_STAGES_PER_DECK)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_unico")

    assert "3" in {e.entity_id for e in data.entities("GHID_UHE")}
    absent_values = data.series("GHID_UHE", "3", "caso_unico", date(2024, 3, 4))
    assert all(value is None for value in absent_values)
    present_values = data.series("GHID_UHE", "3", "caso_unico", date(2024, 3, 3))
    assert any(value is not None for value in present_values)

    matching = [
        w for w in data.warnings() if "GHID_UHE" in w and "caso_unico" in w and "1 entidade" in w
    ]
    assert len(matching) == 1


# --- malformed file is not swallowed --------------------------------------------------------------


def test_build_dashboard_data_malformed_series_file_raises_schema_error(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    path = scenario_tree["caso_a"] / "deck_um" / "sintese" / "GHID_SIN.parquet"
    _rewrite_parquet(path, lambda raw: raw.drop(columns=["valor"]))
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    with pytest.raises(SchemaError):
        build_dashboard_data(scenarios, settings=settings, reference="caso_a")


# --- value_count ------------------------------------------------------------------------------


def test_build_dashboard_data_value_count_matches_manual_computation(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path, include_fictitious=True)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    expected = _expected_series_value_count(
        deck_axis_length=_DECK_STAGE_COUNT,
        n_decks=2,
        chained_axis_length=_CHAINED_AXIS_LENGTH,
        n_scenarios=2,
        submarket_count=4,
        hydro_count=3,
        reservoir_count=2,
        thermal_count=2,
        pair_count=2,
    ) + _expected_scalar_value_count(
        n_scenarios=2,
        n_decks=2,
        custos_parcel_count=_CUSTOS_PARCEL_COUNT,
        tempo_distinct_etapa_count=_TEMPO_DISTINCT_ETAPA_COUNT,
    )

    assert data.value_count() == expected


# --- logging -----------------------------------------------------------------------------------


def test_build_dashboard_data_logs_five_phase_info_lines(
    scenario_tree: dict[str, Path], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=_CONSOLIDATE_LOGGER_NAME)
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    messages = [record.getMessage() for record in caplog.records]
    for marker in ("Fase 1/5", "Fase 2/5", "Fase 3/5", "Fase 4/5", "Fase 5/5"):
        assert any(marker in message for message in messages)


# --- registry name disagreement across decks (requirement 4) -----------------------------------


def test_build_dashboard_data_renamed_plant_between_decks_logs_warning_keeps_primary_name(
    scenario_tree: dict[str, Path], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # discovery sorts decks by folder name, so caso_a's primary deck is "deck_dois"; renaming the
    # plant in the non-primary "deck_um" must not change the label the store ends up with.
    uhe_path = scenario_tree["caso_a"] / "deck_um" / "sintese" / "UHE.parquet"
    _rewrite_parquet(
        uhe_path,
        lambda raw: raw.assign(
            usina=raw["usina"].where(raw["codigo_usina"] != 1, "USINA_1_RENOMEADA")
        ),
    )
    caplog.set_level(logging.WARNING, logger=_CONSOLIDATE_LOGGER_NAME)
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    assert any("nome divergente" in record.getMessage() for record in caplog.records)
    hydro = {e.entity_id: e.label for e in data.entities("GHID_UHE")}
    assert hydro["1"] == "USINA_1"
