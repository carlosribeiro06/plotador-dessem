"""Series consolidation: the function that joins every data-layer component into DashboardData.

Walks the discovered scenarios and decks, reads each enabled chart's source file at most once per
(scenario, deck), pivots the long rows into per-entity arrays aligned on that deck's TimeAxis and on
the chained axis, and pushes the result into DashboardData for both view modes. Three master-plan
decisions shape this module: decision 16 (a chart's entity list comes from its own file), decision
17 (a missing (entity, stage) combination inside an existing file is filled with None, never
dropped) and decision 18 (a missing file or a missing deck degrades to one warning plus a gap,
never a crash). This module performs no writes.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

import pandas as pd

from dessem_dashboard.charts.registry import ChartKind, enabled_specs
from dessem_dashboard.config import Settings
from dessem_dashboard.data.readers import read_costs, read_series, read_times
from dessem_dashboard.data.registries import (
    HydroPlant,
    Registries,
    ThermalPlant,
    load_registries,
    visible_submarket_codes,
)
from dessem_dashboard.data.schemas import AggregationLevel
from dessem_dashboard.data.timeline import (
    align_deck_dates,
    chaining_window,
    load_deck_timeline,
    order_timelines,
    validate_chaining,
)
from dessem_dashboard.errors import DataFileError, SchemaError
from dessem_dashboard.logging_setup import log_step
from dessem_dashboard.models.entities import DeckTimeline, ScenarioRef
from dessem_dashboard.models.store import DashboardData, EntityRef, TimeAxis

logger = logging.getLogger(__name__)

_DATE_FORMAT = "%d/%m/%Y"
_CHAINED_AXIS_KEY = "encadeado"
_SIN_LABEL = "Sistema Interligado"

# Value column each SCALAR_BY_DECK chart stores through add_scalar; parcela/desvio_padrao and
# etapa/execucao are the other columns of Appendix A.5, out of scope for this ticket.
_SCALAR_VALUE_COLUMNS: Mapping[str, tuple[str, str]] = {
    "CUSTOS": ("parcela", "valor_esperado"),
    "TEMPO": ("etapa", "tempo"),
}

_ScenarioTimelines = Mapping[str, Sequence[DeckTimeline]]


@dataclass(frozen=True, slots=True)
class _ChartDeckReading:
    """One (scenario, deck, chart) source file's pivoted values, keyed by entity_id.

    dropped_submarket_codes names every codigo_submercado this reading's source file carried but
    that visible_submarket_codes excluded for a reason other than being fictitious: a real
    coverage gap between the data and the SBM registry (finding 8 of the epic-02 boundary
    review), never populated for a level other than SBM.
    """

    entity_deck_values: Mapping[str, tuple[float | None, ...]]
    entity_window_values: Mapping[str, tuple[float | None, ...]]
    dropped_submarket_codes: frozenset[int] = frozenset()


def _values_from_series(values: pd.Series) -> tuple[float | None, ...]:
    """Convert one reindexed pivot column to a value tuple, replacing NaN with None.

    The only Python-level loop over individual values in this module: no vectorised pandas
    operation turns NaN into the JSON-safe None the store requires.
    """
    return tuple(None if pd.isna(value) else float(value) for value in values)


def _reindexed_values(pivoted: pd.DataFrame, length: int) -> dict[str, tuple[float | None, ...]]:
    """Reindex pivoted onto stages 1..length and convert every column to a value tuple.

    Reindexing is what turns a stage absent from the file into NaN, and therefore into None, per
    decision 17. Both the deck axis and the chaining window derive from the same pivot through
    this one function, so the two lengths cannot diverge in how they treat a gap.
    """
    reindexed = pivoted.reindex(index=range(1, length + 1))
    return {
        str(entity_id): _values_from_series(reindexed[entity_id]) for entity_id in pivoted.columns
    }


def _entity_id_series(frame: pd.DataFrame, level: AggregationLevel) -> pd.Series:
    """Return frame's entity_id column, per the identity rule of master-plan requirement 6."""
    if level is AggregationLevel.SIN:
        return pd.Series("", index=frame.index)
    if level is AggregationLevel.SBM:
        return frame["codigo_submercado"].astype(str)
    if level is AggregationLevel.SBP:
        de = frame["codigo_submercado_de"].astype(str)
        para = frame["codigo_submercado_para"].astype(str)
        return de + "-" + para
    return frame["codigo_usina"].astype(str)


def _entity_ref(level: AggregationLevel, entity_id: str, registries: Registries) -> EntityRef:
    """Return entity_id's EntityRef, with the Portuguese label and sort_key of requirement 6."""
    if level is AggregationLevel.SIN:
        return EntityRef(entity_id="", label=_SIN_LABEL, sort_key=())
    if level is AggregationLevel.SBM:
        code = int(entity_id)
        return EntityRef(
            entity_id=entity_id, label=registries.submarket_label(code), sort_key=(code,)
        )
    if level is AggregationLevel.SBP:
        from_text, to_text = entity_id.split("-", maxsplit=1)
        from_code, to_code = int(from_text), int(to_text)
        from_label = registries.submarket_label(from_code)
        to_label = registries.submarket_label(to_code)
        return EntityRef(
            entity_id=entity_id,
            label=f"{from_label} para {to_label}",
            sort_key=(from_code, to_code),
        )
    if level is AggregationLevel.UHE:
        name = registries.hydro_name(int(entity_id))
        return EntityRef(entity_id=entity_id, label=name, sort_key=(name,))
    name = registries.thermal_name(int(entity_id))
    return EntityRef(entity_id=entity_id, label=name, sort_key=(name,))


def _assert_unique_entity_stage(frame: pd.DataFrame, *, source: Path) -> None:
    """Raise SchemaError unless (entity_id, estagio) is unique, before pivot needs it to be.

    read_series only guarantees uniqueness over the file's own, wider entity keys (for example
    (codigo_usina, codigo_ree, codigo_submercado, estagio) for UHE); the pivot's entity_id column
    is narrower (str(codigo_usina) alone for UHE), so two rows that share codigo_usina under
    different codigo_ree/codigo_submercado values pass read_series but collide here. This
    reproduces decision 15's loud failure at the key the pivot actually uses, instead of letting
    pandas.DataFrame.pivot raise a bare, unnamed ValueError (finding 6 of the epic-02 boundary
    review).
    """
    duplicate_mask = frame.duplicated(subset=["entity_id", "estagio"], keep=False)
    if not duplicate_mask.any():
        return
    first = frame.loc[duplicate_mask].iloc[0]
    raise SchemaError(
        f"Arquivo {source.name}: entidade '{first['entity_id']}' tem mais de um valor no "
        f"estágio {int(first['estagio'])}; chave (entidade, estágio) duplicada"
    )


def _read_chart_deck(
    source_path: Path,
    level: AggregationLevel,
    *,
    deck_axis_length: int,
    window_length: int,
    visible_codes: frozenset[int] | None,
    fictitious_codes: frozenset[int],
) -> _ChartDeckReading:
    """Read, filter, pivot and reindex one chart's source file for one deck.

    Propagates DataFileError when source_path is absent and SchemaError on a contract violation;
    the caller catches only the former. visible_codes, when given, drops rows whose
    codigo_submercado is not in it (requirement 7); it is None for every level but SBM.
    dropped_submarket_codes reports every code the file carries that is neither visible nor
    fictitious, so the caller can warn instead of silently losing that submarket's data.
    """
    frame = read_series(source_path, level)

    dropped_submarket_codes: frozenset[int] = frozenset()
    if visible_codes is not None:
        data_codes = frozenset(int(code) for code in frame["codigo_submercado"].unique())
        dropped_submarket_codes = data_codes - visible_codes - fictitious_codes
        frame = frame[frame["codigo_submercado"].isin(visible_codes)]

    pivoted_source = frame.assign(entity_id=_entity_id_series(frame, level))
    _assert_unique_entity_stage(pivoted_source, source=source_path)
    pivoted = pivoted_source.pivot(index="estagio", columns="entity_id", values="valor")
    return _ChartDeckReading(
        entity_deck_values=_reindexed_values(pivoted, deck_axis_length),
        entity_window_values=_reindexed_values(pivoted, window_length),
        dropped_submarket_codes=dropped_submarket_codes,
    )


def _warn_on_renamed_plants(
    primary: Mapping[int, HydroPlant] | Mapping[int, ThermalPlant],
    other: Mapping[int, HydroPlant] | Mapping[int, ThermalPlant],
    *,
    deck_name: str,
    kind: str,
) -> None:
    """Log a WARNING for every code common to primary and other whose plant name disagrees.

    Never raises and never mutates primary: the first deck's registry always wins (requirement 4).
    """
    for code, plant in other.items():
        primary_plant = primary.get(code)
        if primary_plant is not None and primary_plant.name != plant.name:
            logger.warning(
                "Usina %s de código %d tem nome divergente no deck '%s' ('%s'); mantido o nome "
                "do deck de referência ('%s')",
                kind,
                code,
                deck_name,
                plant.name,
                primary_plant.name,
            )


def _load_timelines(
    scenarios: Sequence[ScenarioRef], *, stages_per_deck: int
) -> tuple[dict[str, tuple[DeckTimeline, ...]], tuple[date, ...], list[str]]:
    """Phase 1: load, order and chain-validate every scenario's deck timelines.

    Raises DataFileError when a deck's EST.parquet is absent and SchemaError on a malformed or
    non-contiguous timeline; neither is caught here, since the deck then has no usable axis.
    """
    start = time.perf_counter()
    ordered_by_scenario: dict[str, tuple[DeckTimeline, ...]] = {}
    warnings: list[str] = []

    for scenario in scenarios:
        timelines = [load_deck_timeline(deck) for deck in scenario.decks]
        ordered = order_timelines(timelines)
        ordered_by_scenario[scenario.label] = ordered
        warnings.extend(validate_chaining(ordered, stages_per_deck=stages_per_deck))

    deck_dates, alignment_warnings = align_deck_dates(ordered_by_scenario)
    warnings.extend(alignment_warnings)

    log_step(
        logger,
        "Fase 1/5: timelines de deck carregadas",
        cenarios=len(scenarios),
        decks=sum(len(timelines) for timelines in ordered_by_scenario.values()),
        avisos=len(warnings),
        elapsed_s=time.perf_counter() - start,
    )
    return ordered_by_scenario, deck_dates, warnings


def _first_start(timeline: DeckTimeline) -> pd.Timestamp | None:
    """Return timeline's first stage start, or None for a timeline with no stages."""
    return timeline.stages[0].start if timeline.stages else None


def _check_timeline_coverage(
    deck_date: date,
    axis_scenario: str,
    axis_timeline: DeckTimeline,
    other_candidates: Sequence[tuple[str, DeckTimeline]],
) -> list[str]:
    """Warn for every scenario at deck_date whose timeline disagrees with the selected axis.

    Compares stage count and first stage start, the two shapes a silent reindex-onto-the-wrong-
    axis corrupts: a stage-count mismatch drops that scenario's excess trailing stages, and a
    first-start mismatch shifts every one of its points by the offset, reaching decision 10's
    failure class through a different door (finding 4 of the epic-02 boundary review). Never
    raises, per decision 18: the dashboard still renders, and the operator learns the fact.
    """
    date_text = deck_date.strftime(_DATE_FORMAT)
    axis_count = len(axis_timeline.stages)
    axis_start = _first_start(axis_timeline)
    messages: list[str] = []
    for other_scenario, other_timeline in other_candidates:
        other_count = len(other_timeline.stages)
        other_start = _first_start(other_timeline)
        if other_count == axis_count and other_start == axis_start:
            continue
        messages.append(
            f"Cenário '{other_scenario}' tem timeline divergente do eixo do deck de {date_text} "
            f"(referência: cenário '{axis_scenario}'): eixo tem {axis_count} estágio(s) "
            f"iniciando em {axis_start}, cenário '{other_scenario}' tem {other_count} "
            f"estágio(s) iniciando em {other_start}"
        )
    return messages


def _build_axes(
    ordered_by_scenario: _ScenarioTimelines,
    scenario_order: Sequence[str],
    deck_dates: Sequence[date],
    *,
    stages_per_deck: int,
) -> tuple[dict[date, TimeAxis], TimeAxis, dict[date, int], list[str]]:
    """Phase 2: build one TimeAxis per deck date, from the first scenario that has it.

    Also builds the chained axis, concatenating every deck's chaining window in deck-date order,
    and returns each deck date's window length so _load_series can pad a gap to the exact shape
    the chained axis already committed to for that date. Every other scenario sharing this deck
    date is compared against the selected timeline (see _check_timeline_coverage); the resulting
    warnings are returned rather than pushed into the store directly, because this phase still
    runs before DashboardData exists.
    """
    start = time.perf_counter()
    deck_axes: dict[date, TimeAxis] = {}
    window_lengths: dict[date, int] = {}
    chained_starts: list[pd.Timestamp] = []
    chained_durations: list[float] = []
    warnings: list[str] = []

    for deck_date in deck_dates:
        candidates = [
            (scenario_label, candidate)
            for scenario_label in scenario_order
            for candidate in ordered_by_scenario[scenario_label]
            if candidate.deck_date == deck_date
        ]
        axis_scenario, timeline = candidates[0]
        deck_axes[deck_date] = TimeAxis(
            key=deck_date.strftime(_DATE_FORMAT),
            starts=tuple(stage.start for stage in timeline.stages),
            durations_hours=tuple(stage.duration_hours for stage in timeline.stages),
        )
        warnings.extend(
            _check_timeline_coverage(deck_date, axis_scenario, timeline, candidates[1:])
        )
        window = chaining_window(timeline, stages_per_deck=stages_per_deck)
        window_lengths[deck_date] = len(window)
        chained_starts.extend(stage.start for stage in window)
        chained_durations.extend(stage.duration_hours for stage in window)

    chained_axis = TimeAxis(
        key=_CHAINED_AXIS_KEY,
        starts=tuple(chained_starts),
        durations_hours=tuple(chained_durations),
    )
    log_step(
        logger,
        "Fase 2/5: eixos de tempo construídos",
        decks=len(deck_dates),
        estagios_encadeados=chained_axis.length,
        avisos=len(warnings),
        elapsed_s=time.perf_counter() - start,
    )
    return deck_axes, chained_axis, window_lengths, warnings


def _load_registries(scenarios: Sequence[ScenarioRef]) -> Registries:
    """Phase 3: load the primary Registries from the first available deck of the first scenario.

    Compares every other deck's UHE and UTE plant names against the primary registry, logging a
    WARNING on a mismatch and always keeping the primary name (requirement 4). A non-primary
    deck's registry is read only to feed that advisory comparison: labels come exclusively from
    the primary registry, and entity ids come from each series file, so a missing registry on a
    non-primary deck is not the "no axis, no labels" case DataFileError is meant to guard.
    Raising there would abort a whole multi-scenario run over a purely advisory comparison,
    against decision 18; instead this logs a Portuguese WARNING and skips that deck's comparison
    (finding 5 of the epic-02 boundary review). The primary deck's own read stays outside this
    guard and still propagates DataFileError unchanged: that deck genuinely supplies the labels,
    so its absence is a hard failure, not a degradable gap.
    """
    start = time.perf_counter()
    primary_deck = scenarios[0].decks[0]
    primary = load_registries(primary_deck.sintese_dir)

    decks_compared = 0
    for scenario in scenarios:
        for deck in scenario.decks:
            if deck is primary_deck:
                continue
            try:
                registries = load_registries(deck.sintese_dir)
            except DataFileError as err:
                logger.warning(
                    "Registro do deck '%s' (cenário '%s') indisponível para a comparação "
                    "advisória de nomes de usinas; comparação ignorada para esse deck: %s",
                    deck.name,
                    scenario.label,
                    err,
                )
                continue
            _warn_on_renamed_plants(
                primary.hydro, registries.hydro, deck_name=deck.name, kind="hidráulica"
            )
            _warn_on_renamed_plants(
                primary.thermal, registries.thermal, deck_name=deck.name, kind="térmica"
            )
            decks_compared += 1

    log_step(
        logger,
        "Fase 3/5: registros consolidados",
        decks=1 + decks_compared,
        elapsed_s=time.perf_counter() - start,
    )
    return primary


def _load_series(
    data: DashboardData,
    *,
    ordered_by_scenario: _ScenarioTimelines,
    scenario_order: Sequence[str],
    window_lengths: Mapping[date, int],
    registries: Registries,
    settings: Settings,
) -> None:
    """Phase 4: consolidate every enabled SERIES chart into data's deck and chained arrays.

    A missing source file or a deck absent from a scenario produces one warning naming the
    chart, the scenario and the deck, and no series is stored for that (scenario, deck)
    (decision 18). An entity absent from a deck file that does exist is stored filled with None
    and counted in one warning per (chart, scenario, deck) (decision 17). A submarket code the
    data carries but that is neither visible nor configured as fictitious is a coverage gap
    between the data and the SBM registry, warned once per (chart, scenario, deck) naming the
    dropped code(s) (finding 8 of the epic-02 boundary review). Reads each file at most once,
    deriving both the deck array and the chained segment from the same pivoted frame.
    """
    start = time.perf_counter()
    series_specs = tuple(
        spec
        for spec in enabled_specs(disabled=settings.charts.disabled)
        if spec.kind is ChartKind.SERIES
    )
    include_fictitious = settings.submarkets.include_fictitious
    visible_codes = frozenset(
        visible_submarket_codes(registries, include_fictitious=include_fictitious)
    )
    fictitious_codes = frozenset(settings.submarkets.fictitious_codes)

    files_read = 0
    series_stored = 0

    for chart_spec in series_specs:
        # ChartRegistry._validate guarantees every SERIES spec carries a level.
        level = cast(AggregationLevel, chart_spec.level)

        readings_by_scenario: dict[str, dict[date, _ChartDeckReading | None]] = {}
        all_entity_ids: set[str] = set()

        for scenario_label in scenario_order:
            timelines_by_date = {
                timeline.deck_date: timeline for timeline in ordered_by_scenario[scenario_label]
            }
            readings: dict[date, _ChartDeckReading | None] = {}
            for deck_date in data.deck_dates:
                timeline = timelines_by_date.get(deck_date)
                if timeline is None:
                    readings[deck_date] = None
                    continue

                source_path = timeline.deck.sintese_dir / f"{chart_spec.source_file}.parquet"
                try:
                    reading = _read_chart_deck(
                        source_path,
                        level,
                        deck_axis_length=data.deck_axis(deck_date).length,
                        window_length=window_lengths[deck_date],
                        visible_codes=visible_codes if level is AggregationLevel.SBM else None,
                        fictitious_codes=fictitious_codes,
                    )
                except DataFileError:
                    data.add_warning(
                        f"Arquivo do gráfico '{chart_spec.key}' não encontrado no cenário "
                        f"'{scenario_label}', deck de {deck_date.strftime(_DATE_FORMAT)}: série "
                        f"não armazenada"
                    )
                    readings[deck_date] = None
                    continue

                files_read += 1
                readings[deck_date] = reading
                all_entity_ids.update(reading.entity_deck_values)
                if reading.dropped_submarket_codes:
                    dropped_text = ", ".join(
                        str(code) for code in sorted(reading.dropped_submarket_codes)
                    )
                    data.add_warning(
                        f"{len(reading.dropped_submarket_codes)} código(s) de submercado do "
                        f"gráfico '{chart_spec.key}' presente(s) nos dados mas ausente(s) do "
                        f"registro de submercados no cenário '{scenario_label}', deck de "
                        f"{deck_date.strftime(_DATE_FORMAT)}: código(s) descartado(s): "
                        f"{dropped_text}"
                    )

            readings_by_scenario[scenario_label] = readings

        data.set_entities(
            chart_spec.key,
            [_entity_ref(level, entity_id, registries) for entity_id in sorted(all_entity_ids)],
        )

        for scenario_label in scenario_order:
            readings = readings_by_scenario[scenario_label]

            for deck_date in data.deck_dates:
                stored_reading = readings[deck_date]
                if stored_reading is None:
                    continue

                absent = sorted(all_entity_ids - set(stored_reading.entity_deck_values))
                if absent:
                    data.add_warning(
                        f"{len(absent)} entidade(s) do gráfico '{chart_spec.key}' ausente(s) no "
                        f"cenário '{scenario_label}', deck de "
                        f"{deck_date.strftime(_DATE_FORMAT)}: valor(es) preenchido(s) com null"
                    )

                deck_axis_length = data.deck_axis(deck_date).length
                for entity_id in sorted(all_entity_ids):
                    values = stored_reading.entity_deck_values.get(
                        entity_id, (None,) * deck_axis_length
                    )
                    data.add_series(
                        chart_key=chart_spec.key,
                        entity_id=entity_id,
                        scenario=scenario_label,
                        deck_date=deck_date,
                        values=values,
                    )
                    series_stored += 1

            for entity_id in sorted(all_entity_ids):
                segments: list[float | None] = []
                for deck_date in data.deck_dates:
                    stored_reading = readings[deck_date]
                    window_length = window_lengths[deck_date]
                    if stored_reading is None:
                        segments.extend([None] * window_length)
                        continue
                    segments.extend(
                        stored_reading.entity_window_values.get(entity_id, (None,) * window_length)
                    )
                data.add_series(
                    chart_key=chart_spec.key,
                    entity_id=entity_id,
                    scenario=scenario_label,
                    deck_date=None,
                    values=segments,
                )
                series_stored += 1

    log_step(
        logger,
        "Fase 4/5: séries consolidadas",
        graficos=len(series_specs),
        arquivos_lidos=files_read,
        series_armazenadas=series_stored,
        elapsed_s=time.perf_counter() - start,
    )


def _read_scalar_frame(chart_key: str, source_path: Path) -> pd.DataFrame:
    """Return CUSTOS or TEMPO's raw frame through the matching public reader."""
    if chart_key == "CUSTOS":
        return read_costs(source_path)
    return read_times(source_path)


def _load_scalars(
    data: DashboardData,
    *,
    ordered_by_scenario: _ScenarioTimelines,
    scenario_order: Sequence[str],
    settings: Settings,
) -> None:
    """Phase 5: consolidate CUSTOS and TEMPO into data's scalar store, per (row, scenario, deck).

    Sums the rows that share a series_column value (etapa for TEMPO, parcela for CUSTOS) before
    storing, because TEMPO.parquet carries nine rows over five distinct etapas -- PL alone
    executes three times -- and add_scalar's key is (series_name, scenario, deck_date): with one
    row per key, storing the last row overwrote the other two thirds of PL's time (finding 1 of
    the epic-02 boundary review). This differs from the grouping ticket-031 owns through
    settings.time.stage_groups: stage_groups later groups *distinct* etapas (for example PL,
    PL.Int.Fix and PL.CalcCMO into one "PL" bucket for display), while this sum collapses
    *repeated executions of the very same stage* into the one entry per (etapa, scenario, deck)
    requirement 8 demands. Both must hold at once, and only summing here, ahead of stage_groups,
    achieves that. Applied identically to CUSTOS for consistency of mechanism: its four parcela
    rows are distinct today, so the sum is a no-op there, but a future duplicate row is then
    handled rather than silently dropped. No total and no further grouping happen here
    regardless (tickets 030 and 031 own those), and no value is ever divided by 60. min_count=1
    keeps an all-missing group NaN instead of pandas' zero-for-empty-sum default, so the pd.isna
    guard below still converts a missing value to None rather than to 0.0 (finding 2 of the
    epic-02 boundary review): the store's public contract never accepts the NaN sentinel, and
    json.dumps has no valid token for it. A missing source file produces one warning naming the
    chart, the scenario and the deck, and no scalar is stored for that (scenario, deck)
    (decision 18).
    """
    start = time.perf_counter()
    scalar_specs = tuple(
        spec
        for spec in enabled_specs(disabled=settings.charts.disabled)
        if spec.kind is ChartKind.SCALAR_BY_DECK
    )

    files_read = 0
    scalars_stored = 0

    for scenario_label in scenario_order:
        for timeline in ordered_by_scenario[scenario_label]:
            for chart_spec in scalar_specs:
                source_path = timeline.deck.sintese_dir / f"{chart_spec.source_file}.parquet"
                try:
                    frame = _read_scalar_frame(chart_spec.key, source_path)
                except DataFileError:
                    data.add_warning(
                        f"Arquivo do gráfico '{chart_spec.key}' não encontrado no cenário "
                        f"'{scenario_label}', deck de "
                        f"{timeline.deck_date.strftime(_DATE_FORMAT)}: valores não armazenados"
                    )
                    continue

                files_read += 1
                series_column, value_column = _SCALAR_VALUE_COLUMNS[chart_spec.key]
                summed = frame.groupby(series_column)[value_column].sum(min_count=1)
                for series_name, value in summed.items():
                    data.add_scalar(
                        chart_key=chart_spec.key,
                        series_name=str(series_name),
                        scenario=scenario_label,
                        deck_date=timeline.deck_date,
                        value=None if pd.isna(value) else float(value),
                    )
                    scalars_stored += 1

    log_step(
        logger,
        "Fase 5/5: escalares consolidados",
        graficos=len(scalar_specs),
        arquivos_lidos=files_read,
        valores_armazenados=scalars_stored,
        elapsed_s=time.perf_counter() - start,
    )


def build_dashboard_data(
    scenarios: Sequence[ScenarioRef], *, settings: Settings, reference: str
) -> DashboardData:
    """Consolidate scenarios into one DashboardData, per master-plan decisions 16, 17 and 18.

    scenarios must be non-empty, as guaranteed by discovery.discover_scenarios; reference must
    name one of scenarios' labels, enforced by the DashboardData constructor. Reads each enabled
    chart's source file at most once per (scenario, deck) and writes nothing to disk.
    """
    scenario_order = tuple(scenario.label for scenario in scenarios)

    ordered_by_scenario, deck_dates, timeline_warnings = _load_timelines(
        scenarios, stages_per_deck=settings.chaining.stages_per_deck
    )
    deck_axes, chained_axis, window_lengths, axis_warnings = _build_axes(
        ordered_by_scenario,
        scenario_order,
        deck_dates,
        stages_per_deck=settings.chaining.stages_per_deck,
    )
    registries = _load_registries(scenarios)

    data = DashboardData(
        scenarios=scenario_order, reference=reference, deck_dates=deck_dates, registries=registries
    )
    for warning in (*timeline_warnings, *axis_warnings):
        data.add_warning(warning)
    for deck_date, axis in deck_axes.items():
        data.set_deck_axis(deck_date, axis)
    data.set_chained_axis(chained_axis)

    _load_series(
        data,
        ordered_by_scenario=ordered_by_scenario,
        scenario_order=scenario_order,
        window_lengths=window_lengths,
        registries=registries,
        settings=settings,
    )
    _load_scalars(
        data,
        ordered_by_scenario=ordered_by_scenario,
        scenario_order=scenario_order,
        settings=settings,
    )

    log_step(logger, "Consolidação de dados concluída", valores=data.value_count())
    return data
