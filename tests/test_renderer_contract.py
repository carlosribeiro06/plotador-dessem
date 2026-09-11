"""Tests for the dashboard.js chart renderer core.

Epic decision E3-1 forbids executing any JavaScript in this suite (`node` and `npm` are not
installed), so these tests are the static, Python-side half of the renderer's contract: they read
`dashboard.js` as text and check it by regular expression, and they compare the `KEYS` object it
declares against a real payload built from the `scenario_tree` fixture. The behavioural half is
`docs/checklist-manual-dashboard.md`, walked manually once per release.
"""

from __future__ import annotations

import importlib.resources
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard.builder import build_html
from dessem_dashboard.dashboard.payload import build_payload
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.models.store import DashboardData

_ASSETS_PACKAGE = "dessem_dashboard.dashboard.assets"
_JS_ASSET = "dashboard.js"

_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)
_DOCS_CHECKLIST = Path(__file__).resolve().parent.parent / "docs" / "checklist-manual-dashboard.md"

# The ticket-021 placeholder this file replaces, verbatim; requirement 9's "longer than the stub"
# test compares against its exact length rather than an arbitrary threshold.
_ORIGINAL_STUB_TEXT = "// Implemented by ticket-022 (JavaScript chart renderer core)."

_SEVEN_DOCUMENTED_MEMBERS = (
    "payload",
    "state",
    "axisKey",
    "buildTraces",
    "renderChart",
    "renderActiveGroup",
    "init",
)

_BANNED_NETWORK_AND_EVAL_TOKENS = (
    "fetch(",
    "XMLHttpRequest",
    "import(",
    "eval(",
    "document.write",
    "http://",
    "https://",
)

_KEYS_BLOCK_PATTERN = re.compile(r"const KEYS = Object\.freeze\(\{(.*?)\}\);", re.DOTALL)
_KEYS_ENTRY_PATTERN = re.compile(r'([A-Z_]+):\s*"([^"]+)"')


# --- shared helpers ------------------------------------------------------------------------------


def _read_js_asset() -> str:
    """Read dashboard.js exactly as build_html itself does, through importlib.resources."""
    return (
        importlib.resources.files(_ASSETS_PACKAGE).joinpath(_JS_ASSET).read_text(encoding="utf-8")
    )


def _extract_keys(asset_text: str) -> dict[str, str]:
    """Extract the KEYS object literal's {IDENTIFIER: "value"} pairs from asset_text by regex.

    Regex-based, not a JS parse: epic decision E3-1 forbids executing JavaScript in the test
    suite, so a static extraction is the only way to inspect the declared contract.
    """
    block_match = _KEYS_BLOCK_PATTERN.search(asset_text)
    assert block_match is not None, "KEYS object literal not found in dashboard.js"
    return dict(_KEYS_ENTRY_PATTERN.findall(block_match.group(1)))


def _collect_keys(value: object) -> set[str]:
    """Recursively collect every dict key nested anywhere inside value, including inside lists."""
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            assert isinstance(key, str)
            keys.add(key)
            keys |= _collect_keys(nested)
    elif isinstance(value, list):
        for item in value:
            keys |= _collect_keys(item)
    return keys


def _settings_dict() -> dict[str, Any]:
    """Build a settings.json-shaped dict matching the repository's own values."""
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
        "charts": {"disabled": []},
    }


def _build_settings(tmp_path: Path) -> Settings:
    """Write settings.json under tmp_path and load it, exercising the real config path."""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(_settings_dict()), encoding="utf-8")
    return load_settings(target)


def _build_data(scenario_tree: dict[str, Path], settings: Settings) -> DashboardData:
    """Discover and consolidate scenario_tree's two scenarios into one DashboardData."""
    scenarios = discover_scenarios([scenario_tree["caso_a"], scenario_tree["caso_b"]])
    return build_dashboard_data(scenarios, settings=settings, reference="caso_a")


def _build_payload_from_scenario_tree(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> dict[str, object]:
    """Consolidate scenario_tree and build its payload, with placeholder theme arguments.

    scenario_colors and plotly_layout are supplied as {}: build_payload neither validates nor
    interprets them (its own docstring), and the recursive key set this test inspects only needs
    the "scenario_colors" and "layout" keys to exist under "theme", not that they carry data.
    """
    settings = _build_settings(tmp_path)
    data = _build_data(scenario_tree, settings)
    return build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})


def _dashboard_js_slice(document: str) -> str:
    """Return the exact text between <script id="dashboard-js"> and its following </script>."""
    open_tag = '<script id="dashboard-js">'
    start = document.index(open_tag) + len(open_tag)
    end = document.index("</script>", start)
    return document[start:end]


def _read_checklist() -> str:
    return _DOCS_CHECKLIST.read_text(encoding="utf-8")


# --- acceptance criterion 1: single global, seven members, ASCII-only --------------------------


def test_dashboard_js_declares_single_global_with_seven_members_and_is_pure_ascii() -> None:
    text = _read_js_asset()

    assert text.count("window.DessemDashboard") == 1

    assignment_start = text.index("window.DessemDashboard")
    assignment_end = text.index("};", assignment_start) + len("};")
    assignment_text = text[assignment_start:assignment_end]
    for member in _SEVEN_DOCUMENTED_MEMBERS:
        assert member in assignment_text, f"member '{member}' not found in the assignment block"

    assert text.count("Object.freeze({") == 1
    assert text.isascii() is True


# --- acceptance criterion 2: no network or dynamic-evaluation constructs -----------------------


def test_dashboard_js_has_no_network_or_eval_construct_and_disables_cloud_button() -> None:
    text = _read_js_asset()

    for token in _BANNED_NETWORK_AND_EVAL_TOKENS:
        assert token not in text, f"forbidden token '{token}' found in dashboard.js"

    assert "displaylogo: false" in text
    modebar_match = re.search(r"modeBarButtonsToRemove:\s*\[([^\]]*)\]", text)
    assert modebar_match is not None
    assert '"sendDataToCloud"' in modebar_match.group(1)


# --- acceptance criterion 3: the KEYS contract ---------------------------------------------------


def test_dashboard_js_keys_extraction_finds_a_non_empty_set() -> None:
    """A renamed or deleted KEYS object must fail loudly, not vacuously pass on an empty set."""
    text = _read_js_asset()

    keys = _extract_keys(text)

    assert keys != {}


def test_dashboard_js_keys_values_are_all_real_payload_keys(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    text = _read_js_asset()
    keys = _extract_keys(text)
    payload = _build_payload_from_scenario_tree(scenario_tree, tmp_path)
    payload_keys = _collect_keys(payload)

    for name, value in keys.items():
        assert value in payload_keys, f"KEYS.{name} = {value!r} is not a key of the payload"


def test_dashboard_js_keys_values_each_occur_exactly_once_as_quoted_literals() -> None:
    """Proves no payload key is read outside KEYS: its literal is written exactly once."""
    text = _read_js_asset()
    keys = _extract_keys(text)

    for name, value in keys.items():
        quoted = f'"{value}"'
        occurrences = text.count(quoted)
        assert occurrences == 1, (
            f"KEYS.{name}'s value {quoted} occurs {occurrences} times in dashboard.js; "
            "a payload key must be read only through KEYS"
        )


def test_dashboard_js_never_accesses_payload_outside_keys() -> None:
    text = _read_js_asset()

    assert re.search(r"payload\.[A-Za-z_]", text) is None
    assert re.search(r'payload\[\s*"', text) is None


def test_dashboard_js_payload_access_resists_the_four_known_evasions() -> None:
    """Close the four ways a payload read can dodge the two regexes above.

    The KEYS contract is the only automated gate on payload access, because decision E3-1 means no
    test executes this file. The original two patterns catch the naive violation but not a reworded
    one, and tickets 023, 024 and 026 all extend this same asset. Each pattern below was found by
    the ticket-022 boundary verification as a concrete evasion, not imagined:

    1. optional chaining, `payload?.charts`, breaks the literal `payload.` the first regex needs;
    2. destructuring, `const { charts } = payload`, uses neither dot nor bracket syntax;
    3. a single-quoted or template-literal key, `payload['charts']`, dodges the double quote;
    4. a key built by concatenation into a variable, `payload[k]`, puts an identifier after the
       bracket rather than a quote.

    Requiring every `payload[` to be followed by `KEYS.` closes 3 and 4 together, since neither a
    quote of any kind nor an arbitrary identifier can satisfy it.
    """
    text = _read_js_asset()

    assert re.search(r"payload\s*\?\s*\.", text) is None, "optional chaining on payload"
    assert re.search(r"[}\]]\s*=\s*payload\b", text) is None, "destructuring of payload"
    assert re.search(r"payload\[(?!\s*KEYS\.)", text) is None, (
        "every payload[...] access must go through KEYS, whatever the quoting"
    )


# --- acceptance criterion 4: Plotly.react-only render path and step interpolation --------------


def test_dashboard_js_renders_with_react_only_and_step_interpolation() -> None:
    text = _read_js_asset()

    assert text.count("Plotly.react(") == 1
    assert "Plotly.newPlot(" not in text
    assert 'shape: "hv"' in text
    assert "connectgaps: false" in text


def test_build_html_scenario_tree_embeds_dashboard_js_asset_verbatim_exactly_once(
    scenario_tree: dict[str, Path], tmp_path: Path
) -> None:
    settings = _build_settings(tmp_path)
    data = _build_data(scenario_tree, settings)
    asset_text = _read_js_asset()

    document = build_html(data, settings=settings)

    assert document.count(asset_text) == 1
    assert _dashboard_js_slice(document) == asset_text


# --- non-empty, non-stub asset -------------------------------------------------------------------


def test_dashboard_js_asset_is_non_empty_and_longer_than_the_replaced_stub() -> None:
    text = _read_js_asset()

    assert len(text) > 0
    assert len(text) > len(_ORIGINAL_STUB_TEXT)


# --- acceptance criterion 5: the manual checklist -------------------------------------------------


def test_checklist_file_has_a_numbered_step_list() -> None:
    text = _read_checklist()

    assert re.search(r"^\d+\.\s", text, re.MULTILINE) is not None


def test_checklist_covers_offline_load_and_console_error_check() -> None:
    text = _read_checklist()

    assert "console" in text.lower()
    assert "file://" in text


def test_checklist_covers_ons_identity_with_exact_footer_text() -> None:
    text = _read_checklist()

    assert "Gerência de Ferramentas Energéticas - FEN" in text


def test_checklist_covers_level_navigation_over_six_groups() -> None:
    text = _read_checklist()

    for group_label in (
        "SIN",
        "Submercado",
        "Intercâmbio",
        "Usinas hidrelétricas",
        "Usinas termelétricas",
        "Execução",
    ):
        assert group_label in text


def test_checklist_covers_deck_and_encadeado_modes_with_disabled_selector_and_stage_width() -> None:
    text = _read_checklist()

    assert "Por deck" in text
    assert "Encadeado" in text
    assert "disabled" in text.lower()
    assert "six times wider" in text


def test_checklist_covers_absoluto_diferenca_toggle_with_the_reproducible_case() -> None:
    text = _read_checklist()

    assert "Absoluto" in text
    assert "Diferença" in text
    assert "04/03/2024 12:00" in text
    assert "GHID_SIN" in text
    assert "caso_oficial" in text
    assert "caso_gurobi" in text
    assert "--casos exemplo/caso_oficial exemplo/caso_gurobi" in text


def test_checklist_covers_submarket_and_interchange_pair_selectors() -> None:
    text = _read_checklist()

    assert "Submercado" in text
    assert "Par de submercados" in text


def test_checklist_covers_avisos_section_on_a_scenario_missing_a_deck() -> None:
    text = _read_checklist()

    assert "Avisos" in text


def test_checklist_ends_with_ticket_028_placeholder_for_plant_filters() -> None:
    text = _read_checklist()

    assert "ticket-028" in text
    placeholder_index = text.rindex("ticket-028")
    # ticket-028's owner section must be the last substantial thing in the file, not buried
    # ahead of other Epic 3 content that a later edit might append after it by mistake.
    assert placeholder_index > len(text) * 0.8
