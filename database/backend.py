"""
Database backend selector.

Picks Postgres (database/postgres_db.py) automatically when DATABASE_URL
is set in the environment, otherwise falls back to SQLite
(database/db.py). This is what api.py and core/observability.py import,
so deploying against Neon/Render/Docker Postgres is a matter of setting
one environment variable -- no code edits required.
"""
from __future__ import annotations
import os

if os.environ.get("DATABASE_URL"):
    from database.postgres_db import (  # noqa: F401
        init_db,
        save_investigation as save,
        get_investigation as get,
        get_investigation_any as get_any,
        list_investigations as list_all,
    )
    init_db()
    BACKEND = "postgres"
else:
    from database.db import save, get, get_any, list_all  # noqa: F401
    BACKEND = "sqlite"
