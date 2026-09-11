import json
import os
import re
import time
import urllib.error
import urllib.request

from scripts.labeling.taxonomy import ALL

_SHAPE = "{" + ",".join(f'"{k}":"..."' for k in ALL) + ',"volume_amount":null}'
_VALUES = "\n".join(f"{k}: {'|'.join(v)}" for k, v in ALL.items())

SYSTEM_PROMPT = f"""Classify sales meeting transcripts into fixed categories. Reply JSON only:
{_SHAPE}
Valid values:
{_VALUES}

volume_amount: the message/enquiry volume the lead states, as a plain integer, in
the SAME unit they said it. Do not convert between days, weeks and months. Do not
do any arithmetic. For a range, use the higher number. If they state no volume,
use null and set volume_period to "unspecified".
Examples: "300 consultas diarias" -> volume_amount 300, volume_period "daily".
"entre 800 y 1500 al mes" -> volume_amount 1500, volume_period "monthly".
"150 tickets semanales" -> volume_amount 150, volume_period "weekly".
"400 consultas anuales" -> volume_amount 400, volume_period "yearly"."""

MAX_VOLUME = 1_000_000


def normalize(cats: dict) -> dict:
    """Accept the shapes models reach for around a number: "300", 300.0, "".*"""
    amount = cats.get("volume_amount")
    if isinstance(amount, bool):
        amount = None
    elif isinstance(amount, str):
        digits = re.sub(r"[^\d]", "", amount)
        amount = int(digits) if digits else None
    elif isinstance(amount, float):
        amount = int(amount)
    elif not isinstance(amount, int):
        amount = None
    cats["volume_amount"] = amount
    return cats


def validate(cats: dict) -> bool:
    if not all(cats.get(k) in v for k, v in ALL.items()):
        return False
    amount = cats.get("volume_amount")
    if amount is None:
        return True
    return isinstance(amount, int) and 0 < amount <= MAX_VOLUME


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
                cats = normalize(json.loads(match.group()))
                if validate(cats):
                    return cats
                continue
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
