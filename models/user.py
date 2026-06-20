"""User model with role-based authentication."""

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


class User(UserMixin, db.Model):
    """Application user with role-based access control."""

    __tablename__ = "users"

    # Allowed roles
    ROLES = (
        "Admin",
        "Sales User",
        "Purchase User",
        "Manufacturing User",
        "Inventory Manager",
        "Business Owner",
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(80), nullable=False, default="")
    last_name = db.Column(db.String(80), nullable=False, default="")
    role = db.Column(db.String(30), nullable=False, default="Sales User", index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # --- Relationships ---
    sales_orders = db.relationship(
        "SalesOrder", back_populates="user", lazy="dynamic"
    )
    purchase_orders = db.relationship(
        "PurchaseOrder", back_populates="user", lazy="dynamic"
    )
    manufacturing_orders = db.relationship(
        "ManufacturingOrder", back_populates="user", lazy="dynamic"
    )
    audit_logs = db.relationship(
        "AuditLog", back_populates="user", lazy="dynamic"
    )
    stock_movements = db.relationship(
        "StockLedger", back_populates="user", lazy="dynamic"
    )

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------
    def set_password(self, password: str) -> None:
        """Hash and store the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    # ------------------------------------------------------------------
    # Flask-Login integration
    # ------------------------------------------------------------------
    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return str(self.id)

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------
    def has_role(self, role: str) -> bool:
        return self.role == role

    def is_admin(self) -> bool:
        return self.role == "Admin"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self) -> str:
        return f"<User {self.id} {self.username!r} role={self.role!r}>"
