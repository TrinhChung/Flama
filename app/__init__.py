from typing import Optional
from flask import Flask, has_request_context, jsonify, redirect, request

from models import db

from .cors import init_cors
from .csrf import init_csrf_protection
from .cli import register_cli_commands, register_audit_cli_commands
from .extensions import login_manager, migrate
from .public_media_session import PublicMediaSessionInterface
from .routes import register_blueprints
from .settings import BASE_DIR, build_app_config
from .spa import init_spa_delivery
from .startup import run_startup_maintenance


class MediaHardenedSessionInterface(PublicMediaSessionInterface):
    """Ensure media responses never leak Vary: Cookie or Set-Cookie."""

    def save_session(self, app, session, response) -> None:
        super().save_session(app, session, response)
        if has_request_context() and (
            request.path == "/media/proxy" or request.path.startswith("/media/proxy/")
        ):
            response.vary.discard("Cookie")
            if not response.vary:
                response.headers.pop("Vary", None)
            while "Set-Cookie" in response.headers:
                response.headers.remove("Set-Cookie")


def create_app(config: Optional[dict] = None, audit_mode: bool = False) -> Flask:
    """Application factory that sets up Flask, database, and authentication."""
    app = Flask(
        __name__,
        template_folder=None,
        static_folder=str(BASE_DIR / "static"),
    )
    app.session_interface = MediaHardenedSessionInterface()
    app.config.update(build_app_config(config))
    if audit_mode:
        app.config.update(
            {
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_RUN_DB_CREATE_ALL": False,
                "STARTUP_RUN_USER_MANAGEMENT_SCHEMA": False,
                "STARTUP_RUN_BACKWARD_COMPAT_SCHEMA": False,
                "STARTUP_RUN_DEFAULT_USER_ROLE_SEED": False,
                "STARTUP_RUN_DEFAULT_TAXONOMY_SEED": False,
                "STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED": False,
                "STARTUP_RUN_CLONE_CUTOVER": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
                "WTF_CSRF_ENABLED": False,
            }
        )
    app.config.setdefault(
        "LEGACY_HTTP_ADAPTERS_ENABLED",
        bool(app.config.get("TESTING")),
    )

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    init_spa_delivery(app)
    init_csrf_protection(app)
    init_cors(app)

    if app.config.get("TRUST_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    from models.user import User
    from models.user_identity import UserIdentity  # noqa: F401
    from models.password_reset_token import PasswordResetToken  # noqa: F401
    from models.email_verification_token import EmailVerificationToken  # noqa: F401
    from models.taxonomy import (  # noqa: F401
        TaxonomyDomain,
        TaxonomyFramework,
        TaxonomyFrameworkLevel,
        TaxonomyOption,
        TaxonomySubject,
        TaxonomySubjectOptionMap,
    )
    from models.oauth_client import OAuthClient  # noqa: F401  # register model
    from models.oauth_authorization_code import OAuthAuthorizationCode  # noqa: F401  # register model
    from models.mcp_access_token import McpAccessToken  # noqa: F401  # register model
    from models.user_api_token import UserApiToken  # noqa: F401

    from models.connect_note_ref import ConnectNoteRef  # noqa: F401
    from models.connect_pending_media import ConnectPendingMedia  # noqa: F401
    from models.connect_import_session import ConnectImportSession  # noqa: F401
    from models.connect_import_package import ConnectImportPackage  # noqa: F401
    from models.connect_import_media import ConnectImportMedia  # noqa: F401
    from models.connect_note_type_ref import ConnectNoteTypeRef  # noqa: F401
    from models.connect_source_deck_ref import ConnectSourceDeckRef  # noqa: F401
    from models.connect_source_note_ref import ConnectSourceNoteRef  # noqa: F401
    from models.connect_source_card_ref import ConnectSourceCardRef  # noqa: F401
    from models.connect_review_event_ref import ConnectReviewEventRef  # noqa: F401
    from models.review_analytics import (  # noqa: F401
        DailyReviewCount,
        ReviewAnalyticsGeneration,
        ReviewAnalyticsHead,
    )
    from models.deck_count_snapshot import (  # noqa: F401
        DeckCountContentRevision,
        DeckCountLearnerRevision,
        DeckStudyCountSnapshot,
    )
    # Counter finalizers run after the history guard and after domain flushes.
    from app.services import review_analytics_projection_service as _review_projection  # noqa: F401
    from app.services import deck_count_projection_service as _deck_projection  # noqa: F401
    from models.user_scheduler_settings import UserSchedulerSettings  # noqa: F401  # register model
    from models.user_role import UserRole  # noqa: F401  # register model
    from models.user_permission_audit_log import UserPermissionAuditLog  # noqa: F401
    from models.user_balance_transaction import UserBalanceTransaction  # noqa: F401  # register model
    from models.deck import Deck  # noqa: F401  # register model
    from models.scheduler_preset import SchedulerPreset  # noqa: F401  # register model
    from models.tts_provider_config import TtsProviderConfig  # noqa: F401  # register model
    from models.tts_user_provider_profile import TtsUserProviderProfile  # noqa: F401  # register model
    from models.support_donation_config import SupportDonationConfig  # noqa: F401  # register model
    from models.support_ticket import SupportTicket  # noqa: F401  # register model
    from models.support_ticket_reply import SupportTicketReply  # noqa: F401  # register model
    from models.card_progress import CardProgress  # noqa: F401  # register model
    from models.study_session import StudySession  # noqa: F401  # register model
    from models.study_session_card import StudySessionCard  # noqa: F401
    from models.study_session_commit import StudySessionCommit  # noqa: F401
    from models.study_session_batch import StudySessionBatch  # noqa: F401
    from models.study_session_authority_pin import StudySessionAuthorityPin  # noqa: F401
    from models.study_progress_subject import StudyProgressSubject  # noqa: F401
    from models.study_application import StudyApplication  # noqa: F401
    from models.study_progress_history_fact import StudyProgressHistoryFact  # noqa: F401
    from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent  # noqa: F401
    from models.study_progress_backfill_run import StudyProgressBackfillRun  # noqa: F401
    from models.study_progress_backfill_checkpoint import StudyProgressBackfillCheckpoint  # noqa: F401
    from models.study_progress_backfill_disposition import StudyProgressBackfillDisposition  # noqa: F401
    from models.study_authority_enrollment import StudyAuthorityEnrollment  # noqa: F401
    from models.study_authority_command_receipt import StudyAuthorityCommandReceipt  # noqa: F401
    from models.study_authority_storage_profile import StudyAuthorityStorageProfile  # noqa: F401
    from models.payment_order import PaymentOrder  # noqa: F401  # register model
    from models.payment_order_item import PaymentOrderItem  # noqa: F401  # register model
    from models.payment_webhook_event import PaymentWebhookEvent  # noqa: F401  # register model
    from models.column_preference import (
        VocabularyColumnPreference,
    )  # noqa: F401  # register model
    from models.marketplace_saved_item import MarketplaceSavedItem  # noqa: F401  # register model
    from models.shared_image_asset import SharedImageAsset  # noqa: F401  # register model
    from models.image_asset import ImageAsset  # noqa: F401  # register model
    from models.admin_security_alert import AdminSecurityAlert  # noqa: F401  # register model
    from models.payout_batch import PayoutBatch  # noqa: F401  # register model
    from models.payout_batch_item import PayoutBatchItem  # noqa: F401  # register model
    from models.deck_change_request import DeckChangeRequest  # noqa: F401
    from models.deck_change_request_item import DeckChangeRequestItem  # noqa: F401
    from models.deck_change_request_conflict import DeckChangeRequestConflict  # noqa: F401
    from models.flashcard import (  # noqa: F401  # register model
        AuditLog,
        Card,
        CreatorFeaturePolicy,
        DeckAccessKey,
        DeckAccessKeyRedemption,
        DeckCloneAddedFieldDef,
        DeckCloneAddedNote,
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
        MediaFieldMigrationItem,
        MediaFieldMigrationRun,
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

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        if not request.path.startswith("/api/"):
            from app.services import oauth_service

            frontend_base = oauth_service.get_frontend_base_url(request)
            current_base = oauth_service.get_base_url(request)
            next_url = request.full_path.rstrip("?")
            login_path = f"/login?next={next_url}"
            login_url = (
                f"{frontend_base}{login_path}"
                if frontend_base and frontend_base.rstrip("/") != current_base.rstrip("/")
                else login_path
            )
            return redirect(login_url)
        return (
            jsonify(
                {
                    "error": "AUTHENTICATION_REQUIRED",
                    "message": "Authentication is required.",
                }
            ),
            401,
        )

    if audit_mode:
        register_audit_cli_commands(app)
    else:
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
        if request.path.startswith(("/api/", "/media/", "/static/")):
            resp = jsonify({"error": "NOT_FOUND", "message": "Resource not found."})
            if request.path == "/media/proxy" or request.path.startswith("/media/proxy/"):
                resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
                resp.headers["Pragma"] = "no-cache"
                resp.headers.pop("Vary", None)
            return resp, 404
        from app.spa import serve_react_spa

        return serve_react_spa()

    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 errors."""
        _rollback_failed_session()
        resp = jsonify({"error": "INTERNAL_ERROR", "message": "Internal server error."})
        if request.path == "/media/proxy" or request.path.startswith("/media/proxy"):
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers.pop("Vary", None)
        return resp, 500

    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 errors."""
        resp = jsonify({"error": "FORBIDDEN", "message": "Access is forbidden."})
        if request.path == "/media/proxy" or request.path.startswith("/media/proxy"):
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers.pop("Vary", None)
        return resp, 403

    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handle unexpected exceptions."""
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            status = int(error.code or 500)
            code = str(error.name or "HTTP_ERROR").upper().replace(" ", "_")
            resp = jsonify({"error": code, "message": str(error.description)})
            if request.path == "/media/proxy" or request.path.startswith("/media/proxy"):
                resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
                resp.headers["Pragma"] = "no-cache"
                resp.headers.pop("Vary", None)
            return resp, status
        import logging
        _rollback_failed_session()
        logging.getLogger(__name__).error(
            "Unhandled request exception: %s",
            error,
            exc_info=True,
        )
        resp = jsonify({"error": "INTERNAL_ERROR", "message": "Internal server error."})
        if request.path == "/media/proxy" or request.path.startswith("/media/proxy"):
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers.pop("Vary", None)
        return resp, 500

    if not audit_mode:
        run_startup_maintenance(app)

    return app


def create_audit_app(config: Optional[dict] = None) -> Flask:
    """Application factory that sets up a read-only audit Flask app.

    Enforces that all startup maintenance, schema mutations, cutovers,
    and seed mutators are strictly disabled prior to and during bootstrap.
    Exposes ONLY read-only audit CLI commands on the command surface.
    """
    return create_app(config=config, audit_mode=True)
