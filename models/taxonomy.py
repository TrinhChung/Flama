from __future__ import annotations

from datetime import datetime
from models import db


class TaxonomyDomain(db.Model):
    __tablename__ = "taxonomy_domains"

    id = db.Column(db.String(64), primary_key=True)
    label = db.Column(db.String(128), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    subjects = db.relationship(
        "TaxonomySubject",
        back_populates="domain",
        cascade="all, delete-orphan",
        order_by="TaxonomySubject.sort_order",
    )


class TaxonomySubject(db.Model):
    __tablename__ = "taxonomy_subjects"

    id = db.Column(db.String(64), primary_key=True)
    domain_id = db.Column(
        db.String(64),
        db.ForeignKey("taxonomy_domains.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = db.Column(db.String(128), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    domain = db.relationship("TaxonomyDomain", back_populates="subjects")
    frameworks = db.relationship(
        "TaxonomyFramework",
        back_populates="subject",
        cascade="all, delete-orphan",
        order_by="TaxonomyFramework.sort_order",
    )


class TaxonomyFramework(db.Model):
    __tablename__ = "taxonomy_frameworks"

    id = db.Column(db.String(64), primary_key=True)
    subject_id = db.Column(
        db.String(64),
        db.ForeignKey("taxonomy_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = db.Column(db.String(128), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    subject = db.relationship("TaxonomySubject", back_populates="frameworks")
    levels = db.relationship(
        "TaxonomyFrameworkLevel",
        back_populates="framework",
        cascade="all, delete-orphan",
        order_by="TaxonomyFrameworkLevel.sort_order",
    )


class TaxonomyFrameworkLevel(db.Model):
    __tablename__ = "taxonomy_framework_levels"

    id = db.Column(db.String(64), primary_key=True)
    framework_id = db.Column(
        db.String(64),
        db.ForeignKey("taxonomy_frameworks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = db.Column(
        db.String(64),
        db.ForeignKey("taxonomy_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = db.Column(db.String(128), nullable=False)
    difficulty_band = db.Column(db.String(32), nullable=False, default="beginner")
    suggested_tags = db.Column(db.JSON, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    framework = db.relationship("TaxonomyFramework", back_populates="levels")


class TaxonomyOption(db.Model):
    __tablename__ = "taxonomy_options"

    id = db.Column(db.String(64), primary_key=True)
    option_type = db.Column(db.String(32), primary_key=True)
    label = db.Column(db.String(128), nullable=False)
    sub_label = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class TaxonomySubjectOptionMap(db.Model):
    __tablename__ = "taxonomy_subject_option_maps"
    __table_args__ = (
        db.UniqueConstraint(
            "subject_id", "option_id", "option_type", name="uq_taxonomy_sub_opt_map"
        ),
        db.ForeignKeyConstraint(
            ["option_id", "option_type"],
            ["taxonomy_options.id", "taxonomy_options.option_type"],
            ondelete="CASCADE",
        ),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject_id = db.Column(
        db.String(64),
        db.ForeignKey("taxonomy_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_id = db.Column(db.String(64), nullable=False, index=True)
    option_type = db.Column(db.String(32), nullable=False, index=True)

    subject = db.relationship("TaxonomySubject")
    option = db.relationship("TaxonomyOption")
