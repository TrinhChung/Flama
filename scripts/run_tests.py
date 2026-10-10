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
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Repo root directory
ROOT_DIR = Path(__file__).resolve().parent.parent

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
            "tests/test_daily_rate_limit.py",
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
            "app/repositories/browse_card_repository.py",
            "app/repositories/logical_overlay_scope_repository.py",
            "app/presenters/vocabulary_presenter.py",
            "app/routes/vocabulary.py",
            "frontend/src/features/browse/**",
        ],
        "backend_tests": [
            "tests/test_flashcard_api_integration.py",
            "tests/test_flashcard_validation_security.py",
            "tests/test_rest_api_v1.py",
            "tests/test_study_note_overlay.py",
        ],
        "frontend_tests": [
            "src/features/browse/components/BrowseCardTable.test.tsx",
            "src/features/browse/components/MediaFieldPreview.test.tsx",
            "src/features/browse/components/BrowseAudioSelectorModal.test.tsx",
            "src/features/browse/components/BrowsePagination.test.tsx",
            "src/features/browse/pages/BrowsePage.test.tsx",
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
            "frontend/src/lib/ankiHtmlSanitizer*",
        ],
        "backend_tests": [
            "tests/test_flashcard_api_integration.py",
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
            "tests/test_field_answers_conversion.py",
        ],
        "frontend_tests": [
            "src/lib/ankiHtmlSanitizer.test.ts",
            "src/features/import/components/DeckSelectionTreeView.test.tsx",
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
            "app/validators/template_library.py",
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
            "frontend/src/features/template-library/**",
            "frontend/src/features/template-versions/**",
            "frontend/src/features/template-distribution/**",
            "frontend/src/features/template-applications/**",
            "frontend/src/features/library/pages/InstallTemplatesPage*",
            "frontend/src/features/study/hooks/useStudyTemplatePreparation*",
            "frontend/src/features/study/components/StudyTemplateFieldsDialog*"
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
            "tests/test_template_library.py",
            "tests/test_template_library_fe_contract.py",
            "tests/test_template_release_service.py",
            "tests/test_template_deck_release.py",
            "tests/test_template_attachment_writers.py",
            "tests/test_study_template_application_sessions.py",
            "tests/test_study_template_presets.py"
        ],
        "frontend_tests": [
            "src/entities/card-template/api/cardTemplateApi.test.ts",
            "src/entities/card-template/api/cardTemplateApi.adversarial.test.ts",
            "src/entities/card-template/lib/fieldMapping.test.ts",
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
            "src/features/template-library/model/useTemplateLibraryEditor.test.tsx",
            "src/features/template-library/pages/TemplateLibraryPage.test.tsx",
            "src/features/template-library/pages/TemplateDetailPage.test.tsx",
            "src/features/template-library/pages/TemplateLocalization.test.tsx",
            "src/features/template-library/pages/TemplateLibraryShell.test.tsx",
            "src/features/template-versions/ui/TemplateVersionHistorySheet.test.tsx",
            "src/features/note-types/lib/templateErrors.test.ts",
            "src/features/note-types/pages/NoteTypeDetailPage.editor.test.tsx",
            "src/features/note-types/pages/NoteTypeDetailPage.draft.test.tsx",
            "src/features/note-types/components/fields/FieldListCard.test.tsx",
            "src/features/note-types/components/fields/FieldEditorPreview.test.tsx",
            "src/features/note-types/hooks/useTemplateMappingDraft.test.ts",
            "src/features/note-types/pages/NoteTypeTemplateMappingPage.test.tsx",
            "src/shared/hooks/useUnsavedChangesGuard.test.tsx",
            "src/features/study/hooks/useStudySession.test.tsx",
            "src/features/study/pages/StudyPage.test.tsx",
            "src/features/study/session/contentPatchAdapter.test.ts",
            "src/features/study/session/contentPatchAdapter.adversarial.test.ts",
            "src/features/study/session/wireContract.test.ts",
            "src/features/study/session/sessionRestore.test.ts",
            "src/features/study/components/StudyQuickEditDialog.test.tsx",
            "src/lib/answersField.test.ts",
            "src/features/note-types/lib/answersConversion.test.ts",
            "src/features/note-types/components/fields/FieldAnswersConversionDialog.test.tsx",
        ]
    },
    "decks": {
        "source_patterns": [
            "app/api/v1/decks/**",
            "app/api/v1/creator/**",
            "app/services/deck_access_key*.py",
            "app/services/deck_naming*.py",
            "app/services/deck_release*.py",
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
        ],
        "backend_tests": [
            "tests/test_deck_access_keys.py",
            "tests/test_deck_api_hierarchical_create.py",
            "tests/test_deck_auto_publish_and_auto_update.py",
            "tests/test_deck_naming_service.py",
            "tests/test_deck_notetype_guard.py",
            "tests/test_deck_release_api.py",
            "tests/test_deck_release_schema.py",
            "tests/test_deck_settings_routes.py",
            "tests/test_owner_note_dirty_tracking_services.py",
            "tests/test_prune_releases.py",
            "tests/test_vocabulary_deck_tree_batch.py",
        ],
        "frontend_tests": [
            "src/features/dashboard/components/DeckModals.test.tsx",
            "src/features/dashboard/components/DeckTree.test.tsx",
            "src/features/dashboard/pages/DashboardPage.test.tsx",
            "src/features/dashboard/utils/deckNaming.test.ts",
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
        ],
        "backend_tests": [
            "tests/test_deck_change_request_flow.py",
            "tests/test_deck_install_rebase_flow.py",
            "tests/test_deck_publish_index.py",
            "tests/test_batched_deck_clone.py",
            "tests/test_shared_deck_detail_ui.py",
            "tests/test_shared_state_services.py",
            "tests/test_vocab_seed_sharing.py",
        ],
        "frontend_tests": [
            "src/features/deck-collaboration/api.test.ts",
            "src/features/deck-collaboration/components/DiffWorkspace.test.tsx",
            "src/features/deck-collaboration/pages/ChangeRequestInboxPage.test.tsx",
            "src/features/deck-collaboration/pages/InstalledDeckUpdatePage.test.tsx",
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
            "src/features/marketplace/components/DeckCard.test.tsx",
            "src/features/marketplace/components/PublishDeckTree.test.tsx",
            "src/features/marketplace/publishApi.test.ts",
            "src/features/marketplace/pages/MarketplacePages.test.tsx",
        ],
    },
    "connect_mcp": {
        "source_patterns": [
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
            "frontend/src/lib/ankiSync*",
        ],
        "backend_tests": [
            "tests/test_anki_content_normalizer.py",
            "tests/test_flama_connect.py",
            "tests/test_flama_connect_auth.py",
            "tests/test_connect_protocol.py",
            "tests/test_flama_connect_mcp.py",
            "tests/test_mcp_access_tokens.py",
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
            "src/lib/ankiSyncEngine.test.ts",
            "src/lib/ankiSyncPackages.test.ts",
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
        "source_patterns": ["app/routes/seo.py", "app/services/seo_service.py"],
        "backend_tests": [
            "tests/test_seo_routes.py",
            "tests/test_seo_adversarial.py",
            "tests/test_schema_jsonld.py",
        ],
        "frontend_tests": [],
    },
    "admin": {
        "source_patterns": [
            "app/api/v1/admin/**",
            "app/services/admin_*.py",
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
            "tests/test_admin_payouts_api.py",
            "tests/test_admin_rest_api_v1.py",
            "tests/test_admin_user_roles.py",
            "tests/test_bootstrap_admin_credentials.py",
            "tests/test_bootstrap_admin_sync.py",
        ],
        "frontend_tests": [],
    },
    "analytics": {
        "source_patterns": [
            "app/api/v1/analytics/**",
            "app/services/deck_aggregation_service.py",
            "app/services/study_analytics_read_service.py",
            "app/services/stats_*.py",
            "app/services/dashboard_service.py",
            "app/repositories/stats_query_repository.py",
            "app/repositories/note_analytics_read_repository.py",
            "app/services/review_analytics_*.py",
            "app/repositories/review_analytics_*.py",
            "app/services/deck_count_*.py",
            "app/repositories/deck_count_*.py",
            "models/review_analytics.py",
            "models/deck_count_snapshot.py",
            "migrations/versions/20261005_000051_*.py",
            "migrations/versions/*_000052_*.py",
            "scripts/probe_review_analytics_mysql.py",
            "scripts/bench_analytics_counts_mysql.py",
            "scripts/probe_deck_counts_mysql.py",
            "scripts/probe_p5_analytics_mysql.py",
            "scripts/probe_dashboard_due_counts_mysql.py",
        ],
        "backend_tests": [
            "tests/test_deck_aggregation_service.py",
            "tests/test_note_analytics_read.py",
            "tests/test_stats_overview.py",
            "tests/test_stats_study_time.py",
            "tests/test_stats_today_future.py",
            "tests/test_review_analytics_schema.py",
            "tests/test_review_analytics_policy.py",
            "tests/test_review_analytics_projection.py",
            "tests/test_review_analytics_backfill.py",
            "tests/test_review_analytics_reads.py",
            "tests/test_review_analytics_mysql_probe.py",
            "tests/test_review_analytics_study_integration.py",
            "tests/test_deck_count_snapshots.py",
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
            "scripts/probe_p1_02_mysql_concurrency.py",
            "scripts/run_phase4_preflight_bundle.py",
            "scripts/probe_p5_study_batch_mysql.py",
            "scripts/run_p5_vps_preflight.py",
        ],
        "backend_tests": [
            "tests/test_app_startup.py",
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
    "tooling": {
        "source_patterns": [
            ".github/workflows/**",
            "deploy/**",
            "scripts/launch_chrome_devtools.*",
            "scripts/run_lighthouse_audit.*",
            "scripts/run_tests.py",
            "scripts/check_*.py",
            "scripts/setup_github_workspace.sh",
            "scripts/setup_new_device.sh",
            "scripts/setup_venv.sh",
            "scripts/update_route_snapshot.py",
            "scripts/deploy_cloudflare_cache_rule.py",
            "fix_deck_imports.py",
            "update_imports.py",
            "wsgi_audit.py",
        ],
        "backend_tests": [
            "tests/test_ci_workflow.py",
            "tests/test_cloudflare_cache_rule.py",
            "tests/test_deploy_environment_consistency.py",
            "tests/test_deploy_workflow.py",
            "tests/test_flama_audio_release_workflow.py",
            "tests/test_modular_test_runner.py",
            "tests/test_test_mapping_coverage.py",
        ],
        "frontend_tests": [],
    },
    "agent_skills": {
        "source_patterns": [
            "skills/**",
            ".claude/skills/**",
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
            "app/services/daily_rate_limit_service.py",
            "app/services/redis_state_service.py",
            "app/services/rest_api_service.py",
            "app/utils/__init__.py",
            "app/utils/deck_move_token.py",
            "app/utils/logging_redactor.py",
            "app/utils/permissions.py",
            "app/utils/redirects.py",
            "app/validators/__init__.py",
            "app/presenters/__init__.py",
            "app/repositories/__init__.py",
            "models/__init__.py",
            "models/audit_log.py",
            "models/column_preference.py",
            "models/creator_feature_policy.py",
            "models/field_rename_job.py",
            "models/media_field_migration.py",
            "models/model_uuid.py",
            "wsgi.py",
            "frontend/src/shared/**",
        ],
        "backend_tests": [
            "tests/test_app_startup.py",
            "tests/test_api_v1_route_map.py",
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
    "pyproject.toml",
    "setup.cfg",
)

FULL_FRONTEND_SOURCE_PATTERNS = (
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/vite.config.ts",
    "frontend/vitest.config.ts",
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
    "app/services/daily_rate_limit_service.py",
    "app/api/v1/health.py",
    "requirements.txt",
    "tests/test_shared_state_services.py",
)

MYSQL_CONTRACT_SOURCE_PATTERNS = (
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
    "scripts/probe_p5_analytics_mysql.py",
    "tests/test_note_analytics_read.py",
    "app/services/review_analytics_*.py",
    "app/repositories/review_analytics_*.py",
    "app/services/deck_count_*.py",
    "app/repositories/deck_count_*.py",
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


def map_files_to_modules(changed_files: list[str]) -> tuple[set[str], set[str], set[str]]:
    """
    Given a list of changed files, determine affected module names,
    backend test files, and frontend test files.
    """
    matched_modules: set[str] = set()
    backend_modules: set[str] = set()
    frontend_modules: set[str] = set()
    backend_tests: set[str] = set()
    frontend_tests: set[str] = set()

    for file_path in changed_files:
        norm_path = file_path.replace("\\", "/")

        # A direct test edit runs that test only. Module names remain useful in
        # diagnostics, but must not expand one test file into a whole domain.
        if norm_path.startswith("tests/test_") and norm_path.endswith(".py"):
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
                for path in discover_all_frontend_tests()
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
            backend_tests.update(discover_all_backend_tests())
            matched = True
        if any(
            fnmatch.fnmatch(norm_path, pattern)
            for pattern in FULL_FRONTEND_SOURCE_PATTERNS
        ):
            frontend_tests.update(discover_all_frontend_tests())
            matched = True

        if not matched:
            # Fail safe when the catalog is stale: run the affected layer in
            # full rather than silently substituting unrelated core tests.
            if norm_path.startswith("app/") or norm_path.startswith("models/"):
                backend_tests.update(discover_all_backend_tests())
            elif is_frontend_source:
                frontend_tests.update(discover_all_frontend_tests())

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
    _, backend_tests, frontend_tests = map_files_to_modules(normalized)

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


def build_backend_test_environment(media_root: str) -> dict[str, str]:
    """Build an isolated environment for the backend test subprocess."""
    env = dict(os.environ)
    env["FLAMA_TEST_MEDIA_UPLOAD_ROOT"] = media_root
    env["FLASHCARD_MEDIA_UPLOAD_ROOT"] = media_root
    # Rate-limit tests opt in explicitly through their app config. Disabling the
    # default here prevents module-level counters from leaking across test apps.
    env["RATE_LIMIT_DAILY_ENABLED"] = "0"
    return env

def run_backend_tests(
    python_cmd: list[str],
    test_files: list[str],
    failfast: bool = False,
    verbose: bool = False,
) -> bool:
    """Execute targeted Python backend tests using unittest."""
    if not test_files:
        return True

    # Filter to files that actually exist on disk
    existing_tests = [f for f in test_files if (ROOT_DIR / f).exists()]
    if not existing_tests:
        print("[BACKEND] No existing backend test files to run.")
        return True

    print("\n" + "=" * 60)
    print(f"[*] Running {len(existing_tests)} Backend Test Suite(s)")
    print("=" * 60)
    for tf in existing_tests:
        print(f"  * {tf}")
    print("-" * 60)

    cmd = list(python_cmd) + ["-m", "unittest"]
    if failfast:
        cmd.append("-f")
    if verbose:
        cmd.append("-v")
    cmd.extend(existing_tests)

    start_time = time.time()
    with tempfile.TemporaryDirectory(prefix="flama-backend-tests-") as media_root:
        res = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            env=build_backend_test_environment(media_root),
        )
    elapsed = time.time() - start_time

    if res.returncode == 0:
        print(f"\n[PASS] BACKEND PASSED ({len(existing_tests)} files in {elapsed:.2f}s)")
        return True
    else:
        print(f"\n[FAIL] BACKEND FAILED ({len(existing_tests)} files in {elapsed:.2f}s, exit code {res.returncode})")
        return False


def run_frontend_tests(
    test_files: list[str],
    failfast: bool = False,
    verbose: bool = False,
) -> bool:
    """Execute targeted Vitest frontend tests."""
    if not test_files:
        return True

    fe_dir = ROOT_DIR / "frontend"
    if not fe_dir.exists():
        return True

    # Filter to files that exist in frontend/
    existing_tests = [f for f in test_files if (fe_dir / f).exists()]
    if not existing_tests:
        print("[FRONTEND] No existing frontend test files to run.")
        return True

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

    args = parser.parse_args()

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
        plan = build_ci_change_plan(
            changed,
            force_all_validation=force_all,
            files_since_deploy=since_deploy,
        )
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
        mods, b_tests, f_tests = map_files_to_modules(args.file)
        target_modules.update(mods)
        selected_backend_tests.update(b_tests)
        selected_frontend_tests.update(f_tests)
        print(f"[TARGET] Files: {', '.join(args.file)}")
        print(f"[TARGET] Resolved Modules: {', '.join(sorted(target_modules)) if target_modules else 'None'}")

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

        mods, b_tests, f_tests = map_files_to_modules(changed)
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
        backend_ok = run_backend_tests(
            python_cmd=python_cmd,
            test_files=sorted(selected_backend_tests),
            failfast=args.failfast,
            verbose=args.verbose,
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
