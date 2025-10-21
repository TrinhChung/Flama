"""Data hierarchy for vocabulary content."""

from datetime import datetime

from models import db


class VocabularyLevel(db.Model):
    __tablename__ = "vocabulary_levels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    topics = db.relationship(
        "VocabularyTopic",
        back_populates="level",
        cascade="all, delete-orphan",
        order_by="VocabularyTopic.position",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<VocabularyLevel id={self.id} name={self.name!r}>"


class VocabularyTopic(db.Model):
    __tablename__ = "vocabulary_topics"

    id = db.Column(db.Integer, primary_key=True)
    level_id = db.Column(db.Integer, db.ForeignKey("vocabulary_levels.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    level = db.relationship("VocabularyLevel", back_populates="topics")
    lessons = db.relationship(
        "VocabularyLesson",
        back_populates="topic",
        cascade="all, delete-orphan",
        order_by="VocabularyLesson.position",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<VocabularyTopic id={self.id} name={self.name!r} level_id={self.level_id}>"


class VocabularyLesson(db.Model):
    __tablename__ = "vocabulary_lessons"

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("vocabulary_topics.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    page_size = db.Column(db.Integer, nullable=False, default=60)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    topic = db.relationship("VocabularyTopic", back_populates="lessons")
    entries = db.relationship(
        "VocabularyEntry",
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="VocabularyEntry.id",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<VocabularyLesson id={self.id} title={self.title!r} topic_id={self.topic_id}>"

