# Kế hoạch chuyển cấu trúc frontend Flama

- Ngày review: 2026-10-03 (Asia/Tokyo).
- Trạng thái: **Đề xuất để review; chưa triển khai migration**.
- Phạm vi: cấu trúc React SPA, ranh giới module, state/API và khả năng bảo trì.
- Nguyên tắc: bảo toàn giao diện, URL, quyền hiện hành, API và dữ liệu phiên học; chuyển từng slice bằng PR nhỏ.
- Nguồn quyết định: code hiện tại. Báo cáo nghiên cứu ngày 01/10 là tham khảo, không tự chứng minh một thay đổi đã được duyệt hoặc đã được triển khai.

## 1. Kết luận review

Frontend đã có nền tảng tốt: React 19, TypeScript, Vite, lazy routes, TanStack Query, UI primitives và 22 thư mục feature. Vấn đề chính là các thư mục feature hiện chứa lẫn route page, giao diện ghép nhiều tính năng, DTO, API và runtime; đổi tên thư mục đơn thuần sẽ không giải quyết được việc này.

Đề xuất giữ stack hiện tại, chuẩn hóa sáu tầng **app → pages → widgets → features → entities → shared**, theo miền nghiệp vụ Flama. Các thư mục con chỉ tạo khi có nội dung; không chia mỗi nút bấm thành một feature. UI state đặt gần nơi dùng, server state thuộc query cache, runtime study và state bền vững có chủ sở hữu riêng.

### Số liệu kiểm kê

Đếm các tệp `.ts/.tsx` trong `frontend/src`, bỏ `.test./.spec.` và `__tests__` khỏi nhóm source. Phân tích import/export/dynamic import có chuỗi literal bằng TypeScript AST, resolve alias `@/`, relative path và index file. Đếm state là số lời gọi `useState` trực tiếp; không phải kết quả profiling.

| Chỉ số | Kết quả |
|---|---:|
| Source TS/TSX (ngoài tệp test được nhận diện bằng tên) | 331 |
| Tệp test TS/TSX được nhận diện bằng tên/thư mục | 82 |
| Dòng source TS/TSX | 96154 |
| Import giữa các feature khác nhau | 45 |
| Cặp feature có phụ thuộc | 28 |
| Nhóm vòng phụ thuộc file khi tính cả type imports | 5 |
| Nhóm vòng phụ thuộc file sau khi bỏ import type tường minh | 0 |

Không phát hiện vòng runtime trong đồ thị import được phân tích. Năm nhóm vòng khi tính cả type imports phản ánh hướng phụ thuộc chưa rõ; không được diễn giải thành lỗi runtime đã xảy ra. Scan không bao quát dynamic import có đường dẫn tính toán hoặc mọi phụ thuộc ngầm qua browser/global state.

### Các vấn đề được xác minh

| Mức | Bằng chứng hiện tại | Hệ quả cho bảo trì | Task |
|---|---|---|---|
| Cao | `features/worksheets/components/DeckWorksheetModal.tsx`: 4.387 dòng; `WorksheetPageRenderer.tsx`: 1.718 dòng. Đã có một số step component và print/storage utility. | Còn gộp wizard, studio controls, preview và hiệu ứng; sửa một khu vực phải đọc file lớn. Tiếp tục tách phần còn lại. | FE-12, FE-13 |
| Cao | `features/browse/hooks/useBrowseState.ts`: 1.052 dòng, 48 lời gọi `useState`; DTO được khai báo trong hook. | Query, editor, selection, TTS và persistence khó thay đổi độc lập. Chưa profiling nên chưa kết luận có waterfall render. | FE-06, FE-11 |
| Cao | `features/study/hooks/useStudySession.ts`: 1.463 dòng, gắn với commit receipt, lease, restore, quarantine và note batch. | Refactor dễ ảnh hưởng tiến độ bền vững. Chuyển sau các foundation và giữ engine/scheduler riêng. | FE-19 |
| Cao | `shared/api/bootstrap.ts` import `app/api.ts`; domain API dùng `appApi`; `app/api.ts` lại import type của auth/dashboard/statistics. | Tầng dưới phụ thuộc tầng khởi tạo, khó cô lập API và test. | FE-04, FE-05 |
| Cao | Browse/audio import thẳng `features/study/session/sessionStore`; preview NoteType/Marketplace dùng `features/study/components/CardDisplay`. | Sửa thẻ và preview kéo theo internals của study. Phải tách renderer dùng chung và cổng đồng bộ nội dung phiên. | FE-06, FE-11, FE-16, FE-19 |
| Vừa | `lib/ankiSyncEngine.ts` import `features/import/api`; `lib/flamaAudioClient.ts` import type của audio. | `lib` chứa cả utility trung lập và nghiệp vụ tích hợp. | FE-15, FE-16 |
| Vừa | `features/mcp/types.ts` re-export scope/policy từ hook settings; settings hook gọi hook MCP. | Có vòng khi tính cả type imports và policy đặt sai chủ sở hữu. MCP đã có manager/component chung. | FE-14 |
| Vừa | Browse dùng `['bootstrap']`; shared bootstrap dùng `['frontend','bootstrap']`. Invalidation được viết rải rác. | Cùng session có nhiều cache identity; khó đảm bảo mọi view được cập nhật. | FE-05, FE-06 |
| Vừa | Router trong `App.tsx`; title ở `AppLayout`; menu ở sidebar; links ở `app/api.ts`. Admin routes nằm dưới `RequireAuth`, creator guard chỉ xuất hiện tại một nhóm route. | Metadata và quyền hiển thị không có một điểm đối chiếu. Backend vẫn là nơi thực thi quyền; đây không phải kết luận về lỗ hổng backend. | FE-07, FE-08 |
| Vừa | UI ở `components/ui`, `shared/ui`, `shared/components`; cấu hình shadcn trỏ `components/ui`. | Đường dẫn và trách nhiệm dùng chung chưa thống nhất; cần chuyển cả generator aliases. | FE-09 |
| Vừa | `frontend/docs/COMPONENT_ARCHITECTURE.md` còn React 18, `app/routes.tsx`, `query-client.ts` không khớp code hiện tại. | Người bảo trì có thể sửa nhầm nơi hoặc hiểu sai hướng phụ thuộc. | FE-23 |

Báo cáo nghiên cứu ngày 01/10 nói MCP còn trùng lặp nguyên khối. Hiện đã có `features/mcp/components/McpTokensManager`, hooks và modal dùng chung; kế hoạch này chỉ hoàn thiện policy/types/API và composition còn lại. Các primitive như SearchInput, ConfirmDialog, CardFieldsForm, SplitPane cũng đã tồn tại; ưu tiên tái sử dụng và hoàn thiện, không tạo bản sao.

## 2. Cấu trúc mục tiêu

```text
frontend/src/
  app/
    providers/             # query client, tooltip, toaster, bootstrap ứng dụng
    router/                # routes, aliases, route metadata, access policy
    styles/                # CSS global và tokens hiện tại
  pages/
    dashboard/             # route entry và ghép workspace
    browse/
    study/
    worksheets/
    marketplace/
    account/
    admin/
    public/
    support/
  widgets/
    app-shell/             # public layout, sidebar, header, footer, mascot
    browse-workspace/
    study-workspace/
    worksheet-studio/
    marketplace-catalog/
    mcp-token-manager/
  features/
    study/                 # session orchestration, scheduler, restore, commit
    browse/                # tìm/lọc/chọn; editor có controller riêng
    note-editor/
    note-type-editor/
    worksheets/            # wizard, presets, layout, print actions
    import/
    anki-sync/
    audio/
    marketplace-publish/
    deck-install/
    deck-collaboration/
    mcp-access/
    yomitan-connect/
    admin-management/      # chia module users/payments/taxonomy khi cần
    account/
    support/
  entities/
    session/               # session DTO, actor capabilities, bootstrap query
    user/
    deck/
    flashcard/             # Note, Card, NoteType, Field, Template, renderer DTO
    media/
    marketplace-item/
    mcp-token/
    order/
    wallet/
    support-ticket/
  shared/
    api/                   # HTTP/CSRF/error envelope/upload; không biết domain
    config/                # env và URL resolution không phụ thuộc app
    ui/                    # primitive + UI trung lập dùng chung
    lib/                   # utility thuần và browser adapters trung lập
    assets/
```

Tên slice cụ thể được chốt bằng FE-02. Các thư mục nhóm trong sơ đồ là định hướng, không bắt buộc tạo đầy đủ ngay. Bên trong slice dùng `ui/`, `model/`, `api/`, `lib/` khi hữu ích.

Gộp Note/Card/NoteType/Template trong `entities/flashcard` trước để tránh tạo nhiều entity phụ thuộc ngang. Study manifest, scheduling, event log, receipt và restore vẫn thuộc study; không nâng các contract này thành DTO chung chỉ vì được import nhiều lần.

### Quy tắc phụ thuộc

- Tầng trên được import tầng dưới; mỗi slice có public exports tường minh qua `index.ts`.
- Feature không import internals của feature khác. Widget/page/app chịu trách nhiệm ghép các feature; data/query/policy thật sự dùng chung được đưa xuống entity.
- Entity không import feature; shared không import entity/feature/widget/page/app.
- Cả type imports phải theo boundary. Các ngoại lệ hiện tại có allowlist theo đường dẫn, owner và task xử lý; không miễn trừ cả `features/**`.
- Không dùng barrel `export *` để xuất toàn bộ runtime. Nội bộ slice dùng relative imports để tránh self-barrel cycle; entry route và runtime lớn phải giữ lazy boundary.
- Giữ callback hoặc adapter tường minh cho việc patch persisted study content sau sửa note/tạo audio. Composition gọi public API của study; không dựng event bus toàn cục chưa có nhu cầu.
- Tách hooks theo trách nhiệm và vòng đời state. Không ép một ngưỡng dòng hay số state thay cho thiết kế; chỉ dùng số liệu để tìm điểm cần review.
- Không đưa scheduler, IndexedDB sessions, Anki sync profile hay logic thanh toán vào utility chung.
- Với chuyển UI, giữ nguyên class, tokens, DOM/layout, focus, keyboard, portal, mounted/unmounted behavior và các data-tour selector. Có thể dùng fragment hoặc API `asChild` hiện có khi cần, không thêm wrapper gây lệch bố cục.

## 3. Bảng task triển khai

Ưu tiên: **P0** là điều kiện/gate của migration; **P1** xử lý kiến trúc hoặc điểm khó bảo trì chính; **P2** hoàn thiện phần còn lại.
Cỡ task: **S** tập trung ít file; **M** một slice; **L** nhiều trách nhiệm trong một workspace; **XL** phải tách thành nhiều PR. Đây là cỡ tương đối, không phải cam kết thời gian.

Tất cả task đang ở trạng thái **Đề xuất**. Owner mặc định là người triển khai FE; task liên quan contract phối hợp reviewer backend nhưng không tự mở rộng sang thay schema/API.

| ID | Ưu tiên / Cỡ | Việc cần làm | Phụ thuộc | Tiêu chí nghiệm thu chính |
|---|---|---|---|---|
| FE-01 | P0 / M | Lập baseline route, alias, quyền, URL/query, module tests và ảnh desktop/mobile của các workspace trọng yếu. Ghi trạng thái loading/empty/error và modal. | — | Có ma trận trước/sau và dữ liệu cố định cho dashboard, browse, study, worksheet, marketplace, admin; cảnh báo lint hiện tại được ghi nhận. |
| FE-02 | P0 / M | Chốt ADR sáu tầng, mapping đủ 22 thư mục feature, owner cho DTO/query/runtime và thứ tự chuyển. | FE-01 | Mỗi file/module có nơi đến; preview, study patch, Anki worker và support-ticket có chủ sở hữu rõ. |
| FE-03 | P0 / M | Thêm kiểm tra import boundary/cycle/public API với allowlist có owner; cập nhật test selection và CI theo mỗi đường dẫn mới. | FE-02 | Tệp thử vi phạm thực sự làm check fail; type/value cycle báo riêng; moved tests không bị bỏ sót; module cũ không chặn rollout. |
| FE-04 | P1 / M | Tách HTTP transport/env khỏi `app/api`; domain adapters đặt tại entity/feature. Giữ shim chỉ cho caller chưa chuyển. | FE-03 | Shared không import app; giữ credentials include, CSRF refresh, timezone, FormData, keepalive, error và API-base resolution. |
| FE-05 | P1 / M | Đưa session DTO/capabilities/bootstrap query xuống entity; thống nhất session query key và invalidation. | FE-04 | Login/logout/expiry/verify-email cập nhật mọi consumer; không còn session cache song song; response mapping giữ đúng contract. |
| FE-06 | P1 / L | Tách deck/flashcard/media DTO khỏi hook/page; tạo query keys theo domain; đưa renderer dùng chung xuống flashcard entity. | FE-04, FE-05 | Browse/editor/NoteType/Marketplace/Study dùng public contracts; renderer giữ sandbox, media proxy, patch và hai mặt card được mount như cũ. |
| FE-07 | P1 / M | Tập trung route/alias/title/layout/access metadata; menu derive từ cùng policy. Ghi riêng các bất nhất quyền hiện có. | FE-05 | Deep link, refresh, `next`, alias/query và quyền backend hiện hành không đổi; mọi sửa hành vi quyền là PR riêng có nghiệm thu. |
| FE-08 | P1 / M | Tách providers/router khỏi entry; chuyển public/authenticated shell, header/sidebar/footer sang widget. | FE-07 | Ba kiểu layout hiện tại được giữ; browse/study vẫn full-screen; lazy routes không thành eager imports. |
| FE-09 | P1 / M | Quy về `shared/ui`, phân biệt primitive và UI ghép trung lập; chuyển shadcn aliases và utility imports. | FE-03 | Generator ghi đúng nơi; không còn hai implementation của cùng primitive; class/tokens/DOM/focus không đổi; shim có lịch xóa. |
| FE-10 | P1 / M | Chuyển dashboard/statistics làm pilot pages/widgets/features/entity contracts. | FE-06, FE-08, FE-09 | Cây deck, drag/drop, New/Learn/Due, heatmap và filter/timezone giữ kết quả; pilot không còn import ngược tầng. |
| FE-11 | P1 / XL | Tách browse hook thành query, URL filters, selection, note editor, bulk actions và tool controllers; nối study patch qua adapter. | FE-06, FE-08, FE-09, FE-10 | Search/pagination/multi-select/edit/delete/TTS giữ hành vi; source và installed clone cùng được kiểm tra; edit không mất patch phiên học. |
| FE-12 | P1 / XL | Tách worksheet studio thành wizard model, controls, preview controller và preset persistence; tiếp tục dùng step components đã có. | FE-06, FE-08, FE-09, FE-10 | Standalone/deck/card selection, mobile controls/preview, zoom và presets giữ nguyên; modal chỉ còn composition. |
| FE-13 | P1 / L | Tách worksheet renderer theo loại mẫu; cô lập geometry và print pipeline. | FE-12 | Mẫu A4 portrait/landscape, pagination, QR/strokes và print output khớp baseline; preset key không đổi. |
| FE-14 | P1 / M | Đưa MCP token/policy/scopes xuống entity; manager dùng chung ở widget, controller user/admin/OAuth có trách nhiệm riêng. | FE-05, FE-08, FE-09 | Không còn vòng settings ↔ MCP; create/rotate/revoke/secret/scopes/OAuth vẫn đúng; không xây lại manager đã có. |
| FE-15 | P1 / L | Chuyển Anki sync engine/packages/IndexedDB/worker khỏi `lib` vào slice tích hợp; tách import wizard và mapping types. | FE-04, FE-06, FE-09 | Giữ subtree deck, note/card mapping, chunk/retry/media và resume; DB name/version/key và worker URL không đổi ngoài ý định. |
| FE-16 | P1 / L | Tách Flama Audio client, connection, synthesis queue, upload và note patch; đặt DTO/helper ở đúng tầng. | FE-06, FE-11 | VoiceVox/Kokoro, cancel/retry, progress, upload/media và persisted study patch hoạt động như baseline. |
| FE-17 | P1 / XL | Tách catalog/detail khỏi publishing controllers; đưa page composition lên pages/widgets. | FE-06, FE-08, FE-09, FE-10 | Filter/taxonomy/preview/pricing/install/review/keys giữ hành vi; publish wizard không còn nằm toàn bộ trong page. |
| FE-18 | P1 / L | Tách installed library, release/update, change-request inbox/detail và diff workspace; chia sẻ entity contracts. | FE-06, FE-17 | Release pinning, diff/conflict, apply update và local overrides giữ nguyên; clone edit không mutate source. |
| FE-19 | P1 / XL | Tách study orchestration thành open/restore, local review, commit/batch, lease, content patch và lifecycle adapters; giữ một chủ sở hữu điều phối. | FE-05, FE-06, FE-08, FE-11; baseline study FE-01 | Engine/scheduler không đổi; undo/resume/offline/retry/quarantine/exit/multi-tab và v4 receipt/note batching đều qua kiểm tra. |
| FE-20 | P2 / XL | Tách admin users/permissions/payments/fees/taxonomy/images/TTS/tickets/analytics thành page + controllers/widgets. | FE-05, FE-08, FE-09, FE-14 | Query/filter/bulk action/permission và số liệu tiền giữ kết quả; admin/user ticket dùng contracts chung thay import admin internals. |
| FE-21 | P2 / L | Chuyển profile/wallet/orders/goals sang page composition và domain API/query. | FE-05, FE-06, FE-08, FE-09, FE-17 | Profile edit/avatar/verification, portfolio, wallet/history/order/payment result và goals giữ luồng; số tiền không được đổi cách tính. |
| FE-22 | P2 / M | Chuyển guide/support/onboarding/public/legal; chia content data và interactions đúng owner. | FE-08, FE-09, FE-14, FE-20 | URL guide/legal/ticket, tour selectors, storage key và hướng dẫn tương tác giữ nguyên. |
| FE-23 | P0 / M | Xóa shim/allowlist đã hết nhiệm vụ; cập nhật README/component guide và module test map cuối cùng. | FE-10 đến FE-22 hoàn tất | Tài liệu phản ánh code thật; không còn import sang đường dẫn cũ; tất cả tests có owner; không còn rule exception vô chủ. |
| FE-24 | P0 / M | Nghiệm thu toàn bộ migration, build/deep-link/API contract smoke, ảnh và rollout/rollback. | FE-23 | CI qua, visual/function checks qua, không tăng dependency/bundle ngoài quyết định được ghi nhận; rollback bằng revert từng PR. |

FE-03 và việc cập nhật test map được thực hiện xuyên suốt mỗi PR, không chờ đến FE-23. FE-01 baseline của slice chưa chuyển được bổ sung ngay trước khi chuyển nếu source thay đổi trong lúc triển khai.

### Thứ tự triển khai

1. **Foundation:** FE-01 → FE-02 → FE-03 → FE-04 → FE-05/06; sau đó FE-07/08 và FE-09.
2. **Pilot:** FE-10. Chốt convention bằng code thật trước khi nhân rộng.
3. **Các điểm khó bảo trì:** FE-11, FE-12/13, FE-14, FE-15, FE-16 theo phụ thuộc trong bảng.
4. **Marketplace và collaboration:** FE-17 → FE-18. Tránh trộn refactor overlay với thay contract backend.
5. **Study:** FE-19 triển khai sau foundation, riêng từng PR có test durability; không cùng PR với thay thuật toán/schema.
6. **Phần còn lại:** FE-20/21/22, rồi FE-23/24.

Các nhánh công việc không chia sẻ file có thể thực hiện độc lập sau foundation; đây là kế hoạch phụ thuộc, không phải yêu cầu khởi chạy subagent.

## 4. Quy trình cho mỗi PR

1. Chọn một slice và ghi đường dẫn trước/sau cùng các caller, test, cache/storage key liên quan.
2. Chuyển cơ học trước; tách responsibility trong PR tiếp theo khi cần. Giữ public shim trong giai đoạn chuyển, tránh mass replace xuyên toàn repo.
3. Chuyển tests cùng source và cập nhật `scripts/run_tests.py` module globs + dependencies trong cùng PR. File runner đang có thay đổi chưa commit ở working tree khi review; phối hợp với người đang sở hữu thay đổi trước khi triển khai.
4. Chạy architecture check, lint, typecheck, module tests phù hợp và build khi đổi route/entry/worker/chunk.
5. So ảnh các view bị ảnh hưởng và kiểm tra keyboard/focus/portal/scroll/resize. Mọi Chrome debug/QA dùng user-data-dir riêng.
6. Revert PR nếu khác biệt chưa được giải thích hoặc contract bị đổi; chưa xóa adapter khi còn consumer.

Không chấp nhận một PR di chuyển toàn bộ frontend rồi mới kiểm thử. Không bổ sung thư viện state/architecture hoặc đổi framework chỉ để đổi cây thư mục. Test mới tập trung boundary, cache/invalidation, persistence và các hành vi có nguy cơ thay đổi; tránh test chỉ lặp lại JSX hoặc implementation.

## 5. Nghiệm thu đặc thù Flama

| Khu vực | Kiểm tra bắt buộc |
|---|---|
| UI | Desktop/mobile; màu, brand gradient, padding, font, icon, shadow, bố cục; trạng thái mở modal, keyboard/focus và tour selector. |
| Auth/API | Session/bootstrap; login/logout/expiry; CSRF refresh; timezone; credential cross-origin; upload/keepalive; backend unavailable → maintenance. |
| Routing | URL và query giữ nguyên; direct navigation/refresh; alias; `next`; authenticated/admin/creator capability được đối chiếu policy hiện hành. |
| Renderer/media | Sandbox `allow-scripts` không thêm `allow-same-origin`; host script/version, postMessage constraints, media proxy; flip không remount sai template. |
| Study | Note-centric session v4; local persistence; receipt validation; batch acknowledgment; undo/restore/quarantine; day-boundary; đa tab; exit/offline/retry không mất hoặc ghi đôi tiến độ. |
| Overlay | Source owner và installed clone; source identity + applied release + local overrides; edit/update/change-request không ghi sai source. |
| Anki/Audio | Deck subtree mapping; media chunk/retry; IndexedDB/profile compatibility; worker URL; local engine connection/cancel/upload; patch nội dung phiên học. |
| Worksheets | Standalone/deck; mapping/preset; zoom/mobile; A4 geometry/page break và output in. |
| Commerce | Order/payment-result, wallet, fee/pricing formatting, role/capability; không đổi nguồn hay công thức số tiền. |
| Deployment | FE có thể deploy độc lập backend; giữ API backward compatibility; Vite asset/deep-link serving và chunk baseline. |

### Kiểm tra thực hiện trong lần review này

- `npm run lint`: **PASS (exit 0)**, có cảnh báo existing về Fast Refresh, hook dependencies và một số utility/props.
- `npm run typecheck`: **PASS (exit 0)**.
- Kiểm kê source/import bằng TypeScript AST: **hoàn thành**, số liệu ở mục 1.
- Chưa chạy build, feature tests, browser QA hay profiling; đây là review cấu trúc và proposal, không phải xác nhận mọi tính năng runtime đều đúng.
- Chưa thay đổi code frontend/backend, skill hoặc test runner. Chỉ tạo tài liệu proposal này.

Ở host hiện tại lệnh `python` trỏ vào Windows App Execution Alias và không chạy được; kiểm kê dùng Node + TypeScript có sẵn trong `frontend/node_modules`. Khi triển khai cần dùng Python environment thật của repo cho modular runner; không tự ý đổi PATH/global setup.

### Lệnh kiểm tra khi triển khai

```powershell
# Tại frontend/
npm run lint
npm run typecheck
npm run build

# Tại repo root, dùng interpreter Python hoạt động của dự án
python scripts/run_tests.py --changed --frontend-only
python scripts/run_tests.py --module study --frontend-only
python scripts/run_tests.py --module browse --frontend-only
python scripts/run_tests.py --list-modules
```

Dùng module narrowest phù hợp và cập nhật mapping ngay khi chuyển file. Full suite là gate CI/pre-release theo AGENTS.md, không chạy ở mọi PR.

## 6. Nguồn đối chiếu

- [Router hiện tại](../../../frontend/src/App.tsx), [layout](../../../frontend/src/layouts/AppLayout.tsx), [sidebar](../../../frontend/src/components/app-sidebar.tsx).
- [App API](../../../frontend/src/app/api.ts), [HTTP client](../../../frontend/src/shared/api/client.ts), [bootstrap](../../../frontend/src/shared/api/bootstrap.ts), [env](../../../frontend/src/config/env.ts).
- [Browse state](../../../frontend/src/features/browse/hooks/useBrowseState.ts), [study orchestration](../../../frontend/src/features/study/hooks/useStudySession.ts), [study storage](../../../frontend/src/features/study/session/sessionStore.ts).
- [Worksheet studio](../../../frontend/src/features/worksheets/components/DeckWorksheetModal.tsx), [worksheet renderer](../../../frontend/src/features/worksheets/components/WorksheetPageRenderer.tsx).
- [MCP types](../../../frontend/src/features/mcp/types.ts), [settings MCP controller](../../../frontend/src/features/settings/hooks/useMcpTokenCRUD.ts), [admin MCP page](../../../frontend/src/features/admin/pages/AdminMcpTokensPage.tsx).
- [Anki sync engine](../../../frontend/src/lib/ankiSyncEngine.ts), [audio controller](../../../frontend/src/features/audio/hooks/useLocalAudioEngine.ts).
- [Component guide hiện tại](../../../frontend/docs/COMPONENT_ARCHITECTURE.md), [frontend README](../../../frontend/README.md), [shadcn config](../../../frontend/components.json), [CI](../../../.github/workflows/ci.yml), [modular runner](../../../scripts/run_tests.py).
- [Nghiên cứu kiến trúc ngày 01/10](../../architecture/FRONTEND_ARCHITECTURE_SELECTION_RESEARCH.md), [renderer boundary](../../architecture/CARD_TEMPLATE_SANDBOX_RENDERER.md), [overlay cutover](../completed/CLONE_CUTOVER_REPORT.md).
- Hướng dẫn frontend được tìm thấy ở [bản sao repo-local](../../../.agents/teamwork/challenger_architecture_1/flama-frontend-architecture-SKILL.md); file `skills/flama-frontend-architecture/SKILL.md` không có trong checkout khi review. Bản sao cung cấp quy tắc sáu tầng/Zero Visual Regression; số liệu và proposal đều được đối chiếu code lại.

