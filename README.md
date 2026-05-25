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

- [Docker](https://www.docker.com/) and Docker Compose
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

Run `schema/schema_prod.sql` against your ClickHouse Cloud instance to create all tables.

**3. Start the stack**

```bash
docker compose up -d
```

This starts:
- **Ingest container** — pulls EventLogFile data from Salesforce every 6 hours
- **Grafana** at `http://localhost:3000` — log in with your `GRAFANA_ADMIN_PASSWORD`
- **LibreChat** at `http://localhost:3080` — AI chat with direct ClickHouse access via MCP
- **Supporting services** — MongoDB, Meilisearch, pgvector (all for LibreChat)

**4. Trigger initial ingest**

```bash
docker compose exec ingest python3 /app/ingest.py
docker compose exec ingest python3 /app/ingest_threat_store.py
```

## Dashboards

| Dashboard | What it shows |
|---|---|
| **SF API Performance** | API call volume vs 820K daily limit, billable vs non-billable, top connected apps |
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
8883i000001R3QM,Amazon AppFlow Embedded Login App,Data Integration,Continuous 24/7 polling...
0H4Uy0000000cGb,Gearset Deploy,DevTools,
```

### Finding unknown app IDs

Salesforce uses two ID prefixes with different lookup paths:

| Prefix | Type | How to identify |
|---|---|---|
| `0H4` | Connected App (modern OAuth 2.0) | **Salesforce Setup → Apps → Connected Apps** — search by name or browse the list |
| `888` | OAuthConsumer / Remote Access (legacy) | **Contact Salesforce Support** — these IDs are not visible in the Setup UI |

When you find a new unknown ID in the dashboards, add it to `schema/connected_app_registry.csv` and re-run `load_registry.py`. Unknown apps still appear in results using their raw ID — they are never excluded.

### Best practice: one connected app per integration

Sharing a single Salesforce user across multiple integrations makes it impossible to attribute API usage accurately. Each integration should have its own dedicated Salesforce user and its own connected app. See `SCHEMA_AUDIT.md` for more on the attribution gap.

## Authentication

The ingest pipeline requires **JWT/ECA authentication** (the Salesforce-recommended approach for unattended server processes). Username and password are not supported.

### Option A — JWT/ECA (required for production)

JWT uses a certificate-based flow that never expires between runs. One-time setup:

```bash
# 1. Generate a key pair
openssl req -x509 -newkey rsa:2048 -keyout server.key -out server.crt -days 365 -nodes

# 2. In Salesforce Setup → Apps → External Client Apps:
#    - Create a new ECA, enable "Enable for Device Flow" and "Use digital signatures"
#    - Upload server.crt as the certificate
#    - Copy the Consumer Key

# 3. Add to .env:
SF_JWT_CLIENT_ID=<Consumer Key>
SF_JWT_KEY_FILE=/path/to/server.key
SF_JWT_USERNAME=your-ingest-user@yourorg.com
```

### Option B — Access token (CI/CD only)

For pipelines that obtain a token externally (e.g. from a prior JWT login step):

```bash
# Get a token: sf org display --target-org MyOrg --json  →  copy "accessToken"
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
