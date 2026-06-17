-- Add report_events (EventType: Report) — security/access EventLogFile coverage (#9).
-- Published Daily for this org. user_name enriched from user_id at ingest.
-- Rollback: DROP TABLE salesforceProd.report_events;
CREATE TABLE IF NOT EXISTS salesforceProd.report_events
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
    entity_name            String,
    display_type           LowCardinality(String),
    rendering_type         LowCardinality(String),
    report_id              String,
    row_count              UInt64,
    number_exception_filters UInt64,
    number_columns         UInt64,
    ui_number_columns      UInt64,
    average_row_size       UInt64,
    sort                   String,
    db_blocks              UInt64,
    db_cpu_time            UInt64,
    number_buckets         UInt64,
    client_ip              String,
    origin                 LowCardinality(String),
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
