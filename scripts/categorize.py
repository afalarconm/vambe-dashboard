#!/usr/bin/env python3
import argparse
import json
import os
import random
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enums import ALL

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "meetings.db"

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

KEYWORDS = {
    "primary_job": {
        "scheduling_booking": r"cita|agendar|reserva|calendario|horario|turno|agenda",
        "catalog_guided_selling": r"catálogo|catalogo|producto|recomend|mostrar|vitrina",
        "quoting_pricing": r"cotiz|precio|presupuesto|tarifa|costo",
        "order_taking": r"pedido|orden|comprar|checkout|carrito",
        "claims_intake": r"reclamo|queja|siniestro|devolución|devolucion",
        "shipment_tracking": r"envío|envio|seguimiento|rastreo|tracking|despacho",
        "lead_qualification": r"prospecto|calificar|lead|calificación|calificacion",
        "faq_education": r"pregunta|informar|educar|faq|consulta general",
    },
    "handoff_topology": {
        "book_specialist": r"especialista|experto|agendar con",
        "role_based_routing": r"departamento|área|area|routing|derivar a",
        "generic_human_handoff": r"agente humano|persona real|operador|humano",
        "bot_only_implied": r"automat|bot|sin intervención|sin intervencion|24.?7",
    },
    "system_gravity": {
        "must_integrate": r"integrar|integración|integracion|api|conectar|sincroniz",
        "named_system_desired": r"salesforce|hubspot|crm|sap|zoho|shopify",
        "standalone_ok": r"independiente|standalone|por sí solo|por si solo",
    },
    "trust_surface": {
        "health_sensitive": r"clínica|clinica|salud|médic|medic|paciente|dental|hospital",
        "regulated_advice_boundary": r"legal|financier|asesoría|asesoria|jurídic|juridic|compliance",
        "discretion_prestige": r"lujo|exclusiv|prestigio|premium|boutique|high.?end",
    },
    "voice_contract": {
        "warm_hospitable": r"cálido|calido|hospital|amable|acogedor",
        "corporate_expert": r"corporativ|profesional|formal|experto",
        "motivational_energetic": r"motivacional|energétic|energetic|dinámic|dinamic",
        "luxury_prestige": r"lujo|prestigio|elegante|sofisticad",
        "care_trustworthy": r"confianza|cuidado|empátic|empatic|tranquil",
        "brand_custom": r"marca|personaliz|identidad|tono propio",
    },
    "buying_trigger": {
        "ops_saturation": r"saturad|no damos abasto|colaps|desbordad|sobrecarg",
        "coverage_gap": r"fuera de horario|no contest|perdemos llamada|horario limitado",
        "growth_ambition": r"crecer|expandir|escalar|crecimiento|nuevas sucursal",
        "budget_cautious": r"presupuesto|económic|econom|barato|costo.?beneficio",
        "efficiency_general": r"eficiencia|optimiz|automatiz|productividad",
    },
}


def match_dim(text: str, dim: str, default: str) -> str:
    best, score = default, 0
    for val, pat in KEYWORDS.get(dim, {}).items():
        n = len(re.findall(pat, text, re.I))
        if n > score:
            score, best = n, val
    return best


def volume_from_text(text: str) -> str:
    nums = [int(n.replace(".", "").replace(",", "")) for n in re.findall(r"\d[\d.,]*", text)]
    big = max(nums) if nums else 0
    if big >= 2000:
        return "2000_plus_mo"
    if big >= 500:
        return "500_1999_mo"
    if big >= 100:
        return "100_499_mo"
    if big > 0 and big < 100:
        return "lt_100_mo"
    return "unspecified"


def heuristic(text: str) -> dict:
    t = text.lower()
    return {
        "primary_job": match_dim(t, "primary_job", "faq_education"),
        "handoff_topology": match_dim(t, "handoff_topology", "generic_human_handoff"),
        "system_gravity": match_dim(t, "system_gravity", "standalone_ok"),
        "trust_surface": match_dim(t, "trust_surface", "standard"),
        "voice_contract": match_dim(t, "voice_contract", "not_specified"),
        "buying_trigger": match_dim(t, "buying_trigger", "efficiency_general"),
        "volume_band": volume_from_text(t),
    }


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


def save_category(conn, meeting_id: int, cats: dict, model: str, prompt_version: str):
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
            prompt_version,
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
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())
                content = data["choices"][0]["message"]["content"]
                match = re.search(r"\{[^{}]+\}", content, re.S)
                if not match:
                    continue
                cats = json.loads(match.group())
                if validate(cats):
                    return cats
            except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError):
                if attempt == 0:
                    continue
    return None


def run(use_llm: bool):
    random.seed(42)
    conn = sqlite3.connect(DB_PATH)
    ids = stratified_sample(conn)
    model = os.environ.get("OPENROUTER_MODEL", "google/gemma-3-27b-it")
    fallback = "google/gemini-2.0-flash-001"
    prompt_version = "llm-v1" if use_llm else "heuristic-v1"
    label_model = model if use_llm else "heuristic"

    ok, skip = 0, 0
    for mid in ids:
        transcript = conn.execute("SELECT transcript FROM meetings WHERE id=?", (mid,)).fetchone()[0]
        if use_llm:
            cats = llm_classify(transcript, model, fallback)
            if not cats:
                skip += 1
                continue
        else:
            cats = heuristic(transcript)
        save_category(conn, mid, cats, label_model, prompt_version)
        ok += 1

    conn.commit()
    conn.close()
    mode = "LLM" if use_llm else "heuristic"
    print(f"{mode}: labeled {ok}, skipped {skip}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    run(args.llm)
