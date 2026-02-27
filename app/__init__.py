
import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import Flask
import sqlalchemy as sa

from models import db

from .cli import register_cli_commands
from .extensions import login_manager, migrate
from .routes import register_blueprints
from .services.user_management_schema import ensure_user_management_schema
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
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }
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
    from models.user_permission_audit_log import UserPermissionAuditLog  # noqa: F401
    from models.vocabulary_deck import VocabularyDeck  # noqa: F401  # register model
    from models.vocabulary_entry import VocabularyEntry  # noqa: F401  # register model
    from models.vocabulary_progress import VocabularyProgress  # noqa: F401  # register model
    from models.column_preference import (
        VocabularyColumnPreference,
    )  # noqa: F401  # register model
    from models.flashcard_entries import (  # noqa: F401  # register model
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
        ReviewEvent,
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
        ensure_user_management_schema(db.session)
        _ensure_backward_compatible_schema()
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


def _ensure_backward_compatible_schema() -> None:
    """Patch legacy schemas that predate newly added columns."""
    bind = db.session.get_bind()
    if bind is None:
        return

    inspector = sa.inspect(bind)
    schema_changed = False

    if inspector.has_table("users"):
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "timezone" not in user_columns:
            db.session.execute(
                sa.text("ALTER TABLE users ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'")
            )
            db.session.execute(
                sa.text("UPDATE users SET timezone = 'UTC' WHERE timezone IS NULL OR timezone = ''")
            )
            schema_changed = True

    inspector = sa.inspect(bind)
    if inspector.has_table("vocabulary_progress"):
        progress_columns = {column["name"] for column in inspector.get_columns("vocabulary_progress")}
        if "is_suspended" not in progress_columns:
            db.session.execute(
                sa.text("ALTER TABLE vocabulary_progress ADD COLUMN is_suspended BOOLEAN NOT NULL DEFAULT 0")
            )
            db.session.execute(
                sa.text("UPDATE vocabulary_progress SET is_suspended = 0 WHERE is_suspended IS NULL")
            )
            schema_changed = True

        progress_indexes = {index["name"] for index in inspector.get_indexes("vocabulary_progress")}
        if "ix_vocabulary_progress_is_suspended" not in progress_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_vocabulary_progress_is_suspended ON vocabulary_progress (is_suspended)")
            )
            schema_changed = True

    inspector = sa.inspect(bind)
    if inspector.has_table("vocabulary_decks"):
        deck_columns = {column["name"] for column in inspector.get_columns("vocabulary_decks")}
        if "owner_user_id" not in deck_columns:
            db.session.execute(
                sa.text("ALTER TABLE vocabulary_decks ADD COLUMN owner_user_id INTEGER NULL")
            )
            deck_columns.add("owner_user_id")
            schema_changed = True
        if "note_type_id" not in deck_columns:
            db.session.execute(
                sa.text("ALTER TABLE vocabulary_decks ADD COLUMN note_type_id VARCHAR(36) NULL")
            )
            deck_columns.add("note_type_id")
            schema_changed = True

        deck_indexes = {index["name"] for index in inspector.get_indexes("vocabulary_decks")}
        if "owner_user_id" in deck_columns and "ix_vocabulary_decks_owner_user_id" not in deck_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_vocabulary_decks_owner_user_id ON vocabulary_decks (owner_user_id)")
            )
            schema_changed = True
        if "note_type_id" in deck_columns and "ix_vocabulary_decks_note_type_id" not in deck_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_vocabulary_decks_note_type_id ON vocabulary_decks (note_type_id)")
            )
            schema_changed = True

    if schema_changed:
        db.session.commit()
