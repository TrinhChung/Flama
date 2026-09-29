"""Snapshot-only non-locking read transaction boundary for analytics endpoints.

These reads never issue study leases, repair tokens, or lock progress rows.
The HTTP entry points (/api/dashboard, /api/statistics/overview) own a fresh,
read-only REPEATABLE READ transaction with consistent snapshot.
"""

from contextlib import contextmanager

from models import db


@contextmanager
def analytics_read_transaction():
    """Own the canonical GET's transaction, including authentication reads.

    Called only after authentication/timezone updates, before analytics work.
    Reuse the request session/connection pool slot instead of opening a second
    connection per request. Reject pending writes rather than discarding them.
    Never use this boundary inside a writer or the Study session transaction.
    """
    session = db.session()
    if session.new or session.dirty or session.deleted:
        raise RuntimeError("Analytics must start after pending writes are resolved.")
    session.rollback()
    try:
        if session.get_bind().dialect.name == "mysql":
            connection = session.connection(
                execution_options={"isolation_level": "REPEATABLE READ"}
            )
            connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        with session.no_autoflush:
            yield
    finally:
        session.rollback()
