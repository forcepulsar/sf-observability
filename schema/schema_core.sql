-- Salesforce Login Events schema for ClickHouse Cloud — PRODUCTION
-- Run this in the ClickHouse Cloud SQL console before first prod ingest

CREATE DATABASE IF NOT EXISTS salesforceProd;

-- Tracks which SF EventLogFiles have already been ingested (deduplication)
CREATE TABLE IF NOT EXISTS salesforceProd.ingestion_state
(
    log_file_id   String,
    event_type    String,
    log_date      Date,
    interval      LowCardinality(String),
    row_count     UInt32,
    ingested_at   DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree()
ORDER BY log_file_id;

-- Migration: add interval column to existing installations (idempotent)
ALTER TABLE salesforceProd.ingestion_state ADD COLUMN IF NOT EXISTS interval LowCardinality(String) DEFAULT '';

-- Per-run summary: one row per invocation of ingest.py or ingest_threat_store.py
CREATE TABLE IF NOT EXISTS salesforceProd.ingestion_runs
(
    run_id        String,
    script        LowCardinality(String),
    started_at    DateTime64(3),
    ended_at      DateTime64(3),
    duration_ms   UInt32,
    files_total   UInt32,
    rows_total    UInt64,
    errors        UInt32,
    status        LowCardinality(String)
)
ENGINE = MergeTree()
ORDER BY started_at;

-- Per-unit timing: one row per EventLogFile or per SOQL object sync
CREATE TABLE IF NOT EXISTS salesforceProd.ingestion_events
(
    run_id        String,
    script        LowCardinality(String),
    event_type    LowCardinality(String),
    source        LowCardinality(String),
    identifier    String,
    log_date      Nullable(Date),
    started_at    DateTime64(3),
    ended_at      DateTime64(3),
    duration_ms   UInt32,
    row_count     UInt32,
    status        LowCardinality(String),
    error_message String
)
ENGINE = MergeTree()
ORDER BY (started_at, run_id);

-- Main login events table
CREATE TABLE IF NOT EXISTS salesforceProd.login_events
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
