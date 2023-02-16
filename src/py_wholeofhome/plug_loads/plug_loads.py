from pathlib import Path

from ..utilities import get_hourly_shares


here = Path(__file__).parent


def calculate_annual_load(occupants: float) -> float:
    """

    :param occupants: Number of occupants per equation 2 (i.e. can be fractional!)
    :return: Plug load in MJ/yr
    """

    return 7022.4 + (occupants * 441.65)


def calculate_hourly_energy_demand(occupants: float) -> [float]:

    annual_load = calculate_annual_load(occupants)
    hourly_shares = get_hourly_shares(here / 'reference_data/plug_load_hourly_share_rev10.1.csv')
    hourly_annual_load = hourly_shares * annual_load / 100

    return hourly_annual_load
