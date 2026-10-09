"""Owner APIs for template source history, using stable Template identity."""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services import flashcard_content_service, template_version_service, template_library_service, template_release_service
from app.validators.template_library import TemplateLibraryError
from .common import content_error

card_templates_bp = Blueprint("api_v1_card_templates", __name__)


def _respond(operation, *, success_status=200, **kwargs):
    try:
        payload = operation(user_id=current_user.id, **kwargs)
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    except (template_version_service.TemplateVersionError, TemplateLibraryError, template_release_service.TemplateReleaseError) as exc:
        payload = {"error": exc.code, "message": str(exc)}
        if exc.field:
            payload["field"] = exc.field
        if getattr(exc, "details", None):
            payload["details"] = exc.details
        return jsonify(payload), exc.status
    response = jsonify(payload)
    response.headers["Cache-Control"] = "private, no-store"
    return response, success_status


@card_templates_bp.get("/card-templates/<template_id>/versions")
@card_templates_bp.get("/note-types/<note_type_id>/templates/<template_id>/versions")
@login_required
def list_versions(template_id, note_type_id=None):
    return _respond(template_version_service.list_versions, template_id=template_id, note_type_id=note_type_id)


@card_templates_bp.get("/card-templates/<template_id>/versions/<version_id>")
@card_templates_bp.get("/note-types/<note_type_id>/templates/<template_id>/versions/<version_id>")
@login_required
def get_version(template_id, version_id, note_type_id=None):
    return _respond(template_version_service.get_version, template_id=template_id, version_id=version_id, note_type_id=note_type_id)


@card_templates_bp.post("/card-templates/<template_id>/versions/<version_id>/restore")
@card_templates_bp.post("/note-types/<note_type_id>/templates/<template_id>/versions/<version_id>/restore")
@login_required
def restore_version(template_id, version_id, note_type_id=None):
    payload = request.get_json(silent=True)
    if payload is None and not request.get_data():
        payload = {}
    return _respond(
        template_version_service.restore_version,
        template_id=template_id, version_id=version_id, note_type_id=note_type_id, payload=payload,
    )


def _body():
    return request.get_json(silent=True)


@card_templates_bp.get("/card-templates")
@login_required
def library():
    return _respond(template_library_service.list_templates, include_archived=request.args.get("include_archived") == "true", category=request.args.get("category"), search=request.args.get("q"), group=request.args.get("group", "all"))


@card_templates_bp.post("/card-templates")
@login_required
def create_definition():
    return _respond(template_library_service.create_template, payload=_body(), success_status=201)


@card_templates_bp.get("/card-templates/<template_id>")
@login_required
def definition(template_id):
    return _respond(template_library_service.get_template, template_id=template_id)


@card_templates_bp.patch("/card-templates/<template_id>")
@login_required
def edit_definition(template_id):
    return _respond(template_library_service.update_template, template_id=template_id, payload=_body())


@card_templates_bp.post("/card-templates/<template_id>/preview")
@login_required
def preview_definition(template_id):
    return _respond(template_library_service.preview_template, template_id=template_id, payload=_body())


@card_templates_bp.post("/card-templates/<template_id>/duplicate")
@login_required
def duplicate_definition(template_id):
    return _respond(template_library_service.duplicate_template, template_id=template_id, payload=_body(), success_status=201)


@card_templates_bp.patch("/card-templates/<template_id>/archive")
@login_required
def archive_definition(template_id):
    return _respond(template_library_service.archive_template, template_id=template_id, payload=_body())


@card_templates_bp.get("/note-types/<note_type_id>/template-applications")
@login_required
def applications(note_type_id):
    return _respond(template_library_service.list_applications, note_type_id=note_type_id, include_retired=request.args.get("include_retired") == "true")


@card_templates_bp.post("/note-types/<note_type_id>/template-applications")
@login_required
def attach_definition(note_type_id):
    return _respond(template_library_service.attach_template, note_type_id=note_type_id, payload=_body(), success_status=201)


@card_templates_bp.patch("/note-types/<note_type_id>/template-applications/<application_id>")
@login_required
def edit_application(note_type_id, application_id):
    return _respond(template_library_service.update_application, note_type_id=note_type_id, application_id=application_id, payload=_body())


@card_templates_bp.delete("/note-types/<note_type_id>/template-applications/<application_id>")
@login_required
def detach_definition(note_type_id, application_id):
    return _respond(template_library_service.retire_application, note_type_id=note_type_id, application_id=application_id)


@card_templates_bp.get("/card-templates/<template_id>/publication")
@login_required
def publication(template_id):
    return _respond(template_release_service.get_publication, template_id=template_id)


@card_templates_bp.patch("/card-templates/<template_id>/publication")
@login_required
def publication_settings(template_id):
    return _respond(template_release_service.update_publication_settings, template_id=template_id, payload=_body())


@card_templates_bp.get("/card-templates/<template_id>/releases")
@login_required
def releases(template_id):
    # Service validates pagination; keep malformed input visible as a 400.
    try:
        limit = int(request.args.get("limit", 100))
        before = int(request.args["before_sequence"]) if "before_sequence" in request.args else None
    except (TypeError, ValueError):
        return jsonify({"error": "VALIDATION_ERROR", "message": "Invalid release pagination."}), 400
    return _respond(template_release_service.list_releases, template_id=template_id, limit=limit, before_sequence=before)


@card_templates_bp.get("/card-templates/<template_id>/releases/<release_id>")
@login_required
def release_detail(template_id, release_id):
    return _respond(template_release_service.get_release, template_id=template_id, release_id=release_id)


@card_templates_bp.post("/card-templates/<template_id>/releases")
@login_required
def publish(template_id):
    return _respond(template_release_service.publish_release, template_id=template_id, payload=_body(), idempotency_key=request.headers.get("Idempotency-Key"), success_status=201)


@card_templates_bp.get("/card-templates/<template_id>/subscription")
@login_required
def subscription(template_id):
    return _respond(template_release_service.get_subscription, template_id=template_id)


@card_templates_bp.patch("/card-templates/<template_id>/subscription")
@login_required
def subscription_settings(template_id):
    return _respond(template_release_service.update_subscription_settings, template_id=template_id, payload=_body())


@card_templates_bp.post("/card-templates/<template_id>/prepare-update")
@login_required
def prepare_update(template_id):
    return _respond(template_release_service.prepare_update, template_id=template_id, payload=_body())


@card_templates_bp.post("/card-templates/<template_id>/apply-update")
@login_required
def apply_update(template_id):
    return _respond(template_release_service.apply_update, template_id=template_id, payload=_body())


@card_templates_bp.post("/card-templates/<template_id>/reset-to-upstream")
@login_required
def reset_upstream(template_id):
    return _respond(template_release_service.reset_to_upstream, template_id=template_id, payload=_body())


@card_templates_bp.get("/deck-installs/<install_id>/templates")
@login_required
def install_templates(install_id):
    return _respond(template_release_service.list_install_templates, install_id=install_id)


@card_templates_bp.get("/decks/<int:deck_id>/study-template-preset")
@login_required
def study_preset(deck_id):
    from app.services.study_template_preset_service import get_preset
    return _respond(get_preset, deck_id=deck_id)


@card_templates_bp.put("/decks/<int:deck_id>/study-template-preset")
@login_required
def save_study_preset(deck_id):
    from app.services.study_template_preset_service import save_preset
    return _respond(save_preset, deck_id=deck_id, payload=_body())
