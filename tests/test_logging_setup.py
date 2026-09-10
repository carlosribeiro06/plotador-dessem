"""Tests for dessem_dashboard.logging_setup."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from dessem_dashboard.errors import ConfigError
from dessem_dashboard.logging_setup import log_step, setup_logging


@pytest.fixture(autouse=True)
def _isolated_root_logger() -> Iterator[None]:
    """Snapshot and restore the root logger's handlers and level around each test."""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    logging.shutdown()
    root.handlers.clear()
    root.handlers.extend(original_handlers)
    root.setLevel(original_level)


def test_setup_logging_writes_accented_message_to_file(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "run.log"
    setup_logging(level="INFO", log_file=log_file, use_rich=False)

    logging.getLogger("dessem_dashboard.t").info("cenário lido")

    content = log_file.read_text(encoding="utf-8")
    assert "cenário lido" in content
    assert "INFO" in content


def test_setup_logging_called_twice_leaves_two_handlers(tmp_path: Path) -> None:
    log_file = tmp_path / "run.log"

    setup_logging(level="INFO", log_file=log_file, use_rich=False)
    setup_logging(level="INFO", log_file=log_file, use_rich=False)

    assert len(logging.getLogger().handlers) == 2


def test_setup_logging_use_rich_false_handler_types(tmp_path: Path) -> None:
    log_file = tmp_path / "run.log"
    setup_logging(level="INFO", log_file=log_file, use_rich=False)

    handlers = logging.getLogger().handlers
    rotating = [h for h in handlers if isinstance(h, RotatingFileHandler)]
    plain_stream = [
        h
        for h in handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
    ]
    assert len(rotating) == 1
    assert len(plain_stream) == 1


def test_setup_logging_use_rich_true_uses_rich_handler(tmp_path: Path) -> None:
    from rich.logging import RichHandler

    log_file = tmp_path / "run.log"
    setup_logging(level="INFO", log_file=log_file, use_rich=True)

    handlers = logging.getLogger().handlers
    assert any(isinstance(h, RichHandler) for h in handlers)


def test_setup_logging_invalid_level_raises_config_error(tmp_path: Path) -> None:
    log_file = tmp_path / "run.log"
    with pytest.raises(ConfigError, match="VERBOSO"):
        setup_logging(level="VERBOSO", log_file=log_file, use_rich=False)


def test_setup_logging_creates_missing_parent_directory(tmp_path: Path) -> None:
    log_file = tmp_path / "nested" / "deep" / "run.log"
    assert not log_file.parent.exists()

    setup_logging(level="INFO", log_file=log_file, use_rich=False)

    assert log_file.parent.is_dir()


def test_log_step_includes_message_fields_and_elapsed(tmp_path: Path) -> None:
    log_file = tmp_path / "run.log"
    logger = setup_logging(level="INFO", log_file=log_file, use_rich=False)

    log_step(logger, "processando cenário", elapsed_s=1.5, decks=3)

    content = log_file.read_text(encoding="utf-8")
    assert "processando cenário" in content
    assert "decks=3" in content
    assert "1.500 s" in content
