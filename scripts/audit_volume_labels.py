#!/usr/bin/env python3
"""Measure volume labels against the transcripts they came from.

`volume_band` is the one dimension with derivable ground truth: the transcripts
state the figure in plain text, so a regex can extract it and the label can be
checked. The other five are judgement calls and would need hand-labeling.

Run it to see whether the model reads the figure AND its unit:

    python scripts/audit_volume_labels.py

The regex is not perfect — transcripts quoting several numbers can fool it — so
treat the absolute rate as a floor. The breakdown by period is the useful part:
it isolates how much the answer depends on arithmetic the model should not do.
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.labeling.taxonomy import volume_band  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "meetings.db"

NOUN = (r"(?:consultas?|mensajes?|tickets?|llamadas?|conversaciones?|pedidos?"
        r"|solicitudes?|interacciones?|contactos?|reservas?|cotizaciones?)")
PATTERN = re.compile(
    rf"(\d[\d.,]*)\s*(?:(?:a|y|hasta)\s*(\d[\d.,]*)\s*)?{NOUN}[^.]{{0,60}}?"
    rf"(diaria|diario|semanal|mensual|anual|al d[ií]a|por d[ií]a|a la semana"
    rf"|por semana|al mes|por mes|al a[ñn]o)",
    re.I,
)
PERIOD_WORDS = [("dia", "daily"), ("día", "daily"), ("seman", "weekly"),
                ("mensual", "monthly"), ("mes", "monthly"),
                ("anual", "yearly"), ("año", "yearly"), ("ano", "yearly")]


def stated_volume(transcript: str) -> tuple[int, str] | None:
    """The figure and unit a transcript states, or None when the regex finds none."""
    m = PATTERN.search(transcript)
    if not m:
        return None
    amount = (m.group(2) or m.group(1)).replace(".", "").replace(",", ".")
    period = next((p for w, p in PERIOD_WORDS if w in m.group(3).lower()), None)
    return (int(float(amount)), period) if period else None


def audit(prompt_version: str | None = None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    sql = """SELECT m.transcript, c.volume_band, c.prompt_version
             FROM meetings m JOIN categories c ON c.meeting_id = m.id"""
    params = []
    if prompt_version:
        sql += " WHERE c.prompt_version = ?"
        params.append(prompt_version)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    if not rows:
        print("No labels found. Run the labeler, then bake_db.py.")
        return

    tally = {p: [0, 0] for p in ("monthly", "weekly", "daily", "yearly")}
    unextractable = 0
    for r in rows:
        stated = stated_volume(r["transcript"])
        if not stated:
            unextractable += 1
            continue
        amount, period = stated
        tally[period][1] += 1
        tally[period][0] += r["volume_band"] == volume_band(amount, period)

    checked = sum(t[1] for t in tally.values())
    agreed = sum(t[0] for t in tally.values())
    version = prompt_version or f"{len({r['prompt_version'] for r in rows})} version(s)"
    print(f"{len(rows)} labels ({version}); a figure was extractable from {checked}, "
          f"not from {unextractable}\n")
    print(f"{'stated as':12} {'n':>6} {'label matches the transcript':>30}")
    print("-" * 50)
    for period in ("monthly", "weekly", "daily", "yearly"):
        ok, total = tally[period]
        if total:
            print(f"{period:12} {total:6} {ok:14} = {100 * ok / total:5.1f}%")
    print("-" * 50)
    print(f"{'ALL':12} {checked:6} {agreed:14} = {100 * agreed / checked:5.1f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-version", help="restrict to one prompt version")
    audit(parser.parse_args().prompt_version)
