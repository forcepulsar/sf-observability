-- Add attachment_events (EventType: Attachment) — security/access EventLogFile coverage (#9).
-- Published Daily for this org. user_name enriched from user_id at ingest.
-- Rollback: DROP TABLE salesforceProd.attachment_events;
CREATE TABLE IF NOT EXISTS salesforceProd.attachment_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    parent_id              String,
    attachment_id          String,
    content_type           LowCardinality(String),
    operation              LowCardinality(String),
    is_private_on          String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
