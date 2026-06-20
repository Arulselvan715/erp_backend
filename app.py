"""
Mini ERP — Demand to Delivery
Flask application factory with blueprint registration and database initialisation.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask, redirect, url_for
from flask_login import LoginManager

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
    CORS(app, supports_credentials=True)
    
    from routes.utils import patch_render_template
    patch_render_template()
    
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(user_id)

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

    # ── Create tables & seed data ─────────────────────────────────────
    with app.app_context():
        # Ensure database directory exists
        db_dir = os.path.join(os.path.dirname(__file__), "database")
        os.makedirs(db_dir, exist_ok=True)

        db.create_all()
        _seed_default_users(app)

    return app


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
        if not User.query.filter_by(email=email).first():
            user = User(username=username, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            seeded += 1

    if seeded > 0:
        db.session.commit()
        app.logger.info("Seeded %d default users.", seeded)


# ── Entry point ───────────────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
