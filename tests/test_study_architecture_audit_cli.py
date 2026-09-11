import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

from app import create_app, create_audit_app
from app.cli import run_study_architecture_audit_command
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_session import StudySession
from models.template import Template
from models.user import User


class StudyArchitectureAuditCLITests(unittest.TestCase):
    def setUp(self):
        self.app = create_audit_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    @staticmethod
    def _parse_audit_output(result) -> dict:
        text = (getattr(result, "stdout", None) or result.output).strip()
        return json.loads(text)

    def test_audit_cli_returns_zero_on_clean_db(self):
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["study-architecture-audit"])
        self.assertEqual(result.exit_code, 0)
        report = self._parse_audit_output(result)
        self.assertEqual(report["schema_version"], "study-architecture-audit.v4")
        self.assertEqual(report["verdicts"]["overall_status"], "PASS")
        self.assertEqual(report["verdicts"]["exit_code"], 0)

    def test_audit_cli_returns_one_on_warning(self):
        with self.app.app_context():
            user = User(username="warn-user", email="warn@example.com")
            user.password_hash = "mock_hash"
            db.session.add(user)
            db.session.flush()

            note_type = NoteType(user_id=user.id, name="EmptyNT")
            db.session.add(note_type)
            db.session.commit()

        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["study-architecture-audit"])
        self.assertEqual(result.exit_code, 1)
        report = self._parse_audit_output(result)
        self.assertEqual(report["verdicts"]["overall_status"], "WARN")
        self.assertEqual(report["verdicts"]["exit_code"], 1)

    def test_audit_cli_returns_two_on_blocker(self):
        with self.app.app_context():
            user = User(username="block-user", email="block@example.com")
            user.password_hash = "mock_hash"
            db.session.add(user)
            db.session.flush()

            nt_a = NoteType(user_id=user.id, name="A")
            nt_b = NoteType(user_id=user.id, name="B")
            db.session.add_all([nt_a, nt_b])
            db.session.flush()

            tmpl_b = Template(note_type_id=nt_b.id, name="B_Tmpl", position=0, is_default=True)
            db.session.add(tmpl_b)
            db.session.flush()

            note_a = Note(user_id=user.id, note_type_id=nt_a.id, field_values={})
            db.session.add(note_a)
            db.session.flush()

            cross_card = Card(note_id=note_a.id, template_id=tmpl_b.id)
            db.session.add(cross_card)
            db.session.commit()

        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["study-architecture-audit"])
        self.assertEqual(result.exit_code, 2)
        report = self._parse_audit_output(result)
        self.assertEqual(report["verdicts"]["overall_status"], "BLOCK")
        self.assertEqual(report["verdicts"]["exit_code"], 2)

    def test_audit_cli_compact_and_output_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = Path(tmp_dir) / "nested" / "dir" / "audit_result.json"
            runner = self.app.test_cli_runner()
            result = runner.invoke(
                args=["study-architecture-audit", "--compact", "--output", str(output_file)]
            )
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(output_file.exists())
            file_content = output_file.read_text(encoding="utf-8")
            report = json.loads(file_content)
            self.assertEqual(report["schema_version"], "study-architecture-audit.v4")
            # Compact file output has no 2-space indented lines
            self.assertNotIn('\n  "card_gates"', file_content)

    def test_audit_cli_accepts_frozen_observation_time(self):
        runner = self.app.test_cli_runner()
        result = runner.invoke(
            args=[
                "study-architecture-audit",
                "--compact",
                "--observed-at",
                "2026-09-10T03:04:05",
            ]
        )

        self.assertEqual(result.exit_code, 0)
        report = self._parse_audit_output(result)
        self.assertEqual(report["observed_at"], "2026-09-10T03:04:05")

    def test_audit_cli_handles_execution_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = Path(tmp_dir) / "error_out.json"
            with patch(
                "app.services.study_architecture_audit_service.build_study_architecture_audit",
                side_effect=RuntimeError("Simulated database connection crash"),
            ):
                runner = self.app.test_cli_runner()
                result = runner.invoke(
                    args=["study-architecture-audit", "--output", str(output_file)]
                )
                self.assertEqual(result.exit_code, 2)
                self.assertTrue(output_file.exists())
                file_report = json.loads(output_file.read_text(encoding="utf-8"))
                self.assertEqual(file_report["schema_version"], "study-architecture-audit.v4")
                self.assertEqual(file_report["verdicts"]["overall_status"], "BLOCK")
                self.assertEqual(file_report["verdicts"]["exit_code"], 2)
                self.assertIn("Simulated database connection crash", file_report["error"])

    def test_audit_cli_handles_missing_table_fail_closed(self):
        with self.app.app_context():
            # Drop card_progress table to simulate missing schema table
            db.session.execute(text("DROP TABLE card_progress"))
            db.session.commit()

        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["study-architecture-audit"])
        self.assertEqual(result.exit_code, 2)
        report = self._parse_audit_output(result)
        self.assertEqual(report["schema_version"], "study-architecture-audit.v4")
        self.assertEqual(report["verdicts"]["overall_status"], "BLOCK")
        self.assertEqual(report["verdicts"]["exit_code"], 2)
        self.assertIn("Audit execution error", report["verdicts"]["block"][0])

    def test_audit_cli_handles_missing_column_fail_closed(self):
        with self.app.app_context():
            # Drop and recreate study_sessions missing a critical column like snapshot_hash
            db.session.execute(text("DROP TABLE study_sessions"))
            db.session.execute(text("CREATE TABLE study_sessions (id INTEGER PRIMARY KEY, status VARCHAR(32))"))
            db.session.commit()

        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["study-architecture-audit"])
        self.assertEqual(result.exit_code, 2)
        report = self._parse_audit_output(result)
        self.assertEqual(report["schema_version"], "study-architecture-audit.v4")
        self.assertEqual(report["verdicts"]["overall_status"], "BLOCK")
        self.assertEqual(report["verdicts"]["exit_code"], 2)

    def test_audit_cli_handles_db_connection_error_fail_closed(self):
        # Create an app pointing to an unreachable/invalid database URI
        broken_app = create_audit_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:////non_existent_dir/broken_db.sqlite",
                "WTF_CSRF_ENABLED": False,
            }
        )
        runner = broken_app.test_cli_runner()
        result = runner.invoke(args=["study-architecture-audit"])
        self.assertEqual(result.exit_code, 2)
        report = self._parse_audit_output(result)
        self.assertEqual(report["schema_version"], "study-architecture-audit.v4")
        self.assertEqual(report["verdicts"]["overall_status"], "BLOCK")
        self.assertEqual(report["verdicts"]["exit_code"], 2)

    def test_audit_app_factory_startup_safety_before_creation(self):
        """Spies are installed BEFORE create_audit_app() runs to prove no mutators run on startup."""
        with patch("app.startup.ensure_user_management_schema") as mock_user_schema, \
             patch("app.startup.ensure_backward_compatible_schema") as mock_compat_schema, \
             patch("app.startup.ensure_default_user_roles") as mock_user_roles, \
             patch("app.startup.ensure_default_taxonomy_data") as mock_taxonomy, \
             patch("app.startup.ensure_default_tts_providers") as mock_tts, \
             patch("app.services.flashcards_share.cutover_clone_model_to_overlay_only") as mock_cutover, \
             patch("models.db.create_all") as mock_create_all:

            # Even if caller passes explicit True for maintenance flags, create_audit_app must override them to False
            audit_app = create_audit_app(
                {
                    "TESTING": True,
                    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                    "STARTUP_RUN_MAINTENANCE": True,
                    "STARTUP_RUN_DB_CREATE_ALL": True,
                    "STARTUP_RUN_USER_MANAGEMENT_SCHEMA": True,
                    "STARTUP_RUN_BACKWARD_COMPAT_SCHEMA": True,
                    "STARTUP_RUN_DEFAULT_USER_ROLE_SEED": True,
                    "STARTUP_RUN_DEFAULT_TAXONOMY_SEED": True,
                    "STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED": True,
                    "STARTUP_RUN_CLONE_CUTOVER": True,
                }
            )

            # Assert that during create_audit_app, NO mutator was called
            mock_create_all.assert_not_called()
            mock_user_schema.assert_not_called()
            mock_compat_schema.assert_not_called()
            mock_user_roles.assert_not_called()
            mock_taxonomy.assert_not_called()
            mock_tts.assert_not_called()
            mock_cutover.assert_not_called()

            # Assert that running the audit CLI command also calls zero mutators
            with audit_app.app_context():
                exit_code = run_study_architecture_audit_command(app=audit_app)
                # Since tables are not created (db.create_all was not run), audit should fail closed
                self.assertEqual(exit_code, 2)

            mock_create_all.assert_not_called()
            mock_user_schema.assert_not_called()
            mock_compat_schema.assert_not_called()
            mock_user_roles.assert_not_called()
            mock_taxonomy.assert_not_called()
            mock_tts.assert_not_called()
            mock_cutover.assert_not_called()

    def test_audit_subprocess_startup_safety_and_real_execution(self):
        """Real subprocess execution with STARTUP_RUN_MAINTENANCE=1 in environment."""
        import shutil
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "test_audit.sqlite"
            db_uri = f"sqlite:///{db_path.as_posix()}"
            out_json = Path(tmp_dir) / "out.json"

            # Create and populate schema first
            setup_app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": db_uri})
            with setup_app.app_context():
                db.create_all()
                db.session.remove()
                db.engine.dispose()

            # Execute real subprocess wsgi_audit.py with aggressive maintenance environment variables
            env = dict(os.environ)
            env["SQLALCHEMY_DATABASE_URI"] = db_uri
            env["STARTUP_RUN_MAINTENANCE"] = "1"
            env["STARTUP_RUN_DB_CREATE_ALL"] = "1"
            env["STARTUP_RUN_USER_MANAGEMENT_SCHEMA"] = "1"
            env["STARTUP_RUN_BACKWARD_COMPAT_SCHEMA"] = "1"
            env["STARTUP_RUN_DEFAULT_USER_ROLE_SEED"] = "1"
            env["STARTUP_RUN_DEFAULT_TAXONOMY_SEED"] = "1"
            env["STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED"] = "1"
            env["STARTUP_RUN_CLONE_CUTOVER"] = "1"

            proc = subprocess.run(
                [
                    sys.executable,
                    "wsgi_audit.py",
                    "--compact",
                    "--observed-at",
                    "2026-09-10T12:04:05+09:00",
                    "--output",
                    str(out_json),
                ],
                env=env,
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).resolve().parent.parent),
            )

            self.assertEqual(proc.returncode, 0, f"Subprocess failed: {proc.stderr}\n{proc.stdout}")
            self.assertTrue(out_json.exists())
            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], "study-architecture-audit.v4")
            self.assertEqual(report["observed_at"], "2026-09-10T03:04:05")
            self.assertEqual(report["verdicts"]["overall_status"], "PASS")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_audit_subprocess_empty_db_no_create_all(self):
        """Real subprocess execution against empty DB does NOT auto-create tables."""
        import shutil
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "empty_audit.sqlite"
            db_uri = f"sqlite:///{db_path.as_posix()}"

            env = dict(os.environ)
            env["SQLALCHEMY_DATABASE_URI"] = db_uri
            env["STARTUP_RUN_MAINTENANCE"] = "1"
            env["STARTUP_RUN_DB_CREATE_ALL"] = "1"

            proc = subprocess.run(
                [
                    sys.executable,
                    "wsgi_audit.py",
                    "--compact",
                ],
                env=env,
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).resolve().parent.parent),
            )

            # Because db.create_all was NOT run, the audit encounters missing tables and fails closed with code 2
            self.assertEqual(proc.returncode, 2)
            report = json.loads(proc.stdout)
            self.assertEqual(report["verdicts"]["overall_status"], "BLOCK")
            self.assertEqual(report["verdicts"]["exit_code"], 2)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_audit_deterministic_output_two_runs(self):
        """Two audit runs with fixed timestamp produce 100% byte-for-byte identical output."""
        from app.services.study_architecture_audit_service import build_study_architecture_audit

        with self.app.app_context():
            user = User(username="det-user", email="det@example.com")
            user.password_hash = "mock_hash"
            db.session.add(user)
            db.session.flush()

            # Multiple NoteTypes and Templates
            for i in range(5):
                nt = NoteType(user_id=user.id, name=f"NT_{i}")
                db.session.add(nt)
                db.session.flush()
                tmpl1 = Template(note_type_id=nt.id, name=f"Tmpl_{i}_A", position=0, is_default=True)
                tmpl2 = Template(note_type_id=nt.id, name=f"Tmpl_{i}_B", position=1, is_default=False)
                db.session.add_all([tmpl1, tmpl2])
                db.session.flush()

                note = Note(user_id=user.id, note_type_id=nt.id, field_values={})
                db.session.add(note)
                db.session.flush()

                c1 = Card(note_id=note.id, template_id=tmpl1.id)
                c2 = Card(note_id=note.id, template_id=tmpl2.id)
                db.session.add_all([c1, c2])
                db.session.flush()

                db.session.add_all(
                    [
                        CardProgress(user_id=user.id, card_id=c1.id, queue=1, interval_days=3, ease_factor=2500),
                        CardProgress(user_id=user.id, card_id=c2.id, queue=2, interval_days=5, ease_factor=2600),
                    ]
                )
            db.session.commit()

            fixed_time = datetime(2026, 8, 29, 12, 0, 0)
            report1 = build_study_architecture_audit(now=fixed_time)
            report2 = build_study_architecture_audit(now=fixed_time)

            payload1 = json.dumps(report1, ensure_ascii=False, sort_keys=True, indent=2)
            payload2 = json.dumps(report2, ensure_ascii=False, sort_keys=True, indent=2)

            self.assertEqual(payload1, payload2)
            self.assertEqual(
                report1["phase4_preflight"]["repository"]["code_manifest_sha256"],
                report2["phase4_preflight"]["repository"]["code_manifest_sha256"],
            )
            self.assertTrue(
                all(report1["phase4_preflight"]["progress"]["accounting"].values())
            )

    def test_audit_app_command_surface_isolation(self):
        """Audit app exposes ONLY study-architecture-audit and zero mutating commands."""
        mutating_commands = [
            "startup-maintenance",
            "clone-cutover-overlay",
            "taxonomy-seed",
            "taxonomy-verify",
            "user-role-seed",
            "tts-provider-seed",
            "vocab-seed",
            "dev-purge-data",
            "marketplace-samples-backfill",
            "market-stats-reconcile",
            "deck-release-bootstrap",
            "deck-notetype-audit",
            "bootstrap-admin-sync",
            "anki-normalize-entities",
            "payments-expire-stale",
            "quiz-dump-seed",
            "seed-data-ensure",
        ]
        self.assertIn("study-architecture-audit", self.app.cli.commands)
        for cmd in mutating_commands:
            self.assertNotIn(cmd, self.app.cli.commands, f"Mutating command '{cmd}' should not be on audit app")

        runner = self.app.test_cli_runner()
        res = runner.invoke(args=["startup-maintenance"])
        self.assertEqual(res.exit_code, 2)
        self.assertIn("No such command", res.output)

    def test_normal_app_command_surface_isolation(self):
        """Normal app does NOT register study-architecture-audit command."""
        normal_app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "STARTUP_RUN_MAINTENANCE": False,
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.assertNotIn("study-architecture-audit", normal_app.cli.commands)
        self.assertIn("startup-maintenance", normal_app.cli.commands)

        runner = normal_app.test_cli_runner()
        res = runner.invoke(args=["study-architecture-audit"])
        self.assertEqual(res.exit_code, 2)
        self.assertIn("No such command", res.output)

    def test_audit_cli_fails_on_normal_mutating_app(self):
        """Programmatic audit invocation rejects execution if app context was initialized with startup maintenance."""
        mutating_app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "STARTUP_RUN_MAINTENANCE": True,
                "WTF_CSRF_ENABLED": False,
            }
        )
        exit_code = run_study_architecture_audit_command(app=mutating_app)
        self.assertEqual(exit_code, 2)

    def test_audit_subprocess_command_surface_isolation(self):
        """Subprocess --help verifies exact command surface on wsgi_audit and wsgi entrypoints."""
        env = dict(os.environ)
        env.update(
            {
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "STARTUP_CHECK_DB_CONNECTIVITY": "0",
                "STARTUP_RUN_MAINTENANCE": "0",
            }
        )
        proc_audit = subprocess.run(
            [
                sys.executable,
                "-m",
                "flask",
                "--app",
                "wsgi_audit:create_app",
                "--help",
            ],
            env=env,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        self.assertEqual(proc_audit.returncode, 0, f"Error: {proc_audit.stderr}")
        self.assertIn("study-architecture-audit", proc_audit.stdout)
        self.assertNotIn("startup-maintenance", proc_audit.stdout)
        self.assertNotIn("clone-cutover-overlay", proc_audit.stdout)
        self.assertNotIn("vocab-seed", proc_audit.stdout)
        self.assertNotIn("dev-purge-data", proc_audit.stdout)

        proc_normal = subprocess.run(
            [
                sys.executable,
                "-m",
                "flask",
                "--app",
                "wsgi:create_app",
                "--help",
            ],
            env=env,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        self.assertEqual(proc_normal.returncode, 0, f"Error: {proc_normal.stderr}")
        self.assertNotIn("study-architecture-audit", proc_normal.stdout)
        self.assertIn("startup-maintenance", proc_normal.stdout)
        self.assertIn("clone-cutover-overlay", proc_normal.stdout)
        self.assertIn("vocab-seed", proc_normal.stdout)

    def test_audit_cli_output_write_failure_returns_two(self):
        """CLI returns exit code 2 and BLOCK report when writing output file fails."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Passing a directory path as output file causes open/write_text to fail
            invalid_output_path = tmp_dir
            runner = self.app.test_cli_runner()
            result = runner.invoke(args=["study-architecture-audit", "--output", str(invalid_output_path)])
            self.assertEqual(result.exit_code, 2)
            report = self._parse_audit_output(result)
            self.assertEqual(report["schema_version"], "study-architecture-audit.v4")
            self.assertEqual(report["verdicts"]["overall_status"], "BLOCK")
            self.assertEqual(report["verdicts"]["exit_code"], 2)
            self.assertIn("Failed to write audit output file", report["error"])

    def test_audit_subprocess_invalid_db_uri_fail_closed(self):
        """Subprocess with invalid DB URI returns exit code 2 and sanitized blocking JSON."""
        env = dict(os.environ)
        env["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://audit_user:super_secret_audit_pw@127.0.0.1:59999/non_existent_db"
        env["STARTUP_RUN_MAINTENANCE"] = "0"

        proc = subprocess.run(
            [
                sys.executable,
                "wsgi_audit.py",
                "--compact",
            ],
            env=env,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )

        self.assertEqual(proc.returncode, 2, f"Expected exit code 2, got {proc.returncode}. Output:\n{proc.stdout}\nStderr:\n{proc.stderr}")
        self.assertNotIn("super_secret_audit_pw", proc.stdout)
        self.assertNotIn("super_secret_audit_pw", proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["schema_version"], "study-architecture-audit.v4")
        self.assertEqual(report["verdicts"]["overall_status"], "BLOCK")
        self.assertEqual(report["verdicts"]["exit_code"], 2)
        self.assertIn("error", report)

    def test_audit_subprocess_output_write_failure_fail_closed(self):
        """Subprocess with output path write failure returns exit code 2 and BLOCK report."""
        import shutil
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "valid_audit.sqlite"
            db_uri = f"sqlite:///{db_path.as_posix()}"
            setup_app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": db_uri})
            with setup_app.app_context():
                db.create_all()
                db.session.remove()
                db.engine.dispose()

            env = dict(os.environ)
            env["SQLALCHEMY_DATABASE_URI"] = db_uri
            env["STARTUP_RUN_MAINTENANCE"] = "0"

            # Passing tmp_dir (a directory) as output path causes write failure
            proc = subprocess.run(
                [
                    sys.executable,
                    "wsgi_audit.py",
                    "--output",
                    str(tmp_dir),
                ],
                env=env,
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).resolve().parent.parent),
            )

            self.assertEqual(proc.returncode, 2)
            report = json.loads(proc.stdout)
            self.assertEqual(report["schema_version"], "study-architecture-audit.v4")
            self.assertEqual(report["verdicts"]["overall_status"], "BLOCK")
            self.assertEqual(report["verdicts"]["exit_code"], 2)
            self.assertIn("Failed to write audit output file", report["error"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
