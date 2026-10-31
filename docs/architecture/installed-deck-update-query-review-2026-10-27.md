# Review query trang cập nhật deck — issue #259

Ngày: 2026-10-27. Chế độ: INVESTIGATE. MySQL local 8.0.40.
Issue: <https://github.com/TrinhChung/Flama/issues/259>.

> Bằng chứng lịch sử cho luồng release/rebase trước Published Base, được
> [kế hoạch chuyển đổi](NOTE_LEVEL_VERSIONING_PLAN_2026-10-28.md) tham chiếu.
> Published Base đã [cutover trên production](NOTE_PUBLISHED_BASE_PRODUCTION_CUTOVER_2026-10-30.md);
> báo cáo này không phải số đo hiệu năng của runtime Base hiện tại.

## Kết luận và phạm vi xác minh

Đã xác nhận query lấy diff đọc thừa lịch sử release rất lớn, kể cả khi bản cài
chỉ cập nhật lên phiên bản liền sau. Luồng bỏ qua nhiều release còn thực hiện
gộp lịch sử lặp lại và phân trang sau bước gộp. Frontend chặn toàn trang cho đến
khi cả API trạng thái và diff hoàn tất.

Review chỉ đọc source và MySQL local; không sửa application code, schema, index,
dữ liệu, cấu hình MySQL hay cập nhật GitHub issue. Các probe dùng transaction
READ ONLY; query nặng được giới hạn 15 giây bằng cấu hình session của probe.
Ngưỡng này không phải timeout đang được chứng minh trên production.

Chưa đối chiếu được đúng installation Tettein1 của tài khoản báo lỗi. Các phép
đo dưới đây dùng dữ liệu hiện có trên local, không phải số đo production của
tài khoản đó. Tên listing local không có chuỗi `Tettei`; không suy diễn rằng deck
N1 local chính là Tettein1 trong issue.

## Luồng và bảng thực sự tham gia

Frontend `useInstalledDeckUpdate.ts:90` gọi song song:

1. GET `/api/marketplace/installations/{installId}/updates` →
   `deck_install_rebase_service.get_update_status()`.
2. GET `/api/marketplace/installations/{installId}/updates/{releaseId}/diff?limit=100`
   → `deck_install_rebase_service.get_update_diff()`.
3. Khi status báo unread, effect tại `useInstalledDeckUpdate.ts:182` gửi
   `mark-seen`; backend lại gọi `get_update_status()` sau khi cập nhật seen pointer.

| Bảng | Vai trò trong luồng đọc |
| --- | --- |
| `deck_installs` | Xác thực ownership, lấy applied/seen release và trạng thái overlay |
| `deck_marketplace_items` | Lấy current release của listing ở API status |
| `deck_releases` | Metadata release, parent, published status, thống kê đã lưu |
| `deck_release_changes` | Atomic history; dữ liệu trước/sau và hash theo `change_key` |
| `deck_release_entity_memberships` | Lọc field definitions còn tồn tại ở release |
| `deck_install_rebases` | Tìm rebase có conflict cho API status |

Không thấy query đầu trang JOIN `notes`, `cards`, `card_progress` hay
`review_events`. Các relationship liên quan không tự eager-load những bảng đó.
JOIN cần xem lại là `deck_release_changes` → `deck_releases` trong nhánh direct;
nhánh gộp nhiều phiên bản còn self-join CTE `first_change`/`last_change`.

## Findings

### P1 — Nhánh direct đọc cả baseline vì chỉ giới hạn sequence ở bảng changes

- **Observed:** `release_changes_query()` lọc item/status trên `deck_releases`,
  nhưng chỉ lọc khoảng sequence trên `deck_release_changes`. `LIMIT` nằm sau
  JOIN, lọc và sort. Nhánh direct cũng dùng query tổng quát này, dù target đã
  được kiểm tra item/published tại `_require_target_release()`.
- **Evidence:** `app/repositories/deck_install_rebase_repository.py:162`,
  `:428`; `app/services/deck_install_rebase_service.py:197`, `:453`.
  `EXPLAIN ANALYZE` trên deck N1 local cho thấy đọc 2 release; index lookup
  changes trả trung bình 81.340 dòng × 2 vòng = **162.680 dòng** trước khi lọc
  còn **232**. Chỉ 101 dòng được trả về cho ứng dụng.
- **Potential concern:** JOIN xác định scope hợp lệ cho hàm tổng quát nhưng
  mở scope quá rộng cho direct update. Bảng release không được chặn khoảng
  sequence trước khi đọc changes của baseline lớn.
- **Impact:** Query của trang đầu đọc gần toàn bộ lịch sử deck; cache ấm vẫn
  phải thực hiện hơn 500 nghìn lượt đọc trang InnoDB. Nhiều người mở đồng thời
  sẽ nhân lượng công việc này.
- **Unknowns:** Plan và số dòng thực tế trên Tettein1 production chưa được đo.

SQL hiện tại, rút gọn projection để dễ đọc:

```sql
SELECT c.*
FROM deck_release_changes c
JOIN deck_releases r ON r.id = c.release_id
WHERE r.deck_item_id = :item_id
  AND r.status = 'published'
  AND c.release_sequence_no > :base_sequence
  AND c.release_sequence_no <= :target_sequence
ORDER BY c.release_sequence_no, c.id
LIMIT 101;
```

Các SELECT đối chứng giữ nguyên projection đầy đủ của ORM và dữ liệu:

| SELECT, cùng dữ liệu N1 sequence 1 → 2 | Thời gian cache ấm | Δ logical page reads | Δ physical reads |
| --- | ---: | ---: | ---: |
| Hiện tại, lần đo plan | 455,84 ms | 501.722 | 0 |
| Thêm giới hạn sequence cho bảng release | 4,44 ms | 741 | 0 |
| Direct: chỉ lọc `c.release_id = target.id` | 5,26 ms | 739 | 0 |
| Hiện tại, lần đối chiếu kết quả | 410,55 ms | 501.722 | 0 |
| Direct theo target ID, lần đối chiếu | 3,49 ms | 740 | 0 |

Đã assert **101 dòng đầy đủ bằng nhau**, bao gồm before/after JSON, giữa query
hiện tại và SELECT theo target ID. Đây là đối chứng đọc, chưa phải bản sửa đã
tích hợp hoặc kiểm chứng mọi trường hợp cursor/filter/permission.

Ở lần đo service trước đó, toàn bộ `get_update_diff()` mất 1,943 giây, 8 SELECT;
riêng SELECT page mất 1,900 giây. Δ logical reads 530.733, physical reads 156.
Không gọi lần này là cold-cache benchmark: không flush cache và không kiểm soát
các hoạt động khác trên máy.

### P1 — Diff gộp phân trang sau window/self-join trên toàn khoảng lịch sử

- **Observed:** `_collapsed_release_changes_selectable()` đưa cả before/after
  JSON, metadata và hash vào CTE, chạy hai `row_number()` theo thứ tự ngược nhau,
  rồi self-join để lấy trước/sau của mỗi key. Query page mới áp cursor và LIMIT
  bên ngoài kết quả collapse. Filter cuối trang không biến bước collapse thành
  công việc chỉ xử lý 100 dòng.
- **Evidence:** `app/repositories/deck_install_rebase_repository.py:197`,
  `:222`, `:365`, `:410`. Probe helper với khoảng baseline 0 → 2 trên dữ liệu
  N1 hiện có: 162.680 atomic rows, 162.448 distinct keys; yêu cầu 101 dòng nhưng
  bị dừng sau **15,107 giây**, error 3024. Phát sinh 2 disk temporary tables,
  Δ logical reads 669.107, physical reads 2.098.
- **Potential concern:** Giới hạn bộ nhớ phía Python không giới hạn công việc
  sort/materialize/self-join của MySQL. Hai JSON payload được mang theo từ sớm
  cũng không cần thiết cho phần chỉ đếm bằng hash. EXPLAIN ước lượng derived
  chỉ 113 dòng, dùng temporary/filesort và hash join; không có actual plan hoàn
  tất cho query lớn vì đã dừng ở ngưỡng probe.
- **Impact:** Khoảng lịch sử lớn vẫn có thể timeout ngay trang đầu; sang trang
  sau tiếp tục dựng collapse từ đầu. Query summary cũng dùng cùng helper.
- **Unknowns:** Probe 0 → 2 là workload của helper trên dữ liệu thật, **không**
  phải installation đang được báo lỗi. Chưa chứng minh đây là nhánh Tettein1
  đang đi qua hoặc chỉ ra duy nhất một thao tác gây toàn bộ 15 giây.

Đã thử SELECT đối chứng chỉ rank ID/sequence/key/operation/hash và lấy JSON sau
LIMIT. Kết quả trên deck nhỏ khớp đủ 74 dòng với query cũ, nhưng workload N1
0 → 2 **vẫn vượt 15 giây**. Vì vậy, bỏ JSON khỏi CTE riêng lẻ chưa phải giải
pháp đủ; cần kiểm tra cả window, self-join, cardinality và phạm vi lịch sử.
Không được đặt LIMIT lên atomic history trước khi xác định first/last event:
làm vậy có thể sai giá trị base và bỏ lọt thay đổi tự triệt tiêu qua các release.

### P1 — Một lần mở trang tính lại effective diff nhiều lượt

- **Observed:** Với non-direct update, API status gọi summary để chỉ lấy
  `change_count`. Helper này vẫn tính thêm added/modified/removed/entity counts,
  bao gồm window thứ ba để đếm entity. API diff chạy collapse lấy page rồi chạy
  summary cùng khoảng thêm lần nữa ở trang đầu. Khi unread, mark-seen trả status
  và tiếp tục chạy lại summary.
- **Evidence:** `app/services/deck_install_rebase_service.py:256`, `:274`,
  `:515`, `:1139`; `app/repositories/deck_install_rebase_repository.py:308`,
  `:335`; `useInstalledDeckUpdate.ts:90`, `:96`, `:182`.
  `InstalledDeckUpdatePage.tsx` lấy số liệu hiển thị từ `firstPage.summary`,
  không đọc `updatesQuery.data.change_count`.
- **Potential concern:** Hai GET đầu trang tương đương **3 lần collapse**;
  thêm mark-seen có thể thành **4 lần**. Đây là đọc lặp, không phải N+1 theo note.
- **Impact:** Lặp CPU/I/O cho cùng khoảng immutable history, có thể đồng thời
  chiếm nhiều connection. Status vốn dùng cho UI điều khiển cũng bị chặn bởi
  phép thống kê nặng.
- **Unknowns:** Lượng đồng thời và mức tranh chấp connection production chưa đo.

### P2 — Loading toàn trang có thể che lỗi và kéo dài cảm giác treo

- **Observed:** `InstalledDeckUpdatePage.tsx:67` kiểm tra một trong hai query
  pending trước khi kiểm tra error ở `:74`. API client truyền AbortSignal khi
  hủy nhưng không đặt deadline request tại `shared/api/client.ts:158`.
  React Query mặc định retry một lần tại `main.tsx:15`.
- **Evidence:** Source nêu trên và hai query độc lập trong hook.
- **Potential concern:** Một request đã lỗi nhưng request còn lại pending thì
  trang vẫn hiện loading; status đã xong cũng chưa render nội dung. Request còn
  chờ phụ thuộc timeout của hạ tầng/browser thay vì deadline tại API client.
- **Impact:** Người dùng thấy spinner kéo dài, không xem được phần đã tải hoặc
  lỗi có thể xử lý ngay.
- **Unknowns:** Chưa thu network trace từ browser của tài khoản báo lỗi; không
  khẳng định spinner thực tế tồn tại vô hạn hoặc production có cùng timeout.

## Những phần phụ chưa phải nút thắt đã đo

- API status direct: 5 SELECT, lần service đầu 369 ms, chỉ 190 logical reads.
  Chưa có bằng chứng phải tối ưu phần này trước query page.
- Tên field được dựng cho applied và target release: 2 history SELECT và
  2 membership SELECT trên trang diff. N1 local trả 80 schema atoms ở mỗi
  mốc và 16 memberships mỗi lần; mỗi SELECT chỉ vài ms trong lần đo chính.
  Không thể bỏ schema base tùy tiện vì field bị xóa ở target vẫn cần tên cũ.
- Không thấy lỗi cú pháp SQL ở hai GET trên local. Error 3024 của probe là do
  ngưỡng dừng đã chủ động đặt cho phép review.

## Môi trường, giới hạn và bước xác minh tiếp

- MySQL 8.0.40, DB local qua loopback. `my.ini` đặt pool size 128M và 8 instances;
  runtime thực tế **1 GiB, 8 instances, chunk 128 MiB**. Persisted buffer-pool
  variables không có dòng. Không resize hoặc restart để làm hai trạng thái khớp.
- Page-read metrics lấy chênh lệch GLOBAL STATUS; có thể gồm hoạt động đồng thời.
  Lần đo lặp direct cũng cho ~501.722 → 740 logical reads, nhưng không dùng số
  đo local đơn lẻ để dự báo SLA production.
- Các index đã tồn tại được đọc bằng SHOW INDEX; EXPLAIN xác nhận có dùng index
  `uq_deck_release_changes_release_key`. **Dùng index không ngăn được đọc dư
  162 nghìn dòng**. Review không đề nghị hay tạo index mới.
- Ưu tiên xác minh/sửa phạm vi query direct, giảm thống kê lặp trên đường mở trang,
  sau đó xử lý query collapse lớn và trạng thái loading. Chưa có bản sửa full
  multi-release đủ cơ sở để coi đã đạt yêu cầu.
- Cần lấy đúng install/applied/current release và request timings của báo cáo
  Tettein1 để xác định các finding nào đang gây lỗi production.
- Chưa chạy unit suite vì không đổi application code. Đã chạy service read-only,
  EXPLAIN ANALYZE và assertion đối chiếu kết quả SELECT. Test hiện có về skipped
  release summary (`tests/test_deck_install_rebase_flow.py:691`) kiểm tra semantics
  và tránh hydrate toàn khoảng vào Python; nó không chứng minh MySQL đọc ít
  dòng hay page 100 có latency tốt trên dataset lớn.
