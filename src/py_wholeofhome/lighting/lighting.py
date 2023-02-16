from pathlib import Path

from ..utilities import get_hourly_shares


here = Path(__file__).parent


def calculate_annual_load(dwelling_area: float) -> float:
    """

    :param dwelling_area:
    :return: Annual lighting demand in MJ
    """

    lighting_density = 5         # Lighting density, W/m^2
    run_time = 1.6   # Average use per day (hours)

    # Equation 63
    return lighting_density * run_time * dwelling_area * 365 * 3.6 / 1000


def calculate_hourly_energy_demand(dwelling_area: float) -> [float]:

    annual_load = calculate_annual_load(dwelling_area)
    hourly_shares = get_hourly_shares(here / 'reference_data/lighting_hourly_share_rev10.1.csv')
    hourly_annual_load = hourly_shares * annual_load / 100

    return hourly_annual_load