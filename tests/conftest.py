"""Shared pytest fixtures: synthetic sintese/ directories built in tmp_path.

No test may depend on the real, gitignored study data. Every fixture here is fully synthetic,
built through fixtures_sintese.make_sintese_dir.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fixtures_sintese import make_sintese_dir

# The chaining window default (chaining.stages_per_deck in settings.json): 48 half-hour stages
# cover exactly one day, so the window of one deck ends exactly where the next deck begins.
_CHAINING_WINDOW_STAGES = 48
_CHAINED_N_STAGES = 50
_CHAINED_LONG_STAGE_HOURS = 6.0
_DECK_DIR_NAMES: tuple[str, str] = ("deck_um", "deck_dois")
_DECK_STARTS: tuple[datetime, datetime] = (
    datetime(2024, 3, 3, tzinfo=UTC),
    datetime(2024, 3, 4, tzinfo=UTC),
)


@pytest.fixture
def sintese_dir(tmp_path: Path) -> Path:
    """A single synthetic sintese/ directory built with the generator's default parameters."""
    return make_sintese_dir(tmp_path / "sintese", first_stage_start=_DECK_STARTS[0])


def build_scenario_tree(root: Path) -> dict[str, Path]:
    """Build the two-scenario, two-deck-per-scenario tree backing the scenario_tree fixture.

    A plain function, not a fixture, so tests.test_fixtures_sintese can call it directly and
    time it without depending on pytest's fixture-resolution machinery.
    """
    tree: dict[str, Path] = {}
    for scenario_name in ("caso_a", "caso_b"):
        scenario_dir = root / scenario_name
        for deck_name, deck_start in zip(_DECK_DIR_NAMES, _DECK_STARTS, strict=True):
            make_sintese_dir(
                scenario_dir / deck_name / "sintese",
                first_stage_start=deck_start,
                n_stages=_CHAINED_N_STAGES,
                half_hour_stages=_CHAINING_WINDOW_STAGES,
                long_stage_hours=_CHAINED_LONG_STAGE_HOURS,
            )
        tree[scenario_name] = scenario_dir
    return tree


@pytest.fixture
def scenario_tree(tmp_path: Path) -> dict[str, Path]:
    """Two scenarios, caso_a and caso_b, each with two decks under non-date directory names.

    Both decks of both scenarios share a 48-stage half-hourly chaining window starting on
    consecutive calendar days, so the window of the first deck ends exactly where the second
    deck's first stage begins.
    """
    return build_scenario_tree(tmp_path)
