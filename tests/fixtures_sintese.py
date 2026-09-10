"""Synthetic sintese/ directory generator for the DESSEM dashboard test suite.

Builds schema-faithful Parquet fixtures under a target directory, driven by
dessem_dashboard.charts.registry.enabled_specs() and dessem_dashboard.data.schemas so the fixtures
track the real data contracts. Test-only infrastructure: no test may read the real, gitignored
study data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pandas as pd

from dessem_dashboard.charts.registry import ChartKind, ChartSpec, enabled_specs
from dessem_dashboard.data.schemas import (
    ENTITY_KEYS,
    FALLBACK_UNITS,
    REGISTRY_COLUMNS,
    SCALAR_COLUMNS,
    SERIES_DTYPES,
    AggregationLevel,
    series_columns,
)

_REGISTRY_FILE_NAMES: tuple[str, ...] = (
    "EST.parquet",
    "PAT.parquet",
    "UHE.parquet",
    "UTE.parquet",
    "SBM.parquet",
    "REE.parquet",
    "METADADOS_OPERACAO.parquet",
)

_REE_POOL: tuple[tuple[int, str], ...] = (
    (1, "SUDESTE"),
    (2, "SUL"),
    (3, "NORDESTE"),
    (4, "NORTE"),
)

_FICTITIOUS_SUBMARKET_CODES: frozenset[int] = frozenset({11, 99})

# Short and long submarket names. Code 99 carries no long name, reproducing the real file's NaN
# (planning-context.md: "11 FC/NOFICT1, 99 IV/NaN"); code 11 has the real long name NOFICT1.
_SUBMARKET_NAMES: Mapping[int, tuple[str, str | None]] = MappingProxyType(
    {
        1: ("SE", "SUDESTE"),
        2: ("S", "SUL"),
        3: ("NE", "NORDESTE"),
        4: ("N", "NORTE"),
        11: ("FC", "NOFICT1"),
        99: ("IV", None),
    }
)

_CUSTOS_PARCELAS: tuple[str, ...] = ("PRESENTE", "FUTURO", "VIOLACOES", "PEQUENAS PENALIDADES")

# Five distinct etapa values over nine rows, three of them "PL", per Appendix A.5.
_TEMPO_ETAPAS: tuple[str, ...] = (
    "Leitura de Dados e Impressão",
    "MILP",
    "PL",
    "PL",
    "PL",
    "PL.Int.Fix",
    "PL.Int.Fix",
    "PL.CalcCMO",
    "PL.CalcCMO",
)

_RESERVOIR_ONLY_KEYS: frozenset[str] = frozenset({"VARMF_UHE", "VARPF_UHE"})
_PERCENTAGE_KEYS: frozenset[str] = frozenset({"VARPF_UHE"})
_DEFAULT_VALUE_RANGE: tuple[float, float] = (0.0, 1000.0)
_PERCENTAGE_VALUE_RANGE: tuple[float, float] = (0.0, 100.0)


def _submarket_names(code: int) -> tuple[str, str | None]:
    """Return (short name, long name) for code, fabricating names for unknown codes."""
    if code in _SUBMARKET_NAMES:
        return _SUBMARKET_NAMES[code]
    if code in _FICTITIOUS_SUBMARKET_CODES:
        return f"SBM{code}", None
    return f"SBM{code}", f"SUBMERCADO_{code}"


def _submarket_pool(submarket_codes: Sequence[int]) -> tuple[int, ...]:
    """Return the non-fictitious codes of submarket_codes, or all of them if none qualify."""
    real_codes = tuple(code for code in submarket_codes if code not in _FICTITIOUS_SUBMARKET_CODES)
    return real_codes if real_codes else tuple(submarket_codes)


def _round_robin(codes: Sequence[int], pool: Sequence[int]) -> dict[int, int]:
    """Assign each entry of codes one entry of pool, cycling when codes is longer than pool."""
    return {code: pool[index % len(pool)] for index, code in enumerate(codes)}


def _to_utc_timestamp(value: datetime) -> pd.Timestamp:
    """Interpret value as UTC: localize a naive datetime, convert an aware one."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _build_stage_table(
    first_stage_start: datetime,
    n_stages: int,
    half_hour_stages: int,
    long_stage_hours: float,
) -> pd.DataFrame:
    """Build the contiguous stage table shared by EST.parquet and every series file."""
    start = _to_utc_timestamp(first_stage_start)
    durations = [0.5 if index < half_hour_stages else long_stage_hours for index in range(n_stages)]
    starts: list[pd.Timestamp] = []
    current = start
    for duration in durations:
        starts.append(current)
        current = current + pd.Timedelta(hours=duration)
    ends = [*starts[1:], current]
    return pd.DataFrame(
        {
            "estagio": np.arange(1, n_stages + 1, dtype="int64"),
            "data_inicio": pd.array(starts, dtype="datetime64[ns, UTC]"),
            "data_fim": pd.array(ends, dtype="datetime64[ns, UTC]"),
            "duracao_patamar": np.array(durations, dtype="float64"),
        }
    )


def _uhe_registry_and_keys(
    hydro_codes: Sequence[int], submarket_codes: Sequence[int]
) -> tuple[pd.DataFrame, dict[int, tuple[int, int]]]:
    """Build UHE.parquet plus a codigo_usina -> (codigo_ree, codigo_submercado) lookup."""
    submarket_pool = _submarket_pool(submarket_codes)
    submarket_by_code = _round_robin(hydro_codes, submarket_pool)
    keys: dict[int, tuple[int, int]] = {}
    rows: list[dict[str, int | str]] = []
    for index, code in enumerate(hydro_codes):
        ree_code, ree_name = _REE_POOL[index % len(_REE_POOL)]
        submarket_code = submarket_by_code[code]
        submarket_short, _ = _submarket_names(submarket_code)
        keys[code] = (ree_code, submarket_code)
        rows.append(
            {
                "codigo_usina": code,
                "codigo_ree": ree_code,
                "codigo_submercado": submarket_code,
                "ree": ree_name,
                "submercado": submarket_short,
                "usina": f"USINA_{code}",
            }
        )
    registry = pd.DataFrame(rows, columns=list(REGISTRY_COLUMNS["UHE"]))
    return registry, keys


def _uhe_entity_frame(codes: Sequence[int], keys: Mapping[int, tuple[int, int]]) -> pd.DataFrame:
    """Build the UHE entity-key rows for codes, using the codigo_usina -> keys lookup."""
    rows = [
        {"codigo_usina": code, "codigo_ree": keys[code][0], "codigo_submercado": keys[code][1]}
        for code in codes
    ]
    return pd.DataFrame(rows, columns=list(ENTITY_KEYS[AggregationLevel.UHE]))


def _ute_registry_and_keys(
    thermal_codes: Sequence[int], submarket_codes: Sequence[int]
) -> tuple[pd.DataFrame, dict[int, int]]:
    """Build UTE.parquet plus a codigo_usina -> codigo_submercado lookup."""
    submarket_pool = _submarket_pool(submarket_codes)
    submarket_by_code = _round_robin(thermal_codes, submarket_pool)
    rows: list[dict[str, int | str]] = []
    for code in thermal_codes:
        submarket_code = submarket_by_code[code]
        submarket_short, _ = _submarket_names(submarket_code)
        rows.append(
            {
                "codigo_usina": code,
                "usina": f"TERMICA_{code}",
                "codigo_submercado": submarket_code,
                "submercado": submarket_short,
            }
        )
    registry = pd.DataFrame(rows, columns=list(REGISTRY_COLUMNS["UTE"]))
    return registry, submarket_by_code


def _ute_entity_frame(codes: Sequence[int], keys: Mapping[int, int]) -> pd.DataFrame:
    """Build the UTE entity-key rows for codes, using the codigo_usina -> keys lookup."""
    rows = [{"codigo_usina": code, "codigo_submercado": keys[code]} for code in codes]
    return pd.DataFrame(rows, columns=list(ENTITY_KEYS[AggregationLevel.UTE]))


def _sbm_registry(submarket_codes: Sequence[int]) -> pd.DataFrame:
    """Build SBM.parquet with the nullable Int64 codigo_submercado dtype."""
    short_names: list[str] = []
    long_names: list[str | None] = []
    for code in submarket_codes:
        short_name, long_name = _submarket_names(code)
        short_names.append(short_name)
        long_names.append(long_name)
    return pd.DataFrame(
        {
            "codigo_submercado": pd.array(list(submarket_codes), dtype="Int64"),
            "submercado": short_names,
            "nome_submercado": long_names,
        }
    )


def _sbm_entity_frame(submarket_codes: Sequence[int]) -> pd.DataFrame:
    """Build the SBM entity-key rows for a series file."""
    return pd.DataFrame({"codigo_submercado": list(submarket_codes)})


def _sbp_entity_frame(pair_codes: Sequence[tuple[int, int]]) -> pd.DataFrame:
    """Build the SBP entity-key rows for INT_SBP."""
    return pd.DataFrame(
        {
            "codigo_submercado_de": [pair[0] for pair in pair_codes],
            "codigo_submercado_para": [pair[1] for pair in pair_codes],
        }
    )


def _ree_registry(uhe_registry: pd.DataFrame) -> pd.DataFrame:
    """Build REE.parquet from the distinct (codigo_ree, ree) pairs used by UHE.parquet."""
    unique = uhe_registry[["codigo_ree", "ree"]].drop_duplicates().sort_values("codigo_ree")
    return unique.reset_index(drop=True)


def _metadados_operacao(specs: Sequence[ChartSpec]) -> pd.DataFrame:
    """Build METADADOS_OPERACAO.parquet with one row per enabled chart key."""
    rows = [
        {
            "chave": chart_spec.key,
            "nome_curto_variavel": chart_spec.key,
            "nome_longo_variavel": chart_spec.title,
            "nome_curto_agregacao": chart_spec.group.value,
            "nome_longo_agregacao": chart_spec.group.value,
            "unidade": FALLBACK_UNITS[chart_spec.key],
            "calculado": False,
            "limitado": False,
        }
        for chart_spec in specs
    ]
    return pd.DataFrame(rows, columns=list(REGISTRY_COLUMNS["METADADOS_OPERACAO"]))


def _custos_frame(rng: np.random.Generator) -> pd.DataFrame:
    """Build CUSTOS.parquet with all four parcela rows."""
    values = rng.uniform(0.0, 1_000_000.0, size=len(_CUSTOS_PARCELAS))
    frame = pd.DataFrame(
        {
            "parcela": list(_CUSTOS_PARCELAS),
            "valor_esperado": values.astype("float64"),
            "desvio_padrao": np.zeros(len(_CUSTOS_PARCELAS), dtype="int64"),
        }
    )
    return frame[list(SCALAR_COLUMNS["CUSTOS"])]


def _tempo_frame(rng: np.random.Generator) -> pd.DataFrame:
    """Build TEMPO.parquet with nine rows, three of them the PL etapa."""
    values = rng.uniform(10.0, 2000.0, size=len(_TEMPO_ETAPAS))
    frame = pd.DataFrame(
        {
            "etapa": list(_TEMPO_ETAPAS),
            "tempo": values.astype("float64"),
            "execucao": np.zeros(len(_TEMPO_ETAPAS), dtype="int64"),
        }
    )
    return frame[list(SCALAR_COLUMNS["TEMPO"])]


def _entity_rows_for_spec(
    chart_spec: ChartSpec,
    *,
    sin_entities: pd.DataFrame,
    sbm_entities: pd.DataFrame,
    sbp_entities: pd.DataFrame,
    uhe_entities: pd.DataFrame,
    uhe_reservoir_entities: pd.DataFrame,
    ute_entities: pd.DataFrame,
) -> pd.DataFrame:
    """Return the entity-key rows a SERIES chart_spec must be crossed with."""
    level = chart_spec.level
    if level is AggregationLevel.SIN:
        return sin_entities
    if level is AggregationLevel.SBM:
        return sbm_entities
    if level is AggregationLevel.SBP:
        return sbp_entities
    if level is AggregationLevel.UHE:
        return uhe_reservoir_entities if chart_spec.key in _RESERVOIR_ONLY_KEYS else uhe_entities
    if level is AggregationLevel.UTE:
        return ute_entities
    raise AssertionError(f"SERIES chart spec without a handled level: {chart_spec.key}")


def _series_frame(
    level: AggregationLevel,
    entity_rows: pd.DataFrame,
    stages: pd.DataFrame,
    rng: np.random.Generator,
    *,
    value_low: float,
    value_high: float,
) -> pd.DataFrame:
    """Cross entity_rows with stages and add the nine shared series columns."""
    frame = entity_rows.merge(stages, how="cross")
    for column in entity_rows.columns:
        frame[column] = frame[column].astype("int64")
    frame["cenario"] = 1
    frame["patamar"] = 2
    frame["valor"] = rng.uniform(value_low, value_high, size=len(frame))
    frame["limite_inferior"] = -np.inf
    frame["limite_superior"] = np.inf
    frame = frame[list(series_columns(level))]
    return frame.astype(SERIES_DTYPES)


def _all_file_names() -> frozenset[str]:
    """Return every file name make_sintese_dir can produce, registries plus enabled specs."""
    series_names = (f"{chart_spec.source_file}.parquet" for chart_spec in enabled_specs())
    return frozenset(_REGISTRY_FILE_NAMES) | frozenset(series_names)


def _write_parquet(target: Path, file_name: str, frame: pd.DataFrame, skip: set[str]) -> None:
    """Write frame to target/file_name unless file_name is in skip."""
    if file_name in skip:
        return
    frame.to_parquet(target / file_name, index=False)


def make_sintese_dir(
    target: Path,
    *,
    first_stage_start: datetime,
    n_stages: int = 6,
    half_hour_stages: int = 4,
    long_stage_hours: float = 2.0,
    hydro_codes: Sequence[int] = (1, 2, 3),
    reservoir_codes: Sequence[int] = (1, 2),
    thermal_codes: Sequence[int] = (1, 2),
    submarket_codes: Sequence[int] = (1, 2, 11, 99),
    pair_codes: Sequence[tuple[int, int]] = ((1, 2), (2, 1)),
    omit: Sequence[str] = (),
    seed: int = 42,
) -> Path:
    """Write a synthetic sintese/ directory of Parquet files under target and return target.

    One file per enabled dessem_dashboard.charts.registry.enabled_specs() entry, plus the seven
    registry files EST, PAT, UHE, UTE, SBM, REE and METADADOS_OPERACAO. hydro_codes drives every
    UHE-level file except VARMF_UHE and VARPF_UHE, which use reservoir_codes, reproducing the real
    non-rectangular coverage. Raises ValueError if omit names a file this function never writes.
    """
    known_names = _all_file_names()
    unknown = sorted(set(omit) - known_names)
    if unknown:
        raise ValueError(f"omit names files the generator does not produce: {unknown}")
    skip = set(omit)

    target.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    stages = _build_stage_table(first_stage_start, n_stages, half_hour_stages, long_stage_hours)

    uhe_registry, uhe_keys = _uhe_registry_and_keys(hydro_codes, submarket_codes)
    ute_registry, ute_keys = _ute_registry_and_keys(thermal_codes, submarket_codes)
    sbm_registry = _sbm_registry(submarket_codes)
    ree_registry = _ree_registry(uhe_registry)

    sin_entities = pd.DataFrame(index=[0])
    sbm_entities = _sbm_entity_frame(submarket_codes)
    sbp_entities = _sbp_entity_frame(pair_codes)
    uhe_entities = _uhe_entity_frame(hydro_codes, uhe_keys)
    uhe_reservoir_entities = _uhe_entity_frame(reservoir_codes, uhe_keys)
    ute_entities = _ute_entity_frame(thermal_codes, ute_keys)

    est_frame = stages[list(REGISTRY_COLUMNS["EST"])]
    _write_parquet(target, "EST.parquet", est_frame, skip)
    pat_frame = pd.DataFrame(
        {
            "data_inicio": stages["data_inicio"],
            "estagio": stages["estagio"],
            "patamar": np.full(len(stages), 2, dtype="int64"),
            "valor": stages["duracao_patamar"],
        }
    )[list(REGISTRY_COLUMNS["PAT"])]
    _write_parquet(target, "PAT.parquet", pat_frame, skip)
    _write_parquet(target, "UHE.parquet", uhe_registry, skip)
    _write_parquet(target, "UTE.parquet", ute_registry, skip)
    _write_parquet(target, "SBM.parquet", sbm_registry, skip)
    _write_parquet(target, "REE.parquet", ree_registry, skip)

    specs = enabled_specs()
    _write_parquet(target, "METADADOS_OPERACAO.parquet", _metadados_operacao(specs), skip)

    for chart_spec in specs:
        file_name = f"{chart_spec.source_file}.parquet"
        if chart_spec.kind is ChartKind.SCALAR_BY_DECK:
            frame = _custos_frame(rng) if chart_spec.key == "CUSTOS" else _tempo_frame(rng)
        else:
            entity_rows = _entity_rows_for_spec(
                chart_spec,
                sin_entities=sin_entities,
                sbm_entities=sbm_entities,
                sbp_entities=sbp_entities,
                uhe_entities=uhe_entities,
                uhe_reservoir_entities=uhe_reservoir_entities,
                ute_entities=ute_entities,
            )
            level = chart_spec.level
            if level is None:
                raise AssertionError(f"SERIES chart spec without a level: {chart_spec.key}")
            value_low, value_high = (
                _PERCENTAGE_VALUE_RANGE
                if chart_spec.key in _PERCENTAGE_KEYS
                else _DEFAULT_VALUE_RANGE
            )
            frame = _series_frame(
                level, entity_rows, stages, rng, value_low=value_low, value_high=value_high
            )
        _write_parquet(target, file_name, frame, skip)

    return target
