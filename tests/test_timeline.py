"""Tests for dessem_dashboard.data.timeline."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.data.timeline import (
    align_deck_dates,
    chaining_window,
    load_deck_timeline,
    order_timelines,
    validate_chaining,
)
from dessem_dashboard.errors import DataFileError, SchemaError
from dessem_dashboard.models.entities import DeckRef, DeckTimeline, Stage
from fixtures_sintese import make_sintese_dir

# Defaults of tests.fixtures_sintese.make_sintese_dir, which the sintese_dir fixture uses as-is;
# also acceptance criterion 1's own numbers (n_stages=6, half_hour_stages=4, long_stage_hours=2.0).
_GENERATOR_N_STAGES = 6
_BASE = pd.Timestamp("2024-03-03T00:00:00", tz="UTC")


def _write_est_parquet(
    directory: Path,
    *,
    estagio: Sequence[int],
    starts: Sequence[pd.Timestamp],
    ends: Sequence[pd.Timestamp],
) -> DeckRef:
    """Write a minimal EST.parquet with exactly the given rows and return its DeckRef."""
    directory.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "estagio": pd.array(list(estagio), dtype="int64"),
            "data_inicio": pd.array(list(starts), dtype="datetime64[ns, UTC]"),
            "data_fim": pd.array(list(ends), dtype="datetime64[ns, UTC]"),
        }
    )
    frame.to_parquet(directory / "EST.parquet", index=False)
    return DeckRef(name=directory.parent.name, path=directory.parent, sintese_dir=directory)


def _build_stages(
    first_start: pd.Timestamp, count: int, *, half_hour_count: int, long_hours: float = 2.0
) -> tuple[Stage, ...]:
    """Build count synthetic Stage records starting at first_start, mirroring fixtures_sintese."""
    stages: list[Stage] = []
    current = first_start
    for position in range(count):
        duration = 0.5 if position < half_hour_count else long_hours
        end = current + pd.Timedelta(hours=duration)
        stages.append(Stage(index=position + 1, start=current, end=end, duration_hours=duration))
        current = end
    return tuple(stages)


def _build_timeline(deck_date: date, stages: tuple[Stage, ...], *, name: str) -> DeckTimeline:
    """Build a DeckTimeline around a placeholder DeckRef, for tests that need no real files."""
    deck = DeckRef(name=name, path=Path(), sintese_dir=Path())
    return DeckTimeline(deck=deck, deck_date=deck_date, stages=stages)


# --- load_deck_timeline --------------------------------------------------------------------


def test_load_deck_timeline_generator_defaults_match_acceptance_criteria(sintese_dir: Path) -> None:
    deck = DeckRef(name="deck_qualquer", path=sintese_dir.parent, sintese_dir=sintese_dir)

    timeline = load_deck_timeline(deck)

    assert timeline.deck_date == date(2024, 3, 3)
    assert len(timeline.stages) == _GENERATOR_N_STAGES
    assert timeline.stages[0].index == 1
    assert timeline.stages[5].index == 6
    assert timeline.stages[0].duration_hours == pytest.approx(0.5)
    assert timeline.stages[5].duration_hours == pytest.approx(2.0)
    assert timeline.stages[0].start == pd.Timestamp("2024-03-03T00:00:00", tz="UTC")


def test_load_deck_timeline_deck_date_comes_from_data_not_from_folder_name(tmp_path: Path) -> None:
    sintese = tmp_path / "pasta_2099-12-31" / "sintese"
    make_sintese_dir(sintese, first_stage_start=datetime(2024, 3, 5, tzinfo=UTC))
    deck = DeckRef(name="pasta_2099-12-31", path=sintese.parent, sintese_dir=sintese)

    timeline = load_deck_timeline(deck)

    assert timeline.deck_date == date(2024, 3, 5)


def test_load_deck_timeline_non_contiguous_estagio_raises_naming_deck_and_missing_index(
    tmp_path: Path,
) -> None:
    sintese = tmp_path / "deck_falho" / "sintese"
    starts = [_BASE, _BASE + pd.Timedelta(hours=0.5), _BASE + pd.Timedelta(hours=2.0)]
    ends = [start + pd.Timedelta(hours=0.5) for start in starts]
    deck = _write_est_parquet(sintese, estagio=[1, 2, 4], starts=starts, ends=ends)

    with pytest.raises(SchemaError) as exc_info:
        load_deck_timeline(deck)

    message = str(exc_info.value)
    assert "deck_falho" in message
    assert message.endswith("ausente: 3")


def test_load_deck_timeline_estagio_not_starting_at_one_raises_naming_first_index(
    tmp_path: Path,
) -> None:
    sintese = tmp_path / "deck_sem_inicio" / "sintese"
    starts = [_BASE, _BASE + pd.Timedelta(hours=0.5), _BASE + pd.Timedelta(hours=1.0)]
    ends = [start + pd.Timedelta(hours=0.5) for start in starts]
    deck = _write_est_parquet(sintese, estagio=[2, 3, 4], starts=starts, ends=ends)

    with pytest.raises(SchemaError) as exc_info:
        load_deck_timeline(deck)

    message = str(exc_info.value)
    assert "deck_sem_inicio" in message
    assert message.endswith("ausente: 1")


def test_load_deck_timeline_stage_with_end_equal_to_start_raises_naming_stage(
    tmp_path: Path,
) -> None:
    sintese = tmp_path / "deck_duracao_nula" / "sintese"
    starts = [_BASE, _BASE + pd.Timedelta(hours=0.5), _BASE + pd.Timedelta(hours=0.5)]
    ends = [
        _BASE + pd.Timedelta(hours=0.5),
        _BASE + pd.Timedelta(hours=0.5),
        _BASE + pd.Timedelta(hours=1.5),
    ]
    deck = _write_est_parquet(sintese, estagio=[1, 2, 3], starts=starts, ends=ends)

    with pytest.raises(SchemaError) as exc_info:
        load_deck_timeline(deck)

    message = str(exc_info.value)
    assert "deck_duracao_nula" in message
    assert "estágio 2" in message


def test_load_deck_timeline_missing_est_parquet_raises_data_file_error(tmp_path: Path) -> None:
    sintese = tmp_path / "deck_vazio" / "sintese"
    sintese.mkdir(parents=True)
    deck = DeckRef(name="deck_vazio", path=sintese.parent, sintese_dir=sintese)

    with pytest.raises(DataFileError):
        load_deck_timeline(deck)


def test_load_deck_timeline_logs_per_deck_info_line(
    sintese_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    deck = DeckRef(name="deck_log", path=sintese_dir.parent, sintese_dir=sintese_dir)

    load_deck_timeline(deck)

    per_deck = [
        record.getMessage() for record in caplog.records if "deck=deck_log" in record.getMessage()
    ]
    assert per_deck
    assert "data=03/03/2024" in per_deck[0]
    assert f"estagios={_GENERATOR_N_STAGES}" in per_deck[0]


# --- chaining_window -------------------------------------------------------------------------


def test_chaining_window_returns_first_n_stages(sintese_dir: Path) -> None:
    deck = DeckRef(name="deck", path=sintese_dir.parent, sintese_dir=sintese_dir)
    timeline = load_deck_timeline(deck)

    window = chaining_window(timeline, stages_per_deck=4)

    assert window == timeline.stages[:4]
    assert len(window) == 4


def test_chaining_window_returns_every_stage_when_deck_is_shorter(sintese_dir: Path) -> None:
    deck = DeckRef(name="deck", path=sintese_dir.parent, sintese_dir=sintese_dir)
    timeline = load_deck_timeline(deck)

    window = chaining_window(timeline, stages_per_deck=100)

    assert window == timeline.stages
    assert len(window) == _GENERATOR_N_STAGES


# --- order_timelines --------------------------------------------------------------------------


def test_order_timelines_sorts_by_deck_date_regardless_of_folder_name() -> None:
    timeline_alfa = _build_timeline(date(2024, 3, 4), (), name="alfa")
    timeline_zulu = _build_timeline(date(2024, 3, 3), (), name="zulu")

    ordered = order_timelines([timeline_alfa, timeline_zulu])

    assert [timeline.deck.name for timeline in ordered] == ["zulu", "alfa"]


def test_order_timelines_duplicate_deck_date_raises_naming_both_decks() -> None:
    timeline_zulu = _build_timeline(date(2024, 3, 3), (), name="zulu")
    timeline_alfa = _build_timeline(date(2024, 3, 3), (), name="alfa")

    with pytest.raises(SchemaError) as exc_info:
        order_timelines([timeline_zulu, timeline_alfa])

    message = str(exc_info.value)
    assert "alfa" in message
    assert "zulu" in message
    assert "03/03/2024" in message


# --- validate_chaining ------------------------------------------------------------------------


def test_validate_chaining_short_deck_returns_message_naming_date_and_both_counts() -> None:
    stages = _build_stages(_BASE, 10, half_hour_count=10)
    timeline = _build_timeline(date(2024, 3, 3), stages, name="deck_curto")

    warnings = validate_chaining([timeline], stages_per_deck=48)

    assert len(warnings) == 1
    assert "03/03/2024" in warnings[0]
    assert "10" in warnings[0]
    assert "48" in warnings[0]


def test_validate_chaining_thirty_minute_gap_returns_one_lacuna_message() -> None:
    stages_a = _build_stages(_BASE, 48, half_hour_count=48)
    timeline_a = _build_timeline(date(2024, 3, 3), stages_a, name="deck_a")
    start_b = _BASE + pd.Timedelta(hours=24, minutes=30)
    stages_b = _build_stages(start_b, 48, half_hour_count=48)
    timeline_b = _build_timeline(start_b.date(), stages_b, name="deck_b")

    warnings = validate_chaining([timeline_a, timeline_b], stages_per_deck=48)

    assert len(warnings) == 1
    assert "lacuna" in warnings[0]
    assert "03/03/2024" in warnings[0]
    assert "04/03/2024" in warnings[0]


def test_validate_chaining_thirty_minute_overlap_returns_one_overlap_message() -> None:
    stages_a = _build_stages(_BASE, 48, half_hour_count=48)
    timeline_a = _build_timeline(date(2024, 3, 3), stages_a, name="deck_a")
    start_b = _BASE + pd.Timedelta(hours=24) - pd.Timedelta(minutes=30)
    stages_b = _build_stages(start_b, 48, half_hour_count=48)
    timeline_b = _build_timeline(start_b.date(), stages_b, name="deck_b")

    warnings = validate_chaining([timeline_a, timeline_b], stages_per_deck=48)

    assert len(warnings) == 1
    assert "sobreposição" in warnings[0]


def test_validate_chaining_empty_window_skips_boundary_comparison() -> None:
    timeline_empty = _build_timeline(date(2024, 3, 3), (), name="deck_sem_estagios")
    stages_b = _build_stages(_BASE + pd.Timedelta(hours=24), 48, half_hour_count=48)
    timeline_b = _build_timeline(date(2024, 3, 4), stages_b, name="deck_b")

    warnings = validate_chaining([timeline_empty, timeline_b], stages_per_deck=48)

    assert len(warnings) == 1
    assert "03/03/2024" in warnings[0]
    assert "0 estágio(s)" in warnings[0]


def test_validate_chaining_scenario_tree_caso_a_returns_empty_list_at_forty_eight(
    scenario_tree: dict[str, Path],
) -> None:
    (scenario,) = discover_scenarios([scenario_tree["caso_a"]])
    timelines = [load_deck_timeline(deck) for deck in scenario.decks]
    ordered = order_timelines(timelines)

    warnings = validate_chaining(ordered, stages_per_deck=48)

    assert warnings == []


def test_validate_chaining_scenario_tree_caso_a_reports_gap_at_four(
    scenario_tree: dict[str, Path],
) -> None:
    (scenario,) = discover_scenarios([scenario_tree["caso_a"]])
    timelines = [load_deck_timeline(deck) for deck in scenario.decks]
    ordered = order_timelines(timelines)

    warnings = validate_chaining(ordered, stages_per_deck=4)

    assert len(warnings) == 1
    assert "lacuna" in warnings[0]
    assert "03/03/2024" in warnings[0]
    assert "04/03/2024" in warnings[0]


# --- align_deck_dates -------------------------------------------------------------------------


def test_align_deck_dates_union_and_one_warning_per_missing_pair() -> None:
    scenario_timelines = {
        "caso_a": [
            _build_timeline(date(2024, 3, 3), (), name="d1"),
            _build_timeline(date(2024, 3, 4), (), name="d2"),
        ],
        "caso_b": [_build_timeline(date(2024, 3, 3), (), name="d1")],
    }

    dates, warnings = align_deck_dates(scenario_timelines)

    assert dates == (date(2024, 3, 3), date(2024, 3, 4))
    assert len(warnings) == 1
    assert "caso_b" in warnings[0]
    assert "04/03/2024" in warnings[0]


def test_align_deck_dates_every_scenario_has_every_date_returns_no_warnings() -> None:
    scenario_timelines = {
        "caso_a": [_build_timeline(date(2024, 3, 3), (), name="d1")],
        "caso_b": [_build_timeline(date(2024, 3, 3), (), name="d1")],
    }

    dates, warnings = align_deck_dates(scenario_timelines)

    assert dates == (date(2024, 3, 3),)
    assert warnings == []
