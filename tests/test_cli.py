"""Tests for dessem_dashboard.cli (and its pipeline.run collaborator)."""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dessem_dashboard import pipeline
from dessem_dashboard.cli import _MAX_LOGGED_WARNINGS, build_parser, main
from dessem_dashboard.config import load_settings
from dessem_dashboard.errors import DashboardError
from fixtures_sintese import make_sintese_dir

_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# Chaining window shared by every deck this module builds directly through make_sintese_dir,
# matching tests.conftest.build_scenario_tree so a missing-deck tree differs from scenario_tree
# only by omitting one call. Kept local rather than imported from tests/test_pipeline.py's own
# copy of the same shape, per this suite's convention against importing a private helper from a
# sibling test module (see test_pipeline.py's own module docstring).
_CHAINING_WINDOW_STAGES = 48
_CHAINED_N_STAGES = 50
_CHAINED_LONG_STAGE_HOURS = 6.0
_DECK_UM_START = datetime(2024, 3, 3, tzinfo=UTC)
_DECK_DOIS_START = datetime(2024, 3, 4, tzinfo=UTC)


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

    `output_dir` and `log_dir` are relative, so writing this next to a temporary directory
    resolves them inside that same temporary directory. `paths.logo_file` points at the
    repository's own logo instead of a relative path, because `pipeline.run` now reads it while
    rendering the document and no temporary directory ships a logo file of its own.

    A second divergence, in `logging.use_rich`: it is set to `False`, the only one of this
    plan's eighteen `_settings_dict`-shaped modules that detunes it -- the silence that let the
    stdout defect survive eight guardians undetected. Ticket-037 requirement 11 item 4 keeps
    this module's value; the separate
    test_main_success_under_shipped_use_rich_still_prints_only_the_path_to_stdout covers the
    shipped `True`.
    """
    return {
        "project": "dessem-dashboard",
        "paths": {
            "output_dir": "output",
            "log_dir": "logs",
            "logo_file": str(_REPO_LOGO),
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


def _settings_and_two_casos(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Write the temporary settings.json and create two scenario directories beside it."""
    settings_path = _write_settings(tmp_path)
    caso_a = tmp_path / "caso_a"
    caso_b = tmp_path / "caso_b"
    caso_a.mkdir()
    caso_b.mkdir()
    return settings_path, caso_a, caso_b


def _build_tree_missing_caso_b_second_deck(root: Path) -> dict[str, Path]:
    """Build caso_a with two decks and caso_b with only the first, under root.

    Mirrors tests.conftest.build_scenario_tree deck by deck, skipping exactly the call that
    would create caso_b's 04/03/2024 deck, so build_dashboard_data's deck-date alignment
    records one degradation warning naming caso_b and that date instead of raising.
    """
    make_sintese_dir(
        root / "caso_a" / "deck_um" / "sintese",
        first_stage_start=_DECK_UM_START,
        n_stages=_CHAINED_N_STAGES,
        half_hour_stages=_CHAINING_WINDOW_STAGES,
        long_stage_hours=_CHAINED_LONG_STAGE_HOURS,
        seed=301,
    )
    make_sintese_dir(
        root / "caso_a" / "deck_dois" / "sintese",
        first_stage_start=_DECK_DOIS_START,
        n_stages=_CHAINED_N_STAGES,
        half_hour_stages=_CHAINING_WINDOW_STAGES,
        long_stage_hours=_CHAINED_LONG_STAGE_HOURS,
        seed=302,
    )
    make_sintese_dir(
        root / "caso_b" / "deck_um" / "sintese",
        first_stage_start=_DECK_UM_START,
        n_stages=_CHAINED_N_STAGES,
        half_hour_stages=_CHAINING_WINDOW_STAGES,
        long_stage_hours=_CHAINED_LONG_STAGE_HOURS,
        seed=303,
    )
    return {"caso_a": root / "caso_a", "caso_b": root / "caso_b"}


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
    tmp_path: Path, scenario_tree: dict[str, Path]
) -> None:
    settings_path = _write_settings(tmp_path)
    caso_a, caso_b = scenario_tree["caso_a"], scenario_tree["caso_b"]

    exit_code = main(["--casos", str(caso_a), str(caso_b), "--settings", str(settings_path)])

    assert exit_code == 0
    log_content = (tmp_path / "logs" / "dashboard.log").read_text(encoding="utf-8")
    assert "caso_a" in log_content
    assert "caso_b" in log_content
    manifest_path = tmp_path / "output" / "run_manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["params"]["referencia"] == "caso_a"


def test_main_explicit_referencia_is_honoured_in_manifest_params(
    tmp_path: Path, scenario_tree: dict[str, Path]
) -> None:
    settings_path = _write_settings(tmp_path)
    caso_a, caso_b = scenario_tree["caso_a"], scenario_tree["caso_b"]

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


def test_main_modo_inicial_reaches_the_document_and_the_manifest(
    tmp_path: Path, scenario_tree: dict[str, Path]
) -> None:
    """Pins --modo-inicial's full correspondence: cli.main forwards it to pipeline.run, which
    renders it into the document's data-initial-mode attribute, while the same value
    independently reaches run_manifest.json through cli.main's own params dict -- an audited
    artefact that must agree with what the document actually shows (ticket-033's "declared and
    never applied" defect shape).
    """
    settings_path = _write_settings(tmp_path)
    caso_a, caso_b = scenario_tree["caso_a"], scenario_tree["caso_b"]

    exit_code = main(
        [
            "--casos",
            str(caso_a),
            str(caso_b),
            "--settings",
            str(settings_path),
            "--modo-inicial",
            "deck",
        ]
    )

    assert exit_code == 0
    document = (tmp_path / "output" / "dashboard_dessem.html").read_text(encoding="utf-8")
    assert 'data-initial-mode="deck"' in document

    manifest_path = tmp_path / "output" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["params"]["modo_inicial"] == "deck"


def test_main_unknown_referencia_exits_2_naming_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings_path, caso_a, caso_b = _settings_and_two_casos(tmp_path)

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


def test_main_nivel_log_debug_sets_root_logger_level(
    tmp_path: Path, scenario_tree: dict[str, Path]
) -> None:
    settings_path = _write_settings(tmp_path)
    caso_a, caso_b = scenario_tree["caso_a"], scenario_tree["caso_b"]

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
    tmp_path: Path, scenario_tree: dict[str, Path]
) -> None:
    settings_path = _write_settings(tmp_path)
    caso_a, caso_b = scenario_tree["caso_a"], scenario_tree["caso_b"]

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


def test_main_dashboard_error_from_pipeline_is_logged_and_returns_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_path, caso_a, caso_b = _settings_and_two_casos(tmp_path)

    def _raise(**_: object) -> pipeline.RunResult:
        raise DashboardError("falha simulada no pipeline")

    monkeypatch.setattr(pipeline, "run", _raise)

    exit_code = main(["--casos", str(caso_a), str(caso_b), "--settings", str(settings_path)])

    assert exit_code == 1
    log_text = (tmp_path / "logs" / "dashboard.log").read_text(encoding="utf-8")
    assert "falha simulada no pipeline" in log_text
    assert "Traceback" in log_text


def test_main_success_prints_only_the_output_path_to_stdout(
    tmp_path: Path,
    scenario_tree: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Acceptance criterion 1: the success path prints exactly the output path to stdout, and
    every failure path -- a malformed settings.json, a duplicate --casos basename, an unknown
    --referencia, and (per the Outputs and Behavior section) a DashboardError from the pipeline
    -- leaves stdout empty.
    """
    settings_path = _write_settings(tmp_path)
    caso_a, caso_b = scenario_tree["caso_a"], scenario_tree["caso_b"]

    exit_code = main(["--casos", str(caso_a), str(caso_b), "--settings", str(settings_path)])

    assert exit_code == 0
    expected_output_file = tmp_path / "output" / "dashboard_dessem.html"
    assert capsys.readouterr().out.strip() == str(expected_output_file)

    malformed_settings = tmp_path / "malformed_settings.json"
    malformed_settings.write_text("{ isto não é json válido", encoding="utf-8")
    with pytest.raises(SystemExit) as malformed_exit:
        main(["--casos", str(caso_a), "--settings", str(malformed_settings)])
    assert malformed_exit.value.code == 2
    assert capsys.readouterr().out == ""

    outro_caso_a = tmp_path / "outro" / "caso_a"
    with pytest.raises(SystemExit) as duplicate_exit:
        main(["--casos", str(caso_a), str(outro_caso_a), "--settings", str(settings_path)])
    assert duplicate_exit.value.code == 2
    assert capsys.readouterr().out == ""

    with pytest.raises(SystemExit) as unknown_reference_exit:
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
    assert unknown_reference_exit.value.code == 2
    assert capsys.readouterr().out == ""

    def _raise(**_: object) -> pipeline.RunResult:
        raise DashboardError("falha simulada para a verificação de stdout vazio")

    monkeypatch.setattr(pipeline, "run", _raise)
    dashboard_error_exit_code = main(
        ["--casos", str(caso_a), str(caso_b), "--settings", str(settings_path)]
    )
    assert dashboard_error_exit_code == 1
    assert capsys.readouterr().out == ""


def test_main_success_under_shipped_use_rich_still_prints_only_the_path_to_stdout(
    tmp_path: Path, scenario_tree: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression for requirement 11 (guardian rejection): acceptance criterion 1 must hold
    under the **shipped** `logging.use_rich: true` default, not only under this module's own
    `_settings_dict`, which hardcodes `use_rich: False` for every other test here.

    That hardcoding is exactly why the original defect went uncaught: the one module driving
    `cli.main` end to end detuned the one setting that exercises `_build_console_handler`'s
    `RichHandler` path, so `Console()`'s stdout default silently mixed the whole log into the
    operator's one pipeable stdout line. This test flips only its own local copy of the
    settings payload -- per requirement 11 item 4, every other test's `use_rich: False` stays
    untouched.
    """
    settings_payload = _settings_dict()
    settings_payload["logging"]["use_rich"] = True
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings_payload, ensure_ascii=False), encoding="utf-8")
    caso_a, caso_b = scenario_tree["caso_a"], scenario_tree["caso_b"]

    exit_code = main(["--casos", str(caso_a), str(caso_b), "--settings", str(settings_path)])

    assert exit_code == 0
    expected_output_file = tmp_path / "output" / "dashboard_dessem.html"
    assert capsys.readouterr().out.strip() == str(expected_output_file)


def test_main_degraded_run_exits_zero_and_logs_the_missing_deck_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Acceptance criterion 2: one scenario missing a deck degrades instead of failing, and the
    resulting warning reaches both the dessem_dashboard.cli logger and the rotating log file.

    caplog's own handler is attached directly to logging.getLogger("dessem_dashboard.cli")
    instead of relying on pytest's default root-logger attachment, because cli.main calls
    setup_logging, which clears the root logger's handlers -- including pytest's own capturing
    handler -- before any warning this test cares about is emitted. Attaching to the named
    child logger survives that clear, since setup_logging never touches it.
    """
    settings_path = _write_settings(tmp_path)
    tree = _build_tree_missing_caso_b_second_deck(tmp_path / "tree")

    cli_logger = logging.getLogger("dessem_dashboard.cli")
    with caplog.at_level(logging.WARNING, logger="dessem_dashboard.cli"):
        cli_logger.addHandler(caplog.handler)
        try:
            exit_code = main(
                [
                    "--casos",
                    str(tree["caso_a"]),
                    str(tree["caso_b"]),
                    "--settings",
                    str(settings_path),
                ]
            )
        finally:
            cli_logger.removeHandler(caplog.handler)

    assert exit_code == 0

    manifest_path = tmp_path / "output" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["warnings"] != []

    cli_warnings = [
        record
        for record in caplog.records
        if record.name == "dessem_dashboard.cli" and record.levelno == logging.WARNING
    ]
    assert any(
        "caso_b" in record.getMessage() and "04/03/2024" in record.getMessage()
        for record in cli_warnings
    )

    log_text = (tmp_path / "logs" / "dashboard.log").read_text(encoding="utf-8")
    assert "caso_b" in log_text
    assert "04/03/2024" in log_text


def test_main_truncates_logged_warnings_at_the_cap_and_names_the_remainder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Acceptance criterion 3: 25 synthetic warnings log 20 individually plus exactly one
    truncation line naming the 5 omitted, while the manifest keeps all 25 uncapped.

    Checks the same correspondence directly against the rotating log FILE, not only against
    caplog's records: dessem_dashboard.cli's logger feeds both the console handler and the
    RotatingFileHandler, so a regression capping one while leaving the other complete would
    otherwise go unnoticed.
    """
    settings_path, caso_a, caso_b = _settings_and_two_casos(tmp_path)
    synthetic_warnings = [f"Aviso sintético número {index}" for index in range(25)]
    output_file = tmp_path / "output" / "dashboard_dessem.html"
    expected_omitted = len(synthetic_warnings) - _MAX_LOGGED_WARNINGS

    def _fake_run(**_: object) -> pipeline.RunResult:
        return pipeline.RunResult(
            output_file=output_file, data_volumes={}, warnings=list(synthetic_warnings)
        )

    monkeypatch.setattr(pipeline, "run", _fake_run)

    cli_logger = logging.getLogger("dessem_dashboard.cli")
    with caplog.at_level(logging.WARNING, logger="dessem_dashboard.cli"):
        cli_logger.addHandler(caplog.handler)
        try:
            exit_code = main(
                ["--casos", str(caso_a), str(caso_b), "--settings", str(settings_path)]
            )
        finally:
            cli_logger.removeHandler(caplog.handler)

    assert exit_code == 0

    warning_records = [record for record in caplog.records if record.levelno == logging.WARNING]
    individual = [record for record in warning_records if record.getMessage() in synthetic_warnings]
    assert len(individual) == 20
    assert {record.getMessage() for record in individual} == set(synthetic_warnings[:20])

    truncation_records = [
        record for record in warning_records if record.getMessage() not in synthetic_warnings
    ]
    assert len(truncation_records) == 1
    truncation_message = truncation_records[0].getMessage()
    # A delimited token, not a bare substring: the omitted count is the message's leading
    # token ("%d aviso(s) ..." % omitted), so a mutation computing the wrong count (e.g.
    # len(messages) instead of len(messages) - _MAX_LOGGED_WARNINGS) changes this leading token
    # even though "5" would still be a substring of the mutated "25 aviso(s) ...".
    assert truncation_message.startswith(str(expected_omitted))
    assert "run_manifest.json" in truncation_message
    assert "Avisos" in truncation_message

    log_lines = (tmp_path / "logs" / "dashboard.log").read_text(encoding="utf-8").splitlines()
    file_messages = [parts[-1] for line in log_lines if len(parts := line.split(" | ", 3)) == 4]
    individual_in_file = [message for message in file_messages if message in synthetic_warnings]
    assert len(individual_in_file) == 20
    assert set(individual_in_file) == set(synthetic_warnings[:20])
    truncation_lines_in_file = [
        message for message in file_messages if message == truncation_message
    ]
    assert len(truncation_lines_in_file) == 1

    manifest = json.loads((tmp_path / "output" / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["warnings"] == synthetic_warnings


def test_build_parser_epilog_carries_the_worked_example_and_the_reference_rule() -> None:
    """Acceptance criterion 4's help half: --help ends with a worked example naming the
    reference-scenario rule.

    Asserts on parser.epilog directly, not only on the full format_help() text, because
    "referência" already appears in --referencia's own help string: a substring check against
    the whole help text alone would pass even if the epilog never mentioned the rule at all.
    """
    parser = build_parser()
    help_text = parser.format_help()

    assert "--casos exemplo/caso_oficial exemplo/caso_gurobi" in help_text
    assert parser.epilog is not None
    assert "cenário de referência" in parser.epilog
    assert parser.epilog in help_text


def test_pipeline_run_returns_data_volumes_matching_number_of_casos(
    tmp_path: Path, scenario_tree: dict[str, Path]
) -> None:
    settings = load_settings(_write_settings(tmp_path))
    scenario_dirs = [scenario_tree["caso_a"], scenario_tree["caso_b"]]

    result = pipeline.run(
        scenario_dirs=scenario_dirs,
        output_file=tmp_path / "saida.html",
        reference="caso_a",
        settings=settings,
    )

    assert list(result.data_volumes.keys()) == [
        "cenarios",
        "decks",
        "graficos",
        "valores",
        "bytes_html",
        "bytes_plotly",
    ]
    assert result.data_volumes["cenarios"] == 2
    assert result.data_volumes["decks"] == 2
    assert result.data_volumes["bytes_html"] == (tmp_path / "saida.html").stat().st_size
    assert result.warnings == []


def test_console_script_help_exits_0_and_lists_casos() -> None:
    script = Path(".venv/bin/dessem-dashboard")
    if not script.is_file():
        pytest.skip("dessem-dashboard console script não está instalado neste ambiente")

    result = subprocess.run([str(script), "--help"], capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert "--casos" in result.stdout
