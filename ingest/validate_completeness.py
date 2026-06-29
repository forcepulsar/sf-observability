#!/usr/bin/env python3
"""Completeness check — hourly ingestion vs the authoritative daily file.

For a settled day, compare the row count of each Salesforce **Daily**
EventLogFile against what we actually ingested into ClickHouse (which now comes
from **Hourly** files). A clean match proves the hourly switch lost no data; a
shortfall flags a gap.

Why this exists: most EventLogFile types were switched from Daily to Hourly
ingestion (PR #27). Hourly files give near-real-time data, but use a 24h
lookback (vs 24 days for daily), so this check guards against silent gaps.

Usage (inside the ingest container):
    python3 /app/validate_completeness.py [YYYY-MM-DD]   # default: 2 days ago (UTC)

READ-ONLY against ClickHouse. Downloads daily files from Salesforce to count
rows (no row-count field exists on EventLogFile). Exits non-zero if any GAP is
found, so it can gate an alert.
"""
import datetime as dt
import os
import re
import sys

import clickhouse_connect
import requests

import sf_auth

API_VER = "v59.0"
TOLERANCE = 0.01  # 1% — small diffs from dedup / late-arriving events are OK
INGEST_PY = os.getenv("INGEST_PY_PATH", "/app/ingest.py")


def load_eventtype_table_map(path: str = INGEST_PY) -> dict[str, str]:
    """Parse ingest.py's CONFIG into {EventType: clickhouse_table}."""
    src = open(path).read()
    start = src.index("CONFIG: dict[str, dict] = {")
    close = src.index("\n}\n", start)
    block = src[start:close]
    keys = [(m.group(1), m.start()) for m in re.finditer(r'^    "([A-Za-z0-9]+)":', block, re.M)]
    out: dict[str, str] = {}
    for i, (key, pos) in enumerate(keys):
        end = keys[i + 1][1] if i + 1 < len(keys) else len(block)
        m = re.search(r'"table":\s*"([a-z0-9_]+)"', block[pos:end])
        if m:
            out[key] = m.group(1)
    return out


def count_daily_file_rows(instance_url: str, session_id: str, file_id: str) -> int:
    """Stream a daily EventLogFile CSV and count data rows (excludes header)."""
    url = f"{instance_url}/services/data/{API_VER}/sobjects/EventLogFile/{file_id}/LogFile"
    with requests.get(
        url, headers={"Authorization": f"Bearer {session_id}"}, stream=True, timeout=600
    ) as r:
        r.raise_for_status()
        lines = sum(1 for _ in r.iter_lines())
    return max(0, lines - 1)


def main() -> int:
    day = sys.argv[1] if len(sys.argv) > 1 else (
        dt.datetime.utcnow().date() - dt.timedelta(days=2)
    ).isoformat()

    cfg = load_eventtype_table_map()
    sf = sf_auth.get_sf_client()
    instance_url = os.environ.get("SF_INSTANCE_URL", "").strip().rstrip("/")

    ch_host = os.environ["CH_HOST"].replace("https://", "").replace("http://", "").rstrip("/")
    ch = clickhouse_connect.get_client(
        host=ch_host,
        port=int(os.getenv("CH_PORT", "8443")),
        username=os.getenv("CH_USER", "default"),
        password=os.environ["CH_PASSWORD"],
        database=os.getenv("CH_DATABASE", "salesforceProd"),
        secure=True,
    )

    # Sum daily-file rows per EventType for the target day (there can be >1 file).
    soql = (
        "SELECT Id, EventType FROM EventLogFile "
        f"WHERE Interval = 'Daily' AND LogDate >= {day}T00:00:00Z AND LogDate < {day}T23:59:59Z"
    )
    records = sf.query_all(soql)["records"]
    daily_rows: dict[str, int] = {}
    for rec in records:
        et = rec["EventType"]
        if et not in cfg:
            continue  # a type we don't ingest
        daily_rows[et] = daily_rows.get(et, 0) + count_daily_file_rows(
            instance_url, sf.session_id, rec["Id"]
        )

    if not daily_rows:
        print(f"No daily EventLogFiles found for {day} (not settled yet, or no data). Nothing to check.")
        return 0

    print(f"\nCompleteness check for {day} (ClickHouse hourly-ingested vs SF daily file)\n")
    print(f"  {'EventType':30} {'daily_file':>11} {'clickhouse':>11} {'diff':>8}  status")
    print(f"  {'-'*30} {'-'*11} {'-'*11} {'-'*8}  ------")

    gaps = 0
    for et in sorted(daily_rows):
        table = cfg[et]
        d = daily_rows[et]
        try:
            res = ch.query(
                f"SELECT count() FROM {ch.database}.{table} FINAL WHERE toDate(timestamp) = toDate(%(d)s)",
                parameters={"d": day},
            )
            c = res.result_rows[0][0]
        except Exception as e:
            print(f"  {et:30} {d:>11} {'ERR':>11} {'':>8}  CH query failed: {e}")
            gaps += 1
            continue
        diff = c - d
        pct = (diff / d) if d else 0.0
        if d > 0 and c < d * (1 - TOLERANCE):
            status = "GAP ❌"
            gaps += 1
        elif d > 0 and c > d * (1 + TOLERANCE):
            status = "EXCESS ⚠"
        else:
            status = "OK ✅"
        print(f"  {et:30} {d:>11,} {c:>11,} {diff:>+8,}  {status}")

    print()
    if gaps:
        print(f"⚠ {gaps} type(s) with a GAP — hourly ingestion is missing rows vs the daily file.")
        return 1
    print("All checked types match the daily file within tolerance — hourly ingestion is complete. ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
