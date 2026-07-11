"""
Admin Panel API — sirf admin role ke liye.

User management, roles & permissions matrix, client/site assignment,
per-user overrides aur audit log. Sab kuch runtime par change hota hai —
code change ki zaroorat nahi.
"""

from flask import Blueprint, g, jsonify, request

from database import Client, Site, db
from database.auth_models import (
    ACTIONS,
    MODULE_KEYS,
    MODULES,
    AuditLog,
    Role,
    RolePermission,
    User,
    UserClient,
    UserPermission,
    UserSite,
    invite_expiry_ts,
    new_invite_token,
)

from .auth import admin_required, audit
from .mailer import send_invite_email

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def bad(msg, code=400):
    return jsonify({"error": msg}), code


def active_admin_count(exclude_user_id=None):
    q = (User.query.join(Role, User.role_id == Role.id)
         .filter(Role.is_admin.is_(True), User.status == "Active"))
    if exclude_user_id:
        q = q.filter(User.id != exclude_user_id)
    return q.count()


# ── Panel bootstrap ───────────────────────────────────────────────────────────
@admin_bp.get("/bootstrap")
@admin_required
def admin_bootstrap():
    users = [u.to_dict() for u in User.query.order_by(User.email).all()]
    roles = [r.to_dict() for r in Role.query.order_by(Role.is_admin.desc(), Role.name).all()]
    clients = [c.to_dict() for c in Client.query.order_by(Client.name).all()]
    sites = [s.to_dict() for s in Site.query.order_by(Site.name).all()]
    return jsonify({
        "users": users,
        "roles": roles,
        "clients": clients,
        "sites": sites,
        "modules": [{"key": k, "label": l} for k, l in MODULES],
        "actions": ACTIONS,
    })


# ── Users ─────────────────────────────────────────────────────────────────────
def _valid_email(email):
    email = (email or "").strip()
    return "@" in email and "." in email.split("@")[-1] and len(email) >= 5


def _user_common_errors(body, user_id=None):
    email = (body.get("email") or "").strip().lower()
    if not _valid_email(email):
        return "Valid email zaroori hai"
    q = User.query.filter(db.func.lower(User.email) == email)
    if user_id:
        q = q.filter(User.id != user_id)
    if q.first():
        return "Ye email pehle se registered hai"
    role = db.session.get(Role, body.get("role_id") or "")
    if not role:
        return "Role select karo"
    if (body.get("status") or "Active") not in ("Active", "Inactive"):
        return "status galat hai"
    return None


@admin_bp.post("/users")
@admin_required
def add_user():
    """Naya user banane par password admin nahi deta — invite email jaati hai,
    user khud apna password set karke account activate karta hai."""
    body = request.get_json(force=True) or {}
    err = _user_common_errors(body)
    if err:
        return bad(err)
    user = User(
        email=body["email"].strip().lower(),
        full_name=body.get("full_name", ""),
        phone=body.get("phone", ""),
        role_id=body["role_id"],
        status="Pending",
    )
    user.start_invite()
    db.session.add(user)
    db.session.flush()
    sent, link = send_invite_email(user.email, user.full_name, user.invite_token, is_reset=False)
    audit("create", "users",
          f"User '{user.email}' banaya (role: {user.role.name}) — "
          f"invite {'email par bheja' if sent else 'email bhejne me fail hui, link manually do'}")
    db.session.commit()
    return jsonify({"id": user.id, "email_sent": sent,
                     "invite_link": None if sent else link}), 201


@admin_bp.put("/users/<uid>")
@admin_required
def update_user(uid):
    """Password yahan se set nahi hota — sirf profile/role/status."""
    user = db.session.get(User, uid)
    if not user:
        return bad("User nahi mila")
    body = request.get_json(force=True) or {}
    err = _user_common_errors(body, user_id=uid)
    if err:
        return bad(err)

    new_role = db.session.get(Role, body["role_id"])
    new_status = body.get("status") or "Active"
    if new_status == "Active" and not user.password_hash:
        return bad("Ye user abhi apna password set nahi kar paaya — 'Resend Invite' use karo, "
                    "manually Active nahi kar sakte")

    # Aakhri active admin ko demote/deactivate mat hone do
    losing_admin = user.is_admin and (not new_role.is_admin or new_status != "Active")
    if losing_admin and active_admin_count(exclude_user_id=uid) == 0:
        return bad("Ye aakhri active admin hai — isse demote/deactivate nahi kar sakte")

    user.email = body["email"].strip().lower()
    user.full_name = body.get("full_name", "")
    user.phone = body.get("phone", "")
    user.role_id = body["role_id"]
    user.status = new_status
    audit("edit", "users", f"User '{user.email}' update kiya")
    db.session.commit()
    return jsonify({"ok": True})


@admin_bp.post("/users/<uid>/status")
@admin_required
def set_user_status(uid):
    user = db.session.get(User, uid)
    if not user:
        return bad("User nahi mila")
    status = (request.get_json(force=True) or {}).get("status")
    if status not in ("Active", "Inactive"):
        return bad("status galat hai")
    if status == "Active" and not user.password_hash:
        return bad("Ye user abhi apna password set nahi kar paaya — 'Resend Invite' use karo")
    if user.id == g.user.id and status == "Inactive":
        return bad("Khud ko deactivate nahi kar sakte")
    if user.is_admin and status == "Inactive" and active_admin_count(exclude_user_id=uid) == 0:
        return bad("Ye aakhri active admin hai — deactivate nahi kar sakte")
    user.status = status
    audit("edit", "users", f"User '{user.email}' ko {status} kiya")
    db.session.commit()
    return jsonify({"ok": True})


@admin_bp.post("/users/<uid>/send_reset")
@admin_required
def send_reset(uid):
    """Naya invite/reset link generate karke email karta hai.
    Pending user ko dobara invite, Active user ko forced password reset
    (jab tak wo naya password set nahi karta, login nahi kar payega)."""
    user = db.session.get(User, uid)
    if not user:
        return bad("User nahi mila")
    if user.status == "Inactive":
        return bad("Deactivated user ko reset link nahi bhej sakte — pehle Activate karo")
    is_reset = user.status == "Active" and bool(user.password_hash)
    user.start_invite()
    if user.status == "Active":
        user.status = "Pending"  # naya password set hone tak login nahi hoga
    db.session.commit()
    sent, link = send_invite_email(user.email, user.full_name, user.invite_token, is_reset=is_reset)
    audit("edit", "users",
          f"{'Password reset' if is_reset else 'Invite'} email {user.email} ko " +
          ("bheja" if sent else "bhejne me fail hui — link manually do"))
    db.session.commit()
    return jsonify({"ok": True, "email_sent": sent, "invite_link": None if sent else link})


@admin_bp.delete("/users/<uid>")
@admin_required
def delete_user(uid):
    user = db.session.get(User, uid)
    if not user:
        return bad("User nahi mila")
    if user.id == g.user.id:
        return bad("Khud ko delete nahi kar sakte")
    if user.is_admin and active_admin_count(exclude_user_id=uid) == 0:
        return bad("Ye aakhri active admin hai — delete nahi kar sakte")
    audit("delete", "users", f"User '{user.email}' delete kiya")
    db.session.delete(user)
    db.session.commit()
    return jsonify({"ok": True})


# ── Access: client/site assignment + per-user overrides ──────────────────────
@admin_bp.put("/users/<uid>/access")
@admin_required
def set_user_access(uid):
    """Ek hi call me: client assignments, site assignments aur module overrides.

    Body: {
      client_ids: [...],                     # poore client (saari sites)
      site_ids: [...],                       # specific sites
      overrides: {module: {action: true|false|null}}   # null = role se inherit
    }
    """
    user = db.session.get(User, uid)
    if not user:
        return bad("User nahi mila")
    body = request.get_json(force=True) or {}

    client_ids = body.get("client_ids", [])
    site_ids = body.get("site_ids", [])
    if not isinstance(client_ids, list) or not isinstance(site_ids, list):
        return bad("client_ids/site_ids list hone chahiye")

    valid_clients = {c.id for c in Client.query.all()}
    valid_sites = {s.id for s in Site.query.all()}
    client_ids = [c for c in client_ids if c in valid_clients]
    site_ids = [s for s in site_ids if s in valid_sites]

    UserClient.query.filter_by(user_id=uid).delete()
    UserSite.query.filter_by(user_id=uid).delete()
    for cid in set(client_ids):
        db.session.add(UserClient(user_id=uid, client_id=cid))
    for sid in set(site_ids):
        db.session.add(UserSite(user_id=uid, site_id=sid))

    overrides = body.get("overrides", {})
    if not isinstance(overrides, dict):
        return bad("overrides object hona chahiye")
    UserPermission.query.filter_by(user_id=uid).delete()
    for module, acts in overrides.items():
        if module not in MODULE_KEYS or not isinstance(acts, dict):
            continue
        vals = {}
        for a in ACTIONS:
            v = acts.get(a, None)
            vals[f"can_{a}"] = None if v is None else bool(v)
        # Saare None ho to row banane ki zaroorat nahi (pure inherit)
        if any(v is not None for v in vals.values()):
            db.session.add(UserPermission(user_id=uid, module=module, **vals))

    audit("edit", "users",
          f"User '{user.email}' ka access update kiya "
          f"({len(set(client_ids))} client, {len(set(site_ids))} site assignments)")
    db.session.commit()
    return jsonify({"ok": True})


# ── Roles & permissions ───────────────────────────────────────────────────────
@admin_bp.post("/roles")
@admin_required
def add_role():
    body = request.get_json(force=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return bad("Role ka naam zaroori hai")
    if Role.query.filter(db.func.lower(Role.name) == name.lower()).first():
        return bad("Ye role pehle se hai")
    role = Role(name=name, description=body.get("description", ""))
    db.session.add(role)
    db.session.flush()
    audit("create", "roles", f"Role '{name}' banaya")
    db.session.commit()
    return jsonify({"id": role.id}), 201


@admin_bp.put("/roles/<rid>")
@admin_required
def update_role(rid):
    role = db.session.get(Role, rid)
    if not role:
        return bad("Role nahi mila")
    body = request.get_json(force=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return bad("Role ka naam zaroori hai")
    if role.is_system and name != role.name:
        return bad("System role ka naam nahi badal sakte")
    if Role.query.filter(db.func.lower(Role.name) == name.lower(), Role.id != rid).first():
        return bad("Ye role pehle se hai")
    role.name = name
    role.description = body.get("description", "")
    audit("edit", "roles", f"Role '{role.name}' update kiya")
    db.session.commit()
    return jsonify({"ok": True})


@admin_bp.put("/roles/<rid>/permissions")
@admin_required
def set_role_permissions(rid):
    """Body: {module: {view: bool, create: bool, ...}} — poora matrix replace."""
    role = db.session.get(Role, rid)
    if not role:
        return bad("Role nahi mila")
    if role.is_admin:
        return bad("Admin role ke paas hamesha full access hota hai — edit nahi hota")
    matrix = request.get_json(force=True) or {}
    if not isinstance(matrix, dict):
        return bad("Permission matrix object hona chahiye")

    RolePermission.query.filter_by(role_id=rid).delete()
    for module, acts in matrix.items():
        if module not in MODULE_KEYS or not isinstance(acts, dict):
            continue
        vals = {f"can_{a}": bool(acts.get(a)) for a in ACTIONS}
        if any(vals.values()):
            db.session.add(RolePermission(role_id=rid, module=module, **vals))

    audit("edit", "roles", f"Role '{role.name}' ki permissions update ki")
    db.session.commit()
    return jsonify({"ok": True})


@admin_bp.delete("/roles/<rid>")
@admin_required
def delete_role(rid):
    role = db.session.get(Role, rid)
    if not role:
        return bad("Role nahi mila")
    if role.is_system:
        return bad("System role delete nahi ho sakta")
    n = User.query.filter_by(role_id=rid).count()
    if n:
        return bad(f"Is role par {n} user(s) hain — pehle unka role badlo", 409)
    audit("delete", "roles", f"Role '{role.name}' delete kiya")
    db.session.delete(role)
    db.session.commit()
    return jsonify({"ok": True})


# ── Audit log ─────────────────────────────────────────────────────────────────
@admin_bp.get("/audit")
@admin_required
def audit_logs():
    q = AuditLog.query
    username = (request.args.get("username") or "").strip()
    module = (request.args.get("module") or "").strip()
    date_from = (request.args.get("from") or "").strip()
    date_to = (request.args.get("to") or "").strip()
    if username:
        q = q.filter(AuditLog.username.ilike(f"%{username}%"))
    if module:
        q = q.filter(AuditLog.module == module)
    if date_from:
        q = q.filter(AuditLog.ts >= date_from)
    if date_to:
        q = q.filter(AuditLog.ts <= date_to + " 23:59:59")
    limit = min(int(request.args.get("limit", 200) or 200), 1000)
    rows = q.order_by(AuditLog.ts.desc()).limit(limit).all()
    return jsonify({"logs": [r.to_dict() for r in rows]})
