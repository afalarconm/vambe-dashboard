# Vambe Take-Home

Sales meeting explorer: ingest CSV → load labels → FastAPI + React dashboard.

## Setup

```bash
python scripts/ingest.py && python scripts/load_labels.py   # demo: 95 Gemma labels, no API key
```

Optional paths:

```bash
python scripts/categorize.py              # heuristic-v1 (~100 stratified)
export OPENROUTER_API_KEY=...             # never commit
python scripts/categorize.py --llm        # live LLM via OpenRouter
```

## Run

```bash
pip install -r apps/api/requirements.txt
uvicorn apps.api.main:app --reload --app-dir .

cd apps/web && npm install && npm run dev   # http://localhost:5173
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /meetings` | Paginated meetings + labels (filters: seller, closed, dims, q) |
| `GET /filters` | Distinct filter values |
| `GET /metrics/win-rate-by-job` | Win rate by `primary_job` |
| `GET /metrics/win-rate-by-handoff` | Win rate by `handoff_topology` |
| `GET /metrics/win-rate-by-trigger` | Win rate by `buying_trigger` |
| `GET /metrics/system-gravity-mix` | Count + share by `system_gravity` |

## Data

CSV: `data/vambe_clients_10k.csv` (~10k rows). Pre-exported LLM labels: `data/labels_llm_v1.json` (95 rows, `google/gemma-3-27b-it` / `llm-v1`).
