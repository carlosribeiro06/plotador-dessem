"""Scalar chart aggregation: turn a raw per-parcel/per-etapa mapping into the series a bar chart
displays.

`aggregate` is `payload._build_chart_entry`'s one entry point into this module for every
`SCALAR_BY_DECK` chart, called once per chart after `_build_scalars` has already rounded the raw
`{series_name: {scenario: {deck_key: value}}}` mapping `consolidate.py` populated. Reads no file,
mutates nothing it is handed, and imports nothing from `builder` or `theme`.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from dessem_dashboard.config import Settings
from dessem_dashboard.errors import ConfigError

logger = logging.getLogger(__name__)

_TOTAL_SERIES_NAME = "TOTAL"
_TOTAL_PARCELS_SETTINGS_KEY = "costs.total_parcels"

ScalarsByName = dict[str, dict[str, dict[str, float | None]]]


def aggregate(chart_key: str, raw: ScalarsByName, *, settings: Settings) -> ScalarsByName:
    """Route chart_key's raw scalar mapping through its own aggregation, or pass it through.

    Dispatches CUSTOS to aggregate_costs; every other chart key -- TEMPO included, until
    ticket-031 adds its own branch -- is returned unchanged and by identity, so the dispatch
    touches only the chart it owns.
    """
    if chart_key == "CUSTOS":
        return aggregate_costs(
            raw, parcels=settings.costs.total_parcels, decimals=settings.output.decimals
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

    pairs: set[tuple[str, str]] = {
        (scenario, deck_key)
        for parcel in present_parcels
        for scenario, by_deck in result[parcel].items()
        for deck_key in by_deck
    }

    total: dict[str, dict[str, float | None]] = {}
    for scenario, deck_key in pairs:
        values: list[float] = []
        for parcel in present_parcels:
            value = result[parcel].get(scenario, {}).get(deck_key)
            if value is None:
                values = []
                break
            values.append(value)
        if not values:
            continue
        summed = round(sum(values), decimals)
        total.setdefault(scenario, {})[deck_key] = 0.0 if summed == 0.0 else summed

    result[_TOTAL_SERIES_NAME] = total
    return result
