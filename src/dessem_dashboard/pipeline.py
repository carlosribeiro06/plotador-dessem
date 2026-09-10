"""Orchestrate scenario comparison into a dashboard HTML file.

Owns the single top-level entry point the CLI calls after resolving arguments and
before writing the run manifest.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from dessem_dashboard.config import Settings
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
) -> RunResult:
    """Compare the given scenarios and write the dashboard to `output_file`."""
    # Epic 5 ticket-033 replaces this body with parquet reading, consolidation and HTML generation.
    for scenario_dir in scenario_dirs:
        log_step(logger, "cenário recebido", diretorio=str(scenario_dir))
    log_step(logger, "arquivo de saída resolvido", saida=str(output_file))
    log_step(logger, "cenário de referência resolvido", referencia=reference)
    return RunResult(output_file=output_file, data_volumes={"cenarios": len(scenario_dirs)})
