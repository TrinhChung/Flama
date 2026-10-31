#!/usr/bin/env python3
"""
Flama Modular Test Runner
=========================
Fast, modular test execution engine that runs only the tests related to
modified files or explicitly targeted modules.

Usage:
  python scripts/run_tests.py --changed               # Run tests for all git-modified files
  python scripts/run_tests.py --module study          # Run tests for a specific domain module
  python scripts/run_tests.py --module auth,payment   # Run tests for multiple modules
  python scripts/run_tests.py --backend-only          # Limit to backend unittest
  python scripts/run_tests.py --frontend-only         # Limit to frontend vitest
  python scripts/run_tests.py --all                   # Run entire test suite
  python scripts/run_tests.py --list-modules          # Inspect all modules & test files
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import fnmatch
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Repo root directory
ROOT_DIR = Path(__file__).resolve().parent.parent
# Direct CLI execution starts with scripts/ on sys.path; helpers live in the repo package.
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# -----------------------------------------------------------------------------
# Module Mapping Definitions
# -----------------------------------------------------------------------------

MODULES: dict[str, dict[str, list[str]]] = {
    "auth": {
        "source_patterns": [
            "app/api/v1/identity/**",
            "app/api/v1/profile/**",
            "app/services/*auth*.py",
            "app/services/identity*.py",
            "app/services/email_verification*.py",
            "app/services/password_*.py",
            "app/services/login_*.py",
            "app/services/profile_service.py",
            "app/services/student_verification_service.py",
            "app/services/user_api_token_service.py",
            "app/services/email_service.py",
            "app/email/**",
            "app/routes/auth.py",
            "app/validators/password.py",
            "models/user.py",
            "models/user_identity.py",
            "models/email_verification_token.py",
            "models/password_reset_token.py",
            "models/user_api_token.py",
            "frontend/src/features/profile/**",
        ],
        "backend_tests": [
            "tests/test_auth_security.py",
            "tests/test_google_auth.py",
            "tests/test_study_new_learner_note_enrollment.py",
            "tests/test_password_reset_api.py",
            "tests/test_student_email_verification.py",
            "tests/test_transactional_email_service.py",
            "tests/test_profile_api.py",
        ],
        "frontend_tests": [
            "src/features/profile/schemas.test.ts",
            "src/features/profile/components/ProfileEditDialog.test.tsx",
        ],
    },
    "study": {
        "source_patterns": [
            "app/services/anki_scheduler.py",
            "app/services/study_*.py",
            "scripts/probe_p5_study_batch_mysql.py",
            "scripts/probe_p5_study_consumer.py",
            "scripts/probe_p5_numeric_storage_mysql.py",
            "scripts/probe_p5_direct_replay_mysql.py",
            "scripts/probe_p5_concurrency_mysql.py",
            "scripts/probe_study_session_scaling_mysql.py",
            "scripts/probe_p6_application_schema_mysql.py",
            "scripts/bench_p6_migration_mysql.py",
            "scripts/bench_p9_profile_migration_mysql.py",
            "scripts/probe_p9_connect_fence_mysql.py",
            "scripts/trace_card_progress_callsites.py",
            "scripts/audit_legacy_progress_retirement.py",
            "scripts/archive_retired_tables.py",
            "scripts/bootstrap_historical_schema.py",
            "scripts/prepare_retirement_mysql_rehearsal.py",
            "scripts/verify_retirement_protected_state.py",
            "scripts/probe_retirement_fresh_chain_mysql.py",
            "scripts/benchmark_note_queue_endpoint.py",
            "scripts/probe_note_queue_queries.py",
            "migrations/*retirement*.py",
            "migrations/retired_*.py",
            "migrations/historical_bootstrap_core.py",
            "migrations/versions/20261012_000058_*.py",
            "migrations/versions/20261012_00005*.py",
            "migrations/versions/20261012_00006*.py",
            "scripts/collect_study_retirement_observation.py",
            "scripts/probe_p9_backup_restore_mysql.py",
            "scripts/probe_p10_schema_mysql.py",
            "scripts/mysql_probe_db.py",
            "app/services/audit_connection_safety.py",
            "migrations/versions/20261003_000049_consolidate_note_progress_row.py",
            "migrations/versions/20261003_000050_drop_retired_note_progress_tables.py",
            "migrations/retired_note_progress_tables.py",
            "scripts/probe_p10_drop_mysql.py",
            "deploy/flama-study-retention.service",
            "deploy/flama-study-retention.timer",
            "models/study_application.py",
            "scripts/bench_p5_session_open_mysql.py",
            "scripts/probe_p7_session_retention_mysql.py",
            "app/services/db_errors.py",
            "study_worker.py",
            "deploy/flama-study-worker.service",
            "app/repositories/study_batch_repository.py",
            "app/services/scheduler_config_service.py",
            "app/repositories/study_repository.py",
            "app/repositories/study_queue_repository.py",
            "app/repositories/study_inserted_rows.py",
            "app/repositories/study_authority_repository.py",
            "app/repositories/study_progress_subject_repository.py",
            "app/repositories/card_progress_repository.py",
            "app/repositories/review_event_repository.py",
            "app/repositories/study_card_editor_repository.py",
            "app/validators/review_event.py",
            "app/validators/study_composition.py",
            "app/validators/study_session_wire.py",
            "app/validators/study_note_batch.py",
            "app/routes/flashcards/study.py",
            "app/api/v1/learning/study.py",
            "models/study_session*.py",
            "models/study_progress*.py",
            "models/study_authority*.py",
            "models/review_event.py",
            "models/card_progress.py",
            "models/scheduler_preset.py",
            "models/user_scheduler_settings.py",
            "frontend/src/features/study/**",
        ],
        "backend_tests": [
            "tests/test_anki_scheduler.py",
            "tests/test_study_action_runtime.py",
            "tests/test_study_algorithm_golden_vectors.py",
            "tests/test_study_algorithm_registry.py",
            "tests/test_study_artifact_service.py",
            "tests/test_study_behavior_acceptance_baseline.py",
            "tests/test_study_batch_queue.py",
            "tests/test_study_consumer.py",
            "tests/test_study_deploy_safety.py",
            "tests/test_study_note_batch.py",
            "tests/test_study_note_storage_precision.py",
            "tests/test_study_direct_note_replay.py",
            "tests/test_study_direct_replay_probe.py",
            "tests/test_study_note_write_gap_locks.py",
            "tests/test_study_application_occurrence.py",
            "tests/test_study_note_level_counts.py",
            "tests/test_study_phase6_continuity.py",
            "tests/test_study_session_retention.py",
            "tests/test_study_session_install_usage.py",
            "tests/test_study_consolidated_schema.py",
            "tests/test_study_retired_tables_migration.py",
            "tests/test_study_consolidated_progress.py",
            "tests/test_legacy_progress_retirement_audit.py",
            "tests/test_legacy_model_retirement.py",
            "tests/test_card_progress_retirement_migration.py",
            "tests/test_derived_card_retirement_migration.py",
            "tests/test_derived_card_retirement_scope.py",
            "tests/test_note_query_retirement.py",
            "tests/test_note_due_index_migration.py",
            "tests/test_note_stats_retirement.py",
            "tests/test_retirement_fresh_migration_chain.py",
            "tests/test_study_consolidated_connect.py",
            "tests/test_study_phase9_readiness.py",
            "tests/test_study_retirement_telemetry.py",
            "tests/test_study_backup_restore_probe.py",
            "tests/test_study_inserted_rows.py",
            "tests/test_study_pristine_bulk_materialization.py",
            "tests/test_study_availability_snapshot.py",
            "tests/test_study_template_application_sessions.py",
            "tests/test_study_template_presets.py",
            "tests/test_study_note_templates.py",
            "tests/test_study_content_delete.py",
            "tests/test_study_note_overlay.py",
            "tests/test_study_algorithm_switch.py",
            "tests/test_study_composition_exit_gate.py",
            "tests/test_study_composition_service.py",
            "tests/test_study_integration.py",
            "tests/test_review_event_provenance.py",
            "tests/test_study_session_api.py",
            "tests/test_study_session_wire_contract.py",
            "tests/test_study_session_authority_pin.py",
            "tests/test_study_session_authority_pin_service.py",
            "tests/test_study_progress_shadow_codec.py",
            "tests/test_study_authority_schema.py",
            "tests/test_study_storage_profile.py",
            "tests/test_study_authority_note_enrollment.py",
            "tests/test_study_new_learner_note_enrollment.py",
            "tests/test_study_authority_receipt.py",
            "tests/test_study_authority_projection_comparator.py",
            "tests/test_study_note_card_projection.py",
            "tests/test_study_authority_cas.py",
            "tests/test_study_authority_sibling_repository.py",
            "tests/test_study_authority_repository.py",
            "tests/test_study_queue_metadata.py",
            "tests/test_study_session_scaling.py",
            "tests/test_scheduler_schema.py",
            "tests/test_stats_study_time.py",
            "tests/test_review_analytics_study_integration.py",
            "tests/test_deck_count_projection.py",
            "tests/test_study_typing_template.py",
        ],
        "frontend_tests": [
            "src/features/study/typing/typingAnswer.test.ts",
            "src/features/study/components/StudyTypingAnswerPanel.test.tsx",
            "src/features/study/components/CardDisplay.test.tsx",
            "src/features/study/components/CardRendererFrame.test.tsx",
            "src/features/study/components/CardRendererHost.test.ts",
            "src/features/study/components/StudyHeaderToolbar.test.tsx",
            "src/features/study/components/StudyModeSelector.test.tsx",
            "src/features/study/components/StudyQuickEditDialog.test.tsx",
            "src/features/study/components/StudySessionConflict.test.tsx",
            "src/features/study/components/StudyTemplateFieldsDialog.test.tsx",
            "src/features/study/components/StudyTemplatePreparation.test.tsx",
            "src/features/study/components/StudyWaitingCard.test.tsx",
            "src/features/study/hooks/useStudySession.test.tsx",
            "src/features/study/interactions/ReviewInteractionControls.test.tsx",
            "src/features/study/interactions/reviewInteraction.test.ts",
            "src/features/study/pages/StudyPage.test.tsx",
            "src/features/study/queries.test.ts",
            "src/features/study/renderer/clientRenderer.test.ts",
            "src/features/study/scheduler/legacyEngine.golden.test.ts",
            "src/features/study/scheduler/legacyEngine.test.ts",
            "src/features/study/scheduler/algorithmRegistry.test.ts",
            "src/features/study/scheduler/noteStoragePrecision.test.ts",
            "src/features/study/session/contentPatchAdapter.test.ts",
            "src/features/study/session/contentPatchAdapter.adversarial.test.ts",
            "src/features/study/session/sessionRestore.test.ts",
            "src/features/study/session/sessionStorageCodec.test.ts",
            "src/features/study/session/sessionStore.test.ts",
            "src/features/study/session/studySessionEngine.test.ts",
            "src/features/study/session/studySessionLease.test.ts",
            "src/features/study/session/wireContract.test.ts",
        ],
    },
    "browse": {
        "source_patterns": [
            "app/api/v1/learning/__init__.py",
            "app/api/v1/learning/browse.py",
            "app/services/browse_card_service.py",
            "app/services/browse_note_service.py",
            "app/services/browse_deck_service.py",
            "app/repositories/browse_card_repository.py",
            "app/repositories/browse_note_repository.py",
            "app/repositories/browse_deck_repository.py",
            "app/repositories/browse_search_repository.py",
            "app/repositories/logical_overlay_scope_repository.py",
            "app/presenters/vocabulary_presenter.py",
            "app/routes/vocabulary.py",
            "app/validators/browse_note.py",
            "app/validators/browse_decks.py",
            "scripts/benchmark_browse_mysql.py",
            "frontend/src/features/browse/**",
            "frontend/src/pages/browse/**",
        ],
        "backend_tests": [
            "tests/test_browse_query_bounds.py",
            "tests/test_browse_baseline_tool.py",
            "tests/test_browse_notes_mysql.py",
            "tests/test_browse_scope_optimization_mysql.py",
            "tests/test_browse_deck_summary_mysql.py",
            "tests/test_flashcard_api_integration.py",
            "tests/test_flashcard_validation_security.py",
            "tests/test_rest_api_v1.py",
            "tests/test_study_note_overlay.py",
        ],
        "frontend_tests": [
            "src/features/browse/api/browseApi.test.ts",
            "src/features/browse/api/deckSummaryLoader.test.ts",
            "src/features/browse/hooks/useBrowseState.test.tsx",
            "src/features/browse/hooks/useBrowsePaginationData.test.tsx",
            "src/features/browse/components/BrowseCardTable.test.tsx",
            "src/features/browse/components/MediaFieldPreview.test.tsx",
            "src/features/browse/components/BrowseAudioSelectorModal.test.tsx",
            "src/features/browse/components/BrowsePagination.test.tsx",
            "src/pages/browse/ui/BrowsePage.test.tsx",
            "src/pages/browse/ui/BrowsePage.contract.test.tsx",
            "src/features/browse/components/BrowseStrokeModal.test.tsx",
            "src/features/browse/components/BrowseTtsModal.test.tsx",
            "src/features/browse/services/strokeStorage.test.ts",
            "src/features/browse/services/ttsSettingsStorage.test.ts",
        ],
    },
    "flashcards": {
        "source_patterns": [
            "app/api/v1/flashcards/**",
            "app/api/v1/strokes/**",
            "app/api/v1/images.py",
            "app/services/flashcard_*.py",
            "app/services/field_*.py",
            "app/repositories/field_value_identity_repository.py",
            "scripts/cutover_field_value_identity.py",
            "scripts/probe_field_identity_mysql.py",
            "scripts/probe_field_identity_cutover_mysql.py",
            "scripts/probe_field_value_consumers_mysql.py",
            "app/repositories/field_value_query_repository.py",
            "app/repositories/media_field_identity_repository.py",
            "app/repositories/media_audit_identity_repository.py",
            "app/services/clone_field_identity_service.py",
            "app/services/note_value_precondition_service.py",
            "models/field_value_identity_definition.py",
            "migrations/versions/*_000063_*.py",
            "migrations/versions/*_000066_*.py",
            "migrations/versions/*_000067_*.py",
            "migrations/field_identity_contract.py",
            "app/services/anki_import_service.py",
            "app/services/anki_content_normalizer.py",
            "app/services/image_*.py",
            "app/services/remote_image_fetcher.py",
            "app/services/stroke*.py",
            "app/repositories/flashcard*.py",
            "app/repositories/image_library_repository.py",
            "app/routes/flashcards/**",
            "app/routes/image_library.py",
            "app/routes/media_asset_routes.py",
            "app/services/media_field_codec.py",
            "app/services/media_staging_service.py",
            "app/services/note_management_service.py",
            "app/services/note_type_service.py",
            "app/validators/flashcard_input.py",
            "app/validators/field_*.py",
            "app/validators/image_*.py",
            "models/flashcard.py",
            "models/note*.py",
            "models/field_def*.py",
            "models/field_types.py",
            "models/template.py",
            "models/card.py",
            "models/image_asset.py",
            "models/shared_image_asset.py",
            "models/media_asset.py",
            "frontend/src/features/import/**",
            "frontend/src/features/import/lib/ankiHtmlSanitizer*",
        ],
        "backend_tests": [
            "tests/test_flashcard_api_integration.py",
            "tests/test_field_value_identity.py",
            "tests/test_field_identity_schema.py",
            "tests/test_field_identity_cutover.py",
            "tests/test_field_value_consumers.py",
            "tests/test_field_identity_deploy.py",
            "tests/test_flashcard_audio_scan.py",
            "tests/test_flashcard_import_media_validation.py",
            "tests/test_flashcard_import_mapping.py",
            "tests/test_flashcard_media_batch_api.py",
            "tests/test_flashcard_media_migration.py",
            "tests/test_flashcard_media_normalizer.py",
            "tests/test_flashcard_renderer.py",
            "tests/test_flashcard_renderer_strokes.py",
            "tests/test_flashcard_validation_security.py",
            "tests/test_deploy_environment_consistency.py",
            "tests/test_media_staging_service.py",
            "tests/test_batch_flashcard_import.py",
            "tests/test_anki_import_api.py",
            "tests/test_image_crawl_service.py",
            "tests/test_image_library.py",
            "tests/test_image_library_schema.py",
            "tests/test_image_upload_csrf.py",
            "tests/test_remote_image_fetcher.py",
            "tests/test_secure_image_pipeline.py",
            "tests/test_cjk_extractor.py",
            "tests/test_counter_logic.py",
            "tests/test_api_strokes.py",
            "tests/test_stroke_service.py",
            "tests/test_worksheet_stroke_cache.py",
            "tests/test_field_array_conversion.py",
            "tests/test_array_cutover.py",
        ],
        "frontend_tests": [
            "src/features/import/lib/ankiHtmlSanitizer.test.ts",
            "src/entities/deck/ui/DeckSelectionTreeView.test.tsx",
        ],
    },
    "templates": {
        "source_patterns": [
            "app/api/v1/flashcards/card_templates.py",
            "app/services/template_*.py",
            "app/services/effective_template_service.py",
            "app/services/study_template_preset_service.py",
            "app/services/release_core/**",
            "app/repositories/template_*.py",
            "app/repositories/legacy_template_provenance_repository.py",
            "app/repositories/note_type_*repository.py",
            "app/services/legacy_template_provenance_service.py",
            "app/services/note_type_bundle_*.py",
            "app/services/note_type_release_service.py",
            "scripts/probe_legacy_template_provenance_mysql.py",
            "scripts/probe_marketplace_quote_access_mysql.py",
            "scripts/probe_note_type_bundle_mysql.py",
            "scripts/probe_note_type_releases_mysql.py",
            "scripts/probe_template_pin_isolation_mysql.py",
            "scripts/probe_template_bindings_mysql.py",
            "scripts/probe_template_sync_mysql.py",
            "app/validators/template_library.py",
            "app/validators/template_preview.py",
            "models/template*.py",
            "models/study_template_preset.py",
            "models/deck_release_template_pin.py",
            "migrations/versions/20261007_000053_add_template_versions.py",
            "migrations/versions/20261007_000054_expand_template_attachments.py",
            "migrations/versions/20261007_000055_add_template_distribution.py",
            "docs/task/template-features/tools/verify_template*mysql.py",
            "frontend/src/entities/card-template/**",
            "frontend/src/entities/flashcard/ui/CardPreviewPanel*",
            "frontend/src/entities/flashcard/ui/CardSideToggle*",
            "frontend/src/shared/ui/SplitPane*",
            "frontend/src/shared/ui/WorkspaceLayout*",
            "frontend/src/features/note-types/**",
            "frontend/src/pages/note-type-template-mapping/**",
            "frontend/src/features/template-library/**",
            "frontend/src/features/template-versions/**",
            "frontend/src/features/template-distribution/**",
            "frontend/src/features/template-applications/**",
            "frontend/src/features/library/pages/InstallTemplatesPage*",
            "frontend/src/features/study/hooks/useStudyTemplatePreparation*",
            "frontend/src/features/study/components/StudyTemplateFieldsDialog*",
            "frontend/src/features/study/components/StudyTemplatePreparation*"
        ],
        "backend_tests": [
            "tests/test_adversarial_template_features.py",
            "tests/test_effective_template_service.py",
            "tests/test_template_default_content.py",
            "tests/test_template_note_count.py",
            "tests/test_template_tokens.py",
            "tests/test_template_versions.py",
            "tests/test_template_versions_contract.py",
            "tests/test_template_versions_migration.py",
            "tests/test_template_attachment_migration.py",
            "tests/test_template_distribution_migration.py",
            "tests/test_template_binding_service.py",
            "tests/test_template_input_policy.py",
            "tests/test_template_library.py",
            "tests/test_template_preview_samples.py",
            "tests/test_template_library_fe_contract.py",
            "tests/test_template_release_service.py",
            "tests/test_note_type_install_locking_mysql.py",
            "tests/test_legacy_template_provenance.py",
            "tests/test_note_type_bundle_pricing.py",
            "tests/test_note_type_bundle_publication.py",
            "tests/test_payment_quote_replacement.py",
            "tests/test_template_marketplace.py",
            "tests/test_template_pinned_content.py",
            "tests/test_template_deck_release.py",
            "tests/test_template_attachment_writers.py",
            "tests/test_template_origin_retirement.py",
            "tests/test_template_origin_retirement_migration.py",
            "tests/test_template_pinned_new_install.py",
            "tests/test_study_template_application_sessions.py",
            "tests/test_study_template_presets.py"
        ],
        "frontend_tests": [
            "src/entities/card-template/api/cardTemplateApi.test.ts",
            "src/entities/card-template/api/cardTemplateApi.adversarial.test.ts",
            "src/entities/card-template/lib/fieldMapping.test.ts",
            "src/entities/card-template/lib/previewSamples.test.ts",
            "src/entities/card-template/lib/lineDiff.test.ts",
            "src/entities/card-template/ui/TemplateCodeEditor.test.tsx",
            "src/entities/card-template/ui/TemplateDiffView.test.tsx",
            "src/entities/card-template/ui/FieldMappingEditor.test.tsx",
            "src/entities/card-template/ui/SampleValuesSheet.test.tsx",
            "src/entities/flashcard/ui/CardPreviewPanel.test.tsx",
            "src/shared/ui/SplitPane.test.tsx",
            "src/shared/ui/WorkspaceLayout.test.tsx",
            "src/features/template-library/components/CreateTemplateDialog.test.tsx",
            "src/features/template-library/components/TemplateInputSchemaEditor.test.tsx",
            "src/features/template-library/components/TemplateInputsDialog.test.tsx",
            "src/features/template-library/components/AttachTemplateDialog.test.tsx",
            "src/features/template-library/components/ApplyTemplateWizard.test.tsx",
            "src/features/template-library/components/TemplateApplicationsPanel.test.tsx",
            "src/features/template-library/lib/inputSchemaValidation.test.ts",
            "src/features/template-library/lib/templateInputReferences.test.ts",
            "src/features/template-library/hooks/useTemplateLibraryEditor.test.tsx",
            "src/features/template-library/pages/TemplateLibraryPage.test.tsx",
            "src/features/template-library/pages/TemplateDetailPage.test.tsx",
            "src/features/template-library/pages/TemplateLocalization.test.tsx",
            "src/features/template-library/pages/TemplateLibraryShell.test.tsx",
            "src/features/template-versions/ui/TemplateVersionHistorySheet.test.tsx",
            "src/features/template-distribution/ui/TemplateDistributionPanel.test.tsx",
            "src/features/note-types/lib/templateErrors.test.ts",
            "src/features/note-types/pages/NoteTypeDetailPage.editor.test.tsx",
            "src/features/note-types/pages/NoteTypeDetailPage.draft.test.tsx",
            "src/features/note-types/components/fields/FieldListCard.test.tsx",
            "src/features/note-types/components/fields/FieldEditorPreview.test.tsx",
            "src/features/note-types/hooks/useTemplateMappingDraft.test.ts",
            "src/pages/note-type-template-mapping/NoteTypeTemplateMappingPage.test.tsx",
            "src/shared/hooks/useUnsavedChangesGuard.test.tsx",
            "src/features/study/hooks/useStudySession.test.tsx",
            "src/features/study/pages/StudyPage.test.tsx",
            "src/features/study/session/contentPatchAdapter.test.ts",
            "src/features/study/session/contentPatchAdapter.adversarial.test.ts",
            "src/features/study/session/wireContract.test.ts",
            "src/features/study/session/sessionRestore.test.ts",
            "src/features/study/components/StudyQuickEditDialog.test.tsx",
            "src/lib/arrayField.test.ts",
            "src/entities/flashcard/lib/arrayTemplates.test.ts",
            "src/entities/flashcard/lib/typingTemplates.test.ts",
            "src/features/note-types/lib/arrayConversion.test.ts",
            "src/features/note-types/components/fields/FieldArrayConversionDialog.test.tsx",
        ]
    },
    "decks": {
        "source_patterns": [
            "app/api/v1/decks/**",
            "app/api/v1/creator/**",
            "app/services/deck_access_key*.py",
            "app/services/deck_naming*.py",
            "app/services/deck_release*.py",
            "app/services/note_base*.py",
            "app/services/note_draft_service.py",
            "app/services/effective_note_reader.py",
            "app/repositories/note_base_repository.py",
            "models/note_draft.py",
            "scripts/note_base_cutover.py",
            "scripts/bench_note_base_review_mysql.py",
            "scripts/bench_note_published_base_mysql.py",
            "deploy/run_note_base_retention.py",
            "deploy/flama-note-base-retention.service",
            "deploy/flama-note-base-retention.timer",
            "app/services/deck_working_tree*.py",
            "app/services/creator_key_entitlement_service.py",
            "app/services/deck_access_policy.py",
            "app/services/deck_api_service.py",
            "app/services/deck_auto_publish_service.py",
            "app/services/deck_management_service.py",
            "app/services/release_core/**",
            "app/repositories/deck_access_key_repository.py",
            "app/repositories/deck_release_repository.py",
            "app/repositories/deck_tree_query.py",
            "app/repositories/vocabulary_repository.py",
            "models/deck.py",
            "models/deck_access_key*.py",
            "models/deck_release*.py",
            "models/deck_working_dirty_entity.py",
            "frontend/src/features/dashboard/**",
            "frontend/src/pages/dashboard/**",
            "frontend/src/entities/study-overview/**",
        ],
        "backend_tests": [
            "tests/test_deck_access_keys.py",
            "tests/test_deck_api_hierarchical_create.py",
            "tests/test_deck_auto_publish_and_auto_update.py",
            "tests/test_deck_naming_service.py",
            "tests/test_deck_notetype_guard.py",
            "tests/test_deck_release_api.py",
            "tests/test_deck_release_performance_mysql.py",
            "tests/test_deck_release_schema.py",
            "tests/test_note_base_publish_mysql.py",
            "tests/test_note_base_cutover_mysql.py",
            "tests/test_note_base_reader_mysql.py",
            "tests/test_note_drafts_mysql.py",
            "tests/test_note_base_retention_runner.py",
            "tests/test_deck_settings_routes.py",
            "tests/test_owner_note_dirty_tracking_services.py",
            "tests/test_prune_releases.py",
            "tests/test_vocabulary_deck_tree_batch.py",
        ],
        "frontend_tests": [
            "src/features/dashboard/components/DeckModals.test.tsx",
            "src/features/dashboard/components/DeckTree.test.tsx",
            "src/features/dashboard/utils/deckNaming.test.ts",
            "src/pages/dashboard/ui/DashboardPage.test.tsx",
            "src/pages/dashboard/ui/DashboardPage.queries.test.tsx",
        ],
    },
    "deck_collaboration": {
        "source_patterns": [
            "app/services/change_request/**",
            "app/services/deck_change_request*.py",
            "app/services/deck_install_rebase*.py",
            "app/services/deck_publish_index.py",
            "app/services/flashcards_share*.py",
            "app/services/share/**",
            "app/repositories/deck_change_request*.py",
            "app/repositories/flashcards_share*.py",
            "app/repositories/deck_install_rebase_repository.py",
            "app/routes/flashcards/change_requests.py",
            "app/routes/flashcards/share.py",
            "app/validators/deck_change_request.py",
            "models/deck_change_request*.py",
            "models/deck_install*.py",
            "models/deck_clone*.py",
            "models/note_type_install.py",
            "frontend/src/features/deck-collaboration/**",
            "frontend/src/pages/installed-deck-comparison/**",
        ],
        "backend_tests": [
            "tests/test_deck_change_request_flow.py",
            "tests/test_change_request_selection_unit.py",
            "tests/test_contribution_selection_mysql.py",
            "tests/test_deck_install_rebase_flow.py",
            "tests/test_deck_publish_index.py",
            "tests/test_batched_deck_clone.py",
            "tests/test_shared_deck_detail_ui.py",
            "tests/test_note_type_install_locking_mysql.py",
            "tests/test_shared_state_services.py",
            "tests/test_vocab_seed_sharing.py",
        ],
        "frontend_tests": [
            "src/features/deck-collaboration/api.test.ts",
            "src/features/deck-collaboration/model/noteChanges.test.ts",
            "src/features/deck-collaboration/hooks/refetchFromFirstPage.test.ts",
            "src/shared/hooks/useNearViewport.test.tsx",
            "src/features/deck-collaboration/components/ChangeRequestDetailView.test.tsx",
            "src/features/deck-collaboration/components/DeckContributionForm.test.tsx",
            "src/features/deck-collaboration/components/DiffWorkspace.test.tsx",
            "src/features/deck-collaboration/pages/ChangeRequestInboxPage.test.tsx",
            "src/pages/installed-deck-comparison/InstalledDeckComparisonPage.test.tsx",
        ],
    },
    "marketplace": {
        "source_patterns": [
            "app/api/v1/marketplace/**",
            "scripts/bench_publish_options_mysql.py",
            "app/services/marketplace/**",
            "app/services/marketplace*.py",
            "app/repositories/marketplace_list_repository.py",
            "app/repositories/marketplace_taxonomy_repository.py",
            "models/deck_marketplace_item.py",
            "models/marketplace_saved_item.py",
            "models/taxonomy.py",
            "models/deck_review.py",
            "models/note_type_review.py",
            "frontend/src/features/marketplace/**",
            "frontend/src/entities/marketplace-deck/**",
            "frontend/src/features/library/**",
            "frontend/src/pages/installed-decks/**",
        ],
        "backend_tests": [
            "tests/test_marketplace_filter_taxonomy.py",
            "tests/test_marketplace_query_service.py",
            "tests/test_marketplace_taxonomy_db.py",
            "tests/test_marketplace_taxonomy_migration.py",
            "tests/test_market_counter_deletion.py",
            "tests/test_api_v1_marketplace_note_types.py",
            "tests/test_marketplace_list_performance.py",
        ],
        "frontend_tests": [
            "src/entities/marketplace-deck/ui/DeckCard.test.tsx",
            "src/features/marketplace/components/PublishDeckTree.test.tsx",
            "src/features/marketplace/publishApi.test.ts",
            "src/features/marketplace/pages/MarketplacePages.test.tsx",
        ],
    },
    "connect_mcp": {
        "source_patterns": [
            "app/services/template_authoring_service.py",
            "app/validators/mcp_template_preview.py",
            "app/validators/template_authoring.py",
            "app/services/template_javascript_service.py",
            "app/services/template_diagnostics.py",
            "scripts/build_template_browser_fixtures.py",
            "scripts/probe_mcp_template_preview_mysql.py",
            "scripts/probe_mcp_authoring_mysql.py",
            "app/validators/mcp_authoring.py",
            "scripts/flama_mcp_server.py",
            "scripts/probe_connect_protocol_mysql.py",
            "connect_wsgi.py",
            "app/connect/**",
            "app/services/connect/**",
            "app/services/mcp/**",
            "app/services/flama_connect*.py",
            "app/services/mcp_*.py",
            "app/services/oauth_service.py",
            "app/services/note_sync_service.py",
            "app/services/anki_sync_service.py",
            "app/services/anki_content_normalizer.py",
            "app/api/v1/settings/**",
            "app/repositories/connect_identity_repository.py",
            "app/repositories/mcp_access_token_repository.py",
            "app/repositories/oauth_repository.py",
            "app/routes/mcp.py",
            "app/routes/oauth.py",
            "app/validators/mcp.py",
            "models/connect_*.py",
            "models/mcp_*.py",
            "models/oauth_*.py",
            "frontend/src/features/import/lib/ankiSync*",
        ],
        "backend_tests": [
            "tests/test_template_authoring.py",
            "tests/test_mcp_authoring.py",
            "tests/test_anki_content_normalizer.py",
            "tests/test_anki_connect_origin_adversarial.py",
            "tests/test_flama_connect.py",
            "tests/test_flama_connect_auth.py",
            "tests/test_connect_protocol.py",
            "tests/test_connect_wire_adversarial.py",
            "tests/test_flama_connect_mcp.py",
            "tests/test_mcp_access_tokens.py",
            "tests/test_mcp_http_transport.py",
            "tests/test_mcp_list_my_decks.py",
            "tests/test_mcp_note_concurrency_identity.py",
            "tests/test_mcp_note_type_capabilities.py",
            "tests/test_mcp_production_handshake.py",
            "tests/test_mcp_public_search.py",
            "tests/test_mcp_adversarial_challenge.py",
            "tests/test_mcp_adversarial_challenger.py",
            "tests/test_mcp_taxonomy_metadata.py",
            "tests/test_note_sync_and_mcp.py",
            "tests/test_oauth_mcp.py",
            "tests/test_oauth_mcp_security_regression.py",
            "tests/test_integration_tokens_api.py",
        ],
        "frontend_tests": [
            "src/features/import/lib/ankiSyncEngine.test.ts",
            "src/features/import/lib/ankiSyncPackages.test.ts",
            "src/features/settings/components/__tests__/ConnectMiningSetup.test.tsx",
        ],
    },
    "payment": {
        "source_patterns": [
            "app/api/v1/billing/**",
            "app/api/v1/wallet/**",
            "app/services/payment/**",
            "app/services/payment*.py",
            "app/services/payos*.py",
            "app/services/wallet*.py",
            "app/services/payout*.py",
            "app/services/support_checkout*.py",
            "app/services/support_donation*.py",
            "app/repositories/payment/**",
            "app/repositories/payment_repository.py",
            "app/repositories/payout_repository.py",
            "app/repositories/wallet_repository.py",
            "app/routes/admin_payments.py",
            "app/routes/payments.py",
            "app/routes/user_orders.py",
            "app/validators/payment_*.py",
            "app/validators/payout_input.py",
            "app/validators/support_donation.py",
            "models/payment_*.py",
            "models/payout_*.py",
            "models/user_balance_transaction.py",
            "models/support_donation_config.py",
        ],
        "backend_tests": [
            "tests/test_payment_order_flow.py",
            "tests/test_payment_management_views.py",
            "tests/test_payos_provider.py",
            "tests/test_payos_sdk_absence.py",
            "tests/test_wallet_api.py",
            "tests/test_wallet_revenue_flow.py",
            "tests/test_support_donation_payment_flow.py",
        ],
        "frontend_tests": [],
    },
    "seo": {
        "source_patterns": ["app/routes/seo.py", "app/services/seo_service.py", "scripts/verify_seo_adversarial.py"],
        "backend_tests": [
            "tests/test_seo_routes.py",
            "tests/test_seo_adversarial.py",
            "tests/test_seo_keyword_coverage_adversarial.py",
            "tests/test_schema_jsonld.py",
        ],
        "frontend_tests": [],
    },
    "admin": {
        "source_patterns": [
            "app/api/v1/admin/**",
            "app/services/admin_*.py",
            "app/services/quota_service.py",
            "app/repositories/quota_repository.py",
            "models/quota.py",
            "frontend/src/features/admin/**",
            "app/services/bootstrap_admin*.py",
            "app/services/user_roles.py",
            "app/services/user_management_schema.py",
            "app/repositories/admin_analytics_repository.py",
            "app/routes/admin.py",
            "app/routes/admin_rest_api.py",
            "app/utils/bootstrap_admin.py",
            "models/user_role.py",
            "models/admin_security_alert.py",
            "models/user_permission_audit_log.py",
        ],
        "backend_tests": [
            "tests/test_admin_analytics_api.py",
            "tests/test_admin_fee_config.py",
            "tests/test_admin_quotas_api.py",
            "tests/test_quota_service.py",
            "tests/test_admin_payouts_api.py",
            "tests/test_admin_rest_api_v1.py",
            "tests/test_admin_user_roles.py",
            "tests/test_bootstrap_admin_credentials.py",
            "tests/test_bootstrap_admin_sync.py",
        ],
        "frontend_tests": [
            "src/features/admin/pages/__tests__/AdminMcpTokensBaseline.characterization.test.tsx",
            "src/features/admin/pages/__tests__/AdminQuotasPage.test.tsx",
        ],
    },
    "analytics": {
        "source_patterns": [
            "app/api/v1/analytics/**",
            "app/services/deck_aggregation_service.py",
            "app/services/study_analytics_read_service.py",
            "app/services/analytics_summary_readiness.py",
            "app/services/stats_*.py",
            "app/services/dashboard_service.py",
            "app/repositories/stats_query_repository.py",
            "app/repositories/note_analytics_read_repository.py",
            "app/repositories/note_analytics_scope_repository.py",
            "app/services/review_analytics_*.py",
            "app/repositories/review_analytics_*.py",
            "app/services/deck_count_*.py",
            "app/repositories/deck_count_*.py",
            "app/services/forecast_snapshot_service.py",
            "app/repositories/forecast_snapshot_repository.py",
            "models/forecast_snapshot.py",
            "migrations/versions/*_000064_*.py",
            "scripts/probe_forecast_snapshots_mysql.py",
            "scripts/qualify_progress_scalability_mysql.py",
            "scripts/bench_review_projection_mysql.py",
            "models/review_analytics.py",
            "models/review_analytics_outbox.py",
            "migrations/versions/*_000065_*.py",
            "migrations/versions/*_000068_*.py",
            "scripts/probe_review_analytics_outbox_mysql.py",
            "deploy/flama-review-analytics-worker.service",
            "deploy/flama-review-analytics-worker.timer",
            "models/deck_count_snapshot.py",
            "migrations/versions/20261005_000051_*.py",
            "migrations/versions/*_000052_*.py",
            "scripts/probe_review_analytics_mysql.py",
            "scripts/bench_analytics_counts_mysql.py",
            "scripts/probe_deck_counts_mysql.py",
            "scripts/probe_p5_analytics_mysql.py",
            "scripts/probe_dashboard_due_counts_mysql.py",
            "scripts/probe_note_analytics_mysql.py",
        ],
        "backend_tests": [
            "tests/test_deck_aggregation_service.py",
            "tests/test_fixed_offset_timezones.py",
            "tests/test_note_analytics_read.py",
            "tests/test_note_stats_retirement.py",
            "tests/test_stats_overview.py",
            "tests/test_stats_study_time.py",
            "tests/test_stats_today_future.py",
            "tests/test_review_analytics_schema.py",
            "tests/test_review_analytics_policy.py",
            "tests/test_review_analytics_projection.py",
            "tests/test_review_analytics_outbox.py",
            "tests/test_review_analytics_backfill.py",
            "tests/test_review_analytics_reads.py",
            "tests/test_review_analytics_mysql_probe.py",
            "tests/test_review_analytics_study_integration.py",
            "tests/test_deck_count_snapshots.py",
            "tests/test_forecast_snapshots.py",
            "tests/test_scalability_qualification.py",
            "tests/test_review_projection_benchmark.py",
            "tests/test_analytics_summary_readiness.py",
            "tests/test_deck_count_projection.py",
        ],
        "frontend_tests": [],
    },
    "audio": {
        "source_patterns": [
            "flama-audio/**",
            "app/services/browse_voicevox*.py",
            "app/services/tts_*.py",
            "models/tts_*.py",
            "frontend/src/features/audio/**",
            "frontend/src/entities/audio/**",
            "scripts/compare_tts_kokoro_vs_cosyvoice.py",
            "scripts/test_cosyvoice_synthesis.py",
        ],
        "backend_tests": [
            "tests/test_flama_audio_release_workflow.py",
            "tests/test_tts_provider_seed.py",
            "tests/test_tts_user_profile_api.py",
        ],
        "frontend_tests": [
            "src/features/audio/audioGenerator.test.ts",
            "src/features/audio/components/FlamaAudioConnectionGate.test.tsx",
            "src/features/audio/hooks/useLocalAudioEngine.test.tsx",
            "src/features/audio/services/localAudioPolling.test.ts",
            "src/lib/flamaAudioClient.test.ts",
        ],
    },
    "support": {
        "source_patterns": [
            "app/api/v1/tickets.py",
            "app/services/support_ticket*.py",
            "app/repositories/support_ticket_repository.py",
            "app/validators/support_ticket*.py",
            "models/support_ticket*.py",
        ],
        "backend_tests": [
            "tests/test_support_tickets.py",
        ],
        "frontend_tests": [],
    },
    "worksheets": {
        "source_patterns": [
            "app/api/v1/worksheets/**",
            "app/services/worksheets/**",
            "frontend/src/features/worksheets/**",
        ],
        "backend_tests": [
            "tests/test_api_worksheets.py",
            "tests/test_worksheet_service.py",
            "tests/test_worksheet_stroke_cache.py",
            "tests/test_worksheet_preview_mysql.py",
        ],
        "frontend_tests": [
            "src/features/worksheets/DeckWorksheetModal.test.tsx",
            "src/features/worksheets/api.test.ts",
        ],
    },
    "seed": {
        "source_patterns": [
            "scripts/seed_flama_template.py",
            "scripts/seed_production_strokes.py",
            "scripts/reseed_local_strokes.py",
            "scripts/reseed_db.*",
            "static/seed_data/**",
            "app/services/seeding_service.py",
            "app/services/flashcard_legacy.py",
        ],
        "backend_tests": [
            "tests/test_admin_user_roles.py",
            "tests/test_bootstrap_admin_credentials.py",
            "tests/test_tts_provider_seed.py",
            "tests/test_vocab_seed_sharing.py",
            "tests/test_stroke_service.py",
        ],
        "frontend_tests": [],
    },
    "database": {
        "source_patterns": [
            "migrations/**",
            "scripts/audit_legacy_schema.py",
            "scripts/audit_legacy_progress_retirement.py",
            "scripts/probe_p1_02_mysql_concurrency.py",
            "scripts/run_phase4_preflight_bundle.py",
            "scripts/probe_p5_study_batch_mysql.py",
            "scripts/run_p5_vps_preflight.py",
        ],
        "backend_tests": [
            "tests/test_app_startup.py",
            "tests/test_scalability_cli.py",
            "tests/test_field_identity_cutover.py",
            "tests/test_field_identity_deploy.py",
            "tests/test_deck_release_schema.py",
            "tests/test_flashcard_media_migration.py",
            "tests/test_image_library_schema.py",
            "tests/test_marketplace_taxonomy_migration.py",
            "tests/test_phase4_preflight_bundle.py",
            "tests/test_scheduler_schema.py",
            "tests/test_study_session_batch_migration.py",
            "tests/test_study_batch_attempt_migration.py",
            "tests/test_study_history_cut_index_migration.py",
            "tests/test_study_session_authority_pin.py",
            "tests/test_study_authority_schema.py",
            "tests/test_study_authority_note_enrollment.py",
            "tests/test_study_authority_receipt.py",
            "tests/test_study_storage_profile.py",
        ],
        "frontend_tests": [],
    },
    "cli": {
        # app/cli.py is still a monolith, so path-only selection cannot know
        # which command changed. Keep a broad CLI contract set here, but do not
        # invalidate unrelated API/UI suites; master/manual still run all tests.
        "source_patterns": [
            "app/cli.py",
            "scripts/run_phase4_preflight_bundle.py",
        ],
        "backend_tests": [
            "tests/test_admin_user_roles.py",
            "tests/test_anki_import_api.py",
            "tests/test_api_strokes.py",
            "tests/test_app_startup.py",
            "tests/test_scalability_cli.py",
            "tests/test_batched_deck_clone.py",
            "tests/test_bootstrap_admin_credentials.py",
            "tests/test_bootstrap_admin_sync.py",
            "tests/test_deck_notetype_guard.py",
            "tests/test_deck_release_api.py",
            "tests/test_flashcard_media_migration.py",
            "tests/test_flashcard_media_normalizer.py",
            "tests/test_image_library.py",
            "tests/test_market_counter_deletion.py",
            "tests/test_marketplace_taxonomy_db.py",
            "tests/test_oauth_mcp.py",
            "tests/test_payment_order_flow.py",
            "tests/test_phase4_preflight_bundle.py",
            "tests/test_stroke_service.py",
            "tests/test_transactional_email_service.py",
            "tests/test_tts_provider_seed.py",
            "tests/test_vocab_seed_sharing.py",
        ],
        "frontend_tests": [],
    },
    "i18n": {
        "source_patterns": [
            "frontend/src/shared/config/i18n/**",
            "frontend/src/shared/ui/LanguageSwitcher*",
            "scripts/verify_m1_challenger.py",
            "scripts/test_adversarial_i18n_parity.py",
        ],
        "backend_tests": [],
        "frontend_tests": [
            "src/shared/config/i18n/i18n.test.ts",
            "src/shared/config/i18n/i18n.stress.test.tsx",
            "src/shared/config/i18n/lazyLoading.test.tsx",
            "src/shared/config/i18n/translationKeys.test.ts",
            "src/shared/ui/LanguageSwitcher.test.tsx",
        ],
    },
    "test_coordination": {
        "source_patterns": ["scripts/watch_test_coordination.py"],
        "backend_tests": ["tests/test_watch_test_coordination.py"],
        "frontend_tests": [],
    },
    "tooling": {
        "source_patterns": [
            ".github/workflows/**",
            "deploy/**",
            "scripts/launch_chrome_devtools.*",
            "scripts/run_lighthouse_audit.*",
            "scripts/run_tests.py",
            "scripts/unittest_manifest.py",
            "scripts/compare_test_manifests.py",
            "scripts/run_mysql_probes.py",
            "scripts/check_*.py",
            "scripts/stress_test_cicd_quota.py",
            "scripts/setup_github_workspace.sh",
            "scripts/setup_new_device.sh",
            "scripts/setup_venv.sh",
            "scripts/update_route_snapshot.py",
            "scripts/verify_m4_link_integrity.py",
            "scripts/deploy_cloudflare_cache_rule.py",
            "wsgi_audit.py",
        ],
        "backend_tests": [
            "tests/test_ci_workflow.py",
            "tests/test_cloudflare_cache_rule.py",
            "tests/test_deploy_environment_consistency.py",
            "tests/test_deploy_workflow.py",
            "tests/test_flama_audio_release_workflow.py",
            "tests/test_modular_test_runner.py",
            "tests/test_parallel_backend_runner.py",
            "tests/test_unittest_manifest.py",
            "tests/test_test_mapping_coverage.py",
        ],
        "frontend_tests": [],
    },
    "agent_skills": {
        "source_patterns": [
            "skills/**",
            ".claude/skills/**",
            ".agents/skills/**",
            "scripts/sync_claude_skills.py",
        ],
        "backend_tests": [
            "tests/test_claude_skills_sync.py",
        ],
        "frontend_tests": [],
    },
    "core": {
        "source_patterns": [
            "app/__init__.py",
            "app/startup*.py",
            "app/extensions.py",
            "app/cors.py",
            "app/csrf.py",
            "app/public_media_session.py",
            "app/spa.py",
            "app/settings.py",
            "app/template_formatters.py",
            "app/api/__init__.py",
            "app/api/common/**",
            "app/api/v1/health.py",
            "app/api/v1/download.py",
            "app/api/v1/__init__.py",
            "app/routes/__init__.py",
            "app/routes/main.py",
            "app/routes/rest_api.py",
            "app/routes/spa_routes.py",
            "app/services/__init__.py",
            "app/services/common/**",
            "app/services/rate_limiter_engine.py",
            "app/services/redis_state_service.py",
            "app/services/rest_api_service.py",
            "app/utils/__init__.py",
            "app/utils/db.py",
            "app/utils/logging_redactor.py",
            "app/utils/permissions.py",
            "app/utils/redirects.py",
            "app/validators/__init__.py",
            "app/validators/base.py",
            "app/presenters/__init__.py",
            "app/repositories/__init__.py",
            "models/__init__.py",
            "models/audit_log.py",
            "models/column_preference.py",
            "models/creator_feature_policy.py",
            "models/media_field_migration.py",
            "models/model_uuid.py",
            "wsgi.py",
            "gunicorn.conf.py",
            "frontend/src/shared/**",
        ],
        "backend_tests": [
            "tests/test_app_startup.py",
            "tests/test_api_v1_route_map.py",
            "tests/test_base_dto.py",
            "tests/test_cors.py",
            "tests/test_deploy_workflow.py",
            "tests/test_download_routes.py",
            "tests/test_logging_redaction.py",
            "tests/test_rest_api_v1.py",
            "tests/test_rest_only_runtime.py",
            "tests/test_spa_artifact_contract.py",
            "tests/test_spa_routes.py",
            "tests/test_sync_managed_env.py",
            "tests/test_template_formatters.py",
        ],
        "frontend_tests": [
            "src/shared/api/client.test.ts",
        ],
    },
}

# Central entrypoints and dependency manifests intentionally invalidate an
# entire runtime layer. Keep this list short and covered by an audit test.
FULL_BACKEND_SOURCE_PATTERNS = (
    "requirements.txt",
    "requirements-test.txt",
    "pyproject.toml",
    "setup.cfg",
)

FULL_FRONTEND_SOURCE_PATTERNS = (
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/vite.config.ts",
    "frontend/vitest.config.ts",
    "frontend/wrangler.jsonc",
    "frontend/.node-version",
)

# Environment-specific contract tiers. These patterns are intentionally
# narrower than the domain catalog so PRs only pay for external services when
# the changed code can affect that contract.
SPA_CONTRACT_SOURCE_PATTERNS = (
    "app/spa.py",
    "frontend/index.html",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/vite.config.*",
    "Dockerfile",
    ".github/workflows/ci.yml",
    "tests/test_spa_artifact_contract.py",
)

REDIS_CONTRACT_SOURCE_PATTERNS = (
    "app/services/redis_state_service.py",
    "app/services/login_rate_limit_service.py",
    "app/services/quota_service.py",
    "app/api/v1/health.py",
    "requirements.txt",
    "tests/test_shared_state_services.py",
)

MYSQL_CONTRACT_SOURCE_PATTERNS = (
    "scripts/run_mysql_probes.py",
    # Every schema-owning probe resets its schema through this helper.
    "scripts/mysql_probe_db.py",
    "tests/test_mysql_probe_schema_reuse.py",
    "scripts/probe_review_analytics_outbox_mysql.py",
    "scripts/archive_retired_tables.py",
    "scripts/bootstrap_historical_schema.py",
    "scripts/prepare_retirement_mysql_rehearsal.py",
    "scripts/verify_retirement_protected_state.py",
    "scripts/probe_retirement_fresh_chain_mysql.py",
    "migrations/**",
    "models/**",
    "requirements.txt",
    "scripts/probe_p1_02_mysql_concurrency.py",
    "tests/test_marketplace_taxonomy_migration.py",
    # Analytics run in a READ ONLY MySQL transaction that SQLite cannot emulate.
    "app/api/v1/analytics/**",
    "app/services/study_analytics_read_service.py",
    "app/services/deck_aggregation_service.py",
    "app/services/dashboard_service.py",
    "app/services/stats_overview.py",
    "app/repositories/note_analytics_read_repository.py",
    "app/repositories/note_analytics_scope_repository.py",
    "app/repositories/stats_query_repository.py",
    "app/services/stats_today_future.py",
    "app/repositories/browse_card_repository.py",
    # Browse's SQL scope, release values and pagination are qualified on MySQL.
    "app/api/v1/learning/browse.py",
    "app/services/browse_card_service.py",
    "app/services/browse_note_service.py",
    "app/services/browse_deck_service.py",
    "app/repositories/browse_note_repository.py",
    "app/repositories/browse_deck_repository.py",
    "app/repositories/browse_search_repository.py",
    "app/validators/browse_*.py",
    "tests/test_browse_*mysql.py",
    "tests/test_browse_mysql_contract.py",
    "tests/test_browse_query_bounds.py",
    "scripts/benchmark_browse_mysql.py",
    "scripts/probe_p5_analytics_mysql.py",
    "scripts/probe_note_analytics_mysql.py",
    "scripts/probe_dashboard_due_counts_mysql.py",
    "tests/test_note_analytics_read.py",
    "tests/test_note_stats_retirement.py",
    "tests/test_stats_overview.py",
    "app/services/review_analytics_*.py",
    "app/repositories/review_analytics_*.py",
    "app/services/deck_count_*.py",
    "app/repositories/deck_count_*.py",
    "app/services/forecast_snapshot_service.py",
    "app/repositories/forecast_snapshot_repository.py",
    "app/services/field_value_identity_*.py",
    "app/services/field_value_runtime_service.py",
    "app/services/clone_field_identity_service.py",
    "app/repositories/field_value_identity_repository.py",
    "app/repositories/field_value_query_repository.py",
    "app/repositories/media_field_identity_repository.py",
    "scripts/probe_field_identity_mysql.py",
    "scripts/probe_field_identity_cutover_mysql.py",
    "scripts/probe_field_value_consumers_mysql.py",
    "scripts/cutover_field_value_identity.py",
    "scripts/probe_forecast_snapshots_mysql.py",
    "scripts/qualify_progress_scalability_mysql.py",
    "scripts/bench_review_projection_mysql.py",
    "models/review_analytics.py",
    "models/deck_count_snapshot.py",
    "migrations/versions/20261005_000051_*.py",
    "migrations/versions/*_000052_*.py",
    "scripts/probe_review_analytics_mysql.py",
    "scripts/bench_analytics_counts_mysql.py",
    "scripts/probe_deck_counts_mysql.py",
    # Gap locks and deadlocks between learners exist only on InnoDB.
    "app/services/db_errors.py",
    "app/services/auth_service.py",
    "app/services/study_authority_evidence_service.py",
    "app/services/study_authority_receipt_service.py",
    "app/services/study_authority_enrollment_service.py",
    "app/services/study_direct_note_replay_service.py",
    "app/services/study_progress_history_service.py",
    "app/services/study_authority_command_service.py",
    "app/services/study_session_service.py",
    "app/routes/flashcards/study.py",
    "scripts/probe_p5_concurrency_mysql.py",
    "tests/test_study_note_write_gap_locks.py",
    # Parallel Note creation (MCP agents) meets on InnoDB gap locks only.
    "app/repositories/study_inserted_rows.py",
    "app/repositories/study_authority_repository.py",
    "app/services/study_progress_lifecycle_mirror_service.py",
    "app/services/mcp/note_tools.py",
    "app/services/study_note_pristine_service.py",
    "scripts/probe_p5_direct_replay_mysql.py",
    "tests/test_study_pristine_bulk_materialization.py",
    # Migration 46 runs while the previous release serves; FK/DDL behaviour is InnoDB-only.
    "app/services/study_note_attribution_service.py",
    "scripts/probe_p6_application_schema_mysql.py",
    "scripts/bench_p6_migration_mysql.py",
    # Migration 47: MySQL adds CHECKs by copying and refuses them on FK-action columns.
    "scripts/bench_p9_profile_migration_mysql.py",
    # Migration 48: one ALTER with a CHECK on connect_source_card_refs.
    "scripts/probe_p9_connect_fence_mysql.py",
    # Migration 49: consolidated progress CHECKs copy study_progress_subjects.
    "scripts/probe_p10_schema_mysql.py",
    # Migration 50: FK/index drops and DROP TABLE order are InnoDB behavior.
    "migrations/versions/20261003_000050_drop_retired_note_progress_tables.py",
    "scripts/probe_p10_drop_mysql.py",
    # Phase 7 foreign-key behavior (cascades from membership to pins) only runs on InnoDB.
    "app/services/study_session_retention_service.py",
    "scripts/probe_p7_session_retention_mysql.py",
    "tests/test_study_session_retention.py",
)

DEPLOY_RUNTIME_SOURCE_PATTERNS = (
    "app/**",
    "models/**",
    "migrations/**",
    "deploy/**",
    "static/**",
    "requirements.txt",
    "wsgi.py",
    "connect_wsgi.py",
    "Dockerfile",
    ".github/workflows/deploy.yml",
)

# -----------------------------------------------------------------------------
# Runtime Helpers
# -----------------------------------------------------------------------------

def resolve_python_command() -> list[str]:
    """Find a Python executable with dependencies installed."""
    # 1. Virtual environments (.venv / venv)
    venv_candidates = [
        ROOT_DIR / ".venv" / "Scripts" / "python.exe",
        ROOT_DIR / ".venv" / "bin" / "python",
        ROOT_DIR / "venv" / "Scripts" / "python.exe",
        ROOT_DIR / "venv" / "bin" / "python",
    ]
    for cand in venv_candidates:
        if cand.exists():
            return [str(cand)]

    # 2. Check current sys.executable
    try:
        res = subprocess.run(
            [sys.executable, "-c", "import flask, sqlalchemy"],
            capture_output=True,
            timeout=5,
        )
        if res.returncode == 0:
            return [sys.executable]
    except Exception:
        pass

    # 3. Windows py launcher check (e.g. py -3.12)
    if sys.platform == "win32":
        for version in ["-3.12", "-3.11", "-3.10"]:
            try:
                res = subprocess.run(
                    ["py", version, "-c", "import flask, sqlalchemy"],
                    capture_output=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    return ["py", version]
            except Exception:
                continue

    # Fallback to sys.executable
    return [sys.executable]


def get_git_modified_files() -> list[str]:
    """Retrieve list of modified, added, or untracked files from git (supports local and CI)."""
    files: set[str] = set()

    # 1. Unstaged + Staged changes via git status (local dev / uncommitted changes)
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # Status format is XY PATH or XY "PATH" or XY PATH -> PATH2
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                path = parts[1].strip('"')
                if " -> " in path:
                    path = path.split(" -> ")[1].strip('"')
                files.add(path.replace("\\", "/"))
    except Exception as e:
        print(f"[WARN] Failed to get git status: {e}", file=sys.stderr)

    # 2. Working tree diffs (git diff HEAD)
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            for path in proc.stdout.splitlines():
                if path.strip():
                    files.add(path.strip().replace("\\", "/"))
    except Exception:
        pass

    # 3. If working tree is clean (e.g. CI runner right after checkout / commit), diff against base branch or previous commit
    if not files:
        diff_targets: list[list[str]] = []
        explicit_base = os.environ.get("TEST_DIFF_BASE")
        explicit_head = os.environ.get("TEST_DIFF_HEAD") or "HEAD"
        is_new_branch_push = bool(explicit_base) and set(explicit_base or "") <= {"0"}
        if explicit_base and not is_new_branch_push:
            diff_targets.append([explicit_base, explicit_head])

        base_ref = os.environ.get("GITHUB_BASE_REF")
        if base_ref:
            diff_targets.append([f"origin/{base_ref}...HEAD"])
            diff_targets.append([f"{base_ref}...HEAD"])

        # A newly-created branch has an all-zero event.before. Compare against
        # the integration branches before falling back to one commit.
        if is_new_branch_push:
            diff_targets.append(["origin/develop...HEAD"])
            diff_targets.append(["origin/master...HEAD"])

        # Local clean-tree fallback. Normal CI pushes supply an explicit range,
        # so a push containing multiple commits is never reduced to HEAD~1.
        diff_targets.append(["HEAD~1", "HEAD"])
        if not is_new_branch_push:
            diff_targets.append(["origin/master...HEAD"])
            diff_targets.append(["origin/develop...HEAD"])

        for target in diff_targets:
            try:
                proc = subprocess.run(
                    ["git", "diff", "--name-only"] + target,
                    cwd=str(ROOT_DIR),
                    capture_output=True,
                    text=True,
                )
                if proc.returncode == 0:
                    found = [p.strip().replace("\\", "/") for p in proc.stdout.splitlines() if p.strip()]
                    if found:
                        files.update(found)
                        break
            except Exception:
                continue

    return sorted(files)


def map_files_to_modules(
    changed_files: list[str], *, from_git_diff: bool = False,
) -> tuple[set[str], set[str], set[str]]:
    """
    Given a list of changed files, determine affected module names,
    backend test files, and frontend test files.
    """
    matched_modules: set[str] = set()
    backend_modules: set[str] = set()
    frontend_modules: set[str] = set()
    backend_tests: set[str] = set()
    frontend_tests: set[str] = set()

    inventories: dict[str, list[str]] = {}

    def current_tests(layer: str) -> list[str]:
        # One inventory per layer keeps a large PR diff consistent and avoids
        # rescanning the whole frontend for every co-located feature change.
        if layer not in inventories:
            inventories[layer] = (
                discover_all_backend_tests() if layer == "backend"
                else discover_all_frontend_tests()
            )
        return inventories[layer]

    for file_path in changed_files:
        norm_path = file_path.replace("\\", "/")

        # Git diffs include removed tests. Without verified rename metadata,
        # a matching basename cannot establish the replacement's coverage.
        # Run the entire current layer so moves, renames and deletions retain
        # their surviving regressions. Explicit --file still rejects typos.
        if from_git_diff and not (ROOT_DIR / norm_path).is_file():
            backend_test = (
                norm_path.startswith("tests/")
                and Path(norm_path).name.startswith("test_")
                and norm_path.endswith(".py")
            )
            frontend_test = norm_path.startswith("frontend/src/") and (
                ".test." in norm_path or ".spec." in norm_path
            )
            if backend_test or frontend_test:
                selected_current_tests = (
                    current_tests("backend") if backend_test
                    else current_tests("frontend")
                )
                layer = "backend" if backend_test else "frontend"
                if not selected_current_tests:
                    raise ValueError(
                        f"Cannot resolve removed {layer} test {norm_path!r}: "
                        "no current tests were discovered; coverage cannot be verified."
                    )
                (backend_tests if backend_test else frontend_tests).update(selected_current_tests)
                continue

        # If a changed file does not exist on disk, check if its filename
        # matches any known test in MODULES (e.g. file was renamed/relocated).
        if not (ROOT_DIR / norm_path).exists():
            target_name = Path(norm_path).name
            resolved = None
            for mod_info in MODULES.values():
                for bt in mod_info["backend_tests"]:
                    if Path(bt).name == target_name and (ROOT_DIR / bt).exists():
                        resolved = bt
                        break
                if resolved:
                    break
                for ft in mod_info["frontend_tests"]:
                    if Path(ft).name == target_name and (ROOT_DIR / "frontend" / ft).exists():
                        resolved = f"frontend/{ft}"
                        break
                if resolved:
                    break
            if resolved:
                norm_path = resolved

        # A direct test edit runs that test only. Module names remain useful in
        # diagnostics, but must not expand one test file into a whole domain.
        if norm_path.startswith("tests/") and Path(norm_path).name.startswith("test_") and norm_path.endswith(".py"):
            backend_tests.add(norm_path)
            for mod_name, mod_info in MODULES.items():
                if norm_path in mod_info["backend_tests"]:
                    matched_modules.add(mod_name)
            continue

        if norm_path.startswith("frontend/src/") and (
            ".test." in norm_path or ".spec." in norm_path
        ):
            rel_fe_test = norm_path.removeprefix("frontend/")
            frontend_tests.add(rel_fe_test)
            for mod_name, mod_info in MODULES.items():
                if rel_fe_test in mod_info["frontend_tests"]:
                    matched_modules.add(mod_name)
            continue

        is_frontend_source = norm_path.startswith("frontend/src/")
        matched = False

        # Frontend tests are co-located. Discover the whole feature so a newly
        # added test does not require immediate catalog maintenance.
        feature_prefix = "frontend/src/features/"
        if norm_path.startswith(feature_prefix):
            feature_name = norm_path[len(feature_prefix):].split("/", 1)[0]
            relative_prefix = f"src/features/{feature_name}/"
            co_located_tests = {
                path
                for path in current_tests("frontend")
                if path.startswith(relative_prefix)
            }
            frontend_tests.update(co_located_tests)
            matched = bool(co_located_tests)

        for mod_name, mod_info in MODULES.items():
            if any(
                fnmatch.fnmatch(norm_path, pattern)
                for pattern in mod_info["source_patterns"]
            ):
                matched_modules.add(mod_name)
                if is_frontend_source:
                    frontend_modules.add(mod_name)
                else:
                    backend_modules.add(mod_name)
                matched = True

        # Any API/blueprint edit must verify both the endpoint list and count.
        # This invariant also covers a route in a brand-new, unmapped domain.
        if (
            norm_path.startswith("app/api/")
            or norm_path.startswith("app/routes/")
            or norm_path == "app/__init__.py"
        ):
            backend_tests.add("tests/test_api_v1_route_map.py")

        # Runtime dependency changes can affect every test in their layer.
        if any(
            fnmatch.fnmatch(norm_path, pattern)
            for pattern in FULL_BACKEND_SOURCE_PATTERNS
        ):
            backend_tests.update(current_tests("backend"))
            matched = True
        if any(
            fnmatch.fnmatch(norm_path, pattern)
            for pattern in FULL_FRONTEND_SOURCE_PATTERNS
        ):
            frontend_tests.update(current_tests("frontend"))
            matched = True

        if not matched:
            # Fail safe when the catalog is stale: run the affected layer in
            # full rather than silently substituting unrelated core tests.
            if norm_path.startswith("app/") or norm_path.startswith("models/"):
                backend_tests.update(current_tests("backend"))
            elif is_frontend_source:
                frontend_tests.update(current_tests("frontend"))

    # Never cross layers: React changes select Vitest only; Python changes
    # select unittest only.
    for mod_name in backend_modules:
        backend_tests.update(MODULES[mod_name]["backend_tests"])
    for mod_name in frontend_modules:
        frontend_tests.update(MODULES[mod_name]["frontend_tests"])

    return matched_modules, backend_tests, frontend_tests


def build_ci_change_plan(
    changed_files: list[str],
    *,
    force_all_validation: bool = False,
    files_since_deploy: list[str] | None = None,
) -> dict[str, bool]:
    """Return job-level CI decisions for one complete event diff.

    ``files_since_deploy`` is the diff between the release running in
    production and HEAD. A push whose runtime change never deployed (its CI
    failed) must still deploy with the next green push, even a test-only one.
    """
    normalized = [path.replace("\\", "/") for path in changed_files]
    _, backend_tests, frontend_tests = map_files_to_modules(normalized, from_git_diff=True)

    def matches_any(patterns: tuple[str, ...], paths: list[str] | None = None) -> bool:
        return any(
            fnmatch.fnmatch(path, pattern)
            for path in (normalized if paths is None else paths)
            for pattern in patterns
        )

    undeployed_runtime = files_since_deploy is not None and matches_any(
        DEPLOY_RUNTIME_SOURCE_PATTERNS,
        [path.replace("\\", "/") for path in files_since_deploy],
    )

    spa_contract = matches_any(SPA_CONTRACT_SOURCE_PATTERNS)
    return {
        "backend": force_all_validation or bool(backend_tests),
        "frontend": force_all_validation or bool(frontend_tests) or spa_contract,
        "spa_contract": force_all_validation or spa_contract,
        "redis_contract": force_all_validation
        or matches_any(REDIS_CONTRACT_SOURCE_PATTERNS),
        "mysql_contract": force_all_validation
        or matches_any(MYSQL_CONTRACT_SOURCE_PATTERNS),
        # Deployment remains path-sensitive even though master intentionally
        # receives full validation. Test/docs-only merges must not deploy,
        # unless runtime code is still missing from production.
        "deploy": matches_any(DEPLOY_RUNTIME_SOURCE_PATTERNS) or undeployed_runtime,
    }


def files_changed_since(base_sha: str) -> list[str] | None:
    """Files differing between ``base_sha`` and HEAD, or None when unknown."""
    base = str(base_sha or "").strip()
    if not base or not all(ch in "0123456789abcdef" for ch in base.lower()):
        return None
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", base, "HEAD"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def write_github_outputs(path: str, values: dict[str, bool]) -> None:
    """Append stable lowercase booleans to a GitHub Actions output file."""
    with open(path, "a", encoding="utf-8", newline="\n") as output_file:
        for key in sorted(values):
            output_file.write(f"{key}={str(values[key]).lower()}\n")


# -----------------------------------------------------------------------------
# Test Execution
# -----------------------------------------------------------------------------

def discover_all_backend_tests() -> list[str]:
    """Return every backend unittest file, independent of module mappings."""
    tests_dir = ROOT_DIR / "tests"
    return sorted(
        path.relative_to(ROOT_DIR).as_posix()
        for path in tests_dir.rglob("test_*.py")
        if "__pycache__" not in path.parts
    )


def discover_all_frontend_tests() -> list[str]:
    """Return every Vitest file relative to frontend/."""
    source_dir = ROOT_DIR / "frontend" / "src"
    if not source_dir.exists():
        return []
    return sorted(
        path.relative_to(ROOT_DIR / "frontend").as_posix()
        for path in source_dir.rglob("*")
        if path.is_file()
        and any(marker in path.name for marker in (".test.", ".spec."))
    )


def build_backend_test_environment(
    media_root: str,
    base: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build an isolated environment for the backend test subprocess."""
    env = dict(os.environ if base is None else base)
    env["FLAMA_TEST_MEDIA_UPLOAD_ROOT"] = media_root
    env["FLASHCARD_MEDIA_UPLOAD_ROOT"] = media_root
    # Rate-limit tests opt in explicitly through their app config. Disabling the
    # default here prevents module-level counters from leaking across test apps.
    env["RATE_LIMIT_DAILY_ENABLED"] = "0"
    # A developer's .env may configure real SMTP/Resend credentials. Tests
    # opt into their provider fixtures explicitly instead of sending mail.
    env["EMAIL_ENABLED"] = "0"
    env["EMAIL_PROVIDER"] = "memory"
    env["EMAIL_ENVIRONMENT"] = "test"
    # Correctness runs must compare committed snapshots in every worker mode.
    env["UPDATE_SNAPSHOT"] = "0"
    env["UPDATE_ROUTE_SNAPSHOT"] = "0"
    return env


def build_parallel_worker_environment(media_root: str, base: dict[str, str]) -> dict[str, str]:
    """Environment of one ``--jobs`` worker, derived from one parent snapshot."""
    env = build_backend_test_environment(media_root, base)
    # Output is spooled and decoded by the parent: pin the encoding and keep
    # stdout unbuffered so test prints cannot split unittest's summary lines.
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    # A parallel run verifies; it must never rewrite committed snapshots.
    env["UPDATE_SNAPSHOT"] = "0"
    env["UPDATE_ROUTE_SNAPSHOT"] = "0"
    return env


# Each backend worker process pays roughly 4-8s to import the app, so files are
# grouped into a few bins per worker instead of one process per file.
BACKEND_BINS_PER_JOB = 3
# Memory ``--jobs auto`` reserves per worker. The largest worker working set
# measured on the full suite was 653 MB (Windows, --jobs 2, 2026-10-23).
BACKEND_WORKER_MEMORY_BYTES = 768 * 1024 * 1024
# Without a memory reading, ``auto`` does not assume every CPU can be fed.
BACKEND_AUTO_JOBS_WITHOUT_MEMORY_INFO = 2
# Only the end of a worker log is parsed for unittest's summary.
UNITTEST_SUMMARY_TAIL_BYTES = 64 * 1024
# A noisy test cannot fill runner disk or flood hosted logs. The entire pipe is
# drained; only a bounded head and tail are retained, with an explicit marker.
BACKEND_LOG_LIMIT_BYTES = 1024 * 1024
BACKEND_CLEANUP_TIMEOUT = 5.0


def _resource_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="ascii").strip()
    except OSError:
        return None


def _cgroup_directories(controller: str) -> list[tuple[Path, bool]]:
    """Standard Linux cgroup mounts, including limits inherited from ancestors."""
    text = _resource_text(Path("/proc/self/cgroup")) or ""
    paths: list[tuple[Path, bool]] = []
    for line in text.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        hierarchy, controllers, relative = parts
        unified = hierarchy == "0" and not controllers
        if not unified and controller not in controllers.split(","):
            continue
        root = Path("/sys/fs/cgroup") if unified else Path("/sys/fs/cgroup") / controllers
        # A private cgroup namespace can expose '/' as its own root.
        current = root / relative.lstrip("/")
        if ".." in current.parts:
            # Namespace-relative paths can point above the visible mount;
            # its root still exposes the effective inherited limits.
            current = root
        while True:
            paths.append((current, unified))
            if current == root:
                break
            current = current.parent
    return list(dict.fromkeys(paths))

UNITTEST_RAN_RE = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
UNITTEST_RESULT_RE = re.compile(r"^(OK|FAILED)(?: \(([^)]*)\))?\s*$", re.MULTILINE)


def effective_cpu_count() -> int:
    """CPUs this process may use, honouring affinity where the OS reports it."""
    counts = [os.cpu_count() or 1]
    try:
        if hasattr(os, "process_cpu_count"):
            counts.append(os.process_cpu_count() or 1)
        elif hasattr(os, "sched_getaffinity"):
            counts.append(len(os.sched_getaffinity(0)) or 1)
        elif sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.GetCurrentProcess.restype = wintypes.HANDLE
            api.GetProcessAffinityMask.argtypes = [
                wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)
            ]
            process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
            if not api.GetProcessAffinityMask(
                api.GetCurrentProcess(), ctypes.byref(process_mask), ctypes.byref(system_mask)
            ):
                raise OSError("GetProcessAffinityMask failed")
            counts.append(bin(process_mask.value).count("1") or 1)
        else:
            counts.append(BACKEND_AUTO_JOBS_WITHOUT_MEMORY_INFO)
    except (OSError, AttributeError):
        counts.append(BACKEND_AUTO_JOBS_WITHOUT_MEMORY_INFO)
    if sys.platform.startswith("linux"):
        directories = _cgroup_directories("cpu")
        observed_limit = False
        for directory, unified in directories:
            if unified:
                values = (_resource_text(directory / "cpu.max") or "").split()
            else:
                values = [
                    _resource_text(directory / "cpu.cfs_quota_us"),
                    _resource_text(directory / "cpu.cfs_period_us"),
                ]
            try:
                if len(values) == 2 and values[0] == "max" and int(values[1]) > 0:
                    observed_limit = True
                    continue
                quota, period = map(int, values)
                observed_limit = True
                if quota > 0 and period > 0:
                    counts.append(max(1, quota // period))
            except (ValueError, TypeError):
                pass
        if directories and not observed_limit:
            counts.append(BACKEND_AUTO_JOBS_WITHOUT_MEMORY_INFO)
    return max(1, min(counts))


def available_memory_bytes() -> int | None:
    """Physical memory available to new processes, or None when unknown."""
    try:
        if sys.platform == "win32":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullAvailPhys)
            return None
        with open("/proc/meminfo", encoding="ascii") as meminfo:
            for line in meminfo:
                if line.startswith("MemAvailable:"):
                    memory = int(line.split()[1]) * 1024
                    if sys.platform.startswith("linux"):
                        directories = _cgroup_directories("memory")
                        observed_limit = False
                        for directory, unified in directories:
                            maximum = _resource_text(directory / ("memory.max" if unified else "memory.limit_in_bytes"))
                            used = _resource_text(directory / ("memory.current" if unified else "memory.usage_in_bytes"))
                            try:
                                if maximum == "max" and int(used) >= 0:
                                    observed_limit = True
                                    continue
                                memory = min(memory, max(0, int(maximum) - int(used)))
                                observed_limit = True
                            except (ValueError, TypeError):
                                pass
                        if directories and not observed_limit:
                            # If a container hides its limits, choose one
                            # worker rather than infer headroom from host RAM.
                            memory = min(memory, BACKEND_WORKER_MEMORY_BYTES)
                    return memory
    except (OSError, ValueError, AttributeError):
        return None
    return None


def memory_worker_limit() -> int | None:
    """Workers that fit in free memory at the measured per-worker peak, if known."""
    memory = available_memory_bytes()
    if memory is None:
        return None
    return max(1, memory // BACKEND_WORKER_MEMORY_BYTES)


def resolve_backend_jobs(requested: str | int | None, file_count: int) -> int:
    """Return the worker count for ``--jobs``.

    ``auto`` uses the CPUs available to this process, capped by available
    memory (or at two workers when memory cannot be read); an explicit number
    is used as given. Both are capped by the number of files.
    """
    if requested is None or str(requested).strip().lower() in {"", "auto"}:
        jobs = effective_cpu_count()
        limit = memory_worker_limit()
        if limit is None:
            jobs = min(jobs, BACKEND_AUTO_JOBS_WITHOUT_MEMORY_INFO)
        else:
            jobs = min(jobs, limit)
    else:
        try:
            jobs = int(requested)
        except ValueError:
            jobs = 0
        if jobs < 1:
            raise ValueError("--jobs must be a positive integer or 'auto'")
    return max(1, min(jobs, file_count))


def partition_backend_tests(
    test_files: list[str],
    bin_count: int,
    weights: dict[str, float] | None = None,
    seed: int | None = None,
) -> list[list[str]]:
    """Split files into balanced bins, heaviest bin first (LPT scheduling).

    Every file lands in exactly one bin. Without measured weights, file size
    stands in for runtime; the order is deterministic for a given input. A
    seed perturbs each weight by up to 25% so a different grouping is tested
    without changing the number of workers.
    """
    rng = random.Random(seed) if seed is not None else None
    measured: dict[str, float] = {}
    for path in sorted(set(test_files)):
        if weights and path in weights:
            value = float(weights[path])
        else:
            value = float((ROOT_DIR / path).stat().st_size)
        if rng is not None:
            value *= 1.0 + rng.uniform(-0.25, 0.25)
        measured[path] = value

    bin_count = max(1, min(bin_count, len(test_files)))
    bins: list[list[str]] = [[] for _ in range(bin_count)]
    loads = [0.0] * bin_count
    for path in sorted(test_files, key=lambda p: (-measured[p], p)):
        target = min(range(bin_count), key=lambda i: (loads[i], i))
        bins[target].append(path)
        loads[target] += measured[path]
    order = sorted(range(bin_count), key=lambda i: (-loads[i], i))
    return [sorted(bins[i]) for i in order if bins[i]]


@dataclass
class UnittestSummary:
    ran: int = 0
    ok: bool = False
    counts: dict[str, int] = field(default_factory=dict)


def parse_unittest_summary(output: str) -> UnittestSummary | None:
    """Parse the final ``Ran N tests`` / ``OK|FAILED (...)`` lines of unittest."""
    ran = UNITTEST_RAN_RE.findall(output)
    results = UNITTEST_RESULT_RE.findall(output)
    if not ran or not results:
        return None
    status, details = results[-1]
    counts: dict[str, int] = {}
    for part in filter(None, (piece.strip() for piece in details.split(","))):
        name, _, value = part.partition("=")
        if value.isdigit():
            counts[name.strip()] = int(value)
    return UnittestSummary(ran=int(ran[-1]), ok=status == "OK", counts=counts)


@dataclass
class BackendBinResult:
    files: list[str]
    returncode: int | None
    log_path: str | None
    elapsed: float
    summary: UnittestSummary | None
    note: str = ""
    manifest_path: str | None = None
    manifest_data: dict | None = None

    @property
    def started(self) -> bool:
        return self.returncode is not None

    @property
    def passed(self) -> bool:
        # Printed text is untrusted test output. Only the validated wrapper's
        # completion record proves that unittest actually ran and finished.
        return (
            self.returncode == 0
            and self.manifest_data is not None
            and self.manifest_data.get("complete") is True
            and self.manifest_data.get("success") is True
            # A fully skipped class/module can legitimately have Ran 0. The
            # manifest reader proves a nonempty loaded inventory and explicit
            # fixture skips; an unexpected empty suite is rejected there.
            and self.manifest_data.get("tests_run", -1) >= 0
            and self.summary is not None
            and self.summary.ok
            and self.summary.ran == self.manifest_data.get("tests_run")
        )

    def read_output(self) -> str:
        if not self.log_path or not os.path.exists(self.log_path):
            return self.note
        with open(self.log_path, "rb") as handle:
            return handle.read().decode("utf-8", errors="replace") + self.note

    def write_output(self, stream) -> None:
        """Copy the spooled log to ``stream`` in chunks (bounded memory)."""
        import codecs

        if self.log_path and os.path.exists(self.log_path):
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            with open(self.log_path, "rb") as handle:
                for chunk in iter(lambda: handle.read(64 * 1024), b""):
                    stream.write(decoder.decode(chunk))
            stream.write(decoder.decode(b"", final=True))
        if self.note:
            stream.write(self.note)
        stream.write("\n")


def _unittest_command(
    python_cmd: list[str],
    test_files: list[str],
    failfast: bool,
    verbose: bool,
) -> list[str]:
    cmd = list(python_cmd) + ["-m", "unittest"]
    if failfast:
        cmd.append("-f")
    if verbose:
        cmd.append("-v")
    cmd.extend(test_files)
    return cmd


def _manifest_command(
    python_cmd: list[str],
    test_files: list[str],
    failfast: bool,
    verbose: bool,
) -> list[str]:
    """Same unittest arguments, run through the outcome-recording wrapper."""
    cmd = _unittest_command(python_cmd, test_files, failfast, verbose)
    index = cmd.index("unittest")
    return cmd[:index] + ["scripts.unittest_manifest"] + cmd[index + 1:]


class _WindowsJob:
    """Kill-on-close ownership, assigned before the gated worker loads tests."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD),
            ]
        class Io(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]
        class Extended(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", Basic), ("IoInfo", Io),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]
        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_longlong) for name in (
                "TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime",
            )] + [(name, w.DWORD) for name in (
                "TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses",
            )]
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        api.CreateJobObjectW.restype = w.HANDLE
        api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        api.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)]
        api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        api.OpenProcess.restype = w.HANDLE
        api.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        api.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
        api.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
        api.CloseHandle.argtypes = [w.HANDLE]
        self.api, self.ctypes, self.Accounting = api, ctypes, Accounting
        self.handle = api.CreateJobObjectW(None, None)
        self._lock = threading.Lock()
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            api.CloseHandle(self.handle)
            self.handle = None
            raise error

    def assign_handle(self, handle):
        from ctypes import wintypes
        already = wintypes.BOOL()
        if not self.api.IsProcessInJob(handle, self.handle, self.ctypes.byref(already)):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        if not already.value and not self.api.AssignProcessToJobObject(self.handle, handle):
            raise self.ctypes.WinError(self.ctypes.get_last_error())

    def assign_pid(self, pid):
        handle = self.api.OpenProcess(0x100 | 0x1 | 0x1000, False, pid)
        if not handle:
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        try:
            self.assign_handle(handle)
        except BaseException:
            # A launcher may have created this gated interpreter before the
            # launcher joined the job. Never leave it outside job ownership
            # when assignment fails: no test code has been released yet.
            self.api.TerminateProcess(handle, 1)
            raise
        finally:
            self.api.CloseHandle(handle)

    def stop(self):
        with self._lock:
            if not self.handle:
                return
            try:
                if not self.api.TerminateJobObject(self.handle, 1):
                    raise self.ctypes.WinError(self.ctypes.get_last_error())
                deadline = time.monotonic() + BACKEND_CLEANUP_TIMEOUT
                while True:
                    status = self.Accounting()
                    if not self.api.QueryInformationJobObject(
                        self.handle, 1, self.ctypes.byref(status), self.ctypes.sizeof(status), None
                    ):
                        raise self.ctypes.WinError(self.ctypes.get_last_error())
                    if status.ActiveProcesses == 0:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Windows worker job did not terminate")
                    time.sleep(0.01)
            finally:
                self.api.CloseHandle(self.handle)
                self.handle = None


def _posix_process_group_alive(pgid: int) -> bool:
    """Ignore Linux zombies: orphan reaping belongs to PID 1, not this runner."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    if not sys.platform.startswith("linux"):
        return True
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            # comm may contain spaces and ')'; the final ')' ends that field.
            fields = (entry / "stat").read_text(encoding="utf-8", errors="replace").rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue  # The process exited during this scan.
        if int(fields[2]) == pgid and fields[0] not in {"Z", "X"}:
            return True
    return False


def _wait_for_posix_process_group(pgid: int) -> None:
    deadline = time.monotonic() + BACKEND_CLEANUP_TIMEOUT
    while _posix_process_group_alive(pgid):
        if time.monotonic() >= deadline:
            raise RuntimeError(f"POSIX worker group {pgid} did not terminate")
        time.sleep(0.01)


def _terminate_process_tree(proc: subprocess.Popen) -> None:
    """Kill descendants even after the root exited, then reap the root."""
    job = getattr(proc, "_flama_job", None)
    cleanup_error = None
    if job is not None:
        try:
            job.stop()
        except Exception as exc:
            cleanup_error = exc
    elif sys.platform != "win32" and getattr(proc, "_flama_session", False):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.poll() is None:
        if sys.platform == "win32":
            # Setup failure can leave a root outside its job. Its bootstrap
            # still waits at the gate, so bounded taskkill can stop the tree
            # before any user test gets a chance to spawn an unowned process.
            try:
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=BACKEND_CLEANUP_TIMEOUT,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        if proc.poll() is None:
            proc.kill()
    try:
        proc.wait(timeout=BACKEND_CLEANUP_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"worker {proc.pid} could not be reaped") from exc
    if sys.platform != "win32" and getattr(proc, "_flama_session", False):
        # killpg only queues the signal; reaping the root says nothing about
        # descendants. Wait before reporting completion or deleting worker media.
        _wait_for_posix_process_group(proc.pid)
    if cleanup_error is not None:
        raise RuntimeError(f"worker tree cleanup failed: {cleanup_error}") from cleanup_error


_WORKER_BOOTSTRAP = """\
import os, runpy, sys
gate_path = os.environ.pop("FLAMA_TEST_GATE_PID_PATH")
with open(gate_path + ".tmp", "w", encoding="ascii") as gate:
    gate.write(str(os.getpid()))
os.replace(gate_path + ".tmp", gate_path)
if os.read(0, 1) != b"1":
    raise SystemExit(125)
mode, target, *arguments = sys.argv[1:]
sys.argv = [target if mode == "-m" else "-c", *arguments]
if mode == "-m":
    runpy.run_module(target, run_name="__main__", alter_sys=True)
else:
    exec(compile(target, "<string>", "exec"), {"__name__": "__main__", "__file__": "<string>"})
"""


def _gated_command(command: list[str]) -> list[str]:
    index = next(i for i, value in enumerate(command) if value in {"-m", "-c"})
    return command[:index] + ["-c", _WORKER_BOOTSTRAP, *command[index:]]


class _WorkerRegistry:
    """Serialize launch/release against stop: late workers cannot load tests."""
    def __init__(self):
        self._lock = threading.Lock()
        self._active: set[subprocess.Popen] = set()
        self.stopped = threading.Event()

    def add(self, proc):
        with self._lock:
            self._active.add(proc)
            stopped = self.stopped.is_set()
        if stopped:
            _terminate_process_tree(proc)

    def launch(self, command, env, gate_path):
        # stop_all sets its event before acquiring the lock. A racing launch
        # remains gated until it sees the event, so no late test code executes.
        with self._lock:
            if self.stopped.is_set():
                return None
            proc = None
            job = _WindowsJob() if sys.platform == "win32" else None
            try:
                options = (
                    {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
                    if sys.platform == "win32" else {"start_new_session": True}
                )
                proc = subprocess.Popen(
                    _gated_command(command), cwd=str(ROOT_DIR), env=env,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **options,
                )
                proc._flama_job = job
                proc._flama_session = sys.platform != "win32"
                self._active.add(proc)
                if job is not None:
                    job.assign_handle(proc._handle)
                deadline = time.monotonic() + BACKEND_CLEANUP_TIMEOUT
                while not os.path.exists(gate_path):
                    if self.stopped.is_set():
                        _terminate_process_tree(proc)
                        return proc
                    if proc.poll() is not None:
                        raise RuntimeError("worker bootstrap exited before launch gate")
                    if time.monotonic() >= deadline:
                        raise RuntimeError("worker bootstrap did not reach launch gate")
                    time.sleep(0.01)
                # py.exe may have created the gated interpreter before root
                # assignment; explicitly include that interpreter in the job.
                if job is not None:
                    job.assign_pid(int(Path(gate_path).read_text(encoding="ascii")))
                if self.stopped.is_set():
                    _terminate_process_tree(proc)
                else:
                    proc.stdin.write(b"1")
                    proc.stdin.flush()
                proc.stdin.close()
                return proc
            except BaseException:
                if proc is not None:
                    try:
                        _terminate_process_tree(proc)
                    finally:
                        self._active.discard(proc)
                        for pipe in (proc.stdin, proc.stdout):
                            if pipe is not None:
                                pipe.close()
                elif job is not None:
                    job.stop()
                raise

    def discard(self, proc):
        with self._lock:
            self._active.discard(proc)

    def stop_all(self):
        self.stopped.set()
        with self._lock:
            active = list(self._active)
        errors = []
        for proc in active:
            try:
                _terminate_process_tree(proc)
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError("; ".join(errors))


class _BoundedWorkerLog:
    """Drain all output, retaining only bounded head/tail diagnostics."""
    def __init__(self, pipe, limit=BACKEND_LOG_LIMIT_BYTES):
        self.pipe, self.limit = pipe, limit
        self.head, self.tail = bytearray(), bytearray()
        self.total = 0
        self.error = None
        self.thread = threading.Thread(target=self._drain, name="flama-worker-output", daemon=True)

    def start(self):
        self.thread.start()

    def _drain(self):
        part = max(1, (self.limit - 256) // 2)
        try:
            while True:
                chunk = os.read(self.pipe.fileno(), 64 * 1024)
                if not chunk:
                    break
                self.total += len(chunk)
                keep = min(len(chunk), max(0, part - len(self.head)))
                self.head.extend(chunk[:keep])
                self.tail.extend(chunk[keep:])
                if len(self.tail) > part:
                    del self.tail[:-part]
        except (OSError, ValueError) as exc:
            self.error = f"worker output drain failed: {exc}"

    def finish(self, path):
        self.thread.join(timeout=BACKEND_CLEANUP_TIMEOUT)
        if self.thread.is_alive():
            self.error = "worker output pipe stayed open after tree cleanup"
        self.pipe.close()
        kept = len(self.head) + len(self.tail)
        marker = (
            f"\n[OUTPUT TRUNCATED: retained head/tail; discarded {self.total - kept} bytes]\n".encode("ascii")
            if self.total > kept else b""
        )
        Path(path).write_bytes(bytes(self.head) + marker + bytes(self.tail))


def _validated_timeout(value):
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("--bin-timeout must be a finite non-negative number")
    return number or None


def _summary_from_manifest(document):
    names = {
        "FAIL": "failures", "ERROR": "errors", "skipped": "skipped",
        "expected failure": "expected failures", "unexpected success": "unexpected successes",
    }
    counts = {}
    for event in document["events"]:
        name = names.get(event["outcome"])
        if event["kind"] in {"outcome", "subtest", "fixture"} and name:
            counts[name] = counts.get(name, 0) + 1
    return UnittestSummary(document["tests_run"], document["success"], counts)


def _run_backend_bin(
    python_cmd, test_files, failfast, verbose, registry=None, *,
    log_path, base_env, timeout=None, manifest_path=None,
):
    from scripts.unittest_manifest import read_manifest
    timeout = _validated_timeout(timeout)
    start = time.monotonic()
    registry = registry or _WorkerRegistry()
    proc = capture = document = summary = None
    note = ""
    returncode = -1
    with tempfile.TemporaryDirectory(prefix="flama-backend-tests-") as media_root:
        internal_manifest = manifest_path or os.path.join(media_root, "manifest.json")
        gate_path = os.path.join(media_root, "launch.pid")
        env = build_parallel_worker_environment(media_root, base_env)
        env["FLAMA_TEST_MANIFEST_PATH"] = internal_manifest
        env["FLAMA_TEST_GATE_PID_PATH"] = gate_path
        env.update(TMPDIR=media_root, TMP=media_root, TEMP=media_root)
        try:
            proc = registry.launch(_manifest_command(python_cmd, test_files, failfast, verbose), env, gate_path)
            if proc is None:
                return BackendBinResult(test_files, None, None, time.monotonic() - start, None)
            capture = _BoundedWorkerLog(proc.stdout)
            capture.start()
            remaining = max(0.0, timeout - (time.monotonic() - start)) if timeout else None
            try:
                returncode = proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                note = f"\n[TIMEOUT] worker stopped after {timeout:g}s"
                _terminate_process_tree(proc)
                returncode = proc.returncode if proc.returncode not in (None, 0) else -1
        finally:
            if proc is not None:
                try:
                    _terminate_process_tree(proc)
                finally:
                    registry.discard(proc)
                    if capture is not None:
                        capture.finish(log_path)
                    else:
                        proc.stdout.close()
                    if proc.stdin is not None and not proc.stdin.closed:
                        proc.stdin.close()
        if capture is not None and capture.error:
            note += "\n[CLEANUP ERROR] " + capture.error
            returncode = -1
        try:
            document = read_manifest(internal_manifest)
            summary = _summary_from_manifest(document)
            if (returncode == 0) != document["success"]:
                note += "\n[MANIFEST ERROR] process exit disagrees with unittest completion"
                document = None
        except (OSError, ValueError) as exc:
            note += "\n[MANIFEST ERROR] " + str(exc)[:1024]
    return BackendBinResult(
        files=test_files, returncode=returncode, log_path=log_path,
        elapsed=time.monotonic() - start, summary=summary, note=note,
        manifest_path=manifest_path, manifest_data=document,
    )


def _format_counts(counts):
    return ", ".join(f"{name}={value}" for name, value in sorted(counts.items()) if value)


def write_test_manifest(bin_manifests, destination):
    from scripts.unittest_manifest import merge_manifests
    return merge_manifests(bin_manifests, destination)


def run_backend_tests_parallel(
    python_cmd, test_files, jobs, failfast=False, verbose=False,
    weights=None, timeout=None, manifest=None, seed=None,
):
    """Run managed unittest bins with bounded logs and process-tree cleanup."""
    from scripts.unittest_manifest import manifest_fingerprints, read_manifest
    timeout = _validated_timeout(timeout)
    if jobs < 1:
        raise ValueError("--jobs must be positive")
    if not test_files:
        return True
    # An interrupted/partial run must never leave an older successful export
    # at the requested path for another process to compare accidentally.
    if manifest:
        Path(manifest).unlink(missing_ok=True)
    bin_count = 1 if jobs == 1 else jobs * BACKEND_BINS_PER_JOB
    bins = partition_backend_tests(test_files, bin_count, weights, seed)
    registry = _WorkerRegistry()
    base_env = dict(os.environ)
    results = []
    started = time.monotonic()
    selected = json.dumps(sorted(test_files), ensure_ascii=True, separators=(",", ":")).encode("ascii")
    print(f"[SELECTION] {len(test_files)} files sha256={hashlib.sha256(selected).hexdigest()}")
    seed_note = f", partition seed {seed}" if seed is not None else ""
    print(f"[BACKEND] {len(test_files)} files in {len(bins)} bins across {jobs} jobs{seed_note}")
    sys.stdout.flush()
    previous_signals = {}
    executor = None
    futures = []
    manifest_error = False

    def on_signal(_signum, _frame):
        registry.stopped.set()
        raise KeyboardInterrupt

    try:
        if threading.current_thread() is threading.main_thread():
            for name in ("SIGINT", "SIGTERM"):
                signum = getattr(signal, name, None)
                if signum is not None:
                    previous_signals[signum] = signal.signal(signum, on_signal)
        with tempfile.TemporaryDirectory(prefix="flama-backend-logs-") as log_dir:
            def run_bin(index, files):
                if registry.stopped.is_set():
                    return BackendBinResult(files, None, None, 0.0, None)
                try:
                    result = _run_backend_bin(
                        python_cmd, files, failfast, verbose, registry,
                        log_path=os.path.join(log_dir, f"bin-{index:03d}.log"),
                        base_env=base_env, timeout=timeout,
                        manifest_path=os.path.join(log_dir, f"bin-{index:03d}.json"),
                    )
                except Exception as exc:
                    result = BackendBinResult(files, -1, None, 0.0, None, f"[WORKER ERROR] {exc!r}"[:2048])
                if failfast and result.started and not result.passed:
                    registry.stop_all()
                return result

            try:
                executor = ThreadPoolExecutor(max_workers=jobs)
                # Dispatch and consumption share the same cancellation scope.
                for index, files in enumerate(bins):
                    futures.append(executor.submit(run_bin, index, files))
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    if not result.started:
                        continue
                    label = "PASS" if result.passed else "FAIL"
                    ran = result.summary.ran if result.summary else "?"
                    print(f"[{label}] {len(result.files)} files, {ran} tests in {result.elapsed:.1f}s")
                    if verbose or not result.passed:
                        print("  " + "\n  ".join(result.files))
                        result.write_output(sys.stdout)
                    sys.stdout.flush()
            except BaseException:
                for signum in previous_signals:
                    signal.signal(signum, signal.SIG_IGN)
                registry.stop_all()
                for future in futures:
                    future.cancel()
                raise
            finally:
                # Stop before shutdown(wait=True), including during submit.
                try:
                    registry.stop_all()
                finally:
                    if executor is not None:
                        executor.shutdown(wait=True, cancel_futures=True)
                        executor = None
            if manifest:
                valid = [r for r in results if r.started and r.manifest_data is not None]
                if len(valid) != len(bins):
                    print("[MANIFEST] export unavailable: one or more bins did not finish validly")
                    manifest_error = True
                else:
                    try:
                        count, outcomes, digest = write_test_manifest([r.manifest_path for r in valid], manifest)
                        document = read_manifest(manifest)
                        print(f"[MANIFEST] {count} events ({_format_counts(outcomes) or 'none'}) sha256={digest} -> {manifest}")
                        print("[MANIFEST DETAILS] " + json.dumps(manifest_fingerprints(document), sort_keys=True))
                    except (OSError, ValueError) as exc:
                        print(f"[MANIFEST ERROR] {exc}")
                        manifest_error = True
    finally:
        for signum, previous in previous_signals.items():
            signal.signal(signum, previous)
    executed = [r for r in results if r.started]
    skipped_bins = [r for r in results if not r.started]
    failed = [r for r in executed if not r.passed]
    total_ran = sum(r.summary.ran for r in executed if r.summary)
    totals = {}
    for result in executed:
        for name, value in (result.summary.counts if result.summary else {}).items():
            totals[name] = totals.get(name, 0) + value
    if skipped_bins:
        print(f"[FAILFAST] {sum(len(r.files) for r in skipped_bins)} files were not started.")
    passed = not failed and not skipped_bins and not manifest_error and len(results) == len(bins)
    detail = _format_counts(totals)
    print(
        f"\n[{'PASS' if passed else 'FAIL'}] BACKEND {'PASSED' if passed else 'FAILED'} "
        f"({len(test_files)} files, {total_ran} tests"
        f"{', ' + detail if detail else ''} in {time.monotonic() - started:.2f}s with {jobs} jobs)"
    )
    for result in failed:
        print("  failed bin: " + ", ".join(result.files))
    return passed


def run_backend_tests(
    python_cmd, test_files, failfast=False, verbose=False, jobs=1,
    bin_timeout=None, manifest=None, partition_seed=None,
):
    """Keep one process by default, with identical correctness safeguards."""
    bin_timeout = _validated_timeout(bin_timeout)
    if not test_files:
        return True
    missing = [f for f in test_files if not (ROOT_DIR / f).is_file()]
    if missing:
        print("[BACKEND] Missing requested test files: " + ", ".join(missing))
        return False
    return run_backend_tests_parallel(
        python_cmd, list(test_files), jobs=max(1, min(jobs, len(test_files))),
        failfast=failfast, verbose=verbose, timeout=bin_timeout, manifest=manifest, seed=partition_seed,
    )


def run_frontend_tests(
    test_files: list[str],
    failfast: bool = False,
    verbose: bool = False,
) -> bool:
    """Execute targeted Vitest frontend tests."""
    if not test_files:
        return True

    fe_dir = ROOT_DIR / "frontend"
    if not fe_dir.is_dir():
        print("[ERROR] Frontend directory is missing for selected tests.", file=sys.stderr)
        return False

    # Ensure all test files actually exist on disk
    missing_tests = [f for f in test_files if not (fe_dir / f).exists()]
    if missing_tests:
        print(
            f"[ERROR] Frontend test file(s) do not exist on disk:\n"
            + "\n".join(f"  * {f}" for f in missing_tests),
            file=sys.stderr,
        )
        return False

    existing_tests = test_files

    print("\n" + "=" * 60)
    print(f"[*] Running {len(existing_tests)} Frontend Test Suite(s)")
    print("=" * 60)
    for tf in existing_tests:
        print(f"  * {tf}")
    print("-" * 60)

    npm_bin = shutil.which("npm.cmd") if sys.platform == "win32" else "npm"
    cmd = [npm_bin or "npm", "--prefix", "frontend", "test", "--", "--run"]
    if failfast:
        cmd.append("--bail=1")
    all_fe_tests = discover_all_frontend_tests()
    if set(existing_tests) < set(all_fe_tests):
        cmd.extend(existing_tests)

    start_time = time.time()
    res = subprocess.run(cmd, cwd=str(ROOT_DIR), shell=False)
    elapsed = time.time() - start_time

    if res.returncode == 0:
        print(f"\n[PASS] FRONTEND PASSED ({len(existing_tests)} files in {elapsed:.2f}s)")
        return True
    else:
        print(f"\n[FAIL] FRONTEND FAILED ({len(existing_tests)} files in {elapsed:.2f}s, exit code {res.returncode})")
        return False


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Flama Modular Test Runner - Execute focused tests based on modules or git changes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-c", "--changed",
        action="store_true",
        help="Auto-detect modified/added files from git and run relevant tests only.",
    )
    parser.add_argument(
        "-m", "--module",
        type=str,
        help="Comma-separated module names (e.g. 'study', 'auth,payment', 'decks').",
    )
    parser.add_argument(
        "-f", "--file",
        nargs="+",
        help="Direct file paths (source or test files) to test.",
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Run entire test suite across all modules.",
    )
    parser.add_argument(
        "-b", "--backend-only",
        action="store_true",
        help="Run only backend unittest suites.",
    )
    parser.add_argument(
        "--frontend-only", "--fe",
        action="store_true",
        help="Run only frontend vitest suites.",
    )
    parser.add_argument(
        "-l", "--list-modules",
        action="store_true",
        help="List all defined domain modules and their associated test counts.",
    )
    parser.add_argument(
        "--ci-plan",
        action="store_true",
        help="Print job-level CI decisions for the current event diff.",
    )
    parser.add_argument(
        "--github-output",
        type=str,
        help="Append --ci-plan decisions to this GitHub Actions output file.",
    )
    parser.add_argument(
        "--failfast",
        action="store_true",
        help="Stop execution on the first test failure.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose test execution output.",
    )
    parser.add_argument(
        "-j", "--jobs",
        default="1",
        help=(
            "Parallel backend unittest processes: a number or 'auto' (CPU/RAM capped). "
            "Default 1 keeps a single process; tests sharing one external "
            "database must keep it."
        ),
    )

    parser.add_argument(
        "--manifest",
        metavar="PATH",
        help=(
            "Write the structured backend case/outcome manifest to PATH and print "
            "its fingerprints; compare runs with scripts/compare_test_manifests.py."
        ),
    )
    parser.add_argument(
        "--partition-seed",
        type=int,
        help="With --jobs above 1, perturb file weights so a different grouping is tested.",
    )
    parser.add_argument(
        "--bin-timeout",
        type=float,
        default=0,
        help="Stop and fail any backend worker running longer than this many seconds (0 = no limit).",
    )

    args = parser.parse_args()
    try:
        resolve_backend_jobs(args.jobs, 1)
        _validated_timeout(args.bin_timeout)
    except ValueError as exc:
        parser.error(str(exc))

    # List modules mode
    if args.list_modules:
        print("\n[MODULES] Flama Domain Test Modules:")
        print(f"{'Module Name':<20} | {'Backend Tests':<15} | {'Frontend Tests':<15}")
        print("-" * 56)
        for mod, data in MODULES.items():
            b_cnt = len(data["backend_tests"])
            f_cnt = len(data["frontend_tests"])
            print(f"{mod:<20} | {b_cnt:<15} | {f_cnt:<15}")
        print("-" * 56)
        total_b = sum(len(d["backend_tests"]) for d in MODULES.values())
        total_f = sum(len(d["frontend_tests"]) for d in MODULES.values())
        print(f"{'TOTAL (Mapped)':<20} | {total_b:<15} | {total_f:<15}\n")
        return 0

    if args.ci_plan:
        changed = get_git_modified_files()
        force_all = str(os.environ.get("CI_FORCE_ALL_VALIDATION") or "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        deployed_sha = str(os.environ.get("DEPLOYED_RELEASE_SHA") or "").strip()
        since_deploy = files_changed_since(deployed_sha) if deployed_sha else None
        try:
            plan = build_ci_change_plan(
                changed,
                force_all_validation=force_all,
                files_since_deploy=since_deploy,
            )
        except ValueError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1
        print(json.dumps({
            "changed_files": changed,
            "deployed_release_sha": deployed_sha or None,
            "files_since_deploy": since_deploy,
            **plan,
        }, indent=2, sort_keys=True))
        if args.github_output:
            write_github_outputs(args.github_output, plan)
        return 0

    # Determine Python executable
    python_cmd = resolve_python_command()
    if args.verbose:
        print(f"[INFO] Using Python command: {' '.join(python_cmd)}")

    selected_backend_tests: set[str] = set()
    selected_frontend_tests: set[str] = set()
    target_modules: set[str] = set()

    if args.all:
        print("[MODE] Running ALL test suites across all modules.")
        target_modules.update(MODULES)
        # --all must discover the filesystem. MODULES intentionally supports
        # focused selection and may lag when a new test file is added.
        selected_backend_tests.update(discover_all_backend_tests())
        selected_frontend_tests.update(discover_all_frontend_tests())

    elif args.module:
        requested = [m.strip().lower() for m in args.module.split(",") if m.strip()]
        for req in requested:
            if req not in MODULES:
                print(f"[ERROR] Unknown module '{req}'. Use --list-modules to see valid names.", file=sys.stderr)
                return 1
            target_modules.add(req)
            selected_backend_tests.update(MODULES[req]["backend_tests"])
            selected_frontend_tests.update(MODULES[req]["frontend_tests"])
        print(f"[TARGET] Modules: {', '.join(sorted(target_modules))}")

    elif args.file:
        missing = [f for f in args.file if not (ROOT_DIR / f).exists()]
        if missing:
            print(
                f"[ERROR] Specified test/source file(s) do not exist:\n"
                + "\n".join(f"  * {f}" for f in missing),
                file=sys.stderr,
            )
            return 1
        mods, b_tests, f_tests = map_files_to_modules(args.file)
        target_modules.update(mods)
        selected_backend_tests.update(b_tests)
        selected_frontend_tests.update(f_tests)
        print(f"[TARGET] Files: {', '.join(args.file)}")
        print(f"[TARGET] Resolved Modules: {', '.join(sorted(target_modules)) if target_modules else 'None'}")
        if not selected_backend_tests and not selected_frontend_tests:
            print(f"[ERROR] No test suites resolved for specified file(s): {', '.join(args.file)}", file=sys.stderr)
            return 1

    elif args.changed or len(sys.argv) == 1:
        # Default behavior: run changed files
        changed = get_git_modified_files()
        if not changed:
            print("[INFO] No modified files detected by git. Everything is clean!")
            print("[TIP] Use '--module <name>' or '--all' to run tests explicitly.")
            return 0

        print(f"[GIT] Detected {len(changed)} modified file(s):")
        for ch in changed[:10]:
            print(f"  * {ch}")
        if len(changed) > 10:
            print(f"  * ... and {len(changed) - 10} more")

        try:
            mods, b_tests, f_tests = map_files_to_modules(changed, from_git_diff=True)
        except ValueError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1
        target_modules.update(mods)
        selected_backend_tests.update(b_tests)
        selected_frontend_tests.update(f_tests)
        print(f"[TARGET] Triggered Modules: {', '.join(sorted(target_modules)) if target_modules else 'None'}")

    else:
        parser.print_help()
        return 0

    # Layer filtering
    run_backend = not args.frontend_only
    run_frontend = not args.backend_only

    total_start = time.time()
    all_passed = True

    if run_backend and selected_backend_tests:
        backend_jobs = resolve_backend_jobs(args.jobs, len(selected_backend_tests))
        if str(args.jobs).strip().lower() != "auto" and backend_jobs > 1:
            limit = memory_worker_limit()
            if limit is not None and backend_jobs > limit:
                # An explicit count is honoured, but say when it may swap.
                print(
                    f"[WARN] --jobs {backend_jobs} exceeds the {limit} worker(s) that fit in free "
                    f"memory at {BACKEND_WORKER_MEMORY_BYTES // (1024 * 1024)} MiB each; "
                    "workers may swap or be killed."
                )
        backend_ok = run_backend_tests(
            python_cmd=python_cmd,
            test_files=sorted(selected_backend_tests),
            failfast=args.failfast,
            verbose=args.verbose,
            jobs=backend_jobs,
            bin_timeout=args.bin_timeout or None,
            manifest=args.manifest,
            partition_seed=args.partition_seed,
        )
        if not backend_ok:
            all_passed = False
            if args.failfast:
                return 1
    elif run_backend and not selected_backend_tests:
        print("\n[INFO] No backend tests required for selected target.")

    if run_frontend and selected_frontend_tests:
        frontend_ok = run_frontend_tests(
            test_files=sorted(selected_frontend_tests),
            failfast=args.failfast,
            verbose=args.verbose,
        )
        if not frontend_ok:
            all_passed = False
    elif run_frontend and not selected_frontend_tests:
        print("\n[INFO] No frontend tests required for selected target.")

    total_time = time.time() - total_start
    print("\n" + "=" * 60)
    if all_passed:
        print(f"[SUCCESS] ALL SELECTED TESTS PASSED in {total_time:.2f}s!")
        print("=" * 60 + "\n")
        return 0
    else:
        print(f"[FAILURE] SOME TESTS FAILED in {total_time:.2f}s.")
        print("=" * 60 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
