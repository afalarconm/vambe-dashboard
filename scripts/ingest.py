#!/usr/bin/env python3
import csv
import hashlib
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "vambe_clients_10k.csv"
DB_PATH = ROOT / "data" / "meetings.db"


def stable_id(email: str, phone: str, meeting_date: str) -> int:
    h = hashlib.sha256(f"{email}|{phone}|{meeting_date}".encode()).digest()
    return int.from_bytes(h[:8], "big") % (2**63)


def ingest():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY,
            nombre TEXT,
            email TEXT,
            phone TEXT,
            meeting_date TEXT,
            seller TEXT,
            closed INTEGER,
            transcript TEXT
        );
        CREATE TABLE IF NOT EXISTS categories (
            meeting_id INTEGER PRIMARY KEY REFERENCES meetings(id),
            primary_job TEXT,
            handoff_topology TEXT,
            system_gravity TEXT,
            trust_surface TEXT,
            voice_contract TEXT,
            buying_trigger TEXT,
            volume_band TEXT,
            model TEXT,
            prompt_version TEXT,
            labeled_at TEXT
        );
    """)

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    conn.execute("DELETE FROM categories")
    conn.execute("DELETE FROM meetings")
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


if __name__ == "__main__":
    ingest()
