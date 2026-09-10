"""Shared data-layer records produced by scenario and deck discovery.

`DeckRef` and `ScenarioRef` are the shared vocabulary between `data.discovery`, `data.timeline`
and `data.consolidate`: plain records with no methods, so downstream modules attach behavior
without coupling it to construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DeckRef:
    """One deck: an immediate scenario subdirectory that holds a synthesis subfolder."""

    name: str
    path: Path
    sintese_dir: Path


@dataclass(frozen=True, slots=True)
class ScenarioRef:
    """One `--casos` entry: its legend label, its resolved path and its discovered decks."""

    label: str
    path: Path
    decks: tuple[DeckRef, ...]
