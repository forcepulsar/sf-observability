# Schema migrations

Incremental schema changes applied to **existing** ClickHouse databases.

`setup.sh` (which uses `CREATE TABLE IF NOT EXISTS`) only ever creates missing
tables — it never alters a table that already exists. Migrations fill that gap:
they carry column adds, engine changes, and new tables to databases that were
created by an earlier version of the schema, so production and a fresh install
converge on the same shape.

## How it works

- One file per change: `NNN_short_description.sql` (e.g. `001_add_apex_columns.sql`).
  Numbers are zero-padded and applied in filename order.
- `migrate.sh <host> <pw> <db>` applies every file not yet recorded in the
  target database's `schema_migrations` table, then records it. Re-running is
  safe — applied files are skipped.
- A fresh install runs `setup.sh` (base schema = current desired state) and then
  `migrate.sh`; because migrations are idempotent, they no-op on the
  already-current tables and are simply marked as applied.

## Writing a migration

- Reference tables with the `salesforceProd.` prefix. `migrate.sh` substitutes it
  to the target database name (same convention as `setup.sh`).
- Make statements idempotent: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`,
  `CREATE TABLE IF NOT EXISTS`, etc. A migration may be applied to several
  databases (prod, dev, a reference DB) and must be safe everywhere.
- Statements are split on `;`. Keep one statement per logical change.
- **Also update the base schema files** (`schema_core.sql` / `schema_events.sql`)
  so a brand-new install gets the change directly. The migration is how
  *existing* databases catch up; the base files are the source of truth for
  *new* ones. (Yes, the column appears in both — that is expected.)

## Verifying

After writing a migration, confirm prod matches the committed schema:

```bash
./schema/setup.sh   <host> <pw> schema_reference
./schema/migrate.sh <host> <pw> schema_reference
./schema/check_drift.sh <host> <pw> salesforceProd schema_reference
```

No rows = production and the repo agree.
