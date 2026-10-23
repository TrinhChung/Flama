# TD-19 — NoteType và Template Marketplace chạy trên bộ máy chia sẻ chung

> Mức: **P2** · Đợt: W5 · Trạng thái: `TODO`
>
> Phụ thuộc: TD-17, TD-18 · Lane: Backend + Frontend (marketplace, note-types) + Payment review · Ước lượng: 8–12 ngày
>
> Quyết định đã chốt ([điều tra §14](../../architecture/template-notetype-decoupling-investigation.md)): #1 (clone & fork như deck), #2 (tác giả Template sở hữu và bán được; người mua có quyền dùng, sửa thì fork), #10 (ghim phiên bản), #21 (xóa/hủy đăng là soft delete, người đã mua vẫn dùng). Liên quan TD-14 SE-06, SE-07.

## Mục tiêu

1. **NoteType marketplace** chuyển từ "copy toàn bộ khi cài" sang cùng vòng đời với deck: ghim release, fork khi sửa, nhận cập nhật, đóng góp ngược.
2. **Template Marketplace**: bán và chia sẻ riêng Template. Người dùng áp dụng Template cho NoteType của mình qua wizard ánh xạ (TD-18).

Cả hai đều là **loại gói** của engine chung (`package_kind = note_type | template`), không xây luồng riêng.

## Bối cảnh

- Cài NoteType hiện gọi `clone_note_type_for_user` và tạo bản sao mới hoàn toàn, không lưu vết nguồn (`app/services/share/note_types.py:451-548`).
- `NoteTypeInstall` duy nhất theo (nguồn, user).
- UI chợ gọi gói NoteType là "Template" ([điều tra §5.1](../../architecture/template-notetype-decoupling-investigation.md)).
- Thanh toán hiện đi qua payOS cho gói trả phí (`app/services/payment_service.py`, `marketplace_note_type_service.py`).

## Phạm vi file dự kiến

- Backend:
  - `app/services/marketplace_note_type_service.py`, `app/services/share/note_types.py`, `app/services/share_engine/package.py` (loại gói mới);
  - quyền sở hữu/quyền dùng (entitlement) cho gói trả phí;
  - API `app/api/v1/marketplace/*`.
- Model/migration: gói `note_type`/`template`; entitlement; lineage cho các bản cài NoteType cũ.
- Frontend:
  - `features/marketplace/*` (trang Template: xem trước sandbox với dữ liệu mẫu, "Áp dụng cho loại thẻ của tôi");
  - `features/note-types/*` (thư viện Template, nhãn nguồn gốc và cập nhật có sẵn).

## Công việc chi tiết

1. **NoteType là gói trên engine:**
   - release gồm `field_def`, `field_order`, `template`, `application`, `slot_binding`;
   - cài mới thì ghim release;
   - sửa thì fork install-local theo adapter;
   - có trang cập nhật và đóng góp như deck.
2. **Bản cài NoteType cũ:**
   - coi là "đã fork" (hành vi hiện tại không đổi);
   - chỉ backfill lineage khi chứng minh được bằng hash nội dung, không ghép theo vị trí mù;
   - cho người dùng tùy chọn "liên kết lại với bản gốc" có xem diff.
3. **Template là gói:**
   - listing, giá, preview, soft delete (#21);
   - cài vào thư viện là tham chiếu ghim;
   - áp dụng cho NoteType qua wizard ánh xạ Slot (TD-18);
   - sửa thì fork (#1, #2).
4. **Thanh toán và quyền:**
   - dùng lại luồng payOS và wallet hiện có cho gói trả phí;
   - cần review riêng với `docs/architecture/FLAMA_PAYMENT_ARCHITECTURE.md`;
   - người đã mua giữ quyền khi tác giả hủy đăng.
5. **Thuật ngữ:** "Loại thẻ" (NoteType) và "Mẫu thẻ" (Template) nhất quán trên mọi màn chợ (SE-07).
6. **An toàn nội dung:** Template từ người khác qua sanitizer + CSP + proxy media; review/báo cáo vi phạm dùng quy trình chợ hiện có.
7. **Deck đã phát hành dùng NoteType từ chợ:** phụ thuộc giữa gói được ghi rõ (deck ghim release NoteType), không phá bản cài cũ.

## Output đầu ra bắt buộc

Hai loại gói trên engine; migration + lineage; trang chợ Template; trang cập nhật/đóng góp cho NoteType; review thanh toán; tài liệu người dùng.

## Acceptance criteria

- Cài NoteType mới: tác giả cập nhật thì người cài thấy "có bản mới" và chọn apply, xung đột giải quyết được; sửa cục bộ không ảnh hưởng ai.
- Bản cài NoteType cũ hoạt động y như trước.
- Mua Template: áp dụng cho NoteType; tác giả hủy đăng thì người mua vẫn dùng; người chưa mua không cài được.
- Không có đường nào mutate Note/Card của người khác. Tiến độ Note không đổi.

## Verification

```text
python scripts/run_tests.py --module marketplace,flashcards,payment,decks,deck_collaboration --backend-only
python scripts/run_tests.py --module marketplace,flashcards --frontend-only
```

Kèm luồng trình duyệt mua/cài/áp dụng với profile Chrome riêng, và probe MySQL cho migration lineage.

## Rollback

Flag giữ luồng cài copy cũ cho NoteType; listing Template ẩn khi tắt flag; dữ liệu gói/entitlement giữ nguyên.

## Không làm trong task này

Template có Interaction mới (P8), gói có code JS chạy ngoài sandbox, xét duyệt tự động nội dung.
