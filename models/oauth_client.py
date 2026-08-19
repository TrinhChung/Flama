"""OAuth 2.1 Client model for remote MCP integrations."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from models import db


class OAuthClient(db.Model):
    __tablename__ = "oauth_clients"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    client_secret_hash = db.Column(db.String(255), nullable=True)
    client_name = db.Column(db.String(120), nullable=False, default="OAuth Client")
    client_uri = db.Column(db.String(255), nullable=True)
    redirect_uris = db.Column(db.Text, nullable=False, default="[]")
    is_confidential = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def get_redirect_uris(self) -> list[str]:
        if not self.redirect_uris:
            return []
        try:
            parsed = json.loads(self.redirect_uris)
            if isinstance(parsed, list):
                return [str(u).strip() for u in parsed if str(u).strip()]
        except Exception:
            pass
        return [self.redirect_uris.strip()] if self.redirect_uris.strip() else []

    def is_valid_redirect_uri(self, uri: str) -> bool:
        norm_uri = str(uri or "").strip()
        if not norm_uri:
            return False
        return norm_uri in self.get_redirect_uris()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_name": self.client_name,
            "client_uri": self.client_uri,
            "redirect_uris": self.get_redirect_uris(),
            "is_confidential": bool(self.is_confidential),
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
