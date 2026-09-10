"""Command-line entry point for dessem-dashboard.

Parses arguments (Portuguese flags and help text, per binding decision), loads and
validates settings, configures logging, then delegates to `pipeline.run`.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from dessem_dashboard import pipeline
from dessem_dashboard.config import load_settings
from dessem_dashboard.errors import ConfigError, DashboardError
from dessem_dashboard.logging_setup import setup_logging
from dessem_dashboard.manifest import write_run_manifest

_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_VIEW_MODES = ("deck", "encadeado")

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the dessem-dashboard argument parser with Portuguese help text."""
    parser = argparse.ArgumentParser(
        prog="dessem-dashboard",
        description=(
            "Gera um dashboard HTML comparando resultados de simulações do DESSEM entre cenários."
        ),
    )
    parser.add_argument(
        "--casos",
        nargs="+",
        type=Path,
        required=True,
        metavar="DIRETORIO",
        help=(
            "Diretórios de cenário a comparar; o rótulo de cada cenário na legenda é o nome "
            "do diretório."
        ),
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        metavar="ARQUIVO",
        help=(
            "Arquivo HTML de saída. Padrão: paths.output_dir/output.default_filename "
            "definidos em settings.json."
        ),
    )
    parser.add_argument(
        "--referencia",
        type=str,
        default=None,
        metavar="NOME",
        help=(
            "Nome do cenário de referência usado na visão de diferença. Padrão: nome do "
            "primeiro diretório informado em --casos."
        ),
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=Path("settings.json"),
        metavar="ARQUIVO",
        help="Arquivo de configuração do projeto. Padrão: settings.json.",
    )
    parser.add_argument(
        "--modo-inicial",
        choices=_VIEW_MODES,
        default="encadeado",
        help="Modo de visão pré-selecionado no dashboard ('deck' ou 'encadeado'). Padrão: encadeado.",
    )
    parser.add_argument(
        "--nivel-log",
        choices=_LOG_LEVELS,
        default=None,
        help="Nível de log, sobrepondo logging.level definido em settings.json.",
    )
    return parser


def _resolve_labels(
    parser: argparse.ArgumentParser, scenario_dirs: Sequence[Path]
) -> dict[str, Path]:
    """Map each `--casos` directory to its legend label (its basename).

    Exits with code 2 through `parser.error` when two directories share a basename.
    """
    labels: dict[str, Path] = {}
    for scenario_dir in scenario_dirs:
        label = scenario_dir.name
        if label in labels:
            parser.error(
                f"Nome de cenário duplicado: '{label}'. Cada diretório em --casos precisa de "
                "um nome de diretório (rótulo da legenda) único."
            )
        labels[label] = scenario_dir
    return labels


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, run the comparison pipeline and write the run manifest."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = load_settings(args.settings)
    except ConfigError as err:
        print(str(err), file=sys.stderr)
        raise SystemExit(2) from err

    setup_logging(
        level=args.nivel_log or settings.logging.level,
        log_file=settings.logging.file,
        max_bytes=settings.logging.rotate_max_bytes,
        backups=settings.logging.rotate_backups,
        use_rich=settings.logging.use_rich,
    )

    labels = _resolve_labels(parser, args.casos)
    reference = args.referencia if args.referencia is not None else args.casos[0].name
    if reference not in labels:
        parser.error(
            f"Cenário de referência desconhecido: '{reference}'. Nomes válidos: {sorted(labels)}."
        )

    output_file = args.saida
    if output_file is None:
        output_file = settings.paths.output_dir / settings.output.default_filename
    output_file.parent.mkdir(parents=True, exist_ok=True)

    params: dict[str, object] = {
        "casos": list(args.casos),
        "saida": output_file,
        "referencia": reference,
        "settings": args.settings,
        "modo_inicial": args.modo_inicial,
        "nivel_log": args.nivel_log,
    }

    start = time.perf_counter()
    try:
        result = pipeline.run(
            scenario_dirs=args.casos,
            output_file=output_file,
            reference=reference,
            settings=settings,
        )
    except DashboardError:
        logger.exception("Falha ao executar o pipeline do dashboard")
        return 1
    elapsed_s = time.perf_counter() - start

    manifest_path = write_run_manifest(
        settings.paths.output_dir,
        params=params,
        elapsed_s=elapsed_s,
        data_volumes=result.data_volumes,
        warnings=result.warnings,
    )
    logger.info("Manifesto de execução escrito em %s", manifest_path)
    return 0
