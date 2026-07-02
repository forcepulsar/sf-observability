-- Add bulk_api_request_events (EventType: BulkApiRequest) — security/API/perf EventLogFile coverage.
-- Hourly. timestamp DateTime64(3) (ms) so high-frequency events don't collapse.
-- Rollback: DROP TABLE salesforceProd.bulk_api_request_events;
CREATE TABLE IF NOT EXISTS salesforceProd.bulk_api_request_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    run_time               Int64,
    cpu_time               Int64,
    uri                    String,
    session_key            String,
    login_key              String,
    request_path           String,
    api_version            String,
    job_id                 String,
    batch_id               String,
    operation_type         LowCardinality(String),
    success                String,
    error_message          String,
    connected_app_id       String,
    client_name            String,
    concurrency_mode       LowCardinality(String),
    status_code            Int64,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
