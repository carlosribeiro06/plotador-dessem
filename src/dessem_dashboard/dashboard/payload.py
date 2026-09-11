"""Compact JSON payload export: the contract between the data layer and the dashboard renderer.

`build_payload` folds a populated `DashboardData` into one plain, JSON-ready `dict` keyed by
chart, entity, scenario and time axis, per master plan decision 6 (no pre-rendered Plotly
figures) and decision 8 (only absolute series travel; the Diferença view is computed in the
browser). `payload_json` then serialises that mapping into HTML-safe text. Neither function
reads a file, writes a file, or mutates `data`; the two theme arguments arrive as caller-supplied
values so this module stays independent of `dashboard.theme`.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping
from typing import Final

import pandas as pd

from dessem_dashboard.charts.registry import ChartKind, ChartSpec, enabled_specs
from dessem_dashboard.config import Settings
from dessem_dashboard.logging_setup import log_step
from dessem_dashboard.models.store import DashboardData, TimeAxis

logger = logging.getLogger(__name__)

_SCHEMA_VERSION: Final = 1

# Machine format for Plotly's "date" axis type, one string per TimeAxis.starts entry. Never
# operator-facing: the display format is dashboard.date_format, applied client-side by
# ticket-019's tickformat, and deck/chained labels are read from TimeAxis.key, never reformatted
# here.
_AXIS_TIMESTAMP_FORMAT: Final = "%Y-%m-%d %H:%M"

_DIFFERENCE_SUFFIX: Final = " (diferença)"


def _round_value(value: float | None, decimals: int) -> float | None:
    """Round value to decimals, normalising a rounded -0.0 to 0.0; None survives unchanged."""
    if value is None:
        return None
    rounded = round(value, decimals)
    return 0.0 if rounded == 0.0 else rounded


def _axis_entry(axis: TimeAxis) -> dict[str, object]:
    """Build one axis's {"starts": [...], "end": "..."} entry from its TimeAxis."""
    starts = [start.strftime(_AXIS_TIMESTAMP_FORMAT) for start in axis.starts]
    end = axis.starts[-1] + pd.Timedelta(hours=axis.durations_hours[-1])
    return {"starts": starts, "end": end.strftime(_AXIS_TIMESTAMP_FORMAT)}


def _build_axes(data: DashboardData) -> dict[str, dict[str, object]]:
    """Build the axes mapping: every deck's TimeAxis plus the chained axis, keyed by axis.key."""
    time_axes = [data.deck_axis(deck_date) for deck_date in data.deck_dates]
    time_axes.append(data.chained_axis())
    return {axis.key: _axis_entry(axis) for axis in time_axes}


def _build_series(
    data: DashboardData, chart_key: str, entity_id: str, *, decimals: int
) -> dict[str, dict[str, list[float | None]]]:
    """Build chart_key's series entry for entity_id, nesting scenario then axis key.

    Reads data.stored_deck_dates(chart_key, entity_id, scenario) once per scenario instead of
    probing has_series for every deck plus the chained axis (requirement 3a), and emits an axis
    key only for the deck dates that accessor actually reports; a scenario missing a deck
    therefore contributes no key at all for it, rather than an array of nulls.

    ticket-027 requirement 1: an axis entry whose stored values are all None carries no
    information (consolidate's all_entity_ids union stores exactly that array for a plant absent
    from one scenario but present in another), so it is omitted rather than emitted in full; a
    scenario whose axis mapping becomes empty this way is then omitted as well. A partially
    covered array -- decision 17's per-stage null -- is untouched.
    """
    result: dict[str, dict[str, list[float | None]]] = {}
    for scenario in data.scenarios:
        stored_dates = data.stored_deck_dates(chart_key, entity_id, scenario)
        if not stored_dates:
            continue
        by_axis: dict[str, list[float | None]] = {}
        for deck_date in stored_dates:
            axis = data.chained_axis() if deck_date is None else data.deck_axis(deck_date)
            values = data.series(chart_key, entity_id, scenario, deck_date)
            if all(value is None for value in values):
                continue
            by_axis[axis.key] = [_round_value(value, decimals) for value in values]
        if not by_axis:
            continue
        result[scenario] = by_axis
    return result


def _build_scalars(
    data: DashboardData, chart_key: str, *, decimals: int
) -> dict[str, dict[str, dict[str, float | None]]]:
    """Build chart_key's scalars entry: series name -> scenario -> deck key -> rounded value."""
    result: dict[str, dict[str, dict[str, float | None]]] = {}
    for (series_name, scenario, deck_date), value in data.scalars(chart_key).items():
        deck_key = data.deck_axis(deck_date).key
        by_scenario = result.setdefault(series_name, {})
        by_deck = by_scenario.setdefault(scenario, {})
        by_deck[deck_key] = _round_value(value, decimals)
    return result


def _build_chart_entry(data: DashboardData, spec: ChartSpec, *, decimals: int) -> dict[str, object]:
    """Build spec's payload entry with the nine documented keys, present for every chart kind.

    title is always the curated spec.title (epic decision E3-2); subtitle is the registry long
    name only when it is neither absent nor identical to title, so it stays additive rather than
    overriding the hm3-versus-percent and afluente-versus-incremental distinctions the catalogue
    preserves.

    ticket-027 requirement 2: series is built first, and entities is then derived from the
    entities that survived in it, rather than the two being filtered independently -- an entity
    dropped from series but kept in entities would still render an <option> that init() could
    pick as the chart's default selection, opening on a blank chart with nothing explaining it.
    """
    registry_title = data.registries.title_for(spec.key)
    subtitle = registry_title if registry_title not in (None, spec.title) else None
    unit = data.registries.unit_for(spec.key)

    scalars: dict[str, dict[str, dict[str, float | None]]]
    series: dict[str, dict[str, dict[str, list[float | None]]]]
    if spec.kind is ChartKind.SERIES:
        entities = data.entities(spec.key)
        series_by_entity = {
            entity.entity_id: _build_series(data, spec.key, entity.entity_id, decimals=decimals)
            for entity in entities
        }
        series = {
            entity_id: entity_series
            for entity_id, entity_series in series_by_entity.items()
            if entity_series
        }
        entities_payload = [
            {"id": entity.entity_id, "label": entity.label}
            for entity in entities
            if entity.entity_id in series
        ]
        dropped = len(entities) - len(entities_payload)
        if dropped:
            logger.info(
                "Gráfico '%s' omitiu %d entidade(s) do payload: nenhum valor armazenado em "
                "nenhum cenário",
                spec.key,
                dropped,
            )
        scalars = {}
    else:
        entities_payload = []
        series = {}
        scalars = _build_scalars(data, spec.key, decimals=decimals)

    return {
        "group": spec.group.value,
        "kind": spec.kind.value,
        "selector": spec.selector.value,
        "title": spec.title,
        "subtitle": subtitle,
        "unit": unit,
        "entities": entities_payload,
        "series": series,
        "scalars": scalars,
    }


def _warn_omitted_charts(data: DashboardData, catalogue_keys: frozenset[str]) -> None:
    """Log one Portuguese WARNING per chart holding stored data absent from catalogue_keys.

    Requirement 3a's silent-defect guard: chart_keys() and scalar_chart_keys() report every
    chart the store actually holds data for, independent of settings.charts.disabled. A key
    present in the store but outside catalogue_keys means that disabled list diverged from the
    one consolidation used to populate data, and the chart is about to disappear from the HTML
    with nothing else reporting it.
    """
    stored_keys = frozenset(data.chart_keys()) | frozenset(data.scalar_chart_keys())
    for chart_key in sorted(stored_keys - catalogue_keys):
        logger.warning(
            "Gráfico '%s' possui dados armazenados mas está ausente do catálogo de gráficos "
            "habilitados (settings.charts.disabled): gráfico omitido do payload",
            chart_key,
        )


def build_payload(
    data: DashboardData,
    *,
    settings: Settings,
    scenario_colors: Mapping[str, str],
    plotly_layout: Mapping[str, object],
) -> dict[str, object]:
    """Build the compact JSON-ready payload the dashboard's renderer inlines and parses.

    Reads no file and touches no disk, and never mutates data: calling this twice on the same
    store returns equal payloads. scenario_colors and plotly_layout arrive from the caller
    (ticket-021 passes theme.scenario_colors(...) and theme.plotly_layout_template(...)) and are
    neither validated nor interpreted here, so this module stays independent of dashboard.theme.
    """
    start = time.perf_counter()
    decimals = settings.output.decimals
    specs = enabled_specs(disabled=settings.charts.disabled)
    catalogue_keys = frozenset(spec.key for spec in specs)
    _warn_omitted_charts(data, catalogue_keys)

    charts = {spec.key: _build_chart_entry(data, spec, decimals=decimals) for spec in specs}
    payload: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "scenarios": list(data.scenarios),
        "reference": data.reference,
        "deck_dates": [data.deck_axis(deck_date).key for deck_date in data.deck_dates],
        "chained_key": data.chained_axis().key,
        "axes": _build_axes(data),
        "charts": charts,
        "theme": {"scenario_colors": dict(scenario_colors), "layout": dict(plotly_layout)},
        "formats": {"decimals": decimals},
        "labels": {"y_axis_difference_suffix": _DIFFERENCE_SUFFIX},
    }

    log_step(
        logger,
        "Payload JSON construído",
        graficos=len(charts),
        valores=data.value_count(),
        elapsed_s=time.perf_counter() - start,
    )
    return payload


def payload_json(payload: Mapping[str, object]) -> str:
    """Serialise payload to compact, HTML-safe JSON text.

    allow_nan=False turns a NaN or infinity that reached the store into a loud ValueError
    instead of the invalid JSON token NaN. Every '<' is escaped to the six-character '\\u003C' so
    the text cannot terminate its own <script type="application/json"> element.
    """
    text = json.dumps(payload, allow_nan=False, ensure_ascii=False, separators=(",", ":"))
    text = text.replace("<", "\\u003C")
    log_step(logger, "Payload JSON serializado", caracteres=len(text))
    return text
