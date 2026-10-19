# P4-00 — Frozen session entry correction

> Phase: 4 prerequisite
>
> Priority: P0 blocker
>
> Status: COMPLETED — 2026-09-10
>
> Dependency: Phase 3 compatibility runtime
>
> Primary lane: Backend + Frontend Study session

## Mục tiêu

Khép các regression vừa phát hiện trong frozen composition/artifact contract trước khi Phase 4 dùng session evidence để chứng minh state parity.

## Evidence

- `frontend/src/features/study/hooks/useStudySession.ts` và `sessionStore.ts` có thể rewrite Template artifact/key/version của active persisted session sau live edit.
- `sessionRestore.ts` chỉ kiểm tra prefix của binding fingerprint và shape tối thiểu.
- `study_session_config.py` coi unknown versioned wrapper như legacy flat policy.
- Durable batch normalization chưa giữ/validate đầy đủ `composition_id`.

## Công việc

1. Lập matrix cho active/pending session với same-tab/cross-tab Template edit, Note content edit, persisted batch và restore.
2. Chốt policy: Template/executable/binding của new-contract lease là immutable. Với content ảnh hưởng evaluation, hướng mặc định là save cho session sau; nếu giữ quick-edit current view, phải tách authoring view khỏi frozen replay material.
3. Không mutate frozen Template artifacts, `template_key`, definition version/hash hoặc composition binding từ sync events.
4. Recompute canonical binding fingerprint và validate application/definition/FieldDef/artifact consistency khi restore.
5. Backend decoder chỉ nhận:
   - exact supported wrapper version;
   - genuine legacy flat policy map đã validate.
   Unknown/partial versioned wrapper fail closed.
6. Preserve `composition_id` through pending-batch serialization/normalization and quarantine mismatch before send.
7. Dùng real canonical hashes trong fixtures; thêm tamper/unknown version tests.
8. Add amendment vào Phase 3 closeout và canonical tracker khi gate pass.

## Acceptance

- Live edit không thay đổi frozen execution material của active/pending new-contract lease.
- Reload, commit, retry và worker đều thấy cùng composition/binding/artifact.
- Binding/hash/identity tamper và unknown wrapper fail closed với bounded errors.
- Genuine legacy flat policies và supported v2/v3 leases tiếp tục hoạt động.
- Active Study presentation không regression ngoài behavior đã chốt cho edit.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module study --frontend-only
npm --prefix frontend run typecheck
```

## Rollback

Giữ strict readers cho mọi wrapper đã phát hành. Nếu UI edit integration cần rollback, disable propagation vào active lease và để saved changes xuất hiện ở session sau.

## Không làm

- Không thêm progress/state schema.
- Không đổi scheduler hoặc composition cardinality.
- Không thực hiện generic Template version store.

## Handoff — 2026-09-10

- Policy đã chốt: mọi thay đổi Template hoặc Note content được lưu bởi authoring API nhưng không propagate vào active/pending StudySession; session hiện tại tiếp tục dùng artifacts đã freeze và thay đổi xuất hiện từ session kế tiếp.
- Frontend restore recompute canonical binding fingerprint, kiểm tra selected composition/application/definition/FieldDef và Template/content artifact identity, đồng thời quarantine durable batch thiếu hoặc lệch `composition_id`.
- Backend decoder chỉ chấp nhận exact supported wrapper hoặc genuine legacy flat policy map đã validate; unknown/partial wrapper và binding tamper fail closed bằng bounded config error.
- Canonical SHA-256 fixtures dùng cùng JSON material với backend, bao gồm UTF-8 vector.
- Không có model, migration, database write, scheduler hoặc authority change. `CardProgress` vẫn là authority duy nhất.

Verification đã pass:

```text
python scripts/run_tests.py --changed
# Study matrix passed: backend 17 files/154 tests; frontend 25 files/186 tests

python scripts/run_tests.py --module study --backend-only
# 17 files, 154 tests passed

npm --prefix frontend run test:study
# 25 files, 186 tests passed

npm --prefix frontend run typecheck
# passed

npm --prefix frontend run lint
# passed; 23 pre-existing unrelated warnings, zero errors
```

Gate result: Phase 3 frozen-session correctness gate được đóng lại. Task tiếp theo là [P4-01](./P4-01_CURRENT_STATE_PREFLIGHT.md); chưa được phép bắt đầu P4-06 schema/migration trước khi G4-0 và các ADR P4-02..P4-05 đạt.
