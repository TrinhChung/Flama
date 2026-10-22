"""Persistence for complete immutable NoteType publications."""

from sqlalchemy import func, select

from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.note_type_release import NoteTypeRelease
from models.template_release import TemplateRelease
from models.template_version import TemplateVersion
from models.template import Template
from models.study_application import StudyApplication


def lock_source(session, source_id):
    return session.execute(select(NoteType).where(NoteType.id == source_id).with_for_update()).scalar_one()


def is_received_note_type(session, note_type_id):
    return session.execute(select(NoteTypeInstall.id).where(
        NoteTypeInstall.installed_note_type_id == note_type_id,
    ).limit(1)).first() is not None


def has_foreign_template(session, source_id, owner_user_id):
    return session.execute(select(Template.id).join(StudyApplication).where(
        StudyApplication.note_type_id == source_id, StudyApplication.status_code == "ACTIVE",
        Template.owner_user_id != owner_user_id,
    ).limit(1)).first() is not None


def release(session, release_id, source_id):
    if not release_id:
        return None
    return session.execute(select(NoteTypeRelease).where(
        NoteTypeRelease.id == release_id, NoteTypeRelease.note_type_id == source_id,
    )).scalar_one_or_none()


def by_label(session, source_id, label):
    return session.execute(select(NoteTypeRelease).where(
        NoteTypeRelease.note_type_id == source_id, NoteTypeRelease.version_label == label,
    )).scalar_one_or_none()


def next_sequence(session, source_id):
    return int(session.execute(select(func.max(NoteTypeRelease.sequence_no)).where(
        NoteTypeRelease.note_type_id == source_id)).scalar() or 0) + 1


def install(session, source_id, user_id):
    return session.execute(select(NoteTypeInstall).where(
        NoteTypeInstall.source_note_type_id == source_id, NoteTypeInstall.user_id == user_id,
    ).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()


def template_contents(session, release_ids):
    if not release_ids:
        return {}
    rows = session.execute(select(TemplateRelease.id.label("release_id"), TemplateRelease.template_id.label("source_template_id"),
        TemplateVersion.__table__).join(TemplateVersion, TemplateVersion.id == TemplateRelease.version_id)
        .where(TemplateRelease.id.in_(release_ids))).mappings().all()
    # Explicit release aliases keep TemplateVersion.id separate from release id.
    return {row["release_id"]: dict(row) for row in rows}
