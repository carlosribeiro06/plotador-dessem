"""Integration test against the real DESSEM example scenario tree.

The only module in the plan authorised to make the suite read `exemplo/` (ticket-034), and the
authorisation is narrow: every test below runs the pipeline over that tree *through the library*
(`dessem_dashboard.pipeline.run`) and never opens, lists, copies or transcribes anything under it
itself -- `exemplo_tree.qualifying_scenarios` does the one non-recursive listing this module needs,
mirroring `dessem_dashboard.data.discovery`'s own rule. No value read *from* the tree is ever
hard-coded here: every pinned figure in `test_exemplo_documented_tree_pinned_volumes` is
transcribed from the master plan's Appendix A, `planning-context.md` and the committed
`reference/parquet-schemas.txt` dump, none of it measured by this module.

Every test is skip-guarded: on a machine without the tree -- every CI runner, since `exemplo/` is
gitignored -- the whole module reports SKIPPED in milliseconds and the rest of the suite is
unaffected. `DESSEM_DASHBOARD_EXEMPLO` overrides the resolved root; this module is the only reader
of it (epic decision E5-6).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dashboard_document import chart_section_slices
from dessem_dashboard import pipeline
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.data.schemas import FALLBACK_UNITS
from exemplo_tree import ENV_VAR, documented_pair, exemplo_root, qualifying_scenarios

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REPO_SETTINGS_PATH = _REPO_ROOT / "settings.json"
_REPO_LOGO = _REPO_ROOT / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
_DEFAULT_ROOT = _REPO_ROOT / "exemplo"

# Measured via enabled_specs() against the repository's own settings.json (charts.disabled ==
# []): 28 of the 47 declared chart specs are enabled by default (21 series plus the seven
# dedicated Custo/Tempo bar charts of melhorias-dashboard design D7), matching
# tests/test_pipeline.py's, tests/test_builder.py's and tests/test_output_size.py's own count.
_ENABLED_CHART_COUNT = 28

_FOOTER_TEXT = "Gerência de Ferramentas Energéticas - FEN"
_LOGO_DATA_URI_PREFIX = "data:image/png;base64,"

_SCRIPT_PLOTLY_TAG = '<script id="plotly-js">'
_PAYLOAD_OPEN_TAG = '<script id="dashboard-payload" type="application/json">'
_SCRIPT_JS_TAG = '<script id="dashboard-js">'
_SCRIPT_CLOSE_TAG = "</script>"

_PAYLOAD_TOP_LEVEL_KEYS = frozenset(
    {
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
)
_CHART_ENTRY_KEYS = frozenset(
    {"group", "kind", "selector", "title", "subtitle", "unit", "entities", "series", "scalars"}
)

# The eight warning shapes dessem_dashboard.data.timeline and dessem_dashboard.data.consolidate
# can emit (Suggested Approach step 6), each matched on a distinctive substring;
# "não encontrado no cenário" is listed twice because two different call sites emit messages
# that share that exact substring.
_WARNING_SHAPES: tuple[str, ...] = (
    "Encadeamento apresenta lacuna entre os decks de",  # timeline.validate_chaining (gap)
    "Encadeamento apresenta sobreposição entre os decks de",  # timeline.validate_chaining (overlap)
    "não possui deck para a data",  # timeline.align_deck_dates
    "tem timeline divergente do eixo do deck de",  # consolidate._check_timeline_coverage
    "não encontrado no cenário",  # consolidate._load_series (missing series file)
    "não encontrado no cenário",  # consolidate._load_scalars (missing scalar file)
    "código(s) de submercado do gráfico",  # consolidate's submarket-coverage branch
    "ausente(s) no cenário",  # consolidate's absent-entity branch
)


# --- settings builder, following tests/test_output_size.py's _REPO_LOGO / _settings_dict pattern -


def _settings_dict() -> dict[str, Any]:
    """Build a settings.json-shaped dict identical to the repository's own file, except that
    `paths.logo_file` points at the repository logo's absolute path (the
    tests/test_output_size.py::_REPO_LOGO pattern).

    Reads the repository's committed settings.json from disk rather than hand-transcribing its
    values, so this module's copy of `time.stage_groups` can never silently diverge from the
    shipped three-group default the way epic-04's spec defect 20 did with a hand-copied, reduced
    single-group dict that still claimed to "match the repository's own values". The documented-
    tree assertions below (`test_exemplo_documented_tree_pinned_volumes`) need exactly the shipped
    MILP/PL/Leitura grouping, not the single-group reduction other test modules deliberately use.
    """
    raw: dict[str, Any] = json.loads(_REPO_SETTINGS_PATH.read_text(encoding="utf-8"))
    raw["paths"] = {**raw["paths"], "logo_file": str(_REPO_LOGO)}
    return raw


def _build_settings(tmp_path: Path) -> Settings:
    """Write settings.json under tmp_path and load it, exercising the real config path."""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(_settings_dict()), encoding="utf-8")
    return load_settings(target)


def _extract_payload(document: str) -> dict[str, Any]:
    """Parse the embedded JSON payload out of a built document.

    Reverses payload_json's `<` escape before parsing (Suggested Approach step 4): `payload_json`
    writes `allow_nan=False`, so a successful parse is itself the proof that no `NaN` or infinity
    reached the payload from the real tree's data.
    """
    start = document.index(_PAYLOAD_OPEN_TAG) + len(_PAYLOAD_OPEN_TAG)
    end = document.index(_SCRIPT_CLOSE_TAG, start)
    text = document[start:end].replace("\\u003C", "<")
    return json.loads(text)


def _select_two_scenarios(root: Path) -> tuple[Path, Path]:
    """Return two scenario paths to compare under root.

    The documented pair when both qualify, else the first two qualifying scenarios sorted by
    name (Inputs section). Callers must have already established that at least two scenarios
    qualify under root.
    """
    pair = documented_pair(root)
    if pair is not None:
        return pair
    scenarios = qualifying_scenarios(root)
    return scenarios[0], scenarios[1]


def _skip_reason(root: Path, minimum: int) -> str:
    """Build the English skip reason naming both ENV_VAR and the resolved default path."""
    return (
        f"Fewer than {minimum} qualifying scenario(s) found under '{root}'. Set the "
        f"{ENV_VAR} environment variable to point at a valid scenario tree, or place at least "
        f"{minimum} scenario(s) under the default path '{_DEFAULT_ROOT}'."
    )


def _require_scenarios(minimum: int) -> tuple[Path, tuple[Path, ...]]:
    """Return `(exemplo_root(), its qualifying scenarios)`, or call `pytest.skip`.

    Skips, naming ENV_VAR and the resolved default path, when fewer than minimum scenarios
    qualify. A plain function, not a fixture, so
    test_exemplo_skip_reason_names_env_var_and_default_path can call it directly and inspect the
    raised `pytest.skip.Exception`. Evaluated at call time (Suggested Approach step 2), never at
    import or collection time, so a filesystem error under the resolved root cannot break
    collection.
    """
    root = exemplo_root()
    scenarios = qualifying_scenarios(root)
    if len(scenarios) < minimum:
        pytest.skip(_skip_reason(root, minimum))
    return root, scenarios


@pytest.fixture
def exemplo_two_scenario_paths() -> tuple[Path, Path]:
    """Resolve exemplo_root() and return two scenario paths to compare.

    Skips, naming ENV_VAR and the resolved default path, when fewer than two scenarios qualify
    under the resolved root.
    """
    root, _ = _require_scenarios(2)
    return _select_two_scenarios(root)


@pytest.fixture
def exemplo_one_scenario_path() -> Path:
    """Resolve exemplo_root() and return one qualifying scenario path.

    Skips, naming ENV_VAR and the resolved default path, when no scenario qualifies under the
    resolved root.
    """
    _, scenarios = _require_scenarios(1)
    return scenarios[0]


def _matches_known_warning_shape(message: str) -> bool:
    """Return whether message contains at least one of the eight documented warning substrings."""
    return any(shape in message for shape in _WARNING_SHAPES)


# --- test_exemplo_two_scenarios_universal_invariants: acceptance criteria 2, 3 and 4 ------------


def test_exemplo_two_scenarios_universal_invariants(
    exemplo_two_scenario_paths: tuple[Path, Path], tmp_path: Path
) -> None:
    """Invariants that hold for any real tree with at least two qualifying scenarios.

    Asserts nothing that depends on which study the data came from: every value below is a
    structural property of the pipeline's output shape (payload contract, length invariant,
    warning classification), never a study value read from `exemplo/`.
    """
    scenario_a, scenario_b = exemplo_two_scenario_paths
    settings = _build_settings(tmp_path)
    output_file = tmp_path / "out" / "dashboard.html"
    reference = scenario_a.name

    result = pipeline.run(
        scenario_dirs=[scenario_a, scenario_b],
        output_file=output_file,
        reference=reference,
        settings=settings,
    )

    # Acceptance criterion 2: the six data_volumes keys, in order, and their invariant values.
    assert list(result.data_volumes.keys()) == [
        "cenarios",
        "decks",
        "graficos",
        "valores",
        "bytes_html",
        "bytes_plotly",
    ]
    assert all(isinstance(value, int) for value in result.data_volumes.values())
    assert result.data_volumes["cenarios"] == 2
    assert result.data_volumes["graficos"] == _ENABLED_CHART_COUNT
    assert result.data_volumes["valores"] > 0
    assert result.data_volumes["bytes_html"] == output_file.stat().st_size
    assert result.data_volumes["bytes_html"] > result.data_volumes["bytes_plotly"]

    document = output_file.read_text(encoding="utf-8")
    assert _FOOTER_TEXT in document
    assert _LOGO_DATA_URI_PREFIX in document
    assert len(chart_section_slices(document)) == _ENABLED_CHART_COUNT

    plotly_index = document.index(_SCRIPT_PLOTLY_TAG)
    payload_index = document.index(_PAYLOAD_OPEN_TAG)
    js_index = document.index(_SCRIPT_JS_TAG)
    assert plotly_index < payload_index < js_index

    payload = _extract_payload(document)
    assert payload["schema_version"] == 1
    assert set(payload.keys()) == _PAYLOAD_TOP_LEVEL_KEYS

    charts = payload["charts"]
    assert len(charts) == _ENABLED_CHART_COUNT
    for chart_entry in charts.values():
        assert set(chart_entry.keys()) == _CHART_ENTRY_KEYS

    # Acceptance criterion 3: the length invariant, the strongest assertion real scale exercises.
    axes = payload["axes"]
    visited_triples = 0
    visited_uhe_group = False
    for chart_entry in charts.values():
        if chart_entry["kind"] != "SERIES":
            continue
        for by_scenario in chart_entry["series"].values():
            for by_axis in by_scenario.values():
                for axis_key, values in by_axis.items():
                    assert len(values) == len(axes[axis_key]["starts"])
                    visited_triples += 1
                    if chart_entry["group"] == "UHE":
                        visited_uhe_group = True
    assert visited_triples > 0
    assert visited_uhe_group

    # Acceptance criterion 4: classify the warnings instead of counting them.
    warnings = result.warnings
    assert all(_matches_known_warning_shape(message) for message in warnings)
    # Non-vacuity: an unrecognised message must make the same check fail, proving the
    # classification rejects an unknown shape instead of accepting anything.
    assert not all(
        _matches_known_warning_shape(message) for message in [*warnings, "mensagem desconhecida"]
    )


# --- test_exemplo_documented_tree_pinned_volumes: Suggested Approach steps 7 and 8 ---------------


def test_exemplo_documented_tree_pinned_volumes(tmp_path: Path) -> None:
    """Structural counts pinned from master plan Appendix A.2, A.4 and A.6, `planning-context.md`
    and the committed `reference/parquet-schemas.txt` dump -- every one measured there, none
    measured by this test. Guarded by its own predicate (Suggested Approach step 7): skips
    whenever the resolved tree is not exactly the documented pair with the documented dates, so a
    developer pointing DESSEM_DASHBOARD_EXEMPLO elsewhere, or a future rebuild of the reference
    deck, degrades to a skip rather than a false failure. If this test runs and a pinned figure
    fails, the failure is the finding (requirement 10): no source module may be edited to make it
    pass.
    """
    root = exemplo_root()
    pair = documented_pair(root)
    if pair is None:
        # Acceptance criterion 1 requires EVERY skip reason of this module to name both ENV_VAR
        # and the resolved default path, not only the ones _skip_reason builds. This predicate is
        # structurally different from _require_scenarios' -- it needs that exact pair of scenario
        # names rather than a count -- so it composes its own first sentence and then borrows the
        # same closing guidance, rather than duplicating the wording.
        pytest.skip(
            "The documented pair ('caso_oficial', 'caso_gurobi') does not both qualify under "
            f"the resolved root '{root}': this test only pins Appendix A's structural counts "
            f"against that exact tree. Set the {ENV_VAR} environment variable to point at a tree "
            f"holding both, or place them under the default path '{_DEFAULT_ROOT}'."
        )
    official, gurobi = pair

    settings = _build_settings(tmp_path)
    output_file = tmp_path / "out" / "dashboard.html"

    result = pipeline.run(
        scenario_dirs=[official, gurobi],
        output_file=output_file,
        reference=official.name,
        settings=settings,
    )
    assert result.data_volumes["cenarios"] == 2

    document = output_file.read_text(encoding="utf-8")
    payload = _extract_payload(document)

    if payload["deck_dates"] != ["03/03/2024", "04/03/2024"]:
        pytest.skip(
            "Resolved tree's deck_dates do not match the documented pair's expected "
            f"['03/03/2024', '04/03/2024']: got {payload['deck_dates']!r}"
        )

    axes = payload["axes"]
    charts = payload["charts"]

    assert len(axes["03/03/2024"]["starts"]) == 68
    assert len(axes["04/03/2024"]["starts"]) == 64
    assert len(axes["encadeado"]["starts"]) == 96

    assert len(charts["GHID_UHE"]["entities"]) == 165
    assert len(charts["VARMF_UHE"]["entities"]) == 118
    assert len(charts["GTER_UTE"]["entities"]) == 89
    assert len(charts["CMO_SBM"]["entities"]) == 4
    assert len(charts["INT_SBP"]["entities"]) == 12

    # melhorias-dashboard design D7: the seven dedicated cost/time charts each emit exactly their
    # own aggregated series, all carrying their source_file's unit (CUSTOS / TEMPO).
    assert set(charts["CUSTO_PRESENTE"]["scalars"]) == {"PRESENTE"}
    assert set(charts["CUSTO_FUTURO"]["scalars"]) == {"FUTURO"}
    assert set(charts["CUSTO_TOTAL"]["scalars"]) == {"TOTAL"}
    assert set(charts["TEMPO_MILP"]["scalars"]) == {"MILP"}
    assert set(charts["TEMPO_PL"]["scalars"]) == {"PL"}
    assert set(charts["TEMPO_LEITURA"]["scalars"]) == {"Leitura"}
    assert set(charts["TEMPO_TOTAL"]["scalars"]) == {"TOTAL"}
    for cost_key in ("CUSTO_PRESENTE", "CUSTO_FUTURO", "CUSTO_TOTAL"):
        assert charts[cost_key]["unit"] == FALLBACK_UNITS["CUSTOS"]
    for time_key in ("TEMPO_MILP", "TEMPO_PL", "TEMPO_LEITURA", "TEMPO_TOTAL"):
        assert charts[time_key]["unit"] == FALLBACK_UNITS["TEMPO"]

    # Suggested Approach step 8: TOTAL == MILP + PL + Leitura, a real check on
    # scalars.aggregate_times at real scale that needs no external figure. The four groups now live
    # in four dedicated charts, each holding its one series.
    milp = charts["TEMPO_MILP"]["scalars"]["MILP"]
    pl = charts["TEMPO_PL"]["scalars"]["PL"]
    leitura = charts["TEMPO_LEITURA"]["scalars"]["Leitura"]
    total = charts["TEMPO_TOTAL"]["scalars"]["TOTAL"]
    tolerance = 10**-settings.output.decimals
    checked_pairs = 0
    for scenario in payload["scenarios"]:
        for deck_key in payload["deck_dates"]:
            group_values = [
                by_series.get(scenario, {}).get(deck_key) for by_series in (milp, pl, leitura)
            ]
            total_value = total.get(scenario, {}).get(deck_key)
            if total_value is None or any(value is None for value in group_values):
                continue
            assert total_value == pytest.approx(sum(group_values), abs=tolerance)
            checked_pairs += 1
    assert checked_pairs > 0


# --- test_exemplo_single_scenario_reference_takes_brand_green: requirement 6 --------------------


def test_exemplo_single_scenario_reference_takes_brand_green(
    exemplo_one_scenario_path: Path, tmp_path: Path
) -> None:
    """A single `--casos` argument is spec-legal; the difference view then has nothing to
    compare against, and this is the cheapest coverage of that case (requirement 6): the
    reference scenario always takes brand green, whatever its position -- here trivially the
    only position -- which `theme.scenario_colors` never had a single-scenario call to exercise
    before this test.
    """
    scenario = exemplo_one_scenario_path
    label = scenario.name
    settings = _build_settings(tmp_path)
    output_file = tmp_path / "out" / "dashboard.html"

    result = pipeline.run(
        scenario_dirs=[scenario],
        output_file=output_file,
        reference=label,
        settings=settings,
    )
    assert result.data_volumes["cenarios"] == 1

    document = output_file.read_text(encoding="utf-8")
    payload = _extract_payload(document)

    assert payload["reference"] == label
    assert payload["theme"]["scenario_colors"] == {label: "#486018"}


# --- test_exemplo_skip_reason_names_env_var_and_default_path: acceptance criterion 1 ------------


def test_exemplo_skip_reason_names_env_var_and_default_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercises the skip predicate on every machine, including one that already has the real
    tree, by pointing DESSEM_DASHBOARD_EXEMPLO at an empty tmp_path directory: this reaches the
    same predicate the two-scenario fixture uses without touching the real tree.
    """
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    monkeypatch.setenv(ENV_VAR, str(empty_root))

    with pytest.raises(pytest.skip.Exception) as exc_info:
        _require_scenarios(2)

    message = str(exc_info.value)
    assert ENV_VAR in message
    assert str(_DEFAULT_ROOT) in message
