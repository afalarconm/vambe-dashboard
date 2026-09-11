# Arquitectura y decisiones

## Cómo funciona

![Label, build, serve](how-it-works.png)

El labeling corre una sola vez, offline. La app en vivo solo lee un SQLite ya generado — sin API key, sin llamadas a un LLM en cada request.

| Step | Dónde | Qué hace |
|---|---|---|
| **Label** | `scripts/labeling/` | Sample de transcripts en SQLite → OpenRouter (Gemma) → `labels_llm_v1.json` |
| **Build** | `scripts/bake_db.py` | CSV + ese JSON → `data/meetings.db` |
| **Serve** | `apps/api/` + `apps/web/` | API read-only + dashboard en React |

Al clonar el repo, `bake_db.py` corre una sola vez: los labels ya vienen versionados y el script carga el CSV y el JSON en la misma pasada. Las dos pasadas son el loop de autoría — generar la DB para que el labeler tenga qué leer, correr el labeling, y volver a generarla.

## Estructura del repo

```
.
├── main.py              entry point de Vercel → apps.api.main:app
├── vercel.json          config de deploy (incluye data/meetings.db en la función)
├── apps/
│   ├── api/             FastAPI: endpoints read-only sobre data/meetings.db, + tests
│   └── web/             React + Vite: filtros, charts, tabla, drawer de transcripts
├── scripts/
│   ├── bake_db.py       CSV + labels_llm_v1.json → data/meetings.db
│   ├── labeling/        labeling offline vía OpenRouter: taxonomía, prompt, cliente, export
│   └── vercel_build.sh  build de deploy: compila apps/web y corre bake_db.py
├── data/                CSV + labels_llm_v1.json (versionados); meetings.db se genera
└── docs/                este doc + el diagrama
```

`scripts/labeling/` es el único que le habla a un LLM y el único que necesita `OPENROUTER_API_KEY`; corre offline, a mano, nunca dentro de un request. `apps/api/` abre la DB read-only y no sabe qué es un LLM. `apps/web/` solo le habla a `apps/api/` — mismo origin en prod, proxy de Vite en dev. Si un componente no necesita un secret o un side effect, no lo tiene.

## Decisiones

- **Python para el pipeline y la API.** El labeler ya es Python contra stdlib pura (`csv`, `sqlite3`, `urllib` — cero deps de HTTP). Servir con FastAPI deja un solo runtime que genera la DB y la sirve, en un solo deploy; las únicas deps de backend son `fastapi` y `uvicorn`.
- **React + Vite para el dashboard.** Tabla, charts y heatmap comparten un set de filtros: eso es client state de verdad, no una página estática. Vite compila a estáticos que sirve el mismo FastAPI, así que no hay CORS ni un segundo deploy.
- **SQLite, no Postgres.** El read model es de solo lectura, 10k filas, y se regenera en cada build. Un servicio de DB no compraría nada; el archivo viaja adentro del bundle de la función.
- **El id de cada meeting sale del contenido, no de la fila.** `stable_id()` es un sha256 de `email|phone|fecha` (`bake_db.py:15`), así que re-ordenar el CSV o insertar filas no mueve los labels y volver a correr el build es idempotente — cero colisiones en las 10.000 filas. Por eso el labeler lee desde SQLite y no desde el CSV: necesita ese id para que la etiqueta apunte a algo estable.
- **La DB se arma en build time, no se versiona.** `data/meetings.db` está en `.gitignore`; el CSV y `labels_llm_v1.json` son el artifact versionado. El costo: volver a correr el labeling exige un redeploy.
- **Los charts usan los mismos filtros que la tabla.** `GET /metrics` toma los mismos query params que `GET /meetings`.

## Dimensiones — qué y por qué

Las filas del CSV son discovery notes cortas en español, no transcripts completos de llamada — así que lo que vale la pena categorizar es el deal, no el estilo de la conversación. Hay seis dimensiones en `scripts/labeling/taxonomy.py` (el tab **Dimensiones** de la app es el glosario, con un gloss por valor):

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
- **Sample estratificado.** `label_meetings.py` saca mitad de reuniones cerradas y mitad abiertas, para que ambos resultados queden representados en cada dimensión en vez de sesgarse hacia lo más común.
- **Se valida, no se confía.** Cada respuesta se chequea contra el set de enums fijo (`openrouter_client.validate`); un valor fuera de eso se rechaza. Los retries usan backoff exponencial en rate limits/timeouts (4 intentos) antes de caer al modelo secundario; un transcript que falla en ambos se descarta en vez de guardarse con un label adivinado.
- **La cobertura es en vivo, no un número fijo.** `GET /health` muestra el `llm_labels` actual sobre `total_meetings` — revisa ese endpoint en vez de confiar en un número de este doc. El filtro "Cobertura" del dashboard muestra por default solo las filas labeled, y cada barra de win rate / celda del heatmap muestra su propio `n` (atenuado bajo un mínimo de 5) para que un rate con poco sample nunca se lea como uno confiable.

## Volver a correr el labeling (opcional)

Necesita una DB ya generada (ver README) y `OPENROUTER_API_KEY`. El labeler lee los transcripts que ya están en SQLite; después corre el build de nuevo para recargar el JSON.

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
