# TD-03 — An toàn phiên học: báo mất lưu bền, nhãn thoát, focus nút, chỉ báo đồng bộ, di động

> Mức: **P1** · Đợt: W1 · Trạng thái: `TODO`
>
> Phụ thuộc: TD-02 · Lane: Frontend Study · Ước lượng: 2–3 ngày
>
> Nguồn: UX-A3, UX-A4, UX-A6, UX-C2, UX-C3, UX-C4, UX-C6 ở [điều tra UI/UX trước P8](../decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md); Phụ lục B #2 của canonical plan.

## Mục tiêu

Sửa các chỗ màn học có thể làm người học mất công hoặc hiểu sai trạng thái:
- mất lưu bền mà không biết;
- nút "Thoát không lưu" không đúng với hành vi;
- phím Space kích hoạt nhầm nút;
- không biết đã đồng bộ chưa;
- phím tắt tắt âm thầm khi focus nằm trong thẻ;
- di động thiếu nút Hoàn tác.

## Bối cảnh và bằng chứng

| Vấn đề | Bằng chứng |
|---|---|
| `sessionDurableRef` được ghi nhưng UI không đọc | `hooks/useStudySession.ts:157, 314, 394, 455` |
| "Thoát không lưu tiến độ này" chỉ gọi `blocker.proceed()`, nhưng hook vẫn `flushOnExit()` khi unmount/`pagehide` *(cần xác minh trình duyệt)* | `pages/StudyPage.tsx:79-81`; `useStudySession.ts:955-972` |
| Handler phím bỏ qua khi focus là `button`, nên Space kích hoạt lại Hoàn tác/Toàn màn hình vừa bấm *(cần xác minh trình duyệt)* | `StudyPage.tsx:235-241` |
| Trạng thái đồng bộ chỉ là chữ 11px, ẩn khi toàn màn hình | `StudyPage.tsx:443-447` |
| Focus trong iframe làm tắt phím tắt, không có tín hiệu | `components/CardRendererFrame.tsx:216-217`; `StudyPage.tsx:283-290` |
| Di động sau khi lật thẻ không có Hoàn tác; lớp `xs:` không có hiệu lực | `components/StudyBottomBar.tsx:46, 67, 80`; `interactions/ReviewInteractionControls.tsx:64` |
| Lật thẻ không được thông báo cho trình đọc màn hình | `CardRendererFrame.tsx:216` |

## Phạm vi file dự kiến

`hooks/useStudySession.ts` (xuất `isDurable`), `pages/StudyPage.tsx`, `components/StudyBottomBar.tsx`, `components/StudyHeaderToolbar.tsx`, `components/StudyExitConfirmDialog.tsx`, `components/CardRendererFrame.tsx`, `interactions/ReviewInteractionControls.tsx`, cùng các test tương ứng.

## Công việc chi tiết

1. **Lưu bền:**
   - xuất `isDurable` từ hook;
   - khi `false`: nhãn "Tiến độ đang chỉ lưu tạm trong tab này", hạ ngưỡng rollover (ví dụ 10 event), luôn bật `beforeunload`.
2. **Hộp thoại thoát:**
   - giữ hành vi lưu (đúng invariant không mất dữ liệu);
   - đổi nhãn "Thoát không lưu tiến độ này" thành "Rời đi — tự đồng bộ sau", mô tả rõ;
   - viết test hook xác nhận có flush.
3. **Focus:**
   - bỏ focus các control của bottom bar sau khi click bằng con trỏ (`pointerup`);
   - hoặc xử lý Space/Enter ở cấp trang khi target là control của bottom bar;
   - test: click Hoàn tác rồi Space thì lật thẻ, không hoàn tác lần hai.
4. **Chỉ báo đồng bộ** ở header, hiện cả khi toàn màn hình:
   - các trạng thái "Đã lưu", "N chưa đồng bộ", "Đang đồng bộ", "Lỗi" (liên kết màn sự cố TD-02);
   - có `aria-live="polite"`.
5. **Iframe focus:** khi `document.activeElement` là iframe thẻ, hiện gợi ý nhỏ "Nhấp ra ngoài thẻ để dùng phím tắt". Không thêm bridge bàn phím (theo ADR).
6. **Di động:**
   - hiện nút Hoàn tác cả khi đã lật thẻ;
   - quyết định bỏ hoặc định nghĩa breakpoint `xs` (Tailwind v4 không có sẵn). Nếu thay đổi hình thức thì cần duyệt ảnh trước/sau.
7. **Trợ năng:** vùng `aria-live` thông báo "Đã hiện đáp án"; nút đánh giá có mô tả khoảng thời gian.

## Output đầu ra bắt buộc

Các thay đổi trên kèm test; ảnh chụp trước/sau cho mọi thay đổi hình thức (di động, chỉ báo); handoff.

## Acceptance criteria

- Tắt IndexedDB (giả lập) thì thấy nhãn cảnh báo và commit sớm hơn.
- Nhãn thoát khớp hành vi đã xác minh bằng test hook.
- Space sau khi click chuột vào nút không gây hoàn tác hay toàn màn hình.
- Người dùng trình đọc màn hình nghe được trạng thái lật thẻ và đồng bộ.
- Không đổi hình thức ngoài các mục đã liệt kê.

## Verification

```text
python scripts/run_tests.py --module study --frontend-only
```

Kèm luồng trình duyệt: chế độ riêng tư Firefox/Safari, màn hình 360px, VoiceOver/NVDA cơ bản (profile Chrome riêng khi dùng Chrome).

## Rollback

Revert frontend.

## Không làm trong task này

Thiết kế lại bottom bar; bridge phím từ iframe; tùy chọn phím tắt (TD-10).
