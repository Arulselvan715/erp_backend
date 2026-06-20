"""Customer CRUD routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import login_required, current_user

from models import db, Customer
from models.audit import log_audit
from routes.utils import role_required, is_json_request

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


# ------------------------------------------------------------------
# List & Create REST Endpoint
# ------------------------------------------------------------------
@customers_bp.route("/", methods=["GET", "POST"])
@login_required
def list_customers():
    if request.method == "POST":
        return create()

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
    data = request.get_json() if request.is_json else request.form

    if request.method == "POST":
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()
        address = data.get("address", "").strip()

        if not name:
            if is_json_request():
                return jsonify({"error": "Customer name is required."}), 400
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
        
        if is_json_request():
            return jsonify({
                "message": f"Customer '{name}' created.",
                "id": customer.id
            }), 201

        flash(f"Customer '{name}' created successfully.", "success")
        return redirect(url_for("customers.list_customers"))

    return render_template("customers/form.html", customer=None)


# ------------------------------------------------------------------
# View / Edit / Delete REST Endpoint
# ------------------------------------------------------------------
@customers_bp.route("/<int:customer_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def view_edit_delete_customer(customer_id):
    if request.method == "PUT":
        return edit(customer_id)
    elif request.method == "DELETE":
        return delete(customer_id)
    return view(customer_id)


# ------------------------------------------------------------------
# Detail / View
# ------------------------------------------------------------------
@customers_bp.route("/<int:customer_id>/view")
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
    data = request.get_json() if request.is_json else request.form

    if request.method in ["POST", "PUT"]:
        old = {"name": customer.name, "email": customer.email, "phone": customer.phone, "address": customer.address}

        customer.name = data.get("name", "").strip() or customer.name
        customer.email = data.get("email", "").strip()
        customer.phone = data.get("phone", "").strip()
        customer.address = data.get("address", "").strip()
        db.session.commit()

        new = {"name": customer.name, "email": customer.email, "phone": customer.phone, "address": customer.address}
        log_audit(
            current_user.id, "UPDATE", "Customer", customer.id,
            old, new,
            f"Updated customer '{customer.name}'",
        )
        
        if is_json_request():
            return jsonify({"message": f"Customer '{customer.name}' updated."}), 200

        flash(f"Customer '{customer.name}' updated.", "success")
        return redirect(url_for("customers.view", customer_id=customer.id))

    return render_template("customers/form.html", customer=customer)


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------
@customers_bp.route("/<int:customer_id>/delete", methods=["POST", "DELETE"])
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
    
    if is_json_request():
        return jsonify({"message": f"Customer '{name}' deleted."}), 200

    flash(f"Customer '{name}' deleted.", "success")
    return redirect(url_for("customers.list_customers"))
