"""Registry loading and human-readable labels for the DESSEM synthesis files.

Loads the five registry Parquet files (UHE, UTE, SBM, REE, METADADOS_OPERACAO) into one immutable
Registries per deck, the single source of every plant name, submarket label, and variable title/unit
the dashboard shows. Every fallback label produced here is Portuguese, because it reaches the
dashboard UI. This module performs no writes and reads only through readers.read_registry.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import pandas as pd

from dessem_dashboard.data.readers import read_registry
from dessem_dashboard.data.schemas import FALLBACK_UNITS
from dessem_dashboard.errors import RegistryError
from dessem_dashboard.logging_setup import log_step

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HydroPlant:
    """One row of UHE.parquet."""

    code: int
    name: str
    ree_code: int
    ree: str
    submarket_code: int
    submarket: str


@dataclass(frozen=True, slots=True)
class ThermalPlant:
    """One row of UTE.parquet."""

    code: int
    name: str
    submarket_code: int
    submarket: str


@dataclass(frozen=True, slots=True)
class Submarket:
    """One row of SBM.parquet. long_name falls back to short_name when nome_submercado is null."""

    code: int
    short_name: str
    long_name: str
    fictitious: bool


@dataclass(frozen=True, slots=True)
class VariableMeta:
    """One row of METADADOS_OPERACAO.parquet. long_name is "" when nome_longo_variavel is null."""

    key: str
    short_name: str
    long_name: str
    unit: str


@dataclass(frozen=True, slots=True)
class Registries:
    """Immutable label lookups for one deck's synthesis directory."""

    hydro: Mapping[int, HydroPlant]
    thermal: Mapping[int, ThermalPlant]
    submarkets: Mapping[int, Submarket]
    rees: Mapping[int, str]
    variables: Mapping[str, VariableMeta]

    def unit_for(self, chart_key: str) -> str:
        """Return the METADADOS_OPERACAO unit, else FALLBACK_UNITS, else raise RegistryError."""
        variable = self.variables.get(chart_key)
        if variable is not None:
            return variable.unit
        try:
            return FALLBACK_UNITS[chart_key]
        except KeyError as err:
            raise RegistryError(
                f"Unidade desconhecida para a chave de gráfico '{chart_key}': ausente em "
                "METADADOS_OPERACAO e em FALLBACK_UNITS"
            ) from err

    def title_for(self, chart_key: str) -> str | None:
        """Return nome_longo_variavel when known and non-null, else None."""
        variable = self.variables.get(chart_key)
        if variable is None or not variable.long_name:
            return None
        return variable.long_name

    def hydro_name(self, code: int) -> str:
        """Return the hydro plant name, or the Portuguese fallback for an unknown code."""
        plant = self.hydro.get(code)
        return plant.name if plant is not None else f"Usina {code}"

    def thermal_name(self, code: int) -> str:
        """Return the thermal plant name, or the Portuguese fallback for an unknown code."""
        plant = self.thermal.get(code)
        return plant.name if plant is not None else f"Usina {code}"

    def submarket_label(self, code: int) -> str:
        """Return "short (long)" for a known submarket, or the Portuguese fallback otherwise."""
        submarket = self.submarkets.get(code)
        if submarket is None:
            return f"Submercado {code}"
        return f"{submarket.short_name} ({submarket.long_name})"


def _build_hydro(frame: pd.DataFrame) -> dict[int, HydroPlant]:
    """Build the codigo_usina -> HydroPlant mapping from a validated UHE.parquet frame.

    Selects columns by name before iterating, so the tuple positions below are independent of the
    source file's own column order (read_registry checks the column set, not the order).
    """
    columns = ["codigo_usina", "codigo_ree", "codigo_submercado", "ree", "submercado", "usina"]
    hydro: dict[int, HydroPlant] = {}
    for code, ree_code, submarket_code, ree, submarket, name in frame[columns].itertuples(
        index=False, name=None
    ):
        hydro[int(code)] = HydroPlant(
            code=int(code),
            name=str(name),
            ree_code=int(ree_code),
            ree=str(ree),
            submarket_code=int(submarket_code),
            submarket=str(submarket),
        )
    return hydro


def _build_thermal(frame: pd.DataFrame) -> dict[int, ThermalPlant]:
    """Build the codigo_usina -> ThermalPlant mapping from a validated UTE.parquet frame."""
    columns = ["codigo_usina", "usina", "codigo_submercado", "submercado"]
    thermal: dict[int, ThermalPlant] = {}
    for code, name, submarket_code, submarket in frame[columns].itertuples(index=False, name=None):
        thermal[int(code)] = ThermalPlant(
            code=int(code),
            name=str(name),
            submarket_code=int(submarket_code),
            submarket=str(submarket),
        )
    return thermal


def _build_rees(frame: pd.DataFrame) -> dict[int, str]:
    """Build the codigo_ree -> ree name mapping from a validated REE.parquet frame."""
    columns = ["codigo_ree", "ree"]
    return {
        int(code): str(name) for code, name in frame[columns].itertuples(index=False, name=None)
    }


def _build_submarkets(
    frame: pd.DataFrame, fictitious_codes: frozenset[int], *, source: Path
) -> dict[int, Submarket]:
    """Build the codigo_submercado -> Submarket mapping from a validated SBM.parquet frame.

    Drops rows with a null codigo_submercado, logging a warning naming them by their short name,
    because a nullable Int64 value cannot be cast to int. A null nome_submercado takes short_name
    as long_name (requirement 6); this never happens for codigo_submercado itself.
    """
    null_mask = frame["codigo_submercado"].isna()
    if bool(null_mask.any()):
        dropped_names = [str(name) for name in frame.loc[null_mask, "submercado"]]
        logger.warning(
            "Descartando %d linha(s) de %s com codigo_submercado nulo (submercado: %s)",
            int(null_mask.sum()),
            source.name,
            ", ".join(dropped_names),
        )
    frame = frame.dropna(subset=["codigo_submercado"])

    columns = ["codigo_submercado", "submercado", "nome_submercado"]
    submarkets: dict[int, Submarket] = {}
    for code, short_name, long_name_raw in frame[columns].itertuples(index=False, name=None):
        code_int = int(code)
        short_name_str = str(short_name)
        long_name = short_name_str if pd.isna(long_name_raw) else str(long_name_raw)
        submarkets[code_int] = Submarket(
            code=code_int,
            short_name=short_name_str,
            long_name=long_name,
            fictitious=code_int in fictitious_codes,
        )
    return submarkets


def _build_variables(frame: pd.DataFrame) -> dict[str, VariableMeta]:
    """Build the chave -> VariableMeta mapping from a validated METADADOS_OPERACAO.parquet frame.

    unit is resolved against FALLBACK_UNITS at load time (requirement 4's suggested approach), so
    unit_for later becomes a plain lookup with one final fallback for keys absent from the file.
    A null nome_curto_variavel/nome_longo_variavel is stored as "" (requirement 5).
    """
    columns = ["chave", "nome_curto_variavel", "nome_longo_variavel", "unidade"]
    variables: dict[str, VariableMeta] = {}
    for key_raw, short_raw, long_raw, unit_raw in frame[columns].itertuples(index=False, name=None):
        key = str(key_raw)
        short_name = "" if pd.isna(short_raw) else str(short_raw)
        long_name = "" if pd.isna(long_raw) else str(long_raw)
        if pd.isna(unit_raw):
            try:
                unit = FALLBACK_UNITS[key]
            except KeyError as err:
                raise RegistryError(
                    f"Nenhuma unidade disponível para a chave de variável '{key}': ausente em "
                    "METADADOS_OPERACAO e em FALLBACK_UNITS"
                ) from err
        else:
            unit = str(unit_raw)
        variables[key] = VariableMeta(
            key=key, short_name=short_name, long_name=long_name, unit=unit
        )
    return variables


def load_registries(sintese_dir: Path, *, fictitious_codes: Sequence[int] = (11, 99)) -> Registries:
    """Load UHE, UTE, SBM, REE and METADADOS_OPERACAO from sintese_dir into one Registries.

    Performs five reads through readers.read_registry and no writes. DataFileError propagates
    unchanged when a registry file is missing; that is a hard failure per the ticket's Error
    Handling section, not a degradable warning.
    """
    fictitious_set = frozenset(fictitious_codes)

    uhe_path = sintese_dir / "UHE.parquet"
    ute_path = sintese_dir / "UTE.parquet"
    sbm_path = sintese_dir / "SBM.parquet"
    ree_path = sintese_dir / "REE.parquet"
    variables_path = sintese_dir / "METADADOS_OPERACAO.parquet"

    uhe_frame = read_registry(uhe_path, "UHE")
    ute_frame = read_registry(ute_path, "UTE")
    sbm_frame = read_registry(sbm_path, "SBM")
    ree_frame = read_registry(ree_path, "REE")
    variables_frame = read_registry(variables_path, "METADADOS_OPERACAO")

    hydro = _build_hydro(uhe_frame)
    thermal = _build_thermal(ute_frame)
    submarkets = _build_submarkets(sbm_frame, fictitious_set, source=sbm_path)
    rees = _build_rees(ree_frame)
    variables = _build_variables(variables_frame)

    registries = Registries(
        hydro=MappingProxyType(hydro),
        thermal=MappingProxyType(thermal),
        submarkets=MappingProxyType(submarkets),
        rees=MappingProxyType(rees),
        variables=MappingProxyType(variables),
    )

    log_step(
        logger,
        "Registros carregados",
        usinas_hidraulicas=len(hydro),
        usinas_termicas=len(thermal),
        submercados=len(submarkets),
        rees=len(rees),
        variaveis=len(variables),
    )
    return registries


def visible_submarket_codes(registries: Registries, *, include_fictitious: bool) -> tuple[int, ...]:
    """Return registries.submarkets codes ascending, excluding fictitious ones unless requested."""
    codes = (
        code
        for code, submarket in registries.submarkets.items()
        if include_fictitious or not submarket.fictitious
    )
    return tuple(sorted(codes))
