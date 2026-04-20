-- Salesforce Event Log File schemas for ClickHouse Cloud — PRODUCTION
-- Database salesforceProd is assumed to already exist.
-- Run this in the ClickHouse Cloud SQL console before first prod ingest.

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
    log_file_id                 String,
    ingested_at                 DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

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
    user_name        String,
    report_id        String,
    rows_processed   UInt32,
    format           LowCardinality(String),
    client_ip        String,
    browser_type     String,
    run_time_ns      UInt64,
    cpu_time_ns      UInt64,
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

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
    user_name        String,
    resource_id      String,
    resource_type    LowCardinality(String),
    action           LowCardinality(String),
    client_ip        String,
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

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
    user_name             String,
    modified_user_id      String,
    modified_user_name    String,
    permission_set_id     String,
    permission_set_name   String,
    action                LowCardinality(String),
    log_file_id           String,
    ingested_at           DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

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
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

-- ---------------------------------------------------------------------------
-- rest_api_events  (EventType: RestApi)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.rest_api_events
(
    timestamp        DateTime64(3),
    event_type       LowCardinality(String),
    request_id       String,
    organization_id  LowCardinality(String),
    user_id          String,
    user_name        String,
    method           LowCardinality(String),
    uri              String,
    status_code      UInt16,
    user_agent       String,
    client_ip        String,
    run_time_ns      UInt64,
    cpu_time_ns      UInt64,
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

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
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

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
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

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
    status_code       UInt16,
    callout_time_ns   UInt64,
    class_name        String,
    type              LowCardinality(String),
    log_file_id       String,
    ingested_at       DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

-- ---------------------------------------------------------------------------
-- named_credential_events  (EventType: NamedCredential)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.named_credential_events
(
    timestamp              DateTime64(3),
    event_type             LowCardinality(String),
    request_id             String,
    organization_id        LowCardinality(String),
    user_id                String,
    user_name              String,
    named_credential_id    String,
    uri                    String,
    method                 LowCardinality(String),
    status_code            UInt16,
    run_time_ns            UInt64,
    log_file_id            String,
    ingested_at            DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

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
    entity_type      String,
    entity_name      String,
    run_time_ns      UInt64,
    log_file_id      String,
    ingested_at      DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

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
    class_name          String,
    method_name         String,
    log_file_id         String,
    ingested_at         DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

-- ---------------------------------------------------------------------------
-- flow_execution_events  (EventType: FlowExecution)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS salesforceProd.flow_execution_events
(
    timestamp               DateTime64(3),
    event_type              LowCardinality(String),
    request_id              String,
    organization_id         LowCardinality(String),
    user_id                 String,
    user_name               String,
    flow_id                 String,
    flow_name               String,
    run_time_ns             UInt64,
    cpu_time_ns             UInt64,
    interview_limit_hit     UInt8,
    log_file_id             String,
    ingested_at             DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

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
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, user_id);

-- ---------------------------------------------------------------------------
-- User lookup table (synced daily from Salesforce User object)
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
    synced_at     DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(synced_at)
ORDER BY id;
