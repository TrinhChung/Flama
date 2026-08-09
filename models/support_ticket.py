import json
from datetime import datetime
from sqlalchemy import Index, UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class SupportTicket(db.Model):
    """Support & Bug Report Ticket model."""

    __tablename__ = "support_tickets"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    ticket_code = db.Column(db.String(32), nullable=False)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_email = db.Column(db.String(255), nullable=True)
    sender_name = db.Column(db.String(150), nullable=True)
    category = db.Column(db.String(50), nullable=False, default="bug")
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    reproduce_steps = db.Column(db.Text, nullable=True)
    screen_url = db.Column(db.String(500), nullable=True)
    screen_name = db.Column(db.String(255), nullable=True)
    attachment_urls_json = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="open")
    priority = db.Column(db.String(20), nullable=False, default="medium")
    admin_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    resolved_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])
    replies = db.relationship(
        "SupportTicketReply",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="SupportTicketReply.created_at.asc()",
    )

    __table_args__ = (
        UniqueConstraint("ticket_code", name="uq_support_tickets_ticket_code"),
        Index("ix_support_tickets_user_id", "user_id"),
        Index("ix_support_tickets_status", "status"),
        Index("ix_support_tickets_category", "category"),
        Index("ix_support_tickets_created_at", "created_at"),
    )

    @property
    def attachment_urls(self) -> list[str]:
        if not self.attachment_urls_json:
            return []
        try:
            parsed = json.loads(self.attachment_urls_json)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except Exception:
            pass
        return []

    @attachment_urls.setter
    def attachment_urls(self, urls: list[str]) -> None:
        if not urls:
            self.attachment_urls_json = None
        else:
            self.attachment_urls_json = json.dumps(urls)

    def to_dict(self, include_replies: bool = False) -> dict:
        data = {
            "id": self.id,
            "ticket_code": self.ticket_code,
            "user_id": self.user_id,
            "user_email": self.user_email or (self.user.email if self.user else None),
            "sender_name": self.sender_name or (self.user.username if self.user else "Khách vô danh"),
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "reproduce_steps": self.reproduce_steps or "",
            "screen_url": self.screen_url or "",
            "screen_name": self.screen_name or "",
            "attachment_urls": self.attachment_urls,
            "status": self.status,
            "priority": self.priority,
            "admin_notes": self.admin_notes or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
        if include_replies:
            data["replies"] = [reply.to_dict() for reply in self.replies]
        return data
