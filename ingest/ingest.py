#!/usr/bin/env python3
"""
Salesforce EventLogFile → ClickHouse Cloud ingestion script.

Usage:
    # One-time Salesforce auth (opens browser):
    sf org login web --alias prod

    # Fill in ClickHouse credentials:
    cp .env.example .env

    pip install -r requirements.txt
    python ingest.py [--backfill] [<org_alias>]
"""

import csv
import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime

import clickhouse_connect
from dotenv import load_dotenv
from simple_salesforce import Salesforce

import metrics

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SF_ORG_ALIAS = os.getenv("SF_ORG_ALIAS", "CHProd")

CH_HOST     = os.environ["CH_HOST"].removeprefix("https://").removeprefix("http://")
CH_PORT     = int(os.getenv("CH_PORT", "8443"))
CH_USER     = os.getenv("CH_USER", "default")
CH_PASSWORD = os.environ["CH_PASSWORD"]
CH_DATABASE = os.getenv("CH_DATABASE", "salesforceProd")

BATCH_SIZE = 1000

# ---------------------------------------------------------------------------
# Per-event-type configuration
#
# Each key is the Salesforce EventType string.
# Values:
#   table        – ClickHouse target table (within CH_DATABASE)
#   column_map   – SF CSV column name → ClickHouse column name
#   numeric_cols – ClickHouse column names that must be cast to int (default 0)
#   interval     – "Hourly" | "Daily" (which SF log interval to query)
# ---------------------------------------------------------------------------

CONFIG: dict[str, dict] = {
    # ------------------------------------------------------------------
    # Login  (pre-existing table, kept exactly as before)
    # ------------------------------------------------------------------
    "Login": {
        "table": "login_events",
        "column_map": {
            "TIMESTAMP_DERIVED":      "timestamp",
            "EVENT_TYPE":             "event_type",
            "REQUEST_ID":             "request_id",
            "ORGANIZATION_ID":        "organization_id",
            "USER_ID":                "user_id",
            "USER_NAME":              "user_name",
            "USER_TYPE":              "user_type",
            "LOGIN_STATUS":           "login_status",
            "LOGIN_TYPE":             "login_type",
            "CLIENT_IP":              "client_ip",
            "BROWSER_TYPE":           "browser_type",
            "PLATFORM_TYPE":          "platform_type",
            "CPU_TIME":               "cpu_time_ns",
            "RUN_TIME":               "run_time_ns",
            "SESSION_KEY":            "session_key",
            "LOGIN_KEY":              "login_key",
            "API_TYPE":               "api_type",
            "API_VERSION":            "api_version",
            "CIPHER_SUITE":           "cipher_suite",
            "AUTHENTICATION_SERVICE": "authentication_service",
        },
        "numeric_cols": ["cpu_time_ns", "run_time_ns"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # LoginAs / SalesforceLoginAs  → login_as_events
    # ------------------------------------------------------------------
    "LoginAs": {
        "table": "login_as_events",
        "column_map": {
            "TIMESTAMP_DERIVED":        "timestamp",
            "EVENT_TYPE":               "event_type",
            "REQUEST_ID":               "request_id",
            "ORGANIZATION_ID":          "organization_id",
            "USER_ID":                  "user_id",
            "USER_NAME":                "user_name",
            "DELEGATED_USER_ID":        "delegated_user_id",
            "DELEGATED_USER_NAME":      "delegated_user_name",
            "DELEGATED_ORGANIZATION_ID": "delegated_organization_id",
            "LOGIN_KEY":                "login_key",
            "SESSION_KEY":              "session_key",
            "CLIENT_IP":                "client_ip",
            "LOGIN_TYPE":               "login_type",
        },
        "numeric_cols": [],
        "interval": "Hourly",
    },

    # SalesforceLoginAs is an alias for the same table
    "SalesforceLoginAs": {
        "table": "login_as_events",
        "column_map": {
            "TIMESTAMP_DERIVED":        "timestamp",
            "EVENT_TYPE":               "event_type",
            "REQUEST_ID":               "request_id",
            "ORGANIZATION_ID":          "organization_id",
            "USER_ID":                  "user_id",
            "USER_NAME":                "user_name",
            "DELEGATED_USER_ID":        "delegated_user_id",
            "DELEGATED_USER_NAME":      "delegated_user_name",
            "DELEGATED_ORGANIZATION_ID": "delegated_organization_id",
            "LOGIN_KEY":                "login_key",
            "SESSION_KEY":              "session_key",
            "CLIENT_IP":                "client_ip",
            "LOGIN_TYPE":               "login_type",
        },
        "numeric_cols": [],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # ReportExport  → report_export_events
    # CSV cols: EVENT_TYPE, TIMESTAMP_DERIVED, REQUEST_ID, ORGANIZATION_ID,
    #   USER_ID, USER_ID_DERIVED, URI_ID_DERIVED, CLIENT_IP, RUN_TIME, CPU_TIME
    # NOTE: no USER_NAME, ROWS_PROCESSED, FORMAT, BROWSER_TYPE in actual CSV
    # ------------------------------------------------------------------
    "ReportExport": {
        "table": "report_export_events",
        "column_map": {
            "TIMESTAMP_DERIVED": "timestamp",
            "EVENT_TYPE":        "event_type",
            "REQUEST_ID":        "request_id",
            "ORGANIZATION_ID":   "organization_id",
            "USER_ID_DERIVED":   "user_id",
            "URI_ID_DERIVED":    "report_id",
            "CLIENT_IP":         "client_ip",
            "RUN_TIME":          "run_time_ns",
            "CPU_TIME":          "cpu_time_ns",
        },
        "numeric_cols": ["run_time_ns", "cpu_time_ns"],
        "interval": "Daily",
    },

    # ------------------------------------------------------------------
    # InsufficientAccess  → insufficient_access_events
    # CSV cols: EVENT_TYPE, TIMESTAMP_DERIVED, REQUEST_ID, ORGANIZATION_ID,
    #   USER_ID, USER_ID_DERIVED, RECORD_ID, ENTITY_TYPE, ACCESS_ERROR,
    #   REQUESTED_ACCESS_LEVEL, ERROR_DESCRIPTION
    # NOTE: no USER_NAME, CLIENT_IP in actual CSV
    # ------------------------------------------------------------------
    "InsufficientAccess": {
        "table": "insufficient_access_events",
        "column_map": {
            "TIMESTAMP_DERIVED":       "timestamp",
            "EVENT_TYPE":              "event_type",
            "REQUEST_ID":              "request_id",
            "ORGANIZATION_ID":         "organization_id",
            "USER_ID_DERIVED":         "user_id",
            "RECORD_ID":               "resource_id",
            "ENTITY_TYPE":             "resource_type",
            "REQUESTED_ACCESS_LEVEL":  "action",
            "ACCESS_ERROR":            "access_error",
            "ERROR_DESCRIPTION":       "error_description",
        },
        "numeric_cols": [],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # PermissionUpdate  → permission_update_events
    # CSV cols: EVENT_TYPE, TIMESTAMP_DERIVED, REQUEST_ID, ORGANIZATION_ID,
    #   USER_ID, FEATURE_ID, UPDATE_TYPE, PERMISSION_TYPE, CONTEXT, DESCRIPTION
    # NOTE: no USER_NAME, MODIFIED_USER_*, PERMISSION_SET_NAME in actual CSV.
    #   Events represent field/object permission changes, not permission set assignments.
    # ------------------------------------------------------------------
    "PermissionUpdate": {
        "table": "permission_update_events",
        "column_map": {
            "TIMESTAMP_DERIVED": "timestamp",
            "EVENT_TYPE":        "event_type",
            "REQUEST_ID":        "request_id",
            "ORGANIZATION_ID":   "organization_id",
            "USER_ID":           "user_id",
            "FEATURE_ID":        "permission_set_id",
            "PERMISSION_TYPE":   "permission_set_name",
            "UPDATE_TYPE":       "action",
            "DESCRIPTION":       "description",
        },
        "numeric_cols": [],
        "interval": "Daily",
    },

    # ------------------------------------------------------------------
    # API (SOAP)  → api_events
    # ------------------------------------------------------------------
    "API": {
        "table": "api_events",
        "column_map": {
            "TIMESTAMP_DERIVED": "timestamp",
            "EVENT_TYPE":        "event_type",
            "REQUEST_ID":        "request_id",
            "ORGANIZATION_ID":   "organization_id",
            "USER_ID":           "user_id",
            "USER_NAME":         "user_name",
            "METHOD_NAME":       "method_name",
            "ENTITY_NAME":       "entity_name",
            "RUN_TIME":          "run_time_ns",
            "CPU_TIME":          "cpu_time_ns",
            "CLIENT_IP":         "client_ip",
            "ROWS_PROCESSED":    "rows_processed",
        },
        "numeric_cols": ["run_time_ns", "cpu_time_ns", "rows_processed"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # RestApi  → rest_api_events
    # ------------------------------------------------------------------
    "RestApi": {
        "table": "rest_api_events",
        "column_map": {
            "TIMESTAMP_DERIVED": "timestamp",
            "EVENT_TYPE":        "event_type",
            "REQUEST_ID":        "request_id",
            "ORGANIZATION_ID":   "organization_id",
            "USER_ID":           "user_id",
            "USER_NAME":         "user_name",
            "METHOD":            "method",
            "URI":               "uri",
            "STATUS_CODE":       "status_code",
            "USER_AGENT":        "user_agent",
            "CLIENT_IP":         "client_ip",
            "RUN_TIME":          "run_time_ns",
            "CPU_TIME":          "cpu_time_ns",
        },
        "numeric_cols": ["status_code", "run_time_ns", "cpu_time_ns"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # BulkApi  → bulk_api_events
    # ------------------------------------------------------------------
    "BulkApi": {
        "table": "bulk_api_events",
        "column_map": {
            "TIMESTAMP_DERIVED": "timestamp",
            "EVENT_TYPE":        "event_type",
            "REQUEST_ID":        "request_id",
            "ORGANIZATION_ID":   "organization_id",
            "USER_ID":           "user_id",
            "USER_NAME":         "user_name",
            "JOB_ID_DERIVED":    "job_id",
            "BATCH_ID":          "batch_id",
            "OPERATION":         "operation",
            "OBJECT_TYPE":       "object_type",
            "ROWS_PROCESSED":    "rows_processed",
            "STATUS":            "status",
        },
        "numeric_cols": ["rows_processed"],
        "interval": "Daily",
    },

    # ------------------------------------------------------------------
    # BulkApi2  → bulk_api2_events
    # ------------------------------------------------------------------
    "BulkApi2": {
        "table": "bulk_api2_events",
        "column_map": {
            "TIMESTAMP_DERIVED": "timestamp",
            "EVENT_TYPE":        "event_type",
            "REQUEST_ID":        "request_id",
            "ORGANIZATION_ID":   "organization_id",
            "USER_ID":           "user_id",
            "USER_NAME":         "user_name",
            "JOB_ID_DERIVED":    "job_id",
            "OPERATION":         "operation",
            "OBJECT_TYPE":       "object_type",
            "ROWS_PROCESSED":    "rows_processed",
            "STATUS":            "status",
        },
        "numeric_cols": ["rows_processed"],
        "interval": "Daily",
    },

    # ------------------------------------------------------------------
    # ApexCallout  → apex_callout_events
    # ------------------------------------------------------------------
    "ApexCallout": {
        "table": "apex_callout_events",
        "column_map": {
            "TIMESTAMP_DERIVED": "timestamp",
            "EVENT_TYPE":        "event_type",
            "REQUEST_ID":        "request_id",
            "ORGANIZATION_ID":   "organization_id",
            "USER_ID":           "user_id",
            "USER_NAME":         "user_name",
            "URL":               "callout_url",
            "METHOD":            "method",
            "STATUS_CODE":       "status_code",
            "TIME":              "callout_time_ns",
            "CLASS_NAME":        "class_name",
            "TYPE":              "type",
        },
        "numeric_cols": ["status_code", "callout_time_ns"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # NamedCredential  → named_credential_events
    # ------------------------------------------------------------------
    "NamedCredential": {
        "table": "named_credential_events",
        "column_map": {
            "TIMESTAMP_DERIVED":    "timestamp",
            "EVENT_TYPE":           "event_type",
            "REQUEST_ID":           "request_id",
            "ORGANIZATION_ID":      "organization_id",
            "USER_ID":              "user_id",
            "USER_NAME":            "user_name",
            "NAMED_CREDENTIAL_ID":  "named_credential_id",
            "URI":                  "uri",
            "METHOD":               "method",
            "STATUS_CODE":          "status_code",
            "RUN_TIME":             "run_time_ns",
        },
        "numeric_cols": ["status_code", "run_time_ns"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # MetadataApiOperation  → metadata_api_events
    # ------------------------------------------------------------------
    "MetadataApiOperation": {
        "table": "metadata_api_events",
        "column_map": {
            "TIMESTAMP_DERIVED": "timestamp",
            "EVENT_TYPE":        "event_type",
            "REQUEST_ID":        "request_id",
            "ORGANIZATION_ID":   "organization_id",
            "USER_ID":           "user_id",
            "USER_NAME":         "user_name",
            "OPERATION":         "operation",
            "TYPE":              "entity_type",
            "ENTITY_NAME":       "entity_name",
            "RUN_TIME":          "run_time_ns",
        },
        "numeric_cols": ["run_time_ns"],
        "interval": "Daily",
    },

    # ------------------------------------------------------------------
    # ApexUnexpectedException  → apex_exception_events
    # ------------------------------------------------------------------
    "ApexUnexpectedException": {
        "table": "apex_exception_events",
        "column_map": {
            "TIMESTAMP_DERIVED":  "timestamp",
            "EVENT_TYPE":         "event_type",
            "REQUEST_ID":         "request_id",
            "ORGANIZATION_ID":    "organization_id",
            "USER_ID":            "user_id",
            "USER_NAME":          "user_name",
            "EXCEPTION_TYPE":     "exception_type",
            "EXCEPTION_MESSAGE":  "exception_message",
            "STACK_TRACE":        "stack_trace",
            "CLASS_NAME":         "class_name",
            "METHOD_NAME":        "method_name",
        },
        "numeric_cols": [],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # FlowExecution  → flow_execution_events
    # ------------------------------------------------------------------
    "FlowExecution": {
        "table": "flow_execution_events",
        "column_map": {
            "TIMESTAMP_DERIVED":      "timestamp",
            "EVENT_TYPE":             "event_type",
            "REQUEST_ID":             "request_id",
            "ORGANIZATION_ID":        "organization_id",
            "USER_ID":                "user_id",
            "USER_NAME":              "user_name",
            "FLOW_ID":                "flow_id",
            "FLOW_NAME":              "flow_name",
            "RUN_TIME":               "run_time_ns",
            "CPU_TIME":               "cpu_time_ns",
            "IS_INTERVIEW_LIMIT_HIT": "interview_limit_hit",
        },
        "numeric_cols": ["run_time_ns", "cpu_time_ns", "interview_limit_hit"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # URI  → uri_events
    # ------------------------------------------------------------------
    "URI": {
        "table": "uri_events",
        "column_map": {
            "TIMESTAMP_DERIVED": "timestamp",
            "EVENT_TYPE":        "event_type",
            "REQUEST_ID":        "request_id",
            "ORGANIZATION_ID":   "organization_id",
            "USER_ID":           "user_id",
            "USER_NAME":         "user_name",
            "URI":               "uri",
            "METHOD":            "method",
            "RUN_TIME":          "run_time_ns",
            "CPU_TIME":          "cpu_time_ns",
            "BROWSER_TYPE":      "browser_type",
            "CLIENT_IP":         "client_ip",
        },
        "numeric_cols": ["run_time_ns", "cpu_time_ns"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # ApexExecution  → apex_execution_events
    # Used for Anonymous Apex detection: filter WHERE quiddity = 'X'
    # Quiddity values: A=Aura, E=AuraEnabled, X=Anonymous, etc.
    # ------------------------------------------------------------------
    "ApexExecution": {
        "table": "apex_execution_events",
        "column_map": {
            "TIMESTAMP_DERIVED":    "timestamp",
            "EVENT_TYPE":           "event_type",
            "REQUEST_ID":           "request_id",
            "ORGANIZATION_ID":      "organization_id",
            "USER_ID":              "user_id",
            "USER_NAME":            "user_name",
            "QUIDDITY":             "quiddity",
            "ENTRY_POINT":          "entry_point",
            "CPU_TIME":             "cpu_time_ns",
            "RUN_TIME":             "run_time_ns",
            "LIMIT_USAGE_PERCENT":  "limit_usage_percent",
        },
        "numeric_cols": ["cpu_time_ns", "run_time_ns", "limit_usage_percent"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # PackageInstall  → package_install_events
    # Correct ELF type for package installation tracking
    # ------------------------------------------------------------------
    "PackageInstall": {
        "table": "package_install_events",
        "column_map": {
            "TIMESTAMP_DERIVED":    "timestamp",
            "EVENT_TYPE":           "event_type",
            "REQUEST_ID":           "request_id",
            "ORGANIZATION_ID":      "organization_id",
            "USER_ID":              "user_id",
            "USER_NAME":            "user_name",
            "PACKAGE_NAMESPACE":    "package_namespace",
            "PACKAGE_VERSION_ID":   "package_version_id",
            "INSTALL_TYPE":         "install_type",
        },
        "numeric_cols": [],
        "interval": "Daily",
    },

    # ------------------------------------------------------------------
    # ApexTrigger  → apex_trigger_events
    # ------------------------------------------------------------------
    "ApexTrigger": {
        "table": "apex_trigger_events",
        "column_map": {
            "TIMESTAMP_DERIVED":    "timestamp",
            "EVENT_TYPE":           "event_type",
            "REQUEST_ID":           "request_id",
            "ORGANIZATION_ID":      "organization_id",
            "USER_ID":              "user_id",
            "USER_NAME":            "user_name",
            "ENTITY_NAME":          "entity_name",
            "TRIGGER_ID":           "trigger_id",
            "TYPE":                 "trigger_type",
            "CPU_TIME":             "cpu_time_ns",
            "RUN_TIME":             "run_time_ns",
            "EXEC_TIME":            "exec_time_ns",
            "CALLOUT_TIME":         "callout_time_ns",
            "NUM_DML_STATEMENTS":   "num_dml_statements",
            "SOQL_QUERY_COUNT":     "soql_query_count",
            "LIMIT_USAGE_PERCENT":  "limit_usage_percent",
        },
        "numeric_cols": ["cpu_time_ns", "run_time_ns", "exec_time_ns", "callout_time_ns", "num_dml_statements", "soql_query_count", "limit_usage_percent"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # LightningInteraction  → lightning_interaction_events
    # ------------------------------------------------------------------
    "LightningInteraction": {
        "table": "lightning_interaction_events",
        "column_map": {
            "TIMESTAMP_DERIVED":        "timestamp",
            "EVENT_TYPE":               "event_type",
            "REQUEST_ID":               "request_id",
            "ORGANIZATION_ID":          "organization_id",
            "USER_IDENTIFIER":          "user_id",
            "APP_NAME":                 "app_name",
            "PAGE_APP_NAME":            "page_app_name",
            "PAGE_CONTEXT":             "page_context",
            "PAGE_ENTITY_TYPE":         "page_entity_type",
            "PAGE_ENTITY_ID":           "page_entity_id",
            "COMPONENT_NAME":           "component_name",
            "TARGET":                   "target",
            "TARGET_TYPE":              "target_type",
            "PAGE_URL":                 "page_url",
            "BROWSER_NAME":             "browser_name",
            "DEVICE_PLATFORM":          "device_platform",
            "OPERATING_SYSTEM_NAME":    "os_name",
            "DURATION":                 "duration_ms",
            "NOTE":                     "note",
        },
        "numeric_cols": ["duration_ms"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # LightningPageView  → lightning_page_view_events
    # Used for: Lightning page load times, slow pages, browser/device breakdown
    # Key fields: EFFECTIVE_PAGE_TIME (ms), PAGE_URL, APP_NAME
    # ------------------------------------------------------------------
    "LightningPageView": {
        "table": "lightning_page_view_events",
        "column_map": {
            "TIMESTAMP_DERIVED":              "timestamp",
            "EVENT_TYPE":                     "event_type",
            "REQUEST_ID":                     "request_id",
            "ORGANIZATION_ID":                "organization_id",
            "USER_IDENTIFIER":                "user_id",
            "APP_NAME":                       "app_name",
            "PAGE_APP_NAME":                  "page_app_name",
            "BROWSER_NAME":                   "browser_name",
            "CLIENT_GEOLOCATION":             "client_geolocation",
            "DEVICE_PLATFORM":                "device_platform",
            "OPERATING_SYSTEM_NAME":          "os_name",
            "PAGE_OBJECT_TYPE":               "page_object_type",
            "PAGE_URL":                       "page_url",
            "PAGE_CONTEXT":                   "page_context",
            "EFFECTIVE_PAGE_TIME":            "effective_page_time_ms",
            "DOES_EFFECTIVE_PAGE_TIME_DEVIATE": "does_page_time_deviate",
        },
        "numeric_cols": ["effective_page_time_ms", "does_page_time_deviate"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # ApiTotalUsage  → api_total_usage_events
    # Used for: total API call volume, errors by API family, top resources
    # ------------------------------------------------------------------
    "ApiTotalUsage": {
        "table": "api_total_usage_events",
        "column_map": {
            "TIMESTAMP_DERIVED":        "timestamp",
            "EVENT_TYPE":               "event_type",
            "REQUEST_ID":               "request_id",
            "ORGANIZATION_ID":          "organization_id",
            "USER_ID":                  "user_id",
            "USER_NAME":                "user_name",
            "API_FAMILY":               "api_family",
            "API_VERSION":              "api_version",
            "HTTP_METHOD":              "http_method",
            "STATUS_CODE":              "status_code",
            "CLIENT_NAME":              "client_name",
            "CLIENT_IP":                "client_ip",
            "CONNECTED_APP_ID":         "connected_app_id",
            "CONNECTED_APP_NAME":       "connected_app_name",
            "API_RESOURCE":             "api_resource",
            "ENTITY_NAME":              "entity_name",
            "COUNTS_AGAINST_API_LIMIT": "counts_against_api_limit",
            "API_CLIENT_CATEGORY":      "api_client_category",
        },
        "numeric_cols": ["status_code", "counts_against_api_limit"],
        "interval": "Daily",
    },

    # ------------------------------------------------------------------
    # FlowNavMetric  → flow_nav_metric_events
    # Used for: flow execution counts, error rates, slow flows
    # ------------------------------------------------------------------
    "FlowNavMetric": {
        "table": "flow_nav_metric_events",
        "column_map": {
            "TIMESTAMP_DERIVED":        "timestamp",
            "EVENT_TYPE":               "event_type",
            "REQUEST_ID":               "request_id",
            "ORGANIZATION_ID":          "organization_id",
            "FLOW_VERSION_IDENTIFIER":  "flow_version_id",
            "TOTAL_EXECUTION_TIME":     "total_execution_time_ms",
            "ERROR_COUNT":              "error_count",
        },
        "numeric_cols": ["total_execution_time_ms", "error_count"],
        "interval": "Daily",
    },
}


# ---------------------------------------------------------------------------
# Salesforce auth via CLI (no credentials stored on disk)
# ---------------------------------------------------------------------------

def get_sf_client(org_alias: str) -> Salesforce:
    """Authenticate via access token, SF CLI, or username/password (in that priority order)."""

    # 1. Explicit access token — set SF_ACCESS_TOKEN + SF_INSTANCE_URL in .env
    #    Get the token from: sf org display --target-org CHProd --json
    access_token = os.environ.get("SF_ACCESS_TOKEN", "").strip()
    instance_url = os.environ.get("SF_INSTANCE_URL", "").strip()
    if access_token and instance_url:
        print(f"  Auth: access token ({instance_url})")
        return Salesforce(instance_url=instance_url, session_id=access_token)

    # 2. SF CLI token — works when running locally with `sf org login web`
    try:
        result = subprocess.run(
            ["sf", "org", "display", "--target-org", org_alias, "--json"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout).get("result", {})
        access_token = data.get("accessToken")
        instance_url = data.get("instanceUrl")
        if access_token and instance_url:
            print(f"  Auth: Salesforce CLI token ({org_alias})")
            return Salesforce(instance_url=instance_url, session_id=access_token)
    except Exception:
        pass

    # 3. Username/password — uses SF_USERNAME / SF_PASSWORD / SF_SECURITY_TOKEN from .env
    username = os.environ.get("SF_USERNAME")
    password = os.environ.get("SF_PASSWORD")
    token    = os.environ.get("SF_SECURITY_TOKEN", "").strip()
    domain   = os.environ.get("SF_DOMAIN", "login")
    if username and password:
        print(f"  Auth: username/password ({username})")
        return Salesforce(username=username, password=password, security_token=token, domain=domain)

    print(f"ERROR: No valid Salesforce auth. Set SF_ACCESS_TOKEN+SF_INSTANCE_URL in .env, "
          f"run `sf org login web --alias {org_alias}`, or set SF_USERNAME/SF_PASSWORD.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Row parsing
# ---------------------------------------------------------------------------

def parse_row(raw: dict, log_file_id: str, cfg: dict, user_map: dict | None = None) -> dict:
    """Map one CSV row to a ClickHouse insert dict using the given config entry."""
    row = {}
    for sf_col, ch_col in cfg["column_map"].items():
        row[ch_col] = raw.get(sf_col, "")

    # Resolve user_name from user_id when the event log CSV leaves it blank.
    # SF stores 15-char IDs in event logs; the users table has 18-char IDs.
    # user_map contains both forms as keys so either will match.
    if user_map and not row.get("user_name") and row.get("user_id"):
        uid = row["user_id"]
        row["user_name"] = user_map.get(uid) or user_map.get(uid[:15], "")

    # Normalize timestamp: SF format is "2024-03-15T12:34:56.789Z"
    ts_raw = row.get("timestamp", "")
    try:
        row["timestamp"] = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%S.%fZ")
    except (ValueError, TypeError):
        row["timestamp"] = datetime(1970, 1, 1)

    # Numeric fields default to 0
    for col in cfg["numeric_cols"]:
        try:
            row[col] = int(row[col]) if row[col] else 0
        except (ValueError, TypeError):
            row[col] = 0

    row["log_file_id"] = log_file_id
    return row


# ---------------------------------------------------------------------------
# ClickHouse helpers
# ---------------------------------------------------------------------------

def already_ingested(client, log_file_ids: list[str]) -> set[str]:
    if not log_file_ids:
        return set()
    placeholders = ", ".join(f"'{fid}'" for fid in log_file_ids)
    result = client.query(
        f"SELECT DISTINCT log_file_id FROM {CH_DATABASE}.ingestion_state "
        f"WHERE log_file_id IN ({placeholders})"
    )
    return {row[0] for row in result.result_rows}


def record_ingestion(client, log_file_id: str, event_type: str, log_date: str, row_count: int):
    parsed_date = datetime.fromisoformat(log_date.replace("Z", "+00:00")).date()
    client.insert(
        f"{CH_DATABASE}.ingestion_state",
        [[log_file_id, event_type, parsed_date, row_count]],
        column_names=["log_file_id", "event_type", "log_date", "row_count"],
    )


def _insert_batch(client, table: str, rows: list[dict]):
    if not rows:
        return
    columns = list(rows[0].keys())
    data = [[r[c] for c in columns] for r in rows]
    try:
        client.insert(f"{CH_DATABASE}.{table}", data, column_names=columns)
    except Exception as e:
        # Retry row-by-row to isolate and skip bad rows
        print(f"\n  [warn] Batch insert failed ({e}), retrying row-by-row…")
        skipped = 0
        for row in rows:
            try:
                client.insert(f"{CH_DATABASE}.{table}", [[row[c] for c in columns]], column_names=columns)
            except Exception:
                skipped += 1
        if skipped:
            print(f"  [warn] Skipped {skipped} bad row(s) in {table}")


# ---------------------------------------------------------------------------
# Per-file ingestion
# ---------------------------------------------------------------------------

def ingest_file(sf, client, file_meta: dict, cfg: dict, user_map: dict | None = None) -> int:
    """Download one EventLogFile CSV and insert rows into the appropriate ClickHouse table."""
    log_file_id = file_meta["Id"]
    table = cfg["table"]
    url = f"https://{sf.sf_instance}{file_meta['LogFile']}"

    response = sf.session.get(
        url,
        headers={"Authorization": f"Bearer {sf.session_id}"},
        stream=True,
        timeout=300,
    )
    response.raise_for_status()

    # Download to a temp file in 64KB chunks so large files don't exhaust
    # memory and Salesforce's connection timeout can't interrupt CSV parsing.
    tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False)
    try:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                tmp.write(chunk)
        tmp.flush()
        tmp.close()

        with open(tmp.name, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = []
            total = 0

            for raw in reader:
                rows.append(parse_row(raw, log_file_id, cfg, user_map))
                if len(rows) >= BATCH_SIZE:
                    _insert_batch(client, table, rows)
                    total += len(rows)
                    rows = []

            if rows:
                _insert_batch(client, table, rows)
                total += len(rows)
    finally:
        os.unlink(tmp.name)

    record_ingestion(client, log_file_id, file_meta["EventType"], file_meta["LogDate"], total)
    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def sync_users(sf, client):
    """Pull all Salesforce users into the ClickHouse lookup table."""
    print("Syncing Salesforce users…")
    result = sf.query(
        "SELECT Id, Username, Name, FirstName, LastName, Email, "
        "Title, Department, UserType, IsActive, ProfileId, Profile.Name FROM User LIMIT 2000"
    )
    users = result["records"]
    while result.get("nextRecordsUrl"):
        result = sf.query_more(result["nextRecordsUrl"], identifier_is_url=True)
        users.extend(result["records"])

    rows = [[
        u["Id"],
        u.get("Username") or "",
        u.get("Name") or "",
        u.get("FirstName") or "",
        u.get("LastName") or "",
        u.get("Email") or "",
        u.get("Title") or "",
        u.get("Department") or "",
        u.get("UserType") or "",
        1 if u.get("IsActive") else 0,
        u.get("ProfileId") or "",
        (u.get("Profile") or {}).get("Name") or "",
    ] for u in users]

    client.insert(
        f"{CH_DATABASE}.users", rows,
        column_names=["id","username","name","first_name","last_name",
                      "email","title","department","user_type","is_active",
                      "profile_id","profile_name"],
    )
    print(f"  Synced {len(rows)} users")


def main():
    args = sys.argv[1:]
    backfill = "--backfill" in args
    org_alias = next((a for a in args if not a.startswith("--")), SF_ORG_ALIAS)

    only_flag = next((a for a in args if a.startswith("--only=")), None)
    only_types = set(only_flag.split("=", 1)[1].split(",")) if only_flag else None

    run_id = metrics.new_run_id()
    run_started = datetime.utcnow()
    print(f"Run {run_id} started at {run_started.isoformat()}Z")

    print(f"Connecting to Salesforce (org: {org_alias})…")
    sf = get_sf_client(org_alias)
    print(f"  Authenticated via CLI → {sf.sf_instance}")

    print("Connecting to ClickHouse…")
    client = clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD,
        database=CH_DATABASE,
        secure=True,
        compress=True,          # LZ4 compression on inserts — reduces transfer size >50%
    )
    print(f"  Connected to {CH_HOST}:{CH_PORT}/{CH_DATABASE}")

    sync_users(sf, client)

    # Build user_id → username map so parse_row can enrich rows where
    # the SF event log CSV leaves user_name blank. Both the 18-char ID
    # (from the users table) and the 15-char ID (used in event logs) are
    # stored as keys so either format matches without truncation logic in
    # the hot path.
    print("Building user lookup map…")
    user_result = client.query(
        f"SELECT id, username FROM {CH_DATABASE}.users WHERE username != ''"
    )
    user_map: dict[str, str] = {}
    for full_id, username in user_result.result_rows:
        user_map[full_id] = username
        user_map[full_id[:15]] = username
    print(f"  {len(user_result.result_rows)} users loaded")

    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    _print_lock = threading.Lock()

    def _make_ch_client():
        """Each thread needs its own ClickHouse client — sessions are not thread-safe."""
        return clickhouse_connect.get_client(
            host=CH_HOST, port=CH_PORT, username=CH_USER,
            password=CH_PASSWORD, database=CH_DATABASE,
            secure=True, compress=True,
        )

    def process_event_type(event_type, cfg):
        if only_types and event_type not in only_types:
            return 0, 0, 0
        interval = "Daily" if backfill else cfg["interval"]
        limit    = 90      if backfill else 24
        thread_client = _make_ch_client()

        mode_label = "backfill (daily, last 90)" if backfill else f"{interval.lower()}, last {limit}"
        with _print_lock:
            print(f"\n[{event_type}] Querying EventLogFiles ({mode_label})…")

        result = sf.query(
            f"SELECT Id, EventType, LogDate, LogFile, Interval "
            f"FROM EventLogFile "
            f"WHERE EventType = '{event_type}' AND Interval = '{interval}' "
            f"ORDER BY LogDate DESC LIMIT {limit}"
        )
        files = result["records"]
        with _print_lock:
            print(f"[{event_type}] Found {len(files)} file(s)")

        if not files:
            return 0, 0, 0

        done      = already_ingested(thread_client, [f["Id"] for f in files])
        new_files = [f for f in files if f["Id"] not in done]
        with _print_lock:
            print(f"[{event_type}] {len(done)} already ingested, {len(new_files)} new")

        type_files  = 0
        type_rows   = 0
        type_errors = 0
        for f in new_files:
            with _print_lock:
                print(f"[{event_type}] Ingesting {f['Id']} ({f['LogDate']}) → {cfg['table']}…", flush=True)
            try:
                log_date = datetime.fromisoformat(f["LogDate"].replace("Z", "+00:00")).date()
            except (ValueError, TypeError, KeyError):
                log_date = None
            try:
                with metrics.timed_event(
                    thread_client, CH_DATABASE, run_id, "ingest",
                    event_type, "elf", f["Id"], log_date,
                ) as set_rows:
                    row_count = ingest_file(sf, thread_client, f, cfg, user_map)
                    set_rows(row_count)
                with _print_lock:
                    print(f"[{event_type}] {row_count} rows inserted")
                type_files += 1
                type_rows  += row_count
            except Exception as e:
                type_errors += 1
                with _print_lock:
                    print(f"[{event_type}] ERROR ingesting {f['Id']}: {e}")
        return type_files, type_rows, type_errors

    grand_total_files  = 0
    grand_total_rows   = 0
    grand_total_errors = 0

    # Run up to 6 event types in parallel — Salesforce API and ClickHouse both handle concurrent requests fine
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(process_event_type, et, cfg): et for et, cfg in CONFIG.items()}
        for future in as_completed(futures):
            et = futures[future]
            try:
                f_count, r_count, e_count = future.result()
                grand_total_files  += f_count
                grand_total_rows   += r_count
                grand_total_errors += e_count
            except Exception as exc:
                grand_total_errors += 1
                print(f"[{et}] ERROR: {exc}")

    metrics.record_run(
        client, CH_DATABASE, run_id, "ingest",
        run_started, datetime.utcnow(),
        grand_total_files, grand_total_rows, grand_total_errors,
    )

    print(f"\nDone. {grand_total_files} file(s), {grand_total_rows} row(s), {grand_total_errors} error(s).")


if __name__ == "__main__":
    main()
