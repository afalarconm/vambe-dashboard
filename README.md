# Vambe Dashboard

Explorador de sales meetings sobre 10k discovery notes en español: filtra meetings, compara win rates, revisa los labels de Gemma. Los filtros viven en la URL, así que cualquier vista filtrada es un link que se comparte.

**Live demo:** [vambe-dashboard-task.vercel.app](https://vambe-dashboard-task.vercel.app/) · [`/health`](https://vambe-dashboard-task.vercel.app/health)

**Arquitectura y decisiones:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Correr local

Necesitas Python 3.12 y Node ≥20.19 (lo pide Vite 8). Ninguna variable de entorno: el CSV y los labels están versionados en el repo.

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
python -m unittest apps.api.test_metrics scripts.test_pipeline
```

Y para medir la calidad de los labels de volumen contra los transcripts:

```bash
python scripts/audit_volume_labels.py
```

## Variables de entorno

Solo las usa el labeler offline ([volver a correr el labeling](docs/ARCHITECTURE.md#volver-a-correr-el-labeling-opcional)); la app en vivo no lee ninguna. El labeler lee un `.env` en la raíz si existe.

| Var | Default | Para qué |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Requerida para correr el labeler |
| `OPENROUTER_MODEL` | `google/gemma-3-27b-it` | Override del modelo primario |
