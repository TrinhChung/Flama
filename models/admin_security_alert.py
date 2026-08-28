"""Admin Security Alert model for recording threats and suspicious security events."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index

from models import db
from models.model_uuid import uuid_str


class AdminSecurityAlert(db.Model):
    """Tracks potential attack attempts, SSRF, malicious uploads, and policy violations."""

    __tablename__ = "admin_security_alerts"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    severity = db.Column(
        db.String(20),
        nullable=False,
        default="warning",
        index=True,
    )  # 'info', 'warning', 'high', 'critical'
    threat_type = db.Column(
        db.String(60),
        nullable=False,
        index=True,
    )  # 'ssrf_attempt', 'decompression_bomb', 'disguised_file', 'malware_detected', 'malicious_redirect', 'unsafe_svg', 'rate_anomaly'
    source_ip = db.Column(db.String(64), nullable=True)
    source_url = db.Column(db.String(2048), nullable=True)
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.JSON, nullable=False, default=dict)

    is_resolved = db.Column(db.Boolean, nullable=False, default=False, index=True)
    resolved_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_user_id])

    __table_args__ = (
        Index("ix_admin_security_alerts_threat_resolved", "threat_type", "is_resolved"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "severity": self.severity,
            "threat_type": self.threat_type,
            "source_ip": self.source_ip,
            "source_url": self.source_url,
            "message": self.message,
            "details": self.details or {},
            "is_resolved": self.is_resolved,
            "resolved_by_user_id": self.resolved_by_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
