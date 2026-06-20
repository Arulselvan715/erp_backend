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

