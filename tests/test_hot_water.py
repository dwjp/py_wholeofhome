import unittest

from py_wholeofhome.hot_water import calculate_annual_purchased_energy, calculate_hourly_energy_demand, calculate_annual_demand, \
    HotWaterType, calculate_winter_peak_demand, get_hot_water_type_code


class HotWaterTests(unittest.TestCase):
    def test_example_1_unit(self):
        # From worked example 1, p81 of methods paper.

        dwelling_area = 200
        occupants = 3.55
        climate_zone = 3
        postcode = "2000"
        stc_count = 27
        hw_type = HotWaterType.SOLAR_ELECTRIC

        winter_peak_demand = calculate_winter_peak_demand(occupants, climate_zone)
        self.assertAlmostEqual(winter_peak_demand, 27.805, places=2)

        annual_demand = calculate_annual_demand(winter_peak_demand)
        self.assertAlmostEqual(annual_demand, 9.1782, places=2)

        type_str = get_hot_water_type_code(hw_type, climate_zone, stc_count=stc_count)
        purchased = calculate_annual_purchased_energy(annual_demand, type_str)
        self.assertAlmostEqual(purchased, 3351.996, places=2)

        hourly = calculate_hourly_energy_demand(dwelling_area, postcode, hw_type, stc_count=stc_count)
        self.assertAlmostEqual(sum(hourly), 3351.996, delta=5)  # Some wobble here again due to data tables, out ~0.5%
        self.assertEqual(len(hourly), 8760)

        # TODO: sanity check monthly/hourly

    def test_example_2(self):
        # From worked example 2, same as example 1 but solar gas.

        dwelling_area = 200
        occupants = 3.55
        climate_zone = 3
        postcode = "2000"
        stc_count = 38
        hw_type = HotWaterType.SOLAR_GAS
        annual_demand = 9.1782  # From example 1

        type_str = get_hot_water_type_code(hw_type, climate_zone, stc_count=stc_count)
        purchased = calculate_annual_purchased_energy(annual_demand, type_str)
        self.assertAlmostEqual(purchased, 2989.25, delta=1)  # Some wobble here again due to data tables

        hourly, hourly_aux = calculate_hourly_energy_demand(dwelling_area,
                                                            postcode,
                                                            hw_type,
                                                            stc_count=stc_count,
                                                            include_aux_electric_load=True)

        # Allow slight error original annual demand given data table lack of precision, <0.5%
        # Sum of gas and electricity demand should match annual total.
        self.assertAlmostEqual(sum(hourly) + sum(hourly_aux), 2989.25, delta=10)
        self.assertEqual(len(hourly), 8760)
        self.assertEqual(len(hourly_aux), 8760)

    def test_example_3(self):
        # From worked example 3, same as example 1 but gas instant.

        dwelling_area = 200
        occupants = 3.55
        climate_zone = 3
        postcode = "2000"
        star_rating = 6
        hw_type = HotWaterType.GAS_INSTANTANEOUS
        annual_demand = 9.1782  # From example 1

        type_str = get_hot_water_type_code(hw_type, climate_zone, gas_star_rating=star_rating)
        purchased = calculate_annual_purchased_energy(annual_demand, type_str)
        self.assertAlmostEqual(purchased, 12611.26, delta=3)  # Some wobble here again due to data tables

        hourly = calculate_hourly_energy_demand(dwelling_area, postcode, hw_type, gas_star_rating=star_rating)
        self.assertAlmostEqual(sum(hourly), 12611.26, delta=3)
        self.assertEqual(len(hourly), 8760)

        # FIXME: Handle electricity component

    def test_example_4(self):
        # From worked example 4, same as example 1 but small electric storage

        dwelling_area = 200
        occupants = 3.55
        climate_zone = 3
        postcode = "2000"
        hw_type = HotWaterType.ELECTRIC_STORAGE_SMALL
        annual_demand = 9.1782  # From example 1

        type_str = get_hot_water_type_code(hw_type, climate_zone)
        purchased = calculate_annual_purchased_energy(annual_demand, type_str)
        self.assertAlmostEqual(purchased, 11048.91, delta=3)  # Some wobble here again due to data tables

        hourly = calculate_hourly_energy_demand(dwelling_area, postcode, hw_type)
        self.assertAlmostEqual(sum(hourly), 11048.91, delta=50) # More wobbble...
        self.assertEqual(len(hourly), 8760)

    def test_example_heat_pump(self):
        # No example in methods paper, but base on example 4. Note that annual demand about 1/3 of a
        # resistive hot water heater as expected.

        dwelling_area = 200
        occupants = 3.55
        climate_zone = 3
        postcode = "2000"
        hw_type = HotWaterType.HEAT_PUMP
        annual_demand = 9.1782  # From example 1
        stc_count = 30

        type_str = get_hot_water_type_code(hw_type, climate_zone, stc_count=stc_count)
        purchased = calculate_annual_purchased_energy(annual_demand, type_str)
        self.assertAlmostEqual(purchased, 3317, delta=5)  # Some wobble here again due to data tables

        hourly = calculate_hourly_energy_demand(dwelling_area, postcode, hw_type, stc_count=stc_count)
        self.assertAlmostEqual(sum(hourly), 3317, delta=5)  # More wobbble...
        self.assertEqual(len(hourly), 8760)