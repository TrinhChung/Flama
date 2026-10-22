"""Read attached definitions and their original marketplace provenance."""

from sqlalchemy import select

from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.study_application import StudyApplication
from models.template import Template
from models.template_subscription import TemplateSubscription
from models.user import User


def note_type(session, note_type_id):
    return session.get(NoteType, str(note_type_id))


def is_received_note_type(session, note_type_id):
    return session.execute(select(NoteTypeInstall.id).where(
        NoteTypeInstall.installed_note_type_id == note_type_id,
    ).limit(1)).first() is not None


def attached_templates(session, note_type_id):
    rows = session.execute(select(Template.__table__).join(
        StudyApplication, StudyApplication.template_id == Template.id,
    ).where(
        StudyApplication.note_type_id == note_type_id,
        StudyApplication.status_code == "ACTIVE",
    ).order_by(StudyApplication.position, StudyApplication.id)).mappings()
    return list({row["id"]: dict(row) for row in rows}.values())


def subscription(session, *, user_id, source_template_id):
    row = session.execute(select(TemplateSubscription.__table__).where(
        TemplateSubscription.user_id == int(user_id),
        TemplateSubscription.source_template_id == source_template_id,
    )).mappings().first()
    return dict(row) if row else None


def author_username(session, user_id):
    return session.execute(select(User.username).where(User.id == user_id)).scalar_one_or_none()
