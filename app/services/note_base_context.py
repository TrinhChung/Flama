"""Explicit, audited authority for writes to the single published Note Base.

The rollout switch is deliberately one-way in production.  These contexts do
not commit: callers must flush their writes inside the context and retain their
existing transaction ownership.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import logging

from flask import current_app, has_app_context


_BASE_WRITE = ContextVar("flama_note_base_write", default=None)
_AUTHOR_VIEW = ContextVar("flama_note_author_view", default=None)
_LISTING_FIELDS = ContextVar("flama_note_listing_fields", default=None)
_log = logging.getLogger(__name__)


def published_base_enabled() -> bool:
    return bool(has_app_context() and current_app.config.get("NOTE_PUBLISHED_BASE_ENABLED", False))


def base_write_authority():
    """Return ``(mode, reason)`` only inside an explicit Base write scope."""
    return _BASE_WRITE.get()


@contextmanager
def published_base_write(reason="publish", session=None, listing_field_ids=None):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("A published Base write requires a non-empty reason")
    token = _BASE_WRITE.set(("publish", reason.strip()))
    fence_token = _LISTING_FIELDS.set(frozenset(listing_field_ids) if listing_field_ids is not None else None)
    try:
        yield
    finally:
        _BASE_WRITE.reset(token)
        _LISTING_FIELDS.reset(fence_token)


def listing_fenced_fields():
    return _LISTING_FIELDS.get()


@contextmanager
def base_maintenance(reason, session=None):
    """Technical maintenance, never an alternative author editing path."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Base maintenance requires a non-empty audit reason")
    token = _BASE_WRITE.set(("maintenance", reason.strip()))
    fence_token = _LISTING_FIELDS.set(None)
    _log.warning("note_base_maintenance begin reason=%s", reason.strip())
    try:
        yield
    except Exception:
        _log.exception("note_base_maintenance failed reason=%s", reason.strip())
        raise
    finally:
        _log.warning("note_base_maintenance end reason=%s", reason.strip())
        _BASE_WRITE.reset(token)
        _LISTING_FIELDS.reset(fence_token)


@contextmanager
def note_author_view(user_id):
    """Select the author for non-HTTP jobs that read author draft deletions."""
    token = _AUTHOR_VIEW.set(int(user_id))
    try:
        yield
    finally:
        _AUTHOR_VIEW.reset(token)


def author_view_user_id():
    explicit = _AUTHOR_VIEW.get()
    if explicit is not None:
        return explicit
    # Request authentication remains the authority; no source Note can select
    # another learner's private view merely by being loaded into a session.
    from flask import has_request_context
    if has_request_context():
        from flask import request
        token_actor = request.environ.get("flama.note_author_user_id")
        if token_actor is not None:
            return int(token_actor)
        # This helper also runs during SQLAlchemy's User load. Resolving the
        # current_user proxy here would re-enter the login loader recursively.
        from flask import g
        user = g.get("_login_user")
        if user is not None:
            from sqlalchemy import inspect
            state = inspect(user, raiseerr=False)
            # The loaded User may have expired after commit. Even its
            # is_authenticated/is_active/id attributes can issue SQL here.
            if state is not None and state.identity:
                return int(state.identity[0])
    return None


def author_drafts_visible(owner_user_id):
    """Anonymous/foreign HTTP readers fail closed; trusted jobs may select an owner."""
    from flask import has_request_context
    actor = author_view_user_id()
    return actor == owner_user_id if actor is not None else not has_request_context()


def require_note_author_write(owner_user_id):
    if not base_write_authority() and not author_drafts_visible(owner_user_id):
        from app.services.field_value_identity_service import FieldIdentityConflict
        raise FieldIdentityConflict("Only the owner can change a published Note's draft.")
