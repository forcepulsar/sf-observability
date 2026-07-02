-- Add queued_execution_events (EventType: QueuedExecution) — security/API/perf EventLogFile coverage.
-- Hourly. timestamp DateTime64(3) (ms) so high-frequency events don't collapse.
-- Rollback: DROP TABLE salesforceProd.queued_execution_events;
CREATE TABLE IF NOT EXISTS salesforceProd.queued_execution_events
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
    user_type              LowCardinality(String),
    request_status         LowCardinality(String),
    db_total_time          Int64,
    job_id                 String,
    entry_point            LowCardinality(String),
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
