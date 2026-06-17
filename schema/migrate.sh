#!/usr/bin/env bash
# Apply pending numbered migrations to an existing ClickHouse database.
#
# Usage: ./schema/migrate.sh <host> <password> [database]
# Example: ./schema/migrate.sh abc123.us-east-1.aws.clickhouse.cloud mypassword salesforceProd
#
# Why this exists: setup.sh uses CREATE TABLE IF NOT EXISTS, which never alters
# an existing table. Migrations carry incremental schema changes (ALTER TABLE,
# new tables) to databases that already exist — so production and a fresh
# install stay in sync.
#
# Migrations live in schema/migrations/NNN_description.sql, applied in filename
# order. Each applied file is recorded in the target DB's `schema_migrations`
# table and never re-run. Migration SQL must be idempotent where possible
# (ALTER TABLE ... ADD COLUMN IF NOT EXISTS, CREATE TABLE IF NOT EXISTS) and
# reference tables via the `salesforceProd.` prefix — it is substituted to the
# target database, the same convention setup.sh uses.

set -e

HOST="${1:?Usage: $0 <host> <password> [database]}"
PASSWORD="${2:?Usage: $0 <host> <password> [database]}"
DATABASE="${3:-salesforceProd}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIGRATIONS_DIR="${SCRIPT_DIR}/migrations"
ERRORS=0

# Execute one SQL statement; counts errors instead of aborting.
run_statement() {
  local stmt="$1"
  [[ -z "${stmt//[[:space:]]/}" ]] && return 0
  local response http_code body
  response=$(curl -s -w "\n%{http_code}" "https://${HOST}:8443/" \
    --user "default:${PASSWORD}" --data "${stmt}")
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')
  if [[ "$http_code" != "200" ]] || echo "$body" | grep -qi "exception\|error\|code:"; then
    echo "    ✗ ERROR (HTTP $http_code): $body" >&2
    ERRORS=$((ERRORS + 1))
    return 1
  fi
}

# Execute a SELECT and return the raw body (trimmed).
run_query() {
  curl -s "https://${HOST}:8443/" --user "default:${PASSWORD}" --data "$1" | tr -d '[:space:]'
}

echo "Migration target: ${DATABASE}"

# 1. Ensure the tracking table exists.
run_statement "CREATE TABLE IF NOT EXISTS ${DATABASE}.schema_migrations (filename String, applied_at DateTime DEFAULT now()) ENGINE = MergeTree ORDER BY filename" || true

# 2. Apply each pending migration in filename order.
applied=0
skipped=0
for path in $(ls "${MIGRATIONS_DIR}"/*.sql 2>/dev/null | sort); do
  fname=$(basename "$path")
  count=$(run_query "SELECT count() FROM ${DATABASE}.schema_migrations WHERE filename = '${fname}'")
  if [[ "$count" != "0" ]]; then
    skipped=$((skipped + 1))
    continue
  fi

  echo "Applying: ${fname}"
  local_errors_before=$ERRORS
  content=$(sed "s/salesforceProd/${DATABASE}/g" "$path" | grep -v '^\s*--' | tr '\n' ' ')
  while IFS= read -r -d ';' stmt; do
    run_statement "$stmt" || true
  done <<< "${content};"

  if [[ $ERRORS -eq $local_errors_before ]]; then
    run_statement "INSERT INTO ${DATABASE}.schema_migrations (filename) VALUES ('${fname}')" || true
    echo "  ✓ ${fname} applied and recorded"
    applied=$((applied + 1))
  else
    echo "  ✗ ${fname} failed — NOT recorded. Fix it and re-run." >&2
    break
  fi
done

echo ""
echo "Migrations: ${applied} applied, ${skipped} already up to date."
if [[ $ERRORS -ne 0 ]]; then
  echo "✗ Finished with ${ERRORS} error(s) — see above." >&2
  exit 1
fi
echo "✓ ${DATABASE} is up to date."
