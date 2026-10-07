# Kế hoạch triển khai tính năng Template sau decoupling (v2): Claude điều phối, Gemini triển khai phần đơn giản

- Lập: **2026-10-05** (v1). Viết lại: **2026-10-06** (v2) theo câu trả lời của người dùng cho Q1–Q5. Bản v1 nằm trong lịch sử git (commit `0d4c293`).
- Trạng thái 2026-10-07: Codex tiếp nhận phần Claude; đã sửa blocker GT-01/06 và triển khai nền phiên bản CT-02/03. GT-10A và GT-15A Ready; GT-10B tiếp nối sau review GT-10A. Template độc lập/attachment/market copy/release core còn các bước sau, không coi M3–M6 hoàn tất.
- Người điều phối/review hiện tại: **Codex (tiếp nhận Claude)**. Người triển khai phần đơn giản: **Gemini** (`agy`, theo [worker orchestration](../../../skills/antigravity-cli/references/worker-orchestration.md)).
- Spec và tracker: [`docs/task/template-features/`](../../task/template-features/README.md).
- Căn cứ: [study-interaction-trigger-algorithm-plan](../../architecture/study-interaction-trigger-algorithm-plan.md) (§5, §9, §16), [P3-07 applied composition contract](../../architecture/applied-composition-binding-contract-2026-09-09.md), [P6 plan](../../task/decoupling/P6_EXECUTION_PLAN_2026-09-29.md) (D6-05, D6-08, D6-09), issue [TrinhChung/Flama#137](https://github.com/TrinhChung/Flama/issues/137) và #138.

## 1. Mục tiêu

| # | Tính năng | Kết quả mong muốn |
|---|---|---|
| F1 | **Template độc lập, dùng chung** | Template là thực thể riêng trong thư viện "Mẫu thẻ". Một loại thẻ (NoteType) gắn nhiều template; khi gắn, người dùng ánh xạ field của loại thẻ vào input của template. Sửa template ảnh hưởng mọi loại thẻ đang gắn nó. |
| F2 | **Một deck nhiều template, thấy rõ và chọn khi học** | Dashboard thấy các kiểu thẻ của deck (đã có ở M1). Bấm Học → màn chuẩn bị phiên: chọn template, tinh chỉnh field nào vào input nào; lựa chọn được nhớ. Input không được ánh xạ hiển thị rỗng, không làm lỗi thẻ. |
| F3 | **Phiên bản và kế thừa template** | Mỗi lần lưu là một phiên bản (lịch sử, so sánh, khôi phục). Tác giả bật/tắt tự động đăng bản mới, khi tắt thì bấm "Đăng bản mới nhất". Người nhận template (qua deck mua/cài) bật/tắt tự động kế thừa, mặc định tắt; sửa thì thành bản riêng; cập nhật có xử lý xung đột. Template từ marketplace dùng được cho mọi deck của người nhận nhưng không được đăng lại. |
| F4 | **Lõi phát hành và kế thừa dùng chung** | Tách logic release/subscribe/rebase/auto-publish/auto-update của deck thành lõi chung có adapter theo loại nội dung; deck chạy trên lõi đó, template là loại thứ hai. Dọn code release trùng lặp. Làm #137 trong đợt này. |

Ngoài phạm vi (chờ người dùng chốt ở §11): marketplace bán/chia sẻ template riêng lẻ (N5), input nhận danh sách nhiều field (N6).

## 2. Quyết định của người dùng (2026-10-06)

| ID | Quyết định | Hệ quả thiết kế |
|---|---|---|
| U1 | Template độc lập; NoteType gắn nhiều template; gắn = ánh xạ field → input, lưu theo ID nên đổi tên field/template không làm sai. Đổi cấu trúc template thì mọi NoteType đang gắn cùng chịu ảnh hưởng; người dùng tự kiểm soát. | Template không còn thuộc một NoteType. Bảng `study_applications` trở thành "attachment" có `input_bindings`. Flama chỉ cảnh báo (số NoteType đang gắn, input chưa ánh xạ), không chặn. |
| U2 | Bản riêng của template lấy từ marketplace thuộc về **người dùng**, dùng chung cho mọi NoteType/deck của họ. | Một "bản nhận" (market copy) cho mỗi (người dùng, template nguồn). Không có fork theo từng deck cài. |
| U3 | Màn phụ trước phiên học: chọn template cho phiên và chọn field đưa vào input; nhớ để khỏi thiết lập lại. Template không lỗi khi chỉ dùng vài field. | Bảng cấu hình học (study preset) theo người dùng + deck; ghi đè ánh xạ ở mức cá nhân; ánh xạ được freeze trong phiên. Input không ánh xạ = rỗng. |
| U4 | Phiên bản template: tác giả bật/tắt tự động đăng lại; tắt thì có nút đăng bản mới nhất (như deck). Người dùng có thể tự động kế thừa, mặc định tắt. | Mô phỏng đúng cơ chế deck hiện có: `DeckMarketplaceItem.auto_publish_enabled` (mặc định tắt, `deck_auto_publish_service.trigger_auto_publish_for_deck_item`) và `DeckInstall.auto_update_enabled` (mặc định tắt, `deck_install_rebase_service.process_subscriber_auto_updates`). |
| U5 | Mua deck trả phí thì được dùng template đó cho các bộ khác; không được đăng lại template clone từ marketplace. | Bản nhận gắn được vào NoteType của người nhận; mọi đường publish chặn template có nguồn marketplace (xem N4). |
| U6 | Đổi tên field không cần sửa template: template ánh xạ input ↔ field. Tác giả ánh xạ sẵn, người dùng tùy biến. | Render theo binding tại thời điểm render (không đổi token trong HTML). Template cũ dùng tên field làm input, binding đồng nhất theo `FieldDef.id`, nên cũng hết hỏng khi đổi tên field. |
| U7 | Làm #137 ngay; tham khảo deck để refactor logic kế thừa thành phần chung, dọn code cũ; code mới viết để mở rộng cho nhiều loại. | Thêm F4 (M5) trước khi làm phát hành template (M6). |
| U8 | Tiếp tục trên nhánh `refactor/frontend-fsd-renderer-boundary`. | Nhánh đã merge `master` (#211, #213) ở commit `1689a0f`. Mỗi task Gemini vẫn dùng worktree riêng. |

## 3. Hiện trạng đã đối chiếu với code (2026-10-06)

| Chủ đề | Bằng chứng | Ghi chú |
|---|---|---|
| Template gắn cứng NoteType | `models/template.py:11` (`note_type_id` NOT NULL, CASCADE); composition dựng `note_type_id` từ `template.note_type_id` (`app/services/study_composition_service.py:119-167`). | Phải chuyển mọi chỗ đọc sang NoteType của attachment/note trước khi cho `note_type_id` nullable. |
| Attachment sẵn có | `models/study_application.py`: unique `(template_id, occurrence_key)`; `cards.application_id`, unique `(note_id, application_id)`; seam `before_flush` tạo occurrence `compat`. | Đổi unique thành `(note_type_id, template_id, occurrence_key)`; thêm binding và trạng thái `RETIRED` (P6 D6-05). |
| Render | Context theo tên field (`flashcard_renderer.build_render_context`); artifact template giữ `id = template_id` và client restore bắt buộc `template.id === card.template_id`, binding kind `legacy-fielddef-direct`, input `legacy-field:{field_def_id}` (`frontend/src/features/study/session/sessionRestore.ts:599-690`). | Binding mới cần binding kind mới, client renderer/restore hiểu được, có thương lượng phiên bản như wire v4. |
| Thẻ của deck đã cài | `build_effective_study_card` dùng `card.template` của tác giả (`app/services/study_artifact_service.py:118,147`); bản sao NoteType khi cài chép Template không lineage (`app/services/share/note_types.py:499-547`). | Thay bằng bản nhận theo người dùng (U2) qua một resolver. |
| Release deck | `deck_release_service.py` (2.158 dòng, 58 hàm), `deck_install_rebase_service.py` (1.195 dòng), `deck_working_tree_service.py`, `deck_auto_publish_service.py`; entity kind release chỉ `note_field`, `field_def` (`app/services/release/base.py:39`). | Package `app/services/release/` là **bản sao cũ** của `deck_release_service.py`: 55/58 hàm/lớp giống hệt theo AST, 3 hàm (`publish_release`, `preview_release`, `serialize_release`) thiếu `publish_mode` mà bản đang chạy đã có; không được import ở đâu (chỉ có trong pattern của `scripts/run_tests.py`). Là code chết cần xóa ở M5. |
| Guard template đã chia sẻ | `_ensure_version_safe_template_mutation` + hotfix #138 (`app/services/flashcard_content_service.py:1509-1551`). | Thay bằng phiên bản template + attachment trong release deck (M6). |
| Migration | Head hiện tại `20261006_000052_add_deck_count_snapshots.py`. | Migration của đợt này bắt đầu từ `000053`. |
| Môi trường test | Code yêu cầu Python 3.12 (`MappingProxyType` làm default dataclass ở `app/repositories/study_authority_repository.py:214`); Dockerfile dùng `python:3.11-slim`. | Ngoài phạm vi kế hoạch; đã báo người dùng. Test của đợt này chạy bằng 3.12. |

M1 đã giao (đã review, xem §7): `note_count` theo template, `include_counts` cho compositions, entity `entities/card-template`, `TemplateCodeEditor`, quản lý template trên trang loại thẻ, dialog "Kiểu thẻ", `template_tokens.py`, `lineDiff`/`TemplateDiffView`.

## 4. Kiến trúc v2

```text
                         ┌──────────── template_versions (bất biến) ◄──── release core (M5): publish / subscribe / rebase
                         │
users ──< templates (độc lập: owner, input_schema, current_version, origin, source lineage)
               │  ▲
               │  └── market copy của người nhận (origin=market_copy, source_template_id, pin + auto_update)
               │
NoteType ──< study_applications = ATTACHMENT (note_type_id, template_id, occurrence, input_bindings, position, is_default, status)
               │
             cards (note_id, template_id, application_id) ──> notes ──> learner/Note progress (không đổi)

study_presets (user, deck): attachment đã chọn + ghi đè input_bindings + có hỏi lại hay không
```

### 4.1 Thực thể (logic; tên bảng/cột chốt trong ADR-T)

1. **Template độc lập** — giữ bảng `templates` để **giữ nguyên mọi `template_id`** (Card, composition id, phiên học, Anki). Thêm: `owner_user_id`, `input_schema` (JSON: `key`, `label`, `type`, `required` mang nghĩa "khuyến nghị"), `current_version_id`, `origin` (`authored` | `market_copy`), `source_template_id` + `source_version_id` (chỉ cho market copy), `auto_publish_enabled` (tác giả), `auto_update_enabled` (người nhận), `archived_at`. `note_type_id` thành nullable (chỉ còn là "loại thẻ gốc" để tương thích) sau khi mọi chỗ đọc đã chuyển.
2. **Phiên bản template** — bảng mới, chỉ insert: `version_no`, `front_html`, `back_html`, `shared_css`, `input_schema`, `content_hash` (`template_tokens.template_content_hash`), `origin`, `change_note`, `created_by`. Phiên bản được đăng là một release của lõi M5.
3. **Attachment** — `study_applications` thêm `input_bindings` (`input_key → field_def_id | null`), `display_name`, `position`, `is_default`, `status` (`ACTIVE` | `RETIRED`). Gắn = tạo attachment + Card cho mọi note của NoteType qua NOTE expansion (như `create_template`). Gỡ = `RETIRED`: ngừng discovery, Card ẩn, progress giữ (P6 D6-05).
4. **Cấu hình học (study preset)** — theo (người dùng, deck): composition đã chọn, ghi đè `input_bindings`, cờ hỏi lại. Phạm vi và hành vi chờ N1/N2.
5. **Market copy** — mỗi (người nhận, template nguồn) một template `origin = market_copy`, tạo khi cài deck/loại thẻ có template đó; pin vào phiên bản đã đăng; sửa thì thành bản riêng (vẫn là market copy, không đăng được); cập nhật theo lõi M5.

### 4.2 Render theo binding

- Binding hiệu lực = ghi đè của study preset → binding của attachment → mặc định đồng nhất (input trùng tên field hiện tại) cho template cũ.
- Context render = context theo tên field như hiện nay **cộng** khóa theo input: `context[input_key]` = giá trị đã xử lý của field được bind (kể cả `_url`, `_urls` cho media); input không bind → `""`/`[]`. Template cũ không đổi một ký tự.
- Server (`flashcard_renderer`, `study_artifact_service`) và client (`entities/flashcard/lib/clientRenderer.ts`, patch nội dung phiên, `sessionRestore.ts`) cùng áp dụng. Phiên học freeze binding với binding kind mới; phiên v2/v3/v4 cũ vẫn đọc được. Server chỉ cấp binding kind mới khi client khai báo hỗ trợ.
- Artifact template của bản nhận/bản riêng vẫn mang `id` = `template_id` nguồn của Card; nội dung khác thì `version` khác.

### 4.3 Phân phối và kế thừa template

- Tác giả: mỗi lần lưu là một phiên bản. Bật "tự động đăng" → đăng ngay sau khi lưu (như `trigger_auto_publish_for_deck_item`); tắt → nút "Đăng bản mới nhất".
- Người nhận: market copy pin ở phiên bản đã đăng lúc cài. Có bản mới → báo "Có bản mới". Bật "tự động kế thừa" (mặc định tắt) → tự cập nhật nếu chưa sửa; đã sửa → xung đột, chọn "Giữ bản của tôi" / "Lấy bản của tác giả" (như `process_subscriber_auto_updates` khi có conflict).
- Thẻ gốc của deck đã cài render bằng market copy của người học; chưa có market copy (dữ liệu cũ) thì render template nguồn như hiện nay cho tới khi CT-14 chuyển đổi xong.
- Không đăng lại: chặn publish template `origin = market_copy`; quy tắc cho deck/loại thẻ có gắn market copy chờ N4.

### 4.4 Lõi phát hành và kế thừa (F4)

Khái niệm chung rút từ deck: **Publisher** (working revision, đánh dấu thay đổi, publish thủ công/tự động, nhãn phiên bản), **Release** (snapshot/changeset bất biến, sequence), **Subscription** (pin release, seen/applied, auto-update, sync mode, detach), **Rebase** (đơn vị thay đổi, phát hiện xung đột, `keep_mine`/`keep_upstream`/`manual`), **Auto-update job**. Mỗi loại nội dung có adapter: deck (journal `note_field`/`field_def` hiện có + attachment template ở M6), template (snapshot nguyên khối: front/back/css/input_schema là các đơn vị xung đột). Cách làm an toàn: (1) test đặc tả hành vi deck hiện tại, (2) xóa code chết, (3) đưa API lõi + adapter deck **giữ nguyên bảng và hành vi**, (4) template dùng lõi. Gộp bảng vật lý (nếu cần) để sau, có ADR riêng.

## 5. Hợp đồng API

Đã giao ở M1 (giữ nguyên): Contract B (`include_counts` → `note_counts`), Contract C (`note_count` trong `GET /api/note-types/<nt>/templates`, nay chỉ đếm note của chính loại thẻ đó).

Contract **A2 đã đóng băng và chạy thật** trong [ADR-T1](../../architecture/template-version-foundation-adr-2026-10-07.md), schema `template-versions.v2`. E2/F vẫn là phác thảo; chỉ mở UI sau backend và spec v2. Gemini không suy diễn field ngoài contract.

| Contract | Endpoint (phác thảo) | Dùng cho |
|---|---|---|
| A2 — phiên bản | `GET /api/card-templates/<id>/versions`, `GET .../versions/<vid>`, `POST .../versions/<vid>/restore` | GT-10 |
| E2 — thư viện | `GET /api/card-templates?q=&group=all\|mine\|market\|standalone\|in_use`, `POST`, `GET/PATCH /<id>`, `PUT /<id>/content`, `POST /<id>/preview`, `POST /<id>/archive` | GT-12 |
| F — attachment | `GET/POST /api/note-types/<nt>/attachments`, `PATCH/DELETE /api/note-types/<nt>/attachments/<application_id>` | GT-13, GT-18 |

## 6. Nguyên tắc chia việc

Gemini nhận task khi **toàn bộ** điều kiện sau đúng:

1. Có hợp đồng/đầu ra cụ thể (chữ ký hàm, JSON, props, chuỗi UI) ghi sẵn trong spec.
2. Danh sách file được sửa ≤ 6 file, không chạm schema/migration, transaction, lock, study runtime, overlay resolver, release engine hoặc sanitizer.
3. Kiểm chứng được bằng test tự động mà spec mô tả từng assertion.
4. Sai sót không gây mất dữ liệu: có thể sửa bằng một lần review.

Claude giữ: ADR và hợp đồng, schema/migration/backfill (MySQL), service có transaction/fence, resolver hiệu lực cho mọi đường render, fork/pin, session freeze, thay đổi ở `useStudySession`, review toàn bộ diff và integration gate. Claude cũng chạy review đối kháng cho phần pure function của Gemini vì lỗi ở đó âm thầm làm hỏng template.

## 7. Task v2 và trạng thái tiếp nhận (2026-10-07)

Codex giữ phần Claude: schema, transaction, resolver, attachment, runtime freeze và release engine. Gemini làm phần frontend/test trong whitelist. Quyết định U1–U8 ở §2 được giữ nguyên; không triển khai bảng definitions hoặc fork theo install của v1.

| ID | Owner hiện tại | Nội dung v2 | Trạng thái / phụ thuộc |
|---|---|---|---|
| CT-00 | Codex | Đối chiếu U1–U8, baseline phần đã có, giữ nhánh U8. | Completed cho nền phiên bản; gate toàn hệ thống làm theo từng milestone |
| CT-01 | Codex | ADR-T1 giữ ID, schema expand và Contract A2; ADR attachment/market-copy/release bổ sung ở bước tương ứng. | A2 frozen; D/E/F chưa frozen |
| GT-01..09 | Gemini, Codex review | M1 management/counts/editor + pure tokens/diff. | Đã có code/test; Codex sửa GT-01 reserved field và GT-06 draft. Browser gate tổng vẫn chưa thực hiện |
| CT-02 | Codex | `templates` thêm owner/schema/head; `template_versions`; migration **20261007_000053**, backfill exact bytes/idempotent, MySQL rehearsal. | Completed cho expand; `note_type_id` vẫn NOT NULL |
| CT-03 | Codex | Repository + transactional ORM history, owner list/get/restore A2, main/Connect registration, backfill CLI và route snapshot. | Completed; mở GT-10A/GT-15A |
| GT-10A | Gemini | Entity API/types/keys cho A2 (5 file). | **Ready** |
| GT-10B | Gemini | History sheet + page, áp response restore vào draft (6 file). | Sau review GT-10A |
| GT-15A | Gemini | Test A2 bổ sung, không lặp test Codex. | **Ready**, độc lập GT-10A |
| CT-R2 | Codex | Review GT-10/GT-15A + browser smoke và freeze gate M2. | Sau hai task Gemini |
| CT-04 | Codex | Resolver hiệu lực tương thích ở mọi render path, trước khi đổi ownership/attachment. | Planned; giữ parity owned/installed/local-added, chưa đổi nguồn |
| CT-06 | Codex | Attachment theo NoteType + Template, input_bindings bằng FieldDef ID; discovery/card retirement/binding render/freeze tương thích; sau đó library E2/F và template độc lập. | Planned sau CT-04; nhiều bước expand/backfill/cutover, contract riêng |
| CT-07 | Codex | Release core + adapter deck parity + adapter template, pin version #137 và auto publish/update theo U4/U7. | Planned trong đợt này; không cần hỏi lại Q4 |
| CT-05 | Codex | Market copy **cấp user/source** (U2), quyền dùng qua nhiều deck và publish restriction; resolver đọc bản nhận/pin release. | Sau CT-06 + nền release CT-07; không có deck_install_template_forks |
| GT-15D/E | Gemini | Test market copy/library/binding theo contract mới. | Blocked; bảng v1 chưa được dùng |
| GT-11 | Gemini | Editor bản nhận; entry từ deck nhưng identity là template của user. | Blocked CT-05, spec v2 cần viết lại |
| GT-12/13 | Gemini | Library và attachment wizard theo E2/F. | Blocked CT-06, spec v1 apply/rewrite chưa được dùng |
| CT-08 | Codex | Preset/chọn template trước phiên và freeze lựa chọn/binding; không đổi scheduler. | Sau attachment và contract preset |
| GT-14 | Gemini | Hướng dẫn theo tính năng đã nghiệm thu. | Sau milestone tương ứng |
| GT-16/17 | Gemini | Inventory template/release. | Candidate reports đang có, chưa đánh dấu Accepted |

### CT-02/03 thực tế

- Models: `models/template.py`, `models/template_version.py`. Đăng ký ở main factory và Connect `_register_models`, không giả định `models/__init__.py` import tất cả model.
- Version persistence: `app/repositories/template_version_repository.py`; orchestration/hooks/CLI: `app/services/template_version_service.py`.
- `before_flush` thu mọi writer ORM, `before_commit` chụp nguồn cuối một lần/template/outer transaction. Raw/bulk SQL phải backfill rõ ràng. Parent lock + current-read head cấp sequence an toàn ở MySQL RR; rollback/savepoint không giữ metadata đã hủy.
- A2 canonical nằm ở `app/api/v1/flashcards/card_templates.py`; thêm alias NoteType và 6 route trong snapshot. Serializer thêm `current_version_id`, không thêm definition_id.
- Rename/no-op không append; restore explicit luôn append, compile validation + ownership/released-schema guard + audit trong cùng transaction. Card ID/progress và runtime artifacts giữ nguyên.
- Migration 52→53 giữ nguyên timestamp/source; runtime schema cũ là `input_schema=[]`, chưa tạo binding. Upgrade phải chạy trước process đọc model mới. Downgrade từ chối authored/history nhiều bản; rollback app giữ schema expand.
- Chi tiết và bằng chứng: [báo cáo CT-02/03](../../task/template-features/reviews/CT-02_CT-03_CODEX_IMPLEMENTATION_2026-10-07.md).

### Thứ tự hiện tại

```text
Codex CT-02/03 đã có code/test → Gemini GT-10A và GT-15A (file độc lập)
Codex review GT-10A → Gemini GT-10B → Codex gate M2
Codex CT-04, CT-06, CT-07 theo từng seam → contract mới → GT-12/13/15E
Codex CT-05 cấp user → contract mới → GT-11/15D
```

Không để hai worker sửa cùng file. Làm trên nhánh U8; checkout/worktree sạch từ HEAD hiện tại chưa chứa nền CT-02/03 đang uncommitted. Phải đưa **đúng diff nền đã review** sang worktree trước khi giao UI/test, hoặc chạy worker tuần tự trên workspace với whitelist. Không commit/push/stash/reset các thay đổi ngoài task.

## 8. Quy trình giao và review một task Gemini

1. **Claude chuẩn bị:** xác nhận phụ thuộc đã `Accepted`, đối chiếu lại số dòng/đoạn code mà spec trích (code có thể đã đổi), cập nhật spec nếu lệch. Ghi `git status` và HEAD vào README task.
2. **Giao:** dán phần "Prompt cho Gemini" trong file spec (đã có phần quy tắc chung). Gemini chạy trong worktree riêng, chế độ `accept-edits`, không commit.
3. **Gemini báo cáo** theo mẫu trong spec: file đã sửa, lệnh đã chạy kèm output thật, điểm chưa chắc chắn.
4. **Claude review** theo checklist:
   - `git diff --stat` chỉ chứa file trong whitelist; không có file ngoài phạm vi, không đổi format hàng loạt.
   - So từng dòng với hợp đồng: tên hàm, kiểu, JSON key, mã lỗi, chuỗi tiếng Việt.
   - Test có assertion về giá trị (không chỉ kiểm tra tồn tại); có case âm; không `skip`/`expectedFailure` mới; không sửa test cũ để cho qua.
   - Tự chạy lại lệnh kiểm tra của spec, cộng `git diff --check`, lint/typecheck cho frontend và route snapshot cho backend.
   - Đọc đối kháng: input rỗng, None, Unicode/tiếng Nhật, field tên có dấu chấm, deck overlay, quyền người khác, StrictMode/unmount, query invalidation.
   - UI: class/DOM của phần cũ giữ nguyên; trạng thái loading/empty/error; mobile 375px; dark mode.
5. **Kết quả:** `Accepted` (Claude có thể sửa nhỏ và ghi lại) hoặc `Needs revision` với danh sách lỗi cụ thể gửi lại Gemini trong cùng conversation. Sau hai lần `Needs revision` cho cùng lỗi, Claude tự sửa.

## 9. Tiêu chí nghiệm thu chung và lệnh kiểm tra

Lệnh (PowerShell, từ repo root, môi trường local đã xác minh trong kế hoạch FSD):

```powershell
& .\.venv\Scripts\python.exe scripts/run_tests.py --module flashcards --backend-only
& .\.venv\Scripts\python.exe scripts/run_tests.py --module study --backend-only
& .\.venv\Scripts\python.exe scripts/run_tests.py --module marketplace,decks,deck_collaboration --backend-only
& .\.venv\Scripts\python.exe -m unittest tests.test_api_v1_route_map
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- <đường dẫn test của task>
npm --prefix frontend run build:ci
git diff --check
```

| Milestone | Bằng chứng bắt buộc |
|---|---|
| M1 | Response compositions không có `include_counts` giống hệt trước (so JSON). Dashboard/NoteType chạy trên desktop + mobile; deck owned và deck đã cài. |
| M2 | Migration 50→51→50→51 trên MySQL 8 local; backfill chạy hai lần không tạo thêm dòng; lưu template tạo đúng một version; khôi phục không xóa version; Card ID/progress không đổi. |
| M3 | Fork không đổi bất kỳ hàng nào của tác giả (đếm/so hash `templates`, `notes`, `cards`); người cài khác không bị ảnh hưởng; phiên đang mở giữ artifact cũ; phiên mới dùng fork; xóa fork quay về bản gốc; browse/MCP/preview hiển thị cùng nội dung hiệu lực. |
| M4 | Apply với binding thiếu/stale/khác NoteType/sai kiểu bị từ chối đúng mã; đổi tên field cập nhật template có binding; template không binding giữ hành vi cũ. |

Browser/DevTools chỉ dùng profile riêng (ví dụ `C:\Users\chung\.gemini\chrome-profiles\flama-template-features`), không dùng profile cá nhân. Thiếu bằng chứng nào thì ghi "chưa kiểm tra", không ghi PASS.

## 10. Rủi ro và cách kiểm soát

| Rủi ro | Kiểm soát |
|---|---|
| Gemini bịa hàm/field không tồn tại | Spec trích nguyên đoạn code liên quan; quy tắc "thiếu symbol thì dừng và báo cáo"; review so contract từng dòng. |
| Đổi token Mustache sai làm hỏng template | GT-08 có bảng test bắt buộc; CT-R2 thêm fuzz/so sánh trước–sau trên toàn bộ template backfill (round-trip phải giữ nguyên byte khi mapping là identity). |
| Market copy rò rỉ sang tác giả hoặc người nhận khác | Resolver theo user/source; test nguồn và quyền scope trước/sau; review của Codex. |
| Đổi `AppliedComposition` làm vỡ session freeze | Contract B thêm key cấp cao nhất, không sửa dataclass; review chặn mọi diff ở `AppliedComposition`. |
| Code mới boot trước migration (cột mới trên `templates`) | CT-02 ghi rõ thứ tự deploy; kiểm tra boot thật qua `wsgi.py` theo AGENTS.md. |
| Xung đột với migration FSD đang chạy (G03 dashboard, G09 note-types) | Không chạy GT-05/06/07/10 khi G03/G09 đang `In progress`; code mới đặt trong slice mới (`entities/card-template`) và component mới, chỉ sửa tối thiểu file cũ. |
| Hiệu năng: đếm note theo composition | Một truy vấn group-by cho mọi composition; chỉ chạy khi `include_counts=1`; không chạy trong luồng mở phiên học. |
| Backfill tạo nhiều version rác | Lưu chỉ append khi nguồn hoặc input_schema thay đổi; restore explicit luôn append (CT-03). |

## 11. Việc tiếp theo đã được cho phép

1. Gemini có thể bắt đầu GT-10A và GT-15A theo prompt trong tracker; không hỏi lại Q1–Q5, đã có U1–U8.
2. Codex review entity diff rồi mở GT-10B, giữ bản sửa draft và kiểm tra restore cùng nguồn.
3. Tiếp tục CT-04/06/07/05 theo thứ tự ở §7; API/library/release chỉ mở khi contract thực đã có. Preset scope/ghi nhớ và quyền phân phối cần được làm rõ trong ADR của bước đó, không chặn A2.
4. N5 (marketplace template riêng lẻ) và N6 (input nhận danh sách nhiều field) vẫn ngoài phạm vi đã chốt. Không suy diễn mở rộng vào nền phiên bản.
