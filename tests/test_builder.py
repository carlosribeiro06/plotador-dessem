"""Tests for dessem_dashboard.dashboard.builder."""

from __future__ import annotations

import base64
import importlib.resources
import json
import logging
import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from string import Template
from types import MappingProxyType
from typing import Any

import pandas as pd
import plotly.offline  # type: ignore[import-untyped]
import pytest

from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import build_html, write_dashboard
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.data.registries import Registries
from dessem_dashboard.errors import ConfigError
from dessem_dashboard.models.store import DashboardData, EntityRef, TimeAxis

_BUILDER_LOGGER_NAME = "dessem_dashboard.dashboard.builder"
_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# Measured on tests.conftest.scenario_tree consolidated with settings matching the repository's
# own settings.json and reference="caso_a": 23 enabled charts, of which 5 are in group SIN.
_ENABLED_CHART_COUNT = 23
_SIN_CHART_COUNT = 5
_LEVEL_NAV_GROUP_COUNT = 6
_MIN_DOCUMENT_LENGTH = 4_300_000
_MAX_DOCUMENT_LENGTH = 5_242_880

_HAND_BUILT_DATE = date(2024, 3, 3)
_HAND_BUILT_DECK_KEY = "03/03/2024"
_CHAINED_KEY = "encadeado"

_EXPECTED_TEMPLATE_IDENTIFIERS = frozenset(
    {
        "title",
        "css",
        "initial_mode",
        "logo_data_uri",
        "level_nav",
        "mode_toggle",
        "deck_selector",
        "value_toggle",
        "reference",
        "warnings_section",
        "chart_sections",
        "footer",
        "plotly_js",
        "payload_json",
        "dashboard_js",
    }
)


def _settings_dict(
    *, decimals: int = 2, disabled: Sequence[str] = (), logo_file: str | None = None
) -> dict[str, Any]:
    """Build a settings.json-shaped dict matching the repository's own values, with knobs.

    logo_file defaults to the real repository logo's absolute path, so every test that does not
    exercise the logo error paths gets a document that actually embeds a valid image, exactly as
    the first acceptance criterion requires.
    """
    return {
        "project": "dessem-dashboard",
        "paths": {
            "output_dir": "output",
            "log_dir": "logs",
            "logo_file": logo_file if logo_file is not None else str(_REPO_LOGO),
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
            "decimals": decimals,
            "size_warning_mb": 50,
        },
        "charts": {"disabled": list(disabled)},
    }


def _build_settings(
    tmp_path: Path,
    *,
    decimals: int = 2,
    disabled: Sequence[str] = (),
    logo_file: str | None = None,
) -> Settings:
    """Write settings.json under tmp_path and load it, so tests exercise the real config path."""
    target = tmp_path / "settings.json"
    target.write_text(
        json.dumps(_settings_dict(decimals=decimals, disabled=disabled, logo_file=logo_file)),
        encoding="utf-8",
    )
    return load_settings(target)


def _build_data(paths: Sequence[Path], *, settings: Settings, reference: str) -> DashboardData:
    """Discover scenarios at paths and consolidate them into one DashboardData."""
    scenarios = discover_scenarios(list(paths))
    return build_dashboard_data(scenarios, settings=settings, reference=reference)


def _empty_registries() -> Registries:
    """Build a Registries with every mapping empty, for hand-built stores that never read a file."""
    return Registries(
        hydro=MappingProxyType({}),
        thermal=MappingProxyType({}),
        submarkets=MappingProxyType({}),
        rees=MappingProxyType({}),
        variables=MappingProxyType({}),
    )


def _hand_built_data() -> DashboardData:
    """Build a minimal one-stage, one-scenario store, sufficient for build_html to succeed.

    build_payload's axes step only needs the deck and chained axes registered; it does not
    require any chart to hold series or scalars, so this minimal store is enough to exercise
    build_html's logo handling and escaping without the cost of a full scenario_tree fixture.
    """
    data = DashboardData(
        scenarios=("caso_a",),
        reference="caso_a",
        deck_dates=(_HAND_BUILT_DATE,),
        registries=_empty_registries(),
    )
    start = pd.Timestamp("2024-03-03T00:00:00", tz="UTC")
    axis = TimeAxis(key=_HAND_BUILT_DECK_KEY, starts=(start,), durations_hours=(0.5,))
    data.set_deck_axis(_HAND_BUILT_DATE, axis)
    data.set_chained_axis(TimeAxis(key=_CHAINED_KEY, starts=(start,), durations_hours=(0.5,)))
    return data


def _rewrite_metadados_long_name(
    sintese_dir: Path, *, chart_key: str, long_name: str | None
) -> None:
    """Overwrite nome_longo_variavel for chart_key's row of one deck's METADADOS_OPERACAO file."""
    path = sintese_dir / "METADADOS_OPERACAO.parquet"
    frame = pd.read_parquet(path, engine="pyarrow")
    mask = frame["chave"] == chart_key
    frame.loc[mask, "nome_longo_variavel"] = long_name
    frame.to_parquet(path, index=False)


def _rewrite_metadados_everywhere(
    scenario_tree: dict[str, Path], *, chart_key: str, long_name: str | None
) -> None:
    """Apply _rewrite_metadados_long_name to every deck of every scenario in scenario_tree."""
    for scenario_dir in scenario_tree.values():
        for deck_dir in sorted(scenario_dir.iterdir()):
            _rewrite_metadados_long_name(
                deck_dir / "sintese", chart_key=chart_key, long_name=long_name
            )


def _section_tags(document: str) -> list[str]:
    """Return every `<section class="chart" ...>` opening tag found in document, in order."""
    return re.findall(r'<section class="chart"[^>]*>', document)


# --- acceptance criterion 1: plotly, logo, script order and document size ----------------------


def test_build_html_scenario_tree_embeds_plotly_logo_and_orders_scripts_within_size_range(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document = build_html(data, settings=settings)

    assert plotly.offline.get_plotlyjs() in document

    logo_bytes = settings.paths.logo_file.read_bytes()
    expected_logo = f"data:image/png;base64,{base64.b64encode(logo_bytes).decode()}"
    assert expected_logo in document

    plotly_index = document.index('<script id="plotly-js">')
    payload_index = document.index('<script id="dashboard-payload"')
    dashboard_js_index = document.index('<script id="dashboard-js">')
    assert plotly_index < payload_index < dashboard_js_index

    assert _MIN_DOCUMENT_LENGTH <= len(document) <= _MAX_DOCUMENT_LENGTH


# --- acceptance criterion 2: no external reference outside the plotly-js block -----------------


def test_build_html_scenario_tree_excising_plotly_block_leaves_no_external_reference(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document = build_html(data, settings=settings)

    plotly_open = document.index('<script id="plotly-js">')
    plotly_close = document.index("</script>", plotly_open) + len("</script>")
    remainder = document[:plotly_open] + document[plotly_close:]

    assert "http://" not in remainder
    assert "https://" not in remainder
    assert "<link" not in remainder
    assert "@import" not in remainder

    references = re.findall(r'(?:src|href)="([^"]*)"', remainder)
    assert references, "expected at least the logo's src attribute in remainder"
    assert all(reference.startswith(("data:", "#")) for reference in references)


# --- acceptance criterion 3: chart sections, hidden state and entity selectors ------------------


def test_build_html_scenario_tree_chart_sections_hidden_state_and_entity_selectors(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document = build_html(data, settings=settings)

    section_tags = _section_tags(document)
    assert len(section_tags) == _ENABLED_CHART_COUNT

    sin_tags = [tag for tag in section_tags if 'data-group="SIN"' in tag]
    other_tags = [tag for tag in section_tags if 'data-group="SIN"' not in tag]
    assert len(sin_tags) == _SIN_CHART_COUNT
    assert len(other_tags) == _ENABLED_CHART_COUNT - _SIN_CHART_COUNT
    assert all(not tag.endswith(" hidden>") for tag in sin_tags)
    assert all(tag.endswith(" hidden>") for tag in other_tags)

    cmo_tag = next(tag for tag in section_tags if 'id="chart-CMO_SBM"' in tag)
    assert 'data-selector="SUBMARKET"' in cmo_tag
    select_match = re.search(
        r'<select class="entity-selector" id="entity-CMO_SBM">(.*?)</select>', document, re.DOTALL
    )
    assert select_match is not None
    assert select_match.group(1) == (
        '<option value="1">SE (SUDESTE)</option><option value="2">S (SUL)</option>'
    )

    ghid_sin_match = re.search(
        r'<section class="chart" id="chart-GHID_SIN".*?</section>', document, re.DOTALL
    )
    assert ghid_sin_match is not None
    assert "<select" not in ghid_sin_match.group(0)
    assert '<p class="chart-subtitle"' not in ghid_sin_match.group(0)


# --- acceptance criterion 4: header, footer, reference, level nav and warnings -----------------


def test_build_html_scenario_tree_header_footer_reference_and_level_nav_without_warnings(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document = build_html(data, settings=settings)

    assert '<h1 id="title">Comparação de Resultados do DESSEM</h1>' in document
    assert "Gerência de Ferramentas Energéticas - FEN" in document

    reference_match = re.search(r'<span id="reference-label">([^<]*)</span>', document)
    assert reference_match is not None
    assert reference_match.group(1) == "Referência: caso_a"

    nav_match = re.search(r'<nav id="level-nav">(.*?)</nav>', document, re.DOTALL)
    assert nav_match is not None
    nav_slice = nav_match.group(1)
    assert nav_slice.count("data-group=") == _LEVEL_NAV_GROUP_COUNT
    assert ">Usinas hidrelétricas<" in nav_slice
    assert ">Execução<" in nav_slice

    assert '<section id="warnings"' not in document


def test_build_html_scenario_tree_with_added_warning_renders_one_warning_item(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    data.add_warning(
        "Cenário 'caso_b' não possui deck para a data 04/03/2024, presente em outro(s) cenário(s)"
    )

    document = build_html(data, settings=settings)

    warnings_match = re.search(r'<section id="warnings">.*?</section>', document, re.DOTALL)
    assert warnings_match is not None
    assert warnings_match.group(0).count("<li>") == 1
    assert "04/03/2024" in warnings_match.group(0)


# --- acceptance criterion 5: the assets themselves, as static text -----------------------------


def _read_dashboard_asset(name: str) -> str:
    return (
        importlib.resources.files("dessem_dashboard.dashboard.assets")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


def test_dashboard_html_asset_is_a_valid_template_with_the_fifteen_documented_identifiers() -> None:
    template = Template(_read_dashboard_asset("dashboard.html"))

    assert template.is_valid() is True
    assert set(template.get_identifiers()) == _EXPECTED_TEMPLATE_IDENTIFIERS


def test_dashboard_css_asset_has_no_color_literal_and_no_import() -> None:
    css_text = _read_dashboard_asset("dashboard.css")

    assert re.search(r"#[0-9A-Fa-f]{3,8}\b", css_text) is None
    assert "@import" not in css_text


# --- write_dashboard: file identity, UTF-8 decoding, and directory creation --------------------


def test_write_dashboard_tmp_path_returns_path_matching_build_html_output(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    output_file = tmp_path / "out" / "dashboard.html"

    returned = write_dashboard(data, settings=settings, output_file=output_file)

    assert returned == output_file
    assert output_file.exists()
    written_text = output_file.read_text(encoding="utf-8")
    assert written_text == build_html(data, settings=settings)


def test_write_dashboard_missing_parent_directory_creates_it(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    output_file = tmp_path / "does" / "not" / "exist" / "dashboard.html"
    assert not output_file.parent.exists()

    write_dashboard(data, settings=settings, output_file=output_file)

    assert output_file.parent.is_dir()
    assert output_file.is_file()


# --- logo error handling: missing file, unsupported suffix, and svg support --------------------


def test_build_html_logo_file_missing_raises_config_error_naming_key_and_resolved_path(
    tmp_path: Path,
) -> None:
    data = _hand_built_data()
    missing_logo = tmp_path / "missing_logo.png"
    settings = _build_settings(tmp_path, logo_file=str(missing_logo))

    pattern = f"{re.escape('paths.logo_file')}.*{re.escape(str(missing_logo.resolve()))}"
    with pytest.raises(ConfigError, match=pattern):
        build_html(data, settings=settings)


def test_build_html_logo_file_unsupported_suffix_raises_config_error(tmp_path: Path) -> None:
    data = _hand_built_data()
    unsupported_logo = tmp_path / "logo.bmp"
    unsupported_logo.write_bytes(b"not a real bitmap; only the suffix matters here")
    settings = _build_settings(tmp_path, logo_file=str(unsupported_logo))

    with pytest.raises(ConfigError, match=re.escape("paths.logo_file")):
        build_html(data, settings=settings)


def test_build_html_logo_file_svg_produces_svg_data_uri(tmp_path: Path) -> None:
    data = _hand_built_data()
    svg_logo = tmp_path / "logo.svg"
    svg_logo.write_text("<svg></svg>", encoding="utf-8")
    settings = _build_settings(tmp_path, logo_file=str(svg_logo))

    document = build_html(data, settings=settings)

    assert "data:image/svg+xml;base64," in document


# --- charts.disabled: fewer sections, but the level navigation is unaffected -------------------


def test_build_html_charts_disabled_omits_sections_but_keeps_six_level_nav_groups(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path, disabled=["GHID_SIN", "CMO_SBM"])
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document = build_html(data, settings=settings)

    assert len(_section_tags(document)) == _ENABLED_CHART_COUNT - 2
    assert 'id="chart-GHID_SIN"' not in document
    assert 'id="chart-CMO_SBM"' not in document

    nav_match = re.search(r'<nav id="level-nav">(.*?)</nav>', document, re.DOTALL)
    assert nav_match is not None
    assert nav_match.group(1).count("data-group=") == _LEVEL_NAV_GROUP_COUNT


# --- epic decision E3-2: the registry long name renders as an additive subtitle ----------------


def test_build_html_metadata_long_name_differing_from_title_adds_subtitle_only_to_that_chart(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    _rewrite_metadados_everywhere(
        scenario_tree, chart_key="CMO_SBM", long_name="Custo Marginal de Operação"
    )
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document = build_html(data, settings=settings)

    cmo_match = re.search(
        r'<section class="chart" id="chart-CMO_SBM".*?</section>', document, re.DOTALL
    )
    assert cmo_match is not None
    assert '<p class="chart-subtitle">Custo Marginal de Operação</p>' in cmo_match.group(0)

    ghid_sin_match = re.search(
        r'<section class="chart" id="chart-GHID_SIN".*?</section>', document, re.DOTALL
    )
    assert ghid_sin_match is not None
    assert '<p class="chart-subtitle"' not in ghid_sin_match.group(0)


# --- requirement 12: escaping ---------------------------------------------------------------


def test_build_html_entity_label_with_ampersand_and_less_than_escapes_in_option_text(
    tmp_path: Path,
) -> None:
    data = _hand_built_data()
    data.set_entities("CMO_SBM", [EntityRef(entity_id="1", label="Usina A & B < C", sort_key=(1,))])
    data.add_series(
        chart_key="CMO_SBM",
        entity_id="1",
        scenario="caso_a",
        deck_date=_HAND_BUILT_DATE,
        values=[1.0],
    )
    settings = _build_settings(tmp_path)

    document = build_html(data, settings=settings)

    assert "Usina A &amp; B &lt; C" in document
    assert "Usina A & B < C" not in document


# --- requirement 6: initial_mode is the only substantive difference between the two modes ------


def test_build_html_initial_mode_deck_and_encadeado_differ_only_in_that_attribute(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    document_deck = build_html(data, settings=settings, initial_mode="deck")
    document_chained = build_html(data, settings=settings, initial_mode="encadeado")

    assert 'data-initial-mode="deck"' in document_deck
    assert 'data-initial-mode="encadeado"' in document_chained

    normalised_deck = document_deck.replace('data-initial-mode="deck"', 'data-initial-mode=""')
    normalised_chained = document_chained.replace(
        'data-initial-mode="encadeado"', 'data-initial-mode=""'
    )
    assert normalised_deck == normalised_chained


# --- pitfall guard: a future plotly upgrade that adds '</script' must fail here, not silently --


def test_get_plotlyjs_contains_no_script_close_sequence() -> None:
    assert "</script" not in plotly.offline.get_plotlyjs()


# --- requirement 13: the two INFO log lines and their volume fields ----------------------------


def test_build_html_and_write_dashboard_log_info_lines_with_volume_fields(
    scenario_tree: dict[str, Path], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    output_file = tmp_path / "out" / "dashboard.html"

    caplog.set_level(logging.INFO, logger=_BUILDER_LOGGER_NAME)
    write_dashboard(data, settings=settings, output_file=output_file)

    messages = [
        record.getMessage() for record in caplog.records if record.name == _BUILDER_LOGGER_NAME
    ]
    document_size = output_file.stat().st_size

    assert any(f"graficos={_ENABLED_CHART_COUNT}" in message for message in messages)
    assert any(f"valores={data.value_count()}" in message for message in messages)
    assert any(str(output_file) in message for message in messages)
    assert any(f"bytes={document_size}" in message for message in messages)
