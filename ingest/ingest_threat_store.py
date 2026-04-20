#!/usr/bin/env python3
"""
Salesforce SOQL-based security data → ClickHouse ingestion.

Covers two categories of data, both accessed via SOQL (not EventLogFiles):

1. Shield / Event Monitoring EventStore (Big Objects — requires Shield or Add-On):
   - CredentialStuffingEventStore
   - SessionHijackingEventStore
   - ApiAnomalyEventStore
   - ReportAnomalyEventStore
   - GuestUserAnomalyEventStore

2. Setup Audit Trail (standard, no Shield required):
   - SetupAuditTrail — every admin action in Setup (profiles, fields,
     flows, connected apps, users, permission sets, etc.)

Usage:
    python ingest_threat_store.py                    # sync all, incremental
    python ingest_threat_store.py --backfill         # pull last 90/180 days
    python ingest_threat_store.py --only=CredentialStuffingEventStore
    python ingest_threat_store.py --only=SetupAuditTrail
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import clickhouse_connect
from dotenv import load_dotenv
from simple_salesforce import Salesforce

load_dotenv()

SF_ORG_ALIAS = os.getenv("SF_ORG_ALIAS", "CHProd")
CH_HOST      = os.environ["CH_HOST"].removeprefix("https://").removeprefix("http://")
CH_PORT      = int(os.getenv("CH_PORT", "8443"))
CH_USER      = os.getenv("CH_USER", "default")
CH_PASSWORD  = os.environ["CH_PASSWORD"]
CH_DATABASE  = os.getenv("CH_DATABASE", "salesforceProd")

BATCH_SIZE = 500

# ---------------------------------------------------------------------------
# EventStore config
# Each entry maps a Salesforce Platform Event History object → ClickHouse table.
# ---------------------------------------------------------------------------

THREAT_STORE_CONFIG = {
    "CredentialStuffingEventStore": {
        "table": "credential_stuffing_events",
        "soql_fields": "Id, EventIdentifier, UserId, Username, EventDate, CreatedDate, Summary, Score, PolicyOutcome",
        "column_map": {
            "Id":               "id",
            "EventIdentifier":  "event_identifier",
            "UserId":           "user_id",
            "Username":         "username",
            "EventDate":        "event_date",
            "CreatedDate":      "created_date",
            "Summary":          "summary",
            "Score":            "score",
            "PolicyOutcome":    "policy_outcome",
        },
        "create_sql": """
            CREATE TABLE IF NOT EXISTS {db}.credential_stuffing_events (
                id               String,
                event_identifier String,
                event_date       DateTime,
                created_date     DateTime,
                user_id          String,
                username         String,
                summary          String,
                score            Int32,
                policy_outcome   String
            ) ENGINE = ReplacingMergeTree()
            ORDER BY (event_date, id)
        """,
    },

    "SessionHijackingEventStore": {
        "table": "session_hijacking_events",
        "soql_fields": "Id, EventIdentifier, UserId, Username, EventDate, CreatedDate, Summary, Score, PolicyOutcome",
        "column_map": {
            "Id":               "id",
            "EventIdentifier":  "event_identifier",
            "UserId":           "user_id",
            "Username":         "username",
            "EventDate":        "event_date",
            "CreatedDate":      "created_date",
            "Summary":          "summary",
            "Score":            "score",
            "PolicyOutcome":    "policy_outcome",
        },
        "create_sql": """
            CREATE TABLE IF NOT EXISTS {db}.session_hijacking_events (
                id               String,
                event_identifier String,
                event_date       DateTime,
                created_date     DateTime,
                user_id          String,
                username         String,
                summary          String,
                score            Int32,
                policy_outcome   String
            ) ENGINE = ReplacingMergeTree()
            ORDER BY (event_date, id)
        """,
    },

    "ApiAnomalyEventStore": {
        "table": "api_anomaly_events",
        "soql_fields": "Id, EventIdentifier, UserId, Username, EventDate, CreatedDate, Summary, Score, PolicyOutcome",
        "column_map": {
            "Id":               "id",
            "EventIdentifier":  "event_identifier",
            "UserId":           "user_id",
            "Username":         "username",
            "EventDate":        "event_date",
            "CreatedDate":      "created_date",
            "Summary":          "summary",
            "Score":            "score",
            "PolicyOutcome":    "policy_outcome",
        },
        "create_sql": """
            CREATE TABLE IF NOT EXISTS {db}.api_anomaly_events (
                id               String,
                event_identifier String,
                event_date       DateTime,
                created_date     DateTime,
                user_id          String,
                username         String,
                summary          String,
                score            Int32,
                policy_outcome   String
            ) ENGINE = ReplacingMergeTree()
            ORDER BY (event_date, id)
        """,
    },

    "ReportAnomalyEventStore": {
        "table": "report_anomaly_events",
        "soql_fields": "Id, EventIdentifier, UserId, Username, EventDate, CreatedDate, Summary, Score, PolicyOutcome",
        "column_map": {
            "Id":               "id",
            "EventIdentifier":  "event_identifier",
            "UserId":           "user_id",
            "Username":         "username",
            "EventDate":        "event_date",
            "CreatedDate":      "created_date",
            "Summary":          "summary",
            "Score":            "score",
            "PolicyOutcome":    "policy_outcome",
        },
        "create_sql": """
            CREATE TABLE IF NOT EXISTS {db}.report_anomaly_events (
                id               String,
                event_identifier String,
                event_date       DateTime,
                created_date     DateTime,
                user_id          String,
                username         String,
                summary          String,
                score            Int32,
                policy_outcome   String
            ) ENGINE = ReplacingMergeTree()
            ORDER BY (event_date, id)
        """,
    },

    "GuestUserAnomalyEventStore": {
        "table": "guest_user_anomaly_events",
        "soql_fields": "Id, EventIdentifier, UserId, Username, EventDate, CreatedDate, Summary, Score, PolicyOutcome",
        "column_map": {
            "Id":               "id",
            "EventIdentifier":  "event_identifier",
            "UserId":           "user_id",
            "Username":         "username",
            "EventDate":        "event_date",
            "CreatedDate":      "created_date",
            "Summary":          "summary",
            "Score":            "score",
            "PolicyOutcome":    "policy_outcome",
        },
        "create_sql": """
            CREATE TABLE IF NOT EXISTS {db}.guest_user_anomaly_events (
                id               String,
                event_identifier String,
                event_date       DateTime,
                created_date     DateTime,
                user_id          String,
                username         String,
                summary          String,
                score            Int32,
                policy_outcome   String
            ) ENGINE = ReplacingMergeTree()
            ORDER BY (event_date, id)
        """,
    },
}


# ---------------------------------------------------------------------------
# Setup Audit Trail config
# ---------------------------------------------------------------------------

SETUP_AUDIT_CONFIG = {
    "table": "setup_audit_trail",
    "create_sql": """
        CREATE TABLE IF NOT EXISTS {db}.setup_audit_trail (
            id                   String,
            action               LowCardinality(String),
            section              LowCardinality(String),
            created_date         DateTime,
            created_by_id        String,
            created_by_username  String,
            created_by_name      String,
            display              String,
            delegate_user        String
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (created_date, id)
    """,
}


# ---------------------------------------------------------------------------
# Auth (same as ingest.py — reuses CLI OAuth token)
# ---------------------------------------------------------------------------

def get_sf_client(org_alias: str) -> Salesforce:
    try:
        result = subprocess.run(
            ["sf", "org", "display", "--target-org", org_alias, "--json"],
            capture_output=True, text=True, check=True,
        )
    except FileNotFoundError:
        print("ERROR: Salesforce CLI not found.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Could not retrieve org '{org_alias}'. Run: sf org login web --alias {org_alias}")
        print(e.stderr)
        sys.exit(1)

    data = json.loads(result.stdout).get("result", {})
    access_token = data.get("accessToken")
    instance_url = data.get("instanceUrl")
    if not access_token or not instance_url:
        print(f"ERROR: Missing token for org '{org_alias}'. Run: sf org login web --alias {org_alias}")
        sys.exit(1)
    return Salesforce(instance_url=instance_url, session_id=access_token)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_sf_datetime(raw) -> datetime:
    if not raw:
        return datetime(1970, 1, 2, tzinfo=timezone.utc)
    # Normalise SF's +0000 offset to +00:00 so strptime %z works on all
    # Python versions, and handle the common Z-suffix variants.
    s = str(raw).replace("+0000", "+00:00").replace("-0000", "+00:00")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",   # 2026-01-15T10:30:00.000+00:00  (SF REST API)
        "%Y-%m-%dT%H:%M:%S%z",      # 2026-01-15T10:30:00+00:00
        "%Y-%m-%dT%H:%M:%S.%fZ",    # 2026-01-15T10:30:00.000Z
        "%Y-%m-%dT%H:%M:%SZ",       # 2026-01-15T10:30:00Z
    ):
        try:
            return datetime.strptime(s, fmt).astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue
    return datetime(1970, 1, 2, tzinfo=timezone.utc)


def _insert_batch(client, table: str, rows: list[dict]):
    if not rows:
        return
    columns = list(rows[0].keys())
    data = [[r[c] for c in columns] for r in rows]
    try:
        client.insert(f"{CH_DATABASE}.{table}", data, column_names=columns)
    except Exception as e:
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
# Main sync function
# ---------------------------------------------------------------------------

def sync_threat_store(sf, client, only_objects=None, backfill=False):
    for object_name, cfg in THREAT_STORE_CONFIG.items():
        if only_objects and object_name not in only_objects:
            continue

        print(f"\n[{object_name}] Syncing…")
        table = cfg["table"]

        # Ensure table exists
        client.command(cfg["create_sql"].format(db=CH_DATABASE))

        # Determine how far back to query
        if backfill:
            since_dt = datetime.now(timezone.utc) - timedelta(days=90)
        else:
            try:
                result = client.query(f"SELECT max(event_date) FROM {CH_DATABASE}.{table}")
                latest = result.result_rows[0][0]
                if latest and latest.year > 1970:
                    # Overlap by 1 hour to catch late-arriving events
                    since_dt = latest.replace(tzinfo=timezone.utc) - timedelta(hours=1)
                else:
                    since_dt = datetime.now(timezone.utc) - timedelta(days=30)
            except Exception:
                since_dt = datetime.now(timezone.utc) - timedelta(days=30)

        since_str = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        soql = (
            f"SELECT {cfg['soql_fields']} FROM {object_name} "
            f"WHERE EventDate >= {since_str} "
            f"ORDER BY EventDate ASC LIMIT 2000"
        )
        print(f"  Query: EventDate >= {since_str}")

        try:
            result = sf.query(soql)
        except Exception as e:
            # Object may not be available in all orgs
            print(f"  [skip] {object_name} not accessible: {e}")
            continue

        total = 0
        while True:
            records = result.get("records", [])
            rows = []
            for rec in records:
                row = {}
                for sf_field, ch_col in cfg["column_map"].items():
                    row[ch_col] = rec.get(sf_field) or ""

                # Parse datetime fields
                for date_col in ("event_date", "created_date"):
                    row[date_col] = _parse_sf_datetime(row[date_col])

                # Parse score
                try:
                    row["score"] = int(row.get("score") or 0)
                except (ValueError, TypeError):
                    row["score"] = 0

                rows.append(row)

            if rows:
                _insert_batch(client, table, rows)
                total += len(rows)

            if not result.get("nextRecordsUrl"):
                break
            result = sf.query_more(result["nextRecordsUrl"], identifier_is_url=True)

        print(f"  Inserted {total} record(s) into {table}")


# ---------------------------------------------------------------------------
# Setup Audit Trail sync
# ---------------------------------------------------------------------------

def sync_setup_audit_trail(sf, client, backfill=False):
    """Pull Salesforce Setup Audit Trail records into ClickHouse.

    SetupAuditTrail captures every admin action in Setup — profile changes,
    custom field creation/deletion, flow activation, connected app changes,
    user management, permission set assignments, login settings, etc.
    No Shield license required; available to all orgs.

    SF retains 180 days of audit trail data.
    """
    cfg = SETUP_AUDIT_CONFIG
    table = cfg["table"]

    client.command(cfg["create_sql"].format(db=CH_DATABASE))

    if backfill:
        since_dt = datetime.now(timezone.utc) - timedelta(days=180)
    else:
        try:
            result = client.query(f"SELECT max(created_date) FROM {CH_DATABASE}.{table}")
            latest = result.result_rows[0][0]
            if latest and latest.year > 1970:
                since_dt = latest.replace(tzinfo=timezone.utc) - timedelta(hours=1)
            else:
                since_dt = datetime.now(timezone.utc) - timedelta(days=30)
        except Exception:
            since_dt = datetime.now(timezone.utc) - timedelta(days=30)

    since_str = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n[SetupAuditTrail] Syncing from {since_str}…")

    soql = (
        f"SELECT Id, Action, Section, CreatedDate, CreatedById, "
        f"CreatedBy.Username, CreatedBy.Name, Display, DelegateUser "
        f"FROM SetupAuditTrail "
        f"WHERE CreatedDate >= {since_str} "
        f"ORDER BY CreatedDate ASC"
    )

    try:
        result = sf.query(soql)
    except Exception as e:
        print(f"  [skip] SetupAuditTrail not accessible: {e}")
        return

    total = 0
    while True:
        records = result.get("records", [])
        rows = []
        for rec in records:
            created_by = rec.get("CreatedBy") or {}
            row = {
                "id":                  rec.get("Id") or "",
                "action":              rec.get("Action") or "",
                "section":             rec.get("Section") or "",
                "created_date":        _parse_sf_datetime(rec.get("CreatedDate")),
                "created_by_id":       rec.get("CreatedById") or "",
                "created_by_username": created_by.get("Username") or "",
                "created_by_name":     created_by.get("Name") or "",
                "display":             rec.get("Display") or "",
                "delegate_user":       rec.get("DelegateUser") or "",
            }
            rows.append(row)

        if rows:
            _insert_batch(client, table, rows)
            total += len(rows)

        if not result.get("nextRecordsUrl"):
            break
        result = sf.query_more(result["nextRecordsUrl"], identifier_is_url=True)

    print(f"  Inserted {total} record(s) into {table}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    backfill = "--backfill" in args
    org_alias = next((a for a in args if not a.startswith("--")), SF_ORG_ALIAS)

    only_flag = next((a for a in args if a.startswith("--only=")), None)
    only_objects = set(only_flag.split("=", 1)[1].split(",")) if only_flag else None

    print(f"Connecting to Salesforce (org: {org_alias})…")
    sf = get_sf_client(org_alias)
    print(f"  Authenticated → {sf.sf_instance}")

    print("Connecting to ClickHouse…")
    client = clickhouse_connect.get_client(
        host=CH_HOST, port=CH_PORT, username=CH_USER,
        password=CH_PASSWORD, database=CH_DATABASE, secure=True,
    )
    print(f"  Connected to {CH_HOST}:{CH_PORT}/{CH_DATABASE}")

    # Threat store objects (Shield / Event Monitoring Add-On)
    # sync_threat_store handles --only= filtering internally.
    if only_objects is None or only_objects & set(THREAT_STORE_CONFIG.keys()):
        sync_threat_store(sf, client, only_objects=only_objects, backfill=backfill)

    # Setup Audit Trail (no Shield required — available to all orgs)
    if only_objects is None or "SetupAuditTrail" in only_objects:
        sync_setup_audit_trail(sf, client, backfill=backfill)

    print("\nDone.")


if __name__ == "__main__":
    main()
