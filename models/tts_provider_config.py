from datetime import datetime

from models import db


class TtsProviderConfig(db.Model):
    __tablename__ = "tts_provider_config"

    id = db.Column(db.Integer, primary_key=True)

    provider_name = db.Column(db.String(120), nullable=False, index=True)
    provider_type = db.Column(db.String(64), nullable=False, index=True)
    base_url = db.Column(db.String(500), nullable=True)

    requires_api_key = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, nullable=False, default=False, index=True)

    # JSON payload stored as text to keep cross-db compatibility (sqlite/mysql).
    shared_config_json = db.Column(db.Text, nullable=False, default="{}")
    provider_config_json = db.Column(db.Text, nullable=False, default="{}")
    default_settings_json = db.Column(db.Text, nullable=False, default="{}")

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    updated_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
