# P1-03 — ReviewEvent provenance and payload hardening

> Phase: 1
>
> Priority: P1
>
> Status: COMPLETED 2026-09-08
>
> Dependency: P1-01
>
> Primary lane: Backend Study / Audit

## Mục tiêu

Đảm bảo mọi ReviewEvent mới có provenance nhất quán, bounded và được validate, đồng thời legacy gaps được classify thay vì tự suy diễn.

## Bối cảnh

- Native REST, MCP and session producers converged in completed P1-01; external/import producers remain intentionally separate and require this task's versioned provenance contract.
- At `46c03f0`, Anki `_import_review` already supplies `anki` / `revlog-v1` when constructing the event. Preserve that behavior; the remaining work is the shared versioned provenance/payload contract and final construction for all producers, including native session metadata.
- The async worker added in `6da743e` uses the native mutation core but adds a transaction/producer path. Include it in the inventory and apply the [2026-09-07 revalidation gate](../P1_P2_EXECUTION_PLAN_2026-09-07.md) before assuming earlier parity evidence covers this path.
- Broad client payload có nguy cơ đưa field dư, malformed hoặc oversized vào history.
- ReviewEvent là audit/analytics fact, không phải current-state source of truth.

## Phạm vi file dự kiến

- `models/review_event.py` chỉ để đọc contract hiện tại; không sửa schema trong task này
- `app/services/study_service.py`
- `app/services/study_session_service.py`
- `app/services/study_worker_service.py`
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

## Completion handoff — 2026-09-08

### Producer inventory trước và sau

| Producer | Trước P1-03 | Canonical new-write sau P1-03 |
|---|---|---|
| REST answer | Copy toàn bộ request body rồi thêm `_study_runtime`; provenance source không bắt buộc | `native.rest`; chỉ context allowlist được lưu; source/runtime lấy từ server |
| MCP `submit_review` | Adapter đưa `source=mcp` và client event vào payload | `native.mcp`; adapter truyền source và client event bằng typed parameter; compatibility keys được builder tạo |
| Session commit | Persist nguyên raw session event; gán session/event/sequence sau khi tạo ORM row | `native.session.commit`; final session/request/wire identity vào constructor ngay lần đầu |
| Async session worker | Persist nguyên raw queued event | `native.session.worker`; final batch/session/wire identity vào cùng canonical builder |
| Anki revlog import/repair | Column Algorithm đã đúng `anki` / `revlog-v1`, payload là raw canonical revlog | `external.anki.revlog`; external identity và fact nằm trong envelope riêng, không có `_study_runtime` |
| Snapshot/repair không tạo ReviewEvent | Không tạo event | Giữ nguyên; không ép snapshot thành native Action fact |

### Contract đã triển khai

Mọi ReviewEvent mới dùng `payload_json.schema_version = review-event-payload.v1`.
Native envelope gồm `provenance.kind=native`, trusted `source_path`, semantic
Action/Trigger identity và version, exact Algorithm/version/state schema/config
hash. Session writers thêm `study_session_id`, `client_event_id`, `sequence_no`,
request/batch ID và wire schema. External revlog dùng `provenance.kind=external`,
`external.anki.revlog`, source/import/external IDs và `anki-revlog.v1` fact; không
gắn Action/Trigger native.

`app/validators/review_event.py` là ownership seam chung. Policy giới hạn 8 KiB,
depth 5, 96 JSON nodes, key 64 ký tự, value string 512 ký tự, signed 64-bit
integer và finite float. Native request và session event có top-level allowlist;
duration là integer `0..3_600_000`. Unknown/reserved provenance field, non-JSON,
non-finite, quá sâu hoặc quá lớn trả typed code `4xx`. Builder chạy trước progress
mutation. Repository nhận session/event/sequence ngay trong constructor, loại bỏ
create-then-relabel.

Audit read-only thêm bốn partition disjoint, sample tối đa 10 ID:
`canonical_payload_complete`, `canonical_payload_missing_expected_field`,
`canonical_payload_conflicting`, `legacy_payload_unknown`. Legacy payload vẫn
đọc được và nằm trong `legacy_payload_unknown`; audit không update hoặc backfill.

### Acceptance evidence

- Focused provenance/REST/session/worker/MCP/Anki/audit: `87/87` pass.
- Study backend gate: `144/144` pass, 17 files.
- Connect/MCP backend gate: `161/161` pass, 13 files.
- `tests/test_review_event_provenance.py`: `5/5` pass và đã được thêm vào Study
  backend module mapping trong consolidation chung.
- Spoofed `source`, oversized string và session provenance field bị reject trước
  write; integration asserts `0` ReviewEvent và `0` CardProgress sau lỗi.
- Không thay model, column hoặc migration; logical overlay và transaction owner
  hiện tại được giữ nguyên.

Async admission/receipt lifecycle vẫn thuộc G0/P2-02. P1-03 chỉ chuẩn hóa writer
provenance của worker đang tồn tại; không dùng completion này làm readiness proof
cho việc bật queue ở production.
