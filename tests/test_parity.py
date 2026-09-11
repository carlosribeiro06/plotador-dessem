"""Legacy parity check: independent recomputation, never legacy execution.

Establishes parity with `Plotadores/*.py` and `main_*.py` without ever importing, running or
reading them: decision E5-1 measured that all twelve legacy modules fail at import in this
environment (a hard-coded Windows path) and expect the date-first tree layout decision 15
replaced, so "parity" here means recomputing the legacy pandas expressions independently, with
every legacy constant transcribed once into the module constants below, each citing its source
line. `ticket-038` deletes `Leitura/` and `Plotadores/` after this ticket, so this module must
share no import with either.

Three groups:

* Group A (synthetic, always runs) -- recomputes every Appendix A.7 quantity from a fixture tree
  built with `submarket_codes=(1, 2, 3, 4, 11, 99)` and compares it to the payload.
* Group B (real data, skip-guarded) -- repeats every Group A comparison over the real scenario
  tree `tests/exemplo_tree.py` resolves, plus two absolute pins transcribed from the committed
  `plans/dashboard-dessem/reference/parquet-schemas.txt` dump (epic decision E5-4). Expressed only
  as assertions: no value from `exemplo/` is ever printed, logged or written to a file.
* Group C (synthetic, always runs) -- asserts the deliberate divergences from the legacy tool:
  the repeated-`etapa` sum, the date-typed axis, and the single-file output.

See `plans/dashboard-dessem/epic-05-parity-report.md` for the transcribed legacy inventory and the
value- and presentation-parity verdicts this module's tests back.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pandas as pd
import pytest

from dashboard_document import chart_section_slices
from dessem_dashboard.config import Settings, load_settings
from dessem_dashboard.dashboard import theme
from dessem_dashboard.dashboard.builder import write_dashboard
from dessem_dashboard.dashboard.payload import build_payload
from dessem_dashboard.data.consolidate import build_dashboard_data
from dessem_dashboard.data.discovery import discover_scenarios
from dessem_dashboard.data.registries import load_registries, visible_submarket_codes
from dessem_dashboard.data.schemas import SCALAR_COLUMNS
from dessem_dashboard.models.store import DashboardData
from exemplo_tree import ENV_VAR, documented_pair, exemplo_root, qualifying_scenarios
from fixtures_sintese import make_sintese_dir

# --- Legacy constants, transcribed once from Plotadores/*.py so this module never re-reads it --

# Plotadores/Ghid_SIN.py:18, Gter_SIN.py:18, Ghid_sbm.py:19, Gter_sbm.py:19, CMO_sbm.py:19: every
# line chart filters `df.loc[df["estagio"] <= 48]` before concatenating.
_LEGACY_STAGE_FILTER_MAX = 48

# Plotadores/Ghid_sbm.py:13, Gter_sbm.py:13, CMO_sbm.py:13: `submercados = [1, 2, 3, 4]`.
_LEGACY_SUBMERCADOS: tuple[int, ...] = (1, 2, 3, 4)

# Plotadores/Custos.py:20-21: `.values[0]` of CUSTOS.parquet's `valor_esperado`, one row per
# parcela, before the two figures are ever added.
_LEGACY_CUSTOS_PARCELA_PRESENTE = "PRESENTE"
_LEGACY_CUSTOS_PARCELA_FUTURO = "FUTURO"

# Plotadores/Tempo.py:22 (Leitura, `.values[0]`), :23 (MILP, `.values[0]`) and :24 (the PL group,
# `.sum()` over these three etapa names), all divided by 60 before being plotted.
_LEGACY_TEMPO_ETAPA_LEITURA = "Leitura de Dados e Impressão"
_LEGACY_TEMPO_ETAPA_MILP = "MILP"
_LEGACY_TEMPO_PL_ETAPAS: tuple[str, ...] = ("PL", "PL.Int.Fix", "PL.CalcCMO")

# dashboard.js:42 and :184 (verbatim, measured against the shipped asset): the only place the new
# dashboard builds a category-axis label for a SCALAR_BY_DECK chart. dashboard.js is embedded
# verbatim in the built document (epic-04 learnings section 6), so these two literals appearing
# in the document is a structural proof of the "<deck key> - <series name>" label format.
_CATEGORY_SEPARATOR_LITERAL = 'const CATEGORY_SEPARATOR = " - ";'
_CATEGORY_LABEL_EXPRESSION = "cell.deckKey + CATEGORY_SEPARATOR + cell.name"

# Every legacy fig.write_html(..., include_plotlyjs="cdn") call loads Plotly from this URL; the
# new dashboard inlines the bundle instead (Requirement 4's file-count divergence).
_LEGACY_CDN_REFERENCE = "https://cdn.plot.ly"

# --- Reference-deck figures, transcribed from plans/dashboard-dessem/reference/parquet-schemas.txt
# (epic decision E5-4) for exemplo/2024-03-03/caso_oficial/sintese ---------------------------------
#
# CORRECTION to this ticket's own precision-trap note: measured directly against the committed
# dump (lines 86-94), the roles are the OPPOSITE of what the ticket describes. CUSTOS.parquet's
# `valor_esperado: 4 unique -> [...]` line (line 89) carries the FULL-PRECISION strings
# '228420390.34615' and '58667.5674'; it is the printed SAMPLE-ROWS table three lines below (91-94)
# that shows the truncated scientific notation '5.866757e+04' / '2.284204e+08'. Verified by
# arithmetic either way: 58667.5674 + 228420390.34615 = 228479057.91355 (rounds to 228479057.91,
# matching every other plan document); 58667.57 + 228420400 = 228479067.57 (the wrong, truncated
# sum the ticket itself names). The VALUES below are correct and triple-corroborated by
# planning-context.md, epic-04-learnings.md and this ticket's own requirement 3; only the
# structural attribution ("unique list" vs "sample rows") in the ticket's added note is wrong,
# flagged in the parity report rather than silently reproduced here.
_REFERENCE_DECK_KEY = "03/03/2024"
_REFERENCE_CUSTOS_PRESENTE = 58667.5674
_REFERENCE_CUSTOS_FUTURO = 228420390.34615

# SECOND CORRECTION, measured by running the real pipeline: the ticket's requirement 3 claims
# "the payload's TOTAL at output.decimals = 2 is 228479057.91", computed as
# round(PRESENTE_raw + FUTURO_raw, 2) = round(228479057.91355, 2) = 228479057.91. That is not
# what dashboard.scalars.aggregate_costs computes. dashboard.payload._build_scalars rounds
# PRESENTE and FUTURO to output.decimals INDIVIDUALLY first (58667.57 and 228420390.35 -- the
# latter rounds UP because its third decimal is 6), and only then does aggregate_costs sum and
# round again: round(58667.57 + 228420390.35, 2) = 228479057.92. The one-cent difference is the
# double rounding, not a bug: it is the same rule dashboard.scalars._strict_total applies
# ("_round_nonzero(sum(values), decimals)" over already-rounded per-parcel values). 228479057.92
# is what a run of this pipeline over the reference deck actually produces; it is used below.
_REFERENCE_CUSTOS_TOTAL_AT_TWO_DECIMALS = 228479057.92

_REFERENCE_TEMPO_SECONDS: tuple[float, ...] = (
    48.0,
    438.0,
    469.0,
    564.0,
    714.0,
    786.0,
    1056.0,
    1086.0,
    6726.0,
)
_REFERENCE_TEMPO_TOTAL_AT_TWO_DECIMALS = 198.12

# --- Chart-family groupings ------------------------------------------------------------------

_SIN_CHART_KEYS: tuple[str, ...] = ("GHID_SIN", "GTER_SIN")
_SBM_FAMILY_CHART_KEYS: tuple[str, ...] = ("GHID_SBM", "GTER_SBM", "CMO_SBM")

# models.store._DATE_FORMAT / data.consolidate._DATE_FORMAT (both private): every deck's
# TimeAxis.key and every scalar's deck_key use this format. Duplicated here, not imported, so
# this recomputation shares no code path with the pipeline it checks.
_DECK_KEY_DATE_FORMAT = "%d/%m/%Y"
_SINTESE_DIRNAME = "sintese"

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REPO_SETTINGS_PATH = _REPO_ROOT / "settings.json"
_REPO_LOGO = _REPO_ROOT / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
_DEFAULT_ROOT = _REPO_ROOT / "exemplo"

_ENABLED_CHART_COUNT = 23  # enabled_specs(), measured; matches every other test module's own pin.

_SCRIPT_PLOTLY_OPEN_TAG = '<script id="plotly-js">'
_SCRIPT_CLOSE_TAG = "</script>"


@dataclass(frozen=True)
class _ParityContext:
    """One consolidated payload plus, per scenario, its deck sintese directories in date order.

    The one shape Group A and Group B share, so both are driven by the same comparison helpers
    below (Suggested Approach step 6) and cannot drift apart.
    """

    payload: dict[str, object]
    settings: Settings
    dirs_by_scenario: Mapping[str, tuple[Path, ...]]

    @property
    def scenarios(self) -> tuple[str, ...]:
        return tuple(self.dirs_by_scenario)


# --- settings / data / payload builders, following tests/test_integration_exemplo.py's pattern -


def _settings_dict(
    *, unit_divisor: float | None = None, total_parcels: Sequence[str] | None = None
) -> dict[str, Any]:
    """Read the repository's own settings.json and override only paths.logo_file (to the
    repository logo's absolute path) plus, optionally, one knob under test.

    Reading the shipped file rather than hand-transcribing it is what keeps this module immune to
    epic-04 spec defect 20's shape: a hand-copied, reduced settings dict that still claimed to
    match the repository's own values.
    """
    raw: dict[str, Any] = json.loads(_REPO_SETTINGS_PATH.read_text(encoding="utf-8"))
    raw["paths"] = {**raw["paths"], "logo_file": str(_REPO_LOGO)}
    if unit_divisor is not None:
        raw["time"] = {**raw["time"], "unit_divisor": unit_divisor}
    if total_parcels is not None:
        raw["costs"] = {**raw["costs"], "total_parcels": list(total_parcels)}
    return raw


def _build_settings(
    tmp_path: Path,
    *,
    unit_divisor: float | None = None,
    total_parcels: Sequence[str] | None = None,
) -> Settings:
    """Write settings.json under tmp_path and load it, exercising the real config path."""
    target = tmp_path / "settings.json"
    target.write_text(
        json.dumps(_settings_dict(unit_divisor=unit_divisor, total_parcels=total_parcels)),
        encoding="utf-8",
    )
    return load_settings(target)


def _build_parity_data(
    scenario_dirs: Sequence[Path], *, settings: Settings, reference: str
) -> DashboardData:
    """Discover scenario_dirs and consolidate them into one DashboardData."""
    scenarios = discover_scenarios(
        list(scenario_dirs), sintese_dirname=settings.discovery.sintese_dirname
    )
    return build_dashboard_data(scenarios, settings=settings, reference=reference)


# --- independent recomputation helpers: pandas only, no dessem_dashboard.data.timeline ----------


def _deck_date(sintese_dir: Path) -> date:
    """Return sintese_dir's deck date, read directly from EST.parquet.

    Deliberately independent of dessem_dashboard.data.timeline.load_deck_timeline: this
    recomputation must share no code path with the pipeline it checks.
    """
    frame = pd.read_parquet(sintese_dir / "EST.parquet", engine="pyarrow")
    return pd.Timestamp(frame["data_inicio"].min()).date()


def _ordered_sintese_dirs(scenario_dir: Path, *, sintese_dirname: str) -> list[Path]:
    """Return scenario_dir's deck sintese directories, sorted by deck date, never by folder name.

    Requirement 2 and Suggested Approach step 3's "deck-date order", the correction over
    Plotadores/Ghid_SIN.py:25-28's filesystem-iteration order.
    """
    candidates = [
        entry / sintese_dirname
        for entry in sorted(scenario_dir.iterdir())
        if entry.is_dir() and (entry / sintese_dirname).is_dir()
    ]
    return sorted(candidates, key=_deck_date)


def _round_like_payload(value: float, decimals: int) -> float:
    """Round value exactly as dashboard.payload._round_value / dashboard.scalars._round_nonzero
    do, so a directly-read figure can be compared by exact equality instead of by tolerance."""
    rounded = round(value, decimals)
    return 0.0 if rounded == 0.0 else rounded


def _legacy_chained_values(
    sintese_dirs_in_date_order: Sequence[Path],
    chart_key: str,
    *,
    submarket_code: int | None,
    stage_filter_max: int,
    decimals: int,
) -> list[float]:
    """Recompute chart_key's chained array with the legacy stage filter, concatenated in
    deck-date order (never Plotadores/Ghid_SIN.py:25-28's filesystem-iteration order)."""
    values: list[float] = []
    for sintese_dir in sintese_dirs_in_date_order:
        frame = pd.read_parquet(sintese_dir / f"{chart_key}.parquet", engine="pyarrow")
        filtered = frame.loc[frame["estagio"] <= stage_filter_max]
        if submarket_code is not None:
            filtered = filtered.loc[filtered["codigo_submercado"] == submarket_code]
        values.extend(float(value) for value in filtered["valor"].to_numpy())
    return [_round_like_payload(value, decimals) for value in values]


def _check_chained_series_matches_legacy(
    context: _ParityContext,
    chart_key: str,
    entity_id: str,
    *,
    submarket_code: int | None,
    stage_filter_max: int = _LEGACY_STAGE_FILTER_MAX,
) -> int:
    """Assert chart_key's stored chained array for entity_id matches the legacy-filter
    recomputation, for every scenario in context that stores a non-empty array for it.

    Returns the number of scenarios visited, so callers enforce non-vacuity (acceptance
    criterion 1's "every comparison visited at least one array of non-zero length").
    """
    decimals = context.settings.output.decimals
    visited = 0
    for scenario in context.scenarios:
        recomputed = _legacy_chained_values(
            context.dirs_by_scenario[scenario],
            chart_key,
            submarket_code=submarket_code,
            stage_filter_max=stage_filter_max,
            decimals=decimals,
        )
        chart = context.payload["charts"][chart_key]  # type: ignore[index]
        series_by_entity = chart["series"]  # type: ignore[index]
        by_scenario = series_by_entity.get(entity_id)
        stored = None if by_scenario is None else by_scenario.get(scenario)
        stored_values = None if stored is None else stored.get("encadeado")
        if not recomputed or stored_values is None:
            continue
        assert list(stored_values) == recomputed, (
            f"chart '{chart_key}' entity '{entity_id}' scenario '{scenario}': chained array "
            "diverges from the legacy filter-and-concatenate recomputation"
        )
        visited += 1
    return visited


def _legacy_custos_raw(sintese_dir: Path, parcela: str) -> float:
    """Plotadores/Custos.py:20 (PRESENTE) / :21 (FUTURO): `.values[0]` of valor_esperado."""
    frame = pd.read_parquet(sintese_dir / "CUSTOS.parquet", engine="pyarrow")
    return float(frame.loc[frame["parcela"] == parcela, "valor_esperado"].to_numpy()[0])


def _assert_custos_scalars_match(
    stored_presente: object,
    stored_futuro: object,
    stored_total: object,
    *,
    presente_raw: float,
    futuro_raw: float,
    decimals: int,
) -> None:
    """Requirement 2's CUSTOS bullet: PRESENTE and FUTURO exactly, TOTAL within their sum."""
    presente_expected = _round_like_payload(presente_raw, decimals)
    futuro_expected = _round_like_payload(futuro_raw, decimals)
    assert stored_presente == presente_expected
    assert stored_futuro == futuro_expected
    total_expected = _round_like_payload(presente_expected + futuro_expected, decimals)
    assert stored_total == pytest.approx(total_expected, abs=10**-decimals)


def _check_custos_scalars_match_legacy(context: _ParityContext) -> int:
    """Run _assert_custos_scalars_match over every (scenario, deck) pair context stores CUSTOS
    for. Returns the number of pairs visited."""
    scalars = context.payload["charts"]["CUSTOS"]["scalars"]  # type: ignore[index]
    decimals = context.settings.output.decimals
    visited = 0
    for scenario in context.scenarios:
        for sintese_dir in context.dirs_by_scenario[scenario]:
            deck_key = _deck_date(sintese_dir).strftime(_DECK_KEY_DATE_FORMAT)
            stored_presente = scalars["PRESENTE"].get(scenario, {}).get(deck_key)  # type: ignore[union-attr]
            stored_futuro = scalars["FUTURO"].get(scenario, {}).get(deck_key)  # type: ignore[union-attr]
            stored_total = scalars["TOTAL"].get(scenario, {}).get(deck_key)  # type: ignore[union-attr]
            if None in (stored_presente, stored_futuro, stored_total):
                continue
            _assert_custos_scalars_match(
                stored_presente,
                stored_futuro,
                stored_total,
                presente_raw=_legacy_custos_raw(sintese_dir, _LEGACY_CUSTOS_PARCELA_PRESENTE),
                futuro_raw=_legacy_custos_raw(sintese_dir, _LEGACY_CUSTOS_PARCELA_FUTURO),
                decimals=decimals,
            )
            visited += 1
    return visited


def _legacy_tempo_raw_seconds(sintese_dir: Path) -> tuple[float, float, float]:
    """Plotadores/Tempo.py:22 (Leitura `.values[0]`), :23 (MILP `.values[0]`) and :24 (the PL
    group's `.sum()`), all before division -- returns (leitura, milp, pl) in raw seconds.

    Asserts exactly one row before each `.values[0]`-mirroring read below: the reference deck
    already has an etapa repeat (TEMPO.parquet shape=(9, 3), etapa: 5 unique), and that repeat
    falls on the summed PL names only by measurement, not by any guarantee. A future deck
    logging two Leitura or MILP rows would make the shipped pipeline's groupby-sum (correct)
    diverge from this legacy first-row mirror (also correct, by design) -- a real behavioural
    divergence this recomputation exists to surface, not the parity regression it would
    otherwise look like. test_group_c_repeated_etapa_milp_is_summed_not_first_row_only owns the
    proof that the shipped pipeline sums repeated rows.
    """
    frame = pd.read_parquet(sintese_dir / "TEMPO.parquet", engine="pyarrow")
    leitura_rows = frame.loc[frame["etapa"] == _LEGACY_TEMPO_ETAPA_LEITURA, "tempo"]
    assert len(leitura_rows) == 1, (
        f"Expected exactly one '{_LEGACY_TEMPO_ETAPA_LEITURA}' row to mirror "
        "Plotadores/Tempo.py:22's `.values[0]` semantics; got "
        f"{len(leitura_rows)} rows instead. See "
        "test_group_c_repeated_etapa_milp_is_summed_not_first_row_only for the proof that the "
        "shipped pipeline sums repeated rows rather than taking the first one."
    )
    milp_rows = frame.loc[frame["etapa"] == _LEGACY_TEMPO_ETAPA_MILP, "tempo"]
    assert len(milp_rows) == 1, (
        f"Expected exactly one '{_LEGACY_TEMPO_ETAPA_MILP}' row to mirror "
        "Plotadores/Tempo.py:23's `.values[0]` semantics; got "
        f"{len(milp_rows)} rows instead. See "
        "test_group_c_repeated_etapa_milp_is_summed_not_first_row_only for the proof that the "
        "shipped pipeline sums repeated rows rather than taking the first one."
    )
    leitura = float(leitura_rows.to_numpy()[0])
    milp = float(milp_rows.to_numpy()[0])
    pl = float(frame.loc[frame["etapa"].isin(_LEGACY_TEMPO_PL_ETAPAS), "tempo"].sum())
    return leitura, milp, pl


def _assert_tempo_scalars_match(
    stored_leitura: object,
    stored_milp: object,
    stored_pl: object,
    stored_total: object,
    *,
    leitura_raw: float,
    milp_raw: float,
    pl_raw: float,
    unit_divisor: float,
    decimals: int,
) -> None:
    """Requirement 2's TEMPO bullet: the four legacy expressions divided by unit_divisor."""
    tolerance = 10**-decimals
    leitura_expected = _round_like_payload(leitura_raw / unit_divisor, decimals)
    milp_expected = _round_like_payload(milp_raw / unit_divisor, decimals)
    pl_expected = _round_like_payload(pl_raw / unit_divisor, decimals)
    total_expected = _round_like_payload(leitura_expected + milp_expected + pl_expected, decimals)
    assert stored_leitura == pytest.approx(leitura_expected, abs=tolerance)
    assert stored_milp == pytest.approx(milp_expected, abs=tolerance)
    assert stored_pl == pytest.approx(pl_expected, abs=tolerance)
    assert stored_total == pytest.approx(total_expected, abs=tolerance)


def _check_tempo_scalars_match_legacy(context: _ParityContext) -> int:
    """Run _assert_tempo_scalars_match over every (scenario, deck) pair context stores TEMPO
    for. Returns the number of pairs visited."""
    scalars = context.payload["charts"]["TEMPO"]["scalars"]  # type: ignore[index]
    decimals = context.settings.output.decimals
    unit_divisor = context.settings.time.unit_divisor
    visited = 0
    for scenario in context.scenarios:
        for sintese_dir in context.dirs_by_scenario[scenario]:
            deck_key = _deck_date(sintese_dir).strftime(_DECK_KEY_DATE_FORMAT)
            stored_leitura = scalars["Leitura"].get(scenario, {}).get(deck_key)  # type: ignore[union-attr]
            stored_milp = scalars["MILP"].get(scenario, {}).get(deck_key)  # type: ignore[union-attr]
            stored_pl = scalars["PL"].get(scenario, {}).get(deck_key)  # type: ignore[union-attr]
            stored_total = scalars["TOTAL"].get(scenario, {}).get(deck_key)  # type: ignore[union-attr]
            if None in (stored_leitura, stored_milp, stored_pl, stored_total):
                continue
            leitura_raw, milp_raw, pl_raw = _legacy_tempo_raw_seconds(sintese_dir)
            _assert_tempo_scalars_match(
                stored_leitura,
                stored_milp,
                stored_pl,
                stored_total,
                leitura_raw=leitura_raw,
                milp_raw=milp_raw,
                pl_raw=pl_raw,
                unit_divisor=unit_divisor,
                decimals=decimals,
            )
            visited += 1
    return visited


# --- Group A: synthetic parity, always runs -----------------------------------------------------

_GROUP_A_SCENARIO_DIR_NAME = "caso_parity"
_GROUP_A_SUBMARKET_CODES: tuple[int, ...] = (1, 2, 3, 4, 11, 99)
_GROUP_A_N_STAGES = 30  # > _LEGACY_STAGE_FILTER_MAX's mutated value (24), so that mutation bites.

# Deck directory names deliberately defeat alphabetical order: "deck_a" (2024-03-04, the LATER
# date) sorts before "deck_z" (2024-03-03, the EARLIER date). A recomputation that concatenated in
# directory-iteration order -- the legacy's own defect, Plotadores/Ghid_SIN.py:25-28 -- would
# silently disagree with the payload's deck-date-ordered chained array on this fixture; only a
# recomputation that reads each deck's own date from EST.parquet (per _ordered_sintese_dirs) can
# pass it.
_GROUP_A_DECK_DIR_NAMES: tuple[str, str] = ("deck_z", "deck_a")
_GROUP_A_DECK_STARTS: tuple[datetime, datetime] = (
    datetime(2024, 3, 3, tzinfo=UTC),
    datetime(2024, 3, 4, tzinfo=UTC),
)
_GROUP_A_DECK_SEEDS: tuple[int, int] = (101, 102)


def _build_group_a_context(tmp_path: Path) -> _ParityContext:
    """Build Group A's fixture tree (one scenario, two decks) and its DashboardData/payload."""
    settings = _build_settings(tmp_path)
    scenario_dir = tmp_path / "tree" / _GROUP_A_SCENARIO_DIR_NAME
    for deck_dir_name, deck_start, seed in zip(
        _GROUP_A_DECK_DIR_NAMES, _GROUP_A_DECK_STARTS, _GROUP_A_DECK_SEEDS, strict=True
    ):
        make_sintese_dir(
            scenario_dir / deck_dir_name / _SINTESE_DIRNAME,
            first_stage_start=deck_start,
            n_stages=_GROUP_A_N_STAGES,
            submarket_codes=_GROUP_A_SUBMARKET_CODES,
            seed=seed,
        )
    data = _build_parity_data([scenario_dir], settings=settings, reference=scenario_dir.name)
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    ordered_dirs = tuple(
        _ordered_sintese_dirs(scenario_dir, sintese_dirname=settings.discovery.sintese_dirname)
    )
    return _ParityContext(
        payload=payload,
        settings=settings,
        dirs_by_scenario=MappingProxyType({scenario_dir.name: ordered_dirs}),
    )


def test_group_a_sin_chained_matches_legacy_filter_and_deck_date_order(tmp_path: Path) -> None:
    """Acceptance criterion 1: GHID_SIN and GTER_SIN's chained arrays match the legacy
    `estagio <= 48` filter, concatenated in deck-date order."""
    context = _build_group_a_context(tmp_path)
    for chart_key in _SIN_CHART_KEYS:
        visited = _check_chained_series_matches_legacy(context, chart_key, "", submarket_code=None)
        assert visited == 1


def test_group_a_submarket_chained_matches_legacy_for_codes_1_to_4(tmp_path: Path) -> None:
    """Acceptance criterion 1: GHID_SBM, GTER_SBM and CMO_SBM's chained arrays match the legacy
    recomputation for every code Plotadores/*_sbm.py:13's `submercados = [1, 2, 3, 4]` names."""
    context = _build_group_a_context(tmp_path)
    for chart_key in _SBM_FAMILY_CHART_KEYS:
        visited_total = 0
        for code in _LEGACY_SUBMERCADOS:
            visited_total += _check_chained_series_matches_legacy(
                context, chart_key, str(code), submarket_code=code
            )
        assert visited_total == len(_LEGACY_SUBMERCADOS)


def test_group_a_custos_scalars_match_legacy_direct_reads_and_sum(tmp_path: Path) -> None:
    """Acceptance criterion 2, CUSTOS half."""
    context = _build_group_a_context(tmp_path)
    assert _check_custos_scalars_match_legacy(context) == len(_GROUP_A_DECK_DIR_NAMES)


def test_group_a_tempo_scalars_match_legacy_expressions_divided_by_unit_divisor(
    tmp_path: Path,
) -> None:
    """Acceptance criterion 2, TEMPO half."""
    context = _build_group_a_context(tmp_path)
    assert _check_tempo_scalars_match_legacy(context) == len(_GROUP_A_DECK_DIR_NAMES)


# --- Group B: real-data parity, skipped without the tree ----------------------------------------


def _skip_reason(root: Path, minimum: int) -> str:
    """English skip reason naming both ENV_VAR and the resolved default path."""
    return (
        f"Fewer than {minimum} qualifying scenario(s) found under '{root}'. Set the "
        f"{ENV_VAR} environment variable to point at a valid scenario tree, or place at least "
        f"{minimum} scenario(s) under the default path '{_DEFAULT_ROOT}'."
    )


def _require_two_scenarios() -> tuple[Path, Path]:
    """Resolve exemplo_root() and return two scenario paths: the documented pair when both
    qualify, else the first two qualifying scenarios sorted by name.

    Calls pytest.skip, naming ENV_VAR and the resolved default path, when fewer than two
    scenarios qualify (acceptance criterion 4's second half).
    """
    root = exemplo_root()
    scenarios = qualifying_scenarios(root)
    if len(scenarios) < 2:
        pytest.skip(_skip_reason(root, 2))
    pair = documented_pair(root)
    if pair is not None:
        return pair
    return scenarios[0], scenarios[1]


def _build_group_b_context(tmp_path: Path) -> _ParityContext:
    """Build one payload over the two documented (or first-two-qualifying) real scenarios."""
    official, gurobi = _require_two_scenarios()
    settings = _build_settings(tmp_path)
    data = _build_parity_data([official, gurobi], settings=settings, reference=official.name)
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    dirs_by_scenario = {
        scenario_dir.name: tuple(
            _ordered_sintese_dirs(scenario_dir, sintese_dirname=settings.discovery.sintese_dirname)
        )
        for scenario_dir in (official, gurobi)
    }
    return _ParityContext(
        payload=payload, settings=settings, dirs_by_scenario=MappingProxyType(dirs_by_scenario)
    )


def test_group_b_series_and_scalar_parity_matches_legacy_expressions(tmp_path: Path) -> None:
    """Acceptance criterion 4's first half: every comparison of acceptance criteria 1 and 2,
    repeated over the two documented real scenarios, with the submarket set read from
    visible_submarket_codes rather than a hard-coded list (requirement 3)."""
    context = _build_group_b_context(tmp_path)

    for chart_key in _SIN_CHART_KEYS:
        visited = _check_chained_series_matches_legacy(context, chart_key, "", submarket_code=None)
        assert visited == len(context.scenarios)

    official_name = context.scenarios[0]
    official_first_deck = context.dirs_by_scenario[official_name][0]
    registries = load_registries(official_first_deck)
    codes = visible_submarket_codes(
        registries, include_fictitious=context.settings.submarkets.include_fictitious
    )
    assert codes, "visible_submarket_codes returned no code: the loop below would visit nothing"

    for chart_key in _SBM_FAMILY_CHART_KEYS:
        visited_total = 0
        for code in codes:
            visited_total += _check_chained_series_matches_legacy(
                context, chart_key, str(code), submarket_code=code
            )
        assert visited_total == len(codes) * len(context.scenarios)

    assert _check_custos_scalars_match_legacy(context) == len(context.scenarios) * 2
    assert _check_tempo_scalars_match_legacy(context) == len(context.scenarios) * 2


def _official_scenario_skip_reason(root: Path) -> str:
    return (
        "The documented pair ('caso_oficial', 'caso_gurobi') does not both qualify under the "
        f"resolved root '{root}'. Set the {ENV_VAR} environment variable to point at a tree "
        f"holding both, or place them under the default path '{_DEFAULT_ROOT}'."
    )


def _resolve_official_scenario_dir() -> Path:
    """Return the official scenario's directory when documented_pair qualifies, else skip."""
    root = exemplo_root()
    pair = documented_pair(root)
    if pair is None:
        pytest.skip(_official_scenario_skip_reason(root))
    official, _gurobi = pair
    return official


def _reference_deck_sintese_dir(scenario_dir: Path) -> Path | None:
    """Return scenario_dir's deck sintese directory whose own deck date is the reference deck
    (03/03/2024), determined from EST.parquet rather than from any folder name, or None."""
    for sintese_dir in _ordered_sintese_dirs(scenario_dir, sintese_dirname=_SINTESE_DIRNAME):
        if _deck_date(sintese_dir).strftime(_DECK_KEY_DATE_FORMAT) == _REFERENCE_DECK_KEY:
            return sintese_dir
    return None


def test_group_b_reference_deck_custos_pins_match_committed_dump(tmp_path: Path) -> None:
    """Requirement 3's CUSTOS absolute pin: PRESENTE and FUTURO exactly, TOTAL at two decimals,
    all transcribed from reference/parquet-schemas.txt (epic decision E5-4)."""
    official = _resolve_official_scenario_dir()
    reference_dir = _reference_deck_sintese_dir(official)
    if reference_dir is None:
        pytest.skip(f"Official scenario has no deck dated {_REFERENCE_DECK_KEY}.")

    presente_raw = _legacy_custos_raw(reference_dir, _LEGACY_CUSTOS_PARCELA_PRESENTE)
    futuro_raw = _legacy_custos_raw(reference_dir, _LEGACY_CUSTOS_PARCELA_FUTURO)
    assert presente_raw == _REFERENCE_CUSTOS_PRESENTE
    assert futuro_raw == _REFERENCE_CUSTOS_FUTURO

    settings = _build_settings(tmp_path)
    data = _build_parity_data([official], settings=settings, reference=official.name)
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    total = payload["charts"]["CUSTOS"]["scalars"]["TOTAL"][official.name].get(  # type: ignore[index]
        _REFERENCE_DECK_KEY
    )
    assert total is not None
    assert total == _REFERENCE_CUSTOS_TOTAL_AT_TWO_DECIMALS


def test_group_b_reference_deck_custos_total_pin_is_not_vacuous_under_single_parcel_total(
    tmp_path: Path,
) -> None:
    """Suggested Approach step 9's second reference-deck mutation: costs.total_parcels reduced
    to a single parcel must break the absolute TOTAL pin."""
    official = _resolve_official_scenario_dir()
    if _reference_deck_sintese_dir(official) is None:
        pytest.skip(f"Official scenario has no deck dated {_REFERENCE_DECK_KEY}.")

    settings = _build_settings(tmp_path, total_parcels=["PRESENTE"])
    data = _build_parity_data([official], settings=settings, reference=official.name)
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    total = payload["charts"]["CUSTOS"]["scalars"]["TOTAL"][official.name].get(  # type: ignore[index]
        _REFERENCE_DECK_KEY
    )
    assert total is not None
    assert total != _REFERENCE_CUSTOS_TOTAL_AT_TWO_DECIMALS


def test_group_b_reference_deck_tempo_pins_match_committed_dump(tmp_path: Path) -> None:
    """Requirement 3's TEMPO absolute pin: the file's nine distinct tempo values, and the
    payload's TOTAL at two decimals, both transcribed from reference/parquet-schemas.txt.

    Only the nine-value tuple is an independent pin -- their sum is entailed by the tuple
    equality below (equal tuples have equal sums), so it is not asserted separately; no
    implementation change can fail one and pass the other.
    """
    official = _resolve_official_scenario_dir()
    reference_dir = _reference_deck_sintese_dir(official)
    if reference_dir is None:
        pytest.skip(f"Official scenario has no deck dated {_REFERENCE_DECK_KEY}.")

    raw = pd.read_parquet(reference_dir / "TEMPO.parquet", engine="pyarrow")
    tempo_values = tuple(sorted(float(value) for value in raw["tempo"].to_numpy()))
    assert tempo_values == _REFERENCE_TEMPO_SECONDS

    settings = _build_settings(tmp_path)
    data = _build_parity_data([official], settings=settings, reference=official.name)
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    total = payload["charts"]["TEMPO"]["scalars"]["TOTAL"][official.name].get(  # type: ignore[index]
        _REFERENCE_DECK_KEY
    )
    assert total is not None
    assert total == _REFERENCE_TEMPO_TOTAL_AT_TWO_DECIMALS


def test_group_b_reference_deck_tempo_total_pin_is_not_vacuous_under_unit_divisor_one(
    tmp_path: Path,
) -> None:
    """Suggested Approach step 9's first reference-deck mutation: time.unit_divisor = 1.0 must
    break the absolute TOTAL pin (minutes versus seconds)."""
    official = _resolve_official_scenario_dir()
    if _reference_deck_sintese_dir(official) is None:
        pytest.skip(f"Official scenario has no deck dated {_REFERENCE_DECK_KEY}.")

    settings = _build_settings(tmp_path, unit_divisor=1.0)
    data = _build_parity_data([official], settings=settings, reference=official.name)
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})
    total = payload["charts"]["TEMPO"]["scalars"]["TOTAL"][official.name].get(  # type: ignore[index]
        _REFERENCE_DECK_KEY
    )
    assert total is not None
    assert total != _REFERENCE_TEMPO_TOTAL_AT_TWO_DECIMALS


# --- Group C: the deliberate divergences, always runs -------------------------------------------

_REPEATED_ETAPA_SCENARIO_DIR_NAME = "caso_repetido"
_REPEATED_ETAPA_DECK_DIR_NAME = "deck_unico"
_REPEATED_MILP_ROW_A = 100.0
_REPEATED_MILP_ROW_B = 260.0
_REPEATED_OTHER_ETAPA_SECONDS: Mapping[str, float] = MappingProxyType(
    {
        "Leitura de Dados e Impressão": 120.0,
        "PL": 90.0,
        "PL.Int.Fix": 30.0,
        "PL.CalcCMO": 30.0,
    }
)


def _write_repeated_milp_tempo_frame(sintese_dir: Path) -> None:
    """Write TEMPO.parquet with two MILP rows, matching SCALAR_COLUMNS["TEMPO"]'s three columns:
    the shape consolidate._load_scalars must sum, unlike Plotadores/Tempo.py:23's `.values[0]`."""
    etapas = ["MILP", "MILP", *_REPEATED_OTHER_ETAPA_SECONDS]
    tempos = [_REPEATED_MILP_ROW_A, _REPEATED_MILP_ROW_B, *_REPEATED_OTHER_ETAPA_SECONDS.values()]
    frame = pd.DataFrame(
        {
            "etapa": etapas,
            "tempo": pd.array(tempos, dtype="float64"),
            "execucao": pd.array([0] * len(etapas), dtype="int64"),
        }
    )[list(SCALAR_COLUMNS["TEMPO"])]
    frame.to_parquet(sintese_dir / "TEMPO.parquet", index=False)


def _repeated_etapa_minutes(
    row_a: float, row_b: float, *, unit_divisor: float, decimals: int
) -> tuple[float, float]:
    """Return (summed minutes, first-row-only minutes) for two rows sharing one etapa."""
    summed = round((row_a + row_b) / unit_divisor, decimals)
    first_row_only = round(row_a / unit_divisor, decimals)
    return summed, first_row_only


def _assert_repeated_etapa_rows_differ(
    summed: float, first_row_only: float, *, decimals: int
) -> None:
    assert summed != first_row_only
    assert abs(summed - first_row_only) > 10**-decimals


def test_group_c_repeated_etapa_milp_is_summed_not_first_row_only(tmp_path: Path) -> None:
    """Acceptance criterion 3: a hand-written TEMPO.parquet with two MILP rows proves
    consolidate._load_scalars' groupby-sum reaches the payload, not Plotadores/Tempo.py:23's
    `.values[0]`, which would silently discard the second row's runtime."""
    settings = _build_settings(tmp_path)
    scenario_dir = tmp_path / "tree" / _REPEATED_ETAPA_SCENARIO_DIR_NAME
    deck_dir = scenario_dir / _REPEATED_ETAPA_DECK_DIR_NAME / _SINTESE_DIRNAME
    # omit names full file names, not chart keys (measured: make_sintese_dir's own
    # _all_file_names() yields "TEMPO.parquet", so omit=("TEMPO",) raises ValueError -- a
    # correction over this ticket's Suggested Approach step 5, which writes omit=("TEMPO",)).
    make_sintese_dir(
        deck_dir, first_stage_start=datetime(2024, 3, 3, tzinfo=UTC), omit=("TEMPO.parquet",)
    )
    _write_repeated_milp_tempo_frame(deck_dir)

    data = _build_parity_data([scenario_dir], settings=settings, reference=scenario_dir.name)
    payload = build_payload(data, settings=settings, scenario_colors={}, plotly_layout={})

    deck_key = _deck_date(deck_dir).strftime(_DECK_KEY_DATE_FORMAT)
    milp_stored = payload["charts"]["TEMPO"]["scalars"]["MILP"][scenario_dir.name][deck_key]  # type: ignore[index]

    summed, first_row_only = _repeated_etapa_minutes(
        _REPEATED_MILP_ROW_A,
        _REPEATED_MILP_ROW_B,
        unit_divisor=settings.time.unit_divisor,
        decimals=settings.output.decimals,
    )
    assert milp_stored == summed
    _assert_repeated_etapa_rows_differ(summed, first_row_only, decimals=settings.output.decimals)


def test_group_c_new_dashboard_diverges_from_legacy_axis_type_and_output_file_count(
    tmp_path: Path,
) -> None:
    """Requirement 4's second and third bullets, always on the new side only: the date-typed
    axis (decision 14/E5-9's opposite of the legacy's inert categorical tickformat) and the
    single inlined-Plotly output file (E4-3/E5-2's opposite of the legacy's 21 CDN-loading
    files)."""
    settings = _build_settings(tmp_path)
    scenario_dir = tmp_path / "tree" / "caso_divergences"
    make_sintese_dir(
        scenario_dir / "deck_unico" / _SINTESE_DIRNAME,
        first_stage_start=datetime(2024, 3, 3, tzinfo=UTC),
    )
    data = _build_parity_data([scenario_dir], settings=settings, reference=scenario_dir.name)

    # The real layout, not an empty stand-in like the other tests' plotly_layout={}: this test's
    # own point is to inspect payload["theme"]["layout"]["xaxis"], which build_html always
    # populates from dashboard.theme.plotly_layout_template.
    plotly_layout = theme.plotly_layout_template(date_format=settings.dashboard.date_format)
    payload = build_payload(
        data, settings=settings, scenario_colors={}, plotly_layout=plotly_layout
    )
    xaxis = payload["theme"]["layout"]["xaxis"]  # type: ignore[index]
    assert xaxis["type"] == "date"
    assert xaxis["tickformat"] == settings.dashboard.date_format

    scalar_by_deck_keys = {
        key
        for key, chart in payload["charts"].items()  # type: ignore[union-attr]
        if chart["kind"] == "SCALAR_BY_DECK"  # type: ignore[index]
    }
    assert scalar_by_deck_keys == {"CUSTOS", "TEMPO"}

    output_dir = tmp_path / "out"
    output_file = output_dir / "dashboard.html"
    write_dashboard(data, settings=settings, output_file=output_file)

    assert list(output_dir.iterdir()) == [output_file]

    document = output_file.read_text(encoding="utf-8")
    assert _CATEGORY_SEPARATOR_LITERAL in document
    assert _CATEGORY_LABEL_EXPRESSION in document

    sections = chart_section_slices(document)
    assert len(sections) == _ENABLED_CHART_COUNT

    plotly_start = document.index(_SCRIPT_PLOTLY_OPEN_TAG)
    plotly_end = document.index(_SCRIPT_CLOSE_TAG, plotly_start)
    outside_plotly_bundle = document[:plotly_start] + document[plotly_end:]
    assert _LEGACY_CDN_REFERENCE not in outside_plotly_bundle


# --- non-vacuity proofs: Suggested Approach step 9's four mutations -----------------------------


def test_group_a_sin_chained_check_is_not_vacuous_when_stage_filter_is_narrowed(
    tmp_path: Path,
) -> None:
    """Mutation 1: narrowing the recomputation's own filter from <= 48 to <= 24 must disagree
    with the payload's <= 48-derived chained array, since _GROUP_A_N_STAGES (30) exceeds 24."""
    context = _build_group_a_context(tmp_path)
    with pytest.raises(AssertionError):
        _check_chained_series_matches_legacy(
            context, "GHID_SIN", "", submarket_code=None, stage_filter_max=24
        )


def test_group_a_custos_total_check_is_not_vacuous_when_total_is_just_futuro() -> None:
    """Mutation 2: a stored TOTAL wrongly equal to FUTURO alone -- the exact defect epic-04
    learnings section 3 measured from a wrong aggregate_costs -- must fail
    _assert_custos_scalars_match."""
    with pytest.raises(AssertionError):
        _assert_custos_scalars_match(
            100.0, 200.0, 200.0, presente_raw=100.0, futuro_raw=200.0, decimals=2
        )


def test_group_c_repeated_etapa_divergence_check_is_not_vacuous_when_second_row_is_zero() -> None:
    """Mutation 3: a second MILP row of 0.0 makes the sum equal the first row, so
    _assert_repeated_etapa_rows_differ must then raise."""
    summed, first_row_only = _repeated_etapa_minutes(100.0, 0.0, unit_divisor=60.0, decimals=2)
    with pytest.raises(AssertionError):
        _assert_repeated_etapa_rows_differ(summed, first_row_only, decimals=2)


def test_group_b_skips_without_erroring_when_exemplo_root_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation 4 / acceptance criterion 4's second half: an empty DESSEM_DASHBOARD_EXEMPLO root
    makes Group B skip, naming ENV_VAR and the default path, rather than erroring -- proven on
    _require_two_scenarios, the same resolver every Group B test in this module calls."""
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    monkeypatch.setenv(ENV_VAR, str(empty_root))

    with pytest.raises(pytest.skip.Exception) as exc_info:
        _require_two_scenarios()

    message = str(exc_info.value)
    assert ENV_VAR in message
    assert str(_DEFAULT_ROOT) in message
