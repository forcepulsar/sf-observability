-- Add dashboard_events (EventType: Dashboard) — security/access EventLogFile coverage (#9).
-- Published Daily for this org. user_name enriched from user_id at ingest.
-- Rollback: DROP TABLE salesforceProd.dashboard_events;
CREATE TABLE IF NOT EXISTS salesforceProd.dashboard_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    run_time               UInt64,
    cpu_time               UInt64,
    uri                    String,
    session_key            String,
    login_key              String,
    dashboard_component_id String,
    dashboard_id           String,
    report_id              String,
    is_success             String,
    dashboard_type         LowCardinality(String),
    is_scheduled           String,
    viewing_user_id        String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
