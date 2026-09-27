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
    _migrate(conn)
    conn.commit()
    conn.close()


def _migrate(conn):
    """Guarded ALTERs for columns added after a table's first deploy.
    schema.sql's CREATE TABLE IF NOT EXISTS only takes effect for a brand
    new database, so an existing table needs an explicit ALTER here."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(chat_bans)")}
    if "name" not in cols:
        conn.execute("ALTER TABLE chat_bans ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    if "expires_at" not in cols:
        conn.execute("ALTER TABLE chat_bans ADD COLUMN expires_at TEXT")


def row_to_dict(row):
    return dict(row) if row is not None else None
