"""
Auth + RBAC models for Site Khata.

Design:
  Role            -> permission matrix ka default set (RolePermission rows)
  User            -> ek role + client/site assignments + per-user overrides
  RolePermission  -> role x module x (view/create/edit/delete/approve/export)
  UserPermission  -> user x module override (NULL = role se inherit)
  UserClient      -> user ko poora client assign (uski saari sites)
  UserSite        -> user ko specific site assign
  AuditLog        -> kisne kya kiya, kab — admin panel me dikhta hai

Effective permission = role default, phir user override (agar set ho).
Admin role (is_admin=True) sab kuch bypass karta hai.
"""

import secrets
from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .models import Serializable, _fk, db, gen_id

# ── Module registry ───────────────────────────────────────────────────────────
# Naya module add karna ho to bas yahan ek line — baaki sab (matrix UI,
# permissions, sidebar) automatically pick kar lega.
MODULES = [
    ("dashboard", "Dashboard"),
    ("clients",   "Clients"),
    ("sites",     "Sites"),
    ("material",  "Material"),
    ("assets",    "Assets"),
    ("labour",    "Labour"),
    ("vendors",   "Vendors"),
    ("expenses",  "Expenses"),
    ("payments",  "Payments"),
    ("receipts",  "Receipts"),
]
MODULE_KEYS = [k for k, _ in MODULES]
ACTIONS = ["view", "create", "edit", "delete", "approve", "export"]
PERM_COLS = [f"can_{a}" for a in ACTIONS]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


INVITE_EXPIRY_HOURS = 48


def new_invite_token():
    return secrets.token_urlsafe(32)


def invite_expiry_ts():
    return (datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRY_HOURS)).strftime("%Y-%m-%d %H:%M:%S")


class Role(Serializable, db.Model):
    __tablename__ = "roles"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    name = db.Column(db.String, nullable=False, unique=True)
    description = db.Column(db.String, default="")
    is_admin = db.Column(db.Boolean, nullable=False, default=False)   # full access, no checks
    is_system = db.Column(db.Boolean, nullable=False, default=False)  # delete/rename nahi ho sakta

    permissions = db.relationship(
        "RolePermission", cascade="all, delete-orphan", backref="role", lazy="selectin"
    )

    def perm_matrix(self):
        """{module: {action: bool}} — missing module = sab False."""
        matrix = {m: {a: False for a in ACTIONS} for m in MODULE_KEYS}
        if self.is_admin:
            return {m: {a: True for a in ACTIONS} for m in MODULE_KEYS}
        for rp in self.permissions:
            if rp.module in matrix:
                matrix[rp.module] = {a: bool(getattr(rp, f"can_{a}")) for a in ACTIONS}
        return matrix

    def to_dict(self):
        d = super().to_dict()
        d["permissions"] = self.perm_matrix()
        return d


class RolePermission(Serializable, db.Model):
    __tablename__ = "role_permissions"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    role_id = db.Column(db.String, _fk("roles.id"), nullable=False, index=True)
    module = db.Column(db.String, nullable=False)
    can_view = db.Column(db.Boolean, nullable=False, default=False)
    can_create = db.Column(db.Boolean, nullable=False, default=False)
    can_edit = db.Column(db.Boolean, nullable=False, default=False)
    can_delete = db.Column(db.Boolean, nullable=False, default=False)
    can_approve = db.Column(db.Boolean, nullable=False, default=False)
    can_export = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (db.UniqueConstraint("role_id", "module", name="uq_role_module"),)


class User(Serializable, db.Model):
    """Login email se hota hai. Naya user 'Pending' state me banta hai — invite
    email ke link se apna password set karke khud Active hota hai. Admin
    kabhi bhi kisi user ka password directly nahi set karta."""
    __tablename__ = "users"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    email = db.Column(db.String, nullable=False, unique=True)
    password_hash = db.Column(db.String, nullable=True)  # invite accept hone tak NULL
    full_name = db.Column(db.String, default="")
    phone = db.Column(db.String, default="")
    role_id = db.Column(db.String, db.ForeignKey("roles.id"), nullable=False, index=True)
    status = db.Column(db.String, nullable=False, default="Pending")  # Pending | Active | Inactive
    created_at = db.Column(db.String, default=now_iso)
    last_login = db.Column(db.String, default="")
    failed_logins = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.String, default="")  # ISO ts — brute force lockout
    invite_token = db.Column(db.String, default="", index=True)
    invite_expires = db.Column(db.String, default="")

    role = db.relationship("Role", lazy="joined")
    overrides = db.relationship(
        "UserPermission", cascade="all, delete-orphan", backref="user", lazy="selectin"
    )
    client_links = db.relationship(
        "UserClient", cascade="all, delete-orphan", backref="user", lazy="selectin"
    )
    site_links = db.relationship(
        "UserSite", cascade="all, delete-orphan", backref="user", lazy="selectin"
    )

    # ── Password ──
    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, raw or "")

    def start_invite(self):
        self.invite_token = new_invite_token()
        self.invite_expires = invite_expiry_ts()
        return self.invite_token

    def invite_valid(self, token):
        return bool(token) and self.invite_token == token and self.invite_expires and now_iso() <= self.invite_expires

    def clear_invite(self):
        self.invite_token = ""
        self.invite_expires = ""

    @property
    def is_admin(self):
        return bool(self.role and self.role.is_admin)

    def effective_permissions(self):
        """Role defaults + per-user overrides (NULL = inherit)."""
        matrix = self.role.perm_matrix() if self.role else {
            m: {a: False for a in ACTIONS} for m in MODULE_KEYS
        }
        if self.is_admin:
            return matrix  # admin par override apply nahi hota
        for up in self.overrides:
            if up.module not in matrix:
                continue
            for a in ACTIONS:
                v = getattr(up, f"can_{a}")
                if v is not None:
                    matrix[up.module][a] = bool(v)
        return matrix

    def to_dict(self):
        d = super().to_dict()
        d.pop("password_hash", None)
        d.pop("failed_logins", None)
        d.pop("locked_until", None)
        d.pop("invite_token", None)  # kabhi bhi API response me nahi jaana chahiye
        d["role_name"] = self.role.name if self.role else ""
        d["is_admin"] = self.is_admin
        d["has_password"] = bool(self.password_hash)
        d["client_ids"] = [l.client_id for l in self.client_links]
        d["site_ids"] = [l.site_id for l in self.site_links]
        d["overrides"] = {
            up.module: {a: getattr(up, f"can_{a}") for a in ACTIONS} for up in self.overrides
        }
        return d


class UserPermission(Serializable, db.Model):
    """Per-user module override. NULL = role se inherit, True/False = force."""
    __tablename__ = "user_permissions"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    user_id = db.Column(db.String, _fk("users.id"), nullable=False, index=True)
    module = db.Column(db.String, nullable=False)
    can_view = db.Column(db.Boolean, nullable=True)
    can_create = db.Column(db.Boolean, nullable=True)
    can_edit = db.Column(db.Boolean, nullable=True)
    can_delete = db.Column(db.Boolean, nullable=True)
    can_approve = db.Column(db.Boolean, nullable=True)
    can_export = db.Column(db.Boolean, nullable=True)

    __table_args__ = (db.UniqueConstraint("user_id", "module", name="uq_user_module"),)


class UserClient(db.Model):
    """User ko poora client assign — us client ki SAARI sites accessible."""
    __tablename__ = "user_clients"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    user_id = db.Column(db.String, _fk("users.id"), nullable=False, index=True)
    client_id = db.Column(db.String, _fk("clients.id"), nullable=False, index=True)

    __table_args__ = (db.UniqueConstraint("user_id", "client_id", name="uq_user_client"),)


class UserSite(db.Model):
    """User ko specific site assign — sirf usi site ka data."""
    __tablename__ = "user_sites"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    user_id = db.Column(db.String, _fk("users.id"), nullable=False, index=True)
    site_id = db.Column(db.String, _fk("sites.id"), nullable=False, index=True)

    __table_args__ = (db.UniqueConstraint("user_id", "site_id", name="uq_user_site"),)


class AuditLog(Serializable, db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.String, primary_key=True, default=gen_id)
    ts = db.Column(db.String, nullable=False, default=now_iso, index=True)
    user_id = db.Column(db.String, default="")
    username = db.Column(db.String, default="")
    action = db.Column(db.String, nullable=False)   # login / create / edit / delete / ...
    module = db.Column(db.String, default="")       # kis module par
    detail = db.Column(db.String, default="")       # human-readable detail
    ip = db.Column(db.String, default="")


# ── Seed: default roles + pehla admin user ────────────────────────────────────
# Supervisor role ka starting template — admin baad me panel se badal sakta hai.
SUPERVISOR_DEFAULTS = {
    "dashboard": {"view": True},
    "material":  {"view": True, "create": True, "edit": True, "export": True},
    "assets":    {"view": True, "create": True, "edit": True},
    "labour":    {"view": True, "create": True, "edit": True, "export": True},
    "vendors":   {"view": True, "create": True},
    "expenses":  {"view": True, "create": True, "edit": True},
    "payments":  {"view": True, "export": True},
    "receipts":  {"view": True, "create": True},
}


def seed_auth(admin_email, admin_password):
    """Default roles banao aur (agar koi user nahi hai to) pehla admin user.
    Bootstrap admin invite se nahi — direct Active + password ke saath banta hai,
    baaki sab users invite email se apna password set karte hain."""
    admin_role = Role.query.filter_by(is_admin=True).first()
    if not admin_role:
        admin_role = Role(name="Admin", description="Full access — sab clients, sab sites, sab modules",
                          is_admin=True, is_system=True)
        db.session.add(admin_role)

    if not Role.query.filter_by(name="Supervisor").first():
        sup = Role(name="Supervisor",
                   description="Site supervisor — assigned site ka data manage karta hai",
                   is_system=True)
        db.session.add(sup)
        db.session.flush()
        for module, actions in SUPERVISOR_DEFAULTS.items():
            db.session.add(RolePermission(
                role_id=sup.id, module=module,
                **{f"can_{a}": actions.get(a, False) for a in ACTIONS},
            ))

    created_admin = False
    if not User.query.first():
        db.session.flush()
        admin = User(email=admin_email.strip().lower(), full_name="Administrator",
                     role_id=admin_role.id, status="Active")
        admin.set_password(admin_password)
        db.session.add(admin)
        created_admin = True

    db.session.commit()
    return created_admin
