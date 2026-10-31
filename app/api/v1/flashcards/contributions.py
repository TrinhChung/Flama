"""Contribution submission: HTTP mapping for the single-action workflow."""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services.change_request.helpers import ChangeRequestError
from app.services.change_request.submission import send_saved_changes
from app.services.field_value_identity_service import FieldIdentityConflict, FieldIdentityError
from app.services.share.helpers import ShareControllerError
from app.validators.deck_change_request import validate_change_request_send_request
from app.validators.flashcard_input import RequestValidationError


contributions_bp = Blueprint("api_v1_contributions", __name__)


@contributions_bp.post("/shared/decks/<deck_item_id>/change-requests/send")
@login_required
def send_contribution(deck_item_id: str):
    try:
        data = validate_change_request_send_request(request.get_json(silent=True))
        result = send_saved_changes(
            deck_item_id=deck_item_id, requester_user_id=current_user.id,
            title=data.title, description=data.description,
            expected_overlay_fingerprint=data.expected_overlay_fingerprint,
        )
        return jsonify(result)
    except RequestValidationError as exc:
        return jsonify(error=exc.code, message=str(exc), field=exc.field), exc.status
    except ChangeRequestError as exc:
        return jsonify(error=exc.error, message=exc.message, field=exc.field), exc.status
    except FieldIdentityConflict as exc:
        return jsonify(error="FIELD_IDENTITY_CONFLICT", message=str(exc)), 409
    except FieldIdentityError as exc:
        return jsonify(error="FIELD_IDENTITY_INVALID", message=str(exc)), 400
    except ShareControllerError as exc:
        return jsonify(error=exc.error, message=str(exc)), exc.status
