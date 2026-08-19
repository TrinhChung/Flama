"""OAuth 2.1 Authorization Code model with PKCE support."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from models import db


class OAuthAuthorizationCode(db.Model):
    __tablename__ = "oauth_authorization_codes"

    id = db.Column(db.Integer, primary_key=True)
    code_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("oauth_clients.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    redirect_uri = db.Column(db.String(500), nullable=False)
    scopes = db.Column(db.Text, nullable=False, default="[]")
    code_challenge = db.Column(db.String(128), nullable=False)
    code_challenge_method = db.Column(db.String(10), nullable=False, default="S256")
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    is_used = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    client = db.relationship("OAuthClient", foreign_keys=[client_id])
    user = db.relationship("User", foreign_keys=[user_id])

    def get_scopes(self) -> list[str]:
        if not self.scopes:
            return []
        try:
            parsed = json.loads(self.scopes)
            if isinstance(parsed, list):
                return [str(s).strip() for s in parsed if str(s).strip()]
        except Exception:
            pass
        return [s.strip() for s in self.scopes.split(",") if s.strip()]

    def is_expired(self, now: datetime | None = None) -> bool:
        current_time = now or datetime.utcnow()
        return self.expires_at <= current_time
