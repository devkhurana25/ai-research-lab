"""
Basic API key auth (spec section 27).

Not a full auth system (no users/roles) — a single shared API key checked
via a dependency, which is the appropriate scope for a portfolio project's
backend. Swap for OAuth/JWT + a users table if this ever needs multi-tenant
accounts.
"""
from __future__ import annotations
import os
from fastapi import Header, HTTPException

API_KEY = os.environ.get("API_KEY")  # unset in dev => auth is a no-op, matching .env.example


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if API_KEY is None:
        return  # auth disabled unless API_KEY is configured — see README for enabling it
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key header")
