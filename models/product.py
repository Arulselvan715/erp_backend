"""Product model with inventory tracking and procurement settings."""

from datetime import datetime

from . import db


class Product(db.Model):
    """Represents an item that can be sold, purchased, or manufactured."""

    __tablename__ = "products"

    PROCUREMENT_TYPES = ("purchase", "manufacturing")

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    category = db.Column(db.String(100), nullable=False, default="", index=True)
    unit_of_measure = db.Column(db.String(20), nullable=False, default="units")
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    cost_price = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    on_hand_qty = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    reserved_qty = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    reorder_level = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    procure_on_demand = db.Column(db.Boolean, nullable=False, default=False)
    procurement_type = db.Column(
        db.String(15), nullable=False, default="purchase"
    )
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # --- Relationships ---
    vendor = db.relationship("Vendor", backref=db.backref("products", lazy="dynamic"))
    sales_order_lines = db.relationship(
        "SalesOrderLine", back_populates="product", lazy="dynamic"
    )
    purchase_order_lines = db.relationship(
        "PurchaseOrderLine", back_populates="product", lazy="dynamic"
    )
    boms = db.relationship(
        "BillOfMaterials", back_populates="product", lazy="dynamic"
    )
    bom_component_usages = db.relationship(
        "BomLine",
        back_populates="component",
        lazy="dynamic",
        foreign_keys="BomLine.component_id",
    )
    manufacturing_orders = db.relationship(
        "ManufacturingOrder", back_populates="product", lazy="dynamic"
    )
    stock_movements = db.relationship(
        "StockLedger", back_populates="product", lazy="dynamic"
    )

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------
    @property
    def sales_price(self):
        """Alias for unit_price to support template and controller compatibility."""
        return self.unit_price

    @sales_price.setter
    def sales_price(self, value):
        self.unit_price = value

    @property
    def procurement_strategy(self):
        """Map procure_on_demand boolean to strategy string expected by frontend."""
        return "make_to_order" if self.procure_on_demand else "make_to_stock"

    @procurement_strategy.setter
    def procurement_strategy(self, value):
        self.procure_on_demand = (value == "make_to_order")

    @property
    def free_to_use_qty(self):
        """Quantity available for new reservations (on_hand − reserved)."""
        return (self.on_hand_qty or 0) - (self.reserved_qty or 0)

    @property
    def needs_reorder(self) -> bool:
        """True when free-to-use stock falls below the reorder level."""
        return self.free_to_use_qty <= (self.reorder_level or 0)

    def __repr__(self) -> str:
        return (
            f"<Product {self.id} sku={self.sku!r} "
            f"on_hand={self.on_hand_qty} reserved={self.reserved_qty}>"
        )

