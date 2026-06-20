"""Vendor CRUD routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from models import db, Vendor
from models.audit import log_audit
from routes.utils import role_required

vendors_bp = Blueprint("vendors", __name__, url_prefix="/vendors")


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------
@vendors_bp.route("/")
@login_required
def list_vendors():
    """List all vendors with optional search."""
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
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
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
        flash(f"Vendor '{name}' created successfully.", "success")
        return redirect(url_for("vendors.list_vendors"))

    return render_template("vendors/form.html", vendor=None)


# ------------------------------------------------------------------
# Detail / View
# ------------------------------------------------------------------
@vendors_bp.route("/<int:vendor_id>")
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

    if request.method == "POST":
        old = {"name": vendor.name, "email": vendor.email, "phone": vendor.phone, "address": vendor.address}

        vendor.name = request.form.get("name", "").strip() or vendor.name
        vendor.email = request.form.get("email", "").strip()
        vendor.phone = request.form.get("phone", "").strip()
        vendor.address = request.form.get("address", "").strip()
        db.session.commit()

        new = {"name": vendor.name, "email": vendor.email, "phone": vendor.phone, "address": vendor.address}
        log_audit(
            current_user.id, "UPDATE", "Vendor", vendor.id,
            old, new,
            f"Updated vendor '{vendor.name}'",
        )
        flash(f"Vendor '{vendor.name}' updated.", "success")
        return redirect(url_for("vendors.view", vendor_id=vendor.id))

    return render_template("vendors/form.html", vendor=vendor)


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------
@vendors_bp.route("/<int:vendor_id>/delete", methods=["POST"])
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
    flash(f"Vendor '{name}' deleted.", "success")
    return redirect(url_for("vendors.list_vendors"))
