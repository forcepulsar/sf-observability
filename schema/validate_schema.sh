#!/usr/bin/env bash
# Schema validation test — applies both schema files to a throwaway database
# and verifies every expected table was created.
#
# Usage: ./schema/validate_schema.sh <host> <password>
# Example: ./schema/validate_schema.sh abc123.us-east-1.aws.clickhouse.cloud mypassword
#
# Creates: schema_test_YYYYMMDD_HHMMSS (you delete these manually)
# Never deletes databases — deletion requires explicit manual action.
#
# Run before committing any changes to schema_core.sql or schema_events.sql.

set -e

HOST="${1:?Usage: $0 <host> <password>}"
PASSWORD="${2:?Usage: $0 <host> <password>}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB="schema_test_$(date +%Y%m%d_%H%M%S)"

# All tables expected to exist after a clean schema setup
EXPECTED_TABLES=(
  # schema_core.sql
  ingestion_state
  ingestion_runs
  ingestion_events
  login_events
  # schema_events.sql
  login_as_events
  report_export_events
  insufficient_access_events
  permission_update_events
  api_events
  rest_api_events
  bulk_api_events
  bulk_api2_events
  apex_callout_events
  named_credential_events
  metadata_api_events
  apex_exception_events
  flow_execution_events
  uri_events
  apex_execution_events
  package_install_events
  apex_trigger_events
  lightning_interaction_events
  lightning_page_view_events
  api_total_usage_events
  flow_nav_metric_events
  users
  connected_app_registry
)

echo "╔════════════════════════════════════════╗"
echo "║       Schema Validation Test           ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Test database: $DB"
echo ""

# Apply schema using setup.sh
echo "── Applying schema files ──────────────"
"${SCRIPT_DIR}/setup.sh" "$HOST" "$PASSWORD" "$DB"
echo ""

# Query which tables were actually created
echo "── Verifying tables ───────────────────"
CREATED=$(curl -s "https://${HOST}:8443/" \
  --user "default:${PASSWORD}" \
  --data "SELECT name FROM system.tables WHERE database = '${DB}' ORDER BY name")

PASS=0
FAIL=0
MISSING=()

for table in "${EXPECTED_TABLES[@]}"; do
  if echo "$CREATED" | grep -q "^${table}$"; then
    echo "  ✓ $table"
    PASS=$((PASS + 1))
  else
    echo "  ✗ MISSING: $table"
    MISSING+=("$table")
    FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "── Result ─────────────────────────────"
echo "  Created: $DB"
echo "  Tables:  $PASS/${#EXPECTED_TABLES[@]} passed, $FAIL missing"
echo ""

if [[ $FAIL -eq 0 ]]; then
  echo "  ✅  PASS — all ${#EXPECTED_TABLES[@]} tables created correctly"
  echo ""
  echo "  Note: '$DB' was left in ClickHouse. Delete it manually when done."
  exit 0
else
  echo "  ❌  FAIL — ${FAIL} table(s) missing:"
  for t in "${MISSING[@]}"; do
    echo "       • $t"
  done
  echo ""
  echo "  Fix schema files before committing."
  echo "  Note: '$DB' was left in ClickHouse. Delete it manually when done."
  exit 1
fi
