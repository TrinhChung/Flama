"""Flashcard content REST API V1 resources."""

from flask import Blueprint

from .note_types import note_types_bp
from .notes import notes_bp
from .imports import imports_bp
from .media import media_bp


flashcards_v1_bp = Blueprint("api_v1_flashcards", __name__)
flashcards_v1_bp.register_blueprint(note_types_bp)
flashcards_v1_bp.register_blueprint(notes_bp)
flashcards_v1_bp.register_blueprint(imports_bp)
flashcards_v1_bp.register_blueprint(media_bp)
