"""In-memory dashboard data store: the Python mirror of the embedded JSON payload.

`DashboardData` holds every value ticket-018's consolidation writes and every value ticket-020's
serialisation later reads: series value arrays keyed by (chart, entity, scenario, deck), one time
axis per deck plus one chained axis, scalar bar-chart values for CUSTOS/TEMPO, the entity lists
shown in each chart's selector, and deduplicated Portuguese warnings. It performs no I/O and
enforces its invariants — known scenario, matching axis length, no duplicate series key — at
insertion time, rather than leaving them to be discovered once the JSON payload reaches the
browser. No public method accepts the floating-point NaN sentinel as a missing value: pass
`None`, which `json.dumps` later serialises as the valid JSON token `null`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

import pandas as pd

from dessem_dashboard.data.registries import Registries
from dessem_dashboard.errors import StoreError


@dataclass(frozen=True, slots=True)
class EntityRef:
    """One entity selectable within a chart: a plant, a submarket, an interchange pair.

    `entity_id` is the stable key used both as the internal dictionary key and as the JSON
    object key ticket-020 emits; `label` is the Portuguese display text shown in the dashboard's
    selector. `sort_key` elements must be pairwise comparable across every `EntityRef` sharing a
    chart key: `entities()` sorts by `sort_key`, and comparing tuples whose elements are of
    different types (for example an `int` next to a `str`) raises `TypeError` at sort time, not
    `StoreError`. Keep `sort_key` homogeneous per chart (all `int`, or all `str`, ...).
    """

    entity_id: str
    label: str
    sort_key: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class TimeAxis:
    """One shared time axis: a deck's stage windows, or the chained axis across decks.

    `starts` and `durations_hours` must have equal length: `add_series` validates every stored
    values array against `length`, and a mismatched axis would make that validation meaningless
    while still reporting a `length` that disagrees with the duration data.
    """

    key: str
    starts: tuple[pd.Timestamp, ...]
    durations_hours: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.starts) != len(self.durations_hours):
            raise StoreError(
                f"Eixo de tempo '{self.key}' é inconsistente: {len(self.starts)} início(s) em "
                f"'starts' contra {len(self.durations_hours)} duração(ões) em 'durations_hours'"
            )

    @property
    def length(self) -> int:
        """Return the number of stages on this axis."""
        return len(self.starts)


class DashboardData:
    """In-memory mirror of the dashboard's embedded JSON data store.

    Mutable while ticket-018 populates it; ticket-020 serialises the result and never mutates it
    further afterwards, so enforcing immutability past construction is out of scope here.
    """

    scenarios: Final[tuple[str, ...]]
    reference: Final[str]
    deck_dates: Final[tuple[date, ...]]
    registries: Final[Registries]

    def __init__(
        self,
        *,
        scenarios: Sequence[str],
        reference: str,
        deck_dates: Sequence[date],
        registries: Registries,
    ) -> None:
        """Build an empty store for scenarios, validating the scenario list and the reference.

        Raises StoreError when scenarios is empty, when it contains a duplicate, or when
        reference is not one of scenarios.
        """
        scenarios_tuple = tuple(scenarios)
        if not scenarios_tuple:
            raise StoreError("Lista de cenários vazia: informe ao menos um cenário")
        duplicates = sorted({name for name in scenarios_tuple if scenarios_tuple.count(name) > 1})
        if duplicates:
            raise StoreError(
                f"Cenário(s) duplicado(s) na lista de cenários: {', '.join(duplicates)}"
            )
        if reference not in scenarios_tuple:
            raise StoreError(
                f"Cenário de referência '{reference}' não consta na lista de cenários "
                f"({', '.join(scenarios_tuple)})"
            )

        self.scenarios = scenarios_tuple
        self.reference = reference
        self.deck_dates = tuple(deck_dates)
        self.registries = registries

        self._axes: dict[date | None, TimeAxis] = {}
        self._series: dict[tuple[str, str, str, date | None], tuple[float | None, ...]] = {}
        self._scalars: dict[str, dict[tuple[str, str, date], float | None]] = {}
        self._entities: dict[str, tuple[EntityRef, ...]] = {}
        self._warnings: list[str] = []

    def set_deck_axis(self, deck_date: date, axis: TimeAxis) -> None:
        """Register axis as the time axis for deck_date, replacing any axis set earlier."""
        self._axes[deck_date] = axis

    def set_chained_axis(self, axis: TimeAxis) -> None:
        """Register axis as the chained time axis, replacing any axis set earlier."""
        self._axes[None] = axis

    def deck_axis(self, deck_date: date) -> TimeAxis:
        """Return the time axis registered for deck_date.

        Raises StoreError when no axis was ever registered for deck_date.
        """
        try:
            return self._axes[deck_date]
        except KeyError as err:
            raise StoreError(
                f"Nenhum eixo de tempo registrado para o deck de {deck_date.strftime('%d/%m/%Y')}"
            ) from err

    def chained_axis(self) -> TimeAxis:
        """Return the registered chained time axis.

        Raises StoreError when no chained axis was ever registered.
        """
        try:
            return self._axes[None]
        except KeyError as err:
            raise StoreError("Nenhum eixo de tempo encadeado foi registrado") from err

    def add_series(
        self,
        *,
        chart_key: str,
        entity_id: str,
        scenario: str,
        deck_date: date | None,
        values: Sequence[float | None],
    ) -> None:
        """Store values for one (chart_key, entity_id, scenario, deck_date) combination.

        deck_date=None targets the chained axis; any other date targets that deck's axis.
        Freezes values to a tuple, so a later mutation of the caller's list cannot corrupt the
        stored payload. A None entry in values is a missing value and survives unchanged; never
        pass the NaN sentinel. Raises StoreError when scenario is not one of self.scenarios, when no
        axis was ever registered for deck_date, when len(values) differs from that axis' length
        (naming both lengths), or when this four-part key was already populated.
        """
        axis_label = "encadeado" if deck_date is None else deck_date.strftime("%d/%m/%Y")

        if scenario not in self.scenarios:
            raise StoreError(
                f"Cenário desconhecido '{scenario}' ao adicionar a série '{chart_key}' "
                f"(entidade '{entity_id}', deck {axis_label})"
            )

        try:
            axis = self._axes[deck_date]
        except KeyError as err:
            raise StoreError(
                f"Nenhum eixo de tempo registrado para o deck {axis_label}, necessário para a "
                f"série '{chart_key}' (entidade '{entity_id}', cenário '{scenario}')"
            ) from err

        values_tuple = tuple(values)
        if len(values_tuple) != axis.length:
            raise StoreError(
                f"Série '{chart_key}' (entidade '{entity_id}', cenário '{scenario}', deck "
                f"{axis_label}) tem {len(values_tuple)} valor(es), mas o eixo de tempo tem "
                f"{axis.length} posição(ões)"
            )

        key = (chart_key, entity_id, scenario, deck_date)
        if key in self._series:
            raise StoreError(
                f"Série já registrada para '{chart_key}' (entidade '{entity_id}', cenário "
                f"'{scenario}', deck {axis_label})"
            )
        self._series[key] = values_tuple

    def series(
        self, chart_key: str, entity_id: str, scenario: str, deck_date: date | None
    ) -> tuple[float | None, ...]:
        """Return the stored value array for this four-part key.

        Raises StoreError when the key was never populated by add_series.
        """
        try:
            return self._series[(chart_key, entity_id, scenario, deck_date)]
        except KeyError as err:
            axis_label = "encadeado" if deck_date is None else deck_date.strftime("%d/%m/%Y")
            raise StoreError(
                f"Série não encontrada: '{chart_key}' (entidade '{entity_id}', cenário "
                f"'{scenario}', deck {axis_label})"
            ) from err

    def has_series(
        self, chart_key: str, entity_id: str, scenario: str, deck_date: date | None
    ) -> bool:
        """Return whether this four-part key was populated by add_series, without raising."""
        return (chart_key, entity_id, scenario, deck_date) in self._series

    def set_entities(self, chart_key: str, entities: Sequence[EntityRef]) -> None:
        """Register entities as chart_key's entity list, sorted by EntityRef.sort_key.

        Replaces any entity list registered earlier for chart_key. Sorting relies on sort_key
        being pairwise comparable across entities; see EntityRef's docstring.
        """
        self._entities[chart_key] = tuple(sorted(entities, key=lambda entity: entity.sort_key))

    def entities(self, chart_key: str) -> tuple[EntityRef, ...]:
        """Return chart_key's registered entities in sort_key order.

        Returns an empty tuple for a chart with no registered entities.
        """
        return self._entities.get(chart_key, ())

    def add_scalar(
        self,
        *,
        chart_key: str,
        series_name: str,
        scenario: str,
        deck_date: date,
        value: float | None,
    ) -> None:
        """Store one scalar bar-chart value, for the CUSTOS and TEMPO charts.

        deck_date is a plain date, never None: a scalar bar chart has one bar per deck and no
        chained variant, unlike add_series' deck_date=None sentinel for the chained axis. value
        may be None for a missing value; never pass the NaN sentinel. Raises StoreError when
        scenario is not one of self.scenarios. A repeated (series_name, scenario, deck_date) key
        overwrites the earlier value rather than raising, since the store never receives more
        than one value per key from ticket-018's per-deck, per-scenario consolidation loop.
        """
        if scenario not in self.scenarios:
            raise StoreError(
                f"Cenário desconhecido '{scenario}' ao adicionar o escalar '{chart_key}' "
                f"(série '{series_name}', deck {deck_date.strftime('%d/%m/%Y')})"
            )
        key = (series_name, scenario, deck_date)
        self._scalars.setdefault(chart_key, {})[key] = value

    def scalars(self, chart_key: str) -> Mapping[tuple[str, str, date], float | None]:
        """Return chart_key's registered scalars, keyed by (series_name, scenario, deck_date).

        Returns an empty mapping for a chart with no registered scalars.
        """
        return self._scalars.get(chart_key, {})

    def add_warning(self, message: str) -> None:
        """Append message to the warning list, skipping it when already present."""
        if message not in self._warnings:
            self._warnings.append(message)

    def warnings(self) -> tuple[str, ...]:
        """Return every distinct warning message, in first-insertion order."""
        return tuple(self._warnings)

    def value_count(self) -> int:
        """Return the total number of stored series values plus the number of stored scalars.

        Each series contributes len(values); a None entry still counts, since it occupies a
        slot in the JSON payload. Each stored scalar counts as one, regardless of its value.
        """
        series_total = sum(len(values) for values in self._series.values())
        scalar_total = sum(len(chart_scalars) for chart_scalars in self._scalars.values())
        return series_total + scalar_total
