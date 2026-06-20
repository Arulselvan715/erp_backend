"""Purchase Order routes — create / confirm / receive.

Business logic:
- **Confirm**: moves PO to ``confirmed`` status (vendor notified conceptually).
- **Receive**: increases ``on_hand_qty`` for each line, creates StockLedger
  entries, and marks lines as received.
"""

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from models import (
    db,
    Product,
    Vendor,
    PurchaseOrder,
    PurchaseOrderLine,
)
from models.inventory import log_stock_movement
from models.audit import log_audit
from routes.utils import role_required

purchase_bp = Blueprint("purchase", __name__, url_prefix="/purchase")


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------
@purchase_bp.route("/")
@login_required
def list_orders():
    status_filter = request.args.get("status", "").strip()
    query = PurchaseOrder.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    orders = query.order_by(PurchaseOrder.created_at.desc()).all()
    return render_template("purchase/list.html", orders=orders, status_filter=status_filter)


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------
@purchase_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager", "purchasing")
def create():
    vendors = Vendor.query.order_by(Vendor.name).all()
    products = Product.query.order_by(Product.name).all()

    if request.method == "POST":
        vendor_id = request.form.get("vendor_id", type=int)
        if not vendor_id:
            flash("Please select a vendor.", "warning")
            return render_template("purchase/form.html", vendors=vendors, products=products, order=None)

        product_ids = request.form.getlist("product_id")
        quantities = request.form.getlist("quantity")
        unit_prices = request.form.getlist("unit_price")

        if not product_ids:
            flash("Add at least one product line.", "warning")
            return render_template("purchase/form.html", vendors=vendors, products=products, order=None)

        po = PurchaseOrder(vendor_id=vendor_id, status="draft", total_amount=0)
        db.session.add(po)
        db.session.flush()

        total = 0.0
        for pid, qty, price in zip(product_ids, quantities, unit_prices):
            pid = int(pid)
            qty = float(qty) if qty else 0
            product = Product.query.get(pid)
            if product is None or qty <= 0:
                continue
            price = float(price) if price else product.cost_price or 0
            line_total = qty * price
            line = PurchaseOrderLine(
                purchase_order_id=po.id,
                product_id=pid,
                quantity=qty,
                received_qty=0,
                unit_price=price,
                line_total=line_total,
            )
            db.session.add(line)
            total += line_total

        po.total_amount = total
        db.session.commit()

        log_audit(
            current_user.id, "CREATE", "PurchaseOrder", po.id,
            None,
            {"vendor_id": vendor_id, "total": total},
            f"Created Purchase Order #{po.id}",
        )
        flash(f"Purchase Order #{po.id} created.", "success")
        return redirect(url_for("purchase.view", order_id=po.id))

    return render_template("purchase/form.html", vendors=vendors, products=products, order=None)


# ------------------------------------------------------------------
# View
# ------------------------------------------------------------------
@purchase_bp.route("/<int:order_id>")
@login_required
def view(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    return render_template("purchase/view.html", order=order)


# ------------------------------------------------------------------
# Confirm
# ------------------------------------------------------------------
@purchase_bp.route("/<int:order_id>/confirm", methods=["POST"])
@login_required
@role_required("admin", "manager", "purchasing")
def confirm(order_id):
    po = PurchaseOrder.query.get_or_404(order_id)
    if po.status != "draft":
        flash("Only draft purchase orders can be confirmed.", "warning")
        return redirect(url_for("purchase.view", order_id=po.id))

    po.status = "confirmed"
    po.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_audit(
        current_user.id, "CONFIRM", "PurchaseOrder", po.id,
        {"status": "draft"}, {"status": "confirmed"},
        f"Confirmed Purchase Order #{po.id}",
    )
    flash(f"Purchase Order #{po.id} confirmed.", "success")
    return redirect(url_for("purchase.view", order_id=po.id))


# ------------------------------------------------------------------
# Receive — increase on_hand, create stock ledger entries
# ------------------------------------------------------------------
@purchase_bp.route("/<int:order_id>/receive", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager", "purchasing", "warehouse")
def receive(order_id):
    po = PurchaseOrder.query.get_or_404(order_id)
    if po.status not in ("confirmed",):
        flash("Only confirmed purchase orders can be received.", "warning")
        return redirect(url_for("purchase.view", order_id=po.id))

    if request.method == "POST":
        all_received = True
        received_lines = request.form.getlist("received_qty")

        for line, recv_str in zip(po.lines, received_lines):
            recv_qty = float(recv_str) if recv_str else 0
            if recv_qty <= 0:
                if line.received_qty < line.quantity:
                    all_received = False
                continue

            # Cap at remaining
            remaining = line.quantity - line.received_qty
            recv_qty = min(recv_qty, remaining)

            product = Product.query.get(line.product_id)
            if product is None:
                continue

            product.on_hand_qty += recv_qty
            line.received_qty += recv_qty

            log_stock_movement(
                product.id, recv_qty, "PurchaseOrder", po.id,
                f"Received {recv_qty} units from PO#{po.id}",
            )

            if line.received_qty < line.quantity:
                all_received = False

        if all_received:
            po.status = "received"
        po.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_audit(
            current_user.id, "RECEIVE", "PurchaseOrder", po.id,
            {"status": "confirmed"}, {"status": po.status},
            f"Received goods for Purchase Order #{po.id}",
        )
        flash(f"Purchase Order #{po.id} receipt processed.", "success")
        return redirect(url_for("purchase.view", order_id=po.id))

    return render_template("purchase/receive.html", order=po)
