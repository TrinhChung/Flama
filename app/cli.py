"""CLI commands for data seeding and maintenance."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import click
from flask import Flask

from app.startup import run_startup_maintenance
from app.startup_schema import ensure_backward_compatible_schema
from app.services.flashcard_import import ImportValidationError, read_delimited_rows
from app.services.flashcard_legacy import (
    LEGACY_NOTE_TYPE_NAME,
    QUIZ_NOTE_TYPE_NAME,
    ensure_legacy_note_type,
    ensure_quiz_note_type,
)
from app.services.bootstrap_admin_service import sync_bootstrap_admin
from app.services.anki_content_normalizer import backfill_anki_note_entities
from app.services.flashcard_media_normalizer import (
    backfill_media_field_values,
    rollback_media_field_migration,
)
from app.services.user_roles import ensure_default_user_roles
from app.services.tts_provider_service import (
    VOICEVOX_AUDIO_BASE_URL,
    VOICEVOX_POINTS_URL,
    VOICEVOX_SPEAKERS_URL,
    ensure_default_tts_providers,
)
from app.services import flashcards_share
from app.services import flashcards_share_service
from app.utils.bootstrap_admin import resolve_bootstrap_admin_credentials
from models import db
from models.flashcard import (
    Card,
    DeckInstall,
    DeckMarketplaceItem,
    Note,
    NoteType,
    NoteTypeInstall,
    Template,
)
from models.user import User
from models.user_role import UserRole
from models.deck import Deck
from models.card_progress import CardProgress

SEED_REQUIRED_FIELDS = ("deck", "word")
SEED_OPTIONAL_FIELDS = (
    "hanviet",
    "reading",
    "translation_vi",
    "meaning_jp",
    "meaning_vi",
    "usage_jp",
    "usage_vi",
    "example_jp",
    "example_vi",
    "additional_note_jp",
    "additional_note_vi",
    "image",
    "diagram",
    "word_audio",
    "example_audio",
)
SEED_LEGACY_POSITIONAL_FIELDS = (
    "deck",
    "word",
    "reading",
    "translation_vi",
    "meaning_jp",
    "meaning_vi",
    "usage_jp",
    "usage_vi",
    "example_jp",
    "example_vi",
    "additional_note_jp",
    "additional_note_vi",
    "image",
    "word_audio",
    "example_audio",
)
SEED_FULL_POSITIONAL_FIELDS = (
    "deck",
    "word",
    *SEED_OPTIONAL_FIELDS,
)
SEED_FULL_POSITIONAL_FIELDS_WITHOUT_DECK = (
    "word",
    *SEED_OPTIONAL_FIELDS,
)
SEED_ANKI_METADATA_COLUMN_DIRECTIVES = (
    "deck column",
    "guid column",
    "notetype column",
    "tags column",
)
SEED_ANKI_DECK_PATH_KEY = "_anki_deck_path"
SEED_SUPPORTED_SUFFIXES = {".tsv", ".csv", ".txt"}

QUIZ_DUMP_DIR = Path("static") / "deck_dumps" / "trac_nghiem_markdown"
QUIZ_DUMP_MANIFEST = "deck_manifest.json"
QUIZ_DUMP_DEFAULT_FILE = "trac_nghiem_markdown.tsv"
QUIZ_DUMP_REQUIRED_COLUMNS = (
    "question",
    "answer_1",
    "answer_2",
    "answer_3",
    "answer_4",
    "correct_answer",
)


@dataclass
class SeedStats:
    created_decks: int = 0
    seeded_files: int = 0
    created_notes: int = 0
    created_cards: int = 0
    replaced_files: int = 0
    skipped_files: int = 0
    shared_decks: int = 0


def run_study_architecture_audit_command(
    app: Flask | None = None,
    compact: bool = False,
    output_path: str | None = None,
    observed_at: datetime | None = None,
) -> int:
    """Run read-only reconciliation gates for the study refactor and return exit code.

    Guarantees:
    - PASS: 0
    - WARN: 1
    - BLOCK / Error: 2
    - Read-only by construction; does not mutate schema or data.
    - Fails closed on output path errors or startup config errors.
    - Sanitizes DB credentials / secrets from error output.
    """
    import json
    import re
    from pathlib import Path
    from app.services.study_architecture_audit_service import (
        SCHEMA_VERSION,
        build_study_architecture_audit,
    )

    def _sanitize_error(err: Exception | str) -> str:
        msg = str(err)
        # Redact credentials in URLs: scheme://user:pass@host and scheme://:pass@host
        msg = re.sub(r"://([^:@\s]*):([^@\s]+)@", r"://\1:***@", msg)
        # Redact password parameters in connection strings/queries
        msg = re.sub(r"(password|pwd)=([^;&\s]+)", r"\1=***", msg, flags=re.IGNORECASE)
        # Redact secrets, tokens, api keys
        msg = re.sub(r"(secret|api_key|token)=([^;&\s]+)", r"\1=***", msg, flags=re.IGNORECASE)
        return msg

    def _write_output_file(path_str: str, payload_str: str) -> None:
        out_p = Path(path_str)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(payload_str, encoding="utf-8")

    try:
        if app is None:
            from app import create_audit_app

            app = create_audit_app()
        else:
            # Guard: ensure the app instance has not enabled startup maintenance mutators
            if (
                app.config.get("STARTUP_RUN_MAINTENANCE")
                or app.config.get("STARTUP_RUN_DB_CREATE_ALL")
                or app.config.get("STARTUP_RUN_USER_MANAGEMENT_SCHEMA")
                or app.config.get("STARTUP_RUN_BACKWARD_COMPAT_SCHEMA")
                or app.config.get("STARTUP_RUN_DEFAULT_USER_ROLE_SEED")
                or app.config.get("STARTUP_RUN_DEFAULT_TAXONOMY_SEED")
                or app.config.get("STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED")
                or app.config.get("STARTUP_RUN_CLONE_CUTOVER")
            ):
                raise RuntimeError(
                    "Unsafe audit execution: cannot run audit on an app instance with startup maintenance enabled. "
                    "Use wsgi_audit.py or create_audit_app()."
                )

        with app.app_context():
            report = build_study_architecture_audit(now=observed_at)
            payload = json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                indent=None if compact else 2,
            )
            exit_code = int(report.get("verdicts", {}).get("exit_code", 0))

            if output_path:
                try:
                    _write_output_file(output_path, payload)
                except Exception as write_err:
                    clean_write_err = _sanitize_error(write_err)
                    raise RuntimeError(
                        f"Failed to write audit output file '{output_path}': {clean_write_err}"
                    ) from write_err

            click.echo(payload)
            return exit_code
    except Exception as err:
        clean_error = _sanitize_error(err)
        error_report = {
            "schema_version": SCHEMA_VERSION,
            "error": clean_error,
            "verdicts": {
                "pass": [],
                "warn": [],
                "block": [f"Audit execution error: {clean_error}"],
                "overall_status": "BLOCK",
                "exit_code": 2,
            },
        }
        error_payload = json.dumps(
            error_report,
            ensure_ascii=False,
            sort_keys=True,
            indent=None if compact else 2,
        )
        if output_path:
            try:
                _write_output_file(output_path, error_payload)
            except Exception:
                pass
        click.echo(error_payload)
        return 2



def register_audit_cli_commands(app: Flask) -> None:
    """Register ONLY read-only audit commands on audit Flask app instances."""

    @app.cli.command("study-architecture-audit")
    @click.option(
        "--compact",
        is_flag=True,
        default=False,
        help="Emit compact JSON instead of indented JSON.",
    )
    @click.option(
        "--output",
        "output_path",
        type=str,
        default=None,
        help="Optional file path to write audit JSON.",
    )
    @click.option(
        "--observed-at",
        type=click.DateTime(formats=["%Y-%m-%dT%H:%M:%S"]),
        default=None,
        help="Freeze the audit observation time for repeatability.",
    )
    def study_architecture_audit(
        compact: bool,
        output_path: str | None,
        observed_at: datetime | None,
    ) -> None:
        """Print read-only reconciliation gates for the study refactor."""
        import sys

        exit_code = run_study_architecture_audit_command(
            app=app,
            compact=compact,
            output_path=output_path,
            observed_at=observed_at,
        )
        if exit_code != 0:
            sys.exit(exit_code)


def register_cli_commands(app: Flask) -> None:
    """Register custom Flask CLI commands."""

    @app.cli.command("study-authority-enrollment")
    @click.option(
        "--user-id",
        type=click.IntRange(1),
        required=True,
        help="Learner user ID whose persisted authority route will be checked.",
    )
    @click.option(
        "--mode",
        type=click.Choice(["NOTE", "LEGACY"], case_sensitive=False),
        required=True,
        help="Target authority mode.",
    )
    @click.option(
        "--apply",
        is_flag=True,
        default=False,
        help="Commit the fenced transition; default proves eligibility then rolls back.",
    )
    def study_authority_enrollment(user_id: int, mode: str, apply: bool) -> None:
        """Prove and optionally switch one learner's study authority mode."""

        from app.repositories.study_authority_repository import (
            StudyAuthorityFenceError,
        )
        from app.services.study_authority_enrollment_service import (
            StudyAuthorityEnrollmentError,
            stage_note_authority_enrollment,
        )

        if mode.upper() == "LEGACY":
            # Phase 9, D9-02: NOTE keeps new data and repairs come from backup;
            # no learner goes back to LEGACY (runbook P9 §9).
            raise click.ClickException(
                "LEGACY_ENROLLMENT_RETIRED: learners no longer move back to LEGACY; "
                "see docs/task/decoupling/P9_EXECUTION_PLAN_2026-09-30.md §9."
            )
        transition = stage_note_authority_enrollment
        if apply and mode.upper() == "NOTE":
            if not bool(app.config.get("STUDY_WIRE_V4_ENABLED", False)):
                raise click.ClickException(
                    "NOTE_ENROLLMENT_DISABLED: STUDY_WIRE_V4_ENABLED must be true."
                )
            if bool(app.config.get("STUDY_ASYNC_BATCH_ENABLED", False)):
                # Canary policy (P5-10): enroll on the synchronous v4 path;
                # enable async only after the Linux worker rehearsal passes.
                raise click.ClickException(
                    "NOTE_ASYNC_UNAVAILABLE: disable STUDY_ASYNC_BATCH_ENABLED "
                    "for NOTE canary enrollment until the worker rehearsal passes."
                )
        try:
            result = transition(
                db.session,
                learner_user_id=user_id,
                now_utc=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            payload = {
                **asdict(result),
                "applied": bool(apply),
            }
            if apply:
                db.session.commit()
            else:
                db.session.rollback()
        except (StudyAuthorityEnrollmentError, StudyAuthorityFenceError) as exc:
            db.session.rollback()
            code = getattr(exc, "code", "AUTHORITY_TRANSITION_FAILED")
            raise click.ClickException(f"{code}: {exc}") from exc
        click.echo(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )

    @app.cli.command("study-authority-learners")
    @click.option(
        "--mode",
        type=click.Choice(["NOTE", "LEGACY"], case_sensitive=False),
        default=None,
        help="Only print learners currently routed to this mode (no row = LEGACY).",
    )
    def study_authority_learners(mode: str | None) -> None:
        """Print learner user IDs, one per line, for enrollment/audit loops."""

        from sqlalchemy import select

        from models.study_authority_enrollment import StudyAuthorityEnrollment
        from models.user import User

        rows = db.session.execute(
            select(User.id, StudyAuthorityEnrollment.mode_code)
            .outerjoin(
                StudyAuthorityEnrollment,
                StudyAuthorityEnrollment.learner_user_id == User.id,
            )
            .order_by(User.id.asc())
        ).all()
        db.session.rollback()
        for user_id, mode_code in rows:
            if mode is None or (mode_code or "LEGACY") == mode.upper():
                click.echo(int(user_id))

    @app.cli.command("study-authority-read-audit")
    @click.option(
        "--user-id",
        type=click.IntRange(1),
        required=True,
        help="Learner user ID whose NOTE read projection will be compared.",
    )
    @click.option(
        "--observed-at-utc",
        type=str,
        default=None,
        help="Fixed ISO-8601 instant with UTC offset; default is current UTC time.",
    )
    @click.option(
        "--timezone-name",
        type=str,
        default=None,
        help="Supported timezone name/offset for fixed-context comparison; default is learner timezone.",
    )
    def study_authority_read_audit(
        user_id: int, observed_at_utc: str | None, timezone_name: str | None
    ) -> None:
        """Compare canonical NOTE queue semantics with the rollback projection."""

        from app.repositories import study_repository
        from app.repositories.study_authority_repository import (
            StudyAuthorityFenceError,
            lock_study_authority_route,
        )
        from app.services.scheduler_config_service import resolve_deck_options
        from app.services.study_progress_contract import SUBJECT_STATUSES
        from app.services.stats_overview import (
            get_effective_timezone_name,
            normalize_timezone_name,
        )
        from app.services.study_authority_read_service import (
            StudyAuthorityReadError,
            load_study_authority_card_reads,
            summarize_study_authority_queue,
        )
        from models.card import Card
        from models.note import Note
        from models.study_progress_subject import StudyProgressSubject
        from models.user import User

        if observed_at_utc is None:
            observed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            try:
                parsed_at = datetime.fromisoformat(
                    observed_at_utc.strip().replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise click.ClickException(
                    "INVALID_AUDIT_TIME: expected an ISO-8601 instant with UTC offset."
                ) from exc
            if parsed_at.tzinfo is None:
                raise click.ClickException(
                    "INVALID_AUDIT_TIME: a UTC offset is required."
                )
            observed_at = parsed_at.astimezone(timezone.utc).replace(tzinfo=None)
        if timezone_name is not None:
            normalized_timezone = normalize_timezone_name(timezone_name)
            if normalized_timezone is None:
                raise click.ClickException(
                    "INVALID_AUDIT_TIMEZONE: expected a supported timezone name or offset."
                )
            timezone_name = normalized_timezone
        try:
            route = lock_study_authority_route(
                db.session,
                learner_user_id=user_id,
                allow_note_authority=True,
            )
            user = db.session.get(User, user_id)
            timezone_name = timezone_name or get_effective_timezone_name(
                getattr(user, "timezone", "UTC")
            )
            if route.mode_code != "NOTE":
                db.session.rollback()
                click.echo(
                    json.dumps(
                        {
                            "schema_version": "study-authority-read-audit.v1",
                            "user_id": user_id,
                            "observed_at_utc": observed_at.isoformat(timespec="microseconds") + "Z",
                            "timezone": timezone_name,
                            "authority_mode": route.mode_code,
                            "status": "SKIP",
                            "mismatches": [],
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
                return
            owned_note_ids = {
                str(note_id).encode("utf-8")
                for (note_id,) in db.session.query(Note.id)
                .filter(Note.user_id == user_id)
                .all()
            }
            active_subject_keys = {
                bytes(logical_note_key)
                for (logical_note_key,) in db.session.query(
                    StudyProgressSubject.logical_note_key
                )
                .filter(
                    StudyProgressSubject.learner_user_id == user_id,
                    StudyProgressSubject.status_code.in_(
                        tuple(
                            status for status in SUBJECT_STATUSES
                            if status.startswith("MIRRORED_")
                        )
                    ),
                )
                .all()
            }
            # Audit vector: every owned Card (never-studied Notes read as
            # pristine NEW) plus every Card of a Note the learner holds state
            # on, including logical-overlay source Notes and uninstalled ones.
            cards_query = Card.query.join(Note, Card.note_id == Note.id).filter(
                db.or_(
                    Note.user_id == user_id,
                    Card.note_id.in_(
                        sorted(key.decode("utf-8") for key in active_subject_keys)
                    ),
                )
            )
            cards = cards_query.order_by(Card.id.asc()).all()
            card_note_ids = {str(card.note_id).encode("utf-8") for card in cards}
            if not owned_note_ids.issubset(card_note_ids) or not active_subject_keys.issubset(
                card_note_ids
            ):
                raise StudyAuthorityReadError(
                    "INCOMPLETE_AUTHORITY_COVERAGE",
                    "NOTE read audit requires Cards for every owned Note and active subject.",
                )
            reads = load_study_authority_card_reads(
                db.session,
                learner_user_id=user_id,
                cards=tuple(cards),
                now_utc=observed_at,
                timezone_name=timezone_name,
                deck_options_by_card_id={
                    str(card.id): resolve_deck_options(
                        user_id=user_id,
                        deck_id=card.note.deck_id,
                    )
                    for card in cards
                },
            )
            canonical = summarize_study_authority_queue(
                cards=tuple(cards),
                reads_by_card_id=reads,
                learner_user_id=user_id,
                now_utc=observed_at,
                timezone_name=timezone_name,
            )
            legacy_counts = study_repository.query_study_queue_counts(
                cards_query,
                user_id=user_id,
                now=observed_at,
                timezone_name=timezone_name,
            )
            legacy_selected = study_repository.query_next_due_card_id(
                cards_query,
                user_id=user_id,
                now=observed_at,
                timezone_name=timezone_name,
            )
            legacy_pending = study_repository.query_pending_learning_summary(
                cards_query,
                user_id=user_id,
                now=observed_at,
                timezone_name=timezone_name,
            )
            legacy_due_order, legacy_ahead_order = (
                study_repository.query_study_card_order(
                    cards_query,
                    user_id=user_id,
                    now=observed_at,
                    timezone_name=timezone_name,
                )
            )
            mismatches: list[str] = []
            canonical_counts = (
                canonical.new_count,
                canonical.learn_count,
                canonical.due_count,
            )
            if canonical_counts != tuple(int(value) for value in legacy_counts):
                mismatches.append("queue_counts")
            if canonical.selected_card_id != legacy_selected:
                mismatches.append("selected_card_id")
            if canonical.due_card_ids != legacy_due_order:
                mismatches.append("due_order")
            if canonical.learn_ahead_card_ids != legacy_ahead_order:
                mismatches.append("learn_ahead_order")
            if (
                canonical.pending_learning_count != int(legacy_pending[0])
                or canonical.next_due_at != legacy_pending[1]
            ):
                mismatches.append("pending_learning")
            payload = {
                "schema_version": "study-authority-read-audit.v1",
                "user_id": user_id,
                "observed_at_utc": observed_at.isoformat(timespec="microseconds") + "Z",
                "timezone": timezone_name,
                "authority_mode": route.mode_code,
                "enrollment_epoch": route.epoch,
                "card_count": len(cards),
                "status": "PASS" if not mismatches else "BLOCK",
                "mismatches": mismatches,
                "canonical": {
                    "new": canonical.new_count,
                    "learn": canonical.learn_count,
                    "due": canonical.due_count,
                    "selected_card_id": canonical.selected_card_id,
                    "pending_learning_count": canonical.pending_learning_count,
                    "next_due_at": (
                        canonical.next_due_at.isoformat()
                        if canonical.next_due_at is not None
                        else None
                    ),
                },
            }
            db.session.rollback()
        except (StudyAuthorityFenceError, StudyAuthorityReadError) as exc:
            db.session.rollback()
            code = getattr(exc, "code", "AUTHORITY_READ_AUDIT_FAILED")
            raise click.ClickException(f"{code}: {exc}") from exc
        click.echo(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        if mismatches:
            raise click.ClickException(
                "AUTHORITY_READ_PARITY_DIVERGED: canonical and rollback reads differ."
            )

    @app.cli.command("study-progress-backfill")
    @click.option(
        "--apply",
        is_flag=True,
        default=False,
        help="Persist mirror/disposition/checkpoint batches; default is read-only dry-run.",
    )
    @click.option(
        "--run-id",
        type=str,
        default=None,
        help="Resume one existing apply run by canonical UUID.",
    )
    @click.option(
        "--max-batches",
        type=click.IntRange(1, 100_000),
        default=None,
        help="Stop cleanly after a bounded number of committed batches.",
    )
    def study_progress_backfill(
        apply: bool,
        run_id: str | None,
        max_batches: int | None,
    ) -> None:
        """Dry-run or resume the fenced Phase 4 current-progress backfill."""

        from app.services.study_progress_backfill_service import (
            StudyProgressBackfillError,
            run_current_progress_backfill,
        )

        try:
            result = run_current_progress_backfill(
                db.session,
                apply=apply,
                run_id=run_id,
                max_batches=max_batches,
            )
        except StudyProgressBackfillError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(
            json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )

    @app.cli.command("study-phase6-attribution-backfill")
    @click.option(
        "--apply",
        is_flag=True,
        default=False,
        help="Stamp occurrences and Note attribution in committed batches; default only counts.",
    )
    @click.option(
        "--batch-size",
        type=click.IntRange(100, 20_000),
        default=2000,
        show_default=True,
        help="Rows per committed batch.",
    )
    def study_phase6_attribution_backfill(apply: bool, batch_size: int) -> None:
        """Bind Cards to occurrences and old rows to their Note after migration 46."""

        from app.services.study_note_attribution_service import backfill_phase6_attribution

        result = backfill_phase6_attribution(apply=apply, batch_size=batch_size)
        click.echo(
            json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )

    @app.cli.command("study-session-retention")
    @click.option(
        "--apply",
        is_flag=True,
        default=False,
        help="Expire stale open sessions and delete old membership rows; default is a dry-run.",
    )
    @click.option(
        "--older-than-days",
        type=click.IntRange(2, 3650),
        default=30,
        show_default=True,
        help="Keep membership rows of sessions newer than this.",
    )
    @click.option(
        "--grace-hours",
        type=click.IntRange(0, 24 * 365),
        default=24,
        show_default=True,
        help="Expire open sessions only this long after their lease ended.",
    )
    @click.option(
        "--batch-sessions",
        type=click.IntRange(1, 5000),
        default=200,
        show_default=True,
        help="Sessions per delete transaction.",
    )
    def study_session_retention(
        apply: bool, older_than_days: int, grace_hours: int, batch_sessions: int,
    ) -> None:
        """Phase 7: expire stale open sessions and purge old session membership rows.

        Review events, history, receipts, progress and the session rows
        themselves are never deleted.
        """

        from datetime import timedelta

        from app.services.study_session_retention_service import run_session_retention

        report = run_session_retention(
            older_than_days=older_than_days,
            grace=timedelta(hours=grace_hours),
            batch_sessions=batch_sessions,
            apply=apply,
        )
        click.echo(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))

    @app.cli.command("study-phase9-readiness")
    @click.option(
        "--window-days",
        type=click.IntRange(1, 365),
        default=30,
        show_default=True,
        help="Observation window for old usage.",
    )
    def study_phase9_readiness(window_days: int) -> None:
        """Read-only evidence for the Phase 9 contraction gates."""

        from app.services.study_phase9_readiness_service import build_phase9_readiness

        click.echo(json.dumps(build_phase9_readiness(window_days=window_days), sort_keys=True))

    @app.cli.command("startup-maintenance")
    @click.option("--skip-db-create-all", is_flag=True, default=False, help="Skip db.create_all().")
    @click.option(
        "--skip-user-management-schema",
        is_flag=True,
        default=False,
        help="Skip user/role schema compatibility maintenance.",
    )
    @click.option(
        "--skip-backward-compat-schema",
        is_flag=True,
        default=False,
        help="Skip legacy backward-compatible schema patching.",
    )
    @click.option(
        "--skip-user-role-seed",
        is_flag=True,
        default=False,
        help="Skip default user-role seeding.",
    )
    @click.option(
        "--skip-tts-provider-seed",
        is_flag=True,
        default=False,
        help="Skip default TTS provider seeding.",
    )
    @click.option(
        "--skip-clone-cutover",
        is_flag=True,
        default=False,
        help="Skip one-time clone cutover maintenance.",
    )
    @click.option(
        "--no-fail-on-mismatch",
        is_flag=True,
        default=False,
        help="Do not fail the command when clone cutover detects mismatches.",
    )
    def startup_maintenance(
        skip_db_create_all: bool,
        skip_user_management_schema: bool,
        skip_backward_compat_schema: bool,
        skip_user_role_seed: bool,
        skip_tts_provider_seed: bool,
        skip_clone_cutover: bool,
        no_fail_on_mismatch: bool,
    ) -> None:
        """Run startup maintenance explicitly from the CLI."""
        config_overrides = {
            "STARTUP_RUN_MAINTENANCE": True,
            "STARTUP_RUN_DB_CREATE_ALL": not skip_db_create_all,
            "STARTUP_RUN_USER_MANAGEMENT_SCHEMA": not skip_user_management_schema,
            "STARTUP_RUN_BACKWARD_COMPAT_SCHEMA": not skip_backward_compat_schema,
            "STARTUP_RUN_DEFAULT_USER_ROLE_SEED": not skip_user_role_seed,
            "STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED": not skip_tts_provider_seed,
            "STARTUP_RUN_CLONE_CUTOVER": not skip_clone_cutover,
            "STARTUP_CUTOVER_FAIL_ON_MISMATCH": not no_fail_on_mismatch,
        }
        run_startup_maintenance(
            app,
            ensure_backward_compatible_schema=ensure_backward_compatible_schema,
            config_overrides=config_overrides,
        )
        click.echo("Startup maintenance completed.")

    @app.cli.command("anki-normalize-entities")
    @click.option("--user-id", type=int, default=None, help="Limit the backfill to one user ID.")
    @click.option("--deck-id", type=int, default=None, help="Limit the backfill to one deck ID.")
    @click.option("--apply", is_flag=True, default=False, help="Commit changes; otherwise run as a dry run.")
    def anki_normalize_entities(user_id: int | None, deck_id: int | None, apply: bool) -> None:
        """Normalize safe apostrophe entities in notes imported from Anki."""
        result = backfill_anki_note_entities(user_id=user_id, deck_id=deck_id)
        if apply:
            db.session.commit()
        else:
            db.session.rollback()
        click.echo(
            f"Anki entity normalization {'applied' if apply else 'dry run'}. "
            f"scanned={result.scanned}, changed={result.changed}"
        )

    @app.cli.command("media-normalize-fields")
    @click.option("--user-id", type=int, default=None, help="Limit the migration to one user ID.")
    @click.option("--deck-id", type=int, default=None, help="Limit the migration to one deck ID.")
    @click.option("--apply", is_flag=True, default=False, help="Commit audited changes; otherwise dry-run.")
    @click.option("--no-overlays", is_flag=True, default=False, help="Skip active clone overlays.")
    @click.option("--no-templates", is_flag=True, default=False, help="Skip Template URL-helper migration.")
    def media_normalize_fields(
        user_id: int | None,
        deck_id: int | None,
        apply: bool,
        no_overlays: bool,
        no_templates: bool,
    ) -> None:
        """Audit or migrate media fields to newline-delimited canonical URLs."""
        result = backfill_media_field_values(
            user_id=user_id,
            deck_id=deck_id,
            apply=apply,
            include_overlays=not no_overlays,
            include_templates=not no_templates,
        )
        if apply:
            db.session.commit()
        else:
            db.session.rollback()
        click.echo(
            f"Media normalization {'applied' if apply else 'dry run'}. "
            f"run_id={result.run_id or '-'}, scanned={result.scanned}, "
            f"fields={result.scanned_fields}, changed={result.changed}, "
            f"normalized={result.normalized}, cleared={result.cleared}, "
            f"quarantined={result.quarantined}, overlays={result.overlays_changed}, "
            f"templates={result.templates_changed}"
        )
        if not apply and result.changed > 0:
            click.echo("Re-run with --apply after reviewing the dry-run summary.")

    @app.cli.command("media-normalize-rollback")
    @click.option("--run-id", required=True, help="Migration run UUID to restore.")
    @click.option("--apply", is_flag=True, default=False, help="Commit restore; otherwise dry-run.")
    def media_normalize_rollback(run_id: str, apply: bool) -> None:
        """Restore one migration run without overwriting later user edits."""
        result = rollback_media_field_migration(run_id=run_id, apply=apply)
        if apply:
            db.session.commit()
        else:
            db.session.rollback()
        click.echo(
            f"Media rollback {'applied' if apply else 'dry run'}. "
            f"run_id={result.run_id}, restorable={result.restorable}, "
            f"restored={result.restored}, skipped_changed_since={result.skipped_changed_since}, "
            f"missing={result.missing}"
        )

    @app.cli.command("clone-cutover-overlay")
    @click.option(
        "--no-fail-on-mismatch",
        is_flag=True,
        default=False,
        help="Continue processing installs even when one legacy install cannot be migrated cleanly.",
    )
    def clone_cutover_overlay(no_fail_on_mismatch: bool) -> None:
        """One-shot cutover from legacy clone rows to logical overlay model."""
        summary = flashcards_share.cutover_clone_model_to_overlay_only(
            fail_on_mismatch=not no_fail_on_mismatch,
        )
        db.session.commit()
        click.echo(
            "Cutover done. "
            f"total={summary.get('total_installs', 0)}, "
            f"migrated={summary.get('migrated', 0)}, "
            f"failed={summary.get('failed', 0)}, "
            f"deck_map_rows={summary.get('deck_map_rows', 0)}, "
            f"note_pairs={summary.get('note_pairs', 0)}, "
            f"note_overrides={summary.get('note_overrides', 0)}, "
            f"progress_rows={summary.get('progress_rows', 0)}"
        )
        if summary.get("errors"):
            click.echo("Errors:")
            for error in summary.get("errors", []):
                click.echo(
                    f"- deck_install_id={error.get('deck_install_id')}: {error.get('message')}"
                )

    @app.cli.command("taxonomy-seed")
    def taxonomy_seed() -> None:
        """Seed default domains, subjects, frameworks, levels, and options into DB."""
        from app.services.marketplace_taxonomy_service import ensure_default_taxonomy_data
        from app.repositories import marketplace_taxonomy_repository

        ensure_default_taxonomy_data(db.session)
        db.session.commit()

        domains = marketplace_taxonomy_repository.list_domains(include_inactive=True)
        subjects = marketplace_taxonomy_repository.list_subjects(include_inactive=True)
        frameworks = marketplace_taxonomy_repository.list_frameworks(include_inactive=True)
        levels = marketplace_taxonomy_repository.list_framework_levels(include_inactive=True)
        options = marketplace_taxonomy_repository.list_options(include_inactive=True)

        click.echo(
            f"Taxonomy seeding complete. "
            f"domains={len(domains)}, "
            f"subjects={len(subjects)}, "
            f"frameworks={len(frameworks)}, "
            f"levels={len(levels)}, "
            f"options={len(options)}"
        )

    @app.cli.command("taxonomy-verify")
    def taxonomy_verify() -> None:
        """Verify database taxonomy entities against existing marketplace items."""
        from app.repositories import marketplace_taxonomy_repository

        domains = {d.id: d.label for d in marketplace_taxonomy_repository.list_domains(include_inactive=True)}
        subjects = {s.id: s.label for s in marketplace_taxonomy_repository.list_subjects(include_inactive=True)}
        frameworks = {f.id: f.label for f in marketplace_taxonomy_repository.list_frameworks(include_inactive=True)}
        levels = {l.id: l.label for l in marketplace_taxonomy_repository.list_framework_levels(include_inactive=True)}

        deck_items = DeckMarketplaceItem.query.all()
        note_type_items = NoteType.query.all()

        unmatched_domains = set()
        unmatched_subjects = set()

        for item in deck_items:
            meta = item.taxonomy_metadata or {}
            dom = meta.get("domain")
            sub = meta.get("subject")
            if dom and dom not in domains:
                unmatched_domains.add(dom)
            if sub and sub not in subjects:
                unmatched_subjects.add(sub)

        for item in note_type_items:
            meta = item.taxonomy_metadata or {}
            dom = meta.get("domain")
            sub = meta.get("subject")
            if dom and dom not in domains:
                unmatched_domains.add(dom)
            if sub and sub not in subjects:
                unmatched_subjects.add(sub)

        click.echo(
            f"Taxonomy verification: "
            f"domains_in_db={len(domains)}, subjects_in_db={len(subjects)}, "
            f"frameworks_in_db={len(frameworks)}, levels_in_db={len(levels)}. "
            f"deck_items_checked={len(deck_items)}, note_types_checked={len(note_type_items)}"
        )
        if unmatched_domains or unmatched_subjects:
            click.echo(f"Warning: unmatched domains={unmatched_domains}, unmatched subjects={unmatched_subjects}")
        else:
            click.echo("All marketplace taxonomy references are 100% matched with DB taxonomy entities.")

    @app.cli.command("deck-release-bootstrap")
    @click.option(
        "--deck-item-id",
        type=str,
        default=None,
        help="Bootstrap only one marketplace deck listing.",
    )
    @click.option(
        "--limit",
        type=click.IntRange(1, 10_000),
        default=100,
        show_default=True,
        help="Maximum number of visible legacy listings to inspect.",
    )
    @click.option(
        "--apply",
        is_flag=True,
        default=False,
        help="Commit each initial release; otherwise validate with rollback.",
    )
    def deck_release_bootstrap(
        deck_item_id: str | None,
        limit: int,
        apply: bool,
    ) -> None:
        """Pin visible legacy listings to immutable initial releases."""

        query = DeckMarketplaceItem.query.filter(
            DeckMarketplaceItem.current_release_id.is_(None),
            DeckMarketplaceItem.publish_status.in_(["published", "unlisted"]),
        )
        if deck_item_id:
            query = query.filter(DeckMarketplaceItem.id == deck_item_id.strip())
        item_ids = [
            str(row[0])
            for row in query.with_entities(DeckMarketplaceItem.id)
            .order_by(DeckMarketplaceItem.id.asc())
            .limit(limit)
            .all()
        ]

        counts = {
            "created": 0,
            "already_versioned": 0,
            "not_visible": 0,
            "missing": 0,
            "failed": 0,
        }
        failures: list[dict[str, Any]] = []
        for current_item_id in item_ids:
            try:
                result = flashcards_share.ensure_visible_deck_item_initial_release(
                    current_item_id
                )
                status = str(result.get("status") or "failed")
                counts[status] = counts.get(status, 0) + 1
                if status == "failed":
                    failures.append(result)
                if apply and status == "created":
                    db.session.commit()
                else:
                    db.session.rollback()
            except Exception as exc:
                db.session.rollback()
                counts["failed"] += 1
                failures.append(
                    {"deck_item_id": current_item_id, "error": str(exc)}
                )

        click.echo(
            "Deck release bootstrap "
            f"{'applied' if apply else 'dry run'}: "
            f"scanned={len(item_ids)}, created={counts['created']}, "
            f"failed={counts['failed']}, skipped="
            f"{counts['already_versioned'] + counts['not_visible'] + counts['missing']}"
        )
        for failure in failures:
            click.echo(
                f"- deck_item_id={failure.get('deck_item_id')}: "
                f"{failure.get('error') or 'unknown error'}"
            )
        if failures:
            raise click.ClickException(
                f"{len(failures)} deck listing(s) could not be bootstrapped."
            )

    @app.cli.command("market-stats-reconcile")
    @click.option(
        "--kind",
        type=click.Choice(["all", "deck", "note-type"]),
        default="all",
        show_default=True,
    )
    @click.option("--limit", type=click.IntRange(1, 100_000), default=10_000, show_default=True)
    @click.option("--apply", is_flag=True, default=False)
    def market_stats_reconcile(kind: str, limit: int, apply: bool) -> None:
        """Re-evaluate per-install activity and repair parent counters."""
        now = datetime.utcnow()
        touched_note_types: set[str] = set()
        touched_deck_items: set[str] = set()
        evaluated = 0

        if kind in {"all", "note-type"}:
            installs = NoteTypeInstall.query.order_by(NoteTypeInstall.id.asc()).limit(limit).all()
            for install in installs:
                flashcards_share_service._update_note_type_install_market_activity(
                    install,
                    now=now,
                )
                touched_note_types.add(str(install.source_note_type_id))
                evaluated += 1

        remaining = max(limit - evaluated, 0) if kind == "all" else limit
        if kind in {"all", "deck"} and remaining:
            installs = DeckInstall.query.order_by(DeckInstall.id.asc()).limit(remaining).all()
            for install in installs:
                flashcards_share_service._update_deck_install_market_activity(
                    install,
                    now=now,
                )
                touched_deck_items.add(str(install.deck_item_id))
                evaluated += 1

        for note_type in NoteType.query.filter(NoteType.id.in_(touched_note_types)).all():
            flashcards_share_service.recompute_note_type_market_stats(note_type)
        for deck_item in DeckMarketplaceItem.query.filter(
            DeckMarketplaceItem.id.in_(touched_deck_items)
        ).all():
            flashcards_share_service.recompute_deck_item_market_stats(deck_item)

        if apply:
            db.session.commit()
        else:
            db.session.rollback()
        click.echo(
            f"Market stats {'applied' if apply else 'dry run'}: "
            f"evaluated={evaluated}, note_types={len(touched_note_types)}, "
            f"deck_items={len(touched_deck_items)}"
        )

    @app.cli.command("marketplace-samples-backfill")
    @click.option("--limit", type=click.IntRange(1, 10_000), default=100, show_default=True)
    @click.option("--apply", is_flag=True, default=False)
    def marketplace_samples_backfill(limit: int, apply: bool) -> None:
        """Backfill deterministic samples from each listing's immutable release."""
        from app.services import marketplace_query_service

        items = (
            DeckMarketplaceItem.query.filter(
                DeckMarketplaceItem.current_release_id.isnot(None),
                db.or_(
                    DeckMarketplaceItem.preview_samples_release_id.is_(None),
                    DeckMarketplaceItem.preview_samples_release_id
                    != DeckMarketplaceItem.current_release_id,
                    DeckMarketplaceItem.preview_samples_schema_version.is_(None),
                    DeckMarketplaceItem.preview_samples_schema_version != 1,
                    DeckMarketplaceItem.preview_samples_json.is_(None),
                ),
            )
            .order_by(DeckMarketplaceItem.id.asc())
            .limit(limit)
            .all()
        )
        updated = 0
        for item in items:
            if item.current_release is None:
                continue
            item.preview_samples_json = (
                marketplace_query_service.build_release_sample_cache_from_release(
                    item,
                    item.current_release,
                    limit=5,
                )
            )
            item.preview_samples_release_id = item.current_release_id
            item.preview_samples_schema_version = 1
            updated += 1
        if apply:
            db.session.commit()
        else:
            db.session.rollback()
        click.echo(
            f"Marketplace samples {'applied' if apply else 'dry run'}: updated={updated}"
        )

    @app.cli.command("deck-notetype-audit")
    @click.option("--limit", type=click.IntRange(1, 10_000), default=1000, show_default=True)
    @click.option("--apply", is_flag=True, default=False)
    def deck_notetype_audit(limit: int, apply: bool) -> None:
        """Audit pointers and fill only unambiguous missing source NoteTypes."""
        counts = {"valid": 0, "backfilled": 0, "missing": 0, "ambiguous": 0, "mismatch": 0}
        items = DeckMarketplaceItem.query.order_by(DeckMarketplaceItem.id.asc()).limit(limit).all()
        for item in items:
            if item.source_deck_id is None:
                counts["missing"] += 1
                continue
            resolved_id, error = flashcards_share_service.resolve_single_note_type_for_deck(
                deck_id=item.source_deck_id,
                owner_user_id=item.owner_user_id,
            )
            pointer = str(item.source_note_type_id or "").strip()
            if resolved_id and not pointer:
                item.source_note_type_id = resolved_id
                counts["backfilled"] += 1
            elif error and "same template" in error:
                counts["ambiguous"] += 1
            elif error:
                counts["missing"] += 1
            elif pointer != str(resolved_id):
                counts["mismatch"] += 1
            else:
                counts["valid"] += 1
        if apply:
            db.session.commit()
        else:
            db.session.rollback()
        click.echo(
            f"Deck NoteType audit {'applied' if apply else 'dry run'}: "
            + ", ".join(f"{key}={value}" for key, value in counts.items())
        )

    @app.cli.command("user-role-seed")
    def user_role_seed() -> None:
        """Seed default user roles and backfill users missing role mapping."""
        ensure_default_user_roles(db.session)
        db.session.commit()
        roles = UserRole.query.order_by(UserRole.position.asc(), UserRole.id.asc()).all()
        codes = ", ".join(role.code for role in roles)
        click.echo(f"Done. Seeded roles: {codes}")

    @app.cli.command("bootstrap-admin-sync")
    def bootstrap_admin_sync() -> None:
        """Create or update the environment-managed admin account."""
        credentials = resolve_bootstrap_admin_credentials(require_password=True)
        result = sync_bootstrap_admin(db.session, credentials=credentials)
        db.session.commit()
        changed_fields = ",".join(result.changed_fields) or "none"
        click.echo(
            "Bootstrap admin synchronized. "
            f"user_id={result.user_id} "
            f"created={str(result.created).lower()} "
            f"changed={changed_fields}"
        )

    @app.cli.command("tts-provider-seed")
    def tts_provider_seed() -> None:
        """Seed default global TTS providers (currently VoiceVox)."""
        result = ensure_default_tts_providers(db.session)
        db.session.commit()
        click.echo(
            "Done. "
            f"created={result.get('created', 0)}, "
            f"updated={result.get('updated', 0)}. "
            f"VoiceVox endpoints: audio={VOICEVOX_AUDIO_BASE_URL}, "
            f"speakers={VOICEVOX_SPEAKERS_URL}, points={VOICEVOX_POINTS_URL}."
        )

    @app.cli.command("payments-expire-stale")
    def payments_expire_stale() -> None:
        """Expire stale unpaid payment attempts/orders."""
        from app.services import payment_service

        result = payment_service.expire_stale_orders()
        click.echo(
            "Done. "
            f"expired_attempts={int(result.get('expired_attempts') or 0)}, "
            f"expired_orders={int(result.get('expired_orders') or 0)}"
        )

    @app.cli.command("dev-purge-data")
    @click.option("--yes", is_flag=True, default=False, help="Confirm destructive purge.")
    def dev_purge_data(yes: bool) -> None:
        """Delete all application rows while keeping schema/migrations."""
        if not yes:
            raise click.ClickException("Refusing to purge data without --yes")

        bind = db.session.get_bind()
        dialect = bind.dialect.name if bind is not None else ""
        is_mysql = str(dialect).lower().startswith("mysql")

        try:
            if is_mysql:
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS=0"))

            for table in reversed(db.metadata.sorted_tables):
                # Alembic migration tracking (if present in metadata) must be preserved.
                if table.name == "alembic_version":
                    continue
                db.session.execute(table.delete())

            db.session.commit()
            click.echo("Done. Purged all application data rows.")
        except Exception as exc:  # pragma: no cover - defensive rollback path
            db.session.rollback()
            raise click.ClickException(f"Failed to purge data: {exc}") from exc
        finally:
            if is_mysql:
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS=1"))
                db.session.commit()

    @app.cli.command("vocab-seed")
    @click.option(
        "--path",
        "seed_path",
        default="static/seed_data",
        show_default=True,
        help="Path to seed source. If path is 'static', command auto-uses 'static/seed_data'.",
    )
    @click.option(
        "--replace-lessons",
        is_flag=True,
        default=False,
        help="Replace entries in existing seeded decks instead of skipping them.",
    )
    @click.option(
        "--owner-user-id",
        type=int,
        default=None,
        help="Owner user id for seeded decks/notes. Defaults to first available user.",
    )
    @click.option(
        "--share-seeded-decks/--no-share-seeded-decks",
        default=True,
        show_default=True,
        help="Auto publish only top-level seeded decks (with full subtree) to shared marketplace.",
    )
    def vocab_seed(
        seed_path: str,
        replace_lessons: bool,
        owner_user_id: int | None,
        share_seeded_decks: bool,
    ) -> None:
        """Seed deck tree from static folder structure.

        Rules:
        - `seed_data` is container only (not a deck node)
        - Subfolders under `seed_data` start hierarchy
        - Folder -> Deck node
        - Headered file (.tsv/.csv/.txt) -> Leaf deck named after the file
        - Anki export with `#deck column` -> Decks split from that column
        """
        _seed_vocabulary_data(
            seed_path=seed_path,
            replace_lessons=replace_lessons,
            owner_user_id=owner_user_id,
            share_seeded_decks=share_seeded_decks,
        )

    @app.cli.command("seed-data-ensure")
    @click.option(
        "--path",
        "seed_path",
        default="static/seed_data",
        show_default=True,
        help="Seed source checked during deployment.",
    )
    @click.option(
        "--share-seeded-decks/--no-share-seeded-decks",
        default=True,
        show_default=True,
        help="Require top-level seeded decks to be published in the marketplace.",
    )
    def seed_data_ensure(
        seed_path: str,
        share_seeded_decks: bool,
    ) -> None:
        """Ensure production seed bundles exist without replacing existing data."""
        credentials = resolve_bootstrap_admin_credentials(require_password=False)
        bootstrap_user = User.query.filter_by(email=credentials.email).first()
        if bootstrap_user is None:
            raise click.ClickException(
                "Bootstrap admin does not exist. Run bootstrap-admin-sync before seed-data-ensure."
            )
        target_user = _resolve_seed_data_owner(bootstrap_user)
        if target_user.id != bootstrap_user.id:
            click.echo(
                "Using existing canonical seed owner. "
                f"owner_user_id={target_user.id}, bootstrap_user_id={bootstrap_user.id}"
            )

        root = _resolve_seed_root(_resolve_seed_path(seed_path))
        gaps = _find_seed_data_gaps(
            root=root,
            owner_user_id=target_user.id,
            share_seeded_decks=share_seeded_decks,
        )
        if not gaps:
            click.echo(
                "Seed data already complete. "
                f"owner_user_id={target_user.id}, path={root}"
            )
            return

        click.echo("Seed data is incomplete:")
        for gap in gaps:
            click.echo(f"- {gap}")
        click.echo("Seeding only missing bundles; existing notes and progress are preserved.")

        _seed_vocabulary_data(
            seed_path=str(root),
            replace_lessons=False,
            owner_user_id=target_user.id,
            share_seeded_decks=share_seeded_decks,
        )

        remaining_gaps = _find_seed_data_gaps(
            root=root,
            owner_user_id=target_user.id,
            share_seeded_decks=share_seeded_decks,
        )
        if remaining_gaps:
            joined = "; ".join(remaining_gaps)
            raise click.ClickException(
                f"Seed data is still incomplete after ensure: {joined}"
            )
        click.echo(
            "Seed data ensure completed. "
            f"owner_user_id={target_user.id}, path={root}"
        )

    @app.cli.command("seed-oauth-client")
    @click.option("--client-id", required=True, help="OAuth Client ID (e.g. chatgpt_flama)")
    @click.option("--name", "client_name", required=True, help="OAuth Client Name (e.g. ChatGPT)")
    @click.option("--redirect-uri", "redirect_uris", multiple=True, required=True, help="Allowed Redirect URIs (can specify multiple)")
    @click.option("--secret", "client_secret", default=None, help="Client Secret for confidential clients (optional)")
    @click.option("--client-uri", default=None, help="Client Homepage / Information URI")
    @click.option("--confidential/--public", default=True, help="Whether this is a confidential client")
    def seed_oauth_client(
        client_id: str,
        client_name: str,
        redirect_uris: tuple[str, ...],
        client_secret: str | None,
        client_uri: str | None,
        confidential: bool,
    ) -> None:
        """Seed or update an OAuth 2.1 client."""
        from app.services import oauth_service

        client = oauth_service.register_oauth_client(
            client_id=client_id,
            client_name=client_name,
            client_secret=client_secret,
            client_uri=client_uri,
            redirect_uris=list(redirect_uris),
            is_confidential=confidential,
        )
        click.echo(
            f"OAuth Client saved: id={client.id}, client_id={client.client_id}, name='{client.client_name}'"
        )

    @app.cli.command("list-oauth-clients")
    def list_oauth_clients_cmd() -> None:
        """List registered OAuth 2.1 clients."""
        from app.repositories import oauth_repository

        clients = oauth_repository.list_clients()
        if not clients:
            click.echo("No OAuth clients found.")
            return
        for c in clients:
            click.echo(
                f"- [{c.id}] client_id={c.client_id} name='{c.client_name}' confidential={c.is_confidential} redirect_uris={c.get_redirect_uris()}"
            )

    @app.cli.command("email-test")
    @click.argument("recipient", type=str)
    def email_test_cmd(recipient: str) -> None:
        """Send a test transactional email to verify delivery configuration."""
        from datetime import datetime, timezone
        from app.email import (
            EmailCategory,
            TemplateKey,
            TransactionalEmailRequest,
            get_email_service,
        )

        service = get_email_service(app.config)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        click.echo(f"Testing email delivery to: {recipient}")
        click.echo(f"- EMAIL_ENABLED: {service.config.enabled}")
        click.echo(f"- EMAIL_PROVIDER: {service.config.provider}")
        click.echo(f"- EMAIL_ENVIRONMENT: {service.config.environment}")
        click.echo(f"- EMAIL_FROM_ADDRESS: {service.config.from_address}")

        req = TransactionalEmailRequest(
            template_key=TemplateKey.SYSTEM_DELIVERY_TEST,
            recipient=recipient.strip(),
            variables={"checked_at": now_str},
            category=EmailCategory.SYSTEM_NOTIFICATION,
            correlation_id=f"cli-test-{int(datetime.now(timezone.utc).timestamp())}",
        )

        try:
            result = service.send(req)
            click.echo(f"\n[Result]")
            click.echo(f"- success: {result.success}")
            click.echo(f"- status: {result.status}")
            click.echo(f"- provider: {result.provider}")
            click.echo(f"- provider_message_id: {result.provider_message_id}")
            click.echo(f"- recipient_masked: {result.recipient_masked}")
            click.echo(f"- sent_at: {result.sent_at}")
            click.echo(f"- extra: {result.extra}")
        except Exception as exc:
            click.echo(f"\n[Delivery Error] {type(exc).__name__}: {exc}", err=True)
            raise click.ClickException(str(exc))

    @app.cli.group("images")
    def images_group() -> None:
        """Manage secure image pipeline queues and background workers."""
        pass

    @images_group.command("process-queue")
    @click.option("--max-jobs", default=100, help="Maximum number of jobs to process.")
    def process_queue_cmd(max_jobs: int) -> None:
        """Drain and process pending image jobs from the queue."""
        from pathlib import Path
        from app.services.image_worker_service import drain_image_queue

        upload_root = Path(app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
        click.echo(f"Processing image queue (max {max_jobs} jobs)...")
        results = drain_image_queue(upload_root=upload_root, max_jobs=max_jobs)
        click.echo(f"Done! Processed: {results['processed_count']}, Failed: {results['failed_count']}, Rejected: {results['rejected_count']}")

    @images_group.command("clear-queue")
    def clear_queue_cmd() -> None:
        """Clear all pending jobs from the image queue."""
        from app.services.image_queue_service import clear_image_queue

        clear_image_queue()
        click.echo("Image queue cleared.")

    @app.cli.group("strokes")
    def strokes_group() -> None:
        """Manage Kanji and Hanzi SVG stroke datasets."""
        pass

    @strokes_group.command("build-dataset")
    @click.option("--locale", default="ja", type=click.Choice(["ja", "zh", "zh-hant"], case_sensitive=False), help="Locale dataset to build.")
    @click.option("--source", required=True, help="Path to directory containing KanjiVG or MakeMeAHanzi SVG files.")
    def build_dataset_cmd(locale: str, source: str) -> None:
        """Build and standardize SVG stroke dataset from source directory."""
        from pathlib import Path
        from app.services.strokes.dataset_builder import build_dataset_from_directory

        static_root = Path(app.static_folder or "static")
        target_dir = static_root / "strokes" / locale.lower()
        click.echo(f"Building stroke dataset for '{locale}' from {source} into {target_dir}...")
        res = build_dataset_from_directory(source_dir=source, target_dir=target_dir, locale=locale)
        click.echo(f"Done! Processed: {res.get('processed', 0)}, Skipped: {res.get('skipped', 0)}")

    @strokes_group.command("seed-starter")
    def seed_starter_cmd() -> None:
        """Seed starter set of common Kanji and Hanzi SVG stroke diagrams into Image Library."""
        from pathlib import Path
        from app.services.strokes.dataset_builder import (
            JA_STARTER_KANJI,
            ZH_STARTER_HANZI,
            ZH_HANT_STARTER_HANZI,
            populate_starter_strokes,
        )
        from app.services.strokes.stroke_service import resolve_stroke_items

        static_root = Path(app.static_folder or "static")
        res = populate_starter_strokes(static_root)
        
        resolve_stroke_items("".join(JA_STARTER_KANJI), locale="ja", max_characters=len(JA_STARTER_KANJI))
        resolve_stroke_items("".join(ZH_STARTER_HANZI), locale="zh", max_characters=len(ZH_STARTER_HANZI))
        resolve_stroke_items("".join(ZH_HANT_STARTER_HANZI), locale="zh-hant", max_characters=len(ZH_HANT_STARTER_HANZI))
        click.echo(f"Starter stroke SVGs seeded into Image Library: {res}")

    @strokes_group.command("status")
    def status_cmd() -> None:
        """Show current stroke dataset and Image Library file counts."""
        from pathlib import Path
        from models.shared_image_asset import SharedImageAsset

        upload_root = Path(app.config.get("FLASHCARD_MEDIA_UPLOAD_ROOT", "media")).resolve()
        
        lib_ja = upload_root / "library" / "strokes" / "ja"
        lib_zh = upload_root / "library" / "strokes" / "zh"
        lib_zh_hant = upload_root / "library" / "strokes" / "zh_hant"

        ja_count = len(list(lib_ja.glob("*.svg"))) if lib_ja.exists() else 0
        zh_count = len(list(lib_zh.glob("*.svg"))) if lib_zh.exists() else 0
        zh_hant_count = len(list(lib_zh_hant.glob("*.svg"))) if lib_zh_hant.exists() else 0
        total_assets = SharedImageAsset.query.filter(SharedImageAsset.image_key.like("stroke_%")).count()

        click.echo("Stroke Dataset Status (Image Library):")
        click.echo(f"  - Japanese (ja): {ja_count} SVGs ({lib_ja})")
        click.echo(f"  - Chinese Simplified (zh): {zh_count} SVGs ({lib_zh})")
        click.echo(f"  - Chinese Traditional (zh-hant): {zh_hant_count} SVGs ({lib_zh_hant})")
        click.echo(f"  - Total Registered Image Library Stroke Assets: {total_assets}")

    @strokes_group.command("migrate-notes")
    @click.option("--dry-run", is_flag=True, help="Preview migrations without committing changes.")
    def migrate_notes_cmd(dry_run: bool) -> None:
        """Compatibility alias for the canonical typed media migration."""
        result = backfill_media_field_values(
            apply=not dry_run,
            include_overlays=True,
            include_templates=False,
        )
        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()
        click.echo(
            "Typed media migration complete. "
            f"run_id={result.run_id or '-'}, changed={result.changed}, "
            f"normalized={result.normalized}, cleared={result.cleared}, "
            f"quarantined={result.quarantined}, dry-run={dry_run}"
        )

    @app.cli.command("seed-production-strokes")
    @click.option("--locale", default="all", type=click.Choice(["all", "ja", "zh", "zh-hant"]), help="Language locale to pre-generate.")
    @click.option("--limit-ja", default=2500, type=int, help="Number of Japanese Kanji to generate (default: 2500).")
    @click.option("--limit-zh", default=9000, type=int, help="Number of Simplified Chinese Hanzi to generate (default: 9000).")
    @click.option("--limit-zh-hant", default=9000, type=int, help="Number of Traditional Chinese Hanzi to generate (default: 9000).")
    @click.option("--workers", default=4, type=int, help="Concurrent download threads (default: 4).")
    @click.option("--delay", default=0.0, type=float, help="Pacing delay in seconds per request (default: 0.0).")
    @click.option("--force", is_flag=True, help="Force regenerate existing SVG files.")
    def seed_production_strokes_command(locale: str, limit_ja: int, limit_zh: int, limit_zh_hant: int, workers: int, delay: float, force: bool):
        """Batch pre-generate 2,500+ Japanese Kanji & 9,000+ Chinese Hanzi for Production."""
        from app.services.strokes.production_seeder import seed_production_strokes_dataset
        import time

        click.echo("==========================================================")
        click.echo(" FLAMA PRODUCTION STROKE PRE-GENERATOR & SEEDER")
        click.echo("==========================================================")
        click.echo(f"  Locale target : {locale}")
        click.echo(f"  JA limit      : {limit_ja}")
        click.echo(f"  ZH limit      : {limit_zh}")
        click.echo(f"  ZH-HANT limit : {limit_zh_hant}")
        click.echo(f"  Concurrency   : {workers} workers (delay: {delay}s)")
        click.echo(f"  Force overwrite: {force}")
        click.echo("----------------------------------------------------------")

        start_time = time.time()

        def on_progress(p: dict):
            completed = p["completed"]
            total = p["total"]
            loc = p["locale"]
            if completed % 100 == 0 or completed == total:
                pct = (completed / total) * 100 if total else 100
                click.echo(f"[{loc.upper()}] Progress: {completed}/{total} ({pct:.1f}%) - U+{ord(p['char']):04X}")

        stats = seed_production_strokes_dataset(
            locales=(locale,) if locale != "all" else ("ja", "zh", "zh-hant"),
            limit_ja=limit_ja,
            limit_zh=limit_zh,
            limit_zh_hant=limit_zh_hant,
            workers=workers,
            delay=delay,
            force=force,
            progress_callback=on_progress,
        )

        elapsed = time.time() - start_time
        click.echo("----------------------------------------------------------")
        click.echo(" PRODUCTION STROKE SEEDING COMPLETED!")
        click.echo(f"  Total targets processed : {stats['total_targets']}")
        click.echo(f"  Newly Generated SVGs    : {stats['generated']}")
        click.echo(f"  Cached / Skipped        : {stats['cached']}")
        click.echo(f"  Failed / Fallback       : {stats['failed']}")
        click.echo(f"  Database Records Synced : {stats['db_updated']}")
        click.echo(f"  Elapsed Time            : {elapsed:.2f}s")
        click.echo("==========================================================")

    @app.cli.command("cleanup-wrong-strokes")
    @click.option("--dry-run", is_flag=True, help="Preview only, do not delete files.")
    def cleanup_wrong_strokes_command(dry_run: bool):
        """Remove incorrectly seeded stroke SVGs (S/T mix-up) from zh and zh-hant folders."""
        import json
        from pathlib import Path
        from app.services.strokes.stroke_service import _get_static_root, _get_upload_root
        from models.shared_image_asset import SharedImageAsset

        click.echo("==========================================================")
        click.echo(" FLAMA STROKE CLEANUP - Remove S/T Mix-up Files")
        click.echo(f"  Dry run: {dry_run}")
        click.echo("----------------------------------------------------------")

        seed_root = Path("static/seed_data/strokes")
        zh_file = seed_root / "zh_production_hanzi.json"
        zh_hant_file = seed_root / "zh_hant_production_hanzi.json"

        if not zh_file.exists() or not zh_hant_file.exists():
            click.echo("ERROR: Locale-specific JSON files not found.")
            return

        zh_chars = set(json.loads(zh_file.read_text(encoding="utf-8")))
        zh_hant_chars = set(json.loads(zh_hant_file.read_text(encoding="utf-8")))

        zh_valid_hexes = set()
        for ch in zh_chars:
            h = format(ord(ch), "x")
            zh_valid_hexes.add(h)
            zh_valid_hexes.add(h.zfill(5))

        zh_hant_valid_hexes = set()
        for ch in zh_hant_chars:
            h = format(ord(ch), "x")
            zh_hant_valid_hexes.add(h)
            zh_hant_valid_hexes.add(h.zfill(5))

        static_root = _get_static_root()
        upload_root = _get_upload_root()

        targets = [
            (static_root / "strokes" / "zh", zh_valid_hexes, "stroke_zh_"),
            (static_root / "strokes" / "zh-hant", zh_hant_valid_hexes, "stroke_zh_hant_"),
            (upload_root / "library" / "strokes" / "zh", zh_valid_hexes, "stroke_zh_"),
            (upload_root / "library" / "strokes" / "zh_hant", zh_hant_valid_hexes, "stroke_zh_hant_"),
        ]

        total_deleted = 0
        total_kept = 0
        db_keys_to_delete: list[str] = []

        for folder, valid_hexes, prefix in targets:
            if not folder.exists():
                continue
            svgs = list(folder.glob("*.svg"))
            deleted = 0
            kept = 0
            for svg_path in svgs:
                stem = svg_path.stem.lower()
                if stem not in valid_hexes:
                    if dry_run:
                        click.echo(f"  [DRY] Would delete: {svg_path}")
                    else:
                        svg_path.unlink()
                    deleted += 1
                    hex_clean = stem.lstrip("0") or stem
                    db_keys_to_delete.append(f"{prefix}{hex_clean}")
                else:
                    kept += 1
            if deleted > 0 or kept > 0:
                action = "would delete" if dry_run else "deleted"
                click.echo(f"  {folder}: kept={kept}, {action}={deleted}")
            total_deleted += deleted
            total_kept += kept

        db_cleaned = 0
        if db_keys_to_delete and not dry_run:
            unique_keys = list(set(db_keys_to_delete))
            for i in range(0, len(unique_keys), 100):
                chunk = unique_keys[i:i + 100]
                assets = SharedImageAsset.query.filter(
                    SharedImageAsset.image_key.in_(chunk)
                ).all()
                for asset in assets:
                    db.session.delete(asset)
                    db_cleaned += 1
            try:
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                click.echo(f"  DB cleanup error: {exc}")

        click.echo("----------------------------------------------------------")
        click.echo(f"  Files kept     : {total_kept}")
        action = "to delete" if dry_run else "deleted"
        click.echo(f"  Files {action} : {total_deleted}")
        if not dry_run:
            click.echo(f"  DB records removed: {db_cleaned}")
        click.echo("==========================================================")


# Re-exports from seeding_service for backward compatibility
from app.services.seeding_service import (
    SeedStats,
    _resolve_seed_data_owner,
    _seed_vocabulary_data,
    _find_seed_data_gaps,
    _resolve_seed_path,
    _resolve_seed_root,
    _normalize_header,
    _natural_sort_key,
    _next_deck_position,
    _get_or_create_deck,
    _seed_dir_to_deck,
    _seed_file_to_leaf_deck,
    _seed_rows_to_deck,
    _get_or_create_seed_deck_path,
    _count_entries_in_deck_subtree,
    _upsert_seeded_deck_marketplace_item,
    _build_header_mapping,
    _default_seed_delimiter,
    _clean_seed_cell,
    _looks_like_seed_header_row,
    _load_seed_rows_from_header_rows,
    _parse_anki_column_indexes,
    _strip_anki_metadata_columns,
    _select_seed_positional_fields,
    _load_seed_rows_from_positional_rows,
    _load_seed_rows,
    _split_anki_deck_path,
    _common_anki_parent_prefix,
    _group_rows_by_anki_deck,
    _seed_row_to_field_values,
    _resolve_quiz_dump_paths,
    _normalize_quiz_correct_answer,
    _load_quiz_dump_rows,
    _seed_quiz_dump_for_user,
)
