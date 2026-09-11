import csv
import unittest
from pathlib import Path

from scripts.bake_db import CSV_PATH, stable_id
from scripts.labeling.openrouter_client import SYSTEM_PROMPT, validate
from scripts.labeling.taxonomy import ALL

VALID = {
    "primary_job": "scheduling_booking",
    "handoff_topology": "bot_only_implied",
    "system_gravity": "standalone_ok",
    "trust_surface": "standard",
    "buying_trigger": "ops_saturation",
    "volume_band": "lt_100_mo",
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
        partial = {k: v for k, v in VALID.items() if k != "volume_band"}
        self.assertFalse(validate(partial))

    def test_rejects_empty_and_null_values(self):
        self.assertFalse(validate({}))
        self.assertFalse(validate({**VALID, "trust_surface": None}))

    def test_every_taxonomy_value_is_accepted(self):
        for dimension, values in ALL.items():
            for value in values:
                self.assertTrue(validate({**VALID, dimension: value}), f"{dimension}={value}")


class PromptTest(unittest.TestCase):
    def test_prompt_lists_every_taxonomy_value(self):
        # The prompt is generated from the taxonomy; adding a value must not need an edit here.
        for values in ALL.values():
            for value in values:
                self.assertIn(value, SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
