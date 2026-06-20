"""Customer CRUD routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from models import db, Customer
from models.audit import log_audit
from routes.utils import role_required

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------
@customers_bp.route("/")
@login_required
def list_customers():
    """List all customers with optional search."""
    q = request.args.get("q", "").strip()
    query = Customer.query
    if q:
        query = query.filter(
            Customer.name.ilike(f"%{q}%") | Customer.email.ilike(f"%{q}%")
        )
    customers = query.order_by(Customer.name).all()
    return render_template("customers/list.html", customers=customers, q=q)


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------
@customers_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager", "sales")
def create():
    """Show create form (GET) or persist a new customer (POST)."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            flash("Customer name is required.", "warning")
            return render_template("customers/form.html", customer=None)

        customer = Customer(name=name, email=email, phone=phone, address=address)
        db.session.add(customer)
        db.session.commit()

        log_audit(
            current_user.id, "CREATE", "Customer", customer.id,
            None,
            {"name": name, "email": email},
            f"Created customer '{name}'",
        )
        flash(f"Customer '{name}' created successfully.", "success")
        return redirect(url_for("customers.list_customers"))

    return render_template("customers/form.html", customer=None)


# ------------------------------------------------------------------
# Detail / View
# ------------------------------------------------------------------
@customers_bp.route("/<int:customer_id>")
@login_required
def view(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return render_template("customers/view.html", customer=customer)


# ------------------------------------------------------------------
# Edit
# ------------------------------------------------------------------
@customers_bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager", "sales")
def edit(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if request.method == "POST":
        old = {"name": customer.name, "email": customer.email, "phone": customer.phone, "address": customer.address}

        customer.name = request.form.get("name", "").strip() or customer.name
        customer.email = request.form.get("email", "").strip()
        customer.phone = request.form.get("phone", "").strip()
        customer.address = request.form.get("address", "").strip()
        db.session.commit()

        new = {"name": customer.name, "email": customer.email, "phone": customer.phone, "address": customer.address}
        log_audit(
            current_user.id, "UPDATE", "Customer", customer.id,
            old, new,
            f"Updated customer '{customer.name}'",
        )
        flash(f"Customer '{customer.name}' updated.", "success")
        return redirect(url_for("customers.view", customer_id=customer.id))

    return render_template("customers/form.html", customer=customer)


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------
@customers_bp.route("/<int:customer_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    name = customer.name
    log_audit(
        current_user.id, "DELETE", "Customer", customer.id,
        {"name": name}, None,
        f"Deleted customer '{name}'",
    )
    db.session.delete(customer)
    db.session.commit()
    flash(f"Customer '{name}' deleted.", "success")
    return redirect(url_for("customers.list_customers"))
