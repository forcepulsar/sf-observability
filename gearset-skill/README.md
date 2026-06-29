# Salesforce Observability skill — for the gearset-devops-deployments repo

Lets the Salesforce team query the **sf-observability ClickHouse data**
(`salesforceProd`) in plain language from Claude Code, via a `/salesforce-observability`
slash command — the same idea as the LibreChat "Salesforce Security Analyst",
packaged for the team's existing Claude Code workflow.

**Why this is safe by design:** it uses ClickHouse Cloud's **remote MCP server
with OAuth** — each developer authenticates as themselves, access is **read-only**
and enforced per user, and **no shared secret is committed**. The `.mcp.json` only
holds the public MCP URL.

---

## Install (drop into `ClickHouse/gearset-devops-deployments`)

Copy these two files into the repo, preserving paths:

| From here | To gearset repo |
|-----------|-----------------|
| `.mcp.json` | repo root → `.mcp.json` |
| `.claude/commands/salesforce-observability.md` | `.claude/commands/salesforce-observability.md` |

Then open a PR following the repo's normal flow (feature branch → PR to `full`).

> If the repo already has a root `.mcp.json`, merge the `clickhouse-cloud` entry
> into its existing `mcpServers` block rather than overwriting the file.

## Prerequisites (one-time)

1. **Enable the ClickHouse Cloud remote MCP** on the org's service: Cloud console →
   the service → **Connect** menu → enable the remote MCP server. (It's in private
   preview and **off by default**; join the waitlist at clickhouse.ai if it isn't
   available yet.)
2. **Each developer needs a ClickHouse Cloud account** in the org with **read
   access to `salesforceProd`** — that's the identity the MCP acts as via OAuth.

## Usage

In Claude Code (inside the gearset repo), the first time the `clickhouse-cloud`
MCP is used it runs an **OAuth flow** in the browser — approve it once. Then:

```
/salesforce-observability top API consumers vs the daily limit today
/salesforce-observability failed-login bursts by IP in the last 24 hours
/salesforce-observability which connected apps drove the most REST calls this week
```

The command writes and runs the ClickHouse `SELECT`s for you and summarizes the
findings — read-only, schema-aware, with connected-app names and driving users
resolved (never raw opaque IDs).

## Notes / differences from the LibreChat agent
- **Auth:** per-developer OAuth via the remote MCP (no shared `sf_readonly`
  password, unlike the server-side LibreChat MCP).
- **Invocation:** explicit `/salesforce-observability <question>` slash command
  (vs LibreChat's auto-selected model spec).
- The command embeds the same schema map + ClickHouse conventions, the hardened
  connected-app resolution, and treats the API limit as dynamic (not hardcoded).
