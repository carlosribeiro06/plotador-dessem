"""Tests for dessem_dashboard.cli (and its pipeline.run collaborator)."""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from dessem_dashboard import pipeline
from dessem_dashboard.cli import build_parser, main
from dessem_dashboard.config import load_settings


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


def _settings_dict() -> dict[str, Any]:
    """Return a settings.json payload identical in shape to the repository's own file.

    All paths are relative, so writing this next to a temporary directory resolves
    `output_dir`, `log_dir` and `logo_file` inside that same temporary directory.
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
            "use_rich": False,
        },
        "discovery": {"sintese_dirname": "sintese"},
        "chaining": {"stages_per_deck": 48},
        "costs": {"total_parcels": ["PRESENTE", "FUTURO"]},
        "time": {
            "stage_groups": {
                "MILP": ["MILP"],
                "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"],
                "Leitura": ["Leitura de Dados e Impressão"],
            },
            "unit_divisor": 60.0,
        },
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


def _write_settings(tmp_path: Path) -> Path:
    """Write a temporary settings.json inside tmp_path so no test touches repository artifacts."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(_settings_dict(), ensure_ascii=False), encoding="utf-8")
    return settings_path


def test_main_missing_casos_exits_2_with_casos_in_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])

    assert exc_info.value.code == 2
    assert "--casos" in capsys.readouterr().err


def test_build_parser_help_contains_all_flags_and_cenario_word() -> None:
    help_text = build_parser().format_help()

    for flag in (
        "--casos",
        "--saida",
        "--referencia",
        "--settings",
        "--modo-inicial",
        "--nivel-log",
    ):
        assert flag in help_text
    assert "cenário" in help_text


def test_main_successful_run_writes_manifest_and_log_with_first_basename_as_reference(
    tmp_path: Path,
) -> None:
    settings_path = _write_settings(tmp_path)
    caso_a = tmp_path / "caso_a"
    caso_b = tmp_path / "caso_b"
    caso_a.mkdir()
    caso_b.mkdir()

    exit_code = main(["--casos", str(caso_a), str(caso_b), "--settings", str(settings_path)])

    assert exit_code == 0
    log_content = (tmp_path / "logs" / "dashboard.log").read_text(encoding="utf-8")
    assert "caso_a" in log_content
    assert "caso_b" in log_content
    manifest_path = tmp_path / "output" / "run_manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["params"]["referencia"] == "caso_a"


def test_main_explicit_referencia_is_honoured_in_manifest_params(tmp_path: Path) -> None:
    settings_path = _write_settings(tmp_path)
    caso_a = tmp_path / "caso_a"
    caso_b = tmp_path / "caso_b"
    caso_a.mkdir()
    caso_b.mkdir()

    exit_code = main(
        [
            "--casos",
            str(caso_a),
            str(caso_b),
            "--settings",
            str(settings_path),
            "--referencia",
            "caso_b",
        ]
    )

    assert exit_code == 0
    manifest_path = tmp_path / "output" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["params"]["referencia"] == "caso_b"


def test_main_unknown_referencia_exits_2_naming_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings_path = _write_settings(tmp_path)
    caso_a = tmp_path / "caso_a"
    caso_b = tmp_path / "caso_b"
    caso_a.mkdir()
    caso_b.mkdir()

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--casos",
                str(caso_a),
                str(caso_b),
                "--settings",
                str(settings_path),
                "--referencia",
                "caso_z",
            ]
        )

    assert exc_info.value.code == 2
    assert "caso_z" in capsys.readouterr().err


def test_main_duplicate_casos_basenames_exits_2_naming_duplicate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings_path = _write_settings(tmp_path)
    caso_a = tmp_path / "caso_a"
    outro_caso_a = tmp_path / "outro" / "caso_a"

    with pytest.raises(SystemExit) as exc_info:
        main(["--casos", str(caso_a), str(outro_caso_a), "--settings", str(settings_path)])

    assert exc_info.value.code == 2
    assert "caso_a" in capsys.readouterr().err


def test_main_nivel_log_debug_sets_root_logger_level(tmp_path: Path) -> None:
    settings_path = _write_settings(tmp_path)
    caso_a = tmp_path / "caso_a"
    caso_b = tmp_path / "caso_b"
    caso_a.mkdir()
    caso_b.mkdir()

    exit_code = main(
        [
            "--casos",
            str(caso_a),
            str(caso_b),
            "--settings",
            str(settings_path),
            "--nivel-log",
            "DEBUG",
        ]
    )

    assert exit_code == 0
    assert logging.getLogger().level == logging.DEBUG


def test_main_default_saida_equals_settings_output_dir_and_default_filename(
    tmp_path: Path,
) -> None:
    settings_path = _write_settings(tmp_path)
    caso_a = tmp_path / "caso_a"
    caso_b = tmp_path / "caso_b"
    caso_a.mkdir()
    caso_b.mkdir()

    exit_code = main(["--casos", str(caso_a), str(caso_b), "--settings", str(settings_path)])

    assert exit_code == 0
    manifest_path = tmp_path / "output" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_saida = (tmp_path / "output" / "dashboard_dessem.html").as_posix()
    assert manifest["params"]["saida"] == expected_saida


def test_main_malformed_settings_exits_2_with_config_error_message_and_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    malformed_settings = tmp_path / "settings.json"
    malformed_settings.write_text("{ isto não é json válido", encoding="utf-8")
    caso_a = tmp_path / "caso_a"
    caso_a.mkdir()

    with pytest.raises(SystemExit) as exc_info:
        main(["--casos", str(caso_a), "--settings", str(malformed_settings)])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "settings.json inválido" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_pipeline_run_returns_data_volumes_matching_number_of_casos(tmp_path: Path) -> None:
    settings = load_settings(_write_settings(tmp_path))
    scenario_dirs = [tmp_path / "caso_a", tmp_path / "caso_b", tmp_path / "caso_c"]

    result = pipeline.run(
        scenario_dirs=scenario_dirs,
        output_file=tmp_path / "saida.html",
        reference="caso_a",
        settings=settings,
    )

    assert result.data_volumes == {"cenarios": 3}
    assert result.warnings == []


def test_console_script_help_exits_0_and_lists_casos() -> None:
    script = Path(".venv/bin/dessem-dashboard")
    if not script.is_file():
        pytest.skip("dessem-dashboard console script não está instalado neste ambiente")

    result = subprocess.run([str(script), "--help"], capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert "--casos" in result.stdout
