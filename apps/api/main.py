import sqlite3
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLE_DB = ROOT / "data" / "meetings.db"
STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"

WIN_RATE_SERIES = (
    ("primary_job", "job"),
    ("handoff_topology", "handoff"),
    ("buying_trigger", "trigger"),
    ("volume_band", "volume_band"),
)
GROUP_COLS = {col for col, _ in WIN_RATE_SERIES} | {"system_gravity"}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def db():
    conn = sqlite3.connect(f"file:{BUNDLE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


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


def win_rate(conn, group_col: str, alias: str, clauses: list[str], params: list):
    if group_col not in GROUP_COLS:
        raise ValueError(group_col)
    where = where_sql([*clauses, f"c.{group_col} IS NOT NULL"])
    rows = conn.execute(f"""
        SELECT c.{group_col} AS {alias},
               SUM(m.closed) AS wins,
               COUNT(*) AS total,
               ROUND(100.0 * SUM(m.closed) / COUNT(*), 1) AS win_rate
        FROM meetings m
        JOIN categories c ON c.meeting_id = m.id
        {where}
        GROUP BY c.{group_col}
        ORDER BY win_rate DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def gravity_mix(conn, clauses: list[str], params: list):
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


def job_handoff_heatmap(conn, clauses: list[str], params: list):
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
               ROUND(100.0 * SUM(m.closed) / COUNT(*), 1) AS win_rate
        FROM meetings m
        JOIN categories c ON c.meeting_id = m.id
        {where}
        GROUP BY c.primary_job, c.handoff_topology
    """, params).fetchall()]
    jobs = sorted({c["job"] for c in cells})
    handoffs = sorted({c["handoff"] for c in cells})
    return {"jobs": jobs, "handoffs": handoffs, "cells": cells, "min_sample": 5}


def labeled_summary(conn, clauses: list[str], params: list):
    where = where_sql(clauses)
    row = conn.execute(f"""
        SELECT COUNT(*) AS labeled, COALESCE(SUM(m.closed), 0) AS wins
        FROM meetings m
        JOIN categories c ON c.meeting_id = m.id
        {where}
    """, params).fetchone()
    labeled = row["labeled"]
    wins = row["wins"]
    return {
        "labeled": labeled,
        "wins": wins,
        "win_rate": round(100.0 * wins / labeled, 1) if labeled else 0,
    }


def collect_metrics(conn, clauses: list[str], params: list) -> dict:
    series = {
        f"by_{alias}": win_rate(conn, col, alias, clauses, params)
        for col, alias in WIN_RATE_SERIES
    }
    return {
        **series,
        "gravity_mix": gravity_mix(conn, clauses, params),
        "job_handoff_heatmap": job_handoff_heatmap(conn, clauses, params),
        "summary": labeled_summary(conn, clauses, params),
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
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    clauses, params = meeting_clauses(
        seller=seller, closed=closed, primary_job=primary_job,
        handoff_topology=handoff_topology, trust_surface=trust_surface,
        buying_trigger=buying_trigger, system_gravity=system_gravity,
        volume_band=volume_band, q=q, labeled_only=labeled_only,
    )
    where = where_sql(clauses)
    sql = f"""
        SELECT m.id, m.nombre, m.email, m.seller, m.meeting_date, m.closed, m.transcript,
               c.primary_job, c.handoff_topology, c.system_gravity, c.trust_surface,
               c.buying_trigger, c.volume_band, c.model, c.prompt_version
        FROM meetings m
        LEFT JOIN categories c ON c.meeting_id = m.id
        {where}
        ORDER BY m.meeting_date DESC
        LIMIT ? OFFSET ?
    """
    conn = db()
    rows = [dict(r) for r in conn.execute(sql, [*params, limit, offset]).fetchall()]
    count = conn.execute(
        f"SELECT COUNT(*) FROM meetings m LEFT JOIN categories c ON c.meeting_id = m.id {where}",
        params,
    ).fetchone()[0]
    conn.close()
    return {"items": rows, "total": count}


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
    if hasattr(app, "frontend"):
        app.frontend("/", directory="apps/web/dist", fallback="index.html")
    else:
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
