"""Flashcard content REST API V1 resources."""

from flask import Blueprint

from .note_types import note_types_bp
from .notes import notes_bp
from .imports import imports_bp
from .anki_imports import anki_imports_bp
from .media import media_bp
from .audio_scan import audio_scan_bp
from .card_templates import card_templates_bp


flashcards_v1_bp = Blueprint("api_v1_flashcards", __name__)
flashcards_v1_bp.register_blueprint(note_types_bp)
flashcards_v1_bp.register_blueprint(notes_bp)
flashcards_v1_bp.register_blueprint(imports_bp)
flashcards_v1_bp.register_blueprint(anki_imports_bp)
flashcards_v1_bp.register_blueprint(media_bp)
flashcards_v1_bp.register_blueprint(audio_scan_bp)
flashcards_v1_bp.register_blueprint(card_templates_bp)
