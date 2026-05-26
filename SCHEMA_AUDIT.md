# EventLogFile Schema Coverage

Field-by-field coverage for all event types ingested by this pipeline.
Verified against live CSV headers downloaded from the Salesforce EventLogFile API.

> **Note on Salesforce documentation:** The official docs are JavaScript-rendered and don't always reflect what the API actually returns. This document is based on live CSV headers — the authoritative source is what Salesforce actually sends, not what the docs list.

---

## Summary

| Event Type | SF EventType | ClickHouse Table | Fields Captured | Interval |
|---|---|---|---|---|
| Login | `Login` | `login_events` | 20 | Hourly |
| Login As | `LoginAs` | `login_as_events` | 13 | Hourly |
| Salesforce Support Login As | `SalesforceLoginAs` | `login_as_events` | 8 | Hourly |
| Report Export | `ReportExport` | `report_export_events` | 9 | Daily |
| Insufficient Access | `InsufficientAccess` | `insufficient_access_events` | 10 | Hourly |
| Permission Update | `PermissionUpdate` | `permission_update_events` | 9 | Daily |
| SOAP API | `API` | `api_events` | 13 | Hourly |
| REST API | `RestApi` | `rest_api_events` | 18 | Hourly |
| Bulk API v1 | `BulkApi` | `bulk_api_events` | 12 | Daily |
| Bulk API v2 | `BulkApi2` | `bulk_api2_events` | 13 | Daily |
| Apex Callout | `ApexCallout` | `apex_callout_events` | 11 | Hourly |
| Named Credential | `NamedCredential` | `named_credential_events` | 9 | Hourly |
| Metadata API | `MetadataApiOperation` | `metadata_api_events` | 9 | Daily |
| Apex Exception | `ApexUnexpectedException` | `apex_exception_events` | 11 | Hourly |
| Flow Execution | `FlowExecution` | `flow_execution_events` | 11 | Hourly |
| URI | `URI` | `uri_events` | 12 | Hourly |
| Apex Execution | `ApexExecution` | `apex_execution_events` | 11 | Hourly |
| Package Install | `PackageInstall` | `package_install_events` | 9 | Daily |
| Apex Trigger | `ApexTrigger` | `apex_trigger_events` | 16 | Hourly |
| Lightning Interaction | `LightningInteraction` | `lightning_interaction_events` | 19 | Hourly |
| Lightning Page View | `LightningPageView` | `lightning_page_view_events` | 17 | Hourly |
| API Total Usage | `ApiTotalUsage` | `api_total_usage_events` | 18 | Daily + Hourly |
| Flow Nav Metric | `FlowNavMetric` | `flow_nav_metric_events` | 7 | Daily |

**Plus via Threat Detection EventStore (SOQL-based, not EventLogFile):**

| Event Type | ClickHouse Table |
|---|---|
| SetupAuditTrail | `ingestion_events` |
| ReportAnomalyEventStore | `ingestion_events` |
| ApiAnomalyEventStore | `ingestion_events` |
| CredentialStuffingEventStore | `ingestion_events` |
| SessionHijackingEventStore | `ingestion_events` |

---

## Field detail

### Login → `login_events`

| SF CSV Field | ClickHouse Column | Notes |
|---|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` | |
| `EVENT_TYPE` | `event_type` | |
| `REQUEST_ID` | `request_id` | |
| `ORGANIZATION_ID` | `organization_id` | |
| `USER_ID` | `user_id` | |
| `USER_NAME` | `user_name` | |
| `USER_TYPE` | `user_type` | |
| `LOGIN_STATUS` | `login_status` | `LOGIN_NO_ERROR` = success |
| `LOGIN_TYPE` | `login_type` | |
| `CLIENT_IP` | `client_ip` | |
| `BROWSER_TYPE` | `browser_type` | |
| `PLATFORM_TYPE` | `platform_type` | |
| `CPU_TIME` | `cpu_time_ns` | |
| `RUN_TIME` | `run_time_ns` | |
| `SESSION_KEY` | `session_key` | |
| `LOGIN_KEY` | `login_key` | |
| `API_TYPE` | `api_type` | |
| `API_VERSION` | `api_version` | |
| `CIPHER_SUITE` | `cipher_suite` | |
| `AUTHENTICATION_SERVICE` | `authentication_service` | |

---

### LoginAs → `login_as_events`

| SF CSV Field | ClickHouse Column | Notes |
|---|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` | |
| `EVENT_TYPE` | `event_type` | |
| `REQUEST_ID` | `request_id` | |
| `ORGANIZATION_ID` | `organization_id` | |
| `USER_ID` | `user_id` | The admin who performed the action |
| `USER_NAME` | `user_name` | |
| `DELEGATED_USER_ID` | `delegated_user_id` | The user being impersonated |
| `DELEGATED_USER_NAME` | `delegated_user_name` | |
| `DELEGATED_ORGANIZATION_ID` | `delegated_organization_id` | |
| `LOGIN_KEY` | `login_key` | |
| `SESSION_KEY` | `session_key` | |
| `CLIENT_IP` | `client_ip` | |
| `LOGIN_TYPE` | `login_type` | |

---

### SalesforceLoginAs → `login_as_events`

Salesforce Support logging into a customer org. Different CSV schema from `LoginAs`.

| SF CSV Field | ClickHouse Column | Notes |
|---|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` | |
| `EVENT_TYPE` | `event_type` | Always `SalesforceLoginAs` |
| `REQUEST_ID` | `request_id` | |
| `ORGANIZATION_ID` | `organization_id` | |
| `ACTUAL_USER_ID` | `actual_user_id` | The SF Support user |
| `OPERATION` | `operation` | |
| `IP_ADDRESS` | `client_ip` | |
| `CASE_ID` | `case_id` | Support case that authorized the access |

---

### ReportExport → `report_export_events`

| SF CSV Field | ClickHouse Column | Notes |
|---|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` | |
| `EVENT_TYPE` | `event_type` | |
| `REQUEST_ID` | `request_id` | |
| `ORGANIZATION_ID` | `organization_id` | |
| `USER_ID_DERIVED` | `user_id` | |
| `URI_ID_DERIVED` | `report_id` | Report identifier |
| `CLIENT_IP` | `client_ip` | |
| `RUN_TIME` | `run_time_ns` | |
| `CPU_TIME` | `cpu_time_ns` | |

> Note: `USER_NAME`, `ROWS_PROCESSED`, `FORMAT`, and `BROWSER_TYPE` do not appear in the actual CSV for this event type despite appearing in some documentation.

---

### InsufficientAccess → `insufficient_access_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `USER_ID_DERIVED` | `user_id` |
| `RECORD_ID` | `resource_id` |
| `ENTITY_TYPE` | `resource_type` |
| `REQUESTED_ACCESS_LEVEL` | `action` |
| `ACCESS_ERROR` | `access_error` |
| `ERROR_DESCRIPTION` | `error_description` |

---

### PermissionUpdate → `permission_update_events`

| SF CSV Field | ClickHouse Column | Notes |
|---|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` | |
| `EVENT_TYPE` | `event_type` | |
| `REQUEST_ID` | `request_id` | |
| `ORGANIZATION_ID` | `organization_id` | |
| `USER_ID` | `user_id` | |
| `FEATURE_ID` | `permission_set_id` | |
| `PERMISSION_TYPE` | `permission_set_name` | |
| `UPDATE_TYPE` | `action` | |
| `DESCRIPTION` | `description` | |

> Note: `MODIFIED_USER_*` and `PERMISSION_SET_NAME` fields visible in UI don't appear in the CSV. This event type represents field/object permission changes, not permission set assignments.

---

### API (SOAP) → `api_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `USER_ID` | `user_id` |
| `USER_NAME` | `user_name` |
| `METHOD_NAME` | `method_name` |
| `ENTITY_NAME` | `entity_name` |
| `RUN_TIME` | `run_time_ns` |
| `CPU_TIME` | `cpu_time_ns` |
| `CLIENT_IP` | `client_ip` |
| `ROWS_PROCESSED` | `rows_processed` |
| `CLIENT_NAME` | `client_name` |

---

### RestApi → `rest_api_events`

| SF CSV Field | ClickHouse Column | Notes |
|---|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` | |
| `EVENT_TYPE` | `event_type` | |
| `REQUEST_ID` | `request_id` | |
| `ORGANIZATION_ID` | `organization_id` | |
| `USER_ID` | `user_id` | |
| `USER_NAME` | `user_name` | |
| `METHOD` | `method` | GET/POST/PATCH/DELETE |
| `URI` | `uri` | |
| `STATUS_CODE` | `status_code` | |
| `USER_AGENT` | `user_agent` | |
| `CLIENT_IP` | `client_ip` | |
| `RUN_TIME` | `run_time_ns` | |
| `CPU_TIME` | `cpu_time_ns` | |
| `CONNECTED_APP_ID` | `connected_app_id` | Key field for attribution |
| `ENTITY_NAME` | `entity_name` | |
| `QUERY` | `query` | SOQL query if applicable |
| `EXCEPTION_MESSAGE` | `exception_message` | |
| `ROWS_PROCESSED` | `rows_processed` | |

---

### BulkApi v1 → `bulk_api_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `USER_ID` | `user_id` |
| `USER_NAME` | `user_name` |
| `JOB_ID` | `job_id` |
| `BATCH_ID` | `batch_id` |
| `OPERATION_TYPE` | `operation` |
| `ENTITY_TYPE` | `object_type` |
| `ROWS_PROCESSED` | `rows_processed` |
| `SUCCESS` | `status` |

---

### BulkApi v2 → `bulk_api2_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `USER_ID` | `user_id` |
| `USER_NAME` | `user_name` |
| `JOB_ID` | `job_id` |
| `OPERATION_TYPE` | `operation` |
| `ENTITY_TYPE` | `object_type` |
| `RECORDS_PROCESSED` | `rows_processed` |
| `JOB_STATUS` | `status` |
| `RECORDS_FAILED` | `records_failed` |
| `ERROR_MESSAGE` | `error_message` |

---

### ApexCallout → `apex_callout_events`

| SF CSV Field | ClickHouse Column | Notes |
|---|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` | |
| `EVENT_TYPE` | `event_type` | |
| `REQUEST_ID` | `request_id` | |
| `ORGANIZATION_ID` | `organization_id` | |
| `USER_ID` | `user_id` | |
| `USER_NAME` | `user_name` | |
| `URL` | `callout_url` | External endpoint called |
| `METHOD` | `method` | |
| `STATUS_CODE` | `status_code` | |
| `TIME` | `callout_time_ns` | |
| `TYPE` | `type` | |

> Note: `CLASS_NAME` does not appear in the actual CSV despite being listed in some documentation.

---

### NamedCredential → `named_credential_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `USER_ID` | `user_id` |
| `USER_NAME` | `user_name` |
| `NAMED_CREDENTIAL_NAME` | `named_credential_id` |
| `URI` | `uri` |
| `RUN_TIME` | `run_time_ns` |

> Note: `METHOD` and `STATUS_CODE` do not appear in this event type's CSV.

---

### MetadataApiOperation → `metadata_api_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `USER_ID` | `user_id` |
| `USER_NAME` | `user_name` |
| `OPERATION` | `operation` |
| `CLIENT_ID` | `client_id` |
| `RUN_TIME` | `run_time_ns` |

> Note: `TYPE` and `ENTITY_NAME` do not appear in this event type's CSV.

---

### ApexUnexpectedException → `apex_exception_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `USER_ID` | `user_id` |
| `USER_NAME` | `user_name` |
| `EXCEPTION_TYPE` | `exception_type` |
| `EXCEPTION_MESSAGE` | `exception_message` |
| `STACK_TRACE` | `stack_trace` |
| `CLASS_NAME` | `class_name` |
| `METHOD_NAME` | `method_name` |

---

### FlowExecution → `flow_execution_events`

| SF CSV Field | ClickHouse Column | Notes |
|---|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` | |
| `EVENT_TYPE` | `event_type` | |
| `REQUEST_ID` | `request_id` | |
| `ORGANIZATION_ID` | `organization_id` | |
| `USER_ID` | `user_id` | |
| `USER_NAME` | `user_name` | |
| `FLOW_VERSION_ID` | `flow_id` | |
| `PROCESS_TYPE` | `process_type` | |
| `TOTAL_EXECUTION_TIME` | `total_execution_time_ns` | |
| `NUMBER_OF_INTERVIEWS` | `number_of_interviews` | |
| `NUMBER_OF_ERRORS` | `number_of_errors` | |

> Note: `FLOW_ID`, `FLOW_NAME`, `RUN_TIME`, `CPU_TIME`, `IS_INTERVIEW_LIMIT_HIT` do not appear in the actual CSV.

---

### URI → `uri_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `USER_ID` | `user_id` |
| `USER_NAME` | `user_name` |
| `URI` | `uri` |
| `METHOD` | `method` |
| `RUN_TIME` | `run_time_ns` |
| `CPU_TIME` | `cpu_time_ns` |
| `BROWSER_TYPE` | `browser_type` |
| `CLIENT_IP` | `client_ip` |

---

### ApexExecution → `apex_execution_events`

| SF CSV Field | ClickHouse Column | Notes |
|---|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` | |
| `EVENT_TYPE` | `event_type` | |
| `REQUEST_ID` | `request_id` | |
| `ORGANIZATION_ID` | `organization_id` | |
| `USER_ID` | `user_id` | |
| `USER_NAME` | `user_name` | |
| `QUIDDITY` | `quiddity` | X = Anonymous Apex |
| `ENTRY_POINT` | `entry_point` | |
| `CPU_TIME` | `cpu_time_ns` | |
| `RUN_TIME` | `run_time_ns` | |
| `NUMBER_SOQL_QUERIES` | `number_soql_queries` | |

> Note: `LIMIT_USAGE_PERCENT` does not appear in the actual CSV.

---

### PackageInstall → `package_install_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `USER_ID` | `user_id` |
| `USER_NAME` | `user_name` |
| `PACKAGE_NAMESPACE` | `package_namespace` |
| `PACKAGE_VERSION_ID` | `package_version_id` |
| `INSTALL_TYPE` | `install_type` |

---

### ApexTrigger → `apex_trigger_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `USER_ID` | `user_id` |
| `USER_NAME` | `user_name` |
| `ENTITY_NAME` | `entity_name` |
| `TRIGGER_ID` | `trigger_id` |
| `TYPE` | `trigger_type` |
| `CPU_TIME` | `cpu_time_ns` |
| `RUN_TIME` | `run_time_ns` |
| `EXEC_TIME` | `exec_time_ns` |
| `CALLOUT_TIME` | `callout_time_ns` |
| `NUM_DML_STATEMENTS` | `num_dml_statements` |
| `SOQL_QUERY_COUNT` | `soql_query_count` |
| `LIMIT_USAGE_PERCENT` | `limit_usage_percent` |

---

### LightningInteraction → `lightning_interaction_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `USER_IDENTIFIER` | `user_id` |
| `APP_NAME` | `app_name` |
| `PAGE_APP_NAME` | `page_app_name` |
| `PAGE_CONTEXT` | `page_context` |
| `PAGE_ENTITY_TYPE` | `page_entity_type` |
| `PAGE_ENTITY_ID` | `page_entity_id` |
| `COMPONENT_NAME` | `component_name` |
| `TARGET` | `target` |
| `TARGET_TYPE` | `target_type` |
| `PAGE_URL` | `page_url` |
| `BROWSER_NAME` | `browser_name` |
| `DEVICE_PLATFORM` | `device_platform` |
| `OPERATING_SYSTEM_NAME` | `os_name` |
| `DURATION` | `duration_ms` |
| `NOTE` | `note` |

---

### LightningPageView → `lightning_page_view_events`

| SF CSV Field | ClickHouse Column | Notes |
|---|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` | |
| `EVENT_TYPE` | `event_type` | |
| `REQUEST_ID` | `request_id` | |
| `ORGANIZATION_ID` | `organization_id` | |
| `USER_IDENTIFIER` | `user_id` | |
| `APP_NAME` | `app_name` | |
| `PAGE_APP_NAME` | `page_app_name` | |
| `BROWSER_NAME` | `browser_name` | |
| `CLIENT_GEOLOCATION` | `client_geolocation` | |
| `DEVICE_PLATFORM` | `device_platform` | |
| `OPERATING_SYSTEM_NAME` | `os_name` | |
| `PAGE_OBJECT_TYPE` | `page_object_type` | |
| `PAGE_URL` | `page_url` | |
| `PAGE_CONTEXT` | `page_context` | |
| `EFFECTIVE_PAGE_TIME` | `effective_page_time_ms` | Key field for perf dashboards |
| `DOES_EFFECTIVE_PAGE_TIME_DEVIATE` | `does_page_time_deviate` | |

---

### ApiTotalUsage → `api_total_usage_events`

Ingested twice: once as a **daily** file (full day totals, 24h lag) and once as **hourly** files (2 sequences/hour, ~1h lag). `ReplacingMergeTree` deduplicates the overlap automatically.

The `counts_against_api_limit` field is the key field for matching Salesforce's billing counter. Not all API calls count against the daily limit — this field is 0 for non-billable calls (e.g. OwnBackup pagination, internal calls).

| SF CSV Field | ClickHouse Column | Notes |
|---|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` | |
| `EVENT_TYPE` | `event_type` | |
| `REQUEST_ID` | `request_id` | |
| `ORGANIZATION_ID` | `organization_id` | |
| `USER_ID` | `user_id` | |
| `USER_NAME` | `user_name` | |
| `API_FAMILY` | `api_family` | REST/SOAP/Bulk/etc. |
| `API_VERSION` | `api_version` | |
| `HTTP_METHOD` | `http_method` | |
| `STATUS_CODE` | `status_code` | |
| `CLIENT_NAME` | `client_name` | |
| `CLIENT_IP` | `client_ip` | |
| `CONNECTED_APP_ID` | `connected_app_id` | Opaque ID — join with `connected_app_registry` |
| `CONNECTED_APP_NAME` | `connected_app_name` | Not always populated by Salesforce |
| `API_RESOURCE` | `api_resource` | |
| `ENTITY_NAME` | `entity_name` | |
| `COUNTS_AGAINST_API_LIMIT` | `counts_against_api_limit` | 1 = billable, 0 = non-billable |
| `API_CLIENT_CATEGORY` | `api_client_category` | |

Intentionally skipped: `BOT_ID`, `BOT_SESSION_ID`, `PLANNER_ID` (Einstein/Agentforce only), `TIMESTAMP` (prefer `TIMESTAMP_DERIVED`).

---

### FlowNavMetric → `flow_nav_metric_events`

| SF CSV Field | ClickHouse Column |
|---|---|
| `TIMESTAMP_DERIVED` | `timestamp` |
| `EVENT_TYPE` | `event_type` |
| `REQUEST_ID` | `request_id` |
| `ORGANIZATION_ID` | `organization_id` |
| `FLOW_VERSION_IDENTIFIER` | `flow_version_id` |
| `TOTAL_EXECUTION_TIME` | `total_execution_time_ms` |
| `ERROR_COUNT` | `error_count` |
