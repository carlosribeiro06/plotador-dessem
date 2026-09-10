"""Audit-grade logging setup: console handler plus rotating file handler."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dessem_dashboard.errors import ConfigError

_FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_VALID_LEVEL_NAMES = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def _resolve_level(level: str) -> int:
    """Return the numeric value of one of the five standard level names."""
    if level not in _VALID_LEVEL_NAMES:
        raise ConfigError(
            f"Nível de log inválido: '{level}'. Valores aceitos: {sorted(_VALID_LEVEL_NAMES)}."
        )
    return logging.getLevelNamesMapping()[level]


def _build_console_handler(*, use_rich: bool) -> logging.Handler:
    """Build the console handler: `RichHandler` when requested and importable, else plain."""
    if use_rich:
        try:
            from rich.logging import RichHandler
        except ImportError:
            pass
        else:
            rich_handler: logging.Handler = RichHandler(rich_tracebacks=True, show_path=False)
            rich_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
            return rich_handler
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FILE_FORMAT))
    return handler


def setup_logging(
    *,
    level: str = "INFO",
    log_file: Path | str = "logs/dashboard.log",
    max_bytes: int = 5_242_880,
    backups: int = 5,
    use_rich: bool = True,
) -> logging.Logger:
    """Configure the root logger once with a console handler and a rotating file handler.

    Call exactly once from the application entry point; library modules must only call
    ``logging.getLogger(__name__)`` and never configure handlers themselves.
    """
    numeric_level = _resolve_level(level)

    resolved_log_file = Path(log_file)
    resolved_log_file.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.handlers.clear()

    root.addHandler(_build_console_handler(use_rich=use_rich))

    file_handler = RotatingFileHandler(
        resolved_log_file, maxBytes=max_bytes, backupCount=backups, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))
    root.addHandler(file_handler)

    return logging.getLogger("dessem_dashboard")


def log_step(
    logger: logging.Logger,
    message: str,
    *,
    elapsed_s: float | None = None,
    **fields: object,
) -> None:
    """Log one INFO line for a pipeline step, with optional key-value fields and elapsed time."""
    fields_text = "  ".join(f"{key}={value}" for key, value in fields.items())
    elapsed_text = f"({elapsed_s:.3f} s)" if elapsed_s is not None else ""
    logger.info("  ".join(part for part in (message, fields_text, elapsed_text) if part))
