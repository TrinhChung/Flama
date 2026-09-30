# TD-16 — Template và application thành entity kind có release; bản cài ghim phiên bản (6B #137)

> Mức: **P1** · Đợt: W5 · Trạng thái: `TODO`
>
> Phụ thuộc: TD-15 · Chặn: TD-17, TD-18 · Thay thế: hotfix tạm #138 · Lane: Backend + Frontend (Note types, deck-collaboration) · Ước lượng: 6–9 ngày
>
> Quyết định đã chốt: #10 (bản cài ghim phiên bản) ở [điều tra §14](../../architecture/template-notetype-decoupling-investigation.md); D6-08 (track 6B) ở [P6 plan](../decoupling/P6_EXECUTION_PLAN_2026-09-29.md).

## Mục tiêu

Tác giả sửa, thêm, xóa Template của NoteType đang có deck phát hành **như sửa field**: thay đổi vào bản làm việc, chỉ tới người cài khi tác giả phát hành, và người cài chọn thời điểm cập nhật. Việc này đóng các điểm J5 A1, A2 và D5 của [báo cáo hành trình](../decoupling/UIUX_COMPLETED_PHASES_USER_JOURNEY_AUDIT_2026-09-30.md), đồng thời loại bỏ lỗ hổng SE-04.

## Bối cảnh

- Guard `_ensure_version_safe_template_mutation` (`app/services/flashcard_content_service.py:1514-1554`): chặn mọi thay đổi cấu trúc Template bằng `409 SHARED_SCHEMA_VERSIONING_REQUIRED`, nhưng cho tác giả hotfix nội dung **tại chỗ**, lộ ngay sang mọi người cài.
- Thẻ gốc của bản cài render bằng `card.template` live (`app/services/study_artifact_service.py:90-150`).
- `study_applications` (Phase 6) là danh tính của việc "Template áp dụng vào NoteType" (`models/study_application.py`).

## Phạm vi file dự kiến

- Adapter mới: `app/services/share_engine/kinds/template.py` (thuộc tính: `name`, `front_html`, `back_html`, `shared_css`) và `kinds/application.py` (membership thêm/xóa/sắp xếp).
- Model/migration theo ADR Q3: snapshot phiên bản Template bất biến (ví dụ `template_versions`, khóa theo content hash) hoặc dựng lại từ change log.
- Sửa:
  - `flashcard_content_service.py` (create/update/reset/delete Template trên NoteType có release → ghi dirty thay vì sửa live hoặc `409`);
  - `study_artifact_service.py` + `study_composition_service.py` (thẻ gốc của install → Template tại `applied_release`; composition lọc application theo membership);
  - `study_session_service.py` (snapshot ghim version);
  - `browse_card_service.py` (preview thẻ clone);
  - `app/services/mcp/*` (render cho người cài);
  - Connect export nếu có đọc Template.
- Frontend:
  - `features/note-types/pages/NoteTypeDetailPage.tsx`: nhãn "bản làm việc chưa phát hành", nút tới trang phát hành;
  - `features/deck-collaboration` (renderer diff HTML/CSS đã sanitize);
  - `InstalledDeckUpdatePage.tsx`: hiển thị thay đổi Template.

## Công việc chi tiết

1. Adapter `template`:
   - identity = template id;
   - serialize chuẩn hóa (chuẩn hóa xuống dòng);
   - hash;
   - diff descriptor là text HTML/CSS, **luôn escape**;
   - `progress_impact = none`.
2. Adapter `application`:
   - membership theo release (`introduced_sequence`/`removed_sequence`);
   - `progress_impact = card_generation`. Thêm application sinh Card cho Note nguồn của tác giả qua content topology hiện có. Bản cài **chỉ thấy** application khi đã apply release chứa nó.
3. Chuyển các thao tác Template trên lineage đã phát hành sang dirty journal. Gỡ nhánh hotfix #138 và giữ một flag để quay lại trong thời gian chuyển tiếp.
4. **Ghim khi render:**
   - thẻ gốc của install render Template tại `applied_release`;
   - tác giả xem bản làm việc;
   - người không có install xem bản live của chính họ.
5. Composition discovery cho install: chỉ liệt kê application có membership tại `applied_release`. Composition id vẫn theo quy tắc hiện có.
6. **Phiên học:**
   - snapshot ghi version id/hash của Template;
   - khôi phục phiên đòi đúng version;
   - apply update trong lúc phiên đang mở không đổi phiên đó (P4-00).
7. **Rebase:**
   - thay đổi Template và application được áp khi người cài cập nhật;
   - chưa có overlay Template (TD-17) nên chưa có xung đột;
   - membership bị xóa thì ẩn composition nhưng giữ Card và tiến độ Note.
8. **Change request:** chưa mở đóng góp Template (#9 ưu tiên thấp; làm ở TD-17).
9. **UI tác giả:**
   - sửa Template không còn bị `409`;
   - banner "Thay đổi sẽ tới người cài khi bạn phát hành";
   - trang phát hành hiển thị diff Template;
   - cảnh báo khi xóa application đang có người học.
10. **UI người cài:** trang cập nhật hiển thị "Giao diện thẻ thay đổi" kèm xem trước trước/sau (render sandbox với dữ liệu mẫu).
11. Tài liệu: cập nhật Deck CR plan §"Còn giới hạn", P6 plan 6B `DONE`, README decoupling.

## Output đầu ra bắt buộc

- 2 adapter, migration + rehearsal MySQL, gỡ hotfix có flag, UI tác giả và người cài, cập nhật tài liệu.

## Acceptance criteria

- Tác giả sửa Template: người cài **không** thấy cho tới khi phát hành và họ apply update. Có test cho study, browse, MCP.
- Tác giả thêm Template: người cài chỉ thấy cách học mới sau khi apply. Tiến độ Note và Card ID không đổi. Learner NOTE được mở rộng sibling đúng.
- Phiên đang mở không đổi khi tác giả phát hành hoặc người cài apply.
- `study_applications.source_ord` và Connect không bị ảnh hưởng.
- Không còn `SHARED_SCHEMA_VERSIONING_REQUIRED` cho thao tác Template; lỗi này vẫn còn cho tên/schema NoteType (kind sau).

## Verification

```text
python scripts/run_tests.py --module study,flashcards,decks,deck_collaboration,marketplace,connect_mcp --backend-only
python scripts/run_tests.py --module flashcards,deck_collaboration,study --frontend-only
```

Probe MySQL: tác giả phát hành Template trong khi người cài đang có phiên mở, apply update, và learner NOTE + LEGACY cùng lúc. Luồng trình duyệt dùng hai tài khoản với profile Chrome riêng.

## Rollback

- Flag trả về hành vi cũ (`409` + hotfix).
- Dữ liệu version/dirty mới không bị xóa khi tắt flag.
- Migration mở rộng downgrade được.

## Không làm trong task này

Fork của người cài (TD-17), Slot/binding (TD-18), NoteType marketplace (TD-19), tên/schema NoteType, tags.
