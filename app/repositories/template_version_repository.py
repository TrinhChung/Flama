"""Persistence for append-only template source history.

The Template row is the serialization lock and remains the live source of truth.
Core operations avoid recursively flushing the ORM while finalizing a commit.
"""

from datetime import datetime

from sqlalchemy import and_, insert, or_, select, update

from models.model_uuid import uuid_str
from models.note_type import NoteType
from models.template import Template
from models.template_version import TemplateVersion
from models.user import User


class TemplateVersionStateError(RuntimeError):
    pass


def snapshots(session, template_ids, *, lock=True):
    table = Template.__table__
    result = {}
    ids = sorted(set(str(value) for value in template_ids))
    for offset in range(0, len(ids), 500):
        statement = select(table).where(table.c.id.in_(ids[offset:offset + 500])).order_by(table.c.id)
        if lock:
            statement = statement.with_for_update()
        result.update((row["id"], dict(row)) for row in session.execute(statement).mappings())
    if any(row["owner_user_id"] is None for row in result.values()):
        raise TemplateVersionStateError("Template owner must be migrated before source history is written.")
    return result


def append_snapshot(session, snapshot, *, origin, actor_user_id=None, change_note=None, force=False):
    """Append under the caller's Template row lock; do not commit."""
    from app.services.template_tokens import template_content_hash

    table = TemplateVersion.__table__
    template_id = snapshot["id"]
    head = None
    if snapshot["current_version_id"]:
        head = session.execute(select(table).where(
            table.c.id == snapshot["current_version_id"], table.c.template_id == template_id,
        ).with_for_update()).mappings().first()
        if head is None:
            raise TemplateVersionStateError(f"Template {template_id} has an invalid history pointer.")
    elif session.execute(select(table.c.id).where(table.c.template_id == template_id).limit(1)).first():
        raise TemplateVersionStateError(f"Template {template_id} has history but no current version.")

    sources = {key: snapshot[key] or "" for key in ("front_html", "back_html", "shared_css")}
    schema = snapshot["input_schema"] if snapshot["input_schema"] is not None else []
    content_hash = template_content_hash(**sources)
    if head is not None and not force and head["content_hash"] == content_hash and head["input_schema"] == schema:
        return str(head["id"]), False

    # Parent locking serializes this identity. Allocate from the current-read
    # head, avoiding stale RR MAX reads and missing-key gap locks when two
    # unrelated new templates insert their first versions concurrently. The
    # unique sequence constraint rejects inconsistent/out-of-band history.
    number = int(head["version_no"] if head is not None else 0) + 1
    version_id = uuid_str()
    session.execute(insert(table).values(
        id=version_id, template_id=template_id, version_no=number,
        **sources, input_schema=schema, content_hash=content_hash,
        origin=origin, change_note=change_note, created_by_user_id=actor_user_id,
        created_at=datetime.utcnow(),
    ))
    # Disable the Template.updated_at onupdate default for history-only metadata.
    session.execute(update(Template.__table__).where(Template.id == template_id).values(
        current_version_id=version_id, owner_user_id=snapshot["owner_user_id"],
        updated_at=snapshot["updated_at"],
    ))
    snapshot["current_version_id"] = version_id
    return version_id, True


def owned_template(session, *, user_id, template_id, note_type_id=None, lock=False):
    statement = select(Template).where(Template.id == str(template_id), Template.owner_user_id == int(user_id))
    if note_type_id is not None:
        from models.study_application import StudyApplication
        statement = statement.where(select(StudyApplication.id).where(
            StudyApplication.template_id == Template.id, StudyApplication.note_type_id == str(note_type_id),
            StudyApplication.status_code == "ACTIVE", StudyApplication.note_type.has(NoteType.user_id == int(user_id)),
        ).exists())
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return session.execute(statement).scalar_one_or_none()


def versions_with_authors(session, *, template_id, version_id=None):
    statement = select(TemplateVersion, User.id, User.username).outerjoin(
        User, User.id == TemplateVersion.created_by_user_id,
    ).where(TemplateVersion.template_id == template_id)
    if version_id is not None:
        statement = statement.where(TemplateVersion.id == str(version_id))
    return session.execute(statement.order_by(TemplateVersion.version_no.desc())).all()
