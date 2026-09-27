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
-- Scrolling ad banner shown at the top of the app, above the map. Admin-only
-- to add/remove; sort_order controls left-to-right order in the strip.
CREATE TABLE IF NOT EXISTS ads (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  image_path  TEXT NOT NULL,        -- /static/uploads/<file>.jpg
  title       TEXT NOT NULL DEFAULT '',  -- optional caption, e.g. "20% off bait this week"
  link_url    TEXT NOT NULL DEFAULT '',  -- optional; banner is clickable if set
  sort_order  INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ads_sort ON ads(sort_order, id);

-- Lake Chat: an ephemeral public chat room. Messages auto-expire 5 hours
-- after posting; a guest's claimed name frees up 7 days after being
-- claimed (both purged lazily whenever chat is touched -- no separate
-- worker needed). A business/stay owner's chat identity is always their
-- pin's title, resolved live from pins.title -- never stored here -- so a
-- guest can never claim a name that currently belongs to a business/stay.
CREATE TABLE IF NOT EXISTS chat_names (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  name_lower  TEXT UNIQUE NOT NULL,
  session_id  TEXT UNIQUE NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_names_expires ON chat_names(expires_at);

CREATE TABLE IF NOT EXISTS chat_messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  name_lower  TEXT NOT NULL,
  session_id  TEXT NOT NULL DEFAULT '',
  owner_id    INTEGER,
  text        TEXT NOT NULL,
  mentions    TEXT NOT NULL DEFAULT '[]',  -- JSON array of lowercased @names (JSONB on Postgres)
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_name ON chat_messages(name_lower);

-- An admin kick: blocks the person (by browser session, or by owner
-- account) from claiming a name or posting again, until unbanned.
CREATE TABLE IF NOT EXISTS chat_bans (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT,
  owner_id    INTEGER,
  name_lower  TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_chat_bans_session ON chat_bans(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_bans_owner ON chat_bans(owner_id);

-- A private admin warning: visible only to the one person it's addressed
-- to (matched back to them by session_id or owner_id at read time).
CREATE TABLE IF NOT EXISTS chat_warnings (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT,
  owner_id    INTEGER,
  name_lower  TEXT NOT NULL DEFAULT '',
  text        TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  read_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_chat_warnings_session ON chat_warnings(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_warnings_owner ON chat_warnings(owner_id);
