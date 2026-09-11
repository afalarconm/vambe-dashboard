import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "meetings.db"
DEFAULT_OUT = ROOT / "data" / "labels_llm_v2.json"


def export_labels(out: Path = DEFAULT_OUT, prompt_version: str = "llm-v2"):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT meeting_id, primary_job, handoff_topology, system_gravity, trust_surface,
                  buying_trigger, volume_amount, volume_period, model, prompt_version, labeled_at
           FROM categories WHERE prompt_version = ? ORDER BY meeting_id""",
        (prompt_version,),
    ).fetchall()
    conn.close()
    data = [dict(r) for r in rows]
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Exported {len(data)} rows → {out}")
    return len(data)


if __name__ == "__main__":
    export_labels()
