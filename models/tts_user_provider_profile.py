from datetime import datetime

from models import db


class TtsUserProviderProfile(db.Model):
    __tablename__ = "tts_user_provider_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("tts_provider_config.id", ondelete="CASCADE"), nullable=False, index=True)

    encrypted_api_key = db.Column(db.Text, nullable=True)
    key_status = db.Column(db.String(32), nullable=False, default="unknown", index=True)
    last_validated_at = db.Column(db.DateTime, nullable=True)
    last_validation_error = db.Column(db.String(500), nullable=True)

    # Provider-specific per-user settings stored as JSON text.
    settings_json = db.Column(db.Text, nullable=False, default="{}")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "provider_id", name="uq_tts_user_provider_profile"),
    )
