from datetime import datetime

from models import db


class SupportDonationConfig(db.Model):
    __tablename__ = "support_donation_config"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False, default="Ủng hộ duy trì hệ thống")
    description = db.Column(db.Text, nullable=False)
    account_name = db.Column(db.String(255), nullable=False)
    account_number = db.Column(db.String(64), nullable=False)
    thank_you_message = db.Column(db.Text, nullable=False)

    qr_image_filename = db.Column(db.String(255), nullable=True)
    qr_image_storage_path = db.Column(db.String(1024), nullable=True)
    qr_image_mime_type = db.Column(db.String(64), nullable=True)

    updated_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
