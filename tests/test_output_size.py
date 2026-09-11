"""Tests for ticket-032's output size strategy.

`builder.plotly_bundle_bytes`, `builder.output_volumes`, the size-in-mebibytes field write_dashboard
adds to its existing INFO line, and the `output.size_warning_mb` threshold warning (epic decision
E4-3: the payload stays fully embedded, size is measured and warned about, never avoided).

Follows tests/test_builder.py's settings-copy-in-tmp_path pattern throughout. Acceptance
criterion 5's two comparison stores follow tests/test_builder.py's hand-built-store pattern
(Suggested Approach step 5): consolidate the scenario_tree fixture, then append one GHID_UHE
entity via set_entities and add_series, all-None in one store and constant real values of the
same axis lengths in the other.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import plotly.offline  # type: ignore[import-untyped]
import pytest

from dashboard_document import entity_options, sections_by_chart_key
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import (
    build_html,
    output_volumes,
    plotly_bundle_bytes,
    write_dashboard,
)
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.manifest import write_run_manifest
from dessem_dashboard.models.store import DashboardData, EntityRef

_BUILDER_LOGGER_NAME = "dessem_dashboard.dashboard.builder"
_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# Measured on tests.conftest.scenario_tree consolidated with settings matching the repository's
# own settings.json and reference="caso_a": matches tests/test_builder.py's own count.
_ENABLED_CHART_COUNT = 23

# Measured on the same build: bytes_html - bytes_plotly is 238_059 bytes -- about 72_600 the
# base64 logo, about 135_000 the payload's embedded values, the rest the CSS, renderer and
# shell. The range brackets that figure with margin wide enough for a future plotly upgrade to
# shift bytes_plotly without breaking this assertion, narrow enough that doubling or halving the
# controlled share (476_118 or 119_029) falls outside it -- see the non-vacuity assertion below.
_MIN_CONTROLLED_SHARE_BYTES = 150_000
_MAX_CONTROLLED_SHARE_BYTES = 400_000

_BYTES_PER_MIB = 1024 * 1024

_PAYLOAD_OPEN_TAG = '<script id="dashboard-payload" type="application/json">'
_SCRIPT_CLOSE_TAG = "</script>"

_EXTRA_ENTITY_ID = "9001"
_EXTRA_ENTITY_LABEL = "Usina Extra Teste"
_EXTRA_ENTITY_VALUE = 123.45


# --- settings/data builders, following tests/test_builder.py's pattern -------------------------


def _settings_dict(*, size_warning_mb: float = 50, disabled: Sequence[str] = ()) -> dict[str, Any]:
    """Build a settings.json-shaped dict matching the repository's own values.

    Two knobs, and one deliberate divergence from
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
            "size_warning_mb": size_warning_mb,
        },
        "charts": {"disabled": list(disabled)},
    }


def _build_settings(
    tmp_path: Path, *, size_warning_mb: float = 50, disabled: Sequence[str] = ()
) -> Settings:
    """Write settings.json under tmp_path and load it, exercising the real config path."""
    target = tmp_path / "settings.json"
    target.write_text(
        json.dumps(_settings_dict(size_warning_mb=size_warning_mb, disabled=disabled)),
        encoding="utf-8",
    )
    return load_settings(target)


def _build_data(paths: Sequence[Path], *, settings: Settings, reference: str) -> DashboardData:
    """Discover scenarios at paths and consolidate them into one DashboardData."""
    scenarios = discover_scenarios(list(paths))
    return build_dashboard_data(scenarios, settings=settings, reference=reference)


def _extract_payload(document: str) -> dict[str, Any]:
    """Parse the embedded JSON payload out of a built document."""
    start = document.index(_PAYLOAD_OPEN_TAG) + len(_PAYLOAD_OPEN_TAG)
    end = document.index(_SCRIPT_CLOSE_TAG, start)
    return json.loads(document[start:end])


def _add_extra_ghid_uhe_entity(
    data: DashboardData, *, values_factory: Callable[[int], tuple[float | None, ...]]
) -> None:
    """Append one extra GHID_UHE entity to data, on every scenario, deck axis and chained axis.

    values_factory(axis_length) supplies the stored tuple for each axis, so the caller controls
    whether every position is None or a constant real value, while every array's length always
    matches the store's own already-registered TimeAxis instances.
    """
    existing = data.entities("GHID_UHE")
    data.set_entities(
        "GHID_UHE",
        (
            *existing,
            EntityRef(
                entity_id=_EXTRA_ENTITY_ID,
                label=_EXTRA_ENTITY_LABEL,
                sort_key=("ZZZZ_EXTRA_ENTITY",),
            ),
        ),
    )
    for scenario in data.scenarios:
        for deck_date in data.deck_dates:
            axis_length = data.deck_axis(deck_date).length
            data.add_series(
                chart_key="GHID_UHE",
                entity_id=_EXTRA_ENTITY_ID,
                scenario=scenario,
                deck_date=deck_date,
                values=values_factory(axis_length),
            )
        chained_length = data.chained_axis().length
        data.add_series(
            chart_key="GHID_UHE",
            entity_id=_EXTRA_ENTITY_ID,
            scenario=scenario,
            deck_date=None,
            values=values_factory(chained_length),
        )


# --- acceptance criterion 1: output_volumes' six integer keys and their values -----------------


def test_output_volumes_scenario_tree_returns_six_int_keys_with_expected_values(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    output_file = tmp_path / "out" / "dashboard.html"
    write_dashboard(data, settings=settings, output_file=output_file)

    volumes = output_volumes(data, settings=settings, output_file=output_file)

    assert list(volumes.keys()) == [
        "cenarios",
        "decks",
        "graficos",
        "valores",
        "bytes_html",
        "bytes_plotly",
    ]
    assert all(isinstance(value, int) for value in volumes.values())
    assert volumes["cenarios"] == 2
    assert volumes["decks"] == 2
    assert volumes["graficos"] == _ENABLED_CHART_COUNT
    assert volumes["valores"] == data.value_count()
    assert volumes["bytes_html"] == output_file.stat().st_size
    assert volumes["bytes_plotly"] == len(plotly.offline.get_plotlyjs().encode("utf-8"))
    assert volumes["bytes_html"] > volumes["bytes_plotly"]


# --- acceptance criterion 2: the controlled share, as a range that a doubling/halving misses ---


def test_output_volumes_controlled_share_within_measured_range_and_not_vacuous(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    output_file = tmp_path / "out" / "dashboard.html"
    write_dashboard(data, settings=settings, output_file=output_file)

    volumes = output_volumes(data, settings=settings, output_file=output_file)
    controlled_share = volumes["bytes_html"] - volumes["bytes_plotly"]

    assert _MIN_CONTROLLED_SHARE_BYTES <= controlled_share <= _MAX_CONTROLLED_SHARE_BYTES

    # Non-vacuity: a doubled or halved controlled share must miss the same range, so the range
    # is proven tight enough to catch either failure rather than accept any payload size.
    assert not (_MIN_CONTROLLED_SHARE_BYTES <= controlled_share * 2 <= _MAX_CONTROLLED_SHARE_BYTES)
    assert not (_MIN_CONTROLLED_SHARE_BYTES <= controlled_share // 2 <= _MAX_CONTROLLED_SHARE_BYTES)


# --- acceptance criterion 3: the low-threshold variant fires exactly one WARNING ----------------


def test_write_dashboard_low_threshold_emits_exactly_one_warning_naming_size_and_key(
    scenario_tree: dict[str, Path], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = _build_settings(tmp_path, size_warning_mb=1)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    output_file = tmp_path / "out" / "dashboard.html"

    caplog.set_level(logging.WARNING, logger=_BUILDER_LOGGER_NAME)
    returned = write_dashboard(data, settings=settings, output_file=output_file)

    warning_records = [
        record
        for record in caplog.records
        if record.name == _BUILDER_LOGGER_NAME and record.levelno == logging.WARNING
    ]
    assert len(warning_records) == 1

    message = warning_records[0].getMessage()
    size_mib = output_file.stat().st_size / _BYTES_PER_MIB
    assert f"{size_mib:.1f}" in message
    assert f"{settings.output.size_warning_mb:.1f}" in message
    assert "output.size_warning_mb" in message

    assert returned == output_file
    assert output_file.read_text(encoding="utf-8") == build_html(data, settings=settings)


def test_write_dashboard_threshold_exactly_at_measured_size_emits_no_warning(
    scenario_tree: dict[str, Path], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Boundary proof that "exceeds" means strictly greater than, never greater-or-equal.

    Measures the document's exact size, then rebuilds it with size_warning_mb set to that exact
    figure: requirement 4 says the threshold must be exceeded, so a threshold equal to the
    measured size must stay silent. Inverting write_dashboard's comparison operator to `>=`
    would make this test fail.
    """
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    probe_file = tmp_path / "probe" / "dashboard.html"
    write_dashboard(data, settings=settings, output_file=probe_file)
    exact_size_mib = probe_file.stat().st_size / _BYTES_PER_MIB

    boundary_settings = _build_settings(tmp_path, size_warning_mb=exact_size_mib)
    boundary_data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]],
        settings=boundary_settings,
        reference="caso_a",
    )
    boundary_file = tmp_path / "boundary" / "dashboard.html"

    caplog.set_level(logging.WARNING, logger=_BUILDER_LOGGER_NAME)
    write_dashboard(boundary_data, settings=boundary_settings, output_file=boundary_file)

    warning_records = [
        record
        for record in caplog.records
        if record.name == _BUILDER_LOGGER_NAME and record.levelno == logging.WARNING
    ]
    assert len(warning_records) == 0


# --- acceptance criterion 4: the repository default threshold stays silent ---------------------


def test_write_dashboard_repository_default_threshold_emits_no_warning_but_logs_mib_field(
    scenario_tree: dict[str, Path], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    output_file = tmp_path / "out" / "dashboard.html"

    caplog.set_level(logging.INFO, logger=_BUILDER_LOGGER_NAME)
    write_dashboard(data, settings=settings, output_file=output_file)

    records = [record for record in caplog.records if record.name == _BUILDER_LOGGER_NAME]
    warning_records = [record for record in records if record.levelno == logging.WARNING]
    write_info_records = [
        record
        for record in records
        if record.levelno == logging.INFO and "escrito em disco" in record.getMessage()
    ]

    assert len(warning_records) == 0
    assert len(write_info_records) == 1

    message = write_info_records[0].getMessage()
    assert "caminho=" in message
    assert f"bytes={output_file.stat().st_size}" in message
    size_mib = output_file.stat().st_size / _BYTES_PER_MIB
    assert f"{size_mib:.1f}" in message


# --- acceptance criterion 5: the all-None entity is omitted and shrinks the document ------------


def test_ghid_uhe_all_none_entity_is_omitted_and_shrinks_document_versus_real_values(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)

    data_omitted = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    _add_extra_ghid_uhe_entity(data_omitted, values_factory=lambda n: (None,) * n)

    data_present = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    _add_extra_ghid_uhe_entity(data_present, values_factory=lambda n: (_EXTRA_ENTITY_VALUE,) * n)

    output_omitted = tmp_path / "omitted" / "dashboard.html"
    output_present = tmp_path / "present" / "dashboard.html"
    write_dashboard(data_omitted, settings=settings, output_file=output_omitted)
    write_dashboard(data_present, settings=settings, output_file=output_present)

    # Measured: 2_952 bytes -- 2 scenarios x 196 positions (50 + 50 + 96) x 6 characters for
    # "123.45", plus the extra entity's <option>, entities-list entry and series-key overhead,
    # entirely absent from the omitted document.
    size_difference = output_present.stat().st_size - output_omitted.stat().st_size
    assert size_difference >= 1500

    document_omitted = output_omitted.read_text(encoding="utf-8")
    document_present = output_present.read_text(encoding="utf-8")

    section_omitted = sections_by_chart_key(document_omitted)["GHID_UHE"]
    section_present = sections_by_chart_key(document_present)["GHID_UHE"]
    ids_omitted = {entity_id for entity_id, _ in entity_options(section_omitted)}
    ids_present = {entity_id for entity_id, _ in entity_options(section_present)}
    assert _EXTRA_ENTITY_ID not in ids_omitted
    assert _EXTRA_ENTITY_ID in ids_present

    series_omitted = _extract_payload(document_omitted)["charts"]["GHID_UHE"]["series"]
    series_present = _extract_payload(document_present)["charts"]["GHID_UHE"]["series"]
    assert _EXTRA_ENTITY_ID not in series_omitted
    assert _EXTRA_ENTITY_ID in series_present


# --- Testing Requirements: settings-driven volumes, manifest round trip, memoisation -----------


def test_output_volumes_with_varpf_uhe_disabled_lowers_graficos_and_valores(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings_enabled = _build_settings(tmp_path)
    data_enabled = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]],
        settings=settings_enabled,
        reference="caso_a",
    )
    output_enabled = tmp_path / "enabled" / "dashboard.html"
    write_dashboard(data_enabled, settings=settings_enabled, output_file=output_enabled)
    volumes_enabled = output_volumes(
        data_enabled, settings=settings_enabled, output_file=output_enabled
    )

    settings_disabled = _build_settings(tmp_path, disabled=["VARPF_UHE"])
    data_disabled = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]],
        settings=settings_disabled,
        reference="caso_a",
    )
    output_disabled = tmp_path / "disabled" / "dashboard.html"
    write_dashboard(data_disabled, settings=settings_disabled, output_file=output_disabled)
    volumes_disabled = output_volumes(
        data_disabled, settings=settings_disabled, output_file=output_disabled
    )

    assert volumes_enabled["graficos"] == _ENABLED_CHART_COUNT
    assert volumes_disabled["graficos"] == _ENABLED_CHART_COUNT - 1
    assert volumes_disabled["valores"] < volumes_enabled["valores"]


def test_output_volumes_round_trips_through_write_run_manifest(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )
    output_file = tmp_path / "out" / "dashboard.html"
    write_dashboard(data, settings=settings, output_file=output_file)
    volumes = output_volumes(data, settings=settings, output_file=output_file)

    manifest_path = write_run_manifest(
        tmp_path / "manifest", params={}, elapsed_s=0.0, data_volumes=volumes
    )

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["data_volumes"] == volumes


def test_plotly_bundle_bytes_is_memoised_and_matches_direct_computation() -> None:
    plotly_bundle_bytes.cache_clear()
    first = plotly_bundle_bytes()
    second = plotly_bundle_bytes()

    assert first == second == len(plotly.offline.get_plotlyjs().encode("utf-8"))
    assert plotly_bundle_bytes.cache_info().hits == 1
    assert plotly_bundle_bytes.cache_info().misses == 1
