# TD-12 — Giới hạn thẻ mới / lượt ôn mỗi ngày; deck lớn hơn 5.000 thẻ không mở được phiên

> Mức: **P1** · Đợt: W4b · Trạng thái: `DECISION` (D-C2)
>
> Phụ thuộc: TD-11 (preset chứa giới hạn) · Lane: Backend Study + Frontend Study/Dashboard + MCP · Ước lượng: 5–8 ngày
>
> Nguồn: C3 ở [tùy chỉnh nút và thuật toán](../decoupling/STUDY_BUTTONS_AND_ALGORITHM_CUSTOMIZATION_2026-09-30.md) §3.2. Skill: `$flama-backend-architecture`, `$mysql`.

## Mục tiêu

- Người học đặt được số Note mới tối đa mỗi ngày và số lượt ôn tối đa mỗi ngày. Số đếm trên Dashboard, phiên học và MCP phản ánh đúng giới hạn.
- Phiên học chỉ nạp phần cần học, nên deck lớn không còn bị lỗi 5.000 thẻ.

## Bối cảnh

- Không có giới hạn nào:
  - hàng đợi client lấy mọi thẻ mới (`frontend/src/features/study/scheduler/queue.ts:68-120`);
  - Dashboard đếm toàn bộ (`app/repositories/study_repository.py:817-844`).
- Mở phiên nạp **mọi** Card của composition, tối đa 5.000. Vượt thì trả `413 SESSION_TOO_LARGE` với thông điệp tiếng Anh (`app/services/study_session_service.py:134, 584-591`), nên deck lớn không học được. *(Cần xác minh production có deck nào vượt ngưỡng.)*
- Hướng dẫn đang hứa "Số thẻ mới mỗi ngày" (TD-08).
- Đếm theo Note cho learner NOTE (D6-04); đọc theo tập hợp đã tối ưu ở P5-11e.

## Phạm vi file dự kiến

- Model/migration: thêm `new_per_day`, `reviews_per_day` vào `scheduler_presets` (mặc định đề xuất 20 / 200 hoặc "không giới hạn" để giữ hành vi, theo D-C2).
- Backend:
  - `app/services/scheduler_config_service.py` (options mới);
  - `study_session_service.py` (mở phiên chỉ nạp due + learning + tối đa số mới còn lại);
  - repository đếm "đã giới thiệu hôm nay" và "đã ôn hôm nay" theo learner + cây deck, theo mốc giờ sang ngày mới và timezone;
  - `study_repository.py` và `app/services/mcp/study_tools.py` (số đếm có giới hạn).
- Frontend:
  - `scheduler/queue.ts` (tôn trọng giới hạn trong phiên);
  - `StudyCompletionCard.tsx` ("Đã đủ N thẻ mới hôm nay");
  - UI preset (TD-11).

## Công việc chi tiết

1. **Định nghĩa (D-C2):**
   - "Note mới đã giới thiệu hôm nay" = Note chuyển từ new sang trạng thái khác trong ngày học hiện tại (theo `review_events` + NOTE state);
   - giới hạn áp theo **cây deck đang học** (deck + con), đếm theo **Note**.
2. **Mở phiên:**
   - nạp due + learning + `min(new_remaining, new_per_day)` Note mới (thứ tự tạo);
   - ôn due tối đa `reviews_per_day` còn lại;
   - bỏ lỗi 5.000 cho trường hợp phổ biến; giữ ngưỡng bảo vệ tải kèm thông điệp tiếng Việt và gợi ý chia nhỏ.
3. **Rollover** trong ngày giữ ngân sách còn lại; sang ngày mới (theo mốc giờ) thì ngân sách làm mới.
4. **Số đếm Dashboard/MCP** áp giới hạn giống phiên (một hàm dùng chung).
5. **Deck đã cài:** giới hạn theo preset của deck local.
6. **Hiệu năng:**
   - benchmark MySQL cho learner 20k Note (mục tiêu: không chậm hơn P5-11e);
   - kiểm tra `EXPLAIN` truy vấn đếm "hôm nay";
   - thêm index nếu cần qua migration.

## Output đầu ra bắt buộc

Migration + rehearsal MySQL; service + repository + test (timezone, mốc giờ, rollover, NOTE/LEGACY, deck đã cài); UI; benchmark; handoff.

## Acceptance criteria

- Với `new_per_day = 20`: sau 20 Note mới, phiên và Dashboard không còn thẻ mới cho tới ngày học kế tiếp.
- Deck 10.000 thẻ mở phiên được, payload giảm tương ứng.
- Mặc định theo D-C2 không đổi hành vi người đang học giữa chừng (nếu chọn "không giới hạn" cho preset mặc định).
- Test giữa mốc giờ sang ngày mới và qua timezone khác nhau đều đúng.

## Verification

```text
python scripts/run_tests.py --module study,decks,connect_mcp,analytics --backend-only
python scripts/run_tests.py --module study --frontend-only
```

Kèm probe MySQL và benchmark.

## Rollback

Giới hạn NULL nghĩa là không giới hạn (hành vi cũ). Flag giữ cách mở phiên cũ.

## Không làm trong task này

"Custom study / học thêm hôm nay" kiểu Anki (có thể làm follow-up); FSRS.
