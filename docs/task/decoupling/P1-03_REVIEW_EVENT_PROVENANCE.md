# P1-03 — ReviewEvent provenance and payload hardening

> Phase: 1
>
> Priority: P1
>
> Status: TODO
>
> Dependency: P1-01
>
> Primary lane: Backend Study / Audit

## Mục tiêu

Đảm bảo mọi ReviewEvent mới có provenance nhất quán, bounded và được validate, đồng thời legacy gaps được classify thay vì tự suy diễn.

## Bối cảnh

- Native producers hiện chưa hoàn toàn hội tụ cho tới khi P1-01 hoàn thành.
- Anki revlog path có behavior mutate Algorithm/version sau khi tạo event thay vì xây event external provenance atomic ngay từ đầu.
- Broad client payload có nguy cơ đưa field dư, malformed hoặc oversized vào history.
- ReviewEvent là audit/analytics fact, không phải current-state source of truth.

## Phạm vi file dự kiến

- `models/review_event.py` chỉ để đọc contract hiện tại; không sửa schema trong task này
- `app/services/study_service.py`
- `app/services/study_session_service.py`
- `app/services/anki_sync_service.py`
- event builder/validator/repository liên quan
- `app/services/study_architecture_audit_service.py`
- Study/Connect/event tests liên quan

## Công việc chi tiết

1. Inventory mọi ReviewEvent producer và source path.
2. Định nghĩa canonical new-write provenance tối thiểu:
   - source path;
   - effective algorithm key/version/config hash;
   - state schema/version nếu có trong compatibility contract;
   - semantic action/trigger identity cho native interaction;
   - session/request/client-event/sequence khi có;
   - external source ID/import provenance khi là sync.
3. Tách native interaction event khỏi external snapshot/revlog fact; không bịa action cho snapshot.
4. Allowlist persisted payload fields và giới hạn:
   - string length;
   - object/list depth/size;
   - numeric type/range;
   - optional legacy fields.
5. Chuyển ad-hoc casts thành typed validation error.
6. Construct event một lần với final provenance trong cùng transaction; không create rồi mutate nhãn.
7. Audit classify legacy rows:
   - complete;
   - missing expected field;
   - conflicting;
   - external/legacy unknown nhưng readable.
8. Thêm tests cho oversized/malformed payload, direct/MCP/batch parity và external provenance.

## Output đầu ra bắt buộc

- Versioned canonical ReviewEvent new-write contract.
- Shared validator/builder hoặc ownership seam rõ ràng.
- Bounded payload policy.
- Producer inventory trước/sau.
- Audit categories cho legacy gap.
- Regression tests cho native và external sources.

## Acceptance criteria

- Mọi native producer mới ghi cùng required provenance contract.
- External import không bị gắn nhãn native review.
- Malformed/oversized payload trả typed error và không ghi partial event.
- Legacy rows vẫn đọc được; missing data được classify, không tự điền giả.
- Không thêm DB column/migration. Nếu query cần column mới, tạo proposal Phase 4 riêng thay vì implement ở đây.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module connect_mcp --backend-only
```

## Rollback

Giữ reader tolerant với legacy payload. Nếu new validator gây incompatibility, revert writer validation/version atomically; không rewrite historical events.

## Không làm trong task này

- Không biến ReviewEvent thành progress authority.
- Không hứa exact replay ngoài active lease.
- Không backfill invented provenance.
- Không tạo migration.
