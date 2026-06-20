"""Sales Order routes — create / confirm / deliver / cancel.

Business logic:
- **Confirm**: reserve stock for every SO line. If a product has
  ``procure_on_demand`` enabled and free-to-use stock is insufficient,
  an auto-procurement record (PO or MO) is created.
- **Deliver**: deduct ``on_hand_qty`` and ``reserved_qty``, write
  StockLedger entries.
- **Cancel**: release reserved stock.
"""

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import login_required, current_user

from models import (
    db,
    Product,
    Customer,
    Vendor,
    SalesOrder,
    SalesOrderLine,
    PurchaseOrder,
    PurchaseOrderLine,
    ManufacturingOrder,
    BillOfMaterials,
)
from models.inventory import log_stock_movement
from models.audit import log_audit
from routes.utils import role_required

sales_bp = Blueprint("sales", __name__, url_prefix="/sales")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _auto_procure(product, shortage_qty, so):
    """Create a PO or MO to cover *shortage_qty* of *product*.

    Called automatically when a sales order is confirmed and there is
    not enough free-to-use stock.
    """
    if product.procurement_type in ("manufacture", "manufacturing"):
        bom = BillOfMaterials.query.filter_by(product_id=product.id).first()
        if bom is None:
            flash(
                f"Cannot auto-manufacture '{product.name}': no BoM defined.",
                "warning",
            )
            return
        mo = ManufacturingOrder(
            product_id=product.id,
            bom_id=bom.id,
            quantity=shortage_qty,
            status="draft",
        )
        db.session.add(mo)
        db.session.flush()
        log_audit(
            current_user.id, "CREATE", "ManufacturingOrder", mo.id,
            None, {"product_id": product.id, "qty": shortage_qty},
            f"Auto-created MO#{mo.id} for '{product.name}' (shortage from SO#{so.id})",
        )
        flash(
            f"Auto-created Manufacturing Order #{mo.id} for {shortage_qty} × {product.name}.",
            "info",
        )
    else:
        # Default: buy
        vendor = None
        if product.vendor_id:
            vendor = Vendor.query.get(product.vendor_id)
        if vendor is None:
            vendor = Vendor.query.first()
        if vendor is None:
            flash(
                f"Cannot auto-purchase '{product.name}': no vendor available.",
                "warning",
            )
            return
        po = PurchaseOrder(vendor_id=vendor.id, status="draft", total_amount=0)
        db.session.add(po)
        db.session.flush()
        line = PurchaseOrderLine(
            purchase_order_id=po.id,
            product_id=product.id,
            quantity=shortage_qty,
            received_qty=0,
            unit_price=product.cost_price or 0,
            line_total=(product.cost_price or 0) * shortage_qty,
        )
        db.session.add(line)
        po.total_amount = line.line_total
        db.session.flush()
        log_audit(
            current_user.id, "CREATE", "PurchaseOrder", po.id,
            None, {"vendor_id": vendor.id, "product_id": product.id, "qty": shortage_qty},
            f"Auto-created PO#{po.id} for '{product.name}' (shortage from SO#{so.id})",
        )
        flash(
            f"Auto-created Purchase Order #{po.id} for {shortage_qty} × {product.name}.",
            "info",
        )


# ------------------------------------------------------------------
# List & Create REST Endpoint
# ------------------------------------------------------------------
@sales_bp.route("/", methods=["GET", "POST"])
@login_required
def list_orders():
    if request.method == "POST":
        return create()

    status_filter = request.args.get("status", "").strip()
    query = SalesOrder.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    orders = query.order_by(SalesOrder.created_at.desc()).all()
    return render_template("sales/list.html", orders=orders, status_filter=status_filter)


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------
@sales_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager", "sales")
def create():
    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.order_by(Product.name).all()

    if request.method == "POST":
        data = request.get_json() if request.is_json else None
        
        if data:
            customer_id = data.get("customer_id")
            if customer_id:
                customer_id = int(customer_id)
            items = data.get("items", [])
            
            if not customer_id:
                return jsonify({"error": "Please select a customer."}), 400
            if not items:
                return jsonify({"error": "Add at least one product line."}), 400
                
            so = SalesOrder(customer_id=customer_id, status="draft", total_amount=0)
            db.session.add(so)
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
                    price = product.sales_price or 0
                line_total = qty * price
                line = SalesOrderLine(
                    order_id=so.id,
                    product_id=pid,
                    quantity=qty,
                    delivered_qty=0,
                    unit_price=price,
                    line_total=line_total,
                )
                db.session.add(line)
                total += line_total
                
            so.total_amount = total
            db.session.commit()
            
            log_audit(
                current_user.id, "CREATE", "SalesOrder", so.id,
                None,
                {"customer_id": customer_id, "total": total},
                f"Created Sales Order #{so.id}",
            )
            return jsonify({
                "message": f"Sales Order #{so.id} created.",
                "id": so.id
            }), 201
            
        else:
            customer_id = request.form.get("customer_id", type=int)
            if not customer_id:
                flash("Please select a customer.", "warning")
                return render_template("sales/form.html", customers=customers, products=products, order=None)

            product_ids = request.form.getlist("product_id")
            quantities = request.form.getlist("quantity")
            unit_prices = request.form.getlist("unit_price")

            if not product_ids:
                flash("Add at least one product line.", "warning")
                return render_template("sales/form.html", customers=customers, products=products, order=None)

            so = SalesOrder(customer_id=customer_id, status="draft", total_amount=0)
            db.session.add(so)
            db.session.flush()

            total = 0.0
            for pid, qty, price in zip(product_ids, quantities, unit_prices):
                pid = int(pid)
                qty = float(qty) if qty else 0
                product = Product.query.get(pid)
                if product is None or qty <= 0:
                    continue
                price = float(price) if price else product.sales_price or 0
                line_total = qty * price
                line = SalesOrderLine(
                    order_id=so.id,
                    product_id=pid,
                    quantity=qty,
                    delivered_qty=0,
                    unit_price=price,
                    line_total=line_total,
                )
                db.session.add(line)
                total += line_total

            so.total_amount = total
            db.session.commit()

            log_audit(
                current_user.id, "CREATE", "SalesOrder", so.id,
                None,
                {"customer_id": customer_id, "total": total},
                f"Created Sales Order #{so.id}",
            )
            flash(f"Sales Order #{so.id} created.", "success")
            return redirect(url_for("sales.view", order_id=so.id))

    return render_template("sales/form.html", customers=customers, products=products, order=None)


# ------------------------------------------------------------------
# View
# ------------------------------------------------------------------
@sales_bp.route("/<int:order_id>")
@login_required
def view(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    return render_template("sales/view.html", order=order)


# ------------------------------------------------------------------
# Confirm — reserve stock, trigger auto-procurement if needed
# ------------------------------------------------------------------
@sales_bp.route("/<int:order_id>/confirm", methods=["POST"])
@login_required
@role_required("admin", "manager", "sales")
def confirm(order_id):
    so = SalesOrder.query.get_or_404(order_id)
    if so.status != "draft":
        if request.is_json:
            return jsonify({"error": "Only draft orders can be confirmed."}), 400
        flash("Only draft orders can be confirmed.", "warning")
        return redirect(url_for("sales.view", order_id=so.id))

    for line in so.lines.all():
        product = Product.query.get(line.product_id)
        if product is None:
            continue

        needed = line.quantity
        free = product.free_to_use_qty  # on_hand - reserved

        if free >= needed:
            # Enough stock — reserve it
            product.reserved_qty += needed
        else:
            # Reserve whatever is free
            can_reserve = max(free, 0)
            product.reserved_qty += can_reserve
            shortage = needed - can_reserve

            if product.procure_on_demand and shortage > 0:
                _auto_procure(product, shortage, so)

        log_stock_movement(
            product.id, 0, "SalesOrder", so.id,
            f"Reserved {min(needed, max(free, 0))} units for SO#{so.id}",
        )

    so.status = "confirmed"
    so.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_audit(
        current_user.id, "CONFIRM", "SalesOrder", so.id,
        {"status": "draft"}, {"status": "confirmed"},
        f"Confirmed Sales Order #{so.id}",
    )
    if request.is_json:
        return jsonify({"message": f"Sales Order #{so.id} confirmed."}), 200

    flash(f"Sales Order #{so.id} confirmed.", "success")
    return redirect(url_for("sales.view", order_id=so.id))


# ------------------------------------------------------------------
# Deliver — deduct on_hand and reserved, create stock-ledger entries
# ------------------------------------------------------------------
@sales_bp.route("/<int:order_id>/deliver", methods=["POST"])
@login_required
@role_required("admin", "manager", "sales", "warehouse")
def deliver(order_id):
    so = SalesOrder.query.get_or_404(order_id)
    if so.status not in ("confirmed", "partially_delivered"):
        if request.is_json:
            return jsonify({"error": "Only confirmed or partially delivered orders can be delivered."}), 400
        flash("Only confirmed orders can be delivered.", "warning")
        return redirect(url_for("sales.view", order_id=so.id))

    if request.is_json:
        deliveries = request.get_json() or []
        # Validate first
        for item in deliveries:
            item_id = int(item.get("item_id") or 0)
            qty = float(item.get("quantity") or 0)
            if qty <= 0:
                continue
            line = SalesOrderLine.query.get(item_id)
            if not line or line.order_id != so.id:
                return jsonify({"error": f"Invalid line item ID {item_id}"}), 400
            
            product = Product.query.get(line.product_id)
            if not product:
                continue
            
            if product.on_hand_qty < qty:
                return jsonify({"error": f"Insufficient stock for '{product.name}': need {qty}, have {product.on_hand_qty}."}), 400

        # Process deliveries
        any_delivered = False
        for item in deliveries:
            item_id = int(item.get("item_id") or 0)
            qty = float(item.get("quantity") or 0)
            if qty <= 0:
                continue
            line = SalesOrderLine.query.get(item_id)
            product = Product.query.get(line.product_id)
            
            product.on_hand_qty -= qty
            product.reserved_qty = max(product.reserved_qty - qty, 0)
            line.delivered_qty = float(line.delivered_qty or 0) + qty
            any_delivered = True
            
            log_stock_movement(
                product.id, -qty, "SalesOrder", so.id,
                f"Delivered {qty} units for SO#{so.id}",
            )
            
        # Update status
        all_delivered = all(line.delivered_qty >= line.quantity for line in so.lines.all())
        if all_delivered:
            so.status = "delivered"
        elif any_delivered:
            so.status = "partially_delivered"
            
        so.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        log_audit(
            current_user.id, "DELIVER", "SalesOrder", so.id,
            {"status": "confirmed"}, {"status": so.status},
            f"Delivered Sales Order #{so.id}",
        )
        return jsonify({"message": f"Sales Order #{so.id} delivery processed."}), 200

    else:
        all_delivered = True
        for line in so.lines.all():
            product = Product.query.get(line.product_id)
            if product is None:
                continue

            to_deliver = line.quantity - line.delivered_qty
            if to_deliver <= 0:
                continue

            # Check if enough on-hand to actually ship
            if product.on_hand_qty < to_deliver:
                flash(
                    f"Insufficient stock for '{product.name}': need {to_deliver}, have {product.on_hand_qty}.",
                    "warning",
                )
                all_delivered = False
                continue

            # Deduct inventory
            product.on_hand_qty -= to_deliver
            product.reserved_qty = max(product.reserved_qty - to_deliver, 0)
            line.delivered_qty = line.quantity

            log_stock_movement(
                product.id, -to_deliver, "SalesOrder", so.id,
                f"Delivered {to_deliver} units for SO#{so.id}",
            )

        if all_delivered:
            so.status = "delivered"
        so.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_audit(
            current_user.id, "DELIVER", "SalesOrder", so.id,
            {"status": "confirmed"}, {"status": so.status},
            f"Delivered Sales Order #{so.id}",
        )
        flash(f"Sales Order #{so.id} delivery processed.", "success")
        return redirect(url_for("sales.view", order_id=so.id))


# ------------------------------------------------------------------
# Cancel — release reserved stock
# ------------------------------------------------------------------
@sales_bp.route("/<int:order_id>/cancel", methods=["POST"])
@login_required
@role_required("admin", "manager", "sales")
def cancel(order_id):
    so = SalesOrder.query.get_or_404(order_id)
    if so.status not in ("draft", "confirmed", "partially_delivered"):
        if request.is_json:
            return jsonify({"error": "Cannot cancel this order."}), 400
        flash("Cannot cancel this order.", "warning")
        return redirect(url_for("sales.view", order_id=so.id))

    old_status = so.status

    if so.status in ("confirmed", "partially_delivered"):
        # Release reserved stock
        for line in so.lines.all():
            product = Product.query.get(line.product_id)
            if product is None:
                continue
            to_release = line.quantity - line.delivered_qty
            if to_release > 0:
                product.reserved_qty = max(product.reserved_qty - to_release, 0)
                log_stock_movement(
                    product.id, 0, "SalesOrder", so.id,
                    f"Released {to_release} reserved units (SO#{so.id} cancelled)",
                )

    so.status = "cancelled"
    so.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_audit(
        current_user.id, "CANCEL", "SalesOrder", so.id,
        {"status": old_status}, {"status": "cancelled"},
        f"Cancelled Sales Order #{so.id}",
    )
    if request.is_json:
        return jsonify({"message": f"Sales Order #{so.id} cancelled."}), 200

    flash(f"Sales Order #{so.id} cancelled.", "success")
    return redirect(url_for("sales.view", order_id=so.id))
