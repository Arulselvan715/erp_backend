"""Vendor (supplier) model."""

from datetime import datetime

from . import db


class Vendor(db.Model):
    """A vendor / supplier from whom purchase orders are placed."""

    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False, default="", index=True)
    phone = db.Column(db.String(30), nullable=False, default="")
    address_line1 = db.Column(db.String(200), nullable=False, default="")
    address_line2 = db.Column(db.String(200), nullable=False, default="")
    city = db.Column(db.String(100), nullable=False, default="")
    state = db.Column(db.String(100), nullable=False, default="")
    postal_code = db.Column(db.String(20), nullable=False, default="")
    country = db.Column(db.String(100), nullable=False, default="")
    tax_id = db.Column(db.String(50), nullable=False, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # --- Relationships ---
    purchase_orders = db.relationship(
        "PurchaseOrder", back_populates="vendor", lazy="dynamic"
    )

    @property
    def address(self):
        return self.address_line1

    @address.setter
    def address(self, value):
        self.address_line1 = value

    def __repr__(self) -> str:
        return f"<Vendor {self.id} {self.name!r}>"
