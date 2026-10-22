"""Evidence of pre-release NoteType receipts; never infer historical pins."""

from sqlalchemy import exists, select

from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.study_application import StudyApplication
from models.template import Template


def legacy_received_condition():
    """Correlated predicate for templates created by the old receipt copier.

    Subsequent edits preserve created_at. Later authored attachments are not
    classified simply because their NoteType was once installed.
    """
    app = StudyApplication.__table__.alias("legacy_template_application")
    install = NoteTypeInstall.__table__.alias("legacy_template_install")
    local = NoteType.__table__.alias("legacy_template_note_type")
    return exists(select(1).select_from(app.join(install,
        install.c.installed_note_type_id == app.c.note_type_id).join(local,
        local.c.id == install.c.installed_note_type_id)).where(
        app.c.template_id == Template.id,
        install.c.applied_release_id.is_(None),
        install.c.user_id == Template.owner_user_id,
        local.c.user_id == install.c.user_id,
        Template.created_at == install.c.installed_at,
        local.c.created_at == install.c.installed_at,
    ).correlate(Template))


def candidate_installs(session, template_id, *, current_read=False):
    statement = select(NoteTypeInstall.__table__).join(
        StudyApplication, StudyApplication.note_type_id == NoteTypeInstall.installed_note_type_id,
    ).join(Template, Template.id == StudyApplication.template_id).join(
        NoteType, NoteType.id == NoteTypeInstall.installed_note_type_id,
    ).where(
        Template.id == str(template_id), NoteTypeInstall.applied_release_id.is_(None),
        NoteTypeInstall.user_id == Template.owner_user_id,
        NoteType.user_id == NoteTypeInstall.user_id,
        Template.created_at == NoteTypeInstall.installed_at,
        NoteType.created_at == NoteTypeInstall.installed_at,
    ).order_by(NoteTypeInstall.id)
    if current_read:
        statement = statement.with_for_update()
    rows = session.execute(statement).mappings()
    return list({row["id"]: dict(row) for row in rows}.values())


def template(session, template_id, *, current_read=False):
    statement = select(Template.__table__).where(Template.id == str(template_id))
    if current_read:
        statement = statement.with_for_update()
    row = session.execute(statement).mappings().first()
    return dict(row) if row else None


def active_template_ids(session, note_type_id, *, current_read=False):
    statement = select(StudyApplication.template_id).where(
        StudyApplication.note_type_id == note_type_id, StudyApplication.status_code == "ACTIVE",
    ).distinct().order_by(StudyApplication.template_id)
    if current_read:
        statement = statement.with_for_update()
    return list(session.execute(statement).scalars())


def candidate_template_ids(session, *, user_id=None, current_read=False):
    statement = select(Template.id).where(legacy_received_condition()).order_by(Template.id)
    if user_id is not None:
        statement = statement.where(Template.owner_user_id == int(user_id))
    if current_read:
        statement = statement.with_for_update()
    return list(session.execute(statement).scalars())


def legacy_license_source_ids(session, *, user_id, source_template_ids=None, current_read=False):
    from app.services.legacy_template_provenance_service import legacy_reference
    requested = set(source_template_ids) if source_template_ids is not None else None
    result = set()
    for template_id in candidate_template_ids(session, user_id=user_id, current_read=current_read):
        reference = legacy_reference(session, template_id, current_read=current_read)
        source_id = (reference or {}).get("source_template_id")
        if source_id and (requested is None or source_id in requested):
            result.add(source_id)
    return result
