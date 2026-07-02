-- Add sandbox_events (EventType: Sandbox) — security/API/perf EventLogFile coverage.
-- Hourly. timestamp DateTime64(3) (ms) so high-frequency events don't collapse.
-- Rollback: DROP TABLE salesforceProd.sandbox_events;
CREATE TABLE IF NOT EXISTS salesforceProd.sandbox_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    sandbox_id             String,
    organization_id        LowCardinality(String),
    pending_sandbox_org_id String,
    current_sandbox_org_id String,
    status                 LowCardinality(String),
    user_id                String,
    user_name              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
