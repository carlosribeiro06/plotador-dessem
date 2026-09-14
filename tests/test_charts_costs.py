"""End-to-end tests for the cost bar charts (ticket-030, amended by melhorias-dashboard design
D7): scalars.aggregate_costs directly, the dedicated CUSTO_* payload entries it produces, the
dashboard.js bar-trace machinery as static text, and the Custo group's document sections.

Suggested Approach step 11 asks for four non-vacuity mutations. The third-quoted-"diferenca"/
third-KEYS.REFERENCE injection lives in tests/test_renderer_value_mode.py instead of here, because
that is the module whose own requirement-10 narrowing it proves non-vacuous
(test_narrowed_diferenca_and_keys_reference_checks_fail_on_a_third_occurrence). The remaining
three -- the stack/group swap, the dropped TOTAL emission, and data-kind appended after hidden --
are this ticket's own criteria and live below.
"""

from __future__ import annotations

import importlib.resources
import json
import logging
import math
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from dashboard_document import (
    chart_section_slices,
    opening_tag,
    section_heading,
    sections_by_chart_key,
    sections_by_group,
)
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import build_html
from dessem_dashboard.dashboard.payload import build_payload
from dessem_dashboard.dashboard.scalars import aggregate, aggregate_costs
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.errors import ConfigError
from dessem_dashboard.models.store import DashboardData

_ASSETS_PACKAGE = "dessem_dashboard.dashboard.assets"
_JS_ASSET = "dashboard.js"
_SCALARS_LOGGER_NAME = "dessem_dashboard.dashboard.scalars"

_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# window.DessemDashboard's members immediately before this ticket: the thirteen ticket-026 left,
# plus applyPlantFilter, which ticket-028 added afterward (tests/test_charts_filters.py's own
# _THIRTEEN_MEMBERS_AFTER_TICKET_026 checks applyPlantFilter separately). Ticket-030's own
# acceptance criterion 4 names only "the thirteen members present after ticket-026", which
# undercounts applyPlantFilter by one -- a minor imprecision the codebase convention (epic-03
# learnings section 7: assert presence, never a count) makes harmless here.
_MEMBERS_BEFORE_TICKET_030: tuple[str, ...] = (
    "payload",
    "state",
    "axisKey",
    "buildTraces",
    "buildLayout",
    "renderChart",
    "renderActiveGroup",
    "init",
    "setMode",
    "setDeck",
    "setGroup",
    "setValueMode",
    "setEntity",
    "applyPlantFilter",
)

# A hand-built four-parcela, two-scenario, two-deck raw mapping, distinct enough that a value
# stored under the wrong parcel, scenario or deck is detectable and that the two-parcel default
# total is strictly less than the four-parcela total at every cell.
_RAW_FOUR_PARCELS: dict[str, dict[str, dict[str, float | None]]] = {
    "PRESENTE": {
        "caso_a": {"03/03/2024": 100.0, "04/03/2024": 110.0},
        "caso_b": {"03/03/2024": 120.0, "04/03/2024": 130.0},
    },
    "FUTURO": {
        "caso_a": {"03/03/2024": 200.0, "04/03/2024": 210.0},
        "caso_b": {"03/03/2024": 220.0, "04/03/2024": 230.0},
    },
    "VIOLACOES": {
        "caso_a": {"03/03/2024": 1.0, "04/03/2024": 2.0},
        "caso_b": {"03/03/2024": 3.0, "04/03/2024": 4.0},
    },
    "PEQUENAS PENALIDADES": {
        "caso_a": {"03/03/2024": 0.5, "04/03/2024": 0.6},
        "caso_b": {"03/03/2024": 0.7, "04/03/2024": 0.8},
    },
}


# --- settings/data/document/payload builders, following tests/test_builder.py's pattern -------


def _settings_dict(*, disabled: Sequence[str] = ()) -> dict[str, Any]:
    """Build a settings.json-shaped dict matching the repository's own values, with a knob.

    costs.total_parcels stays at the repository default ["PRESENTE", "FUTURO"]: every test that
    exercises a different parcel set calls aggregate/aggregate_costs directly over a hand-built
    raw mapping instead, which needs no settings.json at all.

    One deliberate divergence: `time.stage_groups` is reduced to the single `PL` group,
    so these tests do not depend on the shipped three-group default. Correct this sentence
    rather than the value.
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
        "time": {"stage_groups": {"PL": ["PL"]}, "unit_divisor": 60.0},
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
    paths: Sequence[Path], tmp_path: Path, *, reference: str
) -> dict[str, object]:
    settings = _build_settings(tmp_path)
    data = _build_data(paths, settings=settings, reference=reference)
    return build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})


# --- dashboard.js text-slicing helpers, private copies per the plan's per-module convention ----


def _read_js_asset() -> str:
    return (
        importlib.resources.files(_ASSETS_PACKAGE).joinpath(_JS_ASSET).read_text(encoding="utf-8")
    )


def _dessem_dashboard_assignment(text: str) -> str:
    """Return the text of the single `window.DessemDashboard = {...};` assignment."""
    start = text.index("window.DessemDashboard")
    end = text.index("};", start) + len("};")
    return text[start:end]


def _function_body(text: str, name: str) -> str:
    """Return the full `function name(...) { ... }` slice, matching braces by depth."""
    match = re.search(r"function\s+" + re.escape(name) + r"\([^)]*\)\s*\{", text)
    assert match is not None, f"function '{name}' not found in dashboard.js"
    depth = 0
    index = match.end() - 1
    while True:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                break
        index += 1
    return text[match.start() : index + 1]


def _function_bodies(text: str) -> list[str]:
    """Return every top-level `function name(...) { ... }` slice found in text, in order."""
    return [
        _function_body(text, match.group(1)) for match in re.finditer(r"function\s+(\w+)\(", text)
    ]


def _keys_declaration_span(text: str) -> tuple[int, int]:
    """Return the (start, end) character span of the raw `const KEYS = Object.freeze({...});`."""
    start = text.index("const KEYS")
    end = text.index("});", start) + len("});")
    return start, end


def _check_keys_entry_declared_once(text: str, quoted_value: str) -> None:
    """Assert quoted_value is declared exactly once inside the KEYS block and never used as a
    raw index anywhere, mirroring tests/test_charts_sin.py's own narrowed check."""
    stripped = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL))
    start, end = _keys_declaration_span(stripped)
    keys_block = stripped[start:end]
    assert keys_block.count(quoted_value) == 1, (
        f"{quoted_value} must be declared exactly once in the KEYS object"
    )
    assert not re.search(rf"\[\s*{re.escape(quoted_value)}\s*\]", stripped), (
        f"{quoted_value} is used as a raw index; a payload key must be read only through KEYS"
    )


def _check_build_layout_scalar_branch(text: str) -> None:
    """Assert buildLayout's own body reads the kind, sets a category axis and a group barmode."""
    body = _function_body(text, "buildLayout")
    assert "chart[KEYS.KIND]" in body
    assert '"category"' in body
    assert 'layout.barmode = "group";' in body


def _check_yaxis_assigned_in_exactly_one_function(text: str) -> None:
    bodies = _function_bodies(text)
    matching = [body for body in bodies if "yaxis" in body]
    assert len(matching) == 1, f"'yaxis' assigned in {len(matching)} functions, expected exactly 1"


# --- shared checkers over the aggregate_costs result, reused by the non-vacuity proof ----------


def _check_default_parcels_total_is_partial_sum_and_less_than_all_four(
    result: dict[str, dict[str, dict[str, float | None]]],
) -> None:
    """Acceptance criterion 1, first half, factored out so the non-vacuity proof below can call
    it against a deliberately mutated copy of the real result."""
    assert list(result) == ["PRESENTE", "FUTURO", "TOTAL"]
    for scenario, by_deck in result["TOTAL"].items():
        for deck_key, total in by_deck.items():
            presente = result["PRESENTE"][scenario][deck_key]
            futuro = result["FUTURO"][scenario][deck_key]
            assert presente is not None
            assert futuro is not None
            assert total is not None
            assert total == pytest.approx(presente + futuro, abs=0.01)
            all_four = sum(
                value
                for parcel in _RAW_FOUR_PARCELS
                if (value := _RAW_FOUR_PARCELS[parcel][scenario][deck_key]) is not None
            )
            assert total < all_four


# --- acceptance criterion 1: default and all-four-parcela totals -------------------------------


def test_aggregate_costs_default_parcels_total_is_partial_sum_and_less_than_all_four() -> None:
    result = aggregate_costs(_RAW_FOUR_PARCELS, parcels=["PRESENTE", "FUTURO"], decimals=2)
    _check_default_parcels_total_is_partial_sum_and_less_than_all_four(result)


def test_aggregate_costs_all_four_parcels_configured_total_equals_their_sum() -> None:
    parcels = ["PRESENTE", "FUTURO", "VIOLACOES", "PEQUENAS PENALIDADES"]
    result = aggregate_costs(_RAW_FOUR_PARCELS, parcels=parcels, decimals=2)

    assert list(result) == [*parcels, "TOTAL"]
    for scenario, by_deck in result["TOTAL"].items():
        for deck_key, total in by_deck.items():
            expected = sum(_RAW_FOUR_PARCELS[parcel][scenario][deck_key] for parcel in parcels)
            assert total == pytest.approx(expected, abs=0.01)


# --- acceptance criterion 2: a missing parcel warns once; TOTAL in parcels raises --------------


def test_aggregate_costs_parcel_absent_from_raw_is_warned_once_and_omitted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_SCALARS_LOGGER_NAME)

    result = aggregate_costs(
        _RAW_FOUR_PARCELS, parcels=["PRESENTE", "FUTURO", "INEXISTENTE"], decimals=2
    )

    assert list(result) == ["PRESENTE", "FUTURO", "TOTAL"]
    matching = [record for record in caplog.records if record.name == _SCALARS_LOGGER_NAME]
    assert len(matching) == 1
    assert matching[0].levelno == logging.WARNING
    assert matching[0].args == ("INEXISTENTE", "costs.total_parcels")


def test_aggregate_costs_total_named_in_parcels_raises_config_error() -> None:
    with pytest.raises(ConfigError, match=re.escape("costs.total_parcels")):
        aggregate_costs(_RAW_FOUR_PARCELS, parcels=["PRESENTE", "TOTAL"], decimals=2)


# --- Testing Requirements: dispatch touches only the chart it owns -----------------------------


def test_aggregate_passthrough_returns_raw_unchanged_and_by_identity_for_a_series_chart(
    tmp_path: Path,
) -> None:
    settings = _build_settings(tmp_path)
    raw: dict[str, dict[str, dict[str, float | None]]] = {"": {"caso_a": {"03/03/2024": 123.45}}}

    result = aggregate("GHID_SIN", raw, settings=settings)

    assert result is raw


# --- Testing Requirements: missing cell vs missing parcel are governed by different rules ------


def test_aggregate_costs_missing_cell_among_present_parcels_omits_only_that_cell_no_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw: dict[str, dict[str, dict[str, float | None]]] = {
        "PRESENTE": {
            "caso_a": {"03/03/2024": 100.0, "04/03/2024": 110.0},
            "caso_b": {"03/03/2024": 120.0},
        },
        "FUTURO": {
            "caso_a": {"03/03/2024": 200.0, "04/03/2024": 210.0},
            "caso_b": {"03/03/2024": 220.0, "04/03/2024": 230.0},
        },
    }
    caplog.set_level(logging.WARNING, logger=_SCALARS_LOGGER_NAME)

    result = aggregate_costs(raw, parcels=["PRESENTE", "FUTURO"], decimals=2)

    assert "04/03/2024" not in result["TOTAL"]["caso_b"]
    assert result["TOTAL"]["caso_a"] == {"03/03/2024": 300.0, "04/03/2024": 320.0}
    assert result["TOTAL"]["caso_b"]["03/03/2024"] == 340.0
    assert [r for r in caplog.records if r.name == _SCALARS_LOGGER_NAME] == []


def test_aggregate_costs_none_value_cell_is_treated_like_a_missing_cell() -> None:
    raw: dict[str, dict[str, dict[str, float | None]]] = {
        "PRESENTE": {"caso_a": {"03/03/2024": 100.0, "04/03/2024": None}},
        "FUTURO": {"caso_a": {"03/03/2024": 200.0, "04/03/2024": 210.0}},
    }

    result = aggregate_costs(raw, parcels=["PRESENTE", "FUTURO"], decimals=2)

    assert "04/03/2024" not in result["TOTAL"]["caso_a"]
    assert result["TOTAL"]["caso_a"]["03/03/2024"] == 300.0


# --- Testing Requirements: parcel order follows settings, not raw's insertion order ------------


def test_aggregate_costs_parcel_order_follows_configured_order_not_raw_insertion_order() -> None:
    raw: dict[str, dict[str, dict[str, float | None]]] = {
        "PRESENTE": {"caso_a": {"03/03/2024": 100.0}},
        "FUTURO": {"caso_a": {"03/03/2024": 200.0}},
    }

    result = aggregate_costs(raw, parcels=["FUTURO", "PRESENTE"], decimals=2)

    assert list(result) == ["FUTURO", "PRESENTE", "TOTAL"]


# --- Testing Requirements: every value is None or rounded, -0.0 never appears -------------------


def test_aggregate_costs_every_emitted_value_is_none_or_rounded_to_two_decimals() -> None:
    """Feeds already-rounded parcel values, matching what _build_scalars hands aggregate_costs in
    the real pipeline: every pass-through parcel value and the freshly computed TOTAL alike must
    equal itself rounded to two decimals."""
    raw: dict[str, dict[str, dict[str, float | None]]] = {
        "PRESENTE": {"caso_a": {"03/03/2024": 100.25, "04/03/2024": None}},
        "FUTURO": {"caso_a": {"03/03/2024": -50.1, "04/03/2024": 10.0}},
    }

    result = aggregate_costs(raw, parcels=["PRESENTE", "FUTURO"], decimals=2)

    for series in result.values():
        for by_scenario in series.values():
            for value in by_scenario.values():
                assert value is None or value == round(value, 2)


def test_aggregate_costs_total_never_emits_negative_zero() -> None:
    """The TOTAL sum is the one value aggregate_costs itself computes and rounds, so it is the
    one place a rounded-to-zero negative sum could otherwise surface as -0.0."""
    raw: dict[str, dict[str, dict[str, float | None]]] = {
        "PRESENTE": {"caso_a": {"03/03/2024": 0.001}},
        "FUTURO": {"caso_a": {"03/03/2024": -0.002}},
    }

    result = aggregate_costs(raw, parcels=["PRESENTE", "FUTURO"], decimals=2)
    total = result["TOTAL"]["caso_a"]["03/03/2024"]

    assert total == 0.0
    assert math.copysign(1.0, total) == 1.0, "negative zero leaked into the TOTAL series"


# --- acceptance criterion 3: the fixture payload's CUSTOS scalars, and TEMPO's pass-through ------


def test_payload_dedicated_cost_charts_each_emit_only_their_own_series_with_full_coverage(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """melhorias-dashboard design D7: the former combined CUSTOS chart is replaced by three
    dedicated charts, each emitting exactly one aggregated series (PRESENTE, FUTURO or TOTAL) in
    its own scalars, so a reader analyses one cost component per chart. All three still carry
    CUSTOS' unit, since their raw data is the same CUSTOS.parquet aggregated once."""
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    charts = payload["charts"]  # type: ignore[index]

    for chart_key, series_name in (
        ("CUSTO_PRESENTE", "PRESENTE"),
        ("CUSTO_FUTURO", "FUTURO"),
        ("CUSTO_TOTAL", "TOTAL"),
    ):
        chart = charts[chart_key]  # type: ignore[index]
        assert set(chart["scalars"]) == {series_name}
        by_scenario = chart["scalars"][series_name]
        assert set(by_scenario) == {"caso_a", "caso_b"}
        for by_deck in by_scenario.values():
            assert set(by_deck) == {"03/03/2024", "04/03/2024"}
        assert chart["entities"] == []
        assert chart["series"] == {}
        # Every dedicated cost chart shares COP_SIN/CFU_SIN's unit, not R$, derived from its
        # source_file CUSTOS: PRESENTE (58667.5674 raw) tracks COP_SIN's 144 h sum (ratio 1.0019)
        # and FUTURO (228420390.34615 raw) tracks CFU_SIN at 10^3 R$ (ratio 0.9978), not plain R$
        # (epic-04 boundary review finding 1; schemas.py's FALLBACK_UNITS comment has the figures).
        assert chart["unit"] == "10^3 R$"


def test_payload_dedicated_time_charts_slice_the_aggregated_series_under_narrow_stage_groups(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """Design D7 splits the former combined TEMPO chart into four dedicated charts, each slicing
    one series out of the same aggregated TEMPO. Under this module's own narrow settings
    (time.stage_groups = {"PL": ["PL"]}) the aggregation yields only PL and TOTAL, so the PL and
    TOTAL charts each carry their one series while the MILP and Leitura charts degrade by omission
    to an empty scalars -- proving the time path honours these settings (no other group is
    invented) and that building CUSTOS in the same payload does not disturb it."""
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    charts = payload["charts"]  # type: ignore[index]

    assert set(charts["TEMPO_PL"]["scalars"]) == {"PL"}  # type: ignore[index]
    assert set(charts["TEMPO_TOTAL"]["scalars"]) == {"TOTAL"}  # type: ignore[index]
    assert charts["TEMPO_MILP"]["scalars"] == {}  # type: ignore[index]
    assert charts["TEMPO_LEITURA"]["scalars"] == {}  # type: ignore[index]


def test_payload_custos_total_for_caso_a_recomputed_from_the_parquet_file_with_pandas(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """Proves the TOTAL reached the payload from CUSTOS.parquet rather than from a coincidence
    of the aggregation, without restating a specific figure anywhere else in this suite."""
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    raw = pd.read_parquet(
        scenario_tree["caso_a"] / "deck_um" / "sintese" / "CUSTOS.parquet", engine="pyarrow"
    )
    presente = round(float(raw.loc[raw["parcela"] == "PRESENTE", "valor_esperado"].sum()), 2)
    futuro = round(float(raw.loc[raw["parcela"] == "FUTURO", "valor_esperado"].sum()), 2)
    expected_total = round(presente + futuro, 2)

    assert payload["charts"]["CUSTO_TOTAL"]["scalars"]["TOTAL"]["caso_a"]["03/03/2024"] == (  # type: ignore[index]
        expected_total
    )


# --- acceptance criterion 4: the dashboard.js asset text ----------------------------------------


def test_dashboard_js_exposes_build_bar_traces_in_addition_to_the_existing_members() -> None:
    text = _read_js_asset()
    assignment_text = _dessem_dashboard_assignment(text)

    for member in _MEMBERS_BEFORE_TICKET_030:
        assert member in assignment_text, f"member '{member}' not found in the assignment block"
    assert "buildBarTraces" in assignment_text


@pytest.mark.parametrize("quoted_value", ['"kind"', '"scalars"'])
def test_dashboard_js_keys_declares_kind_and_scalars_exactly_once_each(quoted_value: str) -> None:
    text = _read_js_asset()
    _check_keys_entry_declared_once(text, quoted_value)


def test_dashboard_js_contains_bar_type_and_reads_kind_through_keys() -> None:
    text = _read_js_asset()
    assert 'type: "bar"' in text
    assert "chart[KEYS.KIND]" in text


def test_dashboard_js_build_layout_sets_category_axis_and_group_barmode() -> None:
    text = _read_js_asset()
    _check_build_layout_scalar_branch(text)


def test_dashboard_js_pinned_invariants_hold_after_the_bar_chart_additions() -> None:
    text = _read_js_asset()

    assert text.count("Plotly.react(") == 1
    assert text.count("Object.freeze({") == 1
    assert text.count('"absoluto"') == 0
    assert "Plotly.newPlot(" not in text
    for token in ("rangemode", "annotations", "hovertemplate"):
        assert token not in text
    _check_yaxis_assigned_in_exactly_one_function(text)
    assert text.isascii() is True


# --- acceptance criterion 5: the dedicated Custo group's document sections ---------------------

_COST_SECTION_KEYS_AND_HEADINGS: tuple[tuple[str, str], ...] = (
    ("CUSTO_PRESENTE", "Custo Presente"),
    ("CUSTO_FUTURO", "Custo Futuro"),
    ("CUSTO_TOTAL", "Custo Total"),
)
_SCALAR_SECTION_KEYS = frozenset(
    {
        "CUSTO_PRESENTE",
        "CUSTO_FUTURO",
        "CUSTO_TOTAL",
        "TEMPO_MILP",
        "TEMPO_PL",
        "TEMPO_LEITURA",
        "TEMPO_TOTAL",
    }
)


def _check_custo_document_facts(document: str) -> None:
    """Assert the dedicated Custo group's document sections, factored out so the non-vacuity
    proof below can call it against a deliberately mutated copy of a real document.

    melhorias-dashboard design D7: the former single combined CUSTOS section is now three
    dedicated CUSTO-group sections (Custo Presente, Futuro, Total), each a hidden SCALAR_BY_DECK
    with no entity selector and no plant filter; every non-scalar section stays a SERIES."""
    sections = sections_by_group(document, "CUSTO")
    assert len(sections) == 3

    by_key = sections_by_chart_key(document)
    for key, heading in _COST_SECTION_KEYS_AND_HEADINGS:
        section = by_key[key]
        opening = opening_tag(section)
        assert 'data-kind="SCALAR_BY_DECK"' in opening
        assert 'data-selector="NONE"' in opening
        assert opening.endswith(" hidden>")
        assert section.count("<h2>") == 1
        assert section_heading(section) == heading
        assert "<select" not in section
        assert "plant-filter" not in section

    for chart_key, section in by_key.items():
        if chart_key in _SCALAR_SECTION_KEYS:
            continue
        assert 'data-kind="SERIES"' in opening_tag(section)


def test_document_custo_group_has_three_dedicated_scalar_sections_named_per_component(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    _check_custo_document_facts(document)


def test_document_data_kind_appears_exactly_once_per_enabled_chart_section(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    sections = chart_section_slices(document)
    assert len(sections) == 28
    for section in sections:
        assert opening_tag(section).count("data-kind=") == 1


# --- non-vacuity proofs: mutations 2 to 4 of Suggested Approach step 11 ------------------------


def test_build_layout_scalar_branch_check_is_not_vacuous_when_barmode_is_stack() -> None:
    text = _read_js_asset()
    _check_build_layout_scalar_branch(text)

    body = _function_body(text, "buildLayout")
    mutated_body = body.replace('layout.barmode = "group";', 'layout.barmode = "stack";', 1)
    assert mutated_body != body, "transform did not change buildLayout's body"
    mutated_text = text.replace(body, mutated_body, 1)

    with pytest.raises(AssertionError):
        _check_build_layout_scalar_branch(mutated_text)


def test_acceptance_criterion_1_check_is_not_vacuous_when_total_emission_is_dropped() -> None:
    result = aggregate_costs(_RAW_FOUR_PARCELS, parcels=["PRESENTE", "FUTURO"], decimals=2)
    _check_default_parcels_total_is_partial_sum_and_less_than_all_four(result)

    dropped = {name: series for name, series in result.items() if name != "TOTAL"}
    with pytest.raises(AssertionError):
        _check_default_parcels_total_is_partial_sum_and_less_than_all_four(dropped)


def test_document_custo_check_is_not_vacuous_when_data_kind_is_appended_after_hidden(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    _check_custo_document_facts(document)

    custo_section = sections_by_chart_key(document)["CUSTO_PRESENTE"]
    opening = opening_tag(custo_section)
    original_suffix = ' data-kind="SCALAR_BY_DECK" hidden>'
    assert opening.endswith(original_suffix)
    mutated_opening = opening[: -len(original_suffix)] + ' hidden data-kind="SCALAR_BY_DECK">'
    assert mutated_opening != opening

    mutated_document = document.replace(opening, mutated_opening, 1)
    with pytest.raises(AssertionError):
        _check_custo_document_facts(mutated_document)
