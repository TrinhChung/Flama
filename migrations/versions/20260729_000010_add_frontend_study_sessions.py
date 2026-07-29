"""add frontend-driven study sessions

Revision ID: 20260729_000010
Revises: 20260726_000009
Create Date: 2026-07-29 00:00:10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260729_000010"
down_revision = "20260726_000009"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {row["name"] for row in _inspector().get_columns(table_name)}


def _unique_constraint_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {
        row["name"]
        for row in _inspector().get_unique_constraints(table_name)
        if row.get("name")
    }


def _foreign_key_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {
        row["name"]
        for row in _inspector().get_foreign_keys(table_name)
        if row.get("name")
    }


def _has_foreign_key(
    table_name: str,
    constrained_columns: list[str],
    referred_table: str,
) -> bool:
    if not _table_exists(table_name):
        return False
    expected_columns = list(constrained_columns)
    return any(
        list(row.get("constrained_columns") or []) == expected_columns
        and row.get("referred_table") == referred_table
        for row in _inspector().get_foreign_keys(table_name)
    )


def upgrade() -> None:
    if not _table_exists("study_sessions"):
        op.create_table(
            "study_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("scope_type", sa.String(length=20), nullable=False),
            sa.Column("scope_id", sa.String(length=64), nullable=False),
            sa.Column("local_deck_id", sa.Integer(), nullable=True),
            sa.Column("clone_install_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("scheduler_algorithm", sa.String(length=64), nullable=False),
            sa.Column("algorithm_version", sa.String(length=32), nullable=False),
            sa.Column("wire_schema_version", sa.String(length=32), nullable=False),
            sa.Column("timezone", sa.String(length=64), nullable=False),
            sa.Column("day_boundary_hour_local", sa.Integer(), nullable=False),
            sa.Column("learn_ahead_seconds", sa.Integer(), nullable=False),
            sa.Column("snapshot_hash", sa.String(length=80), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("config_snapshot_json", sa.Text(), nullable=False),
            sa.Column("opened_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("committed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["clone_install_id"],
                ["deck_installs.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["local_deck_id"],
                ["decks.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_study_sessions_user_status_expires",
            "study_sessions",
            ["user_id", "status", "expires_at"],
            unique=False,
        )
        op.create_index(
            "ix_study_sessions_clone_install_id",
            "study_sessions",
            ["clone_install_id"],
            unique=False,
        )
        op.create_index(
            "ix_study_sessions_local_deck_id",
            "study_sessions",
            ["local_deck_id"],
            unique=False,
        )
        op.create_index(
            "ix_study_sessions_snapshot_hash",
            "study_sessions",
            ["snapshot_hash"],
            unique=False,
        )
        op.create_index(
            "ix_study_sessions_status",
            "study_sessions",
            ["status"],
            unique=False,
        )
        op.create_index(
            "ix_study_sessions_expires_at",
            "study_sessions",
            ["expires_at"],
            unique=False,
        )
        op.create_index(
            "ix_study_sessions_user_id",
            "study_sessions",
            ["user_id"],
            unique=False,
        )

    if not _table_exists("study_session_cards"):
        op.create_table(
            "study_session_cards",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("card_id", sa.String(length=36), nullable=False),
            sa.Column("source_deck_id", sa.Integer(), nullable=True),
            sa.Column("local_deck_id", sa.Integer(), nullable=True),
            sa.Column("note_type_id", sa.String(length=36), nullable=True),
            sa.Column("scheduler_preset_id", sa.Integer(), nullable=True),
            sa.Column(
                "base_progress_revision",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("base_state_hash", sa.String(length=80), nullable=False),
            sa.Column("scheduler_config_hash", sa.String(length=80), nullable=False),
            sa.Column("initial_state_json", sa.Text(), nullable=False),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["card_id"],
                ["cards.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["local_deck_id"],
                ["decks.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["scheduler_preset_id"],
                ["scheduler_presets.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["session_id"],
                ["study_sessions.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "session_id",
                "card_id",
                name="uq_study_session_cards_session_card",
            ),
        )
        op.create_index(
            "ix_study_session_cards_session_ordinal",
            "study_session_cards",
            ["session_id", "ordinal"],
            unique=False,
        )
        op.create_index(
            "ix_study_session_cards_card_id",
            "study_session_cards",
            ["card_id"],
            unique=False,
        )
        op.create_index(
            "ix_study_session_cards_local_deck_id",
            "study_session_cards",
            ["local_deck_id"],
            unique=False,
        )
        op.create_index(
            "ix_study_session_cards_scheduler_config_hash",
            "study_session_cards",
            ["scheduler_config_hash"],
            unique=False,
        )
        op.create_index(
            "ix_study_session_cards_session_id",
            "study_session_cards",
            ["session_id"],
            unique=False,
        )

    if not _table_exists("study_session_commits"):
        op.create_table(
            "study_session_commits",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("idempotency_key", sa.String(length=64), nullable=False),
            sa.Column("request_hash", sa.String(length=80), nullable=False),
            sa.Column("response_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["session_id"],
                ["study_sessions.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "session_id",
                "idempotency_key",
                name="uq_study_session_commits_idempotency",
            ),
            sa.UniqueConstraint(
                "session_id",
                name="uq_study_session_commits_single_success",
            ),
        )
        op.create_index(
            "ix_study_session_commits_session_id",
            "study_session_commits",
            ["session_id"],
            unique=False,
        )
        op.create_index(
            "ix_study_session_commits_user_id",
            "study_session_commits",
            ["user_id"],
            unique=False,
        )

    if "revision" not in _column_names("card_progress"):
        op.add_column(
            "card_progress",
            sa.Column(
                "revision",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            ),
        )
        op.execute(
            sa.text(
                "UPDATE card_progress SET revision = 1 "
                "WHERE COALESCE(reps, 0) > 0 OR last_reviewed_at IS NOT NULL"
            )
        )

    review_columns = _column_names("review_events")
    for column in (
        sa.Column("study_session_id", sa.String(length=36), nullable=True),
        sa.Column("client_event_id", sa.String(length=36), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.Column("scheduler_algorithm", sa.String(length=64), nullable=True),
        sa.Column("algorithm_version", sa.String(length=32), nullable=True),
        sa.Column("scheduler_config_hash", sa.String(length=80), nullable=True),
    ):
        if column.name not in review_columns:
            op.add_column("review_events", column)

    review_indexes = {
        row["name"] for row in _inspector().get_indexes("review_events")
    }
    if "ix_review_events_study_session_id" not in review_indexes:
        op.create_index(
            "ix_review_events_study_session_id",
            "review_events",
            ["study_session_id"],
            unique=False,
        )
    if not _has_foreign_key(
        "review_events",
        ["study_session_id"],
        "study_sessions",
    ):
        op.create_foreign_key(
            "fk_review_events_study_session_id",
            "review_events",
            "study_sessions",
            ["study_session_id"],
            ["id"],
            ondelete="SET NULL",
        )
    unique_names = _unique_constraint_names("review_events")
    if "uq_review_events_user_client_event" not in unique_names:
        op.create_unique_constraint(
            "uq_review_events_user_client_event",
            "review_events",
            ["user_id", "client_event_id"],
        )
    if "uq_review_events_session_sequence" not in unique_names:
        op.create_unique_constraint(
            "uq_review_events_session_sequence",
            "review_events",
            ["study_session_id", "sequence_no"],
        )


def downgrade() -> None:
    if _table_exists("review_events"):
        unique_names = _unique_constraint_names("review_events")
        if "uq_review_events_session_sequence" in unique_names:
            op.drop_constraint(
                "uq_review_events_session_sequence",
                "review_events",
                type_="unique",
            )
        if "uq_review_events_user_client_event" in unique_names:
            op.drop_constraint(
                "uq_review_events_user_client_event",
                "review_events",
                type_="unique",
            )
        if "fk_review_events_study_session_id" in _foreign_key_names(
            "review_events"
        ):
            op.drop_constraint(
                "fk_review_events_study_session_id",
                "review_events",
                type_="foreignkey",
            )
        if "ix_review_events_study_session_id" in {
            row["name"] for row in _inspector().get_indexes("review_events")
        }:
            op.drop_index(
                "ix_review_events_study_session_id",
                table_name="review_events",
            )
        for name in (
            "scheduler_config_hash",
            "algorithm_version",
            "scheduler_algorithm",
            "sequence_no",
            "client_event_id",
            "study_session_id",
        ):
            if name in _column_names("review_events"):
                op.drop_column("review_events", name)

    if "revision" in _column_names("card_progress"):
        op.drop_column("card_progress", "revision")
    if _table_exists("study_session_commits"):
        op.drop_table("study_session_commits")
    if _table_exists("study_session_cards"):
        op.drop_table("study_session_cards")
    if _table_exists("study_sessions"):
        op.drop_table("study_sessions")
