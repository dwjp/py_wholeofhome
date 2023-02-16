from enum import Enum
from typing import Optional
import logging
import math
import pandas as pd

from utilities import get_nathers_zone

class HeatingCoolingType(Enum):
    AC = 0              # Cooling only
    HEAT_PUMP = 1       # Cooling/heating, i.e. reverse cycle
    GAS = 2
    WOOD = 3
    EVAPORATIVE = 4


class HeatingCoolingLossType(Enum):
    DUCTED_NEW = 0  # < 10 years old
    DUCTED_OLD = 1  # > 10 years old
    HYDRONIC_PANEL = 2
    SLAB = 3
    NON_DUCTED = 4


LOSS_FACTORS = {
    HeatingCoolingLossType.DUCTED_NEW: 0.15,
    HeatingCoolingLossType.DUCTED_OLD: 0.25,
    HeatingCoolingLossType.HYDRONIC_PANEL: 0.1,
    HeatingCoolingLossType.SLAB: 0.15,
    HeatingCoolingLossType.NON_DUCTED: 0.15
}


def get_gems_zone(postcode: int) -> str:
    nathers_zone = get_nathers_zone(postcode)
    gems_zone_data = pd.read_csv('heating_cooling/reference_data/nathers_and_gems_zones_rev10.1.csv',
                                 index_col='NatHERS Climate Zone')
    return gems_zone_data.loc[nathers_zone]['Applicable GEMS ZERL Zone']


def get_default_star_rating(postcode: int):
    # From table 13

    gems_zone = get_gems_zone(postcode)

    if gems_zone == "Hot/humid":
        return {"heating": 4.0, "cooling": 4.0}
    elif gems_zone == "Mixed":
        return {"heating": 3.5, "cooling": 3.5}
    elif gems_zone == "Cold":
        return {"heating": 2.5, "cooling": 3.5}
    else:
        raise AssertionError


def calculate_hourly_energy_demand(postcode,
                                   heating_load,
                                   cooling_load,
                                   heating_cooling_type: HeatingCoolingType,
                                   loss_type,
                                   heating_star_rating:Optional[int]=None,
                                   cooling_star_rating:Optional[int]=None):
    # Get loss factor
    ls = LOSS_FACTORS[loss_type]

    # Get coefficient of performance COP for appliance
    if heating_cooling_type == HeatingCoolingType.GAS:

        if loss_type in [HeatingCoolingLossType.DUCTED_OLD, HeatingCoolingLossType.DUCTED_NEW]:
            if heating_star_rating is None:
                logging.info("Gas star rating not provided, defaulting to 3.")
                star_rating = 3
            if heating_star_rating <= 3:
                # Equation 22
                cop_a = 0.4 + (0.1 * star_rating)
            elif 3 < star_rating <= 6:
                # Equation 23
                cop_a = 0.357892 + (0.3114 * math.log(star_rating))
            else:
                raise NotImplementedError("Invalid gas star rating.")
        else:
            cop_a = 0.61 + (0.06 * (heating_star_rating - 1))

    elif heating_cooling_type == HeatingCoolingType.WOOD:
        # TODO: Optionally allow user efficiency value based on AS/NZS 4012
        cop_a = 0.6

    elif heating_cooling_type == HeatingCoolingType.EVAPORATIVE:
        cop_a = 13

    elif heating_cooling_type == HeatingCoolingType.AC:
        # TODO
        pass

    elif heating_cooling_type == HeatingCoolingType.HEAT_PUMP:
        # TODO
        heat_pump_star_ratings = get_default_star_rating(postcode)
        pass
    else:
        raise NotImplementedError


    if heating_cooling_type == HeatingCoolingType.HEAT_PUMP:
        # Heating and cooling
        pass
    elif heating_cooling_type in [HeatingCoolingType.AC, HeatingCoolingType.EVAPORATIVE]:
        # Cooling only
        pass
    elif heating_cooling_type in [HeatingCoolingType.WOOD, HeatingCoolingType. GAS]:
        # Heating only
        pass
    else:
        raise NotImplementedError