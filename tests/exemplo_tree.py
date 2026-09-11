"""Locate and validate the real DESSEM example scenario tree for the integration test.

Not a test module: it defines no ``test_*`` function, so pytest's default collection never picks
it up, following the precedent of ``tests/fixtures_sintese.py`` and ``tests/dashboard_document.py``.
Imported by ``tests/test_integration_exemplo.py`` here and by ``tests/test_parity.py`` in
ticket-035, so the two tickets share one tree-resolution implementation instead of duplicating it
or reaching into each other's private helpers.

Reads the ``DESSEM_DASHBOARD_EXEMPLO`` environment variable so a developer can point the test
suite at a copy of the example tree living outside the repository. Per epic decision E5-6, this is
the *only* place in the project that reads it: ``settings.json`` stays the single configuration
anchor for production code (CLAUDE.md), and this variable exists to redirect the *suite*, never
the program.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Environment variable a developer can set to point the suite at a copy of the example tree
#: living outside the repository. Exposed publicly so callers can quote it in a skip reason
#: without duplicating the literal string.
ENV_VAR: str = "DESSEM_DASHBOARD_EXEMPLO"

_SINTESE_DIRNAME = "sintese"
_EST_FILE_NAME = "EST.parquet"

# The documented build order (planning-context.md decision 15;
# docs/checklist-manual-dashboard.md step 12's `--casos exemplo/caso_oficial exemplo/caso_gurobi`),
# so an automated run selecting this pair describes the same artefact as the operator's manual
# walk.
_DOCUMENTED_PAIR: tuple[str, str] = ("caso_oficial", "caso_gurobi")


def exemplo_root() -> Path:
    """Return the root directory of the real example scenario tree.

    Reads ``os.environ[ENV_VAR]`` when it is set to a non-empty value; otherwise returns
    ``<repository root>/exemplo``, derived from this module's own location rather than the
    current working directory.
    """
    override = os.environ.get(ENV_VAR, "")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "exemplo"


def _has_sintese_deck(candidate: Path) -> bool:
    """Return whether candidate is an immediate subdirectory holding a sintese deck.

    Stricter than ``dessem_dashboard.data.discovery._decks_of``, not an exact mirror: it also
    requires ``EST.parquet`` to exist, because the deck date this suite reads comes from that
    file, and it hardcodes the ``sintese`` directory name (``_SINTESE_DIRNAME``) instead of
    reading the shipped ``settings.discovery.sintese_dirname`` that
    ``tests/test_integration_exemplo.py`` loads from disk. The stricter direction is the
    dangerous one: it can only make ``qualifying_scenarios()`` return too few paths, never too
    many, so a mismatch here degrades to every real-data test silently reporting SKIPPED while
    the suite stays green, rather than to a false positive. Never raises: any ``OSError`` while
    probing candidate resolves to ``False``.
    """
    try:
        if not candidate.is_dir():
            return False
        sintese_dir = candidate / _SINTESE_DIRNAME
        return sintese_dir.is_dir() and (sintese_dir / _EST_FILE_NAME).is_file()
    except OSError:
        return False


def _qualifies_as_scenario(candidate: Path) -> bool:
    """Return whether candidate qualifies as a scenario directory.

    Non-recursive, mirroring ``dessem_dashboard.data.discovery.discover_scenarios``' own rule:
    candidate qualifies when at least one of its own immediate subdirectories holds a sintese
    deck. A directory that itself directly contains a ``sintese/`` child -- the flat
    ``exemplo/sintese/`` structure sample -- has zero qualifying immediate subdirectories and
    therefore does not qualify, matching ``discover_scenarios``' "no deck" error path rather than
    silently treating it as a single-deck scenario. Never raises: a ``PermissionError`` or any
    other ``OSError`` while listing candidate resolves to ``False``.
    """
    try:
        if not candidate.is_dir():
            return False
        entries = tuple(candidate.iterdir())
    except OSError:
        return False
    return any(_has_sintese_deck(entry) for entry in entries)


def qualifying_scenarios(root: Path) -> tuple[Path, ...]:
    """Return root's immediate subdirectories that qualify as a scenario, sorted by name.

    Never raises: a missing root, a root that is a file, and a ``PermissionError`` while listing
    root all resolve to the empty tuple, so a caller's skip predicate can rely on this function
    alone under any filesystem condition.
    """
    try:
        if not root.is_dir():
            return ()
        entries = tuple(root.iterdir())
    except OSError:
        return ()
    qualifying = [entry for entry in entries if _qualifies_as_scenario(entry)]
    return tuple(sorted(qualifying, key=lambda path: path.name))


def documented_pair(root: Path) -> tuple[Path, Path] | None:
    """Return ``(caso_oficial, caso_gurobi)`` under root, in that documented order.

    Returns ``None`` unless both names qualify as a scenario under root (per
    ``qualifying_scenarios``).
    """
    qualifying_names = {path.name for path in qualifying_scenarios(root)}
    if not all(name in qualifying_names for name in _DOCUMENTED_PAIR):
        return None
    official_name, gurobi_name = _DOCUMENTED_PAIR
    return root / official_name, root / gurobi_name
