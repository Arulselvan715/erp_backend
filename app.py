"""
Mini ERP — Demand to Delivery
Flask application factory with blueprint registration and database initialisation.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask, redirect, url_for
from flask_login import LoginManager, login_required

from config import Config, config_by_name
from models import db
from models.user import User


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Load configuration
    cfg = config_by_name.get(config_name or os.environ.get("FLASK_ENV", "development"))
    app.config.from_object(cfg or Config)

    # ── Initialise extensions ─────────────────────────────────────────
    from flask_cors import CORS
    import re
    CORS(app, supports_credentials=True, origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        re.compile(r"https://.*\.vercel\.app"),
    ], allow_headers=["Content-Type", "Authorization", "Accept"],
       methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    
    from patch import patch_render_template
    patch_render_template()
    
    db.init_app(app)
    app.logger.info(f"Connecting to database: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(user_id)

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, jsonify
        accept_header = request.headers.get("Accept", "")
        if (request.is_json or "application/json" in accept_header or
                request.headers.get("Content-Type", "").startswith("application/json")):
            return jsonify({"error": "Authentication required. Please log in."}), 401
        return redirect(url_for("auth.login"))

    # ── Register blueprints ───────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.products import products_bp
    from routes.customers import customers_bp
    from routes.vendors import vendors_bp
    from routes.sales import sales_bp
    from routes.purchase import purchase_bp
    from routes.manufacturing import manufacturing_bp
    from routes.inventory import inventory_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(products_bp, url_prefix="/products")
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(vendors_bp, url_prefix="/vendors")
    app.register_blueprint(sales_bp, url_prefix="/sales")
    app.register_blueprint(purchase_bp, url_prefix="/purchase")
    app.register_blueprint(manufacturing_bp, url_prefix="/manufacturing")
    app.register_blueprint(inventory_bp, url_prefix="/inventory")

    # ── Root redirect ─────────────────────────────────────────────────
    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.route("/users/", methods=["GET"])
    @app.route("/users", methods=["GET"])
    @login_required
    def list_users():
        from models.user import User
        from routes.utils import serialize
        from flask import jsonify
        users = User.query.order_by(User.username).all()
        return jsonify({
            "data": [serialize(u) for u in users],
            "total": len(users)
        })

    # ── Create tables & seed data ─────────────────────────────────────
    with app.app_context():
        # Ensure database directory exists
        db_dir = os.path.join(os.path.dirname(__file__), "database")
        os.makedirs(db_dir, exist_ok=True)

        db.create_all()
        _seed_default_users(app)
        _seed_default_data(app)

    return app


def _seed_default_data(app: Flask) -> None:
    """Insert default products, vendors, customers, and BoMs if tables are empty."""
    from models.vendor import Vendor
    from models.customer import Customer
    from models.product import Product
    from models.manufacturing import BillOfMaterials, BomLine

    if Vendor.query.first() is not None:
        return

    app.logger.info("Seeding default database records...")

    # 1. Seed Vendors
    vendors_data = [
        {"name": "Global Components Corp", "email": "info@globalcomp.com", "phone": "1-800-555-0199", "city": "San Jose", "state": "CA", "country": "USA"},
        {"name": "Steel Supplies Inc", "email": "sales@steelsupplies.com", "phone": "1-800-555-0245", "city": "Pittsburgh", "state": "PA", "country": "USA"},
        {"name": "Logistics & Copper Ltd", "email": "contact@logcopper.co.uk", "phone": "+44 20 7946 0958", "city": "London", "country": "UK"}
    ]
    
    vendors_dict = {}
    for v_info in vendors_data:
        vendor = Vendor(**v_info)
        db.session.add(vendor)
        db.session.flush()
        vendors_dict[v_info["name"]] = vendor

    # 2. Seed Customers
    customers_data = [
        {"name": "Blue Horizon Industries", "email": "procurement@bluehorizon.com", "phone": "1-888-555-9000", "city": "Austin", "state": "TX", "country": "USA"},
        {"name": "Tesla Motors Inc", "email": "parts@tesla.com", "phone": "1-800-555-8080", "city": "Palo Alto", "state": "CA", "country": "USA"},
        {"name": "General Electric Corp", "email": "supply@ge.com", "phone": "1-800-555-7070", "city": "Boston", "state": "MA", "country": "USA"}
    ]
    
    for c_info in customers_data:
        customer = Customer(**c_info)
        db.session.add(customer)
            
    # 3. Seed Products
    global_comp = vendors_dict["Global Components Corp"]
    steel_supp = vendors_dict["Steel Supplies Inc"]
    log_copper = vendors_dict["Logistics & Copper Ltd"]
    
    products_data = [
        # Raw materials (procurement_type="purchase")
        {"name": "Steel Plate", "sku": "RAW-STEEL-01", "cost_price": 5.00, "sales_price": 0.00, "on_hand_qty": 100.0, "procure_on_demand": False, "procurement_type": "purchase", "vendor_id": steel_supp.id},
        {"name": "Copper Wire", "sku": "RAW-COPPER-01", "cost_price": 2.00, "sales_price": 0.00, "on_hand_qty": 250.0, "procure_on_demand": False, "procurement_type": "purchase", "vendor_id": log_copper.id},
        {"name": "Microcontroller Unit", "sku": "RAW-MCU-01", "cost_price": 15.00, "sales_price": 0.00, "on_hand_qty": 50.0, "procure_on_demand": False, "procurement_type": "purchase", "vendor_id": global_comp.id},
        
        # Finished goods (procurement_type="manufacturing")
        {"name": "Smart Controller Box", "sku": "FG-SMART-BOX-01", "cost_price": 45.00, "sales_price": 120.00, "on_hand_qty": 5.0, "procure_on_demand": True, "procurement_type": "manufacturing"},
        {"name": "Industrial Bracket", "sku": "FG-BRACKET-01", "cost_price": 10.00, "sales_price": 25.00, "on_hand_qty": 20.0, "procure_on_demand": False, "procurement_type": "manufacturing"}
    ]
    
    products_dict = {}
    for p_info in products_data:
        product = Product(**p_info)
        db.session.add(product)
        db.session.flush()
        products_dict[p_info["sku"]] = product
        
    db.session.commit()
    
    # 4. Seed Bill of Materials (BoM)
    smart_box = products_dict["FG-SMART-BOX-01"]
    mcu = products_dict["RAW-MCU-01"]
    copper = products_dict["RAW-COPPER-01"]
    steel = products_dict["RAW-STEEL-01"]
    
    bom_sb = BillOfMaterials(product_id=smart_box.id, name="Smart Controller Assembly", version="1.0", output_qty=1.0)
    db.session.add(bom_sb)
    db.session.flush()
    
    # Add components
    line1 = BomLine(bom_id=bom_sb.id, component_id=mcu.id, quantity=1.0)
    line2 = BomLine(bom_id=bom_sb.id, component_id=copper.id, quantity=2.0)
    line3 = BomLine(bom_id=bom_sb.id, component_id=steel.id, quantity=1.0)
    db.session.add_all([line1, line2, line3])
        
    # BoM for Industrial Bracket (FG-BRACKET-01)
    bracket = products_dict["FG-BRACKET-01"]
    
    bom_ib = BillOfMaterials(product_id=bracket.id, name="Industrial Bracket Forming", version="1.0", output_qty=1.0)
    db.session.add(bom_ib)
    db.session.flush()
    
    # Add components
    line_ib1 = BomLine(bom_id=bom_ib.id, component_id=steel.id, quantity=2.0)
    db.session.add(line_ib1)
        
    db.session.commit()
    app.logger.info("Database default data seeding completed successfully!")


def _seed_default_users(app: Flask) -> None:
    """Insert default users if they do not exist."""
    default_users = [
        ("admin", "admin@minierp.local", "admin123", "Admin"),
        ("sales", "sales@minierp.local", "sales123", "Sales User"),
        ("purchase", "purchase@minierp.local", "purchase123", "Purchase User"),
        ("manufacturing", "mfg@minierp.local", "mfg123", "Manufacturing User"),
        ("inventory", "inv@minierp.local", "inv123", "Inventory Manager"),
        ("owner", "owner@minierp.local", "owner123", "Business Owner"),
        ("devanathan", "msdevanathan992006@gmail.com", "9906", "Admin"),
    ]

    seeded = 0
    for username, email, password, role in default_users:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(username=username, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            seeded += 1
        else:
            if not user.check_password(password):
                user.set_password(password)
                user.role = role
                db.session.add(user)
                seeded += 1

    if seeded > 0:
        db.session.commit()
        app.logger.info("Seeded/Updated %d default users.", seeded)


# ── Entry point ───────────────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
