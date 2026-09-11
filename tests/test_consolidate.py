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
from dessem_dashboard.errors import DataFileError, SchemaError
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


# Deliberately far from any digit pair appearing in "03/03/2024", so a match on these counts in a
# warning message cannot be satisfied incidentally by the date (epic-02-learnings section 7).
_MISMATCHED_STAGE_COUNTS: dict[str, int] = {"caso_a": 10, "caso_b": 16}


def _build_stage_count_mismatch_tree(tmp_path: Path) -> dict[str, Path]:
    """Two scenarios, one deck each, sharing a deck date but disagreeing on stage count."""
    tree: dict[str, Path] = {}
    for scenario_name, n_stages in _MISMATCHED_STAGE_COUNTS.items():
        scenario_dir = tmp_path / scenario_name
        make_sintese_dir(
            scenario_dir / "deck_um" / "sintese",
            first_stage_start=_DECK_STARTS[0],
            n_stages=n_stages,
            half_hour_stages=n_stages,
        )
        tree[scenario_name] = scenario_dir
    return tree


# Same calendar date, deliberately six hours apart so the mismatch cannot be mistaken for a
# rounding artefact, and "06" never appears in "03/03/2024".
_MISMATCHED_STARTS: dict[str, datetime] = {
    "caso_a": datetime(2024, 3, 3, 0, tzinfo=UTC),
    "caso_b": datetime(2024, 3, 3, 6, tzinfo=UTC),
}


def _build_start_mismatch_tree(tmp_path: Path) -> dict[str, Path]:
    """Two scenarios, one deck each, sharing a deck date but starting at different hours."""
    tree: dict[str, Path] = {}
    for scenario_name, first_start in _MISMATCHED_STARTS.items():
        scenario_dir = tmp_path / scenario_name
        make_sintese_dir(scenario_dir / "deck_um" / "sintese", first_stage_start=first_start)
        tree[scenario_name] = scenario_dir
    return tree


def _build_registry_gap_tree(tmp_path: Path, *, omit_from: str) -> Path:
    """One scenario, two decks (alphabetically deck_1 before deck_2); omit REE.parquet from one.

    Discovery sorts decks by folder name, so deck_1 is always the primary deck.
    """
    scenario_dir = tmp_path / "caso_unico"
    for deck_name, deck_start in zip(("deck_1", "deck_2"), _DECK_STARTS, strict=True):
        make_sintese_dir(
            scenario_dir / deck_name / "sintese",
            first_stage_start=deck_start,
            omit=("REE.parquet",) if deck_name == omit_from else (),
        )
    return scenario_dir


def _duplicate_entity_under_new_ree(frame: pd.DataFrame) -> pd.DataFrame:
    """Duplicate codigo_usina 1's rows under a different codigo_ree, at the same estagio.

    read_series' own uniqueness check is over the wider (codigo_usina, codigo_ree,
    codigo_submercado, estagio) key, which stays unique here (codigo_ree differs); the narrower
    (entity_id, estagio) pivot key data.consolidate checks does not.
    """
    duplicated = frame[frame["codigo_usina"] == 1].copy()
    duplicated["codigo_ree"] = duplicated["codigo_ree"] + 1000
    return pd.concat([frame, duplicated], ignore_index=True)


_MIDDLE_GAP_DECK_NAMES: tuple[str, str, str] = ("deck_um", "deck_dois", "deck_tres")
_MIDDLE_GAP_DECK_STARTS: tuple[datetime, datetime, datetime] = (
    datetime(2024, 3, 3, tzinfo=UTC),
    datetime(2024, 3, 4, tzinfo=UTC),
    datetime(2024, 3, 5, tzinfo=UTC),
)


def _build_middle_gap_scenario_tree(tmp_path: Path) -> dict[str, Path]:
    """Three decks for caso_a; caso_b lacks the middle one, a gap at chained positions 4-7."""
    tree: dict[str, Path] = {}
    deck_names_by_scenario = {
        "caso_a": _MIDDLE_GAP_DECK_NAMES,
        "caso_b": (_MIDDLE_GAP_DECK_NAMES[0], _MIDDLE_GAP_DECK_NAMES[2]),
    }
    for scenario_name, deck_names in deck_names_by_scenario.items():
        scenario_dir = tmp_path / scenario_name
        for deck_name in deck_names:
            deck_start = _MIDDLE_GAP_DECK_STARTS[_MIDDLE_GAP_DECK_NAMES.index(deck_name)]
            make_sintese_dir(
                scenario_dir / deck_name / "sintese",
                first_stage_start=deck_start,
                n_stages=_DECK_STAGE_COUNT,
                half_hour_stages=48,
                long_stage_hours=6.0,
            )
        tree[scenario_name] = scenario_dir
    return tree


def _build_registry_missing_submarket_tree(tmp_path: Path) -> Path:
    """One scenario, one deck: submarket 3 present in CMO_SBM but absent from SBM.parquet."""
    scenario_dir = tmp_path / "caso_unico"
    sintese_dir = scenario_dir / "deck_um" / "sintese"
    make_sintese_dir(sintese_dir, first_stage_start=_DECK_STARTS[0], submarket_codes=(1, 2, 3))
    _rewrite_parquet(
        sintese_dir / "SBM.parquet",
        lambda raw: raw[raw["codigo_submercado"] != 3].reset_index(drop=True),
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


# A gap in the middle deck must pad exactly that deck's window, not the tail of the array
# (finding 7 of the epic-02 boundary review): the original suite only ever omitted the last
# deck, which an implementation that appends padding instead of inserting it would pass anyway.
def test_build_dashboard_data_deck_missing_from_middle_pads_gap_at_correct_position(
    tmp_path: Path,
) -> None:
    tree = _build_middle_gap_scenario_tree(tmp_path)
    scenarios = discover_scenarios([tree["caso_a"], tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    chained = data.series("GHID_SIN", "", "caso_b", None)
    assert len(chained) == _STAGES_PER_DECK * 3
    assert all(value is not None for value in chained[:_STAGES_PER_DECK])
    assert all(value is None for value in chained[_STAGES_PER_DECK : 2 * _STAGES_PER_DECK])
    assert all(value is not None for value in chained[2 * _STAGES_PER_DECK :])


# --- axis coverage mismatch between scenarios sharing a deck date (finding 4) -------------------


def test_build_dashboard_data_stage_count_mismatch_between_scenarios_warns(
    tmp_path: Path,
) -> None:
    tree = _build_stage_count_mismatch_tree(tmp_path)
    scenarios = discover_scenarios([tree["caso_a"], tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    axis_count = _MISMATCHED_STAGE_COUNTS["caso_a"]
    other_count = _MISMATCHED_STAGE_COUNTS["caso_b"]
    matching = [
        w
        for w in data.warnings()
        if "caso_b" in w and str(axis_count) in w and str(other_count) in w
    ]
    assert len(matching) == 1


def test_build_dashboard_data_first_start_mismatch_between_scenarios_warns(
    tmp_path: Path,
) -> None:
    tree = _build_start_mismatch_tree(tmp_path)
    scenarios = discover_scenarios([tree["caso_a"], tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    matching = [
        w
        for w in data.warnings()
        if "caso_b" in w and "2024-03-03 00:00:00" in w and "2024-03-03 06:00:00" in w
    ]
    assert len(matching) == 1


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
    # data.deck_dates[0] is deck_um's date (2024-03-03): the expected value must come from the
    # same deck the assertion below reads back, not from deck_dois (finding 3 of the epic-02
    # boundary review; this passed vacuously before build_scenario_tree gave each deck its own
    # seed, because every deck held byte-identical arrays).
    deck_path = scenario_tree["caso_a"] / "deck_um" / "sintese" / "TEMPO.parquet"
    raw = pd.read_parquet(deck_path, engine="pyarrow")
    expected_milp = float(raw.loc[raw["etapa"] == "MILP", "tempo"].iloc[0])

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    stored = data.scalars("TEMPO")
    assert len(stored) == _TEMPO_DISTINCT_ETAPA_COUNT * 2 * 2
    assert stored[("MILP", "caso_a", data.deck_dates[0])] == pytest.approx(expected_milp)


# PL executes three times in fixtures_sintese._TEMPO_ETAPAS: the store must hold their sum, not
# the last row's value (finding 1 of the epic-02 boundary review).
def test_build_dashboard_data_tempo_sums_repeated_pl_rows_instead_of_overwriting(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)
    deck_path = scenario_tree["caso_a"] / "deck_um" / "sintese" / "TEMPO.parquet"
    raw = pd.read_parquet(deck_path, engine="pyarrow")
    pl_rows = raw.loc[raw["etapa"] == "PL", "tempo"]
    assert len(pl_rows) == 3, "fixture drifted: PL must repeat exactly three times"
    expected_pl_sum = float(pl_rows.sum())
    last_pl_row_value = float(pl_rows.iloc[-1])
    assert expected_pl_sum != pytest.approx(last_pl_row_value), (
        "fixture drifted: the sum must differ from the last row for this test to be meaningful"
    )

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    stored = data.scalars("TEMPO")
    assert len(stored) == _TEMPO_DISTINCT_ETAPA_COUNT * 2 * 2
    assert stored[("PL", "caso_a", data.deck_dates[0])] == pytest.approx(expected_pl_sum)


# A NaN valor_esperado must store as None, never as float("nan") (finding 2 of the epic-02
# boundary review): json.dumps has no valid token for NaN, and the browser fails to parse it.
def test_build_dashboard_data_nan_scalar_round_trips_as_none_and_stays_json_clean(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    path = scenario_tree["caso_a"] / "deck_um" / "sintese" / "CUSTOS.parquet"
    _rewrite_parquet(
        path,
        lambda raw: raw.assign(
            valor_esperado=raw["valor_esperado"].where(raw["parcela"] != "FUTURO", float("nan"))
        ),
    )
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_a")

    stored = data.scalars("CUSTOS")
    key = ("FUTURO", "caso_a", data.deck_dates[0])
    assert stored[key] is None
    assert json.dumps({f"{k[0]}|{k[1]}|{k[2]}": v for k, v in stored.items()})


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


# A duplicate (entity_id, estagio) key must raise SchemaError naming the file and the entity
# instead of pandas.DataFrame.pivot's bare ValueError (finding 6 of the epic-02 boundary review).
# read_series' own uniqueness check is over the wider (codigo_usina, codigo_ree,
# codigo_submercado, estagio) key and does not catch this.
def test_build_dashboard_data_duplicate_entity_id_at_same_stage_raises_schema_error(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    path = scenario_tree["caso_a"] / "deck_um" / "sintese" / "GHID_UHE.parquet"
    _rewrite_parquet(path, _duplicate_entity_under_new_ree)
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    with pytest.raises(SchemaError, match="entidade '1'"):
        build_dashboard_data(scenarios, settings=settings, reference="caso_a")


# A non-numeric scalar value column must raise SchemaError naming the file and the column,
# instead of a bare ValueError from float() (finding 9 of the epic-02 boundary review).
def test_build_dashboard_data_non_numeric_custos_value_raises_schema_error(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    path = scenario_tree["caso_a"] / "deck_um" / "sintese" / "CUSTOS.parquet"
    _rewrite_parquet(path, lambda raw: raw.assign(valor_esperado=["abc"] * len(raw)))
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    settings = _build_settings(tmp_path)

    with pytest.raises(SchemaError, match="valor_esperado"):
        build_dashboard_data(scenarios, settings=settings, reference="caso_a")


# --- non-primary deck missing a registry file (finding 5) --------------------------------------


def test_build_dashboard_data_non_primary_deck_missing_registry_still_produces_dashboard(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    scenario_dir = _build_registry_gap_tree(tmp_path, omit_from="deck_2")
    scenarios = discover_scenarios([scenario_dir])
    settings = _build_settings(tmp_path)
    caplog.set_level(logging.WARNING, logger=_CONSOLIDATE_LOGGER_NAME)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_unico")

    assert data.value_count() > 0
    assert any("deck_2" in record.getMessage() for record in caplog.records)


def test_build_dashboard_data_primary_deck_missing_registry_raises(tmp_path: Path) -> None:
    scenario_dir = _build_registry_gap_tree(tmp_path, omit_from="deck_1")
    scenarios = discover_scenarios([scenario_dir])
    settings = _build_settings(tmp_path)

    with pytest.raises(DataFileError):
        build_dashboard_data(scenarios, settings=settings, reference="caso_unico")


# --- submarket present in data but absent from the registry (finding 8) ------------------------


def test_build_dashboard_data_submarket_absent_from_registry_but_present_in_data_warns(
    tmp_path: Path,
) -> None:
    scenario_dir = _build_registry_missing_submarket_tree(tmp_path)
    scenarios = discover_scenarios([scenario_dir])
    settings = _build_settings(tmp_path, include_fictitious=True)

    data = build_dashboard_data(scenarios, settings=settings, reference="caso_unico")

    assert {e.entity_id for e in data.entities("CMO_SBM")} == {"1", "2"}
    matching = [
        w
        for w in data.warnings()
        if "CMO_SBM" in w and "caso_unico" in w and "descartado(s): 3" in w
    ]
    assert len(matching) == 1


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
