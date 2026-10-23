# TD-17 — Fork Template install-local cho thẻ gốc và gửi đề xuất Template về tác giả

> Mức: **P1** · Đợt: W5 · Trạng thái: `TODO`
>
> Phụ thuộc: TD-16 · Chặn: TD-19 · Lane: Backend + Frontend (Note types, deck-collaboration, Study) · Ước lượng: 5–8 ngày
>
> Quyết định đã chốt ([điều tra §14](../../architecture/template-notetype-decoupling-investigation.md)):
> - #1, #10: dùng bản tham chiếu ghim, sửa thì fork copy-on-write;
> - #11: người học tùy biến giao diện cho bản clone của mình, fork **install-local**, không ảnh hưởng tác giả hay người khác;
> - #12: được dùng cùng một Template cho thẻ gốc và thẻ tự thêm;
> - #9: đóng góp Template ưu tiên thấp, nhưng có sẵn engine nên làm luôn ở đây.

## Mục tiêu

Người cài deck sửa được giao diện thẻ của **chính bộ đã cài**, kể cả thẻ gốc, không ảnh hưởng ai. Họ có thể gửi đề xuất sửa Template cho tác giả qua change request như cách gửi sửa nội dung. Việc này đóng các điểm J4 D1, D2, D3 của [báo cáo hành trình](../../backend/old/decoupling/UIUX_COMPLETED_PHASES_USER_JOURNEY_AUDIT_2026-09-30.md).

## Bối cảnh

- Hiện bản sao NoteType của người cài chỉ áp dụng cho Note tự thêm. Thẻ gốc luôn dùng Template tác giả (`study_artifact_service.py:118, 147`).
- `NoteTypeInstall` duy nhất theo (NoteType nguồn, user), nên nhiều deck cài cùng nguồn dùng chung bản sao (TD-14 SE-06).
- Không có model override Template trong overlay (`models/deck_clone_*`).

## Phạm vi file dự kiến

- Adapter `app/services/share_engine/kinds/template_override.py`: overlay theo `(install, source application/template)` với thuộc tính `name`, `front_html`, `back_html`, `shared_css`, `base_version_hash`.
- Sửa:
  - `study_artifact_service.py`, `study_composition_service.py` (context `installed_source` và `installed_local` phân giải override);
  - `study_session_service.py` (ghim version của override);
  - `browse_card_service.py`;
  - render MCP;
  - `deck_install_rebase_service.py` qua adapter (xung đột upstream vs override);
  - change request qua adapter (change type `template.update`).
- Frontend:
  - chế độ "Giao diện của bộ đã cài" dùng lại trình soạn Template (TD-04) với nguồn là install;
  - lối vào từ menu deck đã cài và từ header phiên học ("Tùy biến giao diện bộ này");
  - nút "Khôi phục giao diện của tác giả";
  - "Gửi đề xuất cho tác giả".

## Công việc chi tiết

1. **Phân giải trình bày cho install:**
   - có override thì dùng override;
   - không có thì dùng Template tại `applied_release` (TD-16).
   - Thẻ tự thêm trong install cũng dùng override khi người học chọn "áp dụng cho cả thẻ tự thêm" (#12). Cấu hình này để gộp hai nhóm Template và giải quyết một phần D-T3.
2. **Fork copy-on-write:**
   - lần sửa đầu tạo override từ version đang ghim;
   - lưu `base_version_hash`;
   - không copy Note/Card;
   - Card ID và tiến độ Note không đổi.
3. **Cập nhật từ tác giả:**
   - upstream đổi Template mà người cài có override thì phát sinh xung đột 3 chiều (base/upstream/local), giải quyết bằng: giữ bản mình, lấy bản tác giả, hoặc sửa tay;
   - override bằng upstream thì tự prune.
4. **Đóng góp:**
   - từ override tạo change request item `template.update` (diff escape và sanitize);
   - tác giả merge vào bản làm việc rồi phát hành;
   - người đóng góp apply thì override thừa được prune. Toàn bộ dùng chung engine, không có luồng riêng.
5. **Bảo mật:**
   - override vẫn qua sanitizer, CSP, `/media/proxy`, `sandbox="allow-scripts"`;
   - Template người khác gửi đến tác giả được xem trước trong sandbox.
6. **Phạm vi và vòng đời:**
   - override thuộc install; gỡ install thì xóa override (không đụng tiến độ);
   - bản sao NoteType theo user (`NoteTypeInstall`) giữ nguyên cho tương thích. Ghi rõ trong UI rằng tùy biến theo từng bộ đã cài.
7. **UI:**
   - chỉ báo "Đang dùng giao diện tùy biến" ở bộ chọn cách học và header phiên học;
   - so sánh với bản của tác giả;
   - thông báo "Áp dụng từ phiên học sau".
8. Cập nhật báo cáo hành trình (D-T1 `DONE`) và thay nhãn tạm của TD-07.

## Output đầu ra bắt buộc

Adapter `template_override`; phân giải trình bày cho install; rebase + change request qua engine; UI tùy biến, khôi phục, đóng góp; migration + rehearsal MySQL.

## Acceptance criteria

- Người cài A sửa giao diện: A thấy ở phiên sau. Tác giả, người cài B và các install khác của A không đổi (test hai tài khoản, hai install cùng nguồn).
- Tác giả phát hành Template mới: A thấy xung đột, giải quyết được; không mất override khi chọn "giữ bản mình".
- Change request Template: tác giả merge, phát hành, A apply thì override thừa được prune.
- Card ID, tiến độ Note, `ReviewEvent`, Connect `source_ord` không đổi trong mọi luồng.
- Phiên đang mở không đổi (P4-00).

## Verification

```text
python scripts/run_tests.py --module study,flashcards,decks,deck_collaboration,marketplace,browse,connect_mcp --backend-only
python scripts/run_tests.py --module flashcards,deck_collaboration,study --frontend-only
```

Probe MySQL cho xung đột đồng thời (A sửa override trong khi apply update). Luồng trình duyệt với hai tài khoản, profile Chrome riêng.

## Rollback

- Flag tắt phân giải override (quay về Template tại release); dữ liệu override giữ nguyên.
- Change type `template.update` ẩn khi tắt flag.

## Không làm trong task này

Slot/binding (TD-18), NoteType/Template marketplace (TD-19), gộp phiên thẻ gốc + thẻ tự thêm ở mức chính sách chọn composition (cần quyết định D-T3 riêng).
