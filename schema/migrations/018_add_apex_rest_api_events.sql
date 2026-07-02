-- Add apex_rest_api_events (EventType: ApexRestApi) — security/API/perf EventLogFile coverage.
-- Hourly. timestamp DateTime64(3) (ms) so high-frequency events don't collapse.
-- Rollback: DROP TABLE salesforceProd.apex_rest_api_events;
CREATE TABLE IF NOT EXISTS salesforceProd.apex_rest_api_events
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
    media_type             LowCardinality(String),
    status_code            UInt64,
    user_agent             String,
    rows_processed         UInt64,
    number_fields          UInt64,
    db_blocks              UInt64,
    db_cpu_time            UInt64,
    request_size           UInt64,
    response_size          UInt64,
    entity_name            String,
    connected_app_id       String,
    client_name            String,
    exception_message      String,
    query                  String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
