"""
PostgreSQL + pgvector persistence layer (spec section 9, 10).

This is the real thing, not a stand-in: tested in this build against a
live local Postgres 16 + pgvector 0.6.0 instance. It replaces
database/db.py (SQLite) and the TF-IDF index in tools/retrieval.py's
in-memory matrix with a proper vector column and ANN-friendly index.

Connection is configured via env vars (see .env.example):
  DATABASE_URL=postgresql://user:pass@host:5432/dbname
"""
from __future__ import annotations
import os
import json
from sqlalchemy import create_engine, text
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy import Column, String, Text, Integer, DateTime, func

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:labpass@localhost:5432/ai_research_lab")
EMBEDDING_DIM = 384  # matches all-MiniLM-L6-v2; adjust if you swap embedding models

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Investigation(Base):
    __tablename__ = "investigations"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True)
    question = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    datasets = Column(Text, nullable=False)        # JSON list
    state_json = Column(Text, nullable=False)       # hypotheses/evidence/critic/log
    report_markdown = Column(Text)


class DocumentChunk(Base):
    """Vector-indexed document chunks, replacing the in-memory TF-IDF matrix."""
    __tablename__ = "document_chunks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM))


def init_db() -> None:
    Base.metadata.create_all(engine)
    # ANN index for cosine similarity search — ivfflat needs data present to build well,
    # but creating it empty is safe and postgres will use it once populated.
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx "
            "ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        ))
        conn.commit()


def save_investigation(state, user_id: str | None = None) -> None:
    session: Session = SessionLocal()
    try:
        detail = json.dumps({
            "hypotheses": [h.__dict__ for h in state.hypotheses],
            "evidence": [e.__dict__ for e in state.evidence],
            "critic_findings": [f.__dict__ for f in state.critic_findings],
            "log": state.log,
            "agent_timings_s": state.agent_timings_s,
            "total_runtime_s": state.total_runtime_s,
            "revision_cycles": state.counters.get("revision_cycles", 0),
        })
        existing = session.get(Investigation, state.id)
        if existing:
            existing.status = state.status.value
            existing.state_json = detail
            existing.report_markdown = state.report_markdown
            if user_id and not existing.user_id:
                existing.user_id = user_id
        else:
            session.add(Investigation(
                id=state.id, user_id=user_id, question=state.question, status=state.status.value,
                datasets=json.dumps(state.datasets), state_json=detail,
                report_markdown=state.report_markdown,
            ))
        session.commit()
    finally:
        session.close()


def get_investigation_any(investigation_id: str) -> dict | None:
    """Fetch an investigation's full detail with no ownership check --
    for internal/admin use only (e.g. core/observability.py)."""
    session: Session = SessionLocal()
    try:
        row = session.get(Investigation, investigation_id)
        if not row:
            return None
        return {
            "id": row.id, "user_id": row.user_id, "question": row.question, "status": row.status,
            "created_at": str(row.created_at), "datasets": json.loads(row.datasets),
            "detail": json.loads(row.state_json), "report_markdown": row.report_markdown,
        }
    finally:
        session.close()


def get_investigation(investigation_id: str, user_id: str | None = None) -> dict | None:
    session: Session = SessionLocal()
    try:
        row = session.get(Investigation, investigation_id)
        if not row:
            return None
        # Same ownership rule as database/db.py: an owned investigation is only
        # readable by that same user -- not by a different user or anonymously.
        if row.user_id and row.user_id != user_id:
            return None
        return {
            "id": row.id, "user_id": row.user_id, "question": row.question, "status": row.status,
            "created_at": str(row.created_at), "datasets": json.loads(row.datasets),
            "detail": json.loads(row.state_json), "report_markdown": row.report_markdown,
        }
    finally:
        session.close()


def list_investigations(user_id: str | None = None) -> list[dict]:
    session: Session = SessionLocal()
    try:
        query = session.query(Investigation)
        if user_id:
            query = query.filter(Investigation.user_id == user_id)
        rows = query.order_by(Investigation.created_at.desc()).all()
        return [{"id": r.id, "question": r.question, "status": r.status, "created_at": str(r.created_at)} for r in rows]
    finally:
        session.close()


def index_chunks(chunks: list[str], sources: list[str], embeddings: list[list[float]]) -> None:
    session: Session = SessionLocal()
    try:
        for text_, source, emb in zip(chunks, sources, embeddings):
            session.add(DocumentChunk(source=source, text=text_, embedding=emb))
        session.commit()
    finally:
        session.close()


def query_similar(query_embedding: list[float], top_k: int = 3) -> list[dict]:
    session: Session = SessionLocal()
    try:
        rows = (
            session.query(DocumentChunk)
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
            .all()
        )
        return [{"text": r.text, "source": r.source} for r in rows]
    finally:
        session.close()
