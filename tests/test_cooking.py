import unittest

from py_wholeofhome.cooking import calculate_cooktop_annual_load, calculate_oven_annual_load, \
    calculate_hourly_energy_demand, CooktopType, OvenType


class CooktopTests(unittest.TestCase):
    def test_cooktop_annual_load(self):
        occupants = 3

        annual_load = calculate_cooktop_annual_load(occupants, CooktopType.GAS)
        self.assertAlmostEqual(annual_load, 1600, delta=1)

        annual_load = calculate_cooktop_annual_load(occupants, CooktopType.ELECTRIC)
        self.assertAlmostEqual(annual_load, 1037, delta=1)

        # TODO: This fails, it appears coefficients in the standard are incorrect?
        annual_load = calculate_cooktop_annual_load(occupants, CooktopType.INDUCTION)
        self.assertAlmostEqual(annual_load, 713, delta=1)


class OvenTests(unittest.TestCase):
    def test_oven_annual_load(self):
        occupants = 3

        annual_load = calculate_oven_annual_load(occupants, OvenType.GAS)
        self.assertAlmostEqual(annual_load, 1700, delta=1)

        annual_load = calculate_oven_annual_load(occupants, OvenType.ELECTRIC)
        self.assertAlmostEqual(annual_load, 853, delta=1)


    # def test_hourly(self):
    #     occupants = 2.5
    #     hourly = calculate_hourly_energy_demand(occupants)
    #     self.assertAlmostEqual(sum(hourly), 8126.5, places=1)
