"""Load and validate settings.json into typed, frozen dataclasses.

Every path-valued key resolves to an absolute Path relative to the directory
of the settings file itself, never to the current working directory.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dessem_dashboard.errors import ConfigError

_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True)
class Paths:
    output_dir: Path
    log_dir: Path
    logo_file: Path


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    file: Path
    rotate_max_bytes: int
    rotate_backups: int
    use_rich: bool


@dataclass(frozen=True)
class DiscoveryConfig:
    sintese_dirname: str


@dataclass(frozen=True)
class ChainingConfig:
    stages_per_deck: int


@dataclass(frozen=True)
class CostsConfig:
    total_parcels: list[str]


@dataclass(frozen=True)
class TimeConfig:
    stage_groups: dict[str, list[str]]
    unit_divisor: float


@dataclass(frozen=True)
class SubmarketsConfig:
    include_fictitious: bool
    fictitious_codes: list[int]


@dataclass(frozen=True)
class DashboardConfig:
    title: str
    footer_text: str
    date_format: str


@dataclass(frozen=True)
class OutputConfig:
    default_filename: str
    decimals: int
    size_warning_mb: float


@dataclass(frozen=True)
class ChartsConfig:
    disabled: list[str]


@dataclass(frozen=True)
class Settings:
    """Validated project configuration, loaded from settings.json."""

    project: str
    paths: Paths
    logging: LoggingConfig
    discovery: DiscoveryConfig
    chaining: ChainingConfig
    costs: CostsConfig
    time: TimeConfig
    submarkets: SubmarketsConfig
    dashboard: DashboardConfig
    output: OutputConfig
    charts: ChartsConfig


def _dotted(prefix: str, key: str) -> str:
    return f"{prefix}.{key}" if prefix else key


def _require[T](mapping: Mapping[str, object], key: str, expected: type[T], *, prefix: str) -> T:
    """Return mapping[key], validating presence and JSON type."""
    dotted = _dotted(prefix, key)
    if key not in mapping:
        raise ConfigError(f"Chave obrigatória ausente em settings.json: '{dotted}'")
    value = mapping[key]
    if expected is int and isinstance(value, bool):
        raise ConfigError(f"Chave '{dotted}' deveria ser int, veio bool")
    if not isinstance(value, expected):
        raise ConfigError(
            f"Chave '{dotted}' deveria ser {expected.__name__}, veio {type(value).__name__}"
        )
    return value


def _require_group(mapping: Mapping[str, object], key: str, *, prefix: str) -> dict[str, object]:
    """Return mapping[key] validated as a JSON object (a nested settings group)."""
    dotted = _dotted(prefix, key)
    if key not in mapping:
        raise ConfigError(f"Chave obrigatória ausente em settings.json: '{dotted}'")
    value = mapping[key]
    if not isinstance(value, dict):
        raise ConfigError(f"Chave '{dotted}' deveria ser dict, veio {type(value).__name__}")
    return value


def _require_int_ge(mapping: Mapping[str, object], key: str, minimum: int, *, prefix: str) -> int:
    value = _require(mapping, key, int, prefix=prefix)
    if value < minimum:
        dotted = _dotted(prefix, key)
        raise ConfigError(f"Chave '{dotted}' deve ser >= {minimum}, veio {value}")
    return value


def _require_positive_number(mapping: Mapping[str, object], key: str, *, prefix: str) -> float:
    dotted = _dotted(prefix, key)
    if key not in mapping:
        raise ConfigError(f"Chave obrigatória ausente em settings.json: '{dotted}'")
    value = mapping[key]
    if isinstance(value, bool):
        raise ConfigError(f"Chave '{dotted}' deveria ser number, veio bool")
    if not isinstance(value, (int, float)):
        raise ConfigError(f"Chave '{dotted}' deveria ser number, veio {type(value).__name__}")
    if value <= 0:
        raise ConfigError(f"Chave '{dotted}' deve ser positiva, veio {value}")
    return float(value)


def _require_str_list(
    mapping: Mapping[str, object], key: str, *, prefix: str, allow_empty: bool
) -> list[str]:
    value = _require(mapping, key, list, prefix=prefix)
    dotted = _dotted(prefix, key)
    if not allow_empty and len(value) == 0:
        raise ConfigError(f"Chave '{dotted}' não pode ser uma lista vazia")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(
                f"Chave '{dotted}' deve conter apenas strings, encontrado {type(item).__name__}"
            )
        result.append(item)
    return result


def _require_int_list(mapping: Mapping[str, object], key: str, *, prefix: str) -> list[int]:
    value = _require(mapping, key, list, prefix=prefix)
    dotted = _dotted(prefix, key)
    result: list[int] = []
    for item in value:
        if isinstance(item, bool):
            raise ConfigError(f"Chave '{dotted}' deve conter apenas inteiros, encontrado bool")
        if not isinstance(item, int):
            raise ConfigError(
                f"Chave '{dotted}' deve conter apenas inteiros, encontrado {type(item).__name__}"
            )
        result.append(item)
    return result


def _require_stage_groups(
    mapping: Mapping[str, object], key: str, *, prefix: str
) -> dict[str, list[str]]:
    raw_group = _require_group(mapping, key, prefix=prefix)
    dotted = _dotted(prefix, key)
    result: dict[str, list[str]] = {}
    for group_name, stages in raw_group.items():
        if not isinstance(stages, list):
            raise ConfigError(f"Chave '{dotted}.{group_name}' deveria ser uma lista de strings")
        if len(stages) == 0:
            raise ConfigError(f"Chave '{dotted}.{group_name}' não pode ser uma lista vazia")
        stage_list: list[str] = []
        for stage in stages:
            if not isinstance(stage, str):
                raise ConfigError(f"Chave '{dotted}.{group_name}' deve conter apenas strings")
            stage_list.append(stage)
        result[group_name] = stage_list
    return result


def _require_log_level(mapping: Mapping[str, object], key: str, *, prefix: str) -> str:
    value = _require(mapping, key, str, prefix=prefix)
    if value not in _VALID_LOG_LEVELS:
        dotted = _dotted(prefix, key)
        raise ConfigError(
            f"Chave '{dotted}' deve ser um de {sorted(_VALID_LOG_LEVELS)}, veio '{value}'"
        )
    return value


def _resolve_path(base: Path, mapping: Mapping[str, object], key: str, *, prefix: str) -> Path:
    value = _require(mapping, key, str, prefix=prefix)
    return base / value


def _load_paths(raw: Mapping[str, object], *, base: Path) -> Paths:
    group = _require_group(raw, "paths", prefix="")
    return Paths(
        output_dir=_resolve_path(base, group, "output_dir", prefix="paths"),
        log_dir=_resolve_path(base, group, "log_dir", prefix="paths"),
        logo_file=_resolve_path(base, group, "logo_file", prefix="paths"),
    )


def _load_logging(raw: Mapping[str, object], *, base: Path) -> LoggingConfig:
    group = _require_group(raw, "logging", prefix="")
    return LoggingConfig(
        level=_require_log_level(group, "level", prefix="logging"),
        file=_resolve_path(base, group, "file", prefix="logging"),
        rotate_max_bytes=_require(group, "rotate_max_bytes", int, prefix="logging"),
        rotate_backups=_require(group, "rotate_backups", int, prefix="logging"),
        use_rich=_require(group, "use_rich", bool, prefix="logging"),
    )


def _load_discovery(raw: Mapping[str, object]) -> DiscoveryConfig:
    group = _require_group(raw, "discovery", prefix="")
    return DiscoveryConfig(
        sintese_dirname=_require(group, "sintese_dirname", str, prefix="discovery"),
    )


def _load_chaining(raw: Mapping[str, object]) -> ChainingConfig:
    group = _require_group(raw, "chaining", prefix="")
    return ChainingConfig(
        stages_per_deck=_require_int_ge(group, "stages_per_deck", 1, prefix="chaining"),
    )


def _load_costs(raw: Mapping[str, object]) -> CostsConfig:
    group = _require_group(raw, "costs", prefix="")
    return CostsConfig(
        total_parcels=_require_str_list(group, "total_parcels", prefix="costs", allow_empty=False),
    )


def _load_time(raw: Mapping[str, object]) -> TimeConfig:
    group = _require_group(raw, "time", prefix="")
    return TimeConfig(
        stage_groups=_require_stage_groups(group, "stage_groups", prefix="time"),
        unit_divisor=_require_positive_number(group, "unit_divisor", prefix="time"),
    )


def _load_submarkets(raw: Mapping[str, object]) -> SubmarketsConfig:
    group = _require_group(raw, "submarkets", prefix="")
    return SubmarketsConfig(
        include_fictitious=_require(group, "include_fictitious", bool, prefix="submarkets"),
        fictitious_codes=_require_int_list(group, "fictitious_codes", prefix="submarkets"),
    )


def _load_dashboard(raw: Mapping[str, object]) -> DashboardConfig:
    group = _require_group(raw, "dashboard", prefix="")
    return DashboardConfig(
        title=_require(group, "title", str, prefix="dashboard"),
        footer_text=_require(group, "footer_text", str, prefix="dashboard"),
        date_format=_require(group, "date_format", str, prefix="dashboard"),
    )


def _load_output(raw: Mapping[str, object]) -> OutputConfig:
    group = _require_group(raw, "output", prefix="")
    return OutputConfig(
        default_filename=_require(group, "default_filename", str, prefix="output"),
        decimals=_require_int_ge(group, "decimals", 0, prefix="output"),
        size_warning_mb=_require_positive_number(group, "size_warning_mb", prefix="output"),
    )


def _load_charts(raw: Mapping[str, object]) -> ChartsConfig:
    group = _require_group(raw, "charts", prefix="")
    return ChartsConfig(
        disabled=_require_str_list(group, "disabled", prefix="charts", allow_empty=True),
    )


def load_settings(path: str | Path = "settings.json") -> Settings:
    """Load and validate settings.json, resolving paths against its own directory."""
    settings_path = Path(path)
    if not settings_path.is_file():
        raise ConfigError(f"settings.json não encontrado em: {settings_path.resolve()}")
    try:
        parsed: object = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise ConfigError(f"settings.json inválido em {settings_path.resolve()}: {err}") from err
    if not isinstance(parsed, dict):
        raise ConfigError(f"settings.json deve conter um objeto JSON: {settings_path.resolve()}")
    raw: dict[str, object] = parsed

    base = settings_path.resolve().parent
    return Settings(
        project=_require(raw, "project", str, prefix=""),
        paths=_load_paths(raw, base=base),
        logging=_load_logging(raw, base=base),
        discovery=_load_discovery(raw),
        chaining=_load_chaining(raw),
        costs=_load_costs(raw),
        time=_load_time(raw),
        submarkets=_load_submarkets(raw),
        dashboard=_load_dashboard(raw),
        output=_load_output(raw),
        charts=_load_charts(raw),
    )
