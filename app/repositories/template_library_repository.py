"""Queries for personal definitions and active NoteType applications."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import defer, joinedload, selectinload, undefer
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.template import Template


def owner_filter(user_id):
    return Template.owner_user_id == int(user_id)


def _library_statement(user_id, *, include_archived=False, category=None, search=None, group="all"):
    statement = select(Template).where(owner_filter(user_id))
    if not include_archived:
        statement = statement.where(Template.archived_at.is_(None))
    if category:
        statement = statement.where(Template.primary_category == category)
    if search:
        # Literal substring, including percent/underscore.
        statement = statement.where(Template.name.contains(search, autoescape=True))
    active_usage = select(StudyApplication.id).join(NoteType).where(
        StudyApplication.template_id == Template.id,
        StudyApplication.status_code == "ACTIVE", NoteType.user_id == int(user_id),
    ).exists()
    if group == "mine":
        statement = statement.where(Template.origin != "market_copy")
    elif group == "market":
        statement = statement.where(Template.origin == "market_copy")
    elif group == "standalone":
        statement = statement.where(~active_usage)
    elif group == "in_use":
        statement = statement.where(active_usage)
    return statement


def library_query(session, user_id, *, include_archived=False, category=None, search=None, group="all", compact=False, page=None, page_size=24):
    statement = _library_statement(user_id, include_archived=include_archived, category=category, search=search, group=group)
    total = None
    if page is not None:
        total = session.scalar(select(func.count()).select_from(statement.subquery()))
        statement = statement.offset((page - 1) * page_size).limit(page_size)
    if compact:
        statement = statement.options(defer(Template.front_html), defer(Template.back_html), defer(Template.shared_css))
    items = session.execute(statement.order_by(Template.name, Template.id)).scalars().all()
    if compact:
        # Old definitions infer their inputs from source. Batch that compatibility
        # read for this page rather than triggering a deferred query per item.
        legacy_ids = [item.id for item in items if not item.input_schema]
        if legacy_ids:
            session.execute(select(Template).where(Template.id.in_(legacy_ids)).options(
                undefer(Template.front_html), undefer(Template.back_html),
                defer(Template.shared_css),
            )).scalars().all()
    return items, total


def template_usage(session, user_id, template_ids):
    """Load visible active usages once for an entire library page."""
    if not template_ids:
        return {}
    rows = session.execute(select(StudyApplication, NoteType.name).join(NoteType).where(
        StudyApplication.template_id.in_(template_ids),
        StudyApplication.status_code == "ACTIVE", NoteType.user_id == int(user_id),
    ).order_by(NoteType.name, StudyApplication.position, StudyApplication.id))
    result = {}
    for application, note_type_name in rows:
        result.setdefault(application.template_id, []).append({
            "id": application.id, "application_id": application.id,
            "note_type_id": application.note_type_id, "note_type_name": note_type_name,
            "occurrence_key": application.occurrence_key, "display_name": application.display_name,
            "position": application.position, "is_default": bool(application.is_default),
        })
    return result


def applications(session, note_type_id, *, include_retired=False):
    statement = select(StudyApplication).where(StudyApplication.note_type_id == str(note_type_id))
    if not include_retired:
        statement = statement.where(StudyApplication.status_code == "ACTIVE")
    return session.execute(statement.options(
        joinedload(StudyApplication.template),
        joinedload(StudyApplication.note_type).selectinload(NoteType.field_defs),
    ).order_by(StudyApplication.position, StudyApplication.id)).scalars().all()


class AttachedTemplate:
    """A definition presented through one explicitly scoped application.

    Definition identity/content remain on Template; attachment ordering,
    default and occurrence identity remain on StudyApplication.
    """

    def __init__(self, application):
        self.application = application
        self.template = application.template

    @property
    def application_id(self):
        return self.application.id

    @property
    def position(self):
        return self.application.position

    @property
    def is_default(self):
        return self.application.is_default

    def __getattr__(self, name):
        return getattr(self.template, name)


def attached_templates(session, note_type_id, *, include_retired=False):
    return [AttachedTemplate(row) for row in applications(session, note_type_id, include_retired=include_retired)]


_UNSPECIFIED_ORD = object()


def create_attached_template(session, *, note_type, source_ord=_UNSPECIFIED_ORD, occurrence_key="compat", **values):
    """Stage one owned definition and one attachment; caller owns transaction.

    No commit or per-Note writer runs here. Source ordinal, position and
    default belong to the explicitly created application.
    """
    position = int(values.pop("position", 0))
    is_default = bool(values.pop("is_default", False))
    owner = values.pop("owner_user_id", note_type.user_id)
    if int(owner) != int(note_type.user_id):
        raise ValueError("Attached template ownership must match its authoring NoteType owner.")
    from app.validators.template_library import infer_input_schema
    from models.field_def import FieldDef
    # Normal autoflush gives newly staged FieldDefs their stable IDs. Reading
    # the relation cache can miss additions staged by note_type_id after the
    # collection was loaded (seed/import/schema creation paths).
    fields = session.execute(select(FieldDef).where(FieldDef.note_type_id == note_type.id)
                             .order_by(FieldDef.position, FieldDef.id)).scalars().all()
    if values.get("input_schema") is None:
        values["input_schema"] = infer_input_schema(values.get("front_html", ""), values.get("back_html", ""), fields)
    bindings = values.pop("input_bindings", None)
    if bindings is None:
        bindings = {item["key"]: next((str(field.id) for field in fields if field.id and field.name == item["key"]), None)
                    for item in values["input_schema"]}
    template = Template(owner_user_id=owner, **values)
    application = StudyApplication(
        note_type=note_type, template=template, occurrence_key=occurrence_key,
        source_ord=position if source_ord is _UNSPECIFIED_ORD else source_ord,
        position=position, is_default=is_default, status_code="ACTIVE", input_bindings=bindings,
    )
    session.add_all([template, application])
    return template


def card_slots(session, note_type_id, *, rows=None):
    """(template_id, application_id) of every ACTIVE occurrence: the Cards a Note has.

    Cards are derived from these occurrences (ADR P11); a NoteType without an
    ACTIVE occurrence presents no Card.
    """
    rows = applications(session, note_type_id) if rows is None else [row for row in rows if row.status_code == "ACTIVE"]
    return [(row.template_id, row.id) for row in rows]


def template_used_outside(session, template_id, note_type_id):
    """Whether removing a definition from one NoteType would touch another NoteType's Cards."""
    note_type_id = str(note_type_id)
    return session.execute(select(StudyApplication.id).where(
        StudyApplication.template_id == template_id, StudyApplication.note_type_id != note_type_id,
    ).limit(1)).first() is not None


def detach_template(session, note_type_id, template):
    """Retire this NoteType's occurrences; the definition and progress stay.

    A retired occurrence's Cards leave discovery but stay addressable by key,
    and reactivating it brings the same keys back (ADR P11).
    """
    note_type_id = str(note_type_id)
    rows = session.execute(select(StudyApplication).where(
        StudyApplication.note_type_id == note_type_id, StudyApplication.template_id == template.id,
    ).order_by(StudyApplication.id).with_for_update()).scalars().all()
    for row in rows:
        row.status_code = "RETIRED"
    return rows
