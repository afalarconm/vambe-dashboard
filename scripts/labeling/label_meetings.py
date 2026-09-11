#!/usr/bin/env python3
"""Offline batch labeling via OpenRouter (Label step)."""
import argparse
import os
import random
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from scripts.labeling.export_labels import export_labels
from scripts.labeling.openrouter_client import llm_classify
from scripts.labeling.taxonomy import volume_band

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "meetings.db"
PROMPT_VERSION = "llm-v2"


def load_env(path: Path = ROOT / ".env") -> None:
    """Read .env if present. The labeler is the only thing here that needs a secret,
    so this stays a few lines rather than a dependency the deployed app would carry."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def stratified_sample(conn: sqlite3.Connection, n: int) -> list[int]:
    """Half closed, half open, so every dimension sees both outcomes.

    This deliberately does not mirror the population — apps/api/main.py weights the
    rates back. Deterministic under the seed, so a resumed run targets the same set.
    """
    closed = [r[0] for r in conn.execute("SELECT id FROM meetings WHERE closed=1 ORDER BY id")]
    open_ = [r[0] for r in conn.execute("SELECT id FROM meetings WHERE closed=0 ORDER BY id")]
    half = n // 2
    ids = random.sample(closed, min(half, len(closed))) + random.sample(open_, min(half, len(open_)))
    remaining = n - len(ids)
    if remaining > 0:
        pool = [i for i in closed + open_ if i not in set(ids)]
        ids += random.sample(pool, min(remaining, len(pool)))
    return ids


def already_labeled(conn: sqlite3.Connection) -> set[int]:
    return {r[0] for r in conn.execute(
        "SELECT meeting_id FROM categories WHERE prompt_version = ?", (PROMPT_VERSION,)
    )}


def save_category(conn, meeting_id: int, cats: dict, model: str):
    conn.execute(
        """INSERT OR REPLACE INTO categories
           (meeting_id, primary_job, handoff_topology, system_gravity, trust_surface,
            buying_trigger, volume_amount, volume_period, volume_band,
            model, prompt_version, labeled_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            meeting_id,
            cats["primary_job"],
            cats["handoff_topology"],
            cats["system_gravity"],
            cats["trust_surface"],
            cats["buying_trigger"],
            cats["volume_amount"],
            cats["volume_period"],
            volume_band(cats["volume_amount"], cats["volume_period"]),
            model,
            PROMPT_VERSION,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def run(limit: int, export: Path | None, workers: int, resume: bool):
    load_env()
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY not set (put it in .env or the environment)")

    random.seed(42)
    conn = sqlite3.connect(DB_PATH)
    ids = stratified_sample(conn, limit)
    if resume:
        done = already_labeled(conn)
        skipped_done = len([i for i in ids if i in done])
        ids = [i for i in ids if i not in done]
        if skipped_done:
            print(f"resuming: {skipped_done} already labeled at {PROMPT_VERSION}")

    model = os.environ.get("OPENROUTER_MODEL", "google/gemma-3-27b-it")
    fallback = os.environ.get("OPENROUTER_FALLBACK_MODEL", "google/gemini-2.5-flash")
    transcripts = dict(conn.execute(
        f"SELECT id, transcript FROM meetings WHERE id IN ({','.join('?' * len(ids))})", ids
    )) if ids else {}

    t0 = time.time()
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(llm_classify, transcripts[i], model, fallback): i
            for i in ids
        }
        for done_n, future in enumerate(as_completed(futures), 1):
            mid = futures[future]
            try:
                cats = future.result()
            except Exception as e:                      # one bad call must not kill the run
                print(f"  {mid}: {type(e).__name__}: {e}", flush=True)
                cats = None
            if cats:
                save_category(conn, mid, cats, model)
                ok += 1
            else:
                fail += 1
            if done_n % 100 == 0:
                conn.commit()
                rate = done_n / (time.time() - t0)
                left = (len(ids) - done_n) / rate if rate else 0
                print(f"  {done_n}/{len(ids)}  ok={ok} fail={fail}  "
                      f"{rate:.1f}/s  ~{left/60:.0f}m left", flush=True)

    conn.commit()
    conn.close()
    print(f"LLM: labeled {ok}, failed {fail}, elapsed {time.time() - t0:.0f}s")

    if export:
        export_labels(export, PROMPT_VERSION)


def main():
    parser = argparse.ArgumentParser(description="Label meetings via OpenRouter LLM")
    parser.add_argument("--limit", type=int, default=3000)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--no-resume", action="store_true", help="re-label rows already done")
    parser.add_argument("--export", nargs="?", const=str(ROOT / "data" / "labels_llm_v2.json"))
    args = parser.parse_args()
    run(args.limit, Path(args.export) if args.export else None, args.workers, not args.no_resume)


if __name__ == "__main__":
    main()
