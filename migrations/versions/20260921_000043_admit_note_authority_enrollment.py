"""admit positive-epoch NOTE authority enrollment

Revision ID: 20260921_000043
Revises: 20260921_000042
Create Date: 2026-09-21 00:00:43

This migration widens only the persisted learner enrollment vocabulary. It
does not create enrollment rows, enable wire v4, or route any learner to NOTE.
Downgrade refuses while NOTE rows exist.
"""

from __future__ import annotations

from importlib import import_module

from alembic import op
import sqlalchemy as sa

from models.study_authority_enrollment import StudyAuthorityEnrollment


revision = "20260921_000043"
down_revision = "20260921_000042"
branch_labels = None
depends_on = None

TABLE_NAME = StudyAuthorityEnrollment.__tablename__
NEW_MODE_CHECK = "ck_study_authority_mode"
NEW_EPOCH_CHECK = "ck_study_authority_mode_epoch"
OLD_MODE_CHECK = "ck_study_authority_legacy_only"
OLD_EPOCH_CHECK = "ck_study_authority_epoch"


def _check_names(bind: sa.engine.Connection) -> set[str]:
    return {
        str(row.get("name") or "")
        for row in sa.inspect(bind).get_check_constraints(TABLE_NAME)
    }


def _replace_checks(*, downgrade: bool) -> None:
    bind = op.get_bind()
    names = _check_names(bind)
    drop_names = (
        (NEW_MODE_CHECK, NEW_EPOCH_CHECK)
        if downgrade
        else (OLD_MODE_CHECK, OLD_EPOCH_CHECK)
    )
    create_checks = (
        (
            (OLD_MODE_CHECK, "mode_code = 'LEGACY'"),
            (OLD_EPOCH_CHECK, "epoch >= 0"),
        )
        if downgrade
        else (
            (NEW_MODE_CHECK, "mode_code IN ('LEGACY','NOTE')"),
            (
                NEW_EPOCH_CHECK,
                "(mode_code = 'LEGACY' AND epoch >= 0) OR "
                "(mode_code = 'NOTE' AND epoch >= 1)",
            ),
        )
    )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(TABLE_NAME, recreate="always") as batch:
            for name in drop_names:
                if name in names:
                    batch.drop_constraint(name, type_="check")
            for name, sqltext in create_checks:
                if name not in names:
                    batch.create_check_constraint(name, sqltext)
        return
    for name in drop_names:
        if name in names:
            op.drop_constraint(name, TABLE_NAME, type_="check")
    for name, sqltext in create_checks:
        if name not in names:
            op.create_check_constraint(name, TABLE_NAME, sqltext)


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(TABLE_NAME):
        raise RuntimeError("Cannot admit NOTE authority: enrollment table is missing.")
    names = _check_names(bind)
    if {NEW_MODE_CHECK, NEW_EPOCH_CHECK}.issubset(names):
        foundation = import_module(
            "migrations.versions.20260921_000040_add_study_authority_fence"
        )
        foundation._assert_table_contract(
            bind,
            StudyAuthorityEnrollment.__table__,
        )
        return
    if not {OLD_MODE_CHECK, OLD_EPOCH_CHECK}.issubset(names):
        raise RuntimeError(
            "Enrollment CHECK constraints do not match revision 40 or 43."
        )
    _replace_checks(downgrade=False)
    foundation = import_module(
        "migrations.versions.20260921_000040_add_study_authority_fence"
    )
    foundation._assert_table_contract(bind, StudyAuthorityEnrollment.__table__)


def downgrade() -> None:
    bind = op.get_bind()
    table = StudyAuthorityEnrollment.__table__
    note_count = bind.execute(
        sa.select(sa.func.count()).select_from(table).where(
            table.c.mode_code == "NOTE"
        )
    ).scalar_one()
    if note_count:
        raise RuntimeError(
            "Cannot restore the LEGACY-only enrollment constraint while NOTE "
            f"rows exist: {note_count}. Fence them back through forward repair."
        )
    names = _check_names(bind)
    if {OLD_MODE_CHECK, OLD_EPOCH_CHECK}.issubset(names):
        return
    if not {NEW_MODE_CHECK, NEW_EPOCH_CHECK}.issubset(names):
        raise RuntimeError(
            "Enrollment CHECK constraints do not match revision 40 or 43."
        )
    _replace_checks(downgrade=True)
    foundation = import_module(
        "migrations.versions.20260921_000040_add_study_authority_fence"
    )
    foundation._assert_table_contract(bind, foundation.LEGACY_ENROLLMENT_TABLE)
