FROM python:3.12-slim
WORKDIR /app

# Salesforce auth is now a native Python JWT grant (ingest/sf_auth.py) — no
# Node.js or @salesforce/cli needed. This removes ~300MB and the entire class of
# CLI-output-format breakage (e.g. the 2.138.x token-masking bug).

COPY ingest/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingest/ingest.py ingest/ingest_threat_store.py ingest/sf_auth.py ingest/metrics.py ingest/entrypoint.sh ./
RUN chmod +x entrypoint.sh
COPY schema/optimize_tables.py ./schema/optimize_tables.py

ENTRYPOINT ["./entrypoint.sh"]
