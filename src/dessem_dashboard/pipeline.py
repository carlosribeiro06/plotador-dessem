"""Orchestrate scenario comparison into a dashboard HTML file.

Owns the single top-level entry point the CLI calls after resolving arguments and
before writing the run manifest.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from dessem_dashboard.config import Settings
from dessem_dashboard.dashboard.builder import output_volumes, write_dashboard
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.logging_setup import log_step

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    """Outcome of a `run` call, ready to feed the run manifest."""

    output_file: Path
    data_volumes: dict[str, int]
    warnings: list[str] = field(default_factory=list)


def run(
    *,
    scenario_dirs: Sequence[Path],
    output_file: Path,
    reference: str,
    settings: Settings,
    initial_mode: str = "encadeado",
) -> RunResult:
    """Compare the given scenarios and write the dashboard to `output_file`.

    Composes discovery, consolidation, HTML rendering and volume measurement, in that order:
    `output_volumes` must run after `write_dashboard` because its `bytes_html` field stats the
    written file. Every `DashboardError` subclass raised by a composed function propagates
    unchanged, since only `cli.main` decides how to turn it into an exit code.
    """
    start = time.perf_counter()
    scenarios = discover_scenarios(
        scenario_dirs, sintese_dirname=settings.discovery.sintese_dirname
    )
    data = build_dashboard_data(scenarios, settings=settings, reference=reference)
    written_file = write_dashboard(
        data, settings=settings, output_file=output_file, initial_mode=initial_mode
    )
    volumes = output_volumes(data, settings=settings, output_file=written_file)

    log_step(
        logger,
        "Execução do pipeline concluída",
        **volumes,
        avisos=len(data.warnings()),
        elapsed_s=time.perf_counter() - start,
    )
    return RunResult(output_file=written_file, data_volumes=volumes, warnings=list(data.warnings()))
