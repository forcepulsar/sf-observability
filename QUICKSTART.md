# Deployment Guide

This guide walks you through a complete setup of the sf-observability stack: Salesforce EventLogFile ingestion into ClickHouse Cloud, with Grafana dashboards for visual analysis and LibreChat for AI-native investigation via natural language.

Estimated setup time: 25 minutes. Prerequisites: Docker Desktop, a ClickHouse Cloud cluster, a Salesforce org with Event Monitoring enabled.

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
cp .env.salesforce.example .env.salesforce
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

## Step 4 — Create the External Client App (client credentials)

No certificate needed — the ingest authenticates with the ECA's consumer key + secret.

1. **Setup → Apps → External Client Apps → New External Client App**
2. Fill in App Name and Contact Email
3. Under **OAuth Settings**:
   - Enable OAuth, add scope **Manage user data via APIs (api)**
   - Callback URL is required but unused — `https://localhost` is fine
   - Check **Enable Client Credentials Flow**
4. Save. Under **Policies → OAuth Policies**:
   - **Permitted Users:** Admin approved users are pre-authorized
   - **Client Credentials Flow → Run As:** the ingest user from Step 3
5. Under **App Policies**, add the ingest user's permission set or profile
6. **Settings → OAuth Settings → Consumer Key and Secret** — copy both

Test it before going further:

```bash
curl -s -X POST "https://yourorg.my.salesforce.com/services/oauth2/token" \
  --data-urlencode grant_type=client_credentials \
  --data-urlencode "client_id=<consumer key>" \
  --data-urlencode "client_secret=<consumer secret>" | grep -o '"instance_url":"[^"]*"'
```

> **My Domain required:** client credentials only works against the org's My Domain URL. `login.salesforce.com` and `test.salesforce.com` reject it. Sandboxes use e.g. `https://yourorg--sandbox.sandbox.my.salesforce.com`.

---

## Step 5 — Fill in .env.salesforce and .env (3 min)

Salesforce credentials go in `.env.salesforce`. Only the ingest container loads it — `.env` is shared with Grafana, rag_api and LibreChat, which don't need them.

```bash
# .env.salesforce
SF_CLIENT_ID=<Consumer Key from step 4>
SF_CLIENT_SECRET=<Consumer Secret from step 4>
SF_INSTANCE_URL=https://yourorg.my.salesforce.com
SF_ORG_ALIAS=MyOrg
```

Then open `.env` and fill in these sections:

```bash
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

## Step 6 — Start the stack (2 min)

```bash
docker compose up -d
```

Wait ~60 seconds for all containers to start, then check they're up:

```bash
docker compose ps
```

All services should show `running`.

---

## Step 7 — Trigger the first ingest (1 min)

The ingest container runs automatically every 2 hours, but trigger it now to get data immediately:

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

## Step 8 — Open Grafana (1 min)

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
| `docker compose logs ingest` shows auth error | Check `SF_CLIENT_ID` / `SF_CLIENT_SECRET`, that `SF_INSTANCE_URL` is the My Domain URL, and that the ECA has client credentials enabled with a Run As user |
| Grafana shows "No data" | Run the ingest manually (Step 7) and verify ClickHouse Block 2 variables in `.env` |
| Schema setup fails | Ensure `CH_HOST` has `https://` and the password has no special shell characters |
