#!/bin/bash
set -e

INTERVAL=${INGEST_INTERVAL_SECONDS:-21600}   # default 6 hours
CH_DB="${CH_DATABASE:-salesforceProd}"

echo "=== Salesforce Ingest Service starting ==="
echo "    Interval: ${INTERVAL}s"

# Record a script-level failure to ClickHouse so a broken cycle is visible in
# Grafana without SSH. Crucially this also captures failures that happen BEFORE
# a script connects to ClickHouse (e.g. Salesforce auth failures), which the
# per-event/per-run metrics inside the scripts can never record. Best-effort —
# never breaks the loop.
report_failure() {
    local label="$1" rc="$2" logf="$3"
    local host="${CH_HOST#https://}"; host="${host#http://}"
    if [ -z "$host" ] || [ -z "$CH_PASSWORD" ]; then
        return 0
    fi
    local b64
    b64=$(tail -c 2000 "$logf" 2>/dev/null | base64 | tr -d '\n')
    printf 'INSERT INTO %s.ingestion_errors (script,exit_code,log_tail_b64) FORMAT TSV\n%s\t%s\t%s' \
        "$CH_DB" "$label" "$rc" "$b64" \
        | curl -s "https://${host}:8443/" --user "default:${CH_PASSWORD}" --data-binary @- >/dev/null 2>&1 || true
}

# Run one step: stream output live (so `docker compose logs` is unchanged) while
# also capturing it; on non-zero exit, record the failure to ingestion_errors.
run_step() {
    local label="$1" cmd="$2"
    local logf="/tmp/${label}.log"
    set +e
    eval "$cmd" 2>&1 | tee "$logf"
    local rc=${PIPESTATUS[0]}
    set -e
    if [ "$rc" -eq 0 ]; then
        echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] ${label} done"
    else
        echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] ${label} FAILED (rc=${rc}, continuing) — recorded to ingestion_errors"
        report_failure "$label" "$rc" "$logf"
    fi
}

while true; do
    echo ""
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] ── Starting ingest cycle ──"

    run_step "ingest.py" "python3 /app/ingest.py"
    run_step "ingest_threat_store.py" "python3 /app/ingest_threat_store.py"

    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Optimizing tables to eliminate duplicates…"
    run_step "optimize_tables.py" "python3 /app/schema/optimize_tables.py"

    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Sleeping ${INTERVAL}s..."
    sleep "${INTERVAL}"
done
