"""Tests for dessem_dashboard.dashboard.payload."""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pandas as pd
import pytest

from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.payload import build_payload, payload_json
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.data.registries import Registries
from dessem_dashboard.models.store import DashboardData, EntityRef, TimeAxis
from fixtures_sintese import make_sintese_dir

_PAYLOAD_LOGGER_NAME = "dessem_dashboard.dashboard.payload"

# Measured on tests.conftest.scenario_tree with the repository settings.json values
# (chaining.stages_per_deck=48): both deck axes have length 50, the chained axis has length 96,
# value_count() is 16892, warnings() is empty, and 23 charts are enabled by default.
_DECK_AXIS_LENGTH = 50
_CHAINED_AXIS_LENGTH = 96
_VALUE_COUNT = 16_892
_ENABLED_CHART_COUNT = 28
_DECK_KEYS: tuple[str, str] = ("03/03/2024", "04/03/2024")
_CHAINED_KEY = "encadeado"
_HAND_BUILT_DATE = date(2024, 3, 3)
_HAND_BUILT_DECK_KEY = "03/03/2024"


def _settings_dict(*, decimals: int, disabled: Sequence[str]) -> dict[str, Any]:
    """Build a settings.json-shaped dict matching the repository's own values, with knobs.

    time.stage_groups matches the shipped settings.json's three groups -- MILP, PL (covering
    PL, PL.Int.Fix and PL.CalcCMO) and Leitura -- rather than a narrower placeholder, so this
    docstring's own claim holds: spec defect 20 was a prior {"PL": ["PL"]} value that covered
    only one of the fixture's five etapas while claiming to match the repository default.
    """
    return {
        "project": "dessem-dashboard",
        "paths": {
            "output_dir": "output",
            "log_dir": "logs",
            "logo_file": "logo/logo.png",
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
        "time": {
            "stage_groups": {
                "MILP": ["MILP"],
                "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"],
                "Leitura": ["Leitura de Dados e Impressão"],
            },
            "unit_divisor": 60.0,
        },
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


def _build_settings(tmp_path: Path, *, decimals: int = 2, disabled: Sequence[str] = ()) -> Settings:
    """Write settings.json under tmp_path and load it, so tests exercise the real config path."""
    target = tmp_path / "settings.json"
    target.write_text(
        json.dumps(_settings_dict(decimals=decimals, disabled=disabled)), encoding="utf-8"
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


def _hand_built_data(
    *, scenarios: Sequence[str] = ("caso_a",), reference: str = "caso_a", stages: int = 1
) -> DashboardData:
    """Build a minimal store: one deck axis, a matching chained axis, one SIN entity.

    stages sets the axis length in half-hour steps from 2024-03-03T00:00 UTC; the default of one
    stage keeps every caller but the ticket-027 amendment below byte-identical. Registers "" (the
    SIN entity_id) against GHID_SIN, since build_payload reads its entity list from
    data.entities(key) rather than from the series keys directly (requirement 7); every
    hand-built edge-case test below stores a GHID_SIN series under that same entity_id.
    """
    data = DashboardData(
        scenarios=scenarios,
        reference=reference,
        deck_dates=(_HAND_BUILT_DATE,),
        registries=_empty_registries(),
    )
    start = pd.Timestamp("2024-03-03T00:00:00", tz="UTC")
    starts = tuple(start + pd.Timedelta(hours=0.5 * index) for index in range(stages))
    durations_hours = (0.5,) * stages
    axis = TimeAxis(key=_HAND_BUILT_DECK_KEY, starts=starts, durations_hours=durations_hours)
    data.set_deck_axis(_HAND_BUILT_DATE, axis)
    data.set_chained_axis(
        TimeAxis(key=_CHAINED_KEY, starts=starts, durations_hours=durations_hours)
    )
    sin_entity = EntityRef(entity_id="", label="Sistema Interligado", sort_key=())
    data.set_entities("GHID_SIN", [sin_entity])
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
    """Apply _rewrite_metadados_long_name to every deck of every scenario in scenario_tree.

    title_for reads only the primary deck's registry (consolidate._load_registries), but which
    deck is primary is an internal detail this test must not depend on; rewriting every deck
    keeps the assertion correct regardless.
    """
    for scenario_dir in scenario_tree.values():
        for deck_dir in sorted(scenario_dir.iterdir()):
            _rewrite_metadados_long_name(
                deck_dir / "sintese", chart_key=chart_key, long_name=long_name
            )


# --- acceptance criterion 1: top-level keys -----------------------------------------------------


def test_build_payload_scenario_tree_has_ten_top_level_keys_and_scalar_fields(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})

    assert set(payload) == {
        "schema_version",
        "scenarios",
        "reference",
        "deck_dates",
        "chained_key",
        "axes",
        "charts",
        "theme",
        "formats",
        "labels",
    }
    assert payload["schema_version"] == 1
    assert payload["scenarios"] == ["caso_a", "caso_b"]
    assert payload["reference"] == "caso_a"
    assert payload["deck_dates"] == list(_DECK_KEYS)
    assert payload["chained_key"] == _CHAINED_KEY


# --- acceptance criterion 2: axes ---------------------------------------------------------------


def test_build_payload_scenario_tree_axes_shape_and_values(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    axes = payload["axes"]
    assert isinstance(axes, dict)

    assert set(axes) == {"03/03/2024", "04/03/2024", "encadeado"}
    for axis_entry in axes.values():
        assert set(axis_entry) == {"starts", "end"}

    assert len(axes["03/03/2024"]["starts"]) == _DECK_AXIS_LENGTH
    assert axes["03/03/2024"]["starts"][0] == "2024-03-03 00:00"
    assert axes["03/03/2024"]["end"] == "2024-03-04 12:00"
    assert len(axes["encadeado"]["starts"]) == _CHAINED_AXIS_LENGTH
    assert axes["encadeado"]["end"] == "2024-03-05 00:00"


# --- acceptance criterion 3: charts --------------------------------------------------------------


def test_build_payload_scenario_tree_charts_shape_and_representative_values(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    charts = payload["charts"]
    assert isinstance(charts, dict)

    assert len(charts) == _ENABLED_CHART_COUNT
    for entry in charts.values():
        assert set(entry) == {
            "group",
            "kind",
            "selector",
            "title",
            "subtitle",
            "unit",
            "entities",
            "series",
            "scalars",
        }

    assert charts["GHID_SIN"]["entities"] == [{"id": "", "label": "Sistema Interligado"}]
    assert len(charts["GHID_SIN"]["series"][""]["caso_a"]["03/03/2024"]) == _DECK_AXIS_LENGTH
    assert charts["CMO_SBM"]["unit"] == "R$/MWh"
    assert charts["INT_SBP"]["entities"][0]["label"] == "SE (SUDESTE) para S (SUL)"

    # A dedicated time chart (design D7) carries no series or entities and emits exactly its own
    # aggregated group in scalars.
    tempo_milp = charts["TEMPO_MILP"]
    assert tempo_milp["series"] == {}
    assert tempo_milp["entities"] == []
    assert set(tempo_milp["scalars"]) == {"MILP"}


def test_build_payload_uniform_keys_are_empty_for_the_kind_that_does_not_apply(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    charts = payload["charts"]

    assert charts["GHID_SIN"]["scalars"] == {}
    assert charts["CUSTO_PRESENTE"]["entities"] == []
    assert charts["CUSTO_PRESENTE"]["series"] == {}


# --- acceptance criterion 4: subtitle from E3-2 -------------------------------------------------


def test_build_payload_subtitle_uses_registry_long_name_when_it_differs_from_title(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    _rewrite_metadados_everywhere(
        scenario_tree, chart_key="CMO_SBM", long_name="Custo Marginal de Operação"
    )
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    charts = payload["charts"]

    assert charts["CMO_SBM"]["subtitle"] == "Custo Marginal de Operação"
    assert charts["CMO_SBM"]["title"] == "CMO"
    assert charts["GHID_SIN"]["subtitle"] is None


def test_build_payload_subtitle_is_none_when_title_for_returns_none(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    _rewrite_metadados_everywhere(scenario_tree, chart_key="GHID_SIN", long_name=None)
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})

    assert payload["charts"]["GHID_SIN"]["subtitle"] is None


# --- acceptance criterion 5: rounding and JSON safety -------------------------------------------


def test_payload_json_scenario_tree_rounds_values_and_has_no_nan_or_less_than(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path, decimals=2)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    text = payload_json(payload)

    chained_series = payload["charts"]["GHID_SIN"]["series"][""]["caso_a"]["encadeado"]
    for element in chained_series:
        assert element == round(element, 2)
    assert "NaN" not in text
    assert "<" not in text


# --- requirement 3a: omission warning ------------------------------------------------------------


def test_build_payload_stored_chart_omitted_from_catalogue_logs_one_warning_naming_it(
    scenario_tree: dict[str, Path], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    consolidate_settings = _build_settings(tmp_path, disabled=())
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]],
        settings=consolidate_settings,
        reference="caso_a",
    )
    payload_settings = _build_settings(tmp_path, disabled=("GHID_SIN",))

    caplog.set_level(logging.WARNING, logger=_PAYLOAD_LOGGER_NAME)
    build_payload(data, settings=payload_settings, scenario_colors={}, plotly_layout={})

    matching = [
        record
        for record in caplog.records
        if record.name == _PAYLOAD_LOGGER_NAME and "GHID_SIN" in record.getMessage()
    ]
    assert len(matching) == 1


# --- requirement 8: axis-length invariant across the whole payload -----------------------------


def test_build_payload_every_series_array_length_matches_its_axis_length(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    axes = payload["axes"]
    charts = payload["charts"]
    assert isinstance(axes, dict)
    assert isinstance(charts, dict)

    checked_axis_keys: set[str] = set()
    for entry in charts.values():
        if entry["kind"] != "SERIES":
            continue
        for by_scenario in entry["series"].values():
            for by_axis in by_scenario.values():
                for axis_key, values in by_axis.items():
                    checked_axis_keys.add(axis_key)
                    assert len(values) == len(axes[axis_key]["starts"])

    assert checked_axis_keys == {"03/03/2024", "04/03/2024", "encadeado"}


# --- decision 18: a deck missing from one scenario --------------------------------------------


def _build_partial_scenario_tree(tmp_path: Path) -> dict[str, Path]:
    """Two decks for caso_a; caso_b lacks the second deck (04/03/2024)."""
    deck_names_and_starts = (
        ("deck_um", datetime(2024, 3, 3, tzinfo=UTC)),
        ("deck_dois", datetime(2024, 3, 4, tzinfo=UTC)),
    )
    tree: dict[str, Path] = {}
    for scenario_name, deck_count in (("caso_a", 2), ("caso_b", 1)):
        scenario_dir = tmp_path / scenario_name
        for deck_name, deck_start in deck_names_and_starts[:deck_count]:
            make_sintese_dir(
                scenario_dir / deck_name / "sintese",
                first_stage_start=deck_start,
                n_stages=50,
                half_hour_stages=48,
                long_stage_hours=6.0,
            )
        tree[scenario_name] = scenario_dir
    return tree


def test_build_payload_scenario_missing_a_deck_omits_that_axis_key_but_keeps_chained(
    tmp_path: Path,
) -> None:
    tree = _build_partial_scenario_tree(tmp_path / "tree")
    settings = _build_settings(tmp_path)
    data = _build_data([tree["caso_a"], tree["caso_b"]], settings=settings, reference="caso_a")

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    ghid_sin_series = payload["charts"]["GHID_SIN"]["series"][""]

    assert "04/03/2024" not in ghid_sin_series["caso_b"]
    assert "03/03/2024" in ghid_sin_series["caso_b"]
    assert len(ghid_sin_series["caso_b"]["encadeado"]) == _CHAINED_AXIS_LENGTH


# --- decision 18: a missing series source file for one (scenario, deck) -----------------------


def test_build_payload_missing_series_file_omits_only_that_scenario_and_deck(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    (scenario_tree["caso_b"] / "deck_dois" / "sintese" / "GTER_UTE.parquet").unlink()
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    entry = payload["charts"]["GTER_UTE"]

    assert set(entry) == {
        "group",
        "kind",
        "selector",
        "title",
        "subtitle",
        "unit",
        "entities",
        "series",
        "scalars",
    }
    assert entry["entities"] != []
    assert "04/03/2024" not in entry["series"]["1"]["caso_b"]
    assert "03/03/2024" in entry["series"]["1"]["caso_b"]


# --- rounding on a hand-built store --------------------------------------------------------------


def test_build_payload_rounds_stored_value_to_requested_decimals(tmp_path: Path) -> None:
    data = _hand_built_data()
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_HAND_BUILT_DATE,
        values=[1.23456],
    )

    settings_two = _build_settings(tmp_path, decimals=2)
    payload_two = build_payload(data, settings=settings_two, scenario_colors={}, plotly_layout={})
    assert payload_two["charts"]["GHID_SIN"]["series"][""]["caso_a"]["03/03/2024"] == [1.23]

    settings_three = _build_settings(tmp_path, decimals=3)
    payload_three_first = build_payload(
        data, settings=settings_three, scenario_colors={}, plotly_layout={}
    )
    assert payload_three_first["charts"]["GHID_SIN"]["series"][""]["caso_a"]["03/03/2024"] == [
        1.235
    ]


def test_build_payload_rounded_negative_zero_normalises_to_positive_zero(tmp_path: Path) -> None:
    data = _hand_built_data()
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_HAND_BUILT_DATE,
        values=[-0.00001],
    )
    settings = _build_settings(tmp_path, decimals=2)

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    rounded = payload["charts"]["GHID_SIN"]["series"][""]["caso_a"]["03/03/2024"][0]

    assert rounded == 0.0
    assert math.copysign(1.0, rounded) == 1.0
    assert "-0.0" not in payload_json(payload)


def test_build_payload_scenario_with_no_stored_dates_for_entity_contributes_no_key(
    tmp_path: Path,
) -> None:
    data = _hand_built_data(scenarios=("caso_a", "caso_b"), reference="caso_a")
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_HAND_BUILT_DATE,
        values=[1.0],
    )
    settings = _build_settings(tmp_path)

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    ghid_sin_series = payload["charts"]["GHID_SIN"]["series"][""]

    assert "caso_a" in ghid_sin_series
    assert "caso_b" not in ghid_sin_series


# --- None survives build_payload as None and payload_json as JSON null -------------------------


def test_build_payload_and_payload_json_none_value_survives_as_none_and_null(
    tmp_path: Path,
) -> None:
    """A None slot inside an otherwise-populated array (decision 17) survives untouched.

    ticket-027 amendment (requirement 9): the original one-stage version of this test stored
    values=[None], a single-element array that is trivially all-None -- exactly the shape
    ticket-027 requirement 1 now omits. That collided with this test's own intent, which is
    decision 17's per-slot null, not requirement 1's whole-array omission. Two stages with one
    real value keep the array partially covered, so it survives both rules untouched.
    """
    data = _hand_built_data(stages=2)
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_HAND_BUILT_DATE,
        values=[1.0, None],
    )
    settings = _build_settings(tmp_path)

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    assert payload["charts"]["GHID_SIN"]["series"][""]["caso_a"]["03/03/2024"] == [1.0, None]

    text = payload_json(payload)
    decoded = json.loads(text)
    assert decoded["charts"]["GHID_SIN"]["series"][""]["caso_a"]["03/03/2024"] == [1.0, None]


# --- requirement 2: the entities/series lockstep, at the level that implements it --------------


def test_build_payload_entities_and_series_lockstep_drops_the_all_none_entity_only(
    tmp_path: Path,
) -> None:
    """Two entities on one chart: the all-None one is dropped from both entities and series.

    ticket-027 requirement 9's third change: the omission rule of requirement 1 and the lockstep
    of requirement 2 live in payload.py, but the ticket as originally written left them with no
    test at payload.py's own level -- tests/test_charts_hydro.py only covers the rendered
    consequence, one module away. This asserts entities equals the surviving id set exactly, not
    merely a subset of it, which is what "lockstep by construction" means.
    """
    data = _hand_built_data(stages=2)
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_HAND_BUILT_DATE,
        values=[1.0, 2.0],
    )
    second_entity = EntityRef(entity_id="dropped", label="Usina Ausente", sort_key=("z",))
    data.set_entities("GHID_SIN", [*data.entities("GHID_SIN"), second_entity])
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="dropped",
        scenario="caso_a",
        deck_date=_HAND_BUILT_DATE,
        values=[None, None],
    )
    settings = _build_settings(tmp_path)

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    entry = payload["charts"]["GHID_SIN"]

    surviving_ids = {entity["id"] for entity in entry["entities"]}
    assert surviving_ids == {""}
    assert set(entry["series"]) == surviving_ids
    assert entry["series"][""]["caso_a"]["03/03/2024"] == [1.0, 2.0]


# --- NaN in the store makes payload_json raise ValueError ---------------------------------------


def test_payload_json_nan_value_raises_value_error(tmp_path: Path) -> None:
    data = _hand_built_data()
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_HAND_BUILT_DATE,
        values=[float("nan")],
    )
    settings = _build_settings(tmp_path)
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})

    with pytest.raises(ValueError, match="Out of range float values are not JSON compliant"):
        payload_json(payload)


# --- an entity label containing '<' is escaped and round-trips ---------------------------------


def test_payload_json_escapes_less_than_in_entity_label_and_round_trips(tmp_path: Path) -> None:
    data = _hand_built_data()
    data.set_entities("GHID_SIN", [EntityRef(entity_id="", label="A < B", sort_key=())])
    data.add_series(
        chart_key="GHID_SIN",
        entity_id="",
        scenario="caso_a",
        deck_date=_HAND_BUILT_DATE,
        values=[1.0],
    )
    settings = _build_settings(tmp_path)
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})

    text = payload_json(payload)
    assert "<" not in text
    assert "\\u003C" in text
    decoded = json.loads(text)
    assert decoded["charts"]["GHID_SIN"]["entities"][0]["label"] == "A < B"


# --- dedicated scalar charts: one series each, and no division by time.unit_divisor ------------


def test_build_payload_dedicated_scalar_charts_each_carry_one_series(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path, decimals=2)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    charts = payload["charts"]

    # Design D7 splits the two combined scalar charts into seven dedicated ones, each slicing one
    # series out of its source_file's single aggregation. With the default costs.total_parcels =
    # ["PRESENTE", "FUTURO"], CUSTOS aggregates to {PRESENTE, FUTURO, TOTAL} (dropping VIOLACOES
    # and PEQUENAS PENALIDADES), and with the shipped three-group time.stage_groups TEMPO
    # aggregates to {MILP, PL, Leitura, TOTAL}; each dedicated chart then emits exactly its own.
    dedicated = {
        "CUSTO_PRESENTE": "PRESENTE",
        "CUSTO_FUTURO": "FUTURO",
        "CUSTO_TOTAL": "TOTAL",
        "TEMPO_MILP": "MILP",
        "TEMPO_PL": "PL",
        "TEMPO_LEITURA": "Leitura",
        "TEMPO_TOTAL": "TOTAL",
    }
    for chart_key, series_name in dedicated.items():
        scalars = charts[chart_key]["scalars"]
        assert set(scalars) == {series_name}
        for by_scenario in scalars.values():
            assert set(by_scenario) == {"caso_a", "caso_b"}
            for by_deck in by_scenario.values():
                assert set(by_deck) == set(_DECK_KEYS)

    raw = pd.read_parquet(
        scenario_tree["caso_a"] / "deck_um" / "sintese" / "TEMPO.parquet", engine="pyarrow"
    )
    raw_pl_seconds = float(
        raw.loc[raw["etapa"].isin(["PL", "PL.Int.Fix", "PL.CalcCMO"]), "tempo"].sum()
    )
    expected_pl_minutes = round(raw_pl_seconds / 60.0, 2)
    pl_value = charts["TEMPO_PL"]["scalars"]["PL"]["caso_a"]["03/03/2024"]
    assert pl_value == expected_pl_minutes
    # Proves the payload carries the converted minutes figure, not the raw seconds one: the Y axis
    # claims minutes (FALLBACK_UNITS["TEMPO"] = "min"), so the division must have happened.
    assert pl_value != round(raw_pl_seconds, 2)


# --- caplog: the two INFO log lines and their volume fields ------------------------------------


def test_build_payload_and_payload_json_log_info_lines_with_volume_fields(
    scenario_tree: dict[str, Path], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], settings=settings, reference="caso_a"
    )

    caplog.set_level(logging.INFO, logger=_PAYLOAD_LOGGER_NAME)
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    text = payload_json(payload)

    messages = [
        record.getMessage() for record in caplog.records if record.name == _PAYLOAD_LOGGER_NAME
    ]
    assert any(f"graficos={_ENABLED_CHART_COUNT}" in message for message in messages)
    assert any(f"valores={_VALUE_COUNT}" in message for message in messages)
    assert any(f"caracteres={len(text)}" in message for message in messages)
