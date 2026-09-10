FROM node:20-slim AS web
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY apps/api/requirements.txt apps/api/
RUN pip install --no-cache-dir -r apps/api/requirements.txt
COPY scripts/ scripts/
COPY data/vambe_clients_10k.csv data/
COPY data/labels_llm_v1.json data/
COPY apps/ apps/
COPY --from=web /web/dist apps/web/dist
RUN python scripts/ingest.py && python scripts/load_labels.py
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT}"]
