#!/usr/bin/env python3
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "meetings.db"
LABELS_PATH = ROOT / "data" / "labels_llm_v1.json"


def load_labels(path: Path = LABELS_PATH):
    labels = json.loads(path.read_text(encoding="utf-8"))
    conn = sqlite3.connect(DB_PATH)
    existing = {r[0] for r in conn.execute("SELECT id FROM meetings").fetchall()}
    ok, skip = 0, 0
    for row in labels:
        mid = row["meeting_id"]
        if mid not in existing:
            skip += 1
            continue
        conn.execute(
            """INSERT OR REPLACE INTO categories
               (meeting_id, primary_job, handoff_topology, system_gravity, trust_surface,
                voice_contract, buying_trigger, volume_band, model, prompt_version, labeled_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mid, row["primary_job"], row["handoff_topology"], row["system_gravity"],
                row["trust_surface"], row["voice_contract"], row["buying_trigger"],
                row["volume_band"], row["model"], row["prompt_version"], row["labeled_at"],
            ),
        )
        ok += 1
    conn.commit()
    conn.close()
    print(f"Loaded {ok} labels from {path.name}, skipped {skip}")


if __name__ == "__main__":
    load_labels()
