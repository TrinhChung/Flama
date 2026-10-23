"""Database and transaction utility helpers."""

from __future__ import annotations

from contextlib import contextmanager
import logging
from typing import Generator

from models import db

logger = logging.getLogger(__name__)


@contextmanager
def transaction() -> Generator[None, None, None]:
    """Execute a block inside an atomic database transaction.

    Automatically commits if the block completes without exception.
    Automatically rolls back and re-raises if any exception occurs.

    Example::

        with transaction():
            db.session.add(user)
            db.session.add(profile)
    """
    try:
        yield
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            logger.exception("Failed to rollback database session.")
        raise
