import math
import numpy as np
import numpy.typing as npt
import pandas as pd
from calendar import monthrange


def calculate_occupants(dwelling_area: float) -> float:
    """
    Calculate number of occupants, per Equation 2.

    :param dwelling_area: Floor area of all zones, excluding garage.
    :return: Number of occupants, rounded to 2nd decimal place (bizarre!)
    """

    occupants = 1.525 * np.log(dwelling_area) - 4.533

    return np.round(np.clip(occupants, 1, 6), decimals=2)


def get_hourly_shares(reference_file: str) -> npt.NDArray[float]:
    """
    Get hour-by-hour share of annual load for a whole year (8760 points)
    :param reference_file: Filename of CSV containing hourly factors (one of cooking_hourly_share_rev10.1.csv or plug_load_hourly_share_rev10.1.csv)
    :return:
    """

    hourly_shares_by_month = pd.read_csv(reference_file)
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

    return annual_shares


def get_nathers_zone(postcode: int) -> int:
    nathers_zone_data = pd.read_csv('utilities/reference_data/NatHERSclimatezonesNov2019_0.csv',
                                    index_col='Postcode')
    return nathers_zone_data.loc[postcode]['Primary']




