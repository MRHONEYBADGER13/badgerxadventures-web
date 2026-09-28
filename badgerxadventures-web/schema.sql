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
  link_pin_id INTEGER,               -- optional; banner flies to this pin instead (mutually exclusive with link_url)
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
-- account) from claiming a name or posting again. Auto-expires after a
-- few minutes (expires_at) unless an admin adds them back sooner.
CREATE TABLE IF NOT EXISTS chat_bans (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT,
  owner_id    INTEGER,
  name        TEXT NOT NULL DEFAULT '',
  name_lower  TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at  TEXT
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

-- Whether a currently-active chatter's device last reported itself as
-- being out on the lake (from their own private "my location" duck, never
-- their exact coordinates). Only a yes/no plus a timestamp is kept, so a
-- row that hasn't been refreshed in a while (chat_cleanup) simply stops
-- counting as "on the lake" -- absence, not a stored "no", is the default.
-- x/y (present only once a fix has come in) are the same map-pixel space
-- pins.x/y live in (0..MAP.W, 0..MAP.H on the client) -- still never shown
-- to anyone by themselves; they only ever leave this table through a
-- mutually-agreed chat_pings request below.
CREATE TABLE IF NOT EXISTS chat_locations (
  session_id  TEXT,
  owner_id    INTEGER,
  on_lake     INTEGER NOT NULL DEFAULT 0,
  x           REAL,
  y           REAL,
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_chat_locations_session ON chat_locations(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_locations_owner ON chat_locations(owner_id);

-- A mutual-consent request to briefly show two Lake Chat people's current
-- locations to each other, on the lake map only -- never in chat text and
-- never anywhere else. Typing "ping@Name" creates one of these; sending it
-- is NOT agreeing to it -- both from_agreed and to_agreed have to be set
-- (each from that person explicitly clicking Agree) before anything is
-- filled in. The moment both are set, each side's chat_locations x/y at
-- that instant is copied into from_x/y and to_x/y as a one-time snapshot
-- (never refreshed again) and expires_at is pushed out so the reveal stays
-- up for a while; a request nobody ever agreed to just expires on its own.
CREATE TABLE IF NOT EXISTS chat_pings (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  from_session_id  TEXT,
  from_owner_id    INTEGER,
  from_name_lower  TEXT NOT NULL,
  to_session_id    TEXT,
  to_owner_id      INTEGER,
  to_name_lower    TEXT NOT NULL,
  from_agreed      INTEGER NOT NULL DEFAULT 0,
  to_agreed        INTEGER NOT NULL DEFAULT 0,
  from_x           REAL,
  from_y           REAL,
  to_x             REAL,
  to_y             REAL,
  status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','agreed','declined')),
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_pings_from ON chat_pings(from_session_id, from_owner_id);
CREATE INDEX IF NOT EXISTS idx_chat_pings_to ON chat_pings(to_session_id, to_owner_id);

-- Site-visit counter, shown only on the admin dashboard. One row per unique
-- visitor (a salted hash of their IP, never the IP itself) per calendar day
-- (UTC) -- loading the page twice in a day doesn't inflate it. "Since
-- launch" = distinct ip_hash across every row; "today" = COUNT(*) for
-- today's date, already deduplicated by the primary key.
CREATE TABLE IF NOT EXISTS site_visits (
  day      TEXT NOT NULL,   -- YYYY-MM-DD (UTC)
  ip_hash  TEXT NOT NULL,
  PRIMARY KEY (day, ip_hash)
);
CREATE INDEX IF NOT EXISTS idx_site_visits_day ON site_visits(day);
