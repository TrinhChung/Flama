# P3-04 — Frozen composition restore and stale handling

> Phase: 3
>
> Priority: P1
>
> Status: TODO
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
