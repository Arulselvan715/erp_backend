"""Inventory / Stock Ledger model and helpers."""

from datetime import datetime

from . import db


class StockLedger(db.Model):
    """Immutable record of every stock movement in the system."""

    __tablename__ = "stock_ledger"

    MOVEMENT_TYPES = (
        "purchase_receipt",
        "sales_issue",
        "manufacturing_consume",
        "manufacturing_produce",
        "adjustment",
        "reservation",
        "reservation_release",
        "transfer",
        "return",
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False, index=True
    )
    movement_type = db.Column(db.String(30), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    reference_type = db.Column(db.String(30), nullable=False, default="")
    reference_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=False, default="")
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # --- Relationships ---
    product = db.relationship("Product", back_populates="stock_movements")
    user = db.relationship("User", back_populates="stock_movements")

    @property
    def timestamp(self) -> str:
        return self.created_at.isoformat() if self.created_at else ""

    @property
    def product_name(self) -> str:
        return self.product.name if self.product else ""

    @property
    def product_sku(self) -> str:
        return self.product.sku if self.product else ""

    # Composite index for reference lookups
    __table_args__ = (
        db.Index("ix_stock_ledger_reference", "reference_type", "reference_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<StockLedger {self.id} product={self.product_id} "
            f"{self.movement_type} qty={self.quantity}>"
        )


# ======================================================================
# Helper function
# ======================================================================
def log_stock_movement(
    product,
    movement_type: str,
    quantity,
    reference_type: str = "",
    reference_id: int | None = None,
    description: str = "",
    user_id: int | None = None,
):
    """Create a stock ledger entry **and** update the product's quantities.

    Positive *quantity* = stock increase (receipt / produce / return).
    Negative *quantity* = stock decrease (issue / consume).

    For ``reservation`` and ``reservation_release`` the on-hand quantity is
    not changed — only ``reserved_qty`` is adjusted.

    The caller is responsible for calling ``db.session.commit()``.
    """
    from .product import Product  # noqa: F811 – local import to avoid circular

    entry = StockLedger(
        product_id=product.id,
        movement_type=movement_type,
        quantity=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        user_id=user_id,
    )
    db.session.add(entry)

    # Update product quantities
    if movement_type == "reservation":
        # Reserve stock: increase reserved_qty (quantity should be positive)
        product.reserved_qty = (product.reserved_qty or 0) + abs(quantity)
    elif movement_type == "reservation_release":
        # Release reservation: decrease reserved_qty
        product.reserved_qty = max(0, (product.reserved_qty or 0) - abs(quantity))
    else:
        # All other movements adjust on_hand_qty directly
        product.on_hand_qty = (product.on_hand_qty or 0) + quantity

    db.session.add(product)
    return entry
