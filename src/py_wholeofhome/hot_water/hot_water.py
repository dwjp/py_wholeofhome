import numpy as np
import numpy.typing as npt
import pandas as pd
import math
from enum import Enum
from typing import Optional, Tuple, Union
from calendar import monthrange
from pathlib import Path

from ..utilities import calculate_occupants

here = Path(__file__).parent

class HotWaterType(Enum):
    SOLID_FUEL = 0
    ELECTRIC_STORAGE_SMALL = 1
    ELECTRIC_STORAGE_LARGE = 2
    ELECTRIC_INSTANTANEOUS = 3
    GAS_STORAGE = 4
    GAS_INSTANTANEOUS = 5
    SOLAR_ELECTRIC = 6
    SOLAR_GAS = 7
    HEAT_PUMP = 8
    # Auxiliary electrical load for GAS_INSTANTANEOUS... treat as independent HW unit for sake of analysis here,
    # but not intended for use outside this module.
    _GAS_INSTANTANEOUS_AUXILIARY = 9
    # Likewise for gas boosted solar
    _SOLAR_GAS_AUXILIARY = 10


class EnergisationSchedule(Enum):
    DAYTIME = 0             # Run to fixed daytime schedule
    OVERNIGHT = 1           # ... or overnight schedule
    CONTINUOUS = 3      # Or always on, demand depends on hot water usage.


def calculate_winter_peak_demand(occupants: float, climate_zone: int) -> float:
    """
    Per Equation 25 (assumes 40 L hot water delivery per occupant).
    :param occupants:
    :param climate_zone:
    :return: Winter peak water demand in MJ/day (Kwp)
    """

    # Litres of water per MJ for 1MJ peak load
    y = {1: 6.144,
         2: 5.482,
         3: 5.107,
         4: 4.746,
         5: 4.514}

    return 40 * occupants / y[climate_zone]


def calculate_annual_demand(winter_peak_demand: float) -> float:
    """

    :param winter_peak_demand: Winter peak water demand in MJ/day (K wp)
    :return: annual energy output (hot water demand) in GJ/year (E annual-output)
    """

    return winter_peak_demand * 365 * 0.904521 / 1000


def get_hot_water_type_code(hw_type: HotWaterType, climate_zone: int, gas_star_rating=None, stc_count=None) -> str:

    ### Input validation (not comprehensive, but explains basic requirements)

    # Climate zone between 1 and 4 (or 5 for heat pumps)
    if hw_type == HotWaterType.HEAT_PUMP:
        if not (1 <= climate_zone <= 5):
            raise RuntimeError("Invalid climate zone")
    else:
        if not (1 <= climate_zone <= 4):
            raise RuntimeError("Invalid climate zone")

    # Only support star ratings between 4 and 5 for storage, and 4 and 7 for instant gas.
    if hw_type == HotWaterType.GAS_STORAGE:
        if gas_star_rating is None or not (4 <= gas_star_rating <= 5):
            raise RuntimeError("Invalid gas star rating")
    elif hw_type == HotWaterType.GAS_INSTANTANEOUS:
        if gas_star_rating is None or not (4 <= gas_star_rating <= 7):
            raise RuntimeError("Invalid gas star rating")

    # Convert gas star rating to number format, i.e. 4.5 star becomes 45
    # Only allow half star increments
    if gas_star_rating:
        gas_star_rating_code = int(gas_star_rating * 10)
        if gas_star_rating_code % 5 != 0:
            raise RuntimeError("Gas star rating must be in 0.5 star increments")

    # Need STC count for some types
    if stc_count is None and hw_type in [HotWaterType.SOLAR_GAS, HotWaterType.SOLAR_ELECTRIC, HotWaterType.HEAT_PUMP]:
        raise RuntimeError("Missing STC count input.")

    ### Generate code
    if hw_type == HotWaterType.SOLID_FUEL:
        code = f"SOF-{climate_zone}-00"
    elif hw_type == HotWaterType.ELECTRIC_STORAGE_SMALL:
        code = f"ESS-{climate_zone}-00"
    elif hw_type == HotWaterType.ELECTRIC_STORAGE_LARGE:
        code = f"ESL-{climate_zone}-00"
    elif hw_type == HotWaterType.ELECTRIC_INSTANTANEOUS:
        code = f"ESI-{climate_zone}-00"
    elif hw_type == HotWaterType.GAS_STORAGE:
        code = f"GST-{climate_zone}-{gas_star_rating_code}"
    elif hw_type == HotWaterType.GAS_INSTANTANEOUS:
        code = f"GIN-{climate_zone}-{gas_star_rating_code}"
    elif hw_type == HotWaterType.SOLAR_ELECTRIC:
        code = f"STE-{climate_zone}-{stc_count}"
    elif hw_type == HotWaterType.SOLAR_GAS:
        code = f"STG-{climate_zone}-{stc_count}"
    elif hw_type == HotWaterType.HEAT_PUMP:
        code = f"SHP-{climate_zone}-{stc_count}"
    else:
        raise NotImplementedError

    return code


def calculate_annual_purchased_energy(annual_demand: float, hw_type_code: str) -> float:
    """

    :param annual_demand:
    :param hw_type_code:
    :return: Purchased energy in MJ/yr
    """

    coefficient_data = pd.read_csv(here / "reference_data/hw_annual_energy_by_climate_zone_rev10.1.csv", index_col="System ID")

    # Try to look up coefficients. Could fail because it's not listed (invalid code?), or because a handful of entries
    # don't have coefficients (just have string for 'a', 'b', 'c', 'd' instead so cast to float will fail).
    try:
        row = coefficient_data.loc[hw_type_code]
        a, b, c, d = float(row['a']), float(row['b']), float(row['c']), float(row['d'])
    except KeyError:
        raise RuntimeError(f"No data available for {hw_type_code}")
    except TypeError:
        raise RuntimeError(f"Missing coefficients for {hw_type_code}")

    return (a * (annual_demand ** 3)) + (b * (annual_demand ** 2)) + (c * annual_demand) + d


def get_climate_zone(postcode: str, hw_type: HotWaterType) -> int:
    """
    Get climate zone for given postcode and hot water type.
    Note these are different to NatHERS climate zones!

    :param postcode: Australian postcode as string.
    :param hw_type:
    :return:
    """

    postcode = int(postcode)
    if not (800 <= postcode <= 7470):
        raise ValueError("Invalid postcode")

    if hw_type == HotWaterType.HEAT_PUMP:
        data = pd.read_csv(here / 'reference_data/hw_heat_pump_climate_zones_rev10.1.csv')
        result = data[(data['from_postcode'] <= postcode) & (data['to_postcode'] >= postcode)]
        assert (len(result) == 1)
        zone = result['zone'].values[0]
        # Heat pump zones are verbose, e.g. HP5-AU for 5 -- strip this out.
        zone = int(zone.replace("HP", "").replace("-AU", ""))

    else:
        data = pd.read_csv(here / 'reference_data/hw_climate_zones_rev10.1.csv')
        result = data[(data['from_postcode'] <= postcode) & (data['to_postcode'] >= postcode)]
        assert (len(result) == 1)
        zone = int(result['zone'].values[0])

    return zone


def calculate_monthly_share(hw_type_code: str, annual_demand: float) -> [float]:
    """

    :param hw_type_code: Code describing hot water type, climate zone, and performance per standard, e.g. SHP-4-30
    :param annual_demand: Annual hot water demand. Only used for solar thermal systems (i.e. coefficiencts a/b/c zero
    for other types of hot water system).
    :return: Array with monthly share of HW demand with length of 12.
    """

    coefficient_data = pd.read_csv(here / "reference_data/hw_monthly_share_rev10.1.csv",
                                   index_col="System ID")

    # Just grab type and climate zone, e.g. "SHP-4" for "SHP-4-30"
    hw_type_code_prefix = hw_type_code[0:5]

    months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

    monthly_shares = []

    # No checking that type code and coefficients exist... assume we've already run calculate_annual_purchased_energy
    # which makes sure hw_type_code is valid.
    for month in months:
        hw_type_code_for_month = hw_type_code_prefix + f'-{month}'
        row = coefficient_data.loc[hw_type_code_for_month]
        a, b, c, d = float(row['a-month']), float(row['b-month']), float(row['c-month']), float(row['d-month'])
        monthly_shares.append((a * (annual_demand ** 3)) + (b * (annual_demand ** 2)) + (c * annual_demand) + d)

    # Shares should add up to be close to 1 (within 0.5%, given limited precision in reference data tables)
    # Except for solar thermal gas, where there are separate shares for electricity/gas contribution
    if hw_type_code_prefix[0:3] not in ['STX', 'STG']:
        assert math.isclose(sum(monthly_shares), 1.0, abs_tol=0.005)

    return monthly_shares


def calculate_hourly_performance_by_coefficients(hw_type: HotWaterType, annual_demand: float) -> npt.NDArray[float]:
    """
    For hot water heaters where energy demand isn't directly coupled to usage, apply a set of four
    three order polynomials to represent share of energy usage throughout the day.

    :param hw_type:
    :param annual_demand:
    :return:
    """

    def extract_coefficients(df, system_id):
        row = df.loc[system_id]
        a, b, c, d = row['ax'], row['bx'], row['cx'], row['dx']
        return a, b, c, d

    hourly_coefficients = pd.read_csv(here / "reference_data/hw_hourly_coefficients_rev10.1.csv",
                                      index_col="System ID")

    # Get abbreviations used to describe HW type in data table
    if hw_type == HotWaterType.ELECTRIC_STORAGE_SMALL:
        row_code = 'ESS'
    elif hw_type == HotWaterType.GAS_STORAGE:
        row_code = 'GST'
    elif hw_type == HotWaterType._GAS_INSTANTANEOUS_AUXILIARY:
        row_code = 'GIN'
    elif hw_type == HotWaterType.HEAT_PUMP:
        row_code = 'SHP'
    else:
        raise NotImplementedError

    # Look up coefficients from table
    A_a, A_b, A_c, A_d = extract_coefficients(hourly_coefficients, f'{row_code}-A')
    B_a, B_b, B_c, B_d = extract_coefficients(hourly_coefficients, f'{row_code}-B')
    C_a, C_b, C_c, C_d = extract_coefficients(hourly_coefficients, f'{row_code}-C')
    D_a, D_b, D_c, D_d = extract_coefficients(hourly_coefficients, f'{row_code}-D')

    # Apply equation 31 to 34 from methods paper
    component_A = (A_a * (annual_demand ** 3)) + (A_b * (annual_demand ** 2)) + (A_c * annual_demand) + A_d
    component_B = (B_a * (annual_demand ** 3)) + (B_b * (annual_demand ** 2)) + (B_c * annual_demand) + B_d
    component_C = (C_a * (annual_demand ** 3)) + (C_b * (annual_demand ** 2)) + (C_c * annual_demand) + C_d
    component_D = (D_a * (annual_demand ** 3)) + (D_b * (annual_demand ** 2)) + (D_c * annual_demand) + D_d

    # Hours of day for which each component applies (note that 1 = midnight)
    hours_A = [1, 2, 3, 4, 5, 6, 7, 10, 11, 13, 15, 20, 21, 22, 23, 24]
    hours_B = [12, 14]
    hours_C = [16, 17, 18, 19]
    hours_D = [8, 9]
    assert len(hours_A + hours_B + hours_C + hours_D) == 24

    # Assign components to each hour
    hourly_share = []
    for hour in range(1, 25):
        if hour in hours_A:
            hourly_share.append(component_A)
        elif hour in hours_B:
            hourly_share.append(component_B)
        elif hour in hours_C:
            hourly_share.append(component_C)
        elif hour in hours_D:
            hourly_share.append(component_D)
        else:
            raise AssertionError

    # Should add up to 1...
    # FIXME: Seem to need a bit of wiggle room due to lack of precision in table? Get original spreadsheet instead
    assert math.isclose(sum(hourly_share), 1.0, abs_tol=0.007)

    return np.array(hourly_share)


def calculate_hourly_share(hw_type: HotWaterType,
                           annual_demand: float,
                           energisation_schedule :Optional[EnergisationSchedule]=None) -> npt.NDArray[float]:
    """
    Calculate what fraction of purchased energy is consumed by hour, over 24 hours.

    :param hw_type: Hot water type
    :param annual_demand: Annual hw demand. Not needed for all HW types.
    :param energisation_schedule: Whether HW is continuously powered, or on schedule (not relevant for some HW types)
    :return: Hourly share of purchased energy (24 points, summing to 1.00)
    """

    # N.B. 'Nominal hour number' starts at 1 rather than 0
    hourly_share_data = pd.read_csv(here / "reference_data/hw_hourly_profiles_rev10.1.csv",
                                    index_col="Nominal hour number")

    # Check energisation setting is valid for given hw type
    if hw_type == HotWaterType.SOLID_FUEL:
        # Standard unsure about this one, defaults to continuous...
        energisation_schedule = EnergisationSchedule.CONTINUOUS
    elif hw_type == HotWaterType.ELECTRIC_STORAGE_SMALL:
        # Leave energisation_schedule as is... default to always on, but can run scheduled as well.
        pass
    elif hw_type == HotWaterType.ELECTRIC_STORAGE_LARGE:
        # Don't have method for continuous (load dependent) for large electric storage.
        if energisation_schedule == EnergisationSchedule.CONTINUOUS:
            raise RuntimeError("ELECTRIC_STORAGE_LARGE needs to be run either daytime or overnight, not continuous.")
    elif hw_type == HotWaterType.ELECTRIC_INSTANTANEOUS:
        if energisation_schedule != EnergisationSchedule.CONTINUOUS:
            raise RuntimeError("ELECTRIC_INSTANTANEOUS must run continuously.")
    elif hw_type == HotWaterType.GAS_STORAGE:
        if energisation_schedule != EnergisationSchedule.CONTINUOUS:
            raise RuntimeError("GAS_STORAGE must run continuously. .")
    elif hw_type == HotWaterType.GAS_INSTANTANEOUS:
        if energisation_schedule != EnergisationSchedule.CONTINUOUS:
            raise RuntimeError("GAS_INSTANTANEOUS must run continuously. .")
    elif hw_type == HotWaterType.SOLAR_ELECTRIC:
        # Leave energisation_schedule as is... default to always on, but can run scheduled as well.
        pass
    elif hw_type == HotWaterType.SOLAR_GAS:
        if energisation_schedule != EnergisationSchedule.CONTINUOUS:
            raise RuntimeError("SOLAR_GAS must run continuously. .")
    elif hw_type == HotWaterType.HEAT_PUMP:
        # Leave energisation_schedule as is... default to always on, but can run scheduled as well.
        pass
    elif hw_type == HotWaterType._SOLAR_GAS_AUXILIARY:
        # Doesn't matter for aux load, ignore
        pass
    else:
        raise NotImplementedError

    if hw_type == HotWaterType._SOLAR_GAS_AUXILIARY:
        # Special case for gas boosted solar auxiliary load, we're not looking at gas demand, just electricity for pump
        # and a little bit of idle load.
        hourly_share = hourly_share_data['Share auxiliary electricity energy for solar thermal gas systems'].values
    else:
        # Get hourly shares, based on fixed energisation schedule where relevant, coupled directly to HW demand, or based
        # on more complex empirical model for storage systems.
        if energisation_schedule == EnergisationSchedule.DAYTIME:
            hourly_share = hourly_share_data['Daytime energisation by hour (share)'].values
        elif energisation_schedule == EnergisationSchedule.OVERNIGHT:
            hourly_share = hourly_share_data['Overnight energisation by hour (share)'].values
        elif energisation_schedule == EnergisationSchedule.CONTINUOUS:
            if hw_type in [HotWaterType.SOLID_FUEL, HotWaterType.ELECTRIC_INSTANTANEOUS, HotWaterType.GAS_INSTANTANEOUS,
                           HotWaterType.SOLAR_GAS, HotWaterType.SOLAR_ELECTRIC]:
                hourly_share = hourly_share_data['Time of Hot Water use by hour (share)'].values
            elif hw_type in [HotWaterType.ELECTRIC_STORAGE_SMALL,
                             HotWaterType.GAS_STORAGE,
                             HotWaterType.HEAT_PUMP,
                             HotWaterType._GAS_INSTANTANEOUS_AUXILIARY]:
                # Hourly share depends on more complex model, not just driven by hot water demand or fixed schedule.
                hourly_share = calculate_hourly_performance_by_coefficients(hw_type, annual_demand)
            else:
                raise NotImplementedError
        else:
            raise NotImplementedError

    return hourly_share

def calculate_hourly_energy_demand(dwelling_area: float,
                                   postcode: str,
                                   hw_type: HotWaterType,
                                   stc_count: Optional[int] = None,
                                   gas_star_rating: Optional[float] = None,
                                   energisation_schedule: Optional[EnergisationSchedule] = EnergisationSchedule.CONTINUOUS,
                                   include_aux_electric_load=False) -> Union[npt.NDArray[float],  Tuple[npt.NDArray[float], npt.NDArray[float]]]:
    """

    :param dwelling_area:
    :param postcode:
    :param hw_type:
    :param stc_count:
    :param gas_star_rating:
    :param energisation_schedule:
    :param include_aux_electric_load: Whether to return
    :return:
    """

    occupants = calculate_occupants(dwelling_area)

    climate_zone = get_climate_zone(postcode, hw_type)

    annual_demand = calculate_annual_demand(calculate_winter_peak_demand(occupants, climate_zone))

    hw_type_code = get_hot_water_type_code(hw_type, climate_zone, gas_star_rating=gas_star_rating, stc_count=stc_count)

    annual_purchased_energy = calculate_annual_purchased_energy(annual_demand, hw_type_code)

    monthly_share = calculate_monthly_share(hw_type_code, annual_demand)

    hourly_share = calculate_hourly_share(hw_type, annual_demand,
                                          energisation_schedule=energisation_schedule)

    hourly_purchased_energy = np.array([])

    if hw_type == HotWaterType.SOLAR_GAS:
        aux_monthly_share = calculate_monthly_share(f"STX-{climate_zone}", annual_demand)
        aux_hourly_share = calculate_hourly_share(HotWaterType._SOLAR_GAS_AUXILIARY, 0)
        aux_hourly_purchased_energy = np.array([])

    for month_index in range(12):
        _, month_length = monthrange(2022, month_index + 1)

        month_purchased_energy = monthly_share[month_index] * annual_purchased_energy
        day_purchased_energy = month_purchased_energy / month_length

        hourly_purchased_energy_for_month = np.tile(hourly_share * day_purchased_energy, month_length)
        hourly_purchased_energy = np.concatenate((hourly_purchased_energy, hourly_purchased_energy_for_month))

        if hw_type == HotWaterType.SOLAR_GAS:
            aux_month_purchased_energy = aux_monthly_share[month_index] * annual_purchased_energy
            aux_day_purchased_energy = aux_month_purchased_energy / month_length

            aux_hourly_purchased_energy_for_month = np.tile(aux_hourly_share * aux_day_purchased_energy, month_length)
            aux_hourly_purchased_energy = np.concatenate((aux_hourly_purchased_energy, aux_hourly_purchased_energy_for_month))

    if hw_type == HotWaterType.SOLAR_GAS:
        # Have to check sum of gas and electricity demand matches annual total, not just gas.
        assert math.isclose(sum(hourly_purchased_energy) + sum(aux_hourly_purchased_energy), annual_purchased_energy, rel_tol=0.005)
    else:
        # Allow 0.5% tolerance... data table precision is imperfect.
        assert math.isclose(sum(hourly_purchased_energy), annual_purchased_energy, rel_tol=0.007)

    if include_aux_electric_load:
        return hourly_purchased_energy, aux_hourly_purchased_energy
    else:
        return hourly_purchased_energy
