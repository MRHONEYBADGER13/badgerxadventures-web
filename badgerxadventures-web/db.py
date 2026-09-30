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
    if "ip" not in cols:
        conn.execute("ALTER TABLE chat_bans ADD COLUMN ip TEXT")

    chat_names_cols = {row["name"] for row in conn.execute("PRAGMA table_info(chat_names)")}
    if "ip" not in chat_names_cols:
        conn.execute("ALTER TABLE chat_names ADD COLUMN ip TEXT")

    loc_cols = {row["name"] for row in conn.execute("PRAGMA table_info(chat_locations)")}
    if "x" not in loc_cols:
        conn.execute("ALTER TABLE chat_locations ADD COLUMN x REAL")
    if "y" not in loc_cols:
        conn.execute("ALTER TABLE chat_locations ADD COLUMN y REAL")

    ad_cols = {row["name"] for row in conn.execute("PRAGMA table_info(ads)")}
    if "link_pin_id" not in ad_cols:
        conn.execute("ALTER TABLE ads ADD COLUMN link_pin_id INTEGER")

    # An owner's saved card, for the cabin-cleaning marketplace -- set once
    # they add a payment method, so a bid can be authorized the moment they
    # accept it without asking them to re-enter their card every time.
    owner_cols = {row["name"] for row in conn.execute("PRAGMA table_info(owners)")}
    if "stripe_customer_id" not in owner_cols:
        conn.execute("ALTER TABLE owners ADD COLUMN stripe_customer_id TEXT")
    if "stripe_payment_method_id" not in owner_cols:
        conn.execute("ALTER TABLE owners ADD COLUMN stripe_payment_method_id TEXT")
    # An admin "pause": blocks the owner from logging in or using their
    # account, and hides their pin from the public map -- both reversible
    # the moment an admin flips this back off.
    if "suspended" not in owner_cols:
        conn.execute("ALTER TABLE owners ADD COLUMN suspended INTEGER NOT NULL DEFAULT 0")

    # A cleaner's ID-check photos from signup: a selfie plus both sides of a
    # photo ID, stored as bare filenames under ID_VERIFY_DIR (never a public
    # URL -- see app.py). NULL for any cleaner who signed up before this.
    cleaner_cols = {row["name"] for row in conn.execute("PRAGMA table_info(cleaners)")}
    if "id_face_path" not in cleaner_cols:
        conn.execute("ALTER TABLE cleaners ADD COLUMN id_face_path TEXT")
    if "id_front_path" not in cleaner_cols:
        conn.execute("ALTER TABLE cleaners ADD COLUMN id_front_path TEXT")
    if "id_back_path" not in cleaner_cols:
        conn.execute("ALTER TABLE cleaners ADD COLUMN id_back_path TEXT")


def row_to_dict(row):
    return dict(row) if row is not None else None
