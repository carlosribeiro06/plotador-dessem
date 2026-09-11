"""End-to-end tests for the submarket and interchange chart rendering (ticket-026).

Epic decision E3-1 forbids executing any JavaScript in this suite (`node` and `npm` are not
installed), so the `dashboard.js` half of this ticket -- `setEntity` and the delegated `change`
listener on `<main id="charts">` -- is verified the same way `tests/test_charts_sin.py` verifies
ticket-025: as static text. The `builder.py`/`payload.py` half is verified against real documents
and payloads built from the `scenario_tree` fixture, following the settings-copy-in-`tmp_path`
pattern of `tests/test_builder.py`.

Every option-list and heading assertion is scoped to one chart's own `<section class="chart">`
slice, keyed by its `data-chart` attribute: `Geração Térmica` titles both `GTER_SIN` and
`GTER_SBM`, `Geração Hidráulica` is both `GHID_SBM`'s title and `GHID_SIN`'s registry long name,
and `Volume Armazenado` titles both `VARMF_SIN` and `VARMF_SBM`, so an unscoped substring
assertion could be satisfied by the wrong chart. The slicing helpers below are written once here
for exactly that reason and are meant to be reused by Epic 4, which has 165-option plant selectors
and the same collision risk.
"""

from __future__ import annotations

import importlib.resources
import json
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import build_html
from dessem_dashboard.dashboard.payload import build_payload
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.models.store import DashboardData
from fixtures_sintese import make_sintese_dir

_ASSETS_PACKAGE = "dessem_dashboard.dashboard.assets"
_JS_ASSET = "dashboard.js"

_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# window.DessemDashboard's twelve members after ticket-025; this ticket adds a thirteenth,
# setEntity, verified separately so a later ticket adding a fourteenth cannot break this list.
_TWELVE_MEMBERS_AFTER_TICKET_025 = (
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
)

# The six SBM-group chart keys and the single SBP-group chart key (master plan Appendix A.6).
_SBM_CHART_KEYS: frozenset[str] = frozenset(
    {"MER_SBM", "GHID_SBM", "GTER_SBM", "GUNS_SBM", "CMO_SBM", "VARMF_SBM"}
)
_SBP_CHART_KEYS: frozenset[str] = frozenset({"INT_SBP"})

# Measured on the scenario_tree fixture (ticket-026 context): submarkets.include_fictitious is
# false, so every SBM chart's selector holds exactly these two options, in payload sort_key order.
_EXPECTED_SBM_OPTIONS: tuple[tuple[str, str], ...] = (
    ("1", "SE (SUDESTE)"),
    ("2", "S (SUL)"),
)

# INT_SBP keeps every pair regardless of submarkets.include_fictitious (ticket-018 requirement 7),
# so the default two-pair fixture already exercises the ordering; the fictitious pair itself is
# exercised separately, against a regenerated fixture, per requirement 8.
_EXPECTED_SBP_OPTIONS: tuple[tuple[str, str], ...] = (
    ("1-2", "SE (SUDESTE) para S (SUL)"),
    ("2-1", "S (SUL) para SE (SUDESTE)"),
)

# The fictitious-pair variant's pair_codes: build_scenario_tree's default, ((1, 2), (2, 1)),
# contains no fictitious code at all, so this is passed explicitly to make_sintese_dir
# (requirement 8) rather than relying on the scenario_tree fixture.
_FICTITIOUS_PAIR_CODES: tuple[tuple[int, int], ...] = ((1, 2), (2, 1), (1, 99))

# Deck-key and chained-key value counts (tests.conftest's _CHAINED_N_STAGES and the two decks'
# 48-stage half-hourly chaining window), reused from tests/test_charts_sin.py's own constant.
_DECK_KEYS_AND_LENGTHS: tuple[tuple[str, int], ...] = (
    ("03/03/2024", 50),
    ("04/03/2024", 50),
    ("encadeado", 96),
)

_SECTION_START = '<section class="chart"'
_SECTION_END = "</section>"

_DATA_CHART_PATTERN = re.compile(r'data-chart="([^"]+)"')
_OPTION_PATTERN = re.compile(r'<option value="([^"]*)">([^<]*)</option>')


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

    Depth tracking, not a lazy regex up to the first `}`: setEntity's own body is small, but the
    other functions this file mutates for the non-vacuity checks are not, and a naive match would
    stop at the first nested `{...}` object literal.
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


def _chart_section_slices(document: str) -> list[str]:
    """Split document into one slice per `<section class="chart" ...>...</section>` block.

    Sections are concatenated back to back by builder.py's `_chart_sections` with no separator
    and never nest, so the first `</section>` found after each `<section class="chart"` start is
    that same section's own close.
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


def _section_chart_key(section: str) -> str:
    match = _DATA_CHART_PATTERN.search(section)
    assert match is not None, f"no data-chart attribute found in section slice: {section[:120]!r}"
    return match.group(1)


def _sections_by_chart_key(document: str) -> dict[str, str]:
    """Return document's chart section slices keyed by their own `data-chart` attribute.

    Keying by `data-chart`, not by heading text, is what makes every assertion below immune to
    the curated-title collisions requirement 7 names: `data-chart` is unique per section by
    construction (`ChartRegistry.register` rejects a duplicate key), while several headings are
    shared by an SIN and an SBM chart.
    """
    return {_section_chart_key(section): section for section in _chart_section_slices(document)}


def _sections_by_group(document: str, group: str) -> list[str]:
    """Return document's chart section slices whose `data-group` equals group, in document order."""
    return [
        section for section in _chart_section_slices(document) if f'data-group="{group}"' in section
    ]


def _opening_tag(section: str) -> str:
    match = re.search(r'<section class="chart"[^>]*>', section)
    assert match is not None
    return match.group(0)


def _section_heading(section: str) -> str:
    match = re.search(r"<h2>([^<]*)</h2>", section)
    assert match is not None, f"no <h2> found in section slice: {section[:120]!r}"
    return match.group(1)


def _entity_label_text(section: str) -> str:
    # Attributes, not just the opening tag's exact text, are pinned here: builder.py's
    # _entity_selector_fragment now also emits a for="entity-{key}" attribute (finding 2 of the
    # epic-03 boundary review) so the label focuses its select, and this regex must not require
    # the opening tag to carry no attributes at all.
    match = re.search(r'<label class="entity-label"[^>]*>([^<]*)</label>', section)
    assert match is not None, f"no entity-label found in section slice: {section[:120]!r}"
    return match.group(1)


def _entity_selector_id(section: str) -> str:
    match = re.search(r'<select class="entity-selector" id="entity-([^"]+)">', section)
    assert match is not None, f"no entity-selector select found in section slice: {section[:120]!r}"
    return match.group(1)


def _entity_label_for_attribute(section: str) -> str:
    match = re.search(r'<label class="entity-label" for="entity-([^"]+)">', section)
    assert match is not None, (
        f"no for attribute found on the entity-label in section slice: {section[:120]!r}"
    )
    return match.group(1)


def _entity_options(section: str) -> list[tuple[str, str]]:
    """Return every `<option value="ID">LABEL</option>` pair inside section, in document order."""
    return _OPTION_PATTERN.findall(section)


def _nav_slice(document: str) -> str:
    """Return the text between `<nav id="level-nav">` and its following `</nav>`."""
    match = re.search(r'<nav id="level-nav">(.*?)</nav>', document, re.DOTALL)
    assert match is not None
    return match.group(1)


# --- settings/data/document builders, following tests/test_builder.py's pattern --------------


def _settings_dict(
    *, disabled: Sequence[str] = (), include_fictitious: bool = False
) -> dict[str, Any]:
    """Build a settings.json-shaped dict matching the repository's own values, with two knobs."""
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
        "submarkets": {"include_fictitious": include_fictitious, "fictitious_codes": [11, 99]},
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


def _build_settings(
    tmp_path: Path, *, disabled: Sequence[str] = (), include_fictitious: bool = False
) -> Settings:
    """Write settings.json under tmp_path and load it, exercising the real config path."""
    target = tmp_path / "settings.json"
    target.write_text(
        json.dumps(_settings_dict(disabled=disabled, include_fictitious=include_fictitious)),
        encoding="utf-8",
    )
    return load_settings(target)


def _build_data(paths: Sequence[Path], *, settings: Settings, reference: str) -> DashboardData:
    """Discover scenarios at paths and consolidate them into one DashboardData."""
    scenarios = discover_scenarios(list(paths))
    return build_dashboard_data(scenarios, settings=settings, reference=reference)


def _build_document(
    paths: Sequence[Path],
    tmp_path: Path,
    *,
    reference: str,
    disabled: Sequence[str] = (),
    include_fictitious: bool = False,
) -> str:
    settings = _build_settings(tmp_path, disabled=disabled, include_fictitious=include_fictitious)
    data = _build_data(paths, settings=settings, reference=reference)
    return build_html(data, settings=settings)


def _build_payload_dict(
    paths: Sequence[Path],
    tmp_path: Path,
    *,
    reference: str,
    disabled: Sequence[str] = (),
    include_fictitious: bool = False,
) -> dict[str, object]:
    settings = _build_settings(tmp_path, disabled=disabled, include_fictitious=include_fictitious)
    data = _build_data(paths, settings=settings, reference=reference)
    return build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})


def _build_fictitious_pair_tree(tmp_path: Path) -> Path:
    """One scenario, one deck, whose pair_codes carries the fictitious pair (1, 99).

    build_scenario_tree's default pair_codes, ((1, 2), (2, 1)), contains no fictitious code
    (requirement 8), so this calls make_sintese_dir directly, mirroring
    tests.test_renderer_controls._build_single_deck_tree's single-scenario, single-deck shape --
    a full document only needs one scenario to expose the entity-selector option lists this
    acceptance criterion inspects.
    """
    scenario_dir = tmp_path / "fictitious_pair_source" / "caso_unico"
    make_sintese_dir(
        scenario_dir / "deck_um" / "sintese",
        first_stage_start=datetime(2024, 3, 3, tzinfo=UTC),
        pair_codes=_FICTITIOUS_PAIR_CODES,
    )
    return scenario_dir


# --- reusable text checkers: the four asset assertions of acceptance criterion 1 --------------
#
# Each checker is called both on the real asset (below, expected to pass) and on a deliberately
# mutated copy of it (the "not vacuous" tests further down, expected to raise AssertionError).
# A check that could never fail is not a check, per the same rationale tests/test_charts_sin.py
# already applies to ticket-025.


def _check_set_entity_member(text: str) -> None:
    assignment = _dessem_dashboard_assignment(text)
    for member in _TWELVE_MEMBERS_AFTER_TICKET_025:
        assert member in assignment, f"member '{member}' not found in the assignment block"
    assert "setEntity" in assignment


def _check_set_entity_body(text: str) -> None:
    body = _function_body(text, "setEntity")
    assert "state.entities[chartKey]" in body
    assert "renderChart(" in body
    assert "renderActiveGroup(" not in body


def _check_entity_selector_and_closest(text: str) -> None:
    assert '".entity-selector"' in text
    assert 'closest("section.chart")' in text


def _check_pure_ascii(text: str) -> None:
    assert text.isascii() is True


# --- acceptance criterion 1: setEntity, the delegated listener, and pure ASCII -----------------


def test_dashboard_js_exposes_set_entity_beside_the_twelve_members_after_ticket_025() -> None:
    text = _read_js_asset()
    _check_set_entity_member(text)


def test_dashboard_js_set_entity_assigns_state_and_calls_render_chart_only() -> None:
    text = _read_js_asset()
    _check_set_entity_body(text)


def test_dashboard_js_contains_entity_selector_class_and_closest_section_chart() -> None:
    text = _read_js_asset()
    _check_entity_selector_and_closest(text)


def test_dashboard_js_is_pure_ascii() -> None:
    text = _read_js_asset()
    _check_pure_ascii(text)


def test_dashboard_js_registers_exactly_one_change_listener_on_charts_container() -> None:
    """Exactly one delegated `change` listener on the charts container, alongside the deck
    selector's own listener -- two `change` listeners in total.

    Split into two assertions, neither of which forbids a line break between the container
    lookup and the `addEventListener` call: the epic-03 boundary review judged the original
    single contiguous string over-pinned, since a reformat that moved `.addEventListener` onto
    its own line would turn this suite red at the mutation site rather than at the invariant it
    protects (exactly one delegated listener on the container).
    """
    text = _read_js_asset()

    assert text.count('addEventListener("change"') == 2
    assert 'document.querySelector("#charts")' in text


def test_renderer_contract_suite_still_passes_after_this_ticket_extends_the_asset() -> None:
    """A cheap, in-process proxy for the ticket's own `pytest tests/test_renderer_contract.py`
    instruction: the KEYS-contract regexes there scan the whole file text, so this proves the
    extension introduced no payload key literal outside KEYS without spawning a subprocess."""
    text = _read_js_asset()
    assert re.search(r"payload\s*\?\s*\.", text) is None
    assert re.search(r"[}\]]\s*=\s*payload\b", text) is None
    assert re.search(r"payload\[(?!\s*KEYS\.)", text) is None


# --- non-vacuity proof: each asset assertion of acceptance criterion 1 can actually fail -------


def _remove_first(text: str, target: str) -> str:
    assert target in text, f"expected substring {target!r} not present in the original text"
    return text.replace(target, "", 1)


def _mutate_function_body(text: str, function_name: str, transform: Callable[[str], str]) -> str:
    """Apply transform to function_name's own body slice, leaving the rest of text untouched.

    Mutating the extracted slice, not the whole text, matters here specifically: buildTraces
    also reads `state.entities[chartKey]`, so a whole-text `_remove_first` targeting that
    substring would strike buildTraces's read (the first occurrence in the file) instead of
    setEntity's write.
    """
    body = _function_body(text, function_name)
    mutated_body = transform(body)
    assert mutated_body != body, "transform did not change the function body"
    return text.replace(body, mutated_body, 1)


def _mutate_set_entity_drops_state_assignment(text: str) -> str:
    return _mutate_function_body(
        text, "setEntity", lambda body: body.replace("state.entities[chartKey] = entityId;", "", 1)
    )


def _mutate_set_entity_drops_render_chart_call(text: str) -> str:
    return _mutate_function_body(
        text, "setEntity", lambda body: body.replace("renderChart(chartKey);", "", 1)
    )


def _mutate_set_entity_adds_render_active_group_call(text: str) -> str:
    return _mutate_function_body(
        text,
        "setEntity",
        lambda body: body.replace(
            "renderChart(chartKey);", "renderChart(chartKey);\n    renderActiveGroup();", 1
        ),
    )


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


def _mutate_removes_set_entity_member(text: str) -> str:
    return _remove_member_line(text, "setEntity")


def _mutate_removes_entity_selector_literal(text: str) -> str:
    return _remove_first(text, '".entity-selector"')


def _mutate_removes_closest_section_chart(text: str) -> str:
    return _remove_first(text, 'closest("section.chart")')


def _mutate_inserts_non_ascii_character(text: str) -> str:
    return text + "\n// à\n"


_NON_VACUITY_CASES: tuple[tuple[str, Callable[[str], str], Callable[[str], None]], ...] = (
    (
        "setEntity member removed from window.DessemDashboard",
        _mutate_removes_set_entity_member,
        _check_set_entity_member,
    ),
    (
        "setEntity no longer assigns state.entities[chartKey]",
        _mutate_set_entity_drops_state_assignment,
        _check_set_entity_body,
    ),
    (
        "setEntity no longer calls renderChart",
        _mutate_set_entity_drops_render_chart_call,
        _check_set_entity_body,
    ),
    (
        "setEntity reintroduces a renderActiveGroup call",
        _mutate_set_entity_adds_render_active_group_call,
        _check_set_entity_body,
    ),
    (
        '".entity-selector" literal removed',
        _mutate_removes_entity_selector_literal,
        _check_entity_selector_and_closest,
    ),
    (
        'closest("section.chart") removed',
        _mutate_removes_closest_section_chart,
        _check_entity_selector_and_closest,
    ),
    (
        "non-ASCII character inserted",
        _mutate_inserts_non_ascii_character,
        _check_pure_ascii,
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

    # The same checker fails on a deliberately broken copy: the mutation never touches the file
    # on disk, so "restoring it" is simply never persisting the mutated string.
    broken_text = mutate(original_text)
    with pytest.raises(AssertionError):
        check(broken_text)


# --- acceptance criterion 2: the six SBM sections' selector, label and two submarket options ---


def test_document_sbm_sections_carry_selector_label_and_two_submarket_options(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    sections = _sections_by_chart_key(document)

    for chart_key in _SBM_CHART_KEYS:
        section = sections[chart_key]
        assert 'data-selector="SUBMARKET"' in section
        assert _entity_label_text(section) == "Submercado"
        assert _entity_selector_id(section) == chart_key
        # Finding 2 of the epic-03 boundary review: the label must be associated with its select
        # via a matching for/id pair, or a screen reader announces an unlabelled combobox.
        assert _entity_label_for_attribute(section) == chart_key
        options = _entity_options(section)
        assert options == list(_EXPECTED_SBM_OPTIONS)
        assert all(value not in {"11", "99"} for value, _label in options)


# --- acceptance criterion 3: the single SBP section's selector, heading, label and two pairs ---


def test_document_sbp_section_carries_selector_heading_label_and_two_pair_options(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    sections = _sections_by_chart_key(document)
    section = sections["INT_SBP"]

    assert 'data-selector="SUBMARKET_PAIR"' in section
    assert _section_heading(section) == "Intercâmbios"
    assert _entity_label_text(section) == "Par de submercados"
    assert _entity_selector_id(section) == "INT_SBP"
    assert _entity_label_for_attribute(section) == "INT_SBP"
    assert _entity_options(section) == list(_EXPECTED_SBP_OPTIONS)


# --- acceptance criterion 4: the regenerated fictitious-pair fixture, both include_fictitious ---


def test_document_fictitious_pair_selector_and_cmo_sbm_toggle_with_include_fictitious(
    tmp_path: Path,
) -> None:
    scenario_dir = _build_fictitious_pair_tree(tmp_path)

    document_excluding = _build_document(
        [scenario_dir], tmp_path, reference="caso_unico", include_fictitious=False
    )
    sections_excluding = _sections_by_chart_key(document_excluding)

    sbp_options_excluding = _entity_options(sections_excluding["INT_SBP"])
    assert len(sbp_options_excluding) == 3
    assert ("1-99", "SE (SUDESTE) para IV (IV)") in sbp_options_excluding

    cmo_options_excluding = _entity_options(sections_excluding["CMO_SBM"])
    assert {value for value, _label in cmo_options_excluding} == {"1", "2"}

    document_including = _build_document(
        [scenario_dir], tmp_path, reference="caso_unico", include_fictitious=True
    )
    sections_including = _sections_by_chart_key(document_including)

    cmo_options_including = _entity_options(sections_including["CMO_SBM"])
    assert len(cmo_options_including) == 4
    assert ("11", "FC (NOFICT1)") in cmo_options_including
    assert ("99", "IV (IV)") in cmo_options_including


# --- acceptance criterion 5: the payload's INT_SBP/CMO_SBM/MER_SBM shapes and units ------------


def test_fixture_payload_int_sbp_series_shape_and_cmo_mer_sbm_units(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    charts = payload["charts"]  # type: ignore[index]

    int_sbp_series = charts["INT_SBP"]["series"]  # type: ignore[index]
    assert set(int_sbp_series.keys()) == {"1-2", "2-1"}  # type: ignore[union-attr]
    for pair_series in int_sbp_series.values():  # type: ignore[union-attr]
        for scenario in ("caso_a", "caso_b"):
            for axis_key, expected_length in _DECK_KEYS_AND_LENGTHS:
                assert len(pair_series[scenario][axis_key]) == expected_length  # type: ignore[index]

    # One SBM chart's series shape too, mirroring INT_SBP's check above: both submarkets, both
    # scenarios, all three axis keys.
    cmo_sbm_series = charts["CMO_SBM"]["series"]  # type: ignore[index]
    assert set(cmo_sbm_series.keys()) == {"1", "2"}  # type: ignore[union-attr]
    for submarket_series in cmo_sbm_series.values():  # type: ignore[union-attr]
        for scenario in ("caso_a", "caso_b"):
            for axis_key, expected_length in _DECK_KEYS_AND_LENGTHS:
                assert len(submarket_series[scenario][axis_key]) == expected_length  # type: ignore[index]

    assert charts["CMO_SBM"]["unit"] == "R$/MWh"  # type: ignore[index]
    assert charts["MER_SBM"]["unit"] == "MW"  # type: ignore[index]


# --- additional Testing Requirements: group key sets, hidden state, and disabled catalogue -----


def test_document_sbm_and_sbp_data_group_key_sets_equal_expected(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )

    sbm_sections = _sections_by_group(document, "SBM")
    sbp_sections = _sections_by_group(document, "SBP")

    sbm_keys = {_section_chart_key(section) for section in sbm_sections}
    sbp_keys = {_section_chart_key(section) for section in sbp_sections}
    assert sbm_keys == _SBM_CHART_KEYS
    assert sbp_keys == _SBP_CHART_KEYS


def test_document_sbm_and_sbp_sections_are_hidden_on_default_fixture(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """SIN is the initially active group (ticket-021), so all seven SBM/SBP sections start hidden;
    the level navigation (ticket-023's setGroup) is what reveals them."""
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )

    sections = _sections_by_group(document, "SBM") + _sections_by_group(document, "SBP")
    assert len(sections) == 7
    for section in sections:
        assert _opening_tag(section).endswith(" hidden>")


def test_document_int_sbp_disabled_removes_sbp_group_and_section(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """Disabling INT_SBP removes the SBP group from the level navigation and its own chart
    section, proving the navigation is driven by the enabled catalogue, not a fixed group list."""
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]],
        tmp_path,
        reference="caso_a",
        disabled=["INT_SBP"],
    )

    assert 'id="chart-INT_SBP"' not in document
    assert 'data-group="SBP"' not in _nav_slice(document)
    assert _sections_by_group(document, "SBP") == []
