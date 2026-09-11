"""Shared document-slicing helpers for the end-to-end chart test modules.

Lifted verbatim from the private helpers ticket-025 wrote in tests/test_charts_sin.py and
ticket-026 extended in tests/test_charts_submarket.py, and exposed here under public names so a
third module (starting with ticket-027's tests/test_charts_hydro.py) can reuse them without
importing a private symbol from a sibling test module -- an import that would work today and
break the moment a simplifier renames the private helper it targets.

A helper module, not a test module: it defines no test_* function, so pytest's default
collection (tests/*.py matched against test_*.py/*_test.py) never picks it up, following the
precedent of tests/fixtures_sintese.py.
"""

from __future__ import annotations

import re

_SECTION_START = '<section class="chart"'
_SECTION_END = "</section>"

_DATA_CHART_PATTERN = re.compile(r'data-chart="([^"]+)"')
_OPTION_PATTERN = re.compile(r'<option value="([^"]*)">([^<]*)</option>')


def chart_section_slices(document: str) -> list[str]:
    """Split document into one slice per `<section class="chart" ...>...</section>` block.

    Sections are concatenated back to back by builder.py's `_chart_sections` with no separator
    and never nest, so the first `</section>` found after each `<section class="chart"` start is
    that same section's own close.
    """
    slices: list[str] = []
    search_start = 0
    while True:
        start = document.find(_SECTION_START, search_start)
        if start == -1:
            break
        end = document.index(_SECTION_END, start) + len(_SECTION_END)
        slices.append(document[start:end])
        search_start = end
    return slices


def _section_chart_key(section: str) -> str:
    """Return section's own `data-chart` attribute value."""
    match = _DATA_CHART_PATTERN.search(section)
    assert match is not None, f"no data-chart attribute found in section slice: {section[:120]!r}"
    return match.group(1)


def sections_by_chart_key(document: str) -> dict[str, str]:
    """Return document's chart section slices keyed by their own `data-chart` attribute.

    Keying by `data-chart`, not by heading text, is what makes every caller's assertions immune
    to curated-title collisions: `data-chart` is unique per section by construction
    (`ChartRegistry.register` rejects a duplicate key), while several headings are shared by
    charts of different groups (for example `Geração` titles both `GHID_UHE` and `GTER_UTE`).
    """
    return {_section_chart_key(section): section for section in chart_section_slices(document)}


def sections_by_group(document: str, group: str) -> list[str]:
    """Return document's chart section slices whose `data-group` equals group, in document order."""
    return [
        section for section in chart_section_slices(document) if f'data-group="{group}"' in section
    ]


def opening_tag(section: str) -> str:
    """Return section's own `<section class="chart" ...>` opening tag, attributes included."""
    match = re.search(r'<section class="chart"[^>]*>', section)
    assert match is not None
    return match.group(0)


def section_heading(section: str) -> str:
    """Return the text of section's single `<h2>` heading."""
    match = re.search(r"<h2>([^<]*)</h2>", section)
    assert match is not None, f"no <h2> found in section slice: {section[:120]!r}"
    return match.group(1)


def entity_label_text(section: str) -> str:
    """Return the text of section's `<label class="entity-label">`."""
    match = re.search(r'<label class="entity-label"[^>]*>([^<]*)</label>', section)
    assert match is not None, f"no entity-label found in section slice: {section[:120]!r}"
    return match.group(1)


def entity_selector_id(section: str) -> str:
    """Return the KEY suffix of section's `<select class="entity-selector" id="entity-KEY">`."""
    match = re.search(r'<select class="entity-selector" id="entity-([^"]+)">', section)
    assert match is not None, f"no entity-selector select found in section slice: {section[:120]!r}"
    return match.group(1)


def entity_options(section: str) -> list[tuple[str, str]]:
    """Return every `<option value="ID">LABEL</option>` pair inside section, in document order."""
    return _OPTION_PATTERN.findall(section)


def nav_slice(document: str) -> str:
    """Return the text between `<nav id="level-nav">` and its following `</nav>`."""
    match = re.search(r'<nav id="level-nav">(.*?)</nav>', document, re.DOTALL)
    assert match is not None
    return match.group(1)
