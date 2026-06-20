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
    product_id: int,
    quantity,
    reference_type: str = "",
    reference_id: int | None = None,
    description: str = "",
    user_id: int | None = None,
):
    """Create a stock ledger entry.

    The caller is responsible for modifying product quantities and calling ``db.session.commit()``.
    """
    from flask_login import current_user
    from decimal import Decimal

    # Determine movement type based on reference type and quantity
    movement_type = "adjustment"
    if reference_type == "PurchaseOrder":
        movement_type = "purchase_receipt"
    elif reference_type == "SalesOrder":
        if float(quantity or 0) == 0:
            if "Released" in description or "cancel" in description.lower():
                movement_type = "reservation_release"
            else:
                movement_type = "reservation"
        else:
            movement_type = "sales_issue"
    elif reference_type == "ManufacturingOrder":
        if float(quantity or 0) == 0:
            if "Released" in description or "cancel" in description.lower():
                movement_type = "reservation_release"
            else:
                movement_type = "reservation"
        elif float(quantity or 0) < 0:
            movement_type = "manufacturing_consume"
        else:
            movement_type = "manufacturing_produce"
    elif reference_type == "ManualAdjustment":
        movement_type = "adjustment"

    # Get current user ID if not provided
    if user_id is None:
        if current_user and current_user.is_authenticated:
            user_id = current_user.id
        else:
            user_id = 1

    entry = StockLedger(
        product_id=product_id,
        movement_type=movement_type,
        quantity=Decimal(str(quantity)) if quantity is not None else Decimal("0.00"),
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        user_id=user_id,
    )
    db.session.add(entry)
    return entry

