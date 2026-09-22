"""SQLite helpers for the listings app."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "app.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
