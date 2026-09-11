"""Assemble the single-file offline HTML dashboard: the DOM contract every later ticket attaches
behaviour to.

`build_html` reads the three template assets (`dashboard.html`, `dashboard.css`,
`dashboard.js`) through `importlib.resources`, so the package works installed from a wheel as
well as in an editable checkout; builds the header, level navigation, control panel, warning
list, one `<section class="chart">` per enabled chart, and the mandatory footer; and inlines the
four heavy payloads -- `plotly.min.js`, the stylesheet, the renderer script and the JSON data
block -- with exactly one `string.Template.substitute` call. A second substitution pass, or
`safe_substitute`, would risk re-scanning an already-substituted fragment for `$`: both the
`R$/MWh` unit and the minified inlined JavaScript contain that character.
"""

from __future__ import annotations

import base64
import html
import importlib.resources
import logging
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from string import Template
from typing import Final, cast

import plotly.offline  # type: ignore[import-untyped]

from dessem_dashboard.charts.registry import ChartSpec, EntitySelector, enabled_specs
from dessem_dashboard.config import Settings
from dessem_dashboard.dashboard import theme
from dessem_dashboard.dashboard.payload import build_payload, payload_json
from dessem_dashboard.errors import ConfigError
from dessem_dashboard.logging_setup import log_step
from dessem_dashboard.models.store import DashboardData

logger = logging.getLogger(__name__)

_ASSETS_PACKAGE: Final = "dessem_dashboard.dashboard.assets"
_TEMPLATE_ASSET: Final = "dashboard.html"
_CSS_ASSET: Final = "dashboard.css"
_JS_ASSET: Final = "dashboard.js"

_LOGO_SETTINGS_KEY: Final = "paths.logo_file"

_LOGO_MIME_TYPES: Final[Mapping[str, str]] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
}

# Dashboard navigation group labels (requirement 8), keyed by ChartGroup's string values so an
# unrecognised group raises KeyError rather than rendering an empty button label.
GROUP_LABELS: Final[Mapping[str, str]] = {
    "SIN": "SIN",
    "SBM": "Submercado",
    "SBP": "Intercâmbio",
    "UHE": "Usinas hidrelétricas",
    "UTE": "Usinas termelétricas",
    "EXECUCAO": "Execução",
}

# Entity selector labels (requirement 9), keyed by EntitySelector's string values. EntitySelector
# NONE never reaches this mapping: _chart_sections skips the selector fragment for it entirely.
SELECTOR_LABELS: Final[Mapping[str, str]] = {
    "SUBMARKET": "Submercado",
    "SUBMARKET_PAIR": "Par de submercados",
    "HYDRO_PLANT": "Usina hidrelétrica",
    "THERMAL_PLANT": "Usina termelétrica",
}

# View-mode and value-mode toggle labels (requirement 10), in the declared order the buttons
# must render in.
MODE_LABELS: Final[Mapping[str, str]] = {
    "deck": "Por deck",
    "encadeado": "Encadeado",
}

VALUE_LABELS: Final[Mapping[str, str]] = {
    "absoluto": "Absoluto",
    "diferenca": "Diferença",
}


def _read_asset(name: str) -> str:
    """Read one text asset from the packaged assets directory, as UTF-8.

    Uses `importlib.resources.files`, never a path relative to `__file__`: the latter happens to
    work in an editable install and breaks in a built wheel. Deliberately catches no `OSError`:
    a package shipped without its own data is an unrecoverable programming error, not a
    condition an operator can act on.
    """
    return importlib.resources.files(_ASSETS_PACKAGE).joinpath(name).read_text(encoding="utf-8")


def _logo_data_uri(logo_file_path: Path) -> str:
    """Build a `data:` URI embedding the bytes of `logo_file_path`.

    Raises ConfigError, in Portuguese and naming both the dotted settings key and the resolved
    absolute path, when the suffix is not one of `.png`, `.jpg`, `.jpeg` or `.svg`, or when the
    file does not exist. Master plan decision 18 makes a missing *data* file degrade to a
    warning, but a missing logo is a configuration error: goal 7 makes the ONS visual identity a
    requirement, and a text-only header would silently ship a brand-non-compliant artifact.
    """
    logo_file = logo_file_path.resolve()
    mime = _LOGO_MIME_TYPES.get(logo_file.suffix.lower())
    if mime is None:
        raise ConfigError(
            f"Chave '{_LOGO_SETTINGS_KEY}' aponta para um arquivo de extensão não suportada "
            f"'{logo_file.suffix}': {logo_file}"
        )
    if not logo_file.is_file():
        raise ConfigError(
            f"Chave '{_LOGO_SETTINGS_KEY}' aponta para um arquivo inexistente: {logo_file}"
        )
    encoded = base64.b64encode(logo_file.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _level_nav(specs: Sequence[ChartSpec]) -> str:
    """Build one nav button per chart group holding at least one enabled chart.

    Groups appear in the order they first occur in specs (requirement 8), which is
    `enabled_specs`' own registration order, not an alphabetical or otherwise re-derived order.
    """
    seen_groups: list[str] = []
    for spec in specs:
        group = spec.group.value
        if group not in seen_groups:
            seen_groups.append(group)
    buttons = (
        f'<button type="button" data-group="{html.escape(group)}">'
        f"{html.escape(GROUP_LABELS[group])}</button>"
        for group in seen_groups
    )
    return "".join(buttons)


def _mode_toggle() -> str:
    """Build one button per MODE_LABELS entry, in declared order."""
    return "".join(
        f'<button type="button" data-mode="{html.escape(mode)}">{html.escape(label)}</button>'
        for mode, label in MODE_LABELS.items()
    )


def _value_toggle() -> str:
    """Build one button per VALUE_LABELS entry, in declared order."""
    return "".join(
        f'<button type="button" data-value="{html.escape(value)}">{html.escape(label)}</button>'
        for value, label in VALUE_LABELS.items()
    )


def _deck_selector(deck_dates: Sequence[str]) -> str:
    """Build the deck `<select>`, one `<option>` per already-`%d/%m/%Y`-formatted deck key.

    Does not re-format these strings with `settings.dashboard.date_format`: that pattern carries
    `%H:%M` and would render the deck of 3 March as `03/03/2024 00:00`.
    """
    options = "".join(
        f'<option value="{html.escape(deck_date)}">{html.escape(deck_date)}</option>'
        for deck_date in deck_dates
    )
    return f'<select id="deck-selector">{options}</select>'


def _warnings_section(warnings: Sequence[str]) -> str:
    """Build the warnings section, or the empty string when warnings is empty.

    An empty result means the section is absent from the document rather than an empty box
    (requirement 11): $warnings_section sits alone on its own line in the template.
    """
    if not warnings:
        return ""
    items = "".join(f"<li>{html.escape(message)}</li>" for message in warnings)
    return f'<section id="warnings"><h2>Avisos</h2><ul>{items}</ul></section>'


def _entity_selector_fragment(spec: ChartSpec, entities: Sequence[Mapping[str, str]]) -> str:
    """Build the `<label>` + `<select>` fragment for a chart with a non-NONE entity selector."""
    label = html.escape(SELECTOR_LABELS[spec.selector.value])
    options = "".join(
        f'<option value="{html.escape(entity["id"])}">{html.escape(entity["label"])}</option>'
        for entity in entities
    )
    return (
        f'<label class="entity-label">{label}</label>'
        f'<select class="entity-selector" id="entity-{spec.key}">{options}</select>'
    )


def _chart_sections(specs: Sequence[ChartSpec], charts: Mapping[str, Mapping[str, object]]) -> str:
    """Build one `<section class="chart">` per entry of specs, in that same order.

    A section carries the `hidden` attribute unless its group equals the group of the first
    entry of specs, the initially active level (requirement 9). Neither the pressed-state
    attribute nor `disabled` is ever set here: their initial control state belongs to
    tickets 023 and 024.
    """
    active_group = specs[0].group.value
    sections: list[str] = []
    for spec in specs:
        entry = charts[spec.key]
        group = spec.group.value
        selector = spec.selector.value
        hidden_attribute = "" if group == active_group else " hidden"

        title = html.escape(cast(str, entry["title"]))
        subtitle_value = cast(str | None, entry["subtitle"])
        subtitle_html = (
            ""
            if subtitle_value is None
            else f'<p class="chart-subtitle">{html.escape(subtitle_value)}</p>'
        )

        selector_html = ""
        if selector != EntitySelector.NONE.value:
            entities = cast(list[Mapping[str, str]], entry["entities"])
            selector_html = _entity_selector_fragment(spec, entities)

        sections.append(
            f'<section class="chart" id="chart-{spec.key}" data-chart="{spec.key}" '
            f'data-group="{group}" data-selector="{selector}"{hidden_attribute}>'
            f"<h2>{title}</h2>{subtitle_html}{selector_html}"
            f'<div class="plot" id="plot-{spec.key}"></div>'
            "</section>"
        )
    return "".join(sections)


def build_html(data: DashboardData, *, settings: Settings, initial_mode: str = "encadeado") -> str:
    """Build the complete single-file HTML dashboard document, as a string.

    Reads the three template assets and the logo bytes, builds every DOM fragment described by
    the epic-03 DOM contract, and performs exactly one `Template.substitute` call: no fragment
    (in particular the inlined `plotly.min.js` and the JSON payload) is ever re-scanned for a
    `$` placeholder. Touches no disk beyond those reads.
    """
    start = time.perf_counter()

    specs = enabled_specs(disabled=settings.charts.disabled)

    scenario_colors = theme.scenario_colors(data.scenarios, reference=data.reference)
    plotly_layout = theme.plotly_layout_template(date_format=settings.dashboard.date_format)
    payload = build_payload(
        data, settings=settings, scenario_colors=scenario_colors, plotly_layout=plotly_layout
    )
    charts = cast(dict[str, dict[str, object]], payload["charts"])
    deck_dates = cast(list[str], payload["deck_dates"])

    template = Template(_read_asset(_TEMPLATE_ASSET))
    document = template.substitute(
        title=html.escape(settings.dashboard.title),
        css=theme.css_root_block() + _read_asset(_CSS_ASSET),
        initial_mode=html.escape(initial_mode),
        logo_data_uri=_logo_data_uri(settings.paths.logo_file),
        level_nav=_level_nav(specs),
        mode_toggle=_mode_toggle(),
        deck_selector=_deck_selector(deck_dates),
        value_toggle=_value_toggle(),
        reference=html.escape(data.reference),
        warnings_section=_warnings_section(data.warnings()),
        chart_sections=_chart_sections(specs, charts),
        footer=html.escape(settings.dashboard.footer_text),
        plotly_js=plotly.offline.get_plotlyjs(),
        payload_json=payload_json(payload),
        dashboard_js=_read_asset(_JS_ASSET),
    )

    log_step(
        logger,
        "Payload embutido no documento HTML do dashboard",
        graficos=len(charts),
        valores=data.value_count(),
        elapsed_s=time.perf_counter() - start,
    )
    return document


def write_dashboard(
    data: DashboardData,
    *,
    settings: Settings,
    output_file: Path,
    initial_mode: str = "encadeado",
) -> Path:
    """Build the dashboard document and write it to output_file as UTF-8.

    Creates output_file's parent directory if it does not already exist, and returns
    output_file unchanged so a caller can chain the call.
    """
    start = time.perf_counter()
    document = build_html(data, settings=settings, initial_mode=initial_mode)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(document, encoding="utf-8")

    log_step(
        logger,
        "Dashboard HTML escrito em disco",
        caminho=str(output_file),
        bytes=len(document.encode("utf-8")),
        elapsed_s=time.perf_counter() - start,
    )
    return output_file
