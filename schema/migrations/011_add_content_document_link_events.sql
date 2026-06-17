-- Add content_document_link_events (EventType: ContentDocumentLink) — security/access EventLogFile coverage (#9).
-- Published Daily for this org. user_name enriched from user_id at ingest.
-- Rollback: DROP TABLE salesforceProd.content_document_link_events;
CREATE TABLE IF NOT EXISTS salesforceProd.content_document_link_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    document_id            String,
    shared_with_entity_id  String,
    sharing_permission     LowCardinality(String),
    sharing_operation      LowCardinality(String),
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
