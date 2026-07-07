"""All API routes for Site Khata."""

import uuid

from flask import Blueprint, jsonify, request

from database import commit, qry, rows

api_bp = Blueprint("api", __name__, url_prefix="/api")


def new_id():
    return uuid.uuid4().hex


# ── Bootstrap ────────────────────────────────────────────────────────────────
@api_bp.get("/bootstrap")
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
        "materials": [],
        "labourers": [],
        "labour_payments": [],
        "receipts": [],
    }
    if client_id:
        data["sites"]           = rows(qry("SELECT * FROM sites WHERE client_id=? ORDER BY name", (client_id,)))
        data["entries"]         = rows(qry("SELECT * FROM entries WHERE client_id=? ORDER BY date DESC", (client_id,)))
        data["vendors"]         = rows(qry("SELECT * FROM vendors WHERE client_id=? ORDER BY name", (client_id,)))
        data["vendor_txns"]     = rows(qry("SELECT * FROM vendor_txns WHERE client_id=? ORDER BY date DESC", (client_id,)))
        data["expenses"]        = rows(qry("SELECT * FROM expenses WHERE client_id=? ORDER BY date DESC", (client_id,)))
        data["materials"]       = rows(qry("SELECT * FROM materials WHERE client_id=? ORDER BY name", (client_id,)))
        data["labourers"]       = rows(qry("SELECT * FROM labourers WHERE client_id=? ORDER BY name", (client_id,)))
        data["labour_payments"] = rows(qry("SELECT * FROM labour_payments WHERE client_id=? ORDER BY date DESC", (client_id,)))
        data["receipts"]        = rows(qry("SELECT * FROM receipts WHERE client_id=? ORDER BY date DESC", (client_id,)))
    return jsonify(data)


# ── Clients & Sites ──────────────────────────────────────────────────────────
@api_bp.post("/clients")
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


@api_bp.post("/sites")
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
@api_bp.post("/entries")
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
           (id,client_id,kind,type,date,item,qty,unit,rate,from_loc,to_loc,vendor_id,vehicle,note)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (eid, b["client_id"], b["kind"], b["type"], b["date"],
         b["item"].strip(), qty, b["unit"], rate,
         b.get("from_loc", ""), b.get("to_loc", ""),
         b.get("vendor_id", ""), b.get("vehicle", ""), b.get("note", "")),
    )

    # Auto Goods Received in vendor ledger
    if b["type"] == "Purchase" and b.get("vendor_id") and b.get("create_grn") and qty * rate > 0:
        qry(
            """INSERT INTO vendor_txns
               (id,client_id,vendor_id,type,amount,date,by_name,note)
               VALUES (?,?,?,?,?,?,?,?)""",
            (new_id(), b["client_id"], b["vendor_id"], "Goods Received",
             qty * rate, b["date"], b.get("by_name", "Site Engineer"),
             f"{b['item'].strip()} — {qty:g} {b['unit']} @ ₹{rate:g}"),
        )
    commit()
    return jsonify({"id": eid}), 201


@api_bp.delete("/entries/<eid>")
def del_entry(eid):
    qry("DELETE FROM entries WHERE id=?", (eid,))
    commit()
    return jsonify({"ok": True})


# ── Vendors ──────────────────────────────────────────────────────────────────
@api_bp.post("/vendors")
def add_vendor():
    b = request.get_json(force=True)
    name = (b.get("name") or "").strip()
    if not name or not b.get("client_id"):
        return jsonify({"error": "Vendor ka naam zaroori hai"}), 400
    status = b.get("status") or "Active"
    if status not in ("Active", "Inactive"):
        return jsonify({"error": "status galat hai"}), 400
    vid = new_id()
    qry(
        """INSERT INTO vendors
           (id,client_id,name,phone,contact_person,gst,address,category,status)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (vid, b["client_id"], name, b.get("phone", ""),
         b.get("contact_person", ""), b.get("gst", ""),
         b.get("address", ""), b.get("category", ""), status),
    )
    commit()
    return jsonify({"id": vid}), 201


@api_bp.post("/vendor_txns")
def add_vendor_txn():
    b = request.get_json(force=True)
    if b.get("type") not in ("Goods Received", "Payment"):
        return jsonify({"error": "type galat hai"}), 400
    try:
        amount = float(b.get("amount") or 0)
    except ValueError:
        return jsonify({"error": "Amount number hona chahiye"}), 400
    if amount <= 0 or not b.get("vendor_id") or not b.get("client_id"):
        return jsonify({"error": "Vendor, client aur amount zaroori hain"}), 400
    tid = new_id()
    qry(
        """INSERT INTO vendor_txns
           (id,client_id,vendor_id,type,amount,date,by_name,mode,reference,note)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (tid, b["client_id"], b["vendor_id"], b["type"], amount,
         b.get("date", ""), b.get("by_name", ""),
         b.get("mode", ""), b.get("reference", ""), b.get("note", "")),
    )
    commit()
    return jsonify({"id": tid}), 201


@api_bp.delete("/vendor_txns/<tid>")
def del_vendor_txn(tid):
    qry("DELETE FROM vendor_txns WHERE id=?", (tid,))
    commit()
    return jsonify({"ok": True})


# ── Expenses ─────────────────────────────────────────────────────────────────
@api_bp.post("/expenses")
def add_expense():
    b = request.get_json(force=True)
    required = ["client_id", "site", "date", "category", "item", "qty", "unit"]
    if any(not b.get(k) for k in required):
        return jsonify({"error": "Zaroori fields missing hain"}), 400
    try:
        qty  = float(b["qty"])
        rate = float(b.get("rate") or 0)
    except ValueError:
        return jsonify({"error": "Qty/Rate number hone chahiye"}), 400
    if qty <= 0:
        return jsonify({"error": "Qty 0 se zyada honi chahiye"}), 400
    xid = new_id()
    qry(
        """INSERT INTO expenses
           (id,client_id,site,date,category,item,qty,unit,rate,note)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (xid, b["client_id"], b["site"], b["date"], b["category"],
         b["item"].strip(), qty, b["unit"], rate, b.get("note", "")),
    )
    commit()
    return jsonify({"id": xid}), 201


@api_bp.delete("/expenses/<xid>")
def del_expense(xid):
    qry("DELETE FROM expenses WHERE id=?", (xid,))
    commit()
    return jsonify({"ok": True})


# ── Materials master ─────────────────────────────────────────────────────────
@api_bp.post("/materials")
def add_material():
    b = request.get_json(force=True)
    name = (b.get("name") or "").strip()
    if not name or not b.get("client_id"):
        return jsonify({"error": "Material ka naam zaroori hai"}), 400
    existing = rows(qry(
        "SELECT id FROM materials WHERE client_id=? AND LOWER(name)=LOWER(?)",
        (b["client_id"], name)))
    if existing:
        return jsonify({"error": "Ye material pehle se hai"}), 400
    mid = new_id()
    qry("INSERT INTO materials (id,client_id,name,unit,category) VALUES (?,?,?,?,?)",
        (mid, b["client_id"], name, b.get("unit", ""), b.get("category", "")))
    commit()
    return jsonify({"id": mid}), 201


@api_bp.delete("/materials/<mid>")
def del_material(mid):
    qry("DELETE FROM materials WHERE id=?", (mid,))
    commit()
    return jsonify({"ok": True})


# ── Labourers ────────────────────────────────────────────────────────────────
LABOUR_TYPES = (
    "General Labour", "Contractor Labour", "Steel Binding Labour", "Mason",
    "Carpenter", "Painter", "Electrician", "Plumber", "Tile Worker",
    "Helper", "Other",
)


@api_bp.post("/labourers")
def add_labourer():
    b = request.get_json(force=True)
    name = (b.get("name") or "").strip()
    if not name or not b.get("client_id"):
        return jsonify({"error": "Labour ka naam zaroori hai"}), 400
    ltype = b.get("type") or "General Labour"
    if ltype not in LABOUR_TYPES:
        return jsonify({"error": "Labour type galat hai"}), 400
    status = b.get("status") or "Active"
    if status not in ("Active", "Inactive"):
        return jsonify({"error": "status galat hai"}), 400
    lid = new_id()
    qry(
        """INSERT INTO labourers
           (id,client_id,name,phone,address,id_number,type,contractor_id,site,joining_date,status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (lid, b["client_id"], name, b.get("phone", ""), b.get("address", ""),
         b.get("id_number", ""), ltype, b.get("contractor_id", ""),
         b.get("site", ""), b.get("joining_date", ""), status),
    )
    commit()
    return jsonify({"id": lid}), 201


@api_bp.post("/labourers/<lid>/status")
def set_labourer_status(lid):
    b = request.get_json(force=True)
    status = b.get("status")
    if status not in ("Active", "Inactive"):
        return jsonify({"error": "status galat hai"}), 400
    qry("UPDATE labourers SET status=? WHERE id=?", (status, lid))
    commit()
    return jsonify({"ok": True})


@api_bp.delete("/labourers/<lid>")
def del_labourer(lid):
    qry("DELETE FROM labourers WHERE id=?", (lid,))
    commit()
    return jsonify({"ok": True})


# ── Labour payments ──────────────────────────────────────────────────────────
PAYMENT_MODES = ("Cash", "Online", "Bank Transfer", "UPI", "Cheque")


@api_bp.post("/labour_payments")
def add_labour_payment():
    b = request.get_json(force=True)
    try:
        amount = float(b.get("amount") or 0)
    except ValueError:
        return jsonify({"error": "Amount number hona chahiye"}), 400
    if amount <= 0 or not b.get("labour_id") or not b.get("client_id") or not b.get("date"):
        return jsonify({"error": "Labour, date aur amount zaroori hain"}), 400
    mode = b.get("mode") or "Cash"
    if mode not in PAYMENT_MODES:
        return jsonify({"error": "Payment mode galat hai"}), 400
    pid = new_id()
    qry(
        """INSERT INTO labour_payments
           (id,client_id,labour_id,site,amount,date,mode,reference,note)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (pid, b["client_id"], b["labour_id"], b.get("site", ""),
         amount, b["date"], mode, b.get("reference", ""), b.get("note", "")),
    )
    commit()
    return jsonify({"id": pid}), 201


@api_bp.delete("/labour_payments/<pid>")
def del_labour_payment(pid):
    qry("DELETE FROM labour_payments WHERE id=?", (pid,))
    commit()
    return jsonify({"ok": True})


# ── Receipts (incoming payments) ─────────────────────────────────────────────
@api_bp.post("/receipts")
def add_receipt():
    b = request.get_json(force=True)
    from_name = (b.get("from_name") or "").strip()
    try:
        amount = float(b.get("amount") or 0)
    except ValueError:
        return jsonify({"error": "Amount number hona chahiye"}), 400
    if amount <= 0 or not from_name or not b.get("client_id") or not b.get("date"):
        return jsonify({"error": "Received from, date aur amount zaroori hain"}), 400
    mode = b.get("mode") or "Cash"
    if mode not in PAYMENT_MODES:
        return jsonify({"error": "Payment mode galat hai"}), 400
    rid = new_id()
    qry(
        """INSERT INTO receipts
           (id,client_id,date,from_name,amount,mode,reference,site,note)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (rid, b["client_id"], b["date"], from_name, amount, mode,
         b.get("reference", ""), b.get("site", ""), b.get("note", "")),
    )
    commit()
    return jsonify({"id": rid}), 201


@api_bp.delete("/receipts/<rid>")
def del_receipt(rid):
    qry("DELETE FROM receipts WHERE id=?", (rid,))
    commit()
    return jsonify({"ok": True})
