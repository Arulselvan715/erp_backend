"""Inventory routes — stock levels, stock ledger history, manual adjustments."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from models import db, Product, StockLedger
from models.inventory import log_stock_movement
from models.audit import log_audit
from routes.utils import role_required

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


# ------------------------------------------------------------------
# Stock Levels overview
# ------------------------------------------------------------------
@inventory_bp.route("/")
@login_required
def stock_levels():
    """Show all products with on-hand, reserved, and free-to-use quantities."""
    q = request.args.get("q", "").strip()
    query = Product.query
    if q:
        query = query.filter(
            Product.name.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%")
        )
    products = query.order_by(Product.name).all()
    return render_template("inventory/stock_levels.html", products=products, q=q)


# ------------------------------------------------------------------
# Stock Ledger — full history
# ------------------------------------------------------------------
@inventory_bp.route("/ledger")
@login_required
def ledger():
    """Chronological list of all stock movements."""
    product_id = request.args.get("product_id", type=int)
    ref_type = request.args.get("ref_type", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 50

    query = StockLedger.query

    if product_id:
        query = query.filter_by(product_id=product_id)
    if ref_type:
        query = query.filter_by(reference_type=ref_type)

    pagination = (
        query.order_by(StockLedger.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    products = Product.query.order_by(Product.name).all()

    return render_template(
        "inventory/ledger.html",
        entries=pagination.items,
        pagination=pagination,
        products=products,
        selected_product_id=product_id,
        selected_ref_type=ref_type,
    )


# ------------------------------------------------------------------
# Product stock-ledger detail
# ------------------------------------------------------------------
@inventory_bp.route("/product/<int:product_id>")
@login_required
def product_detail(product_id):
    """Show stock card / ledger for a single product."""
    product = Product.query.get_or_404(product_id)
    entries = (
        StockLedger.query.filter_by(product_id=product.id)
        .order_by(StockLedger.created_at.desc())
        .limit(200)
        .all()
    )
    return render_template(
        "inventory/product_detail.html",
        product=product,
        entries=entries,
    )


# ------------------------------------------------------------------
# Manual Adjustment
# ------------------------------------------------------------------
@inventory_bp.route("/adjust", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager", "warehouse")
def adjust():
    """Create a manual stock adjustment (positive or negative)."""
    products = Product.query.order_by(Product.name).all()

    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        qty_change = request.form.get("qty_change", type=float)
        reason = request.form.get("reason", "").strip()

        if not product_id or qty_change is None:
            flash("Product and quantity change are required.", "warning")
            return render_template("inventory/adjust.html", products=products)

        product = Product.query.get_or_404(product_id)

        if not reason:
            reason = "Manual stock adjustment"

        old_qty = product.on_hand_qty
        product.on_hand_qty += qty_change

        # Prevent negative stock (optional guard)
        if product.on_hand_qty < 0:
            flash(
                f"Adjustment would result in negative stock ({product.on_hand_qty}). "
                f"Current on-hand: {old_qty}.",
                "danger",
            )
            db.session.rollback()
            return render_template("inventory/adjust.html", products=products)

        log_stock_movement(
            product.id, qty_change, "ManualAdjustment", 0,
            f"{reason} (by {current_user.username})",
        )

        log_audit(
            current_user.id, "ADJUST", "Product", product.id,
            {"on_hand_qty": old_qty},
            {"on_hand_qty": product.on_hand_qty, "qty_change": qty_change},
            f"Manual adjustment on '{product.name}': {'+' if qty_change >= 0 else ''}{qty_change} ({reason})",
        )

        db.session.commit()
        flash(
            f"Adjusted '{product.name}' by {'+' if qty_change >= 0 else ''}{qty_change}. "
            f"New on-hand: {product.on_hand_qty}.",
            "success",
        )
        return redirect(url_for("inventory.stock_levels"))

    return render_template("inventory/adjust.html", products=products)
