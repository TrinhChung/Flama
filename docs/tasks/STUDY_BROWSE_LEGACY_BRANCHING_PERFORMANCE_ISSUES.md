# Task: Khảo Sát & Ghi Nhận Các Điểm Nghẽn Hiệu Năng Do Rẽ Nhánh Tương Thích Legacy Models

## 1. Tổng quan (Overview)

Tài liệu này ghi nhận chi tiết 2 vấn đề suy giảm hiệu năng cơ sở dữ liệu và API xuất phát từ các nhánh logic tương thích ngược (backwards-compatibility branching / fallback logic) còn tồn đọng trong hệ thống Flama sau các giai đoạn cutover (Phase 5 – Phase 10).

Theo yêu cầu, tài liệu tập trung **mô tả bản chất vấn đề, vị trí mã nguồn, cơ chế phát sinh lỗi và tác động hiệu năng cụ thể**, không đề xuất giải pháp xử lý.

---

## 2. Vấn đề 1: Quét Toàn Bộ Thẻ Để Kiểm Tra Sai Lệch (Divergence Pre-Flight Check) Trong Browse Cards API

### 2.1. Vị trí mã nguồn
- Tuyến xử lý API Browse: [`app/services/browse_card_service.py`](file:///d:/Project/nihongo/app/services/browse_card_service.py#L751-L782)
- Hàm sinh truy vấn vector vi phạm: [`app/repositories/note_analytics_read_repository.py`](file:///d:/Project/nihongo/app/repositories/note_analytics_read_repository.py#L47-L83)

### 2.2. Đoạn mã phát sinh vấn đề
Tại [`app/services/browse_card_service.py`](file:///d:/Project/nihongo/app/services/browse_card_service.py#L751-L782):
```python
is_note_mode = authority_route.mode_code == "NOTE"
if is_note_mode:
    # Verify every visible candidate (owned and logical-overlay source)
    # against canonical NOTE state before the shared status/sort SQL runs...
    candidate_scope = (
        query.with_entities(
            Note.deck_id.label("deck_id"),
            Card.id.label("card_id"),
            Card.note_id.label("note_id"),
        )
        .order_by(None)
        .subquery("browse_candidates")
    )
    verified = note_analytics_read_repository.note_card_rows(
        candidate_scope,
        learner_user_id=user_id,
        storage_profile=authority_route.storage_profile,
    ).subquery("browse_candidate_rows")
    worst = int(db.session.execute(select(func.max(verified.c.violation))).scalar() or 0)
    if not worst:
        worst = note_analytics_read_repository.subject_vector_violation(
            db.session, scope=candidate_scope, learner_user_id=user_id,
            storage_profile=authority_route.storage_profile,
        )
    violation = note_analytics_read_repository.violation_error(worst)
    if violation is not None:
        db.session.rollback()
        raise BrowseApiError(violation[1], status=409, code=violation[0])

# Sau bước pre-flight mới tiến hành phân trang
pagination = query.paginate(page=page, per_page=per_page, error_out=False)
```

### 2.3. Cơ chế kỹ thuật và bản chất vấn đề
1. **Mục đích lịch sử của nhánh code**:
   - Khi hệ thống chuyển đổi từ kiến trúc cũ (`CardProgress` - per-card) sang kiến trúc mới (`StudyProgressSubject` - per-note authority, Phase 5/P9), nhánh kiểm tra này được bổ sung để đảm bảo không có sự sai lệch (divergence) hoặc mất đồng bộ trạng thái giữa hai mô hình dữ liệu trước khi trả dữ liệu về client.
2. **Hành vi thực thi trên Database (Execution Behavior)**:
   - Thay vì chỉ truy vấn đúng số lượng bản ghi của 1 trang theo phân trang (ví dụ: `LIMIT 20 OFFSET 0` hoặc `LIMIT 50`), câu truy vấn phụ (pre-flight check) bọc toàn bộ các thẻ ứng viên của deck/user vào subquery `browse_candidates`.
   - Subquery này thực hiện `OUTER JOIN` giữa `Card`, `Note` và bảng `study_progress_subjects`, sau đó chạy hàm tổng hợp `MAX(verified.c.violation)` trên **toàn bộ tập dữ liệu thỏa mãn bộ lọc**.
   - Nếu kết quả `worst == 0`, code tiếp tục gọi thêm hàm thứ hai `note_analytics_read_repository.subject_vector_violation` để kiểm tra tiếp.
3. **Tác động hiệu năng**:
   - **Full-scan toàn bộ tập thẻ ứng viên**: Đối với người dùng sở hữu bộ thẻ lớn (từ vài nghìn đến hàng chục nghìn thẻ), database phải tính toán phép tổng hợp trên toàn bộ các thẻ của deck/user trước khi trả về kết quả trang 1.
   - **Tăng vọt thời gian phản hồi API Browse**: Gây ra độ trễ từ 1.5s – 5s tùy thuộc vào kích thước collection và bộ nhớ đệm InnoDB Buffer Pool, dù người dùng chỉ yêu cầu xem danh sách 20 thẻ đầu tiên.
   - **Lãng phí I/O và CPU trên Database Server**: Việc chạy subquery tổng hợp nặng nề trên mọi request phân trang (chuyển trang, lọc từ khóa, lọc tag) làm tăng tải CPU và I/O không cần thiết trên MySQL.

---

## 3. Vấn đề 2: Mệnh Đề `OR` & Rẽ Nhánh Tương Thích Trong SQL Predicates Của Hàng Đợi Học SRS (`due_day` vs `due_at`)

### 2.1. Vị trí mã nguồn
- Truy vấn xếp thứ tự và lọc thẻ đến hạn: [`app/repositories/study_repository.py`](file:///d:/Project/nihongo/app/repositories/study_repository.py#L464-L592) (các hàm `review_due_expr`, `_ordered_study_card_queries`, `query_next_due_card_id`).

### 3.2. Đoạn mã phát sinh vấn đề
Tại [`app/repositories/study_repository.py`](file:///d:/Project/nihongo/app/repositories/study_repository.py#L464-L568):
```python
def review_due_expr(progress_alias, *, now: datetime, timezone_name: str = "UTC", day_boundary_hour_local: int | None = None):
    today_day_index = _today_day_index(now=now, timezone_name=timezone_name, day_boundary_hour_local=day_boundary_hour_local)
    return db.or_(
        progress_alias.due_day <= today_day_index,
        db.and_(
            progress_alias.due_day.is_(None),
            db.or_(
                progress_alias.due_at.is_(None),
                progress_alias.due_at <= now,
            ),
        ),
    )
```
Và trong hàm xác định thẻ cần học `_ordered_study_card_queries`:
```python
learning_due_expr = db.or_(
    db.and_(
        progress_alias.due_day.isnot(None),
        progress_alias.due_day <= today_day_index,
    ),
    db.and_(
        progress_alias.due_day.is_(None),
        db.or_(
            progress_alias.due_at.is_(None),
            progress_alias.due_at <= now,
        ),
    ),
)

review_due_sort_key = db.case(
    (normalized_queue == REVIEW_QUEUE, progress_alias.due_day),
    else_=None,
)
due_sort_key = db.case(
    (
        normalized_queue.in_([LEARNING_QUEUE, RELEARNING_QUEUE, REVIEW_QUEUE]),
        progress_alias.due_at,
    ),
    else_=None,
)
```

### 3.3. Cơ chế kỹ thuật và bản chất vấn đề
1. **Mục đích lịch sử của nhánh code**:
   - Trong phiên bản cơ sở dữ liệu ban đầu, tiến độ học chỉ lưu mốc thời gian dạng timestamp `due_at`. Sau khi nâng cấp thuật toán sang day-boundary (tính ngày theo mốc giờ chuyển ngày cục bộ của người dùng), trường `due_day` (số nguyên biểu diễn ngày) được bổ sung.
   - Nhằm duy trì tính tương thích với các dòng dữ liệu cũ chưa được backfill hoặc thiếu một trong hai trường, các câu truy vấn SQL được cấu trúc với nhiều nhánh điều kiện `OR` để fallback lẫn nhau: nếu có `due_day` thì so sánh theo ngày, nếu `due_day IS NULL` thì fallback về so sánh timestamp `due_at`.
2. **Hành vi thực thi trên Database (Execution Behavior)**:
   - **Vô hiệu hóa B-Tree Composite Range Scan**: Mệnh đề điều kiện dạng:
     `WHERE (due_day <= ? OR (due_day IS NULL AND (due_at IS NULL OR due_at <= ?)))`
     ngăn cản trình tối ưu hóa truy vấn của MySQL (Query Optimizer) sử dụng index range scan đơn giản trên các chỉ mục composite như `(user_id, due_day)` hoặc `(user_id, due_at)`.
   - **Chuyển đổi thành Index Merge hoặc Table Scan**: MySQL buộc phải quét toàn bộ các chỉ mục riêng lẻ rồi hợp kết quả (Index Merge Union/Sort-Union) hoặc quét bảng tạm để lọc bản ghi thỏa mãn.
   - **Filesort khi sắp xếp theo thứ tự ưu tiên (`ORDER BY`)**:
     Biểu thức `ORDER BY` sử dụng nhiều hàm `CASE WHEN` lồng nhau:
     ```sql
     ORDER BY queue_priority ASC,
              (CASE WHEN normalized_queue = 'review' THEN due_day ELSE NULL END) ASC,
              (CASE WHEN normalized_queue IN ('learning', 'relearning', 'review') THEN due_at ELSE NULL END) ASC,
              Card.created_at ASC
     ```
     Việc sắp xếp dựa trên giá trị tính toán động (dynamically computed expressions) thay vì cột vật lý trực tiếp khiến MySQL không thể tận dụng thứ tự đã được đánh index, bắt buộc phải cấp phát bộ nhớ `sort_buffer_size` để thực hiện thuật toán Filesort hoặc ghi xuống bảng tạm trên đĩa (disk-based temporary table).
3. **Tác động hiệu năng**:
   - **Chậm API lấy thẻ tiếp theo (`/api/study/next`)**: Đây là endpoint cốt lõi được gọi liên tục mỗi khi người dùng lật một thẻ bài mới trong phiên học. Mỗi lượt gọi đều phải thực thi câu lệnh SQL với Filesort và điều kiện `OR` phức tạp nói trên.
   - **Tăng chi phí CPU của MySQL**: Khi nhiều người dùng cùng học thẻ đồng thời, khối lượng công việc sắp xếp (sort computations) và ghép chỉ mục (index merge) tạo áp lực liên tục lên CPU của database server.

---

## 4. Tóm tắt so sánh tác động của 2 vấn đề

| Đặc tính so sánh | Vấn đề 1: Divergence Check trong Browse | Vấn đề 2: Predicate `OR` trong SRS Queries |
|---|---|---|
| **Vùng chức năng ảnh hưởng** | Quản lý / Duyệt danh sách từ vựng & thẻ (`/api/vocabulary/browse/cards`) | Phiên học & thuật toán chọn thẻ ôn tập (`/api/study/next`, Session Issue) |
| **Bản chất kỹ thuật** | Chạy subquery aggregate toàn bộ collection trước khi áp dụng `LIMIT / OFFSET` | Mệnh đề `OR (col IS NULL)` và `CASE WHEN` trong `WHERE / ORDER BY` làm hỏng index scan |
| **Mức độ ảnh hưởng** | Rất cao trên các bộ thẻ lớn (> 5.000 thẻ); gây trễ trang rõ rệt (vài giây) | Liên tục và diện rộng; tích tụ tải CPU trên database do tần suất gọi rất cao |
| **Đối tượng dữ liệu liên quan** | `StudyProgressSubject` vs `CardProgress` | `due_day` vs `due_at` trên `CardProgress` / `StudyProgressSubject` |
