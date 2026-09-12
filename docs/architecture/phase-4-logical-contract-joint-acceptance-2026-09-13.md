# Phase 4 logical-contract joint acceptance — 2026-09-13

> Mode: DESIGN / REVIEW
>
> Decisions: P4-D4-1, P4-D4-2, P4-D4-3 and P4-D4-4
>
> Verdict: **ACCEPTED** — P4-01, P4-02, P4-03 and P4-04 gates are closed; P4-05 may translate these contracts into physical storage
>
> Runtime change: none | Schema change: none | Operational authority: `CardProgress`

## 1. Outcome

The refreshed production preflight and the joint logical review close the prerequisites for P4-05. The accepted contracts are:

- [learner/Note identity, fan-in and revision](./phase-4-progress-identity-fanin-revision-adr-2026-09-10.md);
- [versioned Algorithm State and availability](./phase-4-algorithm-state-availability-adr-2026-09-12.md);
- [history, provenance and lifecycle](./phase-4-history-provenance-lifecycle-adr-2026-09-12.md).

Acceptance authorizes physical **design** in P4-05. It does not authorize a model, migration, mirror writer, backfill, production shadow read, Algorithm switch or Phase 5 authority cutover.

## 2. Fresh production evidence

The normal deployment applied revisions `20260913_000037` and `20260913_000038` at release commit `11eefb15938cc8f4847df6d2d4014f40f41f3d13`. A new two-run bundle was then captured at one frozen UTC observation time through `wsgi_audit.py`, with startup maintenance disabled and an ephemeral MySQL principal restricted to `SELECT, SHOW VIEW`.

| Evidence | Result |
|---|---|
| observed at | `2026-09-12T22:57:25Z` |
| secured bundle | `/var/lib/flama-audit/phase4-preflight-20260912T225725Z-11eefb1` |
| release / repository / database head | `11eefb15938cc8f4847df6d2d4014f40f41f3d13` / `20260913_000038` / `20260913_000038` |
| deterministic comparison | `true`; changed paths `[]` |
| canonical report hash, both runs | `59bdd8e680f09d0ed78a9164426abcf19ada81311d738dcf1947c15628aa1d63` |
| report-file SHA-256, each run | `fb45255ecd92f6bb7e10d99873bac0ef6db66e22ed6665a9b1b53be39a38d669` |
| comparison-file SHA-256 | `ad4a8180c65ba4b907163d3ecf509f9d2bcd4b7890d69ffb9be895bd45db1026` |
| checksum verification | all files passed `sha256sum --check` |
| database privilege gate | two grant rows; no disallowed privilege; audit principal absent after cleanup |
| P4 phase gate | `PASS` in both runs; blockers `[]`; warnings `[]` |
| Alembic/schema gate | matching head; `drift_count=0`; batch-table contract issues `[]` |
| rollout activity | zero active sessions, zero active Connect imports, zero active/enqueued batches |

The established wider architecture audit still exits `1` because it reports seven known historical warnings: stale revisions in expired sessions, detached historical events, four null Algorithm labels, four unknown-provenance facts, five legacy payload gaps, 121 expired open sessions and four invalid historical config snapshots. None is a P4 current-state/schema blocker, and none is silently reclassified as clean data.

## 3. Current data contract accepted from P4-01

| Partition | Fresh production result | Design consequence |
|---|---:|---|
| `CardProgress` source rows | 16,424 | P4-05 sizes contributor/state/projection storage from this source count |
| valid learner/Note subjects | 16,424 | every current row resolves; no source row is discarded |
| single / fan-in subjects | 16,424 / 0 | production lowers initial collision risk but does not remove the fan-in contract |
| mirror / quarantine / unresolvable | 16,424 / 0 / 0 | initial backfill is fully classifiable under the accepted mapper |
| owned / installed-source / installed-local / unclassified | 16,107 / 317 / 0 / 0 | install/deck context remains evidence, never subject identity |
| latest-event pointer valid / null / invalid | 15,992 / 432 / 0 | pointer absence is explicit and independent of state validity |
| queue new / learning / relearning / review | 432 / 1,595 / 224 / 14,173 | relational availability must preserve Card-shaped queue ordering |
| due both-null / both-present / time-only / day-only | 432 / 14,173 / 1,819 / 0 | both anchors and their nullness remain stored |
| scheduler label anki / legacy | 14,621 / 1,803 | labels remain provenance; only the exact compatibility Algorithm is executable |
| memory pair null / complete / partial | 16,424 / 0 / 0 | partial pairs still fail closed even though none currently exists |
| Connect source Card / Note refs | 15,828 / 15,828 total, all targets matched; 15,813 current progress contributors match each kind | zero-to-many lineage stays independently accounted |
| ReviewEvents | 119,698 Anki import; 23 native direct; 5,829 native session; 4 null Algorithm label | history is heterogeneous and cannot reconstruct current state |
| detached ReviewEvent/Card references | 595 | physical history evidence must tolerate deliberate detachment |

Every source, subject, context, queue, due, memory, event-pointer and Connect-reference accounting formula passed in both runs.

## 4. Joint consistency decisions

| Concern | Accepted cross-ADR rule | Physical-design handoff |
|---|---|---|
| subject identity | exactly `(learner_user_id, logical_note_id)`; Template, Card, deck, install and source owner are context/provenance | one DB-enforced unique learner/Note coordination identity |
| current authority | `CardProgress` is the only Phase 4 operational read/write authority | shadow rows are derived and feature-flagged off by default |
| fan-in | no timestamp/revision/counter/average winner; semantic equality may mirror, divergence quarantines | explicit contributor rows plus a nullable/absent usable subject state |
| state identity | exact `legacy-anki/1.0.0`, `anki-card-state.v1`, `flama-canonical-state-json.v1` | version columns and bounded canonical JSON are required |
| equality | `semantic_state_hash = algorithm_state_hash + availability/control anchors`; history/provenance never enters semantic equality | state and lineage hashes remain separate columns |
| availability | per physical contributor, relational anchors, evaluated only with a frozen context | no persisted `eligible_now`; no generic JSON extraction in hot queries |
| lineage | latest event and every external ref remain per contributor; equal state never selects a lineage winner | zero-to-many lineage representation plus independent completeness code |
| history | `ReviewEvent` remains history/analytics; current state is never event-replayed | retain bounded scheduler-grade facts and detached identities |
| lifecycle | reset/delete/rekey advance `subject_generation`; `mirror_revision` versions only a derived projection | retained lifecycle ledger; no Note/Card cascade may erase its fence |
| concurrency | transaction-owner/source-identity prefix, sorted subject locks, then sorted contributor progress locks | first-create unique-key pattern and two-connection MySQL proof are mandatory |
| failure | expected invalid source data gets a typed quarantine; unexpected codec/DB/invariant failures roll back the current authoritative unit when mirroring is enabled | never catch arbitrary exceptions as quarantine |
| retention | no Phase 4 detail/history/tombstone purge; user deletion remains the privacy boundary | additive rows survive flag rollback; later cleanup needs a separate gate |

## 5. Review correction: clone cutover lock order

One ambiguous sentence in P4-04 said to retain the P1-02 local/source progress “lock prefix”. P1-02 proves only deterministic ordering **within** the two progress rows. Keeping progress locks ahead of the new subject locks would invert the P4-02 order used by native/session writers and could form a deadlock cycle.

The accepted wording is therefore:

```text
existing transaction-owner / Connect source-identity prefix locks
-> ensure and lock affected subject envelopes in canonical order
-> lock CardProgress contributors in canonical order
   (for cutover, this preserves P1-02's deterministic local/source Card-ID order)
-> authoritative mutation/event flush
-> one mirror finalization per subject
```

This clarification does not change the already shipped P1-02 runtime because subject locks do not exist yet. P4-07/P4-08 must adapt every participating writer to the full order together; P4-11 must prove cutover/review and first-create races with two MySQL connections.

## 6. Acceptance and remaining proof ownership

| Task | Verdict | Evidence still owned by later tasks, not an acceptance blocker |
|---|---|---|
| P4-01 | **ACCEPTED** | regenerate only after relevant schema/audit/deployment changes |
| P4-02 | **ACCEPTED** | physical unique-key/lock pattern in P4-05; concurrency proof in P4-11 |
| P4-03 | **ACCEPTED** | codecs/golden vectors in P4-06; query parity in P4-10/P4-11 |
| P4-04 | **ACCEPTED** | physical FK/ledger shape in P4-05; lifecycle writers in P4-08 |
| P4-05 | **READY** | select exact tables, constraints, indexes and rollback design; no DDL yet |

The logical contracts may be superseded only by a new explicit ADR before P4-06. After an issued schema or codec version exists, changes must be additive and preserve old readers/evidence through the documented rollback and retirement windows.
