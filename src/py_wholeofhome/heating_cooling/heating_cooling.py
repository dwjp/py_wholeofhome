import logging
import math
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
import numpy.typing as npt
import pandas as pd

from ..utilities import get_nathers_zone

here = Path(__file__).parent


class HeatingCoolingType(Enum):
    HEAT_PUMP = 0           # Reverse cycle: heating + cooling (uses HSPF + TCSPF)
    AC = 1                  # Cooling only (uses TCSPF)
    GAS_DUCTED = 2          # Ducted gas heater (Eq 22/23)
    GAS_NON_DUCTED = 3      # Non-ducted gas heater (Eq 24)
    WOOD = 4                # Wood heater
    ELECTRIC_RESISTANCE = 5
    HYDRONIC_GAS = 6
    HYDRONIC_HEAT_PUMP_AIR = 7
    HYDRONIC_HEAT_PUMP_GROUND = 8
    HYDRONIC_ELECTRIC = 9
    EVAPORATIVE = 10        # Cooling only


class HeatingCoolingLossType(Enum):
    # LS: system loss factor — fraction of energy lost in distribution (e.g. ductwork), range 0–1
    DUCTED = 0          # 0.15 (new homes) or 0.15 + age×0.0085 (existing, age capped at 30 years)
    HYDRONIC_PANEL = 1  # 0.10
    SLAB = 2            # 0.15
    NON_DUCTED = 3      # 0.0 — non-ducted systems have no distribution losses (Table 14)


_ELECTRIC_TYPES = {
    HeatingCoolingType.HEAT_PUMP,
    HeatingCoolingType.AC,
    HeatingCoolingType.ELECTRIC_RESISTANCE,
    HeatingCoolingType.EVAPORATIVE,
    HeatingCoolingType.HYDRONIC_HEAT_PUMP_AIR,
    HeatingCoolingType.HYDRONIC_HEAT_PUMP_GROUND,
    HeatingCoolingType.HYDRONIC_ELECTRIC,
}

_GAS_TYPES = {
    HeatingCoolingType.GAS_DUCTED,
    HeatingCoolingType.GAS_NON_DUCTED,
    HeatingCoolingType.HYDRONIC_GAS,
}

_DUCTED_TYPES = {
    HeatingCoolingType.HEAT_PUMP,
    HeatingCoolingType.AC,
    HeatingCoolingType.GAS_DUCTED,
    HeatingCoolingType.EVAPORATIVE,
}

# Ancillary electrical load factors A (Eq 15, Table 15). E_A,hr = E_z,hr × A.
# GAS_DUCTED fan load is computed separately via _gas_ducted_ancillary_factor (depends on GER).
_ANCILLARY_FACTORS = {
    HeatingCoolingType.HEAT_PUMP: 0.0,              # 0% — included in HSPF/TCSPF (Table 15 note b)
    HeatingCoolingType.AC: 0.0,                     # 0% — included in TCSPF (Table 15 note b)
    HeatingCoolingType.EVAPORATIVE: 0.0,            # 0% — included in COP_A (Table 15 note b)
    HeatingCoolingType.GAS_NON_DUCTED: 0.01,        # 1% — non-ducted systems (Table 15)
    HeatingCoolingType.ELECTRIC_RESISTANCE: 0.0,    # 0% — no ancillary (§3.4.6)
    HeatingCoolingType.HYDRONIC_GAS: 0.01,          # 1% — hydronic pump (Table 15)
    HeatingCoolingType.HYDRONIC_HEAT_PUMP_AIR: 0.01,    # 1% — hydronic pump (Table 15)
    HeatingCoolingType.HYDRONIC_HEAT_PUMP_GROUND: 0.01, # 1% — hydronic pump (Table 15)
    HeatingCoolingType.HYDRONIC_ELECTRIC: 0.01,         # 1% — hydronic pump (Table 15)
    HeatingCoolingType.WOOD: 0.01,                  # 1% — non-ducted fan (Table 15); ducted uses 3%
}

# Default COP_A values for appliance types with fixed efficiency (§3.4.6, §3.4.7, §3.4.8; Table 29).
_FIXED_COP_A = {
    HeatingCoolingType.ELECTRIC_RESISTANCE: 1.0,         # §3.4.6
    HeatingCoolingType.EVAPORATIVE: 15.0,                # §3.4.8; ancillary included (Table 15 note b)
    HeatingCoolingType.HYDRONIC_GAS: 0.7,                # Table 29
    HeatingCoolingType.HYDRONIC_HEAT_PUMP_AIR: 3.0,      # Table 29
    HeatingCoolingType.HYDRONIC_HEAT_PUMP_GROUND: 3.6,   # Table 29
    HeatingCoolingType.HYDRONIC_ELECTRIC: 1.0,           # Table 29
}


def get_gems_zone(postcode: int) -> str:
    """Return the GEMS/ZERL climate zone string for a postcode.

    GEMS: Greenhouse and Energy Minimum Standards — national regulatory standard.
    ZERL: zoned energy rating label — climate-zone-specific label (cold/mixed/hot-humid).
    """
    nathers_zone = get_nathers_zone(postcode)
    zone_data = pd.read_csv(
        here / 'reference_data' / 'nathers_and_gems_zones_rev10.1.csv',
        index_col='NatHERS Climate Zone',
    )
    return str(zone_data.loc[nathers_zone]['Applicable GEMS ZERL Zone'])


def get_default_hspf_tcspf(postcode: int) -> dict:
    """Return default HSPF/TCSPF values for a heat pump by GEMS/ZERL zone (Table 13).

    HSPF: heating seasonal performance factor (W/W) per AS/NZS 3823.4.
    TCSPF: total cooling seasonal performance factor (W/W) per AS/NZS 3823.4.
    """
    gems_zone = get_gems_zone(postcode)
    if gems_zone == "Hot/humid":
        return {"heating_hspf": 4.0, "cooling_tcspf": 4.0}  # Table 13
    elif gems_zone == "Mixed":
        return {"heating_hspf": 3.5, "cooling_tcspf": 3.5}  # Table 13
    elif gems_zone == "Cold":
        return {"heating_hspf": 2.5, "cooling_tcspf": 3.5}  # Table 13
    else:
        raise ValueError(f"Unknown GEMS zone: {gems_zone}")


def get_loss_factor(loss_type: HeatingCoolingLossType, duct_age: Optional[int] = None) -> float:
    """Return the system loss factor LS for distribution losses (Table 14).

    duct_age: ductwork age in years (existing homes only). None = new homes (LS = 0.15).
    Age is capped at 30 years per the spec.
    """
    if loss_type == HeatingCoolingLossType.DUCTED:
        if duct_age is None:
            return 0.15                          # Table 14: new homes
        capped_age = min(duct_age, 30)           # Table 14: age capped at 30 years
        return 0.15 + capped_age * 0.0085        # Table 14: existing homes
    elif loss_type == HeatingCoolingLossType.HYDRONIC_PANEL:
        return 0.10                              # Table 14
    elif loss_type == HeatingCoolingLossType.SLAB:
        return 0.15                              # Table 14
    elif loss_type == HeatingCoolingLossType.NON_DUCTED:
        return 0.0                               # non-ducted systems have no distribution losses
    else:
        raise ValueError(f"Unknown loss type: {loss_type}")


def get_hspf_from_star_rating(star_rating: float) -> float:
    """Convert a 2019 GEMS heating star rating to HSPF (Eq 16).

    HSPF: heating seasonal performance factor (W/W) per AS/NZS 3823.4.
    The ZERL label shows zone-specific star ratings (cold/mixed/hot-humid); supply the
    rating for the zone being modelled so the HSPF reflects that zone's seasonal conditions.
    """
    return star_rating + 1.5  # Eq 16


def get_tcspf_from_star_rating(star_rating: float) -> float:
    """Convert a 2019 GEMS cooling star rating to TCSPF (Eq 19).

    TCSPF: total cooling seasonal performance factor (W/W) per AS/NZS 3823.4.
    Supply the zone-specific star rating from the ZERL label (see get_hspf_from_star_rating).
    """
    return star_rating + 1.5  # Eq 19


def get_gas_ducted_cop(ger: float) -> float:
    """Return COP_A for a ducted gas heater from its AGA star rating (Eq 22/23).

    GER: gas energy rating — AGA (Australian Gas Association) star-rating decimal (1.0–6.0).
    Eq 22 applies for 1–3 stars; Eq 23 applies for 3–6 stars.
    """
    if not (1.0 <= ger <= 6.0):
        raise ValueError(f"GER must be 1.0–6.0, got {ger}")
    if ger <= 3.0:
        return 0.4 + 0.1 * ger                       # Eq 22: 1–3 stars
    else:
        return 0.357892 + 0.3114 * math.log(ger)     # Eq 23: 3–6 stars


def get_gas_non_ducted_cop(ger: float) -> float:
    """Return COP_A for a non-ducted gas heater from its AGA star rating (Eq 24).

    GER: gas energy rating — AGA (Australian Gas Association) star-rating decimal (1.0–6.0).
    """
    if not (1.0 <= ger <= 6.0):
        raise ValueError(f"GER must be 1.0–6.0, got {ger}")
    return 0.61 + 0.06 * (ger - 1)   # Eq 24


def _gas_ducted_ancillary_factor(ger: float) -> float:
    """Ancillary electrical load factor for ducted gas fans (Table 15)."""
    return 0.0104 + 0.0044 * ger   # Table 15


def calculate_hourly_energy_demand(
    heating_load: npt.NDArray[float],
    cooling_load: npt.NDArray[float],
    heating_cooling_type: HeatingCoolingType,
    loss_type: HeatingCoolingLossType,
    postcode: Optional[int] = None,
    heating_hspf: Optional[float] = None,
    heating_star_rating: Optional[float] = None,
    cooling_tcspf: Optional[float] = None,
    cooling_star_rating: Optional[float] = None,
    gas_star_rating: Optional[float] = None,
    wood_cop_a: Optional[float] = None,
    duct_age: Optional[int] = None,
) -> Union[npt.NDArray[float], Tuple[npt.NDArray[float], npt.NDArray[float]]]:
    """Calculate hourly energy use for a heating/cooling appliance (Eq 14).

    Takes pre-computed hourly thermal demand arrays (from Chenath simulation,
    blended all-day/work-day per Eq 3) and returns electricity and/or fuel use.

    Parameters
    ----------
    heating_load : array of 8760 floats, MJ/hour of heating thermal demand
    cooling_load : array of 8760 floats, MJ/hour of cooling thermal demand
    heating_cooling_type : appliance type
    loss_type : distribution loss type (ductwork, hydronic, etc.)
    postcode : required for HEAT_PUMP/AC when no explicit HSPF/TCSPF is given
    heating_hspf : HSPF for heat pump heating (overrides star rating)
    heating_star_rating : 2019 GEMS heating star rating (used if hspf not given)
    cooling_tcspf : TCSPF for heat pump/AC cooling (overrides star rating)
    cooling_star_rating : 2019 GEMS cooling star rating (used if tcspf not given)
    gas_star_rating : AGA GER for gas heaters (1.0–6.0); defaults to 3.0 if not given
    wood_cop_a : override COP_A for wood heater (0–1); defaults to 0.60
    duct_age : ductwork age in years for existing homes (only used with DUCTED loss type)

    Returns
    -------
    For electric types (HEAT_PUMP, AC, ELECTRIC_RESISTANCE, EVAPORATIVE, HYDRONIC_*_PUMP_*,
    HYDRONIC_ELECTRIC): single array of electricity consumption (MJ/hour, 8760 elements).

    For gas types (GAS_DUCTED, GAS_NON_DUCTED, HYDRONIC_GAS):
    tuple of (gas_energy, ancillary_electricity), each 8760-element array (MJ/hour).

    For WOOD: tuple of (wood_energy, ancillary_electricity), each 8760 elements (MJ/hour).
    """
    heating_load = np.asarray(heating_load, dtype=float)
    cooling_load = np.asarray(cooling_load, dtype=float)
    assert len(heating_load) == 8760, "heating_load must be 8760 elements"
    assert len(cooling_load) == 8760, "cooling_load must be 8760 elements"

    ls = get_loss_factor(loss_type, duct_age)

    t = heating_cooling_type

    # --- Determine COP_A and compute primary energy ---

    if t in (HeatingCoolingType.HEAT_PUMP, HeatingCoolingType.AC):
        # HSPF: heating seasonal performance factor — seasonal heating efficiency (W/W).
        # TCSPF: total cooling seasonal performance factor — seasonal cooling efficiency (W/W).
        hspf, tcspf = _resolve_heat_pump_efficiencies(
            t, postcode, heating_hspf, heating_star_rating, cooling_tcspf, cooling_star_rating
        )
        heating_energy = heating_load / ((1.0 - ls) * hspf) if hspf else np.zeros(8760)  # Eq 14
        cooling_energy = cooling_load / ((1.0 - ls) * tcspf)                               # Eq 14
        return heating_energy + cooling_energy

    elif t == HeatingCoolingType.GAS_DUCTED:
        ger = _resolve_gas_star_rating(gas_star_rating, "GAS_DUCTED")
        cop_a = get_gas_ducted_cop(ger)
        gas_energy = heating_load / ((1.0 - ls) * cop_a)       # Eq 14
        ancillary_factor = _gas_ducted_ancillary_factor(ger)
        ancillary_elec = gas_energy * ancillary_factor
        return gas_energy, ancillary_elec

    elif t == HeatingCoolingType.GAS_NON_DUCTED:
        ger = _resolve_gas_star_rating(gas_star_rating, "GAS_NON_DUCTED")
        cop_a = get_gas_non_ducted_cop(ger)
        gas_energy = heating_load / ((1.0 - ls) * cop_a)       # Eq 14
        ancillary_factor = _ANCILLARY_FACTORS[t]
        ancillary_elec = gas_energy * ancillary_factor
        return gas_energy, ancillary_elec

    elif t == HeatingCoolingType.WOOD:
        cop_a = wood_cop_a if wood_cop_a is not None else 0.60   # §3.4.5: default 60%
        wood_energy = heating_load / ((1.0 - ls) * cop_a)        # Eq 14
        # Fan-assisted wood heaters: 3% ancillary if ducted, 1% if non-ducted (Table 15)
        anc_factor = 0.03 if loss_type == HeatingCoolingLossType.DUCTED else _ANCILLARY_FACTORS[t]
        ancillary_elec = wood_energy * anc_factor
        return wood_energy, ancillary_elec

    elif t == HeatingCoolingType.HYDRONIC_GAS:
        cop_a = _FIXED_COP_A[t]
        gas_energy = heating_load / ((1.0 - ls) * cop_a)       # Eq 14
        ancillary_elec = gas_energy * _ANCILLARY_FACTORS[t]
        return gas_energy, ancillary_elec

    elif t == HeatingCoolingType.EVAPORATIVE:
        cop_a = _FIXED_COP_A[t]
        return cooling_load / ((1.0 - ls) * cop_a)              # Eq 14

    elif t in _ELECTRIC_TYPES:
        cop_a = _FIXED_COP_A[t]
        electricity = heating_load / ((1.0 - ls) * cop_a)       # Eq 14
        return electricity

    else:
        raise NotImplementedError(f"Unsupported HeatingCoolingType: {t}")


def _resolve_heat_pump_efficiencies(
    t: HeatingCoolingType,
    postcode: Optional[int],
    heating_hspf: Optional[float],
    heating_star_rating: Optional[float],
    cooling_tcspf: Optional[float],
    cooling_star_rating: Optional[float],
) -> Tuple[Optional[float], float]:
    """Resolve HSPF and TCSPF for heat pump and AC types.

    Returns (hspf, tcspf). hspf is None for AC (cooling only).
    """
    # Resolve TCSPF (required for both HEAT_PUMP and AC)
    if cooling_tcspf is not None:
        tcspf = cooling_tcspf
    elif cooling_star_rating is not None:
        tcspf = get_tcspf_from_star_rating(cooling_star_rating)
    else:
        if postcode is None:
            raise ValueError("postcode required when no cooling_tcspf or cooling_star_rating given")
        defaults = get_default_hspf_tcspf(postcode)
        tcspf = defaults["cooling_tcspf"]
        logging.info("Cooling TCSPF not provided; using GEMS zone default %.1f", tcspf)

    if t == HeatingCoolingType.AC:
        return None, tcspf

    # Resolve HSPF (only for HEAT_PUMP)
    if heating_hspf is not None:
        hspf = heating_hspf
    elif heating_star_rating is not None:
        hspf = get_hspf_from_star_rating(heating_star_rating)
    else:
        if postcode is None:
            raise ValueError("postcode required when no heating_hspf or heating_star_rating given")
        defaults = get_default_hspf_tcspf(postcode)
        hspf = defaults["heating_hspf"]
        logging.info("Heating HSPF not provided; using GEMS zone default %.1f", hspf)

    return hspf, tcspf


def _resolve_gas_star_rating(gas_star_rating: Optional[float], type_name: str) -> float:
    """Return gas star rating (GER), defaulting to 3.0 with a warning."""
    if gas_star_rating is not None:
        return gas_star_rating
    logging.warning("%s: gas_star_rating not provided, defaulting to 3 stars", type_name)
    return 3.0
