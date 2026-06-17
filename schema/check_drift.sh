#!/usr/bin/env bash
# Report schema drift between two ClickHouse databases on the same host.
#
# Usage: ./schema/check_drift.sh <host> <password> <db_a> <db_b>
#
# Typical use — verify production matches the committed schema:
#   ./schema/setup.sh   <host> <pw> schema_reference   # fresh DB from repo
#   ./schema/migrate.sh <host> <pw> schema_reference   # + migrations
#   ./schema/check_drift.sh <host> <pw> salesforceProd schema_reference
#
# Empty output under each heading = no drift. Any rows = a column or engine
# that exists in one database but not the other (or differs), which means the
# committed schema and the live database have diverged.

set -e

HOST="${1:?Usage: $0 <host> <password> <db_a> <db_b>}"
PASSWORD="${2:?Usage: $0 <host> <password> <db_a> <db_b>}"
DB_A="${3:?Usage: $0 <host> <password> <db_a> <db_b>}"
DB_B="${4:?Usage: $0 <host> <password> <db_a> <db_b>}"

q() { curl -s "https://${HOST}:8443/" --user "default:${PASSWORD}" --data "$1"; }

echo "=== Column drift (in_a / in_b = 1 present, 0 absent): ${DB_A} vs ${DB_B} ==="
q "SELECT table, name AS column,
     max(database = '${DB_A}') AS in_${DB_A},
     max(database = '${DB_B}') AS in_${DB_B}
   FROM system.columns
   WHERE database IN ('${DB_A}', '${DB_B}')
   GROUP BY table, name
   HAVING max(database = '${DB_A}') != max(database = '${DB_B}')
   ORDER BY table, column
   FORMAT PrettyCompact"

echo ""
echo "=== Engine drift: ${DB_A} vs ${DB_B} ==="
q "SELECT name AS table,
     anyIf(engine, database = '${DB_A}') AS ${DB_A}_engine,
     anyIf(engine, database = '${DB_B}') AS ${DB_B}_engine
   FROM system.tables
   WHERE database IN ('${DB_A}', '${DB_B}')
   GROUP BY name
   HAVING anyIf(engine, database = '${DB_A}') != anyIf(engine, database = '${DB_B}')
   ORDER BY table
   FORMAT PrettyCompact"

echo ""
echo "(no rows under a heading = no drift for that check)"
