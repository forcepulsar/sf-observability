-- Add logout_events (EventType: Logout) — the session-end counterpart to
-- login_events. First of the EventLogFile coverage-expansion types (#9).
-- Salesforce publishes Logout Daily for this org. user_name is enriched from
-- user_id at ingest time (the CSV has no USER_NAME).
-- Rollback: DROP TABLE salesforceProd.logout_events;
CREATE TABLE IF NOT EXISTS salesforceProd.logout_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    user_type              LowCardinality(String),
    session_type           LowCardinality(String),
    session_level          LowCardinality(String),
    browser_type           String,
    platform_type          LowCardinality(String),
    resolution_type        String,
    app_type               LowCardinality(String),
    client_version         String,
    api_type               String,
    api_version            String,
    user_initiated_logout  String,
    session_key            String,
    login_key              String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
