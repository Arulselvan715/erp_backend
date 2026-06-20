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
    ip_address = db.Column(db.String(500), nullable=False, default="")
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
    user_id: int | None,
    action: str,
    table_name: str,
    record_id: int,
    old_values: dict | None = None,
    new_values: dict | None = None,
    details: str = "",
):
    """Create an audit-log entry.

    Parameters
    ----------
    user_id : int | None
        The user who performed the action.
    action : str
        One of ``INSERT``, ``UPDATE``, ``DELETE``, etc.
    table_name : str
        The database table that was modified.
    record_id : int
        Primary key of the affected row.
    old_values : dict | None
        JSON-serialisable snapshot of the row *before* the change.
    new_values : dict | None
        JSON-serialisable snapshot of the row *after* the change.
    details : str
        Audit details or IP address (optional).

    Returns
    -------
    AuditLog
        The newly created (but uncommitted) audit log entry.
    """
    from routes.utils import serialize
    entry = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        old_values=serialize(old_values),
        new_values=serialize(new_values),
        user_id=user_id,
        ip_address=details,
        user_agent="",
    )
    db.session.add(entry)
    return entry
