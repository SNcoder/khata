"""
Database connection config for SQLAlchemy.

Railway/production par DATABASE_URL env var se PostgreSQL, warna local SQLite fallback.
Yahan sirf URL/flags compute hote hain — actual engine/session Flask-SQLAlchemy
(`database.models.db`) handle karta hai.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root ki .env yahan se load hoti hai — ye module har code path me sabse
# pehle import hota hai, isliye baaki jagah os.environ padhne se pehle .env values
# available ho jaati hain (DATABASE_URL, APP_PASSWORD, SECRET_KEY, PORT, ...).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Railway ki PostgreSQL URL "postgres://" se shuru hoti hai — SQLAlchemy ko
# "postgresql://" chahiye, isliye normalize karte hain.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_PG = bool(DATABASE_URL)  # True = PostgreSQL, False = SQLite

SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "khata.db")

if USE_PG:
    # psycopg2 driver ke saath SQLAlchemy URL banao
    if DATABASE_URL.startswith("postgresql://"):
        SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace(
            "postgresql://", "postgresql+psycopg2://", 1
        )
    else:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
else:
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{SQLITE_PATH}"
