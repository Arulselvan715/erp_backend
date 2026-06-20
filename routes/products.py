"""Product CRUD routes + BoM configuration + procurement strategy setup."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from models import db, Product, Vendor, BillOfMaterials, BomLine, BomOperation
from models.audit import log_audit
from routes.utils import role_required

products_bp = Blueprint("products", __name__, url_prefix="/products")


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------
@products_bp.route("/")
@login_required
def list_products():
    q = request.args.get("q", "").strip()
    query = Product.query
    if q:
        query = query.filter(
            Product.name.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%")
        )
    products = query.order_by(Product.name).all()
    return render_template("products/list.html", products=products, q=q)


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------
@products_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def create():
    vendors = Vendor.query.order_by(Vendor.name).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku = request.form.get("sku", "").strip()
        sales_price = request.form.get("sales_price", type=float) or 0.0
        cost_price = request.form.get("cost_price", type=float) or 0.0
        on_hand_qty = request.form.get("on_hand_qty", type=float) or 0.0
        procure_on_demand = bool(request.form.get("procure_on_demand"))
        procurement_type = request.form.get("procurement_type", "buy")  # buy | manufacture
        vendor_id = request.form.get("vendor_id", type=int)

        if not name or not sku:
            flash("Product name and SKU are required.", "warning")
            return render_template("products/form.html", product=None, vendors=vendors)

        if Product.query.filter_by(sku=sku).first():
            flash(f"SKU '{sku}' already exists.", "danger")
            return render_template("products/form.html", product=None, vendors=vendors)

        product = Product(
            name=name,
            sku=sku,
            sales_price=sales_price,
            cost_price=cost_price,
            on_hand_qty=on_hand_qty,
            reserved_qty=0,
            procure_on_demand=procure_on_demand,
            procurement_type=procurement_type,
            vendor_id=vendor_id if vendor_id else None,
        )
        db.session.add(product)
        db.session.commit()

        log_audit(
            current_user.id, "CREATE", "Product", product.id,
            None,
            {"name": name, "sku": sku, "procurement_type": procurement_type},
            f"Created product '{name}' (SKU: {sku})",
        )
        flash(f"Product '{name}' created.", "success")
        return redirect(url_for("products.view", product_id=product.id))

    return render_template("products/form.html", product=None, vendors=vendors)


# ------------------------------------------------------------------
# View / Detail
# ------------------------------------------------------------------
@products_bp.route("/<int:product_id>")
@login_required
def view(product_id):
    product = Product.query.get_or_404(product_id)
    bom = BillOfMaterials.query.filter_by(product_id=product.id).first()
    return render_template("products/view.html", product=product, bom=bom)


# ------------------------------------------------------------------
# Edit
# ------------------------------------------------------------------
@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def edit(product_id):
    product = Product.query.get_or_404(product_id)
    vendors = Vendor.query.order_by(Vendor.name).all()

    if request.method == "POST":
        old = {
            "name": product.name, "sku": product.sku,
            "sales_price": float(product.sales_price),
            "cost_price": float(product.cost_price),
            "procurement_type": product.procurement_type,
            "procure_on_demand": product.procure_on_demand,
            "vendor_id": product.vendor_id,
        }

        product.name = request.form.get("name", "").strip() or product.name
        product.sku = request.form.get("sku", "").strip() or product.sku
        product.sales_price = request.form.get("sales_price", type=float) or product.sales_price
        product.cost_price = request.form.get("cost_price", type=float) or product.cost_price
        product.procure_on_demand = bool(request.form.get("procure_on_demand"))
        product.procurement_type = request.form.get("procurement_type", product.procurement_type)
        vendor_id = request.form.get("vendor_id", type=int)
        product.vendor_id = vendor_id if vendor_id else None
        db.session.commit()

        new = {
            "name": product.name, "sku": product.sku,
            "sales_price": float(product.sales_price),
            "cost_price": float(product.cost_price),
            "procurement_type": product.procurement_type,
            "procure_on_demand": product.procure_on_demand,
            "vendor_id": product.vendor_id,
        }
        log_audit(
            current_user.id, "UPDATE", "Product", product.id,
            old, new,
            f"Updated product '{product.name}'",
        )
        flash(f"Product '{product.name}' updated.", "success")
        return redirect(url_for("products.view", product_id=product.id))

    return render_template("products/form.html", product=product, vendors=vendors)


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------
@products_bp.route("/<int:product_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete(product_id):
    product = Product.query.get_or_404(product_id)
    name = product.name
    log_audit(
        current_user.id, "DELETE", "Product", product.id,
        {"name": name, "sku": product.sku}, None,
        f"Deleted product '{name}'",
    )
    db.session.delete(product)
    db.session.commit()
    flash(f"Product '{name}' deleted.", "success")
    return redirect(url_for("products.list_products"))


# ==================================================================
# BoM Configuration — assign / update a BoM on a product
# ==================================================================

@products_bp.route("/<int:product_id>/bom", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def configure_bom(product_id):
    """Create or update the Bill of Materials for a product."""
    product = Product.query.get_or_404(product_id)
    bom = BillOfMaterials.query.filter_by(product_id=product.id).first()
    components = Product.query.filter(Product.id != product.id).order_by(Product.name).all()

    if request.method == "POST":
        bom_name = request.form.get("bom_name", "").strip() or f"BoM - {product.name}"

        # -- Collect component lines from the form --
        comp_ids = request.form.getlist("component_id")
        comp_qtys = request.form.getlist("component_qty")

        # -- Collect operation lines from the form --
        op_names = request.form.getlist("operation_name")
        op_durations = request.form.getlist("operation_duration")
        op_sequences = request.form.getlist("operation_sequence")

        if not comp_ids:
            flash("At least one component is required for a BoM.", "warning")
            return render_template(
                "products/bom_form.html",
                product=product, bom=bom, components=components,
            )

        # ── Create or update the BoM header ──────────────────────
        if bom is None:
            bom = BillOfMaterials(product_id=product.id, name=bom_name)
            db.session.add(bom)
            db.session.flush()  # get bom.id
        else:
            bom.name = bom_name
            # Clear old lines & operations for replacement
            BomLine.query.filter_by(bom_id=bom.id).delete()
            BomOperation.query.filter_by(bom_id=bom.id).delete()

        # ── Add component lines ──────────────────────────────────
        for cid, cqty in zip(comp_ids, comp_qtys):
            cid = int(cid)
            cqty = float(cqty) if cqty else 1.0
            if cqty <= 0:
                continue
            line = BomLine(bom_id=bom.id, component_product_id=cid, quantity=cqty)
            db.session.add(line)

        # ── Add operations ───────────────────────────────────────
        for idx, (oname, odur, oseq) in enumerate(
            zip(op_names, op_durations, op_sequences), start=1
        ):
            oname = oname.strip()
            if not oname:
                continue
            op = BomOperation(
                bom_id=bom.id,
                operation_name=oname,
                duration_mins=float(odur) if odur else 0,
                sequence=int(oseq) if oseq else idx,
            )
            db.session.add(op)

        # Link product to BoM
        product.bom_id = bom.id
        db.session.commit()

        log_audit(
            current_user.id, "UPDATE", "BillOfMaterials", bom.id,
            None,
            {"product_id": product.id, "bom_name": bom_name, "components": len(comp_ids)},
            f"Configured BoM for product '{product.name}'",
        )
        flash(f"BoM for '{product.name}' saved.", "success")
        return redirect(url_for("products.view", product_id=product.id))

    return render_template(
        "products/bom_form.html",
        product=product, bom=bom, components=components,
    )


# ==================================================================
# Procurement Strategy Setup
# ==================================================================

@products_bp.route("/<int:product_id>/procurement", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def configure_procurement(product_id):
    """Configure how a product is procured: buy vs manufacture,
    on-demand toggle, and default vendor."""
    product = Product.query.get_or_404(product_id)
    vendors = Vendor.query.order_by(Vendor.name).all()

    if request.method == "POST":
        old = {
            "procurement_type": product.procurement_type,
            "procure_on_demand": product.procure_on_demand,
            "vendor_id": product.vendor_id,
        }

        product.procurement_type = request.form.get("procurement_type", "buy")
        product.procure_on_demand = bool(request.form.get("procure_on_demand"))
        vendor_id = request.form.get("vendor_id", type=int)
        product.vendor_id = vendor_id if vendor_id else None
        db.session.commit()

        new = {
            "procurement_type": product.procurement_type,
            "procure_on_demand": product.procure_on_demand,
            "vendor_id": product.vendor_id,
        }
        log_audit(
            current_user.id, "UPDATE", "Product", product.id,
            old, new,
            f"Updated procurement strategy for '{product.name}'",
        )
        flash(f"Procurement strategy for '{product.name}' updated.", "success")
        return redirect(url_for("products.view", product_id=product.id))

    return render_template(
        "products/procurement_form.html",
        product=product, vendors=vendors,
    )
