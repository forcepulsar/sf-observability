-- Add document_attachment_download_events (EventType: DocumentAttachmentDownloads) — security/access EventLogFile coverage (#9).
-- Published Daily for this org. user_name enriched from user_id at ingest.
-- Rollback: DROP TABLE salesforceProd.document_attachment_download_events;
CREATE TABLE IF NOT EXISTS salesforceProd.document_attachment_download_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    entity_id              String,
    file_type              LowCardinality(String),
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
