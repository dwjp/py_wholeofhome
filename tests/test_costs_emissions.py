import unittest

from py_wholeofhome.costs_emissions import (
    FuelType,
    State,
    TariffType,
    get_emissions_factor,
    get_energy_cost,
    get_societal_cost,
    get_tariff_type,
)


class TariffTypeTest(unittest.TestCase):
    """Table 89 time-of-use designations."""

    def test_off_peak_early_morning(self):
        self.assertEqual(get_tariff_type(5), TariffType.OFF_PEAK)

    def test_peak_morning(self):
        self.assertEqual(get_tariff_type(9), TariffType.PEAK)

    def test_shoulder_midday(self):
        self.assertEqual(get_tariff_type(14), TariffType.SHOULDER)

    def test_peak_evening(self):
        self.assertEqual(get_tariff_type(19), TariffType.PEAK)

    def test_shoulder_late_evening(self):
        self.assertEqual(get_tariff_type(22), TariffType.SHOULDER)

    def test_off_peak_midnight(self):
        self.assertEqual(get_tariff_type(24), TariffType.OFF_PEAK)

    def test_invalid_hour_raises(self):
        with self.assertRaises(ValueError):
            get_tariff_type(0)
        with self.assertRaises(ValueError):
            get_tariff_type(25)

    def test_all_24_hours_covered(self):
        for h in range(1, 25):
            self.assertIsInstance(get_tariff_type(h), TariffType)


class EnergyCostTest(unittest.TestCase):
    """Table 86 spot-checks — native units then converted to c/MJ."""

    def test_electricity_nsw_peak_c_per_mj(self):
        # Table 86: NSW peak = 38.72 c/kWh; 1 kWh = 3.6 MJ → 38.72/3.6 = 10.756 c/MJ
        self.assertAlmostEqual(get_energy_cost(FuelType.ELECTRICITY, State.NSW, TariffType.PEAK),
                               38.72 / 3.6, places=3)

    def test_electricity_tas_peak_c_per_mj(self):
        # Table 86: TAS peak = 29.75 c/kWh
        self.assertAlmostEqual(get_energy_cost(FuelType.ELECTRICITY, State.TAS, TariffType.PEAK),
                               29.75 / 3.6, places=3)

    def test_gas_vic_c_per_mj(self):
        # Table 86: VIC gas = 2.36 c/MJ
        self.assertAlmostEqual(get_energy_cost(FuelType.NATURAL_GAS, State.VIC), 2.36, places=4)

    def test_wood_uniform(self):
        # Table 86: wood = 1.85 c/MJ uniform
        for state in State:
            self.assertAlmostEqual(get_energy_cost(FuelType.WOOD, state), 1.85, places=4)

    def test_lpg_uniform(self):
        # Table 86: LPG = 5.50 c/MJ uniform
        for state in State:
            self.assertAlmostEqual(get_energy_cost(FuelType.LPG, state), 5.50, places=4)


class EmissionsFactorTest(unittest.TestCase):
    """Table 87 spot-checks — converted to kg CO2-e/MJ."""

    def test_electricity_tas_very_low(self):
        # Table 87: TAS = 0.1728 kg/kWh → 0.1728/3.6 = 0.048 kg/MJ (mostly hydro)
        self.assertAlmostEqual(get_emissions_factor(FuelType.ELECTRICITY, State.TAS),
                               0.1728 / 3.6, places=4)

    def test_electricity_vic_high(self):
        # Table 87: VIC = 1.1196 kg/kWh → 1.1196/3.6 = 0.311 kg/MJ (coal-heavy)
        self.assertAlmostEqual(get_emissions_factor(FuelType.ELECTRICITY, State.VIC),
                               1.1196 / 3.6, places=3)

    def test_wood_near_zero(self):
        # Table 87: wood = 0.005 kg CO2-e/MJ (renewable)
        for state in State:
            self.assertAlmostEqual(get_emissions_factor(FuelType.WOOD, state), 0.005, places=4)

    def test_gas_nsw(self):
        # Table 87: NSW gas = 0.06433 kg CO2-e/MJ
        self.assertAlmostEqual(get_emissions_factor(FuelType.NATURAL_GAS, State.NSW),
                               0.06433, places=5)


class SocietalCostTest(unittest.TestCase):
    """Table 88: societal cost = energy cost + carbon cost."""

    def test_nsw_gas_societal(self):
        # Table 88: NSW gas = 3.46 c/MJ
        # Energy: 3.38 c/MJ; Carbon: 12 $/t × 0.06433 kg/MJ / 10 = 0.0772 c/MJ → total ≈ 3.457
        self.assertAlmostEqual(get_societal_cost(FuelType.NATURAL_GAS, State.NSW), 3.46, delta=0.02)

    def test_wood_societal_barely_above_energy(self):
        # Wood carbon cost is tiny: 12 × 0.005 / 10 = 0.006 c/MJ
        sc = get_societal_cost(FuelType.WOOD, State.NSW)
        ec = get_energy_cost(FuelType.WOOD, State.NSW)
        self.assertAlmostEqual(sc - ec, 0.006, places=3)

if __name__ == '__main__':
    unittest.main()
