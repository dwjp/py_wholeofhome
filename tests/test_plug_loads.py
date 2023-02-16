import unittest

from py_wholeofhome.plug_loads import calculate_annual_load, calculate_hourly_energy_demand


class PlugLoadsTest(unittest.TestCase):
    def test_annual_load(self):
        occupants = 3
        annual_load = calculate_annual_load(occupants)
        self.assertAlmostEqual(annual_load, 8353, delta=6)

    def test_hourly(self):
        occupants = 3
        hourly = calculate_hourly_energy_demand(occupants)
        self.assertAlmostEqual(sum(hourly), 8353, delta=6)
