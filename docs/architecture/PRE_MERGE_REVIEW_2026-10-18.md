# Pre-merge review — 2026-10-18

Mode: INVESTIGATE. Kết luận ban đầu: **chưa sẵn sàng merge**, do typecheck và backend test còn đỏ.

Cập nhật sau sửa theo yêu cầu người dùng: **cả 3 finding đã được xử lý**. Frontend typecheck/build và 24 test trong hai file backend từng thất bại đều pass. Giới hạn kiểm chứng MySQL/browser bên dưới vẫn áp dụng.

## Phạm vi

- Nhánh: `feat/typing-back-audio-usage`, HEAD `de23bea98fb963cee89b426a26f99c87ca8b95ca`.
- Mốc so sánh: `origin/master` sau fetch, `c1dfa6e88bcac074649fec9579a6314674a9f51b`.
- Master remote đã chứa PR #235. Phần mới gồm 3 commit và các thay đổi working tree hiện tại, kể cả `RouteErrorBoundary.tsx` chưa track.
- Đã kiểm tra các thay đổi runtime ở field identity/cutover, analytics outbox/forecast/deck counts, browse, clone/rebase/change request, Connect, deploy và frontend bị ảnh hưởng.
- Không sửa code ứng dụng, test, migration hoặc thực hiện merge/deploy trong lượt review này.

## Findings ban đầu (đã sửa)

### [P1] Import không dùng làm typecheck frontend thất bại

- **Observed**: `npm.cmd run typecheck` thất bại với `TS6133: 'React' is declared but its value is never read`.
- **Evidence**: [RouteErrorBoundary.tsx](../../frontend/src/shared/ui/RouteErrorBoundary.tsx), dòng 1; file được import từ `frontend/src/App.tsx` trong working tree.
- **Potential concern**: Component mới chưa qua TypeScript gate. Chỉ chạy Vitest không phát hiện lỗi này.
- **Impact**: CI frontend có bước typecheck; `npm run build` và Docker frontend build cũng chạy TypeScript nên bị chặn nếu đưa trạng thái này vào commit.
- **Unknowns**: File hiện chưa track; kết quả này áp dụng cho working tree được review.
- **Hướng xử lý**: Bỏ default import `React`, giữ named import `useState`.

### [P1] Test deck-count vẫn dùng raw Note write đã bị guard mới cấm

- **Observed**: `test_structured_and_text_bulk_mutations_bump_global_once` phát sinh `FieldIdentityError` khi chạy `UPDATE notes SET tags ...`.
- **Evidence**: [test_deck_count_projection.py](../../tests/test_deck_count_projection.py), dòng 295; [field_value_identity_hooks.py](../../app/services/field_value_identity_hooks.py), dòng 284–286.
- **Potential concern**: Contract mới chặn raw Note writes, nhưng regression test cũ vẫn kỳ vọng câu SQL đó thành công.
- **Impact**: Backend validation của analytics/study và CI vẫn đỏ. Đã tái hiện độc lập qua modular runner với đúng file test.
- **Unknowns**: Đây là mâu thuẫn test/contract đã xác nhận; không phải bằng chứng cần nới lỏng guard bảo vệ dữ liệu.
- **Hướng xử lý**: Cập nhật test để kiểm tra hành vi bị từ chối; dùng đường ghi được hỗ trợ hoặc bảng được phép khi kiểm tra invalidation của bulk mutation.

### [P1] Test schema vẫn kỳ vọng unique constraint đã được thay thế

- **Observed**: `test_sparse_change_and_rebase_uniqueness_guards_are_named` thất bại vì không tìm thấy `uq_clone_note_override_install_note_field_def`.
- **Evidence**: [test_deck_release_schema.py](../../tests/test_deck_release_schema.py), dòng 120–123; [deck_clone_note_field_override.py](../../models/deck_clone_note_field_override.py), dòng 56–62; migration `20261014_000067` chuyển uniqueness sang `field_identity_key`.
- **Potential concern**: Model và migration đã dùng `uq_clone_note_override_install_note_identity`, trong khi test vẫn giữ contract cũ.
- **Impact**: Backend/database CI đỏ dù model đã khai báo constraint mới.
- **Unknowns**: Chưa kiểm chứng schema MySQL production trong lượt review này.
- **Hướng xử lý**: Cập nhật assertion cho tên và bộ cột `(deck_install_id, source_note_id, field_identity_key)` của constraint mới.

## Kiểm chứng ban đầu

| Lệnh | Kết quả |
|---|---|
| `.\.venv\Scripts\python.exe scripts/run_tests.py --module database,analytics,browse,worksheets --backend-only` | 550 test: 548 pass, 1 failure, 1 error |
| `.\.venv\Scripts\python.exe scripts/run_tests.py --module deck_collaboration --backend-only` | 54 test: 53 pass, 1 skip |
| Modular runner với 8 file field identity/consumers/schema, MCP concurrency, deploy workflow và Connect protocol/origin/wire | 114 test pass |
| Modular runner với `tests/test_deck_count_projection.py --backend-only --failfast` | Tái hiện cùng lỗi raw Note write; không cộng lại vào tổng test |
| Vitest: dashboard, worksheets, CardFieldsForm, MediaFieldPreview, browse, StudyQuickEditDialog, ArrayFieldInput, arrayField | 193 test pass / 26 file |
| Vitest: StudyPage, StudyTemplatePreparation | 28 test pass / 2 file |
| `npm.cmd run typecheck` | Fail: TS6133 tại RouteErrorBoundary.tsx:1 |

Tổng không tính lượt tái hiện: **718 backend test (715 pass, 2 lỗi, 1 skip)** và **221 frontend test pass**.

## Dữ liệu và giới hạn kiểm chứng

| Trạng thái | Nơi lưu và đường xử lý đã review |
|---|---|
| Nội dung Note hiện hành | `notes.field_values_by_id` + codec/extras; named-value adapter và ORM hooks xử lý ghi, revision và schema fence |
| Bằng chứng trước cutover | `field_value_identity_archive`, identity definitions và cutover manifest; offline preparation rồi migration contraction |
| Clone delta | `deck_clone_note_field_overrides.field_identity_key`; stable identity scoped theo install/Note |
| Review history và projection | `review_events` là nguồn; outbox cùng transaction, worker cập nhật summary |
| Deck counts/forecast | Snapshot dẫn xuất, kiểm tra dependency revision trước khi đọc hoặc publish |

- Các backend test vừa chạy chủ yếu dùng SQLite; đã đọc và chạy test migration/deploy guard, chưa chạy lại MySQL contract probes hoặc diễn tập deploy trên VPS.
- Chưa chạy browser để xác nhận thao tác kéo thả trên thiết bị cảm ứng và layout thực tế; Vitest chỉ kiểm chứng hành vi trong môi trường test.
- Không chạy toàn bộ suite CI. Các kết quả pass trên không chứng minh toàn bộ nhánh không còn lỗi.
- Ba finding đã được sửa và các gate từng thất bại đã xanh theo kết quả xác minh sau sửa bên dưới.

## Xác minh sau sửa

- `RouteErrorBoundary.tsx`: bỏ default import `React` không sử dụng.
- `test_deck_count_projection.py`: dùng raw mutation trên `study_progress_subjects` để giữ kiểm tra structured/text invalidation chỉ tăng global revision một lần; thêm test xác nhận raw Note write bị chặn và rollback không để lại count invalidation.
- `test_deck_release_schema.py`: kiểm tra constraint `uq_clone_note_override_install_note_identity` cùng đúng bộ cột `(deck_install_id, source_note_id, field_identity_key)`.
- `.\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_deck_count_projection.py tests/test_deck_release_schema.py --backend-only`: **24 test pass**, không skip.
- `npm.cmd run build` trong `frontend/`: **pass** cả `tsc -b` và Vite production build.
- `git diff --check` cho hai file test đã sửa: **pass**.
- Không thực hiện commit, merge hoặc deploy trong lượt sửa.
