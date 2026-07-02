-- Add csp_violation_events (EventType: CSPViolation) — security/API/perf EventLogFile coverage.
-- Hourly. timestamp DateTime64(3) (ms) so high-frequency events don't collapse.
-- Rollback: DROP TABLE salesforceProd.csp_violation_events;
CREATE TABLE IF NOT EXISTS salesforceProd.csp_violation_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    blocked_uri            String,
    blocked_uri_domain     String,
    directive              LowCardinality(String),
    context                String,
    unique_id              String,
    disposition            LowCardinality(String),
    source                 String,
    column_number          UInt64,
    line_number            UInt64,
    source_file            String,
    resource_sample        String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
