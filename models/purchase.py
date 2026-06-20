"""Purchase Order and Purchase Order Line models."""

from datetime import datetime

from . import db


def gen_po_number():
    from models.purchase import PurchaseOrder
    last_order = db.session.query(PurchaseOrder).order_by(PurchaseOrder.id.desc()).first()
    next_id = (last_order.id + 1) if last_order else 1
    return f"PO-{next_id:05d}"


def get_current_user_id():
    from flask_login import current_user
    if current_user and current_user.is_authenticated:
        return current_user.id
    return 1


class PurchaseOrder(db.Model):
    """A purchase order placed with a vendor."""

    __tablename__ = "purchase_orders"

    STATUSES = ("draft", "confirmed", "shipped", "received", "cancelled")

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(
        db.String(30), unique=True, nullable=False, index=True, default=gen_po_number
    )
    vendor_id = db.Column(
        db.Integer, db.ForeignKey("vendors.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True, default=get_current_user_id
    )
    status = db.Column(
        db.String(20), nullable=False, default="draft", index=True
    )
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expected_date = db.Column(db.DateTime, nullable=True)
    subtotal = db.Column(db.Numeric(14, 2), nullable=False, default=0.00)
    tax_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.00)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.00)
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # --- Relationships ---
    vendor = db.relationship("Vendor", back_populates="purchase_orders")
    user = db.relationship("User", back_populates="purchase_orders")
    lines = db.relationship(
        "PurchaseOrderLine",
        back_populates="order",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def vendor_name(self) -> str:
        return self.vendor.name if self.vendor else ""

    @property
    def items(self) -> list:
        from routes.utils import serialize
        return [serialize(line) for line in self.lines.all()]

    # ------------------------------------------------------------------
    def recalculate_totals(self) -> None:
        """Recompute subtotal and total_amount from line items."""
        self.subtotal = sum(line.line_total or 0 for line in self.lines.all())
        self.total_amount = (self.subtotal or 0) + (self.tax_amount or 0)

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrder {self.id} #{self.order_number} "
            f"status={self.status!r}>"
        )


class PurchaseOrderLine(db.Model):
    """Individual line item on a purchase order."""

    __tablename__ = "purchase_order_lines"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False, index=True
    )
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=1.00)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    line_total = db.Column(db.Numeric(14, 2), nullable=False, default=0.00)
    received_qty = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # --- Relationships ---
    order = db.relationship("PurchaseOrder", back_populates="lines")
    product = db.relationship("Product", back_populates="purchase_order_lines")

    @property
    def product_name(self) -> str:
        return self.product.name if self.product else ""

    @property
    def price(self) -> float:
        return float(self.unit_price or 0.0)

    # ------------------------------------------------------------------
    def compute_line_total(self) -> None:
        """Calculate line_total = unit_price × quantity."""
        self.line_total = round(
            float(self.unit_price or 0) * float(self.quantity or 0), 2
        )

    @property
    def remaining_qty(self):
        """Quantity still to be received."""
        return (self.quantity or 0) - (self.received_qty or 0)

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrderLine {self.id} order={self.order_id} "
            f"product={self.product_id} qty={self.quantity}>"
        )


class ProcurementRequest(db.Model):
    """A request to procure raw materials or products."""

    __tablename__ = "procurement_requests"

    STATUSES = ("pending", "approved", "po_created", "rejected")

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False, index=True
    )
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=1.00)
    status = db.Column(
        db.String(20), nullable=False, default="pending", index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True, default=get_current_user_id
    )
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # --- Relationships ---
    product = db.relationship("Product", backref=db.backref("procurement_requests", lazy="dynamic"))
    user = db.relationship("User", backref=db.backref("procurement_requests", lazy="dynamic"))

    @property
    def product_name(self) -> str:
        return self.product.name if self.product else ""

    @property
    def product_sku(self) -> str:
        return self.product.sku if self.product else ""

    @property
    def requester_username(self) -> str:
        return self.user.username if self.user else ""

    def __repr__(self) -> str:
        return (
            f"<ProcurementRequest {self.id} product={self.product_id} "
            f"qty={self.quantity} status={self.status!r}>"
        )
