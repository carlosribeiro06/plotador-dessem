"""Deck timeline and chaining logic (Appendix A.3 of the master plan).

Turns `EST.parquet` into an immutable `DeckTimeline`, orders decks by `deck_date` (never by
folder name, per decision 4), and reports chaining problems — short decks, gaps, overlaps and
missing decks across scenarios — as Portuguese warning strings rather than exceptions, per
decision 18. Structural violations of the stage table itself (a non-contiguous `estagio` or a
non-positive stage duration) remain `SchemaError`, since a timeline that fails those checks has
no usable axis at all. This module reads only `EST.parquet`, through `data.readers.read_registry`,
and never converts a timezone (decision 10).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from itertools import pairwise

import numpy as np
import pandas as pd

from dessem_dashboard.data.readers import read_registry
from dessem_dashboard.errors import SchemaError
from dessem_dashboard.logging_setup import log_step
from dessem_dashboard.models.entities import DeckRef, DeckTimeline, Stage

logger = logging.getLogger(__name__)

_EST_FILE_NAME = "EST.parquet"
_DATE_FORMAT = "%d/%m/%Y"


def _validate_stage_sequence(estagio: pd.Series, *, deck_name: str) -> None:
    """Raise SchemaError unless estagio, once sorted, is exactly 1, 2, ..., len(estagio)."""
    expected = np.arange(1, len(estagio) + 1, dtype="int64")
    actual = estagio.to_numpy()
    mismatches = np.flatnonzero(actual != expected)
    if mismatches.size == 0:
        return
    first_offending_index = int(expected[mismatches[0]])
    raise SchemaError(
        f"Deck '{deck_name}': sequência de 'estagio' em EST.parquet não é contígua a partir de "
        f"1; primeiro índice esperado e ausente: {first_offending_index}"
    )


def _validate_stage_durations(
    frame: pd.DataFrame, durations_hours: pd.Series, *, deck_name: str
) -> None:
    """Raise SchemaError when a stage's data_fim is not strictly later than its data_inicio."""
    invalid = durations_hours <= 0
    if not invalid.any():
        return
    first_stage = int(frame.loc[invalid, "estagio"].iloc[0])
    raise SchemaError(
        f"Deck '{deck_name}': estágio {first_stage} em EST.parquet tem 'data_fim' não posterior "
        f"a 'data_inicio'"
    )


def load_deck_timeline(deck: DeckRef) -> DeckTimeline:
    """Read deck's EST.parquet and build its immutable, ordered stage timeline.

    Sorts by 'estagio', then requires that sequence to start at 1 and be contiguous and every
    stage's 'data_fim' to be strictly later than its 'data_inicio' (SchemaError naming deck and
    the first offending stage otherwise). duration_hours is computed from the timestamps, never
    from 'duracao_patamar'. deck_date is `min(data_inicio).date()`, never `deck.name`.
    DataFileError propagates unchanged from `read_registry` when EST.parquet is missing.
    """
    frame = read_registry(deck.sintese_dir / _EST_FILE_NAME, "EST")
    frame = frame.sort_values("estagio").reset_index(drop=True)

    _validate_stage_sequence(frame["estagio"], deck_name=deck.name)

    durations_hours = (frame["data_fim"] - frame["data_inicio"]).dt.total_seconds() / 3600.0
    _validate_stage_durations(frame, durations_hours, deck_name=deck.name)

    stages = tuple(
        Stage(index=int(estagio), start=start, end=end, duration_hours=float(duration))
        for estagio, start, end, duration in zip(
            frame["estagio"], frame["data_inicio"], frame["data_fim"], durations_hours, strict=True
        )
    )
    deck_date = frame["data_inicio"].min().date()

    log_step(
        logger,
        "Timeline de deck carregada",
        deck=deck.name,
        data=deck_date.strftime(_DATE_FORMAT),
        estagios=len(stages),
    )
    return DeckTimeline(deck=deck, deck_date=deck_date, stages=stages)


def chaining_window(timeline: DeckTimeline, *, stages_per_deck: int) -> tuple[Stage, ...]:
    """Return timeline's first stages_per_deck stages, or every stage when it has fewer.

    Emits nothing itself: a shortfall is reported by validate_chaining, never here.
    """
    return timeline.stages[:stages_per_deck]


def order_timelines(timelines: Iterable[DeckTimeline]) -> tuple[DeckTimeline, ...]:
    """Sort timelines by deck_date, then by deck.name as a deterministic tie-break.

    Never sorts by folder name as the primary key. Raises SchemaError when two timelines share a
    deck_date: within one scenario that is a data error, not a warning (requirement 6).
    """
    ordered = tuple(
        sorted(timelines, key=lambda timeline: (timeline.deck_date, timeline.deck.name))
    )
    for previous, current in pairwise(ordered):
        if previous.deck_date == current.deck_date:
            raise SchemaError(
                f"Decks '{previous.deck.name}' e '{current.deck.name}' compartilham a mesma data "
                f"de deck ({current.deck_date.strftime(_DATE_FORMAT)})"
            )
    return ordered


def validate_chaining(ordered: Sequence[DeckTimeline], *, stages_per_deck: int) -> list[str]:
    """Return one Portuguese warning per short deck, gap and overlap in ordered's chaining windows.

    Never raises for these problems (decision 18): a short deck, a gap or an overlap degrades to
    a warning so a partially comparable dashboard still renders. Returns an empty list when every
    deck reaches stages_per_deck and consecutive windows meet exactly.
    """
    windows = [
        (timeline, chaining_window(timeline, stages_per_deck=stages_per_deck))
        for timeline in ordered
    ]

    warnings: list[str] = [
        f"Deck de {timeline.deck_date.strftime(_DATE_FORMAT)} tem apenas {len(window)} "
        f"estágio(s) na janela de encadeamento; esperado {stages_per_deck} estágio(s)"
        for timeline, window in windows
        if len(window) < stages_per_deck
    ]

    for (timeline_a, window_a), (timeline_b, window_b) in pairwise(windows):
        if not window_a or not window_b:
            continue
        window_end = window_a[-1].end
        next_start = window_b[0].start
        date_a = timeline_a.deck_date.strftime(_DATE_FORMAT)
        date_b = timeline_b.deck_date.strftime(_DATE_FORMAT)
        if next_start > window_end:
            warnings.append(
                f"Encadeamento apresenta lacuna entre os decks de {date_a} e {date_b}: a janela "
                f"de {date_a} termina em {window_end}, antes do início de {date_b} em {next_start}"
            )
        elif next_start < window_end:
            warnings.append(
                f"Encadeamento apresenta sobreposição entre os decks de {date_a} e {date_b}: a "
                f"janela de {date_a} termina em {window_end}, após o início de {date_b} em "
                f"{next_start}"
            )

    total_chained_stages = sum(len(window) for _, window in windows)
    log_step(
        logger,
        "Janela de encadeamento validada",
        decks=len(ordered),
        estagios_encadeados=total_chained_stages,
        avisos=len(warnings),
    )
    return warnings


def align_deck_dates(
    scenario_timelines: Mapping[str, Sequence[DeckTimeline]],
) -> tuple[tuple[date, ...], list[str]]:
    """Return the sorted union of deck dates across scenarios, plus one warning per missing pair.

    A deck present in one scenario and absent from another becomes a gap here, reported as a
    warning (decision 18) instead of a misaligned curve.
    """
    dates_by_scenario: dict[str, set[date]] = {
        label: {timeline.deck_date for timeline in timelines}
        for label, timelines in scenario_timelines.items()
    }
    union_dates = tuple(sorted(set[date]().union(*dates_by_scenario.values())))

    warnings = [
        f"Cenário '{label}' não possui deck para a data {missing_date.strftime(_DATE_FORMAT)}, "
        f"presente em outro(s) cenário(s)"
        for label, scenario_dates in dates_by_scenario.items()
        for missing_date in union_dates
        if missing_date not in scenario_dates
    ]
    return union_dates, warnings
