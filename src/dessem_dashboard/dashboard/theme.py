"""Single source of every ONS dashboard visual constant.

Brand and auxiliary colors, tints, non-color layout constants, the scenario color assignment
rule, the shared Plotly layout template and the CSS `:root` custom properties all live here, so
the stylesheet, the chart layout and the scenario palette cannot drift apart.

`planning-context.md` caps the auxiliary palette at three colors combined with the two brand
colors; this module spends that budget on blue, orange and red. The brand manual auxiliary
yellow is deliberately not declared, so that it is not "restored" later as dead code.

This module performs no I/O and configures no logging handler: a pure constants-and-functions
module has no step boundary to audit.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final

BRAND_GREEN: Final[str] = "#486018"
BRAND_GRAY: Final[str] = "#606060"
AUXILIARY_BLUE: Final[str] = "#4F8AD8"
AUXILIARY_ORANGE: Final[str] = "#F76C00"
AUXILIARY_RED: Final[str] = "#D10429"
WHITE: Final[str] = "#FFFFFF"

_HEX_COLOR_PATTERN: Final[re.Pattern[str]] = re.compile(r"#[0-9A-Fa-f]{6}")


def tint(color: str, fraction: float) -> str:
    """Blend color towards WHITE, keeping fraction of its ink.

    Each channel becomes `round(fraction * channel + (1 - fraction) * 255)`, re-rendered as an
    uppercase `#RRGGBB` string.

    Raises:
        ValueError: if fraction is outside the half-open interval (0.0, 1.0], or if color does
            not match `#RRGGBB` in upper or lower case hexadecimal digits.
    """
    if not (0.0 < fraction <= 1.0):
        raise ValueError(f"fraction must be in the half-open interval (0.0, 1.0], got {fraction!r}")
    if _HEX_COLOR_PATTERN.fullmatch(color) is None:
        raise ValueError(f"color must match '#RRGGBB', got {color!r}")
    channels = (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
    r, g, b = (round(fraction * channel + (1 - fraction) * 255) for channel in channels)
    return f"#{r:02X}{g:02X}{b:02X}"


GRID_COLOR: Final[str] = tint(BRAND_GRAY, 0.2)

FONT_FAMILY: Final[str] = "Arial, Helvetica, sans-serif"
FONT_SIZE_PX: Final[int] = 12
CHART_HEIGHT_PX: Final[int] = 450
LOGO_MIN_WIDTH_PX: Final[int] = 220
LOGO_PADDING_PX: Final[int] = 24

SCENARIO_PALETTE: Final[tuple[str, ...]] = (
    BRAND_GREEN,
    AUXILIARY_BLUE,
    AUXILIARY_ORANGE,
    AUXILIARY_RED,
)
TINT_FRACTION: Final[float] = 0.6


def _slot_color(index: int) -> str:
    """Return the color assigned to slot index of the scenario color-assignment rule.

    The first four slots take the palette unshaded; scenarios beyond the fourth reuse it in
    60 percent tints, one further tint level per completed cycle of four.
    """
    base = SCENARIO_PALETTE[index % 4]
    if index < 4:
        return base
    return tint(base, TINT_FRACTION ** (index // 4))


def scenario_colors(scenarios: Sequence[str], *, reference: str) -> dict[str, str]:
    """Assign one color per scenario, reference first so it always takes BRAND_GREEN.

    The slot order is `[reference, *(name for name in scenarios if name != reference)]`, so the
    reference scenario always takes brand green whatever its position in `scenarios`: it is the
    baseline of the Diferença view, and a baseline color that moved with argument order would be
    surprising.

    Raises:
        ValueError: if reference is not in scenarios.
    """
    if reference not in scenarios:
        raise ValueError(f"reference scenario not found in scenarios: {reference!r}")
    slot_order = [reference, *(name for name in scenarios if name != reference)]
    return {name: _slot_color(index) for index, name in enumerate(slot_order)}


def plotly_layout_template(*, date_format: str) -> dict[str, object]:
    """Return the shared, chart-independent Plotly layout.

    Every call returns a freshly built dictionary, so a caller mutating the layout for one chart
    cannot corrupt another chart. The returned mapping never contains a top-level `title` key:
    the chart heading is HTML per epic decision E3-2, and a Plotly title would duplicate it.
    """
    return {
        "font": {"family": FONT_FAMILY, "size": FONT_SIZE_PX, "color": BRAND_GRAY},
        "paper_bgcolor": WHITE,
        "plot_bgcolor": WHITE,
        "hovermode": "x unified",
        "showlegend": True,
        "legend": {
            "orientation": "h",
            "yanchor": "top",
            "y": -0.2,
            "xanchor": "center",
            "x": 0.5,
        },
        "autosize": True,
        "height": CHART_HEIGHT_PX,
        "margin": {"l": 60, "r": 20, "t": 30, "b": 80},
        "xaxis": {
            "type": "date",
            "tickformat": date_format,
            "hoverformat": date_format,
            "gridcolor": GRID_COLOR,
        },
        "yaxis": {
            "gridcolor": GRID_COLOR,
            "zeroline": True,
            "title": {"text": ""},
        },
    }


def css_root_block() -> str:
    """Return a `:root { ... }` CSS declaration carrying every brand custom property.

    `dashboard.css` reaches every value declared here through `var(--ons-*)` and is forbidden
    from containing any color literal; this is the single source of truth those declarations
    read from.
    """
    properties: tuple[tuple[str, str], ...] = (
        ("--ons-green", BRAND_GREEN),
        ("--ons-gray", BRAND_GRAY),
        ("--ons-white", WHITE),
        ("--ons-grid", GRID_COLOR),
        ("--ons-font-family", FONT_FAMILY),
        ("--ons-font-size", f"{FONT_SIZE_PX}px"),
        ("--ons-logo-width", f"{LOGO_MIN_WIDTH_PX}px"),
        ("--ons-logo-padding", f"{LOGO_PADDING_PX}px"),
    )
    declarations = "\n".join(f"  {name}: {value};" for name, value in properties)
    return f":root {{\n{declarations}\n}}\n"
