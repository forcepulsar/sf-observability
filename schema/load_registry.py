"""
Load connected_app_registry.csv into ClickHouse.

Run whenever the CSV is updated. Two options:

Option A — directly with ClickHouse env vars set locally:
    python3 schema/load_registry.py

Option B — via the ingest container (no local env vars needed):
    docker cp schema/connected_app_registry.csv sf-observability-ingest-1:/tmp/connected_app_registry.csv
    docker exec sf-observability-ingest-1 python3 /app/schema/load_registry.py --csv /tmp/connected_app_registry.csv

Note: connected_app_registry.csv is gitignored (contains internal app names).
The example template is at schema/connected_app_registry_example.csv.
"""

import argparse
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


def load(csv_path: Path):
    client = clickhouse_connect.get_client(
        host=CH_HOST, port=CH_PORT, username=CH_USER,
        password=CH_PASSWORD, database=CH_DATABASE, secure=True,
    )

    rows = []
    with open(csv_path, encoding="utf-8") as f:
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None, help="Path to CSV file (default: schema/connected_app_registry.csv)")
    args = parser.parse_args()
    csv_path = Path(args.csv) if args.csv else Path(__file__).parent / "connected_app_registry.csv"
    load(csv_path)
