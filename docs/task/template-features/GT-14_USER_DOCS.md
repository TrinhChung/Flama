# GT-14 — Tài liệu người dùng cho kiểu thẻ, phiên bản, bản riêng và thư viện mẫu

- Owner: Gemini. Reviewer: Claude. Milestone: sau M3 và M4 `Accepted`.
- Trạng thái: **Blocked**.
- Loại: nội dung hướng dẫn, không đổi logic.

## 0. Việc Claude làm trước khi mở task

- [ ] Liệt kê hành vi **đã nghiệm thu** (M1–M4) và hành vi chưa có (ví dụ M5 pin release chưa duyệt) để Gemini không mô tả tính năng chưa tồn tại.
- [ ] Chụp/ghi tên nút, đường dẫn, chuỗi UI thật sau M4 vào §2.
- [ ] Chọn slug hướng dẫn và vị trí chèn trong `guideData.ts`.

## 1. Phạm vi

| File | Được làm gì |
|---|---|
| `docs/guides/NOTE_TYPE_TEMPLATE_GUIDE.md` | Thêm các mục: "Một deck nhiều kiểu thẻ", "Lịch sử phiên bản", "Tùy chỉnh giao diện deck đã cài", "Thư viện mẫu thẻ và ánh xạ trường". Không xóa nội dung cũ. |
| `frontend/src/features/guide/guideData.ts` | Thêm đúng 1 bài trong nhóm Claude chỉ định ở §0, theo cấu trúc `types.ts` hiện có. |

## 2. Nội dung bắt buộc (Claude điền chuỗi UI thật ở §0)

1. Kiểu thẻ là gì; xem ở menu deck → "Kiểu thẻ (template)"; chọn kiểu khi bắt đầu học; tiến độ học tính theo note nên đổi kiểu thẻ không mất tiến độ.
2. Quản lý template ở trang loại thẻ: tạo, đổi tên, xóa (không xóa được template mặc định/duy nhất), số note.
3. Lịch sử phiên bản: mỗi lần lưu là một phiên bản; so sánh; khôi phục tạo phiên bản mới.
4. Deck đã cài: tạo bản riêng, deck của tác giả không đổi, phiên đang học không đổi giữa chừng, cảnh báo khi tác giả cập nhật, dùng lại bản gốc.
5. Thư viện mẫu thẻ: tạo mẫu độc lập, input `{{key}}`, áp dụng vào loại thẻ bằng ánh xạ trường, cập nhật loại thẻ lên phiên bản mới.
6. Giới hạn hiện tại (theo §0): ví dụ chưa có pin phiên bản theo release cho tác giả.

## 3. Kiểm tra

```powershell
npm --prefix frontend run test -- src/features/guide
npm --prefix frontend run typecheck
npm --prefix frontend run lint
git diff --check
```

## 4. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-14. Đọc và làm đúng theo docs/task/template-features/GT-14_USER_DOCS.md (§1–§3).
Chỉ mô tả hành vi đã liệt kê ở §2; không mô tả tính năng khác. Đọc thêm: docs/guides/NOTE_TYPE_TEMPLATE_GUIDE.md,
frontend/src/features/guide/types.ts, guideData.ts. Báo cáo theo README §3. Không commit.
```
