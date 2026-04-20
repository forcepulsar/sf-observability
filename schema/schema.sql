-- Salesforce Login Events schema for ClickHouse Cloud
-- Run this in the ClickHouse Cloud SQL console before first ingest

CREATE DATABASE IF NOT EXISTS salesforceFull;

-- Tracks which SF EventLogFiles have already been ingested (deduplication)
CREATE TABLE IF NOT EXISTS salesforceFull.ingestion_state
(
    log_file_id   String,
    event_type    String,
    log_date      Date,
    row_count     UInt32,
    ingested_at   DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree()
ORDER BY log_file_id;

-- Main login events table
CREATE TABLE IF NOT EXISTS salesforceFull.login_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    user_type              LowCardinality(String),
    login_status           LowCardinality(String),
    login_type             LowCardinality(String),
    client_ip              String,
    browser_type           String,
    platform_type          LowCardinality(String),
    cpu_time_ns            UInt64,
    run_time_ns            UInt64,
    session_key            String,
    login_key              String,
    api_type               String,
    api_version            String,
    cipher_suite           String,
    authentication_service String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);
