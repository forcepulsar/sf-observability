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
import fcntl
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import clickhouse_connect
from dotenv import load_dotenv

import metrics
from sf_auth import get_sf_client

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SF_ORG_ALIAS     = os.getenv("SF_ORG_ALIAS", "MyOrg")

# JWT/ECA auth (recommended for production — never expires between runs)
SF_JWT_CLIENT_ID = os.getenv("SF_JWT_CLIENT_ID", "").strip()
SF_JWT_KEY_FILE  = os.getenv("SF_JWT_KEY_FILE", "").strip()
SF_JWT_USERNAME  = os.getenv("SF_JWT_USERNAME", "").strip()

CH_HOST     = os.environ["CH_HOST"].removeprefix("https://").removeprefix("http://")
CH_PORT     = int(os.getenv("CH_PORT", "8443"))
CH_USER     = os.getenv("CH_USER", "default")
CH_PASSWORD = os.environ["CH_PASSWORD"]
CH_DATABASE = os.getenv("CH_DATABASE", "salesforceProd")

BATCH_SIZE = 1000

# ---------------------------------------------------------------------------
# Logging — writes to stdout and optionally to LOG_FILE if set in .env
# ---------------------------------------------------------------------------

def _setup_logging() -> logging.Logger:
    fmt = "[%(asctime)s] %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    log_file = os.getenv("LOG_FILE", "").strip()
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=handlers)
    return logging.getLogger("ingest")

log = _setup_logging()


# ---------------------------------------------------------------------------
# P5: Pre-flight config validation
# ---------------------------------------------------------------------------

def validate_config() -> None:
    errors = []
    has_jwt   = SF_JWT_CLIENT_ID and SF_JWT_KEY_FILE and SF_JWT_USERNAME
    has_token = os.environ.get("SF_ACCESS_TOKEN") and os.environ.get("SF_INSTANCE_URL")
    if not (has_jwt or has_token):
        errors.append(
            "Salesforce auth not configured. JWT/ECA is required: set "
            "SF_JWT_CLIENT_ID, SF_JWT_KEY_FILE, SF_JWT_USERNAME. "
            "See .env.example for setup instructions."
        )
    if SF_JWT_KEY_FILE and not Path(SF_JWT_KEY_FILE).exists():
        errors.append(f"SF_JWT_KEY_FILE not found: {SF_JWT_KEY_FILE}")
    if not os.environ.get("CH_PASSWORD"):
        errors.append("CH_PASSWORD is not set.")
    if not CH_HOST:
        errors.append("CH_HOST is not set.")
    for err in errors:
        log.error(f"Config error: {err}")
    if errors:
        sys.exit(1)

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

    # SalesforceLoginAs — Salesforce Support logging in as a user.
    # Completely different schema from LoginAs: no session/delegation fields.
    # CSV: ACTUAL_USER_ID, OPERATION, IP_ADDRESS, CASE_ID
    # Shares login_as_events table; distinguish by event_type column.
    "SalesforceLoginAs": {
        "table": "login_as_events",
        "column_map": {
            "TIMESTAMP_DERIVED": "timestamp",
            "EVENT_TYPE":        "event_type",
            "REQUEST_ID":        "request_id",
            "ORGANIZATION_ID":   "organization_id",
            "ACTUAL_USER_ID":    "actual_user_id",
            "OPERATION":         "operation",
            "IP_ADDRESS":        "client_ip",
            "CASE_ID":           "case_id",
        },
        "numeric_cols": [],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # Logout  → logout_events  (completes the Login/session lifecycle)
    # CSV: EVENT_TYPE, TIMESTAMP(_DERIVED), REQUEST_ID, ORGANIZATION_ID, USER_ID,
    #   USER_TYPE, SESSION_TYPE/LEVEL, BROWSER/PLATFORM/RESOLUTION/APP_TYPE,
    #   CLIENT_VERSION, API_TYPE/VERSION, USER_INITIATED_LOGOUT, SESSION_KEY,
    #   LOGIN_KEY, CLIENT_IP. user_name is enriched from user_id (not in the CSV).
    # Published Daily for this org.
    # ------------------------------------------------------------------
    "Logout": {
        "table": "logout_events",
        "column_map": {
            "TIMESTAMP_DERIVED":     "timestamp",
            "EVENT_TYPE":            "event_type",
            "REQUEST_ID":            "request_id",
            "ORGANIZATION_ID":       "organization_id",
            "USER_ID":               "user_id",
            "USER_TYPE":             "user_type",
            "SESSION_TYPE":          "session_type",
            "SESSION_LEVEL":         "session_level",
            "BROWSER_TYPE":          "browser_type",
            "PLATFORM_TYPE":         "platform_type",
            "RESOLUTION_TYPE":       "resolution_type",
            "APP_TYPE":              "app_type",
            "CLIENT_VERSION":        "client_version",
            "API_TYPE":              "api_type",
            "API_VERSION":           "api_version",
            "USER_INITIATED_LOGOUT": "user_initiated_logout",
            "SESSION_KEY":           "session_key",
            "LOGIN_KEY":             "login_key",
            "CLIENT_IP":             "client_ip",
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
        "interval": "Hourly",
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
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # API (SOAP)  → api_events
    # CSV: EVENT_TYPE, TIMESTAMP_DERIVED, USER_ID, USER_NAME, METHOD_NAME,
    #   ENTITY_NAME, RUN_TIME, CPU_TIME, CLIENT_IP, ROWS_PROCESSED, CLIENT_NAME,
    #   API_TYPE, API_VERSION, EXCEPTION_MESSAGE, QUERY, REQUEST_SIZE, RESPONSE_SIZE
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
            "CLIENT_NAME":       "client_name",
        },
        "numeric_cols": ["run_time_ns", "cpu_time_ns", "rows_processed"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # RestApi  → rest_api_events
    # CSV: EVENT_TYPE, TIMESTAMP_DERIVED, USER_ID, METHOD, URI, STATUS_CODE,
    #   USER_AGENT, CLIENT_IP, RUN_TIME, CPU_TIME, CONNECTED_APP_ID, ENTITY_NAME,
    #   QUERY, EXCEPTION_MESSAGE, ROWS_PROCESSED, CLIENT_NAME, MEDIA_TYPE, etc.
    # ------------------------------------------------------------------
    "RestApi": {
        "table": "rest_api_events",
        "column_map": {
            "TIMESTAMP_DERIVED":  "timestamp",
            "EVENT_TYPE":         "event_type",
            "REQUEST_ID":         "request_id",
            "ORGANIZATION_ID":    "organization_id",
            "USER_ID":            "user_id",
            "USER_NAME":          "user_name",
            "METHOD":             "method",
            "URI":                "uri",
            "STATUS_CODE":        "status_code",
            "USER_AGENT":         "user_agent",
            "CLIENT_IP":          "client_ip",
            "RUN_TIME":           "run_time_ns",
            "CPU_TIME":           "cpu_time_ns",
            "CONNECTED_APP_ID":   "connected_app_id",
            "ENTITY_NAME":        "entity_name",
            "QUERY":              "query",
            "EXCEPTION_MESSAGE":  "exception_message",
            "ROWS_PROCESSED":     "rows_processed",
        },
        "numeric_cols": ["status_code", "run_time_ns", "cpu_time_ns", "rows_processed"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # BulkApi  → bulk_api_events
    # CSV: JOB_ID, BATCH_ID, OPERATION_TYPE, ENTITY_TYPE, ROWS_PROCESSED,
    #   SUCCESS, NUMBER_FAILURES, MESSAGE
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
            "JOB_ID":            "job_id",
            "BATCH_ID":          "batch_id",
            "OPERATION_TYPE":    "operation",
            "ENTITY_TYPE":       "object_type",
            "ROWS_PROCESSED":    "rows_processed",
            "SUCCESS":           "status",
        },
        "numeric_cols": ["rows_processed"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # BulkApi2  → bulk_api2_events
    # CSV: JOB_ID, OPERATION_TYPE, ENTITY_TYPE, JOB_STATUS, RECORDS_PROCESSED,
    #   RECORDS_FAILED, RESULT_SIZE_MB, ERROR_MESSAGE
    # ------------------------------------------------------------------
    "BulkApi2": {
        "table": "bulk_api2_events",
        "column_map": {
            "TIMESTAMP_DERIVED":  "timestamp",
            "EVENT_TYPE":         "event_type",
            "REQUEST_ID":         "request_id",
            "ORGANIZATION_ID":    "organization_id",
            "USER_ID":            "user_id",
            "USER_NAME":          "user_name",
            "JOB_ID":             "job_id",
            "OPERATION_TYPE":     "operation",
            "ENTITY_TYPE":        "object_type",
            "RECORDS_PROCESSED":  "rows_processed",
            "JOB_STATUS":         "status",
            "RECORDS_FAILED":     "records_failed",
            "ERROR_MESSAGE":      "error_message",
        },
        "numeric_cols": ["rows_processed", "records_failed"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # ApexCallout  → apex_callout_events
    # CSV: TYPE, METHOD, SUCCESS, STATUS_CODE, TIME, REQUEST_SIZE, RESPONSE_SIZE, URL
    # Note: CLASS_NAME does not exist in CSV
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
            "TYPE":              "type",
        },
        "numeric_cols": ["status_code", "callout_time_ns"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # NamedCredential  → named_credential_events
    # CSV: NAMED_CREDENTIAL_NAME, CALLER_PACKAGE_NAMESPACE, URI, RUN_TIME
    # Note: METHOD and STATUS_CODE do not exist in this event type's CSV
    # ------------------------------------------------------------------
    "NamedCredential": {
        "table": "named_credential_events",
        "column_map": {
            "TIMESTAMP_DERIVED":      "timestamp",
            "EVENT_TYPE":             "event_type",
            "REQUEST_ID":             "request_id",
            "ORGANIZATION_ID":        "organization_id",
            "USER_ID":                "user_id",
            "USER_NAME":              "user_name",
            "NAMED_CREDENTIAL_NAME":  "named_credential_id",
            "URI":                    "uri",
            "RUN_TIME":               "run_time_ns",
        },
        "numeric_cols": ["run_time_ns"],
        "interval": "Hourly",
    },

    # ------------------------------------------------------------------
    # MetadataApiOperation  → metadata_api_events
    # CSV: CLIENT_ID, OPERATION, API_VERSION
    # Note: TYPE and ENTITY_NAME do not exist in this event type's CSV
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
            "CLIENT_ID":         "client_id",
            "RUN_TIME":          "run_time_ns",
        },
        "numeric_cols": ["run_time_ns"],
        "interval": "Hourly",
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
    # CSV: FLOW_VERSION_ID, PROCESS_TYPE, FLOW_LOAD_TIME, TOTAL_EXECUTION_TIME,
    #   NUMBER_OF_INTERVIEWS, NUMBER_OF_ERRORS
    # Note: FLOW_ID, FLOW_NAME, RUN_TIME, CPU_TIME, IS_INTERVIEW_LIMIT_HIT
    #   do not exist in CSV — those columns remain as legacy defaults
    # ------------------------------------------------------------------
    "FlowExecution": {
        "table": "flow_execution_events",
        "column_map": {
            "TIMESTAMP_DERIVED":       "timestamp",
            "EVENT_TYPE":              "event_type",
            "REQUEST_ID":              "request_id",
            "ORGANIZATION_ID":         "organization_id",
            "USER_ID":                 "user_id",
            "USER_NAME":               "user_name",
            "FLOW_VERSION_ID":         "flow_id",
            "PROCESS_TYPE":            "process_type",
            "TOTAL_EXECUTION_TIME":    "total_execution_time_ns",
            "NUMBER_OF_INTERVIEWS":    "number_of_interviews",
            "NUMBER_OF_ERRORS":        "number_of_errors",
        },
        "numeric_cols": ["total_execution_time_ns", "number_of_interviews", "number_of_errors"],
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
    # ------------------------------------------------------------------
    # ApexExecution  → apex_execution_events
    # Note: LIMIT_USAGE_PERCENT does not exist in CSV
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
            "NUMBER_SOQL_QUERIES":  "number_soql_queries",
        },
        "numeric_cols": ["cpu_time_ns", "run_time_ns", "number_soql_queries"],
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
        "interval": "Hourly",
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
    # ApiTotalUsageHourly → api_total_usage_events (same table, hourly files)
    # Gives connected app attribution with ~1h lag instead of 24h.
    # Salesforce generates 2 Sequence files per hour for high-volume orgs,
    # so limit_override=50 ensures we capture all sequences for the last 24h.
    # ReplacingMergeTree deduplicates overlap with the daily file automatically.
    # backfill_as_hourly=True preserves Hourly interval during --backfill runs.
    # backfill_limit_override=500 fetches ~10 days of hourly files per backfill run.
    # ------------------------------------------------------------------
    "ApiTotalUsageHourly": {
        "table": "api_total_usage_events",
        "sf_event_type": "ApiTotalUsage",
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
        "interval": "Hourly",
        "limit_override": 50,
        "backfill_as_hourly": True,
        "backfill_limit_override": 500,
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
        "interval": "Hourly",
    },

    # Report -> report_events (security/access coverage, Hourly)
    "Report": {
        "table": "report_events",
        "column_map": {
            "TIMESTAMP_DERIVED":         "timestamp",
            "EVENT_TYPE":                "event_type",
            "REQUEST_ID":                "request_id",
            "ORGANIZATION_ID":           "organization_id",
            "USER_ID":                   "user_id",
            "RUN_TIME":                  "run_time",
            "CPU_TIME":                  "cpu_time",
            "URI":                       "uri",
            "SESSION_KEY":               "session_key",
            "LOGIN_KEY":                 "login_key",
            "USER_TYPE":                 "user_type",
            "REQUEST_STATUS":            "request_status",
            "DB_TOTAL_TIME":             "db_total_time",
            "ENTITY_NAME":               "entity_name",
            "DISPLAY_TYPE":              "display_type",
            "RENDERING_TYPE":            "rendering_type",
            "REPORT_ID":                 "report_id",
            "ROW_COUNT":                 "row_count",
            "NUMBER_EXCEPTION_FILTERS":  "number_exception_filters",
            "NUMBER_COLUMNS":            "number_columns",
            "UI_NUMBER_COLUMNS":         "ui_number_columns",
            "AVERAGE_ROW_SIZE":          "average_row_size",
            "SORT":                      "sort",
            "DB_BLOCKS":                 "db_blocks",
            "DB_CPU_TIME":               "db_cpu_time",
            "NUMBER_BUCKETS":            "number_buckets",
            "CLIENT_IP":                 "client_ip",
            "ORIGIN":                    "origin",
        },
        "numeric_cols": ['run_time', 'cpu_time', 'db_total_time', 'row_count', 'number_exception_filters', 'number_columns', 'ui_number_columns', 'average_row_size', 'db_blocks', 'db_cpu_time', 'number_buckets'],
        "interval": "Hourly",
    },

    # Dashboard -> dashboard_events (security/access coverage, Hourly)
    "Dashboard": {
        "table": "dashboard_events",
        "column_map": {
            "TIMESTAMP_DERIVED":         "timestamp",
            "EVENT_TYPE":                "event_type",
            "REQUEST_ID":                "request_id",
            "ORGANIZATION_ID":           "organization_id",
            "USER_ID":                   "user_id",
            "RUN_TIME":                  "run_time",
            "CPU_TIME":                  "cpu_time",
            "URI":                       "uri",
            "SESSION_KEY":               "session_key",
            "LOGIN_KEY":                 "login_key",
            "DASHBOARD_COMPONENT_ID":    "dashboard_component_id",
            "DASHBOARD_ID":              "dashboard_id",
            "REPORT_ID":                 "report_id",
            "IS_SUCCESS":                "is_success",
            "DASHBOARD_TYPE":            "dashboard_type",
            "IS_SCHEDULED":              "is_scheduled",
            "VIEWING_USER_ID":           "viewing_user_id",
            "CLIENT_IP":                 "client_ip",
        },
        "numeric_cols": ['run_time', 'cpu_time'],
        "interval": "Hourly",
    },

    # Search -> search_events (security/access coverage, Hourly)
    "Search": {
        "table": "search_events",
        "column_map": {
            "TIMESTAMP_DERIVED":         "timestamp",
            "EVENT_TYPE":                "event_type",
            "REQUEST_ID":                "request_id",
            "ORGANIZATION_ID":           "organization_id",
            "USER_ID":                   "user_id",
            "QUERY_ID":                  "query_id",
            "NUM_RESULTS":               "num_results",
            "SEARCH_QUERY":              "search_query",
            "PREFIXES_SEARCHED":         "prefixes_searched",
        },
        "numeric_cols": ['num_results'],
        "interval": "Hourly",
    },

    # SearchClick -> search_click_events (security/access coverage, Hourly)
    "SearchClick": {
        "table": "search_click_events",
        "column_map": {
            "TIMESTAMP_DERIVED":         "timestamp",
            "EVENT_TYPE":                "event_type",
            "REQUEST_ID":                "request_id",
            "ORGANIZATION_ID":           "organization_id",
            "USER_ID":                   "user_id",
            "QUERY_ID":                  "query_id",
            "CLICKED_RECORD_ID":         "clicked_record_id",
            "RANK":                      "rank",
        },
        "numeric_cols": ['rank'],
        "interval": "Hourly",
    },

    # ContentTransfer -> content_transfer_events (security/access coverage, Hourly)
    "ContentTransfer": {
        "table": "content_transfer_events",
        "column_map": {
            "TIMESTAMP_DERIVED":         "timestamp",
            "EVENT_TYPE":                "event_type",
            "REQUEST_ID":                "request_id",
            "ORGANIZATION_ID":           "organization_id",
            "USER_ID":                   "user_id",
            "TRANSACTION_TYPE":          "transaction_type",
            "DOCUMENT_ID":               "document_id",
            "VERSION_ID":                "version_id",
            "FILE_TYPE":                 "file_type",
            "FILE_PREVIEW_TYPE":         "file_preview_type",
            "SIZE_BYTES":                "size_bytes",
        },
        "numeric_cols": ['size_bytes'],
        "interval": "Hourly",
    },

    # DocumentAttachmentDownloads -> document_attachment_download_events (security/access coverage, Hourly)
    "DocumentAttachmentDownloads": {
        "table": "document_attachment_download_events",
        "column_map": {
            "TIMESTAMP_DERIVED":         "timestamp",
            "EVENT_TYPE":                "event_type",
            "REQUEST_ID":                "request_id",
            "ORGANIZATION_ID":           "organization_id",
            "USER_ID":                   "user_id",
            "ENTITY_ID":                 "entity_id",
            "FILE_TYPE":                 "file_type",
        },
        "numeric_cols": [],
        "interval": "Hourly",
    },

    # Attachment -> attachment_events (security/access coverage, Hourly)
    "Attachment": {
        "table": "attachment_events",
        "column_map": {
            "TIMESTAMP_DERIVED":         "timestamp",
            "EVENT_TYPE":                "event_type",
            "REQUEST_ID":                "request_id",
            "ORGANIZATION_ID":           "organization_id",
            "USER_ID":                   "user_id",
            "PARENT_ID":                 "parent_id",
            "ATTACHMENT_ID":             "attachment_id",
            "CONTENT_TYPE":              "content_type",
            "OPERATION":                 "operation",
            "IS_PRIVATE_ON":             "is_private_on",
        },
        "numeric_cols": [],
        "interval": "Hourly",
    },

    # ContentDocumentLink -> content_document_link_events (security/access coverage, Hourly)
    "ContentDocumentLink": {
        "table": "content_document_link_events",
        "column_map": {
            "TIMESTAMP_DERIVED":         "timestamp",
            "EVENT_TYPE":                "event_type",
            "REQUEST_ID":                "request_id",
            "ORGANIZATION_ID":           "organization_id",
            "USER_ID":                   "user_id",
            "DOCUMENT_ID":               "document_id",
            "SHARED_WITH_ENTITY_ID":     "shared_with_entity_id",
            "SHARING_PERMISSION":        "sharing_permission",
            "SHARING_OPERATION":         "sharing_operation",
        },
        "numeric_cols": [],
        "interval": "Hourly",
    },

    # GroupMembership -> group_membership_events (security/access coverage, Hourly)
    "GroupMembership": {
        "table": "group_membership_events",
        "column_map": {
            "TIMESTAMP_DERIVED":         "timestamp",
            "EVENT_TYPE":                "event_type",
            "REQUEST_ID":                "request_id",
            "ORGANIZATION_ID":           "organization_id",
            "USER_ID":                   "user_id",
            "RUN_TIME":                  "run_time",
            "CPU_TIME":                  "cpu_time",
            "URI":                       "uri",
            "SESSION_KEY":               "session_key",
            "LOGIN_KEY":                 "login_key",
            "OPERATION":                 "operation",
            "GROUP_TYPE":                "group_type",
            "GROUP_ID":                  "group_id",
            "MEMBER_ID":                 "member_id",
            "CLIENT_IP":                 "client_ip",
        },
        "numeric_cols": ['run_time', 'cpu_time'],
        "interval": "Hourly",
    },
}


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
    # FINAL ensures we read a consistent deduplicated view of ingestion_state
    # (SharedReplacingMergeTree may hold unmerged duplicate rows between flushes)
    result = client.query(
        f"SELECT DISTINCT log_file_id FROM {CH_DATABASE}.ingestion_state FINAL "
        f"WHERE log_file_id IN ({placeholders})"
    )
    return {row[0] for row in result.result_rows}


def record_ingestion(client, log_file_id: str, event_type: str, log_date: str, interval: str, row_count: int):
    parsed_date = datetime.fromisoformat(log_date.replace("Z", "+00:00")).date()
    client.insert(
        f"{CH_DATABASE}.ingestion_state",
        [[log_file_id, event_type, parsed_date, interval, row_count]],
        column_names=["log_file_id", "event_type", "log_date", "interval", "row_count"],
    )


def _insert_batch(client, table: str, rows: list[dict]) -> int:
    """Insert a batch of rows. Returns number of rows skipped due to errors."""
    if not rows:
        return 0
    columns = list(rows[0].keys())
    data = [[r[c] for c in columns] for r in rows]
    try:
        client.insert(f"{CH_DATABASE}.{table}", data, column_names=columns)
        return 0
    except Exception as e:
        log.warning(f"  Batch insert failed ({e}), retrying row-by-row…")
        skipped = 0
        for row in rows:
            try:
                client.insert(f"{CH_DATABASE}.{table}", [[row[c] for c in columns]], column_names=columns)
            except Exception:
                skipped += 1
        if skipped:
            log.warning(f"  Skipped {skipped} bad row(s) in {table}")
        return skipped


# ---------------------------------------------------------------------------
# Per-file ingestion
# ---------------------------------------------------------------------------

def ingest_file(sf, client, file_meta: dict, cfg: dict, user_map: dict | None = None,
                smoke: bool = False) -> int:
    """Download one EventLogFile CSV and insert rows into the appropriate ClickHouse table."""
    log_file_id = file_meta["Id"]
    table = cfg["table"]
    url = f"https://{sf.sf_instance}{file_meta['LogFile']}"

    # P2: retry with exponential backoff for transient Salesforce errors (429, 5xx).
    # A missed file within the 24h retention window is permanent data loss.
    for attempt in range(3):
        response = sf.session.get(
            url,
            headers={"Authorization": f"Bearer {sf.session_id}"},
            stream=True,
            timeout=600,  # 10 min — large daily files on slow connections need headroom
        )
        if response.status_code in (429, 500, 502, 503) and attempt < 2:
            wait = 10 * (2 ** attempt)  # 10s → 20s
            log.warning(f"  HTTP {response.status_code} from Salesforce, retrying in {wait}s…")
            time.sleep(wait)
            continue
        response.raise_for_status()
        break

    # Dynamic chunk size: target ~100 iterations per file, bounded 1MB–2MB.
    # Reduces Python loop overhead for large files vs a fixed 64KB chunk.
    content_length = int(response.headers.get("content-length", 0))
    chunk_size = (
        min(max(1024 * 1024, content_length // 100), 2 * 1024 * 1024)
        if content_length else 1024 * 1024
    )

    tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False)
    try:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                tmp.write(chunk)
        tmp.flush()
        tmp.close()

        with open(tmp.name, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = []
            total = 0
            skipped = 0

            for raw in reader:
                rows.append(parse_row(raw, log_file_id, cfg, user_map))
                if smoke and total + len(rows) >= 10:
                    # Smoke test: stop after 10 rows — enough to verify permissions + mapping
                    skipped += _insert_batch(client, table, rows)
                    total += len(rows)
                    rows = []
                    break
                if len(rows) >= BATCH_SIZE:
                    skipped += _insert_batch(client, table, rows)
                    total += len(rows)
                    rows = []

            if rows:
                skipped += _insert_batch(client, table, rows)
                total += len(rows)
    finally:
        os.unlink(tmp.name)

    if not smoke:
        # Don't record smoke runs — they should always re-test on next invocation
        record_ingestion(client, log_file_id, file_meta["EventType"], file_meta["LogDate"], file_meta["Interval"], total)
    return total, skipped


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def sync_users(sf, client):
    """Pull all Salesforce users into the ClickHouse lookup table."""
    log.info("Syncing Salesforce users…")
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
    log.info(f"  Synced {len(rows)} users")


def main():
    args = sys.argv[1:]
    backfill  = "--backfill" in args
    smoke     = "--smoke"    in args   # quick validation: 1 file, 10 rows per event type
    org_alias = next((a for a in args if not a.startswith("--")), SF_ORG_ALIAS)

    only_flag = next((a for a in args if a.startswith("--only=")), None)
    only_types = set(only_flag.split("=", 1)[1].split(",")) if only_flag else None

    # P1: Prevent concurrent runs (skip lock for smoke tests and targeted backfills
    # — both are safe to run alongside a live cycle; backfill uses --only to scope
    # to a single event type and already_ingested() prevents double-writing).
    if not smoke and not (backfill and only_types):
        lock_path = Path(os.getenv("LOCK_FILE", "/tmp/sf_ingest.lock"))
        lock_fh = open(lock_path, "w")
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            log.warning("Another ingest process is already running — exiting to avoid duplicates.")
            sys.exit(0)

    validate_config()

    run_id = metrics.new_run_id()
    run_started = datetime.now(timezone.utc)
    log.info(f"Run {run_id} started at {run_started.isoformat()}Z")

    log.info(f"Connecting to Salesforce (org: {org_alias})…")
    sf = get_sf_client(org_alias)
    log.info(f"  Authenticated → {sf.sf_instance}")

    log.info("Connecting to ClickHouse…")
    client = clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD,
        database=CH_DATABASE,
        secure=True,
        compress=True,          # LZ4 compression on inserts — reduces transfer size >50%
    )
    log.info(f"  Connected to {CH_HOST}:{CH_PORT}/{CH_DATABASE}")

    # Non-fatal: user sync uses a separate auth path that can expire independently.
    # On failure the run continues with the cached users table in ClickHouse.
    try:
        sync_users(sf, client)
    except Exception as e:
        log.warning(f"  [warn] sync_users failed (skipping): {e}")

    log.info("Building user lookup map…")
    user_result = client.query(
        f"SELECT id, username FROM {CH_DATABASE}.users WHERE username != ''"
    )
    user_map: dict[str, str] = {}
    for full_id, username in user_result.result_rows:
        user_map[full_id] = username
        user_map[full_id[:15]] = username
    log.info(f"  {len(user_result.result_rows)} users loaded")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _make_ch_client():
        """Each thread needs its own ClickHouse client — sessions are not thread-safe."""
        return clickhouse_connect.get_client(
            host=CH_HOST, port=CH_PORT, username=CH_USER,
            password=CH_PASSWORD, database=CH_DATABASE,
            secure=True, compress=True,
        )

    smoke_results: list[tuple[str, bool, int, str]] = []

    def process_event_type(event_type, cfg):
        if only_types and event_type not in only_types:
            return 0, 0, 0
        interval = cfg["interval"] if (backfill and cfg.get("backfill_as_hourly")) else ("Daily" if backfill else cfg["interval"])
        if smoke:
            limit = 1
        elif backfill:
            # Hourly event types need a larger limit per backfill run — 2 sequences/hour × 24h × days
            limit = cfg.get("backfill_limit_override", 90)
        else:
            # Allow per-event-type limit override (e.g. hourly ApiTotalUsage has 2 sequences/hour)
            limit = cfg.get("limit_override", 24)
        thread_client = _make_ch_client()

        # P4: explicit date-range filter in normal mode so the intent is unambiguous
        # and gaps can't occur silently if > limit files exist (e.g. after an outage).
        # Smoke test: no date filter — always fetch the single most recent file regardless of age.
        if smoke:
            mode_label  = "smoke (most recent file)"
            date_filter = ""
        elif backfill:
            mode_label  = "backfill (daily, last 90)"
            date_filter = ""
        else:
            now = datetime.now(timezone.utc)
            if interval == "Hourly":
                cutoff = (now - timedelta(hours=limit)).strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                cutoff = (now - timedelta(days=limit)).strftime("%Y-%m-%dT00:00:00Z")
            mode_label  = f"{interval.lower()}, last {limit}"
            date_filter = f"AND LogDate >= {cutoff} "

        log.info(f"\n[{event_type}] Querying EventLogFiles ({mode_label})…")

        # sf_event_type allows the config key to differ from the Salesforce EventType
        # (e.g. "ApiTotalUsageHourly" config key → EventType = "ApiTotalUsage")
        sf_event_type = cfg.get("sf_event_type", event_type)
        result = sf.query(
            f"SELECT Id, EventType, LogDate, LogFile, Interval "
            f"FROM EventLogFile "
            f"WHERE EventType = '{sf_event_type}' AND Interval = '{interval}' "
            f"{date_filter}"
            f"ORDER BY LogDate DESC LIMIT {limit}"
        )
        files = result["records"]
        log.info(f"[{event_type}] Found {len(files)} file(s)")

        if not files:
            return 0, 0, 0

        if smoke:
            new_files = files[:1]  # always re-test most recent file, skip state check
        else:
            done      = already_ingested(thread_client, [f["Id"] for f in files])
            new_files = [f for f in files if f["Id"] not in done]
            log.info(f"[{event_type}] {len(done)} already ingested, {len(new_files)} new")

        type_files  = 0
        type_rows   = 0
        type_errors = 0
        for f in new_files:
            log.info(f"[{event_type}] Ingesting {f['Id']} ({f['LogDate']}) → {cfg['table']}…")
            try:
                log_date = datetime.fromisoformat(f["LogDate"].replace("Z", "+00:00")).date()
            except (ValueError, TypeError, KeyError):
                log_date = None
            try:
                with metrics.timed_event(
                    thread_client, CH_DATABASE, run_id, "ingest",
                    event_type, "elf", f["Id"], log_date,
                ) as set_rows:
                    row_count, row_skipped = ingest_file(sf, thread_client, f, cfg, user_map, smoke=smoke)
                    set_rows(row_count)
                if row_skipped:
                    log.warning(f"[{event_type}] {row_count} inserted, {row_skipped} skipped (schema mismatch?)")
                    type_errors += row_skipped
                else:
                    log.info(f"[{event_type}] {row_count} rows inserted")
                type_files += 1
                type_rows  += row_count
                if smoke:
                    smoke_results.append((event_type, True, row_count, ""))
            except Exception as e:
                type_errors += 1
                log.error(f"[{event_type}] ERROR ingesting {f['Id']}: {e}")
                if smoke:
                    smoke_results.append((event_type, False, 0, str(e)[:60]))
        if smoke and not new_files:
            smoke_results.append((event_type, True, 0, "no files available"))
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
                log.error(f"[{et}] ERROR: {exc}")

    metrics.record_run(
        client, CH_DATABASE, run_id, "ingest",
        run_started, datetime.now(timezone.utc),
        grand_total_files, grand_total_rows, grand_total_errors,
    )

    log.info(f"\nDone. {grand_total_files} file(s), {grand_total_rows} row(s), {grand_total_errors} error(s).")

    if smoke:
        passed = [r for r in smoke_results if r[1]]
        failed = [r for r in smoke_results if not r[1]]
        log.info("")
        log.info("╔══════════════════════════════════════════════════════╗")
        log.info("║              SMOKE TEST RESULTS                      ║")
        log.info("╠══════════════════════════════════════════════════════╣")
        for et, ok, rows, msg in sorted(smoke_results, key=lambda x: x[0]):
            note = f"{rows} rows" if ok and rows else (msg or "ok")
            status = "✓" if ok else "✗"
            log.info(f"║  {status}  {et:<36} {note}")
        log.info("╠══════════════════════════════════════════════════════╣")
        log.info(f"║  PASS: {len(passed)}/{len(smoke_results)}   FAIL: {len(failed):<30}║")
        log.info("╚══════════════════════════════════════════════════════╝")
        if failed:
            sys.exit(1)


if __name__ == "__main__":
    main()
