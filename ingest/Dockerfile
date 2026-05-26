FROM python:3.12-slim
WORKDIR /app
COPY ingest/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ingest/ingest.py ingest/ingest_threat_store.py ingest/metrics.py ingest/entrypoint.sh ./
RUN chmod +x entrypoint.sh
COPY schema/optimize_tables.py ./schema/optimize_tables.py
ENTRYPOINT ["./entrypoint.sh"]
