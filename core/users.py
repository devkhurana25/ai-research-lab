"""
Multi-user auth (spec section 27, replacing the single shared API key).

Users are stored in the same database as investigations (SQLite by
default, Postgres if DATABASE_URL is set — see database/db.py vs
database/postgres_db.py). Passwords are hashed with bcrypt; sessions are
stateless JWTs signed with JWT_SECRET.

This is deliberately not OAuth/SSO — it's the right amount of auth for a
single-team portfolio project: register, log in, get a token, use the
token. Swapping in OAuth later means adding a provider callback that
issues the same JWTs this module already knows how to verify.
"""
from __future__ import annotations
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from fastapi import Header, HTTPException
import bcrypt
from jose import jwt, JWTError

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = 60 * 24 * 7  # 7 days


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "lab.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    return conn


def _new_id() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def create_user(email: str, password: str) -> dict:
    conn = _connect()
    existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "a user with this email already exists")

    user_id = _new_id()
    password_hash = _hash_password(password)
    created_at = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, email, password_hash, created_at),
        )
    conn.close()
    return {"id": user_id, "email": email, "created_at": created_at}


def authenticate_user(email: str, password: str) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT id, email, password_hash FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    if not row or not _verify_password(password, row[2]):
        return None
    return {"id": row[0], "email": row[1]}


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRES_MINUTES),
        "iat": int(time.time()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(401, "invalid or expired token")


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: require a valid 'Authorization: Bearer <token>' header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing Authorization: Bearer <token> header")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    return {"id": payload["sub"], "email": payload["email"]}


def get_current_user_optional(authorization: str | None = Header(default=None)) -> dict | None:
    """Same as get_current_user but returns None instead of raising — for endpoints
    that behave differently for logged-in vs anonymous users rather than rejecting."""
    if not authorization:
        return None
    try:
        return get_current_user(authorization)
    except HTTPException:
        return None
