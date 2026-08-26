"""CLI commands for data seeding and maintenance."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
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


def register_cli_commands(app: Flask) -> None:
    """Register custom Flask CLI commands."""

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

    @app.cli.command("study-architecture-audit")
    @click.option(
        "--compact",
        is_flag=True,
        default=False,
        help="Emit compact JSON instead of indented JSON.",
    )
    def study_architecture_audit(compact: bool) -> None:
        """Print read-only reconciliation gates for the study refactor."""
        from app.services.study_architecture_audit_service import (
            build_study_architecture_audit,
        )

        report = build_study_architecture_audit()
        click.echo(
            json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                indent=None if compact else 2,
            )
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



def _resolve_seed_data_owner(bootstrap_user: User) -> User:
    official_items = (
        DeckMarketplaceItem.query.filter(
            DeckMarketplaceItem.is_official.is_(True),
            DeckMarketplaceItem.owner_user_id.is_not(None),
        )
        .order_by(
            DeckMarketplaceItem.created_at.asc(),
            DeckMarketplaceItem.id.asc(),
        )
        .all()
    )
    seeded_item = next(
        (
            item
            for item in official_items
            if "seeded" in {str(tag).strip().lower() for tag in (item.tags or [])}
        ),
        None,
    )
    if seeded_item is not None:
        existing_owner = db.session.get(User, seeded_item.owner_user_id)
        if existing_owner is not None:
            return existing_owner

    return bootstrap_user


def _seed_vocabulary_data(
    *,
    seed_path: str,
    replace_lessons: bool,
    owner_user_id: int | None,
    share_seeded_decks: bool,
) -> SeedStats:
    root_input = _resolve_seed_path(seed_path)
    root = _resolve_seed_root(root_input)
    if not root.exists() or not root.is_dir():
        raise click.ClickException(f"Seed path not found: {root}")

    stats = SeedStats()
    start_dirs = sorted((p for p in root.iterdir() if p.is_dir()), key=_natural_sort_key)
    root_seed_files = sorted(
        (
            p
            for p in root.iterdir()
            if p.is_file() and p.suffix.lower() in SEED_SUPPORTED_SUFFIXES
        ),
        key=_natural_sort_key,
    )
    if not start_dirs and not root_seed_files:
        click.echo(f"No subfolders or seed files found in {root}. Nothing to seed.")
        return stats

    target_user = (
        db.session.get(User, owner_user_id)
        if owner_user_id
        else User.query.order_by(User.id.asc()).first()
    )
    if target_user is None:
        raise click.ClickException(
            "No user found. Create at least one user before running vocab-seed."
        )

    note_type, template = ensure_legacy_note_type(db.session, target_user.id)
    quiz_note_type, quiz_template = ensure_quiz_note_type(db.session, target_user.id)
    click.echo(f"Seeding from: {root}")
    click.echo(
        f"Using owner_user_id={target_user.id}, "
        f"note_type={note_type.id}, template={template.id}"
    )
    click.echo(
        f"Also ensured quiz_note_type={quiz_note_type.id}, "
        f"template={quiz_template.id}"
    )
    top_level_seed_dirs = list(start_dirs)
    if not top_level_seed_dirs and root_seed_files:
        top_level_seed_dirs = [root]

    for start_dir in top_level_seed_dirs:
        top_deck = _seed_dir_to_deck(
            directory=start_dir,
            parent_deck_id=None,
            owner_user_id=target_user.id,
            note_type_id=note_type.id,
            template_id=template.id,
            replace_existing=replace_lessons,
            stats=stats,
        )
        if share_seeded_decks:
            subtree_entries = _count_entries_in_deck_subtree(top_deck.id)
            shared_created = _upsert_seeded_deck_marketplace_item(
                deck=top_deck,
                owner_user_id=target_user.id,
                note_type_id=note_type.id,
                sample_cards_count=min(max(subtree_entries, 0), 20),
            )
            stats.shared_decks += 1
            action = "Created" if shared_created else "Updated"
            click.echo(f"{action} shared top-level deck item: {top_deck.name}")

    quiz_deck, quiz_note_count = _seed_quiz_dump_for_user(
        owner_user_id=target_user.id,
        note_type_id=quiz_note_type.id,
        template_id=quiz_template.id,
        replace_existing=replace_lessons,
        stats=stats,
    )
    if quiz_deck is not None:
        click.echo(
            f"Seeded quiz dump deck: {quiz_deck.name} ({quiz_note_count} notes)"
        )

    db.session.commit()
    click.echo(
        "Done. "
        f"decks+{stats.created_decks}, files_seeded={stats.seeded_files}, "
        f"notes+{stats.created_notes}, cards+{stats.created_cards}, "
        f"replaced_files={stats.replaced_files}, "
        f"skipped_files={stats.skipped_files}, "
        f"shared_decks={stats.shared_decks}"
    )
    return stats


def _find_seed_data_gaps(
    *,
    root: Path,
    owner_user_id: int,
    share_seeded_decks: bool,
) -> list[str]:
    """Return missing production seed components without parsing large dumps."""
    if not root.exists() or not root.is_dir():
        return [f"seed path not found: {root}"]

    start_dirs = sorted((path for path in root.iterdir() if path.is_dir()), key=_natural_sort_key)
    root_seed_files = sorted(
        (
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in SEED_SUPPORTED_SUFFIXES
        ),
        key=_natural_sort_key,
    )
    top_level_seed_dirs = list(start_dirs)
    if not top_level_seed_dirs and root_seed_files:
        top_level_seed_dirs = [root]
    if not top_level_seed_dirs:
        return [f"no seed bundles found in {root}"]

    gaps: list[str] = []
    legacy_note_type = (
        NoteType.query.filter_by(
            user_id=owner_user_id,
            name=LEGACY_NOTE_TYPE_NAME,
        )
        .order_by(NoteType.created_at.asc(), NoteType.id.asc())
        .first()
    )
    if legacy_note_type is None:
        gaps.append(f"note type missing: {LEGACY_NOTE_TYPE_NAME}")
    elif (
        Template.query.filter_by(note_type_id=legacy_note_type.id)
        .order_by(Template.position.asc(), Template.created_at.asc())
        .first()
        is None
    ):
        gaps.append(f"template missing for note type: {LEGACY_NOTE_TYPE_NAME}")

    for directory in top_level_seed_dirs:
        deck = (
            Deck.query.filter(
                Deck.owner_user_id == owner_user_id,
                Deck.parent_id.is_(None),
                Deck.name == directory.name,
                Deck.deleted_at.is_(None),
            )
            .order_by(Deck.id.asc())
            .first()
        )
        if deck is None:
            gaps.append(f"seed bundle missing: {directory.name}")
            continue
        if _count_entries_in_deck_subtree(deck.id) <= 0:
            gaps.append(f"seed bundle has no notes: {directory.name}")

        if share_seeded_decks:
            listing = (
                DeckMarketplaceItem.query.filter(
                    DeckMarketplaceItem.owner_user_id == owner_user_id,
                    DeckMarketplaceItem.source_deck_id == deck.id,
                    DeckMarketplaceItem.publish_status == "published",
                    DeckMarketplaceItem.archived_at.is_(None),
                )
                .order_by(
                    DeckMarketplaceItem.created_at.asc(),
                    DeckMarketplaceItem.id.asc(),
                )
                .first()
            )
            if listing is None:
                gaps.append(f"shared listing missing: {directory.name}")

    for source_file in sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in SEED_SUPPORTED_SUFFIXES
        ),
        key=_natural_sort_key,
    ):
        source_decks = (
            Deck.query.filter(
                Deck.owner_user_id == owner_user_id,
                Deck.description == f"Seeded from {source_file.name}",
                Deck.deleted_at.is_(None),
            )
            .order_by(Deck.id.asc())
            .all()
        )
        source_deck_ids = [deck.id for deck in source_decks]
        seeded_note_count = 0
        if source_deck_ids:
            seeded_note_count = int(
                db.session.query(db.func.count(Note.id))
                .filter(
                    Note.user_id == owner_user_id,
                    Note.deck_id.in_(source_deck_ids),
                )
                .scalar()
                or 0
            )
        if seeded_note_count <= 0:
            gaps.append(
                f"seed source missing: {source_file.relative_to(root).as_posix()}"
            )

    dump_root, manifest_path = _resolve_quiz_dump_paths()
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            gaps.append(f"quiz manifest invalid: {manifest_path}")
            return gaps

        quiz_note_type = (
            NoteType.query.filter_by(
                user_id=owner_user_id,
                name=QUIZ_NOTE_TYPE_NAME,
            )
            .order_by(NoteType.created_at.asc(), NoteType.id.asc())
            .first()
        )
        if quiz_note_type is None:
            gaps.append(f"note type missing: {QUIZ_NOTE_TYPE_NAME}")
        elif (
            Template.query.filter_by(note_type_id=quiz_note_type.id)
            .order_by(Template.position.asc(), Template.created_at.asc())
            .first()
            is None
        ):
            gaps.append(f"template missing for note type: {QUIZ_NOTE_TYPE_NAME}")

        quiz_deck_name = (
            str(manifest.get("deck_name") or "Trac Nghiem Co Ban").strip()
            or "Trac Nghiem Co Ban"
        )
        quiz_deck = (
            Deck.query.filter(
                Deck.owner_user_id == owner_user_id,
                Deck.parent_id.is_(None),
                Deck.name == quiz_deck_name,
                Deck.deleted_at.is_(None),
            )
            .order_by(Deck.id.asc())
            .first()
        )
        if quiz_deck is None:
            gaps.append(f"quiz seed deck missing: {quiz_deck_name}")
        elif quiz_note_type is not None:
            quiz_notes = int(
                db.session.query(db.func.count(Note.id))
                .filter(
                    Note.user_id == owner_user_id,
                    Note.note_type_id == quiz_note_type.id,
                    Note.deck_id == quiz_deck.id,
                )
                .scalar()
                or 0
            )
            if quiz_notes <= 0:
                gaps.append(f"quiz seed deck has no notes: {quiz_deck_name}")

        dump_filename = (
            str(manifest.get("file") or QUIZ_DUMP_DEFAULT_FILE).strip()
            or QUIZ_DUMP_DEFAULT_FILE
        )
        if not (dump_root / dump_filename).is_file():
            gaps.append(f"quiz dump file missing: {dump_root / dump_filename}")

    return gaps


def _resolve_seed_path(seed_path: str) -> Path:
    candidate = Path(seed_path)
    if candidate.is_absolute():
        return candidate
    return Path(__file__).resolve().parent.parent / candidate


def _resolve_seed_root(root_input: Path) -> Path:
    # If user passes project/static, auto jump into static/seed_data.
    if root_input.name.lower() == "static":
        seed_data = root_input / "seed_data"
        if seed_data.exists():
            return seed_data
    # If user passes project root and it has static/seed_data.
    seed_data_under_root = root_input / "static" / "seed_data"
    if seed_data_under_root.exists():
        return seed_data_under_root
    # Default: use input directly (often already static/seed_data).
    return root_input


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_") if value else ""


def _natural_sort_key(path_obj: Path) -> List[tuple[int, object]]:
    text = path_obj.name.lower()
    key: List[tuple[int, object]] = []
    for part in re.split(r"(\d+)", text):
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return key


def _next_deck_position(parent_deck_id: int | None) -> int:
    query = db.session.query(db.func.max(Deck.position))
    if parent_deck_id is None:
        max_pos = query.filter(Deck.parent_id.is_(None)).scalar()
    else:
        max_pos = query.filter(Deck.parent_id == parent_deck_id).scalar()
    return (max_pos or 0) + 1


def _get_or_create_deck(
    *,
    parent_deck_id: int | None,
    owner_user_id: int,
    name: str,
    description: str | None,
    stats: SeedStats,
) -> tuple[Deck, bool]:
    deck = (
        Deck.query.filter(
            Deck.parent_id == parent_deck_id,
            Deck.name == name,
            Deck.owner_user_id == owner_user_id,
        )
        .order_by(Deck.id.asc())
        .first()
    )
    if deck is None:
        deck = (
            Deck.query.filter(
                Deck.parent_id == parent_deck_id,
                Deck.name == name,
                Deck.owner_user_id.is_(None),
            )
            .order_by(Deck.id.asc())
            .first()
        )
    if deck:
        if deck.owner_user_id is None:
            deck.owner_user_id = owner_user_id
        deck.deleted_at = None
        return deck, False

    deck = Deck(
        parent_id=parent_deck_id,
        owner_user_id=owner_user_id,
        name=name,
        description=description,
        position=_next_deck_position(parent_deck_id),
    )
    db.session.add(deck)
    db.session.flush()
    stats.created_decks += 1
    return deck, True


def _seed_dir_to_deck(
    *,
    directory: Path,
    parent_deck_id: int | None,
    owner_user_id: int,
    note_type_id: str,
    template_id: str,
    replace_existing: bool,
    stats: SeedStats,
) -> Deck:
    deck_name = directory.name.strip()
    if not deck_name:
        return

    deck_node, created = _get_or_create_deck(
        parent_deck_id=parent_deck_id,
        owner_user_id=owner_user_id,
        name=deck_name,
        description=None,
        stats=stats,
    )
    if created:
        click.echo(f"Created deck: {deck_node.name}")
    else:
        click.echo(f"Using deck: {deck_node.name}")

    # Files in a folder become leaf decks under this folder deck.
    seed_files = sorted(
        (
            p
            for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in SEED_SUPPORTED_SUFFIXES
        ),
        key=_natural_sort_key,
    )
    for seed_file in seed_files:
        _seed_file_to_leaf_deck(
            file_path=seed_file,
            parent_deck_id=deck_node.id,
            owner_user_id=owner_user_id,
            note_type_id=note_type_id,
            template_id=template_id,
            replace_existing=replace_existing,
            stats=stats,
        )

    # Recurse subfolders for nested deck hierarchy.
    subdirs = sorted((p for p in directory.iterdir() if p.is_dir()), key=_natural_sort_key)
    for child_dir in subdirs:
        _seed_dir_to_deck(
            directory=child_dir,
            parent_deck_id=deck_node.id,
            owner_user_id=owner_user_id,
            note_type_id=note_type_id,
            template_id=template_id,
            replace_existing=replace_existing,
            stats=stats,
        )
    return deck_node


def _seed_file_to_leaf_deck(
    *,
    file_path: Path,
    parent_deck_id: int,
    owner_user_id: int,
    note_type_id: str,
    template_id: str,
    replace_existing: bool,
    stats: SeedStats,
) -> None:
    rows = _load_seed_rows(file_path)
    if not rows:
        stats.skipped_files += 1
        click.echo(f"  Skip empty file: {file_path.name}")
        return

    anki_deck_groups = _group_rows_by_anki_deck(rows, file_path)
    if not anki_deck_groups:
        leaf_name = file_path.stem.strip() or file_path.name
        leaf_deck, created = _get_or_create_deck(
            parent_deck_id=parent_deck_id,
            owner_user_id=owner_user_id,
            name=leaf_name,
            description=f"Seeded from {file_path.name}",
            stats=stats,
        )
        status = _seed_rows_to_deck(
            rows=rows,
            deck=leaf_deck,
            owner_user_id=owner_user_id,
            note_type_id=note_type_id,
            template_id=template_id,
            replace_existing=replace_existing,
            source_label=file_path.name,
            stats=stats,
        )
        if status == "skipped":
            stats.skipped_files += 1
            return
        if status == "replaced":
            stats.replaced_files += 1
        stats.seeded_files += 1
        deck_state = "Created" if created else "Updated"
        click.echo(f"  {deck_state} leaf deck: {leaf_name} ({len(rows)} rows)")
        return

    seeded_groups = 0
    replaced_groups = 0
    for deck_path, deck_rows in anki_deck_groups:
        leaf_deck, created = _get_or_create_seed_deck_path(
            parent_deck_id=parent_deck_id,
            owner_user_id=owner_user_id,
            path_parts=deck_path,
            source_file=file_path,
            stats=stats,
        )
        status = _seed_rows_to_deck(
            rows=deck_rows,
            deck=leaf_deck,
            owner_user_id=owner_user_id,
            note_type_id=note_type_id,
            template_id=template_id,
            replace_existing=replace_existing,
            source_label=f"{file_path.name}::{'::'.join(deck_path)}",
            stats=stats,
        )
        if status == "skipped":
            continue
        seeded_groups += 1
        if status == "replaced":
            replaced_groups += 1
        deck_state = "Created" if created else "Updated"
        click.echo(
            f"  {deck_state} Anki deck: {'::'.join(deck_path)} ({len(deck_rows)} rows)"
        )

    if seeded_groups:
        stats.seeded_files += 1
        if replaced_groups:
            stats.replaced_files += 1
        click.echo(
            f"  Split Anki export: {file_path.name} -> {len(anki_deck_groups)} deck(s)"
        )
    else:
        stats.skipped_files += 1


def _seed_rows_to_deck(
    *,
    rows: List[Dict[str, str | None]],
    deck: Deck,
    owner_user_id: int,
    note_type_id: str,
    template_id: str,
    replace_existing: bool,
    source_label: str,
    stats: SeedStats,
) -> str:
    existing_count = (
        db.session.query(db.func.count(Note.id))
        .filter(
            Note.deck_id == deck.id,
            Note.user_id == owner_user_id,
            Note.note_type_id == note_type_id,
        )
        .scalar()
        or 0
    )
    if existing_count and not replace_existing:
        click.echo(f"  Skip deck (already seeded): {source_label}")
        return "skipped"
    if existing_count and replace_existing:
        existing_notes = (
            Note.query.filter(
                Note.deck_id == deck.id,
                Note.user_id == owner_user_id,
                Note.note_type_id == note_type_id,
            )
            .all()
        )
        existing_note_ids = [note.id for note in existing_notes]
        existing_card_ids: list[str] = []
        if existing_note_ids:
            existing_card_ids = [
                row[0]
                for row in db.session.query(Card.id)
                .filter(Card.note_id.in_(existing_note_ids))
                .all()
                if row and row[0]
            ]
        if existing_card_ids:
            CardProgress.query.filter(
                CardProgress.card_id.in_(existing_card_ids)
            ).delete(synchronize_session=False)
        if existing_note_ids:
            Card.query.filter(Card.note_id.in_(existing_note_ids)).delete(synchronize_session=False)
            Note.query.filter(Note.id.in_(existing_note_ids)).delete(synchronize_session=False)
        click.echo(f"  Replace seeded deck: {source_label}")

    notes: list[Note] = []
    for row in rows:
        notes.append(
            Note(
                note_type_id=note_type_id,
                user_id=owner_user_id,
                deck_id=deck.id,
                field_values=_seed_row_to_field_values(row),
                tags=[],
            )
        )
    db.session.add_all(notes)
    db.session.flush()

    cards: list[Card] = []
    for note in notes:
        cards.append(
            Card(
                note_id=note.id,
                template_id=template_id,
            )
        )
    db.session.add_all(cards)
    db.session.flush()

    stats.created_notes += len(notes)
    stats.created_cards += len(cards)
    return "replaced" if existing_count else "seeded"


def _get_or_create_seed_deck_path(
    *,
    parent_deck_id: int,
    owner_user_id: int,
    path_parts: tuple[str, ...],
    source_file: Path,
    stats: SeedStats,
) -> tuple[Deck, bool]:
    current_parent_id = parent_deck_id
    leaf_deck: Deck | None = None
    leaf_created = False
    for index, part in enumerate(path_parts):
        is_leaf = index == len(path_parts) - 1
        leaf_deck, created = _get_or_create_deck(
            parent_deck_id=current_parent_id,
            owner_user_id=owner_user_id,
            name=part,
            description=f"Seeded from {source_file.name}" if is_leaf else None,
            stats=stats,
        )
        current_parent_id = leaf_deck.id
        if is_leaf:
            leaf_created = created
    if leaf_deck is None:
        raise click.ClickException(f"Anki deck path is empty in {source_file}")
    return leaf_deck, leaf_created


def _count_entries_in_deck_subtree(deck_id: int) -> int:
    total = 0
    stack = [deck_id]
    while stack:
        current = stack.pop()
        total += (
            db.session.query(db.func.count(Note.id))
            .filter(Note.deck_id == current)
            .scalar()
            or 0
        )
        child_ids = [
            row[0]
            for row in db.session.query(Deck.id)
            .filter(Deck.parent_id == current)
            .all()
        ]
        stack.extend(child_ids)
    return int(total)


def _upsert_seeded_deck_marketplace_item(
    *,
    deck: Deck,
    owner_user_id: int,
    note_type_id: str,
    sample_cards_count: int,
) -> bool:
    same_title_seeded_items = [
        item
        for item in (
            DeckMarketplaceItem.query.filter_by(
                owner_user_id=owner_user_id,
                title=deck.name,
            )
            .order_by(DeckMarketplaceItem.created_at.asc(), DeckMarketplaceItem.id.asc())
            .all()
        )
        if item.is_official and "seeded" in {str(tag).strip().lower() for tag in (item.tags or [])}
    ]
    deck_item = next(
        (
            item
            for item in same_title_seeded_items
            if item.source_deck_id == deck.id
        ),
        None,
    )
    if deck_item is None:
        deck_item = same_title_seeded_items[0] if same_title_seeded_items else None
    if deck_item:
        now = datetime.utcnow()
        for duplicate in same_title_seeded_items:
            if duplicate.id == deck_item.id:
                continue
            # Preserve historical installs/reviews while removing stale seed
            # listings from active marketplace and owner-library surfaces.
            duplicate.publish_status = "archived"
            duplicate.archived_at = duplicate.archived_at or now
            duplicate.is_official = False

        deck_item.source_deck_id = deck.id
        if not deck_item.title:
            deck_item.title = deck.name
        if not deck_item.description:
            deck_item.description = deck.description or f"Seeded deck: {deck.name}"
        deck_item.source_note_type_id = note_type_id
        deck_item.primary_category = deck_item.primary_category or "Japanese"
        deck_item.tags = deck_item.tags or ["seeded", "default"]
        deck_item.preview_text = deck_item.preview_text or f"Default seeded deck: {deck.name}"
        deck_item.sample_cards_count = max(int(deck_item.sample_cards_count or 0), sample_cards_count)
        deck_item.pricing_mode = "free"
        deck_item.price_amount_minor = 0
        deck_item.publish_status = "published"
        deck_item.is_official = True
        deck_item.published_at = deck_item.published_at or now
        deck_item.archived_at = None
        db.session.flush()
        release_error = flashcards_share_service._stage_initial_release_if_visible(deck_item)
        if release_error:
            raise click.ClickException(
                f"Could not publish initial release for seeded deck '{deck.name}': {release_error}"
            )
        return False

    new_item = DeckMarketplaceItem(
        owner_user_id=owner_user_id,
        source_deck_id=deck.id,
        source_note_type_id=note_type_id,
        title=deck.name,
        description=deck.description or f"Seeded deck: {deck.name}",
        primary_category="Japanese",
        tags=["seeded", "default"],
        preview_text=f"Default seeded deck: {deck.name}",
        sample_cards_count=sample_cards_count,
        pricing_mode="free",
        price_amount_minor=0,
        version="1.0.0",
        publish_status="published",
        is_official=True,
        published_at=datetime.utcnow(),
    )
    db.session.add(new_item)
    db.session.flush()
    release_error = flashcards_share_service._stage_initial_release_if_visible(new_item)
    if release_error:
        raise click.ClickException(
            f"Could not publish initial release for seeded deck '{deck.name}': {release_error}"
        )
    return True


def _build_header_mapping(fieldnames: Iterable[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for original in fieldnames:
        normalized = _normalize_header(original)
        if normalized in SEED_REQUIRED_FIELDS or normalized in SEED_OPTIONAL_FIELDS:
            mapping[normalized] = original
    missing = [field for field in SEED_REQUIRED_FIELDS if field not in mapping]
    if missing:
        raise click.ClickException(f"Missing required columns: {', '.join(missing)}")
    return mapping


def _default_seed_delimiter(file_path: Path) -> str:
    return "\t" if file_path.suffix.lower() in {".tsv", ".txt"} else ","


def _clean_seed_cell(value: str | None) -> str | None:
    cleaned = (value or "").replace("\r", "").strip()
    return cleaned or None


def _looks_like_seed_header_row(row: list[str]) -> bool:
    normalized = {_normalize_header(value) for value in row if _normalize_header(value)}
    return all(field in normalized for field in SEED_REQUIRED_FIELDS)


def _load_seed_rows_from_header_rows(rows: List[List[str]]) -> List[Dict[str, str | None]]:
    headers = rows[0]
    mapping = _build_header_mapping(headers)
    items: List[Dict[str, str | None]] = []

    for row_values in rows[1:]:
        raw = {
            headers[index]: row_values[index] if index < len(row_values) else ""
            for index in range(len(headers))
        }
        deck = _clean_seed_cell(raw.get(mapping["deck"]))
        word = _clean_seed_cell(raw.get(mapping["word"]))
        if not deck or not word:
            continue

        payload: Dict[str, str | None] = {"deck": deck, "word": word}
        for field in SEED_OPTIONAL_FIELDS:
            source_key = mapping.get(field)
            payload[field] = _clean_seed_cell(raw.get(source_key) if source_key else None)
        items.append(payload)

    return items


def _parse_anki_column_indexes(
    directives: Dict[str, str],
    file_path: Path,
) -> Dict[str, int]:
    indexes: Dict[str, int] = {}
    for directive in SEED_ANKI_METADATA_COLUMN_DIRECTIVES:
        raw_value = directives.get(directive)
        if raw_value is None:
            continue
        try:
            one_based_index = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise click.ClickException(
                f"Invalid Anki directive #{directive}:{raw_value} in {file_path}: "
                "column must be a positive integer."
            ) from exc
        if one_based_index < 1:
            raise click.ClickException(
                f"Invalid Anki directive #{directive}:{raw_value} in {file_path}: "
                "column numbering starts at 1."
            )
        indexes[directive] = one_based_index - 1
    return indexes


def _strip_anki_metadata_columns(
    row_values: List[str],
    *,
    column_indexes: Dict[str, int],
    file_path: Path,
    row_index: int,
) -> tuple[List[str], str | None]:
    for directive, column_index in column_indexes.items():
        if column_index >= len(row_values):
            raise click.ClickException(
                f"Invalid Anki row in {file_path} at data row {row_index}: "
                f"#{directive} points to column {column_index + 1}, "
                f"but the row has only {len(row_values)} columns."
            )

    deck_column_index = column_indexes.get("deck column")
    anki_deck_path = (
        _clean_seed_cell(row_values[deck_column_index])
        if deck_column_index is not None
        else None
    )
    metadata_indexes = set(column_indexes.values())
    field_values = [
        value for index, value in enumerate(row_values) if index not in metadata_indexes
    ]
    return field_values, anki_deck_path


def _select_seed_positional_fields(
    *,
    field_count: int,
    has_anki_deck_column: bool,
    file_path: Path,
    row_index: int,
) -> tuple[str, ...]:
    if field_count == len(SEED_FULL_POSITIONAL_FIELDS):
        return SEED_FULL_POSITIONAL_FIELDS
    if has_anki_deck_column and field_count == len(SEED_FULL_POSITIONAL_FIELDS_WITHOUT_DECK):
        return SEED_FULL_POSITIONAL_FIELDS_WITHOUT_DECK
    if field_count == len(SEED_LEGACY_POSITIONAL_FIELDS):
        return SEED_LEGACY_POSITIONAL_FIELDS
    if field_count == len(SEED_FULL_POSITIONAL_FIELDS) + 1:
        return SEED_FULL_POSITIONAL_FIELDS
    if not has_anki_deck_column and field_count == len(SEED_LEGACY_POSITIONAL_FIELDS) + 1:
        return SEED_LEGACY_POSITIONAL_FIELDS

    expected_counts = {
        len(SEED_LEGACY_POSITIONAL_FIELDS),
        len(SEED_LEGACY_POSITIONAL_FIELDS) + 1,
        len(SEED_FULL_POSITIONAL_FIELDS),
        len(SEED_FULL_POSITIONAL_FIELDS) + 1,
    }
    if has_anki_deck_column:
        expected_counts.add(len(SEED_FULL_POSITIONAL_FIELDS_WITHOUT_DECK))
    expected_label = ", ".join(str(value) for value in sorted(expected_counts))
    raise click.ClickException(
        f"Unsupported Anki seed row in {file_path} at data row {row_index}: "
        f"found {field_count} note-field columns after removing Anki metadata; "
        f"expected {expected_label}."
    )


def _load_seed_rows_from_positional_rows(
    rows: List[List[str]],
    file_path: Path,
    directives: Dict[str, str],
) -> List[Dict[str, str | None]]:
    column_indexes = _parse_anki_column_indexes(directives, file_path)
    has_anki_deck_column = "deck column" in column_indexes
    items: List[Dict[str, str | None]] = []

    for row_index, row_values in enumerate(rows, start=1):
        note_field_values, anki_deck_path = _strip_anki_metadata_columns(
            row_values,
            column_indexes=column_indexes,
            file_path=file_path,
            row_index=row_index,
        )
        positional_fields = _select_seed_positional_fields(
            field_count=len(note_field_values),
            has_anki_deck_column=has_anki_deck_column,
            file_path=file_path,
            row_index=row_index,
        )

        payload: Dict[str, str | None] = {
            field_name: _clean_seed_cell(note_field_values[index])
            for index, field_name in enumerate(positional_fields)
        }
        deck = payload.get("deck") or anki_deck_path
        word = payload.get("word")
        if not deck or not word:
            continue

        normalized_payload: Dict[str, str | None] = {"deck": deck, "word": word}
        for field in SEED_OPTIONAL_FIELDS:
            normalized_payload[field] = payload.get(field)
        if anki_deck_path:
            normalized_payload[SEED_ANKI_DECK_PATH_KEY] = anki_deck_path
        items.append(normalized_payload)

    return items


def _load_seed_rows(file_path: Path) -> List[Dict[str, str | None]]:
    try:
        raw_rows, metadata = read_delimited_rows(
            file_bytes=file_path.read_bytes(),
            delimiter=_default_seed_delimiter(file_path),
        )
    except OSError as exc:
        raise click.ClickException(f"Failed to read seed file {file_path}: {exc}") from exc
    except ImportValidationError as exc:
        raise click.ClickException(f"Failed to parse seed file {file_path}: {exc}") from exc

    if not raw_rows:
        return []
    if _looks_like_seed_header_row(raw_rows[0]):
        return _load_seed_rows_from_header_rows(raw_rows)
    directives = {
        str(key): str(value)
        for key, value in dict(metadata.get("preamble_directives") or {}).items()
    }
    return _load_seed_rows_from_positional_rows(raw_rows, file_path, directives)


def _split_anki_deck_path(raw_path: str, file_path: Path) -> tuple[str, ...]:
    parts = tuple(part.strip() for part in raw_path.split("::") if part.strip())
    if not parts:
        raise click.ClickException(f"Anki deck path is empty in {file_path}")
    return parts


def _common_anki_parent_prefix(paths: List[tuple[str, ...]]) -> tuple[str, ...]:
    if not paths:
        return ()
    parent_paths = [path[:-1] for path in paths]
    common: list[str] = []
    for parts_at_depth in zip(*parent_paths):
        if len(set(parts_at_depth)) != 1:
            break
        common.append(parts_at_depth[0])
    return tuple(common)


def _group_rows_by_anki_deck(
    rows: List[Dict[str, str | None]],
    file_path: Path,
) -> List[tuple[tuple[str, ...], List[Dict[str, str | None]]]]:
    routed_rows = [row for row in rows if row.get(SEED_ANKI_DECK_PATH_KEY)]
    if not routed_rows:
        return []
    if len(routed_rows) != len(rows):
        raise click.ClickException(
            f"Anki export {file_path} mixes rows with and without a deck path."
        )

    grouped_by_full_path: Dict[tuple[str, ...], List[Dict[str, str | None]]] = {}
    for row in rows:
        raw_path = str(row.get(SEED_ANKI_DECK_PATH_KEY) or "")
        full_path = _split_anki_deck_path(raw_path, file_path)
        grouped_by_full_path.setdefault(full_path, []).append(row)

    full_paths = list(grouped_by_full_path)
    common_parent = _common_anki_parent_prefix(full_paths)
    groups: List[tuple[tuple[str, ...], List[Dict[str, str | None]]]] = []
    for full_path in sorted(full_paths, key=lambda path: _natural_sort_key(Path("::".join(path)))):
        relative_path = full_path[len(common_parent):] or full_path[-1:]
        groups.append((relative_path, grouped_by_full_path[full_path]))
    return groups


def _seed_row_to_field_values(row: Dict[str, str | None]) -> Dict[str, str | None]:
    """Map seed CSV row columns into default Flama note field_values JSON."""
    return {
        "word": row.get("word") or "",
        "hanviet": row.get("hanviet"),
        "reading": row.get("reading"),
        "translation_vi": row.get("translation_vi"),
        "meaning_jp": row.get("meaning_jp"),
        "meaning_vi": row.get("meaning_vi"),
        "usage_jp": row.get("usage_jp"),
        "usage_vi": row.get("usage_vi"),
        "example_jp": row.get("example_jp"),
        "example_vi": row.get("example_vi"),
        "additional_note_jp": row.get("additional_note_jp"),
        "additional_note_vi": row.get("additional_note_vi"),
        "image": row.get("image"),
        "diagram": row.get("diagram"),
        "word_audio": row.get("word_audio"),
        "example_audio": row.get("example_audio"),
    }


def _resolve_quiz_dump_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parent.parent / QUIZ_DUMP_DIR
    return root, root / QUIZ_DUMP_MANIFEST


def _normalize_quiz_correct_answer(raw_value: str | None) -> str:
    candidate = str(raw_value or "").strip()
    if candidate in {"1", "2", "3", "4"}:
        return candidate
    try:
        parsed = int(candidate)
    except (TypeError, ValueError):
        return "1"
    return str(parsed) if 1 <= parsed <= 4 else "1"


def _load_quiz_dump_rows(tsv_path: Path) -> list[dict[str, str]]:
    with tsv_path.open("r", encoding="utf-8-sig", newline="") as infile:
        reader = csv.DictReader(infile, delimiter="\t")
        if not reader.fieldnames:
            raise click.ClickException(f"Missing header row in quiz dump: {tsv_path}")

        normalized_columns = {_normalize_header(name): name for name in reader.fieldnames if name}
        missing_columns = [name for name in QUIZ_DUMP_REQUIRED_COLUMNS if name not in normalized_columns]
        if missing_columns:
            raise click.ClickException(
                "Quiz dump is missing required columns: " + ", ".join(missing_columns)
            )

        rows: list[dict[str, str]] = []
        for raw in reader:
            if not raw:
                continue
            question = str(raw.get(normalized_columns["question"]) or "").strip()
            if not question:
                continue
            rows.append(
                {
                    "question": question,
                    "answer_1": str(raw.get(normalized_columns["answer_1"]) or "").strip(),
                    "answer_2": str(raw.get(normalized_columns["answer_2"]) or "").strip(),
                    "answer_3": str(raw.get(normalized_columns["answer_3"]) or "").strip(),
                    "answer_4": str(raw.get(normalized_columns["answer_4"]) or "").strip(),
                    "correct_answer": _normalize_quiz_correct_answer(
                        str(raw.get(normalized_columns["correct_answer"]) or "").strip()
                    ),
                }
            )
        return rows


def _seed_quiz_dump_for_user(
    *,
    owner_user_id: int,
    note_type_id: str,
    template_id: str,
    replace_existing: bool,
    stats: SeedStats,
) -> tuple[Deck | None, int]:
    dump_root, manifest_path = _resolve_quiz_dump_paths()
    if not manifest_path.exists():
        click.echo(f"Quiz dump manifest not found: {manifest_path}. Skipping quiz deck seed.")
        return None, 0

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid quiz dump manifest JSON: {manifest_path}") from exc

    deck_name = str(manifest.get("deck_name") or "Trac Nghiem Co Ban").strip() or "Trac Nghiem Co Ban"
    dump_filename = str(manifest.get("file") or QUIZ_DUMP_DEFAULT_FILE).strip() or QUIZ_DUMP_DEFAULT_FILE
    dump_file = dump_root / dump_filename
    if not dump_file.exists():
        raise click.ClickException(f"Quiz dump file not found: {dump_file}")

    rows = _load_quiz_dump_rows(dump_file)
    if not rows:
        click.echo(f"Quiz dump has no valid rows: {dump_file}. Skipping quiz deck seed.")
        return None, 0

    deck_description = f"Seeded quiz dump from {dump_file.name}"
    quiz_deck, _created = _get_or_create_deck(
        parent_deck_id=None,
        owner_user_id=owner_user_id,
        name=deck_name,
        description=deck_description,
        stats=stats,
    )
    if not quiz_deck.note_type_id:
        quiz_deck.note_type_id = note_type_id

    existing_notes = (
        Note.query.filter(
            Note.deck_id == quiz_deck.id,
            Note.user_id == owner_user_id,
            Note.note_type_id == note_type_id,
        )
        .all()
    )
    existing_note_ids = [note.id for note in existing_notes]
    if existing_note_ids and not replace_existing:
        stats.skipped_files += 1
        click.echo(f"Skip quiz deck (already seeded): {quiz_deck.name}")
        return quiz_deck, len(existing_notes)

    if existing_note_ids:
        existing_card_ids = [
            row[0]
            for row in db.session.query(Card.id)
            .filter(Card.note_id.in_(existing_note_ids))
            .all()
            if row and row[0]
        ]
        if existing_card_ids:
            CardProgress.query.filter(
                CardProgress.card_id.in_(existing_card_ids)
            ).delete(synchronize_session=False)
        Card.query.filter(Card.note_id.in_(existing_note_ids)).delete(synchronize_session=False)
        Note.query.filter(Note.id.in_(existing_note_ids)).delete(synchronize_session=False)
        stats.replaced_files += 1

    notes: list[Note] = []
    for row in rows:
        notes.append(
            Note(
                note_type_id=note_type_id,
                user_id=owner_user_id,
                deck_id=quiz_deck.id,
                field_values={
                    "question": row["question"],
                    "answer_1": row["answer_1"],
                    "answer_2": row["answer_2"],
                    "answer_3": row["answer_3"],
                    "answer_4": row["answer_4"],
                    "correct_answer": row["correct_answer"],
                },
                tags=["quiz", "seeded"],
            )
        )
    db.session.add_all(notes)
    db.session.flush()

    cards = [Card(note_id=note.id, template_id=template_id) for note in notes]
    db.session.add_all(cards)
    db.session.flush()

    stats.created_notes += len(notes)
    stats.created_cards += len(cards)
    stats.seeded_files += 1
    return quiz_deck, len(notes)
