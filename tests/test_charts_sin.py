"""End-to-end tests for the SIN-level chart rendering (ticket-025).

Epic decision E3-1 forbids executing any JavaScript in this suite (`node` and `npm` are not
installed), so the `dashboard.js` half of this ticket is verified the same way
`tests/test_renderer_contract.py` verifies ticket-022 and `tests/test_renderer_value_mode.py`
verifies ticket-024: as static text. The `builder.py`/`payload.py` half is verified against real
documents and payloads built from the `scenario_tree` fixture, following the
settings-copy-in-`tmp_path` pattern of `tests/test_builder.py`. Every heading assertion is scoped
to the `data-group="SIN"` section slices: `Volume Armazenado` is also the curated title of
`VARMF_SBM` and `Geração Térmica` of `GTER_SBM`, so an unscoped assertion could be satisfied by
the wrong chart.
"""

from __future__ import annotations

import importlib.resources
import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import build_html
from dessem_dashboard.dashboard.payload import build_payload
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.errors import ConfigError
from dessem_dashboard.models.store import DashboardData

_ASSETS_PACKAGE = "dessem_dashboard.dashboard.assets"
_JS_ASSET = "dashboard.js"

_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# window.DessemDashboard's eleven members after ticket-024; this ticket adds a twelfth,
# buildLayout, verified separately so a later ticket adding a thirteenth cannot break this list.
_ELEVEN_MEMBERS_AFTER_TICKET_024 = (
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
    "setValueMode",
)

# The five default-enabled SIN-group chart keys, in dessem_dashboard.charts.specs.SPECS order.
_SIN_CHART_KEYS: tuple[str, ...] = ("GTER_SIN", "GHID_SIN", "GUNS_SIN", "EARMF_SIN", "VARMF_SIN")

# The full 23 keys SPECS enables by default (dessem_dashboard.charts.specs.SPECS), disabling all
# of which leaves enabled_specs() empty -- the precondition finding 1 of the epic-03 boundary
# review guards against, since _level_nav and _chart_sections both index specs[0] unguarded.
_ALL_ENABLED_CHART_KEYS: tuple[str, ...] = (
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

# Measured on the scenario_tree fixture (ticket-025 context), in enabled_specs order.
_SIN_TITLES_IN_ORDER: tuple[str, ...] = (
    "Geração Térmica",
    "Geração Hidrelétrica",
    "Geração Não Simulada",
    "EARMF",
    "Volume Armazenado",
)

# Measured on the scenario_tree fixture: three distinct units across the five SIN charts, not
# two, which is why a hard-coded default unit would mislabel EARMF_SIN and VARMF_SIN alike.
_SIN_UNITS_IN_ORDER: tuple[str, ...] = ("MW", "MW", "MW", "MWh", "hm3")
_THREE_DISTINCT_SIN_UNITS: frozenset[str] = frozenset({"MW", "MWh", "hm3"})

_FORBIDDEN_UNIT_LITERALS: tuple[str, ...] = ('"MW"', '"MWh"', '"hm3"', '"m3/s"')

_EXPECTED_ENTITIES: list[dict[str, str]] = [{"id": "", "label": "Sistema Interligado"}]
_DECK_KEYS_AND_LENGTHS: tuple[tuple[str, int], ...] = (
    ("03/03/2024", 50),
    ("04/03/2024", 50),
    ("encadeado", 96),
)

_SECTION_START = '<section class="chart"'
_SECTION_END = "</section>"


# --- text-slicing helpers ---------------------------------------------------------------------


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
    """Return the full `function name(...) { ... }` slice, matching braces by depth.

    Depth tracking, not a lazy regex up to the first `}`: renderChart's own body contains
    nested `{...}` object literals, and a naive match would stop at the first one.
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


def _function_bodies(text: str) -> list[str]:
    """Return every top-level `function name(...) { ... }` slice found in text, in order."""
    return [
        _function_body(text, match.group(1)) for match in re.finditer(r"function\s+(\w+)\(", text)
    ]


def _chart_section_slices(document: str) -> list[str]:
    """Split document into one slice per `<section class="chart" ...>...</section>` block.

    Sections are concatenated back to back by builder.py's _chart_sections with no separator
    and never nest, so the first `</section>` found after each `<section class="chart"` start
    is that same section's own close.
    """
    slices: list[str] = []
    search_start = 0
    while True:
        start = document.find(_SECTION_START, search_start)
        if start == -1:
            break
        end = document.index(_SECTION_END, start) + len(_SECTION_END)
        slices.append(document[start:end])
        search_start = end
    return slices


def _sin_sections(document: str) -> list[str]:
    """Return the data-group="SIN" section slices of document, in document order.

    Scoping mandatory, not stylistic: Volume Armazenado is also VARMF_SBM's curated title and
    Geração Térmica also GTER_SBM's, so an unscoped assertion could pass on the wrong chart.
    """
    return [section for section in _chart_section_slices(document) if 'data-group="SIN"' in section]


def _section_heading(section: str) -> str:
    match = re.search(r"<h2>([^<]*)</h2>", section)
    assert match is not None, f"no <h2> found in section slice: {section[:120]!r}"
    return match.group(1)


# --- settings/data/document builders, following tests/test_builder.py's pattern --------------


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


def _build_data(scenario_tree: dict[str, Path], settings: Settings) -> DashboardData:
    """Discover and consolidate scenario_tree's two scenarios into one DashboardData."""
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    return build_dashboard_data(scenarios, settings=settings, reference="caso_a")


def _build_payload_from_scenario_tree(
    scenario_tree: dict[str, Path], tmp_path: Path, *, disabled: Sequence[str] = ()
) -> dict[str, object]:
    settings = _build_settings(tmp_path, disabled=disabled)
    data = _build_data(scenario_tree, settings)
    return build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})


def _build_document(
    scenario_tree: dict[str, Path], tmp_path: Path, *, disabled: Sequence[str] = ()
) -> str:
    settings = _build_settings(tmp_path, disabled=disabled)
    data = _build_data(scenario_tree, settings)
    return build_html(data, settings=settings)


# --- reusable text checkers: acceptance criteria 1 to 4, each a small predicate function -------
#
# Each checker is called both on the real asset (below, expected to pass) and on a deliberately
# mutated copy of it (the "not vacuous" tests further down, expected to raise AssertionError).
# This is requirement 6's own justification made concrete: a check that can never fail is not a
# check.


def _check_build_layout_member_and_deep_copy(text: str) -> None:
    assignment = _dessem_dashboard_assignment(text)
    for member in _ELEVEN_MEMBERS_AFTER_TICKET_024:
        assert member in assignment, f"member '{member}' not found in the assignment block"
    assert "buildLayout" in assignment
    assert "JSON.parse(JSON.stringify(" in text


def _check_yaxis_title_from_unit(text: str) -> None:
    assert "chart[KEYS.UNIT]" in text


def _check_no_unit_literal(text: str, literal: str) -> None:
    assert literal not in text, f"forbidden unit literal {literal} found in dashboard.js"


def _check_difference_suffix_read_from_payload(text: str) -> None:
    assert "payload[KEYS.LABELS][KEYS.Y_AXIS_DIFFERENCE_SUFFIX]" in text


def _check_render_chart_single_place_layout(text: str) -> None:
    render_chart_body = _function_body(text, "renderChart")
    assert render_chart_body.count("buildLayout(") == 1
    assert "payload[KEYS.THEME][KEYS.LAYOUT]" not in render_chart_body
    assert text.count("Plotly.react(") == 1


def _check_no_forbidden_layout_token(text: str, token: str) -> None:
    assert token not in text


def _check_yaxis_assigned_in_exactly_one_function(text: str) -> None:
    bodies = _function_bodies(text)
    matching = [body for body in bodies if "yaxis" in body]
    assert len(matching) == 1, f"'yaxis' assigned in {len(matching)} functions, expected exactly 1"


def _keys_declaration_span(text: str) -> tuple[int, int]:
    """Return the (start, end) character span of the raw `const KEYS = Object.freeze({...});`
    declaration inside text.

    Shared by `_check_keys_entry_declared_once` below and `_duplicate_first` further down: the
    declaration carries no comment of its own (this file's only comments sit before it), so the
    same lookup finds identical content whether text has been comment-stripped first or not.
    """
    start = text.index("const KEYS")
    end = text.index("});", start) + len("});")
    return start, end


def _check_keys_entry_declared_once(text: str, quoted_value: str) -> None:
    """Assert a KEYS entry is declared once and never used as a raw index.

    Narrowed 2026-09-11 at the epic-03 boundary, for the same reason as the sibling check in
    tests/test_renderer_contract.py: counting the quoted literal over the raw file text conflated
    "a payload object is indexed with this literal", which is the contract, with "a string equal to
    a payload key appears anywhere, comments included", which is a naming coincidence. The broad
    form forced a workaround in two consecutive tickets. The contract is unchanged; only the
    incidental collisions are now allowed.
    """
    stripped = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL))
    start, end = _keys_declaration_span(stripped)
    keys_block = stripped[start:end]
    assert keys_block.count(quoted_value) == 1, (
        f"{quoted_value} must be declared exactly once in the KEYS object"
    )
    assert not re.search(rf"\[\s*{re.escape(quoted_value)}\s*\]", stripped), (
        f"{quoted_value} is used as a raw index; a payload key must be read only through KEYS"
    )


# --- acceptance criterion 1: buildLayout, its deep copy, KEYS.UNIT, and no unit literal --------


def test_dashboard_js_exposes_build_layout_with_deep_copy_and_unit_driven_title() -> None:
    text = _read_js_asset()
    _check_build_layout_member_and_deep_copy(text)
    _check_yaxis_title_from_unit(text)


@pytest.mark.parametrize("literal", _FORBIDDEN_UNIT_LITERALS)
def test_dashboard_js_contains_no_hardcoded_unit_literal(literal: str) -> None:
    text = _read_js_asset()
    _check_no_unit_literal(text, literal)


def test_fixture_payload_sin_units_are_three_distinct_strings_in_enabled_specs_order(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """The measurement that strengthens requirement 6: three units, not two, across five charts."""
    payload = _build_payload_from_scenario_tree(scenario_tree, tmp_path)
    charts = payload["charts"]  # type: ignore[index]

    observed_units = [charts[key]["unit"] for key in _SIN_CHART_KEYS]  # type: ignore[index]
    assert observed_units == list(_SIN_UNITS_IN_ORDER)
    assert frozenset(observed_units) == _THREE_DISTINCT_SIN_UNITS


# --- acceptance criterion 2: the Diferença suffix comes from the payload, never a literal ------


def test_dashboard_js_reads_difference_suffix_from_payload_and_is_pure_ascii() -> None:
    text = _read_js_asset()
    _check_difference_suffix_read_from_payload(text)
    assert " (diferença)" not in text
    assert text.isascii() is True


def test_fixture_payload_difference_suffix_equals_the_accented_portuguese_text(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    payload = _build_payload_from_scenario_tree(scenario_tree, tmp_path)
    assert payload["labels"]["y_axis_difference_suffix"] == " (diferença)"  # type: ignore[index]


# --- acceptance criterion 3: renderChart's single layout-assembly call, and no stray tokens ----


def test_dashboard_js_render_chart_calls_build_layout_exactly_once() -> None:
    text = _read_js_asset()
    _check_render_chart_single_place_layout(text)


@pytest.mark.parametrize("token", ["rangemode", "annotations", "hovertemplate"])
def test_dashboard_js_contains_no_forbidden_layout_token(token: str) -> None:
    text = _read_js_asset()
    _check_no_forbidden_layout_token(text, token)


def test_dashboard_js_assigns_yaxis_in_exactly_one_function() -> None:
    text = _read_js_asset()
    _check_yaxis_assigned_in_exactly_one_function(text)


# --- acceptance criterion 4: the KEYS contract, and the five SIN section headings --------------


@pytest.mark.parametrize("quoted_value", ['"unit"', '"labels"', '"y_axis_difference_suffix"'])
def test_dashboard_js_keys_declares_the_three_new_entries_exactly_once(quoted_value: str) -> None:
    text = _read_js_asset()
    _check_keys_entry_declared_once(text, quoted_value)


def test_document_sin_sections_carry_curated_headings_in_enabled_specs_order(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(scenario_tree, tmp_path)
    sections = _sin_sections(document)

    assert len(sections) == len(_SIN_TITLES_IN_ORDER)
    for section, expected_title in zip(sections, _SIN_TITLES_IN_ORDER, strict=True):
        assert _section_heading(section) == expected_title
        assert "<select" not in section
        assert section.count('<div class="plot" id="plot-') == 1


def test_document_sin_chart_keys_equal_the_five_default_enabled_charts(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(scenario_tree, tmp_path)
    sections = _sin_sections(document)

    observed_keys = set()
    for section in sections:
        match = re.search(r'data-chart="([^"]+)"', section)
        assert match is not None
        observed_keys.add(match.group(1))
    assert observed_keys == set(_SIN_CHART_KEYS)


def test_document_sin_sections_have_one_h2_and_no_subtitle_on_unmodified_fixture(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """METADADOS_OPERACAO.parquet writes nome_longo_variavel equal to the curated title for
    every SIN key on the unmodified fixture, so subtitle_html is empty for all five sections."""
    document = _build_document(scenario_tree, tmp_path)
    sections = _sin_sections(document)

    assert len(sections) == 5
    for section in sections:
        assert section.count("<h2>") == 1
        assert "chart-subtitle" not in section


def test_document_with_earmf_sin_disabled_has_four_sin_sections_and_unchanged_headings(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(scenario_tree, tmp_path, disabled=["EARMF_SIN"])
    sections = _sin_sections(document)

    assert len(sections) == 4
    assert 'id="chart-EARMF_SIN"' not in document
    remaining_titles = [_section_heading(section) for section in sections]
    expected_remaining = [
        title
        for key, title in zip(_SIN_CHART_KEYS, _SIN_TITLES_IN_ORDER, strict=True)
        if key != "EARMF_SIN"
    ]
    assert remaining_titles == expected_remaining


def test_build_html_with_every_enabled_chart_disabled_raises_config_error_naming_the_key(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """Finding 1 of the epic-03 boundary review: disabling the whole catalogue leaves
    enabled_specs() empty, and _level_nav/_chart_sections both index specs[0] unguarded. build_html
    must fail fast with a Portuguese ConfigError naming 'charts.disabled', never a bare IndexError
    that names neither the offending settings key nor its value."""
    assert len(_ALL_ENABLED_CHART_KEYS) == 23

    with pytest.raises(ConfigError, match=r"charts\.disabled"):
        _build_document(scenario_tree, tmp_path, disabled=_ALL_ENABLED_CHART_KEYS)


# --- acceptance criterion 5: entities, per-axis series lengths, and pre-rounded values ----------


def test_fixture_payload_sin_entries_have_the_sistema_interligado_entity_and_axis_lengths(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    payload = _build_payload_from_scenario_tree(scenario_tree, tmp_path)
    charts = payload["charts"]  # type: ignore[index]

    for chart_key in _SIN_CHART_KEYS:
        entry = charts[chart_key]  # type: ignore[index]
        assert entry["entities"] == _EXPECTED_ENTITIES  # type: ignore[index]
        series = entry["series"][""]  # type: ignore[index]
        for scenario in ("caso_a", "caso_b"):
            for axis_key, expected_length in _DECK_KEYS_AND_LENGTHS:
                assert len(series[scenario][axis_key]) == expected_length  # type: ignore[index]


def test_fixture_payload_ghid_sin_values_are_pre_rounded_to_two_decimals(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    payload = _build_payload_from_scenario_tree(scenario_tree, tmp_path)
    series = payload["charts"]["GHID_SIN"]["series"][""]  # type: ignore[index]

    for scenario in ("caso_a", "caso_b"):
        for axis_key, _length in _DECK_KEYS_AND_LENGTHS:
            for value in series[scenario][axis_key]:  # type: ignore[index]
                assert value is None or value == round(value, 2)


# --- non-vacuity proof: each asset assertion of criteria 1 to 4 can actually fail ---------------
#
# Requirement 6's own rationale, generalised: a static-text check that could never fail is not a
# check. Each case below mutates a copy of the real text (never the file on disk) and confirms
# the matching checker function trips on it, before the pristine text is used everywhere else in
# this module.


def _remove_first(text: str, target: str) -> str:
    assert target in text, f"expected substring {target!r} not present in the original text"
    return text.replace(target, "", 1)


def _duplicate_first(text: str, target: str) -> str:
    """Duplicate target's sole occurrence inside the KEYS declaration slice, never the whole file.

    Narrowed 2026-09-11 at the epic-03 boundary, for the same reason
    `_check_keys_entry_declared_once` was narrowed one layer up: asserting
    `text.count(target) == 1` over the raw file, as the original form did, breaks the instant an
    unrelated comment anywhere in the file mentions the same word -- exactly the collision class
    the sibling checker was narrowed away from. Scoping both the precondition and the mutation to
    the KEYS declaration slice removes that fragility.
    """
    start, end = _keys_declaration_span(text)
    keys_block = text[start:end]
    assert keys_block.count(target) == 1, (
        f"expected exactly one occurrence of {target!r} inside the KEYS declaration"
    )
    index_in_block = keys_block.index(target)
    mutated_block = (
        keys_block[: index_in_block + len(target)]
        + target
        + keys_block[index_in_block + len(target) :]
    )
    return text[:start] + mutated_block + text[end:]


def _remove_member_line(text: str, member: str) -> str:
    """Remove member's own `member: member,` line from window.DessemDashboard's assignment.

    Built from the member name via regex, not as a whitespace- and newline-pinned literal: the
    epic-03 boundary review judged the literal form over-pinned, since a reformat (different
    indentation, no trailing comma on the last member) would turn this non-vacuity mutation red
    at the mutation site itself rather than at the check it exists to exercise.
    """
    pattern = re.compile(
        rf"^[ \t]*{re.escape(member)}\s*:\s*{re.escape(member)}\s*,?\s*\n", re.MULTILINE
    )
    mutated, count = pattern.subn("", text, count=1)
    assert count == 1, f"expected exactly one '{member}: {member},' member line in dashboard.js"
    return mutated


def _append_as_comment(text: str, literal: str) -> str:
    return text + "\n// " + literal + "\n"


def _mutate_render_chart_duplicates_build_layout_call(text: str) -> str:
    target = "const layout = buildLayout(chartKey);"
    return text.replace(target, target + "\n    " + target, 1)


def _mutate_render_chart_reintroduces_inline_yaxis(text: str) -> str:
    target = "const layout = buildLayout(chartKey);"
    injected = target + '\n    layout.yaxis.title = { text: "x" };'
    return text.replace(target, injected, 1)


_NON_VACUITY_CASES: tuple[tuple[str, Callable[[str], str], Callable[[str], None]], ...] = (
    (
        "buildLayout member removed from window.DessemDashboard",
        lambda text: _remove_member_line(text, "buildLayout"),
        _check_build_layout_member_and_deep_copy,
    ),
    (
        "deep copy call removed",
        lambda text: _remove_first(text, "JSON.parse(JSON.stringify("),
        _check_build_layout_member_and_deep_copy,
    ),
    (
        "Y-axis title no longer reads chart[KEYS.UNIT]",
        lambda text: _remove_first(text, "chart[KEYS.UNIT]"),
        _check_yaxis_title_from_unit,
    ),
    (
        "MW literal inserted",
        lambda text: _append_as_comment(text, '"MW"'),
        lambda text: _check_no_unit_literal(text, '"MW"'),
    ),
    (
        "MWh literal inserted",
        lambda text: _append_as_comment(text, '"MWh"'),
        lambda text: _check_no_unit_literal(text, '"MWh"'),
    ),
    (
        "hm3 literal inserted",
        lambda text: _append_as_comment(text, '"hm3"'),
        lambda text: _check_no_unit_literal(text, '"hm3"'),
    ),
    (
        "m3/s literal inserted",
        lambda text: _append_as_comment(text, '"m3/s"'),
        lambda text: _check_no_unit_literal(text, '"m3/s"'),
    ),
    (
        "difference suffix expression removed",
        lambda text: _remove_first(text, "payload[KEYS.LABELS][KEYS.Y_AXIS_DIFFERENCE_SUFFIX]"),
        _check_difference_suffix_read_from_payload,
    ),
    (
        "renderChart calls buildLayout a second time",
        _mutate_render_chart_duplicates_build_layout_call,
        _check_render_chart_single_place_layout,
    ),
    (
        "renderChart reintroduces an inline layout[THEME][LAYOUT] copy",
        lambda text: _remove_first(text, "const layout = buildLayout(chartKey);").replace(
            "const traces = buildTraces(chartKey);",
            "const traces = buildTraces(chartKey);\n    const layout = "
            "JSON.parse(JSON.stringify(payload[KEYS.THEME][KEYS.LAYOUT]));",
            1,
        ),
        _check_render_chart_single_place_layout,
    ),
    (
        "rangemode token inserted",
        lambda text: _append_as_comment(text, "rangemode"),
        lambda text: _check_no_forbidden_layout_token(text, "rangemode"),
    ),
    (
        "annotations token inserted",
        lambda text: _append_as_comment(text, "annotations"),
        lambda text: _check_no_forbidden_layout_token(text, "annotations"),
    ),
    (
        "hovertemplate token inserted",
        lambda text: _append_as_comment(text, "hovertemplate"),
        lambda text: _check_no_forbidden_layout_token(text, "hovertemplate"),
    ),
    (
        "yaxis reintroduced in a second function",
        _mutate_render_chart_reintroduces_inline_yaxis,
        _check_yaxis_assigned_in_exactly_one_function,
    ),
    (
        '"unit" KEYS entry duplicated',
        lambda text: _duplicate_first(text, '"unit"'),
        lambda text: _check_keys_entry_declared_once(text, '"unit"'),
    ),
    (
        '"labels" KEYS entry duplicated',
        lambda text: _duplicate_first(text, '"labels"'),
        lambda text: _check_keys_entry_declared_once(text, '"labels"'),
    ),
    (
        '"y_axis_difference_suffix" KEYS entry duplicated',
        lambda text: _duplicate_first(text, '"y_axis_difference_suffix"'),
        lambda text: _check_keys_entry_declared_once(text, '"y_axis_difference_suffix"'),
    ),
)


@pytest.mark.parametrize(
    ("mutate", "check"),
    [(case[1], case[2]) for case in _NON_VACUITY_CASES],
    ids=[case[0] for case in _NON_VACUITY_CASES],
)
def test_asset_checks_are_not_vacuous(
    mutate: Callable[[str], str],
    check: Callable[[str], None],
) -> None:
    original_text = _read_js_asset()

    # The checker passes on the real, unmodified asset.
    check(original_text)

    # The same checker fails on a deliberately broken copy: the mutation never touches the
    # file on disk, so "restoring it" is simply never persisting the mutated string.
    broken_text = mutate(original_text)
    with pytest.raises(AssertionError):
        check(broken_text)
