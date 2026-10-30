"""Select a Card's presentation source without changing its Template identity.

The compatibility source remains ``card.template``. Callers preparing a batch
may supply already resolved sources keyed by the source Template ID; this seam
does not query per Card or mutate the source model.
"""

from __future__ import annotations

from app.services.effective_note_reader import install_release_id

from copy import deepcopy
from types import SimpleNamespace
from typing import Any, Mapping


_SOURCE_ATTRIBUTES = (
    "id", "name", "note_type_id", "front_html", "back_html", "shared_css",
    "input_schema", "updated_at", "current_version_id", "owner_user_id",
)


def _source_view(source, base, bindings):
    values = {key: getattr(base, key, None) for key in _SOURCE_ATTRIBUTES}
    values.update({key: value for key, value in vars(source).items() if not key.startswith("_")})
    for key in _SOURCE_ATTRIBUTES:
        if hasattr(source, key):
            values[key] = getattr(source, key)
    values["input_schema"] = deepcopy(values.get("input_schema"))
    values["input_bindings"] = deepcopy(bindings)
    return SimpleNamespace(**values)


def _application_bindings(card, source):
    explicit = getattr(source, "input_bindings", None)
    if isinstance(explicit, Mapping):
        return dict(explicit)
    application_id = str(getattr(card, "application_id", None) or "")
    application = getattr(card, "application", None)
    if not application_id:
        application_id = str(getattr(application, "id", None) or "")
    for name in ("application_bindings", "applications_json"):
        applications = getattr(source, name, None)
        if isinstance(applications, Mapping) and application_id in applications:
            entry = applications[application_id]
            if isinstance(entry, Mapping):
                bindings = entry.get("input_bindings", entry)
                return dict(bindings) if isinstance(bindings, Mapping) else {}
    bindings = getattr(application, "input_bindings", None)
    return dict(bindings) if isinstance(bindings, Mapping) else None


def resolve_effective_template(
    card: Any,
    clone_scope: Any = None,
    *,
    template_overrides: Mapping[str, Any] | None = None,
) -> Any:
    """Return the current source, or an identity-preserving batch override.

    ``clone_scope`` identifies the install for future fork resolution. Sources
    supplied through ``template_overrides`` must retain the original Template
    ID so Card, application, composition, and artifact references stay stable.
    An absent entry (or ``None``) follows the compatibility source.
    """
    template = card.template
    if template is None:
        return template
    template_id = str(template.id)
    if template_overrides is None and clone_scope is not None:
        from models import db
        from app.repositories import template_release_repository as repository
        template_overrides = repository.load_effective_template_overrides(
            db.session, user_id=clone_scope.install.user_id, source_template_ids=[template_id],
            release_pins=repository.deck_pins(db.session, install_release_id(clone_scope.install)),
        )
    source = template_overrides.get(template_id) if template_overrides is not None else None
    source = source if source is not None else template
    if str(getattr(source, "id", "")) != template_id:
        raise ValueError("An effective template source must preserve the source Template ID.")
    bindings = _application_bindings(card, source)
    if bindings is not None or (source is not template and not hasattr(source, "name")):
        return _source_view(source, template, bindings)
    return source
