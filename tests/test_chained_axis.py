"""Tests for dessem_dashboard.dashboard.chained_axis: point positions and tick selection."""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from dessem_dashboard.dashboard.chained_axis import (
    ChainedPoint,
    chained_points,
    chained_tick_indices,
)
from dessem_dashboard.errors import StoreError
from dessem_dashboard.models.store import TimeAxis

_DATE_FORMAT = "%d/%m/%Y %H:%M"
_WINDOW_STAGES = 48
_HALF_HOUR = 0.5
_MARCH_THIRD = datetime(2024, 3, 3, tzinfo=UTC)
_MARCH_FOURTH = datetime(2024, 3, 4, tzinfo=UTC)
_MARCH_FIRST = datetime(2024, 3, 1, tzinfo=UTC)
_TICK_BUDGET = 12
_DAILY_WINDOWS = 30


def _axis(*windows: tuple[datetime, Sequence[float]]) -> TimeAxis:
    """Concatenate `(first_start, durations_hours)` windows into one chained TimeAxis.

    Each stage start is its window's first start plus the durations of the stages before it, so
    gap and overlap fixtures read as data rather than as hand-written timestamps.
    """
    starts: list[pd.Timestamp] = []
    durations: list[float] = []
    for first_start, window_durations in windows:
        elapsed_hours = 0.0
        for duration in window_durations:
            starts.append(pd.Timestamp(first_start) + pd.Timedelta(hours=elapsed_hours))
            durations.append(duration)
            elapsed_hours += duration
    return TimeAxis(key="encadeado", starts=tuple(starts), durations_hours=tuple(durations))


def test_chained_points_calendar_gap_between_windows_leaves_no_empty_span() -> None:
    axis = _axis(
        (datetime(2026, 1, 8, tzinfo=UTC), [_HALF_HOUR] * _WINDOW_STAGES),
        (datetime(2026, 9, 10, tzinfo=UTC), [_HALF_HOUR] * _WINDOW_STAGES),
    )

    points = chained_points(axis, date_format=_DATE_FORMAT)

    assert len(points) == 97
    assert [point.position for point in points[:3]] == [0, 30, 60]
    assert points[47].label == "08/01/2026 23:30"
    assert points[48].position == 1440
    assert points[48].label == "10/09/2026 00:00"
    assert points[96].position == 2880
    assert points[96].label == "11/09/2026 00:00"


def test_chained_points_overlapping_windows_positions_strictly_increase() -> None:
    axis = _axis(
        (_MARCH_THIRD, [_HALF_HOUR] * _WINDOW_STAGES + [6.0, 6.0]),
        (_MARCH_FOURTH, [_HALF_HOUR] * _WINDOW_STAGES),
    )

    points = chained_points(axis, date_format=_DATE_FORMAT)

    assert points[49].label == "04/03/2024 06:00"
    assert points[50].position == 2160
    assert points[50].label == "04/03/2024 00:00"
    positions = [point.position for point in points]
    assert all(current > previous for previous, current in itertools.pairwise(positions))


def test_chained_points_unequal_stage_durations_widths_are_proportional() -> None:
    axis = _axis((_MARCH_THIRD, [0.5, 0.5, 6.0, 1.0]))

    points = chained_points(axis, date_format=_DATE_FORMAT)

    assert [point.position for point in points] == [0, 30, 60, 420, 480]
    assert points[4].label == "03/03/2024 08:00"


def test_chained_points_consecutive_windows_positions_are_contiguous() -> None:
    axis = _axis(
        (_MARCH_THIRD, [_HALF_HOUR] * _WINDOW_STAGES),
        (_MARCH_FOURTH, [_HALF_HOUR] * _WINDOW_STAGES),
    )

    points = chained_points(axis, date_format=_DATE_FORMAT)

    assert len(points) == 97
    assert points[48].position == 1440
    assert points[96].position == 2880


def test_chained_points_positions_are_integers() -> None:
    axis = _axis((_MARCH_THIRD, [0.5, 1.0 / 3.0, 6.0]))

    points = chained_points(axis, date_format=_DATE_FORMAT)

    assert all(type(point.position) is int for point in points)


def test_chained_points_sub_minute_stage_raises_store_error() -> None:
    axis = _axis((_MARCH_THIRD, [0.5, 10 / 3600, 0.5]))

    with pytest.raises(StoreError, match="inferior a um minuto"):
        chained_points(axis, date_format=_DATE_FORMAT)


def test_chained_points_sub_minute_stage_message_names_stage_and_start() -> None:
    axis = _axis((_MARCH_THIRD, [0.5, 10 / 3600, 0.5]))

    with pytest.raises(StoreError, match="'encadeado': o estágio 2 iniciado em 03/03/2024 00:30 "):
        chained_points(axis, date_format=_DATE_FORMAT)


def test_chained_points_empty_axis_raises_store_error() -> None:
    axis = TimeAxis(key="encadeado", starts=(), durations_hours=())

    with pytest.raises(StoreError, match="não tem estágios"):
        chained_points(axis, date_format=_DATE_FORMAT)


def test_chained_points_does_not_mutate_axis() -> None:
    axis = _axis(
        (_MARCH_THIRD, [_HALF_HOUR] * _WINDOW_STAGES + [6.0, 6.0]),
        (_MARCH_FOURTH, [_HALF_HOUR] * _WINDOW_STAGES),
    )
    snapshot = dataclasses.replace(axis)

    chained_points(axis, date_format=_DATE_FORMAT)

    assert axis == snapshot


def test_chained_points_returns_chained_point_values() -> None:
    axis = _axis((_MARCH_THIRD, [1.0]))

    points = chained_points(axis, date_format=_DATE_FORMAT)

    assert points == (
        ChainedPoint(position=0, label="03/03/2024 00:00"),
        ChainedPoint(position=60, label="03/03/2024 01:00"),
    )


def _daily_windows_axis() -> TimeAxis:
    return _axis(
        *(
            (_MARCH_FIRST + timedelta(days=day), [_HALF_HOUR] * _WINDOW_STAGES)
            for day in range(_DAILY_WINDOWS)
        )
    )


def test_chained_tick_indices_single_day_window_picks_two_hour_step() -> None:
    axis = _axis((_MARCH_THIRD, [_HALF_HOUR] * _WINDOW_STAGES))

    indices = chained_tick_indices(axis.starts, max_ticks=_TICK_BUDGET)

    assert indices == [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44]


def test_chained_tick_indices_gap_between_windows_picks_six_hour_step() -> None:
    axis = _axis(
        (datetime(2026, 1, 8, tzinfo=UTC), [_HALF_HOUR] * _WINDOW_STAGES),
        (datetime(2026, 9, 10, tzinfo=UTC), [_HALF_HOUR] * _WINDOW_STAGES),
    )

    indices = chained_tick_indices(axis.starts, max_ticks=_TICK_BUDGET)

    assert indices == [0, 12, 24, 36, 48, 60, 72, 84]


def test_chained_tick_indices_overlapping_windows_keep_repeated_start() -> None:
    axis = _axis(
        (_MARCH_THIRD, [_HALF_HOUR] * _WINDOW_STAGES + [6.0, 6.0]),
        (_MARCH_FOURTH, [_HALF_HOUR] * _WINDOW_STAGES),
    )

    indices = chained_tick_indices(axis.starts, max_ticks=_TICK_BUDGET)

    assert indices == [0, 12, 24, 36, 48, 49, 50, 62, 74, 86]


def test_chained_tick_indices_thirty_daily_windows_thin_day_boundaries() -> None:
    axis = _daily_windows_axis()

    indices = chained_tick_indices(axis.starts, max_ticks=_TICK_BUDGET)

    assert indices == [0, 144, 288, 432, 576, 720, 864, 1008, 1152, 1296]


def test_chained_tick_indices_no_hour_aligned_start_thins_every_start() -> None:
    axis = _axis((datetime(2024, 3, 3, 0, 15, tzinfo=UTC), [1.0] * 5))

    indices = chained_tick_indices(axis.starts, max_ticks=2)

    assert indices == [0, 3]


def test_chained_tick_indices_max_ticks_zero_raises_value_error() -> None:
    axis = _axis((_MARCH_THIRD, [_HALF_HOUR] * _WINDOW_STAGES))

    with pytest.raises(ValueError, match="max_ticks"):
        chained_tick_indices(axis.starts, max_ticks=0)


def test_chained_tick_indices_empty_starts_returns_empty_list() -> None:
    assert chained_tick_indices([], max_ticks=_TICK_BUDGET) == []


def test_chained_tick_indices_never_exceeds_budget() -> None:
    starts = _daily_windows_axis().starts

    for max_ticks in range(1, 16):
        result = chained_tick_indices(starts, max_ticks=max_ticks)

        assert 1 <= len(result) <= max_ticks
        assert result == sorted(set(result))
