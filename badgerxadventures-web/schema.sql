-- BADGERxADVENTURES listings app — database schema.
-- Written in plain, portable SQL (works on SQLite as shipped here; the same
-- statements run on Postgres/MySQL with only trivial type tweaks, noted below,
-- if this ever needs to move to a bigger database later).

CREATE TABLE IF NOT EXISTS admins (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Single-use invite codes. An admin generates one of these and hands it to a
-- business/cabin owner; redeeming it is the ONLY way to create an account,
-- and each code is good for exactly one pin.
CREATE TABLE IF NOT EXISTS invite_codes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  code        TEXT UNIQUE NOT NULL,
  pin_type    TEXT NOT NULL CHECK (pin_type IN ('business','stay','custom')),
  label       TEXT,                          -- admin's own note, e.g. "for Joe's Marina"
  status      TEXT NOT NULL DEFAULT 'unused' CHECK (status IN ('unused','claimed')),
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  claimed_at  TEXT
);

-- One row per business/cabin owner who has redeemed a code. Tied 1:1 to the
-- code they redeemed, and (after they place it) 1:1 to their one pin.
CREATE TABLE IF NOT EXISTS owners (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  code_id       INTEGER UNIQUE NOT NULL REFERENCES invite_codes(id),
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pins (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id     INTEGER UNIQUE REFERENCES owners(id) ON DELETE CASCADE, -- NULL for admin-made custom pins with no owner login
  pin_type     TEXT NOT NULL CHECK (pin_type IN ('business','stay','custom')),
  title        TEXT NOT NULL,
  description  TEXT NOT NULL DEFAULT '',
  phone        TEXT NOT NULL DEFAULT '',
  address      TEXT NOT NULL DEFAULT '',
  lat          REAL NOT NULL,
  lon          REAL NOT NULL,
  photos       TEXT NOT NULL DEFAULT '[]',   -- JSON array of image paths (JSONB on Postgres)
  events       TEXT NOT NULL DEFAULT '',      -- "what's going on" free text
  availability TEXT NOT NULL DEFAULT '[]',   -- JSON array of {"from":"YYYY-MM-DD","to":"YYYY-MM-DD"} (JSONB on Postgres)
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pins_type ON pins(pin_type);
CREATE INDEX IF NOT EXISTS idx_codes_status ON invite_codes(code, status);
