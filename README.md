# Vambe Take-Home

Sales meeting explorer: ingest CSV → load labels → FastAPI + React dashboard.

## Vercel deploy

1. Import **afalarconm/vambe-dashboard** (GitHub or Git URL) in [Vercel](https://vercel.com/new)
2. Framework preset: **Other** (auto-detects FastAPI via `main.py`)
3. Root directory: **`.`** (repo root)
4. Build/install commands are in `vercel.json` + `pyproject.toml` — no extra env vars needed
5. Deploy — build runs `npm run build`, `ingest`, `load_labels`; SQLite is read-only at runtime

No OpenRouter at runtime. Demo serves 95 Gemma `llm-v1` labels from baked `data/meetings.db`.

## Local

```bash
python scripts/ingest.py && python scripts/load_labels.py
pip install -r requirements.txt
cd apps/web && npm install && npm run build
uvicorn main:app --reload --port 8080
# → http://localhost:8080
```

Dev with HMR: `cd apps/web && npm run dev` (proxies `/api` → port 8000; run API separately).

Optional — re-run LLM labeling (requires `OPENROUTER_API_KEY`):

```bash
export OPENROUTER_API_KEY=your_key
python scripts/categorize.py --limit 100 --export
python scripts/load_labels.py
```

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

## Other deploy

Docker: `docker build -t vambe-dashboard . && docker run -p 8080:8080 vambe-dashboard`
