"""Tests for the Absoluto/Diferença value-mode toggle (ticket-024).

Epic decision E3-1 forbids executing any JavaScript in this suite, so the dashboard.js half of
this ticket is verified the same way tests/test_renderer_contract.py verifies ticket-022 and
tests/test_renderer_controls.py verifies ticket-023: as static text, by regular expression. The
difference arithmetic itself has no automated test under that decision; it is verified by hand
against docs/checklist-manual-dashboard.md's Absoluto/Diferença section. The builder.py half is
verified against real documents built from the scenario_tree fixture, following the
settings-copy-in-tmp_path pattern of tests/test_builder.py.
"""

from __future__ import annotations

import importlib.resources
import json
import re
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from conftest import build_scenario_tree
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import INITIAL_VALUE_MODE, VALUE_LABELS, build_html
from dessem_dashboard.dashboard.payload import build_payload
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.models.store import DashboardData

_ASSETS_PACKAGE = "dessem_dashboard.dashboard.assets"
_JS_ASSET = "dashboard.js"

_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# The ten members window.DessemDashboard already named after ticket-023; this ticket adds an
# eleventh, setValueMode, verified separately.
_TEN_MEMBERS_AFTER_TICKET_023 = (
    "payload",
    "state",
    "axisKey",
    "buildTraces",
    "renderChart",
    "renderActiveGroup",
    "init",
    "setMode",
    "setDeck",
    "setGroup",
)

# The GHID_SIN chained-axis length on the scenario_tree fixture: two decks, each contributing a
# 48-stage half-hourly chaining window (tests.conftest._CHAINING_WINDOW_STAGES).
_GHID_SIN_CHAINED_LENGTH = 96

# The per-deck stored length on the scenario_tree fixture (tests.conftest._CHAINED_N_STAGES).
_PER_DECK_STORED_LENGTH = 50


# --- shared helpers --------------------------------------------------------------------------


def _settings_dict(*, disabled: Sequence[str] = ()) -> dict[str, Any]:
    """Build a settings.json-shaped dict matching the repository's own values.

    One knob, and one deliberate divergence from
    `time.stage_groups`: it is deliberately reduced to the single `PL` group, so these tests
    do not depend on the shipped three-group default. Correct this sentence rather than the
    value -- changing it would move the `TEMPO` bar count, and a measured byte range in
    `tests/test_output_size.py`.
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


def _read_js_asset() -> str:
    return (
        importlib.resources.files(_ASSETS_PACKAGE).joinpath(_JS_ASSET).read_text(encoding="utf-8")
    )


def _dessem_dashboard_assignment(text: str) -> str:
    """Return the text of the single `window.DessemDashboard = {...};` assignment."""
    assignment_start = text.index("window.DessemDashboard")
    assignment_end = text.index("};", assignment_start) + len("};")
    return text[assignment_start:assignment_end]


def _function_body(text: str, name: str) -> str:
    """Return the full `function name(...) { ... }` slice, matching braces by depth.

    Private copy per the plan's per-module convention (tests/test_charts_sin.py,
    tests/test_charts_submarket.py, tests/test_charts_filters.py each keep their own). Depth
    tracking, not a lazy regex up to the first `}`: both buildTraces and buildBarTraces nest
    object literals inside their own body, and a naive match would stop at the first one.
    """
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


def _mutate_function_body(text: str, function_name: str, transform: Callable[[str], str]) -> str:
    """Apply transform to function_name's own body slice, leaving the rest of text untouched."""
    body = _function_body(text, function_name)
    mutated_body = transform(body)
    assert mutated_body != body, "transform did not change the function body"
    return text.replace(body, mutated_body, 1)


def _check_occurs_once_per_function_and_nowhere_else(
    text: str, literal: str, function_names: Sequence[str]
) -> None:
    """Assert literal occurs exactly once inside each of function_names' own bodies, and not at
    all anywhere else in text.

    Requirement 10's narrowing of the two ticket-024 assertions this file pinned at "exactly once
    in the whole file": ticket-030's buildBarTraces adds its own, legitimate second occurrence of
    both '"diferenca"' and "KEYS.REFERENCE", so the blanket count is now over-broad rather than
    wrong, in exactly the shape the epic-03 boundary review already prescribed the fix for.
    """
    remainder = text
    for name in function_names:
        body = _function_body(text, name)
        assert body.count(literal) == 1, f"expected exactly one {literal!r} inside {name}"
        remainder = remainder.replace(body, "", 1)
    assert remainder.count(literal) == 0, f"{literal!r} found outside {function_names}"


# --- acceptance criterion 1: builder.py's initial value-mode state --------------------------


def test_build_html_marks_absoluto_pressed_and_keeps_reference_label(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    for initial_mode in ("deck", "encadeado"):
        document = build_html(data, settings=settings, initial_mode=initial_mode)

        assert 'data-initial-value="absoluto"' in document
        assert (
            '<button type="button" data-value="absoluto" aria-pressed="true">Absoluto</button>'
            in document
        )
        assert (
            '<button type="button" data-value="diferenca" aria-pressed="false">'
            "Diferença</button>" in document
        )
        assert '<span id="reference-label">Referência: caso_a</span>' in document


def test_initial_value_mode_is_a_value_labels_key() -> None:
    """A typo in either INITIAL_VALUE_MODE or VALUE_LABELS fails this membership check."""
    assert INITIAL_VALUE_MODE in VALUE_LABELS


# --- acceptance criterion 2: dashboard.js's setter, listener and literal discipline ----------


def test_dashboard_js_exposes_set_value_mode_in_addition_to_the_ten_existing_members() -> None:
    text = _read_js_asset()
    assignment_text = _dessem_dashboard_assignment(text)

    for member in _TEN_MEMBERS_AFTER_TICKET_023:
        assert member in assignment_text, f"member '{member}' not found in the assignment block"
    assert "setValueMode" in assignment_text


def test_dashboard_js_reads_initial_value_from_document_and_diferenca_is_singular() -> None:
    text = _read_js_asset()

    assert '"value-toggle"' in text
    assert "dataset.initialValue" in text
    assert text.count('"absoluto"') == 0
    # Narrowed by ticket-030 requirement 10: buildBarTraces adds its own legitimate occurrence
    # of '"diferenca"', so "singular in the whole file" is now "singular per function body".
    _check_occurs_once_per_function_and_nowhere_else(
        text, '"diferenca"', ("buildTraces", "buildBarTraces")
    )
    assert text.isascii() is True


# --- acceptance criterion 3: the difference branch's KEYS discipline and rounding -----------


def test_dashboard_js_difference_branch_reads_reference_once_and_rounds_by_decimals() -> None:
    text = _read_js_asset()

    # Narrowed by ticket-030 requirement 10, for the same reason as the sibling assertion above:
    # buildBarTraces reads payload[KEYS.REFERENCE] once for its own Diferenca branch.
    _check_occurs_once_per_function_and_nowhere_else(
        text, "KEYS.REFERENCE", ("buildTraces", "buildBarTraces")
    )
    assert "Math.pow(10, payload[KEYS.FORMATS][KEYS.DECIMALS])" in text
    assert "Math.pow(10, 2)" not in text
    assert "* 100" not in text
    assert "/ 100" not in text
    for token in ("annotations", "rangemode", "newPlot"):
        assert token not in text


def test_narrowed_diferenca_and_keys_reference_checks_fail_on_a_third_occurrence() -> None:
    """Suggested Approach step 11 (ticket-030): prove the narrowing above is not vacuous by
    injecting a third quoted '"diferenca"' and a third "KEYS.REFERENCE" into setValueMode, a
    function that is neither buildTraces nor buildBarTraces. The old, blanket
    `text.count(...) == 1` this replaces would already fail here; the point of this test is that
    the narrowed, per-function check fails too, rather than being satisfied by any two-per-file
    total."""
    text = _read_js_asset()
    _check_occurs_once_per_function_and_nowhere_else(
        text, '"diferenca"', ("buildTraces", "buildBarTraces")
    )
    _check_occurs_once_per_function_and_nowhere_else(
        text, "KEYS.REFERENCE", ("buildTraces", "buildBarTraces")
    )

    injected = _mutate_function_body(
        text, "setValueMode", lambda body: body + '\n    // "diferenca" KEYS.REFERENCE\n'
    )
    with pytest.raises(AssertionError):
        _check_occurs_once_per_function_and_nowhere_else(
            injected, '"diferenca"', ("buildTraces", "buildBarTraces")
        )
    with pytest.raises(AssertionError):
        _check_occurs_once_per_function_and_nowhere_else(
            injected, "KEYS.REFERENCE", ("buildTraces", "buildBarTraces")
        )


def test_dashboard_js_keys_object_declares_reference_formats_decimals_once_each() -> None:
    text = _read_js_asset()

    for quoted_value in ('"reference"', '"formats"', '"decimals"'):
        assert text.count(quoted_value) == 1, f"{quoted_value} must occur exactly once"


def test_dashboard_js_returns_empty_array_when_reference_read_is_absent() -> None:
    """The Diferenca early-return: a missing reference series yields [], never a zero line.

    The early-return check is a regex, not the exact-indentation literal the epic-03 boundary
    review judged over-pinned: only the early return's existence is meant to be gated here, not
    the depth it happens to sit at, so a reindent of this branch must not turn this test red.
    """
    text = _read_js_asset()

    branch_start = text.index('if (state.valueMode === "diferenca") {')
    traces_declaration = text.index("const traces = [];", branch_start)
    branch_text = text[branch_start:traces_declaration]

    assert "payload[KEYS.REFERENCE]" in branch_text
    assert re.search(r"===\s*undefined\)\s*\{\s*return \[\];", branch_text) is not None


# --- acceptance criterion 4: the missing-reference-deck payload shape and its warning -------


def test_payload_unmodified_fixture_reference_and_ghid_sin_chained_lengths(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """Precondition for the manual checklist case: both scenarios carry 96 chained values."""
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})

    assert payload["reference"] == "caso_a"
    ghid_sin_series = payload["charts"]["GHID_SIN"]["series"][""]  # type: ignore[index]
    for scenario in ("caso_a", "caso_b"):
        chained_values = ghid_sin_series[scenario][payload["chained_key"]]  # type: ignore[index]
        assert len(chained_values) == _GHID_SIN_CHAINED_LENGTH


def test_payload_variant_tree_missing_reference_deck_has_no_key_and_is_warned(
    tmp_path: Path,
) -> None:
    """caso_a lacking the 04/03/2024 deck leaves that key absent, with a naming warning."""
    root = tmp_path / "variant_source"
    tree = build_scenario_tree(root)
    shutil.rmtree(tree["caso_a"] / "deck_dois")

    settings = _build_settings(tmp_path)
    data = _build_data([tree["caso_a"], tree["caso_b"]], settings=settings, reference="caso_a")
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})

    ghid_sin_series = payload["charts"]["GHID_SIN"]["series"][""]  # type: ignore[index]
    assert "04/03/2024" not in ghid_sin_series["caso_a"]
    assert len(ghid_sin_series["caso_b"]["04/03/2024"]) == _PER_DECK_STORED_LENGTH  # type: ignore[index]

    matching_warnings = [
        message for message in data.warnings() if "caso_a" in message and "04/03/2024" in message
    ]
    assert len(matching_warnings) == 1
