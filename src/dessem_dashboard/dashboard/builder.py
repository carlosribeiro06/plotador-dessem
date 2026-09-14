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
import functools
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
_SIZE_WARNING_SETTINGS_KEY: Final = "output.size_warning_mb"
_BYTES_PER_MIB: Final = 1024 * 1024

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
    "CUSTO": "Custo",
    "TEMPO": "Tempo",
}

# Entity selector labels (requirement 9), keyed by EntitySelector's string values. EntitySelector
# NONE never reaches this mapping: _chart_sections skips the selector fragment for it entirely.
SELECTOR_LABELS: Final[Mapping[str, str]] = {
    "SUBMARKET": "Submercado",
    "SUBMARKET_PAIR": "Par de submercados",
    "HYDRO_PLANT": "Usina hidrelétrica",
    "THERMAL_PLANT": "Usina termelétrica",
}

# The two EntitySelector values that name a plant registry rather than a submarket or pair
# (ticket-028 requirement 1). _chart_sections renders the name-and-code filter fragment for
# exactly the charts whose selector is a member of this set, so a future plant level (E4-4 keeps
# submarket/REE filtering out of scope, but a new plant level is not ruled out) joins by adding
# one member here rather than by editing a condition.
PLANT_SELECTORS: Final[frozenset[str]] = frozenset(
    {EntitySelector.HYDRO_PLANT.value, EntitySelector.THERMAL_PLANT.value}
)

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

# The value-mode toggle's initial state (requirement 2): drives only `_value_toggle`'s
# aria-pressed attribute. `dashboard.html` independently hard-codes `data-initial-value="absoluto"`,
# the value `dashboard.js` actually reads client-side via `document.body.dataset.initialValue`; the
# two are not wired together in code, only kept in sync by a test, so this constant is not itself
# the document's single source of truth.
INITIAL_VALUE_MODE: Final = "absoluto"


def _validate_initial_mode(initial_mode: str) -> None:
    """Raise ValueError when initial_mode is neither "deck" nor "encadeado" (requirement 1).

    `--modo-inicial` already restricts the CLI to `MODE_LABELS`' two keys, so a call reaching
    here with anything else is a programming error, not an operator error; this deliberately
    raises plain ValueError rather than ConfigError.
    """
    if initial_mode not in MODE_LABELS:
        raise ValueError(f"initial_mode must be one of {sorted(MODE_LABELS)}, got {initial_mode!r}")


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


def _pressed_buttons(dataset_key: str, labels: Mapping[str, str], active: str) -> str:
    """Build one `<button>` per labels entry, in order, keyed by `data-<dataset_key>`.

    The button whose key equals `active` carries `aria-pressed="true"` and every other carries
    `aria-pressed="false"`, so the shell already shows the selected option before any JavaScript
    runs (requirements 2 and 4). This is the Python counterpart of `syncPressed` in
    `dashboard.js`: the level navigation and the two toggles share one pressed-state renderer
    instead of keeping one variant each.
    """
    return "".join(
        f'<button type="button" data-{dataset_key}="{html.escape(key)}" '
        f'aria-pressed="{str(key == active).lower()}">{html.escape(label)}</button>'
        for key, label in labels.items()
    )


def _level_nav(specs: Sequence[ChartSpec]) -> str:
    """Build one nav button per chart group holding at least one enabled chart.

    Groups appear in the order they first occur in specs (requirement 8), which is
    `enabled_specs`' own registration order, not an alphabetical or otherwise re-derived order.
    The button of `specs[0]`'s group -- the initially active level, matching the chart sections
    `_chart_sections` leaves unhidden -- is the pressed one (requirement 4).
    """
    ordered_groups = list(dict.fromkeys(spec.group.value for spec in specs))
    labels = {group: GROUP_LABELS[group] for group in ordered_groups}
    return _pressed_buttons("group", labels, specs[0].group.value)


def _mode_toggle(initial_mode: str) -> str:
    """Build one button per MODE_LABELS entry, in declared order, with initial_mode pressed.

    Requirement 2: the shell shows the selected view mode before any JavaScript runs.
    """
    return _pressed_buttons("mode", MODE_LABELS, initial_mode)


def _value_toggle() -> str:
    """Build one button per VALUE_LABELS entry, in declared order, INITIAL_VALUE_MODE pressed.

    Requirement 2, mirroring `_mode_toggle`.
    """
    return _pressed_buttons("value", VALUE_LABELS, INITIAL_VALUE_MODE)


def _deck_selector(deck_dates: Sequence[str], *, disabled: bool) -> str:
    """Build the deck `<select>`, one `<option>` per already-`%d/%m/%Y`-formatted deck key.

    Does not re-format these strings with `settings.dashboard.date_format`: that pattern carries
    `%H:%M` and would render the deck of 3 March as `03/03/2024 00:00`. Carries the bare
    `disabled` attribute when `disabled` is True (requirement 3): the control stays present and
    visible in Encadeado mode, merely inert, rather than being hidden.
    """
    options = "".join(
        f'<option value="{html.escape(deck_date)}">{html.escape(deck_date)}</option>'
        for deck_date in deck_dates
    )
    disabled_attribute = " disabled" if disabled else ""
    return f'<select id="deck-selector"{disabled_attribute}>{options}</select>'


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
        f'<label class="entity-label" for="entity-{spec.key}">{label}</label>'
        f'<select class="entity-selector" id="entity-{spec.key}">{options}</select>'
    )


def _plant_filter_fragment(spec: ChartSpec) -> str:
    """Build the name-and-code filter fragment for a chart whose selector is in PLANT_SELECTORS.

    The fragment's text is entirely constant plus spec.key, never operator- or payload-derived,
    so -- like `_entity_selector_fragment`'s own id and value attributes -- `html.escape` buys
    nothing here; the f-string shape mirrors its sibling so the two read alike (requirement 1).
    Both operator-visible strings this fragment carries, the two placeholders and the no-match
    message, ship from here rather than from `dashboard.js` (requirement 2): that is what keeps
    the asset pure ASCII.
    """
    return (
        f'<div class="plant-filters">'
        f'<label class="filter-label" for="filter-name-{spec.key}">Nome</label>'
        f'<input type="text" class="plant-filter" data-filter="name" '
        f'id="filter-name-{spec.key}" placeholder="Filtrar por nome">'
        f'<label class="filter-label" for="filter-code-{spec.key}">Código</label>'
        f'<input type="text" class="plant-filter" data-filter="code" '
        f'id="filter-code-{spec.key}" placeholder="Filtrar por código">'
        f'<p class="filter-empty" hidden>Nenhuma usina corresponde ao filtro</p>'
        f"</div>"
    )


def _chart_sections(specs: Sequence[ChartSpec], charts: Mapping[str, Mapping[str, object]]) -> str:
    """Build one `<section class="chart">` per entry of specs, in that same order.

    A section carries the `hidden` attribute unless its group equals the group of the first
    entry of specs, the initially active level (requirement 9). Neither the pressed-state
    attribute nor `disabled` is ever set here: their initial control state belongs to
    tickets 023 and 024. A chart whose selector is in PLANT_SELECTORS additionally carries the
    name-and-code filter fragment, immediately after the entity selector and before the plot
    `<div>` (ticket-028 requirement 1). `data-kind` sits between `data-selector` and the optional
    ` hidden` (ticket-030 requirement 7), so the two tests pinning a hidden section's opening tag
    to end with ` hidden>` keep holding.
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

        filter_html = _plant_filter_fragment(spec) if selector in PLANT_SELECTORS else ""

        sections.append(
            f'<section class="chart" id="chart-{spec.key}" data-chart="{spec.key}" '
            f'data-group="{group}" data-selector="{selector}" '
            f'data-kind="{spec.kind.value}"{hidden_attribute}>'
            f"<h2>{title}</h2>{subtitle_html}{selector_html}{filter_html}"
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

    Raises:
        ConfigError: if `settings.charts.disabled` names every enabled chart of the catalogue,
            leaving no chart to render. `_level_nav` and `_chart_sections` both index `specs[0]`
            for the initially active group, so an empty `specs` would otherwise surface as a
            bare `IndexError` naming neither the offending settings key nor its value.
    """
    _validate_initial_mode(initial_mode)
    start = time.perf_counter()

    specs = enabled_specs(disabled=settings.charts.disabled)
    if not specs:
        raise ConfigError(
            "Chave 'charts.disabled' desabilita todo o catálogo de gráficos: nenhum gráfico "
            "ficaria disponível no dashboard"
        )

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
        mode_toggle=_mode_toggle(initial_mode),
        deck_selector=_deck_selector(deck_dates, disabled=initial_mode == "encadeado"),
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
    output_file unchanged so a caller can chain the call. Logs one INFO line naming the written
    path, the byte count and the size in mebibytes, and additionally emits one Portuguese
    `logger.warning` when that size exceeds `settings.output.size_warning_mb` (epic decision
    E4-3): the write always completes and output_file is always returned, exceeding the
    threshold changes nothing else.
    """
    start = time.perf_counter()
    document = build_html(data, settings=settings, initial_mode=initial_mode)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(document, encoding="utf-8")

    document_bytes = len(document.encode("utf-8"))
    size_mib = document_bytes / _BYTES_PER_MIB

    log_step(
        logger,
        "Dashboard HTML escrito em disco",
        caminho=str(output_file),
        bytes=document_bytes,
        tamanho_mib=f"{size_mib:.1f}",
        elapsed_s=time.perf_counter() - start,
    )

    threshold_mb = settings.output.size_warning_mb
    if size_mib > threshold_mb:
        logger.warning(
            "Documento HTML do dashboard ocupa %.1f MB, acima do limite de %.1f MB definido em "
            "'%s': considere comparar menos decks ou menos cenários para reduzir o tamanho "
            "do arquivo",
            size_mib,
            threshold_mb,
            _SIZE_WARNING_SETTINGS_KEY,
        )

    return output_file


@functools.cache
def plotly_bundle_bytes() -> int:
    """Return the UTF-8 byte length of the inlined Plotly bundle, memoised per process.

    The 4.3 MB `plotly.offline.get_plotlyjs()` read happens at most once per process: the value
    is a property of the installed `plotly` package version, never hard-coded, so a future
    upgrade changes it here without a source edit. Consumed by `output_volumes` below, and
    through it by the `data_volumes` mapping `manifest.write_run_manifest` records.
    """
    return len(plotly.offline.get_plotlyjs().encode("utf-8"))


def output_volumes(data: DashboardData, *, settings: Settings, output_file: Path) -> dict[str, int]:
    """Return the six integer volumes an audited run records for one written dashboard.

    Keys, in order: `cenarios`, `decks`, `graficos`, `valores`, `bytes_html` and `bytes_plotly`.
    `graficos` recomputes `enabled_specs` exactly as `build_html` does, so the two counts cannot
    diverge; `bytes_html` stats output_file, which must already have been written by
    `write_dashboard`. Reads no parquet and builds no document. Every value is an `int`, so the
    mapping is directly usable as `manifest.write_run_manifest`'s `data_volumes` argument and as
    ticket-033's `pipeline.RunResult.data_volumes`.
    """
    specs = enabled_specs(disabled=settings.charts.disabled)
    return {
        "cenarios": len(data.scenarios),
        "decks": len(data.deck_dates),
        "graficos": len(specs),
        "valores": data.value_count(),
        "bytes_html": output_file.stat().st_size,
        "bytes_plotly": plotly_bundle_bytes(),
    }
