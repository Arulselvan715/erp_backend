"""Reports routes — financial summaries and operational metrics."""

from flask import Blueprint, jsonify
from flask_login import login_required

from models import db, Product, SalesOrder, PurchaseOrder, ManufacturingOrder
from routes.utils import role_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/revenue", methods=["GET"])
@login_required
@role_required("admin", "business owner")
def get_revenue_report():
    """Calculate delivered revenue, procurement costs, and gross profit."""
    total_revenue = db.session.query(db.func.sum(SalesOrder.total_amount)).filter(SalesOrder.status == 'delivered').scalar() or 0.0
    total_cost = db.session.query(db.func.sum(PurchaseOrder.total_amount)).filter(PurchaseOrder.status == 'received').scalar() or 0.0
    gross_profit = float(total_revenue) - float(total_cost)
    
    return jsonify({
        "total_revenue": float(total_revenue),
        "total_cost": float(total_cost),
        "gross_profit": float(gross_profit)
    })


@reports_bp.route("/sales", methods=["GET"])
@login_required
@role_required("admin", "business owner")
def get_sales_report():
    """List all sales orders as historical sales activities."""
    orders = SalesOrder.query.order_by(SalesOrder.created_at.desc()).all()
    result = []
    for o in orders:
        result.append({
            "id": o.id,
            "customer": o.customer.name if o.customer else "Unknown",
            "date": o.order_date.isoformat() if o.order_date else None,
            "total": float(o.total_amount or 0),
            "status": o.status
        })
    return jsonify(result)


@reports_bp.route("/purchase", methods=["GET"])
@login_required
@role_required("admin", "business owner")
def get_purchase_report():
    """List all purchase orders as operational procurement logs."""
    orders = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()
    result = []
    for o in orders:
        result.append({
            "id": o.id,
            "vendor": o.vendor.name if o.vendor else "Unknown",
            "date": o.order_date.isoformat() if o.order_date else None,
            "total": float(o.total_amount or 0),
            "status": o.status
        })
    return jsonify(result)


@reports_bp.route("/inventory", methods=["GET"])
@login_required
@role_required("admin", "business owner")
def get_inventory_report():
    """List all products with stock quantity levels and valuation."""
    products = Product.query.order_by(Product.name).all()
    result = []
    for p in products:
        on_hand = float(p.on_hand_qty or 0)
        cost_price = float(p.cost_price or 0)
        result.append({
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "on_hand": on_hand,
            "reserved": float(p.reserved_qty or 0),
            "free": float(p.free_to_use_qty or 0),
            "value": on_hand * cost_price
        })
    return jsonify(result)


@reports_bp.route("/manufacturing", methods=["GET"])
@login_required
@role_required("admin", "business owner")
def get_manufacturing_report():
    """List all manufacturing orders as production activity log."""
    orders = ManufacturingOrder.query.order_by(ManufacturingOrder.created_at.desc()).all()
    result = []
    for o in orders:
        result.append({
            "id": o.id,
            "product": o.product.name if o.product else "Unknown",
            "quantity": float(o.quantity or 0),
            "date": o.created_at.isoformat() if o.created_at else None,
            "status": o.status
        })
    return jsonify(result)


@reports_bp.route("/low-stock", methods=["GET"])
@login_required
@role_required("admin", "business owner")
def get_low_stock_report():
    """List all products where free stock levels are below 5 units."""
    products = Product.query.all()
    result = []
    for p in products:
        free = float(p.free_to_use_qty or 0)
        if free < 5:
            result.append({
                "sku": p.sku,
                "name": p.name,
                "on_hand": float(p.on_hand_qty or 0),
                "reserved": float(p.reserved_qty or 0),
                "free": free
            })
    return jsonify(result)
