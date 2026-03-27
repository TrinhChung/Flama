"""Route registration for the Flask application."""

from flask import Flask

from .auth import auth_bp
from .admin import admin_bp
from .flashcards import flashcards_bp
from .main import main_bp
from .payments import payments_bp
from .vocabulary import vocabulary_bp


def register_blueprints(app: Flask) -> None:
    """Attach all blueprints to the Flask application."""
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(vocabulary_bp)
    app.register_blueprint(flashcards_bp)
