# Production Architecture Verification & Baseline Snapshot — 2026-08-29

> **Task Reference**: [P0-03 — MySQL baseline verification and drift snapshot](../task/decoupling/P0-03_MYSQL_BASELINE_VERIFICATION.md)
> **Status**: **SUPERSEDED / NOT APPROVED — Independent review round 5**
> **Schema Version**: `study-architecture-audit.v3`
> **Alembic Revision**: `20260902_000031`
> **MySQL Engine Version**: `8.0.40` (InnoDB UTF8mb4)
> **App Commit**: `a1d904d38f28a7596e65deaae3f5fe871f762e9f` (+ working-tree decoupling audit bundle)
> **Observed Timestamp**: `2026-08-29T05:09:22 UTC` (Run 1) / `2026-08-29T05:09:32 UTC` (Run 2)
> **Principal Identity**: SELECT-only (`flama_audit_ro`@`localhost`, rotated credentials)
> **Historical Audit CLI Exit Code**: `1` (`WARN` — 0 BLOCK, 5 WARN / 5 Non-pass Inventory Items)
> **Phase 0 Gate Readiness**: **NO-GO — P0-02 is `COMPLETED`; P0-03 remains `BLOCKED` pending a SELECT-only rerun**

## Independent review round 5 supersession notice

This report preserves a valid two-run snapshot of the pre-final audit code, but it is not the current Phase 0 approval bundle. The authoritative task verdict is [P0_PHASE_REVIEW_HANDOFF_2026-08-29.md](../task/decoupling/P0_PHASE_REVIEW_HANDOFF_2026-08-29.md).

- Stored artifacts contain `67` categories, `11/11` valid formulas and `62 PASS / 5 WARN / 0 BLOCK`.
- Canonical audit rerun on current code/MySQL contains `67` categories, `11/11` valid formulas and `61 PASS / 6 WARN / 0 BLOCK` because tightened provenance classification now reports `unknown_provenance_events=35`.
- The audit service was modified after the stored runs. The current exact dirty state is now identified by `artifacts/study_architecture_audit_code_manifest_2026-08-29.json`, but the stored runs still predate that state.
- P0-02 fixed the session-policy false negative and passed strict canonical digest/schema negative coverage.
- P0-01 and P0-04 passed independent review; they do not make this stale P0-03 bundle current.
- SELECT-only grants were independently confirmed. Credential rotation remains an external operational assertion and no secret is included in this report.

---

## 1. Historical Scope, Environment Metadata & Safety Verification

### 1.1 Environment & Execution Metadata
| Key | Captured Value | Verification Notes |
|---|---|---|
| **Environment Name** | Local MySQL Development / Staging Baseline | Host: `localhost:3306`, Database: `nihongo` |
| **App Git Commit** | `a1d904d38f28a7596e65deaae3f5fe871f762e9f` | Base commit via `git rev-parse HEAD` |
| **Alembic Head** | `20260902_000031` | Verified via `alembic_version` table |
| **Database Server** | MySQL `8.0.40` (InnoDB UTF8mb4) | Query: `SELECT VERSION()` |
| **Audit Schema** | `study-architecture-audit.v3` | Migration-grade machine-readable schema |
| **Observed At** | `2026-08-29T05:09:22 UTC` (Run 1) / `2026-08-29T05:09:32 UTC` (Run 2) | Deterministic timestamp snapshots |
| **Two-Run Determinism** | `True` (100% identical payloads, 0 diffs excluding timestamp) | Comparison artifact saved to `docs/architecture/artifacts/study_architecture_audit_determinism_comparison_2026-08-29.json` |
| **Execution Entrypoint** | Dedicated `wsgi_audit.py` | Maintenance-disabled factory (`create_audit_app`) |

### 1.2 Redacted SELECT-Only Principal Grant Proof
The audit execution was executed strictly under a dedicated, unprivileged read-only database principal (`flama_audit_ro`@`localhost`) with freshly rotated credentials.

```sql
-- Query: SHOW GRANTS FOR 'flama_audit_ro'@'localhost';
GRANT USAGE ON *.* TO `flama_audit_ro`@`localhost`;
GRANT SELECT ON `nihongo`.* TO `flama_audit_ro`@`localhost`;
```

### 1.3 Read-Only Invariant Enforcement
- Executed strictly via read-only queries in `app.services.study_architecture_audit_service`.
- The dedicated audit execution enforced complete bypass of startup maintenance mutators (`STARTUP_RUN_MAINTENANCE=False`, `STARTUP_RUN_DB_CREATE_ALL=False`, `STARTUP_RUN_USER_MANAGEMENT_SCHEMA=False`, `STARTUP_RUN_BACKWARD_COMPAT_SCHEMA=False`, `STARTUP_RUN_DEFAULT_USER_ROLE_SEED=False`, `STARTUP_RUN_DEFAULT_TAXONOMY_SEED=False`, `STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED=False`, `STARTUP_RUN_CLONE_CUTOVER=False`).
- Zero DDL or DML write operations were executed against the database.
- The report output contains zero passwords, secrets, user answer text, or private learner PII.

---

## 2. Historical Executive Verification Summary

The PASS cells below describe the stored Round 4 snapshot and are superseded as Phase 0 approval evidence.

| Dimension | Verification Finding | Verdict |
|---|---|---|
| **Alembic & Schema State** | Migration head `20260902_000031` intact; models registered cleanly | **PASS** |
| **Startup Safety (`P0-01`)** | Dedicated `wsgi_audit.py` entrypoint and `create_audit_app()` factory enforce fail-closed maintenance bypass | **PASS** |
| **Audit Coverage (`P0-02`)** | 67 exhaustive inventory categories, 11 disjoint reconciliation equality checks 100% valid | **PASS** |
| **Two-Run Determinism (`P0-03`)** | Run 1 and Run 2 yield byte-for-byte identical output excluding declared `observed_at` | **PASS** |
| **Behavior Acceptance (`P0-04`)** | Cross-entrypoint golden vectors, multi-timezone 4 AM boundaries, and batch rollback verified | **PASS** |
| **Overlay Invariant** | Shared decks use pointer overlay (`logical_overlay`); source notes are never copied or mutated | **PASS** |

---

## 3. Stored Audit Gate Metrics & Disposition Inventory (`v3`)

### 3.1 Entity Accounting Summary
| Entity | Monitored Table | Captured Count | State / Authority |
|---|---|---:|---|
| **NoteTypes** | `note_types` | `9` | Structural templates valid |
| **Templates** | `templates` | `18` | Render contracts defined |
| **Notes** | `notes` | `21,822` | Content source of truth |
| **Cards** | `cards` | `21,822` | Generated study targets |
| **CardProgress** | `card_progress` | `11,247` | **Sole progress authority** (0 nulls, 0 orphans, 0 divergent fan-ins) |
| **ReviewEvents** | `review_events` | `61,806` | Historical provenance tracked (61,645 Anki import + 126 session + 35 direct) |
| **StudySessions** | `study_sessions` | `34` | Leases bounded (16 committed, 18 expired open, 0 active) |
| **DeckInstalls** | `deck_installs` | `3` | Overlay pointer mode (`logical_overlay`) |

### 3.2 Complete 67-Category Inventory & Disposition Matrix
| # | Category | Gate Group | Count | Severity | Bounded Sample IDs | Disposition Strategy | Target Resolution / Description |
|---|---|---|---:|---|---|---|---|
| 1 | `note_types_without_templates` | template | 0 | **PASS** | `[]` | `investigate_empty_notetypes` | NoteTypes without any Template definitions. |
| 2 | `note_types_with_single_template` | template | 7 | **PASS** | `["1fbae49e-...", "2b170bed-..."]` | `valid_single_template` | NoteTypes with exactly one Template definition. |
| 3 | `note_types_with_multiple_templates` | template | 2 | **PASS** | `["4525f529-...", "48dc0b44-..."]` | `valid_multi_template` | NoteTypes with multiple Templates (valid multi-card design). |
| 4 | `note_types_with_zero_defaults` | template | 0 | **PASS** | `[]` | `investigate_missing_default_template` | NoteTypes with templates but zero default templates designated. |
| 5 | `note_types_with_single_default` | template | 9 | **PASS** | `["1fbae49e-...", "2b170bed-..."]` | `valid_single_default_template` | NoteTypes with exactly one default Template designated. |
| 6 | `note_types_with_multiple_defaults` | template | 0 | **PASS** | `[]` | `reconcile_multiple_default_templates` | NoteTypes with more than one default Template designated. |
| 7 | `default_count_anomalies` | template | 0 | **PASS** | `[]` | `reconcile_default_templates` | NoteTypes with default template count not equal to 1. |
| 8 | `duplicate_name_groups` | template | 0 | **PASS** | `[]` | `review_duplicate_names` | Template name collisions within the same NoteType. |
| 9 | `duplicate_position_groups` | template | 1 | **WARN** | `["notetype:4525f529-f5d5-4c58-9b..."]` | `review_duplicate_positions` | Template position collisions within the same NoteType. (**Task P1-01**) |
| 10 | `cross_note_type_cards` | template | 0 | **PASS** | `[]` | `quarantine_cross_notetype_cards` | Cards referencing a Template from a different NoteType than their Note. |
| 11 | `notes_without_cards` | card | 0 | **PASS** | `[]` | `review_orphan_notes` | Notes without any generated Cards. |
| 12 | `notes_with_single_card` | card | 21,822 | **PASS** | `["00008792-...", "0000f66b-..."]` | `valid_single_card_notes` | Notes with exactly one generated Card. |
| 13 | `notes_with_multiple_cards` | card | 0 | **PASS** | `[]` | `valid_multi_card_notes` | Notes with multiple Cards generated across Templates. |
| 14 | `orphan_cards` | card | 0 | **PASS** | `[]` | `quarantine_orphan_cards` | Cards referencing missing Note or missing Template records. |
| 15 | `null_card_id_rows` | progress | 0 | **PASS** | `[]` | `quarantine_null_card_progress` | CardProgress records with NULL card_id. |
| 16 | `orphan_card_id_rows` | progress | 0 | **PASS** | `[]` | `quarantine_orphan_card_progress` | CardProgress records referencing deleted or non-existent Cards. |
| 17 | `orphan_note_id_rows` | progress | 0 | **PASS** | `[]` | `quarantine_orphan_note_progress` | CardProgress records whose Card references a missing or deleted Note. |
| 18 | `unresolvable_progress_subjects` | progress | 0 | **PASS** | `[]` | `quarantine_unresolvable_progress_subjects` | CardProgress rows with unresolvable subject. |
| 19 | `single_card_progress_groups` | progress | 11,247 | **PASS** | `["user:1/note:00008792-...", ...]` | `single_card_progress` | Learner-Note pairs with exactly one CardProgress record. |
| 20 | `learner_note_fan_in_groups` | progress | 0 | **PASS** | `[]` | `learner_note_fan_in` | Learner-Note pairs with multiple CardProgress records. |
| 21 | `equivalent_fan_in_groups` | progress | 0 | **PASS** | `[]` | `equivalent_fan_in` | Learner-Note fan-in groups sharing equivalent scheduler state. |
| 22 | `divergent_fan_in_groups` | progress | 0 | **PASS** | `[]` | `quarantine_divergent_progress_fan_in` | Learner-Note fan-in groups with conflicting scheduler states. |
| 23 | `learner_note_history_fan_in_groups` | progress | 0 | **PASS** | `[]` | `review_history_fan_in` | Learner-Note pairs with review history across multiple Cards. |
| 24 | `fsrs_rows` | progress | 0 | **PASS** | `[]` | `fsrs_progress_state` | CardProgress rows configured with FSRS scheduler mode. |
| 25 | `partial_fsrs_state_rows` | progress | 0 | **PASS** | `[]` | `reconcile_fsrs_memory_state` | CardProgress rows with incomplete FSRS stability/difficulty fields. |
| 26 | `zero_revision_rows` | revision | 0 | **PASS** | `[]` | `initial_revision_state` | CardProgress rows at baseline initial revision zero. |
| 27 | `active_revision_rows` | revision | 11,247 | **PASS** | `[16, 57, 75, 76, 77, 78, 79, 80, 81, 82]` | `active_revision_state` | CardProgress rows with incremented active revisions. |
| 28 | `invalid_revision_rows` | revision | 0 | **PASS** | `[]` | `quarantine_invalid_revisions` | CardProgress rows with NULL or negative revision counters. |
| 29 | `open_session_stale_revisions` | revision | 751 | **WARN** | `[249, 619, 620, 621, 622, 623, 624, 625, ...]` | `flag_session_revision_drift` | StudySessionCards in open sessions whose base revision drifted. (**P1-02 / P2-02**) |
| 30 | `registered_algorithm_count` | algorithm | 1 | **PASS** | `[]` | `active_registered_executables` | Executable Study Algorithm adapters in memory registry (`legacy-anki@1.0.0`). |
| 31 | `registered_algorithm_events` | algorithm | 126 | **PASS** | `[135, 136, 137, 138, 139, 140, 141, 142, ...]` | `active_registered_algorithm_events` | ReviewEvents matching registered executable algorithms. |
| 32 | `historical_imported_algorithm_events` | algorithm | 61,645 | **PASS** | `[623, 624, 625, 626, 627, 628, 629, 630, ...]` | `historical_imported_algorithm` | Historical Anki imported revlog events partitioned into clean pass status. |
| 33 | `unregistered_native_algorithm_events` | algorithm | 0 | **PASS** | `[]` | `classify_unregistered_algorithm` | Native review events referencing unregistered algorithm keys. |
| 34 | `missing_algorithm_version_events` | algorithm | 0 | **PASS** | `[]` | `classify_missing_algorithm_version` | Native review events with scheduler_algorithm but missing version. |
| 35 | `unprovenanced_fsrs_rows` | algorithm | 0 | **PASS** | `[]` | `verify_fsrs_provenance` | CardProgress rows marked FSRS without FSRS review history. |
| 36 | `orphan_card_id_events` | review_event | 40 | **WARN** | `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]` | `retain_detached_review_events` | ReviewEvents referencing detached/deleted Cards. (**Task P1-03**) |
| 37 | `attached_review_events` | review_event | 61,766 | **PASS** | `[]` | `attached_review_events` | ReviewEvents referencing existing Cards. |
| 38 | `null_session_id_events` | review_event | 61,680 | **PASS** | `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]` | `legacy_or_direct_reviews` | ReviewEvents without session ID (Anki import / direct reviews). |
| 39 | `null_algorithm_events` | review_event | 35 | **WARN** | `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]` | `classify_unversioned_algorithm` | ReviewEvents with NULL scheduler_algorithm. (**Task P1-04**) |
| 40 | `duplicate_client_event_id_groups` | review_event | 0 | **PASS** | `[]` | `quarantine_duplicate_client_events` | ReviewEvents with duplicate client_event_id for the same user. |
| 41 | `duplicate_session_sequence_groups` | review_event | 0 | **PASS** | `[]` | `quarantine_duplicate_session_sequences` | ReviewEvents with colliding sequence_no in session. |
| 42 | `missing_session_sequence_events` | review_event | 0 | **PASS** | `[]` | `review_session_events_missing_sequence` | ReviewEvents in session lacking sequence_no. |
| 43 | `anki_import_events` | review_event | 61,645 | **PASS** | `[623, 624, 625, 626, 627, 628, 629, 630, ...]` | `anki_import_reviews` | ReviewEvents imported from Anki revlogs. |
| 44 | `native_session_events` | review_event | 126 | **PASS** | `[135, 136, 137, 138, 139, 140, 141, 142, ...]` | `native_session_reviews` | ReviewEvents completed in native frontend study sessions. |
| 45 | `native_direct_events` | review_event | 35 | **PASS** | `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]` | `native_direct_reviews` | ReviewEvents executed directly outside sessions. |
| 46 | `native_mcp_events` | review_event | 0 | **PASS** | `[]` | `native_mcp_reviews` | ReviewEvents initiated via Flama MCP connect tools. |
| 47 | `native_batch_events` | review_event | 0 | **PASS** | `[]` | `native_batch_reviews` | ReviewEvents processed in bulk batch review operations. |
| 48 | `conflicting_provenance_events` | review_event | 0 | **PASS** | `[]` | `quarantine_conflicting_provenance` | ReviewEvents with mutually contradictory provenance signals. |
| 49 | `unknown_provenance_events` | review_event | 0 | **PASS** | `[]` | `needs_verification_provenance` | ReviewEvents with unclassifiable provenance markers. |
| 50 | `open_sessions` | session | 18 | **PASS** | `[]` | `total_open_sessions` | Total study sessions in open status. |
| 51 | `active_open_sessions` | session | 0 | **PASS** | `[]` | `active_open_sessions` | StudySession records open and currently active within lease. |
| 52 | `expired_open_sessions` | session | 18 | **WARN** | `["10dbb26e-...", "20b37a1f-..."]` | `expire_stale_sessions` | StudySession records open past expiration. (**P2-02 / P3-04**) |
| 53 | `committed_sessions` | session | 16 | **PASS** | `[]` | `committed_sessions` | StudySession records successfully committed. |
| 54 | `cancelled_sessions` | session | 0 | **PASS** | `[]` | `cancelled_sessions` | StudySession records explicitly cancelled. |
| 55 | `abandoned_sessions` | session | 0 | **PASS** | `[]` | `abandoned_sessions` | StudySession records explicitly marked abandoned. |
| 56 | `unknown_status_sessions` | session | 0 | **PASS** | `[]` | `quarantine_unknown_session_status` | StudySession records with unrecognized lifecycle status. |
| 57 | `missing_snapshot_sessions` | session | 0 | **PASS** | `[]` | `reconstruct_session_snapshot` | StudySession records missing snapshot_hash or metadata. |
| 58 | `invalid_config_snapshot_sessions` | session | 0 | **PASS** | `[]` | `repair_invalid_config_snapshot` | StudySession records containing malformed config_snapshot_json. |
| 59 | `active_session_unavailable_algorithm_sessions` | session | 0 | **PASS** | `[]` | `quarantine_unavailable_session_algorithm` | Active open sessions referencing unregistered scheduler algorithms. |
| 60 | `historical_session_retired_algorithm_sessions` | session | 0 | **PASS** | `[]` | `historical_session_retired_algorithm` | Historical sessions with retired algorithm implementations. |
| 61 | `deck_installs` | clone_overlay | 3 | **PASS** | `[]` | `installed_shared_decks` | Active DeckInstall pointer overlay records. |
| 62 | `installed_notetypes` | clone_overlay | 3 | **PASS** | `[]` | `installed_note_types` | Active NoteTypeInstall records referencing marketplace note types. |
| 63 | `installed_deck_cards` | clone_overlay | 39 | **PASS** | `["011efc28-...", "043ce685-..."]` | `installed_source_cards` | Cards referenced via shared deck installation overlays. |
| 64 | `local_clone_added_cards` | clone_overlay | 0 | **PASS** | `[]` | `local_clone_added_cards` | Cards generated from notes locally added to installed decks. |
| 65 | `local_authored_cards` | clone_overlay | 21,783 | **PASS** | `["00048829-...", "00057b5d-..."]` | `local_authored_cards` | Cards belonging to native local author decks. |
| 66 | `unassigned_deck_cards` | clone_overlay | 0 | **PASS** | `[]` | `unassigned_deck_cards` | Cards belonging to notes without an explicit deck assignment. |
| 67 | `overlay_ambiguities` | clone_overlay | 0 | **PASS** | `[]` | `investigate_overlay_ambiguities` | DeckCloneAddedNote records with ambiguous note associations. |

---

### 3.3 Non-Pass Anomaly, Owner Assignment & Overlap Accounting

| Severity | Anomaly / Category | Count | Sample IDs (bounded) | Overlap / Root Cause | Assigned Task | Assigned Lane / Owner |
|---|---|---:|---|---|---|---|
| **BLOCK** | *None* | 0 | — | — | — | — |
| **WARN** | `duplicate_position_groups` | 1 | `notetype:4525f529-f5d5-4c58-9bb3-b191e318fd28/pos:0` | NoteType has 9 templates with position=0 | **P1-01** | Backend / Review Core |
| **WARN** | `open_session_stale_revisions` | 751 | `[249, 619, 620, 621, 622, 623, 624, 625, 626, 627]` | Stale base revisions in uncommitted historical sessions | **P1-02 / P2-02** | Backend & Frontend Study Session |
| **WARN** | `orphan_card_id_events` | 40 | `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]` | Historical review events retained after card deletion | **P1-03** | Operations / Analytics Data |
| **WARN** | `null_algorithm_events` | 35 | `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]` | Early native direct reviews with NULL scheduler_algorithm | **P1-04** | Backend / Scheduler Engine |
| **WARN** | `expired_open_sessions` | 18 | `["10dbb26e-74b7-4050-9b95-d6551b30ace4", ...]` | Open sessions whose lease expired prior to commit | **P2-02 / P3-04** | Backend & Frontend Study Session |

---

### 3.4 Algorithm Provenance & Distribution Summary
| Scheduler Mode | Algorithm Key | Algorithm Version | Provenance Category | Event Count | Percentage |
|---|---|---|---|---:|---:|
| `anki` | `anki` | `revlog-v1` | **import** (Yomitan / Anki Connect bridge) | `61,645` | 99.74% |
| `legacy` | `legacy-anki` | `1.0.0` | **native** (Native Flama Study Engine) | `126` | 0.20% |
| `legacy` | `NULL` | `NULL` | **native** (Early Native Direct Reviews) | `35` | 0.06% |
| **Total** | | | | **61,806** | **100.00%** |

---

### 3.5 Exhaustive Disjoint Reconciliation Formulas (11/11 Validated)

| # | Formula Name | Formula Definition | Evaluated Math | Status |
|---|---|---|---|---|
| 1 | `card_progress_accounting` | $\text{single\_card\_rows} + \text{fan\_in\_rows} + \text{unresolvable} == \text{total\_cp}$ | $11247 + 0 + 0 == 11247$ | **VALID** |
| 2 | `card_progress_fan_in_consistency` | $\text{equivalent\_fan\_in} + \text{divergent\_fan\_in} == \text{fan\_in\_groups}$ | $0 + 0 == 0$ | **VALID** |
| 3 | `card_progress_revision_accounting` | $\text{zero\_rev\_rows} + \text{active\_rev\_rows} + \text{invalid\_rev\_rows} == \text{total\_cp}$ | $0 + 11247 + 0 == 11247$ | **VALID** |
| 4 | `review_events_attached_accounting` | $\text{attached\_events} + \text{orphan\_events} == \text{total\_events}$ | $61766 + 40 == 61806$ | **VALID** |
| 5 | `review_events_provenance_accounting` | $\text{anki\_import} + \text{session} + \text{mcp} + \text{batch} + \text{direct} + \text{conflict} + \text{unknown} == \text{total}$ | $61645 + 126 + 0 + 0 + 35 + 0 + 0 == 61806$ | **VALID** |
| 6 | `review_events_algorithm_accounting` | $\text{registered} + \text{historical\_import} + \text{unregistered\_native} + \text{missing\_version} + \text{null\_algo} == \text{total}$ | $126 + 61645 + 0 + 0 + 35 == 61806$ | **VALID** |
| 7 | `study_sessions_status_accounting` | $\text{open} + \text{committed} + \text{cancelled} + \text{abandoned} + \text{unknown} == \text{total\_sessions}$ | $18 + 16 + 0 + 0 + 0 == 34$ | **VALID** |
| 8 | `study_sessions_open_accounting` | $\text{active\_open\_sessions} + \text{expired\_open\_sessions} == \text{open\_sessions}$ | $0 + 18 == 18$ | **VALID** |
| 9 | `note_types_template_accounting` | $\text{no\_template} + \text{single\_default} + \text{multi\_default} + \text{zero\_default} == \text{total\_nt}$ | $0 + 9 + 0 + 0 == 9$ | **VALID** |
| 10 | `cards_clone_overlay_accounting` | $\text{installed\_cards} + \text{clone\_added\_cards} + \text{local\_cards} + \text{unassigned} + \text{orphan} == \text{total}$ | $39 + 0 + 21783 + 0 + 0 == 21822$ | **VALID** |
| 11 | `inventory_verdict_accounting` | $\text{len}(\{i \in \text{inventory} \mid i.\text{severity} \neq \text{'pass'}\}) == \text{len}(\text{verdicts.warn}) + \text{len}(\text{verdicts.block})$ | $5 == 5 + 0$ | **VALID** |

---

## 4. Drift Analysis (vs Prior Baselines)

1. **Alembic Head Progression**:
   - Maintained stably at target head `20260902_000031`.
2. **Audit Capability & Inventory Evolution**:
   - Expanded from preliminary 35 categories to **67 migration-grade categories** and **11 exhaustive reconciliation formula checks**.
   - Historical Anki revlog imported events (61,645 rows) are partitioned cleanly into `historical_imported_algorithm_events` (`severity: pass`), eliminating historical false warnings and double-counting anomalies.
3. **Dedicated Entrypoint & Principal Security**:
   - Executed strictly via dedicated `wsgi_audit.py` with maintenance-disabled factory `create_audit_app()`.
   - Principal credentials rotated; SELECT-only grant proof verified.
4. **Determinism Verification**:
   - Consecutive audit executions (Run 1 and Run 2) produce 100% byte-for-byte identical payloads (0 differences excluding timestamp), saved in machine-readable comparison artifact.

---

## 5. Redacted Audit Artifacts & Checksums

The audit artifacts generated from the verified MySQL execution contain zero credentials, learner answers, or user PII.

- **Primary Baseline Artifact**: [`docs/architecture/artifacts/study_architecture_audit_baseline_2026-08-29.json`](./artifacts/study_architecture_audit_baseline_2026-08-29.json)
  - **File Size**: `40,678 bytes` (1,256 lines)
  - **SHA-256 Checksum**: `3eaa6123c5bf02bffb27db3c1a32ee172fe5b8212fb60a0fbecd39c16f4fd511`
- **Two-Run Comparison Artifact**: [`docs/architecture/artifacts/study_architecture_audit_determinism_comparison_2026-08-29.json`](./artifacts/study_architecture_audit_determinism_comparison_2026-08-29.json)
  - **Determinism Status**: `deterministic_excluding_timestamp: true`
  - **Differences Found**: `[]` (0 differences)
- **Raw Run 1 Output**: [`docs/architecture/artifacts/study_architecture_audit_run1_2026-08-29.json`](./artifacts/study_architecture_audit_run1_2026-08-29.json)
- **Raw Run 2 Output**: [`docs/architecture/artifacts/study_architecture_audit_run2_2026-08-29.json`](./artifacts/study_architecture_audit_run2_2026-08-29.json)

---

## 6. Verification Commands, Execution Timing & Evidence

### 6.1 Audit Execution with SELECT-Only Principal
```powershell
$env:SQLALCHEMY_DATABASE_URI = "mysql+pymysql://flama_audit_ro:<REDACTED>@localhost:3306/nihongo?charset=utf8mb4"
$env:STARTUP_RUN_MAINTENANCE = "False"

# Run 1:
.venv\Scripts\python.exe wsgi_audit.py --output docs/architecture/artifacts/study_architecture_audit_run1_2026-08-29.json
# Run 1 completed in ~8.58s (Exit code: 1 / WARN)

# Run 2:
.venv\Scripts\python.exe wsgi_audit.py --output docs/architecture/artifacts/study_architecture_audit_run2_2026-08-29.json
# Run 2 completed in ~8.68s (Exit code: 1 / WARN)
```

### 6.2 Independent Spot-Check Verification Evidence
```powershell
# Direct verification of bounded sample IDs via independent read-only queries with SELECT-only principal
.venv\Scripts\python.exe -c "
import os
os.environ['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://flama_audit_ro:<REDACTED>@localhost:3306/nihongo?charset=utf8mb4'
os.environ['STARTUP_RUN_MAINTENANCE'] = 'False'
from wsgi_audit import create_app
from models import db
from models.template import Template
from models.card import Card
from models.card_progress import CardProgress
from models.review_event import ReviewEvent
from models.study_session import StudySession
from models.study_session_card import StudySessionCard

app = create_app()
with app.app_context():
    # 1. Duplicate position templates
    t = Template.query.filter_by(note_type_id='4525f529-f5d5-4c58-9bb3-b191e318fd28', position=0).all()
    print('1. Duplicate position templates:', len(t), [x.id for x in t])

    # 2. Stale session cards
    for ssc_id in [249, 619, 620]:
        ssc = db.session.get(StudySessionCard, ssc_id)
        cp = CardProgress.query.filter_by(card_id=ssc.card_id, user_id=ssc.session.user_id if ssc.session else 1).first()
        print(f'2. Stale SSC {ssc_id}: card_id={ssc.card_id}, base_rev={ssc.base_progress_revision}, CP rev={cp.revision if cp else None}')

    # 3. Detached / Orphan review events
    for rev_id in [1, 2, 3]:
        rev = db.session.get(ReviewEvent, rev_id)
        c = db.session.get(Card, rev.card_id) if rev and rev.card_id else None
        print(f'3. Orphan review event {rev_id}: card_id={rev.card_id if rev else None}, Card exists={c is not None}')

    # 4. Null algorithm review events
    null_algo_events = ReviewEvent.query.filter(ReviewEvent.scheduler_algorithm.is_(None)).order_by(ReviewEvent.id.asc()).limit(3).all()
    print('4. Null algorithm sample:', [(r.id, r.scheduler_algorithm, r.algorithm_version) for r in null_algo_events])

    # 5. Expired open session
    sess = db.session.get(StudySession, '10dbb26e-74b7-4050-9b95-d6551b30ace4')
    print('5. Expired session status:', sess.status, 'expires_at:', sess.expires_at)

    # 6. Historical Anki revlog imported events count
    anki_imported = ReviewEvent.query.filter_by(scheduler_algorithm='anki', algorithm_version='revlog-v1').count()
    print('6. Anki imported revlog events count:', anki_imported)
"
```

*Execution Output*:
```text
1. Duplicate position templates: 9 ['10adf514-e819-4186-91a6-3efebabc6de1', '4491b783-e017-43e0-8f36-8939ea3b4780', '4a13794b-a739-4eba-aa37-c6853d8cb75b', '5aef61ee-b4fa-46ec-a765-2257ee79d6cd', '9e137c38-faf2-4b66-8cc6-1b22186094d9', 'a28317ac-04a7-49a1-8d9b-426869feb12b', 'd2db431c-dcdf-455a-881e-3c050bbba978', 'f40624fb-20ce-42b0-9f7e-592fed7d7537', 'f8dbd96d-c159-4e26-9a0d-9b28a9976b06']
2. Stale SSC 249: card_id=083ccf36-dc5c-418d-b37f-2d4f935d4841, base_rev=1, CP rev=2
2. Stale SSC 619: card_id=046758f7-f90c-4636-b21b-2abbf059402d, base_rev=0, CP rev=3
2. Stale SSC 620: card_id=05674555-e31e-4c65-aac2-ad61ddf946cd, base_rev=0, CP rev=2
3. Orphan review event 1: card_id=03fd728f-a412-45ee-899c-14b2fd10e049, Card exists=False
3. Orphan review event 2: card_id=03fd728f-a412-45ee-899c-14b2fd10e049, Card exists=False
3. Orphan review event 3: card_id=063529ef-5187-489d-b073-898e64c02d39, Card exists=False
4. Null algorithm sample: [(1, None, None), (2, None, None), (3, None, None)]
5. Expired session status: open expires_at: 2026-08-14 16:30:02
6. Anki imported revlog events count: 61645
```

### 6.3 Automated Domain Test Suite Evidence
```powershell
.venv\Scripts\python.exe scripts/run_tests.py --module study,connect_mcp --backend-only

# Result: 26 test files (257 tests) passed in 163.62s (100% green)
```

---

## 7. Phase 0 Exit Gate Decision

> **Verdict**: **NO-GO — stored evidence is superseded and Phase 0 is not ready for closeout.**

1. P0-02 is `COMPLETED`: strict canonical policy/hash validation and malformed snapshot fixtures pass.
2. P0-03 is `BLOCKED`: stored output has 5 warnings while current code/MySQL has 6, including `unknown_provenance_events=35`.
3. Current audit code is identified by the explicit file-digest manifest, but the stored two-run output was generated from an earlier state.
4. The replacement bundle still requires an authorized `SELECT-only` URI that is not available in the current execution environment.

Phase 1 is not cleared by this report. P0-01, P0-02 and P0-04 are independently accepted; expose the audit URI through a safe secret/environment mechanism, then create and review the replacement P0-03 evidence bundle.
