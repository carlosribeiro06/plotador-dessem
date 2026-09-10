"""Default chart catalogue: the 42 ChartSpec entries and their registration.

Declares SPECS, the literal catalogue fixed by Appendix A.6 of the master plan: the 23 charts
enabled by default (the spec minimum list plus TEMPO), followed by 19 further specs shipped
disabled to demonstrate the registry's extensibility. register_default_specs loads SPECS into a
ChartRegistry, defaulting to the REGISTRY singleton.
"""

from __future__ import annotations

from dessem_dashboard.charts.registry import (
    REGISTRY,
    ChartGroup,
    ChartKind,
    ChartRegistry,
    ChartSpec,
    EntitySelector,
)
from dessem_dashboard.data.schemas import FALLBACK_UNITS, AggregationLevel


def _series(
    key: str,
    group: ChartGroup,
    level: AggregationLevel,
    selector: EntitySelector,
    title: str,
    *,
    enabled: bool = True,
    notes: str = "",
) -> ChartSpec:
    """Build a SERIES ChartSpec whose source_file and unit are derived from key."""
    return ChartSpec(
        key=key,
        source_file=key,
        level=level,
        group=group,
        kind=ChartKind.SERIES,
        selector=selector,
        title=title,
        unit=FALLBACK_UNITS[key],
        enabled=enabled,
        notes=notes,
    )


def _scalar(key: str, title: str, *, notes: str = "") -> ChartSpec:
    """Build a SCALAR_BY_DECK ChartSpec in the EXECUCAO group with no aggregation level."""
    return ChartSpec(
        key=key,
        source_file=key,
        level=None,
        group=ChartGroup.EXECUCAO,
        kind=ChartKind.SCALAR_BY_DECK,
        selector=EntitySelector.NONE,
        title=title,
        unit=FALLBACK_UNITS[key],
        notes=notes,
    )


_OPEN_QUESTION_2_NOTE = (
    "Ships alongside its pair per master plan open question 2 (UHE 'Volume armazenado' "
    "ambiguity: hm3 vs percent)."
)
_OPEN_QUESTION_3_NOTE = (
    "Ships alongside its pair per master plan open question 3 (UHE 'Vazão' ambiguity: "
    "afluente vs incremental)."
)

SPECS: tuple[ChartSpec, ...] = (
    _series(
        "GTER_SIN", ChartGroup.SIN, AggregationLevel.SIN, EntitySelector.NONE, "Geração Térmica"
    ),
    _series(
        "GHID_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Geração Hidrelétrica",
    ),
    _series(
        "GUNS_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Geração Não Simulada",
    ),
    _series("EARMF_SIN", ChartGroup.SIN, AggregationLevel.SIN, EntitySelector.NONE, "EARMF"),
    _series(
        "VARMF_SIN", ChartGroup.SIN, AggregationLevel.SIN, EntitySelector.NONE, "Volume Armazenado"
    ),
    _series(
        "MER_SBM",
        ChartGroup.SBM,
        AggregationLevel.SBM,
        EntitySelector.SUBMARKET,
        "Carga (Mercado de Energia)",
    ),
    _series(
        "GHID_SBM",
        ChartGroup.SBM,
        AggregationLevel.SBM,
        EntitySelector.SUBMARKET,
        "Geração Hidráulica",
    ),
    _series(
        "GTER_SBM",
        ChartGroup.SBM,
        AggregationLevel.SBM,
        EntitySelector.SUBMARKET,
        "Geração Térmica",
    ),
    _series(
        "GUNS_SBM",
        ChartGroup.SBM,
        AggregationLevel.SBM,
        EntitySelector.SUBMARKET,
        "Geração Não Simulada",
    ),
    _series("CMO_SBM", ChartGroup.SBM, AggregationLevel.SBM, EntitySelector.SUBMARKET, "CMO"),
    _series(
        "VARMF_SBM",
        ChartGroup.SBM,
        AggregationLevel.SBM,
        EntitySelector.SUBMARKET,
        "Volume Armazenado",
    ),
    _series(
        "INT_SBP",
        ChartGroup.SBP,
        AggregationLevel.SBP,
        EntitySelector.SUBMARKET_PAIR,
        "Intercâmbios",
    ),
    _series(
        "GHID_UHE", ChartGroup.UHE, AggregationLevel.UHE, EntitySelector.HYDRO_PLANT, "Geração"
    ),
    _series(
        "QTUR_UHE", ChartGroup.UHE, AggregationLevel.UHE, EntitySelector.HYDRO_PLANT, "Turbinamento"
    ),
    _series(
        "QVER_UHE", ChartGroup.UHE, AggregationLevel.UHE, EntitySelector.HYDRO_PLANT, "Vertimento"
    ),
    _series(
        "VARMF_UHE",
        ChartGroup.UHE,
        AggregationLevel.UHE,
        EntitySelector.HYDRO_PLANT,
        "Volume Armazenado (hm3)",
        notes=_OPEN_QUESTION_2_NOTE,
    ),
    _series(
        "VARPF_UHE",
        ChartGroup.UHE,
        AggregationLevel.UHE,
        EntitySelector.HYDRO_PLANT,
        "Volume Armazenado (%)",
        notes=_OPEN_QUESTION_2_NOTE,
    ),
    _series(
        "QDEF_UHE", ChartGroup.UHE, AggregationLevel.UHE, EntitySelector.HYDRO_PLANT, "Defluência"
    ),
    _series(
        "QAFL_UHE",
        ChartGroup.UHE,
        AggregationLevel.UHE,
        EntitySelector.HYDRO_PLANT,
        "Vazão Afluente",
        notes=_OPEN_QUESTION_3_NOTE,
    ),
    _series(
        "QINC_UHE",
        ChartGroup.UHE,
        AggregationLevel.UHE,
        EntitySelector.HYDRO_PLANT,
        "Vazão Incremental",
        notes=_OPEN_QUESTION_3_NOTE,
    ),
    _series(
        "GTER_UTE", ChartGroup.UTE, AggregationLevel.UTE, EntitySelector.THERMAL_PLANT, "Geração"
    ),
    _scalar("CUSTOS", "Custo Presente, Futuro e Total"),
    _scalar("TEMPO", "Tempo Computacional"),
    _series(
        "MER_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Mercado de Energia",
        enabled=False,
    ),
    _series(
        "MERL_SBM",
        ChartGroup.SBM,
        AggregationLevel.SBM,
        EntitySelector.SUBMARKET,
        "Mercado de Energia Líquido",
        enabled=False,
    ),
    _series(
        "MERL_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Mercado de Energia Líquido",
        enabled=False,
    ),
    _series(
        "GUNSD_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Geração Não Simulada Despachada",
        enabled=False,
    ),
    _series(
        "GUNSD_SBM",
        ChartGroup.SBM,
        AggregationLevel.SBM,
        EntitySelector.SUBMARKET,
        "Geração Não Simulada Despachada",
        enabled=False,
    ),
    _series(
        "EARMF_SBM",
        ChartGroup.SBM,
        AggregationLevel.SBM,
        EntitySelector.SUBMARKET,
        "EARMF",
        enabled=False,
    ),
    _series(
        "VARMI_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Volume Armazenado Inicial",
        enabled=False,
    ),
    _series(
        "VARMI_SBM",
        ChartGroup.SBM,
        AggregationLevel.SBM,
        EntitySelector.SUBMARKET,
        "Volume Armazenado Inicial",
        enabled=False,
    ),
    _series(
        "VARMI_UHE",
        ChartGroup.UHE,
        AggregationLevel.UHE,
        EntitySelector.HYDRO_PLANT,
        "Volume Armazenado Inicial (hm3)",
        enabled=False,
    ),
    _series(
        "VARPI_UHE",
        ChartGroup.UHE,
        AggregationLevel.UHE,
        EntitySelector.HYDRO_PLANT,
        "Volume Armazenado Inicial (%)",
        enabled=False,
    ),
    _series(
        "VAGUA_UHE",
        ChartGroup.UHE,
        AggregationLevel.UHE,
        EntitySelector.HYDRO_PLANT,
        "Valor da Água",
        enabled=False,
    ),
    _series(
        "VCALHA_UHE",
        ChartGroup.UHE,
        AggregationLevel.UHE,
        EntitySelector.HYDRO_PLANT,
        "Volume de Calha",
        enabled=False,
    ),
    _series(
        "CFU_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Custo Futuro",
        enabled=False,
    ),
    _series(
        "COP_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Custo de Operação",
        enabled=False,
    ),
    _series(
        "CUNS_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Corte de Geração Não Simulada",
        enabled=False,
    ),
    _series(
        "CUNS_SBM",
        ChartGroup.SBM,
        AggregationLevel.SBM,
        EntitySelector.SUBMARKET,
        "Corte de Geração Não Simulada",
        enabled=False,
    ),
    _series(
        "QDEF_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Defluência",
        enabled=False,
    ),
    _series(
        "QTUR_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Turbinamento",
        enabled=False,
    ),
    _series(
        "QVER_SIN",
        ChartGroup.SIN,
        AggregationLevel.SIN,
        EntitySelector.NONE,
        "Vertimento",
        enabled=False,
    ),
)

_registered_singleton = False


def register_default_specs(registry: ChartRegistry | None = None) -> None:
    """Register every entry of SPECS into registry, defaulting to the REGISTRY singleton.

    Idempotent on the singleton: a second call targeting REGISTRY is a no-op, so importing
    dessem_dashboard.charts more than once cannot raise a duplicate-key RegistryError. A caller
    that passes an explicit registry is never guarded, since a fresh ChartRegistry() has no
    duplicate-key risk.
    """
    global _registered_singleton
    target = REGISTRY if registry is None else registry
    if target is REGISTRY:
        if _registered_singleton:
            return
        _registered_singleton = True
    for chart_spec in SPECS:
        target.register(chart_spec)
