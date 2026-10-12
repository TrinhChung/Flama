"""Explicit, idempotent creation of the sentence mining starter schema."""

from app.repositories import connect_identity_repository
from app.services.connect.base import ConnectError
from app.services.connect.mining_media import lock_account
from models import db
from models.deck import Deck
from models.field_def import FieldDef
from models.note_type import NoteType
from models.template import Template

FIELDS = (("Sentence", "text"), ("Word", "text"), ("Definition", "text"),
          ("Image", "image"), ("Audio", "audio"), ("Source", "text"), ("URL", "text"))


def prepare_sentence_mining(user_id):
    lock_account(user_id)
    types = NoteType.query.filter_by(user_id=user_id, name="Sentence Card").all()
    if len(types) > 1:
        raise ConnectError("Multiple Sentence Card models exist; select a model manually.")
    note_type = types[0] if types else None
    if note_type is None:
        note_type = NoteType(user_id=user_id, name="Sentence Card")
        db.session.add(note_type)
        db.session.flush()
        for position, (name, kind) in enumerate(FIELDS):
            db.session.add(FieldDef(note_type_id=note_type.id, name=name, field_type=kind,
                                    position=position, required=name == "Sentence",
                                    identity_role="primary" if name == "Sentence" else None))
        from app.repositories.template_library_repository import create_attached_template
        create_attached_template(db.session, note_type=note_type, name="Sentence",
                                 front_html="{{Sentence}}<br>{{Image}}<br>{{Audio}}",
                                 back_html="{{Sentence}}<hr>{{Word}}<br>{{Definition}}<br>{{Source}}<br>{{URL}}",
                                 is_default=True)
        db.session.flush()
    else:
        schema = {item.name: item for item in note_type.field_defs}
        if any(name not in schema or schema[name].field_type != kind for name, kind in FIELDS):
            raise ConnectError("Existing Sentence Card fields differ; configure the model manually.")
        sentence = schema["Sentence"]
        if sentence.identity_role != "primary" or not sentence.required or any(item.required for item in note_type.field_defs if item.name != "Sentence") or not connect_identity_repository.has_active_template(note_type.id):
            raise ConnectError("Sentence Card requires a primary Sentence field and an active template.")
    decks = Deck.query.filter_by(owner_user_id=user_id, name="Sentences", parent_id=None, deleted_at=None).all()
    if len(decks) > 1 or (decks and decks[0].note_type_id not in {None, note_type.id}):
        raise ConnectError("Existing Sentences deck differs; select a deck manually.")
    deck = decks[0] if decks else Deck(owner_user_id=user_id, name="Sentences", note_type_id=note_type.id)
    if not decks:
        db.session.add(deck)
    # Do not rebind an existing user deck during setup.
    db.session.flush()
    return {"deckName": deck.name, "modelName": note_type.name, "fields": [name for name, _ in FIELDS]}
