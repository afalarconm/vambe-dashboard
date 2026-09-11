import sqlite3
from pathlib import Path

from typing import Annotated

from fastapi import FastAPI, Query

ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLE_DB = ROOT / "data" / "meetings.db"
STATIC_DIR = ROOT / "apps" / "web" / "dist"

# Win-rate charts. Seller lives on `meetings`, the labelled dimensions on `categories`,
# so every group column is written qualified and checked against GROUP_COLS before use.
WIN_RATE_SERIES = (
    ("m.seller", "seller"),
    ("c.primary_job", "job"),
    ("c.handoff_topology", "handoff"),
    ("c.buying_trigger", "trigger"),
    ("c.volume_band", "volume_band"),
)
GROUP_COLS = {col for col, _ in WIN_RATE_SERIES} | {"c.system_gravity"}


app = FastAPI()


def db():
    conn = sqlite3.connect(f"file:{BUNDLE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def sample_weights(conn) -> tuple[float, float]:
    """Inverse-probability weights, one per outcome, undoing the labeling sample.

    `scripts/labeling/label_meetings.py` draws closed and open meetings in equal
    numbers, so the labeled subset over-represents lost deals and every raw rate
    computed on it is dragged toward 50%. Selection depended *only* on `closed`
    and was uniform at random within each outcome, so scaling each row by
    population/sample for its own outcome recovers population rates — and stays
    valid inside any subgroup, which is why these are two global constants.
    """
    row = conn.execute("""
        SELECT
          (SELECT COUNT(*) FROM meetings WHERE closed = 1) AS pop_won,
          (SELECT COUNT(*) FROM meetings WHERE closed = 0) AS pop_lost,
          (SELECT COUNT(*) FROM meetings m JOIN categories c ON c.meeting_id = m.id
            WHERE m.closed = 1) AS lab_won,
          (SELECT COUNT(*) FROM meetings m JOIN categories c ON c.meeting_id = m.id
            WHERE m.closed = 0) AS lab_lost
    """).fetchone()
    won = row["pop_won"] / row["lab_won"] if row["lab_won"] else 0.0
    lost = row["pop_lost"] / row["lab_lost"] if row["lab_lost"] else 0.0
    return won, lost


def rate_sql(won: float, lost: float) -> str:
    """Win rate with the labeling sample weighted back to the population.

    Both weights come from sample_weights() as floats; nothing here is user input,
    which is why they are formatted into the statement rather than bound.
    """
    return (
        f"ROUND(100.0 * SUM(CASE WHEN m.closed = 1 THEN {float(won)} ELSE 0 END)"
        f" / NULLIF(SUM(CASE WHEN m.closed = 1 THEN {float(won)} ELSE {float(lost)} END), 0), 1)"
    )


def meeting_clauses(
    seller: str | None = None,
    closed: int | None = None,
    primary_job: str | None = None,
    handoff_topology: str | None = None,
    trust_surface: str | None = None,
    buying_trigger: str | None = None,
    system_gravity: str | None = None,
    volume_band: str | None = None,
    q: str | None = None,
    labeled_only: bool = False,
) -> tuple[list[str], list]:
    clauses, params = [], []
    if labeled_only:
        clauses.append("c.prompt_version IS NOT NULL")
    if seller:
        clauses.append("m.seller = ?")
        params.append(seller)
    if closed is not None:
        clauses.append("m.closed = ?")
        params.append(closed)
    if primary_job:
        clauses.append("c.primary_job = ?")
        params.append(primary_job)
    if handoff_topology:
        clauses.append("c.handoff_topology = ?")
        params.append(handoff_topology)
    if trust_surface:
        clauses.append("c.trust_surface = ?")
        params.append(trust_surface)
    if buying_trigger:
        clauses.append("c.buying_trigger = ?")
        params.append(buying_trigger)
    if system_gravity:
        clauses.append("c.system_gravity = ?")
        params.append(system_gravity)
    if volume_band:
        clauses.append("c.volume_band = ?")
        params.append(volume_band)
    if q:
        clauses.append("(m.nombre LIKE ? OR m.transcript LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    return clauses, params


def where_sql(clauses: list[str]) -> str:
    return f"WHERE {' AND '.join(clauses)}" if clauses else ""


def win_rate(conn, group_col: str, alias: str, clauses: list[str], params: list, weights):
    if group_col not in GROUP_COLS:
        raise ValueError(group_col)
    where = where_sql([*clauses, f"{group_col} IS NOT NULL"])
    rows = conn.execute(f"""
        SELECT {group_col} AS {alias},
               SUM(m.closed) AS wins,
               COUNT(*) AS total,
               {rate_sql(*weights)} AS win_rate
        FROM meetings m
        JOIN categories c ON c.meeting_id = m.id
        {where}
        GROUP BY {group_col}
        ORDER BY win_rate DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def gravity_mix(conn, clauses: list[str], params: list):
    """Plain composition of the labeled sample — a count, not a rate, so unweighted."""
    where = where_sql([*clauses, "c.system_gravity IS NOT NULL"])
    rows = [dict(r) for r in conn.execute(f"""
        SELECT c.system_gravity AS gravity, COUNT(*) AS count
        FROM meetings m
        JOIN categories c ON c.meeting_id = m.id
        {where}
        GROUP BY c.system_gravity
        ORDER BY count DESC
    """, params).fetchall()]
    total = sum(r["count"] for r in rows)
    for r in rows:
        r["share"] = round(100.0 * r["count"] / total, 1) if total else 0
    return rows


def job_handoff_heatmap(conn, clauses: list[str], params: list, weights):
    where = where_sql([
        *clauses,
        "c.primary_job IS NOT NULL",
        "c.handoff_topology IS NOT NULL",
    ])
    cells = [dict(r) for r in conn.execute(f"""
        SELECT c.primary_job AS job,
               c.handoff_topology AS handoff,
               SUM(m.closed) AS wins,
               COUNT(*) AS total,
               {rate_sql(*weights)} AS win_rate
        FROM meetings m
        JOIN categories c ON c.meeting_id = m.id
        {where}
        GROUP BY c.primary_job, c.handoff_topology
    """, params).fetchall()]
    jobs = sorted({c["job"] for c in cells})
    handoffs = sorted({c["handoff"] for c in cells})
    return {"jobs": jobs, "handoffs": handoffs, "cells": cells, "min_sample": 5}


def labeled_summary(conn, clauses: list[str], params: list, weights):
    where = where_sql(clauses)
    row = conn.execute(f"""
        SELECT COUNT(*) AS labeled,
               COALESCE(SUM(m.closed), 0) AS wins,
               {rate_sql(*weights)} AS win_rate
        FROM meetings m
        JOIN categories c ON c.meeting_id = m.id
        {where}
    """, params).fetchone()
    return {
        "labeled": row["labeled"],
        "wins": row["wins"],
        "win_rate": row["win_rate"] or 0,
    }


def collect_metrics(conn, clauses: list[str], params: list) -> dict:
    weights = sample_weights(conn)
    series = {
        f"by_{alias}": win_rate(conn, col, alias, clauses, params, weights)
        for col, alias in WIN_RATE_SERIES
    }
    return {
        **series,
        "gravity_mix": gravity_mix(conn, clauses, params),
        "job_handoff_heatmap": job_handoff_heatmap(conn, clauses, params, weights),
        "summary": labeled_summary(conn, clauses, params, weights),
    }


@app.get("/health")
def health():
    conn = db()
    labeled = conn.execute(
        "SELECT COUNT(*) FROM categories WHERE prompt_version IS NOT NULL"
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM meetings").fetchone()[0]
    conn.close()
    return {"ok": True, "llm_labels": labeled, "total_meetings": total}


@app.get("/meetings")
def meetings(
    seller: str | None = None,
    closed: int | None = None,
    primary_job: str | None = None,
    handoff_topology: str | None = None,
    trust_surface: str | None = None,
    buying_trigger: str | None = None,
    system_gravity: str | None = None,
    volume_band: str | None = None,
    q: str | None = None,
    labeled_only: bool = False,
    limit: Annotated[int, Query(le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    clauses, params = meeting_clauses(
        seller=seller, closed=closed, primary_job=primary_job,
        handoff_topology=handoff_topology, trust_surface=trust_surface,
        buying_trigger=buying_trigger, system_gravity=system_gravity,
        volume_band=volume_band, q=q, labeled_only=labeled_only,
    )
    where = where_sql(clauses)
    conn = db()
    rows = [dict(r) for r in conn.execute(f"""
        SELECT m.id, m.nombre, m.email, m.seller, m.meeting_date, m.closed, m.transcript,
               c.primary_job, c.handoff_topology, c.system_gravity, c.trust_surface,
               c.buying_trigger, c.volume_band, c.model, c.prompt_version
        FROM meetings m
        LEFT JOIN categories c ON c.meeting_id = m.id
        {where}
        ORDER BY m.meeting_date DESC
        LIMIT ? OFFSET ?
    """, [*params, limit, offset]).fetchall()]
    count = conn.execute(
        f"SELECT COUNT(*) FROM meetings m LEFT JOIN categories c ON c.meeting_id = m.id {where}",
        params,
    ).fetchone()[0]
    conn.close()
    return {"items": rows, "total": count, "limit": limit, "offset": offset}


@app.get("/metrics")
def metrics(
    seller: str | None = None,
    closed: int | None = None,
    primary_job: str | None = None,
    handoff_topology: str | None = None,
    trust_surface: str | None = None,
    buying_trigger: str | None = None,
    system_gravity: str | None = None,
    volume_band: str | None = None,
    q: str | None = None,
    labeled_only: bool = False,
):
    clauses, params = meeting_clauses(
        seller=seller, closed=closed, primary_job=primary_job,
        handoff_topology=handoff_topology, trust_surface=trust_surface,
        buying_trigger=buying_trigger, system_gravity=system_gravity,
        volume_band=volume_band, q=q, labeled_only=labeled_only,
    )
    conn = db()
    result = collect_metrics(conn, clauses, params)
    conn.close()
    return result


@app.get("/filters")
def filters():
    conn = db()

    def distinct(col, table="meetings"):
        return [r[0] for r in conn.execute(
            f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL ORDER BY 1"
        ).fetchall()]

    result = {
        "sellers": distinct("seller"),
        "primary_jobs": distinct("primary_job", "categories"),
        "handoff_topologies": distinct("handoff_topology", "categories"),
        "trust_surfaces": distinct("trust_surface", "categories"),
        "buying_triggers": distinct("buying_trigger", "categories"),
        "system_gravities": distinct("system_gravity", "categories"),
        "volume_bands": distinct("volume_band", "categories"),
    }
    conn.close()
    return result


if STATIC_DIR.exists():
    app.frontend("/", directory=STATIC_DIR, fallback="index.html")
