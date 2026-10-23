# Ưu tiên cleanup legacy — 2026-10-19

Mốc production đã kiểm tra: `cec70bc37a137e03f9b8544243c29ab4613856ba`, DB head 68.
Phần triển khai dưới đây nằm trong nhánh cleanup riêng. Workspace chính đang có
thay đổi template, payment và import; không đưa các thay đổi đó vào cleanup.

## Phần nhỏ đã xử lý

- Bỏ `STUDY_PROGRESS_SHADOW_WRITE_ENABLED` và `STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED`
  khỏi [config](../../app/settings.py). Đã tìm trong `app/`, `models/`, `scripts/`
  và tests: không có runtime consumer của hai cờ, chỉ còn cấu hình và fixture/probe
  gán giá trị. Gỡ các phép gán đó để tránh thể hiện sai rằng chúng kiểm soát hành vi.
- Giữ `STUDY_PROGRESS_SHADOW_COMPARE_ENABLED`: [audit connection safety](../../app/services/audit_connection_safety.py)
  còn đọc cờ để yêu cầu snapshot MySQL phù hợp. Đây không phải một shadow writer.
- Sửa mô tả [mapper](../../app/services/study_progress_shadow_mapper.py) và
  [codec](../../app/services/study_progress_shadow_codec.py): các helper vẫn được
  NOTE authority, receipt và algorithm switching dùng. Tên module mang lịch sử
  Phase 4 không có nghĩa cả module đã chết.
- Không thay SQL, lịch học, transaction, endpoint, schema hoặc định dạng offline.
  Các biến env cũ trên VPS được để nguyên; code mới bỏ qua chúng như trước.
  Không sửa lại tài liệu/artifact lịch sử để tạo cảm giác các rollout cũ chưa xảy ra.

## Phần cần lên kế hoạch điều tra

Ước lượng dưới đây là công sức kỹ thuật sơ bộ, chưa phải cam kết lịch. Thời gian
quan sát canary/client cũ được tính riêng. Chỉ triển khai sau khi chốt phạm vi.

| Thứ tự | Hạng mục | Ảnh hưởng và bằng chứng hiện tại | Điều tra | Triển khai sơ bộ |
|---|---|---|---|---|
| 1 | Hợp nhất sharing/Marketplace | [Monolith](../../app/services/flashcards_share_service.py) và [package share](../../app/services/share/__init__.py) đều chứa triển khai publish/install/overlay; caller còn import cả hai hướng. Dễ sửa nhầm nguồn xử lý. | 1–2 ngày | 2–4 ngày theo từng nhóm hành vi |
| 2 | Hợp nhất payment | [payment_service.py](../../app/services/payment_service.py) và [package payment](../../app/services/payment/__init__.py) có checkout/webhook/order logic tương ứng; routes còn gọi monolith. Workspace chính cũng đang sửa payment, phải đối chiếu lại sau khi nhánh đó ổn định. | 0,5–1 ngày | 1–3 ngày |
| 3 | Thu hẹp route tương thích | [Registry](../../app/routes/__init__.py) đăng ký API canonical trước các blueprint cũ; [vocabulary](../../app/routes/vocabulary.py) còn adapter, form/redirect và stub cấu trúc đã bỏ. Đây là nợ bảo trì, chưa chứng minh là nguồn độ trễ đáng kể. | 0,5–1 ngày | 1–2 ngày sau inventory client |
| 4 | Chuyển writer checkpoint offline | [sessionStore](../../frontend/src/features/study/session/sessionStore.ts) đang chọn writer inline vì build flag chưa bật; writer tách artifact đã có. Ghi nguyên session làm tăng payload phải lưu, mức ảnh hưởng cần benchmark. | 0,5–1 ngày | 1–2 ngày chuẩn bị, cộng thời gian canary |
| 5 | Retire Study wire v2/v3/fallback | [Wire contracts](../../app/validators/study_session_wire.py) và [session route](../../app/routes/flashcards/study.py) còn negotiation và compatibility branch. Có thể liên quan tab offline, session/receipt/retry cũ. | 1–2 ngày, cộng thời gian quan sát | 2–4 ngày nếu không còn consumer |
| 6 | Kết thúc các chế độ shadow Marketplace | `MARKETPLACE_SAMPLE_MODE=shadow_cache` dùng cache khi có rồi query live để đối chiếu; guard NoteType ở `shadow` ghi log cho một số mismatch. Đây là rollout chuyển tiếp, không phải code chết. | 0,5–1 ngày | Nhỏ nếu coverage/parity đã đạt; nếu chưa thì cần task riêng |

## Đầu ra cần có trước khi triển khai các phần lớn

### Sharing và payment

1. Lập sơ đồ caller → implementation thực tế, cả import trực tiếp, facade và test patch.
2. So sánh từng hàm trùng: semantics, exception type, quyền, transaction/commit,
   rollback, lock/retry và các side effect. Không chọn một bản chỉ vì file nhỏ hơn.
3. Chốt một implementation; facade chỉ re-export/delegate, không giữ bản copy.
4. Xác minh owned/installed clone, release pin/rebase và free/paid install; với
   payment kiểm thêm webhook trùng, retry, cấp quyền và hoàn tiền.
5. Mỗi PR chỉ chuyển một nhóm hành vi; giữ kết quả API và giao diện hiện có.

### Routes và Study wire

1. Inventory request/session theo endpoint và wire version trên production;
   phân biệt traffic thật, bot, tab cũ và test. Không suy luận không dùng chỉ vì flag tắt.
2. Đối chiếu consumer frontend/Connect/MCP và thời hạn offline/retry/receipt.
3. Chuyển consumer rồi mới retire adapter. Stub Level/Topic/Lesson `410` vẫn là
   hành vi có chủ đích theo AGENTS.md, không bỏ hàng loạt trong cleanup nhanh.
4. Không đổi semantic Note/Card ID hoặc xóa alias/history để giảm số nhánh code.

### Offline và Marketplace

1. Offline: đo payload/lần ghi và thời gian checkpoint ở phiên dài, nhiều tab;
   kiểm restore/undo/content patch/quarantine, DB2 → DB3 và reader rollback.
2. Marketplace: đo cache coverage, mismatch và SQL/request, kiểm owned/clone/release.
   Chỉ bỏ live comparison hoặc bật strict khi đã xác định cách xử lý mismatch.

## Các phần không xếp vào legacy cần xóa

- Analytics outbox, deck count snapshot và forecast snapshot là triển khai mới
  chưa rollout: production writer tắt, reader `raw`, các bảng dẫn xuất kiểm tra
  ngày19 đều rỗng. Cần backfill/parity/canary riêng, không xóa vì chưa active.
- Async Study batch là cơ chế mới đang tắt admission, không phải scheduler cũ.
- Derived `Card`, presentation aliases, receipts, release/checkpoint và codec
  giữ identity/replay/history. Bảng `cards`, `card_progress` vật lý và Field rename
  theo tên đã retire; không dùng audit cũ làm căn cứ xóa các cấu trúc hiện hành.
- Adapter AnkiConnect/media, scanner upload và MCP token limiter chưa bật là
  khả năng/chính sách chưa kích hoạt, không tự động là code thừa.

Tham chiếu: [backend debt catalog](tech-debt/README.md),
[scalability rollout](../ops/old/DATABASE_PROGRESS_SCALABILITY_ROLLOUT.md),
[offline rollout](../logs/old/reports/LEGACY_PERFORMANCE_IMPLEMENTATION_2026-10-10.md).

## Xác minh phần cleanup nhỏ

- Modular runner với 8 file startup, import, template, deck settings, REST và
  consolidated Connect: **159 tests PASS**.
- Khởi động entry point thật `wsgi.py` với cấu hình production thụ động và SQLite
  memory riêng: `/api/health` trả 200; hai config key đã bỏ không còn được nạp,
  cờ audit comparison vẫn tồn tại.
- Ba MySQL probe sửa fixture vẫn parse Python hợp lệ; chưa chạy lại probe MySQL
  vì không đổi logic truy vấn/transaction. Không dùng DB production để chạy test.
- `git diff --check` qua; 19 liên kết tài liệu tương đối được kiểm tra đều tồn tại.
- Chưa merge/deploy cleanup hoặc thay env trên VPS trong phạm vi này.
