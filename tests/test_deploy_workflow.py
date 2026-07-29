"""Deployment workflow safety checks."""

from pathlib import Path
import unittest


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "deploy.yml"
)


class DeployWorkflowTests(unittest.TestCase):
    def test_database_migration_runs_before_data_bootstrap_and_activation(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        migration_position = workflow.index(
            '"$PROJECT_DIR/venv/bin/flask" --app wsgi.py db upgrade'
        )
        admin_bootstrap_position = workflow.index(
            '"$PROJECT_DIR/venv/bin/flask" --app wsgi.py bootstrap-admin-sync'
        )
        seed_position = workflow.index(
            '"$PROJECT_DIR/venv/bin/flask" --app wsgi.py seed-data-ensure'
        )
        activation_position = workflow.index(
            'ln -sfn "$release_dir" "$PROJECT_DIR/current"'
        )

        self.assertLess(migration_position, admin_bootstrap_position)
        self.assertLess(migration_position, seed_position)
        self.assertLess(migration_position, activation_position)

    def test_database_migration_uses_release_directory_and_managed_environment(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        migration_unit_start = workflow.index(
            '--unit="flama-db-migrate-$RELEASE_ID"'
        )
        migration_command_end = workflow.index(
            '"$PROJECT_DIR/venv/bin/flask" --app wsgi.py db upgrade'
        )
        migration_block = workflow[migration_unit_start:migration_command_end]

        self.assertIn(
            '--property="WorkingDirectory=$release_dir"',
            migration_block,
        )
        self.assertIn(
            '--property="EnvironmentFile=$desired_environment_file"',
            migration_block,
        )


if __name__ == "__main__":
    unittest.main()
