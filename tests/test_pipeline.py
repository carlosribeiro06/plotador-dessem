"""Tests for ticket-033's `dessem_dashboard.pipeline.run`, the end-to-end composition.

Follows tests/test_output_size.py's settings-copy-in-tmp_path pattern, but with its own
`_settings_dict` / `_build_settings` pair (per the ticket's own prohibition on importing a
private helper from a sibling test module) and one extra knob, `sintese_dirname`, that
`build_dashboard_data`'s and `write_dashboard`'s settings builders never needed.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dessem_dashboard import pipeline
from dessem_dashboard.cli import main
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import output_volumes
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.errors import DiscoveryError
from dessem_dashboard.models.store import DashboardData
from fixtures_sintese import make_sintese_dir

_PIPELINE_LOGGER_NAME = "dessem_dashboard.pipeline"
_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# Measured on tests.conftest.scenario_tree consolidated with settings matching the repository's
# own settings.json: matches tests/test_output_size.py's and tests/test_builder.py's own count.
_ENABLED_CHART_COUNT = 23

_FOOTER_TEXT = "Gerência de Ferramentas Energéticas - FEN"

# Chaining window shared by every deck this module builds directly through make_sintese_dir,
# matching tests.conftest.build_scenario_tree so a missing-deck tree differs from scenario_tree
# only by omitting one call.
_CHAINING_WINDOW_STAGES = 48
_CHAINED_N_STAGES = 50
_CHAINED_LONG_STAGE_HOURS = 6.0
_DECK_UM_START = datetime(2024, 3, 3, tzinfo=UTC)
_DECK_DOIS_START = datetime(2024, 3, 4, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _isolated_root_logger() -> Iterator[None]:
    """Snapshot and restore the root logger's handlers and level around each test.

    Required because test_main_writes_manifest_with_real_data_volumes_and_warnings_matching_data
    below calls cli.main, which calls setup_logging and therefore replaces the root logger's
    handlers; without this restore, that state would leak into every test running later in the
    same session. Copied from tests/test_cli.py's and tests/test_logging_setup.py's own fixture
    of the same name.
    """
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    logging.shutdown()
    root.handlers.clear()
    root.handlers.extend(original_handlers)
    root.setLevel(original_level)


# --- settings/data builders, copied from tests/test_output_size.py's pattern -------------------


def _settings_dict(*, sintese_dirname: str = "sintese") -> dict[str, Any]:
    """Build a settings.json-shaped dict matching the repository's own values.

    sintese_dirname is the one knob this module needs beyond tests/test_output_size.py's own
    pair, so acceptance criterion 4's pair can flip it without touching any other key.
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
            "use_rich": True,
        },
        "discovery": {"sintese_dirname": sintese_dirname},
        "chaining": {"stages_per_deck": 48},
        "costs": {"total_parcels": ["PRESENTE", "FUTURO"]},
        "time": {"stage_groups": {"PL": ["PL"]}, "unit_divisor": 60.0},
        "submarkets": {"include_fictitious": False, "fictitious_codes": [11, 99]},
        "dashboard": {
            "title": "Comparação de Resultados do DESSEM",
            "footer_text": _FOOTER_TEXT,
            "date_format": "%d/%m/%Y %H:%M",
        },
        "output": {
            "default_filename": "dashboard_dessem.html",
            "decimals": 2,
            "size_warning_mb": 50,
        },
        "charts": {"disabled": []},
    }


def _build_settings(tmp_path: Path, *, sintese_dirname: str = "sintese") -> Settings:
    """Write settings.json under tmp_path and load it, exercising the real config path.

    Creates tmp_path itself when it does not yet exist, since the sintese_dirname pair of
    acceptance criterion 4 writes settings.json into a subdirectory pytest never created.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(_settings_dict(sintese_dirname=sintese_dirname)), encoding="utf-8")
    return load_settings(target)


def _write_settings_file(tmp_path: Path, *, sintese_dirname: str = "sintese") -> Path:
    """Write settings.json under tmp_path and return its path, unlike _build_settings above.

    cli.main takes --settings as a path, not a loaded Settings object, so
    test_main_writes_manifest_with_real_data_volumes_and_warnings_matching_data below needs the
    path itself rather than _build_settings' already-loaded return value.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(_settings_dict(sintese_dirname=sintese_dirname)), encoding="utf-8")
    return target


def _build_data(paths: list[Path], *, settings: Settings, reference: str) -> DashboardData:
    """Discover scenarios at paths and consolidate them into one DashboardData.

    Passes settings.discovery.sintese_dirname explicitly, unlike tests/test_output_size.py's own
    helper of the same shape, so this one agrees with what pipeline.run itself discovers.
    """
    scenarios = discover_scenarios(paths, sintese_dirname=settings.discovery.sintese_dirname)
    return build_dashboard_data(scenarios, settings=settings, reference=reference)


def _build_tree_missing_caso_b_second_deck(root: Path) -> dict[str, Path]:
    """Build caso_a with two decks and caso_b with only the first, under root.

    Mirrors tests.conftest.build_scenario_tree deck by deck, skipping exactly the call that
    would create caso_b's 04/03/2024 deck, so build_dashboard_data's deck-date alignment records
    one lacuna warning naming caso_b and that date instead of raising.
    """
    make_sintese_dir(
        root / "caso_a" / "deck_um" / "sintese",
        first_stage_start=_DECK_UM_START,
        n_stages=_CHAINED_N_STAGES,
        half_hour_stages=_CHAINING_WINDOW_STAGES,
        long_stage_hours=_CHAINED_LONG_STAGE_HOURS,
        seed=101,
    )
    make_sintese_dir(
        root / "caso_a" / "deck_dois" / "sintese",
        first_stage_start=_DECK_DOIS_START,
        n_stages=_CHAINED_N_STAGES,
        half_hour_stages=_CHAINING_WINDOW_STAGES,
        long_stage_hours=_CHAINED_LONG_STAGE_HOURS,
        seed=102,
    )
    make_sintese_dir(
        root / "caso_b" / "deck_um" / "sintese",
        first_stage_start=_DECK_UM_START,
        n_stages=_CHAINED_N_STAGES,
        half_hour_stages=_CHAINING_WINDOW_STAGES,
        long_stage_hours=_CHAINED_LONG_STAGE_HOURS,
        seed=103,
    )
    return {"caso_a": root / "caso_a", "caso_b": root / "caso_b"}


# --- acceptance criterion 1: the full synthetic end-to-end round trip --------------------------


def test_pipeline_run_writes_document_and_returns_six_key_volumes(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    output_file = tmp_path / "out" / "dashboard.html"

    result = pipeline.run(
        scenario_dirs=[scenario_tree["caso_a"], scenario_tree["caso_b"]],
        output_file=output_file,
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
    assert result.data_volumes["graficos"] == _ENABLED_CHART_COUNT
    assert result.data_volumes["bytes_html"] == output_file.stat().st_size
    assert result.data_volumes["bytes_html"] > result.data_volumes["bytes_plotly"]
    assert result.output_file == output_file
    assert _FOOTER_TEXT in output_file.read_text(encoding="utf-8")


# --- acceptance criterion 2 (spec defect 22): the manifest join, not just the RunResult object -


def test_main_writes_manifest_with_real_data_volumes_and_warnings_matching_data(
    tmp_path: Path,
) -> None:
    """Regression for spec defect 22: an acceptance criterion with no assigned test.

    tests/test_cli.py pins RunResult.data_volumes on the object pipeline.run returns, and
    tests/test_manifest.py pins write_run_manifest's own round trip given whatever mapping it is
    handed. Neither proves that cli.main actually threads pipeline.run's real data_volumes and,
    critically, its warnings into the written run_manifest.json file: that join is exactly the
    shape of the three defects this ticket closes (--modo-inicial declared and never applied,
    sintese_dirname validated and never passed, add_warning appended and never logged) — two
    correct halves with nothing asserting the correspondence between them. Compares against an
    independently rebuilt DashboardData.warnings() rather than a hard-coded string, so a future
    change to the warning wording does not make this test lie about what it proves.
    """
    tree = _build_tree_missing_caso_b_second_deck(tmp_path / "tree")
    settings_path = _write_settings_file(tmp_path)

    exit_code = main(
        ["--casos", str(tree["caso_a"]), str(tree["caso_b"]), "--settings", str(settings_path)]
    )

    assert exit_code == 0

    manifest_path = tmp_path / "output" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    settings = load_settings(settings_path)
    expected_data = _build_data(
        [tree["caso_a"], tree["caso_b"]], settings=settings, reference="caso_a"
    )
    output_file = tmp_path / "output" / "dashboard_dessem.html"
    expected_volumes = output_volumes(expected_data, settings=settings, output_file=output_file)

    assert manifest["data_volumes"] == expected_volumes
    assert manifest["warnings"] == list(expected_data.warnings())
    # Non-vacuity: caso_b's missing second deck must actually produce a warning, or this test
    # would pass just as well comparing two empty lists.
    assert manifest["warnings"] != []


# --- Testing Requirements: RunResult.warnings equals list(data.warnings()) ---------------------


def test_pipeline_run_warnings_equal_data_warnings_for_missing_deck(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    tree = _build_tree_missing_caso_b_second_deck(tmp_path / "tree")
    output_file = tmp_path / "out" / "dashboard.html"

    result = pipeline.run(
        scenario_dirs=[tree["caso_a"], tree["caso_b"]],
        output_file=output_file,
        reference="caso_a",
        settings=settings,
    )

    expected_data = _build_data(
        [tree["caso_a"], tree["caso_b"]], settings=settings, reference="caso_a"
    )
    assert result.warnings == list(expected_data.warnings())
    assert any("caso_b" in message and "04/03/2024" in message for message in result.warnings)


# --- Testing Requirements: a zero-deck scenario raises DiscoveryError unchanged ----------------


def test_pipeline_run_scenario_with_no_decks_raises_discovery_error(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    caso_a = tmp_path / "caso_a"
    caso_a.mkdir()

    with pytest.raises(DiscoveryError, match=re.escape("caso_a")) as exc_info:
        pipeline.run(
            scenario_dirs=[caso_a],
            output_file=tmp_path / "out" / "dashboard.html",
            reference="caso_a",
            settings=settings,
        )

    assert "sintese" in str(exc_info.value)


# --- Testing Requirements: pipeline.run creates output_file's parent directory ------------------


def test_pipeline_run_creates_output_parent_directory(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    output_file = tmp_path / "nested" / "deep" / "dashboard.html"
    assert not output_file.parent.exists()

    pipeline.run(
        scenario_dirs=[scenario_tree["caso_a"], scenario_tree["caso_b"]],
        output_file=output_file,
        reference="caso_a",
        settings=settings,
    )

    assert output_file.is_file()


# --- Testing Requirements: exactly one completion log_step line, with all six volume fields ----


def test_pipeline_run_logs_exactly_one_completion_line_with_volume_fields(
    scenario_tree: dict[str, Path], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = _build_settings(tmp_path)
    output_file = tmp_path / "out" / "dashboard.html"

    caplog.set_level(logging.INFO, logger=_PIPELINE_LOGGER_NAME)
    result = pipeline.run(
        scenario_dirs=[scenario_tree["caso_a"], scenario_tree["caso_b"]],
        output_file=output_file,
        reference="caso_a",
        settings=settings,
    )

    pipeline_records = [record for record in caplog.records if record.name == _PIPELINE_LOGGER_NAME]
    assert len(pipeline_records) == 1

    expected_data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    expected_volumes = output_volumes(expected_data, settings=settings, output_file=output_file)
    assert expected_volumes == result.data_volumes

    message = pipeline_records[0].getMessage()
    for key, value in expected_volumes.items():
        assert f"{key}={value}" in message
    assert f"avisos={len(expected_data.warnings())}" in message


# --- acceptance criterion 3: --modo-inicial reaches the written document -----------------------


def test_pipeline_run_initial_mode_reaches_written_document(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    deck_file = tmp_path / "deck" / "dashboard.html"
    chained_file = tmp_path / "encadeado" / "dashboard.html"

    pipeline.run(
        scenario_dirs=[scenario_tree["caso_a"], scenario_tree["caso_b"]],
        output_file=deck_file,
        reference="caso_a",
        settings=settings,
        initial_mode="deck",
    )
    pipeline.run(
        scenario_dirs=[scenario_tree["caso_a"], scenario_tree["caso_b"]],
        output_file=chained_file,
        reference="caso_a",
        settings=settings,
        initial_mode="encadeado",
    )

    deck_document = deck_file.read_text(encoding="utf-8")
    chained_document = chained_file.read_text(encoding="utf-8")

    assert 'data-initial-mode="deck"' in deck_document
    assert '<select id="deck-selector">' in deck_document
    assert 'data-initial-mode="encadeado"' in chained_document
    assert '<select id="deck-selector" disabled>' in chained_document
    assert deck_document != chained_document


# --- acceptance criterion 4: settings.discovery.sintese_dirname is consumed, non-vacuously ------


def test_pipeline_run_honours_custom_sintese_dirname(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "tree" / "caso_a"
    make_sintese_dir(
        scenario_dir / "deck_um" / "resultados",
        first_stage_start=_DECK_UM_START,
        n_stages=_CHAINED_N_STAGES,
        half_hour_stages=_CHAINING_WINDOW_STAGES,
        long_stage_hours=_CHAINED_LONG_STAGE_HOURS,
    )

    settings_custom = _build_settings(tmp_path / "custom", sintese_dirname="resultados")
    output_file = tmp_path / "custom_out" / "dashboard.html"

    result = pipeline.run(
        scenario_dirs=[scenario_dir],
        output_file=output_file,
        reference="caso_a",
        settings=settings_custom,
    )

    assert output_file.is_file()
    assert result.data_volumes["cenarios"] == 1


def test_pipeline_run_default_sintese_dirname_does_not_find_custom_named_folder(
    tmp_path: Path,
) -> None:
    scenario_dir = tmp_path / "tree" / "caso_a"
    make_sintese_dir(
        scenario_dir / "deck_um" / "resultados",
        first_stage_start=_DECK_UM_START,
        n_stages=_CHAINED_N_STAGES,
        half_hour_stages=_CHAINING_WINDOW_STAGES,
        long_stage_hours=_CHAINED_LONG_STAGE_HOURS,
    )

    settings_default = _build_settings(tmp_path / "default")

    with pytest.raises(DiscoveryError, match=re.escape("caso_a")) as exc_info:
        pipeline.run(
            scenario_dirs=[scenario_dir],
            output_file=tmp_path / "default_out" / "dashboard.html",
            reference="caso_a",
            settings=settings_default,
        )

    assert "sintese" in str(exc_info.value)
