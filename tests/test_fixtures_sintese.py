"""Tests for the tests.fixtures_sintese synthetic sintese/ directory generator."""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conftest import build_scenario_tree
from dessem_dashboard.charts.registry import enabled_specs
from dessem_dashboard.data.schemas import ENTITY_KEYS, AggregationLevel, series_columns
from fixtures_sintese import make_sintese_dir

_REGISTRY_FILE_NAMES = (
    "EST.parquet",
    "PAT.parquet",
    "UHE.parquet",
    "UTE.parquet",
    "SBM.parquet",
    "REE.parquet",
    "METADADOS_OPERACAO.parquet",
)


def _expected_file_names() -> set[str]:
    series_names = {f"{chart_spec.source_file}.parquet" for chart_spec in enabled_specs()}
    return series_names | set(_REGISTRY_FILE_NAMES)


def test_make_sintese_dir_default_arguments_writes_exactly_thirty_files(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "s"

    # Act
    result = make_sintese_dir(target, first_stage_start=datetime(2024, 3, 3, tzinfo=UTC))

    # Assert
    written = {path.name for path in result.iterdir()}
    assert len(written) == 30
    assert written == _expected_file_names()


def test_make_sintese_dir_returns_the_target_directory(tmp_path: Path) -> None:
    target = tmp_path / "s"
    result = make_sintese_dir(target, first_stage_start=datetime(2024, 3, 3, tzinfo=UTC))
    assert result == target


def test_ghid_uhe_matches_uhe_series_schema_and_row_count(tmp_path: Path) -> None:
    # Arrange
    hydro_codes = (1, 2, 3)
    n_stages = 6

    # Act
    target = make_sintese_dir(
        tmp_path / "s",
        first_stage_start=datetime(2024, 3, 3, tzinfo=UTC),
        n_stages=n_stages,
        hydro_codes=hydro_codes,
    )
    frame = pd.read_parquet(target / "GHID_UHE.parquet")

    # Assert
    assert set(frame.columns) == set(series_columns(AggregationLevel.UHE))
    assert frame["data_inicio"].dtype == "datetime64[ns, UTC]"
    assert len(frame) == len(hydro_codes) * n_stages


@pytest.mark.parametrize(
    ("file_name", "level", "codes_kwarg", "codes"),
    [
        ("GHID_SIN.parquet", AggregationLevel.SIN, None, None),
        ("CMO_SBM.parquet", AggregationLevel.SBM, "submarket_codes", (1, 2, 11)),
        ("INT_SBP.parquet", AggregationLevel.SBP, "pair_codes", ((1, 2), (2, 1))),
        ("GHID_UHE.parquet", AggregationLevel.UHE, "hydro_codes", (1, 2, 3)),
        ("GTER_UTE.parquet", AggregationLevel.UTE, "thermal_codes", (1, 2)),
    ],
)
def test_series_file_matches_its_level_schema_and_row_count(
    tmp_path: Path,
    file_name: str,
    level: AggregationLevel,
    codes_kwarg: str | None,
    codes: object,
) -> None:
    # Arrange
    n_stages = 6
    kwargs: dict[str, object] = {}
    if codes_kwarg is not None:
        kwargs[codes_kwarg] = codes
    entity_count = 1 if codes is None else len(codes)

    # Act
    target = make_sintese_dir(
        tmp_path / "s",
        first_stage_start=datetime(2024, 3, 3, tzinfo=UTC),
        n_stages=n_stages,
        **kwargs,
    )
    frame = pd.read_parquet(target / file_name)

    # Assert
    assert set(frame.columns) == set(series_columns(level))
    assert len(frame) == entity_count * n_stages
    assert frame["data_inicio"].dtype == "datetime64[ns, UTC]"
    assert frame["data_fim"].dtype == "datetime64[ns, UTC]"
    assert (frame["cenario"] == 1).all()
    assert (frame["patamar"] == 2).all()
    assert (frame["limite_inferior"] == -np.inf).all()
    assert (frame["limite_superior"] == np.inf).all()


def test_est_parquet_is_contiguous_with_half_hour_then_long_stages(tmp_path: Path) -> None:
    # Arrange
    target = make_sintese_dir(
        tmp_path / "s",
        first_stage_start=datetime(2024, 3, 3, tzinfo=UTC),
        n_stages=6,
        half_hour_stages=4,
        long_stage_hours=2.0,
    )

    # Act
    est = pd.read_parquet(target / "EST.parquet")

    # Assert
    stage_four = est.loc[est["estagio"] == 4].iloc[0]
    stage_five = est.loc[est["estagio"] == 5].iloc[0]
    assert stage_four["data_fim"] == stage_five["data_inicio"]
    half_hour_rows = est.loc[est["estagio"] <= 4]
    long_rows = est.loc[est["estagio"] > 4]
    half_hour_durations = half_hour_rows["data_fim"] - half_hour_rows["data_inicio"]
    long_durations = long_rows["data_fim"] - long_rows["data_inicio"]
    assert (half_hour_durations == pd.Timedelta(minutes=30)).all()
    assert (long_durations == pd.Timedelta(hours=2)).all()
    assert (est["data_inicio"].iloc[1:].to_numpy() == est["data_fim"].iloc[:-1].to_numpy()).all()


def test_varmf_and_varpf_uhe_are_restricted_to_reservoir_codes(tmp_path: Path) -> None:
    # Arrange
    reservoir_codes = (1, 2)
    hydro_codes = (1, 2, 3)

    # Act
    target = make_sintese_dir(
        tmp_path / "s",
        first_stage_start=datetime(2024, 3, 3, tzinfo=UTC),
        hydro_codes=hydro_codes,
        reservoir_codes=reservoir_codes,
    )
    varmf = pd.read_parquet(target / "VARMF_UHE.parquet")
    varpf = pd.read_parquet(target / "VARPF_UHE.parquet")
    ghid = pd.read_parquet(target / "GHID_UHE.parquet")

    # Assert
    assert set(varmf["codigo_usina"].unique()) == set(reservoir_codes)
    assert set(varpf["codigo_usina"].unique()) == set(reservoir_codes)
    assert set(ghid["codigo_usina"].unique()) == set(hydro_codes)


def test_varpf_uhe_values_stay_within_zero_to_hundred(tmp_path: Path) -> None:
    target = make_sintese_dir(tmp_path / "s", first_stage_start=datetime(2024, 3, 3, tzinfo=UTC))
    varpf = pd.read_parquet(target / "VARPF_UHE.parquet")
    assert varpf["valor"].min() >= 0.0
    assert varpf["valor"].max() <= 100.0


def test_sbm_parquet_default_codes_cover_both_fictitious_submarkets(tmp_path: Path) -> None:
    # Arrange: default submarket_codes includes both fictitious codes settings.json's
    # submarkets.fictitious_codes lists, so include_fictitious filtering (ticket-015) can be
    # exercised against both.
    target = make_sintese_dir(tmp_path / "s", first_stage_start=datetime(2024, 3, 3, tzinfo=UTC))

    # Act
    sbm = pd.read_parquet(target / "SBM.parquet")

    # Assert
    assert set(sbm["codigo_submercado"].to_numpy()) == {1, 2, 11, 99}


def test_sbm_parquet_uses_nullable_int64_dtype(tmp_path: Path) -> None:
    target = make_sintese_dir(tmp_path / "s", first_stage_start=datetime(2024, 3, 3, tzinfo=UTC))
    sbm = pd.read_parquet(target / "SBM.parquet")
    assert sbm["codigo_submercado"].dtype == "Int64"


def test_sbm_parquet_null_long_name_sits_on_code_ninety_nine_not_eleven(tmp_path: Path) -> None:
    # Arrange: the real file's NaN long name belongs to the fictitious code 99, not 11, which
    # has the real long name NOFICT1 (planning-context.md, 00-master-plan.md Appendix A.4).
    target = make_sintese_dir(tmp_path / "s", first_stage_start=datetime(2024, 3, 3, tzinfo=UTC))

    # Act
    sbm = pd.read_parquet(target / "SBM.parquet")

    # Assert
    code_99_row = sbm.loc[sbm["codigo_submercado"] == 99].iloc[0]
    assert pd.isna(code_99_row["nome_submercado"])
    code_11_row = sbm.loc[sbm["codigo_submercado"] == 11].iloc[0]
    assert code_11_row["nome_submercado"] == "NOFICT1"
    real_row = sbm.loc[sbm["codigo_submercado"] == 1].iloc[0]
    assert real_row["nome_submercado"] == "SUDESTE"


def test_custos_parquet_holds_the_four_parcela_rows(tmp_path: Path) -> None:
    target = make_sintese_dir(tmp_path / "s", first_stage_start=datetime(2024, 3, 3, tzinfo=UTC))
    custos = pd.read_parquet(target / "CUSTOS.parquet")
    assert len(custos) == 4
    assert set(custos["parcela"]) == {"PRESENTE", "FUTURO", "VIOLACOES", "PEQUENAS PENALIDADES"}


def test_tempo_parquet_holds_nine_rows_with_three_pl_rows(tmp_path: Path) -> None:
    target = make_sintese_dir(tmp_path / "s", first_stage_start=datetime(2024, 3, 3, tzinfo=UTC))
    tempo = pd.read_parquet(target / "TEMPO.parquet")
    assert len(tempo) == 9
    assert (tempo["etapa"] == "PL").sum() == 3
    assert set(tempo["etapa"]) == {
        "Leitura de Dados e Impressão",
        "MILP",
        "PL",
        "PL.Int.Fix",
        "PL.CalcCMO",
    }


def test_omit_known_file_excludes_it_from_the_written_set(tmp_path: Path) -> None:
    target = make_sintese_dir(
        tmp_path / "s",
        first_stage_start=datetime(2024, 3, 3, tzinfo=UTC),
        omit=("GTER_UTE.parquet",),
    )
    written = {path.name for path in target.iterdir()}
    assert len(written) == 29
    assert "GTER_UTE.parquet" not in written


def test_omit_unknown_file_raises_value_error_naming_it(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=re.escape("INEXISTENTE.parquet")):
        make_sintese_dir(
            tmp_path / "s",
            first_stage_start=datetime(2024, 3, 3, tzinfo=UTC),
            omit=("INEXISTENTE.parquet",),
        )


def test_same_seed_produces_byte_identical_valor_arrays_across_two_calls(tmp_path: Path) -> None:
    # Arrange
    first_stage_start = datetime(2024, 3, 3, tzinfo=UTC)

    # Act
    target_a = make_sintese_dir(tmp_path / "a", first_stage_start=first_stage_start, seed=42)
    target_b = make_sintese_dir(tmp_path / "b", first_stage_start=first_stage_start, seed=42)
    valor_a = pd.read_parquet(target_a / "GHID_UHE.parquet")["valor"].to_numpy()
    valor_b = pd.read_parquet(target_b / "GHID_UHE.parquet")["valor"].to_numpy()

    # Assert
    assert np.array_equal(valor_a, valor_b)


def test_different_seeds_produce_different_valor_arrays(tmp_path: Path) -> None:
    first_stage_start = datetime(2024, 3, 3, tzinfo=UTC)
    target_a = make_sintese_dir(tmp_path / "a", first_stage_start=first_stage_start, seed=42)
    target_b = make_sintese_dir(tmp_path / "b", first_stage_start=first_stage_start, seed=43)
    valor_a = pd.read_parquet(target_a / "GHID_UHE.parquet")["valor"].to_numpy()
    valor_b = pd.read_parquet(target_b / "GHID_UHE.parquet")["valor"].to_numpy()
    assert not np.array_equal(valor_a, valor_b)


def test_sintese_dir_fixture_returns_a_directory_with_thirty_files(sintese_dir: Path) -> None:
    written = {path.name for path in sintese_dir.iterdir()}
    assert len(written) == 30
    assert written == _expected_file_names()


def test_scenario_tree_fixture_has_two_scenarios_each_with_two_decks(
    scenario_tree: dict[str, Path],
) -> None:
    assert set(scenario_tree) == {"caso_a", "caso_b"}
    for scenario_dir in scenario_tree.values():
        deck_dirs = sorted(path for path in scenario_dir.iterdir() if path.is_dir())
        assert len(deck_dirs) == 2
        for deck_dir in deck_dirs:
            assert (deck_dir / "sintese").is_dir()
            assert deck_dir.name in {"deck_um", "deck_dois"}


def test_scenario_tree_fixture_decks_are_not_named_by_date(scenario_tree: dict[str, Path]) -> None:
    for scenario_dir in scenario_tree.values():
        deck_names = {path.name for path in scenario_dir.iterdir() if path.is_dir()}
        assert deck_names == {"deck_um", "deck_dois"}


def test_scenario_tree_fixture_chaining_window_is_contiguous_between_decks(
    scenario_tree: dict[str, Path],
) -> None:
    for scenario_dir in scenario_tree.values():
        first_deck_est = pd.read_parquet(scenario_dir / "deck_um" / "sintese" / "EST.parquet")
        second_deck_est = pd.read_parquet(scenario_dir / "deck_dois" / "sintese" / "EST.parquet")
        chaining_window_end = first_deck_est.loc[first_deck_est["estagio"] == 48].iloc[0][
            "data_fim"
        ]
        second_deck_start = second_deck_est.loc[second_deck_est["estagio"] == 1].iloc[0][
            "data_inicio"
        ]
        assert chaining_window_end == second_deck_start
        # The chaining window is a strict subset: the whole first deck extends further still.
        assert first_deck_est["estagio"].max() > 48


def test_scenario_tree_fixture_builds_in_under_five_seconds(tmp_path: Path) -> None:
    started = time.perf_counter()
    build_scenario_tree(tmp_path)
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0


def test_entity_keys_uhe_covers_the_three_registry_columns_used_by_series_files() -> None:
    assert ENTITY_KEYS[AggregationLevel.UHE] == ("codigo_usina", "codigo_ree", "codigo_submercado")
