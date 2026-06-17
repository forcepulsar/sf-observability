# Deployment Guide

This guide walks you through a complete setup of the sf-observability stack: Salesforce EventLogFile ingestion into ClickHouse Cloud, with Grafana dashboards for visual analysis and LibreChat for AI-native investigation via natural language.

Estimated setup time: 25 minutes. Prerequisites: Docker Desktop, a ClickHouse Cloud cluster, a Salesforce org with Event Monitoring enabled, and Java + OpenSSL installed locally.

For full documentation, see [README.md](README.md).

---

## Before you start — what you need

- [ ] Docker Desktop installed and running
- [ ] ClickHouse Cloud cluster (free tier works) — note the hostname, username, and password
- [ ] Salesforce org with Event Monitoring add-on active
- [ ] Admin access to Salesforce Setup
- [ ] 20 minutes

---

## Step 1 — Clone and copy the config template

```bash
git clone https://github.com/forcepulsar/sf-observability.git
cd sf-observability
cp .env.example .env
```

---

## Step 2 — Create the ClickHouse schema

Run the setup script (it creates the database, substitutes the name, and applies both schema files):

```bash
./schema/setup.sh <your-ch-host> <your-ch-password> salesforceProd
# Example:
./schema/setup.sh abc123.us-east-1.aws.clickhouse.cloud mypassword salesforceProd
```

You should see `✓ Schema setup complete for: salesforceProd`.

### Separate dev and prod databases (optional)

To experiment without touching production data, bootstrap a second, empty
database and keep two env files side by side:

```bash
# One-time: create an empty dev database from the same schema
./schema/setup.sh <your-ch-host> <your-ch-password> salesforceDev
```

```bash
cp .env.prod.example .env.prod   # CH_DATABASE / CLICKHOUSE_DATABASE = salesforceProd
cp .env.dev.example  .env.dev    # CH_DATABASE / CLICKHOUSE_DATABASE = salesforceDev
```

`.env.dev` and `.env.prod` are **identical except for the two `*_DATABASE`
lines** (host and credentials are shared). Both files are gitignored. Select
one per command with `--env-file`, e.g. populate dev via backfill:

```bash
docker compose --env-file .env.dev run --rm ingest /app/ingest.py --backfill 30
```

---

## Step 3 — Create a Salesforce ingest user

In Salesforce Setup:
1. **Setup → Users → New User** — create a dedicated user (e.g. `sf-obs-ingest@yourorg.com`)
2. Assign these permissions (via profile or Permission Set):
   - **View Event Log Files**
   - **View Setup and Configuration**
   - **API Enabled**

Don't reuse an existing admin account — a dedicated user keeps API attribution accurate in dashboards.

---

## Step 4 — Create the certificate in Salesforce

1. **Setup → Certificate and Key Management → Create Self-Signed Certificate**
2. Fill in:
   - **Label:** e.g. `sf_observability_prod_2026` — use underscores (this becomes the JKS alias)
   - **Key Size:** `2048`
   - Check **Exportable Private Key**
3. Save → click the cert label → **Download Certificate** → save the `.crt` file

---

## Step 5 — Create the External Client App and upload the certificate

1. **Setup → Apps → External Client Apps → New External Client App**
2. Fill in App Name and Contact Email
3. Under **OAuth Settings**:
   - Enable OAuth, add scopes: **Manage user data via APIs (api)** and **Perform requests at any time (refresh_token, offline_access)**
   - Check **Use digital signatures**, upload the `.crt` downloaded in Step 4
4. Save and copy the **Consumer Key**
5. Click **OAuth Policies**, set **Permitted Users** to **Admin approved users are pre-authorized**
6. Click **App Policies** and add integration user permission set or profile

---

## Step 6 — Export the keystore and extract the private key

Now that the ECA is configured and you have the Consumer Key, export the keystore:

1. **Setup → Certificate and Key Management → Export to Keystore** → set a password → download the `.jks` file

Then run the helper script (requires Java and OpenSSL):

```bash
./scripts/extract-sf-cert-key.sh <org-id>.jks sf_observability_prod_2026 sf-observability
```

When prompted about the JWT login test, answer **y** — you now have everything needed (Consumer Key from Step 5, username, instance URL).

> **Sandbox users:** As of Salesforce Winter '26, `test.salesforce.com` no longer works. Always use the org-specific My Domain URL (e.g. `https://yourorg--sandbox.sandbox.my.salesforce.com`) as `SF_INSTANCE_URL`.

---

## Step 7 — Fill in .env (3 min)

Open `.env` in a text editor and fill in these sections:

```bash
# Salesforce
SF_JWT_CLIENT_ID=<Consumer Key from step 5>  # from ECA → Manage Consumer Details
SF_JWT_KEY_FILE=/app/cert/server.key     # don't change — this is the in-container path
SF_JWT_USERNAME=sf-obs-ingest@yourorg.com
SF_INSTANCE_URL=https://yourorg.my.salesforce.com
SF_ORG_ALIAS=MyOrg

# ClickHouse — Block 1 (ingest)
CH_HOST=https://abc123.us-east-1.aws.clickhouse.cloud
CH_PORT=8443
CH_USER=default
CH_PASSWORD=yourpassword
CH_DATABASE=salesforceProd

# ClickHouse — Block 2 (Grafana + LibreChat, same values, different format)
CLICKHOUSE_HOST=abc123.us-east-1.aws.clickhouse.cloud
CLICKHOUSE_PORT=8443
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=yourpassword
CLICKHOUSE_SECURE=true
CLICKHOUSE_DATABASE=salesforceProd

# Grafana
GRAFANA_ADMIN_PASSWORD=change-me
```

> The two ClickHouse blocks must have the same credentials. Block 1 uses `https://` in the host; Block 2 does not.

---

## Step 8 — Start the stack (2 min)

```bash
docker compose up -d
```

Wait ~60 seconds for all containers to start, then check they're up:

```bash
docker compose ps
```

All services should show `running`.

---

## Step 9 — Trigger the first ingest (1 min)

The ingest container runs automatically every 6 hours, but trigger it now to get data immediately:

```bash
# Pull the last 24 hours of EventLogFile data (1–10 min depending on event volume)
docker compose exec ingest python3 /app/ingest.py

# Pull threat detection events (credential stuffing, session hijacking, anomalies)
docker compose exec ingest python3 /app/ingest_threat_store.py
```

Watch progress with:

```bash
docker compose logs ingest -f
```

---

## Step 10 — Open Grafana (1 min)

Go to [http://localhost:3000](http://localhost:3000). Log in with `admin` / your `GRAFANA_ADMIN_PASSWORD`.

The 9 dashboards are pre-provisioned under the **Salesforce** folder:
- **Logins - Salesforce Prod** — start here to see login activity
- **Salesforce - API Performance** — API usage vs your daily limit, broken down by connected app
- **Salesforce - Security Events** — credential stuffing, session hijacking, anomaly detection
- **Salesforce - Operational Health** — SetupAuditTrail, permission changes, admin activity
- **Ingestion Pipeline Health** — pipeline status, ingested log files per event type, and run diagnostics

---

## What's next

- **Load the connected app registry** to map numeric app IDs to human-readable names in dashboards:
  ```bash
  python3 schema/load_registry.py
  ```
- **Enable alerting** — see `dashboards/provisioning/alerting/sf_alerts.yaml` for pre-built alert rules (requires setting your datasource UID)
- **Enable Grafana alerting rules** — update `CLICKHOUSE_DS_UID` in the alerting YAML with your datasource UID (Grafana → Connections → Data Sources → your datasource → copy UID from URL)
- **Backfill historical data** — run `python3 /app/ingest.py --backfill 30` inside the container to pull 30 days of history

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker compose logs ingest` shows auth error | Check `SF_JWT_CLIENT_ID`, `SF_JWT_KEY_FILE`, and that the ingest user is pre-authorized on the ECA |
| Grafana shows "No data" | Run the ingest manually (Step 9) and verify ClickHouse Block 2 variables in `.env` |
| Schema setup fails | Ensure `CH_HOST` has `https://` and the password has no special shell characters |
| `cert/server.key: No such file or directory` | Complete Step 6 — export the JKS from Salesforce and run the extraction script before `docker compose up` |
