import json
import os
import re
import time
import urllib.error
import urllib.request

from scripts.labeling.taxonomy import ALL

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
