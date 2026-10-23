# Flama Database Migration & Schema Evolution Playbook

This playbook defines the standard practices for designing, validating, and executing safe, zero-downtime, zero-data-loss schema migrations in Flama's MySQL / SQLAlchemy / Flask-Migrate environment.

---

## 1. The 5-Phase Zero-Downtime Migration Pattern

When executing non-trivial schema refactors (e.g., column renames, type conversions, table splits, JSON structure changes), never execute a destructive one-step migration. Follow the 5-phase pattern:

```
Phase 1: EXPAND
├── Add new nullable columns or new tables via Alembic migration.
└── Deploy code that writes to BOTH old and new formats (dual-write).
      │
Phase 2: BACKFILL
├── Run idempotent CLI / background job to backfill legacy rows.
└── Verify 100% data consistency between old and new stores.
      │
Phase 3: DUAL-READ & VALIDATE
├── Deploy code that reads from the new store with fallback to old.
└── Verify performance, correctness, and absence of errors.
      │
Phase 4: CUTOVER
├── Switch primary reads and writes completely to the new store.
└── Stop reading/writing to the legacy columns/tables.
      │
Phase 5: CONTRACT
├── Drop legacy columns / deprecated tables in a subsequent migration.
└── Clean up compatibility translation code and legacy fallbacks.
```

---

## 2. Safe MySQL DDL Rules in Alembic

When writing migrations in `migrations/versions/*.py`:

### Adding Columns
- **Rule**: Always add new columns as `nullable=True` or with a server default.
- **MySQL Pitfall**: Adding a `nullable=False` column without a default will fail immediately on existing tables with data.

```python
# GOOD: Safe nullable addition with index
op.add_column(
    "card_progress",
    sa.Column("memory_stability", sa.Float(), nullable=True),
)
op.create_index(
    "ix_card_progress_user_stability",
    "card_progress",
    ["user_id", "memory_stability"],
)
```

### Adding Foreign Keys & Constraints
- **Rule**: Always name foreign keys and unique constraints explicitly.
- **MySQL Pitfall**: Unnamed constraints generate auto-generated database names that vary across environments and break `op.drop_constraint`.

```python
# GOOD: Explicitly named foreign key and unique constraint
op.create_foreign_key(
    "fk_deck_installs_applied_release",
    "deck_installs",
    "deck_releases",
    ["applied_release_id"],
    ["id"],
    ondelete="SET NULL",
)
op.create_unique_constraint(
    "uq_card_progress_user_card",
    "card_progress",
    ["user_id", "card_id"],
)
```

### Modifying Column Types or Renaming Columns
- **Rule**: Never use `op.alter_column(..., new_column_name=...)` on live tables with active traffic.
- **Approach**: Add the new column (Expand), backfill data, switch application models, then drop the old column in a later release.

---

## 3. Data Backfill & Migration Scripting

For large table updates (such as `notes`, `cards`, `card_progress`, or `review_events`), avoid running monolithic `UPDATE` statements inside Alembic DDL migrations. Monolithic updates hold row locks, bloat undo logs, and risk locking timeouts.

### Recommended Backfill Pattern
Create an idempotent CLI command in `app/cli.py` that processes rows in batches:

```python
def backfill_field_def_ids_in_notes(batch_size: int = 500) -> int:
    """Migrate Note.field_values from name-keyed to ID-keyed dicts."""
    total_migrated = 0
    while True:
        # Fetch a bounded batch of unmigrated notes
        notes = (
            Note.query.filter(Note.is_migrated == False)
            .limit(batch_size)
            .all()
        )
        if not notes:
            break

        for note in notes:
            # Transform note.field_values ...
            note.is_migrated = True

        db.session.commit()
        total_migrated += len(notes)

    return total_migrated
```

---

## 4. Rollback and Compatibility Gating

Every design and migration plan must document an explicit **Rollback Strategy**:

1. **Schema Rollback**: Every Alembic `upgrade()` function must have a corresponding, fully tested `downgrade()` function.
2. **Feature Flags / Compatibility Gating**: Use application settings in `app/settings.py` to gate new schema read paths (e.g., `ENABLE_ID_KEYED_NOTE_VALUES = True/False`).
3. **Data Loss Prevention**: Never delete or overwrite legacy data columns until the new system has run successfully in production and been verified.

---

## 5. Migration Review Checklist

Before approving any database migration or schema refactoring design:

- [ ] **Alembic Reversible**: Does `downgrade()` cleanly revert all DDL changes?
- [ ] **Non-Blocking DDL**: Are new columns nullable or equipped with server defaults?
- [ ] **Explicit Constraint Names**: Do all `ForeignKeyConstraint`, `UniqueConstraint`, and `Index` definitions have explicit names?
- [ ] **Dual-Engine Compatibility**: Does the migration execute cleanly in both MySQL 8.0 (production) and SQLite (in-memory unit tests)?
- [ ] **Locking & Transaction Impact**: Are heavy data transforms decoupled from the DDL migration into a batched background/CLI task?
- [ ] **No Data Loss**: Is legacy data preserved during intermediate dual-write phases?
- [ ] **Model Synchronization**: Are ORM classes in `models/` updated to match the final migration schema?
