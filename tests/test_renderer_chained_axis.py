"""Static contract tests for the chained (Encadeado) continuous axis in dashboard.js.

Epic decision E3-1 forbids executing JavaScript in this suite, so these tests read `dashboard.js`
as text and pin the statements that put the Encadeado line charts on the payload's continuous
axis: the four payload keys, the X array of `buildTraces` and the chained branch of `buildLayout`.
Each check function is paired with a mutation test proving it fails when its pinned statement is
altered. The browser behaviour is the manual checklist's job.

The two text-slicing helpers are private copies of the ones in tests/test_charts_costs.py, per the
convention in tests/dashboard_document.py's docstring (no private import from a sibling test
module).
"""

from __future__ import annotations

import importlib.resources
import re

import pytest

_ASSETS_PACKAGE = "dessem_dashboard.dashboard.assets"
_JS_ASSET = "dashboard.js"

_KEYS_BLOCK_PATTERN = re.compile(r"const KEYS = Object\.freeze\(\{(.*?)\}\);", re.DOTALL)
_KEYS_ENTRY_PATTERN = re.compile(r'([A-Z_]+):\s*"([^"]+)"')

_EXPECTED_CHAINED_KEYS: dict[str, str] = {
    "POSITIONS": "positions",
    "TICK_VALUES": "tick_values",
    "TICK_LABELS": "tick_labels",
    "HOVER_LABELS": "hover_labels",
}

_CHAINED_BRANCH_HEADER = "} else if (axisKey() === payload[KEYS.CHAINED_KEY]) {"

# The eight statements of the chained branch of buildLayout, each of which must occur exactly once
# inside that branch. Every entry is a complete statement, assignment target included: the three
# whose right-hand side is read from the axis (tickvals, ticktext, labelalias) are pinned as full
# assignments so that swapped targets or a renamed property fail the count instead of passing on
# the right-hand side alone. `delete layout.xaxis.tickformat;` also occurs once in the
# SCALAR_BY_DECK branch, so the count is scoped to the branch slice, never to the whole function
# body.
_CHAINED_BRANCH_STATEMENTS: tuple[str, ...] = (
    "delete layout.xaxis.tickformat;",
    'layout.xaxis.type = "linear";',
    "layout.xaxis.zeroline = false;",
    'layout.xaxis.tickmode = "array";',
    "layout.xaxis.tickvals = axis[KEYS.TICK_VALUES].slice();",
    "layout.xaxis.ticktext = axis[KEYS.TICK_LABELS].slice();",
    'layout.xaxis.hoverformat = "d";',
    "layout.xaxis.labelalias = Object.assign({}, axis[KEYS.HOVER_LABELS]);",
)

# The X-array ternary of buildTraces, pinned as one string so that the condition stays tied to its
# two arms: the chained axis reads the continuous positions, every deck axis the stage starts plus
# the closing end. Matched against whitespace-normalised source, as the JS spans several lines.
_BUILD_TRACES_X_TERNARY = (
    "key === payload[KEYS.CHAINED_KEY] "
    "? axis[KEYS.POSITIONS].slice() "
    ": axis[KEYS.STARTS].concat([axis[KEYS.END]])"
)


# --- dashboard.js text-slicing helpers, private copies per the plan's per-module convention ----


def _read_js_asset() -> str:
    return (
        importlib.resources.files(_ASSETS_PACKAGE).joinpath(_JS_ASSET).read_text(encoding="utf-8")
    )


def _normalise_whitespace(text: str) -> str:
    """Collapse every run of whitespace, newlines included, to a single space."""
    return " ".join(text.split())


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


# --- check functions: requirements 1 to 3 --------------------------------------------------------


def _check_keys_declared(text: str) -> None:
    """Assert the KEYS block maps the four chained-axis names to the payload's key spellings."""
    block_match = _KEYS_BLOCK_PATTERN.search(text)
    assert block_match is not None, "KEYS object literal not found in dashboard.js"
    declared = dict(_KEYS_ENTRY_PATTERN.findall(block_match.group(1)))
    for name, value in _EXPECTED_CHAINED_KEYS.items():
        assert declared.get(name) == value, (
            f"KEYS.{name} must be {value!r}, got {declared.get(name)!r}"
        )


def _check_build_traces_chained_x(text: str) -> None:
    """Assert buildTraces reads the chained axis' positions as X and keeps the deck X unchanged.

    The whole ternary is one whitespace-normalised substring, so the chained condition must select
    the positions arm and the deck axes the starts-plus-end arm; three independent substring tests
    would also pass with the arms swapped.
    """
    body = _normalise_whitespace(_function_body(text, "buildTraces"))
    assert _BUILD_TRACES_X_TERNARY in body, (
        f"buildTraces' X ternary must read {_BUILD_TRACES_X_TERNARY!r}"
    )


def _check_build_layout_chained_branch(text: str) -> None:
    """Assert buildLayout's chained branch follows the SCALAR_BY_DECK one and sets its eight lines.

    The branch is the slice from its `else if` header to the end of the function body, so the
    per-statement counts do not see the SCALAR branch's own `delete layout.xaxis.tickformat;`.
    """
    body = _function_body(text, "buildLayout")
    scalar_index = body.find("SCALAR_CHART_KIND")
    assert scalar_index != -1, "SCALAR_CHART_KIND not found in buildLayout"
    header_index = body.find(_CHAINED_BRANCH_HEADER)
    assert header_index != -1, f"{_CHAINED_BRANCH_HEADER!r} not found in buildLayout"
    assert header_index > scalar_index, "the chained branch must follow the SCALAR_BY_DECK branch"

    branch = body[header_index:]
    for statement in _CHAINED_BRANCH_STATEMENTS:
        occurrences = branch.count(statement)
        assert occurrences == 1, (
            f"{statement!r} occurs {occurrences} times in the chained branch, expected exactly 1"
        )


def _check_init_schema_version(text: str) -> None:
    """Assert init aborts on any payload schema version other than 2, in check and message."""
    body = _function_body(text, "init")
    assert "payload[KEYS.SCHEMA_VERSION] !== 2" in body
    assert "expected 2, got" in body


# --- the checks on the real asset ----------------------------------------------------------------


def test_dashboard_js_keys_declare_the_four_chained_axis_payload_keys() -> None:
    _check_keys_declared(_read_js_asset())


def test_build_traces_uses_positions_as_x_on_the_chained_axis_and_starts_otherwise() -> None:
    _check_build_traces_chained_x(_read_js_asset())


def test_build_layout_chained_branch_follows_scalar_branch_and_sets_linear_array_axis() -> None:
    _check_build_layout_chained_branch(_read_js_asset())


def test_dashboard_js_init_requires_schema_version_2() -> None:
    _check_init_schema_version(_read_js_asset())


# --- non-vacuity proofs: one mutation per check function -----------------------------------------


def test_keys_check_is_not_vacuous_when_positions_value_is_renamed() -> None:
    text = _read_js_asset()
    _check_keys_declared(text)

    mutated_text = text.replace('POSITIONS: "positions"', 'POSITIONS: "position"', 1)
    assert mutated_text != text, "transform did not change the KEYS block"

    with pytest.raises(AssertionError):
        _check_keys_declared(mutated_text)


def test_build_traces_check_is_not_vacuous_when_positions_key_is_replaced_by_starts() -> None:
    text = _read_js_asset()
    _check_build_traces_chained_x(text)

    body = _function_body(text, "buildTraces")
    mutated_body = body.replace("KEYS.POSITIONS", "KEYS.STARTS", 1)
    assert mutated_body != body, "transform did not change buildTraces' body"
    mutated_text = text.replace(body, mutated_body, 1)

    with pytest.raises(AssertionError):
        _check_build_traces_chained_x(mutated_text)


def test_build_traces_check_is_not_vacuous_when_ternary_arms_are_swapped() -> None:
    text = _read_js_asset()
    _check_build_traces_chained_x(text)

    body = _function_body(text, "buildTraces")
    mutated_body = re.sub(
        r"(key === payload\[KEYS\.CHAINED_KEY\]\s*\?\s*)"
        r"(axis\[KEYS\.POSITIONS\]\.slice\(\))"
        r"(\s*:\s*)"
        r"(axis\[KEYS\.STARTS\]\.concat\(\[axis\[KEYS\.END\]\]\))",
        r"\1\4\3\2",
        body,
        count=1,
    )
    assert mutated_body != body, "transform did not change buildTraces' body"
    mutated_text = text.replace(body, mutated_body, 1)

    with pytest.raises(AssertionError):
        _check_build_traces_chained_x(mutated_text)


def test_build_layout_check_is_not_vacuous_when_linear_type_is_replaced_by_date() -> None:
    text = _read_js_asset()
    _check_build_layout_chained_branch(text)

    body = _function_body(text, "buildLayout")
    mutated_body = body.replace('layout.xaxis.type = "linear";', 'layout.xaxis.type = "date";', 1)
    assert mutated_body != body, "transform did not change buildLayout's body"
    mutated_text = text.replace(body, mutated_body, 1)

    with pytest.raises(AssertionError):
        _check_build_layout_chained_branch(mutated_text)


def test_build_layout_check_is_not_vacuous_when_else_if_becomes_a_separate_if() -> None:
    text = _read_js_asset()
    _check_build_layout_chained_branch(text)

    body = _function_body(text, "buildLayout")
    mutated_body = body.replace(
        _CHAINED_BRANCH_HEADER, _CHAINED_BRANCH_HEADER.replace("else if", "if"), 1
    )
    assert mutated_body != body, "transform did not change buildLayout's body"
    mutated_text = text.replace(body, mutated_body, 1)

    with pytest.raises(AssertionError):
        _check_build_layout_chained_branch(mutated_text)


def test_build_layout_check_is_not_vacuous_when_tickvals_and_ticktext_targets_are_swapped() -> None:
    text = _read_js_asset()
    _check_build_layout_chained_branch(text)

    body = _function_body(text, "buildLayout")
    swapped_target = {"tickvals": "ticktext", "ticktext": "tickvals"}
    mutated_body = re.sub(
        r"layout\.xaxis\.(tickvals|ticktext) =",
        lambda match: f"layout.xaxis.{swapped_target[match.group(1)]} =",
        body,
    )
    assert mutated_body != body, "transform did not change buildLayout's body"
    mutated_text = text.replace(body, mutated_body, 1)

    with pytest.raises(AssertionError):
        _check_build_layout_chained_branch(mutated_text)


def test_build_layout_check_is_not_vacuous_when_labelalias_is_renamed_to_camel_case() -> None:
    text = _read_js_asset()
    _check_build_layout_chained_branch(text)

    body = _function_body(text, "buildLayout")
    mutated_body = body.replace("layout.xaxis.labelalias =", "layout.xaxis.labelAlias =", 1)
    assert mutated_body != body, "transform did not change buildLayout's body"
    mutated_text = text.replace(body, mutated_body, 1)

    with pytest.raises(AssertionError):
        _check_build_layout_chained_branch(mutated_text)


def test_init_schema_check_is_not_vacuous_when_version_is_1() -> None:
    text = _read_js_asset()
    _check_init_schema_version(text)

    body = _function_body(text, "init")
    mutated_body = body.replace("!== 2", "!== 1", 1)
    assert mutated_body != body, "transform did not change init's body"
    mutated_text = text.replace(body, mutated_body, 1)

    with pytest.raises(AssertionError):
        _check_init_schema_version(mutated_text)
