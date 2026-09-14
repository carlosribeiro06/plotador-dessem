"""Tests for the view-mode toggle, the deck selector and the level navigation (ticket-023).

Epic decision E3-1 forbids executing any JavaScript in this suite, so the dashboard.js half of
this ticket is verified the same way tests/test_renderer_contract.py verifies ticket-022: as
static text, by regular expression. The builder.py half is verified against real documents built
from the scenario_tree fixture, following the settings-copy-in-tmp_path pattern of
tests/test_builder.py.
"""

from __future__ import annotations

import importlib.resources
import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import build_html
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.models.store import DashboardData
from fixtures_sintese import make_sintese_dir

_ASSETS_PACKAGE = "dessem_dashboard.dashboard.assets"
_JS_ASSET = "dashboard.js"
_CSS_ASSET = "dashboard.css"

_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# The five default-enabled SIN-group chart keys (dessem_dashboard.charts.specs.SPECS): disabling
# all of them removes the group entirely from enabled_specs, so the initially active level shifts
# to SBM, the group of the next entry in registration order.
_ALL_SIN_CHART_KEYS: tuple[str, ...] = (
    "GTER_SIN",
    "GHID_SIN",
    "GUNS_SIN",
    "EARMF_SIN",
    "VARMF_SIN",
)

_NAV_BUTTON_PATTERN = re.compile(
    r'<button type="button" data-group="([^"]+)" aria-pressed="([^"]+)">'
)
_SECTION_GROUP_PATTERN = re.compile(r'data-group="([^"]+)"')


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


def _build_single_deck_tree(tmp_path: Path) -> Path:
    """Build a one-scenario, one-deck sintese tree, for the single-deck selector test."""
    scenario_dir = tmp_path / "single_deck_source" / "caso_unico"
    make_sintese_dir(
        scenario_dir / "deck_um" / "sintese", first_stage_start=datetime(2024, 3, 3, tzinfo=UTC)
    )
    return scenario_dir


def _nav_slice(document: str) -> str:
    """Return the text between <nav id="level-nav"> and its following </nav>."""
    match = re.search(r'<nav id="level-nav">(.*?)</nav>', document, re.DOTALL)
    assert match is not None
    return match.group(1)


def _section_tags(document: str) -> list[str]:
    """Return every `<section class="chart" ...>` opening tag found in document, in order."""
    return re.findall(r'<section class="chart"[^>]*>', document)


def _group_of_section_tag(tag: str) -> str:
    """Return the data-group value of one chart section's opening tag."""
    match = _SECTION_GROUP_PATTERN.search(tag)
    assert match is not None
    return match.group(1)


def _read_js_asset() -> str:
    return (
        importlib.resources.files(_ASSETS_PACKAGE).joinpath(_JS_ASSET).read_text(encoding="utf-8")
    )


def _read_css_asset() -> str:
    return (
        importlib.resources.files(_ASSETS_PACKAGE).joinpath(_CSS_ASSET).read_text(encoding="utf-8")
    )


# --- acceptance criterion 1: initial_mode="encadeado" -----------------------------------------


def test_build_html_initial_mode_encadeado_marks_encadeado_pressed_and_disables_deck_selector(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document = build_html(data, settings=settings, initial_mode="encadeado")

    assert (
        '<button type="button" data-mode="encadeado" aria-pressed="true">Encadeado</button>'
        in document
    )
    assert (
        '<button type="button" data-mode="deck" aria-pressed="false">Por deck</button>' in document
    )
    assert '<select id="deck-selector" disabled>' in document


# --- acceptance criterion 2: initial_mode="deck" and an unknown initial_mode -------------------


def test_build_html_initial_mode_deck_marks_deck_pressed_enables_selector_and_rejects_unknown(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document = build_html(data, settings=settings, initial_mode="deck")

    assert (
        '<button type="button" data-mode="deck" aria-pressed="true">Por deck</button>' in document
    )
    select_match = re.search(
        r'<select id="deck-selector"([^>]*)>(.*?)</select>', document, re.DOTALL
    )
    assert select_match is not None
    assert "disabled" not in select_match.group(1)
    assert select_match.group(2) == (
        '<option value="03/03/2024">03/03/2024</option>'
        '<option value="04/03/2024">04/03/2024</option>'
    )

    with pytest.raises(ValueError, match="por-deck"):
        build_html(data, settings=settings, initial_mode="por-deck")


# --- acceptance criterion 3: level navigation aria-pressed matches the single unhidden group ---


def test_build_html_level_nav_aria_pressed_matches_the_single_unhidden_group(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    for initial_mode in ("deck", "encadeado"):
        document = build_html(data, settings=settings, initial_mode=initial_mode)

        pressed_by_group = dict(_NAV_BUTTON_PATTERN.findall(_nav_slice(document)))
        assert pressed_by_group["SIN"] == "true"
        for other_group in ("SBM", "SBP", "UHE", "UTE", "CUSTO", "TEMPO"):
            assert pressed_by_group[other_group] == "false"

        active_groups = {group for group, pressed in pressed_by_group.items() if pressed == "true"}
        assert active_groups == {"SIN"}

        section_tags = _section_tags(document)
        unhidden_groups = {
            _group_of_section_tag(tag) for tag in section_tags if not tag.endswith(" hidden>")
        }
        assert unhidden_groups == active_groups


# --- requirement 6: initial_mode drives only the documented, normalisable differences ----------


def test_build_html_initial_mode_deck_and_encadeado_differ_only_in_documented_attributes(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document_deck = build_html(data, settings=settings, initial_mode="deck")
    document_chained = build_html(data, settings=settings, initial_mode="encadeado")

    normalised_deck = (
        document_deck.replace('data-initial-mode="deck"', 'data-initial-mode=""')
        .replace('data-mode="deck" aria-pressed="true"', 'data-mode="deck" aria-pressed=""')
        .replace(
            'data-mode="encadeado" aria-pressed="false"', 'data-mode="encadeado" aria-pressed=""'
        )
        .replace('<select id="deck-selector">', '<select id="deck-selector" >')
    )
    normalised_chained = (
        document_chained.replace('data-initial-mode="encadeado"', 'data-initial-mode=""')
        .replace('data-mode="deck" aria-pressed="false"', 'data-mode="deck" aria-pressed=""')
        .replace(
            'data-mode="encadeado" aria-pressed="true"', 'data-mode="encadeado" aria-pressed=""'
        )
        .replace('<select id="deck-selector" disabled>', '<select id="deck-selector" >')
    )
    assert normalised_deck == normalised_chained


# --- charts.disabled removing every SIN chart shifts the active level to SBM ------------------


def test_build_html_charts_disabled_removing_all_sin_shifts_active_group_to_sbm(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path, disabled=_ALL_SIN_CHART_KEYS)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document = build_html(data, settings=settings)

    pressed_by_group = dict(_NAV_BUTTON_PATTERN.findall(_nav_slice(document)))
    assert "SIN" not in pressed_by_group
    assert pressed_by_group["SBM"] == "true"
    assert all(pressed == "false" for group, pressed in pressed_by_group.items() if group != "SBM")

    section_tags = _section_tags(document)
    assert all('data-group="SIN"' not in tag for tag in section_tags)
    unhidden_groups = {
        _group_of_section_tag(tag) for tag in section_tags if not tag.endswith(" hidden>")
    }
    assert unhidden_groups == {"SBM"}


# --- a single-deck tree still disables the selector in Encadeado mode -------------------------


def test_build_html_single_deck_tree_selector_holds_one_option_and_stays_disabled(
    tmp_path: Path,
) -> None:
    settings = _build_settings(tmp_path)
    scenario_dir = _build_single_deck_tree(tmp_path)
    data = _build_data([scenario_dir], settings=settings, reference="caso_unico")

    document = build_html(data, settings=settings, initial_mode="encadeado")

    select_match = re.search(r'<select id="deck-selector"[^>]*>(.*?)</select>', document, re.DOTALL)
    assert select_match is not None
    assert select_match.group(1).count("<option") == 1
    assert '<select id="deck-selector" disabled>' in document


# --- every level-nav group is backed by at least one chart section -----------------------------


def test_build_html_every_level_nav_group_appears_on_at_least_one_chart_section(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document = build_html(data, settings=settings)

    nav_groups = set(re.findall(r'data-group="([^"]+)"', _nav_slice(document)))
    section_groups = {_group_of_section_tag(tag) for tag in _section_tags(document)}
    assert nav_groups <= section_groups


# --- acceptance criterion 4: dashboard.js exposes the three new setters, nothing hash-related ---


def test_dashboard_js_exposes_three_new_setters_delegated_listeners_and_no_hash_routing() -> None:
    text = _read_js_asset()

    assignment_start = text.index("window.DessemDashboard")
    assignment_end = text.index("};", assignment_start) + len("};")
    assignment_text = text[assignment_start:assignment_end]
    for member in ("setMode", "setDeck", "setGroup"):
        assert member in assignment_text

    assert '"level-nav"' in text
    assert '"mode-toggle"' in text
    assert '"deck-selector"' in text
    assert 'addEventListener("click"' in text
    assert 'addEventListener("change"' in text
    assert "hidden" in text
    assert "disabled" in text

    for token in ("location.hash", "pushState", "popstate"):
        assert token not in text

    assert text.isascii() is True


# --- acceptance criterion 5: dashboard.css's disabled-selector rule and the no-color-literal rule


def test_dashboard_css_has_deck_selector_disabled_rule_and_no_color_literal() -> None:
    css_text = _read_css_asset()

    assert "#deck-selector:disabled" in css_text
    assert re.search(r"#[0-9A-Fa-f]{3,8}\b", css_text) is None
