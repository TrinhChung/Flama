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
