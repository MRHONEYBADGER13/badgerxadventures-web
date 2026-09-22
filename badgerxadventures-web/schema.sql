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

-- x/y are fractional map coordinates (0..1 across the illustrated map's
-- width/height) -- the same coordinate space the themed map's own client-side
-- rendering code uses natively, so no lat/lon <-> pixel conversion is needed
-- anywhere. Set once when the pin is first placed; an owner can never change
-- it again (enforced server-side, not just hidden in the UI) -- only an
-- admin edit can move a pin.
CREATE TABLE IF NOT EXISTS pins (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id     INTEGER UNIQUE REFERENCES owners(id) ON DELETE CASCADE, -- NULL for admin-made pins with no owner login
  pin_type     TEXT NOT NULL CHECK (pin_type IN ('business','stay','custom')),
  sub_type     TEXT NOT NULL DEFAULT '',      -- business: a CATS id (gas/marina/food/...); stay: a TYPES id (cabin/house/...); custom: unused
  title        TEXT NOT NULL,
  description  TEXT NOT NULL DEFAULT '',
  phone        TEXT NOT NULL DEFAULT '',
  address      TEXT NOT NULL DEFAULT '',      -- stay
  route        TEXT NOT NULL DEFAULT '',      -- stay: directions text
  host         TEXT NOT NULL DEFAULT '',      -- stay: optional host name
  hours        TEXT NOT NULL DEFAULT '',      -- business
  when_at      TEXT NOT NULL DEFAULT '',      -- business: for timed cats (music/events), ISO datetime-local string
  menu         TEXT NOT NULL DEFAULT '[]',    -- business: JSON [{"n":..,"p":..}]  (JSONB on Postgres)
  price        INTEGER,                       -- stay: per night
  sleeps       INTEGER,                       -- stay
  beds         INTEGER,                       -- stay
  baths        REAL,                          -- stay
  road_name    TEXT NOT NULL DEFAULT '',      -- stay: traced private road name (optional)
  road_pts     TEXT NOT NULL DEFAULT '[]',    -- stay: JSON [[x,y],...] traced private road (JSONB on Postgres)
  x            REAL NOT NULL,
  y            REAL NOT NULL,
  photos       TEXT NOT NULL DEFAULT '[]',    -- JSON array of image URLs (JSONB on Postgres)
  events       TEXT NOT NULL DEFAULT '',      -- "what's going on" free text (shown on every pin type)
  availability TEXT NOT NULL DEFAULT '[]',    -- stay: JSON array of {"from":"YYYY-MM-DD","to":"YYYY-MM-DD"} (JSONB on Postgres)
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pins_type ON pins(pin_type);
CREATE INDEX IF NOT EXISTS idx_codes_status ON invite_codes(code, status);
