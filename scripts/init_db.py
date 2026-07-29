"""One-time bootstrap: create all Postgres tables from app/db.py models.

Usage:
    python scripts/init_db.py

Requires DATABASE_URL to be set (in .env locally, or as a secret in CI/Render).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import create_all_tables, is_db_configured

if __name__ == "__main__":
    if not is_db_configured():
        raise SystemExit("DATABASE_URL is not set — nothing to do.")
    create_all_tables()
    print("Tables created (or already existed).")
