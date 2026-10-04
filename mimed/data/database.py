"""
SQLite database management module for mimed.
"""
import sqlite3
from pathlib import Path
from typing import Optional

from mimed.config import DATABASE_PATH, SCHEMA_PATH, DATA_DIR


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open SQLite database connection with row factory enabled."""
    target_path = db_path or DATABASE_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[Path] = None, schema_path: Optional[Path] = None) -> None:
    """Initialize SQLite database with schema tables and indexes."""
    s_path = schema_path or SCHEMA_PATH
    with open(s_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with get_connection(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()


def reset_db(db_path: Optional[Path] = None) -> None:
    """Drop database file or clear all tables if database exists."""
    target_path = db_path or DATABASE_PATH
    if target_path.exists():
        with get_connection(target_path) as conn:
            conn.execute("PRAGMA foreign_keys = OFF;")
            conn.execute("DROP TABLE IF EXISTS milestone_ladders;")
            conn.execute("DROP TABLE IF EXISTS posts;")
            conn.execute("DROP TABLE IF EXISTS campaigns;")
            conn.execute("DROP TABLE IF EXISTS creators;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.commit()
    init_db(target_path)
