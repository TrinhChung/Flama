from datetime import datetime

from models import db


class UserPermissionAuditLog(db.Model):
    """Audit events for user role and status changes."""

    __tablename__ = "user_permission_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    from_role_id = db.Column(db.Integer, db.ForeignKey("user_roles.id"), nullable=True, index=True)
    to_role_id = db.Column(db.Integer, db.ForeignKey("user_roles.id"), nullable=True, index=True)
    from_is_admin = db.Column(db.Boolean, nullable=False, default=False)
    to_is_admin = db.Column(db.Boolean, nullable=False, default=False)
    from_is_disabled = db.Column(db.Boolean, nullable=False, default=False)
    to_is_disabled = db.Column(db.Boolean, nullable=False, default=False)
    message = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
