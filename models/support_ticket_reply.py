import json
from datetime import datetime
from sqlalchemy import Index

from models import db
from models.model_uuid import uuid_str


class SupportTicketReply(db.Model):
    """Replies / Message thread on a support ticket."""

    __tablename__ = "support_ticket_replies"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    ticket_id = db.Column(
        db.String(36),
        db.ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_admin_reply = db.Column(db.Boolean, nullable=False, default=False)
    sender_name = db.Column(db.String(150), nullable=True)
    message = db.Column(db.Text, nullable=False)
    attachment_urls_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship("SupportTicket", back_populates="replies")
    user = db.relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_support_ticket_replies_ticket_id", "ticket_id"),
        Index("ix_support_ticket_replies_created_at", "created_at"),
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

    def to_dict(self) -> dict:
        sender = self.sender_name
        if not sender:
            if self.is_admin_reply:
                sender = "Quản trị viên (Admin)"
            elif self.user:
                sender = self.user.username
            else:
                sender = "Người dùng"
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "user_id": self.user_id,
            "is_admin_reply": self.is_admin_reply,
            "sender_name": sender,
            "message": self.message,
            "attachment_urls": self.attachment_urls,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
