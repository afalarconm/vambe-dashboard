import csv
import unittest
from pathlib import Path

from scripts.bake_db import CSV_PATH, stable_id
from scripts.labeling.openrouter_client import SYSTEM_PROMPT, normalize, validate
from scripts.labeling.taxonomy import ALL, VOLUME_BAND, volume_band

VALID = {
    "primary_job": "scheduling_booking",
    "handoff_topology": "bot_only_implied",
    "system_gravity": "standalone_ok",
    "trust_surface": "standard",
    "buying_trigger": "ops_saturation",
    "volume_period": "monthly",
    "volume_amount": 50,
}


class StableIdTest(unittest.TestCase):
    """Labels are keyed on this id, so it must depend on content and nothing else."""

    def test_is_deterministic(self):
        self.assertEqual(
            stable_id("a@b.c", "569", "2024-01-01"),
            stable_id("a@b.c", "569", "2024-01-01"),
        )

    def test_any_field_change_moves_the_id(self):
        base = stable_id("a@b.c", "569", "2024-01-01")
        self.assertNotEqual(base, stable_id("x@b.c", "569", "2024-01-01"))
        self.assertNotEqual(base, stable_id("a@b.c", "570", "2024-01-01"))
        self.assertNotEqual(base, stable_id("a@b.c", "569", "2024-01-02"))

    def test_fits_sqlite_signed_integer_primary_key(self):
        self.assertLess(stable_id("a@b.c", "569", "2024-01-01"), 2**63)

    @unittest.skipUnless(CSV_PATH.exists(), "dataset not present")
    def test_no_collisions_across_the_real_dataset(self):
        # ARCHITECTURE.md claims zero collisions over the 10k rows; this is that check.
        with open(CSV_PATH, encoding="utf-8-sig") as f:
            ids = [
                stable_id(r["Correo Electronico"], r["Numero de Telefono"],
                          r["Fecha de la Reunion"])
                for r in csv.DictReader(f)
            ]
        self.assertEqual(len(ids), len(set(ids)))


class ValidateTest(unittest.TestCase):
    """A label that fails validation is discarded, so this guard is the only gate."""

    def test_accepts_a_fully_valid_label(self):
        self.assertTrue(validate(VALID))

    def test_rejects_a_value_outside_the_enum(self):
        self.assertFalse(validate({**VALID, "primary_job": "something_invented"}))

    def test_rejects_a_missing_dimension(self):
        partial = {k: v for k, v in VALID.items() if k != "volume_period"}
        self.assertFalse(validate(partial))

    def test_rejects_empty_and_null_values(self):
        self.assertFalse(validate({}))
        self.assertFalse(validate({**VALID, "trust_surface": None}))

    def test_a_null_volume_is_allowed_but_a_nonsense_one_is_not(self):
        self.assertTrue(validate({**VALID, "volume_amount": None}))
        self.assertFalse(validate({**VALID, "volume_amount": -1}))
        self.assertFalse(validate({**VALID, "volume_amount": 10 ** 9}))
        self.assertFalse(validate({**VALID, "volume_amount": "300"}))  # normalize() runs first

    def test_every_taxonomy_value_is_accepted(self):
        for dimension, values in ALL.items():
            for value in values:
                self.assertTrue(validate({**VALID, dimension: value}), f"{dimension}={value}")


class VolumeBandTest(unittest.TestCase):
    """The model reports a number and a unit; the arithmetic lives here.

    Gemma bucketed "300 consultas diarias" as 100_499_mo — it read the number and
    skipped the x30. Measured against the transcripts its agreement fell from
    72.8% on monthly figures to 25.6% on daily ones, so the conversion moved here.
    """

    def test_converts_the_period_before_bucketing(self):
        self.assertEqual(volume_band(300, "daily"), "2000_plus_mo")     # 9000/mo
        self.assertEqual(volume_band(180, "weekly"), "500_1999_mo")     # ~779/mo
        self.assertEqual(volume_band(200, "monthly"), "100_499_mo")
        self.assertEqual(volume_band(400, "yearly"), "lt_100_mo")       # ~33/mo

    def test_the_same_number_bands_differently_per_unit(self):
        self.assertEqual(volume_band(100, "yearly"), "lt_100_mo")
        self.assertEqual(volume_band(100, "monthly"), "100_499_mo")
        self.assertEqual(volume_band(100, "weekly"), "100_499_mo")
        self.assertEqual(volume_band(100, "daily"), "2000_plus_mo")

    def test_boundaries_land_in_the_higher_band(self):
        self.assertEqual(volume_band(99, "monthly"), "lt_100_mo")
        self.assertEqual(volume_band(100, "monthly"), "100_499_mo")
        self.assertEqual(volume_band(499, "monthly"), "100_499_mo")
        self.assertEqual(volume_band(500, "monthly"), "500_1999_mo")
        self.assertEqual(volume_band(2000, "monthly"), "2000_plus_mo")

    def test_missing_or_nonsense_input_is_unspecified(self):
        for amount, period in [(None, "monthly"), (0, "daily"), (-5, "daily"),
                               (100, "unspecified"), (100, None), (100, "fortnightly")]:
            self.assertEqual(volume_band(amount, period), "unspecified", f"{amount}/{period}")

    def test_every_band_returned_is_in_the_published_vocabulary(self):
        for amount in (1, 99, 100, 499, 500, 1999, 2000, 50000):
            for period in ALL["volume_period"]:
                self.assertIn(volume_band(amount, period), VOLUME_BAND)


class NormalizeTest(unittest.TestCase):
    """Models reach for several shapes around a number; coerce rather than discard."""

    def test_coerces_the_shapes_models_actually_return(self):
        for raw, want in [("300", 300), ("1.500", 1500), ("1,200", 1200),
                          (300.0, 300), (300, 300), ("", None), ("muchos", None),
                          (None, None), (True, None)]:
            self.assertEqual(normalize({"volume_amount": raw})["volume_amount"], want, repr(raw))


class PromptTest(unittest.TestCase):
    def test_prompt_lists_every_taxonomy_value(self):
        # The prompt is generated from the taxonomy; adding a value must not need an edit here.
        for values in ALL.values():
            for value in values:
                self.assertIn(value, SYSTEM_PROMPT)

    def test_prompt_forbids_unit_conversion(self):
        # The whole point of the v2 schema: the model must not do the arithmetic.
        self.assertIn("Do not convert", SYSTEM_PROMPT)
        self.assertIn("volume_amount", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
