import math
import numpy as np

def calculate_occupants(dwelling_area: float) -> float:
    """
    Calculate number of occupants, per Equation 2.

    :param dwelling_area: Floor area of all zones, excluding garage.
    :return: Number of occupants, rounded to 2nd decimal place (bizarre!)
    """

    occupants = 1.525 * np.log(dwelling_area) - 4.533

    return np.round(np.clip(occupants, 1, 6), decimals=2)

