"""Reading a MeterValues sample set.

Voltality reported that a session's kWh stayed at zero while charging and only
appeared at the end. The cause was here: their charger sends the shortest legal
form of a sample, and we discarded it.

The parser had never been tested because it was inline in a handler that needs
a database session and a live websocket, so these go against the payloads real
chargers actually send.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from ocpp_server import parse_sampled_values  # noqa: E402


class SampledValueTests(unittest.TestCase):
    def test_a_bare_value_is_energy_in_watt_hours(self):
        # Exactly what VOLTALITYTEST1 sends: no measurand, no unit. OCPP 1.6
        # defines the default measurand as Energy.Active.Import.Register and
        # the default unit as Wh.
        _, _, _, kwh, _ = parse_sampled_values([{"value": "431"}])
        self.assertAlmostEqual(kwh, 0.431)

    def test_the_whole_of_session_449s_stream_is_read(self):
        # The readings we stored as NULL, in order. The last one has to match
        # the 0.349 kWh that StopTransaction worked out independently.
        for raw, expected in (("0", 0.0), ("100", 0.1), ("349", 0.349)):
            with self.subTest(raw=raw):
                _, _, _, kwh, _ = parse_sampled_values([{"value": raw}])
                self.assertAlmostEqual(kwh, expected)

    def test_an_explicit_measurand_still_works(self):
        _, _, _, kwh, _ = parse_sampled_values([
            {"value": "12500", "measurand": "Energy.Active.Import.Register",
             "unit": "Wh"},
        ])
        self.assertAlmostEqual(kwh, 12.5)

    def test_kwh_is_not_divided_again(self):
        _, _, _, kwh, _ = parse_sampled_values([
            {"value": "12.5", "measurand": "Energy.Active.Import.Register",
             "unit": "kWh"},
        ])
        self.assertAlmostEqual(kwh, 12.5)

    def test_a_full_sample_set_is_read_whole(self):
        v, a, kw, kwh, soc = parse_sampled_values([
            {"value": "233.1", "measurand": "Voltage"},
            {"value": "31.8", "measurand": "Current.Import"},
            {"value": "7360", "measurand": "Power.Active.Import", "unit": "W"},
            {"value": "5453", "measurand": "Energy.Active.Import.Register"},
            {"value": "64", "measurand": "SoC"},
        ])
        self.assertAlmostEqual(v, 233.1)
        self.assertAlmostEqual(a, 31.8)
        self.assertAlmostEqual(kw, 7.36)
        self.assertAlmostEqual(kwh, 5.453)
        self.assertAlmostEqual(soc, 64)

    def test_power_without_a_unit_is_inferred_from_magnitude(self):
        _, _, kw, _, _ = parse_sampled_values([
            {"value": "30000", "measurand": "Power.Active.Import"}])
        self.assertAlmostEqual(kw, 30.0)
        _, _, kw, _, _ = parse_sampled_values([
            {"value": "7.4", "measurand": "Power.Active.Import"}])
        self.assertAlmostEqual(kw, 7.4)

    def test_an_out_of_range_soc_is_dropped(self):
        # A charger with no vehicle attached sometimes reports a placeholder.
        *_, soc = parse_sampled_values([{"value": "255", "measurand": "SoC"}])
        self.assertIsNone(soc)

    def test_junk_does_not_raise(self):
        self.assertEqual(parse_sampled_values([]), (None, None, None, None, None))
        self.assertEqual(parse_sampled_values(None), (None, None, None, None, None))
        _, _, _, kwh, _ = parse_sampled_values([{"value": "not a number"}])
        self.assertEqual(kwh, 0.0)


if __name__ == "__main__":
    unittest.main()
