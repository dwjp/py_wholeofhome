import pandas as pd
import numpy as np
import math
from enum import Enum
from pathlib import Path

from ..utilities import get_hourly_shares, calculate_occupants


here = Path(__file__).parent


class CooktopType(Enum):
    GAS = 0
    ELECTRIC = 1
    INDUCTION = 2


class OvenType(Enum):
    GAS = 0
    ELECTRIC = 1


def calculate_cooktop_annual_load(occupants: float, cooktop_type: CooktopType) -> float:
    """

    :param occupants: Number of occupants per equation 2 (i.e. can be fractional!)
    :param cooktop_type: Cooktop type
    :return: Plug load in MJ/yr
    """


    coefficients = pd.read_csv(here / "reference_data/cooking_coefficients_rev10.1.csv", index_col="variable")

    if cooktop_type == CooktopType.GAS:
        f = coefficients['gas cooktop'].loc['factor']
        c = coefficients['gas cooktop'].loc['constant']
    elif cooktop_type == CooktopType.ELECTRIC:
        f = coefficients['electric cooktop'].loc['factor']
        c = coefficients['electric cooktop'].loc['constant']
    elif cooktop_type == CooktopType.INDUCTION:
        f = coefficients['induction cooktop'].loc['factor']
        c = coefficients['induction cooktop'].loc['constant']
    else:
        raise NotImplementedError

    return c + (occupants * f)


def calculate_oven_annual_load(occupants: float, oven_type: OvenType) -> float:
    """

    :param occupants: Number of occupants per equation 2 (i.e. can be fractional!)
    :param oven_type: Oven type
    :return: Plug load in MJ/yr
    """

    coefficients = pd.read_csv(here / "reference_data/cooking_coefficients_rev10.1.csv", index_col="variable")

    if oven_type == OvenType.GAS:
        f = coefficients['gas oven'].loc['factor']
        c = coefficients['gas oven'].loc['constant']
    elif oven_type == OvenType.ELECTRIC:
        f = coefficients['electric oven'].loc['factor']
        c = coefficients['electric oven'].loc['constant']
    else:
        raise NotImplementedError

    return c + (occupants * f)


def calculate_hourly_energy_demand(dwelling_area: float, cooktop_type: CooktopType, oven_type: OvenType) -> ([float], [float]):

    occupants = calculate_occupants(dwelling_area)
    annual_cooktop_load = calculate_cooktop_annual_load(occupants, cooktop_type)
    annual_oven_load = calculate_oven_annual_load(occupants, oven_type)
    hourly_shares = get_hourly_shares(here / 'reference_data/cooking_hourly_share_rev10.1.csv')

    hourly_cooktop_annual_load = hourly_shares * annual_cooktop_load / 100
    hourly_oven_annual_load = hourly_shares * annual_oven_load / 100

    return hourly_cooktop_annual_load, hourly_oven_annual_load
