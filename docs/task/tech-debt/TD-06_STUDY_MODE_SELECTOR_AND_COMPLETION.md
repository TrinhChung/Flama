# TD-06 — Bộ chọn cách học và màn hoàn thành phiên

> Mức: **P1** · Đợt: W2 · Trạng thái: `DECISION` (D-U2, D-T3, D-U6)
>
> Phụ thuộc: không (TD-04 giúp tên Template có nghĩa) · Chặn: TD-13 · Lane: Backend đọc + Frontend Study · Ước lượng: 3–5 ngày
>
> Nguồn: UX-B1..B4 ở [điều tra UI/UX trước P8](../decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md); S2–S6 ở [hành trình người dùng](../decoupling/UIUX_COMPLETED_PHASES_USER_JOURNEY_AUDIT_2026-09-30.md). Tuân thủ [chính sách phạm vi nhiều NoteType](../../architecture/mixed-notetype-study-scope-policy-2026-09-09.md): server không tự chọn khi có nhiều lựa chọn.

## Mục tiêu

Màn chọn cách học trở thành lối vào hằng ngày dễ dùng: hiểu từng lựa chọn là gì, còn bao nhiêu thẻ, tiến độ dùng chung, nhớ lần trước. Màn hoàn thành nói đúng phạm vi vừa học.

## Bối cảnh và bằng chứng

- Tiêu đề và mô tả mang tính kỹ thuật (`frontend/src/features/study/pages/StudyPage.tsx:352-359`).
- Mỗi lựa chọn chỉ có tên Template và loại nguồn (`components/StudyModeSelector.tsx:50-57`).
- API không có số đếm hay metadata (`app/services/study_composition_service.py:51-70`).
- Không nhớ lựa chọn (`hooks/useStudySession.ts:384-387, 1169-1173`).
- Mọi điểm vào chỉ truyền `deck_id` (`app/api.ts:150`; Marketplace `DeckCard.tsx:446, 475`; Browse; Statistics).
- Màn hoàn thành:
  - nói "Tất cả các thẻ cần học hôm nay…" dù lựa chọn khác còn thẻ (`StudyCompletionCard.tsx:177-181`);
  - "Tỉ lệ đúng 100%" khi 0 lượt (dòng 83, 148);
  - khối "Trạng thái thẻ trong Deck" thực ra dùng số của phiên (`StudyPage.tsx:405, 420`).
- Deck đã cài có Note tự thêm bị tách thành 2 lựa chọn (S5).

## Phạm vi file dự kiến

- Backend:
  - `app/services/study_composition_service.py` + route compositions (`app/routes/flashcards/study.py`): thêm số đếm theo Note (mới/đang học/đến hạn) cho **từng** composition, đọc theo tập hợp như P5-11e, và `display` (nhãn, loại nguồn, `mode_key`);
  - `schema_version` nâng lên `study-scope-compositions.v3`, giữ tương thích đọc v2.
- Frontend:
  - `components/StudyModeSelector.tsx`, `pages/StudyPage.tsx` (màn chuẩn bị phiên);
  - `components/StudyCompletionCard.tsx`;
  - `hooks/useStudySession.ts` (nhận `composition_id` từ URL, nhớ lựa chọn);
  - `features/study/api.ts`, `types.ts`;
  - điểm vào ở Dashboard/Marketplace (tùy chọn nút "Học tiếp: <cách học>").

## Công việc chi tiết

1. **API v3:**
   - mỗi composition có `counts {new, learning, due}` theo Note của learner (NOTE authority), `label`, `context_label`, `is_customized` (dùng từ TD-17);
   - đo hiệu năng trên deck 20k Note (mục tiêu cùng bậc P5-11e).
2. **Bộ chọn:**
   - thẻ lựa chọn có tên, xem trước mặt trước (thu nhỏ, sandbox), số Note đến hạn/mới, nhãn "Dùng lần trước";
   - dòng giải thích "Tiến độ dùng chung theo Note giữa các cách học";
   - lựa chọn 0 thẻ vẫn chọn được nhưng làm mờ.
3. **Nhớ lựa chọn (D-U2):**
   - lưu `last_composition_id` theo (user, deck) ở client (`localStorage`, bọc try/catch);
   - làm nổi bật, nhưng vẫn yêu cầu 1 chạm (không tự mở; đúng P3-05).
4. **Deep link:**
   - `/study?deck_id=…&composition_id=…`;
   - chỉ mở thẳng nếu composition còn hợp lệ (server kiểm tra như `selectComposition`);
   - không hợp lệ thì quay về bộ chọn kèm thông báo.
5. **Deck đã cài (S5, D-T3):**
   - nhóm "Thẻ của tác giả" và "Thẻ bạn thêm" có tiêu đề rõ, kèm giải thích;
   - nếu D-T3 cho phép gộp (sau TD-17), thêm lựa chọn gộp.
6. **Màn hoàn thành:**
   - "Xong phần <cách học>" khi hết hàng đợi của composition;
   - liệt kê cách học khác còn thẻ, kèm CTA "Học tiếp <cách học>";
   - ẩn tỉ lệ đúng khi 0 lượt;
   - bỏ CTA "Kết thúc & Đồng bộ phiên" khi không còn gì để gửi;
   - số đếm deck lấy từ API (theo Note), không lấy từ phiên.
7. **(Tùy chọn, UX-B4)** Điểm vào theo NoteType `scope=note_type`, nếu chủ sản phẩm muốn cho "Luyện mọi Note kiểu X".

## Output đầu ra bắt buộc

API v3 + test backend; bộ chọn + màn hoàn thành + test; ảnh chụp trước/sau (màn mới, cần duyệt thiết kế; dùng `$impeccable`); handoff.

## Acceptance criteria

- Số đếm trên bộ chọn khớp số đếm theo Note của Dashboard (cùng learner, cùng thời điểm).
- Không có đường nào mở phiên mà không có lựa chọn rõ ràng khi có nhiều composition (test "no premature open" hiện có vẫn xanh).
- Deep link hợp lệ mở thẳng; không hợp lệ quay về bộ chọn.
- Màn hoàn thành không còn khẳng định sai phạm vi; không hiện 100% khi 0 lượt.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module study --frontend-only
```

Kèm luồng trình duyệt: deck 1 cách học, deck 2 cách học, deck đã cài có Note tự thêm.

## Rollback

Frontend đọc được cả v2 và v3; server có thể trả lại v2 qua flag.

## Không làm trong task này

Chế độ tương tác mới (P8); cấu hình Interaction (TD-13).
