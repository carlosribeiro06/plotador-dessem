"""Continuous-axis geometry for the chained (Encadeado) time axis.

The chained axis concatenates deck windows that may leave a calendar gap or overlap each other, so
plotting real timestamps would produce an empty span or make X run backwards. This module places
every chained point at the elapsed time of the stages before it, in integer minutes, and keeps the
real timestamp of each point as a formatted label. It also selects which stage starts carry a tick
on that axis.

This module performs no I/O and configures no logging handler: a pure-functions module has no
step boundary to audit.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import pandas as pd

from dessem_dashboard.errors import StoreError
from dessem_dashboard.models.store import TimeAxis

_MINUTES_PER_HOUR = 60
_HOUR_STEPS: Final[tuple[int, ...]] = (1, 2, 3, 6, 12, 24)


@dataclass(frozen=True, slots=True)
class ChainedPoint:
    """One point of the continuous chained axis.

    `position` is the elapsed time in integer minutes from the start of the chained axis;
    `label` is the real timestamp of the point, formatted with the caller's `date_format`.
    """

    position: int
    label: str


def chained_points(axis: TimeAxis, *, date_format: str) -> tuple[ChainedPoint, ...]:
    """Place every stage start of a chained axis, plus its end, on a continuous minute scale.

    Point `i < axis.length` sits at the cumulative duration of stages `0..i-1`; the terminal point
    `axis.length` sits at the total plotted duration and is labelled with the end of the last
    stage. Positions never read `axis.starts`, so a calendar gap or overlap between consecutive
    windows does not alter any position. No timezone conversion is applied: labels render the
    stored wall time.

    Args:
        axis: the chained time axis; `durations_hours` is in hours.
        date_format: a `strftime` pattern used for every label.

    Returns:
        `axis.length + 1` points with strictly increasing integer positions in minutes, the first
        at 0.

    Raises:
        StoreError: if the axis has no stages, or if a stage is so short (under about 30 seconds)
            that it rounds to zero minutes of width.
    """
    if axis.length == 0:
        raise StoreError(
            f"Eixo de tempo '{axis.key}' não tem estágios: "
            "impossível posicionar o eixo encadeado contínuo"
        )
    cumulative_hours = itertools.accumulate(axis.durations_hours, initial=0.0)
    positions = [round(hours * _MINUTES_PER_HOUR) for hours in cumulative_hours]
    end = axis.starts[-1] + pd.Timedelta(hours=axis.durations_hours[-1])
    labels = [start.strftime(date_format) for start in axis.starts]
    labels.append(end.strftime(date_format))
    for i, (previous, current) in enumerate(itertools.pairwise(positions)):
        if current == previous:
            raise StoreError(
                f"Eixo de tempo '{axis.key}': o estágio {i + 1} iniciado em {labels[i]} tem "
                "duração inferior a um minuto e não pode ser posicionado no eixo encadeado "
                "contínuo"
            )
    return tuple(
        ChainedPoint(position=position, label=label)
        for position, label in zip(positions, labels, strict=True)
    )


def _is_hour_aligned(start: pd.Timestamp) -> bool:
    """Whether `start` falls exactly on a whole hour of its own wall clock."""
    return start.minute == start.second == start.microsecond == start.nanosecond == 0


def chained_tick_indices(starts: Sequence[pd.Timestamp], *, max_ticks: int) -> list[int]:
    """Choose which stage starts of a chained axis carry a tick.

    Ticks sit on hour-aligned starts. The finest step of `(1, 2, 3, 6, 12, 24)` hours whose
    candidates (hour-aligned starts with `hour % step == 0`) are non-empty and number at most
    `max_ticks` wins. When even the 24-hour step is too dense, the candidates of the largest step
    that has any (or every start, when none is hour-aligned) are thinned by keeping every
    `ceil(count / max_ticks)`-th one. Each start's own wall-clock hour is read: no timezone
    conversion is applied. A start repeated by an overlapping window can therefore yield two ticks
    with the same label, which is intended because labels show real time.

    Args:
        starts: the stage starts of the chained axis (`TimeAxis.starts`); the terminal point of the
            axis is not part of it and is never a tick.
        max_ticks: the tick budget; at least 1.

    Returns:
        Ascending indices into `starts`, at most `max_ticks` of them; `[]` if `starts` is empty.

    Raises:
        ValueError: if `max_ticks` is below 1.
    """
    if max_ticks < 1:
        raise ValueError(f"max_ticks must be >= 1, got {max_ticks!r}")
    if not starts:
        return []
    candidates_by_step: dict[int, list[int]] = {}
    for step in _HOUR_STEPS:
        candidates = [
            index
            for index, start in enumerate(starts)
            if _is_hour_aligned(start) and start.hour % step == 0
        ]
        if candidates and len(candidates) <= max_ticks:
            return candidates
        candidates_by_step[step] = candidates
    pool = next(
        (candidates_by_step[step] for step in reversed(_HOUR_STEPS) if candidates_by_step[step]),
        list(range(len(starts))),
    )
    return pool[:: math.ceil(len(pool) / max_ticks)]
