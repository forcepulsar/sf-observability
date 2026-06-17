-- Document the "reserved" columns: present in production (from earlier schema
-- iterations) but never populated by the current ingest — the Salesforce
-- EventLogFile CSV for these event types does not contain these fields. They
-- read 0% populated and were misleading anyone (and the LibreChat AI) querying
-- them as if they held data.
--
-- These comments surface in DESCRIBE / system.columns so the columns read as
-- "intentionally empty" rather than "broken or missing data". We keep the
-- columns (not dropped) in case Salesforce begins emitting these fields or
-- ingest is wired to populate them (see task: expand EventLogFile coverage).
--
-- COMMENT COLUMN IF EXISTS is a metadata-only operation (no data rewrite) and
-- no-ops on databases that don't have the column (e.g. a fresh install built
-- from the current clean schema), so this migration is safe everywhere.
-- Rollback: re-run with an empty comment string to clear.
--
-- NOTE: comment strings must not contain ';' — migrate.sh splits statements on
-- semicolons and would break a literal mid-string.

ALTER TABLE salesforceProd.apex_callout_events      COMMENT COLUMN IF EXISTS class_name          'Reserved. Not in the ApexCallout EventLogFile CSV, always empty. Candidate for future coverage.';
ALTER TABLE salesforceProd.apex_execution_events    COMMENT COLUMN IF EXISTS limit_usage_percent 'Reserved. Not in the ApexExecution EventLogFile CSV, always empty. Candidate for future coverage.';
ALTER TABLE salesforceProd.flow_execution_events    COMMENT COLUMN IF EXISTS cpu_time_ns         'Reserved. Not in the FlowExecution EventLogFile CSV, always empty. Candidate for future coverage.';
ALTER TABLE salesforceProd.flow_execution_events    COMMENT COLUMN IF EXISTS flow_name           'Reserved. Not in the FlowExecution EventLogFile CSV, always empty. Candidate for future coverage.';
ALTER TABLE salesforceProd.flow_execution_events    COMMENT COLUMN IF EXISTS interview_limit_hit 'Reserved. Not in the FlowExecution EventLogFile CSV, always empty. Candidate for future coverage.';
ALTER TABLE salesforceProd.flow_execution_events    COMMENT COLUMN IF EXISTS run_time_ns         'Reserved. Not in the FlowExecution EventLogFile CSV, always empty. Candidate for future coverage.';
ALTER TABLE salesforceProd.insufficient_access_events COMMENT COLUMN IF EXISTS client_ip         'Reserved. Not in the InsufficientAccess EventLogFile CSV, always empty.';
ALTER TABLE salesforceProd.metadata_api_events      COMMENT COLUMN IF EXISTS entity_name         'Reserved. Not in the MetadataApiOperation EventLogFile CSV, always empty.';
ALTER TABLE salesforceProd.metadata_api_events      COMMENT COLUMN IF EXISTS entity_type         'Reserved. Not in the MetadataApiOperation EventLogFile CSV, always empty.';
ALTER TABLE salesforceProd.named_credential_events  COMMENT COLUMN IF EXISTS method              'Reserved. Not in the NamedCredential EventLogFile CSV, always empty.';
ALTER TABLE salesforceProd.named_credential_events  COMMENT COLUMN IF EXISTS status_code         'Reserved. Not in the NamedCredential EventLogFile CSV, always empty.';
ALTER TABLE salesforceProd.permission_update_events COMMENT COLUMN IF EXISTS modified_user_id    'Reserved. Not in the PermissionUpdate EventLogFile CSV, always empty.';
ALTER TABLE salesforceProd.permission_update_events COMMENT COLUMN IF EXISTS modified_user_name  'Reserved. Not in the PermissionUpdate EventLogFile CSV, always empty.';
ALTER TABLE salesforceProd.report_export_events     COMMENT COLUMN IF EXISTS browser_type        'Reserved. Not in the ReportExport EventLogFile CSV, always empty.';
ALTER TABLE salesforceProd.report_export_events     COMMENT COLUMN IF EXISTS format              'Reserved. Not in the ReportExport EventLogFile CSV, always empty.';
ALTER TABLE salesforceProd.report_export_events     COMMENT COLUMN IF EXISTS rows_processed      'Reserved. Not in the ReportExport EventLogFile CSV, always empty.';
