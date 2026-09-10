"""Parquet schema contracts for the DESSEM synthesis files.

Transcribes Appendix A of the master plan (00-master-plan.md) into data: the shared long
operation-series schema, the entity keys per aggregation level, the registry and scalar-per-deck
file schemas, and the unit fallback table. This module performs no file I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

import pandas as pd

from dessem_dashboard.errors import SchemaError


class AggregationLevel(StrEnum):
    """Aggregation levels of the 40 long operation-series synthesis files (Appendix A.2)."""

    SIN = "SIN"
    SBM = "SBM"
    SBP = "SBP"
    UHE = "UHE"
    UTE = "UTE"


ENTITY_KEYS: Mapping[AggregationLevel, tuple[str, ...]] = MappingProxyType(
    {
        AggregationLevel.SIN: (),
        AggregationLevel.SBM: ("codigo_submercado",),
        AggregationLevel.SBP: ("codigo_submercado_de", "codigo_submercado_para"),
        AggregationLevel.UHE: ("codigo_usina", "codigo_ree", "codigo_submercado"),
        AggregationLevel.UTE: ("codigo_usina", "codigo_submercado"),
    }
)

# The nine columns shared by every long operation-series file, after the entity keys.
# Column ORDER here is documentation only; validate_columns compares sets, not sequences.
SERIES_COLUMNS: tuple[str, ...] = (
    "estagio",
    "data_inicio",
    "data_fim",
    "cenario",
    "patamar",
    "duracao_patamar",
    "valor",
    "limite_inferior",
    "limite_superior",
)

SERIES_DTYPES: Mapping[str, str] = MappingProxyType(
    {
        "estagio": "int64",
        "data_inicio": "datetime64[ns, UTC]",
        "data_fim": "datetime64[ns, UTC]",
        "cenario": "int64",
        "patamar": "int64",
        "duracao_patamar": "float64",
        "valor": "float64",
        "limite_inferior": "float64",
        "limite_superior": "float64",
    }
)

REGISTRY_COLUMNS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "UHE": ("codigo_usina", "codigo_ree", "codigo_submercado", "ree", "submercado", "usina"),
        "UTE": ("codigo_usina", "usina", "codigo_submercado", "submercado"),
        # codigo_submercado is the nullable pandas Int64 dtype here, unlike its int64 use elsewhere.
        "SBM": ("codigo_submercado", "submercado", "nome_submercado"),
        "REE": ("codigo_ree", "ree"),
        "EST": ("estagio", "data_inicio", "data_fim"),
        "PAT": ("data_inicio", "estagio", "patamar", "valor"),
        "METADADOS_OPERACAO": (
            "chave",
            "nome_curto_variavel",
            "nome_longo_variavel",
            "nome_curto_agregacao",
            "nome_longo_agregacao",
            "unidade",
            "calculado",
            "limitado",
        ),
    }
)

SCALAR_COLUMNS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "CUSTOS": ("parcela", "valor_esperado", "desvio_padrao"),
        "TEMPO": ("etapa", "tempo", "execucao"),
    }
)

# Unit fallback for chart titles when METADADOS_OPERACAO is unavailable or incomplete (ticket-011,
# ticket-015). Covers the 23 keys enabled by default (Appendix A.6) plus the 19 disabled registry
# entries listed below that table; units verified against METADADOS_OPERACAO.parquet.
FALLBACK_UNITS: Mapping[str, str] = MappingProxyType(
    {
        # Enabled chart catalogue (Appendix A.6).
        "GTER_SIN": "MW",
        "GHID_SIN": "MW",
        "GUNS_SIN": "MW",
        "EARMF_SIN": "MWh",
        "VARMF_SIN": "hm3",
        "MER_SBM": "MW",
        "GHID_SBM": "MW",
        "GTER_SBM": "MW",
        "GUNS_SBM": "MW",
        "CMO_SBM": "R$/MWh",
        "VARMF_SBM": "hm3",
        "INT_SBP": "MW",
        "GHID_UHE": "MW",
        "QTUR_UHE": "m3/s",
        "QVER_UHE": "m3/s",
        "VARMF_UHE": "hm3",
        "VARPF_UHE": "%",
        "QDEF_UHE": "m3/s",
        "QAFL_UHE": "m3/s",
        "QINC_UHE": "m3/s",
        "GTER_UTE": "MW",
        "CUSTOS": "R$",
        "TEMPO": "min",
        # Disabled registry entries (Appendix A.6, below the enabled table).
        "MER_SIN": "MW",
        "MERL_SBM": "MW",
        "MERL_SIN": "MW",
        "GUNSD_SIN": "MW",
        "GUNSD_SBM": "MW",
        "EARMF_SBM": "MWh",
        "VARMI_SIN": "hm3",
        "VARMI_SBM": "hm3",
        "VARMI_UHE": "hm3",
        "VARPI_UHE": "%",
        "VAGUA_UHE": "R$/MWh",
        "VCALHA_UHE": "hm3",
        "CFU_SIN": "10^6 R$",
        "COP_SIN": "10^3 R$",
        "CUNS_SIN": "MW",
        "CUNS_SBM": "MW",
        "QDEF_SIN": "m3/s",
        "QTUR_SIN": "m3/s",
        "QVER_SIN": "m3/s",
    }
)


def series_columns(level: AggregationLevel) -> tuple[str, ...]:
    """Return the entity keys of level followed by the nine shared series columns."""
    return ENTITY_KEYS[level] + SERIES_COLUMNS


def validate_columns(frame: pd.DataFrame, expected: Sequence[str], *, source: Path) -> None:
    """Raise SchemaError unless frame's column set equals expected; order is not checked."""
    actual = set(frame.columns)
    expected_set = set(expected)
    missing = sorted(expected_set - actual)
    unexpected = sorted(actual - expected_set)
    if not missing and not unexpected:
        return
    raise SchemaError(
        f"Arquivo {source.name}: colunas ausentes {missing}; colunas inesperadas {unexpected}"
    )


def validate_series_columns(frame: pd.DataFrame, level: AggregationLevel, *, source: Path) -> None:
    """Raise SchemaError unless frame's columns match the long series schema for level."""
    validate_columns(frame, series_columns(level), source=source)
