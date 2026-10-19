"""Learning REST API V1 resources."""

from flask import Blueprint

from .browse import browse_bp
from .study import study_bp


learning_bp = Blueprint("api_v1_learning", __name__)
learning_bp.register_blueprint(browse_bp, url_prefix="/browse")
learning_bp.register_blueprint(study_bp, url_prefix="/study")
