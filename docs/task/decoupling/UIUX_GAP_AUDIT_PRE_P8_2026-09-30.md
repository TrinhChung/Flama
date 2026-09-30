# Điều tra UI/UX sau decoupling — chuẩn bị đợt nâng cấp và Phase 8

> Lập 2026-09-30 tại commit `8a2a3da` (nhánh `fix/legacy-lease-replay-under-note`). Loại: điều tra/báo cáo, **Runtime change: none**.
>
> Phạm vi: React SPA (`frontend/src/`) ở luồng học và các màn liên quan tới tiến độ, StudyMode, Template, thuật toán; đối chiếu với [canonical plan](../../architecture/study-interaction-trigger-algorithm-plan.md) §6, §9, §14.3, §14.4, Phase 8 và Phụ lục B, cùng [`PRODUCT.md`](../../../PRODUCT.md), [`DESIGN.md`](../../../DESIGN.md), [ADR phím tắt tin cậy](../../architecture/trusted-study-keyboard-boundary-2026-09-07.md), [chính sách phạm vi nhiều NoteType](../../architecture/mixed-notetype-study-scope-policy-2026-09-09.md) và [P8/P9 readiness](./P8_P9_READINESS_2026-09-30.md).
>
> Phương pháp: đọc code và truy vết luồng. Chưa chạy trình duyệt và chưa đọc dữ liệu production. Mục cần xác nhận bằng trình duyệt có ghi *(cần xác minh trình duyệt)*. Bằng chứng ghi theo `file:dòng` tại commit trên.

## 1. Kết luận

1. **Backend đã tách xong, UI chưa theo kịp.** Tiến độ theo learner/Note (P5), Card/Template chỉ còn vai trò trình bày (P6), phiên có retention (P7), có composition API và ReviewAction ngữ nghĩa. Tuy vậy, màn học vẫn cứng theo mô hình "flashcard lật thẻ + 4 nút". Bộ chọn "chế độ" thực chất chỉ là danh sách Template, còn Browse vẫn hiển thị theo Card.
2. **Có hai lỗi P0 về phục hồi dữ liệu người học** (§3.A):
   - phiên quá hạn lease 24 giờ vẫn cho trả lời, sau đó commit bị `410` và không được xử lý;
   - lỗi đồng bộ vĩnh viễn để lại vòng quay chờ vô hạn, không có lối thoát trong phiên.

   Kế hoạch gốc đã ghi hai lỗ hổng này (Phụ lục B #2, #3; §14.3 "permanent-conflict/retry/discard UX") nhưng chưa có task nào đóng chúng.
3. **Thuật ngữ, màu và hướng dẫn không khớp với code** (§3.D). Trang phím tắt mô tả sai phím `F`, liệt kê các phím và tính năng không tồn tại, và chỉ tới màn "Deck Settings" mà SPA không có. Ba màn dùng ba bộ màu khác nhau cho Mới/Đang học/Đến hạn.
4. **UI chưa sẵn sàng cho Phase 8** (§4). Trước khi thêm chế độ đầu tiên cần tách "Interaction host" khỏi `StudyPage`, tổng quát hóa event và thống kê cục bộ khỏi bốn rating, và thêm metadata StudyMode vào API. Ô nhập phản hồi cũng phải nằm ở host tin cậy, không đặt trong iframe Template.
5. **Đề xuất trình tự** (§5):
   - **U1**: an toàn và phục hồi, không redesign;
   - **U2**: nhất quán thuật ngữ, màu và hướng dẫn;
   - **U3**: luồng vào học theo StudyMode;
   - **P8-00**: Interaction host;
   - sau đó mới đến năng lực P8 đầu tiên.

   U1 và phần frontend của P9-08/P9-09 cùng sửa `features/study`, nên cần xếp lịch tránh xung đột.

Điểm đã đạt, cần giữ nguyên:
- màn xung đột nhiều tab (`StudySessionConflict.tsx`) có focus tiêu đề, `aria-live`, yêu cầu bàn giao và "Buộc mở";
- các thẻ lỗi phạm vi (`StudyScopeErrorCard.tsx`) phân loại 403/404/không có thẻ, có CTA hợp lý;
- ranh giới semantic `ReviewAction` (`interactions/reviewInteraction.ts:41`);
- ADR phím tắt tin cậy;
- bottom bar tôn trọng safe-area.

## 2. Năng lực đã giao và cách UI đang phản ánh

| Năng lực sau decoupling | Backend hiện có | UI hiện tại | Khoảng trống |
|---|---|---|---|
| Tiến độ theo learner/Note (P5, P6) | NOTE authority 18/18 learner; đếm theo Note (D6-04) | Browse một dòng mỗi Card, không có cột Template; hướng dẫn vẫn nói "mỗi thẻ có hệ số độ khó riêng" | UX-E1, UX-D2 |
| StudyMode / applied composition (P3) | `GET /api/study/scopes/deck/{id}/compositions`; mỗi composition có `mode_key`, `interaction_key`, `algorithm_key` (`app/services/study_composition_service.py:51-70`) nhưng hiện chỉ có `flashcard` / `review.four-rating` / `legacy-anki` (dòng 25-27) | Màn "Chọn kiểu thẻ" liệt kê tên Template, không nhớ lựa chọn, không có số lượng | UX-B1..B4 |
| Action/Trigger ngữ nghĩa (P2) | Bốn Action `review.*`, adapter một chiều | Page state machine cứng: lật thẻ → quyết định → rating | UX-C1 |
| Phiên bền (IndexedDB, lease, rollover, takeover) | Lease 24 giờ (`study_session_service.py:137`), rollover 50 event (`studySessionEngine.ts:50`) | Takeover tốt; hết hạn, xung đột vĩnh viễn và mất lưu trữ bền đều không có UX | UX-A1..A6 |
| Retention phiên (P7) | Phiên quá hạn thành `expired`, commit muộn trả `410 SESSION_EXPIRED` (`study_session_service.py:1423-1427, 2256-2261`) | Không xử lý `410` | UX-A1 |
| Algorithm registry, SchedulerPreset | Chỉ `legacy-anki/1.0.0` (`scheduler/algorithmRegistry.ts:11-12`); preset chỉ có hàm resolve (`scheduler_config_service.py:93-154`), không có API ghi | Không có màn cài đặt ôn tập; hướng dẫn chỉ tới màn không tồn tại | UX-E3, UX-D2 |
| Thuật ngữ `StudyMode` và `ReviewKind` (§9.4) | Admin API trả `modes_breakdown` nhưng dữ liệu là review/learn/relearn (`admin_analytics_repository.py:457`, `admin_analytics_service.py:188`) | Type frontend còn giữ `modes_breakdown` (`features/admin/types/analytics.ts:107`) | UX-E5 |

## 3. Phát hiện chi tiết

Mức độ:
- **P0**: người học mất công sức hoặc bị kẹt, không tự thoát được;
- **P1**: sai lệch rõ, gây hiểu nhầm, hoặc chặn P8;
- **P2**: nhất quán, chất lượng;
- **P3**: nhỏ.

### A. Phục hồi lỗi và an toàn dữ liệu

**UX-A1 (P0) — Phiên quá hạn lease vẫn cho trả lời; commit `410` không được xử lý.**
- Bằng chứng:
  - Client chỉ đọc `expires_at` lúc khởi động, và chỉ để dọn phiên *không có* việc chưa xác nhận (`hooks/useStudySession.ts:321-331`). Phiên còn câu trả lời chờ được giữ lại và kích hoạt.
  - Không có kiểm tra hạn trước khi trả lời, và không có handler `visibilitychange`. Chỉ có handler `online` (`useStudySession.ts:166-167`).
  - Trong `features/study` (ngoài test) không có nhánh nào xử lý `410` hay `SESSION_EXPIRED`.
  - Server từ chối mọi commit hoặc batch sau `expires_at` (`study_session_service.py:1423-1427, 2256-2261`).
- Kịch bản:
  1. Người học trả lời 10 thẻ khi mất mạng, gập máy (flush lúc `pagehide` thất bại).
  2. Hôm sau mở lại deck: phiên cũ được khôi phục, người học tiếp tục trả lời.
  3. Lần commit đầu nhận `410`. Toàn bộ câu trả lời sau hạn không được áp dụng, và màn hình rơi vào UX-A2.
- Đề xuất:
  - Kiểm tra hạn lease trước mỗi lần trả lời và khi tab hiện lại.
  - Khi lease còn ít thời gian (ví dụ dưới 30 phút) thì rollover chủ động: commit rồi mở phiên mới.
  - Nếu đã quá hạn thì không cho trả lời tiếp, báo rõ "Phiên học đã hết hạn", cách ly event cũ (không xóa; P9-08 cũng yêu cầu "không xóa IndexedDB hàng loạt hoặc replay tự động") và mở phiên mới.
  - Cần quyết định D-U1.

**UX-A2 (P0) — Lỗi đồng bộ vĩnh viễn: vòng quay chờ vô hạn, không có lối thoát trong phiên.**
- Bằng chứng:
  - Commit lỗi thì `setError` rồi `throw`, phiên giữ `pending_commit` (`useStudySession.ts:756-757`).
  - `blockingCommit` có hiệu lực khi đang `pending_commit` và có lỗi (`pages/StudyPage.tsx:399-404`). Vùng thẻ bị thay bằng `PageLoading "Đang đồng bộ phiên học…"` (dòng 468-471), phía trên là `PageError` (dòng 451-455).
  - Menu "Tải lại phiên học" gọi `reloadSession()`: hàm này commit lại, thất bại thì `return` (`useStudySession.ts:1141-1142`).
  - Lối thoát duy nhất có "Thử lại" kèm cách ly (`reloadSession(true)`) chỉ hiện khi *không có* phiên (`StudyPage.tsx:386-397`).
  - Rời trang rồi quay lại thì phiên `pending_commit` được khôi phục và tự commit lại (`useStudySession.ts:775-788`), nên lỗi lặp lại.
- Mã lỗi bị ảnh hưởng: `CARD_PROGRESS_CONFLICT` (409, `study_session_service.py:2389, 2494, 2608`), `SESSION_EXPIRED` (410), `FINAL_STATE_MISMATCH`, `BATCH_FAILED` và các mã khác.
- Đề xuất: thêm màn "Không thể đồng bộ N câu trả lời":
  - phân loại lỗi tạm thời (mạng, 5xx, `BATCH_PENDING`: tự thử lại, giữ trạng thái) và lỗi vĩnh viễn (409, 410, 422);
  - hành động: *Thử lại*; *Giữ bản sao và bắt đầu phiên mới* (dùng `acknowledgeStudySessionQuarantine` đã có); *Gửi hỗ trợ* kèm mã phiên và mã lỗi;
  - không tự xóa dữ liệu.

  Mục này đóng Phụ lục B #3 của canonical plan.

**UX-A3 (P1) — Không báo khi mất khả năng lưu bền.** `sessionDurableRef` được gán ở mọi lần lưu (`useStudySession.ts:157, 314, 394, 455, …`) nhưng UI không đọc giá trị này. Khi IndexedDB không dùng được (một số chế độ duyệt riêng tư, hết quota), tiến độ chỉ còn trong bộ nhớ tab mà người học không biết (Phụ lục B #2). Đề xuất: hiện nhãn "Tiến độ đang chỉ lưu tạm trong tab này", hạ ngưỡng rollover để commit sớm, và cảnh báo trước khi đóng tab.

**UX-A4 (P1) — Nút "Thoát không lưu tiến độ này" mâu thuẫn với hành vi thật.** Handler chỉ gọi `blocker.proceed()` (`StudyPage.tsx:79-81`). Khi rời trang, hook vẫn gọi `flushOnExit()` trong cleanup và lúc `pagehide` (`useStudySession.ts:955-972`), gửi batch qua keepalive. Nếu gửi thất bại, dữ liệu vẫn nằm trong IndexedDB và được commit ở lần mở sau. Như vậy nút hứa "không lưu" nhưng thực tế vẫn lưu *(cần xác minh trình duyệt)*. Hành vi lưu đúng với ràng buộc "không mất dữ liệu", nên chỉ cần sửa nhãn và mô tả, ví dụ: "Rời đi — tự đồng bộ sau". Nếu sản phẩm thật sự muốn hủy câu trả lời thì đó là quyết định riêng. Test `StudyPage.test.tsx:622` chỉ kiểm tra trang không gọi `commit`, không bao phủ flush của hook.

**UX-A5 (P1) — Thông báo kỹ thuật hoặc tiếng Anh lộ ra người học.**
- `PageError` luôn có tiêu đề "Không thể tải dữ liệu" và in nguyên `error.message` (`shared/components/PageState.tsx:13-21`), kể cả khi lỗi thực chất là lỗi đồng bộ.
- Thông điệp có thể tới người học:
  - `'Study session lease is not held by this window.'` (`useStudySession.ts:489…577`);
  - `'Study renderer ABI mismatch.'` (`renderer/clientRenderer.ts:495`);
  - `'Card is not part of the active session.'` (`session/studySessionEngine.ts:182, 223`);
  - `'Phiên học cũ không có composition đã khóa…'` (`useStudySession.ts:657, 729`);
  - server `'Study session has expired.'`;
  - các chuỗi chứa "batch", "event", "receipt" (`session/noteBatchTransport.ts:27-144`).
- Chuỗi quarantine còn chèn mã lý do thô vào câu (`useStudySession.ts:318`).
- `DESIGN.md` yêu cầu "Error messages hữu ích".
- Đề xuất: một bảng ánh xạ `error.code` sang thông điệp cho người học kèm hành động; mã kỹ thuật chỉ hiện trong mục "Chi tiết để gửi hỗ trợ".

**UX-A6 (P2) — Trạng thái đồng bộ quá mờ.** Chỉ có dòng chữ 11px "N trả lời chưa đồng bộ" (`StudyPage.tsx:443-447`). Dòng này bị ẩn khi toàn màn hình, không có trạng thái đang gửi / lỗi / đã lưu, và không có `aria-live`. Đề xuất: một chỉ báo đồng bộ nhỏ, ổn định ở header, đọc được bằng trình đọc màn hình.

### B. Luồng vào học và StudyMode

**UX-B1 (P1, chặn P8) — Bộ chọn là "chọn Template", chưa phải "chọn chế độ học".**
- Bằng chứng:
  - Tiêu đề "Chọn kiểu thẻ", mô tả mang tính kỹ thuật "Chọn đúng một kiểu; lựa chọn sẽ được khóa cho toàn bộ phiên học" (`StudyPage.tsx:352-359`).
  - Mỗi lựa chọn chỉ có `template_name` và loại ngữ cảnh sở hữu (`components/StudyModeSelector.tsx:50-57`).
  - API không trả nhãn chế độ, mô tả, icon hay số Note mới / đến hạn theo từng lựa chọn (`study_composition_service.py:51-70`).
- Tác động:
  - Hôm nay bộ chọn hiếm khi xuất hiện: production 40.227 Note = 40.227 Card theo [P6 D6-04](./P6_EXECUTION_PLAN_2026-09-29.md), nên phần lớn deck chỉ có một composition.
  - Khi P8 thêm chế độ, bộ chọn sẽ thành màn vào học hằng ngày, và người học phải chọn giữa các tên Template như "Card 2" (UX-E2).
- Đề xuất:
  - Thẻ StudyMode gồm tên chế độ (Lật thẻ / Nghe / Trắc nghiệm / Gõ đáp án…), mô tả một dòng, icon theo `mode_key`, số Note mới / đến hạn của đúng lựa chọn đó, và nhãn "Dùng lần trước".
  - Mở rộng `study-scope-compositions` với metadata và số đếm (đọc theo tập hợp, cùng cách đếm như P5-11e).

**UX-B2 (P1) — Không nhớ lựa chọn, không chọn trước được từ Dashboard.**
- Mỗi lần vào deck có từ 2 composition trở lên, người học phải chọn lại (`useStudySession.ts:384-387, 1169-1173`).
- Mọi điểm vào chỉ truyền `deck_id`: Dashboard (`app/api.ts:150`), Marketplace (`DeckCard.tsx:446, 475`, `SharedDeckDetailPage.tsx:817`), Browse (`BrowsePage.tsx:253`), Statistics (`StatisticsPage.tsx:166`).
- [Chính sách P3-05](../../architecture/mixed-notetype-study-scope-policy-2026-09-09.md) cấm *server* tự chọn. Client vẫn có thể làm nổi bật lựa chọn lần trước (người học vẫn phải bấm một lần), hoặc Dashboard có thể gửi `composition_id` rõ ràng qua nút "Học tiếp: Nghe". Cần quyết định D-U2, liên quan câu hỏi mở 16.3 #10.

**UX-B3 (P1) — Màn hoàn thành gây hiểu nhầm.**
- Theo chính sách, phiên chỉ gồm composition đã chọn. Màn hoàn thành vẫn nói "Tất cả các thẻ cần học hôm nay đã được ôn tập xong" (`components/StudyCompletionCard.tsx:177-181`) dù các chế độ hoặc NoteType khác trong deck còn thẻ đến hạn.
- Khối "Trạng thái thẻ trong Deck" (dòng 251) thực ra lấy số đếm của phiên (`StudyPage.tsx:405, 420`), nên khác với số Dashboard (đếm theo Note trên toàn deck).
- Phiên không có câu trả lời nào vẫn hiện "Tỉ lệ đúng 100%" (`StudyCompletionCard.tsx:83, 148`) và nút "Kết thúc & Đồng bộ phiên" (dòng 297).
- Đề xuất:
  - đổi câu chữ thành "Xong phần <chế độ>";
  - hiển thị phần còn lại theo từng chế độ, có CTA học tiếp;
  - ẩn tỉ lệ đúng khi chưa có lượt nào;
  - bỏ khái niệm "đồng bộ" khỏi CTA chính (hệ thống đã tự commit khi hoàn tất).

**UX-B4 (P2) — Chưa có điểm vào học theo NoteType.** Backend hỗ trợ scope `note_type` (plan §1.2; `types.ts` có `scope_type: 'deck' | 'note_type'`), nhưng route `/study` chỉ đọc `deck_id` (`StudyPage.tsx:28`) và `fetchStudyScopeCompositions` gắn cứng `deck` (`api.ts:24-27`). Cần quyết định trước P8 nếu muốn có chế độ như "Luyện nghe mọi Note kiểu X".

### C. Màn học và tương tác

**UX-C1 (P1, chặn P8) — `StudyPage` là state machine riêng của flashcard.**
- Trang tự giữ `revealedCardKey`, `decisionState: SchedulerDecision` và bảng phím `1..4 → again/hard/good/easy` (`StudyPage.tsx:31-35, 114-158, 207-281`).
- `ReviewInteractionControls` nhận `revealed` và bốn nút cố định (`interactions/ReviewInteractionControls.tsx:54-131`), còn nhận luôn các prop số đếm không dùng tới (dòng 21-23).
- Plan §14.3 gạch đầu dòng 1 ("Extract StudyBottomBar behavior into the first built-in Interaction Component") mới đạt ở mức semantic Action, chưa có hợp đồng host.
- Nếu thêm trắc nghiệm hoặc gõ đáp án ngay bây giờ thì phải viết lại trang. Xem P8-00 ở §4.

**UX-C2 (P1) — Phím tắt tắt âm thầm khi focus nằm trong iframe thẻ.**
- Đây là hành vi có chủ đích theo ADR phím tắt tin cậy, nhưng không có tín hiệu nào cho người học: iframe chỉ có `title` (`components/CardRendererFrame.tsx:216-217`), còn `handleFocusBack` chỉ bỏ focus khỏi `button`/`a` (`StudyPage.tsx:283-290`).
- Với chế độ Nghe hoặc Gõ, người học sẽ thường xuyên bấm vào nội dung thẻ.
- Đề xuất:
  - chỉ báo "Nhấp ra ngoài thẻ để dùng phím tắt" khi `document.activeElement` là iframe;
  - quy định ô nhập và phương án trả lời của chế độ mới do host render, không đặt trong iframe.

**UX-C3 (P2) — Nút giữ focus sau khi bấm chuột; Space/Enter kích hoạt lại nút đó** *(cần xác minh trình duyệt)*. Handler phím bỏ qua sự kiện khi phần tử đang focus là `button` (`StudyPage.tsx:235-241`), nên trình duyệt thực thi click mặc định. Sau khi bấm chuột vào "Hoàn tác" hoặc "Toàn màn hình" (các nút này không unmount), một lần nhấn Space có thể hoàn tác thêm một lần hoặc bật/tắt toàn màn hình thay vì lật thẻ. Đề xuất: blur sau khi click bằng con trỏ, hoặc xử lý Space/Enter ở cấp trang cho các control của bottom bar.

**UX-C4 (P2) — Hạn chế trên di động và lớp CSS chết.**
- Sau khi lật thẻ, di động không có nút Hoàn tác: nút di động chỉ hiện khi `!revealed` (`components/StudyBottomBar.tsx:67`), nút desktop dùng `hidden sm:flex` (dòng 46).
- `xs:` được dùng (`StudyBottomBar.tsx:80`, `ReviewInteractionControls.tsx:64`) nhưng Tailwind v4 không có breakpoint `xs` mặc định và `src/index.css` không khai báo, nên nhãn "Hoàn tác" và icon của "Học lại" không bao giờ hiện.
- Muốn sửa thì phải quyết định hiện hay bỏ; đây là thay đổi hình thức, cần duyệt theo quy tắc Zero Visual Regression.

**UX-C5 (P2, cần cho chế độ Nghe) — Host không có điều khiển nghe lại âm thanh.** Âm thanh chỉ phát khi Template gửi `play_audio`/`pause_audio` (`static/js/card_renderer_host.js:1028-1035`). Không có nút "Nghe lại" hay phím tắt tin cậy ở host.

**UX-C6 (P3) — Trợ năng khi lật thẻ.** Việc lật thẻ chỉ đổi `title` của iframe (`CardRendererFrame.tsx:216`); không có thông báo `aria-live` "Đã hiện đáp án", và không có liên kết khoảng thời gian dự kiến với từng nút đánh giá.

**UX-C7 (P2) — Sửa Template trong lúc học không có phản hồi.** Đúng thiết kế P4-00, phiên đang mở giữ Template cũ. Tuy nhiên toast chỉ nói "Đã lưu Template." (`note-types/pages/NoteTypeDetailPage.tsx:113`), và lời gọi `updateTemplateInSessions` là no-op (`session/sessionStore.ts:591-599`; tương tự `useStudySession.ts:1116-1123`). Đề xuất: thông báo "Áp dụng từ phiên học tiếp theo"; xóa các no-op khi dọn code ở P9-09.

### D. Nhất quán thuật ngữ, màu và hướng dẫn

**UX-D1 (P1) — Bảng phím tắt sai so với code** (`features/guide/guideData.ts:262-272`):
- `F` được mô tả là "Ẩn/Hiện Furigana", nhưng code dùng `F` cho toàn màn hình (`StudyPage.tsx:251, 273-279`).
- `R / F5` "Phát lại âm thanh" không tồn tại; `F5` tải lại trang.
- `* / -` "Gắn cờ (Flag)" không tồn tại; không có model hoặc UI cờ.
- Bảng không nhắc giới hạn khi focus nằm trong thẻ (UX-C2).

**UX-D2 (P1) — Hướng dẫn chỉ tới tính năng không có và mô tả mô hình cũ.**
- Mục khắc phục sự cố hướng dẫn "Cài đặt Bộ thẻ (Deck Settings) → Số thẻ mới mỗi ngày" (`guideData.ts:935-936`), và trang quản trị deck liệt kê New/day, Max reviews/day, Pinned (`guideData.ts:153-172`). SPA không có route, component hay API ghi cho các mục này (UX-E3).
- Mục thuật toán viết "Mỗi thẻ có một hệ số độ khó riêng" (`guideData.ts:250`), trong khi từ P5 tiến độ thuộc learner/Note và dùng chung cho mọi Template hay chế độ.

**UX-D3 (P2) — Màu trạng thái hàng đợi không nhất quán giữa các màn.**

| Màn | Mới | Đang học | Đến hạn |
|---|---|---|---|
| Dashboard `DeckRow.tsx:186-194` | emerald | **rose** | **orange** |
| Header phiên `StudyHeaderToolbar.tsx:221-235` | emerald | amber (nhãn "Học") | rose |
| Hoàn thành `StudyCompletionCard.tsx:255-273` | emerald | amber | rose |
| Chờ learning `StudyWaitingCard.tsx` | muted | amber | muted |

`DESIGN.md` quy định Learning = amber, Destructive = đỏ; `PRODUCT.md` yêu cầu "một semantic color … cùng ý nghĩa trên mọi màn hình". Đề xuất: token ngữ nghĩa (`--status-new`, `--status-learning`, `--status-due`, `--rating-again…easy`) dùng chung cho mọi màn, kể cả khi thêm chế độ mới.

**UX-D4 (P2) — Thuật ngữ đánh giá và số liệu không thống nhất.**
- Nhãn nút là "Học lại", màn hoàn thành ghi "Quên" (`StudyCompletionCard.tsx:228`), `DESIGN.md` ghi "Good (Được)" trong khi UI ghi "Tốt".
- "Đã ôn N **thẻ**" (dòng 192) thực ra là số **lượt** (dòng 223 ghi "lượt").
- "Tỉ lệ đúng" = (Tốt + Dễ) / tổng (dòng 65-67, 130-132), trùng định nghĩa analytics (`app/repositories/stats_query_repository.py:684, 780`), nhưng UI không giải thích rằng "Khó" không được tính là đúng (khác quy ước Anki). Cần quyết định D-U6.

**UX-D5 (P2) — Trộn tiếng Anh và tiếng Việt trong cùng màn.**
- Header phiên học: "Decks / Study / Stats / Import / Browse" (`StudyHeaderToolbar.tsx`).
- Menu deck: "Deck Settings / Share Deck / Reset Progress / Delete Deck" (`DeckRow.tsx:210-279`).

Nên gộp vào [task i18n](../../tasks/MULTILINGUAL_I18N_MIGRATION_TASK.md) thay vì sửa lẻ.

**UX-D6 (P2) — Thuật ngữ nội bộ lộ ra người học.**
- "learning step", "cửa sổ học sớm", "Mốc ôn danh nghĩa", "thẻ chờ learning step" (`StudyWaitingCard.tsx:52-53, 66, 93`).
- "composition", "batch", "event", "receipt" (UX-A5).

### E. Các màn ngoài phiên học

**UX-E1 (P1 khi P8 bật nhiều application) — Browse vẫn lấy Card làm trung tâm.**
- Mỗi Card là một dòng, cột cố định "Từ vựng / Đọc / Ý nghĩa" và không có cột Template hay chế độ (`features/browse/components/BrowseCardTable.tsx:87-107`).
- Xóa theo Card; khi xóa Card cuối cùng thì xóa luôn Note (`app/services/browse_card_service.py:1143-1158`).
- Khi một Note có nhiều application, nó sẽ hiện nhiều dòng giống nhau với cùng một tiến độ, và thao tác "xóa thẻ" không nói rõ tiến độ vẫn thuộc Note.
- Đề xuất: chế độ xem theo Note (một dòng mỗi Note, liệt kê các chế độ đang gắn), và câu chữ phân biệt "gỡ một cách trình bày" với "xóa Note". Cần quyết định D-U5.

**UX-E2 (P1, chặn phần authoring của P8) — Trình soạn NoteType chỉ là trình sửa HTML Template.**
- Template mới được đặt tên "Card N" (`NoteTypeDetailPage.tsx:132`).
- Chưa có khái niệm chế độ (`mode_key`), Interaction, binding đầu vào, hay mô tả hiển thị trong bộ chọn (plan §14.4).
- Xác nhận khôi phục mặc định dùng `window.confirm` (dòng 324), không phải dialog của design system.
- Theo [D6-09](./P6_EXECUTION_PLAN_2026-09-29.md), UI gắn lặp lại application đi cùng P8.

**UX-E3 (P1) — Không có màn cài đặt ôn tập.** Không có route, component hay API ghi cho SchedulerPreset: số thẻ mới mỗi ngày, learning steps, thuật toán (`scheduler_config_service.py` chỉ có các hàm `resolve_*`). Writer chuyển Algorithm của P5-08 đã có nhưng chưa có route. Nếu năng lực P8 đầu tiên là một Algorithm (ví dụ non-repetition), cần màn chọn thuật toán và màn xác nhận chuyển đổi dựa trên lịch sử, có cảnh báo về mức đầy đủ của lịch sử. Cần quyết định D-U3.

**UX-E4 (P2) — "Đặt lại tiến độ" không nói rõ phạm vi mới.** Hộp thoại chỉ hỏi "Đặt lại toàn bộ tiến độ học … trong <deck>?" (`dashboard/components/DeckModals.tsx:295`). Câu hỏi này không nói rằng tiến độ theo Note dùng chung cho mọi chế độ học, cũng không nói lịch sử có còn hay không. Nhãn menu vẫn là tiếng Anh "Reset Progress".

**UX-E5 (P1, điều kiện tiên quyết của P8) — Analytics và thống kê phiên gắn cứng bốn rating.**
- Analytics tính "đúng" bằng chuỗi `good/easy/3/4` (`stats_query_repository.py:684, 780`; `admin_analytics_repository.py:86, 338`).
- Thống kê tích lũy của phiên đếm `again/hard/good/easy`, và đoạn này bị lặp lại hai lần (`useStudySession.ts:625-646` và `697-718`).
- Màn hoàn thành vẽ cứng bốn ô đánh giá.
- `modes_breakdown` thực chất là ReviewKind (§9.4 plan).
- Chế độ trắc nghiệm hoặc gõ đáp án sinh ra *outcome* (đúng / sai / gần đúng), không phải rating. Nếu không tổng quát hóa trước, số liệu của chế độ mới sẽ bị ép vào bốn nút hoặc bị bỏ sót.

## 4. Mức sẵn sàng UI cho Phase 8

[P8/P9 readiness §2](./P8_P9_READINESS_2026-09-30.md#2-phase-8--cần-chủ-sản-phẩm-chọn-năng-lực-đầu-tiên) yêu cầu mỗi năng lực định nghĩa input, schema Action, trigger, Algorithm State, availability, mức tin cậy, giữ phiên bản và migration. Bảng dưới là phần UI tương ứng.

| # | Điều kiện UI | Hiện trạng | Việc cần làm | Ghi chú |
|---|---|---|---|---|
| P8-UI-1 | Interaction host tách khỏi `StudyPage` | Chưa có (UX-C1) | Định nghĩa hợp đồng host ↔ component: vòng đời present → respond → feedback → emit Action; host sở hữu phím tắt tin cậy, gating và mutex; bốn nút hiện tại là instance đầu tiên | Refactor, zero visual regression |
| P8-UI-2 | Event, outcome và thống kê tổng quát | `rating` là field bắt buộc trong event (`types.ts:229-238`) và stats | Kiểu event có `action_key` + payload phiên bản hóa; bốn rating chỉ còn trong adapter built-in; stats theo outcome | Gộp hoặc xếp lịch cùng P9-09 ("generic types giả định bốn rating") |
| P8-UI-3 | Bề mặt nhập liệu tin cậy | Mọi nội dung tương tác nằm trong iframe sandbox | Ô gõ, phương án trắc nghiệm, nút nghe lại do host render ngoài iframe; iframe chỉ trình bày | Theo ADR phím tắt tin cậy và plan §6.3 |
| P8-UI-4 | Phản hồi tạm thời và đối soát | Chưa có | Hiện kết quả ngay (client evaluator); khi server chấm khác thì hiện đối soát rõ, không lặng lẽ đổi tiến độ | Plan §6.3; cần golden vectors client/server |
| P8-UI-5 | Metadata và số đếm StudyMode | Thiếu (UX-B1, B2) | Mở rộng API compositions; thiết kế lại bộ chọn; nhớ lựa chọn lần trước | Tuân thủ P3-05: không tự chọn |
| P8-UI-6 | Màn hoàn thành và thống kê theo chế độ | Cứng 4 ô (UX-B3, E5) | Tổng kết theo outcome của chế độ; phần còn lại theo chế độ | |
| P8-UI-7 | Authoring chế độ | Chỉ sửa HTML (UX-E2) | Gắn application vào NoteType, binding input, xem trước với dữ liệu mẫu, không ghi tiến độ | Plan §14.4, D6-09 |
| P8-UI-8 | Chọn và chuyển Algorithm | Không có (UX-E3) | Chỉ cần nếu năng lực đầu tiên là Algorithm | Writer P5-08 đã có |
| P8-UI-9 | Tách thuật ngữ `StudyMode` và `ReviewKind` | Chưa tách (UX-E5) | Đổi tên `modes_breakdown` → `review_kinds_breakdown` (giữ alias đọc cũ) | Plan §9.4 |
| P8-UI-10 | Phục hồi phiên an toàn | Thiếu (UX-A1..A3) | Phải xong trước: chế độ gõ và trắc nghiệm lưu raw response, nên mất dữ liệu sẽ đắt hơn | U1 |

Chi phí UI của các lựa chọn năng lực đầu tiên (chủ sản phẩm quyết định, D-U4):

| Năng lực | Cần evaluator/verifier mới? | Điều kiện UI | Rủi ro UX | Nhận xét |
|---|---|---|---|---|
| **Nghe** (audio ở mặt trước, vẫn tự đánh giá 4 nút) | Không | P8-UI-1 (một phần), UI-5, UI-7, nút nghe lại ở host (UX-C5) | Thấp | Kiểm chứng được toàn bộ luồng StudyMode (metadata, bộ chọn, application lặp lại theo D6-09) mà không đụng verifier; phù hợp làm lát đầu |
| **Trắc nghiệm** | Có (phương án đóng băng trong snapshot, verifier xác định) | UI-1..UI-7 | Trung bình | Chế độ "mới thật" đầu tiên; cần quyết định cách sinh phương án nhiễu và ánh xạ outcome → Trigger |
| **Gõ đáp án** | Có (chuẩn hóa kana/kanji, IME, furigana) | UI-1..UI-7, xử lý IME (`isComposing`) | Cao | Nên làm sau trắc nghiệm |
| Algorithm non-repetition | Không (nhưng cần Algorithm State mới) | UI-8, UI-6 | Trung bình | Không phải "chế độ" theo nghĩa người dùng hiểu |
| Consumer analytics/XP | Không | UI-6, UI-9 | Thấp về UI | Cần outbox; ít giá trị "chế độ mới" |

## 5. Kế hoạch nâng cấp đề xuất

Nguyên tắc chung:
- **U1** và **P8-00** là refactor, giữ nguyên hình thức, trừ các màn lỗi mới.
- **U3** là redesign có phạm vi, chỉ bắt đầu sau khi chủ sản phẩm duyệt; dùng `$impeccable` và `$flama-frontend-architecture`.
- Mọi đợt giữ các invariant decoupling: không mất dữ liệu learner, không mutate source note trong clone, và iframe không nhận quyền ghi tiến độ.

| Đợt | Nội dung | Phát hiện đóng | Phụ thuộc / phối hợp | Ước lượng |
|---|---|---|---|---|
| **U1 — An toàn và phục hồi** | Kiểm tra hạn lease và rollover chủ động; màn sự cố đồng bộ (thử lại / cách ly + phiên mới / gửi hỗ trợ); chỉ báo lưu bền; sửa nhãn thoát; ánh xạ mã lỗi sang thông điệp; sửa focus sau click; sửa hướng dẫn phím tắt và "Deck Settings" | A1–A6, C3, D1, D2 | D-U1. Cùng file với P9-08 phần frontend ("pending data cũ được quarantine/hiển thị trạng thái rõ"): làm U1 trước hoặc gộp | 3–5 ngày |
| **U2 — Nhất quán** | Token màu trạng thái và rating; bảng thuật ngữ (Học lại / Khó / Tốt / Dễ, "lượt" vs "Note"); Việt hóa header và menu deck; bỏ thuật ngữ nội bộ; copy "Đặt lại tiến độ" theo Note; thông báo "áp dụng từ phiên sau" | C4 (quyết định `xs:`), C7, D3–D6, E4 | Zero visual regression, trừ các thay đổi màu/nhãn đã duyệt; nối với task i18n | 2–3 ngày |
| **U3 — Luồng vào học theo StudyMode** | API compositions có metadata và số đếm; bộ chọn mới; nhớ lựa chọn; deep link `composition_id`; màn hoàn thành theo chế độ; (tùy chọn) scope NoteType | B1–B4, E5 (phần màn hoàn thành) | D-U2; redesign có phạm vi | 4–6 ngày |
| **P8-00 — Interaction host** | Tách host khỏi `StudyPage`; built-in four-rating thành component đầu tiên; event và stats tổng quát; bề mặt input tin cậy; chỉ báo focus iframe; nút nghe lại ở host | C1, C2, C5, C6, E5 (stats phiên) | Sau U1; phối hợp P9-09; golden vectors cho mọi adapter | 5–8 ngày |
| **P8-01 — năng lực đầu tiên** | Theo D-U4, lập `P8_EXECUTION_PLAN` theo mẫu P6 | tùy năng lực | U3 + P8-00; nếu là Algorithm thì thêm UX-E3 | theo kế hoạch riêng |

UX-E1 (Browse theo Note), UX-E2 (authoring) và UX-E3 (cài đặt ôn tập) nên thành work package riêng trong `P8_EXECUTION_PLAN`, tùy năng lực được chọn.

## 6. Quyết định cần chủ sản phẩm

| ID | Câu hỏi | Khuyến nghị |
|---|---|---|
| D-U1 | Khi lease sắp hết hoặc đã hết | Rollover chủ động trước hạn; nếu đã quá hạn thì chặn trả lời, cách ly dữ liệu cũ (không xóa, không tự replay), mở phiên mới và báo rõ |
| D-U2 | Có nhớ chế độ đã chọn theo deck không | Có, ở client: làm nổi bật "Dùng lần trước" và cho Dashboard gửi `composition_id` rõ ràng; server vẫn không tự chọn (P3-05) |
| D-U3 | Có màn cài đặt ôn tập trong đợt này không | Nếu chưa làm thì sửa hướng dẫn ngay ở U1; màn cài đặt làm cùng P8 khi có Algorithm thứ hai |
| D-U4 | Năng lực P8 đầu tiên | Nghe (lát mỏng, kiểm chứng StudyMode), rồi Trắc nghiệm (evaluator đầu tiên) |
| D-U5 | Browse chuyển sang theo Note khi nào | Cùng P8-01, trước khi bật application thứ hai cho learner |
| D-U6 | "Tỉ lệ đúng" có tính "Khó" không | Chốt một định nghĩa dùng chung cho màn hoàn thành và analytics, và ghi chú thích trên UI |

## 7. Kiểm chứng khi triển khai

- Test hẹp theo module: `python scripts/run_tests.py --module study --frontend-only`; khi đổi API compositions hoặc analytics thì thêm `--module study,analytics --backend-only`.
- Test mới cho mỗi phát hiện:
  - UX-A1: khôi phục phiên quá hạn còn event, và trả lời sau hạn;
  - UX-A2: commit 409/410/422 hiện màn sự cố, và "cách ly + phiên mới" không xóa event;
  - UX-A3: IndexedDB không dùng được;
  - UX-A4: rời trang sau "Rời đi";
  - UX-C3: Space sau khi click Hoàn tác.
- Luồng trình duyệt dùng profile Chrome riêng theo `AGENTS.md`:
  - mất mạng, trả lời, gập máy, mở lại sau khi lease hết hạn;
  - hai tab;
  - chế độ duyệt riêng tư;
  - focus trong iframe;
  - màn hình 360px, dark mode, `prefers-reduced-motion`.
- U2 cần ảnh chụp trước/sau cho mọi màn đổi màu hoặc nhãn.

## 8. Handoff

```text
Task ID: UIUX-AUDIT-PRE-P8
Primary outcome: danh mục khoảng trống UI/UX sau decoupling, kế hoạch nâng cấp U1–U3 và điều kiện UI cho Phase 8
Files changed: docs/task/decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md (mới); liên kết trong README.md và P8_P9_READINESS_2026-09-30.md
Runtime change: none
Contract/API behavior changed: none
Tests added or updated: none (điều tra)
Commands run: đọc code, grep; không chạy trình duyệt, không truy cập production
Known limitations: UX-A4 và UX-C3 cần xác minh trên trình duyệt; số liệu production lấy từ tài liệu P6, chưa đo lại
Follow-up task IDs: U1, U2, U3, P8-00, P8-01 (sau quyết định D-U1..D-U6)
```
