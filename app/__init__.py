
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
from .services.tts_provider_service import ensure_default_tts_providers
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
    app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"] = str(BASE_DIR / "static" / "uploads")
    app.config["FLASHCARD_MEDIA_MAX_BYTES"] = int(os.getenv("FLASHCARD_MEDIA_MAX_BYTES", str(10 * 1024 * 1024)))
    app.config["FLASHCARD_MEDIA_SCAN_ENABLED"] = (
        os.getenv("FLASHCARD_MEDIA_SCAN_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
    )
    app.config["FLASHCARD_MEDIA_SCANNER"] = None
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from models.user import User
    from models.user_role import UserRole  # noqa: F401  # register model
    from models.user_permission_audit_log import UserPermissionAuditLog  # noqa: F401
    from models.deck import Deck  # noqa: F401  # register model
    from models.tts_provider_config import TtsProviderConfig  # noqa: F401  # register model
    from models.tts_user_provider_profile import TtsUserProviderProfile  # noqa: F401  # register model
    from models.card_progress import CardProgress  # noqa: F401  # register model
    from models.column_preference import (
        VocabularyColumnPreference,
    )  # noqa: F401  # register model
    from models.flashcard import (  # noqa: F401  # register model
        AuditLog,
        Card,
        DeckCloneAddedFieldDef,
        DeckCloneDeckMap,
        DeckCloneFieldDefOverride,
        DeckCloneFieldOrderOverride,
        DeckCloneNoteFieldOverride,
        DeckInstall,
        DeckMarketplaceItem,
        DeckReview,
        FieldDef,
        FieldRenameJob,
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

    def _rollback_failed_session() -> None:
        try:
            db.session.rollback()
        except Exception:
            pass

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
        _rollback_failed_session()
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
        _rollback_failed_session()
        logger = logging.getLogger(__name__)
        logger.error(f"Unhandled exception: {error}", exc_info=True)
        return render_template('error.html', error_code=500, error_message='Lỗi máy chủ'), 500

    with app.app_context():
        db.create_all()
        ensure_user_management_schema(db.session)
        _ensure_backward_compatible_schema()
        ensure_default_user_roles(db.session)
        ensure_default_tts_providers(db.session)
        from app.services import flashcards_share

        flashcards_share.cutover_clone_model_to_overlay_only(fail_on_mismatch=True)
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
    """Patch schema for incremental local upgrades."""
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
    if inspector.has_table("card_progress"):
        progress_columns = {column["name"] for column in inspector.get_columns("card_progress")}
        if "is_suspended" not in progress_columns:
            db.session.execute(
                sa.text("ALTER TABLE card_progress ADD COLUMN is_suspended BOOLEAN NOT NULL DEFAULT 0")
            )
            db.session.execute(
                sa.text("UPDATE card_progress SET is_suspended = 0 WHERE is_suspended IS NULL")
            )
            schema_changed = True

        progress_indexes = {index["name"] for index in inspector.get_indexes("card_progress")}
        if "ix_card_progress_is_suspended" not in progress_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_card_progress_is_suspended ON card_progress (is_suspended)")
            )
            schema_changed = True

    inspector = sa.inspect(bind)
    if inspector.has_table("tts_provider_config"):
        tts_columns = {column["name"] for column in inspector.get_columns("tts_provider_config")}
        if "shared_config_json" not in tts_columns:
            db.session.execute(
                sa.text("ALTER TABLE tts_provider_config ADD COLUMN shared_config_json TEXT NULL")
            )
            schema_changed = True
        if "provider_config_json" not in tts_columns:
            db.session.execute(
                sa.text("ALTER TABLE tts_provider_config ADD COLUMN provider_config_json TEXT NULL")
            )
            schema_changed = True
        if "default_settings_json" not in tts_columns:
            db.session.execute(
                sa.text("ALTER TABLE tts_provider_config ADD COLUMN default_settings_json TEXT NULL")
            )
            schema_changed = True
        if "shared_config_json" in tts_columns or schema_changed:
            db.session.execute(
                sa.text(
                    "UPDATE tts_provider_config SET shared_config_json = '{}' "
                    "WHERE shared_config_json IS NULL OR shared_config_json = ''"
                )
            )
            db.session.execute(
                sa.text(
                    "UPDATE tts_provider_config SET provider_config_json = '{}' "
                    "WHERE provider_config_json IS NULL OR provider_config_json = ''"
                )
            )
            db.session.execute(
                sa.text(
                    "UPDATE tts_provider_config SET default_settings_json = '{}' "
                    "WHERE default_settings_json IS NULL OR default_settings_json = ''"
                )
            )

    inspector = sa.inspect(bind)
    if inspector.has_table("decks"):
        deck_columns = {column["name"] for column in inspector.get_columns("decks")}
        if "owner_user_id" not in deck_columns:
            db.session.execute(
                sa.text("ALTER TABLE decks ADD COLUMN owner_user_id INTEGER NULL")
            )
            deck_columns.add("owner_user_id")
            schema_changed = True
        if "note_type_id" not in deck_columns:
            db.session.execute(
                sa.text("ALTER TABLE decks ADD COLUMN note_type_id VARCHAR(36) NULL")
            )
            deck_columns.add("note_type_id")
            schema_changed = True

        deck_indexes = {index["name"] for index in inspector.get_indexes("decks")}
        if "owner_user_id" in deck_columns and "ix_decks_owner_user_id" not in deck_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_decks_owner_user_id ON decks (owner_user_id)")
            )
            schema_changed = True
        if "note_type_id" in deck_columns and "ix_decks_note_type_id" not in deck_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_decks_note_type_id ON decks (note_type_id)")
            )
            schema_changed = True

    inspector = sa.inspect(bind)
    if inspector.has_table("deck_installs"):
        install_columns = {column["name"] for column in inspector.get_columns("deck_installs")}
        if "clone_mode" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN clone_mode VARCHAR(32) NULL")
            )
            install_columns.add("clone_mode")
            schema_changed = True
        if "clone_mode" in install_columns:
            missing_mode_count = db.session.execute(
                sa.text("SELECT COUNT(*) FROM deck_installs WHERE clone_mode IS NULL OR clone_mode = ''")
            ).scalar()
            if int(missing_mode_count or 0) > 0:
                db.session.execute(
                    sa.text("UPDATE deck_installs SET clone_mode = 'legacy_copy' WHERE clone_mode IS NULL OR clone_mode = ''")
                )
                schema_changed = True

        if "source_deck_id" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN source_deck_id INTEGER NULL")
            )
            install_columns.add("source_deck_id")
            schema_changed = True
        if "source_note_type_id" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN source_note_type_id VARCHAR(36) NULL")
            )
            install_columns.add("source_note_type_id")
            schema_changed = True
        if "source_owner_user_id" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN source_owner_user_id INTEGER NULL")
            )
            install_columns.add("source_owner_user_id")
            schema_changed = True
        if "base_snapshot_at" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN base_snapshot_at DATETIME NULL")
            )
            install_columns.add("base_snapshot_at")
            schema_changed = True

        install_indexes = {index["name"] for index in inspector.get_indexes("deck_installs")}
        if "clone_mode" in install_columns and "ix_deck_installs_clone_mode" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_clone_mode ON deck_installs (clone_mode)")
            )
            schema_changed = True
        if "source_deck_id" in install_columns and "ix_deck_installs_source_deck_id" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_source_deck_id ON deck_installs (source_deck_id)")
            )
            schema_changed = True
        if "source_note_type_id" in install_columns and "ix_deck_installs_source_note_type_id" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_source_note_type_id ON deck_installs (source_note_type_id)")
            )
            schema_changed = True
        if "source_owner_user_id" in install_columns and "ix_deck_installs_source_owner_user_id" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_source_owner_user_id ON deck_installs (source_owner_user_id)")
            )
            schema_changed = True
        if "base_snapshot_at" in install_columns and "ix_deck_installs_base_snapshot_at" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_base_snapshot_at ON deck_installs (base_snapshot_at)")
            )
            schema_changed = True

    if schema_changed:
        db.session.commit()
