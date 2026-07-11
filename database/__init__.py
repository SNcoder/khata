"""Database package — SQLAlchemy ORM models + Pydantic schemas."""

from .connection import (
    DATABASE_URL,
    SQLALCHEMY_DATABASE_URI,
    SQLITE_PATH,
    USE_PG,
)
from .models import (
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
    init_db,
)

# Auth/RBAC models — import zaroori hai taaki db.create_all() inki tables bhi banaye
from .auth_models import (  # noqa: E402
    AuditLog,
    Role,
    RolePermission,
    User,
    UserClient,
    UserPermission,
    UserSite,
    invite_expiry_ts,
    new_invite_token,
    seed_auth,
)

__all__ = [
    "DATABASE_URL",
    "SQLALCHEMY_DATABASE_URI",
    "SQLITE_PATH",
    "USE_PG",
    "db",
    "init_db",
    "Client",
    "Site",
    "Entry",
    "Vendor",
    "VendorTxn",
    "Expense",
    "Material",
    "Labourer",
    "LabourPayment",
    "Receipt",
    "User",
    "Role",
    "RolePermission",
    "UserPermission",
    "UserClient",
    "UserSite",
    "AuditLog",
    "seed_auth",
    "new_invite_token",
    "invite_expiry_ts",
]
