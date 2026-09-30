# TD-14 — Nghiên cứu và ADR: tổng quát hóa vòng đời chia sẻ cho Deck, NoteType, Template

> Mức: **P1** · Đợt: W5 · Trạng thái: `TODO` · Loại: nghiên cứu/ADR, **Runtime change: none**
>
> Phụ thuộc: không · Chặn: TD-15, TD-16, TD-17, TD-18, TD-19 · Lane: Kiến trúc (Backend + Database + Frontend review) · Ước lượng: 3–4 ngày
>
> Chỉ đạo chủ sản phẩm (2026-09-30):
> 1. Template và deck dùng chung cơ chế fork, phải tổng quát hóa để không phát triển lặp lại.
> 2. **Không coi cơ chế deck hiện tại là chuẩn mực.** Phần nào chưa tốt thì đề xuất nâng cấp.
>
> Skill: `$flama-database-architecture`, `$flama-backend-architecture`, `$mysql`.

## Mục tiêu

Thay ba cơ chế rời rạc bằng **một vòng đời chia sẻ chung**. Ba cơ chế hiện tại:
- deck: logical overlay + release + rebase + change request;
- NoteType: marketplace copy toàn bộ;
- Template: chưa có gì, chỉ có hotfix tại chỗ.

Vòng đời chung áp dụng cho mọi loại gói (deck, NoteType, Template) và mọi loại entity (field, giá trị Note, Template, application, binding, tags…). Đồng thời xác định **phần nào của bộ máy deck phải nâng cấp** trước khi đem đi dùng chung.

Kết quả là một ADR đủ chi tiết để TD-15..TD-19 triển khai mà không phải quyết định lại.

## 1. Vòng đời chung và hiện trạng từng loại gói

```text
Gói (listing) → Bản làm việc của tác giả (dirty journal) → Release bất biến (atomic change + membership)
      → Bản cài ghim release → Fork cục bộ (copy-on-write, overlay theo install)
      → Cập nhật/rebase (diff, xung đột 3 chiều, giải quyết) → Đóng góp ngược (change request → merge vào bản làm việc)
      → Rút/xóa mềm (soft delete, giữ cho người đã cài)
```

| Bước | Deck (hôm nay) | NoteType (hôm nay) | Template (hôm nay) | Quyết định đã chốt ([điều tra §14](../../architecture/template-notetype-decoupling-investigation.md)) |
|---|---|---|---|---|
| Gói / listing | ✅ `DeckMarketplaceItem` | ✅ NoteType là sản phẩm | ❌ chỉ bán kèm NoteType | #2: Template bán riêng được |
| Bản làm việc + dirty | ✅ `deck_working_dirty_entities` (kind: `note`, `note_field`, `field_def`, `field_order`) | ❌ | ❌ sửa thẳng bản live (hotfix #138) | — |
| Release bất biến | ✅ `deck_releases`, `deck_release_changes`, `deck_release_entity_memberships` | ❌ chỉ chuỗi `version` + changelog | ❌ | #10: bản cài ghim phiên bản |
| Bản cài ghim | ✅ `DeckInstall.applied_release_id` | ❌ copy toàn bộ, không lưu vết nguồn | ❌ render bản live của tác giả | #10 |
| Fork cục bộ | ✅ bảng overlay riêng cho từng kind (`deck_clone_*`) | ⚠️ copy ngay khi cài (fork sớm, không copy-on-write) | ❌ | #1, #11: fork khi sửa, theo install |
| Cập nhật / rebase | ✅ `deck_install_rebases` + conflicts | ❌ | ❌ | #10 |
| Đóng góp ngược | ✅ change request, 6 change type | ❌ | ❌ | #9: Template làm sau, ưu tiên thấp |
| Rút / xóa mềm | ⚠️ archive source | ⚠️ | ❌ | #21: soft delete |

## 2. Đánh giá phản biện bộ máy deck (không coi là chuẩn)

| ID | Điểm yếu | Bằng chứng | Hệ quả nếu nhân bản sang Template/NoteType | Đề xuất nâng cấp |
|---|---|---|---|---|
| SE-01 | Mọi bảng đều khóa theo vật chứa deck (`deck_item_id`, `deck_install_id`) | Model `deck_working_dirty_entity`, `deck_release*`, `deck_install_rebase*`, `deck_change_request*`, `deck_clone_*` | Làm cho NoteType/Template sẽ phải sao chép cả bộ bảng + service | Khái niệm trung lập **Share Package / Package Release / Package Install**; deck item, NoteType listing, Template listing chỉ là loại gói. So sánh 3 phương án ở §4 Q1 |
| SE-02 | Mỗi entity kind tốn một bảng overlay + một nhánh `if` trong rebase + một change type + một renderer diff + một projection browse | `_local_overlay_for_change` (`deck_install_rebase_service.py:564-604`); `CHANGE_REQUEST_CHANGE_TYPES` (`change_request/helpers.py:60-67`); `DiffWorkspace.tsx` | Chi phí tăng tuyến tính theo số kind; đây là nguồn gốc của "phát triển lặp lại" | **Registry adapter theo `entity_kind`** (TD-15): mỗi kind khai báo identity, serialize/hash, đọc tại release, overlay, xung đột, change type, merge, retire, bộ hiển thị diff. Cân nhắc overlay store tổng quát + projection typed cho đường nóng (§4 Q2) |
| SE-03 | Nhiều thay đổi chưa version được nên bị chặn `409` | [Deck CR plan §"Còn giới hạn"](../../plans/completed/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md): tags (`SHARED_NOTE_METADATA_VERSIONING_REQUIRED`), Template/card layout và schema NoteType (`SHARED_SCHEMA_VERSIONING_REQUIRED`), chuyển deck/xóa cứng (`SHARED_ENTITY_RETIRE_REQUIRED`) | Tác giả bị chặn các thao tác bình thường; người dùng nhận lỗi tiếng Anh | Thêm kind theo thứ tự giá trị: `template` + `application` (TD-16) → `note_tags` → `note_type_meta` → `note_placement`/retire. Mỗi kind chỉ là một adapter |
| SE-04 | Hotfix #138 cho tác giả sửa Template tại chỗ, phá bất biến "sửa của tác giả không lộ sang bản clone trước khi phát hành" (DoD #1) | `flashcard_content_service.py:1529-1545` | Nhân bản cách làm này sẽ phá đảm bảo release | Loại bỏ khi TD-16 xong; trong thời gian chờ thì cảnh báo (TD-07) |
| SE-05 | Còn định danh theo **tên/vị trí** | Rebase tra overlay theo tên field khi thiếu ID (`deck_install_rebase_service.py:556-578`); giá trị Note lưu theo tên field, đổi tên phải viết lại khóa JSON (`flashcard_content_service.py:1622-1662`); cutover ghép Template theo vị trí ([điều tra §5.2](../../architecture/template-notetype-decoupling-investigation.md)) | Template/Slot theo tên sẽ gãy khi đổi tên hoặc sắp xếp lại | Bộ máy chung **chỉ** khóa theo ID ổn định (`field_def_id`, application/template id, slot key). Tên chỉ là metadata. Đo số lần đường fallback theo tên còn được dùng rồi mới gỡ |
| SE-06 | Bản sao NoteType không lưu vết nguồn; `NoteTypeInstall` duy nhất theo (NoteType nguồn, user) nên nhiều deck cài cùng nguồn **dùng chung** một bản sao Template | [Điều tra §5.1](../../architecture/template-notetype-decoupling-investigation.md); `models/note_type_install.py`; `share/note_types.py:499-548` | Không fork theo install được (#11), không rebase NoteType được | Bảng **lineage** chung (entity cục bộ → entity nguồn + release nguồn); phạm vi fork = install |
| SE-07 | Hai vòng đời marketplace khác nhau (deck overlay và NoteType copy); UI còn gọi gói NoteType là "Template" | Điều tra §5.1 | Người dùng không đoán được "cài xong có nhận cập nhật không" | NoteType cài theo kiểu ghim + fork khi sửa (#10) trên cùng bộ máy (TD-19); thống nhất thuật ngữ |
| SE-08 | Phát hành chạy đồng bộ, không có worker/outbox; chưa có benchmark MySQL 10k–50k; performance gate #7, #10 và phần concurrency của #9 chưa đạt | [Deck CR plan §17–18](../../plans/completed/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md) | Thêm kind (Template HTML lớn) làm publish chậm hơn nữa | Đưa chứng nhận MySQL + publish bất đồng bộ vào TD-15 **trước** khi thêm kind |
| SE-09 | Change request thiếu merge từng phần, luồng bình luận, đóng góp tags/cây deck | Deck CR plan §15 "Deferred sau v1" | Đóng góp Template thiếu review thực chất | Merge từng phần + bình luận làm ở engine chung, mọi kind hưởng lợi |
| SE-10 | Không có thông báo (push/email); chỉ có con trỏ `seen_release_id` | Deck CR plan §15 #8 | Người cài không biết có bản mới | Outbox + thông báo dùng chung cho mọi gói |
| SE-11 | Không dọn entity đã retired | Deck CR plan §15 #9 | Dữ liệu phình theo thời gian | Job retention chung, cùng nguyên tắc với P7/P9 |
| SE-12 | UI diff render theo từng kind | `features/deck-collaboration/components/DiffWorkspace.tsx` | Mỗi kind mới phải sửa UI | Registry renderer phía frontend theo `entity_kind` (text, HTML/CSS đã sanitize, thứ tự) |

## 3. Kiến trúc đích đề xuất (ADR chốt)

1. **Share Package**: listing trung lập (`package_kind`: `deck` | `note_type` | `template`), chủ sở hữu, giá, trạng thái (soft delete).
2. **Working tree** của package: dirty journal theo `(entity_kind, entity_id, property_key)`, revision tăng dần.
3. **Package Release**: bất biến; atomic change + membership theo `entity_kind`; manifest hash; release trước.
4. **Package Install**: ghim `applied_release_id`; lineage entity cục bộ → nguồn; phạm vi fork = install.
5. **Local overlay**: copy-on-write theo install, qua adapter.
6. **Update/Rebase**: collapse change theo `change_key`; xung đột 3 chiều (base/upstream/local); giải quyết bằng giữ bản mình / lấy upstream / giá trị thủ công.
7. **Contribution**: overlay → change request item theo kind → merge vào working tree (có merge từng phần, bình luận).
8. **Entity Adapter** (contract, mỗi kind một cài đặt): `kind`, identity ổn định, `serialize/hash`, `read_at_release`, `project_for_install`, `overlay_read/write/prune`, `detect_conflict/resolve`, `contribution_change_types/validate/merge`, `retire`, `sanitize` (bắt buộc cho HTML/CSS), `diff_descriptor`, `progress_impact`.
   - Kind trình bày (`template`, `slot_binding`) không đụng tiến độ.
   - Kind sinh Card (`application`) phải đi qua content topology + NOTE authority hiện có.
9. **Kind ban đầu**: `note`, `note_field`, `field_def`, `field_order` (đã có) → `template`, `application` (TD-16) → `template_override` (TD-17) → `slot_binding` (TD-18) → `note_tags`, `note_type_meta`, `note_placement` (sau).
10. **Bất biến**:
    - overlay-only với Note/Card của deck;
    - phiên đang mở ghim version (P4-00);
    - Card ID và tiến độ Note không đổi khi apply update;
    - Template của người khác luôn qua sanitizer + CSP + proxy media;
    - mọi mutation idempotent, an toàn khi chạy đồng thời.

## 4. Câu hỏi ADR phải trả lời (kèm cách đo)

| # | Câu hỏi | Cách trả lời |
|---|---|---|
| Q1 | Tổng quát hóa vật chứa: **A** thêm `share_packages`/`share_installs` và cột `package_id` song song, giữ bảng `deck_*` làm tên cũ; **B** chuyển bảng hiện có sang `container_kind + container_id`; **C** giữ bảng riêng cho từng loại gói, chỉ dùng chung code | Đếm số dòng production (SELECT-only, cần phê duyệt), ước lượng DDL online trên MySQL 8, rủi ro với release đang chạy song song, độ phức tạp rollback. Khuyến nghị sơ bộ: **A** (mở rộng rồi thu hẹp, không đổi tên bảng nóng) |
| Q2 | Overlay store tổng quát hay giữ bảng typed | Benchmark MySQL cho đường browse `q`/sort trên giá trị hiệu lực của clone (đang chạy SQL trên projection) và cho study open; giữ typed cho đường nóng nếu tổng quát chậm hơn ngưỡng ở Deck CR plan §17 |
| Q3 | Lưu phiên bản Template: snapshot theo content hash hay dựng lại từ chuỗi change | Đo chi phí mở phiên (artifact Template cho mỗi thẻ); tận dụng `template_version` hiện có trong `study_artifact_service.py` |
| Q4 | Thêm/xóa application trong release: Card cho Note nguồn sinh lúc tác giả sửa, nhưng bản cài chỉ **thấy** khi release chứa membership | Kiểm tra composition discovery (`study_composition_service.py`) lọc theo membership tại `applied_release`; mở rộng sibling cho learner NOTE qua content topology |
| Q5 | Fork theo install hay theo user; quan hệ với bản sao NoteType của install cho Note tự thêm (#12) | Chốt install; đề xuất gộp hai nhóm Template (thẻ gốc và thẻ tự thêm) về một override theo install |
| Q6 | Đóng góp Template: diff theo dòng hay cả khối; sanitize; UI review | Nguyên mẫu trên `DiffWorkspace` |
| Q7 | Chuyển NoteType marketplace từ copy toàn bộ sang ghim + fork: xử lý các bản sao đã có | Coi bản sao cũ là "đã fork"; chỉ backfill lineage khi chứng minh được (không ghép theo vị trí mù) |
| Q8 | Tương tác với phiên học, NOTE authority, Connect `source_ord` | Phiên ghim version id; `study_applications.source_ord` giữ nguyên; kiểm tra MCP render |
| Q9 | Publish bất đồng bộ và giới hạn tải | Thiết kế job + outbox; ngân sách theo Deck CR plan §17 |
| Q10 | Bảo mật nội dung Template của người khác | Giữ `flashcard_renderer.py` sanitizer + CSP + `/media/proxy`; diff luôn được escape |

## Phạm vi file cần đọc/đo

- Backend: `app/services/deck_release_service.py`, `deck_working_tree_service.py`, `deck_install_rebase_service.py`, `app/services/change_request/*`, `app/services/share/*`, `flashcards_share_service.py` (clone schema view, overrides, cutover), `flashcard_content_service.py` (guard version-safe), `study_composition_service.py`, `study_artifact_service.py`, `marketplace_note_type_service.py`, repositories `deck_release_repository.py`, `deck_install_rebase_repository.py`, `deck_change_request_repository.py`, `logical_overlay_scope_repository.py`.
- Model: `deck_*`, `deck_clone_*`, `note_type_install.py`, `study_application.py`, `template.py`.
- Frontend: `features/deck-collaboration/*`, `features/note-types/*`, `features/marketplace/*`.
- Tài liệu: [Deck CR plan](../../plans/completed/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md), [CLONE_CUTOVER_REPORT](../../plans/completed/CLONE_CUTOVER_REPORT.md), [điều tra Template](../../architecture/template-notetype-decoupling-investigation.md), [đề xuất TPL-01](../../plans/proposals/DECOUPLE_TEMPLATE_NOTE_TYPE_PROPOSAL.md).

## Công việc chi tiết

1. Lập inventory từng bước vòng đời → hàm/đường code hiện có, kể cả mọi guard fail-closed trên Content API, Browse, MCP, Connect.
2. (Cần phê duyệt) Đo production SELECT-only: số deck item, release, install, overlay theo kind, NoteType install, Template/NoteType, dòng dirty, release có nhiều change nhất.
3. Spike **không merge**: cài contract adapter cho `note_field` và `field_def` để kiểm chứng interface; chạy suite decks/deck_collaboration trên spike.
4. Benchmark MySQL cho Q2 và Q3.
5. Viết ADR `docs/architecture/share-lifecycle-generalization-adr-<ngày>.md`: phương án, quyết định, lý do, rủi ro, kế hoạch migration mở rộng → chuyển đổi → thu hẹp, rollback.
6. Ghi disposition cho từng SE-01..SE-12: nhận / hoãn / bác, kèm lý do và khoản TD phụ trách.
7. Ánh xạ từng quyết định §14 #1–#21 sang năng lực của package/adapter.
8. Cập nhật phạm vi chính xác của TD-15..TD-19 (migration, flag, gate).
9. Review chung: kiến trúc + database + backend + frontend.

## Output đầu ra bắt buộc

- ADR đã review; contract adapter (tên hàm, kiểu dữ liệu, lỗi).
- Bảng disposition SE-01..SE-12; bảng ánh xạ quyết định #1–#21.
- Số liệu đo (production nếu được phép, và benchmark local MySQL).
- TD-15..TD-19 cập nhật phạm vi.

## Acceptance criteria

- Không phương án nào vi phạm overlay-only, NOTE authority hoặc đảm bảo phiên bản đã ghim.
- Migration đề xuất chạy online, lùi lại được cho tới bước thu hẹp.
- Mọi điểm yếu SE có quyết định rõ; không còn "làm như deck" khi chưa đánh giá.
- Chi phí thêm một entity kind mới sau TD-15 chỉ gồm một adapter + test + renderer diff; không thêm bảng hay nhánh `if` rải rác.

## Verification

Review tài liệu; spike chạy `python scripts/run_tests.py --module decks,deck_collaboration,marketplace --backend-only` (không merge); benchmark MySQL ghi lại lệnh và kết quả.

## Rollback

Không áp dụng (tài liệu và spike).

## Không làm trong task này

Không đổi schema, code production hay hành vi deck hiện tại; không bật Template Marketplace; không đổi dữ liệu.
