# Vambe Take-Home

**Live demo:** [temporary-sonic-violet-79ppfpr.vercel.app](https://temporary-sonic-violet-79ppfpr.vercel.app) — check [`/health`](https://temporary-sonic-violet-79ppfpr.vercel.app/health)

Sales meeting explorer over Spanish transcripts: filter meetings, compare win rates by category, inspect Gemma labels.

## Run locally

```bash
pip install -r requirements.txt
python scripts/bake_db.py
cd apps/web && npm install && npm run build && cd ../..
uvicorn main:app --reload --port 8080
# → http://localhost:8080
```

**Dev (HMR)** — API and UI on separate ports; Vite proxies `/api` → FastAPI:

```bash
# terminal 1
pip install -r requirements.txt
python scripts/bake_db.py
uvicorn main:app --reload --port 8000

# terminal 2
cd apps/web && npm run dev
# → http://localhost:5173
```

## Architecture

**Label → Bake → Serve** — offline batch labeling, baked read model, read-only API at runtime.

```
                    ┌─ Label (offline, optional) ─────────────────────┐
                    │  OpenRouter LLM → data/labels_llm_v1.json       │
                    └─────────────────────────────────────────────────┘
                                          │
CSV ──Bake──► SQLite (meetings + categories) ◄── labels_llm_v1.json
                    │
FastAPI (apps/api) ◄── read-only ────┘
       │
       ├── JSON /meetings, /filters, /metrics/*
       └── static ──► React (apps/web/dist)
```

| Step | Script | Role |
|------|--------|------|
| **Label** | `scripts/labeling/` | Offline OpenRouter batch → `data/labels_llm_v1.json` |
| **Bake** | `scripts/bake_db.py` | CSV ingest + load labels into SQLite |
| **Serve** | `apps/api/` + `main.py` | Read-only queries; no LLM at runtime |

**Stack:** FastAPI + Vite split monorepo — Python owns the offline pipeline and SQLite; React owns the dashboard. Thin read API + baked SQLite keeps the demo easy to skim and run.

| Layer | Role |
|-------|------|
| `scripts/labeling/` | Offline LLM labeling (taxonomy, OpenRouter client, batch CLI) |
| `scripts/bake_db.py` | Build-time bake: CSV + labels JSON → SQLite |
| `apps/api/` | Read-only SQLite queries, CORS, metrics |
| `apps/web/` | Vite + React dashboard (Recharts) |
| `main.py` | Vercel entrypoint (`from apps.api.main import app`) |

### Dimensions (7)

Six locked taxonomy values (`scripts/labeling/taxonomy.py`) plus derived volume — one line per axis:

| Dimension | Why |
|-----------|-----|
| `primary_job` | Maps discovery notes to the bot capability the prospect wants (booking, catalog, quoting, FAQ…); packaging/demo for Sales + feature demand for Product. |
| `handoff_topology` | How the bot involves humans (bot-only, generic, specialist, role-based); implementation shape + win-rate lever. |
| `system_gravity` | How glued to existing systems (standalone → named → must integrate); SE load / cycle-time / delivery cost. |
| `trust_surface` | Domain sensitivity (standard → health → regulated → discretion); compliance tone, guardrails, approval. |
| `voice_contract` | Expected bot tone; delivery constraint / brand fit — wrong voice kills a good demo. |
| `buying_trigger` | Why shopping now; seller coaching / pipeline quality. |
| `volume_band` | Normalize stated WhatsApp volume into bands for capacity/pricing/win-rate without inventing numbers. |

Fixed taxonomy keeps LLM output validatable and metrics comparable across meetings.

### Labels (offline only)

Offline Gemma batch → `data/labels_llm_v1.json` → Vercel build runs `bake_db.py` into read-only SQLite. UI never calls OpenRouter — reproducible deploys, no prod API key.

Optional re-labeling (requires `OPENROUTER_API_KEY`; run Bake after to refresh SQLite):

```bash
export OPENROUTER_API_KEY=your_key
python -m scripts.labeling.label_meetings --limit 100 --export
python scripts/bake_db.py
```

- **Batch:** `--limit N` controls sample size; progress logged every 25 rows; retries on 429/503.
- **Export:** `--export` writes `data/labels_llm_v1.json` (committed artifact).
- **Re-export:** `python -m scripts.labeling.export_labels` dumps DB → JSON.

### Metrics

Win rate × `primary_job` / `handoff_topology` / `buying_trigger` + `system_gravity` mix — each chart maps to a Vambe role (Product, Solutions, Sales, SE). All metrics use LLM categories only.

### Key decisions

- **Baked labels, no LLM at runtime** — offline Gemma → JSON → SQLite at build; production serves pre-labeled data only.
- **FastAPI + Vite split** — Python pipeline vs React dashboard; single process in prod, separate ports in dev.
- **Enum-locked taxonomy** — schema validation on LLM JSON; comparable metrics across meetings.
- **Read-only runtime DB** — `mode=ro` URI; labeling/bake are build-time or dev-only scripts.
- **SQLite table `categories`** — kept for API stability; script layer uses "labels" terminology.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | `{ok, llm_labels}` |
| `GET /meetings` | Paginated meetings + labels |
| `GET /filters` | Distinct filter values |
| `GET /metrics/win-rate-by-job` | Win rate by `primary_job` |
| `GET /metrics/win-rate-by-handoff` | Win rate by `handoff_topology` |
| `GET /metrics/win-rate-by-trigger` | Win rate by `buying_trigger` |
| `GET /metrics/system-gravity-mix` | Share by `system_gravity` |
| `GET /metrics/win-rate-by-volume-band` | Win rate by `volume_band` |
| `GET /metrics/job-handoff-heatmap` | Win rate matrix: `primary_job` × `handoff_topology` |
