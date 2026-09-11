"""Tests for dessem_dashboard.dashboard.theme."""

from __future__ import annotations

import re

import pytest

from dessem_dashboard.dashboard.theme import (
    AUXILIARY_BLUE,
    AUXILIARY_ORANGE,
    BRAND_GRAY,
    BRAND_GREEN,
    CHART_HEIGHT_PX,
    GRID_COLOR,
    WHITE,
    css_root_block,
    plotly_layout_template,
    scenario_colors,
    tint,
)

# --- tint ---------------------------------------------------------------------------------


def test_tint_brand_green_60_percent_returns_expected_hex() -> None:
    assert tint("#486018", 0.6) == "#91A074"


def test_tint_brand_gray_20_percent_returns_expected_hex() -> None:
    assert tint("#606060", 0.2) == "#DFDFDF"


def test_tint_white_full_fraction_returns_white() -> None:
    assert tint("#FFFFFF", 1.0) == "#FFFFFF"


def test_tint_lowercase_hex_input_returns_uppercase_output() -> None:
    assert tint("#486018".lower(), 0.6) == "#91A074"


def test_tint_missing_hash_raises_value_error() -> None:
    with pytest.raises(ValueError, match="color"):
        tint("486018", 0.6)


def test_tint_short_hex_raises_value_error() -> None:
    with pytest.raises(ValueError, match="color"):
        tint("#48601", 0.6)


def test_tint_invalid_hex_digits_raises_value_error() -> None:
    with pytest.raises(ValueError, match="color"):
        tint("#GGGGGG", 0.6)


def test_tint_zero_fraction_raises_value_error() -> None:
    with pytest.raises(ValueError, match="fraction"):
        tint("#486018", 0.0)


def test_tint_fraction_above_one_raises_value_error() -> None:
    with pytest.raises(ValueError, match="fraction"):
        tint("#486018", 1.5)


def test_grid_color_equals_tint_of_brand_gray() -> None:
    assert tint(BRAND_GRAY, 0.2) == GRID_COLOR


# --- scenario_colors ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scenarios", "reference"),
    [
        (("only",), "only"),
        (("a", "b"), "a"),
        (("a", "b"), "b"),
        (("a", "b", "c"), "b"),
        (("a", "b", "c", "d"), "a"),
        (("a", "b", "c", "d"), "d"),
        (("a", "b", "c", "d", "e"), "c"),
    ],
)
def test_scenario_colors_reference_always_gets_brand_green(
    scenarios: tuple[str, ...], reference: str
) -> None:
    result = scenario_colors(scenarios, reference=reference)
    assert result[reference] == BRAND_GREEN


def test_scenario_colors_three_scenarios_reference_third_position_matches_exact_mapping() -> None:
    result = scenario_colors(("caso_a", "caso_b", "caso_c"), reference="caso_c")
    assert result == {
        "caso_c": BRAND_GREEN,
        "caso_a": AUXILIARY_BLUE,
        "caso_b": AUXILIARY_ORANGE,
    }


def test_scenario_colors_five_scenarios_fifth_slot_uses_tint_and_all_distinct() -> None:
    result = scenario_colors(("s1", "s2", "s3", "s4", "s5"), reference="s1")
    assert result["s5"] == tint(BRAND_GREEN, 0.6)
    assert len(set(result.values())) == 5


def test_scenario_colors_eight_scenarios_returns_pairwise_distinct_values() -> None:
    scenarios = tuple(f"caso_{i}" for i in range(8))
    result = scenario_colors(scenarios, reference="caso_0")
    assert len(set(result.values())) == 8


def test_scenario_colors_reference_not_in_scenarios_raises_value_error() -> None:
    with pytest.raises(ValueError, match="reference"):
        scenario_colors(("a", "b"), reference="z")


# --- plotly_layout_template -----------------------------------------------------------------

_DATE_FORMAT = "%d/%m/%Y %H:%M"


def test_plotly_layout_template_font_family_size_and_color() -> None:
    layout = plotly_layout_template(date_format=_DATE_FORMAT)
    font = layout["font"]
    assert isinstance(font, dict)
    assert font["family"] == "Arial, Helvetica, sans-serif"
    assert font["size"] == 12
    assert font["color"] == BRAND_GRAY


def test_plotly_layout_template_background_colors_are_white() -> None:
    layout = plotly_layout_template(date_format=_DATE_FORMAT)
    assert layout["paper_bgcolor"] == WHITE
    assert layout["plot_bgcolor"] == WHITE


def test_plotly_layout_template_hovermode_is_x_unified() -> None:
    layout = plotly_layout_template(date_format=_DATE_FORMAT)
    assert layout["hovermode"] == "x unified"


def test_plotly_layout_template_showlegend_true_and_horizontal_legend_below_plot() -> None:
    layout = plotly_layout_template(date_format=_DATE_FORMAT)
    assert layout["showlegend"] is True
    legend = layout["legend"]
    assert isinstance(legend, dict)
    assert legend["orientation"] == "h"
    assert legend["y"] < 0


def test_plotly_layout_template_autosize_true_and_height_matches_constant() -> None:
    layout = plotly_layout_template(date_format=_DATE_FORMAT)
    assert layout["autosize"] is True
    assert layout["height"] == CHART_HEIGHT_PX


def test_plotly_layout_template_xaxis_type_date_and_tick_hover_format() -> None:
    layout = plotly_layout_template(date_format=_DATE_FORMAT)
    xaxis = layout["xaxis"]
    assert isinstance(xaxis, dict)
    assert xaxis["type"] == "date"
    assert xaxis["tickformat"] == _DATE_FORMAT
    assert xaxis["hoverformat"] == _DATE_FORMAT


def test_plotly_layout_template_xaxis_gridcolor_matches_grid_color() -> None:
    layout = plotly_layout_template(date_format=_DATE_FORMAT)
    xaxis = layout["xaxis"]
    assert isinstance(xaxis, dict)
    assert xaxis["gridcolor"] == GRID_COLOR


def test_plotly_layout_template_yaxis_gridcolor_zeroline_and_empty_title() -> None:
    layout = plotly_layout_template(date_format=_DATE_FORMAT)
    yaxis = layout["yaxis"]
    assert isinstance(yaxis, dict)
    assert yaxis["gridcolor"] == GRID_COLOR
    assert yaxis["zeroline"] is True
    assert yaxis["title"] == {"text": ""}


def test_plotly_layout_template_has_no_title_key() -> None:
    layout = plotly_layout_template(date_format=_DATE_FORMAT)
    assert "title" not in layout


def test_plotly_layout_template_two_calls_return_distinct_instances() -> None:
    first = plotly_layout_template(date_format=_DATE_FORMAT)
    second = plotly_layout_template(date_format=_DATE_FORMAT)
    assert first is not second
    assert first["xaxis"] is not second["xaxis"]


# --- css_root_block --------------------------------------------------------------------------

_EXPECTED_CUSTOM_PROPERTY_NAMES = (
    "--ons-green",
    "--ons-gray",
    "--ons-white",
    "--ons-grid",
    "--ons-font-family",
    "--ons-font-size",
    "--ons-logo-width",
    "--ons-logo-padding",
)


def test_css_root_block_starts_with_root_selector() -> None:
    assert css_root_block().startswith(":root {")


def test_css_root_block_custom_property_names_in_documented_order() -> None:
    text = css_root_block()
    names = re.findall(r"--[a-z-]+", text)
    assert tuple(names) == _EXPECTED_CUSTOM_PROPERTY_NAMES


def test_css_root_block_contains_green_grid_and_logo_width_substrings() -> None:
    text = css_root_block()
    assert "--ons-green: #486018;" in text
    assert "--ons-grid: #DFDFDF;" in text
    assert "--ons-logo-width: 393px;" in text
