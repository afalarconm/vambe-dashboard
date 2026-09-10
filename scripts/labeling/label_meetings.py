#!/usr/bin/env python3
"""Offline batch labeling via OpenRouter (Label step)."""
import argparse
import os
import random
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.labeling.export_labels import export_labels
from scripts.labeling.openrouter_client import llm_classify

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "meetings.db"
PROMPT_VERSION = "llm-v1"


def stratified_sample(conn: sqlite3.Connection, n: int = 100) -> list[int]:
    closed = [r[0] for r in conn.execute("SELECT id FROM meetings WHERE closed=1").fetchall()]
    open_ = [r[0] for r in conn.execute("SELECT id FROM meetings WHERE closed=0").fetchall()]
    half = n // 2
    pick_closed = random.sample(closed, min(half, len(closed)))
    pick_open = random.sample(open_, min(half, len(open_)))
    ids = pick_closed + pick_open
    remaining = n - len(ids)
    if remaining > 0:
        pool = [i for i in closed + open_ if i not in ids]
        ids += random.sample(pool, min(remaining, len(pool)))
    return ids


def save_category(conn, meeting_id: int, cats: dict, model: str):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO categories
           (meeting_id, primary_job, handoff_topology, system_gravity, trust_surface,
            voice_contract, buying_trigger, volume_band, model, prompt_version, labeled_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            meeting_id,
            cats["primary_job"],
            cats["handoff_topology"],
            cats["system_gravity"],
            cats["trust_surface"],
            cats["voice_contract"],
            cats["buying_trigger"],
            cats["volume_band"],
            model,
            PROMPT_VERSION,
            now,
        ),
    )


def run(limit: int, export: Path | None):
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY not set")

    random.seed(42)
    conn = sqlite3.connect(DB_PATH)
    ids = stratified_sample(conn, limit)
    model = os.environ.get("OPENROUTER_MODEL", "google/gemma-3-27b-it")
    fallback = "google/gemini-2.0-flash-001"
    t0 = time.time()

    ok, skip = 0, 0
    for i, mid in enumerate(ids, 1):
        transcript = conn.execute("SELECT transcript FROM meetings WHERE id=?", (mid,)).fetchone()[0]
        cats = llm_classify(transcript, model, fallback)
        if not cats:
            skip += 1
            if i % 25 == 0:
                print(f"progress {i}/{len(ids)} ok={ok} skip={skip}", flush=True)
            continue
        save_category(conn, mid, cats, model)
        ok += 1
        time.sleep(0.3)
        if i % 25 == 0:
            print(f"progress {i}/{len(ids)} ok={ok} skip={skip}", flush=True)

    conn.commit()
    conn.close()
    elapsed = time.time() - t0
    print(f"LLM: labeled {ok}, skipped {skip}, elapsed {elapsed:.0f}s")

    if export:
        export_labels(export)


def main():
    parser = argparse.ArgumentParser(description="Label meetings via OpenRouter LLM")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--export", nargs="?", const=str(ROOT / "data" / "labels_llm_v1.json"))
    args = parser.parse_args()
    export_path = Path(args.export) if args.export else None
    run(args.limit, export_path)


if __name__ == "__main__":
    main()
