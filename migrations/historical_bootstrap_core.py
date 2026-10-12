"""Frozen pre-Phase-4 startup bootstrap schema for an explicit fresh install.

Source: model declarations at 4d1981b2c0a67ce3a416e94c0c67d74ad1f2fcc6 (2026-09-13,
prior to migration39). At that point startup db.create_all registered the
complete model set before Flask db upgrade. The Alembic chain begins with
payment additions, not an initial users/content schema migration.

This module preserves that historical empty schema. It imports no live model
or app package, creates no rows, and never runs from application startup.
Python client defaults/ORM relationships are omitted: they do not alter DDL.
All column types, server defaults, indexes, foreign keys and checks are frozen.
"""

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from sqlalchemy.orm import declarative_base

SOURCE_COMMIT = "4d1981b2c0a67ce3a416e94c0c67d74ad1f2fcc6"
HISTORICAL_BOOTSTRAP_METADATA = sa.MetaData()
_HistoricalBase = declarative_base(metadata=HISTORICAL_BOOTSTRAP_METADATA)

# models/admin_security_alert.py
class AdminSecurityAlert(_HistoricalBase):
    __tablename__ = 'admin_security_alerts'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    severity = sa.Column(sa.String(20), nullable=False, index=True)
    threat_type = sa.Column(sa.String(60), nullable=False, index=True)
    source_ip = sa.Column(sa.String(64), nullable=True)
    source_url = sa.Column(sa.String(2048), nullable=True)
    message = sa.Column(sa.Text, nullable=False)
    details = sa.Column(sa.JSON, nullable=False)
    is_resolved = sa.Column(sa.Boolean, nullable=False, index=True)
    resolved_by_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False, index=True)
    resolved_at = sa.Column(sa.DateTime, nullable=True)
    __table_args__ = (Index('ix_admin_security_alerts_threat_resolved', 'threat_type', 'is_resolved'),)


# models/audit_log.py
class AuditLog(_HistoricalBase):
    __tablename__ = 'audit_logs'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = sa.Column(sa.String(100), nullable=False, index=True)
    payload = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)


# models/card.py
class Card(_HistoricalBase):
    __tablename__ = 'cards'
    id = sa.Column(sa.String(36), primary_key=True)
    note_id = sa.Column(sa.String(36), sa.ForeignKey('notes.id', ondelete='CASCADE'), nullable=False, index=True)
    template_id = sa.Column(sa.String(36), sa.ForeignKey('templates.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('note_id', 'template_id', name='uq_cards_note_template'),)


# models/card_progress.py
class CardProgress(_HistoricalBase):
    __tablename__ = 'card_progress'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    card_id = sa.Column(sa.String(36), sa.ForeignKey('cards.id', ondelete='CASCADE'), nullable=True, index=True)
    queue = sa.Column(sa.String(20), nullable=False, index=True)
    step_index = sa.Column(sa.Integer, nullable=False)
    due_at = sa.Column(sa.DateTime, nullable=True, index=True)
    due_day = sa.Column(sa.Integer, nullable=True, index=True)
    interval_days = sa.Column(sa.Integer, nullable=False)
    interval_days_raw = sa.Column(sa.Float, nullable=True)
    is_suspended = sa.Column(sa.Boolean, nullable=False, index=True)
    is_buried = sa.Column(sa.Boolean, nullable=False, index=True)
    buried_until_day = sa.Column(sa.Integer, nullable=True, index=True)
    review_kind = sa.Column(sa.String(20), nullable=False, index=True)
    scheduler_mode = sa.Column(sa.String(20), nullable=False, index=True)
    ease_factor = sa.Column(sa.Float, nullable=False)
    memory_stability = sa.Column(sa.Float, nullable=True)
    memory_difficulty = sa.Column(sa.Float, nullable=True)
    suspension_reason = sa.Column(sa.String(32), nullable=True)
    last_leech_at = sa.Column(sa.DateTime, nullable=True)
    last_leech_lapses = sa.Column(sa.Integer, nullable=False)
    last_review_event_id = sa.Column(sa.Integer, sa.ForeignKey('review_events.id', ondelete='SET NULL'), nullable=True, index=True)
    reps = sa.Column(sa.Integer, nullable=False)
    lapses = sa.Column(sa.Integer, nullable=False)
    last_reviewed_at = sa.Column(sa.DateTime, nullable=True)
    revision = sa.Column(sa.BigInteger, nullable=False, server_default=text('0'))
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.UniqueConstraint('user_id', 'card_id', name='uq_card_progress_user_card'), sa.Index('ix_card_progress_user_queue_due_day', 'user_id', 'queue', 'due_day'), sa.Index('ix_card_progress_user_queue_due_at', 'user_id', 'queue', 'due_at'), sa.Index('ix_card_progress_user_hidden_flags', 'user_id', 'is_suspended', 'is_buried'))


# models/column_preference.py
class VocabularyColumnPreference(_HistoricalBase):
    __tablename__ = 'vocabulary_column_preferences'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id'), nullable=False, index=True)
    column_key = sa.Column(sa.String(64), nullable=False)
    width = sa.Column(sa.String(32), nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.UniqueConstraint('user_id', 'column_key', name='uq_vocab_column_pref'),)


# models/connect_import_media.py
class ConnectImportMedia(_HistoricalBase):
    __tablename__ = 'connect_import_media'
    id = sa.Column(sa.String(36), primary_key=True)
    session_id = sa.Column(sa.String(36), sa.ForeignKey('connect_import_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    filename = sa.Column(sa.String(255), nullable=False)
    media_kind = sa.Column(sa.String(16), nullable=False)
    mime_type = sa.Column(sa.String(64), nullable=False)
    storage_path = sa.Column(sa.String(1024), nullable=False)
    sha256 = sa.Column(sa.String(64), nullable=False, index=True)
    size_bytes = sa.Column(sa.Integer, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('session_id', 'filename', name='uq_connect_import_media_session_filename'),)


# models/connect_import_package.py
class ConnectImportPackage(_HistoricalBase):
    __tablename__ = 'connect_import_packages'
    id = sa.Column(sa.String(36), primary_key=True)
    session_id = sa.Column(sa.String(36), sa.ForeignKey('connect_import_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    kind = sa.Column(sa.String(16), nullable=False)
    sequence = sa.Column(sa.Integer, nullable=False)
    sha256 = sa.Column(sa.String(64), nullable=False)
    size_bytes = sa.Column(sa.Integer, nullable=False)
    storage_path = sa.Column(sa.String(1024), nullable=False)
    status = sa.Column(sa.String(32), nullable=False, index=True)
    item_count = sa.Column(sa.Integer, nullable=False)
    result_json = sa.Column(sa.JSON, nullable=False)
    error = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('session_id', 'kind', 'sequence', name='uq_connect_import_packages_session_kind_sequence'),)


# models/connect_import_session.py
class ConnectImportSession(_HistoricalBase):
    __tablename__ = 'connect_import_sessions'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    source = sa.Column(sa.String(64), nullable=False)
    source_key = sa.Column(sa.String(255), nullable=False)
    mode = sa.Column(sa.String(32), nullable=False)
    status = sa.Column(sa.String(32), nullable=False, index=True)
    source_root_path = sa.Column(sa.String(2048), nullable=True)
    target_root_path = sa.Column(sa.String(2048), nullable=True)
    selected_decks = sa.Column(sa.JSON, nullable=False)
    note_type_bindings = sa.Column(sa.JSON, nullable=False)
    blockers = sa.Column(sa.JSON, nullable=False)
    plan_hash = sa.Column(sa.String(64), nullable=True, index=True)
    total_notes = sa.Column(sa.Integer, nullable=False)
    total_media = sa.Column(sa.Integer, nullable=False)
    processed_notes = sa.Column(sa.Integer, nullable=False)
    attempted_notes = sa.Column(sa.Integer, nullable=False, server_default=text('0'))
    processed_media = sa.Column(sa.Integer, nullable=False)
    error_summary = sa.Column(sa.JSON, nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=False, index=True)
    completed_at = sa.Column(sa.DateTime, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/connect_note_ref.py
class ConnectNoteRef(_HistoricalBase):
    __tablename__ = 'connect_note_refs'
    id = sa.Column(sa.BigInteger().with_variant(sa.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    note_id = sa.Column(sa.String(36), sa.ForeignKey('notes.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    provider = sa.Column(sa.String(32), nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'note_id', 'provider', name='uq_connect_note_refs_user_note_provider'),)


# models/connect_note_type_ref.py
class ConnectNoteTypeRef(_HistoricalBase):
    __tablename__ = 'connect_note_type_refs'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    source_key = sa.Column(sa.String(255), nullable=False)
    external_model_id = sa.Column(sa.String(128), nullable=False)
    external_model_name = sa.Column(sa.String(255), nullable=False)
    note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='CASCADE'), nullable=False, index=True)
    schema_hash = sa.Column(sa.String(64), nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'source_key', 'external_model_id', name='uq_connect_note_type_refs_source_model'),)


# models/connect_pending_media.py
class ConnectPendingMedia(_HistoricalBase):
    __tablename__ = 'connect_pending_media'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    filename = sa.Column(sa.String(255), nullable=False)
    mime_type = sa.Column(sa.String(64), nullable=False)
    storage_path = sa.Column(sa.String(1024), nullable=False)
    sha256 = sa.Column(sa.String(64), nullable=False)
    size_bytes = sa.Column(sa.Integer, nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'filename', name='uq_connect_pending_media_user_filename'),)


# models/connect_review_event_ref.py
class ConnectReviewEventRef(_HistoricalBase):
    __tablename__ = 'connect_review_event_refs'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    source_key = sa.Column(sa.String(255), nullable=False)
    external_review_id = sa.Column(sa.String(128), nullable=False)
    external_card_id = sa.Column(sa.String(128), nullable=False)
    review_event_id = sa.Column(sa.Integer, sa.ForeignKey('review_events.id', ondelete='SET NULL'), nullable=True, index=True)
    payload_hash = sa.Column(sa.String(64), nullable=False)
    status = sa.Column(sa.String(20), nullable=False, index=True)
    ignored_reason = sa.Column(sa.String(64), nullable=True)
    last_session_id = sa.Column(sa.String(36), sa.ForeignKey('connect_import_sessions.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.UniqueConstraint('user_id', 'source_key', 'external_review_id', name='uq_connect_review_event_refs_source_review'), sa.Index('ix_connect_review_event_refs_source_card', 'user_id', 'source_key', 'external_card_id'))


# models/connect_source_card_ref.py
class ConnectSourceCardRef(_HistoricalBase):
    __tablename__ = 'connect_source_card_refs'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    source_key = sa.Column(sa.String(255), nullable=False)
    external_card_id = sa.Column(sa.String(128), nullable=False)
    external_note_id = sa.Column(sa.String(128), nullable=False)
    source_ord = sa.Column(sa.Integer, nullable=False)
    card_id = sa.Column(sa.String(36), sa.ForeignKey('cards.id', ondelete='CASCADE'), nullable=False, index=True)
    snapshot_hash = sa.Column(sa.String(64), nullable=True)
    applied_local_revision = sa.Column(sa.BigInteger, nullable=True)
    review_cursor = sa.Column(sa.BigInteger, nullable=True)
    last_session_id = sa.Column(sa.String(36), sa.ForeignKey('connect_import_sessions.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.UniqueConstraint('user_id', 'source_key', 'external_card_id', name='uq_connect_source_card_refs_source_card'), sa.Index('ix_connect_source_card_refs_source_note', 'user_id', 'source_key', 'external_note_id'))


# models/connect_source_deck_ref.py
class ConnectSourceDeckRef(_HistoricalBase):
    __tablename__ = 'connect_source_deck_refs'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    source_key = sa.Column(sa.String(255), nullable=False)
    external_deck_id = sa.Column(sa.String(128), nullable=False)
    source_path = sa.Column(sa.String(2048), nullable=False)
    deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'source_key', 'external_deck_id', name='uq_connect_source_deck_refs_source_deck'),)


# models/connect_source_note_ref.py
class ConnectSourceNoteRef(_HistoricalBase):
    __tablename__ = 'connect_source_note_refs'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    source_key = sa.Column(sa.String(255), nullable=False)
    external_note_id = sa.Column(sa.String(128), nullable=False)
    source_model_id = sa.Column(sa.String(128), nullable=False)
    source_deck_path = sa.Column(sa.String(2048), nullable=False)
    note_id = sa.Column(sa.String(36), sa.ForeignKey('notes.id', ondelete='CASCADE'), nullable=False, index=True)
    content_hash = sa.Column(sa.String(64), nullable=False)
    last_session_id = sa.Column(sa.String(36), sa.ForeignKey('connect_import_sessions.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'source_key', 'external_note_id', name='uq_connect_source_note_refs_source_note'),)


# models/creator_feature_policy.py
class CreatorFeaturePolicy(_HistoricalBase):
    __tablename__ = 'creator_feature_policies'
    id = sa.Column(sa.Integer, primary_key=True)
    feature_code = sa.Column(sa.String(64), unique=True, nullable=False)
    is_monetized = sa.Column(sa.Boolean, nullable=False)
    free_quota_per_creator = sa.Column(sa.Integer, nullable=False)
    price_per_key_minor = sa.Column(sa.Integer, nullable=False)
    requires_pro_role = sa.Column(sa.Boolean, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/deck.py
class Deck(_HistoricalBase):
    __tablename__ = 'decks'
    id = sa.Column(sa.Integer, primary_key=True)
    parent_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='CASCADE'), nullable=True, index=True)
    owner_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='SET NULL'), nullable=True, index=True)
    scheduler_preset_id = sa.Column(sa.Integer, sa.ForeignKey('scheduler_presets.id', ondelete='SET NULL'), nullable=True, index=True)
    name = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    position = sa.Column(sa.Integer, nullable=False)
    deleted_at = sa.Column(sa.DateTime, nullable=True, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/deck_access_key.py
class DeckAccessKey(_HistoricalBase):
    __tablename__ = 'deck_access_keys'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_item_id = sa.Column(sa.String(36), sa.ForeignKey('deck_marketplace_items.id', ondelete='CASCADE'), nullable=False, index=True)
    creator_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    key_code = sa.Column(sa.String(64), unique=True, nullable=False, index=True)
    label = sa.Column(sa.String(150), nullable=True)
    status = sa.Column(sa.Enum('active', 'revoked', 'expired', name='deck_access_key_status_enum', native_enum=False), nullable=False, index=True)
    max_uses = sa.Column(sa.Integer, nullable=True)
    used_count = sa.Column(sa.Integer, nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=True, index=True)
    access_duration_days = sa.Column(sa.Integer, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/deck_access_key_redemption.py
class DeckAccessKeyRedemption(_HistoricalBase):
    __tablename__ = 'deck_access_key_redemptions'
    id = sa.Column(sa.String(36), primary_key=True)
    key_id = sa.Column(sa.String(36), sa.ForeignKey('deck_access_keys.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    deck_install_id = sa.Column(sa.String(36), sa.ForeignKey('deck_installs.id', ondelete='CASCADE'), nullable=False, index=True)
    redeemed_at = sa.Column(sa.DateTime, nullable=False)
    access_expires_at = sa.Column(sa.DateTime, nullable=True, index=True)
    status = sa.Column(sa.Enum('active', 'revoked', 'expired', name='deck_key_redemption_status_enum', native_enum=False), nullable=False, index=True)
    __table_args__ = (sa.UniqueConstraint('key_id', 'user_id', name='uq_deck_key_user_redemption'),)


# models/deck_change_request.py
class DeckChangeRequest(_HistoricalBase):
    __tablename__ = 'deck_change_requests'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_install_id = sa.Column(sa.String(36), sa.ForeignKey('deck_installs.id', ondelete='SET NULL'), nullable=True, index=True)
    deck_item_id = sa.Column(sa.String(36), sa.ForeignKey('deck_marketplace_items.id', ondelete='SET NULL'), nullable=True, index=True)
    local_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='SET NULL'), nullable=True, index=True)
    source_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='SET NULL'), nullable=True, index=True)
    source_note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='SET NULL'), nullable=True, index=True)
    requester_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    owner_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    reviewed_by_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    title = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    status = sa.Column(sa.String(32), nullable=False, index=True)
    install_snapshot_at = sa.Column(sa.DateTime, nullable=True)
    base_release_id = sa.Column(sa.String(36), sa.ForeignKey('deck_releases.id', name='fk_deck_change_requests_base_release', ondelete='SET NULL'), nullable=True, index=True)
    revision = sa.Column(sa.BigInteger, nullable=False)
    overlay_fingerprint = sa.Column(sa.String(64), nullable=False)
    last_synced_overlay_fingerprint = sa.Column(sa.String(64), nullable=True)
    last_sync_status = sa.Column(sa.String(32), nullable=True, index=True)
    last_synced_at = sa.Column(sa.DateTime, nullable=True)
    submitted_at = sa.Column(sa.DateTime, nullable=True)
    reviewed_at = sa.Column(sa.DateTime, nullable=True)
    merged_at = sa.Column(sa.DateTime, nullable=True)
    review_comment = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (Index('ix_deck_change_requests_owner_status_updated_at', 'owner_user_id', 'status', 'updated_at'), Index('ix_deck_change_requests_requester_status_updated_at', 'requester_user_id', 'status', 'updated_at'))


# models/deck_change_request_conflict.py
class DeckChangeRequestConflict(_HistoricalBase):
    __tablename__ = 'deck_change_request_conflicts'
    id = sa.Column(sa.String(36), primary_key=True)
    change_request_id = sa.Column(sa.String(36), sa.ForeignKey('deck_change_requests.id', ondelete='CASCADE'), nullable=False, index=True)
    item_id = sa.Column(sa.String(36), sa.ForeignKey('deck_change_request_items.id', ondelete='CASCADE'), nullable=False, index=True)
    conflict_type = sa.Column(sa.String(64), nullable=False, index=True)
    source_ref_id = sa.Column(sa.String(64), nullable=True, index=True)
    upstream_value = sa.Column(sa.JSON, nullable=True)
    local_value = sa.Column(sa.JSON, nullable=True)
    base_value = sa.Column(sa.JSON, nullable=True)
    resolution_mode = sa.Column(sa.String(32), nullable=True, index=True)
    resolved_value = sa.Column(sa.JSON, nullable=True)
    resolved_by_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    resolved_at = sa.Column(sa.DateTime, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('item_id', name='uq_deck_change_request_conflicts_item'), Index('ix_deck_change_request_conflicts_request_resolved_at', 'change_request_id', 'resolved_at'), Index('ix_deck_change_request_conflicts_request_type', 'change_request_id', 'conflict_type'))


# models/deck_change_request_item.py
class DeckChangeRequestItem(_HistoricalBase):
    __tablename__ = 'deck_change_request_items'
    id = sa.Column(sa.String(36), primary_key=True)
    change_request_id = sa.Column(sa.String(36), sa.ForeignKey('deck_change_requests.id', ondelete='CASCADE'), nullable=False, index=True)
    change_type = sa.Column(sa.String(64), nullable=False, index=True)
    source_ref_id = sa.Column(sa.String(64), nullable=True, index=True)
    local_ref_id = sa.Column(sa.String(64), nullable=True, index=True)
    path_key = sa.Column(sa.String(255), nullable=True)
    path_label = sa.Column(sa.String(255), nullable=True)
    before_value = sa.Column(sa.JSON, nullable=True)
    after_value = sa.Column(sa.JSON, nullable=True)
    metadata_json = sa.Column(sa.JSON, nullable=False)
    sort_order = sa.Column(sa.Integer, nullable=False)
    is_conflict = sa.Column(sa.Boolean, nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (Index('ix_deck_change_request_items_request_sort', 'change_request_id', 'sort_order'), Index('ix_deck_change_request_items_request_type', 'change_request_id', 'change_type'))


# models/deck_clone_added_field_def.py
class DeckCloneAddedFieldDef(_HistoricalBase):
    __tablename__ = 'deck_clone_added_field_defs'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_install_id = sa.Column(sa.String(36), sa.ForeignKey('deck_installs.id', ondelete='CASCADE'), nullable=False, index=True)
    name = sa.Column(sa.String(255), nullable=False)
    field_type = sa.Column(sa.Enum('text', 'richtext', 'markdown', 'image', 'audio', 'diagram', name='deck_clone_field_type_enum', native_enum=False), nullable=False)
    position = sa.Column(sa.Integer, nullable=False)
    required = sa.Column(sa.Boolean, nullable=False)
    properties = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/deck_clone_added_note.py
class DeckCloneAddedNote(_HistoricalBase):
    __tablename__ = 'deck_clone_added_notes'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_install_id = sa.Column(sa.String(36), sa.ForeignKey('deck_installs.id', ondelete='CASCADE'), nullable=False, index=True)
    note_id = sa.Column(sa.String(36), sa.ForeignKey('notes.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/deck_clone_deck_map.py
class DeckCloneDeckMap(_HistoricalBase):
    __tablename__ = 'deck_clone_deck_maps'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_install_id = sa.Column(sa.String(36), sa.ForeignKey('deck_installs.id', ondelete='CASCADE'), nullable=False, index=True)
    local_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='CASCADE'), nullable=False, index=True)
    source_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('local_deck_id', name='uq_clone_map_local_deck'), UniqueConstraint('deck_install_id', 'source_deck_id', name='uq_clone_map_install_source'))


# models/deck_clone_field_def_override.py
class DeckCloneFieldDefOverride(_HistoricalBase):
    __tablename__ = 'deck_clone_field_def_overrides'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_install_id = sa.Column(sa.String(36), sa.ForeignKey('deck_installs.id', ondelete='CASCADE'), nullable=False, index=True)
    source_field_def_id = sa.Column(sa.String(36), sa.ForeignKey('field_defs.id', ondelete='CASCADE'), nullable=False, index=True)
    is_disabled = sa.Column(sa.Boolean, nullable=False)
    properties = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('deck_install_id', 'source_field_def_id', name='uq_clone_field_override_install_source_field'),)


# models/deck_clone_field_order_override.py
class DeckCloneFieldOrderOverride(_HistoricalBase):
    __tablename__ = 'deck_clone_field_order_overrides'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_install_id = sa.Column(sa.String(36), sa.ForeignKey('deck_installs.id', ondelete='CASCADE'), nullable=False, index=True)
    ordered_def_ids = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('deck_install_id', name='uq_clone_field_order_install'),)


# models/deck_clone_note_field_override.py
class DeckCloneNoteFieldOverride(_HistoricalBase):
    __tablename__ = 'deck_clone_note_field_overrides'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_install_id = sa.Column(sa.String(36), sa.ForeignKey('deck_installs.id', ondelete='CASCADE'), nullable=False, index=True)
    source_note_id = sa.Column(sa.String(36), sa.ForeignKey('notes.id', ondelete='CASCADE'), nullable=False, index=True)
    source_field_def_id = sa.Column(sa.String(36), sa.ForeignKey('field_defs.id', name='fk_clone_note_overrides_source_field_def', ondelete='SET NULL'), nullable=True, index=True)
    base_release_id = sa.Column(sa.String(36), sa.ForeignKey('deck_releases.id', name='fk_clone_note_overrides_base_release', ondelete='SET NULL'), nullable=True, index=True)
    field_name = sa.Column(sa.String(255), nullable=False)
    operation = sa.Column(sa.Enum('set', 'remove', name='deck_clone_note_field_op_enum', native_enum=False), nullable=False)
    value = sa.Column(sa.JSON, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('deck_install_id', 'source_note_id', 'field_name', name='uq_clone_note_override_install_note_field'), UniqueConstraint('deck_install_id', 'source_note_id', 'source_field_def_id', name='uq_clone_note_override_install_note_field_def'))


# models/deck_install.py
class DeckInstall(_HistoricalBase):
    __tablename__ = 'deck_installs'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_item_id = sa.Column(sa.String(36), sa.ForeignKey('deck_marketplace_items.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    local_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='SET NULL'), nullable=True, index=True)
    clone_mode = sa.Column(sa.String(32), nullable=False, index=True)
    source_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='SET NULL'), nullable=True, index=True)
    source_note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='SET NULL'), nullable=True, index=True)
    source_owner_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    base_snapshot_at = sa.Column(sa.DateTime, nullable=True, index=True)
    applied_release_id = sa.Column(sa.String(36), sa.ForeignKey('deck_releases.id', name='fk_deck_installs_applied_release', ondelete='SET NULL'), nullable=True, index=True)
    seen_release_id = sa.Column(sa.String(36), sa.ForeignKey('deck_releases.id', name='fk_deck_installs_seen_release', ondelete='SET NULL'), nullable=True, index=True)
    overlay_revision = sa.Column(sa.BigInteger, nullable=False, server_default=text('0'))
    version_mode = sa.Column(sa.String(32), nullable=False, server_default='legacy_snapshot', index=True)
    last_synced_at = sa.Column(sa.DateTime, nullable=True, index=True)
    last_sync_status = sa.Column(sa.String(32), nullable=True, index=True)
    auto_update_enabled = sa.Column(sa.Boolean, nullable=False, server_default=text('0'), index=True)
    sync_mode = sa.Column(sa.String(32), nullable=False, server_default='manual', index=True)
    last_auto_updated_at = sa.Column(sa.DateTime, nullable=True, index=True)
    pending_conflict_count = sa.Column(sa.Integer, nullable=False, server_default=text('0'))
    purchase_amount_minor = sa.Column(sa.Integer, nullable=False)
    installed_at = sa.Column(sa.DateTime, nullable=False)
    purchased_at = sa.Column(sa.DateTime, nullable=True)
    first_use_at = sa.Column(sa.DateTime, nullable=True)
    last_activity_at = sa.Column(sa.DateTime, nullable=True)
    market_active = sa.Column(sa.Boolean, nullable=True)
    market_active_evaluated_at = sa.Column(sa.DateTime, nullable=True)
    market_active_policy_version = sa.Column(sa.SmallInteger, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('deck_item_id', 'user_id', name='uq_deck_installs_item_user'), sa.Index('ix_deck_installs_item_market_active', 'deck_item_id', 'market_active'))


# models/deck_install_rebase.py
class DeckInstallRebase(_HistoricalBase):
    __tablename__ = 'deck_install_rebases'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_install_id = sa.Column(sa.String(36), sa.ForeignKey('deck_installs.id', name='fk_deck_install_rebases_install', ondelete='CASCADE'), nullable=False, index=True)
    from_release_id = sa.Column(sa.String(36), sa.ForeignKey('deck_releases.id', name='fk_deck_install_rebases_from_release', ondelete='SET NULL'), nullable=True, index=True)
    to_release_id = sa.Column(sa.String(36), sa.ForeignKey('deck_releases.id', name='fk_deck_install_rebases_to_release', ondelete='SET NULL'), nullable=True, index=True)
    status = sa.Column(sa.String(32), nullable=False, index=True)
    mode = sa.Column(sa.String(32), nullable=False, index=True)
    expected_overlay_revision = sa.Column(sa.BigInteger, nullable=False)
    idempotency_key = sa.Column(sa.String(64), nullable=True)
    change_count = sa.Column(sa.Integer, nullable=False)
    conflict_count = sa.Column(sa.Integer, nullable=False)
    resolved_conflict_count = sa.Column(sa.Integer, nullable=False)
    applied_change_count = sa.Column(sa.Integer, nullable=False)
    error_message = sa.Column(sa.Text, nullable=True)
    prepared_at = sa.Column(sa.DateTime, nullable=True)
    applied_at = sa.Column(sa.DateTime, nullable=True)
    cancelled_at = sa.Column(sa.DateTime, nullable=True)
    failed_at = sa.Column(sa.DateTime, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('deck_install_id', 'idempotency_key', name='uq_deck_install_rebases_install_idempotency'), Index('ix_deck_install_rebases_install_status_updated', 'deck_install_id', 'status', 'updated_at', 'id'), Index('ix_deck_install_rebases_install_target_status', 'deck_install_id', 'to_release_id', 'status', 'id'))


# models/deck_install_rebase_conflict.py
class DeckInstallRebaseConflict(_HistoricalBase):
    __tablename__ = 'deck_install_rebase_conflicts'
    id = sa.Column(sa.BigInteger().with_variant(sa.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    rebase_id = sa.Column(sa.String(36), sa.ForeignKey('deck_install_rebases.id', name='fk_deck_install_rebase_conflicts_rebase', ondelete='CASCADE'), nullable=False, index=True)
    release_change_id = sa.Column(sa.BigInteger().with_variant(sa.Integer, 'sqlite'), sa.ForeignKey('deck_release_changes.id', name='fk_deck_install_rebase_conflicts_release_change', ondelete='SET NULL'), nullable=True, index=True)
    conflict_key = sa.Column(sa.String(191), nullable=False)
    entity_kind = sa.Column(sa.String(32), nullable=False)
    entity_id = sa.Column(sa.String(64), nullable=False)
    field_def_id = sa.Column(sa.String(36), nullable=True)
    property_key = sa.Column(sa.String(191), nullable=False)
    base_value = sa.Column(sa.JSON, nullable=True)
    upstream_value = sa.Column(sa.JSON, nullable=True)
    local_value = sa.Column(sa.JSON, nullable=True)
    resolution_mode = sa.Column(sa.String(32), nullable=True)
    resolved_value = sa.Column(sa.JSON, nullable=True)
    resolved_by_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', name='fk_deck_install_rebase_conflicts_resolved_by', ondelete='SET NULL'), nullable=True, index=True)
    resolved_at = sa.Column(sa.DateTime, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('rebase_id', 'conflict_key', name='uq_deck_install_rebase_conflicts_rebase_key'), Index('ix_deck_install_rebase_conflicts_resolution', 'rebase_id', 'resolution_mode', 'id'), Index('ix_deck_install_rebase_conflicts_entity', 'rebase_id', 'entity_kind', 'entity_id', 'property_key', 'id'))


# models/deck_marketplace_item.py
class DeckMarketplaceItem(_HistoricalBase):
    __tablename__ = 'deck_marketplace_items'
    __table_args__ = (sa.Index('uq_deck_marketplace_items_source_deck', 'source_deck_id', unique=True),)
    id = sa.Column(sa.String(36), primary_key=True)
    owner_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    source_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='SET NULL'), nullable=True, index=True)
    source_note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='SET NULL'), nullable=True, index=True)
    title = sa.Column(sa.String(255), nullable=False, index=True)
    description = sa.Column(sa.Text, nullable=False)
    primary_category = sa.Column(sa.String(120), nullable=False, index=True)
    tags = sa.Column(sa.JSON, nullable=False)
    taxonomy_metadata = sa.Column(sa.JSON, nullable=False)
    preview_text = sa.Column(sa.Text, nullable=True)
    sample_cards_count = sa.Column(sa.Integer, nullable=False)
    pricing_mode = sa.Column(sa.Enum('free', 'paid', name='deck_marketplace_pricing_mode_enum', native_enum=False), nullable=False, index=True)
    price_amount_minor = sa.Column(sa.Integer, nullable=False)
    distribution_mode = sa.Column(sa.String(32), nullable=False, server_default='free', index=True)
    course_title = sa.Column(sa.String(255), nullable=True)
    course_description = sa.Column(sa.Text, nullable=True)
    course_url = sa.Column(sa.String(500), nullable=True)
    course_instructions = sa.Column(sa.Text, nullable=True)
    student_offer_mode = sa.Column(sa.Enum('none', 'free', 'percent_discount', name='deck_marketplace_student_offer_mode_enum', native_enum=False, length=32), nullable=False, server_default='none', index=True)
    student_discount_percent = sa.Column(sa.Integer, nullable=True)
    version = sa.Column(sa.String(50), nullable=False)
    changelog = sa.Column(sa.Text, nullable=True)
    current_release_id = sa.Column(sa.String(36), sa.ForeignKey('deck_releases.id', name='fk_deck_marketplace_items_current_release', ondelete='SET NULL', use_alter=True), nullable=True, index=True)
    preview_samples_release_id = sa.Column(sa.String(36), sa.ForeignKey('deck_releases.id', name='fk_deck_marketplace_items_preview_samples_release', ondelete='SET NULL', use_alter=True), nullable=True, index=True)
    preview_samples_schema_version = sa.Column(sa.SmallInteger, nullable=True)
    preview_samples_json = sa.Column(sa.JSON, nullable=True)
    working_revision = sa.Column(sa.BigInteger, nullable=False, server_default=text('0'))
    dirty_tracking_revision = sa.Column(sa.BigInteger, nullable=False, server_default=text('0'))
    publish_status = sa.Column(sa.Enum('private', 'published', 'unlisted', 'archived', name='deck_marketplace_publish_status_enum', native_enum=False), nullable=False, index=True)
    is_official = sa.Column(sa.Boolean, nullable=False, index=True)
    published_at = sa.Column(sa.DateTime, nullable=True)
    archived_at = sa.Column(sa.DateTime, nullable=True)
    install_count = sa.Column(sa.Integer, nullable=False)
    active_usage_count = sa.Column(sa.Integer, nullable=False)
    rating_avg = sa.Column(sa.Float, nullable=False)
    rating_count = sa.Column(sa.Integer, nullable=False)
    auto_publish_enabled = sa.Column(sa.Boolean, nullable=False, server_default=text('0'), index=True)
    last_auto_published_at = sa.Column(sa.DateTime, nullable=True)
    last_auto_publish_error = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/deck_release.py
class DeckRelease(_HistoricalBase):
    __tablename__ = 'deck_releases'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_item_id = sa.Column(sa.String(36), sa.ForeignKey('deck_marketplace_items.id', name='fk_deck_releases_deck_item', ondelete='CASCADE'), nullable=False, index=True)
    sequence_no = sa.Column(sa.BigInteger, nullable=False)
    version_label = sa.Column(sa.String(50), nullable=False)
    parent_release_id = sa.Column(sa.String(36), sa.ForeignKey('deck_releases.id', name='fk_deck_releases_parent', ondelete='SET NULL'), nullable=True, index=True)
    status = sa.Column(sa.String(32), nullable=False, index=True)
    publish_mode = sa.Column(sa.String(32), nullable=False, index=True)
    source_working_revision = sa.Column(sa.BigInteger, nullable=False)
    manifest_hash = sa.Column(sa.String(64), nullable=True)
    change_count = sa.Column(sa.Integer, nullable=False)
    entity_count = sa.Column(sa.Integer, nullable=False)
    added_count = sa.Column(sa.Integer, nullable=False)
    modified_count = sa.Column(sa.Integer, nullable=False)
    removed_count = sa.Column(sa.Integer, nullable=False)
    changelog = sa.Column(sa.Text, nullable=True)
    idempotency_key = sa.Column(sa.String(64), nullable=True)
    created_by_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', name='fk_deck_releases_created_by', ondelete='SET NULL'), nullable=True, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    published_at = sa.Column(sa.DateTime, nullable=True)
    failed_at = sa.Column(sa.DateTime, nullable=True)
    failure_message = sa.Column(sa.Text, nullable=True)
    __table_args__ = (UniqueConstraint('deck_item_id', 'sequence_no', name='uq_deck_releases_item_sequence'), UniqueConstraint('deck_item_id', 'version_label', name='uq_deck_releases_item_version'), UniqueConstraint('deck_item_id', 'idempotency_key', name='uq_deck_releases_item_idempotency'), Index('ix_deck_releases_item_status_published', 'deck_item_id', 'status', 'published_at', 'id'))


# models/deck_release_change.py
class DeckReleaseChange(_HistoricalBase):
    __tablename__ = 'deck_release_changes'
    id = sa.Column(sa.BigInteger().with_variant(sa.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    release_id = sa.Column(sa.String(36), sa.ForeignKey('deck_releases.id', name='fk_deck_release_changes_release', ondelete='CASCADE'), nullable=False, index=True)
    release_sequence_no = sa.Column(sa.BigInteger, nullable=False)
    change_key = sa.Column(sa.String(191), nullable=False)
    entity_kind = sa.Column(sa.String(32), nullable=False)
    entity_id = sa.Column(sa.String(64), nullable=False)
    field_def_id = sa.Column(sa.String(36), nullable=True)
    property_key = sa.Column(sa.String(191), nullable=False)
    operation = sa.Column(sa.String(32), nullable=False)
    before_value = sa.Column(sa.JSON, nullable=True)
    after_value = sa.Column(sa.JSON, nullable=True)
    before_hash = sa.Column(sa.String(64), nullable=True)
    after_hash = sa.Column(sa.String(64), nullable=True)
    source_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', name='fk_deck_release_changes_source_deck', ondelete='SET NULL'), nullable=True)
    sort_key = sa.Column(sa.String(255), nullable=False)
    source_change_request_item_id = sa.Column(sa.String(36), sa.ForeignKey('deck_change_request_items.id', name='fk_deck_release_changes_request_item', ondelete='SET NULL'), nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('release_id', 'change_key', name='uq_deck_release_changes_release_key'), Index('ix_deck_release_changes_diff_cursor', 'release_id', 'entity_kind', 'source_deck_id', 'sort_key', 'id'), Index('ix_deck_release_changes_entity_history', 'entity_kind', 'entity_id', 'property_key', 'release_sequence_no', 'id'))


# models/deck_release_entity_membership.py
class DeckReleaseEntityMembership(_HistoricalBase):
    __tablename__ = 'deck_release_entity_memberships'
    id = sa.Column(sa.BigInteger().with_variant(sa.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    deck_item_id = sa.Column(sa.String(36), sa.ForeignKey('deck_marketplace_items.id', name='fk_deck_release_memberships_deck_item', ondelete='CASCADE'), nullable=False, index=True)
    entity_kind = sa.Column(sa.String(32), nullable=False)
    entity_id = sa.Column(sa.String(64), nullable=False)
    source_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', name='fk_deck_release_memberships_source_deck', ondelete='SET NULL'), nullable=True)
    introduced_sequence = sa.Column(sa.BigInteger, nullable=False)
    removed_sequence = sa.Column(sa.BigInteger, nullable=True)
    metadata_json = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('deck_item_id', 'entity_kind', 'entity_id', 'introduced_sequence', name='uq_deck_release_memberships_item_entity_start'), Index('ix_deck_release_memberships_visibility', 'deck_item_id', 'entity_kind', 'introduced_sequence', 'removed_sequence', 'id'), Index('ix_deck_release_memberships_deck_visibility', 'deck_item_id', 'source_deck_id', 'introduced_sequence', 'removed_sequence', 'id'))


# models/deck_release_note_checkpoint.py
class DeckReleaseNoteCheckpoint(_HistoricalBase):
    __tablename__ = 'deck_release_note_checkpoints'
    id = sa.Column(sa.BigInteger().with_variant(sa.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    release_id = sa.Column(sa.String(36), sa.ForeignKey('deck_releases.id', name='fk_deck_release_note_checkpoints_release', ondelete='CASCADE'), nullable=False, index=True)
    release_sequence_no = sa.Column(sa.BigInteger, nullable=False)
    source_note_id = sa.Column(sa.String(36), nullable=False)
    source_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', name='fk_deck_release_note_checkpoints_source_deck', ondelete='SET NULL'), nullable=True)
    note_type_id = sa.Column(sa.String(36), nullable=False)
    field_values = sa.Column(sa.JSON, nullable=False)
    tags = sa.Column(sa.JSON, nullable=False)
    content_hash = sa.Column(sa.String(64), nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('release_id', 'source_note_id', name='uq_deck_release_note_checkpoints_release_note'), Index('ix_deck_release_note_checkpoints_note_sequence', 'source_note_id', 'release_sequence_no', 'id'), Index('ix_deck_release_note_checkpoints_release_deck', 'release_id', 'source_deck_id', 'id'))


# models/deck_review.py
class DeckReview(_HistoricalBase):
    __tablename__ = 'deck_reviews'
    id = sa.Column(sa.String(36), primary_key=True)
    deck_item_id = sa.Column(sa.String(36), sa.ForeignKey('deck_marketplace_items.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    rating = sa.Column(sa.Integer, nullable=False)
    comment = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('deck_item_id', 'user_id', name='uq_deck_reviews_item_user'),)


# models/deck_working_dirty_entity.py
class DeckWorkingDirtyEntity(_HistoricalBase):
    __tablename__ = 'deck_working_dirty_entities'
    id = sa.Column(sa.BigInteger().with_variant(sa.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    deck_item_id = sa.Column(sa.String(36), sa.ForeignKey('deck_marketplace_items.id', name='fk_deck_working_dirty_deck_item', ondelete='CASCADE'), nullable=False, index=True)
    entity_kind = sa.Column(sa.String(32), nullable=False)
    entity_id = sa.Column(sa.String(64), nullable=False)
    field_def_id = sa.Column(sa.String(36), nullable=True)
    property_key = sa.Column(sa.String(191), nullable=False)
    operation = sa.Column(sa.String(32), nullable=False)
    base_hash = sa.Column(sa.String(64), nullable=True)
    current_hash = sa.Column(sa.String(64), nullable=True)
    source_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', name='fk_deck_working_dirty_source_deck', ondelete='SET NULL'), nullable=True)
    working_revision = sa.Column(sa.BigInteger, nullable=False)
    metadata_json = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('deck_item_id', 'entity_kind', 'entity_id', 'property_key', name='uq_deck_working_dirty_item_entity_property'), Index('ix_deck_working_dirty_publish', 'deck_item_id', 'working_revision', 'id'), Index('ix_deck_working_dirty_entity_scope', 'deck_item_id', 'entity_kind', 'source_deck_id', 'id'))


# models/email_verification_token.py
class EmailVerificationToken(_HistoricalBase):
    __tablename__ = 'email_verification_tokens'
    __table_args__ = (sa.Index('ix_email_verification_tokens_user_active', 'user_id', 'used_at', 'revoked_at'), sa.Index('ix_email_verification_tokens_expires_at', 'expires_at'), sa.Index('ix_email_verification_tokens_email', 'email'))
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    email = sa.Column(sa.String(255), nullable=False)
    token_hash = sa.Column(sa.String(64), nullable=False, unique=True, index=True)
    token_type = sa.Column(sa.String(16), nullable=False)
    attempts_count = sa.Column(sa.Integer, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=False)
    used_at = sa.Column(sa.DateTime, nullable=True)
    revoked_at = sa.Column(sa.DateTime, nullable=True)


# models/field_def.py
class FieldDef(_HistoricalBase):
    __tablename__ = 'field_defs'
    id = sa.Column(sa.String(36), primary_key=True)
    note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='CASCADE'), nullable=False, index=True)
    name = sa.Column(sa.String(255), nullable=False)
    field_type = sa.Column(sa.Enum('text', 'richtext', 'markdown', 'image', 'audio', 'diagram', name='field_type_enum', native_enum=False), nullable=False)
    position = sa.Column(sa.Integer, nullable=False)
    required = sa.Column(sa.Boolean, nullable=False)
    identity_role = sa.Column(sa.String(32), nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('note_type_id', 'name', name='uq_field_defs_note_type_name'), UniqueConstraint('note_type_id', 'identity_role', name='uq_field_defs_note_type_identity_role'))


# models/field_rename_job.py
class FieldRenameJob(_HistoricalBase):
    __tablename__ = 'field_rename_jobs'
    id = sa.Column(sa.String(36), primary_key=True)
    note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    field_def_id = sa.Column(sa.String(36), sa.ForeignKey('field_defs.id', ondelete='CASCADE'), nullable=False, index=True)
    old_name = sa.Column(sa.String(255), nullable=False)
    new_name = sa.Column(sa.String(255), nullable=False)
    status = sa.Column(sa.String(50), nullable=False)
    total_notes = sa.Column(sa.Integer, nullable=False)
    processed_notes = sa.Column(sa.Integer, nullable=False)
    error_message = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/image_asset.py
class ImageAsset(_HistoricalBase):
    __tablename__ = 'image_assets'
    id = sa.Column(sa.String(36), primary_key=True)
    owner_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    source_type = sa.Column(sa.String(32), nullable=False, index=True)
    source_url = sa.Column(sa.String(2048), nullable=True)
    display_url = sa.Column(sa.String(2048), nullable=False)
    managed_url = sa.Column(sa.String(2048), nullable=True)
    storage_path = sa.Column(sa.String(1024), nullable=True)
    original_filename = sa.Column(sa.String(255), nullable=True)
    original_mime_type = sa.Column(sa.String(120), nullable=True)
    output_mime_type = sa.Column(sa.String(120), nullable=True)
    original_width = sa.Column(sa.Integer, nullable=True)
    original_height = sa.Column(sa.Integer, nullable=True)
    output_width = sa.Column(sa.Integer, nullable=True)
    output_height = sa.Column(sa.Integer, nullable=True)
    original_size_bytes = sa.Column(sa.Integer, nullable=False)
    output_size_bytes = sa.Column(sa.Integer, nullable=False)
    usage_type = sa.Column(sa.String(50), nullable=False, index=True)
    preset = sa.Column(sa.String(50), nullable=True)
    processing_status = sa.Column(sa.String(32), nullable=False, index=True)
    security_status = sa.Column(sa.String(32), nullable=False, index=True)
    security_reason = sa.Column(sa.String(255), nullable=True)
    sha256 = sa.Column(sa.String(64), nullable=True, index=True)
    retry_count = sa.Column(sa.Integer, nullable=False)
    last_error = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False, index=True)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    processed_at = sa.Column(sa.DateTime, nullable=True)
    __table_args__ = (Index('ix_image_assets_owner_status', 'owner_user_id', 'processing_status'), Index('ix_image_assets_usage_status', 'usage_type', 'processing_status'))


# models/marketplace_saved_item.py
class MarketplaceSavedItem(_HistoricalBase):
    __tablename__ = 'marketplace_saved_items'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    product_type = sa.Column(sa.String(64), nullable=False, index=True)
    product_ref_id = sa.Column(sa.String(36), nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'product_type', 'product_ref_id', name='uq_marketplace_saved_items_user_product'),)


# models/mcp_access_token.py
class McpAccessToken(_HistoricalBase):
    __tablename__ = 'mcp_access_tokens'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    client_id = sa.Column(sa.Integer, sa.ForeignKey('oauth_clients.id', ondelete='SET NULL'), nullable=True, index=True)
    name = sa.Column(sa.String(120), nullable=True)
    token_hash = sa.Column(sa.String(64), nullable=False, unique=True, index=True)
    refresh_token_hash = sa.Column(sa.String(64), nullable=True, unique=True, index=True)
    scopes = sa.Column(sa.Text, nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=True, index=True)
    refresh_token_expires_at = sa.Column(sa.DateTime, nullable=True, index=True)
    max_requests = sa.Column(sa.Integer, nullable=False)
    used_requests = sa.Column(sa.Integer, nullable=False)
    revoked = sa.Column(sa.Boolean, nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    last_used_at = sa.Column(sa.DateTime, nullable=True)
    __table_args__ = (sa.Index('ix_mcp_access_tokens_user_revoked_created_at', 'user_id', 'revoked', 'created_at'),)


# models/media_asset.py
class MediaAsset(_HistoricalBase):
    __tablename__ = 'media_assets'
    id = sa.Column(sa.String(36), primary_key=True)
    note_id = sa.Column(sa.String(36), sa.ForeignKey('notes.id', ondelete='CASCADE'), nullable=False, index=True)
    field_name = sa.Column(sa.String(255), nullable=False)
    filename = sa.Column(sa.String(255), nullable=False)
    mime_type = sa.Column(sa.String(255), nullable=False)
    storage_path = sa.Column(sa.String(1024), nullable=False)
    sha256 = sa.Column(sa.String(64), nullable=False)
    size_bytes = sa.Column(sa.Integer, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('note_id', 'sha256', 'field_name', name='uq_media_assets_note_sha_field'),)


# models/media_field_migration.py
class MediaFieldMigrationRun(_HistoricalBase):
    __tablename__ = 'media_field_migration_runs'
    id = sa.Column(sa.String(36), primary_key=True)
    mode = sa.Column(sa.String(32), nullable=False)
    status = sa.Column(sa.String(32), nullable=False, index=True)
    scope_user_id = sa.Column(sa.Integer, nullable=True, index=True)
    scope_deck_id = sa.Column(sa.Integer, nullable=True, index=True)
    stats = sa.Column(sa.JSON, nullable=False)
    started_at = sa.Column(sa.DateTime, nullable=False)
    finished_at = sa.Column(sa.DateTime, nullable=True)


# models/media_field_migration.py
class MediaFieldMigrationItem(_HistoricalBase):
    __tablename__ = 'media_field_migration_items'
    id = sa.Column(sa.String(36), primary_key=True)
    run_id = sa.Column(sa.String(36), sa.ForeignKey('media_field_migration_runs.id', ondelete='CASCADE'), nullable=False, index=True)
    entity_type = sa.Column(sa.String(32), nullable=False, index=True)
    entity_id = sa.Column(sa.String(36), nullable=False, index=True)
    field_name = sa.Column(sa.String(255), nullable=False)
    field_type = sa.Column(sa.String(32), nullable=True)
    action = sa.Column(sa.String(32), nullable=False, index=True)
    reason = sa.Column(sa.String(64), nullable=False, index=True)
    old_value = sa.Column(sa.Text, nullable=True)
    new_value = sa.Column(sa.Text, nullable=True)
    semantic_change = sa.Column(sa.Boolean, nullable=False)
    user_id = sa.Column(sa.Integer, nullable=True, index=True)
    deck_id = sa.Column(sa.Integer, nullable=True, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)


# models/note.py
class Note(_HistoricalBase):
    __tablename__ = 'notes'
    id = sa.Column(sa.String(36), primary_key=True)
    note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='SET NULL'), nullable=True, index=True)
    field_values = sa.Column(sa.JSON, nullable=False)
    tags = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/note_type.py
class NoteType(_HistoricalBase):
    __tablename__ = 'note_types'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    primary_category = sa.Column(sa.String(120), nullable=True, index=True)
    tags = sa.Column(sa.JSON, nullable=False)
    taxonomy_metadata = sa.Column(sa.JSON, nullable=False)
    preview_text = sa.Column(sa.Text, nullable=True)
    preview_image_url = sa.Column(sa.String(512), nullable=True)
    pricing_mode = sa.Column(sa.Enum('free', 'paid', name='note_type_pricing_mode_enum', native_enum=False), nullable=False, index=True)
    price_amount_minor = sa.Column(sa.Integer, nullable=False)
    version = sa.Column(sa.String(50), nullable=False)
    changelog = sa.Column(sa.Text, nullable=True)
    publish_status = sa.Column(sa.Enum('private', 'published', 'unlisted', 'archived', name='note_type_publish_status_enum', native_enum=False), nullable=False, index=True)
    is_official = sa.Column(sa.Boolean, nullable=False, index=True)
    published_at = sa.Column(sa.DateTime, nullable=True)
    archived_at = sa.Column(sa.DateTime, nullable=True)
    install_count = sa.Column(sa.Integer, nullable=False)
    active_usage_count = sa.Column(sa.Integer, nullable=False)
    rating_avg = sa.Column(sa.Float, nullable=False)
    rating_count = sa.Column(sa.Integer, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'name', name='uq_note_types_user_name'),)


# models/note_type_install.py
class NoteTypeInstall(_HistoricalBase):
    __tablename__ = 'note_type_installs'
    id = sa.Column(sa.String(36), primary_key=True)
    source_note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='CASCADE'), nullable=False, index=True)
    installed_note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='SET NULL'), nullable=True, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    purchase_amount_minor = sa.Column(sa.Integer, nullable=False)
    installed_at = sa.Column(sa.DateTime, nullable=False)
    purchased_at = sa.Column(sa.DateTime, nullable=True)
    first_use_at = sa.Column(sa.DateTime, nullable=True)
    last_activity_at = sa.Column(sa.DateTime, nullable=True)
    market_active = sa.Column(sa.Boolean, nullable=True)
    market_active_evaluated_at = sa.Column(sa.DateTime, nullable=True)
    market_active_policy_version = sa.Column(sa.SmallInteger, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('source_note_type_id', 'user_id', name='uq_note_type_installs_source_user'), sa.Index('ix_note_type_installs_source_market_active', 'source_note_type_id', 'market_active'), sa.Index('ix_note_type_installs_user_installed', 'user_id', 'installed_note_type_id'))


# models/note_type_review.py
class NoteTypeReview(_HistoricalBase):
    __tablename__ = 'note_type_reviews'
    id = sa.Column(sa.String(36), primary_key=True)
    note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    rating = sa.Column(sa.Integer, nullable=False)
    comment = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('note_type_id', 'user_id', name='uq_note_type_reviews_item_user'),)


# models/oauth_authorization_code.py
class OAuthAuthorizationCode(_HistoricalBase):
    __tablename__ = 'oauth_authorization_codes'
    id = sa.Column(sa.Integer, primary_key=True)
    code_hash = sa.Column(sa.String(64), nullable=False, unique=True, index=True)
    client_id = sa.Column(sa.Integer, sa.ForeignKey('oauth_clients.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    redirect_uri = sa.Column(sa.String(500), nullable=False)
    scopes = sa.Column(sa.Text, nullable=False)
    code_challenge = sa.Column(sa.String(128), nullable=False)
    code_challenge_method = sa.Column(sa.String(10), nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=False, index=True)
    is_used = sa.Column(sa.Boolean, nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)


# models/oauth_client.py
class OAuthClient(_HistoricalBase):
    __tablename__ = 'oauth_clients'
    id = sa.Column(sa.Integer, primary_key=True)
    client_id = sa.Column(sa.String(64), nullable=False, unique=True, index=True)
    client_secret = sa.Column(sa.String(255), nullable=True)
    client_secret_hash = sa.Column(sa.String(255), nullable=True)
    client_name = sa.Column(sa.String(120), nullable=False)
    client_uri = sa.Column(sa.String(255), nullable=True)
    redirect_uris = sa.Column(sa.Text, nullable=False)
    is_confidential = sa.Column(sa.Boolean, nullable=False)
    is_default = sa.Column(sa.Boolean, nullable=False, index=True)
    is_active = sa.Column(sa.Boolean, nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)


# models/password_reset_token.py
class PasswordResetToken(_HistoricalBase):
    __tablename__ = 'password_reset_tokens'
    __table_args__ = (sa.Index('ix_password_reset_tokens_user_active', 'user_id', 'used_at', 'revoked_at'), sa.Index('ix_password_reset_tokens_expires_at', 'expires_at'))
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_hash = sa.Column(sa.String(64), nullable=False, unique=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=False)
    used_at = sa.Column(sa.DateTime, nullable=True)
    revoked_at = sa.Column(sa.DateTime, nullable=True)


# models/payment_attempt.py
class PaymentAttempt(_HistoricalBase):
    __tablename__ = 'payment_attempts'
    id = sa.Column(sa.String(36), primary_key=True)
    order_id = sa.Column(sa.String(36), sa.ForeignKey('payment_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    provider_code = sa.Column(sa.String(64), nullable=False)
    payment_method_code = sa.Column(sa.String(64), nullable=False)
    status = sa.Column(sa.Enum('created', 'pending', 'confirmed', 'manual_review', 'expired', 'canceled', 'failed', 'refunded', name='payment_attempt_status_enum', native_enum=False), nullable=False, index=True)
    amount_minor = sa.Column(sa.Integer, nullable=False)
    currency_code = sa.Column(sa.String(8), nullable=False)
    provider_payment_id = sa.Column(sa.String(255), nullable=True)
    provider_order_code = sa.Column(sa.String(255), nullable=True)
    expected_payment_reference = sa.Column(sa.String(255), nullable=True, index=True)
    checkout_url = sa.Column(sa.Text, nullable=True)
    provider_metadata_json = sa.Column(sa.JSON, nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=True, index=True)
    confirmed_at = sa.Column(sa.DateTime, nullable=True)
    failed_at = sa.Column(sa.DateTime, nullable=True)
    failure_code = sa.Column(sa.String(120), nullable=True)
    failure_message = sa.Column(sa.Text, nullable=True)
    manual_review_reason = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (Index('ix_payment_attempts_order_created_at', 'order_id', 'created_at'), Index('ix_payment_attempts_status_expires_at', 'status', 'expires_at'), UniqueConstraint('provider_code', 'provider_payment_id', name='uq_payment_attempts_provider_payment_id'), UniqueConstraint('provider_code', 'provider_order_code', name='uq_payment_attempts_provider_order_code'))


# models/payment_entitlement.py
class PaymentEntitlement(_HistoricalBase):
    __tablename__ = 'payment_entitlements'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    payment_order_id = sa.Column(sa.String(36), sa.ForeignKey('payment_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    payment_order_item_id = sa.Column(sa.String(36), sa.ForeignKey('payment_order_items.id', ondelete='CASCADE'), nullable=False, index=True)
    payment_attempt_id = sa.Column(sa.String(36), sa.ForeignKey('payment_attempts.id', ondelete='SET NULL'), nullable=True, index=True)
    entitlement_type = sa.Column(sa.String(64), nullable=False)
    resource_type = sa.Column(sa.String(64), nullable=False)
    resource_ref_id = sa.Column(sa.String(36), nullable=False)
    status = sa.Column(sa.Enum('pending', 'active', 'revoked', 'expired', 'refunded', name='payment_entitlement_status_enum', native_enum=False), nullable=False, index=True)
    granted_at = sa.Column(sa.DateTime, nullable=True)
    effective_from = sa.Column(sa.DateTime, nullable=True)
    expires_at = sa.Column(sa.DateTime, nullable=True)
    revoked_at = sa.Column(sa.DateTime, nullable=True)
    grant_data_json = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('payment_order_item_id', name='uq_payment_entitlements_order_item'), Index('ix_payment_entitlements_user_status', 'user_id', 'status'), Index('ix_payment_entitlements_resource_ref', 'resource_type', 'resource_ref_id'))


# models/payment_order.py
class PaymentOrder(_HistoricalBase):
    __tablename__ = 'payment_orders'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    merchant_order_code = sa.Column(sa.String(64), nullable=False, unique=True)
    status = sa.Column(sa.Enum('pending_payment', 'paid', 'under_review', 'expired', 'canceled', 'failed', 'refunded', name='payment_order_status_enum', native_enum=False), nullable=False, index=True)
    grant_status = sa.Column(sa.Enum('pending', 'completed', 'failed', name='payment_order_grant_status_enum', native_enum=False), nullable=False, index=True)
    currency_code = sa.Column(sa.String(8), nullable=False)
    subtotal_amount_minor = sa.Column(sa.Integer, nullable=False)
    discount_amount_minor = sa.Column(sa.Integer, nullable=False)
    total_amount_minor = sa.Column(sa.Integer, nullable=False)
    paid_at = sa.Column(sa.DateTime, nullable=True)
    closed_at = sa.Column(sa.DateTime, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (Index('ix_payment_orders_user_created_at', 'user_id', 'created_at'), Index('ix_payment_orders_status_created_at', 'status', 'created_at'), Index('ix_payment_orders_grant_status_created_at', 'grant_status', 'created_at'))


# models/payment_order_item.py
class PaymentOrderItem(_HistoricalBase):
    __tablename__ = 'payment_order_items'
    id = sa.Column(sa.String(36), primary_key=True)
    order_id = sa.Column(sa.String(36), sa.ForeignKey('payment_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    product_type = sa.Column(sa.String(64), nullable=False)
    product_ref_id = sa.Column(sa.String(36), nullable=False)
    quantity = sa.Column(sa.Integer, nullable=False)
    unit_amount_minor = sa.Column(sa.Integer, nullable=False)
    line_total_amount_minor = sa.Column(sa.Integer, nullable=False)
    title_snapshot = sa.Column(sa.String(255), nullable=False)
    product_snapshot_json = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('order_id', 'product_type', 'product_ref_id', name='uq_payment_order_items_order_product'), Index('ix_payment_order_items_product_ref', 'product_type', 'product_ref_id'))


# models/payment_webhook_event.py
class PaymentWebhookEvent(_HistoricalBase):
    __tablename__ = 'payment_webhook_events'
    id = sa.Column(sa.String(36), primary_key=True)
    provider_code = sa.Column(sa.String(64), nullable=False)
    event_key = sa.Column(sa.String(255), nullable=False)
    event_type = sa.Column(sa.String(120), nullable=False)
    payment_attempt_id = sa.Column(sa.String(36), sa.ForeignKey('payment_attempts.id', ondelete='SET NULL'), nullable=True, index=True)
    payment_order_id = sa.Column(sa.String(36), sa.ForeignKey('payment_orders.id', ondelete='SET NULL'), nullable=True, index=True)
    signature_valid = sa.Column(sa.Boolean, nullable=False)
    processing_status = sa.Column(sa.Enum('received', 'processed', 'ignored', 'failed', name='payment_webhook_processing_status_enum', native_enum=False), nullable=False, index=True)
    error_message = sa.Column(sa.Text, nullable=True)
    payload_json = sa.Column(sa.JSON, nullable=False)
    received_at = sa.Column(sa.DateTime, nullable=False)
    processed_at = sa.Column(sa.DateTime, nullable=True)
    __table_args__ = (UniqueConstraint('provider_code', 'event_key', name='uq_payment_webhook_events_provider_event'), Index('ix_payment_webhook_events_processing_status_received_at', 'processing_status', 'received_at'), Index('ix_payment_webhook_events_payment_attempt_received_at', 'payment_attempt_id', 'received_at'), Index('ix_payment_webhook_events_payment_order_received_at', 'payment_order_id', 'received_at'))


# models/payout_batch.py
class PayoutBatch(_HistoricalBase):
    __tablename__ = 'payout_batches'
    id = sa.Column(sa.Integer, primary_key=True)
    reference_id = sa.Column(sa.String(96), nullable=False, unique=True, index=True)
    client_reference_key = sa.Column(sa.String(96), nullable=False, index=True)
    request_fingerprint = sa.Column(sa.String(64), nullable=False, index=True)
    provider_payout_id = sa.Column(sa.String(128), nullable=True, unique=True, index=True)
    internal_status = sa.Column(sa.String(32), nullable=False, index=True)
    provider_approval_state = sa.Column(sa.String(32), nullable=True, index=True)
    validate_destination = sa.Column(sa.Boolean, nullable=False)
    item_count = sa.Column(sa.Integer, nullable=False)
    category_json = sa.Column(sa.Text, nullable=False)
    request_payload_json = sa.Column(sa.Text, nullable=False)
    response_payload_json = sa.Column(sa.Text, nullable=True)
    error_payload_json = sa.Column(sa.Text, nullable=True)
    created_by_admin_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    submitted_at = sa.Column(sa.DateTime, nullable=True, index=True)
    last_synced_at = sa.Column(sa.DateTime, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False, index=True)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/payout_batch_item.py
class PayoutBatchItem(_HistoricalBase):
    __tablename__ = 'payout_batch_items'
    id = sa.Column(sa.Integer, primary_key=True)
    batch_id = sa.Column(sa.Integer, sa.ForeignKey('payout_batches.id', ondelete='CASCADE'), nullable=False, index=True)
    reference_id = sa.Column(sa.String(128), nullable=False, unique=True, index=True)
    client_reference_key = sa.Column(sa.String(96), nullable=False, index=True)
    amount = sa.Column(sa.Integer, nullable=False)
    description = sa.Column(sa.String(255), nullable=False)
    to_bin = sa.Column(sa.String(12), nullable=False)
    to_account_number = sa.Column(sa.String(64), nullable=False)
    internal_status = sa.Column(sa.String(32), nullable=False, index=True)
    provider_transaction_id = sa.Column(sa.String(128), nullable=True, index=True)
    provider_reference = sa.Column(sa.String(128), nullable=True, index=True)
    provider_state = sa.Column(sa.String(32), nullable=True, index=True)
    response_payload_json = sa.Column(sa.Text, nullable=True)
    error_code = sa.Column(sa.String(64), nullable=True)
    error_message = sa.Column(sa.String(255), nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/review_event.py
class ReviewEvent(_HistoricalBase):
    __tablename__ = 'review_events'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    card_id = sa.Column(sa.String(64), nullable=False, index=True)
    deck_id = sa.Column(sa.Integer, nullable=True, index=True)
    note_type_id = sa.Column(sa.String(36), nullable=True, index=True)
    scheduler_preset_id = sa.Column(sa.Integer, sa.ForeignKey('scheduler_presets.id', ondelete='SET NULL'), nullable=True, index=True)
    study_session_id = sa.Column(sa.String(36), sa.ForeignKey('study_sessions.id', ondelete='SET NULL'), nullable=True, index=True)
    client_event_id = sa.Column(sa.String(36), nullable=True)
    sequence_no = sa.Column(sa.Integer, nullable=True)
    scheduler_algorithm = sa.Column(sa.String(64), nullable=True)
    algorithm_version = sa.Column(sa.String(32), nullable=True)
    scheduler_config_hash = sa.Column(sa.String(80), nullable=True)
    reviewed_at = sa.Column(sa.DateTime, nullable=False, index=True)
    duration_ms = sa.Column(sa.Integer, nullable=True)
    rating = sa.Column(sa.String(20), nullable=False)
    mode = sa.Column(sa.String(20), nullable=False)
    scheduler_mode = sa.Column(sa.String(20), nullable=False, index=True)
    review_kind = sa.Column(sa.String(20), nullable=False, index=True)
    queue_before = sa.Column(sa.String(20), nullable=True)
    queue_after = sa.Column(sa.String(20), nullable=True)
    interval_days_before = sa.Column(sa.Float, nullable=True)
    interval_days_after = sa.Column(sa.Float, nullable=True)
    due_day_before = sa.Column(sa.Integer, nullable=True)
    due_day_after = sa.Column(sa.Integer, nullable=True)
    days_late = sa.Column(sa.Integer, nullable=True)
    ease_factor_before = sa.Column(sa.Float, nullable=True)
    ease_factor_after = sa.Column(sa.Float, nullable=True)
    memory_stability_before = sa.Column(sa.Float, nullable=True)
    memory_stability_after = sa.Column(sa.Float, nullable=True)
    memory_difficulty_before = sa.Column(sa.Float, nullable=True)
    memory_difficulty_after = sa.Column(sa.Float, nullable=True)
    leeched_after = sa.Column(sa.Boolean, nullable=False)
    suspended_after = sa.Column(sa.Boolean, nullable=False)
    payload_json = sa.Column(sa.Text, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.UniqueConstraint('user_id', 'client_event_id', name='uq_review_events_user_client_event'), sa.UniqueConstraint('study_session_id', 'sequence_no', name='uq_review_events_session_sequence'), sa.Index('ix_review_events_user_reviewed_at', 'user_id', 'reviewed_at'), sa.Index('ix_review_events_user_card_reviewed_at', 'user_id', 'card_id', 'reviewed_at'), sa.Index('ix_review_events_user_scheduler_reviewed_at', 'user_id', 'scheduler_mode', 'reviewed_at'), sa.Index('ix_review_events_user_kind_reviewed_at', 'user_id', 'review_kind', 'reviewed_at'))


# models/scheduler_preset.py
class SchedulerPreset(_HistoricalBase):
    __tablename__ = 'scheduler_presets'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = sa.Column(sa.String(120), nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    learning_steps_json = sa.Column(sa.Text, nullable=False)
    relearning_steps_json = sa.Column(sa.Text, nullable=False)
    fsrs_parameters_json = sa.Column(sa.Text, nullable=False)
    extra_config_json = sa.Column(sa.Text, nullable=False)
    graduating_interval_days = sa.Column(sa.Integer, nullable=False)
    easy_interval_days = sa.Column(sa.Integer, nullable=False)
    hard_multiplier = sa.Column(sa.Float, nullable=False)
    easy_multiplier = sa.Column(sa.Float, nullable=False)
    interval_modifier = sa.Column(sa.Float, nullable=False)
    lapse_multiplier = sa.Column(sa.Float, nullable=False)
    minimum_lapse_interval_days = sa.Column(sa.Integer, nullable=False)
    maximum_interval_days = sa.Column(sa.Integer, nullable=False)
    leech_threshold = sa.Column(sa.Integer, nullable=False)
    leech_action = sa.Column(sa.String(32), nullable=False)
    desired_retention = sa.Column(sa.Float, nullable=False)
    historical_retention = sa.Column(sa.Float, nullable=True)
    ignore_reviews_before = sa.Column(sa.DateTime, nullable=True)
    fsrs_reschedule_on_change = sa.Column(sa.Boolean, nullable=False)
    fsrs_short_term_enabled = sa.Column(sa.Boolean, nullable=False)
    is_default = sa.Column(sa.Boolean, nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.UniqueConstraint('user_id', 'name', name='uq_scheduler_presets_user_name'), sa.Index('ix_scheduler_presets_user_default', 'user_id', 'is_default'))


# models/shared_image_asset.py
class SharedImageAsset(_HistoricalBase):
    __tablename__ = 'shared_image_assets'
    id = sa.Column(sa.String(36), primary_key=True)
    image_key = sa.Column(sa.String(120), nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    filename = sa.Column(sa.String(255), nullable=True)
    mime_type = sa.Column(sa.String(255), nullable=True)
    storage_path = sa.Column(sa.String(1024), nullable=True)
    sha256 = sa.Column(sa.String(64), nullable=True)
    size_bytes = sa.Column(sa.Integer, nullable=False)
    is_enabled = sa.Column(sa.Boolean, nullable=False)
    source_url = sa.Column(sa.String(2048), nullable=True)
    tags = sa.Column(sa.JSON, nullable=False)
    created_by_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_by_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('image_key', name='uq_shared_image_assets_image_key'), Index('ix_shared_image_assets_is_enabled', 'is_enabled'), Index('ix_shared_image_assets_updated_at', 'updated_at'), Index('ix_shared_image_assets_sha256', 'sha256'))


# models/study_session.py
class StudySession(_HistoricalBase):
    __tablename__ = 'study_sessions'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    scope_type = sa.Column(sa.String(20), nullable=False)
    scope_id = sa.Column(sa.String(64), nullable=False)
    local_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='SET NULL'), nullable=True, index=True)
    clone_install_id = sa.Column(sa.String(36), sa.ForeignKey('deck_installs.id', ondelete='SET NULL'), nullable=True, index=True)
    status = sa.Column(sa.String(20), nullable=False, index=True)
    scheduler_algorithm = sa.Column(sa.String(64), nullable=False)
    algorithm_version = sa.Column(sa.String(32), nullable=False)
    wire_schema_version = sa.Column(sa.String(32), nullable=False)
    timezone = sa.Column(sa.String(64), nullable=False)
    day_boundary_hour_local = sa.Column(sa.Integer, nullable=False)
    learn_ahead_seconds = sa.Column(sa.Integer, nullable=False)
    snapshot_hash = sa.Column(sa.String(80), nullable=False, index=True)
    token_hash = sa.Column(sa.String(64), nullable=False)
    config_snapshot_json = sa.Column(sa.Text, nullable=False)
    opened_at = sa.Column(sa.DateTime, nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=False, index=True)
    committed_at = sa.Column(sa.DateTime, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.Index('ix_study_sessions_user_status_expires', 'user_id', 'status', 'expires_at'),)


# models/study_session_batch.py
class StudySessionBatch(_HistoricalBase):
    __tablename__ = 'study_session_batches'
    id = sa.Column(sa.String(36), primary_key=True)
    session_id = sa.Column(sa.String(36), sa.ForeignKey('study_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    batch_id = sa.Column(sa.String(64), nullable=False, index=True)
    batch_sequence = sa.Column(sa.Integer, nullable=False)
    event_count = sa.Column(sa.Integer, nullable=False)
    status = sa.Column(sa.String(20), nullable=False, index=True)
    commit_reason = sa.Column(sa.String(32), nullable=True)
    is_final = sa.Column(sa.Boolean, nullable=False)
    request_hash = sa.Column(sa.String(80), nullable=False)
    payload_json = sa.Column(sa.Text, nullable=True)
    response_json = sa.Column(sa.Text, nullable=True)
    error_message = sa.Column(sa.Text, nullable=True)
    enqueued_at = sa.Column(sa.DateTime, nullable=False)
    processed_at = sa.Column(sa.DateTime, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.UniqueConstraint('session_id', 'batch_id', name='uq_study_session_batches_batch_id'), sa.Index('ix_study_session_batches_status_enqueued', 'status', 'enqueued_at'))


# models/study_session_card.py
class StudySessionCard(_HistoricalBase):
    __tablename__ = 'study_session_cards'
    id = sa.Column(sa.Integer, primary_key=True)
    session_id = sa.Column(sa.String(36), sa.ForeignKey('study_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    card_id = sa.Column(sa.String(36), sa.ForeignKey('cards.id', ondelete='CASCADE'), nullable=False, index=True)
    source_deck_id = sa.Column(sa.Integer, nullable=True)
    local_deck_id = sa.Column(sa.Integer, sa.ForeignKey('decks.id', ondelete='SET NULL'), nullable=True, index=True)
    note_type_id = sa.Column(sa.String(36), nullable=True)
    scheduler_preset_id = sa.Column(sa.Integer, sa.ForeignKey('scheduler_presets.id', ondelete='SET NULL'), nullable=True)
    base_progress_revision = sa.Column(sa.BigInteger, nullable=False)
    base_state_hash = sa.Column(sa.String(80), nullable=False)
    scheduler_config_hash = sa.Column(sa.String(80), nullable=False, index=True)
    initial_state_json = sa.Column(sa.Text, nullable=False)
    ordinal = sa.Column(sa.Integer, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.UniqueConstraint('session_id', 'card_id', name='uq_study_session_cards_session_card'), sa.Index('ix_study_session_cards_session_ordinal', 'session_id', 'ordinal'))


# models/study_session_commit.py
class StudySessionCommit(_HistoricalBase):
    __tablename__ = 'study_session_commits'
    id = sa.Column(sa.String(36), primary_key=True)
    session_id = sa.Column(sa.String(36), sa.ForeignKey('study_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    idempotency_key = sa.Column(sa.String(64), nullable=False)
    request_hash = sa.Column(sa.String(80), nullable=False)
    response_json = sa.Column(sa.Text, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.UniqueConstraint('session_id', 'idempotency_key', name='uq_study_session_commits_idempotency'), sa.UniqueConstraint('session_id', name='uq_study_session_commits_single_success'))


# models/support_donation_config.py
class SupportDonationConfig(_HistoricalBase):
    __tablename__ = 'support_donation_config'
    id = sa.Column(sa.Integer, primary_key=True)
    title = sa.Column(sa.String(120), nullable=False)
    description = sa.Column(sa.Text, nullable=False)
    account_name = sa.Column(sa.String(255), nullable=False)
    account_number = sa.Column(sa.String(64), nullable=False)
    thank_you_message = sa.Column(sa.Text, nullable=False)
    qr_image_filename = sa.Column(sa.String(255), nullable=True)
    qr_image_storage_path = sa.Column(sa.String(1024), nullable=True)
    qr_image_mime_type = sa.Column(sa.String(64), nullable=True)
    updated_by_admin_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/support_ticket.py
class SupportTicket(_HistoricalBase):
    __tablename__ = 'support_tickets'
    id = sa.Column(sa.String(36), primary_key=True)
    ticket_code = sa.Column(sa.String(32), nullable=False)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    user_email = sa.Column(sa.String(255), nullable=True)
    sender_name = sa.Column(sa.String(150), nullable=True)
    category = sa.Column(sa.String(50), nullable=False)
    title = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.Text, nullable=False)
    reproduce_steps = sa.Column(sa.Text, nullable=True)
    screen_url = sa.Column(sa.String(500), nullable=True)
    screen_name = sa.Column(sa.String(255), nullable=True)
    attachment_urls_json = sa.Column(sa.Text, nullable=True)
    status = sa.Column(sa.String(30), nullable=False)
    priority = sa.Column(sa.String(20), nullable=False)
    admin_notes = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    resolved_at = sa.Column(sa.DateTime, nullable=True)
    __table_args__ = (UniqueConstraint('ticket_code', name='uq_support_tickets_ticket_code'), Index('ix_support_tickets_user_id', 'user_id'), Index('ix_support_tickets_status', 'status'), Index('ix_support_tickets_category', 'category'), Index('ix_support_tickets_created_at', 'created_at'))


# models/support_ticket_reply.py
class SupportTicketReply(_HistoricalBase):
    __tablename__ = 'support_ticket_replies'
    id = sa.Column(sa.String(36), primary_key=True)
    ticket_id = sa.Column(sa.String(36), sa.ForeignKey('support_tickets.id', ondelete='CASCADE'), nullable=False)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    is_admin_reply = sa.Column(sa.Boolean, nullable=False)
    sender_name = sa.Column(sa.String(150), nullable=True)
    message = sa.Column(sa.Text, nullable=False)
    attachment_urls_json = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (Index('ix_support_ticket_replies_ticket_id', 'ticket_id'), Index('ix_support_ticket_replies_created_at', 'created_at'))


# models/taxonomy.py
class TaxonomyDomain(_HistoricalBase):
    __tablename__ = 'taxonomy_domains'
    id = sa.Column(sa.String(64), primary_key=True)
    label = sa.Column(sa.String(128), nullable=False)
    sort_order = sa.Column(sa.Integer, nullable=False)
    is_active = sa.Column(sa.Boolean, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/taxonomy.py
class TaxonomySubject(_HistoricalBase):
    __tablename__ = 'taxonomy_subjects'
    id = sa.Column(sa.String(64), primary_key=True)
    domain_id = sa.Column(sa.String(64), sa.ForeignKey('taxonomy_domains.id', ondelete='CASCADE'), nullable=False, index=True)
    label = sa.Column(sa.String(128), nullable=False)
    sort_order = sa.Column(sa.Integer, nullable=False)
    is_active = sa.Column(sa.Boolean, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/taxonomy.py
class TaxonomyFramework(_HistoricalBase):
    __tablename__ = 'taxonomy_frameworks'
    id = sa.Column(sa.String(64), primary_key=True)
    subject_id = sa.Column(sa.String(64), sa.ForeignKey('taxonomy_subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    label = sa.Column(sa.String(128), nullable=False)
    sort_order = sa.Column(sa.Integer, nullable=False)
    is_active = sa.Column(sa.Boolean, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/taxonomy.py
class TaxonomyFrameworkLevel(_HistoricalBase):
    __tablename__ = 'taxonomy_framework_levels'
    id = sa.Column(sa.String(64), primary_key=True)
    framework_id = sa.Column(sa.String(64), sa.ForeignKey('taxonomy_frameworks.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id = sa.Column(sa.String(64), sa.ForeignKey('taxonomy_subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    label = sa.Column(sa.String(128), nullable=False)
    difficulty_band = sa.Column(sa.String(32), nullable=False)
    suggested_tags = sa.Column(sa.JSON, nullable=True)
    sort_order = sa.Column(sa.Integer, nullable=False)
    is_active = sa.Column(sa.Boolean, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/taxonomy.py
class TaxonomyOption(_HistoricalBase):
    __tablename__ = 'taxonomy_options'
    id = sa.Column(sa.String(64), primary_key=True)
    option_type = sa.Column(sa.String(32), primary_key=True)
    label = sa.Column(sa.String(128), nullable=False)
    sub_label = sa.Column(sa.String(255), nullable=True)
    sort_order = sa.Column(sa.Integer, nullable=False)
    is_active = sa.Column(sa.Boolean, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/taxonomy.py
class TaxonomySubjectOptionMap(_HistoricalBase):
    __tablename__ = 'taxonomy_subject_option_maps'
    __table_args__ = (sa.UniqueConstraint('subject_id', 'option_id', 'option_type', name='uq_taxonomy_sub_opt_map'), sa.ForeignKeyConstraint(['option_id', 'option_type'], ['taxonomy_options.id', 'taxonomy_options.option_type'], ondelete='CASCADE'))
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    subject_id = sa.Column(sa.String(64), sa.ForeignKey('taxonomy_subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    option_id = sa.Column(sa.String(64), nullable=False, index=True)
    option_type = sa.Column(sa.String(32), nullable=False, index=True)


# models/template.py
class Template(_HistoricalBase):
    __tablename__ = 'templates'
    id = sa.Column(sa.String(36), primary_key=True)
    note_type_id = sa.Column(sa.String(36), sa.ForeignKey('note_types.id', ondelete='CASCADE'), nullable=False, index=True)
    name = sa.Column(sa.String(255), nullable=False)
    front_html = sa.Column(sa.Text, nullable=False)
    back_html = sa.Column(sa.Text, nullable=False)
    shared_css = sa.Column(sa.Text, nullable=False)
    position = sa.Column(sa.Integer, nullable=False)
    is_default = sa.Column(sa.Boolean, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/tts_provider_config.py
class TtsProviderConfig(_HistoricalBase):
    __tablename__ = 'tts_provider_config'
    id = sa.Column(sa.Integer, primary_key=True)
    provider_name = sa.Column(sa.String(120), nullable=False, index=True)
    provider_type = sa.Column(sa.String(64), nullable=False, index=True)
    base_url = sa.Column(sa.String(500), nullable=True)
    requires_api_key = sa.Column(sa.Boolean, nullable=False)
    is_active = sa.Column(sa.Boolean, nullable=False, index=True)
    shared_config_json = sa.Column(sa.Text, nullable=False)
    provider_config_json = sa.Column(sa.Text, nullable=False)
    default_settings_json = sa.Column(sa.Text, nullable=False)
    created_by_admin_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    updated_by_admin_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/tts_user_provider_profile.py
class TtsUserProviderProfile(_HistoricalBase):
    __tablename__ = 'tts_user_provider_profile'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    provider_id = sa.Column(sa.Integer, sa.ForeignKey('tts_provider_config.id', ondelete='CASCADE'), nullable=False, index=True)
    encrypted_api_key = sa.Column(sa.Text, nullable=True)
    key_status = sa.Column(sa.String(32), nullable=False, index=True)
    last_validated_at = sa.Column(sa.DateTime, nullable=True)
    last_validation_error = sa.Column(sa.String(500), nullable=True)
    settings_json = sa.Column(sa.Text, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.UniqueConstraint('user_id', 'provider_id', name='uq_tts_user_provider_profile'),)


# models/user.py
class User(_HistoricalBase):
    __tablename__ = 'users'
    id = sa.Column(sa.Integer, primary_key=True)
    email = sa.Column(sa.String(255), unique=True, nullable=False, index=True)
    username = sa.Column(sa.String(150), unique=True, nullable=False)
    display_name = sa.Column(sa.String(150), nullable=True)
    avatar_url = sa.Column(sa.String(512), nullable=True)
    bio = sa.Column(sa.Text, nullable=True)
    social_links = sa.Column(sa.JSON, nullable=True)
    password_hash = sa.Column(sa.String(255), nullable=True)
    timezone = sa.Column(sa.String(64), nullable=False)
    role_id = sa.Column(sa.Integer, sa.ForeignKey('user_roles.id'), nullable=True, index=True)
    is_admin = sa.Column(sa.Boolean, nullable=False)
    is_disabled = sa.Column(sa.Boolean, nullable=False)
    can_use_mcp = sa.Column(sa.Boolean, nullable=False)
    can_manage_mcp_tokens = sa.Column(sa.Boolean, nullable=False)
    balance_amount_minor = sa.Column(sa.Integer, nullable=False)
    custom_platform_fee_percent = sa.Column(sa.Float, nullable=True)
    email_verified_at = sa.Column(sa.DateTime, nullable=True)
    email_verification_source = sa.Column(sa.String(32), nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/user_api_token.py
class UserApiToken(_HistoricalBase):
    __tablename__ = 'user_api_tokens'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = sa.Column(sa.String(120), nullable=False)
    token_hash = sa.Column(sa.String(64), nullable=False, unique=True, index=True)
    token_prefix = sa.Column(sa.String(32), nullable=False)
    scopes = sa.Column(sa.Text, nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=True, index=True)
    revoked_at = sa.Column(sa.DateTime, nullable=True, index=True)
    last_used_at = sa.Column(sa.DateTime, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/user_balance_transaction.py
class UserBalanceTransaction(_HistoricalBase):
    __tablename__ = 'user_balance_transactions'
    id = sa.Column(sa.String(36), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    buyer_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    payment_order_id = sa.Column(sa.String(36), sa.ForeignKey('payment_orders.id', ondelete='SET NULL'), nullable=True, index=True)
    payment_order_item_id = sa.Column(sa.String(36), sa.ForeignKey('payment_order_items.id', ondelete='SET NULL'), nullable=True, index=True)
    transaction_type = sa.Column(sa.String(50), nullable=False, index=True)
    gross_amount_minor = sa.Column(sa.Integer, nullable=False)
    platform_fee_percent = sa.Column(sa.Float, nullable=False)
    platform_fee_amount_minor = sa.Column(sa.Integer, nullable=False)
    net_amount_minor = sa.Column(sa.Integer, nullable=False)
    balance_after_minor = sa.Column(sa.Integer, nullable=False)
    description = sa.Column(sa.String(255), nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('payment_order_item_id', 'user_id', 'transaction_type', name='uq_user_balance_tx_order_item_user_type'), Index('ix_user_balance_tx_user_created', 'user_id', 'created_at'))


# models/user_identity.py
class UserIdentity(_HistoricalBase):
    __tablename__ = 'user_identities'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    provider = sa.Column(sa.String(32), nullable=False)
    provider_sub = sa.Column(sa.String(255), nullable=False)
    provider_email = sa.Column(sa.String(255), nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    __table_args__ = (sa.UniqueConstraint('provider', 'provider_sub', name='uq_user_identity_provider_sub'),)


# models/user_permission_audit_log.py
class UserPermissionAuditLog(_HistoricalBase):
    __tablename__ = 'user_permission_audit_logs'
    id = sa.Column(sa.Integer, primary_key=True)
    actor_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id'), nullable=False, index=True)
    target_user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id'), nullable=False, index=True)
    action = sa.Column(sa.String(50), nullable=False, index=True)
    from_role_id = sa.Column(sa.Integer, sa.ForeignKey('user_roles.id'), nullable=True, index=True)
    to_role_id = sa.Column(sa.Integer, sa.ForeignKey('user_roles.id'), nullable=True, index=True)
    from_is_admin = sa.Column(sa.Boolean, nullable=False)
    to_is_admin = sa.Column(sa.Boolean, nullable=False)
    from_is_disabled = sa.Column(sa.Boolean, nullable=False)
    to_is_disabled = sa.Column(sa.Boolean, nullable=False)
    message = sa.Column(sa.String(255), nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False, index=True)


# models/user_role.py
class UserRole(_HistoricalBase):
    __tablename__ = 'user_roles'
    id = sa.Column(sa.Integer, primary_key=True)
    code = sa.Column(sa.String(50), unique=True, nullable=False, index=True)
    name = sa.Column(sa.String(150), unique=True, nullable=False)
    description = sa.Column(sa.String(255), nullable=True)
    is_admin = sa.Column(sa.Boolean, nullable=False)
    position = sa.Column(sa.Integer, nullable=False)
    default_platform_fee_percent = sa.Column(sa.Float, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


# models/user_scheduler_settings.py
class UserSchedulerSettings(_HistoricalBase):
    __tablename__ = 'user_scheduler_settings'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    scheduler_mode = sa.Column(sa.String(20), nullable=False, index=True)
    day_boundary_hour_local = sa.Column(sa.Integer, nullable=False)
    learn_ahead_seconds = sa.Column(sa.Integer, nullable=False)
    fsrs_allow_short_term = sa.Column(sa.Boolean, nullable=False)
    extra_settings_json = sa.Column(sa.Text, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)


def bootstrap_empty_schema(connection):
    """Create only this frozen baseline, refusing every preexisting object."""
    inspector = sa.inspect(connection)
    existing = sorted(set(inspector.get_table_names()) | set(inspector.get_view_names()))
    if existing:
        raise RuntimeError("Historical bootstrap requires an entirely empty schema; found: " + ", ".join(existing))
    HISTORICAL_BOOTSTRAP_METADATA.create_all(connection, checkfirst=False)
