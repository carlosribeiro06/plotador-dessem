"""Chart registry mechanics: ChartSpec record, ChartRegistry, and the REGISTRY singleton.

Pure metadata: no pandas import, no file I/O. The catalogue itself (ticket-011) declares
ChartSpec instances against this module; Epic 3/4 consumers iterate `enabled_specs()` to decide
what to render.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from dessem_dashboard.data.schemas import AggregationLevel
from dessem_dashboard.errors import RegistryError


class ChartKind(StrEnum):
    """Whether a chart is a time series or a scalar-per-deck bar chart."""

    SERIES = "SERIES"
    SCALAR_BY_DECK = "SCALAR_BY_DECK"


class EntitySelector(StrEnum):
    """UI selector a chart exposes, if any."""

    NONE = "NONE"
    SUBMARKET = "SUBMARKET"
    SUBMARKET_PAIR = "SUBMARKET_PAIR"
    HYDRO_PLANT = "HYDRO_PLANT"
    THERMAL_PLANT = "THERMAL_PLANT"


class ChartGroup(StrEnum):
    """Dashboard navigation group a chart belongs to."""

    SIN = "SIN"
    SBM = "SBM"
    SBP = "SBP"
    UHE = "UHE"
    UTE = "UTE"
    EXECUCAO = "EXECUCAO"


@dataclass(frozen=True, slots=True)
class ChartSpec:
    """Declarative description of one chart in the catalogue."""

    key: str
    source_file: str
    level: AggregationLevel | None
    group: ChartGroup
    kind: ChartKind
    selector: EntitySelector
    title: str
    unit: str
    enabled: bool = True
    notes: str = ""


class ChartRegistry:
    """Insertion-ordered collection of ChartSpec instances, keyed by ChartSpec.key."""

    def __init__(self) -> None:
        self._specs: dict[str, ChartSpec] = {}

    def register(self, spec: ChartSpec) -> None:
        """Validate spec and add it, keyed by spec.key."""
        self._validate(spec)
        self._specs[spec.key] = spec

    def _validate(self, spec: ChartSpec) -> None:
        if spec.key in self._specs:
            raise RegistryError(f"Chave de gráfico já registrada: '{spec.key}'")
        if not spec.source_file:
            raise RegistryError(f"Arquivo de origem vazio para a chave de gráfico: '{spec.key}'")
        if spec.kind is ChartKind.SERIES and spec.level is None:
            raise RegistryError(
                f"Nível de agregação obrigatório para gráfico do tipo SERIES: chave '{spec.key}'"
            )

    def all_specs(self) -> tuple[ChartSpec, ...]:
        """Return every registered spec, in registration order."""
        return tuple(self._specs.values())

    def enabled_specs(self, *, disabled: Sequence[str] = ()) -> tuple[ChartSpec, ...]:
        """Return enabled specs not named in disabled, in registration order.

        Raises RegistryError if disabled names a key that was never registered, so a typo in
        settings.json's charts.disabled fails loudly instead of silently disabling nothing.
        """
        for key in disabled:
            if key not in self._specs:
                raise RegistryError(f"Chave de gráfico desconhecida em 'disabled': '{key}'")
        excluded = set(disabled)
        return tuple(
            spec for spec in self._specs.values() if spec.enabled and spec.key not in excluded
        )

    def spec(self, key: str) -> ChartSpec:
        """Return the registered spec for key."""
        if key not in self._specs:
            raise RegistryError(f"Chave de gráfico não registrada: '{key}'")
        return self._specs[key]


REGISTRY = ChartRegistry()


def register(spec: ChartSpec) -> None:
    """Register spec into the module-level REGISTRY singleton."""
    REGISTRY.register(spec)


def all_specs() -> tuple[ChartSpec, ...]:
    """Return every spec in REGISTRY, in registration order."""
    return REGISTRY.all_specs()


def enabled_specs(*, disabled: Sequence[str] = ()) -> tuple[ChartSpec, ...]:
    """Return REGISTRY's enabled specs not named in disabled."""
    return REGISTRY.enabled_specs(disabled=disabled)


def spec(key: str) -> ChartSpec:
    """Return REGISTRY's spec for key."""
    return REGISTRY.spec(key)
