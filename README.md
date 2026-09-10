# Vambe Dashboard

Sales-meeting explorer over 10k Spanish transcripts: filter meetings, compare win rates, inspect Gemma labels.

**Live demo:** [temporary-sonic-violet-79ppfpr.vercel.app](https://temporary-sonic-violet-79ppfpr.vercel.app) · [`/health`](https://temporary-sonic-violet-79ppfpr.vercel.app/health)

## How it works

![Label, bake, serve](docs/how-it-works.png)

**Label → Bake → Serve.** Gemma classifies transcripts offline into a locked taxonomy. Build (local or Vercel) bakes the CSV and those labels into SQLite. FastAPI serves that file read-only — no LLM, no database server, no runtime env vars.

| Step | Where | What |
|------|--------|------|
| **Label** | `scripts/labeling/` | OpenRouter → `data/labels_llm_v1.json` |
| **Bake** | `scripts/bake_db.py` | CSV + JSON → `data/meetings.db` |
| **Serve** | `apps/api/` + `apps/web/` | Read-only API + React dashboard |

Seven locked dimensions live in `scripts/labeling/taxonomy.py`. The **Dimensions** tab is the glossary.

## Run locally

```bash
pip install -r requirements.txt
python scripts/bake_db.py
cd apps/web && npm install && npm run build && cd ../..
uvicorn main:app --reload --port 8080
```

Open [http://localhost:8080](http://localhost:8080).

<details>
<summary>Hot reload (API and UI on separate ports)</summary>

```bash
# terminal 1
pip install -r requirements.txt
python scripts/bake_db.py
uvicorn main:app --reload --port 8000

# terminal 2
cd apps/web && npm run dev
# → http://localhost:5173  (Vite proxies /api → FastAPI)
```

</details>

## Relabel (optional)

Needs `OPENROUTER_API_KEY`. Bake again afterwards.

```bash
python -m scripts.labeling.label_meetings --limit 100 --export
python scripts/bake_db.py
```

`--export` writes `data/labels_llm_v1.json`. Re-export from the DB with `python -m scripts.labeling.export_labels`.

## API

| Endpoint | Returns |
|----------|---------|
| `GET /health` | `{ok, llm_labels, total_meetings}` |
| `GET /meetings` | Paginated meetings + labels |
| `GET /filters` | Distinct filter values |
| `GET /metrics/win-rate-by-job` | Win rate by `primary_job` |
| `GET /metrics/win-rate-by-handoff` | Win rate by `handoff_topology` |
| `GET /metrics/win-rate-by-trigger` | Win rate by `buying_trigger` |
| `GET /metrics/win-rate-by-volume-band` | Win rate by `volume_band` |
| `GET /metrics/system-gravity-mix` | Share by `system_gravity` |
| `GET /metrics/job-handoff-heatmap` | Win rate: `primary_job` × `handoff_topology` |
