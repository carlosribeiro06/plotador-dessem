"""Tests for dessem_dashboard.data.registries."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from dessem_dashboard.data.registries import (
    HydroPlant,
    Registries,
    Submarket,
    ThermalPlant,
    VariableMeta,
    load_registries,
    visible_submarket_codes,
)
from dessem_dashboard.data.schemas import FALLBACK_UNITS
from dessem_dashboard.errors import DataFileError, RegistryError
from fixtures_sintese import make_sintese_dir

# Defaults of tests.fixtures_sintese.make_sintese_dir, which the sintese_dir fixture uses as-is.
_HYDRO_COUNT = 3
_THERMAL_COUNT = 2
_SUBMARKET_COUNT = 4
_REE_COUNT = 3
_ENABLED_CHART_KEY_COUNT = 23

_REGISTRIES_LOGGER_NAME = "dessem_dashboard.data.registries"
_FIRST_STAGE_START = datetime(2024, 3, 3, tzinfo=UTC)
_UNKNOWN_CODE = 9999


def _rewrite_parquet(path: Path, transform: Callable[[pd.DataFrame], pd.DataFrame]) -> pd.DataFrame:
    """Read path, apply transform, write the result back to path, and return the written frame."""
    raw = pd.read_parquet(path, engine="pyarrow")
    written = transform(raw)
    written.to_parquet(path, index=False)
    return written


def _raw_metadados_operacao(sintese_dir: Path) -> pd.DataFrame:
    """Read METADADOS_OPERACAO.parquet without going through the reader, for expected values."""
    return pd.read_parquet(sintese_dir / "METADADOS_OPERACAO.parquet", engine="pyarrow")


def test_load_registries_happy_path_counts_and_spot_checks(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    assert len(registries.hydro) == _HYDRO_COUNT
    assert len(registries.thermal) == _THERMAL_COUNT
    assert len(registries.submarkets) == _SUBMARKET_COUNT
    assert len(registries.rees) == _REE_COUNT
    assert len(registries.variables) == _ENABLED_CHART_KEY_COUNT

    raw_uhe = pd.read_parquet(sintese_dir / "UHE.parquet", engine="pyarrow")
    expected_name = str(raw_uhe.loc[raw_uhe["codigo_usina"] == 1, "usina"].iloc[0])
    assert registries.hydro[1].name == expected_name
    assert registries.submarkets[1].short_name == "SE"
    assert isinstance(registries.rees[1], str)
    assert registries.rees[1] != ""


def test_load_registries_returns_frozen_dataclasses(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    assert isinstance(registries, Registries)
    assert isinstance(registries.hydro[1], HydroPlant)
    assert isinstance(registries.thermal[1], ThermalPlant)
    assert isinstance(registries.submarkets[1], Submarket)
    assert isinstance(next(iter(registries.variables.values())), VariableMeta)


def test_null_nome_submercado_on_code_99_falls_back_to_short_name(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    submarket_99 = registries.submarkets[99]
    assert submarket_99.long_name == submarket_99.short_name == "IV"
    assert submarket_99.fictitious is True


def test_code_11_keeps_its_real_long_name_despite_being_fictitious(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    submarket_11 = registries.submarkets[11]
    assert submarket_11.long_name == "NOFICT1"
    assert submarket_11.fictitious is True


@pytest.mark.parametrize("code", [11, 99])
def test_fictitious_flag_true_for_fictitious_codes(sintese_dir: Path, code: int) -> None:
    registries = load_registries(sintese_dir)

    assert registries.submarkets[code].fictitious is True


@pytest.mark.parametrize("code", [1, 2])
def test_fictitious_flag_false_for_real_codes(sintese_dir: Path, code: int) -> None:
    registries = load_registries(sintese_dir)

    assert registries.submarkets[code].fictitious is False


def test_null_codigo_submercado_row_is_dropped_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    sintese_dir = make_sintese_dir(tmp_path / "sintese", first_stage_start=_FIRST_STAGE_START)
    ghost_row = pd.DataFrame(
        {
            "codigo_submercado": pd.array([None], dtype="Int64"),
            "submercado": ["SEM_CODIGO"],
            "nome_submercado": ["SEM_CODIGO_LONGO"],
        }
    )
    _rewrite_parquet(
        sintese_dir / "SBM.parquet", lambda raw: pd.concat([raw, ghost_row], ignore_index=True)
    )
    caplog.set_level(logging.WARNING, logger=_REGISTRIES_LOGGER_NAME)

    registries = load_registries(sintese_dir)

    assert len(registries.submarkets) == _SUBMARKET_COUNT
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "SEM_CODIGO" in warnings[0].getMessage()
    assert "SBM.parquet" in warnings[0].getMessage()


def test_unit_for_returns_the_metadata_unit_when_present(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    assert registries.unit_for("GHID_SIN") == FALLBACK_UNITS["GHID_SIN"]


def test_unit_for_falls_back_when_the_metadata_row_is_absent(sintese_dir: Path) -> None:
    _rewrite_parquet(
        sintese_dir / "METADADOS_OPERACAO.parquet", lambda raw: raw[raw["chave"] != "QTUR_UHE"]
    )
    registries = load_registries(sintese_dir)

    assert registries.unit_for("QTUR_UHE") == "m3/s"


def test_unit_for_raises_registry_error_on_an_unknown_key(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    with pytest.raises(RegistryError, match=re.escape("NAO_EXISTE")):
        registries.unit_for("NAO_EXISTE")


def test_unit_for_falls_back_when_the_metadata_unit_is_null(sintese_dir: Path) -> None:
    _rewrite_parquet(
        sintese_dir / "METADADOS_OPERACAO.parquet",
        lambda raw: raw.assign(
            unidade=raw["unidade"].mask(raw["chave"] == "GHID_SIN", None),
        ),
    )
    registries = load_registries(sintese_dir)

    assert registries.unit_for("GHID_SIN") == FALLBACK_UNITS["GHID_SIN"]


def test_load_registries_raises_registry_error_when_a_variable_has_no_unit_anywhere(
    sintese_dir: Path,
) -> None:
    ghost_row = pd.DataFrame(
        {
            "chave": ["CHAVE_FANTASMA"],
            "nome_curto_variavel": [None],
            "nome_longo_variavel": [None],
            "nome_curto_agregacao": ["FANTASMA"],
            "nome_longo_agregacao": ["FANTASMA"],
            "unidade": [None],
            "calculado": [False],
            "limitado": [False],
        }
    )
    _rewrite_parquet(
        sintese_dir / "METADADOS_OPERACAO.parquet",
        lambda raw: pd.concat([raw, ghost_row], ignore_index=True),
    )

    with pytest.raises(RegistryError, match=re.escape("CHAVE_FANTASMA")):
        load_registries(sintese_dir)


def test_title_for_returns_the_long_name_when_present(sintese_dir: Path) -> None:
    raw = _raw_metadados_operacao(sintese_dir)
    expected_title = str(raw.loc[raw["chave"] == "GHID_SIN", "nome_longo_variavel"].iloc[0])
    registries = load_registries(sintese_dir)

    assert registries.title_for("GHID_SIN") == expected_title


def test_title_for_returns_none_when_the_metadata_title_is_null(sintese_dir: Path) -> None:
    _rewrite_parquet(
        sintese_dir / "METADADOS_OPERACAO.parquet",
        lambda raw: raw.assign(
            nome_longo_variavel=raw["nome_longo_variavel"].mask(raw["chave"] == "GHID_SIN", None),
        ),
    )
    registries = load_registries(sintese_dir)

    assert registries.title_for("GHID_SIN") is None


def test_title_for_returns_none_when_the_key_has_no_metadata_row(sintese_dir: Path) -> None:
    _rewrite_parquet(
        sintese_dir / "METADADOS_OPERACAO.parquet", lambda raw: raw[raw["chave"] != "QTUR_UHE"]
    )
    registries = load_registries(sintese_dir)

    assert registries.title_for("QTUR_UHE") is None


def test_hydro_name_returns_the_registry_name_for_a_known_code(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    assert registries.hydro_name(1) == registries.hydro[1].name


def test_hydro_name_falls_back_for_an_unknown_code(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    assert registries.hydro_name(_UNKNOWN_CODE) == f"Usina {_UNKNOWN_CODE}"


def test_thermal_name_returns_the_registry_name_for_a_known_code(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    assert registries.thermal_name(1) == registries.thermal[1].name


def test_thermal_name_falls_back_for_an_unknown_code(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    assert registries.thermal_name(_UNKNOWN_CODE) == f"Usina {_UNKNOWN_CODE}"


def test_submarket_label_for_a_known_code(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    assert registries.submarket_label(1) == "SE (SUDESTE)"


def test_submarket_label_for_an_unknown_code(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    unknown_code = 7
    assert registries.submarket_label(unknown_code) == f"Submercado {unknown_code}"


def test_visible_submarket_codes_excludes_fictitious_by_default(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    assert visible_submarket_codes(registries, include_fictitious=False) == (1, 2)


def test_visible_submarket_codes_includes_fictitious_when_requested(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    codes = visible_submarket_codes(registries, include_fictitious=True)
    assert codes == (1, 2, 11, 99)
    assert 11 in codes


def test_load_registries_missing_uhe_file_raises_data_file_error(tmp_path: Path) -> None:
    sintese_dir = make_sintese_dir(
        tmp_path / "sintese", first_stage_start=_FIRST_STAGE_START, omit=["UHE.parquet"]
    )

    with pytest.raises(DataFileError, match=re.escape("UHE.parquet")):
        load_registries(sintese_dir)


def test_hydro_name_9999_matches_the_acceptance_criterion(sintese_dir: Path) -> None:
    registries = load_registries(sintese_dir)

    assert registries.hydro_name(9999) == "Usina 9999"


@pytest.mark.parametrize("field", ["hydro", "thermal", "submarkets", "rees", "variables"])
def test_registries_mappings_reject_mutation(sintese_dir: Path, field: str) -> None:
    registries = load_registries(sintese_dir)
    mapping = getattr(registries, field)
    key = next(iter(mapping))

    with pytest.raises(TypeError):
        mapping[key] = mapping[key]


def test_load_registries_logs_one_info_line_with_the_five_counts(
    sintese_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=_REGISTRIES_LOGGER_NAME)

    registries = load_registries(sintese_dir)

    records = [
        record
        for record in caplog.records
        if record.name == _REGISTRIES_LOGGER_NAME and record.levelno == logging.INFO
    ]
    assert len(records) == 1
    message = records[0].getMessage()
    assert str(len(registries.hydro)) in message
    assert str(len(registries.thermal)) in message
    assert str(len(registries.submarkets)) in message
    assert str(len(registries.rees)) in message
    assert str(len(registries.variables)) in message
