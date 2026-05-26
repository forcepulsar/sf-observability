#!/usr/bin/env python3
"""
Run OPTIMIZE TABLE on all SharedReplacingMergeTree event tables after ingestion.
This forces ClickHouse to merge all unmerged parts, eliminating duplicate rows
so queries return correct results without needing FINAL.

Usage:
    python3 schema/optimize_tables.py
Or via the ingest container:
    docker compose exec ingest python3 /app/schema/optimize_tables.py
"""
import os, logging, clickhouse_connect
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("optimize")

CH_HOST     = os.environ["CH_HOST"].removeprefix("https://").removeprefix("http://")
CH_PORT     = int(os.environ.get("CH_PORT", 8443))
CH_USER     = os.environ.get("CH_USER", "default")
CH_PASSWORD = os.environ["CH_PASSWORD"]
CH_DATABASE = os.environ.get("CH_DATABASE", "salesforceProd")

# All SharedReplacingMergeTree event tables
TABLES = [
    "rest_api_events",
    "uri_events",
    "api_events",
    "apex_callout_events",
    "named_credential_events",
    "flow_execution_events",
    "bulk_api2_events",
    "login_events",
    "bulk_api_events",
    "metadata_api_events",
    "apex_exception_events",
    "login_as_events",
    "permission_update_events",
    "insufficient_access_events",
    "report_export_events",
    "apex_execution_events",
    "apex_trigger_events",
    "lightning_interaction_events",
    "lightning_page_view_events",
    "api_total_usage_events",
]

def optimize():
    client = clickhouse_connect.get_client(
        host=CH_HOST, port=CH_PORT, username=CH_USER,
        password=CH_PASSWORD, database=CH_DATABASE, secure=True,
        settings={"max_execution_time": 300},
    )
    for table in TABLES:
        log.info(f"Optimizing {table}…")
        client.command(f"OPTIMIZE TABLE {CH_DATABASE}.{table}")
    log.info("Done.")

if __name__ == "__main__":
    optimize()
