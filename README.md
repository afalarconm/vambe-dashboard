# Vambe Dashboard

Explorador de sales meetings sobre 10k transcripts en español: filtra meetings, compara win rates, revisa los labels de Gemma.

**Live demo:** [vambe-dashboard-task.vercel.app](https://vambe-dashboard-task.vercel.app/) · [`/health`](https://vambe-dashboard-task.vercel.app/health)

## Cómo funciona

![Label, bake, serve](docs/how-it-works.png)

El labeling corre una sola vez, offline. La app en vivo solo lee un SQLite ya baked — sin API key, sin llamadas a un LLM en cada request.

| Step | Dónde | Qué hace |
|------|--------|------|
| **Label** | `scripts/labeling/` | Un sample de transcripts en SQLite → OpenRouter (Gemma) → `labels_llm_v1.json` |
| **Bake** | `scripts/bake_db.py` | CSV + ese JSON → `data/meetings.db` |
| **Serve** | `apps/api/` + `apps/web/` | API read-only + dashboard en React |

El bake corre dos veces en la práctica: primero carga el CSV en `meetings` (para que el labeler tenga transcripts que leer), y después de labelear carga `labels_llm_v1.json` en `categories`.

## Dimensiones — qué y por qué

Las filas del CSV son discovery notes cortas en español, no transcripts completos de llamada — así que lo que vale la pena categorizar es el deal, no el estilo de la conversación. Hay siete dimensiones en `scripts/labeling/taxonomy.py` (el tab **Dimensiones** de la app es el glosario, con un gloss por valor):

| Dimensión | Qué captura | Por qué importa |
|---|---|---|
| `primary_job` | La capacidad del bot que el lead realmente quiere (agendamiento, catálogo/venta guiada, cotización, toma de pedidos, reclamos, tracking, calificación de leads, FAQ) | Señal de packaging para Ventas, de demanda de features para Producto |
| `handoff_topology` | Cuánto se espera que el bot derive a un humano | Define la forma de la implementación y el win rate resultante |
| `system_gravity` | Qué tan atado está el pedido a sistemas existentes (standalone-OK → debe integrarse) | Determina la carga de ingeniería de soluciones y el costo de implementación |
| `trust_surface` | Sensibilidad del rubro (estándar, salud, regulado, discreción/prestigio) | Define el nivel de compliance y quién tiene que aprobar |
| `buying_trigger` | Por qué están comprando ahora (saturación operativa, brecha de cobertura, crecimiento, cautela de presupuesto, eficiencia general) | Alimenta el coaching de vendedores y la lectura de calidad del pipeline |
| `volume_band` | Volumen de WhatsApp declarado, normalizado | Señal comparable de capacidad/pricing entre leads |

## Labeling con LLM

- **Modelo:** `google/gemma-3-27b-it` vía OpenRouter, temperature 0, con system prompt de enum fijo; si la respuesta de Gemma no valida, cae a `google/gemini-2.0-flash-001`. El transcript se trata como contenido no confiable — el prompt nunca sigue instrucciones metidas ahí.
- **Sample, no los 10k completos.** El brief permite labelear un segmento si el costo es alto. `label_meetings.py` saca un **sample estratificado** (mitad cerradas, mitad abiertas) para que ambos resultados queden representados en cada dimensión, en vez de sesgarse hacia lo más común en un slice random.
- **Se valida, no se confía.** Cada respuesta se chequea contra el set de enums fijo (`openrouter_client.validate`); un valor fuera de eso se rechaza. Los retries usan backoff exponencial en rate limits/timeouts (4 intentos) antes de caer al modelo secundario; un transcript que falla en ambos se skipea en vez de guardarse con un label adivinado.
- **La cobertura es en vivo, no un número fijo.** `GET /health` muestra el `llm_labels` actual sobre `total_meetings` — revisa ese endpoint en vez de confiar en un número de este doc. El filtro "Cobertura" del dashboard muestra por default solo las filas labeled, y cada barra de win rate / celda del heatmap muestra su propio `n` (atenuado bajo un mínimo de 5) para que un rate con poco sample nunca se lea como uno confiable.

## Decisiones clave

- **Labelear offline, servir read-only.** OpenRouter corre en `scripts/labeling/`, nunca en un request. El demo en vivo no necesita API key.
- **Bake de SQLite desde CSV + labels JSON.** La DB está en `.gitignore`; los labels son el artifact que se commitea.
- **Los charts usan los mismos filtros que la tabla.** `GET /metrics` toma los mismos query params que `GET /meetings`.
- **El sample size se muestra, no se esconde.** Los charts de win rate muestran su `n` y atenúan barras/celdas bajo 5 meetings — con solo unos cientos de filas labeled, un porcentaje sin contexto sobrestimaría la confianza.

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

## Re-labelear (opcional)

Necesita una DB ya baked y `OPENROUTER_API_KEY`. El labeler lee los transcripts que ya están en SQLite; después bake de nuevo para recargar el JSON.

```bash
python -m scripts.labeling.label_meetings --limit 100 --export
python scripts/bake_db.py
```

`--export` escribe `data/labels_llm_v1.json`. Re-exporta desde la DB con `python -m scripts.labeling.export_labels`.

## API

| Endpoint | Devuelve |
|----------|---------|
| `GET /health` | `{ok, llm_labels, total_meetings}` |
| `GET /meetings` | Meetings paginados + labels (filtros: seller, closed, dimensiones, `q`, `labeled_only`) |
| `GET /filters` | Valores distintos para los filtros |
| `GET /metrics` | Series de win rate, mezcla de gravity, heatmap job × handoff — mismos filtros que `/meetings` |
