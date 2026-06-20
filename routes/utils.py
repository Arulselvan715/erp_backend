"""Shared utilities for route handlers."""

from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user


ROLE_MAPPING = {
    "admin": {"Admin"},
    "manager": {"Admin", "Inventory Manager", "Business Owner"},
    "sales": {"Sales User"},
    "purchasing": {"Purchase User"},
    "production": {"Manufacturing User"},
    "warehouse": {"Inventory Manager"},
    "business owner": {"Business Owner"}
}


def role_required(*roles):
    """Decorator that restricts access to users whose role is in *roles*.

    Usage::

        @role_required('admin', 'manager')
        def admin_view():
            ...

    Must be applied **after** ``@login_required`` so that
    ``current_user`` is guaranteed to be authenticated.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in first.", "warning")
                return redirect(url_for("auth.login"))
            
            # Resolve database-level roles that are allowed
            allowed_db_roles = set()
            for r in roles:
                r_clean = r.strip().lower()
                if r_clean in ROLE_MAPPING:
                    allowed_db_roles.update(ROLE_MAPPING[r_clean])
                else:
                    allowed_db_roles.add(r)
            
            # Check if user's role matches any allowed role case-insensitively
            user_role = current_user.role
            user_role_lower = user_role.lower() if user_role else ""
            is_allowed = (user_role in allowed_db_roles) or any(
                user_role_lower == allowed.lower() for allowed in allowed_db_roles
            )

            if not is_allowed:
                flash("You do not have permission to access this page.", "danger")
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


from datetime import datetime, date
from decimal import Decimal
import flask

def serialize(data):
    if data is None:
        return None
    if isinstance(data, list):
        return [serialize(item) for item in data]
    if isinstance(data, dict):
        return {k: serialize(v) for k, v in data.items()}
    if isinstance(data, (Decimal, float, int, str, bool)):
        if isinstance(data, Decimal):
            return float(data)
        return data
    if isinstance(data, (datetime, date)):
        return data.isoformat()
    if hasattr(data, "items") and hasattr(data, "page") and hasattr(data, "pages"):
        # Flask-SQLAlchemy Pagination object
        return {
            "items": serialize(data.items),
            "page": data.page,
            "pages": data.pages,
            "per_page": data.per_page,
            "total": data.total
        }
    if hasattr(data, "__iter__") and not isinstance(data, (str, dict)):
        return [serialize(item) for item in data]
    if hasattr(data, "__table__"):
        # SQLAlchemy Model
        result = {}
        for column in data.__table__.columns:
            val = getattr(data, column.name)
            if isinstance(val, (datetime, date)):
                val = val.isoformat()
            elif isinstance(val, Decimal):
                val = float(val)
            result[column.name] = val
        # Expose custom hybrid properties or class properties if they exist
        for key in dir(data.__class__):
            prop = getattr(data.__class__, key)
            if isinstance(prop, property):
                try:
                    val = getattr(data, key)
                    if isinstance(val, Decimal):
                        val = float(val)
                    elif isinstance(val, (datetime, date)):
                        val = val.isoformat()
                    result[key] = val
                except Exception:
                    pass
        return result
    # Fallback to string representation
    return str(data)


def patch_render_template():
    original_render_template = flask.render_template

    def custom_render_template(template_name_or_list, **context):
        from flask import request, jsonify
        # Check if request expects JSON
        if (request.is_json or 
            request.headers.get("Accept") == "application/json" or 
            request.path.startswith("/api/") or
            request.args.get("format") == "json"):
            
            serialized_context = {}
            for k, v in context.items():
                # Skip internal Flask/SQLAlchemy objects
                if k not in ["current_user", "g", "request", "session", "bootstrap"]:
                    serialized_context[k] = serialize(v)
            
            # Search for the primary list in the serialized context
            primary_list = None
            primary_key = None
            
            # Common names for list variables in our routes
            list_keys = ["products", "orders", "boms", "customers", "vendors", "ledger", "movements", "logs"]
            
            for k in list_keys:
                if k in serialized_context:
                    primary_list = serialized_context[k]
                    primary_key = k
                    break
            
            if primary_list is not None and isinstance(primary_list, list):
                return jsonify({
                    "data": primary_list,
                    "total": len(primary_list)
                })
            
            # If the context contains only one main key, return that directly
            if len(serialized_context) == 1:
                key = list(serialized_context.keys())[0]
                return jsonify(serialized_context[key])
            
            return jsonify(serialized_context)
        return original_render_template(template_name_or_list, **context)

    flask.render_template = custom_render_template


