"""
Database connection layer.
Railway par DATABASE_URL env var se PostgreSQL, warna local SQLite fallback.
"""

import os

from flask import g

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Railway PostgreSQL URL "postgres://" se shuru hota hai — psycopg2 ko
# "postgresql://" chahiye, isliye replace karte hain
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_PG = bool(DATABASE_URL)   # True = PostgreSQL, False = SQLite

if USE_PG:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3
    SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "khata.db")


def connect():
    """Fresh raw connection (Flask app-context se bahar bhi kaam karta hai, e.g. init_db)."""
    if USE_PG:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db:
        db.close()


def qry(sql, params=()):
    """Query chalao — dono databases ke liye placeholder auto-replace."""
    db = get_db()
    cur = db.cursor()
    if USE_PG:
        sql = sql.replace("?", "%s")
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
