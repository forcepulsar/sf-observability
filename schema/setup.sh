#!/usr/bin/env bash
# Apply both schema files to ClickHouse Cloud.
# Usage: ./schema/setup.sh <host> <password> [database]
# Example: ./schema/setup.sh abc123.us-east-1.aws.clickhouse.cloud mypassword salesforceProd
#
# ClickHouse's HTTP interface accepts one statement at a time.
# This script splits each file on semicolons and executes statements individually.

set -e

HOST="${1:?Usage: $0 <host> <password> [database]}"
PASSWORD="${2:?Usage: $0 <host> <password> [database]}"
DATABASE="${3:-salesforceProd}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ERRORS=0

# Run a single SQL statement against ClickHouse, exit on error
run_statement() {
  local stmt="$1"
  # Skip blank statements
  [[ -z "${stmt//[[:space:]]/}" ]] && return 0

  local response
  response=$(curl -s -w "\n%{http_code}" "https://${HOST}:8443/" \
    --user "default:${PASSWORD}" \
    --data "${stmt}")

  local http_code
  http_code=$(echo "$response" | tail -1)
  local body
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" != "200" ]] || echo "$body" | grep -qi "exception\|error\|code:"; then
    echo "  ✗ ERROR (HTTP $http_code): $body" >&2
    ERRORS=$((ERRORS + 1))
    return 1
  fi
}

# Apply a SQL file: substitute database name, split on ; and run each statement
apply_file() {
  local file="$1"
  local path="${SCRIPT_DIR}/${file}"

  if [[ ! -f "$path" ]]; then
    echo "ERROR: file not found: $path" >&2
    exit 1
  fi

  echo "Applying $file..."

  # Substitute database name, strip comments, split on semicolons
  local content
  content=$(sed "s/salesforceProd/${DATABASE}/g" "$path" | \
            grep -v '^\s*--' | \
            tr '\n' ' ')

  # Split on semicolons, execute each statement
  local count=0
  local errors_before=$ERRORS
  while IFS= read -r -d ';' stmt; do
    run_statement "$stmt" && count=$((count + 1))
  done <<< "${content};"

  local file_errors=$((ERRORS - errors_before))
  if [[ $file_errors -eq 0 ]]; then
    echo "  ✓ $file — $count statements applied"
  else
    echo "  ✗ $file — $file_errors error(s), $count succeeded" >&2
  fi
}

# 1. Create database
echo "Creating database: $DATABASE"
run_statement "CREATE DATABASE IF NOT EXISTS ${DATABASE}"
echo "  ✓ Database ready"

# 2. Apply schema files in order
apply_file "schema_core.sql"
apply_file "schema_events.sql"

# 3. Summary
echo ""
if [[ $ERRORS -eq 0 ]]; then
  echo "✓ Schema setup complete for: $DATABASE"
else
  echo "✗ Schema setup finished with $ERRORS error(s) — check output above" >&2
  exit 1
fi
