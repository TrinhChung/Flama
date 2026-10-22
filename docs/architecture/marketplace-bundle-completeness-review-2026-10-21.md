# Review phần còn thiếu của Marketplace bundle

Ngày: 2026-10-21, Asia/Tokyo. Review trên checkout hiện tại và MySQL 8.0.40 local. Phần review không sửa application code. Sau yêu cầu tiếp theo của chủ sản phẩm, đã chạy publication rollout trên DB local chính; kết quả và phạm vi được ghi riêng ở cuối tài liệu.

Luồng chính đã có: publish inline template của mình, tham chiếu release gốc của người khác, giá gói riêng của tác giả Note Type, cộng phí template bên ngoài, bỏ phí đã có quyền, cấp quyền theo snapshot và chia doanh thu cho tác giả gốc. Review ban đầu tìm thấy bốn lỗi luồng và một khoảng trống chuyển dữ liệu cũ. Các mục 1–5 bên dưới giữ lại bằng chứng tại thời điểm phát hiện; xem trạng thái sửa ngày 2026-10-22 ngay sau đây.

## Trạng thái sau xử lý — 2026-10-22

| Finding | Kết quả hiện tại |
|---|---|
| 1. Quote cũ thu lại phí template | Reconcile cả trước checkout/free receipt và sau khi cấp quyền. Khóa theo buyer; kiểm tra quyền bằng current read trước fulfillment. Link cũ được hủy; giao dịch đã trả tiền trong race được giữ `under_review`, không cấp quyền hoặc ghi thêm doanh thu. |
| 2. Quyền hết hạn/chưa hiệu lực | Standalone install, catalog và bundle dùng chung chính sách quyền hợp lệ. Khôi phục copy đã xóa vẫn miễn phí khi entitlement còn hợp lệ. |
| 3. Restore kiểm tra release mới | Khôi phục theo `applied_release_id` đã nhận, kể cả khi dependency mới không khả dụng. Legacy đã xóa mà không biết release trả lỗi rõ ràng, không tự chọn release hiện tại. |
| 4. Nhiều application cùng source | API preview nhận `application_id`; UI chọn/key theo application. License và phí vẫn deduplicate theo source gốc. |
| 5. Copy legacy thiếu provenance | Đã dry-run, apply, verify 20 copy trên MySQL local `nihongo`. Gắn nguồn gốc; giữ nguyên nội dung cá nhân, mapping, note và tiến độ. Pin lịch sử chưa biết vẫn NULL; UI khóa update/reset có thể ghi đè. |

Kiểm chứng sau sửa: 28 backend tests trong 5 file; 19 frontend tests liên quan; TypeScript và lint phạm vi sửa đạt. Ba probe MySQL riêng kiểm tra bundle/restore/occurrence, quote/access/webhook đồng thời và legacy cutover/rollback. Các schema probe được xóa sau khi chạy; provider thanh toán dùng mock. Apply legacy lặp ngày 2026-10-22 trả `changed_templates=0`, `already_applied=true`, verify đủ 20 template.

Browser dùng Chrome profile riêng, Vite port 5196 và API fixture, không tạo giao dịch trên DB chính. Đã kiểm tra drawer legacy ở 1440/390px: unknown historical release, link đúng tác giả gốc, update/auto-update/reset bị vô hiệu hóa. Detail Note Type có hai application cùng source chỉ đánh dấu một application đang xem và render đúng mapping thứ hai. Đã sửa grid co cột để các nút không bị cắt trên mobile; kiểm tra cả scroll overflow và bounding box của nút. Ảnh tại `output/playwright/marketplace-{legacy,occurrences}-{desktop,mobile}-20261022.png`. Console chỉ có cảnh báo CSP sẵn có của iframe (`frame-ancestors` qua meta và `navigate-to`), không có lỗi JavaScript ứng dụng trong các luồng này.

Các ca thanh toán đã thắng race được chuyển review để đối soát/hoàn tiền theo quy trình vận hành; không có tuyên bố tự động hoàn tiền liên đơn. Chưa deploy production hoặc chạy PayOS thật. Production cần inventory/plan riêng và diễn tập trên bản sao dữ liệu của môi trường đó. Chi tiết: [local runbook](../runbooks/MARKETPLACE_BUNDLE_LOCAL_ROLLOUT_20261021.md), [legacy cutover](marketplace-legacy-provenance-cutover-2026-10-21.md).

Kiểm tra trước commit ngày 2026-10-22 dùng checkout riêng chỉ chứa phạm vi Marketplace: 28 backend tests, 26 frontend tests, typecheck và 12 REST API cases trên MySQL đều đạt. Bốn probe MySQL bundle, quote/access, legacy provenance và Note Type release/DDL đạt; snapshot 301 route được kiểm tra qua entry point ứng dụng trên MySQL với startup maintenance tắt. Không kèm các thay đổi array, đồng bộ template nền hoặc UI khác đang nằm trong checkout chính.

## 1. P1 — Đơn chờ vẫn có thể thu lại tiền template đã mua

- **Observed:** Khi giá phần tác giả bằng 0, người mua mở checkout gói có template B giá 21.000đ; sau đó mua B riêng. Cài lại gói nhận miễn phí thành công, nhưng link thanh toán gói cũ vẫn tồn tại. Thanh toán link cũ sau đó vẫn được fulfillment và ghi thêm doanh thu B.
- **Evidence:** `marketplace_note_type_service.py:502-506` đi thẳng vào free receipt khi tổng mới bằng 0. Việc hủy quote cũ nằm trong `payment/checkout.py:512` và chỉ được gọi khi tạo/reuse checkout. `checkout.py:78` cũng kết thúc sớm với `PAYMENT_NOT_REQUIRED` khi giá bằng 0. Probe MySQL xác nhận `cancel_count=0`, order cũ `pending_payment`, cùng người mua/template có 2 credit, tổng gross 42.000đ.
- **Potential concern:** Đã xử lý đổi quote khi vẫn phải trả tiền, nhưng chưa bao phủ chuyển về miễn phí hoặc các quote độc lập đã phát hành trước khi quyền thay đổi.
- **Impact:** Vi phạm quy tắc chủ sản phẩm đã chốt: không thu lại phí template đã có quyền. Người mua vẫn có thể thanh toán một link đã trở nên thừa.
- **Unknowns:** Chưa có giao dịch PayOS thật để xác nhận trạng thái provider trong ca này. Probe dùng provider mock và webhook thật của ứng dụng; lỗi thiếu nhánh hủy/reconcile đã tái hiện.

## 2. P1 — Quyền hết hạn/chưa có hiệu lực được kiểm tra khác nhau giữa hai chợ

- **Observed:** Bundle quote không công nhận entitlement hết hạn hoặc có `effective_from` trong tương lai. Nhưng standalone install vẫn nhận template và trả HTTP 201, không yêu cầu thanh toán, với chính entitlement đó.
- **Evidence:** `app/repositories/template_marketplace_repository.py:29-36` chỉ lọc `status=active`. `app/services/template_marketplace_service.py:274` sử dụng kết quả này sau khi kiểm tra quyền chặt hơn đã thất bại. `template_release_service.py:291` trả subscription hiện hữu ngay. Hai ca MySQL đều có `strict_access=false`, `install_status=201`, `payment_required=false`.
- **Potential concern:** Có hai cách xác định quyền hợp lệ và chúng không tương đương. Query `purchased()` của standalone catalog cũng chỉ xét status.
- **Impact:** Hiển thị/quyền nhận template không nhất quán; entitlement chưa có hiệu lực hoặc hết hạn vẫn vượt qua bước thanh toán standalone.
- **Unknowns:** Tần suất entitlement dạng này trong production chưa được đọc. Lỗi đã tái hiện với fixture thực trên MySQL.

## 3. P2 — Khôi phục bản đã mua lại kiểm tra dependency của release mới

- **Observed:** Người mua đã nhận v1. Tác giả phát hành v1.1 có thêm template D, rồi D bị gỡ bán. Khi người mua xóa bản local và khôi phục v1, endpoint install trả 409 dù release v1 và các quyền đã mua vẫn đầy đủ.
- **Evidence:** `app/services/marketplace_note_type_service.py:502` tính quote từ current release trước khi khôi phục. Trong khi đó `app/services/note_type_release_service.py:136` đã chủ động dùng `install.applied_release_id`. Probe: endpoint trả `NOTE_TYPE_TEMPLATE_NOT_AVAILABLE`, nhưng gọi receipt service với cùng install khôi phục đúng pinned release thành công.
- **Potential concern:** Điều kiện mua mới đang chặn điều kiện khôi phục quyền cũ.
- **Impact:** Người mua có thể mất đường khôi phục một bản đã mua vì thay đổi không thuộc bản của họ.
- **Unknowns:** Chưa kiểm tra đủ mọi đường UI khôi phục; lỗi trên REST install đã tái hiện.

## 4. P2 — Preview chưa phân biệt nhiều lần áp dụng cùng một template

- **Observed:** Release giữ hai application riêng, nhưng trả cùng `templates[].id` là canonical template ID. UI và preview endpoint đều chọn bằng ID này.
- **Evidence:** `app/services/note_type_release_service.py:109-110` trả cả `id` và `application_id`; `marketplace_note_type_service.py:428` dùng `next()` theo template ID nên luôn lấy lần đầu. `frontend/src/pages/marketplace-note-type-detail/ui/SharedNoteTypeDetailPage.tsx:349` dùng `key={tmpl.id}` và selection cùng ID. Probe trả 2 application ID nhưng chỉ 1 template ID.
- **Potential concern:** Deduplicate license/fee là đúng, nhưng application có mapping/display name riêng vẫn cần được nhận diện riêng khi preview.
- **Impact:** Không xem riêng được occurrence thứ hai; duplicate React keys, hai hàng có thể cùng mang trạng thái đang chọn.
- **Unknowns:** Chưa chạy browser với fixture mapping khác nhau; dữ liệu trùng ID và nhánh chọn lần đầu đã được kiểm chứng trực tiếp.

## 5. P1 — Dữ liệu nhận từ Note Type cũ chưa có provenance template

- **Observed:** Local có 21 `NoteTypeInstall` legacy chưa pin release, trong đó 20 bản local còn tồn tại và 1 đã xóa. Mỗi bản còn tồn tại có một template `authored`, `source_template_id=NULL`. Cả 20 template được tạo cùng giây với thời điểm install. Bốn template còn khớp hoàn toàn một immutable version của template gốc; các bản khác có chỉnh sửa/nội dung khác lịch sử hiện còn lưu.
- **Evidence:** Đọc trực tiếp các bảng `note_type_installs`, `study_applications`, `templates`, `template_versions`. Artifact riêng tư: `output/marketplace-local-verification-20261021.json`. Migration `20261007_000054` thêm mặc định `authored` nhưng không phục hồi nguồn của các copy cũ. Guard `template_marketplace_service.py:52-55` chỉ xét origin/source pointer, không nhận diện một legacy copy qua install. Probe MySQL dựng đúng dạng legacy này có `NoteTypeInstall` và vẫn đăng template standalone paid 4.000đ thành công, seller là người nhận.
- **Potential concern:** Guard chống publish lại đã đúng với receipt mới, nhưng không bao phủ các copy cũ bị ghi là authored. Không thể chuyển tất cả bằng cách gán current release làm release đã mua: có các chỉnh sửa riêng và thời điểm nhận trước publication mới.
- **Impact:** Copy cũ có thể bị coi là template của người nhận khi đi qua standalone publication hoặc tái sử dụng; quyền đã nhận cũ cũng chưa có canonical subscription tương ứng. Đây là khoảng trống trước khi bật bán rộng rãi.
- **Unknowns:** Production cần inventory riêng, mapping và chính sách cutover legacy được kiểm chứng. Local chưa đổi origin, HTML/CSS, subscription hoặc `applied_release_id` của 21 install này. Không gán một version chưa có bằng chứng.

## Kiểm chứng trong lượt review

- Chạy lại probe MySQL gói nhiều tác giả hiện có, cộng các ca bổ sung ở mục 1–4: tất cả assertion kiểm chứng hành vi tái hiện đạt.
- Kết quả `status=PASS` của review probe nghĩa là **tái hiện đúng các vấn đề đã mô tả**, không phải các lỗi đã được sửa.
- PayOS client/HTTP thật bị chặn trong probe. Chỉ dùng schema sinh ngẫu nhiên có tiền tố `flama_notetype_bundle_probe_`; schema đã được drop trong `finally`.
- Kết quả chi tiết: `output/marketplace-review-remaining-results.json`; harness hiện có ở `output/marketplace_review_remaining.py` là artifact local, không phải migration production.
- Chưa xác minh concurrency credit ví, hoàn tiền nhiều tác giả hoặc giao dịch PayOS thật trong lượt này. Không đưa các điểm chưa tái hiện này thành lỗi đã xác nhận.

## Dữ liệu local đã xử lý theo yêu cầu tiếp theo

Đã chạy trên MySQL loopback, database `nihongo`. Revision hiện có `20261020_000071`, schema cần cho Note Type release/template listing đã đầy đủ. Không chạy migration `000072` về token/payment FK vì không thuộc publication rollout này.

| Hạng mục | Inventory ban đầu | Đọc cuối lượt |
|---|---:|---:|
| Note Type đang public có complete release | 0/4 | 4/4 |
| Template riêng của 4 gói được list public | 0/4 | 4/4 |
| Tổng standalone template public, gồm mẫu Kanji có trước | 1 | 5 |
| Notes toàn DB | 41.534 | 41.544 (có writer ngoài batch) |
| NoteTypeInstall cũ | 21 | 21 |
| TemplateSubscription có trước | 1 | 1 |
| PaymentOrder | 4 | 4 |

Giá của cả 4 Note Type giữ `free/0`. Các template chưa từng có giá standalone được chọn rõ `free/0` trong plan cho diễn tập local; công cụ không tự chọn giá paid. Taxonomy bổ sung cho Standard Vocabulary/Trắc nghiệm; En4Everyone đổi từ tiếng Nhật sang tiếng Anh; category Văn pháp N1 đổi từ `Templates` sang tiếng Nhật. Đây là metadata của publication mới, không sửa lịch sử cũ.

4 detail API và 4 preview API đều trả 200, quote 0, release available; standalone catalog API có đủ 4 template và tổng 5 listing. Mỗi release giữ đúng các field/application ID. Chạy lại apply trả `already_applied=true`, giữ nguyên release ID. Trong giao dịch đã kiểm tra số note/card phát sinh và toàn bộ row của các Note Type ngoài phạm vi không đổi. Các lượt đọc cách nhau thấy tổng note tăng 10; 6 note có timestamp sau audit rollout. Vì DB dùng chung vẫn có writer, không dùng hai inventory cách xa nhau làm bằng chứng số note bất biến; script rollout không có thao tác ghi `notes`, và kiểm tra bất biến nằm ngay trong transaction.

Công cụ và quy trình: [Marketplace bundle local rollout](../runbooks/MARKETPLACE_BUNDLE_LOCAL_ROLLOUT_20261021.md). Publication rollout ngày 2026-10-21 chỉ xử lý publication; phần sửa lỗi và legacy cutover đã hoàn tất local trong đợt tiếp theo, theo bảng trạng thái ở đầu tài liệu. Chưa deploy production.
