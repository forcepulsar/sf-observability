"""Ingestion telemetry — writes timing rows to ClickHouse for dashboard use.

Two tables (defined in schema/schema_prod.sql):
  - ingestion_events  one row per file or SOQL object sync
  - ingestion_runs    one row per invocation of ingest.py / ingest_threat_store.py
"""

import uuid
from contextlib import contextmanager
from datetime import datetime


def new_run_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


def _insert_safe(client, table: str, row: list, columns: list[str]):
    """Metrics inserts must never break ingestion — swallow and warn."""
    try:
        client.insert(table, [row], column_names=columns)
    except Exception as e:
        print(f"  [warn] metrics write to {table} failed: {e}")


@contextmanager
def timed_event(
    client,
    db: str,
    run_id: str,
    script: str,
    event_type: str,
    source: str,
    identifier: str = "",
    log_date=None,
):
    """Context manager that records one ingestion_events row on exit.

    Usage:
        with timed_event(client, db, run_id, "ingest", "Login", "elf", file_id, d) as set_rows:
            n = do_work()
            set_rows(n)

    Exceptions are captured as status='failed' with error_message, then re-raised.
    """
    started = _now()
    state = {"rows": 0}

    def set_rows(n: int):
        state["rows"] = int(n)

    status = "success"
    err = ""
    try:
        yield set_rows
    except Exception as e:
        status = "failed"
        err = f"{type(e).__name__}: {e}"[:500]
        raise
    finally:
        ended = _now()
        duration_ms = int((ended - started).total_seconds() * 1000)
        _insert_safe(
            client,
            f"{db}.ingestion_events",
            [run_id, script, event_type, source, identifier, log_date,
             started, ended, duration_ms, state["rows"], status, err],
            ["run_id", "script", "event_type", "source", "identifier",
             "log_date", "started_at", "ended_at", "duration_ms",
             "row_count", "status", "error_message"],
        )


def record_event(
    client,
    db: str,
    run_id: str,
    script: str,
    event_type: str,
    source: str,
    identifier: str = "",
    log_date=None,
    row_count: int = 0,
    status: str = "skipped",
    error_message: str = "",
):
    """Record a single ingestion_events row directly (for skipped/no-op cases).

    duration_ms is 0; started_at and ended_at are both set to now.
    """
    now = _now()
    _insert_safe(
        client,
        f"{db}.ingestion_events",
        [run_id, script, event_type, source, identifier, log_date,
         now, now, 0, int(row_count), status, error_message[:500]],
        ["run_id", "script", "event_type", "source", "identifier",
         "log_date", "started_at", "ended_at", "duration_ms",
         "row_count", "status", "error_message"],
    )


def record_run(
    client,
    db: str,
    run_id: str,
    script: str,
    started_at: datetime,
    ended_at: datetime,
    files_total: int,
    rows_total: int,
    errors: int,
):
    status = "failed" if errors and files_total == 0 else ("partial" if errors else "success")
    duration_ms = int((ended_at - started_at).total_seconds() * 1000)
    _insert_safe(
        client,
        f"{db}.ingestion_runs",
        [run_id, script, started_at, ended_at, duration_ms,
         files_total, rows_total, errors, status],
        ["run_id", "script", "started_at", "ended_at", "duration_ms",
         "files_total", "rows_total", "errors", "status"],
    )
