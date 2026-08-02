"""Lifecycle and authentication for long-lived user integration tokens."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import re
import secrets

from sqlalchemy import or_

from models import db
from models.audit_log import AuditLog
from models.user import User
from models.user_api_token import UserApiToken


TOKEN_PREFIX = "flama_yt_"
TOKEN_RE = re.compile(r"^flama_yt_[0-9a-f]{8}_[A-Za-z0-9_-]{40,64}$")
DEFAULT_SCOPES = ("deck:read", "note-type:read", "note:check", "note:create")
ALLOWED_EXPIRY_DAYS = {30, 90, 180, 365}
MAX_ACTIVE_TOKENS_PER_USER = 10
MAX_TOKEN_RECORDS_PER_USER = 100


class TokenInputError(ValueError):
    pass


@dataclass(frozen=True)
class IssuedUserApiToken:
    record: UserApiToken
    plaintext: str


def _utcnow() -> datetime:
    return datetime.utcnow()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _serialize_scopes(scopes: tuple[str, ...] = DEFAULT_SCOPES) -> str:
    return json.dumps(list(scopes), separators=(",", ":"))


def parse_scopes(record: UserApiToken) -> frozenset[str]:
    try:
        values = json.loads(record.scopes)
    except (TypeError, ValueError):
        return frozenset()
    return frozenset(str(value) for value in values if isinstance(value, str))


def issue_token(*, user_id: int, name: str, expires_in_days: int | None = 180) -> IssuedUserApiToken:
    normalized_name = str(name or "").strip()
    if not normalized_name or len(normalized_name) > 120:
        raise TokenInputError("Token name must contain between 1 and 120 characters.")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized_name):
        raise TokenInputError("Token name cannot contain control characters.")
    if expires_in_days is not None and expires_in_days not in ALLOWED_EXPIRY_DAYS:
        raise TokenInputError("expires_in_days must be 30, 90, 180, 365, or null.")
    now = _utcnow()
    total_records = UserApiToken.query.filter_by(user_id=user_id).count()
    if total_records >= MAX_TOKEN_RECORDS_PER_USER:
        raise TokenInputError("This account has reached the integration token history limit.")
    active_count = UserApiToken.query.filter(
        UserApiToken.user_id == user_id,
        UserApiToken.revoked_at.is_(None),
        or_(UserApiToken.expires_at.is_(None), UserApiToken.expires_at > now),
    ).count()
    if active_count >= MAX_ACTIVE_TOKENS_PER_USER:
        raise TokenInputError("This account already has the maximum number of active integration tokens.")

    marker = secrets.token_hex(4)
    plaintext = f"{TOKEN_PREFIX}{marker}_{secrets.token_urlsafe(32)}"
    record = UserApiToken(
        user_id=user_id,
        name=normalized_name,
        token_hash=_hash_token(plaintext),
        token_prefix=f"{TOKEN_PREFIX}{marker}",
        scopes=_serialize_scopes(),
        expires_at=(now + timedelta(days=expires_in_days)) if expires_in_days is not None else None,
        created_at=now,
        updated_at=now,
    )
    db.session.add(record)
    db.session.flush()
    db.session.add(
        AuditLog(
            user_id=user_id,
            action="integration_token.create",
            payload={
                "token_id": record.id,
                "expires_at": record.expires_at.isoformat() if record.expires_at else None,
                "scopes": list(DEFAULT_SCOPES),
            },
        )
    )
    return IssuedUserApiToken(record=record, plaintext=plaintext)


def list_tokens(*, user_id: int) -> list[UserApiToken]:
    return (
        UserApiToken.query.filter_by(user_id=user_id)
        .order_by(UserApiToken.created_at.desc(), UserApiToken.id.desc())
        .all()
    )


def revoke_token(*, user_id: int, token_id: int) -> bool:
    record = UserApiToken.query.filter_by(id=token_id, user_id=user_id).first()
    if record is None:
        return False
    if record.revoked_at is None:
        record.revoked_at = _utcnow()
        db.session.add(
            AuditLog(
                user_id=user_id,
                action="integration_token.revoke",
                payload={"token_id": record.id},
            )
        )
    return True


def rotate_token(
    *,
    user_id: int,
    token_id: int,
    expires_in_days: int | None = 180,
) -> IssuedUserApiToken | None:
    record = UserApiToken.query.filter_by(id=token_id, user_id=user_id).first()
    if record is None:
        return None
    if record.revoked_at is None:
        record.revoked_at = _utcnow()
    issued = issue_token(user_id=user_id, name=record.name, expires_in_days=expires_in_days)
    db.session.add(
        AuditLog(
            user_id=user_id,
            action="integration_token.rotate",
            payload={"previous_token_id": record.id, "new_token_id": issued.record.id},
        )
    )
    return issued


def authenticate_token(plaintext: object, *, required_scope: str | None = None) -> tuple[UserApiToken, User] | None:
    if not isinstance(plaintext, str) or not TOKEN_RE.fullmatch(plaintext):
        return None
    digest = _hash_token(plaintext)
    record = UserApiToken.query.filter_by(token_hash=digest).first()
    if record is None or not hmac.compare_digest(record.token_hash, digest):
        return None
    now = _utcnow()
    if record.revoked_at is not None or (record.expires_at is not None and record.expires_at <= now):
        return None
    if required_scope and required_scope not in parse_scopes(record):
        return None
    user = db.session.get(User, record.user_id)
    if user is None or not user.is_active:
        return None
    if record.last_used_at is None or (now - record.last_used_at) >= timedelta(minutes=1):
        record.last_used_at = now
    return record, user


def serialize_token(record: UserApiToken) -> dict:
    now = _utcnow()
    if record.revoked_at is not None:
        status = "revoked"
    elif record.expires_at is not None and record.expires_at <= now:
        status = "expired"
    else:
        status = "active"
    return {
        "id": record.id,
        "name": record.name,
        "token_prefix": record.token_prefix,
        "scopes": sorted(parse_scopes(record)),
        "status": status,
        "expires_at": record.expires_at.isoformat() + "Z" if record.expires_at else None,
        "last_used_at": record.last_used_at.isoformat() + "Z" if record.last_used_at else None,
        "created_at": record.created_at.isoformat() + "Z",
    }
