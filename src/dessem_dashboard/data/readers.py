"""Typed Parquet readers for the DESSEM synthesis files (Appendix A of the master plan).

The only module in dessem_dashboard allowed to call pandas.read_parquet. Every function validates
the frame against the dessem_dashboard.data.schemas contract, normalises dtypes where the contract
requires it, and raises DataFileError or SchemaError rather than returning a silently wrong frame.
Readers never mutate their input files, never cache, never convert a timezone and never aggregate
rows: that is ticket-015/016/018/031 business.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

import pandas as pd

# pyarrow ships no py.typed marker (verified against the installed 25.0.1 wheel), so mypy cannot
# see through this module regardless of how it is imported.
from pyarrow.lib import ArrowInvalid  # type: ignore[import-untyped]

from dessem_dashboard.data.schemas import (
    ENTITY_KEYS,
    REGISTRY_COLUMNS,
    SCALAR_COLUMNS,
    SERIES_DTYPES,
    AggregationLevel,
    validate_columns,
    validate_series_columns,
)
from dessem_dashboard.errors import DataFileError, SchemaError

logger = logging.getLogger(__name__)

# data_inicio and data_fim need pandas.to_datetime(..., utc=True) rather than a plain astype, so a
# timezone-naive source column is labeled UTC (decision 10) instead of raising TypeError.
_TIMESTAMP_COLUMNS: tuple[str, ...] = ("data_inicio", "data_fim")
_NON_TIMESTAMP_SERIES_DTYPES: Mapping[str, str] = {
    column: dtype for column, dtype in SERIES_DTYPES.items() if column not in _TIMESTAMP_COLUMNS
}

# The value column each scalar-per-deck file stores through data.consolidate._load_scalars; cast
# to float64 here, consistent with read_series' dtype enforcement, so a malformed value column
# raises SchemaError naming the file and the column instead of a bare ValueError from float()
# further downstream (finding 9 of the epic-02 boundary review).
_SCALAR_VALUE_COLUMN: Mapping[str, str] = {"CUSTOS": "valor_esperado", "TEMPO": "tempo"}


def _read_parquet(path: Path) -> pd.DataFrame:
    """Read path as Parquet, raising DataFileError when it is missing or unreadable."""
    if not path.is_file():
        raise DataFileError(f"Arquivo de dados não encontrado: {path}")
    try:
        # to_pandas_kwargs={} is the documented default; passing it explicitly satisfies the
        # pandas-stubs overload for engine="pyarrow" (it has no default in that overload).
        return pd.read_parquet(path, engine="pyarrow", to_pandas_kwargs={})
    except (OSError, ArrowInvalid) as err:
        raise DataFileError(f"Falha ao ler o arquivo Parquet '{path}': {err}") from err


def _cast(frame: pd.DataFrame, dtypes: Mapping[str, str], *, source: Path) -> pd.DataFrame:
    """Cast frame's columns to dtypes one at a time, naming the failing column on error."""
    result = frame
    for column, dtype in dtypes.items():
        try:
            result = result.astype({column: dtype})
        except ValueError as err:
            raise SchemaError(
                f"Arquivo {source.name}: falha ao converter a coluna '{column}' para o tipo "
                f"'{dtype}': {err}"
            ) from err
    return result


def _cast_timestamps(frame: pd.DataFrame, *, source: Path) -> pd.DataFrame:
    """Normalise data_inicio and data_fim to nanosecond-precision UTC, without shifting them.

    pandas.to_datetime(..., utc=True) labels a naive column as UTC and converts an already
    tz-aware one; per decision 10 the source is always wall-clock time labeled UTC, so neither
    path shifts the value. The trailing astype only pins the storage precision to nanoseconds.
    """
    result = frame
    for column in _TIMESTAMP_COLUMNS:
        try:
            converted = pd.to_datetime(result[column], utc=True).astype("datetime64[ns, UTC]")
        except (ValueError, TypeError) as err:
            raise SchemaError(
                f"Arquivo {source.name}: falha ao converter a coluna '{column}' para o tipo "
                f"'datetime64[ns, UTC]': {err}"
            ) from err
        result = result.assign(**{column: converted})
    return result


def _assert_unique_keys(frame: pd.DataFrame, keys: Sequence[str], *, source: Path) -> None:
    """Raise SchemaError unless (keys) is unique, per decision 15 (one row per entity + stage)."""
    key_columns = list(keys)
    duplicate_mask = frame.duplicated(subset=key_columns, keep=False)
    if not duplicate_mask.any():
        return
    duplicated_keys = frame.loc[duplicate_mask, key_columns].drop_duplicates()
    first_key = duplicated_keys.iloc[0]
    key_text = ", ".join(f"{column}={first_key[column]}" for column in key_columns)
    raise SchemaError(
        f"Arquivo {source.name}: {len(duplicated_keys)} chave(s) duplicada(s) em "
        f"{key_columns}; primeira ocorrência: {key_text}"
    )


def read_series(path: Path, level: AggregationLevel) -> pd.DataFrame:
    """Read a long operation-series Parquet file and enforce the Appendix A.1 contract for level.

    Validates the declared columns, casts the nine shared columns to SERIES_DTYPES and the entity
    key columns of level to int64, asserts (entity keys, estagio) uniqueness, and returns the
    frame sorted by the entity keys then estagio with a reset index.
    """
    frame = _read_parquet(path)
    validate_series_columns(frame, level, source=path)

    frame = _cast_timestamps(frame, source=path)
    frame = _cast(frame, _NON_TIMESTAMP_SERIES_DTYPES, source=path)

    entity_keys = ENTITY_KEYS[level]
    if entity_keys:
        frame = _cast(frame, dict.fromkeys(entity_keys, "int64"), source=path)

    key_columns = (*entity_keys, "estagio")
    _assert_unique_keys(frame, key_columns, source=path)

    frame = frame.sort_values(list(key_columns)).reset_index(drop=True)

    entity_count = frame[list(entity_keys)].drop_duplicates().shape[0] if entity_keys else 1
    logger.debug(
        "read_series: %s -> %d linha(s), %d entidade(s), nível %s",
        path.name,
        len(frame),
        entity_count,
        level.value,
    )
    return frame


def read_registry(path: Path, name: str) -> pd.DataFrame:
    """Read a registry Parquet file, validating against REGISTRY_COLUMNS[name].

    Applies no dtype coercion and no sort, so the nullable Int64 SBM.codigo_submercado survives
    unchanged and a registry's row order, which carries no meaning, is never disturbed.
    """
    frame = _read_parquet(path)
    try:
        expected_columns = REGISTRY_COLUMNS[name]
    except KeyError as err:
        raise SchemaError(
            f"Registro desconhecido '{name}' ao ler {path.name}; nomes válidos: "
            f"{sorted(REGISTRY_COLUMNS)}"
        ) from err
    validate_columns(frame, expected_columns, source=path)
    logger.debug("read_registry: %s -> %d linha(s) (registro %s)", path.name, len(frame), name)
    return frame


def _read_scalar(path: Path, name: str) -> pd.DataFrame:
    """Read a scalar-per-deck Parquet file, validating against SCALAR_COLUMNS[name].

    Casts the file's value column to float64, raising SchemaError naming the column on failure,
    the same contract read_series enforces for its own numeric columns.
    """
    frame = _read_parquet(path)
    validate_columns(frame, SCALAR_COLUMNS[name], source=path)
    frame = _cast(frame, {_SCALAR_VALUE_COLUMN[name]: "float64"}, source=path)
    return frame


def read_costs(path: Path) -> pd.DataFrame:
    """Read CUSTOS.parquet, validating the four cost-parcel rows. Performs no aggregation."""
    frame = _read_scalar(path, "CUSTOS")
    logger.debug("read_costs: %s -> %d linha(s)", path.name, len(frame))
    return frame


def read_times(path: Path) -> pd.DataFrame:
    """Read TEMPO.parquet, validating its rows and keeping every PL row intact (no grouping)."""
    frame = _read_scalar(path, "TEMPO")
    logger.debug("read_times: %s -> %d linha(s)", path.name, len(frame))
    return frame
