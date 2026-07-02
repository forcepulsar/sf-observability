-- Salesforce EventLogFile → ClickHouse event tables
-- Generated from ingest.py column_map definitions.
-- Run via: ./schema/setup.sh <host> <password> [database]
-- Database must already exist before running this file.
--
-- ⚠️  KEEP IN SYNC WITH ingest.py
-- Every time a column_map entry is added/changed in ingest/ingest.py,
-- the corresponding CREATE TABLE here must be updated in the same commit.
-- Drift between these two files causes silent data loss on fresh installs.
--
-- Engine: ReplacingMergeTree(ingested_at) deduplicates on re-ingest.
-- ClickHouse Cloud maps this to SharedReplacingMergeTree automatically.
-- ORDER BY (timestamp, request_id) matches the ingest deduplication key.

-- ---------------------------------------------------------------------------
-- login_as_events  (EventType: LoginAs / SalesforceLoginAs)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.login_as_events
(
    timestamp                   DateTime64(3),
    event_type                  LowCardinality(String),
    request_id                  String,
    organization_id             LowCardinality(String),
    user_id                     String,
    user_name                   String,
    delegated_user_id           String,
    delegated_user_name         String,
    delegated_organization_id   LowCardinality(String),
    login_key                   String,
    session_key                 String,
    client_ip                   String,
    login_type                  LowCardinality(String),
    actual_user_id              String DEFAULT '',
    operation                   String DEFAULT '',
    case_id                     String DEFAULT '',
    log_file_id                 String,
    ingested_at                 DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- report_export_events  (EventType: ReportExport)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.report_export_events
(
    timestamp        DateTime64(3),
    event_type       LowCardinality(String),
    request_id       String,
    organization_id  LowCardinality(String),
    user_id          String,
    user_name      String DEFAULT '',
    report_id        String,
    client_ip        String,
    run_time_ns      UInt64,
    cpu_time_ns      UInt64,
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- insufficient_access_events  (EventType: InsufficientAccess)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.insufficient_access_events
(
    timestamp        DateTime64(3),
    event_type       LowCardinality(String),
    request_id       String,
    organization_id  LowCardinality(String),
    user_id          String,
    user_name      String DEFAULT '',
    resource_id      String,
    resource_type    LowCardinality(String),
    action           LowCardinality(String),
    access_error     String,
    error_description String,
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- permission_update_events  (EventType: PermissionUpdate)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.permission_update_events
(
    timestamp             DateTime64(3),
    event_type            LowCardinality(String),
    request_id            String,
    organization_id       LowCardinality(String),
    user_id               String,
    user_name      String DEFAULT '',
    permission_set_id     String,
    permission_set_name   String,
    action                LowCardinality(String),
    description           String DEFAULT '',
    log_file_id           String,
    ingested_at           DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- api_events  (EventType: API — SOAP API)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.api_events
(
    timestamp        DateTime64(3),
    event_type       LowCardinality(String),
    request_id       String,
    organization_id  LowCardinality(String),
    user_id          String,
    user_name        String,
    method_name      String,
    entity_name      String,
    run_time_ns      UInt64,
    cpu_time_ns      UInt64,
    client_ip        String,
    rows_processed   UInt32,
    client_name      String DEFAULT '',
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- rest_api_events  (EventType: RestApi)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.rest_api_events
(
    timestamp           DateTime64(3),
    event_type          LowCardinality(String),
    request_id          String,
    organization_id     LowCardinality(String),
    user_id             String,
    user_name           String,
    method              LowCardinality(String),
    uri                 String,
    status_code         UInt16,
    user_agent          String,
    client_ip           String,
    run_time_ns         UInt64,
    cpu_time_ns         UInt64,
    connected_app_id    String DEFAULT '',
    entity_name         String DEFAULT '',
    query               String DEFAULT '',
    exception_message   String DEFAULT '',
    rows_processed      UInt32 DEFAULT 0,
    log_file_id         String,
    ingested_at         DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- bulk_api_events  (EventType: BulkApi)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.bulk_api_events
(
    timestamp        DateTime64(3),
    event_type       LowCardinality(String),
    request_id       String,
    organization_id  LowCardinality(String),
    user_id          String,
    user_name        String,
    job_id           String,
    batch_id         String,
    operation        LowCardinality(String),
    object_type      String,
    rows_processed   UInt32,
    status           LowCardinality(String),
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- bulk_api2_events  (EventType: BulkApi2)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.bulk_api2_events
(
    timestamp        DateTime64(3),
    event_type       LowCardinality(String),
    request_id       String,
    organization_id  LowCardinality(String),
    user_id          String,
    user_name        String,
    job_id           String,
    operation        LowCardinality(String),
    object_type      String,
    rows_processed   UInt32,
    status           LowCardinality(String),
    records_failed   UInt32 DEFAULT 0,
    error_message    String DEFAULT '',
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- apex_callout_events  (EventType: ApexCallout)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.apex_callout_events
(
    timestamp         DateTime64(3),
    event_type        LowCardinality(String),
    request_id        String,
    organization_id   LowCardinality(String),
    user_id           String,
    user_name         String,
    callout_url       String,
    method            LowCardinality(String),
    status_code       Int32,
    callout_time_ns   UInt64,
    type              LowCardinality(String),
    log_file_id       String,
    ingested_at       DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- named_credential_events  (EventType: NamedCredential)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.named_credential_events
(
    timestamp             DateTime64(3),
    event_type            LowCardinality(String),
    request_id            String,
    organization_id       LowCardinality(String),
    user_id               String,
    user_name             String,
    named_credential_id   String,
    uri                   String,
    run_time_ns           UInt64,
    log_file_id           String,
    ingested_at           DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- metadata_api_events  (EventType: MetadataApiOperation)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.metadata_api_events
(
    timestamp        DateTime64(3),
    event_type       LowCardinality(String),
    request_id       String,
    organization_id  LowCardinality(String),
    user_id          String,
    user_name        String,
    operation        LowCardinality(String),
    client_id        String DEFAULT '',
    run_time_ns      UInt64,
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- apex_exception_events  (EventType: ApexUnexpectedException)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.apex_exception_events
(
    timestamp           DateTime64(3),
    event_type          LowCardinality(String),
    request_id          String,
    organization_id     LowCardinality(String),
    user_id             String,
    user_name           String,
    exception_type      String,
    exception_message   String,
    stack_trace         String,
    -- Derived category for dashboards/AI grouping; computed from exception_message.
    -- MATERIALIZED = recomputed on insert, no ingest change needed. Mirrors the
    -- hand-added column already present in production.
    exception_category  String MATERIALIZED multiIf(
        exception_message LIKE '%CPU time limit%', 'CPU Timeout',
        exception_message LIKE '%Too many DML statements%', 'DML Limit',
        exception_message LIKE '%Too many query rows%', 'Too Many Rows',
        exception_message LIKE '%UNABLE_TO_LOCK_ROW%' OR exception_message LIKE '%unable to obtain exclusive%', 'Row Lock',
        exception_message LIKE '%Too many SOQL queries%', 'SOQL Limit',
        exception_message LIKE '%CalloutException%' OR exception_message LIKE '%timed out%' OR exception_message LIKE '%Read timed out%', 'Callout Timeout',
        exception_message LIKE '%heap size%', 'Heap Limit',
        exception_message LIKE '%LimitException%', 'Other Limit',
        'Other'),
    class_name          String,
    method_name         String,
    log_file_id         String,
    ingested_at         DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- flow_execution_events  (EventType: FlowExecution)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.flow_execution_events
(
    timestamp                   DateTime64(3),
    event_type                  LowCardinality(String),
    request_id                  String,
    organization_id             LowCardinality(String),
    user_id                     String,
    user_name                   String,
    flow_id                     String,
    process_type                String DEFAULT '',
    total_execution_time_ns     UInt64 DEFAULT 0,
    number_of_interviews        UInt32 DEFAULT 0,
    number_of_errors            UInt32 DEFAULT 0,
    log_file_id                 String,
    ingested_at                 DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- uri_events  (EventType: URI)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.uri_events
(
    timestamp        DateTime64(3),
    event_type       LowCardinality(String),
    request_id       String,
    organization_id  LowCardinality(String),
    user_id          String,
    user_name        String,
    uri              String,
    method           LowCardinality(String),
    run_time_ns      UInt64,
    cpu_time_ns      UInt64,
    browser_type     String,
    client_ip        String,
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- apex_execution_events  (EventType: ApexExecution)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.apex_execution_events
(
    timestamp             DateTime64(3),
    event_type            LowCardinality(String),
    request_id            String,
    organization_id       LowCardinality(String),
    user_id               String,
    user_name             String,
    quiddity              LowCardinality(String),
    entry_point           String,
    cpu_time_ns           UInt64,
    run_time_ns           UInt64,
    number_soql_queries   UInt32 DEFAULT 0,
    log_file_id           String,
    ingested_at           DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- package_install_events  (EventType: PackageInstall)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.package_install_events
(
    timestamp            DateTime64(3),
    event_type           LowCardinality(String),
    request_id           String,
    organization_id      LowCardinality(String),
    user_id              String,
    user_name            String,
    package_namespace    String,
    package_version_id   String,
    install_type         LowCardinality(String),
    log_file_id          String,
    ingested_at          DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- apex_trigger_events  (EventType: ApexTrigger)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.apex_trigger_events
(
    timestamp             DateTime64(3),
    event_type            LowCardinality(String),
    request_id            String,
    organization_id       LowCardinality(String),
    user_id               String,
    user_name             String,
    entity_name           String,
    trigger_id            String,
    trigger_type          LowCardinality(String),
    cpu_time_ns           UInt64,
    run_time_ns           UInt64,
    exec_time_ns          UInt64,
    callout_time_ns       UInt64,
    num_dml_statements    UInt32,
    soql_query_count      UInt32,
    limit_usage_percent   UInt32,
    log_file_id           String,
    ingested_at           DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- lightning_interaction_events  (EventType: LightningInteraction)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.lightning_interaction_events
(
    timestamp          DateTime64(3),
    event_type         LowCardinality(String),
    request_id         String,
    organization_id    LowCardinality(String),
    user_id            String,
    user_name      String DEFAULT '',
    app_name           String,
    page_app_name      String,
    page_context       String,
    page_entity_type   String,
    page_entity_id     String,
    component_name     String,
    target             String,
    target_type        String,
    page_url           String,
    browser_name       String,
    device_platform    String,
    os_name            String,
    duration_ms        UInt64,
    note               String,
    log_file_id        String,
    ingested_at        DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- lightning_page_view_events  (EventType: LightningPageView)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.lightning_page_view_events
(
    timestamp                    DateTime64(3),
    event_type                   LowCardinality(String),
    request_id                   String,
    organization_id              LowCardinality(String),
    user_id                      String,
    user_name      String DEFAULT '',
    app_name                     String,
    page_app_name                String,
    browser_name                 String,
    client_geolocation           String,
    device_platform              String,
    os_name                      String,
    page_object_type             String,
    page_url                     String,
    page_context                 String,
    effective_page_time_ms       UInt64,
    does_page_time_deviate       UInt8,
    log_file_id                  String,
    ingested_at                  DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- api_total_usage_events  (EventType: ApiTotalUsage — daily + hourly)
-- The authoritative source for API limit tracking. counts_against_api_limit=1
-- means the call counts toward the org's daily API request limit.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.api_total_usage_events
(
    timestamp                   DateTime64(3),
    event_type                  String,
    request_id                  String,
    organization_id             String,
    api_family                  String,
    http_method                 String,
    status_code                 Int32,
    client_name                 String DEFAULT '',
    api_resource                String,
    object_name                 String DEFAULT '',
    run_time_ms                 Int64  DEFAULT 0,
    log_file_id                 String,
    user_id                     String DEFAULT '',
    user_name                   String DEFAULT '',
    api_version                 String DEFAULT '',
    client_ip                   String DEFAULT '',
    connected_app_id            String DEFAULT '',
    connected_app_name          String DEFAULT '',
    entity_name                 String DEFAULT '',
    counts_against_api_limit    UInt8  DEFAULT 0,
    api_client_category         String DEFAULT ''
)
ENGINE = ReplacingMergeTree()
ORDER BY (timestamp, request_id)
SETTINGS index_granularity = 8192;

-- ---------------------------------------------------------------------------
-- flow_nav_metric_events  (EventType: FlowNavMetric)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.flow_nav_metric_events
(
    timestamp               DateTime64(3),
    event_type              LowCardinality(String),
    request_id              String,
    organization_id         LowCardinality(String),
    flow_version_id         String,
    total_execution_time_ms UInt64,
    error_count             UInt32,
    log_file_id             String,
    ingested_at             DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- logout_events  (EventType: Logout) — session-end counterpart to login_events
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.logout_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    user_type              LowCardinality(String),
    session_type           LowCardinality(String),
    session_level          LowCardinality(String),
    browser_type           String,
    platform_type          LowCardinality(String),
    resolution_type        String,
    app_type               LowCardinality(String),
    client_version         String,
    api_type               String,
    api_version            String,
    user_initiated_logout  String,
    session_key            String,
    login_key              String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- User lookup table (synced on every ingest run from Salesforce User object)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.users
(
    id            String,
    username      String,
    name          String,
    first_name    String,
    last_name     String,
    email         String,
    title         String,
    department    String,
    user_type     LowCardinality(String),
    is_active     UInt8,
    profile_id    String DEFAULT '',
    profile_name  String DEFAULT '',
    synced_at     DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(synced_at)
ORDER BY id;

-- ---------------------------------------------------------------------------
-- connected_app_registry  (manually maintained; loaded by schema/load_registry.py)
-- Maps connected app IDs to human-readable names and optional category/notes.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.connected_app_registry
(
    connected_app_id  String,
    app_name          String,
    category          String DEFAULT '',
    notes             String DEFAULT '',
    updated_date      Date   DEFAULT today()
)
ENGINE = ReplacingMergeTree(updated_date)
ORDER BY connected_app_id
SETTINGS index_granularity = 8192;

-- ---------------------------------------------------------------------------
-- report_events  (EventType: Report)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- dashboard_events  (EventType: Dashboard)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.dashboard_events
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
    dashboard_component_id String,
    dashboard_id           String,
    report_id              String,
    is_success             String,
    dashboard_type         LowCardinality(String),
    is_scheduled           String,
    viewing_user_id        String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- search_events  (EventType: Search)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- search_click_events  (EventType: SearchClick)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.search_click_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    query_id               String,
    clicked_record_id      String,
    rank                   UInt64,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- content_transfer_events  (EventType: ContentTransfer)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- document_attachment_download_events  (EventType: DocumentAttachmentDownloads)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- attachment_events  (EventType: Attachment)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- content_document_link_events  (EventType: ContentDocumentLink)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- group_membership_events  (EventType: GroupMembership)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.group_membership_events
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
    operation              LowCardinality(String),
    group_type             LowCardinality(String),
    group_id               String,
    member_id              String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- csp_violation_events  (EventType: CSPViolation)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- content_distribution_events  (EventType: ContentDistribution)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- sandbox_events  (EventType: Sandbox)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.sandbox_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    sandbox_id             String,
    organization_id        LowCardinality(String),
    pending_sandbox_org_id String,
    current_sandbox_org_id String,
    status                 LowCardinality(String),
    user_id                String,
    user_name              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- platform_encryption_events  (EventType: PlatformEncryption)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.platform_encryption_events
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
    key_id                 String,
    action                 LowCardinality(String),
    key_type               LowCardinality(String),
    method                 LowCardinality(String),
    bot_id                 String,
    bot_session_id         String,
    planner_id             String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- visualforce_request_events  (EventType: VisualforceRequest)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.visualforce_request_events
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
    page_name              String,
    request_type           LowCardinality(String),
    is_first_request       String,
    query                  String,
    http_method            LowCardinality(String),
    user_agent             String,
    request_size           UInt64,
    response_size          UInt64,
    view_state_size        UInt64,
    controller_type        LowCardinality(String),
    managed_package_namespace String,
    is_ajax_request        String,
    db_blocks              UInt64,
    db_cpu_time            UInt64,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- apex_rest_api_events  (EventType: ApexRestApi)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.apex_rest_api_events
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
    method                 LowCardinality(String),
    media_type             LowCardinality(String),
    status_code            UInt64,
    user_agent             String,
    rows_processed         UInt64,
    number_fields          UInt64,
    db_blocks              UInt64,
    db_cpu_time            UInt64,
    request_size           UInt64,
    response_size          UInt64,
    entity_name            String,
    connected_app_id       String,
    client_name            String,
    exception_message      String,
    query                  String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- sites_events  (EventType: Sites)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.sites_events
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
    page_name              String,
    request_type           LowCardinality(String),
    is_first_request       String,
    query                  String,
    site_id                String,
    is_secure              String,
    response_size          UInt64,
    is_guest               String,
    is_api                 String,
    is_error               String,
    http_method            LowCardinality(String),
    http_headers           String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- bulk_api_request_events  (EventType: BulkApiRequest)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.bulk_api_request_events
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
    request_path           String,
    api_version            String,
    job_id                 String,
    batch_id               String,
    operation_type         LowCardinality(String),
    success                String,
    error_message          String,
    connected_app_id       String,
    client_name            String,
    concurrency_mode       LowCardinality(String),
    status_code            UInt64,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- database_save_events  (EventType: DatabaseSave)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.database_save_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    key_prefix             LowCardinality(String),
    dml_type               LowCardinality(String),
    num_rows               UInt64,
    sample_factor          UInt64,
    first_entity_id        String,
    session_key            String,
    login_key              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- composite_api_subrequest_events  (EventType: CompositeApiSubrequest)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.composite_api_subrequest_events
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
    method                 LowCardinality(String),
    is_cancelled           String,
    cancelled_reason       String,
    success                String,
    status_code            UInt64,
    initial_reference_ids  String,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- queued_execution_events  (EventType: QueuedExecution)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.queued_execution_events
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
    job_id                 String,
    entry_point            LowCardinality(String),
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);

-- ---------------------------------------------------------------------------
-- composite_api_events  (EventType: CompositeApi)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.composite_api_events
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
    all_or_none            String,
    failure_reason         String,
    is_request_collation_on String,
    num_retries            UInt64,
    num_graph_depth        UInt64,
    client_ip              String,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id);
