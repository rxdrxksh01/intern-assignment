"""Database connection helpers for the Netflix API."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ingestion.models import DB_PATH


def connect_database(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the generated SQLite database with row access by column name."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}. Run `python ingest.py` first.")

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection
