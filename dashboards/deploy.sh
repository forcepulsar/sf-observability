#!/usr/bin/env bash
# Deploy all Grafana dashboards from this folder to the local Grafana instance.
# Run this any time after a fresh Grafana install or to re-apply changes.
#
# Usage:
#   ./dashboards/deploy.sh                  # deploy all
#   ./dashboards/deploy.sh sf-threats-access  # deploy one by uid

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DIR/../.env"

# Read one KEY=value from the repo .env (without sourcing it); strips surrounding quotes.
env_val() {
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -E 's/^"(.*)"$/\1/; s/^'"'"'(.*)'"'"'$/\1/' || true
}

# Defaults follow the repo .env, so this works on prod (GRAFANA_PORT=8000) and locally (3000).
GRAFANA_PORT="${GRAFANA_PORT:-$(env_val GRAFANA_PORT)}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:${GRAFANA_PORT:-3000}}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASS:-$(env_val GRAFANA_ADMIN_PASSWORD)}"
GRAFANA_PASS="${GRAFANA_PASS:-admin}"

deploy_one() {
  local file="$1"
  local uid
  uid=$(basename "$file" .json)
  local title
  title=$(python3 -c "import json; d=json.load(open('$file')); print(d['dashboard']['title'])")
  local result
  result=$(curl -s -X POST "$GRAFANA_URL/api/dashboards/db" \
    -H "Content-Type: application/json" \
    -u "$GRAFANA_USER:$GRAFANA_PASS" \
    -d @"$file")
  local status
  status=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','error'), d.get('message',''))" 2>/dev/null)
  echo "  [$uid] $title → $status"
}

if [ -n "$1" ]; then
  deploy_one "$DIR/$1.json"
else
  echo "Deploying all dashboards to $GRAFANA_URL …"
  for f in "$DIR"/sf-*.json; do
    deploy_one "$f"
  done
  echo "Done."
fi
