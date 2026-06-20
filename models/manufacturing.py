"""Manufacturing models: BoM, BoM Lines, BoM Operations, MO, Work Orders."""

from datetime import datetime

from . import db


# ======================================================================
# Bill of Materials (header)
# ======================================================================
class BillOfMaterials(db.Model):
    """Defines how to manufacture a product (recipe / routing)."""

    __tablename__ = "bill_of_materials"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False, index=True
    )
    name = db.Column(db.String(200), nullable=False)
    version = db.Column(db.String(20), nullable=False, default="1.0")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    status = db.Column(db.String(20), nullable=False, default="pending")
    output_qty = db.Column(db.Numeric(12, 2), nullable=False, default=1.00)
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # --- Relationships ---
    product = db.relationship("Product", back_populates="boms")
    lines = db.relationship(
        "BomLine",
        back_populates="bom",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    operations = db.relationship(
        "BomOperation",
        back_populates="bom",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BomOperation.sequence",
    )
    manufacturing_orders = db.relationship(
        "ManufacturingOrder", back_populates="bom", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return (
            f"<BillOfMaterials {self.id} {self.name!r} "
            f"product={self.product_id} v{self.version}>"
        )


# ======================================================================
# BoM Lines (components)
# ======================================================================
class BomLine(db.Model):
    """A single component required by a Bill of Materials."""

    __tablename__ = "bom_lines"

    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(
        db.Integer,
        db.ForeignKey("bill_of_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False, index=True
    )
    quantity = db.Column(db.Numeric(12, 4), nullable=False, default=1.0000)
    unit_of_measure = db.Column(db.String(20), nullable=False, default="units")
    notes = db.Column(db.Text, nullable=False, default="")

    # --- Relationships ---
    bom = db.relationship("BillOfMaterials", back_populates="lines")
    component = db.relationship(
        "Product",
        back_populates="bom_component_usages",
        foreign_keys=[component_id],
    )

    def __repr__(self) -> str:
        return (
            f"<BomLine {self.id} bom={self.bom_id} "
            f"component={self.component_id} qty={self.quantity}>"
        )


# ======================================================================
# BoM Operations (routing steps)
# ======================================================================
class BomOperation(db.Model):
    """A manufacturing step / routing operation within a BoM."""

    __tablename__ = "bom_operations"

    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(
        db.Integer,
        db.ForeignKey("bill_of_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence = db.Column(db.Integer, nullable=False, default=10)
    name = db.Column(db.String(200), nullable=False)
    work_center = db.Column(db.String(100), nullable=False, default="")
    duration_minutes = db.Column(db.Numeric(8, 2), nullable=False, default=0.00)
    notes = db.Column(db.Text, nullable=False, default="")

    # --- Relationships ---
    bom = db.relationship("BillOfMaterials", back_populates="operations")
    work_orders = db.relationship(
        "WorkOrder", back_populates="bom_operation", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return (
            f"<BomOperation {self.id} seq={self.sequence} "
            f"{self.name!r} bom={self.bom_id}>"
        )


# ======================================================================
# Manufacturing Order
# ======================================================================
def gen_mo_number():
    from models.manufacturing import ManufacturingOrder
    last_order = db.session.query(ManufacturingOrder).order_by(ManufacturingOrder.id.desc()).first()
    next_id = (last_order.id + 1) if last_order else 1
    return f"MO-{next_id:05d}"


def get_current_user_id():
    from flask_login import current_user
    if current_user and current_user.is_authenticated:
        return current_user.id
    return 1


class ManufacturingOrder(db.Model):
    """An order to manufacture a quantity of a product using a BoM."""

    __tablename__ = "manufacturing_orders"

    STATUSES = ("draft", "confirmed", "in_progress", "done", "cancelled")

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(
        db.String(30), unique=True, nullable=False, index=True, default=gen_mo_number
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False, index=True
    )
    bom_id = db.Column(
        db.Integer,
        db.ForeignKey("bill_of_materials.id"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True, default=get_current_user_id
    )
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=1.00)
    status = db.Column(
        db.String(20), nullable=False, default="draft", index=True
    )
    planned_start = db.Column(db.DateTime, nullable=True)
    planned_end = db.Column(db.DateTime, nullable=True)
    actual_start = db.Column(db.DateTime, nullable=True)
    actual_end = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # --- Relationships ---
    product = db.relationship("Product", back_populates="manufacturing_orders")
    bom = db.relationship("BillOfMaterials", back_populates="manufacturing_orders")
    user = db.relationship("User", back_populates="manufacturing_orders")
    work_orders = db.relationship(
        "WorkOrder",
        back_populates="manufacturing_order",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WorkOrder.sequence",
    )

    @property
    def product_name(self) -> str:
        return self.product.name if self.product else ""

    @property
    def bom_name(self) -> str:
        return self.bom.name if self.bom else ""

    @property
    def items(self) -> list:
        # Expose items as serialised work orders list for detail page compatibility
        from routes.utils import serialize
        return [serialize(wo) for wo in self.work_orders.all()]

    def __repr__(self) -> str:
        return (
            f"<ManufacturingOrder {self.id} #{self.order_number} "
            f"product={self.product_id} status={self.status!r}>"
        )


# ======================================================================
# Work Order (per-operation execution within an MO)
# ======================================================================
class WorkOrder(db.Model):
    """Tracks execution of a single BoM operation within an MO."""

    __tablename__ = "work_orders"

    STATUSES = ("pending", "in_progress", "done", "cancelled")

    id = db.Column(db.Integer, primary_key=True)
    manufacturing_order_id = db.Column(
        db.Integer,
        db.ForeignKey("manufacturing_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bom_operation_id = db.Column(
        db.Integer,
        db.ForeignKey("bom_operations.id"),
        nullable=False,
        index=True,
    )
    sequence = db.Column(db.Integer, nullable=False, default=10)
    status = db.Column(
        db.String(20), nullable=False, default="pending", index=True
    )
    planned_duration_min = db.Column(db.Numeric(8, 2), nullable=False, default=0.00)
    actual_duration_min = db.Column(db.Numeric(8, 2), nullable=False, default=0.00)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # --- Relationships ---
    manufacturing_order = db.relationship(
        "ManufacturingOrder", back_populates="work_orders"
    )
    bom_operation = db.relationship(
        "BomOperation", back_populates="work_orders"
    )

    @property
    def operation_name(self) -> str:
        return self.bom_operation.name if self.bom_operation else ""

    @property
    def order_number(self) -> str:
        return self.manufacturing_order.order_number if self.manufacturing_order else ""

    @property
    def product_name(self) -> str:
        return self.manufacturing_order.product.name if self.manufacturing_order and self.manufacturing_order.product else ""

    @property
    def work_center(self) -> str:
        return self.bom_operation.work_center if self.bom_operation else ""

    def __repr__(self) -> str:
        return (
            f"<WorkOrder {self.id} mo={self.manufacturing_order_id} "
            f"seq={self.sequence} status={self.status!r}>"
        )
