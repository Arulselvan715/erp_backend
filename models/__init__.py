"""Mini ERP — SQLAlchemy models package.

Usage::

    from models import db, User, Product, Customer, ...

Initialise with a Flask app::

    from models import db
    db.init_app(app)
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ── Import all models so they are registered with SQLAlchemy ──────────
from .user import User  # noqa: E402, F401
from .product import Product  # noqa: E402, F401
from .customer import Customer  # noqa: E402, F401
from .vendor import Vendor  # noqa: E402, F401
from .sales import SalesOrder, SalesOrderLine  # noqa: E402, F401
from .purchase import PurchaseOrder, PurchaseOrderLine  # noqa: E402, F401
from .manufacturing import (  # noqa: E402, F401
    BillOfMaterials,
    BomLine,
    BomOperation,
    ManufacturingOrder,
    WorkOrder,
)
from .inventory import StockLedger, log_stock_movement  # noqa: E402, F401
from .audit import AuditLog, log_audit  # noqa: E402, F401

__all__ = [
    "db",
    # Auth
    "User",
    # Master data
    "Product",
    "Customer",
    "Vendor",
    # Sales
    "SalesOrder",
    "SalesOrderLine",
    # Purchasing
    "PurchaseOrder",
    "PurchaseOrderLine",
    # Manufacturing
    "BillOfMaterials",
    "BomLine",
    "BomOperation",
    "ManufacturingOrder",
    "WorkOrder",
    # Inventory
    "StockLedger",
    "log_stock_movement",
    # Audit
    "AuditLog",
    "log_audit",
]
