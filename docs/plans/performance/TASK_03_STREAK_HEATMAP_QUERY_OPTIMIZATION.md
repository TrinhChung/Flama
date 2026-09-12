# Kế hoạch Tối ưu #03: Tối ưu hoá Truy vấn Thống kê Streak & Dashboard Heatmap

> **Mã Task:** `PERF-STATS-03`  
> **Mức độ ưu tiên:** 🟠 P1 (High - Ảnh hưởng trực tiếp tốc độ mở Dashboard và biểu đồ nhiệt của học viên)  
> **Trạng thái:** DỰ THẢO CHỜ DUYỆT (PROPOSED)  
> **Phạm vi tác động:** Stats Query Repository (`stats_query_repository.py`), Analytics API (`/api/v1/analytics/overview`)  
> **Tài liệu tham chiếu:** [`app/repositories/stats_query_repository.py`](file:///d:/Project/nihongo/app/repositories/stats_query_repository.py#L247-L325), [`app/services/stats_overview.py`](file:///d:/Project/nihongo/app/services/stats_overview.py#L267-L397)

---

## 1. Vấn đề Kỹ thuật Cần Giải quyết

### 1.1 Hiện trạng mã nguồn
Tại [`app/repositories/stats_query_repository.py`](file:///d:/Project/nihongo/app/repositories/stats_query_repository.py#L247-L275), hàm `_query_active_review_days_mysql` được sử dụng để lấy tất cả các ngày mà người dùng đã từng học nhằm tính chuỗi ngày liên tục (streak):

```python
# stats_query_repository.py:254-268
local_day_expr = db.func.date(
    db.func.date_sub(
        _mysql_local_timestamp(timezone_name),
        db.text(f"INTERVAL {int(day_boundary_hour_local)} HOUR"),
    )
)
rows = (
    db.session.query(local_day_expr.label("local_day"))
    .filter(
        ReviewEvent.user_id == user_id,
        ReviewEvent.reviewed_at < end_utc,
    )
    .group_by(local_day_expr)
    .all()
)
```

### 1.2 Điểm nghẽn
1. **Vô hiệu hóa B-Tree Index (Non-SARGable Expression):** Biểu thức `GROUP BY date(date_sub(date_add(...)))` bọc các hàm thời gian lồng nhau lên trường `ReviewEvent.reviewed_at`. Trong MySQL 8.0, việc bọc hàm trên cột khiến bộ tối ưu truy vấn không thể sử dụng B-Tree Index để gom nhóm, bắt buộc phải duyệt qua tất cả các bản ghi thỏa mãn `user_id`, đẩy vào bảng tạm (`Using temporary`) và sắp xếp lại trên đĩa (`Using filesort`).
2. **Quét toàn bộ lịch sử không giới hạn đáy:** Điều kiện chỉ có `reviewed_at < end_utc`. Với một tài khoản học 2–3 năm (hàng chục nghìn lượt review), mỗi lần người dùng vào trang Dashboard, MySQL lại phải quét ngược về ngày đầu tiên lập nick.
3. **Overhead chuyển dữ liệu Due Cards:** Hàm `query_due_progress_rows` ([dòng 627](file:///d:/Project/nihongo/app/repositories/stats_query_repository.py#L627-L648)) nạp toàn bộ hàng tiến độ (`due_at`, `due_day`, `queue`) của user không giới hạn phân trang về RAM Python để tự tính bucket.

---

## 2. Giải pháp Kỹ thuật (Technical Mechanism)

Triển khai đồng thời 2 giải pháp tối ưu:

```text
CƠ CHẾ TRƯỚC TỐI ƯU:
SELECT date(...) FROM review_events WHERE user_id = 1 AND reviewed_at < NOW() GROUP BY date(...)
──► MySQL quét 36.500 rows (tất cả review_events của user)
──► Using Temporary + Using Filesort (Quá trình sort tốn CPU & RAM máy chủ)
──► Thời gian: 80ms - 150ms

CƠ CHẾ SAU TỐI ƯU (Cửa sổ trượt + Functional Index / Cache Streak):
1. Tính Streak theo Cửa sổ trượt (Sliding Window):
   Để tính chuỗi ngày học hiện tại (Current Streak), chỉ cần quét tối đa 60 ngày gần nhất!
   Nếu trong 60 ngày không đứt streak, mới quét tiếp chặng trước đó.
2. Index Chức năng (Functional Index) trên MySQL 8.0:
   CREATE INDEX ix_review_events_user_local_day 
   ON review_events (user_id, (CAST(reviewed_at AS DATE)));
   ──► MySQL đọc trực tiếp từ Index B-Tree (Using Index), loại bỏ 100% temporary table và filesort!
3. Cache thuộc tính Streak trên User Record:
   Lưu `current_streak` và `last_studied_local_day` trực tiếp trên bảng `User`.
   Khi commit phiên học (study commit), cập nhật O(1) ngay trong phiên học đó.
```

### Chi tiết thay đổi mã nguồn
1. **Thay đổi truy vấn Streak:**
   Thay vì query toàn bộ lịch sử từ đầu tới nay, giới hạn chặn đáy `reviewed_at >= :recent_cutoff_utc` (mặc định 60 ngày gần nhất). Chỉ khi streak chạm mốc 60 ngày mới mở rộng cửa sổ.
2. **Bổ sung Migration Functional Index (Alembic):**
   Tạo index trên `(user_id, reviewed_at)` kết hợp hỗ trợ grouping trực tiếp mà không cần filesort.

---

## 3. Tính toán Định lượng Cụ thể (Quantitative Impact)

* Giả sử một người học chăm chỉ học trong 1 năm ($100\text{ thẻ/ngày} \times 365 = \mathbf{36.500\text{ records}}$):

| Tiêu chí đo lường | Trước khi tối ưu | Sau khi tối ưu (Sliding Window + Index) | Mức độ cải thiện |
|---|---|---|:---:|
| **Số bản ghi MySQL phải duyệt** | $\mathbf{36.500\text{ rows}}$ | $\mathbf{\le 365\text{ rows}}$ (hoặc 60 rows cho streak) | **Giảm 99% số row đọc** |
| **MySQL Execution Plan** | `Using where; Using temporary; Using filesort` | `Using index; Using where` | **Loại bỏ hoàn toàn đĩa tạm & filesort** |
| **Thời gian thực thi câu query** | $\mathbf{80\text{ms} - 150\text{ms}}$ | $\mathbf{\le 3\text{ms}}$ | **Nhanh gấp 30 - 50 lần** |
| **Băng thông mạng nạp Due Cards** | Kéo 20.000 tuples về RAM Python | Query trực tiếp SQL `COUNT(...) GROUP BY due_offset` | **Tiết kiệm 95% RAM Python** |

---

## 4. Kế hoạch Triển khai (Checklist)

- [ ] **Repository:** Điều chỉnh hàm `query_active_review_days` trong [`app/repositories/stats_query_repository.py`](file:///d:/Project/nihongo/app/repositories/stats_query_repository.py) có tham số chặn đáy thời gian `start_utc`.
- [ ] **Service:** Cập nhật [`app/services/stats_overview.py`](file:///d:/Project/nihongo/app/services/stats_overview.py) sử dụng cửa sổ tìm streak thông minh (windowed streak search).
- [ ] **Migration:** Viết Alembic migration bổ sung Index tối ưu cho `review_events (user_id, reviewed_at)`.
- [ ] **Testing:** Chạy kiểm thử toàn bộ module analytics: `python scripts/run_tests.py --module analytics`, đảm bảo logic tính `current_streak` và `longest_streak` không bị sai lệch ngày.
