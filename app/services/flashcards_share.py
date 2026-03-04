"""Compatibility shim for legacy `app.services.flashcards_share` imports."""

from __future__ import annotations

from sqlalchemy.exc import OperationalError

from app.services.flashcards_share_service import *  # noqa: F401,F403


def _is_mysql_deadlock(exc: OperationalError) -> bool:
    """Match old deadlock detection helper used by install retry loops."""
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ()) if original is not None else ()
    if args:
        if str(args[0]) == "1213":
            return True
    message = str(exc).lower()
    return "deadlock" in message and ("1213" in message or "try restarting transaction" in message)

