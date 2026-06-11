FROM python:3.12-slim
WORKDIR /app

# Install Node.js 20 + Salesforce CLI — required for JWT/ECA authentication
# sf CLI is called as a subprocess by ingest.py during get_sf_client()
# PINNED: 2.138.x masks accessToken in `sf org display --json` (54-char stub),
# which breaks the token extraction in get_sf_client() with INVALID_AUTH_HEADER.
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @salesforce/cli@2.135.7 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ingest/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingest/ingest.py ingest/ingest_threat_store.py ingest/metrics.py ingest/entrypoint.sh ./
RUN chmod +x entrypoint.sh
COPY schema/optimize_tables.py ./schema/optimize_tables.py

ENTRYPOINT ["./entrypoint.sh"]
