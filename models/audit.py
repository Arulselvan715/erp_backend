"""Audit Log model and helper."""

from datetime import datetime

from . import db


class AuditLog(db.Model):
    """Immutable record of every data change for compliance / debugging."""

    __tablename__ = "audit_logs"

    ACTIONS = ("INSERT", "UPDATE", "DELETE")

    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(80), nullable=False, index=True)
    record_id = db.Column(db.Integer, nullable=False, index=True)
    action = db.Column(db.String(10), nullable=False, index=True)
    old_values = db.Column(db.JSON, nullable=True)
    new_values = db.Column(db.JSON, nullable=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    ip_address = db.Column(db.String(45), nullable=False, default="")
    user_agent = db.Column(db.String(300), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # --- Relationships ---
    user = db.relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return (
            f"<AuditLog {self.id} {self.action} "
            f"{self.table_name}#{self.record_id}>"
        )


# ======================================================================
# Helper function
# ======================================================================
def log_audit(
    table_name: str,
    record_id: int,
    action: str,
    old_values: dict | None = None,
    new_values: dict | None = None,
    user_id: int | None = None,
    ip_address: str = "",
    user_agent: str = "",
):
    """Create an audit-log entry.

    Parameters
    ----------
    table_name : str
        The database table that was modified (e.g. ``"products"``).
    record_id : int
        Primary key of the affected row.
    action : str
        One of ``INSERT``, ``UPDATE``, ``DELETE``.
    old_values : dict | None
        JSON-serialisable snapshot of the row *before* the change.
    new_values : dict | None
        JSON-serialisable snapshot of the row *after* the change.
    user_id : int | None
        The user who performed the action (``None`` for system actions).
    ip_address : str
        Client IP address (optional).
    user_agent : str
        Client user-agent string (optional).

    Returns
    -------
    AuditLog
        The newly created (but uncommitted) audit log entry.

    Note
    ----
    The caller is responsible for calling ``db.session.commit()``.
    """
    entry = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        old_values=old_values,
        new_values=new_values,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.session.add(entry)
    return entry
