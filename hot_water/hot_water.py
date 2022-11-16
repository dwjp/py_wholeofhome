import numpy as np
import numpy.typing as npt
import pandas as pd
import math
from enum import Enum
from typing import Optional

from utilities import calculate_occupants

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


def calculate_winter_peak_demand(occupants: float, climate_zone: int) -> float:
    """
    Per Equation 25 (assumes 40 L hot water delivery per occupant).
    :param occupants:
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
    :return:
    """

    coefficient_data = pd.read_csv("hot_water/reference_data/hw_annual_energy_by_climate_zone_rev10.1.csv", index_col="System ID")

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
    Get climate zone for given postcode and hot water type. Note these are different to NatHERS climate zones!

    :param postcode: Australian postcode as string.
    :param hw_type:
    :return:
    """

    postcode = int(postcode)
    if not (800 <= postcode <= 7470):
        raise ValueError("Invalid postcode")

    if hw_type == HotWaterType.HEAT_PUMP:
        data = pd.read_csv('hot_water/reference_data/hw_heat_pump_climate_zones_rev10.1.csv')
        result = data[(data['from_postcode'] <= postcode) & (data['to_postcode'] >= postcode)]
        assert (len(result) == 1)
        zone = result['zone'].values[0]
        # Heat pump zones are verbose, e.g. HP5-AU for 5 -- strip this out.
        zone = int(zone.replace("HP", "").replace("-AU", ""))

    else:
        data = pd.read_csv('hot_water/reference_data/hw_climate_zones_rev10.1.csv')
        result = data[(data['from_postcode'] <= postcode) & (data['to_postcode'] >= postcode)]
        assert (len(result) == 1)
        zone = int(result['zone'].values[0])

    return zone


def calculate_hourly_energy_demand(dwelling_area: float,
                                   postcode: str,
                                   hw_type: HotWaterType,
                                   stc_count: Optional[int] = None,
                                   gas_star_rating: Optional[float] = None,) -> npt.NDArray[float]:

    occupants = calculate_occupants(dwelling_area)

    climate_zone = get_climate_zone(postcode, hw_type)

    annual_demand = calculate_annual_demand(calculate_winter_peak_demand(occupants, climate_zone))

    hw_type_code = get_hot_water_type_code(hw_type, climate_zone, gas_star_rating=gas_star_rating, stc_count=stc_count)

    annual_purchased_energy = calculate_annual_purchased_energy(annual_demand, hw_type_code)

    return annual_purchased_energy