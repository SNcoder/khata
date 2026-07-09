"""
Pydantic validation + normalization schemas for Site Khata.

Ye purane `routes.py` ke `*_error` (validation) aur `*_values` (normalization)
helpers ki jagah leti hai — bilkul wahi rules aur wahi Hinglish error messages.

Har schema `mode="before"` validator me raw request body leta hai, rules check
karta hai (galat par ValueError raise), aur normalized dict return karta hai jise
Pydantic typed fields me daal deta hai. Routes `load(Schema, body)` use karte hain.
"""

from typing import List, Optional

from pydantic import BaseModel, ValidationError, model_validator

# ── Domain constants (routes se yahan move kiye) ──────────────────────────────
STATUSES = ("Active", "Inactive")
ENTRY_KINDS = ("material", "asset")
ENTRY_TYPES = ("Purchase", "Sale", "Transfer", "Consumed")
LABOUR_TYPES = (
    "General Labour", "Contractor Labour", "Steel Binding Labour", "Mason",
    "Carpenter", "Painter", "Electrician", "Plumber", "Tile Worker",
    "Helper", "Other",
)
PAYMENT_MODES = ("Cash", "Online", "Bank Transfer", "UPI", "Cheque")


def load(schema, body):
    """
    (data, None) return karta hai agar valid, warna (None, error_message).
    Error message wahi Hinglish string hota hai jo schema ne raise ki.
    """
    try:
        return schema.model_validate(body or {}), None
    except ValidationError as e:
        errs = e.errors()
        msg = errs[0].get("msg", "Invalid input") if errs else "Invalid input"
        # Pydantic v2 custom ValueError ko "Value error, ..." prefix karta hai
        prefix = "Value error, "
        if msg.startswith(prefix):
            msg = msg[len(prefix):]
        return None, msg


# ── Clients ───────────────────────────────────────────────────────────────────
class ClientIn(BaseModel):
    name: str
    contact_person: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    status: str = "Active"
    sites: List[str] = []

    @model_validator(mode="before")
    @classmethod
    def _v(cls, b):
        b = b or {}
        name = (b.get("name") or "").strip()
        if not name:
            raise ValueError("Client ka naam zaroori hai")
        status = b.get("status") or "Active"
        if status not in STATUSES:
            raise ValueError("status galat hai")
        return {
            "name": name,
            "contact_person": b.get("contact_person", ""),
            "phone": b.get("phone", ""),
            "email": b.get("email", ""),
            "address": b.get("address", ""),
            "status": status,
            "sites": b.get("sites", []) or [],
        }


# ── Sites ───────────────────────────────────────────────────────────────────
class SiteIn(BaseModel):
    client_id: str
    name: str
    address: str = ""
    status: str = "Active"

    @model_validator(mode="before")
    @classmethod
    def _v(cls, b):
        b = b or {}
        name = (b.get("name") or "").strip()
        if not name:
            raise ValueError("Site ka naam zaroori hai")
        if not b.get("client_id"):
            raise ValueError("client_id zaroori hai")
        status = b.get("status") or "Active"
        if status not in STATUSES:
            raise ValueError("status galat hai")
        return {
            "client_id": b["client_id"],
            "name": name,
            "address": b.get("address", ""),
            "status": status,
        }


# ── Entries (material + asset) ────────────────────────────────────────────────
class EntryIn(BaseModel):
    client_id: Optional[str] = None
    kind: str
    type: str
    date: str
    item: str
    qty: float
    unit: str
    rate: float = 0
    from_loc: str = ""
    to_loc: str = ""
    vendor_id: str = ""
    vehicle: str = ""
    note: str = ""
    create_grn: bool = False
    by_name: str = "Site Engineer"

    @model_validator(mode="before")
    @classmethod
    def _v(cls, b):
        b = b or {}
        required = ["kind", "type", "date", "item", "qty", "unit"]
        if any(not b.get(k) for k in required):
            raise ValueError("Zaroori fields missing hain")
        if b["kind"] not in ENTRY_KINDS:
            raise ValueError("kind galat hai")
        if b["type"] not in ENTRY_TYPES:
            raise ValueError("type galat hai")
        try:
            qty = float(b["qty"])
            rate = float(b.get("rate") or 0)
        except (TypeError, ValueError):
            raise ValueError("Qty/Rate number hone chahiye")
        if qty <= 0:
            raise ValueError("Qty 0 se zyada honi chahiye")
        if b["type"] == "Transfer":
            if not b.get("from_loc") or not b.get("to_loc"):
                raise ValueError("Transfer mein From aur To dono zaroori hain")
            if b["from_loc"] == b["to_loc"]:
                raise ValueError("Transfer mein From aur To alag hone chahiye")
        elif b["type"] == "Purchase":
            if not b.get("to_loc"):
                raise ValueError("Location zaroori hai")
        elif not b.get("from_loc"):
            raise ValueError("Location zaroori hai")
        return {
            "client_id": b.get("client_id"),
            "kind": b["kind"],
            "type": b["type"],
            "date": b["date"],
            "item": b["item"].strip(),
            "qty": qty,
            "unit": b["unit"],
            "rate": rate,
            "from_loc": b.get("from_loc", ""),
            "to_loc": b.get("to_loc", ""),
            "vendor_id": b.get("vendor_id", ""),
            "vehicle": b.get("vehicle", ""),
            "note": b.get("note", ""),
            "create_grn": bool(b.get("create_grn")),
            "by_name": b.get("by_name", "Site Engineer"),
        }


# ── Vendors ───────────────────────────────────────────────────────────────────
class VendorIn(BaseModel):
    client_id: Optional[str] = None
    name: str
    phone: str = ""
    contact_person: str = ""
    gst: str = ""
    address: str = ""
    category: str = ""
    status: str = "Active"

    @model_validator(mode="before")
    @classmethod
    def _v(cls, b):
        b = b or {}
        name = (b.get("name") or "").strip()
        if not name:
            raise ValueError("Vendor ka naam zaroori hai")
        status = b.get("status") or "Active"
        if status not in STATUSES:
            raise ValueError("status galat hai")
        return {
            "client_id": b.get("client_id"),
            "name": name,
            "phone": b.get("phone", ""),
            "contact_person": b.get("contact_person", ""),
            "gst": b.get("gst", ""),
            "address": b.get("address", ""),
            "category": b.get("category", ""),
            "status": status,
        }


# ── Vendor transactions ───────────────────────────────────────────────────────
class VendorTxnIn(BaseModel):
    client_id: Optional[str] = None
    vendor_id: str
    type: str
    amount: float
    date: str = ""
    by_name: str = ""
    mode: str = ""
    reference: str = ""
    note: str = ""

    @model_validator(mode="before")
    @classmethod
    def _v(cls, b):
        b = b or {}
        if b.get("type") not in ("Goods Received", "Payment"):
            raise ValueError("type galat hai")
        try:
            amount = float(b.get("amount") or 0)
        except (TypeError, ValueError):
            raise ValueError("Amount number hona chahiye")
        if amount <= 0 or not b.get("vendor_id"):
            raise ValueError("Vendor aur amount zaroori hain")
        return {
            "client_id": b.get("client_id"),
            "vendor_id": b["vendor_id"],
            "type": b["type"],
            "amount": amount,
            "date": b.get("date", ""),
            "by_name": b.get("by_name", ""),
            "mode": b.get("mode", ""),
            "reference": b.get("reference", ""),
            "note": b.get("note", ""),
        }


# ── Expenses ──────────────────────────────────────────────────────────────────
class ExpenseIn(BaseModel):
    client_id: Optional[str] = None
    site: str
    date: str
    category: str
    item: str
    qty: float
    unit: str
    rate: float = 0
    note: str = ""

    @model_validator(mode="before")
    @classmethod
    def _v(cls, b):
        b = b or {}
        required = ["site", "date", "category", "item", "qty", "unit"]
        if any(not b.get(k) for k in required):
            raise ValueError("Zaroori fields missing hain")
        try:
            qty = float(b["qty"])
            rate = float(b.get("rate") or 0)
        except (TypeError, ValueError):
            raise ValueError("Qty/Rate number hone chahiye")
        if qty <= 0:
            raise ValueError("Qty 0 se zyada honi chahiye")
        return {
            "client_id": b.get("client_id"),
            "site": b["site"],
            "date": b["date"],
            "category": b["category"],
            "item": b["item"].strip(),
            "qty": qty,
            "unit": b["unit"],
            "rate": rate,
            "note": b.get("note", ""),
        }


# ── Materials master ──────────────────────────────────────────────────────────
class MaterialIn(BaseModel):
    client_id: str
    name: str
    unit: str = ""
    category: str = ""

    @model_validator(mode="before")
    @classmethod
    def _v(cls, b):
        b = b or {}
        name = (b.get("name") or "").strip()
        if not name or not b.get("client_id"):
            raise ValueError("Material ka naam zaroori hai")
        return {
            "client_id": b["client_id"],
            "name": name,
            "unit": b.get("unit", ""),
            "category": b.get("category", ""),
        }


# ── Labourers ─────────────────────────────────────────────────────────────────
class LabourerIn(BaseModel):
    client_id: Optional[str] = None
    name: str
    phone: str = ""
    address: str = ""
    id_number: str = ""
    type: str = "General Labour"
    contractor_id: str = ""
    site: str = ""
    joining_date: str = ""
    status: str = "Active"

    @model_validator(mode="before")
    @classmethod
    def _v(cls, b):
        b = b or {}
        name = (b.get("name") or "").strip()
        if not name:
            raise ValueError("Labour ka naam zaroori hai")
        typ = b.get("type") or "General Labour"
        if typ not in LABOUR_TYPES:
            raise ValueError("Labour type galat hai")
        status = b.get("status") or "Active"
        if status not in STATUSES:
            raise ValueError("status galat hai")
        return {
            "client_id": b.get("client_id"),
            "name": name,
            "phone": b.get("phone", ""),
            "address": b.get("address", ""),
            "id_number": b.get("id_number", ""),
            "type": typ,
            "contractor_id": b.get("contractor_id", ""),
            "site": b.get("site", ""),
            "joining_date": b.get("joining_date", ""),
            "status": status,
        }


# ── Labour payments ───────────────────────────────────────────────────────────
class LabourPaymentIn(BaseModel):
    client_id: Optional[str] = None
    labour_id: str
    site: str = ""
    amount: float
    date: str
    mode: str = "Cash"
    reference: str = ""
    note: str = ""

    @model_validator(mode="before")
    @classmethod
    def _v(cls, b):
        b = b or {}
        try:
            amount = float(b.get("amount") or 0)
        except (TypeError, ValueError):
            raise ValueError("Amount number hona chahiye")
        if amount <= 0 or not b.get("labour_id") or not b.get("date"):
            raise ValueError("Labour, date aur amount zaroori hain")
        mode = b.get("mode") or "Cash"
        if mode not in PAYMENT_MODES:
            raise ValueError("Payment mode galat hai")
        return {
            "client_id": b.get("client_id"),
            "labour_id": b["labour_id"],
            "site": b.get("site", ""),
            "amount": amount,
            "date": b["date"],
            "mode": mode,
            "reference": b.get("reference", ""),
            "note": b.get("note", ""),
        }


# ── Receipts (incoming payments) ──────────────────────────────────────────────
class ReceiptIn(BaseModel):
    client_id: Optional[str] = None
    date: str
    from_name: str
    amount: float
    mode: str = "Cash"
    reference: str = ""
    site: str = ""
    note: str = ""

    @model_validator(mode="before")
    @classmethod
    def _v(cls, b):
        b = b or {}
        from_name = (b.get("from_name") or "").strip()
        if not from_name:
            raise ValueError("Received from zaroori hai")
        try:
            amount = float(b.get("amount") or 0)
        except (TypeError, ValueError):
            raise ValueError("Amount number hona chahiye")
        if amount <= 0 or not b.get("date"):
            raise ValueError("Received from, date aur amount zaroori hain")
        mode = b.get("mode") or "Cash"
        if mode not in PAYMENT_MODES:
            raise ValueError("Payment mode galat hai")
        return {
            "client_id": b.get("client_id"),
            "date": b["date"],
            "from_name": from_name,
            "amount": amount,
            "mode": mode,
            "reference": b.get("reference", ""),
            "site": b.get("site", ""),
            "note": b.get("note", ""),
        }
