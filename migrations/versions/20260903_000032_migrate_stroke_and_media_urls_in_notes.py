"""migrate stroke and media urls in notes

Revision ID: 20260903_000032
Revises: 20260902_000031
Create Date: 2026-09-03 00:00:32
"""

from __future__ import annotations


revision = "20260903_000032"
down_revision = "20260902_000031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Intentionally non-mutating. The original draft scanned every JSON key,
    # ignored FieldDef types, and converted MediaAsset UUIDs to filenames.
    # Production had not applied this revision when the defect was found.
    # Revision 20260904_000033 adds the audit schema; data conversion is then
    # performed by the idempotent, typed ``media-normalize-fields`` command.
    return


def downgrade() -> None:
    return
