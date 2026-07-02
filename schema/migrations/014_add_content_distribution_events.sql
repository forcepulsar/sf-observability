-- Add content_distribution_events (EventType: ContentDistribution) — security/API/perf EventLogFile coverage.
-- Hourly. timestamp DateTime64(3) (ms) so high-frequency events don't collapse.
-- Rollback: DROP TABLE salesforceProd.content_distribution_events;
CREATE TABLE IF NOT EXISTS salesforceProd.content_distribution_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    delivery_id            String,
    user_id                String,
    user_name              String,
    version_id             String,
    related_entity_id      String,
    delivery_location      LowCardinality(String),
    action                 LowCardinality(String),
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
