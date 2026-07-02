-- Add composite_api_subrequest_events (EventType: CompositeApiSubrequest) — security/API/perf EventLogFile coverage.
-- Hourly. timestamp DateTime64(3) (ms) so high-frequency events don't collapse.
-- Rollback: DROP TABLE salesforceProd.composite_api_subrequest_events;
CREATE TABLE IF NOT EXISTS salesforceProd.composite_api_subrequest_events
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
    user_type              LowCardinality(String),
    request_status         LowCardinality(String),
    db_total_time          UInt64,
    method                 LowCardinality(String),
    is_cancelled           String,
    cancelled_reason       String,
    success                String,
    status_code            UInt64,
    initial_reference_ids  String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
