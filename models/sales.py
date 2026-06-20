"""Sales Order and Sales Order Line models."""

from datetime import datetime

from . import db


def gen_so_number():
    from models.sales import SalesOrder
    last_order = db.session.query(SalesOrder).order_by(SalesOrder.id.desc()).first()
    next_id = (last_order.id + 1) if last_order else 1
    return f"SO-{next_id:05d}"


def get_current_user_id():
    from flask_login import current_user
    if current_user and current_user.is_authenticated:
        return current_user.id
    return 1


class SalesOrder(db.Model):
    """A customer-facing sales order (header)."""

    __tablename__ = "sales_orders"

    STATUSES = ("draft", "confirmed", "processing", "shipped", "delivered", "cancelled")

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(
        db.String(30), unique=True, nullable=False, index=True, default=gen_so_number
    )
    customer_id = db.Column(
        db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True
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
    customer = db.relationship("Customer", back_populates="sales_orders")
    user = db.relationship("User", back_populates="sales_orders")
    lines = db.relationship(
        "SalesOrderLine",
        back_populates="order",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def customer_name(self) -> str:
        return self.customer.name if self.customer else ""

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
            f"<SalesOrder {self.id} #{self.order_number} "
            f"status={self.status!r}>"
        )


class SalesOrderLine(db.Model):
    """Individual line item on a sales order."""

    __tablename__ = "sales_order_lines"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("sales_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False, index=True
    )
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=1.00)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    discount_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    line_total = db.Column(db.Numeric(14, 2), nullable=False, default=0.00)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # --- Relationships ---
    order = db.relationship("SalesOrder", back_populates="lines")
    product = db.relationship("Product", back_populates="sales_order_lines")

    @property
    def product_name(self) -> str:
        return self.product.name if self.product else ""

    @property
    def price(self) -> float:
        return float(self.unit_price or 0.0)

    # ------------------------------------------------------------------
    def compute_line_total(self) -> None:
        """Calculate line_total accounting for discount."""
        price = float(self.unit_price or 0)
        qty = float(self.quantity or 0)
        discount = float(self.discount_pct or 0) / 100.0
        self.line_total = round(price * qty * (1 - discount), 2)

    def __repr__(self) -> str:
        return (
            f"<SalesOrderLine {self.id} order={self.order_id} "
            f"product={self.product_id} qty={self.quantity}>"
        )
