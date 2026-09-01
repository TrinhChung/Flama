"""Read-only reconciliation metrics and disposition inventory for study architecture."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from app.services import study_artifact_service
from app.services.study_algorithm_registry import _REGISTRY
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.connect_review_event_ref import ConnectReviewEventRef
from models.deck import Deck
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.review_event import ReviewEvent
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.template import Template

SCHEMA_VERSION = "study-architecture-audit.v3"
MAX_SAMPLE_IDS = 10
_SESSION_CONFIG_SCHEMA_VERSION = "scheduler-config.v1"
_SESSION_POLICY_MATERIAL_KEYS = (
    "algorithm_key",
    "algorithm_version",
    "config_schema_version",
    "timezone",
    "config",
)


def _is_valid_session_policy_snapshot(
    *,
    policy_key: str,
    policy: Any,
    session_algorithm: str,
    session_algorithm_version: str,
    session_timezone: str,
) -> bool:
    """Validate a frozen scheduler policy against the canonical writer contract."""
    if not isinstance(policy, dict):
        return False

    for key in _SESSION_POLICY_MATERIAL_KEYS[:-1]:
        value = policy.get(key)
        if not isinstance(value, str) or not value.strip():
            return False
    if not isinstance(policy.get("config"), dict):
        return False

    normalized_policy_key = str(policy_key or "")
    if str(policy.get("config_hash") or "") != normalized_policy_key:
        return False
    if str(policy.get("algorithm_key")) != str(session_algorithm or ""):
        return False
    if str(policy.get("algorithm_version")) != str(session_algorithm_version or ""):
        return False
    if str(policy.get("config_schema_version")) != _SESSION_CONFIG_SCHEMA_VERSION:
        return False
    if str(policy.get("timezone")) != str(session_timezone or ""):
        return False

    policy_material = {key: policy[key] for key in _SESSION_POLICY_MATERIAL_KEYS}
    return (
        study_artifact_service.canonical_digest(policy_material)
        == normalized_policy_key
    )


def _group_count(query) -> int:
    return int(db.session.query(db.func.count()).select_from(query.subquery()).scalar() or 0)


def _sample_scalars(query, limit: int = MAX_SAMPLE_IDS) -> list[Any]:
    rows = query.limit(limit).all()
    results = []
    for r in rows:
        if isinstance(r, (tuple, list)):
            results.append(r[0])
        elif hasattr(r, "_mapping") and len(r._mapping) > 0:
            results.append(list(r._mapping.values())[0])
        else:
            results.append(r)
    return results


def _build_disposition_inventory(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate machine-readable disposition inventory for each audit category."""
    inventory = []

    def add_item(
        category: str,
        gate_group: str,
        count: int,
        sample_ids: list[Any],
        severity: str,
        disposition: str,
        description: str,
    ) -> None:
        inventory.append(
            {
                "category": category,
                "gate_group": gate_group,
                "count": count,
                "sample_ids": sample_ids[:MAX_SAMPLE_IDS],
                "severity": severity,
                "disposition": disposition,
                "description": description,
            }
        )

    tg = metrics["template_gates"]
    cg = metrics["card_gates"]
    pg = metrics["progress_gates"]
    rvg = metrics.get("revision_gates", {})
    ag = metrics.get("algorithm_gates", {})
    rg = metrics["review_event_gates"]
    sg = metrics["session_gates"]
    og = metrics.get("clone_overlay_gates", {})

    # 1. Template gates
    add_item(
        "note_types_without_templates",
        "template",
        tg["note_types_without_templates"],
        tg.get("note_types_without_templates_samples", []),
        "warn" if tg["note_types_without_templates"] > 0 else "pass",
        "investigate_empty_notetypes",
        "NoteTypes without any Template definitions.",
    )
    add_item(
        "note_types_with_single_template",
        "template",
        tg.get("note_types_with_single_template", 0),
        tg.get("note_types_with_single_template_samples", []),
        "pass",
        "valid_single_template",
        "NoteTypes with exactly one Template definition.",
    )
    add_item(
        "note_types_with_multiple_templates",
        "template",
        tg["note_types_with_multiple_templates"],
        tg.get("note_types_with_multiple_templates_samples", []),
        "pass",
        "valid_multi_template",
        "NoteTypes with multiple Templates (valid multi-card design).",
    )
    add_item(
        "note_types_with_zero_defaults",
        "template",
        tg.get("note_types_with_zero_defaults", 0),
        tg.get("note_types_with_zero_defaults_samples", []),
        "warn" if tg.get("note_types_with_zero_defaults", 0) > 0 else "pass",
        "investigate_missing_default_template",
        "NoteTypes with templates but zero default templates designated.",
    )
    add_item(
        "note_types_with_single_default",
        "template",
        tg.get("note_types_with_single_default", 0),
        tg.get("note_types_with_single_default_samples", []),
        "pass",
        "valid_single_default_template",
        "NoteTypes with exactly one default Template designated.",
    )
    add_item(
        "note_types_with_multiple_defaults",
        "template",
        tg.get("note_types_with_multiple_defaults", 0),
        tg.get("note_types_with_multiple_defaults_samples", []),
        "warn" if tg.get("note_types_with_multiple_defaults", 0) > 0 else "pass",
        "reconcile_multiple_default_templates",
        "NoteTypes with more than one default Template designated.",
    )
    add_item(
        "default_count_anomalies",
        "template",
        tg["default_count_anomalies"],
        tg.get("default_count_anomalies_samples", []),
        "warn" if tg["default_count_anomalies"] > 0 else "pass",
        "reconcile_default_templates",
        "NoteTypes with default template count not equal to 1.",
    )
    add_item(
        "duplicate_name_groups",
        "template",
        tg["duplicate_name_groups"],
        tg.get("duplicate_name_samples", []),
        "warn" if tg["duplicate_name_groups"] > 0 else "pass",
        "review_duplicate_names",
        "Template name collisions within the same NoteType.",
    )
    add_item(
        "duplicate_position_groups",
        "template",
        tg["duplicate_position_groups"],
        tg.get("duplicate_position_samples", []),
        "warn" if tg["duplicate_position_groups"] > 0 else "pass",
        "review_duplicate_positions",
        "Template position collisions within the same NoteType.",
    )
    add_item(
        "cross_note_type_cards",
        "template",
        tg["cross_note_type_cards"],
        tg.get("cross_note_type_cards_samples", []),
        "block" if tg["cross_note_type_cards"] > 0 else "pass",
        "quarantine_cross_notetype_cards",
        "Cards referencing a Template from a different NoteType than their Note.",
    )

    # 2. Card gates
    add_item(
        "notes_without_cards",
        "card",
        cg["notes_without_cards"],
        cg.get("notes_without_cards_samples", []),
        "warn" if cg["notes_without_cards"] > 0 else "pass",
        "review_orphan_notes",
        "Notes without any generated Cards.",
    )
    add_item(
        "notes_with_single_card",
        "card",
        cg.get("notes_with_single_card", 0),
        cg.get("notes_with_single_card_samples", []),
        "pass",
        "valid_single_card_notes",
        "Notes with exactly one generated Card.",
    )
    add_item(
        "notes_with_multiple_cards",
        "card",
        cg["notes_with_multiple_cards"],
        cg.get("notes_with_multiple_cards_samples", []),
        "pass",
        "valid_multi_card_notes",
        "Notes with multiple Cards generated across Templates.",
    )
    add_item(
        "orphan_cards",
        "card",
        cg.get("orphan_cards", 0),
        cg.get("orphan_cards_samples", []),
        "block" if cg.get("orphan_cards", 0) > 0 else "pass",
        "quarantine_orphan_cards",
        "Cards referencing missing Note or missing Template records.",
    )

    # 3. Progress gates
    add_item(
        "null_card_id_rows",
        "progress",
        pg["null_card_id_rows"],
        pg.get("null_card_id_samples", []),
        "block" if pg["null_card_id_rows"] > 0 else "pass",
        "quarantine_null_card_progress",
        "CardProgress records with NULL card_id.",
    )
    add_item(
        "orphan_card_id_rows",
        "progress",
        pg["orphan_card_id_rows"],
        pg.get("orphan_card_id_samples", []),
        "block" if pg["orphan_card_id_rows"] > 0 else "pass",
        "quarantine_orphan_card_progress",
        "CardProgress records referencing deleted or non-existent Cards.",
    )
    add_item(
        "orphan_note_id_rows",
        "progress",
        pg.get("orphan_note_id_rows", 0),
        pg.get("orphan_note_id_samples", []),
        "block" if pg.get("orphan_note_id_rows", 0) > 0 else "pass",
        "quarantine_orphan_note_progress",
        "CardProgress records whose Card references a missing or deleted Note.",
    )
    add_item(
        "unresolvable_progress_subjects",
        "progress",
        pg.get("unresolvable_progress_subjects", 0),
        pg.get("unresolvable_progress_samples", []),
        "block" if pg.get("unresolvable_progress_subjects", 0) > 0 else "pass",
        "quarantine_unresolvable_progress_subjects",
        "CardProgress rows with unresolvable subject (missing card or missing note).",
    )
    add_item(
        "single_card_progress_groups",
        "progress",
        pg.get("single_card_progress_groups", 0),
        pg.get("single_card_progress_samples", []),
        "pass",
        "single_card_progress",
        "Learner-Note pairs with exactly one CardProgress record.",
    )
    add_item(
        "learner_note_fan_in_groups",
        "progress",
        pg["learner_note_fan_in_groups"],
        pg.get("learner_note_fan_in_samples", []),
        "pass",
        "learner_note_fan_in",
        "Learner-Note pairs with multiple CardProgress records.",
    )
    add_item(
        "equivalent_fan_in_groups",
        "progress",
        pg.get("equivalent_fan_in_groups", 0),
        pg.get("equivalent_fan_in_samples", []),
        "pass",
        "equivalent_fan_in",
        "Learner-Note fan-in groups where all cards share equivalent scheduler state.",
    )
    add_item(
        "divergent_fan_in_groups",
        "progress",
        pg["divergent_fan_in_groups"],
        pg.get("divergent_fan_in_samples", []),
        "block" if pg["divergent_fan_in_groups"] > 0 else "pass",
        "quarantine_divergent_progress_fan_in",
        "Learner-Note fan-in groups with conflicting scheduler states.",
    )
    add_item(
        "learner_note_history_fan_in_groups",
        "progress",
        pg.get("learner_note_history_fan_in_groups", 0),
        pg.get("learner_note_history_fan_in_samples", []),
        "pass",
        "review_history_fan_in",
        "Learner-Note pairs with review history across multiple Cards.",
    )
    add_item(
        "fsrs_rows",
        "progress",
        pg.get("fsrs_rows", 0),
        pg.get("fsrs_samples", []),
        "pass",
        "fsrs_progress_state",
        "CardProgress rows configured with FSRS scheduler mode.",
    )
    add_item(
        "partial_fsrs_state_rows",
        "progress",
        pg["partial_fsrs_state_rows"],
        pg.get("partial_fsrs_samples", []),
        "warn" if pg["partial_fsrs_state_rows"] > 0 else "pass",
        "reconcile_fsrs_memory_state",
        "CardProgress rows with incomplete FSRS stability/difficulty fields.",
    )

    # 4. Revision gates
    if rvg:
        add_item(
            "zero_revision_rows",
            "revision",
            rvg.get("zero_revision_rows", 0),
            rvg.get("zero_revision_samples", []),
            "pass",
            "initial_revision_state",
            "CardProgress rows at baseline initial revision zero.",
        )
        add_item(
            "active_revision_rows",
            "revision",
            rvg.get("active_revision_rows", 0),
            rvg.get("active_revision_samples", []),
            "pass",
            "active_revision_state",
            "CardProgress rows with incremented active revisions.",
        )
        add_item(
            "invalid_revision_rows",
            "revision",
            rvg.get("invalid_revision_rows", 0),
            rvg.get("invalid_revision_samples", []),
            "block" if rvg.get("invalid_revision_rows", 0) > 0 else "pass",
            "quarantine_invalid_revisions",
            "CardProgress rows with NULL or negative revision counters.",
        )
        add_item(
            "open_session_stale_revisions",
            "revision",
            rvg.get("open_session_stale_revisions", 0),
            rvg.get("open_session_stale_samples", []),
            "warn" if rvg.get("open_session_stale_revisions", 0) > 0 else "pass",
            "flag_session_revision_drift",
            "StudySessionCards in open sessions whose base revision has drifted.",
        )

    # 5. Algorithm gates
    if ag:
        add_item(
            "registered_algorithm_count",
            "algorithm",
            ag.get("registered_algorithm_count", 0),
            [],
            "pass",
            "active_registered_executables",
            "Number of executable Study Algorithm adapters currently registered in memory.",
        )
        add_item(
            "registered_algorithm_events",
            "algorithm",
            ag.get("registered_algorithm_events", 0),
            [],
            "pass",
            "active_registered_algorithm_events",
            "ReviewEvents matching an active registered Study Algorithm executable in memory.",
        )
        add_item(
            "historical_imported_algorithm_events",
            "algorithm",
            ag.get("historical_imported_algorithm_events", 0),
            ag.get("historical_imported_algo_samples", []),
            "pass",
            "historical_imported_algorithm",
            "ReviewEvents imported from Anki or external sources carrying historical scheduler algorithm identities.",
        )
        add_item(
            "unregistered_native_algorithm_events",
            "algorithm",
            ag.get("unregistered_native_algorithm_events", 0),
            ag.get("unregistered_native_algo_samples", []),
            "warn" if ag.get("unregistered_native_algorithm_events", 0) > 0 else "pass",
            "classify_unregistered_algorithm",
            "Native ReviewEvents with scheduler_algorithm/version not registered in active executable registry.",
        )
        add_item(
            "missing_algorithm_version_events",
            "algorithm",
            ag.get("missing_algorithm_version_events", 0),
            ag.get("missing_algo_version_samples", []),
            "warn" if ag.get("missing_algorithm_version_events", 0) > 0 else "pass",
            "classify_missing_algorithm_version",
            "Native ReviewEvents with scheduler_algorithm specified but missing algorithm_version.",
        )
        add_item(
            "unprovenanced_fsrs_rows",
            "algorithm",
            ag.get("unprovenanced_fsrs_rows", 0),
            ag.get("unprovenanced_fsrs_samples", []),
            "warn" if ag.get("unprovenanced_fsrs_rows", 0) > 0 else "pass",
            "verify_fsrs_provenance",
            "CardProgress rows marked FSRS without corresponding FSRS review history.",
        )

    # 6. ReviewEvent gates
    add_item(
        "orphan_card_id_events",
        "review_event",
        rg["orphan_card_id_events"],
        rg.get("orphan_card_id_samples", []),
        "warn" if rg["orphan_card_id_events"] > 0 else "pass",
        "retain_detached_review_events",
        "ReviewEvent records referencing detached or deleted Cards.",
    )
    add_item(
        "attached_review_events",
        "review_event",
        rg.get("attached_review_events", 0),
        [],
        "pass",
        "attached_review_events",
        "ReviewEvent records referencing existing Cards.",
    )
    add_item(
        "null_session_id_events",
        "review_event",
        rg["null_session_id_events"],
        rg.get("null_session_id_samples", []),
        "pass",
        "legacy_or_direct_reviews",
        "ReviewEvent records without study_session_id (legacy or direct review).",
    )
    add_item(
        "null_algorithm_events",
        "review_event",
        rg["null_algorithm_events"],
        rg.get("null_algorithm_samples", []),
        "warn" if rg["null_algorithm_events"] > 0 else "pass",
        "classify_unversioned_algorithm",
        "ReviewEvent records with NULL scheduler_algorithm.",
    )
    add_item(
        "duplicate_client_event_id_groups",
        "review_event",
        rg.get("duplicate_client_event_id_groups", 0),
        rg.get("duplicate_client_samples", []),
        "block" if rg.get("duplicate_client_event_id_groups", 0) > 0 else "pass",
        "quarantine_duplicate_client_events",
        "ReviewEvents with duplicate client_event_id for the same user.",
    )
    add_item(
        "duplicate_session_sequence_groups",
        "review_event",
        rg.get("duplicate_session_sequence_groups", 0),
        rg.get("duplicate_seq_samples", []),
        "block" if rg.get("duplicate_session_sequence_groups", 0) > 0 else "pass",
        "quarantine_duplicate_session_sequences",
        "ReviewEvents with colliding sequence_no within the same study session.",
    )
    add_item(
        "missing_session_sequence_events",
        "review_event",
        rg.get("missing_session_sequence_events", 0),
        rg.get("missing_seq_samples", []),
        "warn" if rg.get("missing_session_sequence_events", 0) > 0 else "pass",
        "review_session_events_missing_sequence",
        "ReviewEvents attached to a study session but lacking sequence_no.",
    )
    # Provenance classifications
    add_item(
        "anki_import_events",
        "review_event",
        rg.get("anki_import_events", 0),
        rg.get("anki_import_samples", []),
        "pass",
        "anki_import_reviews",
        "ReviewEvents imported from Anki revlogs or connect import sessions.",
    )
    add_item(
        "native_session_events",
        "review_event",
        rg.get("native_session_events", 0),
        rg.get("native_session_samples", []),
        "pass",
        "native_session_reviews",
        "ReviewEvents completed within native frontend study sessions.",
    )
    add_item(
        "native_direct_events",
        "review_event",
        rg.get("native_direct_events", 0),
        rg.get("native_direct_samples", []),
        "pass",
        "native_direct_reviews",
        "ReviewEvents executed directly via native review actions outside sessions.",
    )
    add_item(
        "native_mcp_events",
        "review_event",
        rg.get("native_mcp_events", 0),
        rg.get("native_mcp_samples", []),
        "pass",
        "native_mcp_reviews",
        "ReviewEvents initiated via Flama MCP connect tools.",
    )
    add_item(
        "native_batch_events",
        "review_event",
        rg.get("native_batch_events", 0),
        rg.get("native_batch_samples", []),
        "pass",
        "native_batch_reviews",
        "ReviewEvents processed in bulk batch review operations.",
    )
    add_item(
        "conflicting_provenance_events",
        "review_event",
        rg.get("conflicting_provenance_events", 0),
        rg.get("conflicting_provenance_samples", []),
        "block" if rg.get("conflicting_provenance_events", 0) > 0 else "pass",
        "quarantine_conflicting_provenance",
        "ReviewEvents with mutually contradictory provenance signals.",
    )
    add_item(
        "unknown_provenance_events",
        "review_event",
        rg.get("unknown_provenance_events", 0),
        rg.get("unknown_provenance_samples", []),
        "warn" if rg.get("unknown_provenance_events", 0) > 0 else "pass",
        "needs_verification_provenance",
        "ReviewEvents with unclassifiable or ambiguous provenance markers.",
    )

    # 7. Session gates
    add_item(
        "open_sessions",
        "session",
        sg.get("open_sessions", 0),
        [],
        "pass",
        "total_open_sessions",
        "Total study sessions in open status.",
    )
    add_item(
        "active_open_sessions",
        "session",
        sg.get("active_open_sessions", 0),
        sg.get("active_open_sessions_samples", []),
        "pass",
        "active_open_sessions",
        "StudySession records open and currently within expiration lease.",
    )
    add_item(
        "expired_open_sessions",
        "session",
        sg["expired_open_sessions"],
        sg.get("expired_open_sessions_samples", []),
        "warn" if sg["expired_open_sessions"] > 0 else "pass",
        "expire_stale_sessions",
        "StudySession records open past their expiration timestamp.",
    )
    add_item(
        "committed_sessions",
        "session",
        sg.get("committed_sessions", 0),
        [],
        "pass",
        "committed_sessions",
        "StudySession records successfully committed.",
    )
    add_item(
        "cancelled_sessions",
        "session",
        sg.get("cancelled_sessions", 0),
        [],
        "pass",
        "cancelled_sessions",
        "StudySession records explicitly cancelled.",
    )
    add_item(
        "abandoned_sessions",
        "session",
        sg.get("abandoned_sessions", 0),
        [],
        "pass",
        "abandoned_sessions",
        "StudySession records explicitly marked abandoned.",
    )
    add_item(
        "unknown_status_sessions",
        "session",
        sg.get("unknown_status_sessions", 0),
        sg.get("unknown_status_sessions_samples", []),
        "block" if sg.get("unknown_status_sessions", 0) > 0 else "pass",
        "quarantine_unknown_session_status",
        "StudySession records with unrecognized lifecycle status.",
    )
    add_item(
        "missing_snapshot_sessions",
        "session",
        sg.get("missing_snapshot_sessions", 0),
        sg.get("missing_snapshot_samples", []),
        "warn" if sg.get("missing_snapshot_sessions", 0) > 0 else "pass",
        "reconstruct_session_snapshot",
        "StudySession records missing snapshot_hash or configuration metadata.",
    )
    add_item(
        "invalid_config_snapshot_sessions",
        "session",
        sg.get("invalid_config_snapshot_sessions", 0),
        sg.get("invalid_config_snapshot_samples", []),
        "warn" if sg.get("invalid_config_snapshot_sessions", 0) > 0 else "pass",
        "repair_invalid_config_snapshot",
        "StudySession records containing malformed config_snapshot_json.",
    )
    add_item(
        "active_session_unavailable_algorithm_sessions",
        "session",
        sg.get("active_session_unavailable_algorithm_sessions", 0),
        sg.get("active_session_unavailable_algo_samples", []),
        "block" if sg.get("active_session_unavailable_algorithm_sessions", 0) > 0 else "pass",
        "quarantine_unavailable_session_algorithm",
        "Active open StudySession records referencing unregistered scheduler algorithms.",
    )
    add_item(
        "historical_session_retired_algorithm_sessions",
        "session",
        sg.get("historical_session_retired_algorithm_sessions", 0),
        sg.get("historical_session_retired_algo_samples", []),
        "pass",
        "historical_session_retired_algorithm",
        "Historical or inactive StudySession records referencing retired scheduler algorithms.",
    )

    # 8. Clone overlay gates
    if og:
        add_item(
            "deck_installs",
            "clone_overlay",
            og.get("deck_installs_count", 0),
            [],
            "pass",
            "installed_shared_decks",
            "Active DeckInstall pointer overlay records.",
        )
        add_item(
            "installed_notetypes",
            "clone_overlay",
            og.get("installed_notetypes_count", 0),
            [],
            "pass",
            "installed_note_types",
            "Active NoteTypeInstall records referencing marketplace note types.",
        )
        add_item(
            "installed_deck_cards",
            "clone_overlay",
            og.get("installed_deck_cards", 0),
            og.get("installed_deck_cards_samples", []),
            "pass",
            "installed_source_cards",
            "Cards referenced via shared deck installation overlays.",
        )
        add_item(
            "local_clone_added_cards",
            "clone_overlay",
            og.get("local_clone_added_cards", 0),
            og.get("local_clone_added_cards_samples", []),
            "pass",
            "local_clone_added_cards",
            "Cards generated from notes locally added to installed decks.",
        )
        add_item(
            "local_authored_cards",
            "clone_overlay",
            og.get("local_authored_cards", 0),
            og.get("local_authored_cards_samples", []),
            "pass",
            "local_authored_cards",
            "Cards belonging to native local author decks.",
        )
        add_item(
            "unassigned_deck_cards",
            "clone_overlay",
            og.get("unassigned_deck_cards", 0),
            og.get("unassigned_deck_cards_samples", []),
            "pass",
            "unassigned_deck_cards",
            "Cards belonging to notes without an explicit deck assignment.",
        )
        add_item(
            "overlay_ambiguities",
            "clone_overlay",
            og.get("overlay_ambiguity_count", 0),
            og.get("overlay_ambiguity_samples", []),
            "warn" if og.get("overlay_ambiguity_count", 0) > 0 else "pass",
            "investigate_overlay_ambiguities",
            "DeckCloneAddedNote records with ambiguous or drifted note associations.",
        )

    return inventory


def _categorize_verdicts(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive consistent verdicts and exit codes directly from the disposition inventory single source of truth."""
    verdicts: dict[str, Any] = {
        "pass": [],
        "warn": [],
        "block": [],
        "overall_status": "PASS",
        "exit_code": 0,
    }

    for item in inventory:
        cat = item["category"]
        sev = item["severity"]
        cnt = item["count"]
        desc = item["description"]
        if sev == "block":
            verdicts["block"].append(f"{cat}: {desc} ({cnt} item(s))")
        elif sev == "warn":
            verdicts["warn"].append(f"{cat}: {desc} ({cnt} item(s))")
        else:
            verdicts["pass"].append(f"{cat}: {cnt}")

    if len(verdicts["block"]) > 0:
        verdicts["overall_status"] = "BLOCK"
        verdicts["exit_code"] = 2
    elif len(verdicts["warn"]) > 0:
        verdicts["overall_status"] = "WARN"
        verdicts["exit_code"] = 1
    else:
        verdicts["overall_status"] = "PASS"
        verdicts["exit_code"] = 0

    return verdicts


def build_study_architecture_audit(*, now: datetime | None = None) -> dict[str, Any]:
    """Return comprehensive migration-grade audit v3 with bounded sample IDs, dispositions, and exhaustive reconciliation."""
    observed_at = now or datetime.utcnow()

    # -------------------------------------------------------------------------
    # 1. Template Gates
    # -------------------------------------------------------------------------
    template_counts = (
        db.session.query(
            NoteType.id.label("note_type_id"),
            db.func.count(Template.id).label("template_count"),
            db.func.sum(
                db.case((Template.is_default.is_(True), 1), else_=0)
            ).label("default_count"),
        )
        .outerjoin(Template, Template.note_type_id == NoteType.id)
        .group_by(NoteType.id)
        .subquery()
    )

    empty_nt_q = (
        db.session.query(template_counts.c.note_type_id)
        .select_from(template_counts)
        .filter(template_counts.c.template_count == 0)
        .order_by(template_counts.c.note_type_id.asc())
    )
    note_types_without_templates = int(
        db.session.query(db.func.count()).select_from(empty_nt_q.subquery()).scalar() or 0
    )
    empty_nt_samples = _sample_scalars(empty_nt_q)

    single_nt_q = (
        db.session.query(template_counts.c.note_type_id)
        .select_from(template_counts)
        .filter(template_counts.c.template_count == 1)
        .order_by(template_counts.c.note_type_id.asc())
    )
    note_types_with_single_template = int(
        db.session.query(db.func.count()).select_from(single_nt_q.subquery()).scalar() or 0
    )
    single_nt_samples = _sample_scalars(single_nt_q)

    multi_nt_q = (
        db.session.query(template_counts.c.note_type_id)
        .select_from(template_counts)
        .filter(template_counts.c.template_count > 1)
        .order_by(template_counts.c.note_type_id.asc())
    )
    note_types_with_multiple_templates = int(
        db.session.query(db.func.count()).select_from(multi_nt_q.subquery()).scalar() or 0
    )
    multi_nt_samples = _sample_scalars(multi_nt_q)

    # Defaults accounting
    zero_defaults_q = (
        db.session.query(template_counts.c.note_type_id)
        .select_from(template_counts)
        .filter(template_counts.c.template_count > 0, template_counts.c.default_count == 0)
        .order_by(template_counts.c.note_type_id.asc())
    )
    note_types_with_zero_defaults = int(
        db.session.query(db.func.count()).select_from(zero_defaults_q.subquery()).scalar() or 0
    )
    zero_defaults_samples = _sample_scalars(zero_defaults_q)

    single_default_q = (
        db.session.query(template_counts.c.note_type_id)
        .select_from(template_counts)
        .filter(template_counts.c.template_count > 0, template_counts.c.default_count == 1)
        .order_by(template_counts.c.note_type_id.asc())
    )
    note_types_with_single_default = int(
        db.session.query(db.func.count()).select_from(single_default_q.subquery()).scalar() or 0
    )
    single_default_samples = _sample_scalars(single_default_q)

    multi_defaults_q = (
        db.session.query(template_counts.c.note_type_id)
        .select_from(template_counts)
        .filter(template_counts.c.template_count > 0, template_counts.c.default_count > 1)
        .order_by(template_counts.c.note_type_id.asc())
    )
    note_types_with_multiple_defaults = int(
        db.session.query(db.func.count()).select_from(multi_defaults_q.subquery()).scalar() or 0
    )
    multi_defaults_samples = _sample_scalars(multi_defaults_q)

    default_anom_q = (
        db.session.query(template_counts.c.note_type_id)
        .select_from(template_counts)
        .filter(template_counts.c.default_count != 1)
        .order_by(template_counts.c.note_type_id.asc())
    )
    template_default_anomalies = int(
        db.session.query(db.func.count()).select_from(default_anom_q.subquery()).scalar() or 0
    )
    default_anom_samples = _sample_scalars(default_anom_q)

    dup_names_q = (
        db.session.query(Template.note_type_id, db.func.lower(Template.name))
        .group_by(Template.note_type_id, db.func.lower(Template.name))
        .having(db.func.count(Template.id) > 1)
        .order_by(Template.note_type_id.asc(), db.func.lower(Template.name).asc())
    )
    duplicate_template_names = _group_count(dup_names_q)
    dup_names_samples = [
        f"notetype:{nt_id}/name:{name}" for nt_id, name in dup_names_q.limit(MAX_SAMPLE_IDS).all()
    ]

    dup_pos_q = (
        db.session.query(Template.note_type_id, Template.position)
        .group_by(Template.note_type_id, Template.position)
        .having(db.func.count(Template.id) > 1)
        .order_by(Template.note_type_id.asc(), Template.position.asc())
    )
    duplicate_template_positions = _group_count(dup_pos_q)
    dup_pos_samples = [
        f"notetype:{nt_id}/pos:{pos}" for nt_id, pos in dup_pos_q.limit(MAX_SAMPLE_IDS).all()
    ]

    cross_cards_q = (
        db.session.query(Card.id)
        .join(Note, Note.id == Card.note_id)
        .join(Template, Template.id == Card.template_id)
        .filter(Note.note_type_id != Template.note_type_id)
        .order_by(Card.id.asc())
    )
    cross_note_type_cards = int(
        db.session.query(db.func.count()).select_from(cross_cards_q.subquery()).scalar() or 0
    )
    cross_cards_samples = _sample_scalars(cross_cards_q)

    # -------------------------------------------------------------------------
    # 2. Card Gates
    # -------------------------------------------------------------------------
    notes_without_cards_q = (
        db.session.query(Note.id)
        .outerjoin(Card, Card.note_id == Note.id)
        .filter(Card.id.is_(None))
        .order_by(Note.id.asc())
    )
    notes_without_cards = int(
        db.session.query(db.func.count()).select_from(notes_without_cards_q.subquery()).scalar() or 0
    )
    notes_without_cards_samples = _sample_scalars(notes_without_cards_q)

    notes_with_multi_cards_q = (
        db.session.query(Card.note_id)
        .group_by(Card.note_id)
        .having(db.func.count(Card.id) > 1)
        .order_by(Card.note_id.asc())
    )
    notes_with_multiple_cards = _group_count(notes_with_multi_cards_q)
    notes_with_multi_cards_samples = _sample_scalars(notes_with_multi_cards_q)

    notes_with_single_card_q = (
        db.session.query(Card.note_id)
        .group_by(Card.note_id)
        .having(db.func.count(Card.id) == 1)
        .order_by(Card.note_id.asc())
    )
    notes_with_single_card = _group_count(notes_with_single_card_q)
    notes_with_single_card_samples = _sample_scalars(notes_with_single_card_q)

    orphan_cards_q = (
        db.session.query(Card.id)
        .outerjoin(Note, Note.id == Card.note_id)
        .outerjoin(Template, Template.id == Card.template_id)
        .filter(db.or_(Note.id.is_(None), Template.id.is_(None)))
        .order_by(Card.id.asc())
    )
    orphan_cards_count = int(
        db.session.query(db.func.count()).select_from(orphan_cards_q.subquery()).scalar() or 0
    )
    orphan_cards_samples = _sample_scalars(orphan_cards_q)

    # -------------------------------------------------------------------------
    # 3. Progress Gates & Expanded Fan-In Equivalence
    # -------------------------------------------------------------------------
    null_progress_q = (
        db.session.query(CardProgress.id)
        .filter(CardProgress.card_id.is_(None))
        .order_by(CardProgress.id.asc())
    )
    null_progress_subjects = int(
        db.session.query(db.func.count()).select_from(null_progress_q.subquery()).scalar() or 0
    )
    null_progress_samples = _sample_scalars(null_progress_q)

    orphan_progress_q = (
        db.session.query(CardProgress.id)
        .outerjoin(Card, Card.id == CardProgress.card_id)
        .filter(CardProgress.card_id.isnot(None), Card.id.is_(None))
        .order_by(CardProgress.id.asc())
    )
    orphan_progress_subjects = int(
        db.session.query(db.func.count()).select_from(orphan_progress_q.subquery()).scalar() or 0
    )
    orphan_progress_samples = _sample_scalars(orphan_progress_q)

    orphan_note_progress_q = (
        db.session.query(CardProgress.id)
        .join(Card, Card.id == CardProgress.card_id)
        .outerjoin(Note, Note.id == Card.note_id)
        .filter(Note.id.is_(None))
        .order_by(CardProgress.id.asc())
    )
    orphan_note_progress_subjects = int(
        db.session.query(db.func.count()).select_from(orphan_note_progress_q.subquery()).scalar() or 0
    )
    orphan_note_progress_samples = _sample_scalars(orphan_note_progress_q)

    unresolvable_progress_q = (
        db.session.query(CardProgress.id)
        .outerjoin(Card, Card.id == CardProgress.card_id)
        .outerjoin(Note, Note.id == Card.note_id)
        .filter(
            db.or_(
                CardProgress.card_id.is_(None),
                Card.id.is_(None),
                Card.note_id.is_(None),
                Note.id.is_(None),
            )
        )
        .order_by(CardProgress.id.asc())
    )
    unresolvable_progress_subjects = int(
        db.session.query(db.func.count()).select_from(unresolvable_progress_q.subquery()).scalar() or 0
    )
    unresolvable_progress_samples = _sample_scalars(unresolvable_progress_q)

    # Valid progress groups per (user_id, note_id) covering ALL 21 scheduling state fields
    valid_progress_group_subq = (
        db.session.query(
            CardProgress.user_id.label("user_id"),
            Card.note_id.label("note_id"),
            db.func.count(CardProgress.id).label("progress_count"),
            db.func.count(db.distinct(CardProgress.queue)).label("distinct_queues"),
            db.func.count(db.distinct(CardProgress.step_index)).label("distinct_steps"),
            db.func.count(db.distinct(CardProgress.due_at)).label("distinct_due_ats"),
            db.func.count(db.distinct(CardProgress.due_day)).label("distinct_due_days"),
            db.func.count(db.distinct(CardProgress.interval_days)).label("distinct_intervals"),
            db.func.count(db.distinct(CardProgress.interval_days_raw)).label("distinct_interval_raws"),
            db.func.count(db.distinct(CardProgress.is_suspended)).label("distinct_suspended"),
            db.func.count(db.distinct(CardProgress.is_buried)).label("distinct_buried"),
            db.func.count(db.distinct(CardProgress.buried_until_day)).label("distinct_buried_days"),
            db.func.count(db.distinct(CardProgress.suspension_reason)).label("distinct_suspension_reasons"),
            db.func.count(db.distinct(CardProgress.review_kind)).label("distinct_review_kinds"),
            db.func.count(db.distinct(CardProgress.scheduler_mode)).label("distinct_modes"),
            db.func.count(db.distinct(CardProgress.ease_factor)).label("distinct_eases"),
            db.func.count(db.distinct(CardProgress.memory_stability)).label("distinct_stabilities"),
            db.func.count(db.distinct(CardProgress.memory_difficulty)).label("distinct_difficulties"),
            db.func.count(db.distinct(CardProgress.last_leech_lapses)).label("distinct_leech_lapses"),
            db.func.count(db.distinct(CardProgress.last_leech_at)).label("distinct_leech_ats"),
            db.func.count(db.distinct(CardProgress.reps)).label("distinct_reps"),
            db.func.count(db.distinct(CardProgress.lapses)).label("distinct_lapses"),
            db.func.count(db.distinct(CardProgress.last_reviewed_at)).label("distinct_reviewed_ats"),
            db.func.count(db.distinct(CardProgress.revision)).label("distinct_revisions"),
            db.func.sum(db.case((CardProgress.due_at.is_(None), 1), else_=0)).label("null_due_ats"),
            db.func.sum(db.case((CardProgress.due_day.is_(None), 1), else_=0)).label("null_due_days"),
            db.func.sum(db.case((CardProgress.interval_days_raw.is_(None), 1), else_=0)).label("null_interval_raws"),
            db.func.sum(db.case((CardProgress.buried_until_day.is_(None), 1), else_=0)).label("null_buried_days"),
            db.func.sum(db.case((CardProgress.suspension_reason.is_(None), 1), else_=0)).label("null_suspension_reasons"),
            db.func.sum(db.case((CardProgress.memory_stability.is_(None), 1), else_=0)).label("null_stabilities"),
            db.func.sum(db.case((CardProgress.memory_difficulty.is_(None), 1), else_=0)).label("null_difficulties"),
            db.func.sum(db.case((CardProgress.last_leech_at.is_(None), 1), else_=0)).label("null_leech_ats"),
            db.func.sum(db.case((CardProgress.last_reviewed_at.is_(None), 1), else_=0)).label("null_reviewed_ats"),
        )
        .join(Card, Card.id == CardProgress.card_id)
        .join(Note, Note.id == Card.note_id)
        .group_by(CardProgress.user_id, Card.note_id)
        .subquery()
    )

    single_prog_q = (
        db.session.query(valid_progress_group_subq.c.user_id, valid_progress_group_subq.c.note_id)
        .filter(valid_progress_group_subq.c.progress_count == 1)
        .order_by(valid_progress_group_subq.c.user_id.asc(), valid_progress_group_subq.c.note_id.asc())
    )
    single_card_progress_groups = _group_count(single_prog_q)
    single_card_progress_samples = [
        f"user:{uid}/note:{nid}" for uid, nid in single_prog_q.limit(MAX_SAMPLE_IDS).all()
    ]
    single_card_progress_rows = single_card_progress_groups

    fan_in_q = (
        db.session.query(valid_progress_group_subq.c.user_id, valid_progress_group_subq.c.note_id)
        .filter(valid_progress_group_subq.c.progress_count > 1)
        .order_by(valid_progress_group_subq.c.user_id.asc(), valid_progress_group_subq.c.note_id.asc())
    )
    progress_fan_in_groups = _group_count(fan_in_q)
    fan_in_samples = [
        f"user:{uid}/note:{nid}" for uid, nid in fan_in_q.limit(MAX_SAMPLE_IDS).all()
    ]

    fan_in_rows_sum = int(
        db.session.query(db.func.sum(valid_progress_group_subq.c.progress_count))
        .filter(valid_progress_group_subq.c.progress_count > 1)
        .scalar()
        or 0
    )

    # Equivalence requires identical state across all 21 behavioral fields and no null divergence
    is_equivalent_fan_in_expr = db.and_(
        valid_progress_group_subq.c.progress_count > 1,
        valid_progress_group_subq.c.distinct_queues == 1,
        valid_progress_group_subq.c.distinct_steps <= 1,
        valid_progress_group_subq.c.distinct_due_ats <= 1,
        valid_progress_group_subq.c.distinct_due_days <= 1,
        valid_progress_group_subq.c.distinct_intervals == 1,
        valid_progress_group_subq.c.distinct_interval_raws <= 1,
        valid_progress_group_subq.c.distinct_suspended <= 1,
        valid_progress_group_subq.c.distinct_buried <= 1,
        valid_progress_group_subq.c.distinct_buried_days <= 1,
        valid_progress_group_subq.c.distinct_suspension_reasons <= 1,
        valid_progress_group_subq.c.distinct_review_kinds <= 1,
        valid_progress_group_subq.c.distinct_modes <= 1,
        valid_progress_group_subq.c.distinct_eases == 1,
        valid_progress_group_subq.c.distinct_stabilities <= 1,
        valid_progress_group_subq.c.distinct_difficulties <= 1,
        valid_progress_group_subq.c.distinct_leech_lapses <= 1,
        valid_progress_group_subq.c.distinct_leech_ats <= 1,
        valid_progress_group_subq.c.distinct_reps <= 1,
        valid_progress_group_subq.c.distinct_lapses <= 1,
        valid_progress_group_subq.c.distinct_reviewed_ats <= 1,
        valid_progress_group_subq.c.distinct_revisions <= 1,
        db.or_(
            valid_progress_group_subq.c.null_due_ats == 0,
            valid_progress_group_subq.c.null_due_ats == valid_progress_group_subq.c.progress_count,
        ),
        db.or_(
            valid_progress_group_subq.c.null_due_days == 0,
            valid_progress_group_subq.c.null_due_days == valid_progress_group_subq.c.progress_count,
        ),
        db.or_(
            valid_progress_group_subq.c.null_interval_raws == 0,
            valid_progress_group_subq.c.null_interval_raws == valid_progress_group_subq.c.progress_count,
        ),
        db.or_(
            valid_progress_group_subq.c.null_buried_days == 0,
            valid_progress_group_subq.c.null_buried_days == valid_progress_group_subq.c.progress_count,
        ),
        db.or_(
            valid_progress_group_subq.c.null_suspension_reasons == 0,
            valid_progress_group_subq.c.null_suspension_reasons == valid_progress_group_subq.c.progress_count,
        ),
        db.or_(
            valid_progress_group_subq.c.null_stabilities == 0,
            valid_progress_group_subq.c.null_stabilities == valid_progress_group_subq.c.progress_count,
        ),
        db.or_(
            valid_progress_group_subq.c.null_difficulties == 0,
            valid_progress_group_subq.c.null_difficulties == valid_progress_group_subq.c.progress_count,
        ),
        db.or_(
            valid_progress_group_subq.c.null_leech_ats == 0,
            valid_progress_group_subq.c.null_leech_ats == valid_progress_group_subq.c.progress_count,
        ),
        db.or_(
            valid_progress_group_subq.c.null_reviewed_ats == 0,
            valid_progress_group_subq.c.null_reviewed_ats == valid_progress_group_subq.c.progress_count,
        ),
    )

    equiv_fan_in_q = (
        db.session.query(valid_progress_group_subq.c.user_id, valid_progress_group_subq.c.note_id)
        .filter(is_equivalent_fan_in_expr)
        .order_by(valid_progress_group_subq.c.user_id.asc(), valid_progress_group_subq.c.note_id.asc())
    )
    equivalent_fan_in_groups = _group_count(equiv_fan_in_q)
    equivalent_fan_in_samples = [
        f"user:{uid}/note:{nid}" for uid, nid in equiv_fan_in_q.limit(MAX_SAMPLE_IDS).all()
    ]

    divergent_fan_in_q = (
        db.session.query(valid_progress_group_subq.c.user_id, valid_progress_group_subq.c.note_id)
        .filter(valid_progress_group_subq.c.progress_count > 1, ~is_equivalent_fan_in_expr)
        .order_by(valid_progress_group_subq.c.user_id.asc(), valid_progress_group_subq.c.note_id.asc())
    )
    divergent_fan_in_groups = _group_count(divergent_fan_in_q)
    divergent_fan_in_samples = [
        f"user:{uid}/note:{nid}" for uid, nid in divergent_fan_in_q.limit(MAX_SAMPLE_IDS).all()
    ]

    history_fan_in_q = (
        db.session.query(ReviewEvent.user_id, Card.note_id)
        .join(Card, Card.id == ReviewEvent.card_id)
        .group_by(ReviewEvent.user_id, Card.note_id)
        .having(db.func.count(db.distinct(ReviewEvent.card_id)) > 1)
        .order_by(ReviewEvent.user_id.asc(), Card.note_id.asc())
    )
    review_history_fan_in_groups = _group_count(history_fan_in_q)
    history_fan_in_samples = [
        f"user:{uid}/note:{nid}" for uid, nid in history_fan_in_q.limit(MAX_SAMPLE_IDS).all()
    ]

    fsrs_prog_q = (
        db.session.query(CardProgress.id)
        .filter(db.func.lower(CardProgress.scheduler_mode) == "fsrs")
        .order_by(CardProgress.id.asc())
    )
    fsrs_progress_rows = int(
        db.session.query(db.func.count()).select_from(fsrs_prog_q.subquery()).scalar() or 0
    )
    fsrs_samples = _sample_scalars(fsrs_prog_q)

    partial_fsrs_q = (
        db.session.query(CardProgress.id)
        .filter(
            db.or_(
                db.and_(
                    CardProgress.memory_stability.is_(None),
                    CardProgress.memory_difficulty.isnot(None),
                ),
                db.and_(
                    CardProgress.memory_stability.isnot(None),
                    CardProgress.memory_difficulty.is_(None),
                ),
            )
        )
        .order_by(CardProgress.id.asc())
    )
    partial_fsrs_state_rows = int(
        db.session.query(db.func.count()).select_from(partial_fsrs_q.subquery()).scalar() or 0
    )
    partial_fsrs_samples = _sample_scalars(partial_fsrs_q)

    # -------------------------------------------------------------------------
    # 4. Revision Gates
    # -------------------------------------------------------------------------
    zero_revision_q = (
        db.session.query(CardProgress.id)
        .filter(CardProgress.revision == 0)
        .order_by(CardProgress.id.asc())
    )
    zero_revision_rows = int(
        db.session.query(db.func.count()).select_from(zero_revision_q.subquery()).scalar() or 0
    )
    zero_revision_samples = _sample_scalars(zero_revision_q)

    active_revision_q = (
        db.session.query(CardProgress.id)
        .filter(CardProgress.revision > 0)
        .order_by(CardProgress.id.asc())
    )
    active_revision_rows = int(
        db.session.query(db.func.count()).select_from(active_revision_q.subquery()).scalar() or 0
    )
    active_revision_samples = _sample_scalars(active_revision_q)

    invalid_revision_q = (
        db.session.query(CardProgress.id)
        .filter(db.or_(CardProgress.revision.is_(None), CardProgress.revision < 0))
        .order_by(CardProgress.id.asc())
    )
    invalid_revision_rows = int(
        db.session.query(db.func.count()).select_from(invalid_revision_q.subquery()).scalar() or 0
    )
    invalid_revision_samples = _sample_scalars(invalid_revision_q)

    stale_open_revisions_q = (
        db.session.query(StudySessionCard.id)
        .join(StudySession, StudySession.id == StudySessionCard.session_id)
        .join(
            CardProgress,
            db.and_(
                CardProgress.card_id == StudySessionCard.card_id,
                CardProgress.user_id == StudySession.user_id,
            ),
        )
        .filter(
            StudySession.status == "open",
            StudySessionCard.base_progress_revision != CardProgress.revision,
        )
        .order_by(StudySessionCard.id.asc())
    )
    open_session_stale_revisions = int(
        db.session.query(db.func.count()).select_from(stale_open_revisions_q.subquery()).scalar() or 0
    )
    stale_open_revisions_samples = _sample_scalars(stale_open_revisions_q)
    max_observed_revision = int(db.session.query(db.func.max(CardProgress.revision)).scalar() or 0)

    # -------------------------------------------------------------------------
    # 5. Algorithm & Executable Registry Partitioning
    # -------------------------------------------------------------------------
    registered_pairs = set(_REGISTRY.keys())
    registered_algorithms_inventory = [
        {
            "key": k,
            "version": v,
            "state_schema_version": adapter.identity.state_schema_version,
        }
        for (k, v), adapter in sorted(_REGISTRY.items())
    ]

    # Build SQL condition matching registered algorithm/version pairs
    if registered_pairs:
        is_registered_algo_cond = db.or_(
            *[
                db.and_(
                    ReviewEvent.scheduler_algorithm == k,
                    ReviewEvent.algorithm_version == v,
                )
                for k, v in registered_pairs
            ]
        )
    else:
        is_registered_algo_cond = db.literal(False)

    connect_ref_subq = (
        db.session.query(ConnectReviewEventRef.review_event_id)
        .filter(ConnectReviewEventRef.review_event_id.isnot(None))
        .subquery()
    )

    is_anki_import = db.or_(
        ReviewEvent.id.in_(db.session.query(connect_ref_subq.c.review_event_id)),
        db.func.lower(db.func.coalesce(ReviewEvent.scheduler_mode, "")) == "anki",
        db.func.lower(db.func.coalesce(ReviewEvent.scheduler_algorithm, "")) == "anki",
        db.func.lower(db.func.coalesce(ReviewEvent.mode, "")) == "import",
        db.func.lower(db.func.coalesce(ReviewEvent.review_kind, "")) == "import",
    )

    # 1. Registered algorithm events (events matching an active registered executable)
    registered_algo_events_q = (
        db.session.query(ReviewEvent.id)
        .filter(is_registered_algo_cond)
        .order_by(ReviewEvent.id.asc())
    )
    registered_algorithm_events = int(
        db.session.query(db.func.count()).select_from(registered_algo_events_q.subquery()).scalar() or 0
    )

    # 2. Historical imported algorithm events (Anki/external import events with historical non-registry algorithms)
    historical_imported_algo_q = (
        db.session.query(ReviewEvent.id, ReviewEvent.scheduler_algorithm, ReviewEvent.algorithm_version)
        .filter(db.and_(is_anki_import, ~is_registered_algo_cond))
        .order_by(ReviewEvent.id.asc())
    )
    historical_imported_algorithm_events = _group_count(historical_imported_algo_q)
    historical_imported_algo_samples = [
        f"id:{r_id}/algo:{algo}/ver:{ver}"
        for r_id, algo, ver in historical_imported_algo_q.limit(MAX_SAMPLE_IDS).all()
    ]

    # 3. Unregistered native algorithm events (native events specifying non-registered algorithm/version)
    unregistered_native_algo_q = (
        db.session.query(ReviewEvent.id, ReviewEvent.scheduler_algorithm, ReviewEvent.algorithm_version)
        .filter(
            db.and_(
                ~is_anki_import,
                ~is_registered_algo_cond,
                ReviewEvent.scheduler_algorithm.isnot(None),
                ReviewEvent.algorithm_version.isnot(None),
            )
        )
        .order_by(ReviewEvent.id.asc())
    )
    unregistered_native_algorithm_events = _group_count(unregistered_native_algo_q)
    unregistered_native_algo_samples = [
        f"id:{r_id}/algo:{algo}/ver:{ver}"
        for r_id, algo, ver in unregistered_native_algo_q.limit(MAX_SAMPLE_IDS).all()
    ]

    # 4. Missing algorithm version events (native events with algorithm specified but missing version)
    missing_algo_version_q = (
        db.session.query(ReviewEvent.id)
        .filter(
            db.and_(
                ~is_anki_import,
                ReviewEvent.scheduler_algorithm.isnot(None),
                ReviewEvent.algorithm_version.is_(None),
            )
        )
        .order_by(ReviewEvent.id.asc())
    )
    missing_algorithm_version_events = int(
        db.session.query(db.func.count()).select_from(missing_algo_version_q.subquery()).scalar() or 0
    )
    missing_algo_version_samples = _sample_scalars(missing_algo_version_q)

    # 5. NULL algorithm events (native events with NULL scheduler_algorithm)
    null_algo_events_q = (
        db.session.query(ReviewEvent.id)
        .filter(
            db.and_(
                ~is_anki_import,
                ReviewEvent.scheduler_algorithm.is_(None),
            )
        )
        .order_by(ReviewEvent.id.asc())
    )
    null_algorithm_events = int(
        db.session.query(db.func.count()).select_from(null_algo_events_q.subquery()).scalar() or 0
    )
    null_algo_samples = _sample_scalars(null_algo_events_q)

    # FSRS without review provenance
    fsrs_users_subq = (
        db.session.query(ReviewEvent.user_id)
        .filter(
            db.or_(
                ReviewEvent.scheduler_mode == "fsrs",
                ReviewEvent.scheduler_algorithm == "fsrs",
            )
        )
        .distinct()
        .subquery()
    )
    unprovenanced_fsrs_q = (
        db.session.query(CardProgress.id)
        .filter(
            db.func.lower(CardProgress.scheduler_mode) == "fsrs",
            ~CardProgress.user_id.in_(db.session.query(fsrs_users_subq.c.user_id)),
        )
        .order_by(CardProgress.id.asc())
    )
    unprovenanced_fsrs_rows = int(
        db.session.query(db.func.count()).select_from(unprovenanced_fsrs_q.subquery()).scalar() or 0
    )
    unprovenanced_fsrs_samples = _sample_scalars(unprovenanced_fsrs_q)

    # -------------------------------------------------------------------------
    # 6. ReviewEvent Gates & Exhaustive Provenance Accounting
    # -------------------------------------------------------------------------
    orphan_events_q = (
        db.session.query(ReviewEvent.id)
        .outerjoin(Card, Card.id == ReviewEvent.card_id)
        .filter(ReviewEvent.card_id.isnot(None), Card.id.is_(None))
        .order_by(ReviewEvent.id.asc())
    )
    orphan_review_events = int(
        db.session.query(db.func.count()).select_from(orphan_events_q.subquery()).scalar() or 0
    )
    orphan_events_samples = _sample_scalars(orphan_events_q)

    total_review_events_count = int(ReviewEvent.query.count())
    attached_review_events = total_review_events_count - orphan_review_events

    null_session_events_q = (
        db.session.query(ReviewEvent.id)
        .filter(ReviewEvent.study_session_id.is_(None))
        .order_by(ReviewEvent.id.asc())
    )
    null_session_review_events = int(
        db.session.query(db.func.count()).select_from(null_session_events_q.subquery()).scalar() or 0
    )
    null_session_samples = _sample_scalars(null_session_events_q)

    dup_client_q = (
        db.session.query(ReviewEvent.user_id, ReviewEvent.client_event_id)
        .filter(ReviewEvent.client_event_id.isnot(None))
        .group_by(ReviewEvent.user_id, ReviewEvent.client_event_id)
        .having(db.func.count(ReviewEvent.id) > 1)
        .order_by(ReviewEvent.user_id.asc(), ReviewEvent.client_event_id.asc())
    )
    duplicate_client_event_id_groups = _group_count(dup_client_q)
    dup_client_samples = [
        f"user:{uid}/client_event:{cid}" for uid, cid in dup_client_q.limit(MAX_SAMPLE_IDS).all()
    ]

    dup_seq_q = (
        db.session.query(ReviewEvent.study_session_id, ReviewEvent.sequence_no)
        .filter(
            ReviewEvent.study_session_id.isnot(None),
            ReviewEvent.sequence_no.isnot(None),
        )
        .group_by(ReviewEvent.study_session_id, ReviewEvent.sequence_no)
        .having(db.func.count(ReviewEvent.id) > 1)
        .order_by(ReviewEvent.study_session_id.asc(), ReviewEvent.sequence_no.asc())
    )
    duplicate_session_sequence_groups = _group_count(dup_seq_q)
    dup_seq_samples = [
        f"session:{sid}/seq:{sno}" for sid, sno in dup_seq_q.limit(MAX_SAMPLE_IDS).all()
    ]

    missing_seq_q = (
        db.session.query(ReviewEvent.id)
        .filter(
            ReviewEvent.study_session_id.isnot(None),
            ReviewEvent.sequence_no.is_(None),
        )
        .order_by(ReviewEvent.id.asc())
    )
    missing_session_sequence_events = int(
        db.session.query(db.func.count()).select_from(missing_seq_q.subquery()).scalar() or 0
    )
    missing_seq_samples = _sample_scalars(missing_seq_q)

    # Exhaustive Disjoint Provenance Classification
    conflicting_prov_cond = db.and_(
        is_anki_import,
        ReviewEvent.study_session_id.isnot(None),
    )
    conflicting_prov_q = (
        db.session.query(ReviewEvent.id)
        .filter(conflicting_prov_cond)
        .order_by(ReviewEvent.id.asc())
    )
    conflicting_provenance_events = int(
        db.session.query(db.func.count()).select_from(conflicting_prov_q.subquery()).scalar() or 0
    )
    conflicting_prov_samples = _sample_scalars(conflicting_prov_q)

    pure_anki_cond = db.and_(
        is_anki_import,
        ReviewEvent.study_session_id.is_(None),
    )
    anki_import_q = (
        db.session.query(ReviewEvent.id)
        .filter(pure_anki_cond)
        .order_by(ReviewEvent.id.asc())
    )
    anki_import_events = int(
        db.session.query(db.func.count()).select_from(anki_import_q.subquery()).scalar() or 0
    )
    anki_import_samples = _sample_scalars(anki_import_q)

    native_session_cond = db.and_(
        ~is_anki_import,
        ReviewEvent.study_session_id.isnot(None),
    )
    native_session_q = (
        db.session.query(ReviewEvent.id)
        .filter(native_session_cond)
        .order_by(ReviewEvent.id.asc())
    )
    native_session_events = int(
        db.session.query(db.func.count()).select_from(native_session_q.subquery()).scalar() or 0
    )
    native_session_samples = _sample_scalars(native_session_q)

    # Native MCP: client_event_id starts with mcp-/connect-, mode is mcp, or payload indicates source=mcp
    mcp_marker = db.or_(
        db.func.coalesce(ReviewEvent.client_event_id, "").like("mcp-%"),
        db.func.coalesce(ReviewEvent.client_event_id, "").like("connect-%"),
        db.func.lower(db.func.coalesce(ReviewEvent.mode, "")) == "mcp",
        ReviewEvent.payload_json.like('%"source": "mcp"%'),
        ReviewEvent.payload_json.like('%"source":"mcp"%'),
    )
    native_mcp_cond = db.and_(
        ~is_anki_import,
        ReviewEvent.study_session_id.is_(None),
        mcp_marker,
    )
    native_mcp_q = (
        db.session.query(ReviewEvent.id)
        .filter(native_mcp_cond)
        .order_by(ReviewEvent.id.asc())
    )
    native_mcp_events = int(
        db.session.query(db.func.count()).select_from(native_mcp_q.subquery()).scalar() or 0
    )
    native_mcp_samples = _sample_scalars(native_mcp_q)

    # Native batch: mode is batch or client_event_id starts with batch-
    batch_marker = db.or_(
        db.func.lower(db.func.coalesce(ReviewEvent.mode, "")) == "batch",
        db.func.coalesce(ReviewEvent.client_event_id, "").like("batch-%"),
    )
    native_batch_cond = db.and_(
        ~is_anki_import,
        ReviewEvent.study_session_id.is_(None),
        ~mcp_marker,
        batch_marker,
    )
    native_batch_q = (
        db.session.query(ReviewEvent.id)
        .filter(native_batch_cond)
        .order_by(ReviewEvent.id.asc())
    )
    native_batch_events = int(
        db.session.query(db.func.count()).select_from(native_batch_q.subquery()).scalar() or 0
    )
    native_batch_samples = _sample_scalars(native_batch_q)

    # Native direct: explicit channel or runtime evidence (must have explicit payload runtime / source / direct marker)
    direct_marker = db.or_(
        ReviewEvent.payload_json.like('%_study_runtime%'),
        ReviewEvent.payload_json.like('%"source": "direct"%'),
        ReviewEvent.payload_json.like('%"source":"direct"%'),
        ReviewEvent.payload_json.like('%"channel": "direct"%'),
        ReviewEvent.payload_json.like('%"channel":"direct"%'),
        db.func.coalesce(ReviewEvent.client_event_id, "").like("direct-%"),
        db.func.coalesce(ReviewEvent.client_event_id, "").like("rest-%"),
        db.func.coalesce(ReviewEvent.client_event_id, "").like("native-direct-%"),
        db.func.lower(db.func.coalesce(ReviewEvent.mode, "")) == "direct",
    )
    native_direct_cond = db.and_(
        ~is_anki_import,
        ReviewEvent.study_session_id.is_(None),
        ~mcp_marker,
        ~batch_marker,
        direct_marker,
    )
    native_direct_q = (
        db.session.query(ReviewEvent.id)
        .filter(native_direct_cond)
        .order_by(ReviewEvent.id.asc())
    )
    native_direct_events = int(
        db.session.query(db.func.count()).select_from(native_direct_q.subquery()).scalar() or 0
    )
    native_direct_samples = _sample_scalars(native_direct_q)

    # Unknown provenance: all remaining non-classified events
    unknown_prov_cond = db.and_(
        ~is_anki_import,
        ReviewEvent.study_session_id.is_(None),
        ~mcp_marker,
        ~batch_marker,
        ~direct_marker,
    )
    unknown_prov_q = (
        db.session.query(ReviewEvent.id)
        .filter(unknown_prov_cond)
        .order_by(ReviewEvent.id.asc())
    )
    unknown_provenance_events = int(
        db.session.query(db.func.count()).select_from(unknown_prov_q.subquery()).scalar() or 0
    )
    unknown_prov_samples = _sample_scalars(unknown_prov_q)

    # -------------------------------------------------------------------------
    # 7. Session Gates, Active Leases & Config Integrity
    # -------------------------------------------------------------------------
    open_sessions_q = (
        db.session.query(StudySession.id)
        .filter(StudySession.status == "open")
        .order_by(StudySession.id.asc())
    )
    open_sessions_count = int(
        db.session.query(db.func.count()).select_from(open_sessions_q.subquery()).scalar() or 0
    )

    expired_sessions_q = (
        db.session.query(StudySession.id)
        .filter(
            StudySession.status == "open",
            StudySession.expires_at < observed_at,
        )
        .order_by(StudySession.id.asc())
    )
    expired_open_sessions = int(
        db.session.query(db.func.count()).select_from(expired_sessions_q.subquery()).scalar() or 0
    )
    expired_sessions_samples = _sample_scalars(expired_sessions_q)

    active_open_sessions_q = (
        db.session.query(StudySession.id)
        .filter(
            StudySession.status == "open",
            StudySession.expires_at >= observed_at,
        )
        .order_by(StudySession.id.asc())
    )
    active_open_sessions_count = int(
        db.session.query(db.func.count()).select_from(active_open_sessions_q.subquery()).scalar() or 0
    )
    active_open_sessions_samples = _sample_scalars(active_open_sessions_q)

    committed_sessions_q = (
        db.session.query(StudySession.id)
        .filter(StudySession.status == "committed")
        .order_by(StudySession.id.asc())
    )
    committed_sessions_count = int(
        db.session.query(db.func.count()).select_from(committed_sessions_q.subquery()).scalar() or 0
    )

    cancelled_sessions_q = (
        db.session.query(StudySession.id)
        .filter(StudySession.status == "cancelled")
        .order_by(StudySession.id.asc())
    )
    cancelled_sessions_count = int(
        db.session.query(db.func.count()).select_from(cancelled_sessions_q.subquery()).scalar() or 0
    )

    abandoned_sessions_q = (
        db.session.query(StudySession.id)
        .filter(StudySession.status == "abandoned")
        .order_by(StudySession.id.asc())
    )
    abandoned_sessions_count = int(
        db.session.query(db.func.count()).select_from(abandoned_sessions_q.subquery()).scalar() or 0
    )

    unknown_status_sessions_q = (
        db.session.query(StudySession.id)
        .filter(~StudySession.status.in_(["open", "committed", "cancelled", "abandoned"]))
        .order_by(StudySession.id.asc())
    )
    unknown_status_sessions_count = int(
        db.session.query(db.func.count()).select_from(unknown_status_sessions_q.subquery()).scalar() or 0
    )
    unknown_status_sessions_samples = _sample_scalars(unknown_status_sessions_q)

    missing_snapshot_q = (
        db.session.query(StudySession.id)
        .filter(
            db.or_(
                StudySession.snapshot_hash.is_(None),
                StudySession.snapshot_hash == "",
                StudySession.config_snapshot_json.is_(None),
                StudySession.config_snapshot_json == "",
            )
        )
        .order_by(StudySession.id.asc())
    )
    missing_snapshot_sessions = int(
        db.session.query(db.func.count()).select_from(missing_snapshot_q.subquery()).scalar() or 0
    )
    missing_snapshot_samples = _sample_scalars(missing_snapshot_q)

    # Session JSON snapshot validation & active vs historical session algorithm availability
    invalid_config_sessions: set[str] = set()
    active_unavailable_algo_sessions = []
    historical_retired_algo_sessions = []

    session_card_hashes = (
        db.session.query(
            StudySessionCard.session_id,
            StudySessionCard.scheduler_config_hash,
        )
        .filter(StudySessionCard.scheduler_config_hash.isnot(None))
        .distinct()
        .all()
    )
    hashes_by_session: dict[str, set[str]] = {}
    for sess_id, cfg_hash in session_card_hashes:
        if sess_id not in hashes_by_session:
            hashes_by_session[sess_id] = set()
        if cfg_hash:
            hashes_by_session[sess_id].add(str(cfg_hash))

    all_sessions = db.session.query(
        StudySession.id,
        StudySession.status,
        StudySession.expires_at,
        StudySession.scheduler_algorithm,
        StudySession.algorithm_version,
        StudySession.timezone,
        StudySession.config_snapshot_json,
    ).order_by(StudySession.id.asc()).all()

    for s_id, s_status, s_expires, s_algo, s_ver, s_timezone, s_json in all_sessions:
        is_algo_registered = (str(s_algo or ""), str(s_ver or "")) in registered_pairs
        is_active_lease = (s_status == "open" and (s_expires is None or s_expires >= observed_at))

        if not is_algo_registered:
            if is_active_lease:
                active_unavailable_algo_sessions.append(s_id)
            else:
                historical_retired_algo_sessions.append(s_id)

        if s_json is not None:
            try:
                parsed = json.loads(s_json)
                if not isinstance(parsed, dict):
                    invalid_config_sessions.add(s_id)
                else:
                    required_hashes = hashes_by_session.get(s_id, set())
                    missing_hashes = [h for h in required_hashes if h not in parsed]
                    if missing_hashes:
                        invalid_config_sessions.add(s_id)
                    else:
                        for policy_key, policy in parsed.items():
                            if not _is_valid_session_policy_snapshot(
                                policy_key=str(policy_key),
                                policy=policy,
                                session_algorithm=str(s_algo or ""),
                                session_algorithm_version=str(s_ver or ""),
                                session_timezone=str(s_timezone or ""),
                            ):
                                invalid_config_sessions.add(s_id)
                                break
            except (ValueError, TypeError):
                invalid_config_sessions.add(s_id)

    invalid_config_snapshot_samples = sorted(invalid_config_sessions)[:MAX_SAMPLE_IDS]
    invalid_config_snapshot_count = len(invalid_config_sessions)
    active_unavailable_algo_count = len(active_unavailable_algo_sessions)
    historical_retired_algo_count = len(historical_retired_algo_sessions)

    # -------------------------------------------------------------------------
    # 8. Clone Overlay Gates & Detailed Card Breakdown
    # -------------------------------------------------------------------------
    deck_installs_count = int(DeckInstall.query.count())
    installed_notetypes_count = int(NoteTypeInstall.query.count())
    total_cards_count = int(Card.query.count())

    # Source cards: cards belonging to source decks of active deck installs
    installed_source_subq = (
        db.session.query(DeckMarketplaceItem.source_deck_id)
        .join(DeckInstall, DeckInstall.deck_item_id == DeckMarketplaceItem.id)
        .filter(DeckMarketplaceItem.source_deck_id.isnot(None))
        .subquery()
    )
    installed_source_cards_q = (
        db.session.query(Card.id)
        .join(Note, Note.id == Card.note_id)
        .filter(Note.deck_id.in_(db.session.query(installed_source_subq.c.source_deck_id)))
        .order_by(Card.id.asc())
    )
    installed_deck_cards = _group_count(installed_source_cards_q)
    installed_deck_cards_samples = _sample_scalars(installed_source_cards_q)

    # Local clone added cards: notes in DeckCloneAddedNote
    clone_added_notes_subq = (
        db.session.query(DeckCloneAddedNote.note_id)
        .subquery()
    )
    local_clone_added_cards_q = (
        db.session.query(Card.id)
        .filter(Card.note_id.in_(db.session.query(clone_added_notes_subq.c.note_id)))
        .order_by(Card.id.asc())
    )
    local_clone_added_cards = _group_count(local_clone_added_cards_q)
    local_clone_added_cards_samples = _sample_scalars(local_clone_added_cards_q)

    # Local authored cards: valid cards, Note.deck_id is NOT an installed source deck, and NOT in DeckCloneAddedNote
    local_authored_cards_q = (
        db.session.query(Card.id)
        .join(Note, Note.id == Card.note_id)
        .filter(
            Note.deck_id.isnot(None),
            ~Note.deck_id.in_(db.session.query(installed_source_subq.c.source_deck_id)),
            ~Note.id.in_(db.session.query(clone_added_notes_subq.c.note_id)),
        )
        .order_by(Card.id.asc())
    )
    local_authored_cards = _group_count(local_authored_cards_q)
    local_authored_cards_samples = _sample_scalars(local_authored_cards_q)

    # Unassigned deck cards: Note.deck_id is NULL and NOT in DeckCloneAddedNote
    unassigned_deck_cards_q = (
        db.session.query(Card.id)
        .join(Note, Note.id == Card.note_id)
        .filter(
            Note.deck_id.is_(None),
            ~Note.id.in_(db.session.query(clone_added_notes_subq.c.note_id)),
        )
        .order_by(Card.id.asc())
    )
    unassigned_deck_cards = _group_count(unassigned_deck_cards_q)
    unassigned_deck_cards_samples = _sample_scalars(unassigned_deck_cards_q)

    # Overlay ambiguities: DeckCloneAddedNotes referencing missing note or install without local_deck_id
    overlay_ambiguity_q = (
        db.session.query(DeckCloneAddedNote.id)
        .outerjoin(Note, Note.id == DeckCloneAddedNote.note_id)
        .outerjoin(DeckInstall, DeckInstall.id == DeckCloneAddedNote.deck_install_id)
        .filter(db.or_(Note.id.is_(None), DeckInstall.id.is_(None)))
        .order_by(DeckCloneAddedNote.id.asc())
    )
    overlay_ambiguity_count = int(
        db.session.query(db.func.count()).select_from(overlay_ambiguity_q.subquery()).scalar() or 0
    )
    overlay_ambiguity_samples = _sample_scalars(overlay_ambiguity_q)

    # Algorithm distribution with accurate provenance
    algorithm_rows = (
        db.session.query(
            ReviewEvent.scheduler_mode,
            ReviewEvent.scheduler_algorithm,
            ReviewEvent.algorithm_version,
            db.func.count(ReviewEvent.id),
        )
        .group_by(
            ReviewEvent.scheduler_mode,
            ReviewEvent.scheduler_algorithm,
            ReviewEvent.algorithm_version,
        )
        .order_by(
            ReviewEvent.scheduler_mode.asc(),
            ReviewEvent.scheduler_algorithm.asc(),
            ReviewEvent.algorithm_version.asc(),
        )
        .all()
    )

    algorithm_distribution = []
    for scheduler_mode, algorithm_key, algorithm_version, count in algorithm_rows:
        provenance = "native"
        if scheduler_mode == "anki" or algorithm_key == "anki":
            provenance = "import"
        elif not algorithm_key and not scheduler_mode:
            provenance = "unknown"
        algorithm_distribution.append(
            {
                "scheduler_mode": scheduler_mode,
                "algorithm_key": algorithm_key,
                "algorithm_version": algorithm_version,
                "provenance": provenance,
                "count": int(count or 0),
            }
        )

    # -------------------------------------------------------------------------
    # Aggregated Metrics Payload
    # -------------------------------------------------------------------------
    metrics: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "observed_at": observed_at.isoformat(timespec="seconds"),
        "counts": {
            "note_types": int(NoteType.query.count()),
            "templates": int(Template.query.count()),
            "notes": int(Note.query.count()),
            "cards": total_cards_count,
            "card_progress": int(CardProgress.query.count()),
            "review_events": total_review_events_count,
            "study_sessions": int(StudySession.query.count()),
            "deck_installs": deck_installs_count,
        },
        "template_gates": {
            "note_types_without_templates": note_types_without_templates,
            "note_types_without_templates_samples": empty_nt_samples,
            "note_types_with_single_template": note_types_with_single_template,
            "note_types_with_single_template_samples": single_nt_samples,
            "note_types_with_multiple_templates": note_types_with_multiple_templates,
            "note_types_with_multiple_templates_samples": multi_nt_samples,
            "note_types_with_zero_defaults": note_types_with_zero_defaults,
            "note_types_with_zero_defaults_samples": zero_defaults_samples,
            "note_types_with_single_default": note_types_with_single_default,
            "note_types_with_single_default_samples": single_default_samples,
            "note_types_with_multiple_defaults": note_types_with_multiple_defaults,
            "note_types_with_multiple_defaults_samples": multi_defaults_samples,
            "default_count_anomalies": template_default_anomalies,
            "default_count_anomalies_samples": default_anom_samples,
            "duplicate_name_groups": duplicate_template_names,
            "duplicate_name_samples": dup_names_samples,
            "duplicate_position_groups": duplicate_template_positions,
            "duplicate_position_samples": dup_pos_samples,
            "cross_note_type_cards": cross_note_type_cards,
            "cross_note_type_cards_samples": cross_cards_samples,
        },
        "card_gates": {
            "notes_without_cards": notes_without_cards,
            "notes_without_cards_samples": notes_without_cards_samples,
            "notes_with_single_card": notes_with_single_card,
            "notes_with_single_card_samples": notes_with_single_card_samples,
            "notes_with_multiple_cards": notes_with_multiple_cards,
            "notes_with_multiple_cards_samples": notes_with_multi_cards_samples,
            "orphan_cards": orphan_cards_count,
            "orphan_cards_samples": orphan_cards_samples,
        },
        "progress_gates": {
            "null_card_id_rows": null_progress_subjects,
            "null_card_id_samples": null_progress_samples,
            "orphan_card_id_rows": orphan_progress_subjects,
            "orphan_card_id_samples": orphan_progress_samples,
            "orphan_note_id_rows": orphan_note_progress_subjects,
            "orphan_note_id_samples": orphan_note_progress_samples,
            "unresolvable_progress_subjects": unresolvable_progress_subjects,
            "unresolvable_progress_samples": unresolvable_progress_samples,
            "single_card_progress_groups": single_card_progress_groups,
            "single_card_progress_samples": single_card_progress_samples,
            "single_card_progress_rows": single_card_progress_rows,
            "learner_note_fan_in_groups": progress_fan_in_groups,
            "learner_note_fan_in_samples": fan_in_samples,
            "fan_in_card_progress_rows": fan_in_rows_sum,
            "equivalent_fan_in_groups": equivalent_fan_in_groups,
            "equivalent_fan_in_samples": equivalent_fan_in_samples,
            "divergent_fan_in_groups": divergent_fan_in_groups,
            "divergent_fan_in_samples": divergent_fan_in_samples,
            "learner_note_history_fan_in_groups": review_history_fan_in_groups,
            "learner_note_history_fan_in_samples": history_fan_in_samples,
            "fsrs_rows": fsrs_progress_rows,
            "fsrs_samples": fsrs_samples,
            "partial_fsrs_state_rows": partial_fsrs_state_rows,
            "partial_fsrs_samples": partial_fsrs_samples,
        },
        "revision_gates": {
            "zero_revision_rows": zero_revision_rows,
            "zero_revision_samples": zero_revision_samples,
            "active_revision_rows": active_revision_rows,
            "active_revision_samples": active_revision_samples,
            "invalid_revision_rows": invalid_revision_rows,
            "invalid_revision_samples": invalid_revision_samples,
            "open_session_stale_revisions": open_session_stale_revisions,
            "open_session_stale_samples": stale_open_revisions_samples,
            "max_observed_revision": max_observed_revision,
        },
        "algorithm_gates": {
            "registered_algorithm_count": len(registered_pairs),
            "active_registry_executables": registered_algorithms_inventory,
            "registered_algorithm_events": registered_algorithm_events,
            "historical_imported_algorithm_events": historical_imported_algorithm_events,
            "historical_imported_algo_samples": historical_imported_algo_samples,
            "unregistered_native_algorithm_events": unregistered_native_algorithm_events,
            "unregistered_native_algo_samples": unregistered_native_algo_samples,
            "unregistered_algorithm_events": unregistered_native_algorithm_events,
            "missing_algorithm_version_events": missing_algorithm_version_events,
            "missing_algo_version_samples": missing_algo_version_samples,
            "unprovenanced_fsrs_rows": unprovenanced_fsrs_rows,
            "unprovenanced_fsrs_samples": unprovenanced_fsrs_samples,
        },
        "review_event_gates": {
            "orphan_card_id_events": orphan_review_events,
            "orphan_card_id_samples": orphan_events_samples,
            "attached_review_events": attached_review_events,
            "null_session_id_events": null_session_review_events,
            "null_session_id_samples": null_session_samples,
            "null_algorithm_events": null_algorithm_events,
            "null_algorithm_samples": null_algo_samples,
            "duplicate_client_event_id_groups": duplicate_client_event_id_groups,
            "duplicate_client_samples": dup_client_samples,
            "duplicate_session_sequence_groups": duplicate_session_sequence_groups,
            "duplicate_seq_samples": dup_seq_samples,
            "missing_session_sequence_events": missing_session_sequence_events,
            "missing_seq_samples": missing_seq_samples,
            "anki_import_events": anki_import_events,
            "anki_import_samples": anki_import_samples,
            "native_session_events": native_session_events,
            "native_session_samples": native_session_samples,
            "native_direct_events": native_direct_events,
            "native_direct_samples": native_direct_samples,
            "native_mcp_events": native_mcp_events,
            "native_mcp_samples": native_mcp_samples,
            "native_batch_events": native_batch_events,
            "native_batch_samples": native_batch_samples,
            "conflicting_provenance_events": conflicting_provenance_events,
            "conflicting_provenance_samples": conflicting_prov_samples,
            "unknown_provenance_events": unknown_provenance_events,
            "unknown_provenance_samples": unknown_prov_samples,
        },
        "session_gates": {
            "open_sessions": open_sessions_count,
            "active_open_sessions": active_open_sessions_count,
            "active_open_sessions_samples": active_open_sessions_samples,
            "expired_open_sessions": expired_open_sessions,
            "expired_open_sessions_samples": expired_sessions_samples,
            "committed_sessions": committed_sessions_count,
            "cancelled_sessions": cancelled_sessions_count,
            "abandoned_sessions": abandoned_sessions_count,
            "unknown_status_sessions": unknown_status_sessions_count,
            "unknown_status_sessions_samples": unknown_status_sessions_samples,
            "missing_snapshot_sessions": missing_snapshot_sessions,
            "missing_snapshot_samples": missing_snapshot_samples,
            "invalid_config_snapshot_sessions": invalid_config_snapshot_count,
            "invalid_config_snapshot_samples": invalid_config_snapshot_samples,
            "active_session_unavailable_algorithm_sessions": active_unavailable_algo_count,
            "active_session_unavailable_algo_samples": active_unavailable_algo_sessions[:MAX_SAMPLE_IDS],
            "historical_session_retired_algorithm_sessions": historical_retired_algo_count,
            "historical_session_retired_algo_samples": historical_retired_algo_sessions[:MAX_SAMPLE_IDS],
            "unavailable_session_algorithm_sessions": active_unavailable_algo_count,
        },
        "clone_overlay_gates": {
            "deck_installs_count": deck_installs_count,
            "installed_notetypes_count": installed_notetypes_count,
            "installed_deck_cards": installed_deck_cards,
            "installed_deck_cards_samples": installed_deck_cards_samples,
            "local_clone_added_cards": local_clone_added_cards,
            "local_clone_added_cards_samples": local_clone_added_cards_samples,
            "local_authored_cards": local_authored_cards,
            "local_authored_cards_samples": local_authored_cards_samples,
            "unassigned_deck_cards": unassigned_deck_cards,
            "unassigned_deck_cards_samples": unassigned_deck_cards_samples,
            "overlay_ambiguity_count": overlay_ambiguity_count,
            "overlay_ambiguity_samples": overlay_ambiguity_samples,
        },
        "review_event_algorithm_distribution": algorithm_distribution,
    }

    # 1. Build machine-readable inventory
    inventory = _build_disposition_inventory(metrics)
    metrics["inventory"] = inventory

    # 2. Derive single-source verdicts directly from inventory
    verdicts = _categorize_verdicts(inventory)
    metrics["verdicts"] = verdicts

    # -------------------------------------------------------------------------
    # Exhaustive Disjoint Reconciliation Accounting Formulas (11/11 Verified)
    # -------------------------------------------------------------------------
    total_cp = metrics["counts"]["card_progress"]
    total_rev = metrics["counts"]["review_events"]
    total_sess = metrics["counts"]["study_sessions"]
    total_nt = metrics["counts"]["note_types"]
    total_cards = metrics["counts"]["cards"]

    # 1. CardProgress accounting: single + fan_in_rows + unresolvable == total_cp
    progress_accounting = (single_card_progress_rows + fan_in_rows_sum + unresolvable_progress_subjects == total_cp)

    # 2. Fan-in group consistency: equivalent + divergent == fan_in_groups
    fan_in_consistency = (equivalent_fan_in_groups + divergent_fan_in_groups == progress_fan_in_groups)

    # 3. Revision accounting: zero + active + invalid == total_cp
    revision_accounting = (zero_revision_rows + active_revision_rows + invalid_revision_rows == total_cp)

    # 4. ReviewEvents attached vs orphan accounting
    review_events_attached = (attached_review_events + orphan_review_events == total_rev)

    # 5. ReviewEvents provenance accounting: all disjoint categories sum to total_rev
    provenance_sum = (
        anki_import_events
        + native_session_events
        + native_mcp_events
        + native_batch_events
        + native_direct_events
        + conflicting_provenance_events
        + unknown_provenance_events
    )
    review_events_provenance = (provenance_sum == total_rev)

    # 6. ReviewEvents algorithm accounting: registered + historical_imported + unregistered_native + missing_version + null_algo == total_rev
    algorithm_events_sum = (
        registered_algorithm_events
        + historical_imported_algorithm_events
        + unregistered_native_algorithm_events
        + missing_algorithm_version_events
        + null_algorithm_events
    )
    review_events_algorithm = (algorithm_events_sum == total_rev)

    # 7. StudySession status accounting: open + committed + cancelled + abandoned + unknown == total_sess
    sessions_status_sum = (
        open_sessions_count
        + committed_sessions_count
        + cancelled_sessions_count
        + abandoned_sessions_count
        + unknown_status_sessions_count
    )
    sessions_accounting = (sessions_status_sum == total_sess)

    # 8. Open sessions partitioning: active + expired == open
    open_sessions_accounting = (active_open_sessions_count + expired_open_sessions == open_sessions_count)

    # 9. NoteTypes template defaults accounting: without_templates + zero_defaults + single_default + multi_defaults == total_nt
    notetypes_template_sum = (
        note_types_without_templates
        + note_types_with_zero_defaults
        + note_types_with_single_default
        + note_types_with_multiple_defaults
    )
    notetypes_accounting = (notetypes_template_sum == total_nt)

    # 10. Cards overlay accounting: installed_source + local_clone_added + local_authored + unassigned + orphan == total_cards
    cards_overlay_sum = (
        installed_deck_cards
        + local_clone_added_cards
        + local_authored_cards
        + unassigned_deck_cards
        + orphan_cards_count
    )
    cards_overlay_accounting = (cards_overlay_sum == total_cards)

    # 11. Inventory vs Verdict accounting: number of non-pass items in inventory equals total warnings + blockers in verdict
    non_pass_inventory_count = len([i for i in inventory if i["severity"] != "pass"])
    verdict_anomaly_count = len(verdicts["warn"]) + len(verdicts["block"])
    inventory_verdict_accounting = (non_pass_inventory_count == verdict_anomaly_count)

    formula_checks = {
        "card_progress_accounting": progress_accounting,
        "card_progress_fan_in_consistency": fan_in_consistency,
        "card_progress_revision_accounting": revision_accounting,
        "review_events_attached_accounting": review_events_attached,
        "review_events_provenance_accounting": review_events_provenance,
        "review_events_algorithm_accounting": review_events_algorithm,
        "study_sessions_status_accounting": sessions_accounting,
        "study_sessions_open_accounting": open_sessions_accounting,
        "note_types_template_accounting": notetypes_accounting,
        "cards_clone_overlay_accounting": cards_overlay_accounting,
        "inventory_verdict_accounting": inventory_verdict_accounting,
    }
    reconciliation_valid = all(formula_checks.values())
    if not reconciliation_valid:
        failed_checks = [k for k, v in formula_checks.items() if not v]
        verdicts["overall_status"] = "BLOCK"
        verdicts["exit_code"] = 2
        verdicts["block"].append(
            f"reconciliation_drift: Accounting reconciliation failed on checks: {', '.join(failed_checks)}"
        )

    metrics["reconciliation"] = {
        "status": "VALID" if reconciliation_valid else "DRIFT_DETECTED",
        "formula_checks": formula_checks,
        "verified_tables": [
            "note_types",
            "templates",
            "notes",
            "cards",
            "card_progress",
            "review_events",
            "study_sessions",
            "study_session_cards",
            "deck_installs",
            "deck_marketplace_items",
            "deck_clone_added_notes",
            "note_type_installs",
            "connect_review_event_refs",
        ],
    }

    return metrics
