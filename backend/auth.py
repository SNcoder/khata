"""
Authentication + authorization core for Site Khata.

- Session-based login (email + password, hashed via werkzeug)
- Naye user invite email se apna password set karte hain (admin password nahi dekhta/set nahi karta)
- g.user har request par load hota hai (load_current_user)
- require_perm(module, action) — route-level RBAC check
- Client/site scoping helpers — supervisor sirf apni assigned site ka data dekhe
- audit() — har important action ka log (Admin Panel > Audit Log)
"""

from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, g, jsonify, request, session

from database import db
from database.auth_models import ACTIONS, MODULES, AuditLog, User, now_iso

auth_bp = Blueprint("auth", __name__, url_prefix="/api")

LOCKOUT_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# In endpoints par login zaroori nahi (invite accept karne se pehle user logged-in nahi hota)
PUBLIC_API_PATHS = {"/api/login", "/api/accept_invite"}
PUBLIC_API_PREFIXES = ("/api/invite/",)


# ── Request-level user loading ────────────────────────────────────────────────
def load_current_user():
    """before_request hook — session se user load karo, warna 401 (API par)."""
    g.user = None
    uid = session.get("user_id")
    if uid:
        user = db.session.get(User, uid)
        if user and user.status == "Active":
            g.user = user

    path = request.path
    is_public = path in PUBLIC_API_PATHS or path.startswith(PUBLIC_API_PREFIXES)
    if path.startswith("/api/") and not is_public and g.user is None:
        return jsonify({"error": "Login required"}), 401
    return None


def audit(action, module="", detail=""):
    """Audit log entry add karo (commit route ke commit ke saath hota hai)."""
    user = getattr(g, "user", None)
    db.session.add(AuditLog(
        user_id=user.id if user else "",
        username=user.email if user else "",
        action=action, module=module, detail=(detail or "")[:500],
        ip=(request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr or ""),
    ))


# ── Permission checks ─────────────────────────────────────────────────────────
def has_perm(module, action):
    if g.user is None:
        return False
    if g.user.is_admin:
        return True
    return g.user.effective_permissions().get(module, {}).get(action, False)


def require_perm(module, action):
    """Decorator: module+action permission nahi hai to 403."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not has_perm(module, action):
                return jsonify({"error": "Permission nahi hai (" + module + ": " + action + ")"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if g.user is None or not g.user.is_admin:
            return jsonify({"error": "Sirf admin access kar sakta hai"}), 403
        return fn(*args, **kwargs)
    return wrapper


# ── Client/site scoping ───────────────────────────────────────────────────────
def allowed_client_ids():
    """None = sab clients (admin). Warna assigned client ids ka set
    (direct client assignment + assigned sites ke clients)."""
    if g.user.is_admin:
        return None
    from database import Site
    ids = {l.client_id for l in g.user.client_links}
    site_ids = [l.site_id for l in g.user.site_links]
    if site_ids:
        rows = Site.query.filter(Site.id.in_(site_ids)).all()
        ids.update(s.client_id for s in rows)
    return ids


def client_allowed(client_id):
    allowed = allowed_client_ids()
    return allowed is None or client_id in allowed


def allowed_site_names(client_id):
    """Is client ke andar user ko kaunsi sites dikhein.
    None = saari sites. Warna allowed site names ka set.
    Rule: poora client assigned hai -> saari sites; warna sirf assigned sites."""
    if g.user.is_admin:
        return None
    if client_id in {l.client_id for l in g.user.client_links}:
        return None
    from database import Site
    site_ids = [l.site_id for l in g.user.site_links]
    if not site_ids:
        return set()
    rows = Site.query.filter(Site.id.in_(site_ids), Site.client_id == client_id).all()
    return {s.name for s in rows}


def site_value_ok(names, value):
    """Free-text site field scoping ke andar hai? Blank = client-general, allowed."""
    return names is None or not value or value in names


def entry_in_scope(names, entry_like):
    """Entry (from_loc/to_loc) visible hai agar koi bhi location allowed ho."""
    if names is None:
        return True
    f = getattr(entry_like, "from_loc", "") or ""
    t = getattr(entry_like, "to_loc", "") or ""
    if not f and not t:
        return True
    return (f in names) or (t in names)


# ── Auth routes ───────────────────────────────────────────────────────────────
@auth_bp.post("/login")
def login():
    body = request.get_json(force=True, silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"error": "Email aur password dono chahiye"}), 400

    user = User.query.filter(db.func.lower(User.email) == email).first()
    generic_err = (jsonify({"error": "Email ya password galat hai"}), 401)
    if not user:
        return generic_err
    if user.status == "Pending":
        return jsonify({"error": "Account abhi activate nahi hua — apna email check karo aur invite link se password set karo"}), 403
    if user.status != "Active":
        return jsonify({"error": "Account deactivate hai — admin se baat karo"}), 403

    now = now_iso()
    if user.locked_until and now < user.locked_until:
        return jsonify({"error": f"Account temporarily locked hai. {user.locked_until} UTC ke baad try karo"}), 423

    if not user.check_password(password):
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= LOCKOUT_ATTEMPTS:
            until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            user.locked_until = until.strftime("%Y-%m-%d %H:%M:%S")
            user.failed_logins = 0
        db.session.commit()
        return generic_err

    user.failed_logins = 0
    user.locked_until = ""
    user.last_login = now
    session.permanent = True
    session["user_id"] = user.id
    g.user = user
    audit("login", detail=f"{user.email} logged in")
    db.session.commit()
    return jsonify({"ok": True, "me": me_payload(user)})


@auth_bp.post("/logout")
def logout():
    if g.user:
        audit("logout", detail=f"{g.user.email} logged out")
        db.session.commit()
    session.clear()
    return jsonify({"ok": True})


def me_payload(user):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name or user.email,
        "role_name": user.role.name if user.role else "",
        "is_admin": user.is_admin,
        "permissions": user.effective_permissions(),
        "modules": [{"key": k, "label": l} for k, l in MODULES],
        "actions": ACTIONS,
    }


# ── Invite / password-set flow (public — user abhi logged in nahi hota) ──────
@auth_bp.get("/invite/<token>")
def get_invite(token):
    user = User.query.filter_by(invite_token=token).first()
    if not user or not user.invite_valid(token):
        return jsonify({"error": "Ye invite link invalid ya expire ho gayi hai — admin se naya link mangwao"}), 400
    return jsonify({"email": user.email, "full_name": user.full_name})


@auth_bp.post("/accept_invite")
def accept_invite():
    body = request.get_json(force=True, silent=True) or {}
    token = body.get("token") or ""
    password = body.get("password") or ""
    user = User.query.filter_by(invite_token=token).first()
    if not user or not user.invite_valid(token):
        return jsonify({"error": "Ye invite link invalid ya expire ho gayi hai — admin se naya link mangwao"}), 400
    if user.status == "Inactive":
        return jsonify({"error": "Ye account deactivate hai — admin se baat karo"}), 403
    if len(password) < 6:
        return jsonify({"error": "Password kam se kam 6 characters ka ho"}), 400

    user.set_password(password)
    user.status = "Active"
    user.clear_invite()
    user.failed_logins = 0
    user.locked_until = ""
    user.last_login = now_iso()
    session.permanent = True
    session["user_id"] = user.id
    g.user = user
    audit("accept_invite", detail=f"{user.email} ne password set karke account activate kiya")
    db.session.commit()
    return jsonify({"ok": True, "me": me_payload(user)})


@auth_bp.get("/me")
def me():
    return jsonify(me_payload(g.user))


@auth_bp.post("/change_password")
def change_password():
    body = request.get_json(force=True, silent=True) or {}
    current = body.get("current_password") or ""
    new = body.get("new_password") or ""
    if not g.user.check_password(current):
        return jsonify({"error": "Current password galat hai"}), 400
    if len(new) < 6:
        return jsonify({"error": "Naya password kam se kam 6 characters ka ho"}), 400
    g.user.set_password(new)
    audit("change_password", detail=f"{g.user.email} ne apna password badla")
    db.session.commit()
    return jsonify({"ok": True})
