-- Add content_transfer_events (EventType: ContentTransfer) — security/access EventLogFile coverage (#9).
-- Published Daily for this org. user_name enriched from user_id at ingest.
-- Rollback: DROP TABLE salesforceProd.content_transfer_events;
CREATE TABLE IF NOT EXISTS salesforceProd.content_transfer_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    transaction_type       LowCardinality(String),
    document_id            String,
    version_id             String,
    file_type              LowCardinality(String),
    file_preview_type      LowCardinality(String),
    size_bytes             UInt64,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
