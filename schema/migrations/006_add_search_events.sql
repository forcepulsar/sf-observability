-- Add search_events (EventType: Search) — security/access EventLogFile coverage (#9).
-- Published Daily for this org. user_name enriched from user_id at ingest.
-- Rollback: DROP TABLE salesforceProd.search_events;
CREATE TABLE IF NOT EXISTS salesforceProd.search_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    query_id               String,
    num_results            UInt64,
    search_query           String,
    prefixes_searched      String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
