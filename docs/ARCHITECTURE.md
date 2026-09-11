# Arquitectura y decisiones

## Cómo funciona

![Label, build, serve](how-it-works.png)

El labeling corre una sola vez, offline. La app en vivo solo lee un SQLite ya generado — sin API key, sin llamadas a un LLM en cada request.

| Step | Dónde | Qué hace |
|---|---|---|
| **Label** | `scripts/labeling/` | Sample de transcripts en SQLite → OpenRouter (Gemma) → `labels_llm_v1.json` |
| **Build** | `scripts/bake_db.py` | CSV + ese JSON → `data/meetings.db` |
| **Serve** | `apps/api/` + `apps/web/` | API read-only + dashboard en React |

El build corre dos veces en la práctica: primero carga el CSV en `meetings` (para que el labeler tenga transcripts que leer), y de nuevo después de labelear, para cargar `labels_llm_v1.json` en `categories`.

## Estructura del repo

| Path | Qué hay ahí |
|---|---|
| `apps/api/` | FastAPI — endpoints read-only sobre `data/meetings.db` (`main.py`) |
| `apps/web/` | Dashboard en React + Vite: filtros, charts, tabla, drawer de transcripts |
| `scripts/labeling/` | Labeling offline vía OpenRouter — taxonomía, prompt, cliente, export |
| `scripts/bake_db.py` | Arma `data/meetings.db` desde el CSV + `labels_llm_v1.json` |
| `data/` | CSV fuente + `labels_llm_v1.json` (commiteados); `meetings.db` se genera en build time y vive en `.gitignore` |
| `docs/` | Este doc + el diagrama de arquitectura |
| `main.py` | Entry point de FastAPI para Vercel — sirve la API y el build estático del dashboard |
| `vercel.json`, `scripts/vercel_build.sh` | Config de deploy: el build corre `bake_db.py` y compila `apps/web` |

## Los tres componentes, y sus límites

- **`scripts/labeling/`** es el único lugar que le habla a un LLM. Corre offline, a mano, nunca en un request — necesita `OPENROUTER_API_KEY`.
- **`apps/api/`** sirve `data/meetings.db` en modo read-only. No sabe qué es un LLM, no tiene la API key, no escribe nada.
- **`apps/web/`** (React) solo le habla a `apps/api` — mismo origin en prod, proxy de Vite en dev. Nunca toca OpenRouter ni la DB directamente.

Cada límite es intencional: si un componente no necesita un secret o un side effect, no lo tiene.

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
- **Sample estratificado.** `label_meetings.py` saca mitad de reuniones cerradas y mitad abiertas, para que ambos resultados queden representados en cada dimensión en vez de sesgarse hacia lo más común.
- **Se valida, no se confía.** Cada respuesta se chequea contra el set de enums fijo (`openrouter_client.validate`); un valor fuera de eso se rechaza. Los retries usan backoff exponencial en rate limits/timeouts (4 intentos) antes de caer al modelo secundario; un transcript que falla en ambos se skipea en vez de guardarse con un label adivinado.
- **La cobertura es en vivo, no un número fijo.** `GET /health` muestra el `llm_labels` actual sobre `total_meetings` — revisa ese endpoint en vez de confiar en un número de este doc. El filtro "Cobertura" del dashboard muestra por default solo las filas labeled, y cada barra de win rate / celda del heatmap muestra su propio `n` (atenuado bajo un mínimo de 5) para que un rate con poco sample nunca se lea como uno confiable.

## Decisiones clave

- **La DB se arma en build time, no se commitea.** `data/meetings.db` está en `.gitignore`; el CSV y `labels_llm_v1.json` son el artifact versionado.
- **Los charts usan los mismos filtros que la tabla.** `GET /metrics` toma los mismos query params que `GET /meetings`.

## Re-labelear (opcional)

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
