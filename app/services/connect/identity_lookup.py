"""Request-local identity indexes shared by Connect checks and updates."""

from dataclasses import dataclass, field
from types import SimpleNamespace

from app.repositories import connect_identity_repository
from app.services.connect.base import _normalized_identity
from models import db
from models.deck import Deck
from models.note import Note


@dataclass(frozen=True)
class NoteIdentityMatch:
    id: str
    note_type_id: str


@dataclass
class NoteIdentityLookup:
    """Cache only within one action; never reuse across writes or requests."""

    user_id: int
    local_indexes: dict[tuple[int, str], dict[str, list[NoteIdentityMatch]]] = field(default_factory=dict)
    clone_indexes: dict[tuple, dict[str, list[NoteIdentityMatch]]] = field(default_factory=dict)

    def local_matches(self, *, deck_id: int, field_name: str, identity_value: str) -> list[NoteIdentityMatch]:
        key = (deck_id, field_name)
        if key not in self.local_indexes:
            index: dict[str, list[NoteIdentityMatch]] = {}
            for note_id, note_type_id, value in connect_identity_repository.local_identity_rows(
                user_id=self.user_id, deck_id=deck_id, field_name=field_name,
            ):
                index.setdefault(_normalized_identity(value), []).append(
                    NoteIdentityMatch(note_id, note_type_id),
                )
            self.local_indexes[key] = index
        return self.local_indexes[key].get(identity_value, [])

    def clone_matches(self, *, clone_map, field_name: str, identity_value: str) -> list[NoteIdentityMatch]:
        from app.services import deck_release_service, flashcards_share_service

        install = clone_map.deck_install
        from app.services.effective_note_reader import current_release_for_install, install_release_id
        key = (
            install.id, clone_map.source_deck_id, field_name,
            install_release_id(install), install.overlay_revision,
        )
        if key not in self.clone_indexes:
            index: dict[str, list[NoteIdentityMatch]] = {}
            source_deck = db.session.get(Deck, clone_map.source_deck_id)
            if source_deck is not None:
                schema = flashcards_share_service.build_clone_schema_view(
                    install=install, source_note_type_id=source_deck.note_type_id,
                )
                uses_release = flashcards_share_service._install_uses_release(install)
                rows = connect_identity_repository.clone_source_rows(
                    install=install, source_deck_id=clone_map.source_deck_id,
                    uses_release=uses_release,
                )
                release_values = (
                    deck_release_service.get_note_values_for_ids_at_release(
                        current_release_for_install(install), [row.id for row in rows],
                    )
                    if uses_release and rows else {}
                )
                overrides_by_note = {}
                for override in connect_identity_repository.clone_note_overrides(
                    install=install, source_deck_id=clone_map.source_deck_id,
                    uses_release=uses_release,
                ):
                    overrides_by_note.setdefault(override.source_note_id, []).append(override)
                for row in rows:
                    if uses_release and row.id not in release_values:
                        # An override cannot make a hidden/unpublished source
                        # note visible outside the applied release membership.
                        continue
                    values = flashcards_share_service.apply_clone_note_field_overrides(
                        install=install,
                        source_note=SimpleNamespace(id=row.id, field_values=row.field_values),
                        schema_view=schema,
                        base_field_values=(
                            release_values.get(row.id, {})
                            if uses_release else row.field_values or {}
                        ),
                        note_override_rows=overrides_by_note.get(row.id, []),
                    )
                    index.setdefault(_normalized_identity(values.get(field_name)), []).append(
                        NoteIdentityMatch(row.id, row.note_type_id),
                    )
            self.clone_indexes[key] = index
        return self.clone_indexes[key].get(identity_value, [])

    def is_duplicate(self, prepared) -> bool:
        if self.local_matches(
            deck_id=prepared.deck.id, field_name=prepared.identity_field.name,
            identity_value=prepared.identity_value,
        ):
            return True
        return prepared.clone_map is not None and bool(self.clone_matches(
            clone_map=prepared.clone_map, field_name=prepared.identity_field.name,
            identity_value=prepared.identity_value,
        ))

    def existing_local_note(self, prepared) -> Note | None:
        for match in self.local_matches(
            deck_id=prepared.deck.id, field_name=prepared.identity_field.name,
            identity_value=prepared.identity_value,
        ):
            if match.note_type_id == prepared.note_type.id:
                return connect_identity_repository.local_note_by_id(
                    user_id=self.user_id, deck_id=prepared.deck.id,
                    note_type_id=prepared.note_type.id, note_id=match.id,
                )
        return None
