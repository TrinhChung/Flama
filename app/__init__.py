from typing import Optional
from flask import Flask

from models import db

from .cli import register_cli_commands
from .extensions import login_manager, migrate
from .routes import register_blueprints
from .settings import BASE_DIR, build_app_config
from .startup import run_startup_maintenance
from .startup_schema import ensure_backward_compatible_schema
from .template_formatters import format_number, format_price_display, format_vnd


def create_app(config: Optional[dict] = None) -> Flask:
    """Application factory that sets up Flask, database, and authentication."""
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.update(build_app_config(config))

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    app.jinja_env.filters["format_number"] = format_number
    app.jinja_env.filters["format_vnd"] = format_vnd
    app.jinja_env.filters["format_price_display"] = format_price_display

    from models.user import User
    from models.mcp_access_token import McpAccessToken  # noqa: F401  # register model
    from models.user_scheduler_settings import UserSchedulerSettings  # noqa: F401  # register model
    from models.user_role import UserRole  # noqa: F401  # register model
    from models.user_permission_audit_log import UserPermissionAuditLog  # noqa: F401
    from models.deck import Deck  # noqa: F401  # register model
    from models.scheduler_preset import SchedulerPreset  # noqa: F401  # register model
    from models.tts_provider_config import TtsProviderConfig  # noqa: F401  # register model
    from models.tts_user_provider_profile import TtsUserProviderProfile  # noqa: F401  # register model
    from models.support_donation_config import SupportDonationConfig  # noqa: F401  # register model
    from models.card_progress import CardProgress  # noqa: F401  # register model
    from models.payment_attempt import PaymentAttempt  # noqa: F401  # register model
    from models.payment_entitlement import PaymentEntitlement  # noqa: F401  # register model
    from models.payment_order import PaymentOrder  # noqa: F401  # register model
    from models.payment_order_item import PaymentOrderItem  # noqa: F401  # register model
    from models.payment_webhook_event import PaymentWebhookEvent  # noqa: F401  # register model
    from models.column_preference import (
        VocabularyColumnPreference,
    )  # noqa: F401  # register model
    from models.marketplace_saved_item import MarketplaceSavedItem  # noqa: F401  # register model
    from models.payout_batch import PayoutBatch  # noqa: F401  # register model
    from models.payout_batch_item import PayoutBatchItem  # noqa: F401  # register model
    from models.deck_change_request import DeckChangeRequest  # noqa: F401
    from models.deck_change_request_item import DeckChangeRequestItem  # noqa: F401
    from models.deck_change_request_conflict import DeckChangeRequestConflict  # noqa: F401
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
            return db.session.get(User, int(user_id))
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

    run_startup_maintenance(
        app,
        ensure_backward_compatible_schema=ensure_backward_compatible_schema,
    )

    return app
