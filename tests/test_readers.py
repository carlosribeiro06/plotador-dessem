"""Tests for dessem_dashboard.data.readers."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from pyarrow.lib import ArrowInvalid

from dessem_dashboard.data.readers import read_costs, read_registry, read_series, read_times
from dessem_dashboard.data.schemas import ENTITY_KEYS, REGISTRY_COLUMNS, AggregationLevel
from dessem_dashboard.errors import DataFileError, SchemaError
from fixtures_sintese import make_sintese_dir

# Defaults of tests.fixtures_sintese.make_sintese_dir, which the sintese_dir fixture uses as-is.
_N_STAGES = 6
_SUBMARKET_COUNT = 4
_HYDRO_COUNT = 3
_RESERVOIR_COUNT = 2
_THERMAL_COUNT = 2
_PAIR_COUNT = 2

_READER_LOGGER_NAME = "dessem_dashboard.data.readers"


def _assert_sorted_and_index_reset(frame: pd.DataFrame, key_columns: Sequence[str]) -> None:
    """Assert frame is sorted by key_columns and carries a fresh 0..n-1 index."""
    columns = list(key_columns)
    expected = frame[columns].sort_values(columns).reset_index(drop=True)
    pd.testing.assert_frame_equal(frame[columns].reset_index(drop=True), expected)
    assert list(frame.index) == list(range(len(frame)))


def _rewrite_parquet(path: Path, transform: Callable[[pd.DataFrame], pd.DataFrame]) -> pd.DataFrame:
    """Read path, apply transform, write the result back to path, and return the written frame."""
    raw = pd.read_parquet(path, engine="pyarrow")
    written = transform(raw)
    written.to_parquet(path, index=False)
    return written


def test_read_series_sin_level_returns_one_row_per_stage(sintese_dir: Path) -> None:
    frame = read_series(sintese_dir / "GHID_SIN.parquet", AggregationLevel.SIN)

    assert len(frame) == _N_STAGES
    assert frame["data_inicio"].dtype == "datetime64[ns, UTC]"
    assert frame["estagio"].tolist() == list(range(1, _N_STAGES + 1))
    _assert_sorted_and_index_reset(frame, ["estagio"])


def test_read_series_sbm_level_matches_acceptance_criteria(sintese_dir: Path) -> None:
    frame = read_series(sintese_dir / "GHID_SBM.parquet", AggregationLevel.SBM)

    assert frame["codigo_submercado"].dtype == "int64"
    assert frame["data_inicio"].dtype == "datetime64[ns, UTC]"
    assert len(frame) == _SUBMARKET_COUNT * _N_STAGES
    _assert_sorted_and_index_reset(frame, ["codigo_submercado", "estagio"])


def test_read_series_sbp_level_returns_one_row_per_pair_and_stage(sintese_dir: Path) -> None:
    frame = read_series(sintese_dir / "INT_SBP.parquet", AggregationLevel.SBP)

    assert len(frame) == _PAIR_COUNT * _N_STAGES
    assert frame["codigo_submercado_de"].dtype == "int64"
    assert frame["codigo_submercado_para"].dtype == "int64"
    _assert_sorted_and_index_reset(
        frame, ["codigo_submercado_de", "codigo_submercado_para", "estagio"]
    )


def test_read_series_uhe_level_returns_one_row_per_plant_and_stage(sintese_dir: Path) -> None:
    frame = read_series(sintese_dir / "GHID_UHE.parquet", AggregationLevel.UHE)

    assert len(frame) == _HYDRO_COUNT * _N_STAGES
    _assert_sorted_and_index_reset(frame, [*ENTITY_KEYS[AggregationLevel.UHE], "estagio"])


def test_read_series_ute_level_returns_one_row_per_plant_and_stage(sintese_dir: Path) -> None:
    frame = read_series(sintese_dir / "GTER_UTE.parquet", AggregationLevel.UTE)

    assert len(frame) == _THERMAL_COUNT * _N_STAGES
    _assert_sorted_and_index_reset(frame, [*ENTITY_KEYS[AggregationLevel.UTE], "estagio"])


def test_read_series_reservoir_only_variable_covers_only_reservoir_codes(
    sintese_dir: Path,
) -> None:
    frame = read_series(sintese_dir / "VARMF_UHE.parquet", AggregationLevel.UHE)

    assert len(frame) == _RESERVOIR_COUNT * _N_STAGES


def test_read_series_preserves_a_known_timestamp_without_shift(tmp_path: Path) -> None:
    first_stage_start = datetime(2024, 3, 3, 13, 45, tzinfo=UTC)
    sintese = make_sintese_dir(tmp_path / "sintese", first_stage_start=first_stage_start)

    frame = read_series(sintese / "GHID_SIN.parquet", AggregationLevel.SIN)

    first_row = frame.loc[frame["estagio"] == 1].iloc[0]
    assert first_row["data_inicio"] == pd.Timestamp(first_stage_start)


def test_read_series_labels_a_naive_timestamp_as_utc_without_shifting_it(tmp_path: Path) -> None:
    sintese = make_sintese_dir(
        tmp_path / "sintese", first_stage_start=datetime(2024, 3, 3, tzinfo=UTC)
    )
    path = sintese / "GHID_SIN.parquet"
    naive_start = _rewrite_parquet(
        path,
        lambda raw: raw.assign(
            data_inicio=raw["data_inicio"].dt.tz_localize(None),
            data_fim=raw["data_fim"].dt.tz_localize(None),
        ),
    )["data_inicio"].iloc[0]

    frame = read_series(path, AggregationLevel.SIN)

    assert frame["data_inicio"].dtype == "datetime64[ns, UTC]"
    first_row = frame.loc[frame["estagio"] == 1].iloc[0]
    assert first_row["data_inicio"] == pd.Timestamp(naive_start).tz_localize("UTC")


def test_read_series_missing_valor_column_raises_schema_error_naming_file_and_column(
    sintese_dir: Path,
) -> None:
    path = sintese_dir / "GHID_SBM.parquet"
    _rewrite_parquet(path, lambda raw: raw.drop(columns=["valor"]))

    with pytest.raises(SchemaError) as exc_info:
        read_series(path, AggregationLevel.SBM)
    message = str(exc_info.value)
    assert "valor" in message
    assert "GHID_SBM.parquet" in message


def test_read_series_extra_column_raises_schema_error_naming_column(sintese_dir: Path) -> None:
    path = sintese_dir / "GHID_SIN.parquet"
    _rewrite_parquet(path, lambda raw: raw.assign(coluna_extra=1))

    with pytest.raises(SchemaError, match=re.escape("coluna_extra")):
        read_series(path, AggregationLevel.SIN)


def test_read_series_duplicated_key_raises_schema_error_naming_file_count_and_key(
    sintese_dir: Path,
) -> None:
    path = sintese_dir / "GHID_SBM.parquet"
    raw = pd.read_parquet(path, engine="pyarrow")
    duplicated_row = raw.iloc[[0]]
    expected_submercado = int(duplicated_row["codigo_submercado"].iloc[0])
    expected_estagio = int(duplicated_row["estagio"].iloc[0])
    pd.concat([raw, duplicated_row], ignore_index=True).to_parquet(path, index=False)

    with pytest.raises(SchemaError) as exc_info:
        read_series(path, AggregationLevel.SBM)
    message = str(exc_info.value)
    assert "duplicad" in message
    assert "GHID_SBM.parquet" in message
    assert "1 chave" in message
    assert f"codigo_submercado={expected_submercado}" in message
    assert f"estagio={expected_estagio}" in message


def test_read_series_missing_file_raises_data_file_error_naming_path(tmp_path: Path) -> None:
    path = tmp_path / "ausente.parquet"

    with pytest.raises(DataFileError, match=re.escape("ausente.parquet")):
        read_series(path, AggregationLevel.SIN)


def test_read_series_malformed_file_raises_data_file_error_chained_from_arrow_error(
    tmp_path: Path,
) -> None:
    path = tmp_path / "malformado.parquet"
    path.write_bytes(b"conteudo que nao e um arquivo parquet valido")

    with pytest.raises(DataFileError) as exc_info:
        read_series(path, AggregationLevel.SIN)
    assert isinstance(exc_info.value.__cause__, ArrowInvalid)


def test_read_series_casts_entity_key_column_to_int64_even_from_a_narrower_source_dtype(
    sintese_dir: Path,
) -> None:
    path = sintese_dir / "GHID_SBM.parquet"
    _rewrite_parquet(
        path, lambda raw: raw.assign(codigo_submercado=raw["codigo_submercado"].astype("int32"))
    )

    frame = read_series(path, AggregationLevel.SBM)

    assert frame["codigo_submercado"].dtype == "int64"


def test_read_series_non_castable_column_raises_schema_error_naming_column(
    sintese_dir: Path,
) -> None:
    path = sintese_dir / "GHID_SIN.parquet"

    def _corrupt_estagio(raw: pd.DataFrame) -> pd.DataFrame:
        corrupted = raw.assign(estagio=raw["estagio"].astype("str"))
        corrupted.loc[corrupted.index[0], "estagio"] = "nao_numerico"
        return corrupted

    _rewrite_parquet(path, _corrupt_estagio)

    with pytest.raises(SchemaError) as exc_info:
        read_series(path, AggregationLevel.SIN)
    message = str(exc_info.value)
    assert "estagio" in message
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_read_series_unparsable_timestamp_raises_schema_error_naming_column(
    sintese_dir: Path,
) -> None:
    path = sintese_dir / "GHID_SIN.parquet"

    def _corrupt_data_inicio(raw: pd.DataFrame) -> pd.DataFrame:
        corrupted = raw.assign(data_inicio=raw["data_inicio"].astype("str"))
        corrupted.loc[corrupted.index[0], "data_inicio"] = "nao_e_uma_data"
        return corrupted

    _rewrite_parquet(path, _corrupt_data_inicio)

    with pytest.raises(SchemaError) as exc_info:
        read_series(path, AggregationLevel.SIN)
    message = str(exc_info.value)
    assert "data_inicio" in message
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_read_series_logs_one_debug_line_with_row_and_entity_counts(
    sintese_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    frame = read_series(sintese_dir / "GHID_SBM.parquet", AggregationLevel.SBM)

    records = [record for record in caplog.records if record.name == _READER_LOGGER_NAME]
    assert len(records) == 1
    message = records[0].getMessage()
    assert str(len(frame)) in message
    assert str(_SUBMARKET_COUNT) in message


@pytest.mark.parametrize("name", ["UHE", "UTE", "SBM", "REE", "EST", "PAT", "METADADOS_OPERACAO"])
def test_read_registry_validates_and_returns_every_known_registry(
    sintese_dir: Path, name: str
) -> None:
    frame = read_registry(sintese_dir / f"{name}.parquet", name)

    assert not frame.empty
    assert set(frame.columns) == set(REGISTRY_COLUMNS[name])


def test_read_registry_sbm_preserves_the_nullable_int64_dtype(sintese_dir: Path) -> None:
    frame = read_registry(sintese_dir / "SBM.parquet", "SBM")

    assert frame["codigo_submercado"].dtype == "Int64"
    assert frame.loc[frame["codigo_submercado"] == 99, "nome_submercado"].isna().all()


def test_read_registry_does_not_sort_rows(sintese_dir: Path) -> None:
    raw = pd.read_parquet(sintese_dir / "UHE.parquet", engine="pyarrow")

    frame = read_registry(sintese_dir / "UHE.parquet", "UHE")

    pd.testing.assert_frame_equal(frame.reset_index(drop=True), raw.reset_index(drop=True))


def test_read_registry_unknown_name_raises_schema_error(sintese_dir: Path) -> None:
    with pytest.raises(SchemaError, match=re.escape("BOGUS")):
        read_registry(sintese_dir / "SBM.parquet", "BOGUS")


def test_read_registry_missing_file_raises_data_file_error_naming_path(tmp_path: Path) -> None:
    path = tmp_path / "ausente.parquet"

    with pytest.raises(DataFileError, match=re.escape("ausente.parquet")):
        read_registry(path, "SBM")


def test_read_registry_malformed_file_raises_data_file_error_chained_from_arrow_error(
    tmp_path: Path,
) -> None:
    path = tmp_path / "malformado.parquet"
    path.write_bytes(b"conteudo que nao e um arquivo parquet valido")

    with pytest.raises(DataFileError) as exc_info:
        read_registry(path, "SBM")
    assert isinstance(exc_info.value.__cause__, ArrowInvalid)


def test_read_registry_logs_one_debug_line_with_row_count(
    sintese_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    frame = read_registry(sintese_dir / "UHE.parquet", "UHE")

    records = [record for record in caplog.records if record.name == _READER_LOGGER_NAME]
    assert len(records) == 1
    assert str(len(frame)) in records[0].getMessage()


def test_read_costs_returns_the_four_parcela_rows(sintese_dir: Path) -> None:
    frame = read_costs(sintese_dir / "CUSTOS.parquet")

    assert len(frame) == 4
    assert set(frame["parcela"]) == {
        "PRESENTE",
        "FUTURO",
        "VIOLACOES",
        "PEQUENAS PENALIDADES",
    }


def test_read_costs_missing_column_raises_schema_error_naming_column(sintese_dir: Path) -> None:
    path = sintese_dir / "CUSTOS.parquet"
    _rewrite_parquet(path, lambda raw: raw.drop(columns=["valor_esperado"]))

    with pytest.raises(SchemaError, match=re.escape("valor_esperado")):
        read_costs(path)


def test_read_costs_missing_file_raises_data_file_error_naming_path(tmp_path: Path) -> None:
    path = tmp_path / "ausente.parquet"

    with pytest.raises(DataFileError, match=re.escape("ausente.parquet")):
        read_costs(path)


def test_read_costs_logs_one_debug_line_with_row_count(
    sintese_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    frame = read_costs(sintese_dir / "CUSTOS.parquet")

    records = [record for record in caplog.records if record.name == _READER_LOGGER_NAME]
    assert len(records) == 1
    assert str(len(frame)) in records[0].getMessage()


def test_read_times_returns_nine_rows_with_three_pl_rows_preserved(sintese_dir: Path) -> None:
    frame = read_times(sintese_dir / "TEMPO.parquet")

    assert len(frame) == 9
    assert (frame["etapa"] == "PL").sum() == 3


def test_read_times_missing_column_raises_schema_error_naming_column(sintese_dir: Path) -> None:
    path = sintese_dir / "TEMPO.parquet"
    _rewrite_parquet(path, lambda raw: raw.drop(columns=["tempo"]))

    with pytest.raises(SchemaError, match=re.escape("tempo")):
        read_times(path)


def test_read_times_missing_file_raises_data_file_error_naming_path(tmp_path: Path) -> None:
    path = tmp_path / "ausente.parquet"

    with pytest.raises(DataFileError, match=re.escape("ausente.parquet")):
        read_times(path)


def test_read_times_logs_one_debug_line_with_row_count(
    sintese_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    frame = read_times(sintese_dir / "TEMPO.parquet")

    records = [record for record in caplog.records if record.name == _READER_LOGGER_NAME]
    assert len(records) == 1
    assert str(len(frame)) in records[0].getMessage()
