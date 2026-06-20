"""Bill of Materials CRUD REST endpoints."""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from models import db, Product, BillOfMaterials, BomLine, BomOperation
from models.audit import log_audit
from routes.utils import role_required, is_json_request

bom_bp = Blueprint("bom", __name__, url_prefix="/bom")


@bom_bp.route("/", methods=["GET"])
@login_required
def list_boms():
    """List all Bills of Materials with details."""
    boms = BillOfMaterials.query.all()
    data = []
    for bom in boms:
        data.append({
            "id": bom.id,
            "product_id": bom.product_id,
            "product_name": bom.product.name if bom.product else "Unknown",
            "name": bom.name,
            "version": bom.version,
            "is_active": bom.is_active,
            "components": [{
                "id": line.id,
                "component_id": line.component_id,
                "component_sku": line.component.sku if line.component else "Unknown",
                "component_name": line.component.name if line.component else "Unknown",
                "quantity": float(line.quantity)
            } for line in bom.lines.all()],
            "operations": [{
                "id": op.id,
                "sequence": op.sequence,
                "operation_name": op.name,
                "work_center": op.work_center,
                "duration_minutes": float(op.duration_minutes)
            } for op in bom.operations.all()]
        })
    return jsonify({
        "data": data,
        "total": len(data)
    })


@bom_bp.route("/<int:bom_id>", methods=["GET"])
@login_required
def get_bom(bom_id):
    """Retrieve detailed information of a single BoM."""
    bom = BillOfMaterials.query.get_or_404(bom_id)
    return jsonify({
        "id": bom.id,
        "product_id": bom.product_id,
        "product_name": bom.product.name if bom.product else "Unknown",
        "name": bom.name,
        "version": bom.version,
        "is_active": bom.is_active,
        "components": [{
            "id": line.id,
            "component_id": line.component_id,
            "component_sku": line.component.sku if line.component else "Unknown",
            "component_name": line.component.name if line.component else "Unknown",
            "quantity": float(line.quantity)
        } for line in bom.lines.all()],
        "operations": [{
            "id": op.id,
            "sequence": op.sequence,
            "operation_name": op.name,
            "work_center": op.work_center,
            "duration_minutes": float(op.duration_minutes)
        } for op in bom.operations.all()]
    })


@bom_bp.route("/", methods=["POST"])
@login_required
@role_required("admin", "manager")
def create_bom():
    """Create or update in-place a Bill of Materials."""
    data = request.get_json() or {}
    product_id = data.get("product_id")
    components = data.get("components", [])
    operations = data.get("operations", [])
    
    if not product_id or not components:
        return jsonify({"error": "Product and at least one component are required."}), 400
        
    product = Product.query.get_or_404(product_id)
    
    # Check if a BoM already exists for this product
    existing_bom = BillOfMaterials.query.filter_by(product_id=product_id).first()
    if existing_bom:
        # Delete old lines and operations to perform update in-place
        BomLine.query.filter_by(bom_id=existing_bom.id).delete()
        BomOperation.query.filter_by(bom_id=existing_bom.id).delete()
        bom = existing_bom
        bom.name = f"BoM - {product.name}"
    else:
        bom = BillOfMaterials(
            product_id=product_id,
            name=f"BoM - {product.name}",
            version="1.0",
            is_active=True
        )
        db.session.add(bom)
        db.session.flush()
    
    for c in components:
        line = BomLine(
            bom_id=bom.id,
            component_id=int(c.get("component_product_id")),
            quantity=float(c.get("quantity"))
        )
        db.session.add(line)
        
    for op in operations:
        operation = BomOperation(
            bom_id=bom.id,
            sequence=int(op.get("sequence") or 1),
            name=op.get("operation_name"),
            work_center=op.get("work_center") or "Assembly Unit",
            duration_minutes=float(op.get("duration_minutes") or 0)
        )
        db.session.add(operation)
        
    db.session.commit()
    
    log_audit(
        current_user.id, "CREATE" if not existing_bom else "UPDATE", "BillOfMaterials", bom.id,
        None,
        {"product_id": product_id, "components_count": len(components)},
        f"Created/Updated Bill of Materials for product '{product.name}'"
    )
    
    return jsonify({
        "message": f"Bill of Materials for '{product.name}' saved.",
        "id": bom.id
    }), 201


@bom_bp.route("/<int:bom_id>", methods=["DELETE"])
@login_required
@role_required("admin", "manager")
def delete_bom(bom_id):
    """Delete a Bill of Materials (soft-deactivates if in use)."""
    bom = BillOfMaterials.query.get_or_404(bom_id)
    product_name = bom.product.name if bom.product else "Unknown"
    
    # Check if there are any manufacturing orders using this BoM
    has_orders = bom.manufacturing_orders.count() > 0
    
    if has_orders:
        bom.is_active = False
        db.session.commit()
        log_audit(
            current_user.id, "DEACTIVATE", "BillOfMaterials", bom.id,
            {"is_active": True}, {"is_active": False},
            f"Deactivated Bill of Materials for '{product_name}' (in use)"
        )
        return jsonify({"message": f"Bill of Materials for '{product_name}' is in use, so it was deactivated."}), 200
        
    db.session.delete(bom)
    db.session.commit()
    log_audit(
        current_user.id, "DELETE", "BillOfMaterials", bom.id,
        {"name": bom.name}, None,
        f"Deleted Bill of Materials for '{product_name}'"
    )
    return jsonify({"message": f"Bill of Materials for '{product_name}' deleted."}), 200
