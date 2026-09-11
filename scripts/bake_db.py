#!/usr/bin/env python3
"""Bake read model: CSV → SQLite meetings + labels JSON → categories (Bake step)."""
import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.labeling.taxonomy import volume_band  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "vambe_clients_10k.csv"
DB_PATH = ROOT / "data" / "meetings.db"
LABELS_PATH = ROOT / "data" / "labels_llm_v2.json"


def stable_id(email: str, phone: str, meeting_date: str) -> int:
    h = hashlib.sha256(f"{email}|{phone}|{meeting_date}".encode()).digest()
    return int.from_bytes(h[:8], "big") % (2**63)


# Single source of truth for the read model: tests seed from this same string,
# so a column added here can never silently drift out of the test fixture.
SCHEMA = """
CREATE TABLE meetings (
    id INTEGER PRIMARY KEY,
    nombre TEXT,
    email TEXT,
    phone TEXT,
    meeting_date TEXT,
    seller TEXT,
    closed INTEGER,
    transcript TEXT
);
CREATE TABLE categories (
    meeting_id INTEGER PRIMARY KEY REFERENCES meetings(id),
    primary_job TEXT,
    handoff_topology TEXT,
    system_gravity TEXT,
    trust_surface TEXT,
    buying_trigger TEXT,
    volume_amount INTEGER,
    volume_period TEXT,
    volume_band TEXT,
    model TEXT,
    prompt_version TEXT,
    labeled_at TEXT
);
"""


def create_schema(conn):
    conn.executescript("DROP TABLE IF EXISTS categories; DROP TABLE IF EXISTS meetings;")
    conn.executescript(SCHEMA)


def ingest_meetings():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        mid = stable_id(
            row["Correo Electronico"],
            row["Numero de Telefono"],
            row["Fecha de la Reunion"],
        )
        conn.execute(
            """INSERT OR REPLACE INTO meetings
               (id, nombre, email, phone, meeting_date, seller, closed, transcript)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mid,
                row["Nombre"],
                row["Correo Electronico"],
                row["Numero de Telefono"],
                row["Fecha de la Reunion"],
                row["Vendedor asignado"],
                int(row["closed"]),
                row["Transcripcion"],
            ),
        )
    conn.commit()
    conn.close()
    print(f"Ingested {len(rows)} meetings → {DB_PATH}")


def load_labels(path: Path = LABELS_PATH):
    if not path.exists():
        # Bootstrap: the labeler reads transcripts from this DB, so the first bake
        # of a fresh checkout runs before any labels exist.
        print(f"No labels at {path.name}; skipping")
        return
    labels = json.loads(path.read_text(encoding="utf-8"))
    conn = sqlite3.connect(DB_PATH)
    existing = {r[0] for r in conn.execute("SELECT id FROM meetings").fetchall()}
    ok, skip = 0, 0
    for row in labels:
        mid = row["meeting_id"]
        if mid not in existing:
            skip += 1
            continue
        # The band is derived here, not read from the file: changing a boundary
        # is then a re-bake rather than another labeling run.
        conn.execute(
            """INSERT OR REPLACE INTO categories
               (meeting_id, primary_job, handoff_topology, system_gravity, trust_surface,
                buying_trigger, volume_amount, volume_period, volume_band,
                model, prompt_version, labeled_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mid, row["primary_job"], row["handoff_topology"], row["system_gravity"],
                row["trust_surface"], row["buying_trigger"],
                row["volume_amount"], row["volume_period"],
                volume_band(row["volume_amount"], row["volume_period"]),
                row["model"], row["prompt_version"], row["labeled_at"],
            ),
        )
        ok += 1
    conn.commit()
    conn.close()
    print(f"Loaded {ok} labels from {path.name}, skipped {skip}")


def bake():
    ingest_meetings()
    load_labels()


if __name__ == "__main__":
    bake()
