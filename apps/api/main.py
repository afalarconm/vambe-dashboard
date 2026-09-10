from pathlib import Path

import sqlite3
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "meetings.db"
STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def win_rate(conn, group_col: str, alias: str):
    rows = conn.execute(f"""
        SELECT c.{group_col} AS {alias},
               SUM(m.closed) AS wins,
               COUNT(*) AS total,
               ROUND(100.0 * SUM(m.closed) / COUNT(*), 1) AS win_rate
        FROM meetings m
        JOIN categories c ON c.meeting_id = m.id
        WHERE c.{group_col} IS NOT NULL
        GROUP BY c.{group_col}
        ORDER BY win_rate DESC
    """).fetchall()
    return [dict(r) for r in rows]


@app.get("/health")
def health():
    conn = db()
    n = conn.execute("SELECT COUNT(*) FROM categories WHERE prompt_version='llm-v1'").fetchone()[0]
    conn.close()
    return {"ok": True, "llm_labels": n}


@app.get("/meetings")
def meetings(
    seller: str | None = None,
    closed: int | None = None,
    primary_job: str | None = None,
    handoff_topology: str | None = None,
    trust_surface: str | None = None,
    buying_trigger: str | None = None,
    q: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    clauses, params = [], []
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
    if q:
        clauses.append("(m.nombre LIKE ? OR m.transcript LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT m.id, m.nombre, m.email, m.seller, m.meeting_date, m.closed,
               c.primary_job, c.handoff_topology, c.trust_surface, c.buying_trigger,
               c.volume_band, c.model, c.prompt_version
        FROM meetings m
        LEFT JOIN categories c ON c.meeting_id = m.id
        {where}
        ORDER BY m.meeting_date DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    conn = db()
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    count = conn.execute(
        f"SELECT COUNT(*) FROM meetings m LEFT JOIN categories c ON c.meeting_id = m.id {where}",
        params[:-2],
    ).fetchone()[0]
    conn.close()
    return {"items": rows, "total": count}


@app.get("/metrics/win-rate-by-job")
def win_rate_by_job():
    conn = db()
    result = win_rate(conn, "primary_job", "job")
    conn.close()
    return result


@app.get("/metrics/win-rate-by-handoff")
def win_rate_by_handoff():
    conn = db()
    result = win_rate(conn, "handoff_topology", "handoff")
    conn.close()
    return result


@app.get("/metrics/win-rate-by-trigger")
def win_rate_by_trigger():
    conn = db()
    result = win_rate(conn, "buying_trigger", "trigger")
    conn.close()
    return result


@app.get("/metrics/system-gravity-mix")
def system_gravity_mix():
    conn = db()
    rows = conn.execute("""
        SELECT c.system_gravity AS gravity,
               COUNT(*) AS count,
               ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM categories), 1) AS share
        FROM categories c
        WHERE c.system_gravity IS NOT NULL
        GROUP BY c.system_gravity
        ORDER BY count DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/filters")
def filters():
    conn = db()
    def distinct(col, table="meetings", alias="m"):
        return [r[0] for r in conn.execute(
            f"SELECT DISTINCT {col} FROM {table} {alias} WHERE {col} IS NOT NULL ORDER BY 1"
        ).fetchall()]

    result = {
        "sellers": distinct("seller"),
        "primary_jobs": [r[0] for r in conn.execute(
            "SELECT DISTINCT primary_job FROM categories WHERE primary_job IS NOT NULL ORDER BY 1"
        ).fetchall()],
        "handoff_topologies": [r[0] for r in conn.execute(
            "SELECT DISTINCT handoff_topology FROM categories WHERE handoff_topology IS NOT NULL ORDER BY 1"
        ).fetchall()],
        "trust_surfaces": [r[0] for r in conn.execute(
            "SELECT DISTINCT trust_surface FROM categories WHERE trust_surface IS NOT NULL ORDER BY 1"
        ).fetchall()],
        "buying_triggers": [r[0] for r in conn.execute(
            "SELECT DISTINCT buying_trigger FROM categories WHERE buying_trigger IS NOT NULL ORDER BY 1"
        ).fetchall()],
    }
    conn.close()
    return result


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
