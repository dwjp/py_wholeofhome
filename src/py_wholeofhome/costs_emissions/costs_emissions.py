"""
NatHERS Whole of Home energy costs and emissions factors (§3.11, Tables 86–89).

WARNING: Energy prices are from ~2022; emission factors from National Greenhouse
Accounts 2019 (via NCC 2022 Whole of Home update). Use these values for NatHERS
accredited pathway compliance only. For other purposes substitute current values
from AEMO, state retailers, or DCCEEW.
"""
from enum import Enum
from typing import Union

import numpy as np
import numpy.typing as npt

_MJ_PER_KWH = 3.6  # unit conversion constant


class State(Enum):
    NSW = "NSW"
    VIC = "VIC"
    QLD = "QLD"
    SA = "SA"
    WA = "WA"
    TAS = "TAS"
    NT = "NT"
    ACT = "ACT"


class FuelType(Enum):
    ELECTRICITY = "electricity"
    NATURAL_GAS = "natural_gas"
    LPG = "lpg"
    WOOD = "wood"


class TariffType(Enum):
    PEAK = "peak"
    SHOULDER = "shoulder"
    OFF_PEAK = "off_peak"
    CONTROLLED = "controlled"


# Table 86: Energy prices — electricity in c/kWh, gas/LPG/wood in c/MJ
_ELECTRICITY_COST = {   # c/kWh
    State.NSW: {TariffType.PEAK: 38.72, TariffType.SHOULDER: 24.89, TariffType.OFF_PEAK: 19.36, TariffType.CONTROLLED: 12.99},
    State.VIC: {TariffType.PEAK: 37.07, TariffType.SHOULDER: 23.83, TariffType.OFF_PEAK: 18.54, TariffType.CONTROLLED: 19.27},
    State.QLD: {TariffType.PEAK: 32.35, TariffType.SHOULDER: 20.80, TariffType.OFF_PEAK: 16.18, TariffType.CONTROLLED: 15.63},
    State.SA:  {TariffType.PEAK: 50.65, TariffType.SHOULDER: 32.56, TariffType.OFF_PEAK: 25.33, TariffType.CONTROLLED: 19.79},
    State.WA:  {TariffType.PEAK: 40.35, TariffType.SHOULDER: 25.94, TariffType.OFF_PEAK: 20.17, TariffType.CONTROLLED: 11.84},
    State.TAS: {TariffType.PEAK: 29.75, TariffType.SHOULDER: 19.13, TariffType.OFF_PEAK: 14.88, TariffType.CONTROLLED: 13.29},
    State.NT:  {TariffType.PEAK: 36.47, TariffType.SHOULDER: 23.45, TariffType.OFF_PEAK: 18.24, TariffType.CONTROLLED: 26.05},
    State.ACT: {TariffType.PEAK: 33.67, TariffType.SHOULDER: 21.65, TariffType.OFF_PEAK: 16.84, TariffType.CONTROLLED: 14.62},
}

_GAS_COST = {   # c/MJ (Table 86)
    State.NSW: 3.38, State.VIC: 2.36, State.QLD: 4.88, State.SA: 4.23,
    State.WA: 4.01,  State.TAS: 3.56, State.NT:  3.56, State.ACT: 3.56,
}

_LPG_COST  = {s: 5.50 for s in State}   # c/MJ (Table 86 — uniform across states)
_WOOD_COST = {s: 1.85 for s in State}   # c/MJ (Table 86 — uniform across states)

# Table 87: Emissions factors — electricity in kg CO2-e/kWh, gas/LPG/wood in kg CO2-e/MJ
# Sourced from National Greenhouse Accounts 2019 via NCC 2022 Whole of Home update.
_ELECTRICITY_EF = {   # kg CO2-e/kWh
    State.NSW: 0.9000, State.VIC: 1.1196, State.QLD: 0.9252, State.SA: 0.5328,
    State.WA:  0.7380, State.TAS: 0.1728, State.NT:  0.7092, State.ACT: 0.1750,
}

_GAS_EF = {   # kg CO2-e/MJ (Table 87)
    State.NSW: 0.06433, State.VIC: 0.05543, State.QLD: 0.06023, State.SA: 0.06193,
    State.WA:  0.05553, State.TAS: 0.06433, State.NT:  0.06433, State.ACT: 0.06433,
}

_LPG_EF  = {s: 0.06420 for s in State}   # kg CO2-e/MJ (Table 87 — uniform)
_WOOD_EF = {s: 0.00500 for s in State}   # kg CO2-e/MJ (Table 87 — near-zero; renewable)

CARBON_PRICE_PER_TONNE = 12.0   # $/tonne CO2-e (Table 87 — uniform across states)

# Table 89: Time-of-use hour designations (hours 1–24, 1-indexed)
_TOU_SCHEDULE = {
    **{h: TariffType.OFF_PEAK for h in range(1, 9)},    # hours 1–8
    **{h: TariffType.PEAK     for h in range(9, 11)},   # hours 9–10
    **{h: TariffType.SHOULDER for h in range(11, 18)},  # hours 11–17
    **{h: TariffType.PEAK     for h in range(18, 22)},  # hours 18–21
    **{h: TariffType.SHOULDER for h in range(22, 24)},  # hours 22–23
    24: TariffType.OFF_PEAK,
}


def get_tariff_type(hour: int) -> TariffType:
    """Return peak/shoulder/off-peak designation for hour 1–24 (Table 89).

    Hour is 1-indexed (1 = midnight–1am, 24 = 11pm–midnight).
    """
    if not (1 <= hour <= 24):
        raise ValueError(f"hour must be 1–24, got {hour}")
    return _TOU_SCHEDULE[hour]


def get_energy_cost(
    fuel: FuelType,
    state: State,
    tariff: TariffType = TariffType.PEAK,
) -> float:
    """Return energy-only cost in c/MJ (Table 86).

    For electricity, converts from c/kWh (native unit in the spec) to c/MJ.
    tariff is only used for electricity; ignored for other fuels.
    """
    if fuel == FuelType.ELECTRICITY:
        return _ELECTRICITY_COST[state][tariff] / _MJ_PER_KWH   # c/kWh → c/MJ
    elif fuel == FuelType.NATURAL_GAS:
        return _GAS_COST[state]
    elif fuel == FuelType.LPG:
        return _LPG_COST[state]
    elif fuel == FuelType.WOOD:
        return _WOOD_COST[state]
    else:
        raise ValueError(f"Unknown fuel type: {fuel}")


def get_emissions_factor(fuel: FuelType, state: State) -> float:
    """Return emissions intensity in kg CO2-e/MJ (Table 87).

    For electricity, converts from kg CO2-e/kWh (native unit in the spec) to kg CO2-e/MJ.
    """
    if fuel == FuelType.ELECTRICITY:
        return _ELECTRICITY_EF[state] / _MJ_PER_KWH   # kg/kWh → kg/MJ
    elif fuel == FuelType.NATURAL_GAS:
        return _GAS_EF[state]
    elif fuel == FuelType.LPG:
        return _LPG_EF[state]
    elif fuel == FuelType.WOOD:
        return _WOOD_EF[state]
    else:
        raise ValueError(f"Unknown fuel type: {fuel}")


def get_societal_cost(
    fuel: FuelType,
    state: State,
    tariff: TariffType = TariffType.PEAK,
) -> float:
    """Return societal cost (energy + carbon) in c/MJ (Table 88).

    Societal cost = energy cost + (carbon price × emissions factor).
    Carbon price is $12/tonne CO2-e (Table 87).
    """
    energy_cost_c_per_mj = get_energy_cost(fuel, state, tariff)
    ef_kg_per_mj = get_emissions_factor(fuel, state)
    carbon_cost_c_per_mj = CARBON_PRICE_PER_TONNE * ef_kg_per_mj / 10   # $/t × kg/MJ ÷ 10 = c/MJ
    return energy_cost_c_per_mj + carbon_cost_c_per_mj


def calculate_annual_cost(
    hourly_mj: npt.NDArray[float],
    fuel: FuelType,
    state: State,
    use_time_of_use: bool = False,
    tariff: TariffType = TariffType.PEAK,
) -> float:
    """Return annual energy cost in AUD.

    hourly_mj: 8760-element array of hourly energy consumption in MJ.
    use_time_of_use: if True, applies Table 89 peak/shoulder/off-peak tariffs hour by hour
        (only meaningful for electricity). If False, uses the single tariff specified.
    """
    hourly_mj = np.asarray(hourly_mj, dtype=float)
    assert len(hourly_mj) == 8760, "hourly_mj must have 8760 elements"

    if use_time_of_use and fuel == FuelType.ELECTRICITY:
        hourly_cost = np.array([
            hourly_mj[i] * get_energy_cost(fuel, state, get_tariff_type(i % 24 + 1))
            for i in range(8760)
        ])
        total_cents = hourly_cost.sum()
    else:
        rate_c_per_mj = get_energy_cost(fuel, state, tariff)
        total_cents = hourly_mj.sum() * rate_c_per_mj

    return total_cents / 100   # cents → AUD


def calculate_annual_emissions(
    hourly_mj: npt.NDArray[float],
    fuel: FuelType,
    state: State,
) -> float:
    """Return annual emissions in kg CO2-e.

    hourly_mj: 8760-element array of hourly energy consumption in MJ.
    """
    hourly_mj = np.asarray(hourly_mj, dtype=float)
    assert len(hourly_mj) == 8760, "hourly_mj must have 8760 elements"
    return float(hourly_mj.sum() * get_emissions_factor(fuel, state))
