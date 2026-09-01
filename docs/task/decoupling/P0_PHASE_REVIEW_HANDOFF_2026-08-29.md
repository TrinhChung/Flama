# Phase 0 review handoff — P0-01 đến P0-04 — 2026-08-29

> Gate verdict: **GO — Phase 0 đã đóng bằng replacement SELECT-only bundle**
>
> Current task status: `P0-01 COMPLETED`, `P0-02 COMPLETED`, `P0-03 COMPLETED`, `P0-04 COMPLETED`.
>
> Scope: review implementation, test coverage, MySQL audit evidence and artifact integrity. This closeout changed no database data/schema and does not authorize Phase 4.

## Authoritative Phase 0 closeout — 2026-08-29

The blocked Round 5 state was resolved with the dedicated `flama_audit`@`localhost` principal. Grant preflight confirmed SELECT-only access to `nihongo`; both current-code audit runs returned `61 PASS / 6 WARN / 0 BLOCK`, exit code `1`, with no semantic difference outside `observed_at`.

| Evidence | Result |
|---|---|
| Audit code manifest | All listed file hashes and canonical manifest digest verified |
| MySQL/Alembic | MySQL `8.0.40`; revision `20260902_000031` |
| Run timestamps | `08:05:08` and `08:05:17` UTC |
| Determinism | `true`; semantic diff count `0` |
| Inventory/reconciliation | 67 categories; 11/11 formulas valid |
| Primary SHA-256 | `8b7c7f36fa6f2049bda0a82f8f0de10ca5b68a4c54c31ccf995b06c47e0d4484` |
| Required regression | 33 focused audit/baseline, 97 Study backend and 161 Connect/MCP tests passed |

The six warnings are assigned to P1-01, P1-02, P1-03, P1-04, P2-02 and P3-04. They are downstream correctness/lifecycle work, not blocking anomalies. Phase 1 may start at P1-01.2; Phase 4 remains out of scope.

## 1. Kết luận bàn giao

Round 5 previously blocked P0-03 because the stored five-warning bundle was superseded. The authoritative closeout above replaces it with the current six-warning SELECT-only bundle.

| Task | Verdict | Trạng thái | Blocker chính |
|---|---|---|---|
| P0-01 | Đạt | `COMPLETED` | Audit/normal command surfaces đã tách; audit app không đăng ký mutator và không gọi startup maintenance; failure contract pass executable tests |
| P0-02 | Đạt | `COMPLETED` | Canonical material/schema/digest validation và 9 malformed fixtures đã qua executable review; MySQL strict validator trả `invalid_config_snapshot_sessions=0` |
| P0-03 | Đạt có warning đã phân công | `COMPLETED` | Replacement two-run bundle, checksum manifest, spot checks and required regressions passed |
| P0-04 | Đạt | `COMPLETED` | Rollback sau ORM flush, direct/MCP parity, import/overlay và frontend containment đã có executable evidence; runtime contract changes đã được khai báo |

## 2. Evidence đã xác minh

### 2.1 Test modules

```text
.venv\Scripts\python.exe scripts/run_tests.py --module study --backend-only
PASS — 13 files, 97 tests, 69.64s runner time (66.601s unittest)

.venv\Scripts\python.exe scripts/run_tests.py --module study --frontend-only
PASS — 19 files, 89 tests, 10.91s

.venv\Scripts\python.exe scripts/run_tests.py --module connect_mcp --backend-only
PASS — 13 files, 161 tests, 94.49s

.venv\Scripts\python.exe -m unittest tests.test_study_architecture_audit_cli tests.test_study_architecture_audit_service tests.test_study_behavior_acceptance_baseline
PASS — 33 tests, 38.276s
```

Lệnh dùng `python scripts/run_tests.py ...` trong task docs không chạy được ở shell review vì `python` không có trên `PATH`; virtualenv command ở trên là invocation đã xác minh.

### 2.2 MySQL read-only diagnostic

Review round 3 chạy canonical dedicated entrypoint `wsgi_audit.py --compact`, không ghi artifact. Audit principal được kiểm tra độc lập bằng `SHOW GRANTS`: có `SELECT`, không có `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP` hoặc `GRANT OPTION`.

```text
Dialect: mysql
MySQL: 8.0.40
Alembic revision observed: 20260902_000031
Audit schema: study-architecture-audit.v3
Inventory categories: 67
Reconciliation checks: 11/11 true
Verdict: WARN, exit code 1
Inventory dispositions: PASS 61 / WARN 6 / BLOCK 0
Principal has SELECT grant: true
Principal has write privileges: false
```

Warnings observed:

- `duplicate_position_groups = 1`
- `open_session_stale_revisions = 751`
- `orphan_card_id_events = 40`
- `null_algorithm_events = 35`
- `unknown_provenance_events = 35`
- `expired_open_sessions = 18`

Algorithm partition hiện phân loại `historical_imported_algorithm_events = 61,645`, `unregistered_native_algorithm_events = 0`; tightened channel classifier đưa `35` legacy rows thiếu evidence vào `unknown_provenance_events`. Đây vẫn chỉ là diagnostic review, không thay thế P0-03 vì chưa chạy bằng authorized `SELECT-only` principal và evidence bundle chưa tái sinh theo current code.

### 2.3 Artifact integrity mismatch

Report hiện tại: `docs/architecture/production-architecture-verification-2026-08-29.md`.

Artifact hiện tại: `docs/architecture/artifacts/study_architecture_audit_baseline_2026-08-29.json`.

| Evidence | Report/artifact claim | Current code/MySQL observation |
|---|---|---|
| SHA-256 | baseline/Run 1 `3eaa6123c5bf02bffb27db3c1a32ee172fe5b8212fb60a0fbecd39c16f4fd511` | checksum đúng cho stored Run 1 nhưng không đại diện latest service code |
| Inventory | 67 categories | 67 categories |
| Reconciliation formulas | 11 checks | 11 checks |
| Warning count | 62 PASS / 5 WARN / 0 BLOCK | 61 PASS / 6 WARN / 0 BLOCK |
| Provenance | `unknown_provenance_events = 0` | `unknown_provenance_events = 35` |
| Code identity | base commit `a1d904d...` + “working-tree bundle” | current state đã freeze bằng `study_architecture_audit_code_manifest_2026-08-29.json`; stored runs vẫn predate manifest state |
| Determinism evidence | hai raw runs + comparison artifact | độc lập xác minh equal khi chuẩn hóa `observed_at`, nhưng chỉ cho pre-change code state |
| Read-only identity | report ghi SELECT-only/rotated | grants được xác minh độc lập là SELECT-only; rotation là operational assertion chưa thể xác minh từ repo |

Security containment vẫn đạt: artifacts/docs hiện không chứa plaintext URI/credential và grants không có write privilege. Không có secret file `scratch/ro_uri.txt` trong worktree tại thời điểm review.

Kết luận: report/artifact Round 4 là `superseded/unverified`, không phải Phase 0 approval bundle. Chỉ regenerate sau khi P0-02 đạt gate và exact code state được freeze.

### 2.4 Task specs authoritative sau independent review round 5

Các mục handoff round 1 ở phần 3–7 được giữ làm lịch sử review. Khi có khác biệt, status header và phần `Independent review round 5 — 2026-08-29` trong từng task là kết luận hiện hành:

- [`P0-01_AUDIT_COMMAND_SAFETY.md`](./completed/P0-01_AUDIT_COMMAND_SAFETY.md): `PASSED`; canonical audit-only factory/command surface đã được xác minh.
- [`P0-02_AUDIT_COVERAGE_AND_DISPOSITION.md`](./completed/P0-02_AUDIT_COVERAGE_AND_DISPOSITION.md): `PASSED`; strict canonical policy/hash validation và negative fixtures đã đạt.
- [`P0-03_MYSQL_BASELINE_VERIFICATION.md`](./completed/P0-03_MYSQL_BASELINE_VERIFICATION.md): `COMPLETED`; current six-warning SELECT-only replacement bundle passed.
- [`P0-04_BEHAVIOR_ACCEPTANCE_BASELINE.md`](./completed/P0-04_BEHAVIOR_ACCEPTANCE_BASELINE.md): `PASSED`; write-phase rollback và parity evidence đạt gate.

Output tối thiểu khi giao review lần kế tiếp:

| Task | Công việc phải chứng minh | Output đầu ra |
|---|---|---|
| P0-01 | Đã đạt | Giữ command-surface regression tests xanh; không phục hồi normal-app audit command |
| P0-02 | Đã đạt | Giữ required schema/digest checks và 9 malformed fixtures xanh trong các refactor tiếp theo |
| P0-04 | Đã đạt | Giữ rollback-after-flush và cross-entrypoint parity characterization xanh trong P1 refactor |
| P0-03 | Evidence phản ánh exact reviewed code bằng SELECT-only principal | Dùng code manifest hiện tại; two-run bundle mới; report/checksum/counts khớp current warning set |

## 3. Handoff P0-01 — Audit command safety

### Đã có

- `--compact`, `--output`.
- JSON schema `study-architecture-audit.v3`.
- Exit code `PASS=0`, `WARN=1`, `BLOCK/error=2`.
- Command-body exception mapping sang JSON blocking report.

### Việc code tiếp

1. Tạo dedicated audit app/entrypoint đặt toàn bộ maintenance flag về false trước app creation.
2. Không cho caller/environment bật lại schema/data maintenance trong audit process.
3. Thêm subprocess integration test cho real invocation, với spy được cài trước `create_app()`.
4. Test app config error, DB connectivity failure, missing table và missing column; failure phải machine-readable/non-green.
5. Thêm deterministic `ORDER BY` cho mọi bounded sample/query array.
6. Test hai lần cùng DB state và fixed/declarative timestamp cho payload giống nhau.
7. Viết invocation/runbook local, CI và production-like; không log URL/secret/content.

### File ownership đề xuất

- `app/cli.py`
- `app/__init__.py` hoặc audit-only factory/entrypoint mới
- `app/services/study_architecture_audit_service.py` chỉ cho deterministic output nếu cần
- `tests/test_study_architecture_audit_cli.py`
- startup subprocess test mới

### Exit gate

- Real audit process không gọi mutator trong mọi environment configuration.
- Config/schema errors trả non-zero và không green.
- Output deterministic trừ timestamp được khai báo.
- Handoff đầy đủ theo `README.md`.

## 4. Handoff P0-02 — Audit coverage/disposition

### Đã có

- Template/card/progress fan-in/revision/event/session audit cơ bản.
- Bounded samples và inventory severity/disposition.
- SQLite/MySQL query execution proof.

### Việc code tiếp

1. Resolve executable bằng exact `(key, version)` từ `study_algorithm_registry`; không dùng key allow-list hard-code.
2. Audit active/open session pinned algorithm, version, config hash và decoder availability.
3. Phân loại ReviewEvent theo native direct/MCP/batch và external Anki snapshot/revlog/import; ambiguous evidence phải `needs_verification`.
4. Audit overlay theo source/local-installed/local-added, `DeckCloneAddedNote`, installed NoteType/Template/application state.
5. Bổ sung disposition cho mọi counted category hoặc mô tả overlap rõ ràng.
6. Viết reconciliation disjoint/exhaustive bằng equality cho CardProgress groups, ReviewEvent provenance và mọi StudySession status.
7. Thêm fixtures cho unavailable key/version, session pin drift, provenance conflict, local-added overlay và unknown session status.
8. Review MySQL query plans/compatibility; giữ audit read-only.

### File ownership đề xuất

- `app/services/study_architecture_audit_service.py`
- query helper/repository audit mới nếu service tiếp tục phình lớn
- `tests/test_study_architecture_audit_service.py`
- fixtures audit mới

### Exit gate

- Mọi row/group có đúng một disposition hoặc overlap được chứng minh.
- Không suy diễn provenance khi evidence không đủ.
- Exact algorithm/version availability được kiểm tra.
- Reconciliation phải fail khi fixture cố ý tạo unknown/unaccounted category.

## 5. Handoff P0-04 — Behavior acceptance baseline

### Đã có

- Behavior matrix cho 6 nhóm chính.
- Batch retry idempotency test.
- Suspended/buried due selection test.
- Frontend forged `host_command` negative tests đang xanh.
- Golden vectors không bị sửa.

### Việc code tiếp

1. Tạo cùng một initial-state fixture và chạy cả REST/direct lẫn MCP; so sánh scheduler state, ReviewEvent, key/version/config hash và source metadata.
2. Thêm batch atomic rollback test và stale revision test với assert zero partial write.
3. Thêm due queue ordering và 4 AM boundary vectors cho nhiều timezone với expected độc lập.
4. Đi qua Anki import/Connect entrypoint thật để kiểm tra identity/idempotency/provenance.
5. Đi qua real install/session/query path cho source overlay và local-added content; assert không source mutation.
6. Giữ iframe/postMessage evidence ở frontend tests; đổi/xóa backend test đang chỉ gọi `resolve_review_action` nhưng đặt tên như renderer security test.
7. Map đầy đủ P2-01 negative cases và parent shortcut evidence.
8. Tách thay đổi `oauth_service.py` khỏi P0-04; không ghi “API behavior changed: None” khi URL resolution order bị đổi.

### File ownership đề xuất

- `tests/test_study_behavior_acceptance_baseline.py`
- `tests/test_study_session_api.py`
- `tests/test_flama_connect_mcp.py`
- import/Connect tests gần nhất
- `frontend/src/features/study/components/CardRendererHost.test.ts`
- `frontend/src/features/study/pages/StudyPage.test.tsx`

### Exit gate

- Tên test, entrypoint thực thi và invariant phải khớp nhau.
- Direct/MCP/batch/import/overlay/renderer đều có executable evidence thật.
- Không khóa security bug hoặc physical clone behavior.
- Không có production implementation ngoài test seam thuộc P0-04.

## 6. Handoff P0-03 — MySQL baseline

P0-03 chỉ bắt đầu lại sau khi P0-01, P0-02 và P0-04 đạt review gate.

### Run sequence bắt buộc

1. Ghi operator authorization, target environment, app commit và snapshot time.
2. Xác minh SELECT-only principal bằng redacted grant evidence.
3. Xác minh Alembic revision/MySQL version trước audit.
4. Chạy dedicated maintenance-disabled audit entrypoint hai lần trên cùng snapshot.
5. So sánh deterministic payload trừ timestamp; lưu comparison result.
6. Spot-check bounded samples bằng independent read-only queries.
7. Sinh JSON, Markdown report và checksum trong cùng execution bundle.
8. Recompute checksum sau khi file đã đóng; verify lại ngay trước handoff.
9. Ghi drift định lượng so với baseline trước và owner/disposition cho mọi warning/blocker.
10. Chỉ đổi status sang `DONE` khi report, artifact, checksum, environment metadata và exit code khớp.

## 7. Thứ tự thực thi tiếp

```text
P0-01 dedicated read-only entrypoint + startup tests
  -> P0-02 exhaustive inventory/reconciliation

P0-04 real cross-entrypoint characterization
  -> có thể chạy song song với P0-01/P0-02 nếu ownership file không chồng nhau

P0-01 + P0-02 + P0-04 independently reviewed DONE
  -> P0-03 fresh SELECT-only MySQL evidence bundle
  -> Phase 0 closeout review
```

P0-02 hiện đã ổn định. Chỉ regenerate P0-03 sau khi credential `SELECT-only` khả dụng và code manifest được xác minh, nếu không artifact sẽ stale hoặc không đạt security gate.

## 8. Next execution plan after round 5

Kế hoạch chi tiết hiện hành nằm tại [`PHASE_0_3_NEXT_EXECUTION_PLAN_2026-08-29.md`](./PHASE_0_3_NEXT_EXECUTION_PLAN_2026-08-29.md).

- Immediate executable task: unblock và hoàn tất P0-03 bằng replacement `SELECT-only` bundle.
- First runtime task after Phase 0 closes: P1-01 canonical native review transaction.
- Frontend correctness order: P2-02 → P2-03 → P2-04 → P2-05.
- Composition decisions P3-05/P3-07 are documentation-only and begin only after authoritative P0-03 evidence exists.
- Phase 0 is `GO`; begin P1-01.2 while preserving all downstream dependency gates.

## 9. Handoff completion template

Mỗi task khi giao lại phải append:

```text
Task ID:
Primary outcome:
Files changed:
Contract/API behavior changed:
Tests added or updated:
Commands run:
Test results:
Rollback path:
Known limitations:
Follow-up task IDs:
Reviewer gate result: PASS / RETURNED
```

Task chỉ chuyển `DONE` sau khi reviewer xác minh output và acceptance criteria, không chỉ dựa vào test suite xanh.
