"""Purchase Order routes — create / confirm / receive.

Business logic:
- **Confirm**: moves PO to ``confirmed`` status (vendor notified conceptually).
- **Receive**: increases ``on_hand_qty`` for each line, creates StockLedger
  entries, and marks lines as received.
"""

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
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
# List & Create REST Endpoint
# ------------------------------------------------------------------
@purchase_bp.route("/", methods=["GET", "POST"])
@login_required
def list_orders():
    if request.method == "POST":
        return create()

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
        data = request.get_json() if request.is_json else None
        
        if data:
            vendor_id = data.get("vendor_id")
            if vendor_id:
                vendor_id = int(vendor_id)
            items = data.get("items", [])
            
            if not vendor_id:
                return jsonify({"error": "Please select a vendor."}), 400
            if not items:
                return jsonify({"error": "Add at least one product line."}), 400
                
            po = PurchaseOrder(vendor_id=vendor_id, status="draft", total_amount=0)
            db.session.add(po)
            db.session.flush()
            
            total = 0.0
            for item in items:
                pid = int(item.get("product_id") or 0)
                qty = float(item.get("quantity") or 0)
                price = float(item.get("price") or 0)
                
                product = Product.query.get(pid)
                if product is None or qty <= 0:
                    continue
                if not price:
                    price = product.cost_price or 0
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
            return jsonify({
                "message": f"Purchase Order #{po.id} created.",
                "id": po.id
            }), 201
            
        else:
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
        if request.is_json:
            return jsonify({"error": "Only draft purchase orders can be confirmed."}), 400
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
    if request.is_json:
        return jsonify({"message": f"Purchase Order #{po.id} confirmed."}), 200

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
    if po.status not in ("confirmed", "partially_received"):
        if request.is_json:
            return jsonify({"error": "Only confirmed purchase orders can be received."}), 400
        flash("Only confirmed purchase orders can be received.", "warning")
        return redirect(url_for("purchase.view", order_id=po.id))

    if request.method == "POST":
        if request.is_json:
            receipts = request.get_json() or []
            # Validate first
            for item in receipts:
                item_id = int(item.get("item_id") or 0)
                qty = float(item.get("quantity") or 0)
                if qty <= 0:
                    continue
                line = PurchaseOrderLine.query.get(item_id)
                if not line or line.purchase_order_id != po.id:
                    return jsonify({"error": f"Invalid line item ID {item_id}"}), 400

            # Process receipts
            any_received = False
            for item in receipts:
                item_id = int(item.get("item_id") or 0)
                qty = float(item.get("quantity") or 0)
                if qty <= 0:
                    continue
                line = PurchaseOrderLine.query.get(item_id)
                product = Product.query.get(line.product_id)
                
                remaining = line.quantity - line.received_qty
                qty = min(qty, remaining)
                if qty <= 0:
                    continue
                    
                if product:
                    product.on_hand_qty += qty
                line.received_qty += qty
                any_received = True

                log_stock_movement(
                    line.product_id, qty, "PurchaseOrder", po.id,
                    f"Received {qty} units from PO#{po.id}",
                )

            # Update status
            all_received = all(line.received_qty >= line.quantity for line in po.lines.all())
            if all_received:
                po.status = "received"
            elif any_received:
                po.status = "partially_received"
                
            po.updated_at = datetime.now(timezone.utc)
            db.session.commit()

            log_audit(
                current_user.id, "RECEIVE", "PurchaseOrder", po.id,
                {"status": "confirmed"}, {"status": po.status},
                f"Received goods for Purchase Order #{po.id}",
            )
            return jsonify({"message": f"Purchase Order #{po.id} receipt processed."}), 200

        else:
            all_received = True
            received_lines = request.form.getlist("received_qty")

            for line, recv_str in zip(po.lines.all(), received_lines):
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
