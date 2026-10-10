"""Transport metadata shared by every Connect protocol adapter."""

from dataclasses import dataclass

FLAMA_CONNECT_PROTOCOL_VERSION = 6
MAX_NOTES_PER_REQUEST = 50
MAX_MULTI_ACTIONS = 10
MAX_SAFE_NUMERIC_ID = 2**53 - 1


@dataclass(frozen=True)
class ActionSpec:
    params: frozenset[str]
    scope: str | None = None
    batch_read: bool = False
    legacy_only: bool = False


def _spec(params=(), scope=None, *, batch_read=False, legacy_only=False):
    return ActionSpec(frozenset(params), scope, batch_read, legacy_only)


ACTIONS = {
    "version": _spec(batch_read=True),
    "apiReflect": _spec(("scopes", "actions"), "note-type:read", batch_read=True),
    "deckNames": _spec(scope="deck:read", batch_read=True),
    "modelNames": _spec(scope="note-type:read", batch_read=True),
    "modelFieldNames": _spec(("modelName",), "note-type:read", batch_read=True),
    "canAddNotes": _spec(("notes",), "note:check", batch_read=True),
    "canAddNotesWithErrorDetail": _spec(("notes",), "note:check", batch_read=True),
    "findNotes": _spec(("query",), "note:check", batch_read=True),
    "multi": _spec(("actions",), "note:check"),
    "addNote": _spec(("note",), "note:create"),
    "storeMediaFile": _spec(("filename", "data", "path", "url", "deleteExisting", "importSessionId", "mediaKind"), "note:create"),
    "validateKey": _spec(legacy_only=True),
    "userInfo": _spec(legacy_only=True),
    "createImportSession": _spec(("source", "sourceKey", "sourceRootPath", "targetRootPath", "selectedDecks", "decks", "totalNotes", "totalMedia", "appVersion", "mode", "noteTypes", "planHash"), "note:create", legacy_only=True),
    "importCards": _spec(("importSessionId", "cards", "deckName"), "note:create", legacy_only=True),
    "getImportStatus": _spec(("importSessionId",), "note:create", legacy_only=True),
    "completeImportSession": _spec(("importSessionId",), "note:create", legacy_only=True),
}
SUPPORTED_ACTIONS = tuple(name for name, spec in ACTIONS.items() if not spec.legacy_only)
ACTION_PARAMS = {name: spec.params for name, spec in ACTIONS.items()}
ACTION_SCOPES = {name: spec.scope for name, spec in ACTIONS.items()}
LEGACY_WEB_ACTIONS = frozenset(name for name, spec in ACTIONS.items() if spec.legacy_only)
