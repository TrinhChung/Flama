"""Legacy schema compatibility helpers used during startup maintenance."""

from __future__ import annotations

import sqlalchemy as sa

from models import db


def ensure_backward_compatible_schema() -> None:
    """Patch schema for incremental local upgrades."""
    bind = db.session.get_bind()
    if bind is None:
        return

    is_mysql = str(bind.dialect.name).lower().startswith("mysql")
    inspector = sa.inspect(bind)
    schema_changed = False

    def _refresh_inspector():
        return sa.inspect(bind)

    def _column_names(table_name: str) -> set[str]:
        local_inspector = _refresh_inspector()
        if not local_inspector.has_table(table_name):
            return set()
        return {column["name"] for column in local_inspector.get_columns(table_name)}

    def _index_names(table_name: str) -> set[str]:
        local_inspector = _refresh_inspector()
        if not local_inspector.has_table(table_name):
            return set()
        return {index["name"] for index in local_inspector.get_indexes(table_name)}

    def _ensure_column(table_name: str, column_name: str, ddl_sql: str) -> bool:
        nonlocal schema_changed
        if column_name in _column_names(table_name):
            return False
        db.session.execute(sa.text(ddl_sql))
        schema_changed = True
        return True

    def _ensure_index(table_name: str, index_name: str, ddl_sql: str) -> bool:
        nonlocal schema_changed
        if index_name in _index_names(table_name):
            return False
        db.session.execute(sa.text(ddl_sql))
        schema_changed = True
        return True

    def _rename_int_column_if_present(
        table_name: str,
        old_name: str,
        new_name: str,
        *,
        nullable: bool = False,
        default: int = 0,
    ) -> bool:
        nonlocal schema_changed
        column_names = _column_names(table_name)
        if new_name in column_names or old_name not in column_names:
            return False
        if is_mysql:
            null_sql = "NULL" if nullable else "NOT NULL"
            ddl_sql = (
                f"ALTER TABLE {table_name} CHANGE COLUMN {old_name} {new_name} "
                f"INT {null_sql} DEFAULT {default}"
            )
        else:
            ddl_sql = f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name}"
        db.session.execute(sa.text(ddl_sql))
        schema_changed = True
        return True

    if inspector.has_table("users"):
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "timezone" not in user_columns:
            db.session.execute(
                sa.text("ALTER TABLE users ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'")
            )
            db.session.execute(
                sa.text("UPDATE users SET timezone = 'UTC' WHERE timezone IS NULL OR timezone = ''")
            )
            schema_changed = True
        if "display_name" not in user_columns:
            db.session.execute(
                sa.text("ALTER TABLE users ADD COLUMN display_name VARCHAR(150) NULL")
            )
            schema_changed = True
        if "avatar_url" not in user_columns:
            db.session.execute(
                sa.text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512) NULL")
            )
            schema_changed = True
        if "bio" not in user_columns:
            db.session.execute(
                sa.text("ALTER TABLE users ADD COLUMN bio TEXT NULL")
            )
            schema_changed = True
        if "social_links" not in user_columns:
            social_links_ddl = (
                "ALTER TABLE users ADD COLUMN social_links JSON NULL"
                if is_mysql
                else "ALTER TABLE users ADD COLUMN social_links TEXT NULL"
            )
            db.session.execute(sa.text(social_links_ddl))
            db.session.execute(
                sa.text("UPDATE users SET social_links = '[]' WHERE social_links IS NULL OR social_links = ''")
            )
            schema_changed = True

    _rename_int_column_if_present("note_types", "price_cents", "price_amount_minor")
    _rename_int_column_if_present("deck_marketplace_items", "price_cents", "price_amount_minor")
    _rename_int_column_if_present("note_type_installs", "purchase_price_cents", "purchase_amount_minor")
    _rename_int_column_if_present("deck_installs", "purchase_price_cents", "purchase_amount_minor")

    note_type_taxonomy_ddl = (
        "ALTER TABLE note_types ADD COLUMN taxonomy_metadata JSON NULL"
        if is_mysql
        else "ALTER TABLE note_types ADD COLUMN taxonomy_metadata TEXT NULL"
    )
    if _ensure_column("note_types", "taxonomy_metadata", note_type_taxonomy_ddl):
        db.session.execute(
            sa.text(
                "UPDATE note_types SET taxonomy_metadata = '{}' "
                "WHERE taxonomy_metadata IS NULL OR taxonomy_metadata = ''"
            )
        )

    deck_taxonomy_ddl = (
        "ALTER TABLE deck_marketplace_items ADD COLUMN taxonomy_metadata JSON NULL"
        if is_mysql
        else "ALTER TABLE deck_marketplace_items ADD COLUMN taxonomy_metadata TEXT NULL"
    )
    if _ensure_column("deck_marketplace_items", "taxonomy_metadata", deck_taxonomy_ddl):
        db.session.execute(
            sa.text(
                "UPDATE deck_marketplace_items SET taxonomy_metadata = '{}' "
                "WHERE taxonomy_metadata IS NULL OR taxonomy_metadata = ''"
            )
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("user_scheduler_settings"):
        if _ensure_column(
            "user_scheduler_settings",
            "scheduler_mode",
            "ALTER TABLE user_scheduler_settings ADD COLUMN scheduler_mode VARCHAR(20) NOT NULL DEFAULT 'legacy'",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE user_scheduler_settings SET scheduler_mode = 'legacy' "
                    "WHERE scheduler_mode IS NULL OR scheduler_mode = ''"
                )
            )
        if _ensure_column(
            "user_scheduler_settings",
            "day_boundary_hour_local",
            "ALTER TABLE user_scheduler_settings ADD COLUMN day_boundary_hour_local INTEGER NOT NULL DEFAULT 4",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE user_scheduler_settings SET day_boundary_hour_local = 4 "
                    "WHERE day_boundary_hour_local IS NULL"
                )
            )
        if _ensure_column(
            "user_scheduler_settings",
            "learn_ahead_seconds",
            "ALTER TABLE user_scheduler_settings ADD COLUMN learn_ahead_seconds INTEGER NOT NULL DEFAULT 1200",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE user_scheduler_settings SET learn_ahead_seconds = 1200 "
                    "WHERE learn_ahead_seconds IS NULL"
                )
            )
        if _ensure_column(
            "user_scheduler_settings",
            "fsrs_allow_short_term",
            "ALTER TABLE user_scheduler_settings ADD COLUMN fsrs_allow_short_term BOOLEAN NOT NULL DEFAULT 0",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE user_scheduler_settings SET fsrs_allow_short_term = 0 "
                    "WHERE fsrs_allow_short_term IS NULL"
                )
            )
        if _ensure_column(
            "user_scheduler_settings",
            "extra_settings_json",
            "ALTER TABLE user_scheduler_settings ADD COLUMN extra_settings_json TEXT NULL",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE user_scheduler_settings SET extra_settings_json = '{}' "
                    "WHERE extra_settings_json IS NULL OR extra_settings_json = ''"
                )
            )
        _ensure_index(
            "user_scheduler_settings",
            "ix_user_scheduler_settings_scheduler_mode",
            "CREATE INDEX ix_user_scheduler_settings_scheduler_mode ON user_scheduler_settings (scheduler_mode)",
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("scheduler_presets"):
        if _ensure_column(
            "scheduler_presets",
            "description",
            "ALTER TABLE scheduler_presets ADD COLUMN description TEXT NULL",
        ):
            pass
        if _ensure_column(
            "scheduler_presets",
            "learning_steps_json",
            "ALTER TABLE scheduler_presets ADD COLUMN learning_steps_json TEXT NULL",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE scheduler_presets SET learning_steps_json = '[60, 600]' "
                    "WHERE learning_steps_json IS NULL OR learning_steps_json = ''"
                )
            )
        if _ensure_column(
            "scheduler_presets",
            "relearning_steps_json",
            "ALTER TABLE scheduler_presets ADD COLUMN relearning_steps_json TEXT NULL",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE scheduler_presets SET relearning_steps_json = '[600]' "
                    "WHERE relearning_steps_json IS NULL OR relearning_steps_json = ''"
                )
            )
        if _ensure_column(
            "scheduler_presets",
            "fsrs_parameters_json",
            "ALTER TABLE scheduler_presets ADD COLUMN fsrs_parameters_json TEXT NULL",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE scheduler_presets SET fsrs_parameters_json = '[]' "
                    "WHERE fsrs_parameters_json IS NULL OR fsrs_parameters_json = ''"
                )
            )
        if _ensure_column(
            "scheduler_presets",
            "extra_config_json",
            "ALTER TABLE scheduler_presets ADD COLUMN extra_config_json TEXT NULL",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE scheduler_presets SET extra_config_json = '{}' "
                    "WHERE extra_config_json IS NULL OR extra_config_json = ''"
                )
            )
        for column_name, ddl_sql, update_sql in (
            (
                "graduating_interval_days",
                "ALTER TABLE scheduler_presets ADD COLUMN graduating_interval_days INTEGER NOT NULL DEFAULT 1",
                "UPDATE scheduler_presets SET graduating_interval_days = 1 WHERE graduating_interval_days IS NULL",
            ),
            (
                "easy_interval_days",
                "ALTER TABLE scheduler_presets ADD COLUMN easy_interval_days INTEGER NOT NULL DEFAULT 5",
                "UPDATE scheduler_presets SET easy_interval_days = 5 WHERE easy_interval_days IS NULL",
            ),
            (
                "hard_multiplier",
                "ALTER TABLE scheduler_presets ADD COLUMN hard_multiplier FLOAT NOT NULL DEFAULT 1.2",
                "UPDATE scheduler_presets SET hard_multiplier = 1.2 WHERE hard_multiplier IS NULL",
            ),
            (
                "easy_multiplier",
                "ALTER TABLE scheduler_presets ADD COLUMN easy_multiplier FLOAT NOT NULL DEFAULT 1.3",
                "UPDATE scheduler_presets SET easy_multiplier = 1.3 WHERE easy_multiplier IS NULL",
            ),
            (
                "interval_modifier",
                "ALTER TABLE scheduler_presets ADD COLUMN interval_modifier FLOAT NOT NULL DEFAULT 1.0",
                "UPDATE scheduler_presets SET interval_modifier = 1.0 WHERE interval_modifier IS NULL",
            ),
            (
                "lapse_multiplier",
                "ALTER TABLE scheduler_presets ADD COLUMN lapse_multiplier FLOAT NOT NULL DEFAULT 0.0",
                "UPDATE scheduler_presets SET lapse_multiplier = 0.0 WHERE lapse_multiplier IS NULL",
            ),
            (
                "minimum_lapse_interval_days",
                "ALTER TABLE scheduler_presets ADD COLUMN minimum_lapse_interval_days INTEGER NOT NULL DEFAULT 1",
                "UPDATE scheduler_presets SET minimum_lapse_interval_days = 1 WHERE minimum_lapse_interval_days IS NULL",
            ),
            (
                "maximum_interval_days",
                "ALTER TABLE scheduler_presets ADD COLUMN maximum_interval_days INTEGER NOT NULL DEFAULT 36500",
                "UPDATE scheduler_presets SET maximum_interval_days = 36500 WHERE maximum_interval_days IS NULL",
            ),
            (
                "leech_threshold",
                "ALTER TABLE scheduler_presets ADD COLUMN leech_threshold INTEGER NOT NULL DEFAULT 8",
                "UPDATE scheduler_presets SET leech_threshold = 8 WHERE leech_threshold IS NULL",
            ),
            (
                "leech_action",
                "ALTER TABLE scheduler_presets ADD COLUMN leech_action VARCHAR(32) NOT NULL DEFAULT 'suspend'",
                "UPDATE scheduler_presets SET leech_action = 'suspend' WHERE leech_action IS NULL OR leech_action = ''",
            ),
            (
                "desired_retention",
                "ALTER TABLE scheduler_presets ADD COLUMN desired_retention FLOAT NOT NULL DEFAULT 0.9",
                "UPDATE scheduler_presets SET desired_retention = 0.9 WHERE desired_retention IS NULL",
            ),
            (
                "historical_retention",
                "ALTER TABLE scheduler_presets ADD COLUMN historical_retention FLOAT NULL",
                None,
            ),
            (
                "ignore_reviews_before",
                "ALTER TABLE scheduler_presets ADD COLUMN ignore_reviews_before DATETIME NULL",
                None,
            ),
            (
                "fsrs_reschedule_on_change",
                "ALTER TABLE scheduler_presets ADD COLUMN fsrs_reschedule_on_change BOOLEAN NOT NULL DEFAULT 0",
                "UPDATE scheduler_presets SET fsrs_reschedule_on_change = 0 WHERE fsrs_reschedule_on_change IS NULL",
            ),
            (
                "fsrs_short_term_enabled",
                "ALTER TABLE scheduler_presets ADD COLUMN fsrs_short_term_enabled BOOLEAN NOT NULL DEFAULT 0",
                "UPDATE scheduler_presets SET fsrs_short_term_enabled = 0 WHERE fsrs_short_term_enabled IS NULL",
            ),
            (
                "is_default",
                "ALTER TABLE scheduler_presets ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT 0",
                "UPDATE scheduler_presets SET is_default = 0 WHERE is_default IS NULL",
            ),
        ):
            if _ensure_column("scheduler_presets", column_name, ddl_sql) and update_sql:
                db.session.execute(sa.text(update_sql))
        _ensure_index(
            "scheduler_presets",
            "ix_scheduler_presets_user_default",
            "CREATE INDEX ix_scheduler_presets_user_default ON scheduler_presets (user_id, is_default)",
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("card_progress"):
        progress_columns = _column_names("card_progress")
        if "is_suspended" not in progress_columns:
            db.session.execute(sa.text("ALTER TABLE card_progress ADD COLUMN is_suspended BOOLEAN NOT NULL DEFAULT 0"))
            db.session.execute(
                sa.text("UPDATE card_progress SET is_suspended = 0 WHERE is_suspended IS NULL")
            )
            schema_changed = True
        _ensure_column(
            "card_progress",
            "interval_days_raw",
            "ALTER TABLE card_progress ADD COLUMN interval_days_raw FLOAT NULL",
        )
        if _ensure_column(
            "card_progress",
            "is_buried",
            "ALTER TABLE card_progress ADD COLUMN is_buried BOOLEAN NOT NULL DEFAULT 0",
        ):
            db.session.execute(sa.text("UPDATE card_progress SET is_buried = 0 WHERE is_buried IS NULL"))
        _ensure_column(
            "card_progress",
            "buried_until_day",
            "ALTER TABLE card_progress ADD COLUMN buried_until_day INTEGER NULL",
        )
        if _ensure_column(
            "card_progress",
            "review_kind",
            "ALTER TABLE card_progress ADD COLUMN review_kind VARCHAR(20) NOT NULL DEFAULT 'review'",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE card_progress SET review_kind = 'review' "
                    "WHERE review_kind IS NULL OR review_kind = ''"
                )
            )
        if _ensure_column(
            "card_progress",
            "scheduler_mode",
            "ALTER TABLE card_progress ADD COLUMN scheduler_mode VARCHAR(20) NOT NULL DEFAULT 'legacy'",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE card_progress SET scheduler_mode = 'legacy' "
                    "WHERE scheduler_mode IS NULL OR scheduler_mode = ''"
                )
            )
        _ensure_column(
            "card_progress",
            "memory_stability",
            "ALTER TABLE card_progress ADD COLUMN memory_stability FLOAT NULL",
        )
        _ensure_column(
            "card_progress",
            "memory_difficulty",
            "ALTER TABLE card_progress ADD COLUMN memory_difficulty FLOAT NULL",
        )
        _ensure_column(
            "card_progress",
            "suspension_reason",
            "ALTER TABLE card_progress ADD COLUMN suspension_reason VARCHAR(32) NULL",
        )
        _ensure_column(
            "card_progress",
            "last_leech_at",
            "ALTER TABLE card_progress ADD COLUMN last_leech_at DATETIME NULL",
        )
        if _ensure_column(
            "card_progress",
            "last_leech_lapses",
            "ALTER TABLE card_progress ADD COLUMN last_leech_lapses INTEGER NOT NULL DEFAULT 0",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE card_progress SET last_leech_lapses = 0 "
                    "WHERE last_leech_lapses IS NULL"
                )
            )
        _ensure_column(
            "card_progress",
            "last_review_event_id",
            "ALTER TABLE card_progress ADD COLUMN last_review_event_id INTEGER NULL",
        )
        db.session.execute(
            sa.text(
                "UPDATE card_progress SET interval_days_raw = interval_days "
                "WHERE interval_days_raw IS NULL AND interval_days IS NOT NULL"
            )
        )

        _ensure_index(
            "card_progress",
            "ix_card_progress_is_suspended",
            "CREATE INDEX ix_card_progress_is_suspended ON card_progress (is_suspended)",
        )
        _ensure_index(
            "card_progress",
            "ix_card_progress_is_buried",
            "CREATE INDEX ix_card_progress_is_buried ON card_progress (is_buried)",
        )
        _ensure_index(
            "card_progress",
            "ix_card_progress_buried_until_day",
            "CREATE INDEX ix_card_progress_buried_until_day ON card_progress (buried_until_day)",
        )
        _ensure_index(
            "card_progress",
            "ix_card_progress_review_kind",
            "CREATE INDEX ix_card_progress_review_kind ON card_progress (review_kind)",
        )
        _ensure_index(
            "card_progress",
            "ix_card_progress_scheduler_mode",
            "CREATE INDEX ix_card_progress_scheduler_mode ON card_progress (scheduler_mode)",
        )
        _ensure_index(
            "card_progress",
            "ix_card_progress_last_review_event_id",
            "CREATE INDEX ix_card_progress_last_review_event_id ON card_progress (last_review_event_id)",
        )
        _ensure_index(
            "card_progress",
            "ix_card_progress_user_queue_due_day",
            "CREATE INDEX ix_card_progress_user_queue_due_day ON card_progress (user_id, queue, due_day)",
        )
        _ensure_index(
            "card_progress",
            "ix_card_progress_user_queue_due_at",
            "CREATE INDEX ix_card_progress_user_queue_due_at ON card_progress (user_id, queue, due_at)",
        )
        _ensure_index(
            "card_progress",
            "ix_card_progress_user_hidden_flags",
            "CREATE INDEX ix_card_progress_user_hidden_flags ON card_progress (user_id, is_suspended, is_buried)",
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("review_events"):
        if _ensure_column(
            "review_events",
            "scheduler_preset_id",
            "ALTER TABLE review_events ADD COLUMN scheduler_preset_id INTEGER NULL",
        ):
            pass
        if _ensure_column(
            "review_events",
            "scheduler_mode",
            "ALTER TABLE review_events ADD COLUMN scheduler_mode VARCHAR(20) NOT NULL DEFAULT 'legacy'",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE review_events SET scheduler_mode = 'legacy' "
                    "WHERE scheduler_mode IS NULL OR scheduler_mode = ''"
                )
            )
        if _ensure_column(
            "review_events",
            "review_kind",
            "ALTER TABLE review_events ADD COLUMN review_kind VARCHAR(20) NOT NULL DEFAULT 'review'",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE review_events SET review_kind = 'review' "
                    "WHERE review_kind IS NULL OR review_kind = ''"
                )
            )
        _ensure_column(
            "review_events",
            "queue_before",
            "ALTER TABLE review_events ADD COLUMN queue_before VARCHAR(20) NULL",
        )
        _ensure_column(
            "review_events",
            "queue_after",
            "ALTER TABLE review_events ADD COLUMN queue_after VARCHAR(20) NULL",
        )
        _ensure_column(
            "review_events",
            "interval_days_before",
            "ALTER TABLE review_events ADD COLUMN interval_days_before FLOAT NULL",
        )
        _ensure_column(
            "review_events",
            "interval_days_after",
            "ALTER TABLE review_events ADD COLUMN interval_days_after FLOAT NULL",
        )
        _ensure_column(
            "review_events",
            "due_day_before",
            "ALTER TABLE review_events ADD COLUMN due_day_before INTEGER NULL",
        )
        _ensure_column(
            "review_events",
            "due_day_after",
            "ALTER TABLE review_events ADD COLUMN due_day_after INTEGER NULL",
        )
        _ensure_column(
            "review_events",
            "days_late",
            "ALTER TABLE review_events ADD COLUMN days_late INTEGER NULL",
        )
        _ensure_column(
            "review_events",
            "ease_factor_before",
            "ALTER TABLE review_events ADD COLUMN ease_factor_before FLOAT NULL",
        )
        _ensure_column(
            "review_events",
            "ease_factor_after",
            "ALTER TABLE review_events ADD COLUMN ease_factor_after FLOAT NULL",
        )
        _ensure_column(
            "review_events",
            "memory_stability_before",
            "ALTER TABLE review_events ADD COLUMN memory_stability_before FLOAT NULL",
        )
        _ensure_column(
            "review_events",
            "memory_stability_after",
            "ALTER TABLE review_events ADD COLUMN memory_stability_after FLOAT NULL",
        )
        _ensure_column(
            "review_events",
            "memory_difficulty_before",
            "ALTER TABLE review_events ADD COLUMN memory_difficulty_before FLOAT NULL",
        )
        _ensure_column(
            "review_events",
            "memory_difficulty_after",
            "ALTER TABLE review_events ADD COLUMN memory_difficulty_after FLOAT NULL",
        )
        if _ensure_column(
            "review_events",
            "leeched_after",
            "ALTER TABLE review_events ADD COLUMN leeched_after BOOLEAN NOT NULL DEFAULT 0",
        ):
            db.session.execute(
                sa.text("UPDATE review_events SET leeched_after = 0 WHERE leeched_after IS NULL")
            )
        if _ensure_column(
            "review_events",
            "suspended_after",
            "ALTER TABLE review_events ADD COLUMN suspended_after BOOLEAN NOT NULL DEFAULT 0",
        ):
            db.session.execute(
                sa.text("UPDATE review_events SET suspended_after = 0 WHERE suspended_after IS NULL")
            )
        if _ensure_column(
            "review_events",
            "payload_json",
            "ALTER TABLE review_events ADD COLUMN payload_json TEXT NULL",
        ):
            db.session.execute(
                sa.text(
                    "UPDATE review_events SET payload_json = '{}' "
                    "WHERE payload_json IS NULL OR payload_json = ''"
                )
            )

        _ensure_index(
            "review_events",
            "ix_review_events_scheduler_preset_id",
            "CREATE INDEX ix_review_events_scheduler_preset_id ON review_events (scheduler_preset_id)",
        )
        _ensure_index(
            "review_events",
            "ix_review_events_scheduler_mode",
            "CREATE INDEX ix_review_events_scheduler_mode ON review_events (scheduler_mode)",
        )
        _ensure_index(
            "review_events",
            "ix_review_events_review_kind",
            "CREATE INDEX ix_review_events_review_kind ON review_events (review_kind)",
        )
        _ensure_index(
            "review_events",
            "ix_review_events_user_scheduler_reviewed_at",
            "CREATE INDEX ix_review_events_user_scheduler_reviewed_at ON review_events (user_id, scheduler_mode, reviewed_at)",
        )
        _ensure_index(
            "review_events",
            "ix_review_events_user_kind_reviewed_at",
            "CREATE INDEX ix_review_events_user_kind_reviewed_at ON review_events (user_id, review_kind, reviewed_at)",
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("tts_provider_config"):
        tts_columns_meta = {column["name"]: column for column in inspector.get_columns("tts_provider_config")}
        tts_columns = set(tts_columns_meta.keys())
        if "shared_config_json" not in tts_columns:
            db.session.execute(
                sa.text("ALTER TABLE tts_provider_config ADD COLUMN shared_config_json TEXT NULL")
            )
            schema_changed = True
        if "provider_config_json" not in tts_columns:
            db.session.execute(
                sa.text("ALTER TABLE tts_provider_config ADD COLUMN provider_config_json TEXT NULL")
            )
            schema_changed = True
        if "default_settings_json" not in tts_columns:
            db.session.execute(
                sa.text("ALTER TABLE tts_provider_config ADD COLUMN default_settings_json TEXT NULL")
            )
            schema_changed = True
        if "shared_config_json" in tts_columns or schema_changed:
            db.session.execute(
                sa.text(
                    "UPDATE tts_provider_config SET shared_config_json = '{}' "
                    "WHERE shared_config_json IS NULL OR shared_config_json = ''"
                )
            )
            db.session.execute(
                sa.text(
                    "UPDATE tts_provider_config SET provider_config_json = '{}' "
                    "WHERE provider_config_json IS NULL OR provider_config_json = ''"
                )
            )
            db.session.execute(
                sa.text(
                    "UPDATE tts_provider_config SET default_settings_json = '{}' "
                    "WHERE default_settings_json IS NULL OR default_settings_json = ''"
                )
            )
        key_status_column = tts_columns_meta.get("key_status")
        if key_status_column is not None:
            key_status_default = str(key_status_column.get("default") or "").strip().strip("'")
            key_status_nullable = bool(key_status_column.get("nullable", True))
            if is_mysql and (key_status_default.lower() != "unknown" or key_status_nullable):
                db.session.execute(
                    sa.text(
                        "ALTER TABLE tts_provider_config "
                        "MODIFY COLUMN key_status VARCHAR(32) NOT NULL DEFAULT 'unknown'"
                    )
                )
                schema_changed = True
            db.session.execute(
                sa.text(
                    "UPDATE tts_provider_config SET key_status = 'unknown' "
                    "WHERE key_status IS NULL OR key_status = ''"
                )
            )

    inspector = sa.inspect(bind)
    if inspector.has_table("decks"):
        deck_columns = _column_names("decks")
        if "owner_user_id" not in deck_columns:
            db.session.execute(
                sa.text("ALTER TABLE decks ADD COLUMN owner_user_id INTEGER NULL")
            )
            deck_columns.add("owner_user_id")
            schema_changed = True
        if "note_type_id" not in deck_columns:
            db.session.execute(
                sa.text("ALTER TABLE decks ADD COLUMN note_type_id VARCHAR(36) NULL")
            )
            deck_columns.add("note_type_id")
            schema_changed = True
        if "scheduler_preset_id" not in deck_columns:
            db.session.execute(
                sa.text("ALTER TABLE decks ADD COLUMN scheduler_preset_id INTEGER NULL")
            )
            deck_columns.add("scheduler_preset_id")
            schema_changed = True
        if "deleted_at" not in deck_columns:
            db.session.execute(
                sa.text("ALTER TABLE decks ADD COLUMN deleted_at DATETIME NULL")
            )
            deck_columns.add("deleted_at")
            schema_changed = True

        deck_indexes = _index_names("decks")
        if "owner_user_id" in deck_columns and "ix_decks_owner_user_id" not in deck_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_decks_owner_user_id ON decks (owner_user_id)")
            )
            schema_changed = True
        if "note_type_id" in deck_columns and "ix_decks_note_type_id" not in deck_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_decks_note_type_id ON decks (note_type_id)")
            )
            schema_changed = True
        if "scheduler_preset_id" in deck_columns and "ix_decks_scheduler_preset_id" not in deck_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_decks_scheduler_preset_id ON decks (scheduler_preset_id)")
            )
            schema_changed = True
        if "deleted_at" in deck_columns and "ix_decks_deleted_at" not in deck_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_decks_deleted_at ON decks (deleted_at)")
            )
            schema_changed = True

    inspector = sa.inspect(bind)
    if inspector.has_table("deck_installs"):
        install_columns = {column["name"] for column in inspector.get_columns("deck_installs")}
        if "clone_mode" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN clone_mode VARCHAR(32) NULL")
            )
            install_columns.add("clone_mode")
            schema_changed = True
        if "clone_mode" in install_columns:
            missing_mode_count = db.session.execute(
                sa.text("SELECT COUNT(*) FROM deck_installs WHERE clone_mode IS NULL OR clone_mode = ''")
            ).scalar()
            if int(missing_mode_count or 0) > 0:
                db.session.execute(
                    sa.text("UPDATE deck_installs SET clone_mode = 'legacy_copy' WHERE clone_mode IS NULL OR clone_mode = ''")
                )
                schema_changed = True

        if "source_deck_id" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN source_deck_id INTEGER NULL")
            )
            install_columns.add("source_deck_id")
            schema_changed = True
        if "source_note_type_id" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN source_note_type_id VARCHAR(36) NULL")
            )
            install_columns.add("source_note_type_id")
            schema_changed = True
        if "source_owner_user_id" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN source_owner_user_id INTEGER NULL")
            )
            install_columns.add("source_owner_user_id")
            schema_changed = True
        if "base_snapshot_at" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN base_snapshot_at DATETIME NULL")
            )
            install_columns.add("base_snapshot_at")
            schema_changed = True
        if "last_synced_at" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN last_synced_at DATETIME NULL")
            )
            install_columns.add("last_synced_at")
            schema_changed = True
        if "last_sync_status" not in install_columns:
            db.session.execute(
                sa.text("ALTER TABLE deck_installs ADD COLUMN last_sync_status VARCHAR(32) NULL")
            )
            install_columns.add("last_sync_status")
            schema_changed = True

        install_indexes = {index["name"] for index in inspector.get_indexes("deck_installs")}
        if "clone_mode" in install_columns and "ix_deck_installs_clone_mode" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_clone_mode ON deck_installs (clone_mode)")
            )
            schema_changed = True
        if "source_deck_id" in install_columns and "ix_deck_installs_source_deck_id" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_source_deck_id ON deck_installs (source_deck_id)")
            )
            schema_changed = True
        if "source_note_type_id" in install_columns and "ix_deck_installs_source_note_type_id" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_source_note_type_id ON deck_installs (source_note_type_id)")
            )
            schema_changed = True
        if "source_owner_user_id" in install_columns and "ix_deck_installs_source_owner_user_id" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_source_owner_user_id ON deck_installs (source_owner_user_id)")
            )
            schema_changed = True
        if "base_snapshot_at" in install_columns and "ix_deck_installs_base_snapshot_at" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_base_snapshot_at ON deck_installs (base_snapshot_at)")
            )
            schema_changed = True
        if "last_synced_at" in install_columns and "ix_deck_installs_last_synced_at" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_last_synced_at ON deck_installs (last_synced_at)")
            )
            schema_changed = True
        if "last_sync_status" in install_columns and "ix_deck_installs_last_sync_status" not in install_indexes:
            db.session.execute(
                sa.text("CREATE INDEX ix_deck_installs_last_sync_status ON deck_installs (last_sync_status)")
            )
            schema_changed = True

    table_names = inspector.get_table_names()
    if "oauth_clients" not in table_names:
        from models.oauth_client import OAuthClient

        OAuthClient.__table__.create(bind=db.engine, checkfirst=True)
        schema_changed = True
    else:
        try:
            if db.engine.dialect.name == "mysql":
                db.session.execute(sa.text("ALTER TABLE oauth_clients MODIFY COLUMN client_secret_hash VARCHAR(255) NULL"))
                schema_changed = True
        except Exception:
            pass


    if "oauth_authorization_codes" not in table_names:
        from models.oauth_authorization_code import OAuthAuthorizationCode

        OAuthAuthorizationCode.__table__.create(bind=db.engine, checkfirst=True)
        schema_changed = True

    if "mcp_access_tokens" in table_names:
        _ensure_column(
            "mcp_access_tokens",
            "name",
            "ALTER TABLE mcp_access_tokens ADD COLUMN name VARCHAR(120) NULL DEFAULT 'MCP Token'",
        )
        _ensure_column(
            "mcp_access_tokens",
            "client_id",
            "ALTER TABLE mcp_access_tokens ADD COLUMN client_id INT NULL",
        )
        _ensure_column(
            "mcp_access_tokens",
            "refresh_token_hash",
            "ALTER TABLE mcp_access_tokens ADD COLUMN refresh_token_hash VARCHAR(64) NULL",
        )
        _ensure_column(
            "mcp_access_tokens",
            "refresh_token_expires_at",
            "ALTER TABLE mcp_access_tokens ADD COLUMN refresh_token_expires_at DATETIME NULL",
        )

    if "shared_image_assets" in table_names:
        _ensure_column(
            "shared_image_assets",
            "source_url",
            "ALTER TABLE shared_image_assets ADD COLUMN source_url VARCHAR(2048) NULL",
        )
        tags_ddl = (
            "ALTER TABLE shared_image_assets ADD COLUMN tags JSON NULL"
            if is_mysql
            else "ALTER TABLE shared_image_assets ADD COLUMN tags JSON DEFAULT '[]'"
        )
        if _ensure_column("shared_image_assets", "tags", tags_ddl):
            db.session.execute(
                sa.text(
                    "UPDATE shared_image_assets SET tags = '[]' WHERE tags IS NULL"
                )
            )
            schema_changed = True

    if "users" in table_names:
        added_verified = _ensure_column(
            "users",
            "email_verified_at",
            "ALTER TABLE users ADD COLUMN email_verified_at DATETIME NULL",
        )
        added_source = _ensure_column(
            "users",
            "email_verification_source",
            "ALTER TABLE users ADD COLUMN email_verification_source VARCHAR(32) NULL",
        )
        if added_verified or added_source:
            db.session.execute(
                sa.text(
                    "UPDATE users SET "
                    "email_verified_at = COALESCE(created_at, CURRENT_TIMESTAMP), "
                    "email_verification_source = 'legacy' "
                    "WHERE email_verified_at IS NULL"
                )
            )
            schema_changed = True

    if "email_verification_tokens" not in table_names:
        from models.email_verification_token import EmailVerificationToken

        EmailVerificationToken.__table__.create(bind=db.engine, checkfirst=True)
        schema_changed = True

    if "deck_marketplace_items" in table_names:
        _ensure_column(
            "deck_marketplace_items",
            "student_offer_mode",
            "ALTER TABLE deck_marketplace_items ADD COLUMN student_offer_mode VARCHAR(32) NOT NULL DEFAULT 'none'",
        )
        _ensure_column(
            "deck_marketplace_items",
            "student_discount_percent",
            "ALTER TABLE deck_marketplace_items ADD COLUMN student_discount_percent INT NULL",
        )
        _ensure_column(
            "deck_marketplace_items",
            "auto_publish_enabled",
            "ALTER TABLE deck_marketplace_items ADD COLUMN auto_publish_enabled BOOLEAN NOT NULL DEFAULT 0",
        )
        _ensure_column(
            "deck_marketplace_items",
            "last_auto_published_at",
            "ALTER TABLE deck_marketplace_items ADD COLUMN last_auto_published_at DATETIME NULL",
        )
        _ensure_column(
            "deck_marketplace_items",
            "distribution_mode",
            "ALTER TABLE deck_marketplace_items ADD COLUMN distribution_mode VARCHAR(32) NOT NULL DEFAULT 'free'",
        )
        _ensure_column(
            "deck_marketplace_items",
            "course_title",
            "ALTER TABLE deck_marketplace_items ADD COLUMN course_title VARCHAR(255) NULL",
        )
        _ensure_column(
            "deck_marketplace_items",
            "course_description",
            "ALTER TABLE deck_marketplace_items ADD COLUMN course_description TEXT NULL",
        )
        _ensure_column(
            "deck_marketplace_items",
            "course_url",
            "ALTER TABLE deck_marketplace_items ADD COLUMN course_url VARCHAR(500) NULL",
        )
        _ensure_column(
            "deck_marketplace_items",
            "course_instructions",
            "ALTER TABLE deck_marketplace_items ADD COLUMN course_instructions TEXT NULL",
        )
        _ensure_column(
            "deck_marketplace_items",
            "last_auto_publish_error",
            "ALTER TABLE deck_marketplace_items ADD COLUMN last_auto_publish_error TEXT NULL",
        )

    if "deck_installs" in table_names:
        _ensure_column(
            "deck_installs",
            "auto_update_enabled",
            "ALTER TABLE deck_installs ADD COLUMN auto_update_enabled BOOLEAN NOT NULL DEFAULT 0",
        )
        _ensure_column(
            "deck_installs",
            "sync_mode",
            "ALTER TABLE deck_installs ADD COLUMN sync_mode VARCHAR(32) NOT NULL DEFAULT 'manual'",
        )
        _ensure_column(
            "deck_installs",
            "last_auto_updated_at",
            "ALTER TABLE deck_installs ADD COLUMN last_auto_updated_at DATETIME NULL",
        )
        _ensure_column(
            "deck_installs",
            "pending_conflict_count",
            "ALTER TABLE deck_installs ADD COLUMN pending_conflict_count INT NOT NULL DEFAULT 0",
        )

    if "deck_install_rebases" in table_names:
        _ensure_column(
            "deck_install_rebases",
            "mode",
            "ALTER TABLE deck_install_rebases ADD COLUMN mode VARCHAR(32) NOT NULL DEFAULT 'manual'",
        )

    if "deck_releases" in table_names:
        _ensure_column(
            "deck_releases",
            "publish_mode",
            "ALTER TABLE deck_releases ADD COLUMN publish_mode VARCHAR(32) NOT NULL DEFAULT 'manual'",
        )

    if schema_changed:
        db.session.commit()


