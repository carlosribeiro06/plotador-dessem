"""End-to-end verification of the thermal plant chart (ticket-029).

This is a verification ticket, not a rendering one: ticket-027 generalised the plant rendering
path over `AggregationLevel` and `EntitySelector`, and ticket-028's filter fragment is driven by
`PLANT_SELECTORS`, a set of selector values rather than a group name, so `GTER_UTE` -- the entire
`UTE` level -- is already covered by construction. This module proves that on the shipped
fixture rather than asserting it, and changes no source file at all (requirement 7): if any
assertion below cannot be made to pass, the defect belongs to ticket-027 or ticket-028, which own
`builder.py` and `payload.py`, not to a new mechanism invented here.

`Geração` is the exact curated title of both `GHID_UHE` and `GTER_UTE` (Background), so every
heading and option-list assertion is scoped to the single `data-group="UTE"` section slice
through the shared helpers of `tests/dashboard_document.py` -- an unscoped substring assertion
would be satisfied by the wrong chart, the incidental-match failure mode of Epic 2 learnings
section 7. `dashboard.js` is untouched by this level (`GTER_UTE` reuses every JavaScript path
ticket-023/025/026 wrote for `HYDRO_PLANT`), so this module reads no asset, only `builder.py`'s
and `payload.py`'s output, following the settings-copy-in-`tmp_path` pattern of
`tests/test_builder.py`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dashboard_document import (
    entity_label_text,
    entity_options,
    entity_selector_id,
    nav_slice,
    opening_tag,
    section_heading,
    sections_by_chart_key,
    sections_by_group,
)
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import build_html
from dessem_dashboard.dashboard.payload import build_payload
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.models.store import DashboardData
from fixtures_sintese import make_sintese_dir

_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)

# Deck-key and chained-key value counts, reused from tests/test_charts_hydro.py's own constant
# (Current State: 50, 50 and 96 values for 03/03/2024, 04/03/2024 and encadeado).
_DECK_KEYS_AND_LENGTHS: tuple[tuple[str, int], ...] = (
    ("03/03/2024", 50),
    ("04/03/2024", 50),
    ("encadeado", 96),
)

# The three-plant tree's deck names, starts and base seed, mirroring tests/conftest.py's
# build_scenario_tree exactly except for thermal_codes, which build_scenario_tree never forwards
# (Suggested Approach step 3; the exact trap that cost ticket-018 a correction).
_THREE_PLANT_DECK_NAMES: tuple[str, str] = ("deck_um", "deck_dois")
_THREE_PLANT_DECK_STARTS: tuple[datetime, datetime] = (
    datetime(2024, 3, 3, tzinfo=UTC),
    datetime(2024, 3, 4, tzinfo=UTC),
)
_THREE_PLANT_BASE_SEED = 42


# --- settings/data/document/payload builders, following tests/test_builder.py's pattern -------


def _settings_dict(*, disabled: Sequence[str] = ()) -> dict[str, Any]:
    """Build a settings.json-shaped dict matching the repository's own values, with a knob."""
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
            "size_warning_mb": 50,
        },
        "charts": {"disabled": list(disabled)},
    }


def _build_settings(tmp_path: Path, *, disabled: Sequence[str] = ()) -> Settings:
    """Write settings.json under tmp_path and load it, exercising the real config path."""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(_settings_dict(disabled=disabled)), encoding="utf-8")
    return load_settings(target)


def _build_data(paths: Sequence[Path], *, settings: Settings, reference: str) -> DashboardData:
    """Discover scenarios at paths and consolidate them into one DashboardData."""
    scenarios = discover_scenarios(list(paths))
    return build_dashboard_data(scenarios, settings=settings, reference=reference)


def _build_document(
    paths: Sequence[Path], tmp_path: Path, *, reference: str, disabled: Sequence[str] = ()
) -> str:
    settings = _build_settings(tmp_path, disabled=disabled)
    data = _build_data(paths, settings=settings, reference=reference)
    return build_html(data, settings=settings)


def _build_payload_dict(
    paths: Sequence[Path], tmp_path: Path, *, reference: str, disabled: Sequence[str] = ()
) -> dict[str, object]:
    settings = _build_settings(tmp_path, disabled=disabled)
    data = _build_data(paths, settings=settings, reference=reference)
    return build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})


# --- the three-plant tree: proves the option list follows the file, not the registry -----------


def _build_three_thermal_plant_tree(root: Path) -> dict[str, Path]:
    """Two scenarios, two decks each, mirroring build_scenario_tree's own shape exactly except
    for thermal_codes=(1, 2, 3), which build_scenario_tree never forwards (its generator default
    is thermal_codes=(1, 2)). Requirement 5: this is what proves the entity-GTER_UTE option list
    is read from the stored file rather than derived from a fixed registry size -- an assertion
    that would be unsatisfiable, hence vacuous, on the shared scenario_tree fixture.
    """
    tree: dict[str, Path] = {}
    seed_offset = 0
    for scenario_name in ("caso_a", "caso_b"):
        scenario_dir = root / scenario_name
        for deck_name, deck_start in zip(
            _THREE_PLANT_DECK_NAMES, _THREE_PLANT_DECK_STARTS, strict=True
        ):
            make_sintese_dir(
                scenario_dir / deck_name / "sintese",
                first_stage_start=deck_start,
                n_stages=50,
                half_hour_stages=48,
                long_stage_hours=6.0,
                thermal_codes=(1, 2, 3),
                seed=_THREE_PLANT_BASE_SEED + seed_offset,
            )
            seed_offset += 1
        tree[scenario_name] = scenario_dir
    return tree


# --- reusable checkers over the single UTE section slice, shared with the non-vacuity proofs ---


def _check_ute_document_facts(document: str) -> None:
    """Assert the Current State's document facts, scoped to the single data-group="UTE" slice
    (acceptance criterion 1 and requirement 2's level-navigation clause).

    A single checker so that mutating a copy of the document (the non-vacuity proof below) and
    the direct positive test share one definition of "correct" -- the pattern
    tests/test_charts_filters.py's _check_plant_filter_markup established.
    """
    sections = sections_by_group(document, "UTE")
    assert len(sections) == 1
    section = sections[0]

    opening = opening_tag(section)
    assert 'data-chart="GTER_UTE"' in opening
    assert 'data-selector="THERMAL_PLANT"' in opening
    assert opening.endswith(" hidden>")

    assert section.count("<h2>") == 1
    assert section_heading(section) == "Geração"
    assert "chart-subtitle" not in section

    assert entity_label_text(section) == "Usina termelétrica"
    assert entity_selector_id(section) == "GTER_UTE"
    assert entity_options(section) == [("1", "TERMICA_1"), ("2", "TERMICA_2")]

    assert ">Usinas termelétricas<" in nav_slice(document)


def _check_ute_filter_fragment(document: str) -> None:
    """Assert the UTE section carries ticket-028's filter fragment exactly once, with both
    inputs' ids and data-filter roles, the empty-state paragraph, and the plot div after it
    inside the slice (acceptance criterion 2). The nine-key set and the 18-occurrence count
    across the whole document already belong to tests/test_charts_filters.py; this checks only
    what is specific to the GTER_UTE slice.
    """
    section = sections_by_group(document, "UTE")[0]

    assert section.count('class="plant-filters"') == 1
    assert section.count('class="plant-filter"') == 2
    assert 'id="filter-name-GTER_UTE"' in section
    assert 'data-filter="name"' in section
    assert 'id="filter-code-GTER_UTE"' in section
    assert 'data-filter="code"' in section
    assert section.count('<p class="filter-empty" hidden>') == 1

    filters_index = section.index('class="plant-filters"')
    plot_index = section.index('<div class="plot" id="plot-GTER_UTE">')
    assert filters_index < plot_index


def _check_ute_section_inner_order(document: str) -> None:
    """Assert the slice's inner order: heading, entity label, entity select, filter fragment,
    plot div, by index within the slice (Testing Requirements)."""
    section = sections_by_group(document, "UTE")[0]
    heading_index = section.index("<h2>")
    label_index = section.index('<label class="entity-label"')
    select_index = section.index('<select class="entity-selector"')
    filters_index = section.index('class="plant-filters"')
    plot_index = section.index('<div class="plot"')
    assert heading_index < label_index < select_index < filters_index < plot_index


def _check_three_thermal_plant_options(document: str) -> None:
    """Assert entity-GTER_UTE holds exactly three options ending with TERMICA_3 (acceptance
    criterion 4, first half)."""
    section = sections_by_chart_key(document)["GTER_UTE"]
    assert entity_options(section) == [("1", "TERMICA_1"), ("2", "TERMICA_2"), ("3", "TERMICA_3")]


def _mutate_ute_section(document: str, transform: Callable[[str], str]) -> str:
    """Apply transform to the UTE section's own slice text, leaving the rest of document
    untouched. Mirrors tests/test_charts_filters.py's _mutate_function_body: mutating the whole
    document text directly would risk hitting the wrong one of the (up to) nine identical
    plant-filter literals first -- exactly the trap ticket-028 hit removing the first of two
    identical literals -- so the replace is scoped to this chart's own slice, which is unique in
    the document by its data-chart="GTER_UTE" attribute.
    """
    section = sections_by_group(document, "UTE")[0]
    mutated_section = transform(section)
    assert mutated_section != section, "transform did not change the UTE section"
    return document.replace(section, mutated_section, 1)


# --- acceptance criterion 1 and requirement 2: document facts, scoped to the UTE slice ----------


def test_document_ute_section_singular_opening_tag_heading_label_and_options(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    _check_ute_document_facts(document)


def test_document_facts_check_is_not_vacuous_when_label_reads_hidraulica(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """Suggested Approach step 6: changing "Usina termelétrica" to "Usina hidrelétrica" inside
    the UTE slice must fail the document-facts check, proving it is not vacuous."""
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    _check_ute_document_facts(document)

    mutated = _mutate_ute_section(
        document, lambda section: section.replace("Usina termelétrica", "Usina hidrelétrica", 1)
    )
    with pytest.raises(AssertionError):
        _check_ute_document_facts(mutated)


# --- acceptance criterion 2: the filter fragment and its position inside the UTE slice ----------


def test_document_ute_section_filter_fragment_matches_ticket_028_contract(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    _check_ute_filter_fragment(document)


def test_filter_fragment_check_is_not_vacuous_without_data_filter_code(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """Suggested Approach step 6: removing data-filter="code" from the UTE slice must fail the
    filter-fragment check, proving it is not vacuous."""
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    _check_ute_filter_fragment(document)

    mutated = _mutate_ute_section(
        document, lambda section: section.replace('data-filter="code"', "", 1)
    )
    with pytest.raises(AssertionError):
        _check_ute_filter_fragment(mutated)


# --- Testing Requirements: the slice's inner element order --------------------------------------


def test_document_ute_section_inner_order_is_heading_label_select_filter_and_plot(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    _check_ute_section_inner_order(document)


# --- acceptance criterion 3: the GTER_UTE payload entry -----------------------------------------


def test_payload_gter_ute_unit_title_subtitle_entities_scalars_and_series_lengths(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    entry = payload["charts"]["GTER_UTE"]  # type: ignore[index]

    assert entry["unit"] == "MW"  # type: ignore[index]
    assert entry["title"] == "Geração"  # type: ignore[index]
    assert entry["subtitle"] is None  # type: ignore[index]
    assert entry["entities"] == [  # type: ignore[index]
        {"id": "1", "label": "TERMICA_1"},
        {"id": "2", "label": "TERMICA_2"},
    ]
    assert entry["scalars"] == {}  # type: ignore[index]

    series = entry["series"]  # type: ignore[index]
    for entity in entry["entities"]:  # type: ignore[index,union-attr]
        series_for_entity = series[entity["id"]]  # type: ignore[index]
        for scenario in ("caso_a", "caso_b"):
            for axis_key, expected_length in _DECK_KEYS_AND_LENGTHS:
                assert len(series_for_entity[scenario][axis_key]) == expected_length


def test_fixture_payload_gter_ute_values_are_none_or_rounded_to_two_decimals(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    payload = _build_payload_dict(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    series = payload["charts"]["GTER_UTE"]["series"]  # type: ignore[index]

    for by_scenario in series.values():  # type: ignore[union-attr]
        for by_axis in by_scenario.values():
            for values in by_axis.values():
                for value in values:
                    assert value is None or value == round(value, 2)


# --- acceptance criterion 4, first half: the option list follows the file, not the registry -----


def test_three_plant_tree_selector_holds_three_options_ending_with_termica_3(
    tmp_path: Path,
) -> None:
    tree = _build_three_thermal_plant_tree(tmp_path / "three_plant_tree")
    document = _build_document([tree["caso_a"], tree["caso_b"]], tmp_path, reference="caso_a")
    _check_three_thermal_plant_options(document)


def test_three_plant_options_check_is_not_vacuous_on_the_shared_two_plant_fixture(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """Pitfall guard: build_scenario_tree's thermal_codes default to (1, 2), so the three-option
    assertion must fail on the shared fixture, proving it is not satisfied by incidental fixture
    shape (Epic 2 learnings section 7) and that it genuinely depends on the regenerated tree."""
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    with pytest.raises(AssertionError):
        _check_three_thermal_plant_options(document)


def test_three_plant_options_assertion_is_not_vacuous_against_a_truncated_expectation(
    tmp_path: Path,
) -> None:
    """Suggested Approach step 6: dropping the third option from the regenerated tree's own
    expectation must fail against the real three-plant document, proving the check is not
    satisfied by a mistaken two-option expectation either."""
    tree = _build_three_thermal_plant_tree(tmp_path / "three_plant_tree")
    document = _build_document([tree["caso_a"], tree["caso_b"]], tmp_path, reference="caso_a")
    section = sections_by_chart_key(document)["GTER_UTE"]
    actual_options = entity_options(section)
    assert actual_options == [("1", "TERMICA_1"), ("2", "TERMICA_2"), ("3", "TERMICA_3")]

    truncated_expectation = actual_options[:-1]
    with pytest.raises(AssertionError):
        assert actual_options == truncated_expectation


# --- acceptance criterion 4, second half: the level is registry-driven, disabled cleanly --------


def test_disabling_gter_ute_removes_section_group_and_nav_button_but_keeps_eight_uhe_sections(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]],
        tmp_path,
        reference="caso_a",
        disabled=["GTER_UTE"],
    )

    assert 'id="chart-GTER_UTE"' not in document
    assert sections_by_group(document, "UTE") == []
    assert ">Usinas termelétricas<" not in nav_slice(document)
    assert len(sections_by_group(document, "UHE")) == 8


# --- pinning the collision that makes the scoping of every assertion above necessary ------------


def test_unscoped_document_contains_geracao_heading_exactly_twice(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """Requirement 1 and Suggested Approach step 5: "Geração" titles both GHID_UHE and GTER_UTE,
    so the whole, unscoped document must contain exactly two "<h2>Geração</h2>" headings. If this
    count ever becomes one, either a chart disappeared or a title changed, and both are worth
    failing on -- and it is what justifies every other heading assertion in this module being
    scoped to its own section slice instead of searched over the whole document."""
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    assert document.count("<h2>Geração</h2>") == 2


# --- Testing Requirements: the selector is wired to the right level, nowhere else ---------------


def test_document_data_selector_thermal_plant_once_and_hydro_plant_eight_times(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    """data-selector="THERMAL_PLANT" must appear on exactly one section of the whole document,
    and data-selector="HYDRO_PLANT" on exactly eight, so a selector wired to the wrong level --
    or a thermal chart silently rendered with the hydro label -- fails here rather than in a
    browser."""
    document = _build_document(
        [scenario_tree["caso_a"], scenario_tree["caso_b"]], tmp_path, reference="caso_a"
    )
    assert document.count('data-selector="THERMAL_PLANT"') == 1
    assert document.count('data-selector="HYDRO_PLANT"') == 8
