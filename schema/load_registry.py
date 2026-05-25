"""
Load connected_app_registry.csv into ClickHouse.

Run whenever the CSV is updated:
    python3 schema/load_registry.py

Uses the same ClickHouse credentials as the ingest pipeline (CH_HOST, CH_PORT, etc.)
or falls back to the Salesforce CLI token flow used by ingest.py.
"""

import csv
import os
import sys
from datetime import date
from pathlib import Path

import clickhouse_connect

CH_HOST     = os.environ.get("CH_HOST", "").removeprefix("https://").removeprefix("http://")
CH_PORT     = int(os.environ.get("CH_PORT", 8443))
CH_USER     = os.environ.get("CH_USER", "default")
CH_PASSWORD = os.environ.get("CH_PASSWORD", "")
CH_DATABASE = os.environ.get("CH_DATABASE", "salesforceProd")

CSV_PATH = Path(__file__).parent / "connected_app_registry.csv"


def load():
    client = clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD,
        database=CH_DATABASE,
        secure=True,
    )

    rows = []
    with open(CSV_PATH, encoding="utf-8") as f:
        for rec in csv.DictReader(f):
            rows.append([
                rec["connected_app_id"].strip(),
                rec["app_name"].strip(),
                rec.get("category", "").strip(),
                rec.get("notes", "").strip(),
                date.today(),
            ])

    if not rows:
        print("No rows found in CSV — nothing loaded.")
        sys.exit(1)

    client.insert(
        f"{CH_DATABASE}.connected_app_registry",
        rows,
        column_names=["connected_app_id", "app_name", "category", "notes", "updated_date"],
    )
    print(f"Loaded {len(rows)} rows into {CH_DATABASE}.connected_app_registry")


if __name__ == "__main__":
    load()
