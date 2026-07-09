"""All API routes for Site Khata (SQLAlchemy ORM + Pydantic schemas)."""

import os

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from database import (
    Client,
    Entry,
    Expense,
    Labourer,
    LabourPayment,
    Material,
    Receipt,
    Site,
    Vendor,
    VendorTxn,
    db,
)
from database.schemas import (
    ClientIn,
    EntryIn,
    ExpenseIn,
    LabourerIn,
    LabourPaymentIn,
    MaterialIn,
    ReceiptIn,
    SiteIn,
    VendorIn,
    VendorTxnIn,
    load,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def bad(msg):
    return jsonify({"error": msg}), 400


def _dicts(query):
    return [row.to_dict() for row in query]


# ── Bootstrap ────────────────────────────────────────────────────────────────
@api_bp.get("/bootstrap")
def bootstrap():
    clients = _dicts(Client.query.order_by(Client.name).all())
    # Stale/foreign client_id (e.g. purani localStorage value) ko ignore karo
    requested = request.args.get("client_id") or ""
    valid_ids = {c["id"] for c in clients}
    client_id = requested if requested in valid_ids else (clients[0]["id"] if clients else "")

    all_sites = _dicts(
        Site.query.options(joinedload(Site.client))
        .join(Client)
        .order_by(Client.name, Site.name)
        .all()
    )

    data = {
        "auth": bool(os.environ.get("APP_PASSWORD", "")),
        "clients": clients,
        "client_id": client_id,
        "all_sites": all_sites,
        "sites": [],
        "entries": [],
        "vendors": [],
        "vendor_txns": [],
        "expenses": [],
        "materials": [],
        "labourers": [],
        "labour_payments": [],
        "receipts": [],
    }
    if client_id:
        by_client = lambda m: m.query.filter_by(client_id=client_id)  # noqa: E731
        data["sites"]           = _dicts(by_client(Site).order_by(Site.name).all())
        data["entries"]         = _dicts(by_client(Entry).order_by(Entry.date.desc()).all())
        data["vendors"]         = _dicts(by_client(Vendor).order_by(Vendor.name).all())
        data["vendor_txns"]     = _dicts(by_client(VendorTxn).order_by(VendorTxn.date.desc()).all())
        data["expenses"]        = _dicts(by_client(Expense).order_by(Expense.date.desc()).all())
        data["materials"]       = _dicts(by_client(Material).order_by(Material.name).all())
        data["labourers"]       = _dicts(by_client(Labourer).order_by(Labourer.name).all())
        data["labour_payments"] = _dicts(by_client(LabourPayment).order_by(LabourPayment.date.desc()).all())
        data["receipts"]        = _dicts(by_client(Receipt).order_by(Receipt.date.desc()).all())
    return jsonify(data)


# ── Clients ────────────────────────────────────────────────────────────────
@api_bp.post("/clients")
def add_client():
    data, err = load(ClientIn, request.get_json(force=True))
    if err:
        return bad(err)
    client = Client(
        name=data.name, contact_person=data.contact_person, phone=data.phone,
        email=data.email, address=data.address, status=data.status,
    )
    db.session.add(client)
    db.session.flush()  # id mil jaaye
    for name in data.sites:
        name = (name or "").strip()
        if name:
            db.session.add(Site(client_id=client.id, name=name))
    db.session.commit()
    return jsonify({"id": client.id}), 201


@api_bp.put("/clients/<cid>")
def update_client(cid):
    data, err = load(ClientIn, request.get_json(force=True))
    if err:
        return bad(err)
    client = db.session.get(Client, cid)
    if not client:
        return bad("Client nahi mila")
    client.name = data.name
    client.contact_person = data.contact_person
    client.phone = data.phone
    client.email = data.email
    client.address = data.address
    client.status = data.status
    db.session.commit()
    return jsonify({"ok": True})


# client delete se pehle check karo — cascade se poora ledger na ud jaaye
CLIENT_DEPENDENCY_TABLES = [
    (Site, "site(s)"),
    (Entry, "material/asset entr(y/ies)"),
    (Vendor, "vendor(s)"),
    (VendorTxn, "vendor transaction(s)"),
    (Expense, "expense(s)"),
    (Material, "material master item(s)"),
    (Labourer, "labourer(s)"),
    (LabourPayment, "labour payment(s)"),
    (Receipt, "receipt(s)"),
]


@api_bp.delete("/clients/<cid>")
def del_client(cid):
    blocks = []
    for model, label in CLIENT_DEPENDENCY_TABLES:
        n = model.query.filter_by(client_id=cid).count()
        if n:
            blocks.append(f"{n} {label}")
    if blocks:
        return jsonify({"error": "Client delete nahi ho sakta — abhi bhi hai: " + ", ".join(blocks) +
                                  ". Pehle inhe remove karo, ya client ko Inactive kar do."}), 409
    Client.query.filter_by(id=cid).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ── Sites ────────────────────────────────────────────────────────────────
@api_bp.post("/sites")
def add_site():
    data, err = load(SiteIn, request.get_json(force=True))
    if err:
        return bad(err)
    db.session.add(Site(
        client_id=data.client_id, name=data.name,
        address=data.address, status=data.status,
    ))
    db.session.commit()
    return jsonify({"ok": True}), 201


# In tables mein site ka naam free-text ke roop mein store hota hai (site_id FK nahi hai)
SITE_REF_MODELS = [
    (Expense, "expense(s)"),
    (Labourer, "labourer(s)"),
    (LabourPayment, "labour payment(s)"),
    (Receipt, "receipt(s)"),
]


@api_bp.put("/sites/<sid>")
def update_site(sid):
    data, err = load(SiteIn, request.get_json(force=True))
    if err:
        return bad(err)
    site = db.session.get(Site, sid)
    if not site:
        return bad("Site nahi mila")
    old_name, client_id = site.name, site.client_id
    new_name = data.name

    site.name = new_name
    site.address = data.address
    site.status = data.status

    # Naam badla to har jagah free-text site references bhi sync karo
    if new_name != old_name:
        Entry.query.filter_by(client_id=client_id, from_loc=old_name).update(
            {"from_loc": new_name}, synchronize_session=False)
        Entry.query.filter_by(client_id=client_id, to_loc=old_name).update(
            {"to_loc": new_name}, synchronize_session=False)
        for model, _ in SITE_REF_MODELS:
            model.query.filter_by(client_id=client_id, site=old_name).update(
                {"site": new_name}, synchronize_session=False)
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/sites/<sid>")
def del_site(sid):
    site = db.session.get(Site, sid)
    if not site:
        return bad("Site nahi mila")
    name, client_id = site.name, site.client_id

    blocks = []
    n = Entry.query.filter(
        Entry.client_id == client_id,
        or_(Entry.from_loc == name, Entry.to_loc == name),
    ).count()
    if n:
        blocks.append(f"{n} material/asset entr(y/ies)")
    for model, label in SITE_REF_MODELS:
        n = model.query.filter_by(client_id=client_id, site=name).count()
        if n:
            blocks.append(f"{n} {label}")

    if blocks:
        return jsonify({"error": "Site delete nahi ho sakta — abhi bhi hai: " + ", ".join(blocks) +
                                  ". Pehle inhe remove/reassign karo, ya site ko Inactive kar do."}), 409
    db.session.delete(site)
    db.session.commit()
    return jsonify({"ok": True})


# ── Entries (material + asset) ───────────────────────────────────────────────
@api_bp.post("/entries")
def add_entry():
    data, err = load(EntryIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    entry = Entry(
        client_id=data.client_id, kind=data.kind, type=data.type, date=data.date,
        item=data.item, qty=data.qty, unit=data.unit, rate=data.rate,
        from_loc=data.from_loc, to_loc=data.to_loc, vendor_id=data.vendor_id,
        vehicle=data.vehicle, note=data.note,
    )
    db.session.add(entry)
    db.session.flush()

    # Auto Goods Received in vendor ledger
    if data.type == "Purchase" and data.vendor_id and data.create_grn and data.qty * data.rate > 0:
        db.session.add(VendorTxn(
            client_id=data.client_id, vendor_id=data.vendor_id, type="Goods Received",
            amount=data.qty * data.rate, date=data.date,
            by_name=data.by_name or "Site Engineer",
            note=f"{data.item} — {data.qty:g} {data.unit} @ ₹{data.rate:g}",
        ))
    db.session.commit()
    return jsonify({"id": entry.id}), 201


@api_bp.put("/entries/<eid>")
def update_entry(eid):
    data, err = load(EntryIn, request.get_json(force=True))
    if err:
        return bad(err)
    entry = db.session.get(Entry, eid)
    if not entry:
        return bad("Entry nahi mili")
    # Edit par GRN dobara nahi banta — vendor ledger alag se manage hota hai
    entry.kind = data.kind
    entry.type = data.type
    entry.date = data.date
    entry.item = data.item
    entry.qty = data.qty
    entry.unit = data.unit
    entry.rate = data.rate
    entry.from_loc = data.from_loc
    entry.to_loc = data.to_loc
    entry.vendor_id = data.vendor_id
    entry.vehicle = data.vehicle
    entry.note = data.note
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/entries/<eid>")
def del_entry(eid):
    Entry.query.filter_by(id=eid).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ── Vendors ──────────────────────────────────────────────────────────────────
@api_bp.post("/vendors")
def add_vendor():
    data, err = load(VendorIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    vendor = Vendor(
        client_id=data.client_id, name=data.name, phone=data.phone,
        contact_person=data.contact_person, gst=data.gst, address=data.address,
        category=data.category, status=data.status,
    )
    db.session.add(vendor)
    db.session.commit()
    return jsonify({"id": vendor.id}), 201


@api_bp.put("/vendors/<vid>")
def update_vendor(vid):
    data, err = load(VendorIn, request.get_json(force=True))
    if err:
        return bad(err)
    vendor = db.session.get(Vendor, vid)
    if not vendor:
        return bad("Vendor nahi mila")
    vendor.name = data.name
    vendor.phone = data.phone
    vendor.contact_person = data.contact_person
    vendor.gst = data.gst
    vendor.address = data.address
    vendor.category = data.category
    vendor.status = data.status
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/vendors/<vid>")
def del_vendor(vid):
    # Ledger bhi saath mein saaf karo (FK cascade ke bina bane purane rows ke liye)
    VendorTxn.query.filter_by(vendor_id=vid).delete()
    Vendor.query.filter_by(id=vid).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ── Vendor transactions ──────────────────────────────────────────────────────
@api_bp.post("/vendor_txns")
def add_vendor_txn():
    data, err = load(VendorTxnIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    txn = VendorTxn(
        client_id=data.client_id, vendor_id=data.vendor_id, type=data.type,
        amount=data.amount, date=data.date, by_name=data.by_name, mode=data.mode,
        reference=data.reference, note=data.note,
    )
    db.session.add(txn)
    db.session.commit()
    return jsonify({"id": txn.id}), 201


@api_bp.put("/vendor_txns/<tid>")
def update_vendor_txn(tid):
    data, err = load(VendorTxnIn, request.get_json(force=True))
    if err:
        return bad(err)
    txn = db.session.get(VendorTxn, tid)
    if not txn:
        return bad("Transaction nahi mila")
    txn.vendor_id = data.vendor_id
    txn.type = data.type
    txn.amount = data.amount
    txn.date = data.date
    txn.by_name = data.by_name
    txn.mode = data.mode
    txn.reference = data.reference
    txn.note = data.note
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/vendor_txns/<tid>")
def del_vendor_txn(tid):
    VendorTxn.query.filter_by(id=tid).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ── Expenses ─────────────────────────────────────────────────────────────────
@api_bp.post("/expenses")
def add_expense():
    data, err = load(ExpenseIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    expense = Expense(
        client_id=data.client_id, site=data.site, date=data.date,
        category=data.category, item=data.item, qty=data.qty, unit=data.unit,
        rate=data.rate, note=data.note,
    )
    db.session.add(expense)
    db.session.commit()
    return jsonify({"id": expense.id}), 201


@api_bp.put("/expenses/<xid>")
def update_expense(xid):
    data, err = load(ExpenseIn, request.get_json(force=True))
    if err:
        return bad(err)
    expense = db.session.get(Expense, xid)
    if not expense:
        return bad("Expense nahi mila")
    expense.site = data.site
    expense.date = data.date
    expense.category = data.category
    expense.item = data.item
    expense.qty = data.qty
    expense.unit = data.unit
    expense.rate = data.rate
    expense.note = data.note
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/expenses/<xid>")
def del_expense(xid):
    Expense.query.filter_by(id=xid).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ── Materials master ─────────────────────────────────────────────────────────
@api_bp.post("/materials")
def add_material():
    data, err = load(MaterialIn, request.get_json(force=True))
    if err:
        return bad(err)
    existing = Material.query.filter(
        Material.client_id == data.client_id,
        func.lower(Material.name) == data.name.lower(),
    ).first()
    if existing:
        return bad("Ye material pehle se hai")
    material = Material(
        client_id=data.client_id, name=data.name, unit=data.unit, category=data.category,
    )
    db.session.add(material)
    db.session.commit()
    return jsonify({"id": material.id}), 201


@api_bp.delete("/materials/<mid>")
def del_material(mid):
    Material.query.filter_by(id=mid).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ── Labourers ────────────────────────────────────────────────────────────────
@api_bp.post("/labourers")
def add_labourer():
    data, err = load(LabourerIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    labourer = Labourer(
        client_id=data.client_id, name=data.name, phone=data.phone,
        address=data.address, id_number=data.id_number, type=data.type,
        contractor_id=data.contractor_id, site=data.site,
        joining_date=data.joining_date, status=data.status,
    )
    db.session.add(labourer)
    db.session.commit()
    return jsonify({"id": labourer.id}), 201


@api_bp.put("/labourers/<lid>")
def update_labourer(lid):
    data, err = load(LabourerIn, request.get_json(force=True))
    if err:
        return bad(err)
    labourer = db.session.get(Labourer, lid)
    if not labourer:
        return bad("Labour nahi mila")
    labourer.name = data.name
    labourer.phone = data.phone
    labourer.address = data.address
    labourer.id_number = data.id_number
    labourer.type = data.type
    labourer.contractor_id = data.contractor_id
    labourer.site = data.site
    labourer.joining_date = data.joining_date
    labourer.status = data.status
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.post("/labourers/<lid>/status")
def set_labourer_status(lid):
    b = request.get_json(force=True)
    status = b.get("status")
    if status not in ("Active", "Inactive"):
        return bad("status galat hai")
    Labourer.query.filter_by(id=lid).update({"status": status}, synchronize_session=False)
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/labourers/<lid>")
def del_labourer(lid):
    Labourer.query.filter_by(id=lid).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ── Labour payments ──────────────────────────────────────────────────────────
@api_bp.post("/labour_payments")
def add_labour_payment():
    data, err = load(LabourPaymentIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    payment = LabourPayment(
        client_id=data.client_id, labour_id=data.labour_id, site=data.site,
        amount=data.amount, date=data.date, mode=data.mode,
        reference=data.reference, note=data.note,
    )
    db.session.add(payment)
    db.session.commit()
    return jsonify({"id": payment.id}), 201


@api_bp.put("/labour_payments/<pid>")
def update_labour_payment(pid):
    data, err = load(LabourPaymentIn, request.get_json(force=True))
    if err:
        return bad(err)
    payment = db.session.get(LabourPayment, pid)
    if not payment:
        return bad("Payment nahi mila")
    payment.labour_id = data.labour_id
    payment.site = data.site
    payment.amount = data.amount
    payment.date = data.date
    payment.mode = data.mode
    payment.reference = data.reference
    payment.note = data.note
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/labour_payments/<pid>")
def del_labour_payment(pid):
    LabourPayment.query.filter_by(id=pid).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ── Receipts (incoming payments) ─────────────────────────────────────────────
@api_bp.post("/receipts")
def add_receipt():
    data, err = load(ReceiptIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    receipt = Receipt(
        client_id=data.client_id, date=data.date, from_name=data.from_name,
        amount=data.amount, mode=data.mode, reference=data.reference,
        site=data.site, note=data.note,
    )
    db.session.add(receipt)
    db.session.commit()
    return jsonify({"id": receipt.id}), 201


@api_bp.put("/receipts/<rid>")
def update_receipt(rid):
    data, err = load(ReceiptIn, request.get_json(force=True))
    if err:
        return bad(err)
    receipt = db.session.get(Receipt, rid)
    if not receipt:
        return bad("Receipt nahi mila")
    receipt.date = data.date
    receipt.from_name = data.from_name
    receipt.amount = data.amount
    receipt.mode = data.mode
    receipt.reference = data.reference
    receipt.site = data.site
    receipt.note = data.note
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/receipts/<rid>")
def del_receipt(rid):
    Receipt.query.filter_by(id=rid).delete()
    db.session.commit()
    return jsonify({"ok": True})
