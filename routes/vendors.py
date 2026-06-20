"""Vendor CRUD routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import login_required, current_user

from models import db, Vendor
from models.audit import log_audit
from routes.utils import role_required, is_json_request

vendors_bp = Blueprint("vendors", __name__, url_prefix="/vendors")


# ------------------------------------------------------------------
# List & Create REST Endpoint
# ------------------------------------------------------------------
@vendors_bp.route("/", methods=["GET", "POST"])
@login_required
def list_vendors():
    if request.method == "POST":
        return create()

    q = request.args.get("q", "").strip()
    query = Vendor.query
    if q:
        query = query.filter(
            Vendor.name.ilike(f"%{q}%") | Vendor.email.ilike(f"%{q}%")
        )
    vendors = query.order_by(Vendor.name).all()
    return render_template("vendors/list.html", vendors=vendors, q=q)


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------
@vendors_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager", "purchasing")
def create():
    data = request.get_json() if request.is_json else request.form

    if request.method == "POST":
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()
        address = data.get("address", "").strip()

        if not name:
            if is_json_request():
                return jsonify({"error": "Vendor name is required."}), 400
            flash("Vendor name is required.", "warning")
            return render_template("vendors/form.html", vendor=None)

        vendor = Vendor(name=name, email=email, phone=phone, address=address)
        db.session.add(vendor)
        db.session.commit()

        log_audit(
            current_user.id, "CREATE", "Vendor", vendor.id,
            None,
            {"name": name, "email": email},
            f"Created vendor '{name}'",
        )
        
        if is_json_request():
            return jsonify({
                "message": f"Vendor '{name}' created.",
                "id": vendor.id
            }), 201

        flash(f"Vendor '{name}' created successfully.", "success")
        return redirect(url_for("vendors.list_vendors"))

    return render_template("vendors/form.html", vendor=None)


# ------------------------------------------------------------------
# View / Edit / Delete REST Endpoint
# ------------------------------------------------------------------
@vendors_bp.route("/<int:vendor_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def view_edit_delete_vendor(vendor_id):
    if request.method == "PUT":
        return edit(vendor_id)
    elif request.method == "DELETE":
        return delete(vendor_id)
    return view(vendor_id)


# ------------------------------------------------------------------
# Detail / View
# ------------------------------------------------------------------
@vendors_bp.route("/<int:vendor_id>/view")
@login_required
def view(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    return render_template("vendors/view.html", vendor=vendor)


# ------------------------------------------------------------------
# Edit
# ------------------------------------------------------------------
@vendors_bp.route("/<int:vendor_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager", "purchasing")
def edit(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    data = request.get_json() if request.is_json else request.form

    if request.method in ["POST", "PUT"]:
        old = {"name": vendor.name, "email": vendor.email, "phone": vendor.phone, "address": vendor.address}

        vendor.name = data.get("name", "").strip() or vendor.name
        vendor.email = data.get("email", "").strip()
        vendor.phone = data.get("phone", "").strip()
        vendor.address = data.get("address", "").strip()
        db.session.commit()

        new = {"name": vendor.name, "email": vendor.email, "phone": vendor.phone, "address": vendor.address}
        log_audit(
            current_user.id, "UPDATE", "Vendor", vendor.id,
            old, new,
            f"Updated vendor '{vendor.name}'",
        )
        
        if is_json_request():
            return jsonify({"message": f"Vendor '{vendor.name}' updated."}), 200

        flash(f"Vendor '{vendor.name}' updated.", "success")
        return redirect(url_for("vendors.view", vendor_id=vendor.id))

    return render_template("vendors/form.html", vendor=vendor)


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------
@vendors_bp.route("/<int:vendor_id>/delete", methods=["POST", "DELETE"])
@login_required
@role_required("admin")
def delete(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    name = vendor.name
    log_audit(
        current_user.id, "DELETE", "Vendor", vendor.id,
        {"name": name}, None,
        f"Deleted vendor '{name}'",
    )
    db.session.delete(vendor)
    db.session.commit()
    
    if is_json_request():
        return jsonify({"message": f"Vendor '{name}' deleted."}), 200

    flash(f"Vendor '{name}' deleted.", "success")
    return redirect(url_for("vendors.list_vendors"))
