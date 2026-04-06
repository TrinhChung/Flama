from datetime import datetime

from models import db


class McpAccessToken(db.Model):
    __tablename__ = "mcp_access_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    scopes = db.Column(db.Text, nullable=False, default="[]")
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    max_requests = db.Column(db.Integer, nullable=False, default=30)
    used_requests = db.Column(db.Integer, nullable=False, default=0)
    revoked = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        db.Index(
            "ix_mcp_access_tokens_user_revoked_created_at",
            "user_id",
            "revoked",
            "created_at",
        ),
    )
