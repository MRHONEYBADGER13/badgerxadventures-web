"""SQLite helpers for the listings app."""
import sqlite3
import os

_RENDER_DISK_DIR = "/opt/render/project/src/instance"
DATA_DIR = _RENDER_DISK_DIR if os.path.isdir(_RENDER_DISK_DIR) else os.path.join(os.path.dirname(__file__), "instance")
DB_PATH = os.path.join(DATA_DIR, "app.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def row_to_dict(row):
    return dict(row) if row is not None else None
