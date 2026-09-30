"""Remember the progress rows this transaction inserted.

A ``FOR UPDATE`` read that finds nothing takes a gap lock. Children of a
subject or contributor inserted by the current transaction can only have been
created by this same transaction: every child row has a foreign key to its
uncommitted parent. Subject and contributor ids grow at the end of their
indexes, so the gap locks of those reads all land on the same supremum and
concurrent Note creations deadlock on them. Callers ask
``inserted_in_transaction`` and read such children without ``FOR UPDATE``
(a plain read still sees this transaction's own rows).

Marks are bound to the root transaction that inserted the rows: they are
dropped when it ends and are never honoured by any later transaction.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session, scoped_session

_KEY = "study_rows_inserted_in_transaction"
SUBJECT = "subject"
CONTRIBUTOR = "contributor"


def _root_transaction(session):
    real = session() if isinstance(session, scoped_session) else session
    transaction = real.get_transaction()
    return real, transaction


def remember_inserted(session, kind: str, row_id) -> None:
    if row_id is None:
        return
    real, transaction = _root_transaction(session)
    if transaction is None:
        return  # nothing was inserted outside a transaction
    owner, marks = real.info.get(_KEY, (None, None))
    if owner is not transaction:
        marks = {}
        real.info[_KEY] = (transaction, marks)
    marks.setdefault(kind, set()).add(int(row_id))


def inserted_in_transaction(session, kind: str, row_id) -> bool:
    if row_id is None:
        return False
    real, transaction = _root_transaction(session)
    owner, marks = real.info.get(_KEY, (None, None))
    if transaction is None or owner is not transaction:
        return False
    return int(row_id) in marks.get(kind, ())


@event.listens_for(Session, "after_transaction_end")
def _forget_inserted_rows(session, transaction) -> None:
    if transaction.parent is None:
        session.info.pop(_KEY, None)
