"""StudyMode composition discovery, identity, and selection resolution.

Phase 3 keeps the current Template/Card rows as compatibility authority while
making the selected composition explicit. Installed deck source cards retain
their physical identity, but their effective composition is scoped to the
logical install so two overlays cannot silently share presentation context.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import joinedload

from models import db
from models.card import Card
from models.note import Note
from models.note_type import NoteType
from models.study_application import COMPAT_OCCURRENCE_KEY, StudyApplication
from models.template import Template
from app.repositories.template_library_repository import active_card_condition
from app.repositories.deck_tree_query import collect_subtree_ids
from app.services import flashcards_share_service
from app.services.study_action_runtime import REVIEW_TRIGGER_CONTRACT_VERSION
from app.services.study_algorithm_registry import DEFAULT_ALGORITHM_IDENTITY


DEFAULT_STUDY_MODE_KEY = "flashcard"
DEFAULT_INTERACTION_KEY = "review.four-rating"
DEFAULT_TRIGGER_KEY = "scheduler.review"
COMPOSITION_CONTRACT_VERSION = "applied-composition.compat.v1"
COMPOSITION_SCOPE_SCHEMA_VERSION = "study-scope-compositions.v2"

CONTEXT_OWNED = "owned"
CONTEXT_INSTALLED_SOURCE = "installed_source"
CONTEXT_INSTALLED_LOCAL = "installed_local"


class StudyCompositionError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details


@dataclass(frozen=True)
class AppliedComposition:
    composition_id: str
    mode_key: str
    note_type_id: str
    note_type_name: str
    template_id: str
    template_name: str
    is_default: bool
    context_kind: str = CONTEXT_OWNED
    install_id: str | None = None
    definition_id: str = ""
    application_id: str = ""
    interaction_key: str = DEFAULT_INTERACTION_KEY
    trigger_key: str = DEFAULT_TRIGGER_KEY
    trigger_contract_version: str = REVIEW_TRIGGER_CONTRACT_VERSION
    algorithm_key: str = DEFAULT_ALGORITHM_IDENTITY.key
    algorithm_version: str = DEFAULT_ALGORITHM_IDENTITY.version
    study_application_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CompositionGroup:
    note_type_id: str
    note_type_name: str
    compositions: tuple[AppliedComposition, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_type_id": self.note_type_id,
            "note_type_name": self.note_type_name,
            "compositions": [item.to_dict() for item in self.compositions],
        }


@dataclass(frozen=True)
class ResolvedCompositionSelection:
    composition: AppliedComposition
    resolution: str


def make_compatibility_composition_id(
    note_type_id: str | int,
    template_id: str | int,
) -> str:
    return f"comp:notetype:{note_type_id}:template:{template_id}"


def make_installed_composition_id(
    *,
    install_id: str | int,
    context_kind: str,
    note_type_id: str | int,
    template_id: str | int,
) -> str:
    if context_kind not in {CONTEXT_INSTALLED_SOURCE, CONTEXT_INSTALLED_LOCAL}:
        raise ValueError("Installed composition context must be source or local.")
    side = "source" if context_kind == CONTEXT_INSTALLED_SOURCE else "local"
    return (
        f"comp:install:{install_id}:{side}:"
        f"notetype:{note_type_id}:template:{template_id}"
    )


def build_compatibility_composition(
    template: Template,
    *,
    context_kind: str = CONTEXT_OWNED,
    install_id: str | None = None,
    mode_key: str = DEFAULT_STUDY_MODE_KEY,
    interaction_key: str = DEFAULT_INTERACTION_KEY,
    trigger_key: str = DEFAULT_TRIGGER_KEY,
    trigger_contract_version: str = REVIEW_TRIGGER_CONTRACT_VERSION,
    algorithm_key: str = DEFAULT_ALGORITHM_IDENTITY.key,
    algorithm_version: str = DEFAULT_ALGORITHM_IDENTITY.version,
    note_type: Any = None,
    application: Any = None,
) -> AppliedComposition:
    note_type = note_type if note_type is not None else getattr(template, "note_type", None)
    note_type_id = str(getattr(note_type, "id", None) or template.note_type_id)
    template_id = str(template.id)
    note_type_name = str(
        getattr(note_type, "name", "") or ""
    )
    if context_kind == CONTEXT_OWNED:
        composition_id = make_compatibility_composition_id(
            note_type_id,
            template_id,
        )
    else:
        if not install_id:
            raise ValueError("Installed composition requires install_id.")
        composition_id = make_installed_composition_id(
            install_id=install_id,
            context_kind=context_kind,
            note_type_id=note_type_id,
            template_id=template_id,
        )
    definition_id = f"legacy-template:{template_id}"
    repeated = application is not None and application.occurrence_key != COMPAT_OCCURRENCE_KEY
    if repeated:
        composition_id += f":application:{application.id}"
    return AppliedComposition(
        composition_id=composition_id,
        mode_key=mode_key,
        note_type_id=note_type_id,
        note_type_name=note_type_name,
        template_id=template_id,
        template_name=str(getattr(application, "display_name", None) or template.name or ""),
        is_default=bool(application.is_default if application is not None else template.is_default),
        context_kind=context_kind,
        install_id=str(install_id) if install_id else None,
        definition_id=definition_id,
        application_id=str(application.id) if repeated else composition_id,
        interaction_key=interaction_key,
        trigger_key=trigger_key,
        trigger_contract_version=trigger_contract_version,
        algorithm_key=algorithm_key,
        algorithm_version=algorithm_version,
        study_application_id=str(application.id) if application is not None and getattr(application, "id", None) else None,
    )


def _card_context_kind(
    card: Card,
    clone_scope: flashcards_share_service.CloneDeckScope | None,
) -> str:
    if clone_scope is None:
        return CONTEXT_OWNED
    note = card.note
    if (
        note is not None
        and note.deck_id is not None
        and int(note.deck_id) in set(clone_scope.local_deck_ids)
        and int(note.user_id) == int(clone_scope.install.user_id)
    ):
        return CONTEXT_INSTALLED_LOCAL
    return CONTEXT_INSTALLED_SOURCE


def resolve_compatibility_composition_for_card(
    card: Card,
    clone_scope: flashcards_share_service.CloneDeckScope | None = None,
) -> AppliedComposition:
    template = getattr(card, "template", None) or db.session.get(
        Template,
        card.template_id,
    )
    if template is None:
        raise ValueError(f"Card {card.id} references missing template {card.template_id}")
    context_kind = _card_context_kind(card, clone_scope)
    application = getattr(card, "application", None)
    if application is None and getattr(card, "application_id", None):
        application = db.session.get(StudyApplication, card.application_id)
    return build_compatibility_composition(
        template,
        note_type=getattr(getattr(card, "note", None), "note_type", None),
        application=application,
        context_kind=context_kind,
        install_id=(str(clone_scope.install.id) if clone_scope is not None else None),
    )


def resolve_compatibility_compositions_for_note_type(
    note_type_id: str | int,
) -> list[AppliedComposition]:
    applications = StudyApplication.query.filter(
        StudyApplication.note_type_id == str(note_type_id),
        StudyApplication.status_code == "ACTIVE",
    ).options(joinedload(StudyApplication.template), joinedload(StudyApplication.note_type)).order_by(
        StudyApplication.position.asc(), StudyApplication.id.asc(),
    ).all()
    compositions = [build_compatibility_composition(
        item.template, note_type=item.note_type, application=item,
    ) for item in applications]
    templates = (
        Template.query.filter(Template.note_type_id == str(note_type_id))
        .filter(~Template.id.in_(db.session.query(StudyApplication.template_id).filter(
            StudyApplication.note_type_id == str(note_type_id),
        )))
        .options(joinedload(Template.note_type))
        .order_by(Template.position.asc(), Template.id.asc())
        .all()
    )
    return compositions + [build_compatibility_composition(item) for item in templates]


def _composition_sort_key(
    item: AppliedComposition, positions: dict[str, int]
) -> tuple[Any, ...]:
    return (
        item.note_type_name.casefold(),
        item.note_type_id,
        positions.get(item.composition_id, positions.get(item.application_id, positions.get(item.template_id, 0))),
        item.template_id,
        item.context_kind,
        item.composition_id,
    )


def list_available_compositions_for_query(
    query: Any,
    *,
    clone_scope: flashcards_share_service.CloneDeckScope | None,
) -> list[AppliedComposition]:
    """Return deterministic compositions backed by cards in an effective scope."""

    eligible_card_ids = (
        (query.filter(active_card_condition()) if clone_scope is None else query)
        .with_entities(Card.id.label("card_id"))
        .order_by(None)
        .subquery()
    )
    rows = (
        db.session.query(
            db.func.min(Card.id).label("sample_card_id"),
            Card.template_id,
            Card.application_id,
            Note.note_type_id,
            NoteType.name.label("note_type_name"),
            StudyApplication.occurrence_key,
            StudyApplication.display_name,
            StudyApplication.position,
            StudyApplication.is_default,
            Note.deck_id,
            Note.user_id,
        )
        .join(Note, Card.note_id == Note.id)
        .join(NoteType, Note.note_type_id == NoteType.id)
        .outerjoin(StudyApplication, Card.application_id == StudyApplication.id)
        .filter(
            Card.id.in_(
                db.session.query(eligible_card_ids.c.card_id)
            )
        )
        .order_by(None)
        .group_by(Card.template_id, Card.application_id, Note.note_type_id, NoteType.name,
                  StudyApplication.occurrence_key, StudyApplication.display_name,
                  StudyApplication.position, StudyApplication.is_default, Note.deck_id, Note.user_id)
        .all()
    )
    samples = {}
    local_deck_ids = (
        set(clone_scope.local_deck_ids) if clone_scope is not None else set()
    )
    for row in rows:
        (card_id, template_id, application_id, note_type_id, note_type_name,
         occurrence_key, display_name, position, is_default, deck_id, note_user_id) = row
        context_kind = CONTEXT_OWNED
        if clone_scope is not None:
            is_local = (
                deck_id is not None
                and int(deck_id) in local_deck_ids
                and int(note_user_id) == int(clone_scope.install.user_id)
            )
            context_kind = (
                CONTEXT_INSTALLED_LOCAL if is_local else CONTEXT_INSTALLED_SOURCE
            )
        samples.setdefault((str(note_type_id), str(template_id), str(application_id or ""), context_kind), row)

    # The grouped scope already supplies the effective presentation context.
    # Loading sample Card/Note entities here repeats content reads for each
    # composition; only Template and NoteType metadata are needed.
    template_ids = sorted({key[1] for key in samples})
    templates: dict[str, Template] = {}
    for offset in range(0, len(template_ids), 500):
        batch = (
            Template.query.options(joinedload(Template.note_type))
            .filter(Template.id.in_(template_ids[offset:offset + 500]))
            .all()
        )
        templates.update((str(template.id), template) for template in batch)
    positions = {
        template_id: int(template.position or 0)
        for template_id, template in templates.items()
    }
    fallback_apps: dict[tuple[str, str], StudyApplication] = {}
    if any(not key[2] for key in samples):
        for offset in range(0, len(template_ids), 500):
            batch_apps = (
                StudyApplication.query.filter(
                    StudyApplication.template_id.in_(template_ids[offset:offset + 500]),
                    StudyApplication.status_code == "ACTIVE",
                ).all()
            )
            for app in batch_apps:
                fallback_apps.setdefault((str(app.note_type_id), str(app.template_id)), app)

    compositions: list[AppliedComposition] = []
    for (note_type_id, template_id, application_id, context_kind), row in samples.items():
        card_id = row.sample_card_id
        template = templates.get(template_id)
        if template is None:
            raise ValueError(f"Card {card_id} references missing template {template_id}")
        application = (SimpleNamespace(id=application_id, occurrence_key=row.occurrence_key,
                        display_name=row.display_name, position=row.position, is_default=row.is_default)
                       if application_id else fallback_apps.get((str(note_type_id), str(template_id))))
        composition = build_compatibility_composition(
                template,
                note_type=SimpleNamespace(id=note_type_id, name=row.note_type_name),
                application=application,
                context_kind=context_kind,
                install_id=(str(clone_scope.install.id) if clone_scope is not None else None),
            )
        positions[composition.composition_id] = int(row.position if row.position is not None else template.position or 0)
        compositions.append(composition)
    return sorted(compositions, key=lambda item: _composition_sort_key(item, positions))


def group_available_compositions(
    compositions: list[AppliedComposition],
) -> list[CompositionGroup]:
    grouped: dict[tuple[str, str], list[AppliedComposition]] = {}
    # Sorting may run after the ORM identity map releases discovery entities.
    # Fetch positions in batches instead of issuing one lazy get per item.
    template_ids = sorted({item.template_id for item in compositions})
    positions: dict[str, int] = {}
    for offset in range(0, len(template_ids), 500):
        rows = db.session.query(Template.id, Template.position, StudyApplication.id, StudyApplication.position).outerjoin(
            StudyApplication, StudyApplication.template_id == Template.id,
        )
        for template_id, position, application_id, application_position in (
            rows.filter(Template.id.in_(template_ids[offset:offset + 500])).all()
        ):
            positions[str(template_id)] = int(position or 0)
            if application_id is not None:
                positions[str(application_id)] = int(application_position or 0)
    for item in sorted(compositions, key=lambda item: _composition_sort_key(item, positions)):
        grouped.setdefault(
            (item.note_type_id, item.note_type_name),
            [],
        ).append(item)
    return [
        CompositionGroup(
            note_type_id=note_type_id,
            note_type_name=note_type_name,
            compositions=tuple(items),
        )
        for (note_type_id, note_type_name), items in grouped.items()
    ]


def count_notes_by_composition(
    query: Any,
    *,
    clone_scope: flashcards_share_service.CloneDeckScope | None,
    compositions: list[AppliedComposition],
) -> dict[str, int]:
    """Count distinct Notes per composition inside one effective scope query.

    ``compositions`` must come from ``list_available_compositions_for_query``
    for the same query and clone scope. Every composition id gets a count.
    """

    counts = {item.composition_id: 0 for item in compositions}
    if not compositions:
        return counts
    key_to_id = {
        (item.note_type_id, str(item.template_id), item.context_kind,
         _application_id_from_composition_id(item.composition_id)): item.composition_id
        for item in compositions
    }
    eligible_card_ids = (
        query.with_entities(Card.id.label("card_id"))
        .order_by(None)
        .subquery()
    )
    rows = (
        db.session.query(
            Card.template_id,
            Note.note_type_id,
            Card.application_id,
            StudyApplication.occurrence_key,
            Note.deck_id,
            Note.user_id,
            db.func.count(db.distinct(Card.note_id)),
        )
        .join(Note, Card.note_id == Note.id)
        .outerjoin(StudyApplication, Card.application_id == StudyApplication.id)
        .filter(Card.id.in_(db.session.query(eligible_card_ids.c.card_id)))
        .order_by(None)
        .group_by(Card.template_id, Note.note_type_id, Card.application_id,
                  StudyApplication.occurrence_key, Note.deck_id, Note.user_id)
        .all()
    )
    local_deck_ids = (
        set(clone_scope.local_deck_ids) if clone_scope is not None else set()
    )
    for template_id, note_type_id, application_id, occurrence_key, deck_id, note_user_id, note_count in rows:
        context_kind = CONTEXT_OWNED
        if clone_scope is not None:
            is_local = (
                deck_id is not None
                and int(deck_id) in local_deck_ids
                and int(note_user_id) == int(clone_scope.install.user_id)
            )
            context_kind = (
                CONTEXT_INSTALLED_LOCAL if is_local else CONTEXT_INSTALLED_SOURCE
            )
        repeated_id = str(application_id) if application_id and occurrence_key != COMPAT_OCCURRENCE_KEY else None
        composition_id = key_to_id.get((str(note_type_id), str(template_id), context_kind, repeated_id))
        if composition_id is None:
            continue
        counts[composition_id] += int(note_count or 0)
    return counts


def resolve_composition_selection(
    query: Any,
    *,
    clone_scope: flashcards_share_service.CloneDeckScope | None,
    requested_composition_id: str | None,
    request_source: str,
) -> ResolvedCompositionSelection:
    available = list_available_compositions_for_query(
        query,
        clone_scope=clone_scope,
    )
    by_id = {item.composition_id: item for item in available}
    if requested_composition_id is None:
        if not available:
            raise StudyCompositionError(
                "NO_STUDY_CARDS",
                "Bộ thẻ này chưa có thẻ học phù hợp.",
                status=404,
            )
        if len(available) != 1:
            raise StudyCompositionError(
                "COMPOSITION_SELECTION_REQUIRED",
                "Hãy chọn một chế độ học trước khi bắt đầu phiên.",
                status=409,
                details={"eligible_composition_count": len(available)},
            )
        return ResolvedCompositionSelection(
            composition=available[0],
            resolution="unambiguous_fallback",
        )

    selected = by_id.get(requested_composition_id)
    if selected is not None:
        return ResolvedCompositionSelection(
            composition=selected,
            resolution=request_source,
        )

    template_id = _template_id_from_composition_id(requested_composition_id)
    if template_id is None:
        raise StudyCompositionError(
            "INVALID_COMPOSITION_ID",
            "composition_id không đúng định dạng được hỗ trợ.",
            status=400,
        )
    if db.session.get(Template, template_id) is None:
        raise StudyCompositionError(
            "COMPOSITION_STALE",
            "Chế độ học đã chọn không còn khả dụng.",
            status=409,
        )
    raise StudyCompositionError(
        "COMPOSITION_OUT_OF_SCOPE",
        "Chế độ học đã chọn không thuộc phạm vi được phép.",
        status=403,
    )


def apply_composition_selection_to_query(
    query: Any,
    *,
    clone_scope: flashcards_share_service.CloneDeckScope | None,
    selection: ResolvedCompositionSelection,
) -> Any:
    item = selection.composition
    filtered = query.filter(Card.template_id == item.template_id, Note.note_type_id == item.note_type_id)
    application_id = _application_id_from_composition_id(item.composition_id)
    if application_id is not None:
        filtered = filtered.filter(Card.application_id == application_id)
    else:
        filtered = filtered.filter(db.or_(Card.application_id.is_(None), Card.application.has(
            StudyApplication.occurrence_key == COMPAT_OCCURRENCE_KEY,
        )))
    if item.context_kind == CONTEXT_OWNED:
        return filtered
    if clone_scope is None or str(clone_scope.install.id) != str(item.install_id):
        raise StudyCompositionError(
            "COMPOSITION_OUT_OF_SCOPE",
            "Chế độ học đã chọn không thuộc installation hiện tại.",
            status=403,
        )
    if item.context_kind == CONTEXT_INSTALLED_LOCAL:
        return filtered.filter(
            Note.deck_id.in_(clone_scope.local_deck_ids),
            Note.user_id == int(clone_scope.install.user_id),
        )
    source_filtered = filtered.filter(Note.deck_id.in_(clone_scope.source_deck_ids))
    if clone_scope.source_owner_user_id is not None:
        source_filtered = source_filtered.filter(
            Note.user_id == int(clone_scope.source_owner_user_id)
        )
    return source_filtered


def _template_id_from_composition_id(composition_id: str) -> str | None:
    parts = str(composition_id or "").split(":")
    if len(parts) in {7, 10} and parts[-2] == "application" and parts[-1]:
        parts = parts[:-2]
    if (
        len(parts) == 5
        and parts[0] == "comp"
        and parts[1] == "notetype"
        and parts[2]
        and parts[3] == "template"
        and parts[4]
    ):
        return parts[4]
    if (
        len(parts) == 8
        and parts[0] == "comp"
        and parts[1] == "install"
        and parts[2]
        and parts[3] in {"source", "local"}
        and parts[4] == "notetype"
        and parts[5]
        and parts[6] == "template"
        and parts[7]
    ):
        return parts[7]
    return None


def _application_id_from_composition_id(composition_id: str) -> str | None:
    parts = str(composition_id or "").split(":")
    return parts[-1] if len(parts) in {7, 10} and parts[-2] == "application" and parts[-1] else None


def list_available_compositions_for_scope(
    scope_type: str,
    scope_id: str | int,
    user_id: int,
) -> list[AppliedComposition]:
    """Compatibility entrypoint backed by effective Card queries."""

    normalized_scope = str(scope_type or "").strip().lower()
    clone_scope: flashcards_share_service.CloneDeckScope | None = None
    if normalized_scope == "note_type":
        note_type = db.session.get(NoteType, str(scope_id))
        if note_type is None:
            return []
        query = Card.query.join(Note, Card.note_id == Note.id).filter(
            Note.user_id == int(user_id),
            Note.note_type_id == str(scope_id),
        )
    elif normalized_scope == "deck" and str(scope_id).isdigit():
        deck_id = int(scope_id)
        clone_scope = flashcards_share_service.resolve_clone_scope_for_local_deck(
            user_id=int(user_id),
            local_deck_id=deck_id,
        )
        if clone_scope is not None:
            query = flashcards_share_service.query_clone_scope_cards(clone_scope)
        else:
            scope_deck_ids = collect_subtree_ids(deck_id)
            if not scope_deck_ids:
                return []
            query = Card.query.join(Note, Card.note_id == Note.id).filter(
                Note.user_id == int(user_id),
                Note.deck_id.in_(scope_deck_ids),
            )
    else:
        return []
    return list_available_compositions_for_query(
        query,
        clone_scope=clone_scope,
    )
