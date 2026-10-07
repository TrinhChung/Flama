"""Route registration for the Flask application."""

from flask import Flask

from .auth import auth_bp
from .admin import admin_bp
from .admin_payments import admin_payments_bp
from .flashcards import flashcards_bp
from .image_library import image_library_bp
from .main import main_bp
from .mcp import mcp_bp
from .media_asset_routes import media_asset_bp
from .oauth import oauth_bp
from .payments import payments_bp
from .seo import seo_bp
from .spa_routes import spa_routes_bp
from .user_orders import user_orders_bp
from .vocabulary import vocabulary_bp


def register_blueprints(app: Flask) -> None:
    """Attach all blueprints to the Flask application."""
    from app.api import register_api_blueprints

    # The canonical /api namespace must be registered before legacy adapters
    # that still expose overlapping compatibility rules.
    register_api_blueprints(app)
    app.register_blueprint(seo_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(mcp_bp)
    app.register_blueprint(oauth_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_payments_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(spa_routes_bp)
    app.register_blueprint(user_orders_bp)
    app.register_blueprint(vocabulary_bp)
    app.register_blueprint(flashcards_bp)
    app.register_blueprint(image_library_bp)
    app.register_blueprint(media_asset_bp)

