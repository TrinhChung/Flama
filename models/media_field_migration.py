from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class MediaFieldMigrationRun(db.Model):
    __tablename__ = "media_field_migration_runs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    mode = db.Column(db.String(32), nullable=False, default="audit")
    status = db.Column(db.String(32), nullable=False, default="running", index=True)
    scope_user_id = db.Column(db.Integer, nullable=True, index=True)
    scope_deck_id = db.Column(db.Integer, nullable=True, index=True)
    stats = db.Column(db.JSON, nullable=False, default=dict)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)

    items = db.relationship(
        "MediaFieldMigrationItem",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class MediaFieldMigrationItem(db.Model):
    __tablename__ = "media_field_migration_items"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    run_id = db.Column(
        db.String(36),
        db.ForeignKey("media_field_migration_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type = db.Column(db.String(32), nullable=False, index=True)
    entity_id = db.Column(db.String(36), nullable=False, index=True)
    field_name = db.Column(db.String(255), nullable=False)
    field_type = db.Column(db.String(32), nullable=True)
    action = db.Column(db.String(32), nullable=False, index=True)
    reason = db.Column(db.String(64), nullable=False, index=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    semantic_change = db.Column(db.Boolean, nullable=False, default=False)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    deck_id = db.Column(db.Integer, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    run = db.relationship("MediaFieldMigrationRun", back_populates="items")
