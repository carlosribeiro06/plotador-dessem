"""End-to-end regression of the continuous Encadeado axis on a gap-and-overlap tree.

Drives the whole pipeline (discovery, timeline loading, chaining validation, consolidation,
payload, HTML write) over synthetic decks that really overlap and really leave a gap, then reads
the payload back out of the written document. Reads no real data: every deck is built through
fixtures_sintese.make_sintese_dir, and the settings are a private hand-built dict, so a change of
the repository's own settings.json cannot move the literal labels asserted here.

The tree has two scenarios, caso_a and caso_b, each with three decks starting 2026-01-07,
2026-01-08 and 2026-09-10 (all 00:00 UTC), each holding 50 stages: 48 of 0.5 h followed by two
of 6 h, so one deck spans 36 h. With chaining.stages_per_deck = 50 the 07/01 window ends on
08/01 12:00, after the 08/01 deck starts (overlap), and the 08/01 window ends on 09/01 12:00,
eight months before the 10/09 deck starts (gap). One tree exercises both.

Measured reference values, from a probe run through pipeline.run during ticket-006's refinement
(default date format "%d/%m/%Y %H:%M"): 150 chained stages, 151 positions, the chained span
6480 minutes (3 decks x 2160), chained end 2026-09-11 12:00.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from dessem_dashboard import pipeline
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.pipeline import RunResult
from fixtures_sintese import make_sintese_dir

_SCENARIO_NAMES = ("caso_a", "caso_b")
_DECK_DIR_NAMES = ("deck_0", "deck_1", "deck_2")
_DECK_STARTS = (
    datetime(2026, 1, 7, tzinfo=UTC),
    datetime(2026, 1, 8, tzinfo=UTC),
    datetime(2026, 9, 10, tzinfo=UTC),
)
_DECK_KEYS = ("07/01/2026", "08/01/2026", "10/09/2026")
_CHAINED_KEY = "encadeado"

_STAGES_PER_DECK = 50
_N_STAGES = 50
_HALF_HOUR_STAGES = 48
_LONG_STAGE_HOURS = 6.0
_LONG_STAGE_MINUTES = 360

# Seed of (scenario_index, deck_index) is _BASE_SEED + 3 * scenario_index + deck_index, so each of
# the six decks holds its own deterministic array of values.
_BASE_SEED = 300

_AXIS_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"
_SERIES_KIND = "SERIES"

# Chained index of the first stage after the gap: the stage before it (index 99) is the last 6 h
# stage of the 08/01 window, which ends where the calendar says nothing and the axis says 6 h.
_FIRST_STAGE_AFTER_GAP = 100

_OVERLAP_WARNING_PREFIX = (
    "Encadeamento apresenta sobreposição entre os decks de 07/01/2026 e 08/01/2026"
)
_GAP_WARNING_PREFIX = "Encadeamento apresenta lacuna entre os decks de 08/01/2026 e 10/09/2026"

_PAYLOAD_OPEN_TAG = '<script id="dashboard-payload" type="application/json">'
_SCRIPT_CLOSE_TAG = "</script>"


@dataclass(frozen=True)
class _GapOverlapBuild:
    """The outcome of one pipeline.run over the gap-and-overlap tree."""

    result: RunResult
    payload: dict[str, Any]


def _settings_dict() -> dict[str, Any]:
    """Build a settings.json-shaped dict with chaining.stages_per_deck = 50.

    Copied from tests/test_pipeline.py's helper of the same name (per-module convention: no
    import of a sibling module's private helper), minus its sintese_dirname knob. The format
    "%d/%m/%Y %H:%M" is pinned here on purpose: the tick and hover labels asserted below are
    literals. time.stage_groups is reduced to the single PL group, as in that module.
    """
    return {
        "project": "dessem-dashboard",
        "paths": {
            "output_dir": "output",
            "log_dir": "logs",
            "logo_file": "logo/MarcasONS_Secundarias_verticais_Verde.png",
        },
        "logging": {
            "level": "INFO",
            "file": "logs/dashboard.log",
            "rotate_max_bytes": 5242880,
            "rotate_backups": 5,
            "use_rich": True,
        },
        "discovery": {"sintese_dirname": "sintese"},
        "chaining": {"stages_per_deck": _STAGES_PER_DECK},
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
        "charts": {"disabled": []},
    }


def _build_settings(root: Path) -> Settings:
    """Write settings.json under root and load it, exercising the real config path."""
    target = root / "settings.json"
    target.write_text(json.dumps(_settings_dict()), encoding="utf-8")
    return load_settings(target)


def _build_gap_overlap_tree(root: Path) -> dict[str, Path]:
    """Build the two-scenario, three-deck tree under root and return each scenario's directory."""
    tree: dict[str, Path] = {}
    for scenario_index, scenario_name in enumerate(_SCENARIO_NAMES):
        scenario_dir = root / scenario_name
        for deck_index, (deck_name, deck_start) in enumerate(
            zip(_DECK_DIR_NAMES, _DECK_STARTS, strict=True)
        ):
            make_sintese_dir(
                scenario_dir / deck_name / "sintese",
                first_stage_start=deck_start,
                n_stages=_N_STAGES,
                half_hour_stages=_HALF_HOUR_STAGES,
                long_stage_hours=_LONG_STAGE_HOURS,
                seed=_BASE_SEED + 3 * scenario_index + deck_index,
            )
        tree[scenario_name] = scenario_dir
    return tree


def _extract_payload(document: str) -> dict[str, Any]:
    """Parse the embedded JSON payload out of a built document.

    Copied from tests/test_integration_exemplo.py. Reverses payload_json's `<` escape before
    parsing; payload_json writes allow_nan=False, so a successful parse also proves that no NaN or
    infinity reached the payload.
    """
    start = document.index(_PAYLOAD_OPEN_TAG) + len(_PAYLOAD_OPEN_TAG)
    end = document.index(_SCRIPT_CLOSE_TAG, start)
    text = document[start:end].replace("\\u003C", "<")
    return json.loads(text)


@pytest.fixture(scope="module")
def gap_overlap_build(tmp_path_factory: pytest.TempPathFactory) -> _GapOverlapBuild:
    """Run the pipeline once over the gap-and-overlap tree; every test of this module reads it."""
    root = tmp_path_factory.mktemp("gap_overlap")
    scenario_dirs = _build_gap_overlap_tree(root / "tree")
    settings = _build_settings(root)
    output_file = root / "out" / "dashboard.html"

    result = pipeline.run(
        scenario_dirs=[scenario_dirs[name] for name in _SCENARIO_NAMES],
        output_file=output_file,
        reference=_SCENARIO_NAMES[0],
        settings=settings,
    )

    payload = _extract_payload(output_file.read_text(encoding="utf-8"))
    return _GapOverlapBuild(result=result, payload=payload)


def _check_continuous_across_gap(positions: list[Any]) -> None:
    """Assert positions are ints, strictly increasing, and 360 minutes wide across the gap.

    The width between chained index 99 and 100 must be that of the 6 h stage before the gap,
    never the calendar distance between 09/01 and 10/09.
    """
    not_int = [index for index, position in enumerate(positions) if type(position) is not int]
    assert not not_int, f"positions at indices {not_int[:5]} are not int"

    not_increasing = [
        index for index in range(1, len(positions)) if positions[index] <= positions[index - 1]
    ]
    assert not not_increasing, (
        f"positions are not strictly increasing at indices {not_increasing[:5]}"
    )

    gap_width = positions[_FIRST_STAGE_AFTER_GAP] - positions[_FIRST_STAGE_AFTER_GAP - 1]
    assert gap_width == _LONG_STAGE_MINUTES, (
        f"width across the gap is {gap_width} minutes, expected {_LONG_STAGE_MINUTES}"
    )


def _expected_deck_entry(first: datetime) -> dict[str, object]:
    """Return the Por deck axis entry of a deck whose first stage starts at first.

    Computed with datetime arithmetic only, independently of the payload code: 48 half-hour
    starts from first, then the two 6 h stages at first + 24 h and first + 30 h, ending at
    first + 36 h.
    """
    starts = [first + timedelta(minutes=30 * index) for index in range(_HALF_HOUR_STAGES)]
    starts.append(first + timedelta(hours=24))
    starts.append(first + timedelta(hours=30))
    end = first + timedelta(hours=36)
    return {
        "starts": [start.strftime(_AXIS_TIMESTAMP_FORMAT) for start in starts],
        "end": end.strftime(_AXIS_TIMESTAMP_FORMAT),
    }


def test_run_gap_overlap_tree_reports_overlap_then_gap_and_schema_version_2(
    gap_overlap_build: _GapOverlapBuild,
) -> None:
    warnings = gap_overlap_build.result.warnings
    payload = gap_overlap_build.payload

    # Two scenarios with identical deck dates still report each chaining warning once, because
    # DashboardData.add_warning drops duplicates.
    assert len(warnings) == 2, f"expected exactly 2 warnings, got {warnings}"
    assert warnings[0].startswith(_OVERLAP_WARNING_PREFIX), warnings[0]
    assert warnings[1].startswith(_GAP_WARNING_PREFIX), warnings[1]
    assert payload["schema_version"] == 2
    assert payload["deck_dates"] == list(_DECK_KEYS)


def test_chained_positions_gap_tree_are_continuous_across_the_gap(
    gap_overlap_build: _GapOverlapBuild,
) -> None:
    chained = gap_overlap_build.payload["axes"][_CHAINED_KEY]
    positions = chained["positions"]
    starts = chained["starts"]
    hover_labels = chained["hover_labels"]

    _check_continuous_across_gap(positions)

    assert len(positions) == 151
    assert len(starts) == 150
    assert positions[0] == 0
    assert positions[150] == 6480
    assert starts[99] == "2026-01-09 06:00"
    assert starts[_FIRST_STAGE_AFTER_GAP] == "2026-09-10 00:00"
    assert chained["end"] == "2026-09-11 12:00"
    assert hover_labels["3960"] == "09/01/2026 06:00"
    assert hover_labels["4320"] == "10/09/2026 00:00"
    assert hover_labels["6480"] == "11/09/2026 12:00"
    assert set(hover_labels) == {str(position) for position in positions}


def test_continuity_check_calendar_positions_are_rejected(
    gap_overlap_build: _GapOverlapBuild,
) -> None:
    chained = gap_overlap_build.payload["axes"][_CHAINED_KEY]
    real_positions = chained["positions"]
    _check_continuous_across_gap(real_positions)

    calendar_stamps = [
        datetime.strptime(stamp, _AXIS_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
        for stamp in [*chained["starts"], chained["end"]]
    ]
    calendar_positions = [
        int((stamp - calendar_stamps[0]).total_seconds() // 60) for stamp in calendar_stamps
    ]
    assert calendar_positions != real_positions, "calendar positions equal the plotted ones"
    with pytest.raises(AssertionError):
        _check_continuous_across_gap(calendar_positions)

    # The calendar sequence also fails the strictly-increasing check (the overlap repeats a
    # start), which can mask the width check. Restoring only the calendar gap on top of the real
    # positions leaves the sequence int and strictly increasing, so the width check alone must
    # reject it.
    calendar_gap_minutes = (
        calendar_positions[_FIRST_STAGE_AFTER_GAP] - calendar_positions[_FIRST_STAGE_AFTER_GAP - 1]
    )
    gap_restored = [
        position + (calendar_gap_minutes - _LONG_STAGE_MINUTES)
        if index >= _FIRST_STAGE_AFTER_GAP
        else position
        for index, position in enumerate(real_positions)
    ]
    with pytest.raises(AssertionError, match="width across the gap"):
        _check_continuous_across_gap(gap_restored)


def test_chained_positions_overlap_tree_run_forward_with_repeated_tick_label(
    gap_overlap_build: _GapOverlapBuild,
) -> None:
    chained = gap_overlap_build.payload["axes"][_CHAINED_KEY]
    positions = chained["positions"]
    starts = chained["starts"]

    assert positions[48:51] == [1440, 1800, 2160]
    assert starts[48] == "2026-01-08 00:00"
    assert starts[50] == "2026-01-08 00:00"
    assert chained["tick_values"] == [0, 720, 1440, 2160, 2880, 3600, 4320, 5040, 5760]
    assert chained["tick_labels"] == [
        "07/01/2026 00:00",
        "07/01/2026 12:00",
        "08/01/2026 00:00",
        "08/01/2026 00:00",
        "08/01/2026 12:00",
        "09/01/2026 00:00",
        "10/09/2026 00:00",
        "10/09/2026 12:00",
        "11/09/2026 00:00",
    ]
    # Two ticks sharing one label is intended: the overlap makes the 08/01 00:00 instant occur
    # twice on the elapsed-time axis (chained_axis.py, chained_tick_indices).
    assert chained["tick_labels"][2] == chained["tick_labels"][3] == "08/01/2026 00:00"


def test_deck_axes_gap_tree_keep_starts_and_end_only(
    gap_overlap_build: _GapOverlapBuild,
) -> None:
    axes = gap_overlap_build.payload["axes"]

    for deck_key, first in zip(_DECK_KEYS, _DECK_STARTS, strict=True):
        assert axes[deck_key] == _expected_deck_entry(first), f"deck axis '{deck_key}' changed"
    assert axes["10/09/2026"]["end"] == "2026-09-11 12:00"


def test_series_gap_tree_align_by_stage_index(gap_overlap_build: _GapOverlapBuild) -> None:
    payload = gap_overlap_build.payload
    chained_length = len(payload["axes"][_CHAINED_KEY]["positions"]) - 1
    expected_axis_keys = {*_DECK_KEYS, _CHAINED_KEY}
    visited_arrays = 0

    for chart_key, chart in payload["charts"].items():
        if chart["kind"] != _SERIES_KIND:
            continue
        for entity_id, by_scenario in chart["series"].items():
            for scenario in _SCENARIO_NAMES:
                where = f"chart '{chart_key}', entity '{entity_id}', scenario '{scenario}'"
                assert scenario in by_scenario, f"{where}: scenario missing"
                by_axis = by_scenario[scenario]
                assert set(by_axis) == expected_axis_keys, f"{where}: axis keys {set(by_axis)}"
                for axis_key, values in by_axis.items():
                    expected_length = chained_length if axis_key == _CHAINED_KEY else _N_STAGES
                    assert len(values) == expected_length, (
                        f"{where}, axis '{axis_key}': {len(values)} values, "
                        f"expected {expected_length}"
                    )
                    visited_arrays += 1

    assert chained_length == 150
    assert visited_arrays > 0
