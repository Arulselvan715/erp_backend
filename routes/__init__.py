from .auth import auth_bp
from .dashboard import dashboard_bp
from .products import products_bp
from .customers import customers_bp
from .vendors import vendors_bp
from .sales import sales_bp
from .purchase import purchase_bp
from .manufacturing import manufacturing_bp
from .inventory import inventory_bp
from .reports import reports_bp

all_blueprints = [
    auth_bp,
    dashboard_bp,
    products_bp,
    customers_bp,
    vendors_bp,
    sales_bp,
    purchase_bp,
    manufacturing_bp,
    inventory_bp,
    reports_bp,
]


def register_blueprints(app):
    """Register every blueprint with the Flask application."""
    for bp in all_blueprints:
        app.register_blueprint(bp)
