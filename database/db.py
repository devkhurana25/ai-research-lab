"""
Persistence layer (spec section 10).

Uses SQLite rather than PostgreSQL+pgvector because no database server is
reachable from this build environment. The schema and access pattern are
deliberately kept swap-compatible: replacing `sqlite3` calls here with
`asyncpg`/SQLAlchemy against Postgres is a drop-in change, not a redesign.
Vector search (RAG) is handled separately in tools/retrieval.py with an
in-memory TF-IDF index, standing in for pgvector.

Investigations are scoped to `user_id` (nullable — anonymous/no-auth usage
still works) once core/users.py issues real user accounts.
"""
from __future__ import annotations
import sqlite3
import json
import os
from core.state import InvestigationState

DB_PATH = os.path.join(os.path.dirname(__file__), "lab.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    question TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    datasets TEXT NOT NULL,       -- JSON list
    state_json TEXT NOT NULL,     -- full serialized state for audit/replay
    report_markdown TEXT
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    # Migrate older DBs created before user_id existed.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(investigations)").fetchall()]
    if "user_id" not in cols:
        conn.execute("ALTER TABLE investigations ADD COLUMN user_id TEXT")
    return conn


def save(state: InvestigationState, user_id: str | None = None) -> None:
    conn = _connect()
    with conn:
        conn.execute(
            """INSERT INTO investigations (id, user_id, question, status, created_at, datasets, state_json, report_markdown)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 status=excluded.status, state_json=excluded.state_json, report_markdown=excluded.report_markdown""",
            (
                state.id, user_id, state.question, state.status.value, state.created_at,
                json.dumps(state.datasets),
                json.dumps({
                    "hypotheses": [h.__dict__ for h in state.hypotheses],
                    "evidence": [e.__dict__ for e in state.evidence],
                    "critic_findings": [f.__dict__ for f in state.critic_findings],
                    "log": state.log,
                    "agent_timings_s": state.agent_timings_s,
                    "total_runtime_s": state.total_runtime_s,
                    "revision_cycles": state.counters.get("revision_cycles", 0),
                }),
                state.report_markdown,
            ),
        )
    conn.close()


def get_any(investigation_id: str) -> dict | None:
    """Fetch an investigation's full detail with no ownership check --
    for internal/admin use only (e.g. core/observability.py). Never expose
    this over an API endpoint without an actual admin-role check in front
    of it; see README's honest-gaps list."""
    conn = _connect()
    row = conn.execute(
        "SELECT id, user_id, question, status, created_at, datasets, state_json, report_markdown FROM investigations WHERE id=?",
        (investigation_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "user_id": row[1], "question": row[2], "status": row[3], "created_at": row[4],
        "datasets": json.loads(row[5]), "detail": json.loads(row[6]), "report_markdown": row[7],
    }


def get(investigation_id: str, user_id: str | None = None) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT id, user_id, question, status, created_at, datasets, state_json, report_markdown FROM investigations WHERE id=?",
        (investigation_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    # If the investigation belongs to a registered user, only that same user may
    # fetch it -- an anonymous caller (no token) must not be able to read it either.
    if row[1] and row[1] != user_id:
        return None
    return {
        "id": row[0], "user_id": row[1], "question": row[2], "status": row[3], "created_at": row[4],
        "datasets": json.loads(row[5]), "detail": json.loads(row[6]), "report_markdown": row[7],
    }


def list_all(user_id: str | None = None) -> list[dict]:
    conn = _connect()
    if user_id:
        rows = conn.execute(
            "SELECT id, question, status, created_at FROM investigations WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, question, status, created_at FROM investigations ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [{"id": r[0], "question": r[1], "status": r[2], "created_at": r[3]} for r in rows]
