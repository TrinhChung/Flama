from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class LegacyMigrationMap(db.Model):
    __tablename__ = "legacy_migration_maps"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    entry_id = db.Column(db.Integer, db.ForeignKey("vocabulary_entries.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    note_id = db.Column(db.String(36), db.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id = db.Column(db.String(36), db.ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

