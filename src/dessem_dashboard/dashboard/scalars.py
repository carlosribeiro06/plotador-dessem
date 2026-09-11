"""Scalar chart aggregation: turn a raw per-parcel/per-etapa mapping into the series a bar chart
displays.

`aggregate` is `payload._build_chart_entry`'s one entry point into this module for every
`SCALAR_BY_DECK` chart, called once per chart after `_build_scalars` has already rounded the raw
`{series_name: {scenario: {deck_key: value}}}` mapping `consolidate.py` populated. Reads no file,
mutates nothing it is handed, and imports nothing from `builder` or `theme`.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from dessem_dashboard.config import Settings
from dessem_dashboard.errors import ConfigError

logger = logging.getLogger(__name__)

_TOTAL_SERIES_NAME = "TOTAL"
_TOTAL_PARCELS_SETTINGS_KEY = "costs.total_parcels"
_STAGE_GROUPS_SETTINGS_KEY = "time.stage_groups"
_UNIT_DIVISOR_SETTINGS_KEY = "time.unit_divisor"
# The only divisor consistent with FALLBACK_UNITS["TEMPO"] = "min" in data/schemas.py: that label
# is hard-coded there, independently of this setting, so a divisor other than 60.0 makes the two
# sides disagree without either one raising (epic-04 boundary review finding 3).
_EXPECTED_UNIT_DIVISOR = 60.0

ScalarsByName = dict[str, dict[str, dict[str, float | None]]]


def aggregate(chart_key: str, raw: ScalarsByName, *, settings: Settings) -> ScalarsByName:
    """Route chart_key's raw scalar mapping through its own aggregation, or pass it through.

    Dispatches CUSTOS to aggregate_costs and TEMPO to aggregate_times; every other chart key is
    returned unchanged and by identity, so the dispatch touches only the chart it owns.
    """
    if chart_key == "CUSTOS":
        return aggregate_costs(
            raw, parcels=settings.costs.total_parcels, decimals=settings.output.decimals
        )
    if chart_key == "TEMPO":
        return aggregate_times(
            raw,
            stage_groups=settings.time.stage_groups,
            unit_divisor=settings.time.unit_divisor,
            decimals=settings.output.decimals,
        )
    return raw


def aggregate_costs(raw: ScalarsByName, *, parcels: Sequence[str], decimals: int) -> ScalarsByName:
    """Build CUSTOS's displayed series: the members of parcels present in raw, plus TOTAL.

    Never computes the total as a literal sum of two named parcels: E4-1 makes the parcel set
    entirely settings-driven, so any parcel named in the configured order contributes to TOTAL
    the same way as every other one, the default pair included.

    Raises:
        ConfigError: if TOTAL itself is named in parcels -- the computed series would overwrite a
            data series of the same name, and no output would be correct.

    A parcel named in parcels but absent from raw altogether is logged once as a Portuguese
    warning naming the parcel and the dotted settings key, then omitted from both the bars and the
    total (E4-1's degradation rule). That is a different case, governed by a different rule, from
    a single (scenario, deck_key) cell missing among the parcels that ARE present: TOTAL is
    emitted for a (scenario, deck_key) pair only when every present parcel carries a non-None
    value there, so a partially covered cell degrades by omission rather than by summing a subset.
    """
    if _TOTAL_SERIES_NAME in parcels:
        raise ConfigError(
            f"Chave '{_TOTAL_PARCELS_SETTINGS_KEY}' não pode incluir '{_TOTAL_SERIES_NAME}': "
            "essa série é calculada a partir das demais parcelas, não é configurável"
        )

    result: ScalarsByName = {}
    present_parcels: list[str] = []
    for parcel in parcels:
        series = raw.get(parcel)
        if series is None:
            logger.warning(
                "Parcela '%s' configurada em '%s' não foi encontrada nos dados de CUSTOS: "
                "parcela omitida do gráfico e do total",
                parcel,
                _TOTAL_PARCELS_SETTINGS_KEY,
            )
            continue
        result[parcel] = series
        present_parcels.append(parcel)

    result[_TOTAL_SERIES_NAME] = _strict_total(result, present_parcels, decimals=decimals)
    return result


def _round_nonzero(value: float, decimals: int) -> float:
    """Round value to decimals, normalising a rounded -0.0 to 0.0."""
    rounded = round(value, decimals)
    return 0.0 if rounded == 0.0 else rounded


def _strict_total(
    series_by_name: ScalarsByName, names: Sequence[str], *, decimals: int
) -> dict[str, dict[str, float | None]]:
    """Sum names' series of series_by_name into the TOTAL series, under the strict rule.

    A (scenario, deck_key) cell is emitted only when every one of names carries a non-None value
    there, so a partially covered cell degrades by omission rather than by summing a subset:
    aggregate_costs' parcels and aggregate_times' groups are themselves displayed bars, and a
    partial TOTAL would stop equalling what the operator can already add up beside it on the
    chart. Deliberately stricter than aggregate_times' own per-group sum, whose member etapas are
    never displayed on their own and which is therefore lenient by design.

    Sorting the (scenario, deck_key) set is a reproducibility requirement, not redundancy:
    iterating the set directly follows the per-process randomised hash, which makes the generated
    HTML non-reproducible.
    """
    pairs: set[tuple[str, str]] = {
        (scenario, deck_key)
        for name in names
        for scenario, by_deck in series_by_name[name].items()
        for deck_key in by_deck
    }

    total: dict[str, dict[str, float | None]] = {}
    for scenario, deck_key in sorted(pairs):
        values: list[float] = []
        for name in names:
            value = series_by_name[name].get(scenario, {}).get(deck_key)
            if value is None:
                values = []
                break
            values.append(value)
        if not values:
            continue
        total.setdefault(scenario, {})[deck_key] = _round_nonzero(sum(values), decimals)
    return total


def aggregate_times(
    raw: ScalarsByName,
    *,
    stage_groups: Mapping[str, Sequence[str]],
    unit_divisor: float,
    decimals: int,
) -> ScalarsByName:
    """Build TEMPO's displayed series: one bar per stage_groups entry, in configured order, plus
    TOTAL.

    Each group's cell at (scenario, deck_key) sums raw[etapa][scenario][deck_key] over the
    group's members that exist in raw, divided by unit_divisor and rounded once (requirement 2).
    raw already holds one value per distinct etapa -- consolidate._load_scalars sums the repeated
    executions of one etapa (PL runs three times) before this module ever sees it -- so this sum
    only ever combines DISTINCT etapas, PL, PL.Int.Fix and PL.CalcCMO under the shipped "PL"
    group, and never re-sums what that phase already summed.

    A group cell is omitted, never written as 0, only when every one of the group's present
    members lacks a value there (requirement 3); when at least one does, the cell sums whichever
    present members carry a value. This is deliberately more lenient than TOTAL below: a group's
    member etapas are never displayed on their own, so a partial sum here degrades one bar's
    precision rather than contradicting a visible sibling.

    Raises:
        ConfigError: if TOTAL itself is named as a group in stage_groups -- the computed series
            would overwrite a configured one, mirroring aggregate_costs' requirement 6.

    A group named in stage_groups whose members are all absent from raw is logged once as a
    Portuguese warning naming the group and the dotted settings key, then omitted entirely
    (requirement 3). An etapa present in raw but named by no group is logged once as a Portuguese
    warning naming the etapa and the dotted settings key, then contributes to no bar and no total
    (requirement 5). Neither case raises: only the TOTAL-as-group-name collision above does.

    TOTAL follows the emitted groups, in stage_groups' own insertion order, summing their
    already-converted, already-rounded values and rounding once more (requirement 4). Unlike a
    group's own leniency above, TOTAL is emitted for a (scenario, deck_key) only when every
    emitted group carries a non-None value there: the groups ARE separately displayed bars, so a
    partial TOTAL would stop equalling what the operator can already add up beside it on the
    chart.

    unit_divisor other than 60.0 is also logged once as a Portuguese warning, naming the "min"
    label that FALLBACK_UNITS["TEMPO"] (data/schemas.py) hard-codes independently of this setting
    and that would then no longer match the values this function divides and emits (epic-04
    boundary review finding 3: the two sides were pinned by separate tests and never together).
    """
    if _TOTAL_SERIES_NAME in stage_groups:
        raise ConfigError(
            f"Chave '{_STAGE_GROUPS_SETTINGS_KEY}' não pode incluir um grupo chamado "
            f"'{_TOTAL_SERIES_NAME}': essa série é calculada a partir dos demais grupos, não é "
            "configurável"
        )

    if unit_divisor != _EXPECTED_UNIT_DIVISOR:
        logger.warning(
            "Configuração '%s' = %s difere de %s: o eixo Y do gráfico TEMPO continua rotulado "
            "'min' (FALLBACK_UNITS['TEMPO'] em data/schemas.py), que deixa de corresponder à "
            "unidade dos valores exibidos",
            _UNIT_DIVISOR_SETTINGS_KEY,
            unit_divisor,
            _EXPECTED_UNIT_DIVISOR,
        )

    result: ScalarsByName = {}
    emitted_groups: list[str] = []
    configured_members: set[str] = set()

    for group_name, members in stage_groups.items():
        configured_members.update(members)
        present_members = [member for member in members if member in raw]
        if not present_members:
            logger.warning(
                "Grupo '%s' configurado em '%s' não possui nenhuma etapa presente nos dados de "
                "TEMPO: grupo omitido do gráfico e do total",
                group_name,
                _STAGE_GROUPS_SETTINGS_KEY,
            )
            continue

        pairs: set[tuple[str, str]] = {
            (scenario, deck_key)
            for member in present_members
            for scenario, by_deck in raw[member].items()
            for deck_key in by_deck
        }

        group_series: dict[str, dict[str, float | None]] = {}
        for scenario, deck_key in sorted(pairs):
            values = [
                value
                for member in present_members
                if (value := raw[member].get(scenario, {}).get(deck_key)) is not None
            ]
            if not values:
                continue
            group_series.setdefault(scenario, {})[deck_key] = _round_nonzero(
                sum(values) / unit_divisor, decimals
            )

        result[group_name] = group_series
        emitted_groups.append(group_name)

    for etapa in sorted(set(raw) - configured_members):
        logger.warning(
            "Etapa '%s' presente nos dados de TEMPO não está coberta por nenhum grupo de '%s': "
            "etapa omitida do gráfico e do total",
            etapa,
            _STAGE_GROUPS_SETTINGS_KEY,
        )

    result[_TOTAL_SERIES_NAME] = _strict_total(result, emitted_groups, decimals=decimals)
    return result
