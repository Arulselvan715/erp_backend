"""Manufacturing routes — BoM management + Manufacturing Order lifecycle.

Manufacturing Order states:
    draft → confirmed → in_progress → done  (or → cancelled)

Business logic:
- **Confirm**: reserve component stock per BoM lines × MO quantity.
- **Progress**: start work orders, track status.
- **Complete**: increase finished-goods ``on_hand_qty``, decrease
  component ``on_hand_qty`` and ``reserved_qty``, write StockLedger entries.
"""

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import login_required, current_user

from models import (
    db,
    Product,
    BillOfMaterials,
    BomLine,
    BomOperation,
    ManufacturingOrder,
    WorkOrder,
)
from models.inventory import log_stock_movement
from models.audit import log_audit
from routes.utils import role_required

manufacturing_bp = Blueprint("manufacturing", __name__, url_prefix="/manufacturing")


# ==================================================================
# Bill of Materials — list & view (creation via products blueprint)
# ==================================================================

@manufacturing_bp.route("/boms")
@login_required
def list_boms():
    boms = BillOfMaterials.query.order_by(BillOfMaterials.name).all()
    return render_template("manufacturing/bom_list.html", boms=boms)


@manufacturing_bp.route("/boms/<int:bom_id>")
@login_required
def view_bom(bom_id):
    bom = BillOfMaterials.query.get_or_404(bom_id)
    return render_template("manufacturing/bom_view.html", bom=bom)


# ==================================================================
# Manufacturing Orders
# ==================================================================

# ------------------------------------------------------------------
# List & Create REST Endpoint
# ------------------------------------------------------------------
@manufacturing_bp.route("/", methods=["GET", "POST"])
@login_required
def list_orders():
    if request.method == "POST":
        return create()

    status_filter = request.args.get("status", "").strip()
    query = ManufacturingOrder.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    orders = query.order_by(ManufacturingOrder.created_at.desc()).all()
    return render_template(
        "manufacturing/list.html", orders=orders, status_filter=status_filter,
    )


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------
@manufacturing_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager", "production")
def create():
    # Only show products that have a BoM
    products = (
        Product.query.filter(Product.boms.any())
        .order_by(Product.name)
        .all()
    )

    if request.method == "POST":
        data = request.get_json() if request.is_json else None
        
        if data:
            product_id = data.get("product_id")
            if product_id:
                product_id = int(product_id)
            quantity = float(data.get("quantity") or 0.0)
            assigned_to = data.get("assigned_to")
            
            if not product_id or quantity <= 0:
                return jsonify({"error": "Select a product and enter a valid quantity."}), 400
                
            product = Product.query.get_or_404(product_id)
            if product.bom_id is None:
                return jsonify({"error": f"Product '{product.name}' has no Bill of Materials."}), 400
                
            bom = BillOfMaterials.query.get(product.bom_id)
            
            mo = ManufacturingOrder(
                product_id=product.id,
                bom_id=bom.id,
                quantity=quantity,
                status="draft",
            )
            if assigned_to:
                mo.user_id = int(assigned_to)
                
            db.session.add(mo)
            db.session.flush()
            
            for op in bom.operations.all():
                wo = WorkOrder(
                    manufacturing_order_id=mo.id,
                    bom_operation_id=op.id,
                    sequence=op.sequence,
                    planned_duration_min=op.duration_minutes,
                    status="pending",
                )
                db.session.add(wo)
                
            db.session.commit()
            
            log_audit(
                current_user.id, "CREATE", "ManufacturingOrder", mo.id,
                None,
                {"product_id": product.id, "bom_id": bom.id, "quantity": quantity},
                f"Created Manufacturing Order #{mo.id} for {quantity} × {product.name}",
            )
            return jsonify({
                "message": f"Manufacturing Order #{mo.id} created.",
                "id": mo.id
            }), 201

        else:
            product_id = request.form.get("product_id", type=int)
            quantity = request.form.get("quantity", type=float) or 0

            if not product_id or quantity <= 0:
                flash("Select a product and enter a valid quantity.", "warning")
                return render_template("manufacturing/form.html", products=products, order=None)

            product = Product.query.get_or_404(product_id)
            if product.bom_id is None:
                flash(f"Product '{product.name}' has no Bill of Materials.", "danger")
                return render_template("manufacturing/form.html", products=products, order=None)

            bom = BillOfMaterials.query.get(product.bom_id)

            mo = ManufacturingOrder(
                product_id=product.id,
                bom_id=bom.id,
                quantity=quantity,
                status="draft",
            )
            db.session.add(mo)
            db.session.flush()

            # Pre-create work orders from BoM operations
            for op in bom.operations.all():
                wo = WorkOrder(
                    manufacturing_order_id=mo.id,
                    bom_operation_id=op.id,
                    sequence=op.sequence,
                    planned_duration_min=op.duration_minutes,
                    status="pending",
                )
                db.session.add(wo)

            db.session.commit()

            log_audit(
                current_user.id, "CREATE", "ManufacturingOrder", mo.id,
                None,
                {"product_id": product.id, "bom_id": bom.id, "quantity": quantity},
                f"Created Manufacturing Order #{mo.id} for {quantity} × {product.name}",
            )
            flash(f"Manufacturing Order #{mo.id} created.", "success")
            return redirect(url_for("manufacturing.view", order_id=mo.id))

    return render_template("manufacturing/form.html", products=products, order=None)


# ------------------------------------------------------------------
# View
# ------------------------------------------------------------------
@manufacturing_bp.route("/<int:order_id>")
@login_required
def view(order_id):
    order = ManufacturingOrder.query.get_or_404(order_id)
    if request.is_json:
        from routes.utils import serialize
        return jsonify(serialize(order))
    bom = BillOfMaterials.query.get(order.bom_id)
    return render_template("manufacturing/view.html", order=order, bom=bom)


# ------------------------------------------------------------------
# Confirm — reserve components
# ------------------------------------------------------------------
@manufacturing_bp.route("/<int:order_id>/confirm", methods=["POST"])
@login_required
@role_required("admin", "manager", "production")
def confirm(order_id):
    mo = ManufacturingOrder.query.get_or_404(order_id)
    if mo.status != "draft":
        if request.is_json:
            return jsonify({"error": "Only draft manufacturing orders can be confirmed."}), 400
        flash("Only draft manufacturing orders can be confirmed.", "warning")
        return redirect(url_for("manufacturing.view", order_id=mo.id))

    bom = BillOfMaterials.query.get(mo.bom_id)
    if bom is None:
        if request.is_json:
            return jsonify({"error": "BoM not found. Cannot confirm."}), 400
        flash("BoM not found. Cannot confirm.", "danger")
        return redirect(url_for("manufacturing.view", order_id=mo.id))

    # Check component availability and reserve
    shortage_products = []
    for bom_line in bom.lines.all():
        component = Product.query.get(bom_line.component_id)
        if component is None:
            continue

        required = bom_line.quantity * mo.quantity
        free = component.free_to_use_qty

        if free < required:
            shortage_products.append(
                f"'{component.name}': need {required}, free {free}"
            )
        else:
            component.reserved_qty += required
            log_stock_movement(
                component.id, 0, "ManufacturingOrder", mo.id,
                f"Reserved {required} units of '{component.name}' for MO#{mo.id}",
            )

    if shortage_products:
        db.session.rollback()
        err_msg = "Insufficient component stock: " + "; ".join(shortage_products)
        if request.is_json:
            return jsonify({"error": err_msg}), 400
        flash(err_msg, "danger")
        return redirect(url_for("manufacturing.view", order_id=mo.id))

    mo.status = "confirmed"
    mo.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_audit(
        current_user.id, "CONFIRM", "ManufacturingOrder", mo.id,
        {"status": "draft"}, {"status": "confirmed"},
        f"Confirmed Manufacturing Order #{mo.id}",
    )
    
    if request.is_json:
        from routes.utils import serialize
        return jsonify(serialize(mo))

    flash(f"Manufacturing Order #{mo.id} confirmed — components reserved.", "success")
    return redirect(url_for("manufacturing.view", order_id=mo.id))


# ------------------------------------------------------------------
# Start / Progress — move to in_progress, manage work orders
# ------------------------------------------------------------------
@manufacturing_bp.route("/<int:order_id>/start", methods=["POST"])
@login_required
@role_required("admin", "manager", "production")
def start(order_id):
    mo = ManufacturingOrder.query.get_or_404(order_id)
    if mo.status != "confirmed":
        if request.is_json:
            return jsonify({"error": "Only confirmed orders can be started."}), 400
        flash("Only confirmed orders can be started.", "warning")
        return redirect(url_for("manufacturing.view", order_id=mo.id))

    mo.status = "in_progress"
    mo.updated_at = datetime.now(timezone.utc)

    # Start the first work order
    first_wo = (
        WorkOrder.query.filter_by(manufacturing_order_id=mo.id)
        .order_by(WorkOrder.sequence)
        .first()
    )
    if first_wo:
        first_wo.status = "in_progress"
        first_wo.started_at = datetime.now(timezone.utc)

    db.session.commit()

    log_audit(
        current_user.id, "START", "ManufacturingOrder", mo.id,
        {"status": "confirmed"}, {"status": "in_progress"},
        f"Started Manufacturing Order #{mo.id}",
    )
    
    if request.is_json:
        from routes.utils import serialize
        return jsonify(serialize(mo))

    flash(f"Manufacturing Order #{mo.id} started.", "success")
    return redirect(url_for("manufacturing.view", order_id=mo.id))


# ------------------------------------------------------------------
# Progress Work Order — complete current WO, start next
# ------------------------------------------------------------------
@manufacturing_bp.route("/<int:order_id>/wo/<int:wo_id>/complete", methods=["POST"])
@login_required
@role_required("admin", "manager", "production")
def complete_work_order(order_id, wo_id):
    mo = ManufacturingOrder.query.get_or_404(order_id)
    wo = WorkOrder.query.get_or_404(wo_id)

    if wo.manufacturing_order_id != mo.id:
        flash("Work order does not belong to this manufacturing order.", "danger")
        return redirect(url_for("manufacturing.view", order_id=mo.id))

    if wo.status != "in_progress":
        flash("Only in-progress work orders can be completed.", "warning")
        return redirect(url_for("manufacturing.view", order_id=mo.id))

    wo.status = "done"
    wo.completed_at = datetime.now(timezone.utc)

    # Auto-start the next work order in sequence
    next_wo = (
        WorkOrder.query.filter_by(manufacturing_order_id=mo.id, status="pending")
        .order_by(WorkOrder.sequence)
        .first()
    )
    if next_wo:
        next_wo.status = "in_progress"
        next_wo.started_at = datetime.now(timezone.utc)

    db.session.commit()

    log_audit(
        current_user.id, "PROGRESS", "WorkOrder", wo.id,
        {"status": "in_progress"}, {"status": "done"},
        f"Completed work order '{wo.operation_name}' for MO#{mo.id}",
    )
    flash(f"Work order '{wo.operation_name}' completed.", "success")
    return redirect(url_for("manufacturing.view", order_id=mo.id))


# ------------------------------------------------------------------
# Update Work Order REST API Endpoint (PUT)
# ------------------------------------------------------------------
@manufacturing_bp.route("/work-orders/<int:wo_id>", methods=["PUT"])
@login_required
@role_required("admin", "manager", "production")
def update_work_order(wo_id):
    wo = WorkOrder.query.get_or_404(wo_id)
    data = request.get_json() or {}
    
    status = data.get("status")
    
    if status:
        wo.status = status
        if status == "in_progress" and not wo.started_at:
            wo.started_at = datetime.now(timezone.utc)
        elif status == "done" and not wo.finished_at:
            wo.finished_at = datetime.now(timezone.utc)
            
            # Auto-start the next work order in sequence
            mo = wo.manufacturing_order
            next_wo = (
                WorkOrder.query.filter_by(manufacturing_order_id=mo.id, status="pending")
                .order_by(WorkOrder.sequence)
                .first()
            )
            if next_wo:
                next_wo.status = "in_progress"
                next_wo.started_at = datetime.now(timezone.utc)
                
    db.session.commit()
    return jsonify({"message": f"Work order {wo_id} updated."}), 200


# ------------------------------------------------------------------
# Complete MO — produce finished goods, consume components
# ------------------------------------------------------------------
@manufacturing_bp.route("/<int:order_id>/complete", methods=["POST"])
@login_required
@role_required("admin", "manager", "production")
def complete(order_id):
    mo = ManufacturingOrder.query.get_or_404(order_id)
    if mo.status != "in_progress":
        if request.is_json:
            return jsonify({"error": "Only in-progress orders can be completed."}), 400
        flash("Only in-progress orders can be completed.", "warning")
        return redirect(url_for("manufacturing.view", order_id=mo.id))

    # Ensure all work orders are done
    pending_wos = WorkOrder.query.filter(
        WorkOrder.manufacturing_order_id == mo.id,
        WorkOrder.status != "done",
    ).count()
    if pending_wos > 0:
        err_msg = f"Cannot complete: {pending_wos} work order(s) still pending."
        if request.is_json:
            return jsonify({"error": err_msg}), 400
        flash(err_msg, "warning")
        return redirect(url_for("manufacturing.view", order_id=mo.id))

    bom = BillOfMaterials.query.get(mo.bom_id)

    # ── Consume components ───────────────────────────────────────
    for bom_line in bom.lines.all():
        component = Product.query.get(bom_line.component_id)
        if component is None:
            continue
        consumed = bom_line.quantity * mo.quantity
        component.on_hand_qty -= consumed
        component.reserved_qty = max(component.reserved_qty - consumed, 0)

        log_stock_movement(
            component.id, -consumed, "ManufacturingOrder", mo.id,
            f"Consumed {consumed} units of '{component.name}' for MO#{mo.id}",
        )

    # ── Produce finished goods ───────────────────────────────────
    finished = Product.query.get(mo.product_id)
    if finished:
        finished.on_hand_qty += mo.quantity
        log_stock_movement(
            finished.id, mo.quantity, "ManufacturingOrder", mo.id,
            f"Produced {mo.quantity} units of '{finished.name}' from MO#{mo.id}",
        )

    mo.status = "done"
    mo.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_audit(
        current_user.id, "COMPLETE", "ManufacturingOrder", mo.id,
        {"status": "in_progress"}, {"status": "done"},
        f"Completed Manufacturing Order #{mo.id}",
    )
    
    if request.is_json:
        from routes.utils import serialize
        return jsonify(serialize(mo))

    flash(f"Manufacturing Order #{mo.id} completed — {mo.quantity} units produced.", "success")
    return redirect(url_for("manufacturing.view", order_id=mo.id))


# ------------------------------------------------------------------
# Cancel — release reserved components
# ------------------------------------------------------------------
@manufacturing_bp.route("/<int:order_id>/cancel", methods=["POST"])
@login_required
@role_required("admin", "manager", "production")
def cancel(order_id):
    mo = ManufacturingOrder.query.get_or_404(order_id)
    if mo.status in ("done", "cancelled"):
        if request.is_json:
            return jsonify({"error": "Cannot cancel a completed or already-cancelled order."}), 400
        flash("Cannot cancel a completed or already-cancelled order.", "warning")
        return redirect(url_for("manufacturing.view", order_id=mo.id))

    old_status = mo.status

    # Release reserved components if order was confirmed or in progress
    if mo.status in ("confirmed", "in_progress"):
        bom = BillOfMaterials.query.get(mo.bom_id)
        if bom:
            for bom_line in bom.lines.all():
                component = Product.query.get(bom_line.component_id)
                if component is None:
                    continue
                to_release = bom_line.quantity * mo.quantity
                component.reserved_qty = max(component.reserved_qty - to_release, 0)
                log_stock_movement(
                    component.id, 0, "ManufacturingOrder", mo.id,
                    f"Released {to_release} reserved units of '{component.name}' (MO#{mo.id} cancelled)",
                )

    mo.status = "cancelled"
    mo.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_audit(
        current_user.id, "CANCEL", "ManufacturingOrder", mo.id,
        {"status": old_status}, {"status": "cancelled"},
        f"Cancelled Manufacturing Order #{mo.id}",
    )
    
    if request.is_json:
        from routes.utils import serialize
        return jsonify(serialize(mo))

    flash(f"Manufacturing Order #{mo.id} cancelled.", "success")
    return redirect(url_for("manufacturing.view", order_id=mo.id))


@manufacturing_bp.route("/work-orders", methods=["GET"])
@manufacturing_bp.route("/work-orders/", methods=["GET"])
@login_required
def list_work_orders():
    """List all work orders in the system."""
    status_filter = request.args.get("status", "").strip()
    query = WorkOrder.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    orders = query.order_by(WorkOrder.sequence, WorkOrder.id.desc()).all()
    
    from routes.utils import serialize
    return jsonify({
        "data": [serialize(wo) for wo in orders],
        "total": len(orders)
    })
