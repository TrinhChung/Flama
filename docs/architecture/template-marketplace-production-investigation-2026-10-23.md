# Chợ template trống trên production

Ngày: 2026-10-23, Asia/Tokyo. Mode: INVESTIGATE. Kiểm tra trực tiếp VPS qua SSH alias `chung_hostinger_vps`, database `flama`, MySQL 8.0.46; mốc đọc dữ liệu khoảng 21:01–21:03 JST.

**Cập nhật sau yêu cầu xử lý tiếp:** đã rollout production lúc 21:23 JST, chợ trả đủ 7 template. Xem kết quả và bằng chứng ở cuối tài liệu. Các mục điều tra bên dưới ghi nhận trạng thái trước rollout.

## Kết luận kiểm tra ban đầu

Production còn đủ 7 template đang gắn vào 4 Note Type công khai, nhưng không có standalone listing `published`. Catalog lọc đúng điều kiện hiện hành nên trả danh sách rỗng. Schema và code bundle đã có; dữ liệu publication cũ chưa được chuyển sang cơ chế mới. Không có bằng chứng mất template.

Local là database khác: đã chạy publication rollout ngày 2026-10-21, hiện có 4 complete Note Type releases và 5 standalone listings. Không dùng kết quả local để kết luận production đã rollout.

## Phạm vi và nguồn dữ liệu

- Chỉ đọc production bằng SQLAlchemy connection, `SET TRANSACTION READ ONLY` và `START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY`; kết thúc bằng rollback. Không import Flask app hoặc gọi startup trên VPS.
- Không DDL/DML, publish, đổi giá, restart service hoặc chạy rollout trên production.
- Symlink `/opt/flama/current` trỏ release `d385295b7171951b802656622be6fe8a28afa5a1`; Alembic ở `20261020_000071`.
- SHA-256 của repository catalog, service bundle publication và script rollout trên VPS trùng các file tương ứng trong checkout local.

| Trạng thái có thẩm quyền | Nơi lưu | Luồng ghi/đọc liên quan |
|---|---|---|
| Nội dung, tác giả template | `templates` | Template library/content services |
| Template gắn vào Note Type | `study_applications`, `status_code=ACTIVE` | Attachment services; bundle publication |
| Listing riêng và release head | `template_publications` | `template_marketplace_service.stage_listing`; repository catalog |
| Publication đầy đủ của Note Type | `note_types.current_release_id`, `note_type_releases` | `note_type_release_service.stage_publication` |

## F1 — Dữ liệu publication production chưa được rollout

- **Observed:** 4 Note Type `published`, tất cả có `current_release_id=NULL`; bảng `note_type_releases` có 0 row. 7 active attached templates đều `authored`, chưa archived, không có `source_template_id`, và đều thuộc tác giả của Note Type. Có 4 row `template_publications`, tất cả `private/free`, đã có template release head. Ba template còn lại chưa có publication row. Tổng `template_releases` là 8; có release không đồng nghĩa đã có listing trên chợ.
- **Evidence:** SELECT trực tiếp trên production; điều kiện tại [`template_marketplace_repository.py`](../../app/repositories/template_marketplace_repository.py), hàm `listed_conditions()` và `catalog()`. [`TemplatePublication`](../../models/template_publication.py) tách listing khỏi release. [`migration 000069`](../../migrations/versions/20261019_000069_add_template_marketplace_listing.py) thêm `marketplace_status` mặc định `private`, không tự công khai các row cũ.
- **Potential concern:** Deploy code/schema không thực hiện publication dữ liệu cũ. Công bố Note Type theo luồng mới gọi `stage_template_listings()` rồi `stage_publication()` trong [`share/note_types.py`](../../app/services/share/note_types.py); các Note Type được công bố từ trước không tự chạy lại luồng đó.
- **Impact:** Chợ template trống dù Note Type và template vẫn còn. Complete Note Type release cũng chưa được thiết lập.
- **Unknowns:** Chưa thực hiện production rollout hoặc kiểm chứng giao diện sau rollout; chưa có quyết định giá standalone mới cho các template chưa có offer.

| Note Type công khai | Active templates | Template có release head | Listing published | Complete Note Type release |
|---|---:|---:|---:|---:|
| En4Everyone | 2 | 0 | 0 | 0 |
| Flama Standard Vocabulary | 3 | 3 | 0 | 0 |
| Trắc nghiệm | 1 | 0 | 0 | 0 |
| 文法N1 | 1 | 1 | 0 | 0 |
| Tổng | 7 | 4 | 0 | 0 |

## F2 — Metadata production khác local

- **Observed:** Cả 7 template có description; 3 template thiếu `primary_category`: “Gõ cách đọc”, “Gõ chép chính tả”, “Gõ nghĩa”. Local chỉ có 4 active templates trong 4 Note Type tương ứng, nên inventory local không đại diện production.
- **Evidence:** SELECT trực tiếp production; yêu cầu metadata trong [`template_marketplace_service.py`](../../app/services/template_marketplace_service.py), `_missing_requirements()` và `stage_listing()`.
- **Potential concern:** Dùng nguyên manifest local hoặc chỉ đổi `marketplace_status` sẽ bỏ qua inventory, metadata và quy trình publication production.
- **Impact:** Cần review đủ 7 template trước khi thực hiện publication. [`marketplace_bundle_rollout.py`](../../scripts/migrations/marketplace_bundle_rollout.py) đã có quy trình plan/dry-run/apply/verify với kiểm tra database/server và preimage; không nên thay bằng UPDATE trạng thái hàng loạt.
- **Unknowns:** Metadata và giá standalone sẽ được chọn khi chuẩn bị rollout production. Bốn Note Type hiện đều free; điều này không tự xác định giá standalone của từng template.

## Quan sát vận hành riêng

`flama.service` và `flama-connect.service` đều `inactive/dead` khi kiểm tra. Journal ghi `flama.service` dừng thành công lúc 20:58:29 JST, không phải lỗi khởi động được xác nhận trong lượt này. Không restart hoặc suy đoán nguyên nhân dừng. Truy cập endpoint công khai từ VPS trả HTTP 403, nên không coi đó là phép kiểm chứng API catalog đã đăng nhập. Kết luận catalog rỗng dựa trên database và predicate đã triển khai.

## Tài liệu và giới hạn tiếp theo

[Runbook rollout local](../runbooks/MARKETPLACE_BUNDLE_LOCAL_ROLLOUT_20261021.md) đã ghi rõ chưa chạy production. [Thiết kế bundle](note-type-template-bundle-design-2026-10-21.md) mô tả việc đăng template của tác giả cùng Note Type, giữ original identity và giá riêng. Chẩn đoán hiện tại xác nhận khoảng trống nằm ở publication dữ liệu production; chưa thay đổi ứng dụng hoặc dữ liệu để sửa khoảng trống này.

## Rollout production sau khi được yêu cầu xử lý tiếp

Chủ sản phẩm yêu cầu tiếp tục xử lý sau kết luận điều tra. Lượt xử lý dùng các service publication đã triển khai, không sửa schema hoặc application code, không deploy release mới. Release vẫn là `d385295b7171951b802656622be6fe8a28afa5a1`.

- Review lại đúng 4 Note Type và 7 template trên production. Giữ `free/0` cho 4 gói đang miễn phí và 4 offer cũ; chọn `free/0` cho 3 template chưa có offer trong các gói miễn phí này.
- Bổ sung `primary_category=Luyện gõ` cho “Gõ cách đọc”, “Gõ nghĩa”, “Gõ chép chính tả”. Bổ sung taxonomy bắt buộc còn trống cho Trắc nghiệm và Flama Standard Vocabulary, giữ tên, category hiện hữu, field, mapping và giá gói.
- Sao lưu nhất quán toàn bộ 116 bảng InnoDB bằng `mysqldump --single-transaction`. Khôi phục đầy đủ vào schema diễn tập riêng, rồi kiểm tra dry-run, publication, HTTP detail/preview, rollback đã commit, áp dụng lại và idempotency. Đã xóa đúng schema diễn tập sau khi production qua kiểm tra.
- Lập plan mới từ database/server production, kiểm tra preimage và checksum. Không tái sử dụng plan local. Checksum plan production: `a0babc6742393f0248cf985f8b6be627f1c8db6a6b46504dc39eb89a07b4c418`.
- Dùng khóa `/opt/flama/deploy.lock`, dừng HTTP/Connect/study writers và các timer/one-shot liên quan. Sao lưu riêng 7 bảng publication sẽ ghi ngay trước thay đổi. Dry-run production và apply dùng cùng plan; apply commit trong một transaction.
- Worker chạy độc lập SSH bằng systemd unit `flama-template-market-rollout-20261023.service`; khôi phục các service/timer vốn đang chạy trong `finally`. Journal ghi quiesce lúc 21:23:08, verification và services restored lúc 21:23:36 JST; unit kết thúc thành công lúc 21:23:38.

### Kết quả xác minh

| Note Type | Complete release mới | Active templates trên chợ |
|---|---|---:|
| 文法N1 | `7e673da7-50b0-4e33-a242-3d0f9e230f58` | 1 |
| En4Everyone | `fa6b9cfe-313d-46f7-a96b-492c6857e251` | 2 |
| Trắc nghiệm | `b00f0452-fb59-4c24-b5bc-e4b7b564f926` | 1 |
| Flama Standard Vocabulary | `d624c199-9dff-4f8a-ade6-d2ad6f6c0f6b` | 3 |

- API catalog trên Gunicorn đang chạy, gọi qua loopback với Host `api.flama.vn` và session xác thực, trả **HTTP 200, total=7**, header `Cache-Control: private, no-store`.
- Một lượt kiểm chứng độc lập sau commit kiểm tra cả 7 template detail và preview đều HTTP 200; 4 Note Type detail đều HTTP 200. Catalog cũng trả 7 với viewer tác giả và viewer khác.
- Trong cửa sổ đã dừng writer, count + tổng CRC32 + XOR CRC32 trên toàn bộ cột của 12 bảng được bảo vệ khớp trước/sau dry-run và trước/sau commit: notes, field_defs, study_applications, decks, note_type_installs, template_subscriptions, payment_orders, payment_order_items, payment_entitlements, user_balance_transactions, review_events, study_progress_subjects. Gồm 41.613 notes, 135.159 review events và 45.587 progress subjects. Không gán release giả cho install cũ hoặc tạo receipt/order mới.
- API, Connect, study worker và các timer vốn hoạt động đều được khôi phục. Trạng thái `inactive` của hai service trong phần điều tra là quan sát cũ trước lượt xử lý này.

### Bằng chứng riêng và khôi phục

Artifact có preimage/nội dung nguồn được giữ riêng trên VPS ở `/root/flama-template-rollout-20261023-v1/`, thư mục mode 0700, plan/receipt/backup mode 0600; không đưa dump hoặc plan vào Git.

- Full backup: `production-before.sql.gz`, 243.787.412 bytes, SHA-256 `215488e28c64daf9ef8b591753c3166f46ed55d132fcb72abb9dc32cb597ec12`; đã kiểm tra gzip và khôi phục đầy đủ trên MySQL.
- Backup sát thời điểm apply: `production-touched-before.sql.gz`, SHA-256 `681e137b6a3409ef50262ea9d6bd092b440b878470353a9d184aefa119066742`.
- `production-plan.json`, `production-precommit-receipt.json`, `production-result.json`, `production-independent-verification.json`, `production-live-http.json`, `production-protected-before.json`, service preimage/after và `rehearsal-result.json` lưu bằng chứng tương ứng. `rollout_operator.py` là wrapper vận hành riêng của lượt này, gọi script/service đã triển khai.
- Rollback publication đã được diễn tập trên bản sao với plan của chính bản sao: dùng `marketplace_bundle_rollout.rollback`, giữ immutable release/audit history, khôi phục publication pointers/settings và taxonomy Note Type; khôi phục thêm 3 category template từ preimage. Với production, phải giữ khóa, dừng writer, dùng **production plan** và kiểm tra các guard chống ghi đè thay đổi mới trước khi rollback. Không restore full dump lên dữ liệu đang có writer hoặc giao dịch mới.

Giới hạn xác minh: đã kiểm tra origin HTTP và Flask routes, chưa chụp ảnh trình duyệt qua Cloudflare và không thực hiện giao dịch PayOS thật. Đây là rollout publication miễn phí; không thay đổi payment flow.
