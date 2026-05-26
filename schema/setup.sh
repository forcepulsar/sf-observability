#!/usr/bin/env bash
# Apply both schema files to ClickHouse Cloud.
# Usage: ./schema/setup.sh <host> <password> [database]
# Example: ./schema/setup.sh abc123.us-east-1.aws.clickhouse.cloud mypassword salesforceProd

set -e

HOST="${1:?Usage: $0 <host> <password> [database]}"
PASSWORD="${2:?Usage: $0 <host> <password> [database]}"
DATABASE="${3:-salesforceProd}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Creating database: $DATABASE"
curl -s "https://${HOST}:8443/" \
  --user "default:${PASSWORD}" \
  --data "CREATE DATABASE IF NOT EXISTS ${DATABASE}"

for file in schema_core.sql schema_events.sql; do
  echo "Applying $file..."
  sed "s/salesforceProd/${DATABASE}/g" "${SCRIPT_DIR}/${file}" | \
    curl -s "https://${HOST}:8443/" \
      --user "default:${PASSWORD}" \
      --data-binary @-
  echo "$file done."
done

echo "Schema setup complete for database: $DATABASE"
