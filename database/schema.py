"""Schema definitions + one-time init/migrations for both PostgreSQL and SQLite."""

from . import connection as db

# PostgreSQL aur SQLite dono ke liye compatible schema
SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS clients (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sites (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    kind      TEXT NOT NULL,
    type      TEXT NOT NULL,
    date      TEXT NOT NULL,
    item      TEXT NOT NULL,
    qty       REAL NOT NULL,
    unit      TEXT NOT NULL,
    rate      REAL NOT NULL DEFAULT 0,
    from_loc  TEXT DEFAULT '',
    to_loc    TEXT DEFAULT '',
    vendor_id TEXT DEFAULT '',
    vehicle   TEXT DEFAULT '',
    note      TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vendors (
    id             TEXT PRIMARY KEY,
    client_id      TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    phone          TEXT DEFAULT '',
    contact_person TEXT DEFAULT '',
    gst            TEXT DEFAULT '',
    address        TEXT DEFAULT '',
    category       TEXT DEFAULT '',
    status         TEXT DEFAULT 'Active'
);
CREATE TABLE IF NOT EXISTS vendor_txns (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    vendor_id TEXT NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    type      TEXT NOT NULL,
    amount    REAL NOT NULL,
    date      TEXT NOT NULL,
    by_name   TEXT DEFAULT '',
    mode      TEXT DEFAULT '',
    reference TEXT DEFAULT '',
    note      TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS expenses (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    site      TEXT NOT NULL,
    date      TEXT NOT NULL,
    category  TEXT NOT NULL,
    item      TEXT NOT NULL,
    qty       REAL NOT NULL,
    unit      TEXT NOT NULL,
    rate      REAL NOT NULL DEFAULT 0,
    note      TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS materials (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    unit      TEXT DEFAULT '',
    category  TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS labourers (
    id            TEXT PRIMARY KEY,
    client_id     TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    phone         TEXT DEFAULT '',
    address       TEXT DEFAULT '',
    id_number     TEXT DEFAULT '',
    type          TEXT NOT NULL DEFAULT 'General Labour',
    contractor_id TEXT DEFAULT '',
    site          TEXT DEFAULT '',
    joining_date  TEXT DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'Active'
);
CREATE TABLE IF NOT EXISTS labour_payments (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    labour_id TEXT NOT NULL REFERENCES labourers(id) ON DELETE CASCADE,
    site      TEXT DEFAULT '',
    amount    REAL NOT NULL,
    date      TEXT NOT NULL,
    mode      TEXT NOT NULL DEFAULT 'Cash',
    reference TEXT DEFAULT '',
    note      TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS receipts (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date      TEXT NOT NULL,
    from_name TEXT NOT NULL,
    amount    REAL NOT NULL,
    mode      TEXT NOT NULL DEFAULT 'Cash',
    reference TEXT DEFAULT '',
    site      TEXT DEFAULT '',
    note      TEXT DEFAULT ''
);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS clients (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sites (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    kind      TEXT NOT NULL,
    type      TEXT NOT NULL,
    date      TEXT NOT NULL,
    item      TEXT NOT NULL,
    qty       DOUBLE PRECISION NOT NULL,
    unit      TEXT NOT NULL,
    rate      DOUBLE PRECISION NOT NULL DEFAULT 0,
    from_loc  TEXT DEFAULT '',
    to_loc    TEXT DEFAULT '',
    vendor_id TEXT DEFAULT '',
    vehicle   TEXT DEFAULT '',
    note      TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vendors (
    id             TEXT PRIMARY KEY,
    client_id      TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    phone          TEXT DEFAULT '',
    contact_person TEXT DEFAULT '',
    gst            TEXT DEFAULT '',
    address        TEXT DEFAULT '',
    category       TEXT DEFAULT '',
    status         TEXT DEFAULT 'Active'
);
CREATE TABLE IF NOT EXISTS vendor_txns (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    vendor_id TEXT NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    type      TEXT NOT NULL,
    amount    DOUBLE PRECISION NOT NULL,
    date      TEXT NOT NULL,
    by_name   TEXT DEFAULT '',
    mode      TEXT DEFAULT '',
    reference TEXT DEFAULT '',
    note      TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS expenses (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    site      TEXT NOT NULL,
    date      TEXT NOT NULL,
    category  TEXT NOT NULL,
    item      TEXT NOT NULL,
    qty       DOUBLE PRECISION NOT NULL,
    unit      TEXT NOT NULL,
    rate      DOUBLE PRECISION NOT NULL DEFAULT 0,
    note      TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS materials (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    unit      TEXT DEFAULT '',
    category  TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS labourers (
    id            TEXT PRIMARY KEY,
    client_id     TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    phone         TEXT DEFAULT '',
    address       TEXT DEFAULT '',
    id_number     TEXT DEFAULT '',
    type          TEXT NOT NULL DEFAULT 'General Labour',
    contractor_id TEXT DEFAULT '',
    site          TEXT DEFAULT '',
    joining_date  TEXT DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'Active'
);
CREATE TABLE IF NOT EXISTS labour_payments (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    labour_id TEXT NOT NULL REFERENCES labourers(id) ON DELETE CASCADE,
    site      TEXT DEFAULT '',
    amount    DOUBLE PRECISION NOT NULL,
    date      TEXT NOT NULL,
    mode      TEXT NOT NULL DEFAULT 'Cash',
    reference TEXT DEFAULT '',
    note      TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS receipts (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date      TEXT NOT NULL,
    from_name TEXT NOT NULL,
    amount    DOUBLE PRECISION NOT NULL,
    mode      TEXT NOT NULL DEFAULT 'Cash',
    reference TEXT DEFAULT '',
    site      TEXT DEFAULT '',
    note      TEXT DEFAULT ''
);
"""

# Purane databases ke liye: naye columns add karo agar missing hain
MIGRATIONS = [
    ("vendors",     "contact_person", "TEXT DEFAULT ''"),
    ("vendors",     "gst",            "TEXT DEFAULT ''"),
    ("vendors",     "address",        "TEXT DEFAULT ''"),
    ("vendors",     "category",       "TEXT DEFAULT ''"),
    ("vendors",     "status",         "TEXT DEFAULT 'Active'"),
    ("vendor_txns", "mode",           "TEXT DEFAULT ''"),
    ("vendor_txns", "reference",      "TEXT DEFAULT ''"),
    ("entries",     "vehicle",        "TEXT DEFAULT ''"),
]

# Badi tables par common lookups ke liye indexes
INDEXES = """
CREATE INDEX IF NOT EXISTS idx_sites_client            ON sites(client_id);
CREATE INDEX IF NOT EXISTS idx_entries_client_date     ON entries(client_id, date);
CREATE INDEX IF NOT EXISTS idx_vendors_client          ON vendors(client_id);
CREATE INDEX IF NOT EXISTS idx_vendor_txns_client_date ON vendor_txns(client_id, date);
CREATE INDEX IF NOT EXISTS idx_expenses_client_date    ON expenses(client_id, date);
CREATE INDEX IF NOT EXISTS idx_materials_client        ON materials(client_id);
CREATE INDEX IF NOT EXISTS idx_labourers_client        ON labourers(client_id);
CREATE INDEX IF NOT EXISTS idx_labour_pay_client_date  ON labour_payments(client_id, date);
CREATE INDEX IF NOT EXISTS idx_receipts_client_date    ON receipts(client_id, date);
"""


def _existing_columns(cur, table):
    if db.USE_PG:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        return {r[0] for r in cur.fetchall()}
    cur.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in cur.fetchall()}


def _run_statements(cur, sql_block):
    for stmt in sql_block.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)


def init_db():
    conn = db.connect()
    cur = conn.cursor()

    _run_statements(cur, SCHEMA_PG if db.USE_PG else SCHEMA_SQLITE)

    for table, col, decl in MIGRATIONS:
        if col not in _existing_columns(cur, table):
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

    _run_statements(cur, INDEXES)

    conn.commit()
    conn.close()
    if db.USE_PG:
        print("PostgreSQL database ready ✓")
    else:
        print(f"SQLite database ready ✓  ({db.SQLITE_PATH})")
