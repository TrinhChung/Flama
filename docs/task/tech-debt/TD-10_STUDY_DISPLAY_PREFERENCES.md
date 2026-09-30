# TD-10 — Tùy chọn hiển thị nút học: khoảng thời gian, định dạng, phím tắt, Space

> Mức: **P2** · Đợt: W4 · Trạng thái: `DECISION` (D-C3)
>
> Phụ thuộc: TD-09 · Lane: Frontend Study + Backend nhỏ (lưu tùy chọn) · Ước lượng: 2–3 ngày
>
> Nguồn: tầng 1 và C1 ở [tùy chỉnh nút và thuật toán](../decoupling/STUDY_BUTTONS_AND_ALGORITHM_CUSTOMIZATION_2026-09-30.md) §2.2.

## Mục tiêu

Người học tự chỉnh cách **hiển thị** nút đánh giá mà không đổi Action gửi lên server: không ảnh hưởng tiến độ, MCP, Anki sync hay analytics.

## Bối cảnh

- Nhãn, phím và bố cục viết cứng (`frontend/src/features/study/interactions/ReviewInteractionControls.tsx:54-131`, `pages/StudyPage.tsx:207-281`).
- Nhãn khoảng thời gian `m` vừa là phút vừa là tháng (`scheduler/legacyEngine.ts:610-691`). Chuỗi `label` bị golden vectors đóng băng (`tests/fixtures/study/legacy-anki-1.0.0-golden-vectors.json`), nhưng `SchedulerPreview` có số `seconds`/`days` (`scheduler/types.ts:55-60`).
- Không có nơi lưu tùy chọn người dùng cho màn học.

## Phạm vi file dự kiến

- Backend:
  - model/migration `user_study_preferences` (hoặc cột JSON trên bảng tùy chọn người dùng hiện có, nếu có);
  - API `GET/PUT /api/v1/settings/study-preferences` trong `app/api/v1/settings/`;
  - validator trong `app/validators/`.
- Frontend:
  - `features/settings` (mục "Màn học");
  - `features/study/interactions/ReviewInteractionControls.tsx`, `pages/StudyPage.tsx` (keymap từ tùy chọn);
  - formatter mới `features/study/scheduler/intervalLabel.ts` (dựng nhãn từ số, không sửa `legacyEngine`).

## Công việc chi tiết

1. Tùy chọn v1:
   - `show_intervals` (bật/tắt);
   - `interval_format` (`compact_vi` "10 ph, 3 ng, 1,5 th" | `long_vi` | `anki_compat`);
   - `space_on_back` (`good` | `none`);
   - `keymap` (phím cho lật, 4 đánh giá, hoàn tác, sửa, toàn màn hình; kiểm tra trùng và phím cấm).
2. Formatter tiếng Việt dựng từ `seconds`/`days`; golden vectors giữ nguyên.
3. Keymap áp dụng ở handler trang (host tin cậy). Không ảnh hưởng iframe (ADR).
4. Lưu server để đồng bộ nhiều thiết bị; cache ở client; mặc định = hành vi hiện tại.
5. Trang hướng dẫn phím tắt đọc keymap thực tế của người dùng (phối hợp TD-08).

## Output đầu ra bắt buộc

API + validator + migration + test; UI cài đặt + áp dụng; formatter + test; handoff.

## Acceptance criteria

- Mặc định giống hệt hiện tại (Zero Visual Regression khi chưa chỉnh gì).
- Đổi tùy chọn không đổi payload event/commit (test so sánh payload).
- Keymap trùng hoặc phím cấm bị từ chối kèm thông báo.

## Verification

```text
python scripts/run_tests.py --module study --frontend-only
python scripts/run_tests.py --module study,core --backend-only
```

## Rollback

Bỏ đọc tùy chọn thì về mặc định; bảng mới giữ nguyên.

## Quyết định liên quan

D-C3: làm tầng 1 trước (khuyến nghị). Chế độ 2 nút làm ở TD-13.

## Không làm trong task này

Đổi màu tùy ý; ẩn nút đánh giá (TD-13).
