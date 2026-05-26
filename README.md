# Salesforce Observability with ClickHouse

Real-time security and operational observability for Salesforce orgs — built on ClickHouse Cloud, Grafana, and LibreChat with a ClickHouse MCP server.

## What it does

Pulls Salesforce [EventLogFile](https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_eventlogfile.htm) data and [Threat Detection events](https://help.salesforce.com/s/articleView?id=sf.real_time_em_threat_detection.htm) into ClickHouse Cloud, then surfaces them in Grafana dashboards and a LibreChat AI interface for natural-language investigation.

**What you can monitor:**
- Login activity — who logged in, from where, via which integration, success vs failure
- API usage — which connected apps are consuming your daily limit, billable vs non-billable calls
- REST, SOAP, Bulk API attribution by connected app, user, and endpoint
- Admin changes — SetupAuditTrail ingested and queryable
- Security events — CredentialStuffing, SessionHijacking, ReportAnomaly, ApiAnomaly
- Apex performance, Flow execution, Lightning page load times

## Architecture

```
Salesforce EventLogFile API          Threat Detection EventStore
        │                                      │
        └──────────────┬───────────────────────┘
                       ▼
          ┌─────────────────────────────┐
          │   Ingest Container          │
          │   ingest.py   (every 6h)    │
          │   ingest_threat_store.py    │
          └──────────────┬──────────────┘
                         │
                         ▼
          ┌─────────────────────────────┐
          │   ClickHouse Cloud          │
          │   ~30 event tables          │
          │   connected_app_registry    │
          └──────┬──────────────┬───────┘
                 │              │
                 ▼              ▼
          ┌──────────┐   ┌─────────────────┐
          │  Grafana  │   │   LibreChat      │
          │  port 3000│   │   + ClickHouse  │
          │           │   │   MCP server    │
          │  9 dashboards │   port 3080     │
          └──────────┘   └─────────────────┘
```

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — install this first if you don't have it
- [ClickHouse Cloud](https://clickhouse.cloud/) account (free tier works)
- Salesforce org with [Event Monitoring](https://help.salesforce.com/s/articleView?id=sf.real_time_em_buying.htm) enabled
- An Anthropic API key (for LibreChat AI features — optional)

## Quick start

**1. Clone and configure**

```bash
git clone https://github.com/your-org/sf-observability.git
cd sf-observability
cp .env.example .env
# Edit .env with your Salesforce and ClickHouse credentials
```

**2. Create the ClickHouse schema**

There are two schema files that must both be applied. The easiest way is the setup script:

```bash
./schema/setup.sh <clickhouse-host> <password> <database-name>
# Example:
./schema/setup.sh abc123.us-east-1.aws.clickhouse.cloud mypassword salesforceProd
```

This creates the database, substitutes the name throughout both schema files, and applies them in order. If you prefer to apply them manually via the ClickHouse Cloud SQL console, run `schema/schema_core.sql` then `schema/schema_events.sql` (substituting `salesforceProd` with your `CH_DATABASE` value in both).

**3. Start the stack**

```bash
docker compose up -d
```

This starts:
- **Ingest container** — pulls EventLogFile data from Salesforce every 6 hours
- **Grafana** at `http://localhost:3000` — log in with your `GRAFANA_ADMIN_PASSWORD`
- **LibreChat** at `http://localhost:3080` — AI chat with direct ClickHouse access via MCP
- **Supporting services** — MongoDB, Meilisearch, pgvector (all for LibreChat)

**4. Set up Salesforce JWT authentication**

The pipeline uses JWT/ECA (certificate-based) auth. This is a one-time setup — see [Authentication](#authentication) for step-by-step instructions to create the External Client App, generate a certificate, and populate `SF_JWT_CLIENT_ID` / `SF_JWT_KEY_FILE` / `SF_JWT_USERNAME` in your `.env`.

If you just want to verify the rest of the stack first, you can temporarily use `SF_ACCESS_TOKEN` (see [Access token](#access-token-cicd-only)) while you complete the ECA setup.

**5. Trigger initial ingest**

```bash
docker compose exec ingest python3 /app/ingest.py
docker compose exec ingest python3 /app/ingest_threat_store.py
```

## Dashboards

| Dashboard | What it shows |
|---|---|
| **SF API Performance** | API call volume vs your daily API limit, billable vs non-billable, top connected apps |
| **Logins — Salesforce Prod** | Login activity by status, source IP, browser/user-agent, success/failure ratio |
| **Security Events** | Threat detection events — credential stuffing, session hijacking, anomalies |
| **SF Ops Health** | Setup audit trail, permission changes, admin activity |
| **SF URI Performance** | Page/endpoint performance, slow requests |
| **SF API Health** | Error rates by API family and endpoint |
| **SF Perf Health** | Apex execution, trigger performance, Flow execution |
| **Logins As** | Login-as activity (admin impersonation) |
| **Ingestion Monitor** | Pipeline health — rows ingested per run, last run time |

## Connected app registry

Salesforce identifies integrations in event logs using opaque numeric IDs rather than human-readable names. The registry maps those IDs to app names so dashboards and queries can display "Amazon AppFlow" instead of `8883i000001R3QM`.

### How it works

A CSV file (`schema/connected_app_registry.csv`) is the source of truth. Run this whenever you update it:

```bash
python3 schema/load_registry.py
```

This inserts the CSV into a `connected_app_registry` ClickHouse table. All dashboards and queries join against it automatically.

A template with the expected columns is at `schema/connected_app_registry_example.csv`:

```
connected_app_id,app_name,category,notes
8883i000001XXXXX,Your App Name Here,Data Integration,888-prefix: contact SF Support to identify
0H4Uy0000XXXXXXX,Another App,DevTools,0H4-prefix: look up in SF Setup → Apps → Connected Apps
```

### What happens when an app is unknown

When an app ID appears in usage data but is not in the registry, the system shows the raw 15-char ID rather than a name. Unknown apps are **never excluded** from totals or queries — they are always counted. This means:

- All billing, error, and volume metrics remain accurate even when new integrations appear
- The "Unregistered Connected Apps (Action Required)" panel in the SF Performance & Health dashboard surfaces any unknown IDs automatically
- No data is silently lost — you will see the raw ID in place of a name until the registry is updated

### Finding unknown apps: gap-detection query

Run this query to find connected app IDs present in the last 30 days of API usage that are not yet in the registry:

```sql
SELECT
    t.connected_app_id,
    count() AS total_calls,
    countIf(t.counts_against_api_limit = 1) AS billable_calls,
    uniq(t.user_name) AS distinct_users,
    groupArray(3)(DISTINCT t.user_name) AS sample_users,
    min(toDate(t.timestamp)) AS first_seen,
    max(toDate(t.timestamp)) AS last_seen,
    groupArray(3)(DISTINCT t.client_ip) AS sample_ips
FROM api_total_usage_events t FINAL
LEFT JOIN connected_app_registry r FINAL
    ON t.connected_app_id = r.connected_app_id
WHERE t.timestamp >= now() - INTERVAL 30 DAY
  AND t.connected_app_id != ''
  AND r.connected_app_id = ''  -- not in registry
GROUP BY t.connected_app_id
ORDER BY billable_calls DESC
```

The same query (scoped to 7 days) runs automatically as the "Unregistered Connected Apps (Action Required)" panel in Grafana. Check it monthly or whenever new integrations are added.

### 15-char vs 18-char IDs — important note

Salesforce exposes connected app IDs in two different lengths depending on the source:

| Source | ID length | Example |
|---|---|---|
| **EventLogFile CSV** (what we ingest) | **15-char** | `8888Z000000pihz` |
| **`ApiTotalUsageEventLog` SOQL object** | **18-char** | `8888Z000000pihzQAA` |

The registry uses **15-char IDs** (from EventLogFile). If you look up an ID via SOQL (`ApiTotalUsageEventLog`), you will get the 18-char version. To convert: strip the last 3 characters.

```
18-char: 8888Z000000pihzQAA
15-char: 8888Z000000pihz      ← use this in the registry CSV
```

When writing SOQL queries that filter by connected app ID, use `LIKE '8888Z000000pihz%'` rather than an exact match, since SOQL returns 18-char IDs.

### Finding unknown app IDs

Salesforce uses two ID prefixes with different lookup paths:

| Prefix | Type | How to identify |
|---|---|---|
| `0H4` | Connected App (modern OAuth 2.0) | **Salesforce Setup → Apps → Connected Apps** — search by name or browse the list |
| `888` | OAuthConsumer / Remote Access (legacy) | **Contact Salesforce Support** — these IDs are not visible in the Setup UI |

When you find a new unknown ID in the dashboards, add it to `schema/connected_app_registry.csv` and re-run `load_registry.py`. Unknown apps still appear in results using their raw ID — they are never excluded.

### Adding a new app to the registry

1. Identify the app name using the prefix table above
2. Add a row to `schema/connected_app_registry.csv`:
   ```
   8888Z000000pihz,Clay,Data Integration,Added 2026-05-24 after SF Support identified
   ```
3. Load it into ClickHouse:
   ```bash
   python3 schema/load_registry.py
   ```
   Or via the ingest container if you don't have local env vars:
   ```bash
   docker cp schema/connected_app_registry.csv sf-observability-ingest-1:/tmp/connected_app_registry.csv
   docker exec sf-observability-ingest-1 python3 /app/schema/load_registry.py --csv /tmp/connected_app_registry.csv
   ```

### Best practice: one connected app per integration

Sharing a single Salesforce user across multiple integrations makes it impossible to attribute API usage accurately. Each integration should have its own dedicated Salesforce user and its own connected app. See `SCHEMA_AUDIT.md` for more on the attribution gap.

## Authentication

The ingest pipeline requires **JWT/ECA authentication** — the Salesforce-recommended approach for unattended server processes. Username/password auth is not supported.

JWT uses a certificate-based flow: the pipeline signs a request with your private key, Salesforce validates it against the uploaded certificate, and returns an access token. No human interaction needed after initial setup; tokens are refreshed automatically each run.

### Salesforce setup — one-time steps

#### 1. Create a dedicated ingest user

Create a dedicated Salesforce user for the pipeline (don't reuse an existing account — this ensures API usage in dashboards is attributed correctly to the pipeline vs. a human user).

1. **Setup → Users → New User**
2. Username: e.g. `sf-observability-ingest@yourorg.com`
3. Profile: System Administrator works; or use a custom profile/Permission Set with these permissions:
   - **View Event Log Files** — required for EventLogFile API (bundled with Event Monitoring add-on)
   - **View Setup and Configuration** — required to read `ProfileId`/`ProfileName` on User records
   - **API Enabled** — required for all REST API calls

#### 2. Generate a key pair

Run once on the machine where the Docker container will run:

```bash
mkdir -p cert
openssl req -x509 -newkey rsa:2048 \
  -keyout cert/server.key \
  -out cert/server.crt \
  -days 365 -nodes \
  -subj "/CN=sf-observability"
```

- `cert/server.key` — private key. Keep this on the host only; never commit it (`.gitignore` covers `cert/*.key`)
- `cert/server.crt` — certificate to upload to Salesforce in the next step

#### 3. Create the External Client App (ECA)

1. **Setup → Apps → External Client Apps → New External Client App**
2. Fill in the basics (App Name, API Name, Contact Email)
3. Under **OAuth Settings**:
   - Check **Enable OAuth Settings**
   - Add scope: **Manage user data via APIs (api)**
   - Check **Use digital signatures**
   - Upload your `cert/server.crt`
4. Save — Salesforce will generate a **Consumer Key** (also called Client ID). Copy it.

#### 4. Pre-authorize the ingest user

Salesforce requires the ingest user to be explicitly allowed before the JWT flow works:

1. **Setup → Apps → External Client Apps → Manage** (next to your app)
2. Click **Edit Policies**
3. Set **Permitted Users** to **Admin approved users are pre-authorized**
4. Save, then click **Manage Users → Add** and add your ingest user

#### 5. Update .env

```bash
SF_JWT_CLIENT_ID=<Consumer Key from step 3>
SF_JWT_KEY_FILE=/app/cert/server.key    # in-container path — don't change this line
SF_JWT_USERNAME=sf-observability-ingest@yourorg.com
SF_INSTANCE_URL=https://yourorg.my.salesforce.com
SF_ORG_ALIAS=MyOrg
```

The `cert/` directory on your host is volume-mounted into the container at `/app/cert/`. The key stays on the host; the container reads it at runtime.

#### 6. Verify

```bash
docker compose up -d
docker compose logs ingest --tail=20
# Should show: Auth: JWT/ECA as yourorg
```

### Access token (CI/CD only)

For pipelines that pre-obtain a token in a prior step (e.g. a GitHub Actions workflow that runs `sf org login jwt` and then passes `SF_ACCESS_TOKEN` to a downstream job):

```bash
SF_ACCESS_TOKEN=<token>
SF_INSTANCE_URL=https://yourorg.my.salesforce.com
```

Access tokens expire (typically 2–24 hours). Not suitable for long-running Docker containers.

## Configuration reference

See `.env.example` for all required variables. Key ones:

| Variable | Description |
|---|---|
| `SF_JWT_CLIENT_ID` | Consumer Key from your Salesforce External Client App |
| `SF_JWT_KEY_FILE` | Absolute path to your JWT private key file (`server.key`) |
| `SF_JWT_USERNAME` | Salesforce username the ingest runs as |
| `SF_ACCESS_TOKEN` + `SF_INSTANCE_URL` | CI/CD fallback — pre-obtained access token |
| `CH_HOST` / `CH_PASSWORD` / `CH_DATABASE` | ClickHouse Cloud connection |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin login |
| `ANTHROPIC_API_KEY` | For LibreChat AI features (optional) |

## Event types ingested

The pipeline captures 22 Salesforce EventLogFile event types. See `SCHEMA_AUDIT.md` for a full field-by-field comparison of what each event type contains vs what is captured.

Key types: `Login`, `RestApi`, `API` (SOAP), `BulkApi2`, `ApexTrigger`, `ApexExecution`, `FlowExecution`, `URI`, `LightningPageView`, `MetadataApiOperation`, `SetupAuditTrail` (via threat store).

## Limitations

- Requires Salesforce Event Monitoring add-on (not included in standard org editions)
- Daily API Total Usage (`ApiTotalUsage`) is a daily log file — near-real-time analysis uses the hourly `RestApi` and `API` event types instead
- The Salesforce daily API limit varies by org edition and license count — check Setup → Company Information for your specific limit

## License

Apache License 2.0 — see [LICENSE](LICENSE).
