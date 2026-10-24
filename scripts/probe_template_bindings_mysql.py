"""Qualify advisory template mappings and typed note writes in disposable local MySQL."""

from contextlib import ExitStack
import importlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
import pymysql

from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

CASES = {
    "test_template_library.TemplateLibraryTests": [
        "test_mismatched_mapping_round_trips_with_warning_and_original_text",
        "test_array_note_writes_reject_text_and_accept_native_lists",
        "test_preview_accepts_arrays_and_source_type_metadata_without_saving",
        "test_invalid_schema_bindings_compile_and_body_are_atomic",
        "test_required_unbound_input_warns_and_renders_empty",
        "test_cross_user_ownership_hidden_and_no_binding_write",
    ],
    "test_study_template_application_sessions.StudyTemplateApplicationTests": [
        "test_mismatched_preset_and_transient_binding_keep_native_array_in_session",
        "test_transient_bindings_reject_malformed_unknown_and_out_of_scope",
        "test_session_binding_override_is_frozen_and_does_not_change_application",
    ],
    "test_study_template_presets.StudyTemplatePresetTests": [
        "test_saved_choice_and_binding_auto_apply_only_for_its_user_and_deck",
        "test_invalid_saved_bindings_leave_existing_preset_unchanged",
    ],
    "test_study_template_presets.StudyInstalledTemplatePresetTests": [
        "test_overlay_field_type_override_is_used_by_preset_validation",
    ],
    "test_study_typing_template.TypingTemplateArtifactTests": [
        "test_array_input_binds_to_text_field_and_reaches_the_content_artifact",
        "test_array_input_accepts_other_fields_with_a_warning",
        "test_array_field_type_is_created_saved_and_bound_but_never_switched_bare",
    ],
    "test_flashcard_validation_security.FlashcardValidationSecurityTests": [
        "test_array_field_accepts_safe_html_and_rejects_malicious_script",
        "test_required_array_field_rejects_empty_items_and_accepts_partially_filled",
    ],
}


def run():
    load_dotenv(ROOT / ".env", override=False)
    for flag in ("STUDY_WIRE_V4_ENABLED", "STUDY_ASYNC_BATCH_ENABLED", "STUDY_NEW_LEARNER_NOTE_ENABLED",
                 "STUDY_NOTE_COUNT_ENABLED", "STUDY_PROGRESS_SHADOW_WRITE_ENABLED",
                 "STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED", "STUDY_PROGRESS_SHADOW_COMPARE_ENABLED"):
        os.environ[flag] = ""
    from app import create_app
    from models import db

    settings = _connection_settings()
    name = f"flama_template_binding_probe_{os.getpid()}_{secrets.token_hex(6)}"
    apps = []
    created = False
    report = {"status": "FAIL", "configured_database_modified": False, "generated_schema": name}

    def guard():
        if (settings["host"] not in {"localhost", "127.0.0.1", "::1"}
                or not re.fullmatch(r"flama_template_binding_probe_[0-9]+_[a-f0-9]{12}", name)
                or name == os.getenv("DB_NAME")):
            raise RuntimeError("Qualification requires a generated loopback MySQL schema.")

    guard()
    admin = pymysql.connect(**settings)
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
            if cursor.fetchone():
                raise RuntimeError("Generated schema exists; refusing reuse.")
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]

        def factory(config):
            app = create_app({**config, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, name),
                              "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False})
            with app.app_context():
                if db.engine.url.database != name or set(db.engines) != {None}:
                    raise RuntimeError("Fixture engine is outside the generated schema.")
            apps.append(app)
            return app

        def drop_fixture_tables(*_args, **_kwargs):
            guard()
            if db.engine.url.database != name:
                raise RuntimeError("Refusing fixture teardown outside generated schema.")
            with db.engine.begin() as connection:
                connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
                try:
                    db.metadata.drop_all(bind=connection)
                finally:
                    connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")

        modules = {module: importlib.import_module(f"tests.{module}") for module in {
            *(key.split('.')[0] for key in CASES), "test_study_composition_service",
            "test_study_direct_note_replay", "test_study_session_install_usage",
        }}
        suite = unittest.TestSuite()
        for key, names in CASES.items():
            module, class_name = key.split('.')
            case_class = getattr(modules[module], class_name)
            suite.addTests(case_class(case) for case in names)
        with ExitStack() as stack:
            for module in modules.values():
                if hasattr(module, "create_app"):
                    stack.enter_context(patch.object(module, "create_app", side_effect=factory))
            stack.enter_context(patch.object(db, "drop_all", side_effect=drop_fixture_tables))
            output = io.StringIO()
            result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
        report.update(status="PASS" if result.wasSuccessful() else "FAIL", tests_run=result.testsRun,
                      failures=[trace for _, trace in result.failures + result.errors])
        if not result.wasSuccessful():
            print(output.getvalue(), file=sys.stderr)
        return report
    finally:
        for app in apps:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            guard()
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
            report["probe_database_dropped"] = True
        admin.close()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)
