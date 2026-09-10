# Vambe Take-Home

Sales meeting explorer: ingest CSV → load labels → FastAPI + React dashboard.

## Live demo

**https://journal-abraham-buys-armed.trycloudflare.com**

Single-service deploy: FastAPI serves API + built Vite static files. DB baked at build time (10k meetings, 95 Gemma `llm-v1` labels). No OpenRouter at runtime.

> Quick-tunnel URL — ephemeral while the host VM runs. For a permanent URL, use Deploy below.

## Setup (local)

```bash
python scripts/ingest.py && python scripts/load_labels.py
pip install -r apps/api/requirements.txt
cd apps/web && npm install && npm run build
uvicorn apps.api.main:app --host 0.0.0.0 --port 8080 --app-dir .
# → http://localhost:8080
```

Dev with HMR: `cd apps/web && npm run dev` (proxies `/api` → port 8000).

Optional: `python scripts/categorize.py` (heuristic) or `python scripts/categorize.py --llm` (OpenRouter).

## Deploy

**Docker** (Render, Fly, Railway, etc.):

```bash
docker build -t vambe-dashboard .
docker run -p 8080:8080 vambe-dashboard
```

**Fly.io** (persistent HTTPS):

```bash
fly auth login
fly launch --copy-config --yes    # uses fly.toml
fly deploy
```

**Render**: connect repo → New Web Service → Docker → uses `render.yaml`.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | `{ok, llm_labels}` |
| `GET /meetings` | Paginated meetings + labels (filters: seller, closed, dims, q) |
| `GET /filters` | Distinct filter values |
| `GET /metrics/win-rate-by-job` | Win rate by `primary_job` |
| `GET /metrics/win-rate-by-handoff` | Win rate by `handoff_topology` |
| `GET /metrics/win-rate-by-trigger` | Win rate by `buying_trigger` |
| `GET /metrics/system-gravity-mix` | Count + share by `system_gravity` |
