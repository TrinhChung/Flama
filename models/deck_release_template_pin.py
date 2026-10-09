"""Frozen presentation and attachment state belonging to one deck release."""

from models import db


class DeckReleaseTemplatePin(db.Model):
    __tablename__ = "deck_release_template_pins"

    deck_release_id = db.Column(db.String(36), db.ForeignKey("deck_releases.id", ondelete="CASCADE"), primary_key=True)
    source_template_id = db.Column(db.String(36), db.ForeignKey("templates.id", ondelete="RESTRICT"), primary_key=True, index=True)
    template_release_id = db.Column(db.String(36), db.ForeignKey("template_releases.id", ondelete="RESTRICT"), nullable=False, index=True)
    applications_json = db.Column(db.JSON, nullable=False, default=dict)
