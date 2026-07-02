-- Add database_save_events (EventType: DatabaseSave) — security/API/perf EventLogFile coverage.
-- Hourly. timestamp DateTime64(3) (ms) so high-frequency events don't collapse.
-- Rollback: DROP TABLE salesforceProd.database_save_events;
CREATE TABLE IF NOT EXISTS salesforceProd.database_save_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    key_prefix             LowCardinality(String),
    dml_type               LowCardinality(String),
    num_rows               UInt64,
    sample_factor          UInt64,
    first_entity_id        String,
    session_key            String,
    login_key              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
