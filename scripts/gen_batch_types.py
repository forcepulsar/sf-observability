#!/usr/bin/env python3
"""Generate CONFIG entries, schema_events.sql tables, and migrations for 12 new
EventLogFile types (security + API/perf coverage). Fields were fetched live from
the org's actual CSV headers. timestamp is DateTime64(3) (millisecond) so
high-frequency types don't collapse under the (timestamp, request_id) dedup key.
"""
import pathlib
import re

# EventType -> (table, [SF CSV fields as they actually appear], migration_number)
TYPES = {
    "CSPViolation": ("csp_violation_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,BLOCKED_URI,BLOCKED_URI_DOMAIN,DIRECTIVE,CONTEXT,UNIQUE_ID,DISPOSITION,SOURCE,COLUMN_NUMBER,LINE_NUMBER,SOURCE_FILE,RESOURCE_SAMPLE,TIMESTAMP_DERIVED", "013"),
    "ContentDistribution": ("content_distribution_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,ORGANIZATION_ID,DELIVERY_ID,USER_ID,VERSION_ID,RELATED_ENTITY_ID,DELIVERY_LOCATION,ACTION,TIMESTAMP_DERIVED,USER_ID_DERIVED", "014"),
    "Sandbox": ("sandbox_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,SANDBOX_ID,ORGANIZATION_ID,PENDING_SANDBOX_ORG_ID,CURRENT_SANDBOX_ORG_ID,STATUS,USER_ID,TIMESTAMP_DERIVED,USER_ID_DERIVED", "015"),
    "PlatformEncryption": ("platform_encryption_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,ORGANIZATION_ID,USER_ID,RUN_TIME,CPU_TIME,URI,SESSION_KEY,LOGIN_KEY,KEY_ID,ACTION,KEY_TYPE,METHOD,BOT_ID,BOT_SESSION_ID,PLANNER_ID,TIMESTAMP_DERIVED,USER_ID_DERIVED,CLIENT_IP,URI_ID_DERIVED,KEY_ID_DERIVED", "016"),
    "VisualforceRequest": ("visualforce_request_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,ORGANIZATION_ID,USER_ID,RUN_TIME,CPU_TIME,URI,SESSION_KEY,LOGIN_KEY,USER_TYPE,REQUEST_STATUS,DB_TOTAL_TIME,PAGE_NAME,REQUEST_TYPE,IS_FIRST_REQUEST,QUERY,HTTP_METHOD,USER_AGENT,REQUEST_SIZE,RESPONSE_SIZE,VIEW_STATE_SIZE,CONTROLLER_TYPE,MANAGED_PACKAGE_NAMESPACE,IS_AJAX_REQUEST,DB_BLOCKS,DB_CPU_TIME,TIMESTAMP_DERIVED,USER_ID_DERIVED,CLIENT_IP,URI_ID_DERIVED", "017"),
    "ApexRestApi": ("apex_rest_api_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,ORGANIZATION_ID,USER_ID,RUN_TIME,CPU_TIME,URI,SESSION_KEY,LOGIN_KEY,USER_TYPE,REQUEST_STATUS,DB_TOTAL_TIME,METHOD,MEDIA_TYPE,STATUS_CODE,USER_AGENT,ROWS_PROCESSED,NUMBER_FIELDS,DB_BLOCKS,DB_CPU_TIME,REQUEST_SIZE,RESPONSE_SIZE,ENTITY_NAME,CONNECTED_APP_ID,CLIENT_NAME,EXCEPTION_MESSAGE,QUERY,TIMESTAMP_DERIVED,USER_ID_DERIVED,CLIENT_IP,URI_ID_DERIVED", "018"),
    "Sites": ("sites_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,ORGANIZATION_ID,USER_ID,RUN_TIME,CPU_TIME,URI,SESSION_KEY,LOGIN_KEY,USER_TYPE,REQUEST_STATUS,DB_TOTAL_TIME,PAGE_NAME,REQUEST_TYPE,IS_FIRST_REQUEST,QUERY,SITE_ID,IS_SECURE,RESPONSE_SIZE,IS_GUEST,IS_API,IS_ERROR,HTTP_METHOD,HTTP_HEADERS,TIMESTAMP_DERIVED,USER_ID_DERIVED,CLIENT_IP,URI_ID_DERIVED", "019"),
    "BulkApiRequest": ("bulk_api_request_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,ORGANIZATION_ID,USER_ID,RUN_TIME,CPU_TIME,URI,SESSION_KEY,LOGIN_KEY,REQUEST_PATH,API_VERSION,JOB_ID,BATCH_ID,OPERATION_TYPE,SUCCESS,ERROR_MESSAGE,CONNECTED_APP_ID,CLIENT_NAME,CONCURRENCY_MODE,STATUS_CODE,TIMESTAMP_DERIVED,USER_ID_DERIVED,CLIENT_IP,URI_ID_DERIVED", "020"),
    "DatabaseSave": ("database_save_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,ORGANIZATION_ID,USER_ID,KEY_PREFIX,DML_TYPE,NUM_ROWS,SAMPLE_FACTOR,FIRST_ENTITY_ID,SESSION_KEY,LOGIN_KEY,TIMESTAMP_DERIVED", "021"),
    "CompositeApiSubrequest": ("composite_api_subrequest_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,ORGANIZATION_ID,USER_ID,RUN_TIME,CPU_TIME,URI,SESSION_KEY,LOGIN_KEY,USER_TYPE,REQUEST_STATUS,DB_TOTAL_TIME,METHOD,IS_CANCELLED,CANCELLED_REASON,SUCCESS,STATUS_CODE,INITIAL_REFERENCE_IDS,TIMESTAMP_DERIVED,USER_ID_DERIVED,CLIENT_IP,URI_ID_DERIVED", "022"),
    "QueuedExecution": ("queued_execution_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,ORGANIZATION_ID,USER_ID,RUN_TIME,CPU_TIME,URI,SESSION_KEY,LOGIN_KEY,USER_TYPE,REQUEST_STATUS,DB_TOTAL_TIME,JOB_ID,ENTRY_POINT,TIMESTAMP_DERIVED,USER_ID_DERIVED,CLIENT_IP,URI_ID_DERIVED", "023"),
    "CompositeApi": ("composite_api_events", "EVENT_TYPE,TIMESTAMP,REQUEST_ID,ORGANIZATION_ID,USER_ID,RUN_TIME,CPU_TIME,URI,SESSION_KEY,LOGIN_KEY,ALL_OR_NONE,FAILURE_REASON,IS_REQUEST_COLLATION_ON,NUM_RETRIES,NUM_GRAPH_DEPTH,TIMESTAMP_DERIVED,USER_ID_DERIVED,CLIENT_IP,URI_ID_DERIVED", "024"),
}

# Redundant / raw fields we don't store (TIMESTAMP_DERIVED becomes `timestamp`)
SKIP = {"TIMESTAMP", "USER_ID_DERIVED", "URI_ID_DERIVED", "KEY_ID_DERIVED"}
NUMERIC = {"RUN_TIME", "CPU_TIME", "DB_TOTAL_TIME", "DB_CPU_TIME", "DB_BLOCKS", "RESPONSE_SIZE",
           "REQUEST_SIZE", "VIEW_STATE_SIZE", "ROWS_PROCESSED", "NUMBER_FIELDS", "STATUS_CODE",
           "NUM_ROWS", "SAMPLE_FACTOR", "NUM_RETRIES", "NUM_GRAPH_DEPTH", "COLUMN_NUMBER", "LINE_NUMBER"}
LOWCARD = {"EVENT_TYPE", "ORGANIZATION_ID", "DIRECTIVE", "DISPOSITION", "ACTION", "STATUS",
           "DELIVERY_LOCATION", "KEY_TYPE", "METHOD", "USER_TYPE", "REQUEST_STATUS", "REQUEST_TYPE",
           "HTTP_METHOD", "CONTROLLER_TYPE", "MEDIA_TYPE", "OPERATION_TYPE", "CONCURRENCY_MODE",
           "DML_TYPE", "KEY_PREFIX", "ENTRY_POINT"}


def ch_col(f):
    return "timestamp" if f == "TIMESTAMP_DERIVED" else f.lower()


def ch_type(f):
    if f == "TIMESTAMP_DERIVED":
        return "DateTime64(3)"
    if f in NUMERIC:
        return "Int64"
    if f in LOWCARD:
        return "LowCardinality(String)"
    return "String"


def build(et, table, raw_fields):
    fields = raw_fields.split(",")
    used = [f for f in fields if f not in SKIP]
    has_user = "USER_ID" in used
    # column_map: TIMESTAMP_DERIVED first, then the rest in CSV order (user_name is enriched, not mapped)
    cm_fields = ["TIMESTAMP_DERIVED"] + [f for f in used if f != "TIMESTAMP_DERIVED"]
    cm = "\n".join(f'            "{f}":{" " * max(1, 28 - len(f))}"{ch_col(f)}",' for f in cm_fields)
    numeric = [ch_col(f) for f in used if f in NUMERIC]
    cfg = (f'    "{et}": {{\n'
           f'        "table": "{table}",\n'
           f'        "column_map": {{\n{cm}\n        }},\n'
           f'        "numeric_cols": {numeric},\n'
           f'        "interval": "Hourly",\n'
           f'    }},\n')

    # DDL: timestamp first; then used fields in CSV order (user_name after user_id); log_file_id + ingested_at
    lines = ["    timestamp              DateTime64(3),"]
    for f in used:
        if f == "TIMESTAMP_DERIVED":
            continue
        lines.append(f"    {ch_col(f):22} {ch_type(f)},")
        if f == "USER_ID" and has_user:
            lines.append(f"    {'user_name':22} String,")
    lines.append(f"    {'log_file_id':22} String,")
    lines.append(f"    {'ingested_at':22} DateTime DEFAULT now()")
    ddl = ("CREATE TABLE IF NOT EXISTS salesforceProd.%s\n(\n%s\n)\n"
           "ENGINE = ReplacingMergeTree(ingested_at)\n"
           "PARTITION BY toYYYYMM(timestamp)\n"
           "ORDER BY (timestamp, request_id);\n" % (table, "\n".join(lines)))
    return cfg, ddl


root = pathlib.Path(".")
cfg_blocks, table_blocks = [], []
for et, (table, raw, num) in TYPES.items():
    cfg, ddl = build(et, table, raw)
    cfg_blocks.append(cfg)
    header = ("-- ---------------------------------------------------------------------------\n"
              f"-- {table}  (EventType: {et})\n"
              "-- ---------------------------------------------------------------------------\n")
    table_blocks.append(header + ddl)
    (root / f"schema/migrations/{num}_add_{table}.sql").write_text(
        f"-- Add {table} (EventType: {et}) — security/API/perf EventLogFile coverage.\n"
        f"-- Hourly. timestamp DateTime64(3) (ms) so high-frequency events don't collapse.\n"
        f"-- Rollback: DROP TABLE salesforceProd.{table};\n" + ddl)
    print(f"  migration {num}_add_{table}.sql")

ing = root / "ingest/ingest.py"
src = ing.read_text()
start = src.index("CONFIG: dict[str, dict] = {")
close = src.index("\n}\n", start)
src = src[:close + 1] + "\n" + "\n".join(cfg_blocks) + src[close + 1:]
ing.write_text(src)
print(f"inserted {len(cfg_blocks)} CONFIG entries into ingest.py")

se = root / "schema/schema_events.sql"
se.write_text(se.read_text().rstrip() + "\n\n" + "\n".join(table_blocks))
print(f"appended {len(table_blocks)} tables to schema_events.sql")
