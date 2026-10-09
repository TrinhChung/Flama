# Template feature execution plan: Codex backend, Gemini frontend

Updated 2026-10-08 after the backend handoff and frontend completion. The accepted decisions below remain verbatim. The historical v1 definitions/fork/rewrite design is not an implementation contract. Current acceptance evidence: [CT-R2](../../task/template-features/reviews/CT-R2_TEMPLATE_UI_COMPLETION_2026-10-08.md).

## 1. Current scope and ownership

CT-02/03/04/05/06/07/08 backend implementation and GT-10B/11/12/13/18/14 frontend work are complete locally. Codex reviewed the existing GT-12A entity work and completed the missing UI, integration, browser checks and user guide. [Tracker](../../task/template-features/README.md) is the task status source; [backend handoff](../../task/template-features/reviews/CT-04_CT-08_BACKEND_HANDOFF_2026-10-08.md) and CT-R2 record evidence and limits. UI changes are not yet committed/pushed.

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

## 3. Implemented foundation

- Template retains its ID and history; migrations 53, 54 and 55 add versions, independent ownership/attachments and distribution. `note_type_id` is nullable compatibility metadata, not ownership or membership authority. FieldDef IDs drive `StudyApplication.input_bindings`; active occurrences determine use/order/defaults.
- Library list/detail/create/PATCH/archive/duplicate/preview and application attach/PATCH/retire APIs exist. Usage counts group ACTIVE owned occurrences. An independently attached definition remains the same Template; there is no token rewrite or copied definition per apply. Required/unbound inputs are advisory; missing input renders empty. Wrong type or foreign field is rejected.
- Effective resolver selects user market copy or immutable release pin and projects the application binding for all covered study/render paths. One received template exists per user/source, across deck and NoteType installs. New installs/rebases retain personal copies; paid entitlement permits attaching the received template to other owned NoteTypes. Marketplace source lineage cannot be duplicated or republished.
- Shared `app/services/release_core` drives deck/template publication/update policies. Deck releases capture template/version/application pins. Template-only or binding-only edits advance deck working state and can publish a deck update without exposing HTML/CSS in deck change atoms. Subscriber template conflict resolution belongs to its subscription. Auto flags default off; idempotency and optimistic head fences remain enforced.
- Study preparation opts into `include_template_inputs=1`. Personal preset and session input overrides are strictly validated against effective schema, including clone-added/disabled/overridden fields. Artifacts freeze the original source fields and ID binding map; content patch, restore and quick edit preserve alias correctness. Scheduler and negotiated wire versions retain existing semantics.
- Archive hides the library definition and blocks new attachments/explicit standalone publication. Existing ACTIVE use remains valid, and archived content edits still save/version while standalone auto publication is skipped. Existing deck captures can include archived definitions.

## 4. Canonical contracts

| Contract | Source |
|---|---|
| Immutable version list/get/restore A2 | [ADR-T1](../../architecture/template-version-foundation-adr-2026-10-07.md) |
| Library, draft preview, schema and attachment | [library contract](../../architecture/template-library-attachments-contract-2026-10-07.md) |
| Author releases, user copies, update/conflict/reset | [GT-11 backend section](../../task/template-features/GT-11_INSTALL_TEMPLATE_EDITOR.md) |
| Preparation, preset, personal binding, session freeze | [study contract](../../architecture/template-study-bindings-contract-2026-10-07.md) |
| Focused v2 coverage | [GT-15](../../task/template-features/GT-15_CONTRACT_TESTS.md) |

A2 restore returns the compatibility template DTO; a standalone definition can have `note_type_id: null`. Refetch library detail after explicitly applying a restore response to recover full schema/usage. History origins include `market_copy` and `update` in addition to the earlier values; unknown origins require a label fallback. Do not infer a definitions table, per-install fork, sync-definition API or required-input hard failure from v1.

## 5. Frontend completion

GT-01..09, GT-10A and GT-15A already existed. GT-12A was reviewed against the actual API; GT-10B, GT-12B/C/D/E, GT-13A/B/C/D, GT-11A/B/C and GT-18A/B/C/D are now implemented and tested. `TemplateDetailPage` composes library editing, history, attachment and distribution. GT-14 documents the accepted screen names, including the new archive visibility control. Historical GT-16/17 inventory requests remain superseded, not unfinished features.

Keep existing DOM/classes unchanged. Use current branch U8 and verify the actual committed foundation plus later local fixes before transferring to a separate checkout. Other tasks may be changing the workspace; never stash/reset or overwrite their files. The phase prompts are historical implementation criteria; use the current tracker before assigning more work.

## 6. Validation and acceptance

```powershell
& .\.venv\Scripts\python.exe scripts/run_tests.py --module templates --backend-only
& .\.venv\Scripts\python.exe scripts/run_tests.py --module templates --frontend-only
& .\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_deck_auto_publish_and_auto_update.py tests/test_deck_install_rebase_flow.py tests/test_deck_release_api.py --backend-only
npm --prefix frontend run lint
npm --prefix frontend run build
git diff --check
```

MySQL rehearsal tools use disposable databases and clean them up. Never run data-changing probes against the real local database. `wsgi.py` boot verification must disable startup maintenance for a read-only local smoke. Current configured local schema was observed at migration 55; deploys still need migrations before code reads new columns. Keep expand schema when rolling the application back; downgrade guards deliberately reject unsafe history/standalone/distribution data.

Backend checks do not complete UI acceptance. After each implemented FE phase, verify loading/empty/error, stale requests, restore draft, ownership, source pin vs personal copy, mobile 375px and dark mode. Browser/DevTools uses a separate profile; existing frozen sessions must keep their original projection after source/template/preset edits.

## 7. Explicit exclusions

N5 (standalone template marketplace catalog) and N6 (one input receives a list of several fields) remain outside the accepted scope. No new scheduler policy, bulk legacy clone model or visual redesign is part of this work.
