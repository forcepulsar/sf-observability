#!/usr/bin/env bash
# Extracts a private key from a Salesforce-exported JKS keystore.
# Run from the repo root after downloading the .jks file from SF Certificate and Key Management.
#
# Usage:
#   ./scripts/extract-sf-cert-key.sh <jks-file> <cert-alias> <output-name>
#
# Example:
#   ./scripts/extract-sf-cert-key.sh 00DVG000008FEyv.jks sf_observability_prod_2026 sf-observability
#
# Output: cert/server.key  (private key — volume-mounted into the ingest container)
#
# Notes:
#   - cert-alias uses underscores (the label you set in SF), not hyphens
#   - Requires Java (keytool) and OpenSSL
#   - You will be prompted once for your JKS password (set when exporting from SF)

set -euo pipefail

JKS_FILE="${1:-}"
CERT_ALIAS="${2:-}"
OUTPUT_NAME="${3:-}"

if [[ -z "$JKS_FILE" || -z "$CERT_ALIAS" || -z "$OUTPUT_NAME" ]]; then
  echo "Usage: $0 <jks-file> <cert-alias> <output-name>"
  echo ""
  echo "  jks-file    — keystore file exported from SF (e.g. 00DVG000008FEyv.jks)"
  echo "  cert-alias  — alias inside the JKS, uses underscores (e.g. sf_observability_prod_2026)"
  echo "  output-name — base name for log messages (e.g. sf-observability)"
  exit 1
fi

P12_FILE="${OUTPUT_NAME}.p12"
KEY_OUT="cert/server.key"

# ── Prerequisites ──────────────────────────────────────────────────────────────
echo "Checking prerequisites..."
if ! command -v keytool &>/dev/null; then
  echo "ERROR: keytool not found — install Java: brew install openjdk"
  exit 1
fi
if ! command -v openssl &>/dev/null; then
  echo "ERROR: openssl not found — install with: brew install openssl"
  exit 1
fi
if [[ ! -f "$JKS_FILE" ]]; then
  echo "ERROR: JKS file not found: $JKS_FILE"
  exit 1
fi

mkdir -p cert

# ── Prompt for password once ───────────────────────────────────────────────────
echo ""
read -rsp "Enter JKS keystore password (set when exporting from SF): " JKS_PASSWORD
echo ""
export JKS_PASSWORD

# ── List aliases to confirm cert is present ────────────────────────────────────
echo ""
echo "Aliases in keystore (confirm '${CERT_ALIAS}' is listed):"
ALIASES=$(keytool -list -keystore "$JKS_FILE" -storepass:env JKS_PASSWORD 2>/dev/null \
  | grep "PrivateKeyEntry" \
  | awk -F, '{print " •", $1}') || true
if [[ -z "$ALIASES" ]]; then
  echo "WARNING: No PrivateKeyEntry aliases found — check your password and JKS file."
else
  echo "$ALIASES"
fi

# ── JKS → PKCS12 ──────────────────────────────────────────────────────────────
echo ""
echo "Extracting '${CERT_ALIAS}' to PKCS12..."
keytool -importkeystore \
  -srckeystore "$JKS_FILE" \
  -destkeystore "$P12_FILE" \
  -deststoretype PKCS12 \
  -srcalias "$CERT_ALIAS" \
  -srcstorepass:env JKS_PASSWORD \
  -deststorepass:env JKS_PASSWORD \
  -noprompt 2>/dev/null
echo "Done."

# ── PKCS12 → PEM private key ───────────────────────────────────────────────────
echo ""
echo "Extracting private key to ${KEY_OUT}..."
openssl pkcs12 \
  -in "$P12_FILE" \
  -nocerts \
  -nodes \
  -passin env:JKS_PASSWORD 2>/dev/null \
  | openssl pkey -out "$KEY_OUT"
rm -f "$P12_FILE"
echo "Done."

# ── Verify ─────────────────────────────────────────────────────────────────────
echo ""
FIRST_LINE=$(head -1 "$KEY_OUT")
if [[ "$FIRST_LINE" == "-----BEGIN PRIVATE KEY-----" ]]; then
  echo "✓ Private key extracted to ${KEY_OUT}"
else
  echo "ERROR: Unexpected output — first line: ${FIRST_LINE}"
  exit 1
fi

# ── Optional JWT login test ────────────────────────────────────────────────────
echo ""
if command -v sf &>/dev/null; then
  echo "JWT login test requires the Consumer Key from the External Client App."
  echo "If you haven't created the ECA yet, answer 'n' and re-run this step after Step 5."
  echo ""
  read -rp "Run live JWT login test against Salesforce? (y/n): " RUN_TEST
  if [[ "$RUN_TEST" == "y" ]]; then
    echo ""
    read -rp "  SF Username (e.g. sf-observability-ingest@yourorg.com): " SF_USERNAME
    read -rp "  Consumer Key (from ECA → Manage Consumer Details): " CLIENT_ID
    read -rp "  Instance URL (e.g. https://yourorg.my.salesforce.com): " INSTANCE_URL

    echo ""
    echo "Testing JWT login..."
    sf org login jwt \
      --username "$SF_USERNAME" \
      --jwt-key-file "$KEY_OUT" \
      --client-id "$CLIENT_ID" \
      --instance-url "$INSTANCE_URL" \
      --alias "${OUTPUT_NAME}-test"

    echo ""
    echo "✓ JWT login succeeded."
  fi
else
  echo "(sf CLI not installed — skipping live JWT test)"
  echo "  To test manually: docker compose exec ingest python3 /app/ingest.py --smoke"
fi

# ── Cleanup reminder ───────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────────────────"
echo "NEXT STEPS:"
echo "  1. Update .env — set SF_JWT_CLIENT_ID and SF_JWT_USERNAME"
echo "  2. Start the stack: docker compose up -d"
echo "  3. Verify: docker compose logs ingest --tail=20"
echo "  4. Delete the downloaded keystore: rm ${JKS_FILE}"
echo ""
echo "  cert/server.key is gitignored — keep it on this host only."
echo "────────────────────────────────────────────────────"
