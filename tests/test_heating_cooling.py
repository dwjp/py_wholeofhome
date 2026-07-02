import math
import unittest

import numpy as np

from py_wholeofhome.heating_cooling import (
    HeatingCoolingLossType,
    HeatingCoolingType,
    calculate_hourly_energy_demand,
    get_gas_ducted_cop,
    get_gas_non_ducted_cop,
    get_loss_factor,
)


class GasDuctedCopTest(unittest.TestCase):
    """Spot-checks against spec Table 26 (§3.4.3, p40)."""

    def test_1_star(self):
        self.assertAlmostEqual(get_gas_ducted_cop(1.0), 0.50, places=4)

    def test_3_star(self):
        self.assertAlmostEqual(get_gas_ducted_cop(3.0), 0.70, places=4)

    def test_4_star(self):
        # Table 26 says 79.0%; Eq 23: 0.357892 + 0.3114*ln(4)
        self.assertAlmostEqual(get_gas_ducted_cop(4.0), 0.789, delta=0.001)

    def test_5_star(self):
        # Table 26 says 85.9%
        self.assertAlmostEqual(get_gas_ducted_cop(5.0), 0.859, delta=0.001)

    def test_6_star(self):
        # Table 26 says 91.6%
        self.assertAlmostEqual(get_gas_ducted_cop(6.0), 0.916, delta=0.001)

    def test_invalid_ger_raises(self):
        with self.assertRaises(ValueError):
            get_gas_ducted_cop(0.5)
        with self.assertRaises(ValueError):
            get_gas_ducted_cop(7.0)


class GasNonDuctedCopTest(unittest.TestCase):
    """Spot-checks against spec Table 27 (§3.4.4, p41)."""

    def test_1_star(self):
        self.assertAlmostEqual(get_gas_non_ducted_cop(1.0), 0.61, places=4)

    def test_4_star(self):
        self.assertAlmostEqual(get_gas_non_ducted_cop(4.0), 0.79, places=4)

    def test_6_star(self):
        self.assertAlmostEqual(get_gas_non_ducted_cop(6.0), 0.91, places=4)


class LossFactorTest(unittest.TestCase):
    """Tests for get_loss_factor (Table 14)."""

    def test_ducted_new(self):
        self.assertAlmostEqual(get_loss_factor(HeatingCoolingLossType.DUCTED), 0.15)

    def test_ducted_age_20(self):
        # 0.15 + 20 * 0.0085 = 0.32
        self.assertAlmostEqual(get_loss_factor(HeatingCoolingLossType.DUCTED, duct_age=20), 0.32)

    def test_ducted_age_capped_at_30(self):
        # Age 35 is capped at 30: 0.15 + 30 * 0.0085 = 0.405
        ls_35 = get_loss_factor(HeatingCoolingLossType.DUCTED, duct_age=35)
        ls_30 = get_loss_factor(HeatingCoolingLossType.DUCTED, duct_age=30)
        self.assertAlmostEqual(ls_35, ls_30)
        self.assertAlmostEqual(ls_35, 0.405)

    def test_hydronic_panel(self):
        self.assertAlmostEqual(get_loss_factor(HeatingCoolingLossType.HYDRONIC_PANEL), 0.10)

    def test_slab(self):
        self.assertAlmostEqual(get_loss_factor(HeatingCoolingLossType.SLAB), 0.15)

    def test_non_ducted(self):
        self.assertAlmostEqual(get_loss_factor(HeatingCoolingLossType.NON_DUCTED), 0.0)


class HeatPumpTest(unittest.TestCase):
    """Ducted reverse-cycle heat pump — spec Example 3, §3.12.4 (p145).

    3-star (2019 GEMS) ducted reverse-cycle; HSPF = TCSPF = 3 + 1.5 = 4.5 (Eq 16/19);
    15% duct losses (Table 14 new homes). Total thermal load 17,428 MJ/year.
    Expected electricity = 17,428 / ((1 - 0.15) × 4.5) = 4,556 MJ = 1,265 kWh/year.
    """

    TOTAL_LOAD_MJ = 17_428.0
    EXPECTED_ELEC_MJ = TOTAL_LOAD_MJ / ((1 - 0.15) * 4.5)  # ≈ 4,556 MJ

    def setUp(self):
        # Put all thermal demand into heating (simpler; same COP applies to both)
        load_per_hour = self.TOTAL_LOAD_MJ / 8760
        self.heating_load = np.full(8760, load_per_hour)
        self.cooling_load = np.zeros(8760)

    def test_annual_electricity(self):
        elec = calculate_hourly_energy_demand(
            self.heating_load,
            self.cooling_load,
            HeatingCoolingType.HEAT_PUMP,
            HeatingCoolingLossType.DUCTED,
            heating_hspf=4.5,
            cooling_tcspf=4.5,
        )
        self.assertAlmostEqual(sum(elec), self.EXPECTED_ELEC_MJ, delta=5)

    def test_length(self):
        elec = calculate_hourly_energy_demand(
            self.heating_load,
            self.cooling_load,
            HeatingCoolingType.HEAT_PUMP,
            HeatingCoolingLossType.DUCTED,
            heating_hspf=4.5,
            cooling_tcspf=4.5,
        )
        self.assertEqual(len(elec), 8760)

    def test_star_rating_input(self):
        # Star rating path: 3 stars → HSPF/TCSPF = 4.5 (Eq 16/19)
        elec = calculate_hourly_energy_demand(
            self.heating_load,
            self.cooling_load,
            HeatingCoolingType.HEAT_PUMP,
            HeatingCoolingLossType.DUCTED,
            heating_star_rating=3.0,
            cooling_star_rating=3.0,
        )
        self.assertAlmostEqual(sum(elec), self.EXPECTED_ELEC_MJ, delta=5)


class GasDuctedEndToEndTest(unittest.TestCase):
    """Gas ducted heater end-to-end with 5.1-star rating, no duct losses."""

    GER = 5.1
    HEATING_TOTAL_MJ = 10_000.0

    def setUp(self):
        load_per_hour = self.HEATING_TOTAL_MJ / 8760
        self.heating_load = np.full(8760, load_per_hour)
        self.cooling_load = np.zeros(8760)
        self.cop_a = get_gas_ducted_cop(self.GER)
        self.ancillary_factor = 0.0104 + 0.0044 * self.GER

    def test_gas_output(self):
        gas, _ = calculate_hourly_energy_demand(
            self.heating_load,
            self.cooling_load,
            HeatingCoolingType.GAS_DUCTED,
            HeatingCoolingLossType.NON_DUCTED,
            gas_star_rating=self.GER,
        )
        expected_gas = self.HEATING_TOTAL_MJ / self.cop_a
        self.assertAlmostEqual(sum(gas), expected_gas, delta=1)

    def test_ancillary_electricity(self):
        gas, ancillary = calculate_hourly_energy_demand(
            self.heating_load,
            self.cooling_load,
            HeatingCoolingType.GAS_DUCTED,
            HeatingCoolingLossType.NON_DUCTED,
            gas_star_rating=self.GER,
        )
        expected_ancillary = sum(gas) * self.ancillary_factor
        self.assertAlmostEqual(sum(ancillary), expected_ancillary, delta=0.1)

    def test_length(self):
        gas, ancillary = calculate_hourly_energy_demand(
            self.heating_load,
            self.cooling_load,
            HeatingCoolingType.GAS_DUCTED,
            HeatingCoolingLossType.NON_DUCTED,
            gas_star_rating=self.GER,
        )
        self.assertEqual(len(gas), 8760)
        self.assertEqual(len(ancillary), 8760)


class ElectricResistanceTest(unittest.TestCase):
    """Electric resistance heater: COP_A = 1.0, no distribution losses."""

    def test_electricity_equals_thermal_load(self):
        rng = np.random.default_rng(42)
        heating_load = rng.uniform(0, 10, 8760)
        cooling_load = np.zeros(8760)

        elec = calculate_hourly_energy_demand(
            heating_load,
            cooling_load,
            HeatingCoolingType.ELECTRIC_RESISTANCE,
            HeatingCoolingLossType.NON_DUCTED,
        )
        np.testing.assert_allclose(elec, heating_load)


class EvaporativeCoolerTest(unittest.TestCase):
    """Evaporative cooler: COP_A = 15, ancillary already included."""

    def test_cooling_electricity(self):
        heating_load = np.zeros(8760)
        cooling_total = 5_000.0
        cooling_load = np.full(8760, cooling_total / 8760)

        elec = calculate_hourly_energy_demand(
            heating_load,
            cooling_load,
            HeatingCoolingType.EVAPORATIVE,
            HeatingCoolingLossType.NON_DUCTED,
        )
        # COP_A = 15, LS = 0
        self.assertAlmostEqual(sum(elec), cooling_total / 15.0, delta=1)
        self.assertEqual(len(elec), 8760)


class WoodHeaterTest(unittest.TestCase):
    """Wood heater with default COP_A = 0.60."""

    HEATING_TOTAL_MJ = 8_000.0

    def setUp(self):
        self.heating_load = np.full(8760, self.HEATING_TOTAL_MJ / 8760)
        self.cooling_load = np.zeros(8760)

    def test_wood_energy(self):
        wood, _ = calculate_hourly_energy_demand(
            self.heating_load,
            self.cooling_load,
            HeatingCoolingType.WOOD,
            HeatingCoolingLossType.NON_DUCTED,
        )
        self.assertAlmostEqual(sum(wood), self.HEATING_TOTAL_MJ / 0.60, delta=1)

    def test_wood_cop_override(self):
        wood, _ = calculate_hourly_energy_demand(
            self.heating_load,
            self.cooling_load,
            HeatingCoolingType.WOOD,
            HeatingCoolingLossType.NON_DUCTED,
            wood_cop_a=0.75,
        )
        self.assertAlmostEqual(sum(wood), self.HEATING_TOTAL_MJ / 0.75, delta=1)


if __name__ == '__main__':
    unittest.main()
