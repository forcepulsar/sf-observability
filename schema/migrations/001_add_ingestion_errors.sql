-- Capture script-level failures (incl. pre-ClickHouse-connect crashes like SF
-- auth failures) so a broken cycle is diagnosable from Grafana without SSH.
-- Written by entrypoint.sh on non-zero exit. log_tail_b64 = base64 of the last
-- ~2KB of output; decode with base64Decode() in queries.
-- Rollback: DROP TABLE salesforceProd.ingestion_errors;
CREATE TABLE IF NOT EXISTS salesforceProd.ingestion_errors
(
    ts            DateTime DEFAULT now(),
    script        LowCardinality(String),
    exit_code     Int32,
    log_tail_b64  String
)
ENGINE = MergeTree()
ORDER BY ts;
