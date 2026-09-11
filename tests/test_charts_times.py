"""End-to-end tests for the time bar chart (ticket-031): scalars.aggregate_times directly, the
TEMPO payload it produces through the real repository settings.json, and the EXECUCAO document
section.

Suggested Approach step 8 asks for three non-vacuity mutations proving criterion 1's division and
criterion 2's warning and strict-inequality assertions can fail. They live in the "non-vacuity
proofs" section below, each restoring the mutation immediately after observing the failure.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from dashboard_document import opening_tag, section_heading, sections_by_chart_key
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import build_html
from dessem_dashboard.dashboard.payload import build_payload
from dessem_dashboard.dashboard.scalars import ScalarsByName, aggregate_times
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.data.schemas import FALLBACK_UNITS
from dessem_dashboard.errors import ConfigError
from dessem_dashboard.models.store import DashboardData

_SCALARS_LOGGER_NAME = "dessem_dashboard.dashboard.scalars"

_REPO_SETTINGS = Path(__file__).resolve().parent.parent / "settings.json"

_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# The shipped settings.json's own time.stage_groups, repeated here as a literal so the tests
# that mutate it (dropping Leitura, naming a non-existent etapa) can be written as small diffs
# against something readable, per tests/test_charts_costs.py's own convention for costs.
_DEFAULT_STAGE_GROUPS: dict[str, list[str]] = {
    "MILP": ["MILP"],
    "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"],
    "Leitura": ["Leitura de Dados e Impressão"],
}

# A hand-built five-etapa, two-scenario, two-deck raw mapping, every cell distinct so a value
# stored under the wrong etapa, scenario or deck is detectable. Mirrors
# tests/test_charts_costs.py's own _RAW_FOUR_PARCELS in spirit: pure data in, pure data out.
_RAW_FIVE_ETAPAS: ScalarsByName = {
    "MILP": {
        "caso_a": {"03/03/2024": 100.0, "04/03/2024": 110.0},
        "caso_b": {"03/03/2024": 120.0, "04/03/2024": 130.0},
    },
    "PL": {
        "caso_a": {"03/03/2024": 200.0, "04/03/2024": 210.0},
        "caso_b": {"03/03/2024": 220.0, "04/03/2024": 230.0},
    },
    "PL.Int.Fix": {
        "caso_a": {"03/03/2024": 300.0, "04/03/2024": 310.0},
        "caso_b": {"03/03/2024": 320.0, "04/03/2024": 330.0},
    },
    "PL.CalcCMO": {
        "caso_a": {"03/03/2024": 400.0, "04/03/2024": 410.0},
        "caso_b": {"03/03/2024": 420.0, "04/03/2024": 430.0},
    },
    "Leitura de Dados e Impressão": {
        "caso_a": {"03/03/2024": 500.0, "04/03/2024": 510.0},
        "caso_b": {"03/03/2024": 520.0, "04/03/2024": 530.0},
    },
}


def _raw_group_seconds(
    raw: ScalarsByName, members: Sequence[str], scenario: str, deck_key: str
) -> float:
    """Sum members' raw (undivided) seconds at (scenario, deck_key), for the division proof."""
    total = 0.0
    for member in members:
        value = raw[member][scenario][deck_key]
        assert value is not None
        total += value
    return total


# --- the module docstring above claims _DEFAULT_STAGE_GROUPS is "the shipped settings.json's ---
# --- own time.stage_groups": this proves it, instead of merely asserting the four group names --


def test_default_stage_groups_literal_matches_the_repository_settings_json() -> None:
    """_DEFAULT_STAGE_GROUPS must equal, member for member, settings.json's own
    time.stage_groups: dropping an etapa from either side without updating the other -- for
    example settings.json losing "PL.CalcCMO" while this literal still lists it -- would
    otherwise pass every other test in this module and degrade the shipped Tempo Computacional
    chart's TOTAL by one etapa, signalled by nothing louder than a single logger.warning."""
    settings = load_settings(_REPO_SETTINGS)
    assert settings.time.stage_groups == _DEFAULT_STAGE_GROUPS


# --- settings/data/document/payload builders, following tests/test_charts_costs.py's pattern --


def _settings_dict(*, disabled: Sequence[str] = ()) -> dict[str, Any]:
    """Build a settings.json-shaped dict matching the repository's own values, with a knob.

    time.stage_groups stays at the repository default: every test that exercises a different
    stage_groups mapping calls aggregate_times directly over _RAW_FIVE_ETAPAS instead, which
    needs no settings.json at all.
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
        "discovery": {"sintese_dirname": "sintese"},
        "chaining": {"stages_per_deck": 48},
        "costs": {"total_parcels": ["PRESENTE", "FUTURO"]},
        "time": {"stage_groups": _DEFAULT_STAGE_GROUPS, "unit_divisor": 60.0},
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
        "charts": {"disabled": list(disabled)},
    }


def _build_settings(tmp_path: Path, *, disabled: Sequence[str] = ()) -> Settings:
    """Write settings.json under tmp_path and load it, exercising the real config path."""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(_settings_dict(disabled=disabled)), encoding="utf-8")
    return load_settings(target)


def _build_data(paths: Sequence[Path], *, settings: Settings, reference: str) -> DashboardData:
    """Discover scenarios at paths and consolidate them into one DashboardData."""
    scenarios = discover_scenarios(list(paths))
    return build_dashboard_data(scenarios, settings=settings, reference=reference)


def _build_document(paths: Sequence[Path], tmp_path: Path, *, reference: str) -> str:
    settings = _build_settings(tmp_path)
    data = _build_data(paths, settings=settings, reference=reference)
    return build_html(data, settings=settings)


def _build_payload_dict(
    paths: Sequence[Path], *, settings: Settings, reference: str
) -> dict[str, object]:
    data = _build_data(paths, settings=settings, reference=reference)
    return build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})


# --- shared checkers, reused by the non-vacuity proofs below -----------------------------------


def _check_default_stage_groups_shape_and_division_proof(result: ScalarsByName) -> None:
    """Acceptance criterion 1, factored out so the non-vacuity proof below can call it against
    a deliberately mutated (unit_divisor=1.0) copy of the real result."""
    assert list(result) == ["MILP", "PL", "Leitura", "TOTAL"]
    for group_name, members in (
        ("MILP", ["MILP"]),
        ("PL", ["PL", "PL.Int.Fix", "PL.CalcCMO"]),
        ("Leitura", ["Leitura de Dados e Impressão"]),
    ):
        for scenario, by_deck in result[group_name].items():
            for deck_key, value in by_deck.items():
                raw_seconds = _raw_group_seconds(_RAW_FIVE_ETAPAS, members, scenario, deck_key)
                assert value == round(raw_seconds / 60.0, 2)
                # The division is proven, not assumed: the emitted value never equals the raw
                # (undivided) seconds figure of its own group.
                assert value != raw_seconds

    for scenario, by_deck in result["TOTAL"].items():
        for deck_key, total in by_deck.items():
            components = sum(
                result[group_name][scenario][deck_key] for group_name in ("MILP", "PL", "Leitura")
            )
            assert total == pytest.approx(components, abs=0.01)


def _check_total_strictly_below_every_row_sum(result: ScalarsByName) -> None:
    """Acceptance criterion 2's strict inequality, factored out so the non-vacuity proof below
    can call it in isolation against a TOTAL deliberately redefined as the sum of every row."""
    for scenario, by_deck in result["TOTAL"].items():
        for deck_key, total in by_deck.items():
            all_five_seconds = _raw_group_seconds(
                _RAW_FIVE_ETAPAS,
                ["MILP", "PL", "PL.Int.Fix", "PL.CalcCMO", "Leitura de Dados e Impressão"],
                scenario,
                deck_key,
            )
            assert total < round(all_five_seconds / 60.0, 2)


def _check_reduced_stage_groups_total_and_warning(
    result: ScalarsByName, caplog: pytest.LogCaptureFixture
) -> None:
    """Acceptance criterion 2, factored out so the non-vacuity proof below can call it against
    a deliberately widened stage_groups (Leitura restored)."""
    assert list(result) == ["MILP", "PL", "TOTAL"]
    for scenario, by_deck in result["TOTAL"].items():
        for deck_key, total in by_deck.items():
            expected = result["MILP"][scenario][deck_key] + result["PL"][scenario][deck_key]
            assert total == pytest.approx(expected, abs=0.01)
    _check_total_strictly_below_every_row_sum(result)

    matching = [
        record
        for record in caplog.records
        if record.name == _SCALARS_LOGGER_NAME
        and record.args == ("Leitura de Dados e Impressão", "time.stage_groups")
    ]
    assert len(matching) == 1


# --- acceptance criterion 1: shipped default, division proven per group and TOTAL ---------------


def test_aggregate_times_default_stage_groups_shape_and_division_proof() -> None:
    result = aggregate_times(
        _RAW_FIVE_ETAPAS, stage_groups=_DEFAULT_STAGE_GROUPS, unit_divisor=60.0, decimals=2
    )
    _check_default_stage_groups_shape_and_division_proof(result)


# --- acceptance criterion 2: Leitura dropped -- TOTAL is the configured groups, not every row ---


def test_aggregate_times_reduced_stage_groups_total_is_partial_and_warns_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_SCALARS_LOGGER_NAME)
    reduced = {"MILP": ["MILP"], "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"]}

    result = aggregate_times(_RAW_FIVE_ETAPAS, stage_groups=reduced, unit_divisor=60.0, decimals=2)

    _check_reduced_stage_groups_total_and_warning(result, caplog)


# --- acceptance criterion 3: an empty group and TOTAL-as-group-name -----------------------------


def test_aggregate_times_empty_group_omitted_no_exception_one_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_SCALARS_LOGGER_NAME)
    ghost = {"MILP": ["MILP"], "FANTASMA": ["INEXISTENTE"]}

    result = aggregate_times(_RAW_FIVE_ETAPAS, stage_groups=ghost, unit_divisor=60.0, decimals=2)

    assert list(result) == ["MILP", "TOTAL"]
    for scenario, by_deck in result["TOTAL"].items():
        for deck_key, total in by_deck.items():
            assert total == result["MILP"][scenario][deck_key]

    matching = [
        record
        for record in caplog.records
        if record.name == _SCALARS_LOGGER_NAME and record.args == ("FANTASMA", "time.stage_groups")
    ]
    assert len(matching) == 1


def test_aggregate_times_total_named_as_a_group_raises_config_error() -> None:
    with pytest.raises(ConfigError, match=re.escape("time.stage_groups")):
        aggregate_times(
            _RAW_FIVE_ETAPAS,
            stage_groups={"MILP": ["MILP"], "TOTAL": ["PL"]},
            unit_divisor=60.0,
            decimals=2,
        )


# --- acceptance criterion 4: the fixture payload, built through the real settings.json ----------


def test_payload_tempo_scalars_has_four_groups_via_the_repository_settings_json(
    scenario_tree: dict[str, Path],
) -> None:
    settings = load_settings(_REPO_SETTINGS)
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    tempo = payload["charts"]["TEMPO"]  # type: ignore[index]

    assert set(tempo["scalars"]) == {"MILP", "PL", "Leitura", "TOTAL"}  # type: ignore[index]
    for by_scenario in tempo["scalars"].values():  # type: ignore[union-attr]
        assert set(by_scenario) == {"caso_a", "caso_b"}
        for by_deck in by_scenario.values():
            assert set(by_deck) == {"03/03/2024", "04/03/2024"}
    assert tempo["unit"] == "min"  # type: ignore[index]
    assert tempo["entities"] == []  # type: ignore[index]

    # This ticket must not have disturbed the other scalar chart ticket-030 produced.
    assert set(payload["charts"]["CUSTOS"]["scalars"]) == {  # type: ignore[index]
        "PRESENTE",
        "FUTURO",
        "TOTAL",
    }


def test_payload_tempo_milp_recomputed_from_the_parquet_file_with_pandas(
    scenario_tree: dict[str, Path],
) -> None:
    """Proves the MILP value reached the payload from TEMPO.parquet rather than from a
    coincidence of the aggregation, without restating a specific figure anywhere else."""
    settings = load_settings(_REPO_SETTINGS)
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    raw = pd.read_parquet(
        scenario_tree["caso_a"] / "deck_um" / "sintese" / "TEMPO.parquet", engine="pyarrow"
    )
    expected_milp = round(float(raw.loc[raw["etapa"] == "MILP", "tempo"].sum()) / 60.0, 2)

    assert payload["charts"]["TEMPO"]["scalars"]["MILP"]["caso_a"]["03/03/2024"] == (  # type: ignore[index]
        expected_milp
    )


# --- acceptance criterion 5: the EXECUCAO group's TEMPO document section -----------------------


def test_document_tempo_section_is_a_hidden_scalar_chart_with_no_selector(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    section = sections_by_chart_key(document)["TEMPO"]
    opening = opening_tag(section)

    assert 'data-group="EXECUCAO"' in opening
    assert 'data-kind="SCALAR_BY_DECK"' in opening
    assert 'data-selector="NONE"' in opening
    assert opening.endswith(" hidden>")
    assert section.count("<h2>") == 1
    assert section_heading(section) == "Tempo Computacional"
    assert "<select" not in section
    assert "plant-filter" not in section


# --- Testing Requirements: a group whose members exist but whose cells are all None for one -----
# --- deck stays absent there, in both the group and TOTAL, while the other deck's cells hold ----


def test_aggregate_times_all_none_cell_for_one_deck_is_absent_from_group_and_total() -> None:
    raw: ScalarsByName = {
        "MILP": {"caso_a": {"03/03/2024": 100.0, "04/03/2024": 110.0}},
        "PL": {"caso_a": {"03/03/2024": 200.0, "04/03/2024": None}},
        "PL.Int.Fix": {"caso_a": {"03/03/2024": 300.0, "04/03/2024": None}},
        "PL.CalcCMO": {"caso_a": {"03/03/2024": 400.0, "04/03/2024": None}},
    }

    result = aggregate_times(
        raw,
        stage_groups={"MILP": ["MILP"], "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"]},
        unit_divisor=60.0,
        decimals=2,
    )

    assert "04/03/2024" not in result["PL"]["caso_a"]
    assert result["PL"]["caso_a"]["03/03/2024"] == round((200.0 + 300.0 + 400.0) / 60.0, 2)
    assert "04/03/2024" not in result["TOTAL"]["caso_a"]
    assert "03/03/2024" in result["TOTAL"]["caso_a"]


# --- Testing Requirements: requirement 4 (TOTAL over emitted groups) and requirement 5 -----------
# --- (uncovered etapa) compose: a sixth uncovered etapa warns once and leaves TOTAL unchanged ----


def test_aggregate_times_sixth_uncovered_etapa_warns_once_and_leaves_total_unchanged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_SCALARS_LOGGER_NAME)
    raw_with_sixth: ScalarsByName = {
        **_RAW_FIVE_ETAPAS,
        "PL.Aleatorio": {
            "caso_a": {"03/03/2024": 999.0, "04/03/2024": 888.0},
            "caso_b": {"03/03/2024": 777.0, "04/03/2024": 666.0},
        },
    }

    result_five = aggregate_times(
        _RAW_FIVE_ETAPAS, stage_groups=_DEFAULT_STAGE_GROUPS, unit_divisor=60.0, decimals=2
    )
    result_six = aggregate_times(
        raw_with_sixth, stage_groups=_DEFAULT_STAGE_GROUPS, unit_divisor=60.0, decimals=2
    )

    assert result_six["TOTAL"] == result_five["TOTAL"]
    matching = [
        record
        for record in caplog.records
        if record.name == _SCALARS_LOGGER_NAME
        and record.args == ("PL.Aleatorio", "time.stage_groups")
    ]
    assert len(matching) == 1


# --- Testing Requirements: group order follows stage_groups insertion order, not a sort ---------


def test_aggregate_times_group_order_follows_reversed_insertion_order() -> None:
    reversed_groups = {
        "Leitura": ["Leitura de Dados e Impressão"],
        "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"],
        "MILP": ["MILP"],
    }

    result = aggregate_times(
        _RAW_FIVE_ETAPAS, stage_groups=reversed_groups, unit_divisor=60.0, decimals=2
    )

    assert list(result) == ["Leitura", "PL", "MILP", "TOTAL"]


# --- Testing Requirements: every emitted value is None or rounded, -0.0 never appears -----------


def test_aggregate_times_every_emitted_value_is_none_or_rounded_to_two_decimals() -> None:
    result = aggregate_times(
        _RAW_FIVE_ETAPAS, stage_groups=_DEFAULT_STAGE_GROUPS, unit_divisor=60.0, decimals=2
    )

    for series in result.values():
        for by_scenario in series.values():
            for value in by_scenario.values():
                assert value is None or value == round(value, 2)


def test_aggregate_times_group_value_never_emits_negative_zero() -> None:
    """A group's own conversion (sum of raw seconds divided by unit_divisor, rounded once) is
    the one place in aggregate_times a small negative value can round to -0.0: TOTAL only ever
    sums already-normalised group values, and IEEE 754 addition of a value together with its
    exact negation yields +0.0 rather than -0.0, so this same guard is not reachable at the
    TOTAL step through ordinary cancellation (verified empirically: every exact-cancellation pair
    tried summed to a clean +0.0 before this test was written). -0.06 seconds divided by the
    shipped 60.0 unit_divisor is -0.001 minutes, which round(-0.001, 2) renders as -0.0 without
    the guard -- and TOTAL, summing that one already-normalised group, stays clean too."""
    raw: ScalarsByName = {"MILP": {"caso_a": {"03/03/2024": -0.06}}}

    result = aggregate_times(raw, stage_groups={"MILP": ["MILP"]}, unit_divisor=60.0, decimals=2)
    milp = result["MILP"]["caso_a"]["03/03/2024"]
    total = result["TOTAL"]["caso_a"]["03/03/2024"]

    assert milp == 0.0
    assert math.copysign(1.0, milp) == 1.0, "negative zero leaked into the MILP group"
    assert total == 0.0
    assert math.copysign(1.0, total) == 1.0, "negative zero leaked into the TOTAL series"


# --- ruling of 2026-09-11: the lenient group sum against the strict TOTAL, locked in ------------


def test_aggregate_times_group_sums_present_members_leniently_unlike_the_strict_total() -> None:
    """A group's own cell sums whichever present members carry a value, omitting the cell only
    when literally every present member lacks one there (requirement 3) -- deliberately more
    lenient than TOTAL, which requires every emitted group to carry a value (requirement 4). If
    the group applied TOTAL's strict rule instead, this cell would be entirely absent rather than
    a partial sum over PL and PL.CalcCMO, since PL.Int.Fix explicitly lacks a value here."""
    raw: ScalarsByName = {
        "PL": {"caso_a": {"03/03/2024": 200.0}},
        "PL.Int.Fix": {"caso_a": {"03/03/2024": None}},
        "PL.CalcCMO": {"caso_a": {"03/03/2024": 400.0}},
    }

    result = aggregate_times(
        raw,
        stage_groups={"PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"]},
        unit_divisor=60.0,
        decimals=2,
    )

    assert "03/03/2024" in result["PL"]["caso_a"]
    assert result["PL"]["caso_a"]["03/03/2024"] == round((200.0 + 400.0) / 60.0, 2)


# --- epic-04 boundary review finding 3 (2026-09-11): unit_divisor and the pinned "min" label ----
# --- are checked TOGETHER, not each in its own test ----------------------------------------------


def test_aggregate_times_unit_divisor_and_pinned_min_label_checked_together(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """FALLBACK_UNITS["TEMPO"] (data/schemas.py) hard-codes "min" independently of
    time.unit_divisor; this module's own criterion-1 test above pins the 60.0 divisor and
    tests/test_charts_costs.py's payload test pins the "min" label, but each does so alone, so
    neither would notice the two drifting apart if only one side changed -- exactly the defect
    epic 3 shipped and ticket-031 closed, reintroducible by a one-line settings.json edit. This
    test calls aggregate_times with the two divisors in the same body and checks both halves of
    the pairing at once: the matching divisor (60.0) stays silent, and the mismatched one (1.0)
    warns while naming the exact label read from FALLBACK_UNITS itself, not a copy of the
    literal.
    """
    caplog.set_level(logging.WARNING, logger=_SCALARS_LOGGER_NAME)

    aggregate_times(
        _RAW_FIVE_ETAPAS, stage_groups=_DEFAULT_STAGE_GROUPS, unit_divisor=60.0, decimals=2
    )
    assert [r for r in caplog.records if r.name == _SCALARS_LOGGER_NAME] == []

    caplog.clear()
    aggregate_times(
        _RAW_FIVE_ETAPAS, stage_groups=_DEFAULT_STAGE_GROUPS, unit_divisor=1.0, decimals=2
    )
    matching = [
        record
        for record in caplog.records
        if record.name == _SCALARS_LOGGER_NAME and record.args == ("time.unit_divisor", 1.0, 60.0)
    ]
    assert len(matching) == 1
    assert f"'{FALLBACK_UNITS['TEMPO']}'" in matching[0].getMessage()


# --- non-vacuity proofs: the three mutations of Suggested Approach step 8 -----------------------


def test_criterion_1_division_check_is_not_vacuous_when_unit_divisor_is_one() -> None:
    result = aggregate_times(
        _RAW_FIVE_ETAPAS, stage_groups=_DEFAULT_STAGE_GROUPS, unit_divisor=60.0, decimals=2
    )
    _check_default_stage_groups_shape_and_division_proof(result)

    mutated = aggregate_times(
        _RAW_FIVE_ETAPAS, stage_groups=_DEFAULT_STAGE_GROUPS, unit_divisor=1.0, decimals=2
    )
    with pytest.raises(AssertionError):
        _check_default_stage_groups_shape_and_division_proof(mutated)


def test_criterion_2_warning_check_is_not_vacuous_when_leitura_is_restored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_SCALARS_LOGGER_NAME)
    reduced = {"MILP": ["MILP"], "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"]}
    result = aggregate_times(_RAW_FIVE_ETAPAS, stage_groups=reduced, unit_divisor=60.0, decimals=2)
    _check_reduced_stage_groups_total_and_warning(result, caplog)

    caplog.clear()
    restored = {**reduced, "Leitura": ["Leitura de Dados e Impressão"]}
    mutated = aggregate_times(
        _RAW_FIVE_ETAPAS, stage_groups=restored, unit_divisor=60.0, decimals=2
    )
    with pytest.raises(AssertionError):
        _check_reduced_stage_groups_total_and_warning(mutated, caplog)


def test_criterion_2_strict_inequality_is_not_vacuous_against_a_sum_of_every_row_total() -> None:
    """The default settings cannot distinguish "TOTAL is the sum of the emitted groups" from
    "TOTAL is the sum of every etapa row", because the three default groups happen to cover all
    five etapas (background section of the ticket). This mutation substitutes the real, correct
    TOTAL of the reduced (Leitura-dropped) case with what the wrong "every row" definition would
    have produced -- MILP + PL + Leitura, which by construction equals the every-row sum exactly
    -- and confirms criterion 2's own strict-inequality check then fails."""
    reduced = {"MILP": ["MILP"], "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"]}
    result = aggregate_times(_RAW_FIVE_ETAPAS, stage_groups=reduced, unit_divisor=60.0, decimals=2)
    _check_total_strictly_below_every_row_sum(result)

    wrong_total: dict[str, dict[str, float | None]] = {}
    for scenario, by_deck in result["TOTAL"].items():
        for deck_key in by_deck:
            all_five_seconds = _raw_group_seconds(
                _RAW_FIVE_ETAPAS,
                ["MILP", "PL", "PL.Int.Fix", "PL.CalcCMO", "Leitura de Dados e Impressão"],
                scenario,
                deck_key,
            )
            wrong_total.setdefault(scenario, {})[deck_key] = round(all_five_seconds / 60.0, 2)
    mutated_result = {**result, "TOTAL": wrong_total}

    with pytest.raises(AssertionError):
        _check_total_strictly_below_every_row_sum(mutated_result)
