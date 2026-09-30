"""Tell database failures apart from typed domain refusals, and retry deadlocks.

SQLAlchemy exceptions carry a ``code`` attribute (``e3q8`` for
``OperationalError``) that links to its documentation. It is not a domain
refusal code, so callers that map ``exc.code`` to an HTTP 409 must ask
``domain_error_code`` instead; otherwise a deadlock reaches the client as a
409 whose message contains the SQL statement.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

from sqlalchemy.exc import DBAPIError, SQLAlchemyError

logger = logging.getLogger(__name__)

MYSQL_DEADLOCK = 1213
DEADLOCK_RETRY_ATTEMPTS = 3

T = TypeVar("T")


def domain_error_code(exc: BaseException) -> str | None:
    """Return the typed refusal code of ``exc``, or None for database errors."""

    if isinstance(exc, SQLAlchemyError):
        return None
    code = getattr(exc, "code", None)
    return None if code is None else str(code)


def mysql_error_number(exc: BaseException) -> int | None:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ()) if original is not None else ()
    if args and isinstance(args[0], int):
        return int(args[0])
    return None


def is_mysql_deadlock(exc: BaseException) -> bool:
    """InnoDB rolled the whole transaction back; rerunning it is safe."""

    return isinstance(exc, DBAPIError) and mysql_error_number(exc) == MYSQL_DEADLOCK


def run_with_deadlock_retry(
    operation: Callable[[], T],
    *,
    session,
    label: str,
    attempts: int = DEADLOCK_RETRY_ATTEMPTS,
) -> T:
    """Run a self-committing unit of work, rerunning it after a deadlock.

    ``operation`` must own its transaction: it starts from a clean session,
    commits on success and leaves nothing outside the database behind before
    its commit. A deadlock victim's work is entirely rolled back by InnoDB, so
    the rerun sees fresh data and repeats no side effect. Lock wait timeouts
    are not retried: only the statement was rolled back and the caller has
    already waited ``innodb_lock_wait_timeout``.
    """

    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except DBAPIError as exc:
            if not is_mysql_deadlock(exc) or attempt >= attempts:
                raise
            try:
                session.rollback()
            except Exception:  # pragma: no cover - rollback of a dead txn
                pass
            logger.warning("Deadlock in %s; retrying (attempt %d of %d).", label, attempt + 1, attempts)
            time.sleep(random.uniform(0.02, 0.08) * attempt)
    raise AssertionError("unreachable")  # pragma: no cover
