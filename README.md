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

Salesforce uses numeric IDs (prefixed `888` or `4H0`) to identify connected apps in event logs. To map these to human-readable names, maintain `schema/connected_app_registry.csv` and load it:

```bash
python3 schema/load_registry.py
```

To identify unknown `888`-prefix IDs, contact Salesforce Support with the ID — they can look up the app name.

## Configuration reference

See `.env.example` for all required variables. Key ones:

| Variable | Description |
|---|---|
| `SF_USERNAME` / `SF_PASSWORD` | Salesforce credentials for the ingestion user |
| `SF_ACCESS_TOKEN` + `SF_INSTANCE_URL` | Alternative: use an access token instead of username/password |
| `CH_HOST` / `CH_PASSWORD` / `CH_DATABASE` | ClickHouse Cloud connection |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin login |
| `ANTHROPIC_API_KEY` | For LibreChat AI features |

## Event types ingested

The pipeline captures 22 Salesforce EventLogFile event types. See `SCHEMA_AUDIT.md` for a full field-by-field comparison of what each event type contains vs what is captured.

Key types: `Login`, `RestApi`, `API` (SOAP), `BulkApi2`, `ApexTrigger`, `ApexExecution`, `FlowExecution`, `URI`, `LightningPageView`, `MetadataApiOperation`, `SetupAuditTrail` (via threat store).

## Limitations

- Requires Salesforce Event Monitoring add-on (not included in standard org editions)
- Daily API Total Usage (`ApiTotalUsage`) is a daily log file — near-real-time analysis uses the hourly `RestApi` and `API` event types instead
- The Salesforce daily API limit varies by org edition and license count — check Setup → Company Information for your specific limit

## License

Apache License 2.0 — see [LICENSE](LICENSE).
