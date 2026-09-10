"""Scenario and deck discovery: the entry point of the data layer.

Discovery is deliberately **non-recursive**: only the immediate subdirectories of a scenario
directory are candidate decks, per `planning-context.md` decision 4. Deck folder names are
free-form and are never parsed as dates; the deck date is `EST.parquet`'s job (ticket-016). A
scenario directory that itself directly contains a synthesis subfolder — the flat
`exemplo/sintese/` structure sample — has zero decks among its immediate subdirectories and
therefore raises the same fatal "no deck" error as any other empty scenario, so a wrongly-shaped
tree fails loudly instead of silently producing a single-deck dashboard.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from dessem_dashboard.errors import DiscoveryError
from dessem_dashboard.logging_setup import log_step
from dessem_dashboard.models.entities import DeckRef, ScenarioRef

logger = logging.getLogger(__name__)


def _decks_of(scenario_path: Path, sintese_dirname: str) -> tuple[DeckRef, ...]:
    """Return scenario_path's immediate subdirectories that hold a sintese_dirname child."""
    decks = [
        DeckRef(name=entry.name, path=entry, sintese_dir=entry / sintese_dirname)
        for entry in sorted(scenario_path.iterdir())
        if entry.is_dir() and (entry / sintese_dirname).is_dir()
    ]
    return tuple(decks)


def discover_scenarios(
    paths: Sequence[Path], *, sintese_dirname: str = "sintese"
) -> tuple[ScenarioRef, ...]:
    """Discover one `ScenarioRef` per path, in the given order, each with decks sorted by name.

    Reads directory entries only; opens no file. Raises `DiscoveryError` when `paths` is empty,
    when a path does not exist or is not a directory, when a scenario has zero decks, or when
    two paths share a basename, since the basename is the legend label and must be unique. A
    `PermissionError` raised while listing a directory propagates unchanged.
    """
    if not paths:
        raise DiscoveryError("Nenhum diretório de cenário foi informado para a descoberta")

    labels: dict[str, Path] = {}
    scenarios: list[ScenarioRef] = []
    for path in paths:
        scenario_path = path.resolve()
        if not scenario_path.is_dir():
            raise DiscoveryError(
                f"Diretório de cenário não encontrado ou não é um diretório: '{scenario_path}'"
            )

        label = scenario_path.name
        if label in labels:
            raise DiscoveryError(
                f"Rótulo de cenário duplicado: '{label}'. Os diretórios '{labels[label]}' e "
                f"'{scenario_path}' têm o mesmo nome e gerariam a mesma legenda."
            )
        labels[label] = scenario_path

        decks = _decks_of(scenario_path, sintese_dirname)
        if not decks:
            raise DiscoveryError(
                f"Cenário '{label}' não contém nenhum deck: nenhum subdiretório imediato de "
                f"'{scenario_path}' possui uma pasta '{sintese_dirname}'"
            )

        log_step(logger, "Cenário descoberto", cenario=label, decks=len(decks))
        scenarios.append(ScenarioRef(label=label, path=scenario_path, decks=decks))

    log_step(
        logger,
        "Descoberta de cenários concluída",
        cenarios=len(scenarios),
        decks=sum(len(scenario.decks) for scenario in scenarios),
    )
    return tuple(scenarios)
