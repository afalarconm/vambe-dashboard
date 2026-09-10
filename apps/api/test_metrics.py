import sqlite3
import unittest

from apps.api.main import collect_metrics, meeting_clauses


def seed():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE meetings (
            id INTEGER PRIMARY KEY, nombre TEXT, seller TEXT, closed INTEGER, transcript TEXT
        );
        CREATE TABLE categories (
            meeting_id INTEGER PRIMARY KEY,
            primary_job TEXT, handoff_topology TEXT, system_gravity TEXT,
            trust_surface TEXT, buying_trigger TEXT, volume_band TEXT, prompt_version TEXT
        );
        INSERT INTO meetings VALUES
            (1, 'A1', 'Ana', 1, 'hola'),
            (2, 'A2', 'Ana', 1, 'hola'),
            (3, 'B1', 'Ben', 0, 'hola'),
            (4, 'B2', 'Ben', 0, 'hola');
        INSERT INTO categories VALUES
            (1, 'scheduling_booking', 'bot_only_implied', 'standalone_ok', 'standard', 'ops_saturation', 'lt_100_mo', 'llm-v1'),
            (2, 'scheduling_booking', 'generic_human_handoff', 'must_integrate', 'standard', 'ops_saturation', 'lt_100_mo', 'llm-v1'),
            (3, 'scheduling_booking', 'bot_only_implied', 'standalone_ok', 'standard', 'growth_ambition', 'lt_100_mo', 'llm-v1'),
            (4, 'order_taking', 'bot_only_implied', 'must_integrate', 'standard', 'growth_ambition', 'lt_100_mo', 'llm-v1');
    """)
    return conn


def by_job(metrics):
    return {row["job"]: row["win_rate"] for row in metrics["by_job"]}


class FilteredMetricsTest(unittest.TestCase):
    def test_seller_filter_changes_win_rate(self):
        conn = seed()
        all_jobs = by_job(collect_metrics(conn, *meeting_clauses()))
        ana = by_job(collect_metrics(conn, *meeting_clauses(seller="Ana")))
        conn.close()

        self.assertEqual(all_jobs["scheduling_booking"], 66.7)
        self.assertEqual(all_jobs["order_taking"], 0.0)
        self.assertEqual(ana["scheduling_booking"], 100.0)
        self.assertNotIn("order_taking", ana)

    def test_gravity_filter_narrows_mix(self):
        conn = seed()
        mix = collect_metrics(conn, *meeting_clauses(system_gravity="standalone_ok"))
        conn.close()
        gravities = {row["gravity"] for row in mix["gravity_mix"]}
        self.assertEqual(gravities, {"standalone_ok"})

    def test_summary_win_rate(self):
        conn = seed()
        summary = collect_metrics(conn, *meeting_clauses())["summary"]
        conn.close()
        self.assertEqual(summary["labeled"], 4)
        self.assertEqual(summary["wins"], 2)
        self.assertEqual(summary["win_rate"], 50.0)


if __name__ == "__main__":
    unittest.main()
