# Vambe Take-Home

**Live demo:** [temporary-sonic-violet-79ppfpr.vercel.app](https://temporary-sonic-violet-79ppfpr.vercel.app) — check [`/health`](https://temporary-sonic-violet-79ppfpr.vercel.app/health) (`llm_labels: 971`)

Sales meeting explorer over ~10k Spanish transcripts: filter meetings, compare win rates by category, inspect Gemma labels.

## Run locally

```bash
pip install -r requirements.txt
python scripts/ingest.py
python scripts/load_labels.py
cd apps/web && npm install && npm run build && cd ../..
uvicorn main:app --reload --port 8080
# → http://localhost:8080
```

**Dev (HMR)** — API and UI on separate ports; Vite proxies `/api` → FastAPI:

```bash
# terminal 1
pip install -r requirements.txt
python scripts/ingest.py && python scripts/load_labels.py
uvicorn main:app --reload --port 8000

# terminal 2
cd apps/web && npm run dev
# → http://localhost:5173
```

## Architecture

```
CSV ──ingest──► SQLite (meetings)
labels_llm_v1.json ──load_labels──► SQLite (categories)
                                      │
FastAPI (apps/api) ◄── read-only ────┘
       │
       ├── JSON /meetings, /filters, /metrics/*
       └── static ──► React (apps/web/dist)
```

| Layer | Role |
|-------|------|
| `scripts/` | Offline data + labeling pipeline |
| `apps/api/` | Read-only SQLite queries, CORS, metrics |
| `apps/web/` | Vite + React dashboard (Recharts) |
| `main.py` | Vercel entrypoint (`from apps.api.main import app`) |

### Category dimensions

Seven fields per meeting — six locked enums (`scripts/enums.py`) plus derived volume:

| Dimension | Why |
|-----------|-----|
| `primary_job` | Core bot job (scheduling, quoting, FAQ, …) — drives product-fit charts |
| `handoff_topology` | Bot-only vs human routing — affects deployment complexity |
| `system_gravity` | Standalone vs named CRM vs must-integrate — integration signal |
| `trust_surface` | Standard vs health/legal/luxury — compliance & tone constraints |
| `voice_contract` | Brand voice expectation when stated |
| `buying_trigger` | Why they’re buying (saturation, coverage gap, growth, …) |
| `volume_band` | Monthly inquiry volume parsed from transcript numbers |

Fixed enums keep LLM output validatable and metrics comparable across meetings.

### Labeling (offline only)

| Mode | Command | Use |
|------|---------|-----|
| Heuristic | `python scripts/categorize.py` | Regex/keyword demo, no API key |
| LLM | `OPENROUTER_API_KEY=… python scripts/categorize.py --llm --limit 100 --export` | Gemma via OpenRouter; stratified 50/50 closed/open sample |

- **Batch:** `--limit N` controls sample size; progress logged every 25 rows; retries on 429/503.
- **Export:** `--export` writes `data/labels_llm_v1.json` (committed artifact, 971 `llm-v1` rows).
- **Load:** `python scripts/load_labels.py` bakes JSON into SQLite.
- **Re-export:** `python scripts/export_labels.py` dumps DB → JSON.

Production never calls OpenRouter — it serves pre-baked labels only.

### Vercel deploy

Build (`scripts/vercel_build.sh`): `npm run build` → `ingest` → `load_labels`. SQLite is gitignored; generated at build and bundled read-only (`vercel.json` `includeFiles`). No runtime env vars required.

### Key decisions

- **SQLite + baked JSON** — zero managed DB on serverless; reproducible deploys from git.
- **Separate API / UI** — FastAPI for data; React for filters and charts; single process serves both in prod.
- **Enum-locked taxonomy** — schema validation on LLM JSON; heuristic fallback for local demos.
- **Read-only runtime DB** — `mode=ro` URI; ingest/labeling are build-time or dev-only scripts.

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
