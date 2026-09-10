"""Tests for dessem_dashboard.config."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from dessem_dashboard.config import load_settings
from dessem_dashboard.errors import ConfigError


def _valid() -> dict[str, Any]:
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
            "use_rich": True,
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


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return target


def test_load_settings_valid_settings_spot_checks_all_groups(tmp_path: Path) -> None:
    settings = load_settings(_write(tmp_path, _valid()))
    assert settings.paths.output_dir == tmp_path / "output"
    assert settings.logging.level == "INFO"
    assert settings.discovery.sintese_dirname == "sintese"
    assert settings.chaining.stages_per_deck == 48
    assert settings.costs.total_parcels == ["PRESENTE", "FUTURO"]
    assert settings.time.unit_divisor == 60.0
    assert settings.submarkets.include_fictitious is False
    assert settings.dashboard.footer_text == "Gerência de Ferramentas Energéticas - FEN"
    assert settings.output.default_filename == "dashboard_dessem.html"
    assert settings.charts.disabled == []


def test_load_settings_relative_paths_resolve_against_settings_file_directory(
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = _write(tmp_path, _valid())
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    monkeypatch.chdir(elsewhere)
    settings = load_settings(settings_path)
    assert settings.paths.output_dir == tmp_path / "output"


def test_load_settings_missing_group_raises_config_error(tmp_path: Path) -> None:
    data = _valid()
    del data["chaining"]
    with pytest.raises(ConfigError, match="chaining"):
        load_settings(_write(tmp_path, data))


def test_load_settings_missing_leaf_key_raises_config_error_naming_dotted_key(
    tmp_path: Path,
) -> None:
    data = _valid()
    del data["chaining"]["stages_per_deck"]
    with pytest.raises(ConfigError, match="chaining.stages_per_deck"):
        load_settings(_write(tmp_path, data))


def test_load_settings_wrong_type_output_decimals_raises_config_error(tmp_path: Path) -> None:
    data = _valid()
    data["output"]["decimals"] = "2"
    with pytest.raises(ConfigError, match="decimals"):
        load_settings(_write(tmp_path, data))


def test_load_settings_wrong_type_chaining_stages_per_deck_raises_config_error(
    tmp_path: Path,
) -> None:
    data = _valid()
    data["chaining"]["stages_per_deck"] = "48"
    with pytest.raises(ConfigError, match="stages_per_deck"):
        load_settings(_write(tmp_path, data))


def test_load_settings_wrong_type_charts_disabled_raises_config_error(tmp_path: Path) -> None:
    data = _valid()
    data["charts"]["disabled"] = "none"
    with pytest.raises(ConfigError, match="disabled"):
        load_settings(_write(tmp_path, data))


def test_load_settings_invalid_logging_level_raises_config_error(tmp_path: Path) -> None:
    data = _valid()
    data["logging"]["level"] = "VERBOSO"
    with pytest.raises(ConfigError, match="VERBOSO"):
        load_settings(_write(tmp_path, data))


def test_load_settings_unit_divisor_int_loads_as_float(tmp_path: Path) -> None:
    data = _valid()
    data["time"]["unit_divisor"] = 60
    settings = load_settings(_write(tmp_path, data))
    assert settings.time.unit_divisor == 60.0


def test_load_settings_unit_divisor_zero_raises_config_error(tmp_path: Path) -> None:
    data = _valid()
    data["time"]["unit_divisor"] = 0
    with pytest.raises(ConfigError, match="unit_divisor"):
        load_settings(_write(tmp_path, data))


def test_load_settings_unit_divisor_negative_raises_config_error(tmp_path: Path) -> None:
    data = _valid()
    data["time"]["unit_divisor"] = -60
    with pytest.raises(ConfigError, match="unit_divisor"):
        load_settings(_write(tmp_path, data))


def test_load_settings_stages_per_deck_zero_raises_config_error(tmp_path: Path) -> None:
    data = _valid()
    data["chaining"]["stages_per_deck"] = 0
    with pytest.raises(ConfigError):
        load_settings(_write(tmp_path, data))


def test_load_settings_empty_total_parcels_raises_config_error(tmp_path: Path) -> None:
    data = _valid()
    data["costs"]["total_parcels"] = []
    with pytest.raises(ConfigError):
        load_settings(_write(tmp_path, data))


def test_load_settings_malformed_json_raises_config_error_from_json_decode_error(
    tmp_path: Path,
) -> None:
    target = tmp_path / "settings.json"
    target.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        load_settings(target)
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


def test_load_settings_missing_file_raises_config_error_naming_resolved_path(
    tmp_path: Path,
) -> None:
    absent = tmp_path / "absent.json"
    with pytest.raises(ConfigError, match=re.escape(str(absent.resolve()))):
        load_settings(absent)


def test_load_settings_repository_settings_json_has_expected_defaults() -> None:
    repo_settings = Path(__file__).resolve().parent.parent / "settings.json"
    settings = load_settings(repo_settings)
    assert settings.output.default_filename == "dashboard_dessem.html"
    assert settings.chaining.stages_per_deck == 48
    assert settings.dashboard.footer_text == "Gerência de Ferramentas Energéticas - FEN"


def test_load_settings_bool_for_int_key_raises_config_error(tmp_path: Path) -> None:
    data = _valid()
    data["chaining"]["stages_per_deck"] = True
    with pytest.raises(ConfigError, match="stages_per_deck"):
        load_settings(_write(tmp_path, data))


def test_load_settings_int_for_use_rich_raises_config_error(tmp_path: Path) -> None:
    data = _valid()
    data["logging"]["use_rich"] = 1
    with pytest.raises(ConfigError, match="use_rich"):
        load_settings(_write(tmp_path, data))


def test_load_settings_int_for_include_fictitious_raises_config_error(tmp_path: Path) -> None:
    data = _valid()
    data["submarkets"]["include_fictitious"] = 0
    with pytest.raises(ConfigError, match="include_fictitious"):
        load_settings(_write(tmp_path, data))
