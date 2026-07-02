-- Add visualforce_request_events (EventType: VisualforceRequest) — security/API/perf EventLogFile coverage.
-- Hourly. timestamp DateTime64(3) (ms) so high-frequency events don't collapse.
-- Rollback: DROP TABLE salesforceProd.visualforce_request_events;
CREATE TABLE IF NOT EXISTS salesforceProd.visualforce_request_events
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
    page_name              String,
    request_type           LowCardinality(String),
    is_first_request       String,
    query                  String,
    http_method            LowCardinality(String),
    user_agent             String,
    request_size           UInt64,
    response_size          UInt64,
    view_state_size        UInt64,
    controller_type        LowCardinality(String),
    managed_package_namespace String,
    is_ajax_request        String,
    db_blocks              UInt64,
    db_cpu_time            UInt64,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
