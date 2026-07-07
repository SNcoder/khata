"""
Site Khata — Material Management & Site Accounts
-------------------------------------------------
Backend  : Python (Flask)
Database : PostgreSQL (Railway par) ya SQLite (local computer par)
Frontend : static/index.html

LOCAL chalane ke liye:
    pip install -r requirements.txt
    python app.py
    Browser: http://localhost:5000

RAILWAY par automatically:
    DATABASE_URL environment variable se PostgreSQL connect hota hai
    Agar DATABASE_URL nahi mili to SQLite fallback ho jaata hai
"""

import os
import uuid

from flask import Flask, g, jsonify, request, send_from_directory

# ── Database driver decide karo ──────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Railway PostgreSQL URL "postgres://" se shuru hota hai — psycopg2 ko
# "postgresql://" chahiye, isliye replace karte hain
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_PG = bool(DATABASE_URL)   # True = PostgreSQL, False = SQLite

if USE_PG:
    import psycopg2
    import psycopg2.extras
    PH = "%s"          # PostgreSQL placeholder
else:
    import sqlite3
    SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "khata.db")
    PH = "?"           # SQLite placeholder

app = Flask(__name__, static_folder="static")


# ── DB connection helpers ────────────────────────────────────────────────────
def get_db():
    if "db" not in g:
        if USE_PG:
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = False
            g.db = conn
        else:
            conn = sqlite3.connect(SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def qry(sql, params=()):
    """Query chalao — dono databases ke liye placeholder auto-replace."""
    db = get_db()
    cur = db.cursor()
    if USE_PG:
        # SQLite ? → PostgreSQL %s
        sql = sql.replace("?", "%s")
        # PostgreSQL CHECK constraints alag syntax mein likhte hain
    cur.execute(sql, params)
    return cur


def rows(cur):
    """Cursor se list of dict banao."""
    if USE_PG:
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    return [dict(r) for r in cur.fetchall()]


def commit():
    get_db().commit()


# ── Schema ───────────────────────────────────────────────────────────────────
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
    note      TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vendors (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    phone     TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vendor_txns (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    vendor_id TEXT NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    type      TEXT NOT NULL,
    amount    REAL NOT NULL,
    date      TEXT NOT NULL,
    by_name   TEXT DEFAULT '',
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
"""

# PostgreSQL: IF NOT EXISTS aur TEXT PRIMARY KEY sahi kaam karta hai
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
    note      TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vendors (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    phone     TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vendor_txns (
    id        TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    vendor_id TEXT NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    type      TEXT NOT NULL,
    amount    DOUBLE PRECISION NOT NULL,
    date      TEXT NOT NULL,
    by_name   TEXT DEFAULT '',
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
"""


def init_db():
    if USE_PG:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        for stmt in SCHEMA_PG.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        conn.commit()
        conn.close()
        print("PostgreSQL database ready ✓")
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.executescript(SCHEMA_SQLITE)
        conn.commit()
        conn.close()
        print(f"SQLite database ready ✓  ({SQLITE_PATH})")


def new_id():
    return uuid.uuid4().hex


# ── Frontend ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── Bootstrap ────────────────────────────────────────────────────────────────
@app.get("/api/bootstrap")
def bootstrap():
    clients = rows(qry("SELECT * FROM clients ORDER BY name"))
    client_id = request.args.get("client_id") or (clients[0]["id"] if clients else "")

    data = {
        "clients": clients,
        "client_id": client_id,
        "sites": [],
        "entries": [],
        "vendors": [],
        "vendor_txns": [],
        "expenses": [],
    }
    if client_id:
        data["sites"]       = rows(qry("SELECT * FROM sites WHERE client_id=? ORDER BY name", (client_id,)))
        data["entries"]     = rows(qry("SELECT * FROM entries WHERE client_id=? ORDER BY date DESC", (client_id,)))
        data["vendors"]     = rows(qry("SELECT * FROM vendors WHERE client_id=? ORDER BY name", (client_id,)))
        data["vendor_txns"] = rows(qry("SELECT * FROM vendor_txns WHERE client_id=? ORDER BY date DESC", (client_id,)))
        data["expenses"]    = rows(qry("SELECT * FROM expenses WHERE client_id=? ORDER BY date DESC", (client_id,)))
    return jsonify(data)


# ── Clients & Sites ──────────────────────────────────────────────────────────
@app.post("/api/clients")
def add_client():
    body = request.get_json(force=True)
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Client ka naam zaroori hai"}), 400
    cid = new_id()
    qry("INSERT INTO clients (id, name) VALUES (?,?)", (cid, name))
    for s in body.get("sites", []):
        s = (s or "").strip()
        if s:
            qry("INSERT INTO sites (id, client_id, name) VALUES (?,?,?)", (new_id(), cid, s))
    commit()
    return jsonify({"id": cid}), 201


@app.post("/api/sites")
def add_site():
    body = request.get_json(force=True)
    name      = (body.get("name") or "").strip()
    client_id = body.get("client_id")
    if not name or not client_id:
        return jsonify({"error": "Site ka naam aur client_id zaroori hai"}), 400
    qry("INSERT INTO sites (id, client_id, name) VALUES (?,?,?)", (new_id(), client_id, name))
    commit()
    return jsonify({"ok": True}), 201


# ── Entries (material + asset) ───────────────────────────────────────────────
@app.post("/api/entries")
def add_entry():
    b = request.get_json(force=True)
    required = ["client_id", "kind", "type", "date", "item", "qty", "unit"]
    if any(not b.get(k) for k in required):
        return jsonify({"error": "Zaroori fields missing hain"}), 400
    if b["kind"] not in ("material", "asset"):
        return jsonify({"error": "kind galat hai"}), 400
    if b["type"] not in ("Purchase", "Sale", "Transfer", "Consumed"):
        return jsonify({"error": "type galat hai"}), 400
    try:
        qty  = float(b["qty"])
        rate = float(b.get("rate") or 0)
    except ValueError:
        return jsonify({"error": "Qty/Rate number hone chahiye"}), 400
    if qty <= 0:
        return jsonify({"error": "Qty 0 se zyada honi chahiye"}), 400
    if b["type"] == "Transfer" and b.get("from_loc") == b.get("to_loc"):
        return jsonify({"error": "Transfer mein From aur To alag hone chahiye"}), 400

    eid = new_id()
    qry(
        """INSERT INTO entries
           (id,client_id,kind,type,date,item,qty,unit,rate,from_loc,to_loc,vendor_id,note)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (eid, b["client_id"], b["kind"], b["type"], b["date"],
         b["item"].strip(), qty, b["unit"], rate,
         b.get("from_loc",""), b.get("to_loc",""),
         b.get("vendor_id",""), b.get("note","")),
    )

    # Auto Goods Received in vendor ledger
    if b["type"]=="Purchase" and b.get("vendor_id") and b.get("create_grn") and qty*rate>0:
        qry(
            """INSERT INTO vendor_txns
               (id,client_id,vendor_id,type,amount,date,by_name,note)
               VALUES (?,?,?,?,?,?,?,?)""",
            (new_id(), b["client_id"], b["vendor_id"], "Goods Received",
             qty*rate, b["date"], b.get("by_name","Site Engineer"),
             f"{b['item'].strip()} — {qty:g} {b['unit']} @ ₹{rate:g}"),
        )
    commit()
    return jsonify({"id": eid}), 201


@app.delete("/api/entries/<eid>")
def del_entry(eid):
    qry("DELETE FROM entries WHERE id=?", (eid,))
    commit()
    return jsonify({"ok": True})


# ── Vendors ──────────────────────────────────────────────────────────────────
@app.post("/api/vendors")
def add_vendor():
    b = request.get_json(force=True)
    name = (b.get("name") or "").strip()
    if not name or not b.get("client_id"):
        return jsonify({"error": "Vendor ka naam zaroori hai"}), 400
    vid = new_id()
    qry("INSERT INTO vendors (id,client_id,name,phone) VALUES (?,?,?,?)",
        (vid, b["client_id"], name, b.get("phone","")))
    commit()
    return jsonify({"id": vid}), 201


@app.post("/api/vendor_txns")
def add_vendor_txn():
    b = request.get_json(force=True)
    if b.get("type") not in ("Goods Received","Payment"):
        return jsonify({"error": "type galat hai"}), 400
    try:
        amount = float(b.get("amount") or 0)
    except ValueError:
        return jsonify({"error": "Amount number hona chahiye"}), 400
    if amount<=0 or not b.get("vendor_id") or not b.get("client_id"):
        return jsonify({"error": "Vendor, client aur amount zaroori hain"}), 400
    tid = new_id()
    qry(
        """INSERT INTO vendor_txns
           (id,client_id,vendor_id,type,amount,date,by_name,note)
           VALUES (?,?,?,?,?,?,?,?)""",
        (tid, b["client_id"], b["vendor_id"], b["type"], amount,
         b.get("date",""), b.get("by_name",""), b.get("note","")),
    )
    commit()
    return jsonify({"id": tid}), 201


@app.delete("/api/vendor_txns/<tid>")
def del_vendor_txn(tid):
    qry("DELETE FROM vendor_txns WHERE id=?", (tid,))
    commit()
    return jsonify({"ok": True})


# ── Expenses ─────────────────────────────────────────────────────────────────
@app.post("/api/expenses")
def add_expense():
    b = request.get_json(force=True)
    required = ["client_id","site","date","category","item","qty","unit"]
    if any(not b.get(k) for k in required):
        return jsonify({"error": "Zaroori fields missing hain"}), 400
    try:
        qty  = float(b["qty"])
        rate = float(b.get("rate") or 0)
    except ValueError:
        return jsonify({"error": "Qty/Rate number hone chahiye"}), 400
    if qty<=0:
        return jsonify({"error": "Qty 0 se zyada honi chahiye"}), 400
    xid = new_id()
    qry(
        """INSERT INTO expenses
           (id,client_id,site,date,category,item,qty,unit,rate,note)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (xid, b["client_id"], b["site"], b["date"], b["category"],
         b["item"].strip(), qty, b["unit"], rate, b.get("note","")),
    )
    commit()
    return jsonify({"id": xid}), 201


@app.delete("/api/expenses/<xid>")
def del_expense(xid):
    qry("DELETE FROM expenses WHERE id=?", (xid,))
    commit()
    return jsonify({"ok": True})


# ── Health check (Railway monitoring ke liye) ────────────────────────────────
@app.get("/health")
def health():
    return jsonify({"status": "ok", "db": "postgresql" if USE_PG else "sqlite"})


# ── Start ────────────────────────────────────────────────────────────────────
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Site Khata chal raha hai → http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
