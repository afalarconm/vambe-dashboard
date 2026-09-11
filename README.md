# Vambe Dashboard

Explorador de sales meetings sobre 10k discovery notes en español: filtra meetings, compara win rates, revisa los labels de Gemma.

**Live demo:** [vambe-dashboard-task.vercel.app](https://vambe-dashboard-task.vercel.app/) · [`/health`](https://vambe-dashboard-task.vercel.app/health)

**Arquitectura y decisiones:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Correr local

Necesitas Python 3.12 y Node ≥20.19 (lo pide Vite 8). Ninguna variable de entorno: el CSV y los labels están commiteados.

```bash
pip install -r requirements.txt
python scripts/bake_db.py     # CSV + labels JSON → data/meetings.db
cd apps/web && npm install && npm run build && cd ../..
uvicorn main:app --reload --port 8080
```

Abre [http://localhost:8080](http://localhost:8080).

<details>
<summary>Hot reload (API y UI en puertos separados)</summary>

```bash
# terminal 1
pip install -r requirements.txt
python scripts/bake_db.py
uvicorn main:app --reload --port 8000

# terminal 2
cd apps/web && npm run dev
# → http://localhost:5173  (Vite hace proxy de /api → FastAPI)
```

</details>

## Tests

```bash
python -m unittest discover apps
```

## Variables de entorno

Solo las usa el labeler offline ([re-labelear](docs/ARCHITECTURE.md#re-labelear-opcional)); la app en vivo no lee ninguna.

| Var | Default | Para qué |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Requerida para correr el labeler |
| `OPENROUTER_MODEL` | `google/gemma-3-27b-it` | Override del modelo primario |
