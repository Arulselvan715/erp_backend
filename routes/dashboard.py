"""Dashboard route — summary statistics and alerts."""

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from models import (
    db,
    Product,
    SalesOrder,
    PurchaseOrder,
    ManufacturingOrder,
    Customer,
    Vendor,
    StockLedger,
    AuditLog,
)
from routes.utils import role_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/debug/db")
def debug_db():
    import os
    from flask import current_app, jsonify
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(uri)
        if parsed.password:
            netloc = f"{parsed.username}:*****@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            uri = parsed._replace(netloc=netloc).geturl()
    except Exception as e:
        uri = f"Error parsing URI: {e}"
    return jsonify({
        "database_uri": uri,
        "env": os.environ.get("FLASK_ENV", "not set")
    })


@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
@login_required
def index():
    """Render the main dashboard with KPI cards and alerts."""

    # ── Order counts by status ───────────────────────────────────
    so_counts = (
        db.session.query(SalesOrder.status, db.func.count(SalesOrder.id))
        .group_by(SalesOrder.status)
        .all()
    )
    so_stats = dict(so_counts)

    po_counts = (
        db.session.query(PurchaseOrder.status, db.func.count(PurchaseOrder.id))
        .group_by(PurchaseOrder.status)
        .all()
    )
    po_stats = dict(po_counts)

    mo_counts = (
        db.session.query(ManufacturingOrder.status, db.func.count(ManufacturingOrder.id))
        .group_by(ManufacturingOrder.status)
        .all()
    )
    mo_stats = dict(mo_counts)

    # ── Totals ───────────────────────────────────────────────────
    total_products = Product.query.count()
    total_customers = Customer.query.count()
    total_vendors = Vendor.query.count()

    # ── Pending deliveries (confirmed SOs not yet delivered) ─────
    pending_deliveries = SalesOrder.query.filter(
        SalesOrder.status.in_(["confirmed"])
    ).count()

    # ── Alerts: low-stock products (free-to-use < 5) ────────────
    low_stock_products = [
        p for p in Product.query.all() if p.free_to_use_qty < 5
    ]

    # ── Recent stock ledger entries ──────────────────────────────
    recent_ledger = (
        StockLedger.query.order_by(StockLedger.created_at.desc()).limit(10).all()
    )

    return render_template(
        "dashboard/index.html",
        so_stats=so_stats,
        po_stats=po_stats,
        mo_stats=mo_stats,
        total_products=total_products,
        total_customers=total_customers,
        total_vendors=total_vendors,
        pending_deliveries=pending_deliveries,
        low_stock_products=low_stock_products,
        recent_ledger=recent_ledger,
    )


@dashboard_bp.route("/reports")
@login_required
@role_required("admin", "business owner")
def reports():
    """Reports page with audit logs and business summaries."""

    # ── Audit logs (most recent first) ────────────────────────────
    page = 1
    try:
        from flask import request as _req
        page = _req.args.get("page", 1, type=int)
    except Exception:
        pass

    audit_pagination = (
        AuditLog.query.order_by(AuditLog.created_at.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )

    # ── Order totals ──────────────────────────────────────────────
    total_sales = SalesOrder.query.count()
    total_purchases = PurchaseOrder.query.count()
    total_mos = ManufacturingOrder.query.count()
    total_products = Product.query.count()
    total_customers = Customer.query.count()
    total_vendors = Vendor.query.count()

    return render_template(
        "reports.html",
        audit_logs=audit_pagination.items,
        audit_pagination=audit_pagination,
        total_sales=total_sales,
        total_purchases=total_purchases,
        total_mos=total_mos,
        total_products=total_products,
        total_customers=total_customers,
        total_vendors=total_vendors,
    )
