"""
SQLAlchemy ORM models for Site Khata.

Ye file purane raw-SQL `schema.py` ki jagah leti hai. Ek hi model set
PostgreSQL aur SQLite dono par kaam karta hai (engine URL se decide hota hai).
"""

from uuid import uuid4

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import joinedload  # noqa: F401 (routes se use hota hai)

db = SQLAlchemy()


def gen_id():
    """Python-side UUID hex id (jaise pehle routes.new_id() karta tha)."""
    return uuid4().hex


# SQLite par foreign-key cascade tabhi chalta hai jab PRAGMA on ho.
# PostgreSQL connections par ye no-op rehta hai.
@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _record):
    try:
        import sqlite3
    except ImportError:  # pragma: no cover
        return
    if isinstance(dbapi_connection, sqlite3.Connection):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()


class Serializable:
    """Har model ko SELECT * jaisa dict deta hai (JSON response ke liye)."""

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


def _fk(target):
    return db.ForeignKey(target, ondelete="CASCADE")


class Client(Serializable, db.Model):
    __tablename__ = "clients"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    name = db.Column(db.String, nullable=False)
    contact_person = db.Column(db.String, default="")
    phone = db.Column(db.String, default="")
    email = db.Column(db.String, default="")
    address = db.Column(db.String, default="")
    status = db.Column(db.String, default="Active")


class Site(Serializable, db.Model):
    __tablename__ = "sites"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    client_id = db.Column(db.String, _fk("clients.id"), nullable=False, index=True)
    name = db.Column(db.String, nullable=False)
    address = db.Column(db.String, default="")
    status = db.Column(db.String, default="Active")

    client = db.relationship("Client")

    def to_dict(self):
        d = super().to_dict()
        d["client_name"] = self.client.name if self.client else ""
        return d


class Entry(Serializable, db.Model):
    __tablename__ = "entries"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    client_id = db.Column(db.String, _fk("clients.id"), nullable=False)
    kind = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)
    date = db.Column(db.String, nullable=False)
    item = db.Column(db.String, nullable=False)
    qty = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String, nullable=False)
    rate = db.Column(db.Float, nullable=False, default=0)
    from_loc = db.Column(db.String, default="")
    to_loc = db.Column(db.String, default="")
    vendor_id = db.Column(db.String, default="")
    vehicle = db.Column(db.String, default="")
    note = db.Column(db.String, default="")

    __table_args__ = (db.Index("idx_entries_client_date", "client_id", "date"),)


class Vendor(Serializable, db.Model):
    __tablename__ = "vendors"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    client_id = db.Column(db.String, _fk("clients.id"), nullable=False, index=True)
    name = db.Column(db.String, nullable=False)
    phone = db.Column(db.String, default="")
    contact_person = db.Column(db.String, default="")
    gst = db.Column(db.String, default="")
    address = db.Column(db.String, default="")
    category = db.Column(db.String, default="")
    status = db.Column(db.String, default="Active")


class VendorTxn(Serializable, db.Model):
    __tablename__ = "vendor_txns"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    client_id = db.Column(db.String, _fk("clients.id"), nullable=False)
    vendor_id = db.Column(db.String, _fk("vendors.id"), nullable=False)
    type = db.Column(db.String, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.String, nullable=False)
    by_name = db.Column(db.String, default="")
    mode = db.Column(db.String, default="")
    reference = db.Column(db.String, default="")
    note = db.Column(db.String, default="")

    __table_args__ = (db.Index("idx_vendor_txns_client_date", "client_id", "date"),)


class Expense(Serializable, db.Model):
    __tablename__ = "expenses"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    client_id = db.Column(db.String, _fk("clients.id"), nullable=False)
    site = db.Column(db.String, nullable=False)
    date = db.Column(db.String, nullable=False)
    category = db.Column(db.String, nullable=False)
    item = db.Column(db.String, nullable=False)
    qty = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String, nullable=False)
    rate = db.Column(db.Float, nullable=False, default=0)
    note = db.Column(db.String, default="")

    __table_args__ = (db.Index("idx_expenses_client_date", "client_id", "date"),)


class Material(Serializable, db.Model):
    __tablename__ = "materials"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    client_id = db.Column(db.String, _fk("clients.id"), nullable=False, index=True)
    name = db.Column(db.String, nullable=False)
    unit = db.Column(db.String, default="")
    category = db.Column(db.String, default="")


class Labourer(Serializable, db.Model):
    __tablename__ = "labourers"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    client_id = db.Column(db.String, _fk("clients.id"), nullable=False, index=True)
    name = db.Column(db.String, nullable=False)
    phone = db.Column(db.String, default="")
    address = db.Column(db.String, default="")
    id_number = db.Column(db.String, default="")
    type = db.Column(db.String, nullable=False, default="General Labour")
    contractor_id = db.Column(db.String, default="")
    site = db.Column(db.String, default="")
    joining_date = db.Column(db.String, default="")
    status = db.Column(db.String, nullable=False, default="Active")


class LabourPayment(Serializable, db.Model):
    __tablename__ = "labour_payments"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    client_id = db.Column(db.String, _fk("clients.id"), nullable=False)
    labour_id = db.Column(db.String, _fk("labourers.id"), nullable=False)
    site = db.Column(db.String, default="")
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.String, nullable=False)
    mode = db.Column(db.String, nullable=False, default="Cash")
    reference = db.Column(db.String, default="")
    note = db.Column(db.String, default="")

    __table_args__ = (db.Index("idx_labour_pay_client_date", "client_id", "date"),)


class Receipt(Serializable, db.Model):
    __tablename__ = "receipts"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    client_id = db.Column(db.String, _fk("clients.id"), nullable=False)
    date = db.Column(db.String, nullable=False)
    from_name = db.Column(db.String, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    mode = db.Column(db.String, nullable=False, default="Cash")
    reference = db.Column(db.String, default="")
    site = db.Column(db.String, default="")
    note = db.Column(db.String, default="")

    __table_args__ = (db.Index("idx_receipts_client_date", "client_id", "date"),)


def init_db():
    """Missing tables/indexes bana do (Flask app-context ke andar call karo)."""
    from .connection import SQLALCHEMY_DATABASE_URI, USE_PG

    db.create_all()
    if USE_PG:
        print("PostgreSQL database ready")
    else:
        print(f"SQLite database ready ({SQLALCHEMY_DATABASE_URI})")
