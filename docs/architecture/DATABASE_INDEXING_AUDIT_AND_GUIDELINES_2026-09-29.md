# Kiểm Kê và Định Hướng Tối Ưu Index Database (Flama MySQL)

> **Ngày lập:** 2026-09-29  
> **Mục đích:** Tài liệu hoá toàn bộ các Index hiện hành trên các bảng cốt lõi (đặc biệt là domain Study / Progress), chỉ ra các điểm đen "lạm dụng Index" (Over-indexing) gây suy giảm hiệu năng ghi (Write Amplification / B-Tree Re-sorting), và thiết lập bộ nguyên tắc chuẩn mực: **Khi nào NÊN và khi nào KHÔNG NÊN đánh Index**.

---

## 1. Vấn Đề Cốt Lõi: Lạm Dụng Index & Chi Phí Ghi (Write Penalty)

Trong cơ sở dữ liệu quan hệ (đặc biệt là MySQL InnoDB với cấu trúc Clustered Index):
1. **Mỗi Secondary Index là một cây B-Tree độc lập.** Lá của Secondary Index trỏ về Primary Key.
2. **Chi phí khi INSERT / UPDATE / DELETE:**
   - Mỗi lần một bản ghi được tạo mới: Tất cả các secondary index đều phải chèn thêm nút mới.
   - Mỗi lần một cột trong index bị UPDATE: InnoDB bắt buộc phải **xóa entry cũ và chèn entry mới** vào đúng vị trí thứ tự trên cây B-Tree.
   - Khi các trang (pages) của B-Tree bị đầy, InnoDB phải thực hiện **Page Split**, ghi đĩa ngẫu nhiên (Random I/O) và làm tăng phân mảnh dữ liệu trong Buffer Pool.
3. **Nghịch lý tại Flama:** 
   - Quá trình Decoupling (Phase 4 & Phase 5) bổ sung nhiều bảng và composite index dài tới 5–7 cột trên các bảng tiến độ học tập (vốn là các bảng có tần suất UPDATE cao nhất hệ thống).
   - Một số index được tạo ra để phục vụ cho các câu query lọc của Dashboard/Reporting nhưng lại đặt trực tiếp lên bảng giao dịch nóng (OLTP Hot-Path), gây suy giảm throughput ghi của toàn bộ luồng học thẻ (Study Session).

---

## 2. Bản Kiểm Kê Toàn Bộ Index Hiện Hành (Database Inventory)

### 2.1. Nhóm Bảng Write-Heavy / Hot-Path (Tần suất ghi và cập nhật cao)

Đây là các bảng bị ghi nhận hoặc sửa đổi **mỗi khi người dùng lật thẻ, chấm điểm (Again/Hard/Good/Easy), hoặc đồng bộ tiến độ**.

#### Bảng `card_progress` (Tiến độ thẻ truyền thống — Cập nhật liên tục theo từng lượt review)
* **Primary Key:** `id` (bigint)
* **Unique Key:**
  * `uq_card_progress_user_card` (`user_id`, `card_id`)
* **Secondary Indexes:**
  1. `ix_card_progress_user_queue_due_day` (`user_id`, `queue`, `due_day`)
  2. `ix_card_progress_user_queue_due_at` (`user_id`, `queue`, `due_at`)
  3. `ix_card_progress_user_hidden_flags` (`user_id`, `is_suspended`, `is_buried`)
  4. FK `review_event_id` (index đơn)
* **Cột bị UPDATE liên tục:** `queue`, `due_day`, `due_at`, `reps`, `lapses`, `last_reviewed_at`, `revision`, `updated_at`.
* **Đánh giá rủi ro:**
  * Cả 2 index (1) và (2) đều chứa `due_day` và `due_at`. Mỗi lần trả lời thẻ, giá trị này **chắc chắn thay đổi**, buộc B-Tree phải xóa nút và sort lại vị trí mới liên tục.
  * Index (4) trên `review_event_id` hầu như không bao giờ được query theo chiều `WHERE review_event_id = ?` trong nghiệp vụ thường ngày.

---

#### Bảng `study_progress_availability` (Bảng dự phóng hàng đợi NOTE — Cập nhật mỗi lượt học NOTE)
* **Primary Key:** `contributor_id` (bigint)
* **Foreign Key:** `fk_sp_avail_contributor_subject` (`contributor_id`, `subject_id`)
* **Secondary Indexes:**
  1. `ix_sp_avail_subject_queue_day` (`subject_id`, `subject_generation`, `normalized_queue`, `is_suspended`, `is_buried`, `due_day`, `due_at`) — *Composite index 7 cột!*
  2. `ix_sp_avail_queue_time` (`normalized_queue`, `is_suspended`, `is_buried`, `due_at`, `contributor_id`)
* **Cột bị UPDATE liên tục:** `normalized_queue`, `due_at`, `due_day`, `semantic_state_hash`, `updated_at`.
* **Đánh giá rủi ro:**
  * **Cực kỳ nặng:** Index 7 cột (1) chứa cả 3 trường biến động (`normalized_queue`, `due_day`, `due_at`).
  * **Thiếu `learner_user_id`:** Bảng này không có `learner_user_id`. Muốn lọc thẻ của một người dùng cụ thể, MySQL không thể lọc trực tiếp từ index mà phải JOIN lòng vòng.
  * **Index `ix_sp_avail_queue_time` cực kỳ nguy hiểm:** Cột đứng đầu là `normalized_queue` (độ chọn lọc cực thấp, chỉ gồm `'new'`, `'learn'`, `'review'`) và không có `user_id`. Nếu query theo queue, MySQL phải quét index của TẤT CẢ người dùng trên toàn hệ thống.

---

#### Bảng `study_progress_contributors` (Map 1 Card -> 1 Subject trong NOTE)
* **Primary Key:** `id` (bigint)
* **Unique Keys:**
  * `uq_sp_contributor_id_subject` (`id`, `subject_id`)
  * `uq_sp_contributor_generation_source` (`subject_id`, `subject_generation`, `source_progress_id`)
  * `uq_sp_contributor_live_progress` (`live_card_progress_id`)
* **Secondary Indexes:**
  1. `ix_sp_contributor_subject_current` (`subject_id`, `subject_generation`, `contributor_status`, `id`)
  2. `ix_sp_contributor_live_card` (`live_card_id`, `subject_id`)
* **Đánh giá:** Bảng này có tới 3 Unique Constraints + 2 Secondary Indexes. Dù ít update hơn `availability`, nhưng chi phí INSERT khi tạo card/note mới hoặc khi migrate là rất lớn.

---

#### Bảng `study_progress_subjects` (Đại diện cho Note của Learner)
* **Primary Key:** `id` (bigint)
* **Unique Key:**
  * `uq_sp_subject_user_note` (`learner_user_id`, `logical_note_key`)
* **Secondary Indexes:**
  1. `ix_sp_subject_live_note` (`live_note_id`)
  2. `ix_sp_subject_status_updated` (`status_code`, `updated_at`, `id`)
* **Đánh giá:** Mức độ rủi ro trung bình. `uq_sp_subject_user_note` có `learner_user_id` đứng đầu là chuẩn xác. Tuy nhiên `ix_sp_subject_status_updated` chứa `updated_at` (bị đổi liên tục mỗi khi có review thẻ thuộc Note này).

---

#### Bảng `study_progress_states` & `study_authority_subject_tokens`
* **Primary Key:** `subject_id` (bigint)
* **Indexes:**
  * `study_progress_states`: có `ix_sp_state_identity` (`algorithm_key`, `algorithm_version`, `state_schema_version`).
  * `study_authority_subject_tokens`: chỉ có PK `subject_id`.
* **Đánh giá:** Hai bảng này được thiết kế tương đối tinh gọn về index, chủ yếu truy vấn theo PK `subject_id`.

---

#### Bảng `review_events` (Nhật ký lịch sử trả lời thẻ — Append-Only)
* **Primary Key:** `id` (bigint auto_increment)
* **Secondary Indexes:**
  1. `ix_review_events_user_reviewed_at` (`user_id`, `reviewed_at`)
  2. `ix_review_events_user_card_reviewed_at` (`user_id`, `card_id`, `reviewed_at`)
  3. `ix_review_events_user_scheduler_reviewed_at` (`user_id`, `scheduler_mode`, `reviewed_at`)
  4. `ix_review_events_user_kind_reviewed_at` (`user_id`, `review_kind`, `reviewed_at`)
* **Đặc điểm:** Bảng chỉ INSERT, không UPDATE.
* **Đánh giá rủi ro:** 
  * Có tới **4 Secondary Indexes** cùng bắt đầu bằng `user_id` và kết thúc bằng `reviewed_at`.
  * Mỗi một thao tác trả lời thẻ phải ghi thêm 1 dòng vào bảng này đồng thời chèn vào **4 cây B-Tree khác nhau**! Cần điều tra xem các query thực tế có thực sự cần phân tách `scheduler_mode` và `review_kind` thành 2 index riêng biệt hay không.

---

### 2.2. Nhóm Bảng Read-Heavy / Structural (Tần suất đọc cao, tần suất sửa thấp)

Các bảng này lưu trữ cấu trúc nội dung, ít bị biến động khi người dùng học thẻ.

#### Bảng `notes`
* **Primary Key:** `id` (varchar 36)
* **Foreign Key Indexes:**
  * `deck_id`
  * `user_id`
  * `note_type_id`
* **Đánh giá:** Hợp lý cho các câu query tìm note theo deck/user.

#### Bảng `cards`
* **Primary Key:** `id` (varchar 36)
* **Unique Key:** `uq_cards_note_template` (`note_id`, `template_id`)
* **Foreign Key Indexes:**
  * `note_id` (trùng tiền tố với Unique Key, có thể là Redundant Index!)
  * `template_id`
* **Đánh giá:** Index `note_id` trên `cards` là **thừa (redundant)** vì Unique Key `uq_cards_note_template` đã có `note_id` đứng đầu (tuân theo Leftmost Prefix Rule).

---

## 3. Các Anti-Pattern Đang Tồn Tại Cần Điều Tra Sâu

```text
               +----------------------------------------------------+
               |           CÁC ANTI-PATTERN INDEX TRONG HỆ THỐNG     |
               +----------------------------------------------------+
                                      |
         +----------------------------+----------------------------+
         |                                                         |
[1. Over-indexing Bảng Ghi]                               [2. Index Thiếu Chọn Lọc]
- Composite 7 cột trên bảng availability                  - Index bắt đầu bằng queue/status
- 4 composite indexes trên review_events                  - Thiếu user_id ở leading column
- Cột due_day / due_at đổi liên tục                       - Quét toàn bảng thay vì theo user
         |                                                         |
[3. Redundant / Duplicate Index]                          [4. Đánh Index Thay Rollup]
- cards(note_id) trùng với uq_cards(note_id, template_id) - Cố đánh index để đếm Dashboard
- FK review_event_id ít khi query ngược                   - Không dùng Counter Rollup
```

### Anti-Pattern 1: Composite Index quá dài trên bảng có tần suất UPDATE cao
- **Trường hợp điển hình:** `study_progress_availability.ix_sp_avail_subject_queue_day` (7 cột).
- **Hệ quả:** Mỗi câu lệnh UPDATE khi học bài phải tốn công tính toán và sắp xếp lại cây B-tree của một tuple 7 phần tử. Nếu hệ thống có nhiều concurrent learner, lock contention trên các leaf page của index này sẽ tăng vọt.

### Anti-Pattern 2: Cột dẫn đầu (Leading Column) có độ chọn lọc (Cardinality) cực thấp
- **Trường hợp điển hình:** `ix_sp_avail_queue_time` bắt đầu bằng `normalized_queue`.
- **Hệ quả:** B-Tree không thể thu hẹp phạm vi tìm kiếm hiệu quả. Nếu không có `user_id` đi kèm, query optimizer của MySQL thường sẽ bỏ qua index này (Table Scan) hoặc phải scan một dải index khổng lồ của tất cả user.

### Anti-Pattern 3: Index dư thừa (Redundant / Shadowed Indexes)
- **Trường hợp điển hình:** Bảng `cards` có index đơn trên `note_id`, trong khi đã có unique constraint trên `(note_id, template_id)`. Theo nguyên tắc Leftmost Prefix của MySQL, index trên `(A, B)` đã tự động phục vụ tốt cho các query tìm theo `A`. Index đơn trên `A` là hoàn toàn lãng phí đĩa và tài nguyên ghi.

### Anti-Pattern 4: Dùng Index để "chữa cháy" cho bài toán thống kê/Dashboard
- Thay vì duy trì một bảng đếm tổng hợp (Rollup Table / Counter Cache), hệ thống lại cố gắng giữ nhiều secondary index trên bảng tiến độ chi tiết để chạy query đếm `COUNT(*)`. Điều này bắt luồng học (OLTP) phải gánh chi phí ghi để phục vụ cho luồng xem Dashboard (OLAP).

---

## 4. Bộ Quy Chuẩn Kỹ Thuật: Khi Nào NÊN và KHÔNG NÊN Đánh Index

### 4.1. Khi nào KHÔNG NÊN đánh Index (Strict Restrictions)

1. **KHÔNG đánh index trên các cột thay đổi liên tục trong các bảng Hot-Path:**
   - Các cột timestamp như `updated_at`, `last_reviewed_at`, `last_mirrored_at` (trừ khi bảng đó là read-mostly hoặc append-only log).
   - Các cột biến động theo từng hành động của user (`due_day`, `due_at`, `counter`, `revision`).
2. **KHÔNG đánh index trên các cột có Cardinality thấp (Low-selectivity):**
   - Các cột boolean (`is_suspended`, `is_buried`, `is_active`).
   - Các cột enum ít giá trị (`queue` chỉ có 3-4 trạng thái).
   - *Ngoại lệ duy nhất:* Khi kết hợp thành Composite Index với cột có độ chọn lọc cao đứng ĐẦU (ví dụ: `(user_id, queue, due_day)` thì `user_id` đứng đầu lọc ra 99.9% dữ liệu trước).
3. **KHÔNG tạo index trùng tiền tố (Redundant Indexes):**
   - Nếu đã có index `(col_a, col_b, col_c)`, tuyệt đối không tạo thêm index `(col_a)` hoặc `(col_a, col_b)`.
4. **KHÔNG tạo Composite Index vượt quá 3–4 cột trên bảng OLTP ghi nhiều:**
   - Composite index dài từ 5 đến 7 cột chỉ phù hợp cho Data Warehouse / Read-Only reporting, hoàn toàn cấm kỵ trên bảng học thẻ thời gian thực.
5. **KHÔNG đánh index cho các bảng có quy mô nhỏ (< 1.000 bản ghi):**
   - Bảng cấu trúc, vai trò, settings: Full table scan trong RAM (Buffer Pool) thường nhanh hơn việc duyệt cây B-tree của secondary index rồi lookup lại Clustered Index.

---

### 4.2. Khi nào NÊN đánh Index (Recommended Patterns)

1. **Bắt buộc:** Primary Key và các cột ràng buộc nghiệp vụ duy nhất (Unique Constraints).
2. **Khóa ngoại (Foreign Keys):** Các cột tham chiếu thường xuyên xuất hiện trong mệnh đề `JOIN` hoặc có hành vi `ON DELETE CASCADE` (để tránh table-level lock khi xóa dòng cha).
3. **Mệnh đề `WHERE` thường xuyên với độ chọn lọc cao:** Cột định danh đối tượng thuộc sở hữu của người dùng (`user_id`, `deck_id`, `note_type_id`).
4. **Mệnh đề `ORDER BY` + `LIMIT` trong phân trang:** Đánh composite index theo đúng thứ tự `(filter_col, sort_col)` để tránh MySQL phải chạy `Using filesort` trong bộ nhớ.
5. **Covering Index tinh gọn:** Khi một query cực kỳ quan trọng chỉ cần lấy 2-3 cột scalar, một composite index chứa đủ các cột đó giúp MySQL trả về kết quả trực tiếp từ B-Tree (gắn cờ `Using index`) mà không cần lookup vào bảng chính (Clustered Index).

---

## 5. Kế Hoạch Điều Tra Sâu & Dọn Dẹp (Action Plan)

Khi bước vào đợt tối ưu database tiếp theo, thực hiện quy trình điều tra thực nghiệm sau:

### Bước 1: Thu thập số liệu sử dụng Index thực tế trên MySQL Production
Chạy truy vấn trên `performance_schema` để tìm ra các index **hoàn toàn không được sử dụng** (0 read) nhưng vẫn tốn chi phí ghi:

```sql
SELECT 
    OBJECT_SCHEMA,
    OBJECT_NAME AS table_name,
    INDEX_NAME AS index_name,
    COUNT_FETCH AS read_operations,
    COUNT_INSERT AS write_inserts,
    COUNT_UPDATE AS write_updates,
    COUNT_DELETE AS write_deletes
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE OBJECT_SCHEMA = 'flama'
  AND INDEX_NAME IS NOT NULL
  AND INDEX_NAME != 'PRIMARY'
ORDER BY COUNT_FETCH ASC, (COUNT_INSERT + COUNT_UPDATE + COUNT_DELETE) DESC;
```
> *Các index có `COUNT_FETCH = 0` nhưng `COUNT_UPDATE` hàng trăm nghìn lần là ứng viên hàng đầu cần xoá bỏ ngay lập tức.*

### Bước 2: Dọn dẹp Redundant Index
Kiểm tra và viết Alembic migration drop các index thừa:
- Drop index `cards(note_id)` vì đã có `cards(note_id, template_id)`.
- Rà soát các index trên `review_events` để gom cụm hoặc loại bỏ index không có câu query thực tế.

### Bước 3: Chuyển dịch Dashboard sang Counter Cache / Rollup
- Tuyệt đối không thêm index vào bảng `study_progress_availability` hoặc `card_progress` chỉ để phục vụ đếm Dashboard.
- Triển khai bảng tổng hợp `deck_counters` hoặc cơ chế đếm tối ưu, tách rời ranh giới giữa OLTP Study và Reporting Dashboard.
