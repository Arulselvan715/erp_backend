"""Authentication routes — login / logout / session management."""

from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import current_user, login_required, login_user, logout_user

from models import db, User
from models.audit import log_audit

auth_bp = Blueprint("auth", __name__)


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Show the login form (GET) or authenticate the user (POST)."""
    if current_user.is_authenticated:
        accept_header = request.headers.get("Accept", "")
        if request.is_json or "application/json" in accept_header:
            return jsonify({
                "access_token": "dummy-session-token",
                "user": {
                    "id": current_user.id,
                    "username": current_user.username,
                    "email": current_user.email,
                    "role": current_user.role
                }
            })
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        # Check for JSON API login request
        accept_header = request.headers.get("Accept", "")
        if request.is_json or "application/json" in accept_header:
            data = request.json or {}
            email = data.get("email", "").strip()
            password = data.get("password", "")

            if not email or not password:
                return jsonify({"error": "Email and password are required."}), 400

            user = User.query.filter_by(email=email).first()

            if user is None or not user.check_password(password):
                return jsonify({"error": "Invalid email or password."}), 401

            login_user(user, remember=True)
            log_audit(user.id, "LOGIN", "User", user.id, None, None, f"User '{user.username}' logged in via API")

            return jsonify({
                "access_token": "dummy-session-token",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role
                }
            })

        # Fallback to standard form-data login
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        if not username or not password:
            flash("Username and password are required.", "warning")
            return render_template("auth/login.html")

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html")

        login_user(user, remember=remember)
        log_audit(user.id, "LOGIN", "User", user.id, None, None, f"User '{user.username}' logged in")
        flash(f"Welcome back, {user.username}!", "success")

        next_page = request.args.get("next")
        if next_page:
            return redirect(next_page)
        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html")


# ------------------------------------------------------------------
# Logout
# ------------------------------------------------------------------
@auth_bp.route("/logout")
@login_required
def logout():
    """Log the current user out and redirect to the login page."""
    log_audit(current_user.id, "LOGOUT", "User", current_user.id, None, None, f"User '{current_user.username}' logged out")
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
