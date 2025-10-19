from datetime import datetime

from models import db


class VocabularyColumnPreference(db.Model):
    """Persist user-specific column widths for vocabulary lessons."""

    __tablename__ = "vocabulary_column_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    column_key = db.Column(db.String(64), nullable=False)
    width = db.Column(db.String(32), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "column_key", name="uq_vocab_column_pref"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<VocabularyColumnPreference user={self.user_id} column={self.column_key} width={self.width}>"
