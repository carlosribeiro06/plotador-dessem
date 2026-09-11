"""End-to-end tests for the plant name and code filters (ticket-028).

Epic decision E3-1 forbids executing any JavaScript in this suite (`node` and `npm` are not
installed), so the `dashboard.js` half of this ticket -- `applyPlantFilter`, its normalisation
helper and the delegated `input` listener -- is verified the same way
`tests/test_charts_submarket.py` verifies ticket-026: as static text, with function-body
isolation and break-then-restore mutations. The `builder.py` half is verified against real
documents built from the `scenario_tree` fixture, following the settings-copy-in-`tmp_path`
pattern of `tests/test_builder.py`.
`dashboard.css` is verified against `theme.css_root_block()`'s eight declared custom properties,
following `tests/test_theme.py`'s subset check.

Every section-scoped assertion below reads through the shared slicing helpers of
`tests/dashboard_document.py` (requirement 10) rather than through a private copy: this is the
third module ticket-027 identified as reusing them, after `tests/test_charts_hydro.py`.
"""

from __future__ import annotations

import importlib.resources
import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from dashboard_document import sections_by_chart_key
from dessem_dashboard.charts.registry import EntitySelector
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import PLANT_SELECTORS, build_html
from dessem_dashboard.dashboard.theme import css_root_block
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.models.store import DashboardData

_ASSETS_PACKAGE = "dessem_dashboard.dashboard.assets"
_JS_ASSET = "dashboard.js"
_CSS_ASSET = "dashboard.css"

_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)
_DOCS_CHECKLIST = Path(__file__).resolve().parent.parent / "docs" / "checklist-manual-dashboard.md"

# The nine plant chart keys of the default catalogue, in enabled_specs order: the eight UHE
# charts plus GTER_UTE (Background: "Nine sections carry a plant selector on the default
# catalogue").
_PLANT_CHART_KEYS: tuple[str, ...] = (
    "GHID_UHE",
    "QTUR_UHE",
    "QVER_UHE",
    "VARMF_UHE",
    "VARPF_UHE",
    "QDEF_UHE",
    "QAFL_UHE",
    "QINC_UHE",
    "GTER_UTE",
)

_NAME_PLACEHOLDER = "Filtrar por nome"
_CODE_PLACEHOLDER = "Filtrar por código"
_EMPTY_MESSAGE = "Nenhuma usina corresponde ao filtro"

# window.DessemDashboard's thirteen members after ticket-026 (epic-03-learnings section 7); this
# ticket adds a fourteenth, applyPlantFilter, checked separately so a later ticket adding a
# fifteenth cannot break this list.
_THIRTEEN_MEMBERS_AFTER_TICKET_026: tuple[str, ...] = (
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
)


# --- settings/data/document builders, following tests/test_builder.py's pattern ---------------


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


def _build_document(
    paths: Sequence[Path], tmp_path: Path, *, reference: str, disabled: Sequence[str] = ()
) -> str:
    settings = _build_settings(tmp_path, disabled=disabled)
    data = _build_data(paths, settings=settings, reference=reference)
    return build_html(data, settings=settings)


# --- markup checker: acceptance criterion 1, reused by the non-vacuity proof -------------------


def _check_plant_filter_markup(document: str) -> None:
    """Assert the filter fragment on every plant section, and its absence everywhere else.

    A single checker for both the positive and the negative case, so that mutating the document
    (the non-vacuity proof below) and the direct test below share one definition of "correct".
    """
    sections = sections_by_chart_key(document)
    plant_keys = set(_PLANT_CHART_KEYS)
    assert plant_keys <= set(sections)

    for key, section in sections.items():
        if key not in plant_keys:
            assert "plant-filter" not in section, f"{key} must carry no plant-filter markup"
            continue

        assert section.count('class="plant-filters"') == 1, (
            f"{key} must carry exactly one plant-filters fragment"
        )
        assert section.count('class="plant-filter"') == 2, f"{key} must carry two filter inputs"
        assert f'id="filter-name-{key}"' in section
        assert f'id="filter-code-{key}"' in section
        assert 'data-filter="name"' in section
        assert 'data-filter="code"' in section
        assert f'placeholder="{_NAME_PLACEHOLDER}"' in section
        assert f'placeholder="{_CODE_PLACEHOLDER}"' in section
        assert _EMPTY_MESSAGE in section


# --- acceptance criterion 1: markup on the nine plant sections, absent elsewhere ---------------


def test_plant_sections_carry_exactly_one_filter_fragment_and_non_plant_sections_do_not(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    _check_plant_filter_markup(document)


def test_plant_filter_markup_check_is_not_vacuous_without_data_filter_code(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """Suggested Approach step 7's builder.py mutation: removing `data-filter="code"` from a
    copy of the document must fail acceptance criterion 1, proving it is not vacuous."""
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    _check_plant_filter_markup(document)

    mutated = document.replace('data-filter="code"', "", 1)
    with pytest.raises(AssertionError):
        _check_plant_filter_markup(mutated)


def test_plant_selectors_constant_holds_exactly_the_two_plant_selector_values() -> None:
    expected = frozenset({EntitySelector.HYDRO_PLANT.value, EntitySelector.THERMAL_PLANT.value})
    assert expected == PLANT_SELECTORS


def test_plant_chart_keys_carrying_filter_equal_the_eight_uhe_keys_plus_gter_ute(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """A fragment rendered for the wrong selector fails here: the set is computed from the
    document itself, not copied from the constant above."""
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    sections = sections_by_chart_key(document)
    carrying_filter = {key for key, section in sections.items() if "plant-filters" in section}
    assert carrying_filter == set(_PLANT_CHART_KEYS)


def test_document_holds_exactly_eighteen_plant_filter_class_occurrences(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    assert document.count('class="plant-filter"') == 18


def test_disabling_gter_ute_leaves_sixteen_plant_filter_occurrences_and_no_gter_ute_inputs(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]],
        tmp_path,
        reference="caso_a",
        disabled=["GTER_UTE"],
    )
    assert document.count('class="plant-filter"') == 16
    assert "filter-name-GTER_UTE" not in document
    assert "filter-code-GTER_UTE" not in document


def test_filter_fragment_sits_after_the_entity_select_and_before_the_plot_div(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    sections = sections_by_chart_key(document)
    for key in _PLANT_CHART_KEYS:
        section = sections[key]
        select_index = section.index('<select class="entity-selector"')
        filters_index = section.index('class="plant-filters"')
        plot_index = section.index('<div class="plot"')
        assert select_index < filters_index < plot_index, (
            f"{key}: filter fragment must sit between the entity select and the plot div"
        )


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


def _input_listener_body(text: str) -> str:
    """Return the callback body of the delegated `input` listener on `#charts`, brace-matched.

    Not a named `function` declaration -- like ticket-026's `change` listener, it is anonymous --
    so this walks forward from `addEventListener("input", ...)` rather than reusing
    `_function_body`, which only matches a named declaration.
    """
    start = text.index('addEventListener("input"')
    open_brace = text.index("{", start)
    depth = 0
    index = open_brace
    while True:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                break
        index += 1
    return text[start : index + 1]


def _remove_first(text: str, target: str) -> str:
    assert target in text, f"expected substring {target!r} not present in the original text"
    return text.replace(target, "", 1)


def _mutate_function_body(text: str, function_name: str, transform: Callable[[str], str]) -> str:
    """Apply transform to function_name's own body slice, leaving the rest of text untouched."""
    body = _function_body(text, function_name)
    mutated_body = transform(body)
    assert mutated_body != body, "transform did not change the function body"
    return text.replace(body, mutated_body, 1)


def _remove_member_line(text: str, member: str) -> str:
    """Remove member's own `member: member,` line from window.DessemDashboard's assignment."""
    pattern = re.compile(
        rf"^[ \t]*{re.escape(member)}\s*:\s*{re.escape(member)}\s*,?\s*\n", re.MULTILINE
    )
    mutated, count = pattern.subn("", text, count=1)
    assert count == 1, f"expected exactly one '{member}: {member},' member line in dashboard.js"
    return mutated


# --- reusable text checkers: each of acceptance criteria 2 and 3 ------------------------------


def _check_apply_plant_filter_member(text: str) -> None:
    assignment = _dessem_dashboard_assignment(text)
    for member in _THIRTEEN_MEMBERS_AFTER_TICKET_026:
        assert member in assignment, f"member '{member}' not found in the assignment block"
    assert "applyPlantFilter" in assignment


def _check_dashboard_js_required_tokens(text: str) -> None:
    for token in (
        '".plant-filter"',
        'addEventListener("input"',
        'closest("section.chart")',
        'normalize("NFD")',
        "toUpperCase()",
        "[\\u0300-\\u036f]",
    ):
        assert token in text, f"required token {token!r} not found in dashboard.js"


def _check_input_listener_resolves_via_closest_chart(text: str) -> None:
    body = _input_listener_body(text)
    assert '".plant-filter"' in body
    assert 'closest(".chart")' in body
    assert "dataset.chart" in body
    assert "applyPlantFilter(" in body


def _check_apply_plant_filter_body(text: str) -> None:
    body = _function_body(text, "applyPlantFilter")
    assert "option.hidden" in body
    assert body.count("setEntity(") == 1
    assert ".filter-empty" in body
    assert ".hidden = matchingValues.length > 0" in body


def _check_no_rebuild_or_debounce_tokens(text: str) -> None:
    for token in (
        "innerHTML",
        "createElement",
        "removeChild",
        "new RegExp",
        "setTimeout",
        "Filtrar",
        "Nenhuma",
    ):
        assert token not in text, f"forbidden token {token!r} found in dashboard.js"


def _check_pure_ascii_and_single_freeze(text: str) -> None:
    assert text.isascii() is True
    assert text.count("Object.freeze({") == 1


# --- direct tests over the real, unmodified asset ----------------------------------------------


def test_dashboard_js_exposes_apply_plant_filter_beside_the_thirteen_members_after_ticket_026() -> (
    None
):
    text = _read_js_asset()
    _check_apply_plant_filter_member(text)


def test_apply_plant_filter_appears_once_as_declaration_and_once_in_the_assignment() -> None:
    text = _read_js_asset()
    assert text.count("function applyPlantFilter(") == 1
    assert text.count("applyPlantFilter: applyPlantFilter,") == 1


def test_dashboard_js_contains_required_filter_tokens() -> None:
    text = _read_js_asset()
    _check_dashboard_js_required_tokens(text)


def test_dashboard_js_input_listener_resolves_chart_via_closest_chart_and_dataset() -> None:
    text = _read_js_asset()
    _check_input_listener_resolves_via_closest_chart(text)


def test_apply_plant_filter_body_hides_options_calls_set_entity_once_and_toggles_message() -> None:
    text = _read_js_asset()
    _check_apply_plant_filter_body(text)


def test_dashboard_js_never_rebuilds_options_or_debounces_or_leaks_portuguese_strings() -> None:
    text = _read_js_asset()
    _check_no_rebuild_or_debounce_tokens(text)


def test_dashboard_js_is_pure_ascii_and_freezes_exactly_one_object() -> None:
    text = _read_js_asset()
    _check_pure_ascii_and_single_freeze(text)


def test_dashboard_js_registers_exactly_one_input_listener_and_change_listener_still_intact() -> (
    None
):
    text = _read_js_asset()
    assert text.count('addEventListener("input"') == 1
    assert text.count('addEventListener("change"') == 2


def test_dashboard_js_never_accesses_payload_and_adds_no_keys_entry() -> None:
    """This ticket reads no payload field at all (Background); a KEYS-contract regression here
    would mean applyPlantFilter started reading the payload, which it must never do."""
    text = _read_js_asset()
    body = _function_body(text, "applyPlantFilter")
    assert "payload" not in body
    assert "KEYS." not in body


# --- non-vacuity proof: every checker above can actually fail -----------------------------------


def _mutate_removes_apply_plant_filter_member(text: str) -> str:
    return _remove_member_line(text, "applyPlantFilter")


def _mutate_apply_plant_filter_drops_option_hidden(text: str) -> str:
    return _mutate_function_body(
        text, "applyPlantFilter", lambda body: body.replace("option.hidden = !isMatch;", "", 1)
    )


def _mutate_apply_plant_filter_calls_set_entity_twice(text: str) -> str:
    call = "setEntity(chartKey, matchingValues[0]);"
    return _mutate_function_body(
        text, "applyPlantFilter", lambda body: body.replace(call, call + "\n      " + call, 1)
    )


def _mutate_apply_plant_filter_drops_filter_empty_assignment(text: str) -> str:
    return _mutate_function_body(
        text,
        "applyPlantFilter",
        lambda body: body.replace(
            'section.querySelector(".filter-empty").hidden = matchingValues.length > 0;', "", 1
        ),
    )


def _mutate_input_listener_drops_closest_chart(text: str) -> str:
    return _remove_first(text, 'closest(".chart")')


def _mutate_inserts_non_ascii_character(text: str) -> str:
    return text + "\n// à\n"


def _mutate_inserts_second_object_freeze(text: str) -> str:
    return text + "\nconst DEBUG = Object.freeze({});\n"


_NON_VACUITY_CASES: tuple[tuple[str, Callable[[str], str], Callable[[str], None]], ...] = (
    (
        "applyPlantFilter member removed from window.DessemDashboard",
        _mutate_removes_apply_plant_filter_member,
        _check_apply_plant_filter_member,
    ),
    (
        "applyPlantFilter no longer assigns option.hidden",
        _mutate_apply_plant_filter_drops_option_hidden,
        _check_apply_plant_filter_body,
    ),
    (
        "applyPlantFilter calls setEntity twice instead of at most once",
        _mutate_apply_plant_filter_calls_set_entity_twice,
        _check_apply_plant_filter_body,
    ),
    (
        "applyPlantFilter no longer toggles the filter-empty message",
        _mutate_apply_plant_filter_drops_filter_empty_assignment,
        _check_apply_plant_filter_body,
    ),
    (
        '".plant-filter" literal removed',
        lambda text: _remove_first(text, '".plant-filter"'),
        _check_dashboard_js_required_tokens,
    ),
    (
        'addEventListener("input" literal removed',
        lambda text: _remove_first(text, 'addEventListener("input"'),
        _check_dashboard_js_required_tokens,
    ),
    (
        'closest("section.chart") literal removed',
        lambda text: _remove_first(text, 'closest("section.chart")'),
        _check_dashboard_js_required_tokens,
    ),
    (
        'normalize("NFD") literal removed',
        lambda text: _remove_first(text, 'normalize("NFD")'),
        _check_dashboard_js_required_tokens,
    ),
    (
        "toUpperCase() literal removed",
        lambda text: _remove_first(text, "toUpperCase()"),
        _check_dashboard_js_required_tokens,
    ),
    (
        "escaped combining-mark range removed",
        lambda text: _remove_first(text, "[\\u0300-\\u036f]"),
        _check_dashboard_js_required_tokens,
    ),
    (
        'closest(".chart") removed from the input listener',
        _mutate_input_listener_drops_closest_chart,
        _check_input_listener_resolves_via_closest_chart,
    ),
    (
        "non-ASCII character inserted",
        _mutate_inserts_non_ascii_character,
        _check_pure_ascii_and_single_freeze,
    ),
    (
        "a second Object.freeze({ introduced",
        _mutate_inserts_second_object_freeze,
        _check_pure_ascii_and_single_freeze,
    ),
)


@pytest.mark.parametrize(
    ("mutate", "check"),
    [(case[1], case[2]) for case in _NON_VACUITY_CASES],
    ids=[case[0] for case in _NON_VACUITY_CASES],
)
def test_dashboard_js_checks_are_not_vacuous(
    mutate: Callable[[str], str], check: Callable[[str], None]
) -> None:
    original_text = _read_js_asset()

    # The checker passes on the real, unmodified asset.
    check(original_text)

    # The same checker fails on a deliberately broken copy, never persisted to disk.
    broken_text = mutate(original_text)
    with pytest.raises(AssertionError):
        check(broken_text)


def test_no_rebuild_check_is_not_vacuous_with_an_injected_filtrar_literal() -> None:
    """Suggested Approach step 7's dashboard.js mutation: inserting "Filtrar" into a copy of the
    asset must fail acceptance criterion 3, proving it is not vacuous."""
    text = _read_js_asset()
    _check_no_rebuild_or_debounce_tokens(text)

    mutated = text + "\n// Filtrar\n"
    with pytest.raises(AssertionError):
        _check_no_rebuild_or_debounce_tokens(mutated)


# --- acceptance criterion 4: dashboard.css's five selectors and property discipline ------------


def _read_css_asset() -> str:
    return (
        importlib.resources.files(_ASSETS_PACKAGE).joinpath(_CSS_ASSET).read_text(encoding="utf-8")
    )


def test_dashboard_css_declares_the_five_plant_filter_selectors_with_no_color_or_import() -> None:
    css_text = _read_css_asset()

    for selector in (
        ".plant-filters",
        ".filter-label",
        "input.plant-filter",
        ".filter-empty",
        "option[hidden]",
    ):
        assert selector in css_text, f"selector {selector!r} not found in dashboard.css"

    assert re.search(r"#[0-9A-Fa-f]{3,8}\b", css_text) is None
    assert "@import" not in css_text


def test_dashboard_css_plant_filter_rules_reference_only_theme_declared_properties() -> None:
    css_text = _read_css_asset()
    declared = set(re.findall(r"(--ons-[a-z-]+):", css_root_block()))
    referenced = set(re.findall(r"var\((--ons-[a-z-]+)\)", css_text))

    assert referenced != set()
    assert referenced <= declared


def test_css_subset_check_is_not_vacuous_with_an_undeclared_custom_property() -> None:
    """Suggested Approach step 7's dashboard.css mutation: adding `var(--ons-missing)` to a copy
    of the CSS must fail acceptance criterion 4, proving it is not vacuous."""
    css_text = _read_css_asset()
    declared = set(re.findall(r"(--ons-[a-z-]+):", css_root_block()))
    referenced = set(re.findall(r"var\((--ons-[a-z-]+)\)", css_text))
    assert referenced <= declared

    mutated = css_text + "\n.plant-filters { color: var(--ons-missing); }\n"
    mutated_referenced = set(re.findall(r"var\((--ons-[a-z-]+)\)", mutated))
    assert not (mutated_referenced <= declared)


# --- acceptance criterion 5: the manual checklist replacement ----------------------------------


def _read_checklist() -> str:
    return _DOCS_CHECKLIST.read_text(encoding="utf-8")


def test_checklist_replaces_the_placeholder_with_plant_filter_steps() -> None:
    text = _read_checklist()

    assert "Not yet written" not in text
    assert "Usinas hidrelétricas" in text
    assert _NAME_PLACEHOLDER in text
    assert _CODE_PLACEHOLDER in text
    assert _EMPTY_MESSAGE in text
