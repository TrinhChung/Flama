# Review và sửa phần flashcard extraction của Gemini

Ngày: 2026-10-05. Baseline: HEAD `745c357` và các thay đổi chưa commit của Gemini trong working tree. Phạm vi là renderer, media preview, content patch và các caller Browse/Audio/NoteType/Marketplace; chưa phải toàn bộ migration FSD.

## Các lỗi đã sửa

| Mức | Phát hiện trong implementation Gemini | Sửa của Codex |
|---|---|---|
| P1 | Browse/Audio chỉ phát event. Listener persistence nằm trong module Study được tải theo route, nên mở Browse/Audio trước Study có thể không cập nhật session đã lưu. Browse cũng mất `await`. | App đăng ký một adapter headless trước khi render route. Entity gọi adapter bằng Promise; adapter lazy-load public entry của Study và chờ patch/lưu xong. Browse và Audio đều chờ kết quả. |
| P1 | `sessionStore` đăng ký window listener và BroadcastChannel ở module scope, ghi lại dữ liệu vừa được chính store phát; có thể phát sinh ghi trùng và tranh chấp với active session. | Bỏ hai listener mới. Store patch các session trước rồi phát notification; hook active session tiếp tục dùng lifecycle/lease và `skipBroadcast` sẵn có. |
| P1 | `CardDisplay` và `CardRendererFrame` luôn thêm wrapper DOM, thay đổi chuỗi chiều cao `h-full` và viewport mặc định. | Không thêm wrapper khi không dùng header/footer slots. Giữ class, sandbox, hai mặt và iframe instances khi flip. Có test kiểm tra trực tiếp hierarchy/classes và identity. |
| P2 | Frame/media preview mới tồn tại cùng implementation cũ; hai Frame có hai script-loader promises riêng. | Implementation canonical nằm trong entity. Đường dẫn Frame, CardDisplay và Browse MediaFieldPreview cũ chỉ còn compatibility shim. |
| P2 | Entity sao chép và làm rộng Study wire schemas; renderer shim `export *` kéo cả UI/event hub vào headless callers. Có DTO/protocol types tự đặt chưa có caller. | Entity chỉ giữ renderer inputs trung lập và media/payload/UI contracts thực sự dùng. Study wire artifacts giữ tại `features/study/types.ts`. Renderer shim dùng explicit exports từ entry `lib`; port cập nhật dùng entry `model` riêng. Bỏ DTO/protocol types không dùng. |
| P2 | Broadcast test không assert nếu không nhận được message. Boundary test dò chuỗi toàn file, có thể tính comment thành import hoặc bỏ sót relative/dynamic imports. | Broadcast test luôn kiểm tra payload, channel và close bằng mock. Boundary test dùng TypeScript AST cho imports, re-exports và dynamic imports; cho phép App composition, loại test fixtures khỏi audit production code. |

## Các entry cần dùng khi làm tiếp

- UI: `frontend/src/entities/flashcard/index.ts`.
- Headless renderer: `frontend/src/entities/flashcard/lib/clientRenderer.ts` (`renderCardSide`, `patchRenderContext`).
- Port cập nhật field: `frontend/src/entities/flashcard/model/cardContentUpdates.ts` (`updateCardFieldValues`). Caller phải `await`; event notification không thay thế persistence.
- App composition: `frontend/src/app/studyContentSync.ts`, được import trước khi router render trong `App.tsx`.
- Study persistence public entry: `frontend/src/features/study/contentUpdates.ts`. Chỉ app composition hoặc nội bộ Study được import Study; Browse/Audio không import store.
- Pure session patch: `frontend/src/features/study/session/contentPatchAdapter.ts`, dùng chung cho hook và store, không mutate snapshot đầu vào.

Template authoring tiếp tục không patch template artifacts của active lease. Việc Gemini bỏ các lời gọi `updateTemplateInSessions` vốn no-op trong NoteType save/reset được giữ lại; API mutation, toast và query invalidation vẫn như trước.

## Kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| Focused Vitest: entity, app binding, Study adapters/store/hook | 13 files, 143 tests PASS. Bao gồm regression cho app/headless persistence, session của cùng note và DOM mặc định. |
| `.\.venv\Scripts\python.exe scripts/run_tests.py --module study,browse,audio --frontend-only` | 31 files, 290 tests PASS. Bao gồm các caller qua shim, lease/restore/scheduler và frozen template contract. |
| `npm run typecheck` | PASS. |
| `npm run lint` | PASS, còn warnings hiện hành về Fast Refresh/hooks; không có lint errors. |
| `npm run build:ci` | PASS. StudyPage và sessionStore vẫn là chunks riêng; public contentUpdates được dynamic import. Có cảnh báo chunk chính trên 500 kB. |
| Đối chiếu renderer/media preview với HEAD | Renderer giữ logic sanitization/media/CSS/scripts; MediaFieldPreview giữ implementation, chỉ export props. |

Hai lượt test có overlap; không cộng 143 và 290 thành số test riêng biệt.

Chưa chạy screenshot comparison trên browser hoặc thử IndexedDB/BroadcastChannel bằng nhiều tab thật. DOM assertions, host runtime tests và fallback persistence tests không thay thế bằng chứng đó. Không xác nhận toàn bộ Zero Visual Regression hay toàn bộ C02 đã hoàn tất.

Các shim còn lại được giữ cho caller trong migration. Gói này không hoàn thành C01, entity DTO/query migration hoặc các sửa R1–R8 của tài liệu G00; xem [review G00](G00_CODEX_REVIEW_2026-10-04.md) trước khi mở gói chuyển đổi tiếp theo. Chưa commit/push.
