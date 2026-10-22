"""Small library rows without loading definitions or template source HTML."""

from sqlalchemy import exists, func, or_, select

from models import db
from models.field_def import FieldDef
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.study_application import StudyApplication


def list_summaries(*, user_id):
    installed = exists(select(NoteTypeInstall.id).where(
        NoteTypeInstall.user_id == user_id,
        NoteTypeInstall.installed_note_type_id == NoteType.id,
    ))
    fields = select(func.count(FieldDef.id)).where(
        FieldDef.note_type_id == NoteType.id,
    ).correlate(NoteType).scalar_subquery()
    applications = select(func.count(StudyApplication.id)).where(
        StudyApplication.note_type_id == NoteType.id,
        StudyApplication.status_code == "ACTIVE",
    ).correlate(NoteType).scalar_subquery()
    statement = select(
        NoteType.id, NoteType.name, NoteType.description, NoteType.publish_status,
        NoteType.version, NoteType.created_at, NoteType.updated_at,
        installed.label("is_marketplace_install"), fields.label("field_count"),
        applications.label("template_count"),
    ).where(or_(NoteType.user_id == user_id, installed)).order_by(NoteType.name, NoteType.id)
    return [{key: value.isoformat() if key in {"created_at", "updated_at"} and value else value
             for key, value in row.items()}
            for row in db.session.execute(statement).mappings()]
