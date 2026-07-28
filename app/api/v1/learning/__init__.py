"""Learning REST API V1 resources."""

from flask import Blueprint

from .browse import browse_bp


learning_bp = Blueprint("api_v1_learning", __name__)
learning_bp.register_blueprint(browse_bp, url_prefix="/browse")
