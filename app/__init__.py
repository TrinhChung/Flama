
import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import Flask

from models import db

from .cli import register_cli_commands
from .extensions import login_manager, migrate
from .routes import register_blueprints
from .services.user_roles import ensure_default_user_roles

BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv()


def create_app(config: Optional[dict] = None) -> Flask:
    """Application factory that sets up Flask, database, and authentication."""
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = _build_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["USE_NEW_CARD_MODEL"] = os.getenv("USE_NEW_CARD_MODEL", "false").strip().lower() == "true"
    app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"] = str(BASE_DIR / "static" / "uploads")
    app.config["FLASHCARD_MEDIA_MAX_BYTES"] = int(os.getenv("FLASHCARD_MEDIA_MAX_BYTES", str(10 * 1024 * 1024)))
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from models.user import User
    from models.user_role import UserRole  # noqa: F401  # register model
    from models.vocabulary_deck import VocabularyDeck  # noqa: F401  # register model
    from models.vocabulary_entry import VocabularyEntry  # noqa: F401  # register model
    from models.vocabulary_progress import VocabularyProgress  # noqa: F401  # register model
    from models.column_preference import (
        VocabularyColumnPreference,
    )  # noqa: F401  # register model
    from models.flashcard import (  # noqa: F401  # register model
        AuditLog,
        Card,
        DeckInstall,
        DeckMarketplaceItem,
        DeckReview,
        FieldDef,
        FieldRenameJob,
        LegacyMigrationMap,
        MediaAsset,
        Note,
        NoteType,
        NoteTypeInstall,
        NoteTypeReview,
        Template,
    )

    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[User]:
        if user_id.isdigit():
            return User.query.get(int(user_id))
        return None

    register_blueprints(app)
    register_cli_commands(app)

    # Register error handlers
    @app.errorhandler(404)
    def page_not_found(error):
        """Handle 404 errors."""
        from flask import render_template
        return render_template('error.html', error_code=404, error_message='Trang không tìm thấy'), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 errors."""
        from flask import render_template
        return render_template('error.html', error_code=500, error_message='Lỗi máy chủ'), 500

    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 errors."""
        from flask import render_template
        return render_template('error.html', error_code=403, error_message='Truy cập bị từ chối'), 403

    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handle unexpected exceptions."""
        from flask import render_template
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unhandled exception: {error}", exc_info=True)
        return render_template('error.html', error_code=500, error_message='Lỗi máy chủ'), 500

    with app.app_context():
        db.create_all()
        ensure_default_user_roles(db.session)
        db.session.commit()

    return app


def _build_database_uri() -> str:
    """Construct the MySQL connection string from environment variables."""
    db_user = os.getenv("DB_USER", "").strip()
    db_password = os.getenv("DB_PASSWORD", "")
    db_host = os.getenv("DB_HOST", "localhost").strip()
    db_port = os.getenv("DB_PORT", "3306").strip()
    db_name = os.getenv("DB_NAME", "").strip()

    if not db_user or not db_name:
        raise RuntimeError(
            "DB_USER và DB_NAME phải được cấu hình trong tập tin .env."
        )

    safe_password = quote_plus(db_password)
    return (
        f"mysql+pymysql://{db_user}:{safe_password}"
        f"@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    )
