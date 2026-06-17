-- ===========================================================================
-- Threat-detection, audit, and user-lookup objects
-- ===========================================================================
-- These were previously created only at runtime (the *_events / setup_audit_trail
-- tables by ingest_threat_store.py; the user_id_map view and user_lookup
-- dictionary by hand directly in production). Capturing them here makes a fresh
-- install create them up front and gives the repo a single source of truth.
--
-- Applied AFTER schema_events.sql, because user_id_map / user_lookup depend on
-- the `users` table defined there. Run via ./schema/setup.sh (salesforceProd is
-- substituted to the target database).
-- ===========================================================================

-- --- Shield threat-detection EventStores -----------------------------------
-- Real-time Event Monitoring detections. ReplacingMergeTree (no version column,
-- matching production) deduplicates on re-ingest by (event_date, id).

CREATE TABLE IF NOT EXISTS salesforceProd.credential_stuffing_events
(
    id String, event_identifier String, event_date DateTime, created_date DateTime,
    user_id String, username String, summary String, score Int32, policy_outcome String
) ENGINE = ReplacingMergeTree() ORDER BY (event_date, id);

CREATE TABLE IF NOT EXISTS salesforceProd.session_hijacking_events
(
    id String, event_identifier String, event_date DateTime, created_date DateTime,
    user_id String, username String, summary String, score Int32, policy_outcome String
) ENGINE = ReplacingMergeTree() ORDER BY (event_date, id);

CREATE TABLE IF NOT EXISTS salesforceProd.api_anomaly_events
(
    id String, event_identifier String, event_date DateTime, created_date DateTime,
    user_id String, username String, summary String, score Int32, policy_outcome String
) ENGINE = ReplacingMergeTree() ORDER BY (event_date, id);

CREATE TABLE IF NOT EXISTS salesforceProd.report_anomaly_events
(
    id String, event_identifier String, event_date DateTime, created_date DateTime,
    user_id String, username String, summary String, score Int32, policy_outcome String
) ENGINE = ReplacingMergeTree() ORDER BY (event_date, id);

CREATE TABLE IF NOT EXISTS salesforceProd.guest_user_anomaly_events
(
    id String, event_identifier String, event_date DateTime, created_date DateTime,
    user_id String, username String, summary String, score Int32, policy_outcome String
) ENGINE = ReplacingMergeTree() ORDER BY (event_date, id);

-- --- Setup Audit Trail (admin/config changes; no Shield license required) ---

CREATE TABLE IF NOT EXISTS salesforceProd.setup_audit_trail
(
    id String, action LowCardinality(String), section LowCardinality(String),
    created_date DateTime, created_by_id String, created_by_username String,
    created_by_name String, display String, delegate_user String
) ENGINE = ReplacingMergeTree() ORDER BY (created_date, id);

-- --- User lookup view + dictionary ------------------------------------------
-- user_id_map maps both 18- and 15-char Salesforce user IDs to a username
-- (mirrors the in-memory user_map ingest.py builds). user_lookup caches it as a
-- dictionary for fast joins in dashboards/queries. Order matters: users ->
-- user_id_map -> user_lookup.

CREATE VIEW IF NOT EXISTS salesforceProd.user_id_map
(
    user_id String, username String
) AS
SELECT id AS user_id, username FROM salesforceProd.users WHERE username != ''
UNION ALL
SELECT substring(id, 1, 15) AS user_id, username FROM salesforceProd.users WHERE username != '';

CREATE DICTIONARY IF NOT EXISTS salesforceProd.user_lookup
(
    user_id String, username String
)
PRIMARY KEY user_id
SOURCE(CLICKHOUSE(TABLE 'user_id_map' DB 'salesforceProd'))
LIFETIME(MIN 300 MAX 600)
LAYOUT(COMPLEX_KEY_HASHED());
