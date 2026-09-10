# Vambe Take-Home

Sales meeting explorer: ingest CSV → categorize transcripts → FastAPI + React dashboard.

## Setup

```bash
# ingest CSV into SQLite
python scripts/ingest.py

# categorize ~100 stratified meetings (heuristic, no API key needed)
python scripts/categorize.py

# optional: LLM categorization via OpenRouter
export OPENROUTER_API_KEY=sk-...
python scripts/categorize.py --llm
# override model: OPENROUTER_MODEL=google/gemma-3-27b-it
```

## Run

```bash
# API (port 8000)
pip install -r apps/api/requirements.txt
uvicorn apps.api.main:app --reload --app-dir .

# Web (port 5173, proxies /api → 8000)
cd apps/web && npm install && npm run dev
```

Open http://localhost:5173

## Decisions

- **Stable IDs**: SHA-256 hash of email|phone|date — re-ingest is idempotent.
- **Categorization**: Default Spanish keyword heuristics (`heuristic-v1`); optional OpenRouter LLM (`llm-v1`) with enum validation and one retry. Stratified sample: ~50 closed + ~50 open.
- **API**: SQLite, no ORM. Filters join meetings ↔ categories. CORS for Vite dev.
- **Frontend**: Single-page filters + table + Recharts win-rate bar chart. No state library.

## Data

CSV fetched from ClickUp attachment (~10k rows, UTF-8 BOM). Columns: Nombre, Correo Electronico, Numero de Telefono, Fecha de la Reunion, Vendedor asignado, closed, Transcripcion.
