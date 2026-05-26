#!/bin/bash
set -e

INTERVAL=${INGEST_INTERVAL_SECONDS:-21600}   # default 6 hours

echo "=== Salesforce Ingest Service starting ==="
echo "    Interval: ${INTERVAL}s"

while true; do
    echo ""
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] ── Starting ingest cycle ──"

    python3 /app/ingest.py \
        && echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] ingest.py done" \
        || echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] ingest.py FAILED (continuing)"

    python3 /app/ingest_threat_store.py \
        && echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] ingest_threat_store.py done" \
        || echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] ingest_threat_store.py FAILED (continuing)"

    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Optimizing tables to eliminate duplicates…"
    python3 /app/schema/optimize_tables.py \
        && echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] optimize done" \
        || echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] optimize FAILED (continuing)"

    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Sleeping ${INTERVAL}s..."
    sleep "${INTERVAL}"
done
