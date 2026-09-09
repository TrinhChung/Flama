# P3-04 — Frozen composition restore and stale handling

> Phase: 3
>
> Priority: P1
>
> Status: COMPLETED — 2026-09-09
>
> Dependency: P3-01 and P3-03
>
> Primary lane: Backend + Frontend Session

## Mục tiêu

Freeze selected composition và effective runtime metadata cho toàn bộ session lease; restore/reload phải dùng snapshot đã freeze thay vì re-resolve current live definition.

## Phạm vi file dự kiến

- `app/services/study_session_service.py`
- `models/study_session.py` chỉ dùng JSON snapshot hiện có; không migration
- session API serialization
- `frontend/src/features/study/session/`
- `frontend/src/features/study/hooks/useStudySession.ts`
- backend/frontend session tests

## Công việc chi tiết

1. Định nghĩa canonical snapshot material theo P3-07:
   - selected composition/application ID;
   - effective legacy Template identity;
   - Interaction/trigger/Algorithm/config/state-schema versions hiện có;
   - binding/config fingerprint nếu compatibility layer có thể cung cấp.
2. Ghi selected composition một lần khi tạo session.
3. Per-card snapshot phải reference cùng selected contract và không chứa contradictory composition IDs.
4. Restore dùng frozen snapshot; không gọi discovery để thay selection.
5. Chốt behavior khi live definition bị edit/delete/unpublish sau session open:
   - active lease tiếp tục với frozen material nếu executable còn support;
   - nếu material thiếu/unavailable, trả typed recoverable/terminal error.
6. Reject commit nếu client selection khác frozen composition.
7. Old v2/legacy session không có selected composition được xử lý theo explicit compatibility rule.
8. Test definition drift, reload, stale UI selection, unavailable version và old session restore.

## Output đầu ra bắt buộc

- Versioned composition snapshot contract trong existing JSON.
- Backend freeze + frontend restore implementation.
- Stable stale/unavailable error behavior.
- Compatibility behavior cho legacy session.
- Cross-language restore/commit tests.
- Handoff report.

## Acceptance criteria

- Reload không prompt lại hoặc đổi StudyMode của active session.
- Live Template/application edit không đổi semantics của active lease.
- Commit selection phải khớp frozen snapshot.
- Không cần DB migration.
- Unknown/unavailable frozen version fail closed, không fallback latest.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module study --frontend-only
```

## Rollback

Snapshot fields mới additive trong JSON. Old readers bỏ qua fields; new readers giữ compatibility normalization. Không rewrite active session snapshot khi rollback.

## Không làm trong task này

- Không tạo composition column/table.
- Không implement long-term Template version storage.
- Không kéo lease vượt approved maximum.
- Không change progress authority.

## Handoff — 2026-09-09

- Task ID: `P3-04`
- Primary outcome: the selected composition and effective binding material are frozen in the existing session JSON for the full lease and reused on restore/reload.
- Files changed: `app/services/study_session_config.py`, session/worker/audit services, frontend restore/engine/hook code, and cross-language tests.
- Contract/API behavior changed: `study-session-config.v2` wraps the legacy policy with selected composition and binding data; readers accept supported legacy flat policies; contradictory client commit/batch composition IDs fail closed.
- Tests added or updated: frozen restore without discovery, partial/contradictory snapshot quarantine, definition drift, and commit mismatch.
- Rollback path: stop issuing new v2 config wrappers while retaining the dual reader for already-open leases.
- Known limitations: immutable physical Template versions remain a Phase 4+ concern; Phase 3 freezes the executable compatibility material available today.
- Follow-up task IDs: `P3-06`, `INT-01` — completed.
