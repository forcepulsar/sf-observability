# Deployment Guide

This guide walks you through a complete setup of the sf-observability stack: Salesforce EventLogFile ingestion into ClickHouse Cloud, with Grafana dashboards for visual analysis and LibreChat for AI-native investigation via natural language.

Estimated setup time: 20 minutes. Prerequisites: Docker Desktop, a ClickHouse Cloud cluster, and a Salesforce org with Event Monitoring enabled.

For full documentation, see [README.md](README.md).

---

## Before you start — what you need

- [ ] Docker Desktop installed and running
- [ ] ClickHouse Cloud cluster (free tier works) — note the hostname, username, and password
- [ ] Salesforce org with Event Monitoring add-on active
- [ ] Admin access to Salesforce Setup
- [ ] 20 minutes

---

## Step 1 — Clone and copy the config template (2 min)

```bash
git clone https://github.com/forcepulsar/sf-observability.git
cd sf-observability
cp .env.example .env
```

---

## Step 2 — Create the ClickHouse schema (2 min)

Run the setup script (it creates the database, substitutes the name, and applies both schema files):

```bash
./schema/setup.sh <your-ch-host> <your-ch-password> salesforceProd
# Example:
./schema/setup.sh abc123.us-east-1.aws.clickhouse.cloud mypassword salesforceProd
```

You should see `✓ Schema setup complete for: salesforceProd`.

---

## Step 3 — Create a Salesforce ingest user (3 min)

In Salesforce Setup:
1. **Setup → Users → New User** — create a dedicated user (e.g. `sf-obs-ingest@yourorg.com`)
2. Assign these permissions (via profile or Permission Set):
   - **View Event Log Files**
   - **View Setup and Configuration**
   - **API Enabled**

Don't reuse an existing admin account — a dedicated user keeps API attribution accurate in dashboards.

---

## Step 4 — Generate a certificate (1 min)

```bash
mkdir -p cert
openssl req -x509 -newkey rsa:2048 \
  -keyout cert/server.key \
  -out cert/server.crt \
  -days 365 -nodes \
  -subj "/CN=sf-observability"
```

This creates the private key (`cert/server.key`) and the certificate (`cert/server.crt`).

---

## Step 5 — Create the External Client App in Salesforce (5 min)

1. **Setup → Apps → External Client Apps → New External Client App**
2. Fill in App Name and Contact Email
3. Under **OAuth Settings**:
   - Enable OAuth, add scope **Manage user data via APIs (api)**
   - Check **Use digital signatures**, upload `cert/server.crt`
4. Save and copy the **Consumer Key**
5. Click **Manage → Edit Policies**, set **Permitted Users** to **Admin approved users are pre-authorized**
6. Click **Manage Users → Add** and add your ingest user

---

## Step 6 — Fill in .env (3 min)

Open `.env` in a text editor and fill in these sections:

```bash
# Salesforce
SF_JWT_CLIENT_ID=<Consumer Key from step 5>
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

## Step 7 — Start the stack (2 min)

```bash
docker compose up -d
```

Wait ~60 seconds for all containers to start, then check they're up:

```bash
docker compose ps
```

All services should show `running`.

---

## Step 8 — Trigger the first ingest (1 min)

The ingest container runs automatically on an hourly schedule, but trigger it now to get data immediately:

```bash
docker compose exec ingest python3 /app/ingest.py
```

This pulls the last 24 hours of EventLogFile data. Depending on your event volume it takes 1–10 minutes. Watch progress with:

```bash
docker compose logs ingest -f
```

---

## Step 9 — Open Grafana (1 min)

Go to [http://localhost:3000](http://localhost:3000). Log in with `admin` / your `GRAFANA_ADMIN_PASSWORD`.

The 9 dashboards are pre-provisioned under the **Salesforce** folder:
- **Logins — Salesforce Prod** — start here to see login activity
- **SF API Performance** — API usage vs your daily limit, broken down by connected app
- **Security Events** — credential stuffing, session hijacking, anomaly detection
- **SF Ops Health** — SetupAuditTrail, permission changes, admin activity
- **Ingestion Monitor** — pipeline health and row counts per run

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
| Grafana shows "No data" | Run the ingest manually (Step 8) and verify ClickHouse Block 2 variables in `.env` |
| Schema setup fails | Ensure `CH_HOST` has `https://` and the password has no special shell characters |
| `cert/server.key: No such file or directory` | Run Step 4 — the cert directory must exist before `docker compose up` |
