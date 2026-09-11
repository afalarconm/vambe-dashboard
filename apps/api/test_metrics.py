import sqlite3
import tempfile
import unittest
from pathlib import Path

from apps.api import main
from apps.api.main import collect_metrics, meeting_clauses, sample_weights
from scripts.bake_db import SCHEMA

# Population: 8 won / 4 lost -> a true win rate of 66.7%.
# Labeled:    2 won / 2 lost -> the labeler's 50/50 draw, whose RAW rate reads 50%.
# Weighting by 8/2 and 4/2 has to put the reported rate back at 66.7%.
MEETINGS = [(i, f"C{i}", "a@b.c", "56900000000", "2024-01-%02d" % i, "Ana" if i % 2 else "Ben",
             1 if i <= 8 else 0, "transcripcion") for i in range(1, 13)]
# Won meetings carry job A, lost ones job B, so the two jobs must land at 100% and 0%.
LABELS = [
    (1, "scheduling_booking"), (2, "scheduling_booking"),
    (9, "order_taking"), (10, "order_taking"),
]


def seed(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.executemany("INSERT INTO meetings VALUES (?,?,?,?,?,?,?,?)", MEETINGS)
    conn.executemany(
        """INSERT INTO categories (meeting_id, primary_job, handoff_topology,
           system_gravity, trust_surface, buying_trigger, volume_band, model, prompt_version)
           VALUES (?,?,'bot_only_implied','standalone_ok','standard','ops_saturation',
                   'lt_100_mo','gemma','llm-v1')""",
        LABELS,
    )
    conn.commit()
    return conn


def by_job(metrics):
    return {row["job"]: row for row in metrics["by_job"]}


class SampleWeightingTest(unittest.TestCase):
    """The labeler samples 50/50 on outcome; unweighted rates are pulled toward 50%."""

    def test_weights_are_population_over_sample(self):
        conn = seed()
        won, lost = sample_weights(conn)
        conn.close()
        self.assertAlmostEqual(won, 8 / 2)
        self.assertAlmostEqual(lost, 4 / 2)

    def test_reported_rate_recovers_the_population_not_the_sample(self):
        conn = seed()
        summary = collect_metrics(conn, *meeting_clauses())["summary"]
        conn.close()
        # The raw sample is 2 won of 4 = 50.0; weighting must report the true 66.7.
        self.assertEqual(summary["win_rate"], 66.7)
        self.assertEqual(summary["labeled"], 4)

    def test_sample_size_stays_raw_so_min_sample_dimming_is_honest(self):
        conn = seed()
        jobs = by_job(collect_metrics(conn, *meeting_clauses()))
        conn.close()
        # Weighting changes the rate but must never inflate n.
        self.assertEqual(jobs["scheduling_booking"]["total"], 2)
        self.assertEqual(jobs["scheduling_booking"]["win_rate"], 100.0)
        self.assertEqual(jobs["order_taking"]["win_rate"], 0.0)

    def test_no_labels_does_not_divide_by_zero(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO meetings VALUES (?,?,?,?,?,?,?,?)", MEETINGS)
        self.assertEqual(sample_weights(conn), (0.0, 0.0))
        self.assertEqual(collect_metrics(conn, *meeting_clauses())["summary"]["win_rate"], 0)
        conn.close()


class FilteredMetricsTest(unittest.TestCase):
    def test_seller_filter_narrows_results(self):
        conn = seed()
        ana = collect_metrics(conn, *meeting_clauses(seller="Ana"))
        conn.close()
        self.assertEqual({r["seller"] for r in ana["by_seller"]}, {"Ana"})

    def test_seller_series_is_present(self):
        conn = seed()
        sellers = collect_metrics(conn, *meeting_clauses())["by_seller"]
        conn.close()
        self.assertEqual({r["seller"] for r in sellers}, {"Ana", "Ben"})

    def test_gravity_filter_narrows_mix(self):
        conn = seed()
        mix = collect_metrics(conn, *meeting_clauses(system_gravity="standalone_ok"))
        conn.close()
        self.assertEqual({r["gravity"] for r in mix["gravity_mix"]}, {"standalone_ok"})
        self.assertEqual(sum(r["share"] for r in mix["gravity_mix"]), 100.0)

    def test_labeled_only_clause_is_emitted(self):
        clauses, _ = meeting_clauses(labeled_only=True)
        self.assertIn("c.prompt_version IS NOT NULL", clauses)

    def test_unknown_group_column_is_rejected(self):
        conn = seed()
        with self.assertRaises(ValueError):
            main.win_rate(conn, "m.transcript; DROP TABLE meetings", "x", [], [], (1.0, 1.0))
        conn.close()


class MeetingsEndpointTest(unittest.TestCase):
    """Covers the query behind the table: ordering, paging and the label LEFT JOIN."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "t.db"
        seed(str(path)).close()
        self._real_db = main.BUNDLE_DB
        main.BUNDLE_DB = path

    def tearDown(self):
        main.BUNDLE_DB = self._real_db
        self.tmp.cleanup()

    def test_orders_by_date_descending(self):
        page = main.meetings()
        dates = [m["meeting_date"] for m in page["items"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(page["total"], 12)

    def test_offset_pages_without_overlap(self):
        first = main.meetings(limit=5)
        second = main.meetings(limit=5, offset=5)
        self.assertEqual(len(first["items"]), 5)
        self.assertEqual(second["offset"], 5)
        self.assertFalse({m["id"] for m in first["items"]} & {m["id"] for m in second["items"]})

    def test_unlabeled_rows_still_appear_with_null_labels(self):
        unlabeled = [m for m in main.meetings(limit=200)["items"] if m["primary_job"] is None]
        self.assertEqual(len(unlabeled), 8)

    def test_labeled_only_filters_to_labeled_rows(self):
        page = main.meetings(labeled_only=True, limit=200)
        self.assertEqual(page["total"], 4)
        self.assertTrue(all(m["primary_job"] for m in page["items"]))


if __name__ == "__main__":
    unittest.main()
