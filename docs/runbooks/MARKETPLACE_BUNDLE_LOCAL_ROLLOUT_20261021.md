# Diễn tập publication Marketplace bundle trên local

Ngày chạy publication: 2026-10-21; kiểm tra hoàn tất và apply lặp legacy: 2026-10-22. MySQL local 8.0.40, DB `nihongo`. Liên quan: [thiết kế bundle](../architecture/note-type-template-bundle-design-2026-10-21.md), [review và trạng thái sửa lỗi](../architecture/marketplace-bundle-completeness-review-2026-10-21.md).

## Phạm vi

`scripts/migrations/marketplace_bundle_rollout.py` tạo publication mới từ definition hiện tại cho các Note Type đang `published/unlisted` nhưng chưa có `current_release_id`, đồng thời đăng template riêng của tác giả. Không có DDL, sửa note, field, mapping, deck hoặc tiến độ học. Không tự pin install cũ, không phát sinh order/thu tiền, không publish Note Type private.

Tool chỉ chấp nhận MySQL loopback, đúng database truyền bằng `--expect-database` và đúng server UUID trong plan. App chạy `audit_mode=True`, tắt startup maintenance. Không dùng `db.create_all()` hoặc `flask db stamp`.

Plan có preimage và checksum. Nếu row đã đổi từ lúc lập plan, apply từ chối. Publication của cả batch commit trong một transaction; template dùng chung giữa nhiều gói được đăng một lần. Receipt được lưu trước commit để có release ID khi đối chiếu; kết luận commit thành công dựa trên exit code thành công và lượt `verify`, không chỉ dựa vào việc file receipt tồn tại.

Metadata override được đọc từ JSON review riêng, chỉ cho phép metadata/taxonomy; không được thay owner, price, field hay mapping. Manifest `marketplace_bundle_rollout_manifest_20261021.json` là cho **4 ID local đã kiểm tra**, không được coi là mapping áp dụng được cho mọi database.

## Lệnh đã chạy trên Windows

Từ repo root, `.env` trỏ MySQL local. Plan/receipt ở `output/` bị Git ignore và có preimage nội dung template; không đưa lên repository công khai.

```powershell
.\.venv\Scripts\python.exe scripts/migrations/marketplace_bundle_rollout.py plan --expect-database nihongo --free-unpriced-templates --metadata-overrides scripts/migrations/marketplace_bundle_rollout_manifest_20261021.json --plan output/marketplace-rollout-local-plan-20261021.json

.\.venv\Scripts\python.exe scripts/migrations/marketplace_bundle_rollout.py apply --expect-database nihongo --plan output/marketplace-rollout-local-plan-20261021.json --dry-run --receipt output/marketplace-rollout-local-dry-run-20261021.json

.\.venv\Scripts\python.exe scripts/migrations/marketplace_bundle_rollout.py apply --expect-database nihongo --plan output/marketplace-rollout-local-plan-20261021.json --receipt output/marketplace-rollout-local-applied-20261021.json

.\.venv\Scripts\python.exe scripts/migrations/marketplace_bundle_rollout.py verify --expect-database nihongo --plan output/marketplace-rollout-local-plan-20261021.json
```

`--free-unpriced-templates` là lựa chọn giá rõ ràng của operator cho template chưa có offer riêng. Đã chọn miễn phí cho rehearsal vì cả 4 gói local đang miễn phí. Với catalog paid hoặc chưa được duyệt giá, phải chuẩn bị quyết định giá riêng; không chạy cờ này để tự biến hàng chưa định giá thành miễn phí. Template có offer riêng từ trước giữ giá offer đó.

Mỗi receipt cần tên file mới: tool không ghi đè. Apply lại cùng plan, sau khi đã thành công, trả `already_applied=true` và verify các release hiện hữu.

## Kết quả local

| Note Type | Field | Application | Complete release |
|---|---:|---:|---|
| 文法N1 | 15 | 1 | `45a61fd0-a68e-4745-8365-185727d4d6de` |
| En4Everyone | 19 | 1 | `342fe0d0-c08f-403a-9b68-2393c15cc0aa` |
| Trắc nghiệm | 6 | 1 | `91b5df0f-10b6-458f-b5d9-61af64142adf` |
| Flama Standard Vocabulary | 16 | 1 | `18367c29-0b10-4b8b-8d8a-ddc3bb0cc4c9` |

4 template tương ứng đã có listing `published/free/0`, tác giả vẫn là owner gốc. Cộng mẫu Kanji có trước, chợ giao diện có 5 listing. API detail và `POST /api/marketplace/note-types/<id>/templates/<template_id>/preview` đều trả 200 khi chạy bằng test client trên chính DB local.

Không ghi note hoặc tiến độ học; kiểm tra count note/card ngay trong transaction không đổi. Inventory đầu lượt có 41.534 note, lần đọc cuối có 41.544 vì DB dùng chung còn writer ngoài batch; không coi hai lượt đọc đó là một snapshot bất biến. Giữ 21 install cũ, 1 subscription có trước và 4 payment order. 21 install vẫn là legacy; không dùng publication mới để tự viết lại lịch sử của họ. 20 template copy cũ đã được xử lý provenance riêng như dưới đây.

## Legacy provenance đã apply trên local

Đã review plan có 20 mapping duy nhất, không có mapping chưa giải quyết; checksum `d9f26471463380fba42e183ee451eafbf064ecdc417b5b092c58bac06385d90b`. Công cụ chỉ đổi provenance: `origin=market_copy`, `source_template_id` về tác giả gốc, giữ `source_version_id=NULL`. Không dựng subscription hay giả định release đã nhận. Một install đã xóa local không được tái tạo khi chưa biết release lịch sử.

```powershell
.\.venv\Scripts\python.exe scripts/migrations/marketplace_legacy_provenance.py apply --expect-database nihongo --plan output/marketplace-legacy-provenance-plan-20261021.json --dry-run --receipt output/marketplace-legacy-provenance-dry-run-20261021.json

.\.venv\Scripts\python.exe scripts/migrations/marketplace_legacy_provenance.py apply --expect-database nihongo --plan output/marketplace-legacy-provenance-plan-20261021.json --receipt output/marketplace-legacy-provenance-applied-20261021.json

.\.venv\Scripts\python.exe scripts/migrations/marketplace_legacy_provenance.py verify --expect-database nihongo --plan output/marketplace-legacy-provenance-plan-20261021.json
```

Dry-run, apply và verify đều đạt: 20 template đổi provenance; checksum nội dung, mapping, note và tiến độ giữ nguyên trong transaction. Apply lặp với receipt mới `output/marketplace-legacy-provenance-repeat-20261022.json` trả `changed_templates=0`, `already_applied=true`, `verified_templates=20`. Runtime chặn bán lại cả trước/sau cutover, giữ quyền đã nhận và cho sửa nội dung cá nhân; UI thể hiện rõ bản cũ chưa biết release và không cho update/reset tự động. Nhận bản hiện tại từ chợ tạo canonical copy riêng. Xem [thiết kế và rollback legacy](../architecture/marketplace-legacy-provenance-cutover-2026-10-21.md).

## Rollback

Đã kiểm chứng hai loại trên schema MySQL tạm: apply rồi rollback transaction bằng `--dry-run`; và apply đã commit → rollback publication settings đã commit → tạo plan mới và apply lại. Có hai Note Type dùng chung một template; chỉ tạo một template release và retry không nhân bản release.

Để rollback một batch đã apply, giữ plan gốc và dừng writer theo quy trình vận hành của môi trường đó:

```powershell
.\.venv\Scripts\python.exe scripts/migrations/marketplace_bundle_rollout.py rollback --expect-database nihongo --plan output/marketplace-rollout-local-plan-20261021.json --receipt output/marketplace-rollout-local-rollback-NEW.json
```

Rollback phục hồi metadata và Note Type current pointer trước rollout, phục hồi offer cũ; publication row mới trở về private với head rỗng. Giữ mọi immutable release/audit đã tạo. Không xóa đơn hàng, license hoặc lịch sử. Nếu cấu trúc, nội dung template, quyền sở hữu hoặc giá đã đổi thì dừng để review thay vì ghi đè. Sau rollback cần tạo **plan mới** nếu muốn apply lại, vì publication row/history đã tồn tại.

Trên DB local chính, trạng thái cuối vẫn là **đã apply**. Chưa rollback batch chính; rehearsal rollback sau commit được thực hiện trên schema tạm đã xóa.

## Trước production

1. Các lỗi đã xác nhận trong review và provenance của 20 copy local đã xử lý. Chạy các probe MySQL `scripts/probe_note_type_bundle_mysql.py`, `scripts/probe_marketplace_quote_access_mysql.py`, `scripts/probe_legacy_template_provenance_mysql.py` trên môi trường kiểm thử phù hợp; không dùng kết quả local để suy ra inventory production.
2. Backup nhất quán, rehearsal trên bản sao database production, inventory lại missing releases/metadata/offers/installs. Dùng đúng procedure dừng writer trong [Operations Architecture](../ops/ARCHITECTURE.md).
3. Đảm bảo migration marketplace/release cần thiết đã được apply bằng Alembic. Kiểm tra actual columns; không nâng revision bằng stamp để né schema thiếu.
4. Review ID, metadata và từng giá template. Tạo plan mới cho đúng database/server; không tái sử dụng plan local. Tool hiện chỉ hỗ trợ loopback, ví dụ operator chạy trên host database hoặc qua tunnel đã cấu hình.
5. Chạy dry-run, apply, verify; kiểm tra detail, standalone catalog, preview, mua paid thật/sandbox, webhook và doanh thu nhiều tác giả. Hiện PayOS mới được mock trong kiểm thử.

Chưa chạy bất kỳ bước nào trên production trong lượt này.
