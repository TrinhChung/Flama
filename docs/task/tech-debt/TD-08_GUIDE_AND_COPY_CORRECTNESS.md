# TD-08 — Hướng dẫn và câu chữ sai với hành vi thực tế

> Mức: **P1** · Đợt: W4 · Trạng thái: `TODO`
>
> Phụ thuộc: không (cập nhật lại khi TD-11/TD-12 phát hành) · Lane: Frontend nội dung · Ước lượng: 0,5–1 ngày
>
> Nguồn: UX-D1, UX-D2 ở [điều tra UI/UX trước P8](../decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md); C0 ở [tùy chỉnh nút và thuật toán](../decoupling/STUDY_BUTTONS_AND_ALGORITHM_CUSTOMIZATION_2026-09-30.md).

## Mục tiêu

Không hứa với người học những tính năng không tồn tại và không mô tả sai phím tắt hay mô hình tiến độ.

## Bối cảnh và bằng chứng (`frontend/src/features/guide/guideData.ts`)

| Dòng | Nội dung sai | Thực tế |
|---|---|---|
| 250 | "Mỗi thẻ có một hệ số độ khó riêng" | Từ P5, tiến độ thuộc learner/Note, dùng chung giữa các Template |
| 153-172 | Tham số deck: "Số thẻ mới mỗi ngày", "Max Reviews/Day", "Pinned" | Không có trong code (không có cột, API hay UI) |
| 267 | `R / F5` phát lại âm thanh | Không có; `F5` tải lại trang |
| 269 | `F` ẩn/hiện Furigana | `F` = toàn màn hình (`pages/StudyPage.tsx:251, 273-279`) |
| 271 | `* / -` gắn cờ | Không có tính năng cờ |
| 931-937 | Khắc phục: vào "Deck Settings" tăng "Số thẻ mới mỗi ngày" | Không có màn này |

Thêm: `features/library/pages/LibraryPages.tsx:384` giới thiệu "Anki SM-2 / FSRS", trong khi FSRS chưa chạy thật.

## Phạm vi file dự kiến

`features/guide/guideData.ts`, `features/library/pages/LibraryPages.tsx`, và nếu có: `pages/LandingPage.tsx`, câu chữ onboarding/tour nhắc tới giới hạn/ngày hoặc FSRS.

## Công việc chi tiết

1. Sửa bảng phím tắt theo code hiện tại: Space/Enter, 1–4, Z/Ctrl+Z, E, F (toàn màn hình). Thêm ghi chú "Khi đang tương tác trong thẻ (bấm vào nội dung), nhấp ra ngoài để dùng phím tắt".
2. Bỏ hoặc đánh dấu "Sắp có" các tham số deck không tồn tại; khôi phục khi TD-11/TD-12 phát hành.
3. Sửa mục khắc phục sự cố "không thấy thẻ mới" theo hành vi thật (hiện không có giới hạn/ngày).
4. Viết lại đoạn thuật toán: tiến độ theo Note, dùng chung giữa các cách học.
5. Bỏ nhắc FSRS như tính năng đang chạy (tùy D-C4).
6. Rà các trang hướng dẫn khác có nhắc Template/NoteType để khớp với TD-04 khi TD-04 xong.

## Output đầu ra bắt buộc

Nội dung đã sửa; danh sách thay đổi trong handoff.

## Acceptance criteria

Mọi phím tắt và tính năng được mô tả đều tồn tại. Kiểm bằng checklist đối chiếu `StudyPage.tsx` và grep các từ khóa: `F5`, `Furigana`, `Flag`, `New Cards/Day`, `Max Reviews`, `FSRS`.

## Verification

```text
python scripts/run_tests.py --module core --frontend-only
```

(hoặc module chứa test guide nếu có), kèm đọc lại trên trình duyệt.

## Rollback

Revert nội dung.

## Không làm trong task này

Thêm tính năng phím tắt mới (TD-10), giới hạn/ngày (TD-12).
