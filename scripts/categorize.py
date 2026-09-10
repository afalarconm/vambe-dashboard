#!/usr/bin/env python3
import argparse
import json
import os
import random
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enums import ALL

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "meetings.db"
PROMPT_VERSION = "llm-v1"

SYSTEM_PROMPT = """Classify sales meeting transcripts into fixed categories. Reply JSON only:
{"primary_job":"...","handoff_topology":"...","system_gravity":"...","trust_surface":"...","voice_contract":"...","buying_trigger":"...","volume_band":"..."}
Valid values:
primary_job: scheduling_booking|catalog_guided_selling|quoting_pricing|order_taking|claims_intake|shipment_tracking|lead_qualification|faq_education
handoff_topology: bot_only_implied|generic_human_handoff|book_specialist|role_based_routing
system_gravity: standalone_ok|named_system_desired|must_integrate
trust_surface: standard|health_sensitive|regulated_advice_boundary|discretion_prestige
voice_contract: not_specified|warm_hospitable|corporate_expert|motivational_energetic|luxury_prestige|care_trustworthy|brand_custom
buying_trigger: ops_saturation|coverage_gap|growth_ambition|budget_cautious|efficiency_general
volume_band: lt_100_mo|100_499_mo|500_1999_mo|2000_plus_mo|unspecified"""


def validate(cats: dict) -> bool:
    return all(cats.get(k) in v for k, v in ALL.items())


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


def llm_classify(transcript: str, model: str, fallback: str) -> dict | None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    for m in [model, fallback]:
        body = json.dumps({
            "model": m,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript[:8000]},
            ],
            "temperature": 0,
        }).encode()
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = json.loads(resp.read())
                content = data["choices"][0]["message"]["content"]
                match = re.search(r"\{[^{}]+\}", content, re.S)
                if not match:
                    continue
                cats = json.loads(match.group())
                if validate(cats):
                    return cats
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and attempt < 3:
                    time.sleep(min(2 ** attempt * 2, 30))
                    continue
                break
            except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError, TimeoutError):
                if attempt < 3:
                    time.sleep(2)
                    continue
                break
    return None


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
        from export_labels import export_labels
        export_labels(export)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Label meetings via OpenRouter LLM")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--export", nargs="?", const=str(ROOT / "data" / "labels_llm_v1.json"))
    args = parser.parse_args()
    export_path = Path(args.export) if args.export else None
    run(args.limit, export_path)
