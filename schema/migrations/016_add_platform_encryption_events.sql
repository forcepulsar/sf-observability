-- Add platform_encryption_events (EventType: PlatformEncryption) — security/API/perf EventLogFile coverage.
-- Hourly. timestamp DateTime64(3) (ms) so high-frequency events don't collapse.
-- Rollback: DROP TABLE salesforceProd.platform_encryption_events;
CREATE TABLE IF NOT EXISTS salesforceProd.platform_encryption_events
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
    key_id                 String,
    action                 LowCardinality(String),
    key_type               LowCardinality(String),
    method                 LowCardinality(String),
    bot_id                 String,
    bot_session_id         String,
    planner_id             String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
