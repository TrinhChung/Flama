"""Scoped identity provenance retained after schema definitions are removed."""
from datetime import datetime
from sqlalchemy.dialects.mysql import LONGTEXT

from models import db


class FieldValueIdentityDefinition(db.Model):
    __tablename__ = "field_value_identity_definitions"

    identity_key = db.Column(db.String(115), primary_key=True)
    identity_kind = db.Column(db.String(16), nullable=False)
    field_id = db.Column(db.String(36), nullable=True)
    # Deliberately detached: removal of a schema must not erase provenance.
    note_type_id = db.Column(db.String(36), nullable=True, index=True)
    deck_install_id = db.Column(db.String(36), nullable=True, index=True)
    retained_name = db.Column(db.String(255), nullable=False)
    label_history = db.Column(db.JSON, nullable=False, default=list)
    is_retired = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class FieldValueIdentityArchive(db.Model):
    """Immutable pre-cutover evidence; this table is never a runtime value reader."""
    __tablename__ = "field_value_identity_archive"

    object_kind = db.Column(db.String(16), primary_key=True)
    object_id = db.Column(db.String(115), primary_key=True)
    source_raw = db.Column(db.Text().with_variant(LONGTEXT(), "mysql"), nullable=False)
    captured_schema = db.Column(db.JSON, nullable=False)
    canonical_payload = db.Column(db.JSON, nullable=False)
    source_sha256 = db.Column(db.String(64), nullable=False)
    canonical_sha256 = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class FieldValueIdentityCutover(db.Model):
    __tablename__ = "field_value_identity_cutovers"

    id = db.Column(db.String(32), primary_key=True)
    state = db.Column(db.String(16), nullable=False)
    archive_count = db.Column(db.Integer, nullable=False)
    note_count = db.Column(db.Integer, nullable=False)
    media_count = db.Column(db.Integer, nullable=False)
    rename_job_count = db.Column(db.Integer, nullable=False)
    override_count = db.Column(db.Integer, nullable=False)
    archive_root_sha256 = db.Column(db.String(64), nullable=False)
    schema_sha256 = db.Column(db.String(64), nullable=False)
    definitions_sha256 = db.Column(db.String(64), nullable=False)
    writers_quiesced = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
