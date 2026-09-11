# Vambe Dashboard

Explorador de sales meetings sobre 10k transcripts en español: filtra meetings, compara win rates, revisa los labels de Gemma.

**Live demo:** [vambe-dashboard-task.vercel.app](https://vambe-dashboard-task.vercel.app/) · [`/health`](https://vambe-dashboard-task.vercel.app/health)

**Arquitectura y decisiones:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Correr local

```bash
pip install -r requirements.txt
python scripts/bake_db.py
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
