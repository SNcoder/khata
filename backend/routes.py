"""All API routes for Site Khata (SQLAlchemy ORM + Pydantic schemas).

Har route par RBAC enforce hota hai:
  - require_perm(module, action)  -> role/user permission check
  - client_allowed / allowed_site_names -> data scoping (supervisor sirf
    apni assigned client/site ka data dekh aur badal sakta hai)
Server-side enforcement hai — frontend gating sirf UX ke liye hai.
"""

from flask import Blueprint, g, jsonify, request
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
from database.auth_models import UserClient
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

from .auth import (
    allowed_client_ids,
    allowed_site_names,
    audit,
    client_allowed,
    entry_in_scope,
    has_perm,
    me_payload,
    require_perm,
    site_value_ok,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def bad(msg):
    return jsonify({"error": msg}), 400


def forbidden(msg="Is data par aapka access nahi hai"):
    return jsonify({"error": msg}), 403


def _dicts(query):
    return [row.to_dict() for row in query]


def scope_error(client_id, site_values=()):
    """Client + free-text site fields ki scoping check. Error msg ya None."""
    if not client_id or not client_allowed(client_id):
        return "Is client par aapka access nahi hai"
    names = allowed_site_names(client_id)
    for v in site_values:
        if not site_value_ok(names, v):
            return f"Site '{v}' par aapka access nahi hai"
    return None


def entry_scope_error(client_id, from_loc, to_loc):
    """Entry locations me se kam se kam ek allowed honi chahiye."""
    if not client_id or not client_allowed(client_id):
        return "Is client par aapka access nahi hai"
    names = allowed_site_names(client_id)
    if names is None:
        return None
    if not from_loc and not to_loc:
        return None
    if (from_loc and from_loc in names) or (to_loc and to_loc in names):
        return None
    return "In locations par aapka access nahi hai"


def entry_module(kind):
    return "material" if kind == "material" else "assets"


# ── Bootstrap ────────────────────────────────────────────────────────────────
@api_bp.get("/bootstrap")
def bootstrap():
    allowed = allowed_client_ids()  # None = admin (sab clients)
    cq = Client.query.order_by(Client.name)
    if allowed is None:
        clients = _dicts(cq.all())
    elif allowed:
        clients = _dicts(cq.filter(Client.id.in_(allowed)).all())
    else:
        clients = []

    # Stale/foreign client_id (e.g. purani localStorage value) ko ignore karo
    requested = request.args.get("client_id") or ""
    valid_ids = {c["id"] for c in clients}
    client_id = requested if requested in valid_ids else (clients[0]["id"] if clients else "")

    site_rows = (Site.query.options(joinedload(Site.client))
                 .join(Client).order_by(Client.name, Site.name).all())
    # Non-admin: sirf allowed clients ki (aur unme allowed) sites
    if allowed is not None:
        names_cache = {}
        visible = []
        for s in site_rows:
            if s.client_id not in allowed:
                continue
            if s.client_id not in names_cache:
                names_cache[s.client_id] = allowed_site_names(s.client_id)
            names = names_cache[s.client_id]
            if names is None or s.name in names:
                visible.append(s)
        site_rows = visible
    all_sites = _dicts(site_rows)

    data = {
        "auth": True,
        "me": me_payload(g.user),
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
    if not client_id:
        return jsonify(data)

    by_client = lambda m: m.query.filter_by(client_id=client_id)  # noqa: E731
    names = allowed_site_names(client_id)  # None = saari sites
    in_scope = lambda row: site_value_ok(names, getattr(row, "site", ""))  # noqa: E731

    # Sites hamesha bhejo (dropdowns ke liye) — scoped
    sites = by_client(Site).order_by(Site.name).all()
    if names is not None:
        sites = [s for s in sites if s.name in names]
    data["sites"] = _dicts(sites)

    # Vendors master dropdowns me bhi lagta hai (material/assets/labour forms)
    if any(has_perm(m, "view") for m in ("vendors", "material", "assets", "labour", "payments")):
        data["vendors"] = _dicts(by_client(Vendor).order_by(Vendor.name).all())

    entries = by_client(Entry).order_by(Entry.date.desc()).all()
    entries = [e for e in entries if entry_in_scope(names, e)]
    kinds = []
    if has_perm("material", "view"):
        kinds.append("material")
    if has_perm("assets", "view"):
        kinds.append("asset")
    data["entries"] = [e.to_dict() for e in entries if e.kind in kinds]

    if has_perm("vendors", "view") or has_perm("payments", "view"):
        data["vendor_txns"] = _dicts(by_client(VendorTxn).order_by(VendorTxn.date.desc()).all())
    if has_perm("expenses", "view") or has_perm("payments", "view"):
        rows = by_client(Expense).order_by(Expense.date.desc()).all()
        data["expenses"] = [x.to_dict() for x in rows if in_scope(x)]
    if has_perm("material", "view"):
        data["materials"] = _dicts(by_client(Material).order_by(Material.name).all())
    if has_perm("labour", "view") or has_perm("payments", "view"):
        rows = by_client(Labourer).order_by(Labourer.name).all()
        data["labourers"] = [l.to_dict() for l in rows if in_scope(l)]
        rows = by_client(LabourPayment).order_by(LabourPayment.date.desc()).all()
        data["labour_payments"] = [p.to_dict() for p in rows if in_scope(p)]
    if has_perm("receipts", "view"):
        rows = by_client(Receipt).order_by(Receipt.date.desc()).all()
        data["receipts"] = [r.to_dict() for r in rows if in_scope(r)]
    return jsonify(data)


# ── Clients ────────────────────────────────────────────────────────────────
@api_bp.post("/clients")
@require_perm("clients", "create")
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
    # Non-admin creator ko naya client automatically assign ho jaaye,
    # warna wo khud ka banaya client hi nahi dekh paayega.
    if not g.user.is_admin:
        db.session.add(UserClient(user_id=g.user.id, client_id=client.id))
    audit("create", "clients", f"Client '{data.name}' banaya")
    db.session.commit()
    return jsonify({"id": client.id}), 201


@api_bp.put("/clients/<cid>")
@require_perm("clients", "edit")
def update_client(cid):
    data, err = load(ClientIn, request.get_json(force=True))
    if err:
        return bad(err)
    client = db.session.get(Client, cid)
    if not client:
        return bad("Client nahi mila")
    if not client_allowed(cid):
        return forbidden()
    client.name = data.name
    client.contact_person = data.contact_person
    client.phone = data.phone
    client.email = data.email
    client.address = data.address
    client.status = data.status
    audit("edit", "clients", f"Client '{data.name}' update kiya")
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
@require_perm("clients", "delete")
def del_client(cid):
    if not client_allowed(cid):
        return forbidden()
    blocks = []
    for model, label in CLIENT_DEPENDENCY_TABLES:
        n = model.query.filter_by(client_id=cid).count()
        if n:
            blocks.append(f"{n} {label}")
    if blocks:
        return jsonify({"error": "Client delete nahi ho sakta — abhi bhi hai: " + ", ".join(blocks) +
                                  ". Pehle inhe remove karo, ya client ko Inactive kar do."}), 409
    client = db.session.get(Client, cid)
    audit("delete", "clients", f"Client '{client.name if client else cid}' delete kiya")
    Client.query.filter_by(id=cid).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ── Sites ────────────────────────────────────────────────────────────────
@api_bp.post("/sites")
@require_perm("sites", "create")
def add_site():
    data, err = load(SiteIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not client_allowed(data.client_id):
        return forbidden()
    db.session.add(Site(
        client_id=data.client_id, name=data.name,
        address=data.address, status=data.status,
    ))
    audit("create", "sites", f"Site '{data.name}' banayi")
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
@require_perm("sites", "edit")
def update_site(sid):
    data, err = load(SiteIn, request.get_json(force=True))
    if err:
        return bad(err)
    site = db.session.get(Site, sid)
    if not site:
        return bad("Site nahi mila")
    err = scope_error(site.client_id, [site.name])
    if err:
        return forbidden(err)
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
    audit("edit", "sites", f"Site '{old_name}' update ki" + (f" (naya naam: {new_name})" if new_name != old_name else ""))
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/sites/<sid>")
@require_perm("sites", "delete")
def del_site(sid):
    site = db.session.get(Site, sid)
    if not site:
        return bad("Site nahi mila")
    err = scope_error(site.client_id, [site.name])
    if err:
        return forbidden(err)
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
    audit("delete", "sites", f"Site '{name}' delete ki")
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
    module = entry_module(data.kind)
    if not has_perm(module, "create"):
        return forbidden(f"Permission nahi hai ({module}: create)")
    err = entry_scope_error(data.client_id, data.from_loc, data.to_loc)
    if err:
        return forbidden(err)
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
    audit("create", module, f"{data.type}: {data.item} — {data.qty:g} {data.unit}")
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
    module = entry_module(entry.kind)
    if not has_perm(module, "edit"):
        return forbidden(f"Permission nahi hai ({module}: edit)")
    # Purani aur nayi dono locations scope me honi chahiye
    err = (entry_scope_error(entry.client_id, entry.from_loc, entry.to_loc)
           or entry_scope_error(entry.client_id, data.from_loc, data.to_loc))
    if err:
        return forbidden(err)
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
    audit("edit", module, f"{data.type}: {data.item} entry update ki")
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/entries/<eid>")
def del_entry(eid):
    entry = db.session.get(Entry, eid)
    if not entry:
        return jsonify({"ok": True})
    module = entry_module(entry.kind)
    if not has_perm(module, "delete"):
        return forbidden(f"Permission nahi hai ({module}: delete)")
    err = entry_scope_error(entry.client_id, entry.from_loc, entry.to_loc)
    if err:
        return forbidden(err)
    audit("delete", module, f"{entry.type}: {entry.item} entry delete ki")
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"ok": True})


# ── Vendors ──────────────────────────────────────────────────────────────────
@api_bp.post("/vendors")
@require_perm("vendors", "create")
def add_vendor():
    data, err = load(VendorIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    if not client_allowed(data.client_id):
        return forbidden()
    vendor = Vendor(
        client_id=data.client_id, name=data.name, phone=data.phone,
        contact_person=data.contact_person, gst=data.gst, address=data.address,
        category=data.category, status=data.status,
    )
    db.session.add(vendor)
    audit("create", "vendors", f"Vendor '{data.name}' banaya")
    db.session.commit()
    return jsonify({"id": vendor.id}), 201


@api_bp.put("/vendors/<vid>")
@require_perm("vendors", "edit")
def update_vendor(vid):
    data, err = load(VendorIn, request.get_json(force=True))
    if err:
        return bad(err)
    vendor = db.session.get(Vendor, vid)
    if not vendor:
        return bad("Vendor nahi mila")
    if not client_allowed(vendor.client_id):
        return forbidden()
    vendor.name = data.name
    vendor.phone = data.phone
    vendor.contact_person = data.contact_person
    vendor.gst = data.gst
    vendor.address = data.address
    vendor.category = data.category
    vendor.status = data.status
    audit("edit", "vendors", f"Vendor '{data.name}' update kiya")
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/vendors/<vid>")
@require_perm("vendors", "delete")
def del_vendor(vid):
    vendor = db.session.get(Vendor, vid)
    if not vendor:
        return jsonify({"ok": True})
    if not client_allowed(vendor.client_id):
        return forbidden()
    audit("delete", "vendors", f"Vendor '{vendor.name}' + ledger delete kiya")
    # Ledger bhi saath mein saaf karo (FK cascade ke bina bane purane rows ke liye)
    VendorTxn.query.filter_by(vendor_id=vid).delete()
    Vendor.query.filter_by(id=vid).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ── Vendor transactions ──────────────────────────────────────────────────────
@api_bp.post("/vendor_txns")
@require_perm("vendors", "create")
def add_vendor_txn():
    data, err = load(VendorTxnIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    if not client_allowed(data.client_id):
        return forbidden()
    txn = VendorTxn(
        client_id=data.client_id, vendor_id=data.vendor_id, type=data.type,
        amount=data.amount, date=data.date, by_name=data.by_name, mode=data.mode,
        reference=data.reference, note=data.note,
    )
    db.session.add(txn)
    audit("create", "vendors", f"Vendor txn {data.type} ₹{data.amount:g}")
    db.session.commit()
    return jsonify({"id": txn.id}), 201


@api_bp.put("/vendor_txns/<tid>")
@require_perm("vendors", "edit")
def update_vendor_txn(tid):
    data, err = load(VendorTxnIn, request.get_json(force=True))
    if err:
        return bad(err)
    txn = db.session.get(VendorTxn, tid)
    if not txn:
        return bad("Transaction nahi mila")
    if not client_allowed(txn.client_id):
        return forbidden()
    txn.vendor_id = data.vendor_id
    txn.type = data.type
    txn.amount = data.amount
    txn.date = data.date
    txn.by_name = data.by_name
    txn.mode = data.mode
    txn.reference = data.reference
    txn.note = data.note
    audit("edit", "vendors", f"Vendor txn update ki ({data.type} ₹{data.amount:g})")
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/vendor_txns/<tid>")
@require_perm("vendors", "delete")
def del_vendor_txn(tid):
    txn = db.session.get(VendorTxn, tid)
    if not txn:
        return jsonify({"ok": True})
    if not client_allowed(txn.client_id):
        return forbidden()
    audit("delete", "vendors", f"Vendor txn delete ki ({txn.type} ₹{txn.amount:g})")
    db.session.delete(txn)
    db.session.commit()
    return jsonify({"ok": True})


# ── Expenses ─────────────────────────────────────────────────────────────────
@api_bp.post("/expenses")
@require_perm("expenses", "create")
def add_expense():
    data, err = load(ExpenseIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    err = scope_error(data.client_id, [data.site])
    if err:
        return forbidden(err)
    expense = Expense(
        client_id=data.client_id, site=data.site, date=data.date,
        category=data.category, item=data.item, qty=data.qty, unit=data.unit,
        rate=data.rate, note=data.note,
    )
    db.session.add(expense)
    audit("create", "expenses", f"{data.category}: {data.item} ({data.site})")
    db.session.commit()
    return jsonify({"id": expense.id}), 201


@api_bp.put("/expenses/<xid>")
@require_perm("expenses", "edit")
def update_expense(xid):
    data, err = load(ExpenseIn, request.get_json(force=True))
    if err:
        return bad(err)
    expense = db.session.get(Expense, xid)
    if not expense:
        return bad("Expense nahi mila")
    err = scope_error(expense.client_id, [expense.site, data.site])
    if err:
        return forbidden(err)
    expense.site = data.site
    expense.date = data.date
    expense.category = data.category
    expense.item = data.item
    expense.qty = data.qty
    expense.unit = data.unit
    expense.rate = data.rate
    expense.note = data.note
    audit("edit", "expenses", f"{data.category}: {data.item} update kiya")
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/expenses/<xid>")
@require_perm("expenses", "delete")
def del_expense(xid):
    expense = db.session.get(Expense, xid)
    if not expense:
        return jsonify({"ok": True})
    err = scope_error(expense.client_id, [expense.site])
    if err:
        return forbidden(err)
    audit("delete", "expenses", f"{expense.category}: {expense.item} delete kiya")
    db.session.delete(expense)
    db.session.commit()
    return jsonify({"ok": True})


# ── Materials master ─────────────────────────────────────────────────────────
@api_bp.post("/materials")
@require_perm("material", "create")
def add_material():
    data, err = load(MaterialIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not client_allowed(data.client_id):
        return forbidden()
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
    audit("create", "material", f"Master material '{data.name}' add kiya")
    db.session.commit()
    return jsonify({"id": material.id}), 201


@api_bp.delete("/materials/<mid>")
@require_perm("material", "delete")
def del_material(mid):
    material = db.session.get(Material, mid)
    if not material:
        return jsonify({"ok": True})
    if not client_allowed(material.client_id):
        return forbidden()
    audit("delete", "material", f"Master material '{material.name}' remove kiya")
    db.session.delete(material)
    db.session.commit()
    return jsonify({"ok": True})


# ── Labourers ────────────────────────────────────────────────────────────────
@api_bp.post("/labourers")
@require_perm("labour", "create")
def add_labourer():
    data, err = load(LabourerIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    err = scope_error(data.client_id, [data.site])
    if err:
        return forbidden(err)
    labourer = Labourer(
        client_id=data.client_id, name=data.name, phone=data.phone,
        address=data.address, id_number=data.id_number, type=data.type,
        contractor_id=data.contractor_id, site=data.site,
        joining_date=data.joining_date, status=data.status,
    )
    db.session.add(labourer)
    audit("create", "labour", f"Labour '{data.name}' add kiya")
    db.session.commit()
    return jsonify({"id": labourer.id}), 201


@api_bp.put("/labourers/<lid>")
@require_perm("labour", "edit")
def update_labourer(lid):
    data, err = load(LabourerIn, request.get_json(force=True))
    if err:
        return bad(err)
    labourer = db.session.get(Labourer, lid)
    if not labourer:
        return bad("Labour nahi mila")
    err = scope_error(labourer.client_id, [labourer.site, data.site])
    if err:
        return forbidden(err)
    labourer.name = data.name
    labourer.phone = data.phone
    labourer.address = data.address
    labourer.id_number = data.id_number
    labourer.type = data.type
    labourer.contractor_id = data.contractor_id
    labourer.site = data.site
    labourer.joining_date = data.joining_date
    labourer.status = data.status
    audit("edit", "labour", f"Labour '{data.name}' update kiya")
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.post("/labourers/<lid>/status")
@require_perm("labour", "edit")
def set_labourer_status(lid):
    b = request.get_json(force=True)
    status = b.get("status")
    if status not in ("Active", "Inactive"):
        return bad("status galat hai")
    labourer = db.session.get(Labourer, lid)
    if not labourer:
        return bad("Labour nahi mila")
    err = scope_error(labourer.client_id, [labourer.site])
    if err:
        return forbidden(err)
    labourer.status = status
    audit("edit", "labour", f"Labour '{labourer.name}' ko {status} kiya")
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/labourers/<lid>")
@require_perm("labour", "delete")
def del_labourer(lid):
    labourer = db.session.get(Labourer, lid)
    if not labourer:
        return jsonify({"ok": True})
    err = scope_error(labourer.client_id, [labourer.site])
    if err:
        return forbidden(err)
    audit("delete", "labour", f"Labour '{labourer.name}' delete kiya")
    db.session.delete(labourer)
    db.session.commit()
    return jsonify({"ok": True})


# ── Labour payments ──────────────────────────────────────────────────────────
@api_bp.post("/labour_payments")
@require_perm("labour", "create")
def add_labour_payment():
    data, err = load(LabourPaymentIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    err = scope_error(data.client_id, [data.site])
    if err:
        return forbidden(err)
    payment = LabourPayment(
        client_id=data.client_id, labour_id=data.labour_id, site=data.site,
        amount=data.amount, date=data.date, mode=data.mode,
        reference=data.reference, note=data.note,
    )
    db.session.add(payment)
    audit("create", "labour", f"Labour payment ₹{data.amount:g} record ki")
    db.session.commit()
    return jsonify({"id": payment.id}), 201


@api_bp.put("/labour_payments/<pid>")
@require_perm("labour", "edit")
def update_labour_payment(pid):
    data, err = load(LabourPaymentIn, request.get_json(force=True))
    if err:
        return bad(err)
    payment = db.session.get(LabourPayment, pid)
    if not payment:
        return bad("Payment nahi mila")
    err = scope_error(payment.client_id, [payment.site, data.site])
    if err:
        return forbidden(err)
    payment.labour_id = data.labour_id
    payment.site = data.site
    payment.amount = data.amount
    payment.date = data.date
    payment.mode = data.mode
    payment.reference = data.reference
    payment.note = data.note
    audit("edit", "labour", f"Labour payment update ki (₹{data.amount:g})")
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/labour_payments/<pid>")
@require_perm("labour", "delete")
def del_labour_payment(pid):
    payment = db.session.get(LabourPayment, pid)
    if not payment:
        return jsonify({"ok": True})
    err = scope_error(payment.client_id, [payment.site])
    if err:
        return forbidden(err)
    audit("delete", "labour", f"Labour payment delete ki (₹{payment.amount:g})")
    db.session.delete(payment)
    db.session.commit()
    return jsonify({"ok": True})


# ── Receipts (incoming payments) ─────────────────────────────────────────────
@api_bp.post("/receipts")
@require_perm("receipts", "create")
def add_receipt():
    data, err = load(ReceiptIn, request.get_json(force=True))
    if err:
        return bad(err)
    if not data.client_id:
        return bad("client_id zaroori hai")
    err = scope_error(data.client_id, [data.site])
    if err:
        return forbidden(err)
    receipt = Receipt(
        client_id=data.client_id, date=data.date, from_name=data.from_name,
        amount=data.amount, mode=data.mode, reference=data.reference,
        site=data.site, note=data.note,
    )
    db.session.add(receipt)
    audit("create", "receipts", f"Receipt ₹{data.amount:g} from '{data.from_name}'")
    db.session.commit()
    return jsonify({"id": receipt.id}), 201


@api_bp.put("/receipts/<rid>")
@require_perm("receipts", "edit")
def update_receipt(rid):
    data, err = load(ReceiptIn, request.get_json(force=True))
    if err:
        return bad(err)
    receipt = db.session.get(Receipt, rid)
    if not receipt:
        return bad("Receipt nahi mila")
    err = scope_error(receipt.client_id, [receipt.site, data.site])
    if err:
        return forbidden(err)
    receipt.date = data.date
    receipt.from_name = data.from_name
    receipt.amount = data.amount
    receipt.mode = data.mode
    receipt.reference = data.reference
    receipt.site = data.site
    receipt.note = data.note
    audit("edit", "receipts", f"Receipt update ki (₹{data.amount:g})")
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.delete("/receipts/<rid>")
@require_perm("receipts", "delete")
def del_receipt(rid):
    receipt = db.session.get(Receipt, rid)
    if not receipt:
        return jsonify({"ok": True})
    err = scope_error(receipt.client_id, [receipt.site])
    if err:
        return forbidden(err)
    audit("delete", "receipts", f"Receipt delete ki (₹{receipt.amount:g})")
    db.session.delete(receipt)
    db.session.commit()
    return jsonify({"ok": True})
