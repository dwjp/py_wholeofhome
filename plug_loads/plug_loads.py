import pandas as pd
import numpy as np
import math
from calendar import monthrange


def calculate_annual_load(occupants: float) -> float:
    """

    :param occupants: Number of occupants per equation 2 (i.e. can be fractional!)
    :return: Plug load in MJ/yr
    """

    return 7022.4 + (occupants * 441.65)


def calculate_hourly_energy_demand(occupants: float) -> [float]:

    annual_load = calculate_annual_load(occupants)

    hourly_shares_by_month = pd.read_csv('plug_loads/reference_data/plug_load_hourly_share_rev10.1.csv')

    annual_shares = np.array([])

    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # Build an array mapping hourly shares for each month to a whole year
    # Probably not super efficient, but can always memoise yearly array later to speed up.
    for month_index, month in enumerate(months):
        _, month_length = monthrange(2022, month_index + 1)

        monthly_shares = np.tile(hourly_shares_by_month[month].values, month_length)
        annual_shares = np.concatenate((annual_shares, monthly_shares))

    assert len(annual_shares) == 8760

    assert math.isclose(sum(annual_shares), 100, abs_tol=0.001)

    hourly_annual_load = annual_shares * annual_load / 100

    return hourly_annual_load
