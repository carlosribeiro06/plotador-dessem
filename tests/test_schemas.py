"""Tests for dessem_dashboard.data.schemas."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from dessem_dashboard.data.schemas import (
    ENTITY_KEYS,
    FALLBACK_UNITS,
    REGISTRY_COLUMNS,
    SCALAR_COLUMNS,
    SERIES_COLUMNS,
    SERIES_DTYPES,
    AggregationLevel,
    series_columns,
    validate_columns,
    validate_series_columns,
)
from dessem_dashboard.errors import SchemaError

# The 23 enabled chart-catalogue keys, Appendix A.6.
_ENABLED_CHART_KEYS = (
    "GTER_SIN",
    "GHID_SIN",
    "GUNS_SIN",
    "EARMF_SIN",
    "VARMF_SIN",
    "MER_SBM",
    "GHID_SBM",
    "GTER_SBM",
    "GUNS_SBM",
    "CMO_SBM",
    "VARMF_SBM",
    "INT_SBP",
    "GHID_UHE",
    "QTUR_UHE",
    "QVER_UHE",
    "VARMF_UHE",
    "VARPF_UHE",
    "QDEF_UHE",
    "QAFL_UHE",
    "QINC_UHE",
    "GTER_UTE",
    "CUSTOS",
    "TEMPO",
)

# The 19 disabled registry entries listed just below the Appendix A.6 table.
_DISABLED_CHART_KEYS = (
    "MER_SIN",
    "MERL_SBM",
    "MERL_SIN",
    "GUNSD_SIN",
    "GUNSD_SBM",
    "EARMF_SBM",
    "VARMI_SIN",
    "VARMI_SBM",
    "VARMI_UHE",
    "VARPI_UHE",
    "VAGUA_UHE",
    "VCALHA_UHE",
    "CFU_SIN",
    "COP_SIN",
    "CUNS_SIN",
    "CUNS_SBM",
    "QDEF_SIN",
    "QTUR_SIN",
    "QVER_SIN",
)


def test_aggregation_level_values_equal_member_names() -> None:
    assert AggregationLevel.SIN == "SIN"
    assert AggregationLevel.UHE.value == "UHE"


def test_entity_keys_sin_is_empty() -> None:
    assert ENTITY_KEYS[AggregationLevel.SIN] == ()


def test_entity_keys_sbm_has_one_column() -> None:
    assert ENTITY_KEYS[AggregationLevel.SBM] == ("codigo_submercado",)


def test_entity_keys_sbp_has_submarket_pair_columns() -> None:
    assert ENTITY_KEYS[AggregationLevel.SBP] == ("codigo_submercado_de", "codigo_submercado_para")


def test_entity_keys_uhe_matches_plant_ree_submarket() -> None:
    assert ENTITY_KEYS[AggregationLevel.UHE] == (
        "codigo_usina",
        "codigo_ree",
        "codigo_submercado",
    )


def test_entity_keys_ute_matches_plant_submarket() -> None:
    assert ENTITY_KEYS[AggregationLevel.UTE] == ("codigo_usina", "codigo_submercado")


def test_series_columns_has_nine_entries_in_appendix_order() -> None:
    assert SERIES_COLUMNS == (
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


@pytest.mark.parametrize(
    ("level", "expected_length"),
    [
        (AggregationLevel.SIN, 9),
        (AggregationLevel.SBM, 10),
        (AggregationLevel.SBP, 11),
        (AggregationLevel.UHE, 12),
        (AggregationLevel.UTE, 11),
    ],
)
def test_series_columns_length_per_level(level: AggregationLevel, expected_length: int) -> None:
    assert len(series_columns(level)) == expected_length


def test_series_columns_prefixes_entity_keys_before_shared_columns() -> None:
    expected = ENTITY_KEYS[AggregationLevel.UHE] + SERIES_COLUMNS
    assert series_columns(AggregationLevel.UHE) == expected


def test_series_dtypes_covers_every_series_column() -> None:
    assert set(SERIES_DTYPES) == set(SERIES_COLUMNS)


def test_series_dtypes_uses_utc_timestamps_for_the_two_date_columns() -> None:
    assert SERIES_DTYPES["data_inicio"] == "datetime64[ns, UTC]"
    assert SERIES_DTYPES["data_fim"] == "datetime64[ns, UTC]"


def test_registry_columns_covers_exactly_seven_files() -> None:
    assert set(REGISTRY_COLUMNS) == {
        "UHE",
        "UTE",
        "SBM",
        "REE",
        "EST",
        "PAT",
        "METADADOS_OPERACAO",
    }


def test_scalar_columns_covers_exactly_two_files() -> None:
    assert set(SCALAR_COLUMNS) == {"CUSTOS", "TEMPO"}


def test_validate_columns_returns_none_for_exact_match() -> None:
    frame = pd.DataFrame(columns=list(SERIES_COLUMNS))
    assert validate_columns(frame, SERIES_COLUMNS, source=Path("GHID_SIN.parquet")) is None


def test_validate_columns_returns_none_for_permuted_column_order() -> None:
    permuted = list(reversed(SERIES_COLUMNS))
    frame = pd.DataFrame(columns=permuted)
    assert validate_columns(frame, SERIES_COLUMNS, source=Path("GHID_SIN.parquet")) is None


def test_validate_columns_raises_on_missing_column_naming_column_and_source() -> None:
    columns = [column for column in SERIES_COLUMNS if column != "duracao_patamar"]
    frame = pd.DataFrame(columns=columns)
    with pytest.raises(SchemaError) as exc_info:
        validate_columns(frame, SERIES_COLUMNS, source=Path("GHID_SIN.parquet"))
    message = str(exc_info.value)
    assert "duracao_patamar" in message
    assert "GHID_SIN.parquet" in message


def test_validate_columns_raises_on_unexpected_column_naming_it() -> None:
    frame = pd.DataFrame(columns=[*SERIES_COLUMNS, "extra"])
    with pytest.raises(SchemaError, match=re.escape("extra")):
        validate_columns(frame, SERIES_COLUMNS, source=Path("GHID_SIN.parquet"))


def test_validate_columns_raises_naming_both_missing_and_unexpected() -> None:
    columns = [column for column in SERIES_COLUMNS if column != "duracao_patamar"]
    frame = pd.DataFrame(columns=[*columns, "extra"])
    with pytest.raises(SchemaError) as exc_info:
        validate_columns(frame, SERIES_COLUMNS, source=Path("GHID_SIN.parquet"))
    message = str(exc_info.value)
    assert "duracao_patamar" in message
    assert "extra" in message


def test_validate_series_columns_raises_on_missing_column() -> None:
    columns = [column for column in SERIES_COLUMNS if column != "duracao_patamar"]
    frame = pd.DataFrame(columns=columns)
    with pytest.raises(SchemaError) as exc_info:
        validate_series_columns(frame, AggregationLevel.SIN, source=Path("GHID_SIN.parquet"))
    message = str(exc_info.value)
    assert "duracao_patamar" in message
    assert "GHID_SIN.parquet" in message


def test_validate_series_columns_raises_on_unexpected_extra_column() -> None:
    frame = pd.DataFrame(columns=[*SERIES_COLUMNS, "extra"])
    with pytest.raises(SchemaError, match=re.escape("extra")):
        validate_series_columns(frame, AggregationLevel.SIN, source=Path("GHID_SIN.parquet"))


def test_validate_series_columns_returns_none_for_sbm_with_entity_key() -> None:
    columns = [*ENTITY_KEYS[AggregationLevel.SBM], *SERIES_COLUMNS]
    frame = pd.DataFrame(columns=columns)
    result = validate_series_columns(frame, AggregationLevel.SBM, source=Path("CMO_SBM.parquet"))
    assert result is None


def test_fallback_units_covers_every_enabled_chart_key() -> None:
    assert set(_ENABLED_CHART_KEYS) <= set(FALLBACK_UNITS)


def test_fallback_units_covers_every_disabled_chart_key() -> None:
    assert set(_DISABLED_CHART_KEYS) <= set(FALLBACK_UNITS)


def test_fallback_units_has_exactly_forty_two_keys() -> None:
    assert len(FALLBACK_UNITS) == 42
    assert set(FALLBACK_UNITS) == set(_ENABLED_CHART_KEYS) | set(_DISABLED_CHART_KEYS)


def test_fallback_units_matches_acceptance_criteria_values() -> None:
    assert FALLBACK_UNITS["CMO_SBM"] == "R$/MWh"
    assert FALLBACK_UNITS["QTUR_UHE"] == "m3/s"
    assert FALLBACK_UNITS["VARPF_UHE"] == "%"
    assert FALLBACK_UNITS["EARMF_SIN"] == "MWh"


def test_entity_keys_rejects_mutation() -> None:
    with pytest.raises(TypeError):
        ENTITY_KEYS[AggregationLevel.SIN] = ("x",)


def test_series_dtypes_rejects_mutation() -> None:
    with pytest.raises(TypeError):
        SERIES_DTYPES["estagio"] = "float64"


def test_registry_columns_rejects_mutation() -> None:
    with pytest.raises(TypeError):
        REGISTRY_COLUMNS["UHE"] = ()


def test_scalar_columns_rejects_mutation() -> None:
    with pytest.raises(TypeError):
        SCALAR_COLUMNS["CUSTOS"] = ()


def test_fallback_units_rejects_mutation() -> None:
    with pytest.raises(TypeError):
        FALLBACK_UNITS["CMO_SBM"] = "MW"
