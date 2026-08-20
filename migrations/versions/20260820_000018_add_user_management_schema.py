"""add user management schema and permission audit logs

Revision ID: 20260820_000018
Revises: 20260814_000017
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_000018"
down_revision = "20260814_000017"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("users"):
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_disabled" not in user_columns:
            with op.batch_alter_table("users") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "is_disabled",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.text("0"),
                    )
                )

    if not inspector.has_table("user_permission_audit_logs"):
        op.create_table(
            "user_permission_audit_logs",
            sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
            sa.Column("actor_user_id", sa.Integer(), nullable=False),
            sa.Column("target_user_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("from_role_id", sa.Integer(), nullable=True),
            sa.Column("to_role_id", sa.Integer(), nullable=True),
            sa.Column("from_is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("to_is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("from_is_disabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("to_is_disabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("message", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["from_role_id"], ["user_roles.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["to_role_id"], ["user_roles.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_user_permission_audit_logs_actor_user_id", "user_permission_audit_logs", ["actor_user_id"])
        op.create_index("ix_user_permission_audit_logs_target_user_id", "user_permission_audit_logs", ["target_user_id"])
        op.create_index("ix_user_permission_audit_logs_action", "user_permission_audit_logs", ["action"])
        op.create_index("ix_user_permission_audit_logs_from_role_id", "user_permission_audit_logs", ["from_role_id"])
        op.create_index("ix_user_permission_audit_logs_to_role_id", "user_permission_audit_logs", ["to_role_id"])
        op.create_index("ix_user_permission_audit_logs_created_at", "user_permission_audit_logs", ["created_at"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("user_permission_audit_logs"):
        op.drop_table("user_permission_audit_logs")

    if inspector.has_table("users"):
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_disabled" in user_columns:
            with op.batch_alter_table("users") as batch_op:
                batch_op.drop_column("is_disabled")
