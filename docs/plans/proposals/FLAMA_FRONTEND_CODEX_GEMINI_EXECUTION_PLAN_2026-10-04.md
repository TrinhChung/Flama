# Phân công migration frontend: Codex điều phối, Gemini chuyển đổi

- Ngày lập: **2026-10-04, Asia/Tokyo**.
- Trạng thái: **Kế hoạch để người dùng duyệt; chưa giao việc hoặc khởi chạy Gemini, chưa sửa source frontend**.
- Căn cứ: [proposal cấu trúc ngày 03/10](FLAMA_FRONTEND_STRUCTURE_MIGRATION_PLAN_2026-10-03.md), đã đối chiếu lại các điểm trọng yếu với code.
- Phạm vi: nâng cấp cấu trúc React SPA hiện tại, giữ stack, giao diện, URL và hành vi. Không bao gồm redesign, đổi thuật toán học, API backend hoặc schema.

## 1. Cách chia việc

**Gemini là người chuyển đổi chính**: di chuyển module, tách component, tách controller cục bộ khi contract đã rõ, chuyển page/widget, sửa imports trong phạm vi được giao và chuyển tests cùng source.

**Codex là người điều phối và xử lý phần khó**: chốt kiến trúc, mapping và contract; chia từng gói; quản lý quyền sửa file; xử lý state dùng chung, API/query cache, renderer, persistence, worker, study runtime và các luồng nhạy cảm. Codex đọc toàn bộ diff và kiểm tra lại trước khi nghiệm thu mỗi gói Gemini.

Người dùng duyệt kế hoạch và cho Gemini bắt đầu. Sau đó Codex giao lần lượt các gói theo phụ thuộc; checkpoint giữa các gói là bước review kỹ thuật, không cần xin lại quyền thực hiện phạm vi đã duyệt.

Không cố chia đều số dòng hoặc số task. Gemini nhận phần lớn công việc chuyển đổi UI; Codex nhận các điểm mà thay đổi vòng đời, cache hoặc durability có thể làm sai hành vi dù build vẫn qua.

## 2. Bằng chứng và baseline hiện tại

Kiểm kê ngày 04/10: **22 thư mục feature, 331 tệp source TS/TSX và 82 tệp test**. Nhận diện test bằng `.test.`, `.spec.` và thư mục `__tests__`; không diễn giải số file test thành độ bao phủ hành vi.

| Điểm đã đối chiếu | Ảnh hưởng tới phân công |
|---|---|
| `shared/api/bootstrap.ts` gọi `app/api.ts`; `app/api.ts` phụ thuộc auth/dashboard/statistics | Codex tách transport, domain adapters và bootstrap trước khi Gemini chuyển caller. |
| Browse dùng `['bootstrap']`, bootstrap chung dùng `['frontend', 'bootstrap']` | Codex thống nhất cache identity và invalidation, kiểm tra login/logout/expiry. |
| Browse, audio và NoteType editor gọi internals `study/session/sessionStore` | Codex định nghĩa cổng patch nội dung; Gemini dùng contract đã chốt. |
| NoteType/Marketplace preview dùng `study/components/CardDisplay` | Codex chuyển renderer dùng chung, giữ iframe sandbox và hai mặt card luôn mounted. |
| `useBrowseState.ts` khoảng 1.053 dòng; `useStudySession.ts` khoảng 1.464 dòng | Codex xử lý orchestration và vòng đời, Gemini xử lý workspace UI sau đó. |
| Worksheet modal khoảng 4.388 dòng; renderer khoảng 1.719 dòng | Gemini tách UI; Codex giữ model/persistence/geometry/print contract. |
| Anki engine trong `lib/` phụ thuộc import API, có worker và IndexedDB | Codex chuyển engine/worker/storage; Gemini chuyển wizard và giao diện sync. |
| MCP đã có manager và modal chung; types còn re-export policy từ settings hook | Hoàn thiện ranh giới, không xây lại manager. Policy/OAuth controller nhạy cảm thuộc Codex. |

Kiểm tra đã thực hiện cho lần lập kế hoạch này:

| Kiểm tra | Kết quả |
|---|---|
| `npm run lint` | PASS, còn warnings có sẵn về Fast Refresh, hook dependencies và một số utility/props. |
| `npm run typecheck` | PASS. |
| `npm run build` | PASS; có cảnh báo chunk lớn hơn 500 kB và plugin timings. |
| `.venv\Scripts\python.exe scripts/run_tests.py --module decks --frontend-only` | PASS: 4 tệp dashboard, 24 tests. |
| `.venv\Scripts\python.exe scripts/run_tests.py --list-modules` | PASS; dùng được Python environment của repo. |
| Browser/ảnh trước-sau, study durability, các domain còn lại | Chưa thực hiện; là đầu việc baseline/nghiệm thu khi triển khai. |

Build đã sinh output local trong `frontend/dist`; không có thay đổi source frontend trong lần lập kế hoạch này. Không lấy baseline trên đây để kết luận toàn bộ sản phẩm đã được QA.

Working tree đang có công việc backend/database khác. Trong lúc khảo sát, `.github/workflows/ci.yml` và `scripts/run_tests.py` cũng xuất hiện thay đổi. Hai agent phải ghi snapshot trước mỗi gói, giữ nguyên thay đổi ngoài nhiệm vụ; Codex phối hợp các file tooling trước khi sửa. Không reset/stash toàn bộ workspace hay gộp chúng vào migration frontend.

## 3. Kiến trúc và mapping dự kiến

Giữ đề xuất sáu tầng **app → pages → widgets → features → entities → shared**. Tầng trên dùng public API của tầng dưới; không import internals của slice ngang hàng. Type imports cũng tuân thủ boundary. Ngoại lệ tạm thời phải có owner, caller và gói xóa cụ thể.

`app` giữ entry/providers/router. `pages` giữ route composition. `widgets` ghép workspace hoặc nhiều feature. `features` giữ hành động nghiệp vụ. `entities` giữ DTO/query/renderer theo domain. `shared` chỉ giữ transport, config, UI và utilities trung lập.

Không bắt buộc mọi component dùng compound pattern hoặc context. Chỉ tạo segment có nội dung; không tách từng nút thành một feature. Không dùng `export *` làm runtime lớn trở thành eager import. Shim giữ API cũ trong lúc chuyển, không sao chép implementation.

Mapping dưới đây bao quát đủ 22 thư mục hiện tại. G00 ghi nhận caller; C00 chốt đường dẫn chính xác trước khi chuyển source.

| Slice hiện tại | Nơi đến theo trách nhiệm | Người chuyển chính / phần Codex giữ |
|---|---|---|
| `auth` | `pages/account`, `features/account`, `entities/session`, access policy trong `app/router` | Gemini: forms/pages; Codex: session và guards. |
| `dashboard` | `pages/dashboard`, `widgets/dashboard-workspace`, deck/user contracts | Gemini pilot; Codex query/contracts. |
| `statistics` | `pages/statistics`, `widgets/statistics-overview`, queries theo domain | Gemini UI; Codex cache/timezone contract. |
| `browse` | `pages/browse`, `widgets/browse-workspace`, `features/browse`, `features/note-editor` | Gemini UI; Codex filters/query/selection/mutations/persisted patch. |
| `study` | `pages/study`, `widgets/study-workspace`, `features/study`; renderer chung xuống `entities/flashcard` | Codex thực hiện runtime và tích hợp; giữ engine/scheduler riêng. |
| `worksheets` | `pages/worksheets`, `widgets/worksheet-studio`, `features/worksheets` | Gemini controls/wizard UI/render branches; Codex state/geometry/persistence/print. |
| `note-types` | `pages/note-types`, `features/note-type-editor`, `entities/flashcard` | Gemini editor UI/local controller; Codex template patch và renderer contract. |
| `import` | `pages/import`, `features/import`, `features/anki-sync`; selector trung lập theo deck entity | Gemini wizard/UI; Codex engine/worker/resume/storage. |
| `audio` | `pages/audio`, `features/audio`, media/flashcard contracts | Gemini UI; Codex client/queue/cancel/upload/content patch. |
| `marketplace` | `pages/marketplace`, catalog widget, publish/install features, marketplace-item entity | Gemini catalog/detail/publish UI; Codex pricing/install/payment/preview contract. |
| `library` | `pages/library`, library workspace, deck-install và marketplace-item contracts | Gemini page; Codex install/update contract. |
| `deck-collaboration` | `pages/deck-collaboration`, diff workspace, `features/deck-collaboration` | Gemini UI; Codex release/conflict/apply/overlay. |
| `mcp` | `entities/mcp-token`, `features/mcp-access`, `widgets/mcp-token-manager` | Gemini manager UI; Codex scopes/policy/API. |
| `settings` | Account goals; MCP/OAuth/Yomitan pages/controllers theo chức năng | Gemini pages; Codex policy/OAuth/revoke và session invalidation. |
| `oauth` | `pages/account`, consent feature/controller liên quan OAuth | Gemini consent UI; Codex redirect/approval/security contract. |
| `admin` | `pages/admin`, `features/admin-management`, các widgets theo miền | Gemini chia page/controller cục bộ; Codex quyền, tiền, token/ticket contracts. |
| `profile` | `pages/account`, account feature, user entity | Gemini UI; Codex verification/bootstrap/creator capability contract. |
| `orders` | `pages/account`, order entity và payment actions | Gemini UI; Codex status/redirect/amount semantics. |
| `wallet` | `pages/account`, wallet entity và wallet actions | Gemini UI; Codex amount/fee/payout semantics. |
| `guide` | `pages/guide`, guide widget, content data; public help-link API cho consumer | Gemini chuyển; Codex chốt public exports và route integration. |
| `onboarding` | Onboarding feature/widget; tour UI trung lập dùng chung khi phù hợp | Gemini chuyển, giữ selectors/storage keys. |
| `support` | `pages/support`, support feature, support-ticket entity dùng chung với admin | Gemini UI/content; Codex ticket contracts. |

Các file ngoài features cũng phải có owner: shell/layout/components → widgets hoặc shared UI; `config/env.ts` → shared config; utilities trung lập → shared lib; Anki/audio không chuyển vào shared lib; public/legal pages và content data → page/widget tương ứng. `CardFieldsForm` có flashcard semantics phải được phân loại theo dependency thật, không mặc định đưa mọi thứ trong `shared/ui` vào primitive chung.

## 4. Gói nhiệm vụ và phụ thuộc

Mã FE tham chiếu bảng 24 task trong proposal ngày 03/10. Mã C/G bên dưới là gói phân công thực tế. Mỗi hàng lớn phải tách thành các lượt bàn giao nhỏ như mô tả; không thực hiện toàn bộ hàng bằng một diff lớn.

| Gói | Owner | Công việc / phạm vi | Gate trước khi bắt đầu |
|---|---|---|---|
| C00 | Codex | FE-01/02/03: chốt mapping, contract, file locks, baseline matrix và boundary/cycle/public-export check; phối hợp test selection/CI đang thay đổi. | Người dùng cho triển khai; nhận G00 trước khi chốt mapping. |
| G00 | Gemini | Kiểm kê và đề xuất mapping/caller/test; chỉ ghi báo cáo, chưa chuyển source. | Người dùng cho Gemini bắt đầu. |
| C01 | Codex | FE-04/05: transport/env, domain API adapters, session DTO/bootstrap/cache/invalidation. Chia transport và session thành hai lượt. | C00. |
| C02 | Codex | FE-06: entity DTO/query contracts, renderer dùng chung và public content-patch adapter. Chia DTO, renderer, patch thành ba lượt. | C01. |
| C03 | Codex | FE-07/08: route metadata/aliases/access/layout contract và providers; tích hợp shell của Gemini. | C01; shell integration sau G02. |
| G01 | Gemini | FE-09: chuyển primitives/utilities trung lập sang shared, aliases shadcn và imports của caller được cấp quyền. | C00; slot riêng nếu caller trùng C01/C02/C03. |
| G02 | Gemini | FE-08: chuyển AppLayout/header/sidebar/footer/mascot và page shells, giữ DOM/class/layout. | C03 đã cung cấp metadata contract, G01. |
| G03 | Gemini | FE-10: pilot dashboard trước, statistics sau; chuyển pages/widgets, API caller và tests. | C02, C03/G02, G01. |
| C04 | Codex | FE-11: query/URL/selection/editor/bulk controllers, mutation invalidation và adapter patch phiên. | G03; mỗi controller một lượt, giữ facade tạm. |
| G04 | Gemini | FE-11: browse toolbar/table/sidebar/dialog/page composition theo controllers mới. | C04 contract tương ứng đã qua review. |
| C05 | Codex | FE-12/13: worksheet wizard/preview state, presets, geometry và print lifecycle. | C02, G03; chia state/presets rồi geometry/print. |
| G05 | Gemini | FE-12/13: tách studio controls/steps/layout; tách renderer theo template bằng props đã chốt, giữ output. | C05 contract tương ứng; mỗi nhóm controls/template một lượt. |
| C06.a | Codex | FE-15: chuyển Anki engine/worker/packages/IndexedDB, giữ request protocol và resume. | C01/C02, G01. |
| C06.b | Codex | FE-16: audio client/connection/queue/cancel/upload/persisted patch. | C02, C04. |
| G06 | Gemini | FE-15/16: import wizard, sync tabs, audio page/dialog/progress; chuyển tests. | C06.a hoặc C06.b tương ứng. |
| C07.a | Codex | FE-14: MCP token entity/policy/scopes, user/admin controllers và OAuth contract. | C01/C03, G01. |
| G07 | Gemini | FE-14: manager widget, settings/admin token pages, OAuth/Yomitan UI; dùng manager đã có. | C07.a. |
| C07.b | Codex | FE-17/21: pricing/install/order/wallet/payment adapters và invalidation contract. | C02/C03; giữ công thức và payload hiện tại. |
| G08 | Gemini | FE-17: catalog/detail/publish wizard UI và controllers cục bộ; page composition. | C07.b, G03; review từng catalog/detail/publish. |
| C07.c | Codex | FE-18: release pinning/update/change-request/conflict/apply và clone overlay contracts. | G08; đọc overlay cutover report trước khi sửa flow. |
| G09 | Gemini | FE-18 và phần NoteType của FE-06: library/diff/inbox UI, NoteType editor/pages/live preview dùng renderer public. | C07.c cho collaboration; C02 cho NoteType. |
| G10 | Gemini | FE-20: admin theo miền users → taxonomy/images/TTS → analytics/tickets → payments/fees; tách UI/local controller đã rõ contract. | C01/C03, G07; contracts nhạy cảm được Codex chốt trước từng miền. |
| G11 | Gemini | FE-21: profile/avatar/verification/goals/orders/wallet/payment-result UI và page composition. | C01/C03/C07.b, G08. |
| G12 | Gemini | FE-22: guide/support/onboarding/public/legal và content; giữ URLs, selectors, keys. | C03/G02, G10 phần shared ticket contracts. |
| C08 | Codex | FE-19: study open/restore → local review → commit/batch → lease → patch/lifecycle; giữ một owner orchestration. | C01/C02/C03/C04; baseline durability hoàn thành. |
| C09 | Codex | FE-23/24: nghiệm thu, xóa shim/allowlist đã hết nhiệm vụ, chốt docs/test map, build/visual/runtime/bundle/rollback. Gemini cập nhật mapping/docs của từng gói. | Mọi gói cần thiết đã được nghiệm thu. |

Thứ tự thực tế:

1. **Chuẩn bị:** G00 + C00; chỉ baseline/mapping/tooling cần thiết.
2. **Foundation:** C01 → C02; C03/G01/G02 theo file locks. Codex xử lý phần lõi, Gemini chuyển shared UI và shell khi contract sẵn sàng.
3. **Pilot:** G03. Sau pilot mới giao các gói chuyển đổi lớn; rút convention từ diff và kết quả thật.
4. **Nhân rộng:** browse, worksheet, MCP, import/audio, marketplace/collaboration, NoteType, admin/account/public. Theo gate của từng gói, không cần chờ mọi nhánh khác xong.
5. **Study và đóng migration:** C08 sau baseline và foundation/browse; C09 sau tất cả gói. C08 có thể chạy cùng gói UI khác trong worktree riêng nếu không chia sẻ file.

Không chốt số ngày trước khi pilot hoàn thành. Sau G03, Codex dùng kích thước diff, thời gian review và lỗi thực tế để chia lại các gói tiếp theo. Không dùng ngưỡng số dòng như tiêu chí nghiệm thu kiến trúc.

## 5. Quyền sửa file và cách bàn giao

**Mặc định khi cùng working tree: một người sửa code tại một thời điểm.** Codex có thể đọc/review khi Gemini đang làm, nhưng chỉ sửa diff đó sau khi Gemini bàn giao. Nếu thực hiện song song, dùng worktrees riêng từ cùng checkpoint và file ownership không chồng nhau.

Các đường dẫn điều phối do Codex giữ: `App.tsx`, `main.tsx`, `app/**`, transport/bootstrap/config nền tảng, entity contracts, study runtime/scheduler/storage, Anki worker/engine/storage, CI và modular runner. Quyền sửa một file có thể bàn giao rõ ràng cho Gemini theo gói, không tự suy ra từ quyền sửa thư mục lớn.

Gemini sửa source và target đã liệt kê trong gói. Nếu di chuyển file cần đổi caller ngoài phạm vi, Gemini liệt kê caller và patch đề xuất; Codex cấp quyền bổ sung hoặc tự tích hợp. Không để public shim kéo dài chỉ vì caller nằm ngoài phạm vi.

Mỗi gói được giao phải có:

1. ID, mục tiêu, checkpoint/working directory và đường dẫn source → target cụ thể.
2. File được sửa, file cấm sửa và owner của các caller liên quan.
3. Exports/props/callbacks/DTO/query keys cần tuân thủ; shim có task xóa.
4. Hành vi phải giữ, test/visual baseline và điều kiện nghiệm thu.
5. Báo cáo: files changed, caller imports, tests đã chạy, failures, visual evidence, risks và việc còn lại.

Trạng thái: `Planned → Ready → In progress → Review → Accepted`, hoặc `Needs revision`. Chỉ Codex đánh dấu Accepted sau khi đọc diff và tự chạy kiểm tra phù hợp. Gemini không tự nhảy sang gói tiếp theo; task tiếp theo được mở khi gate trước đã qua.

Nếu thay đổi ngoài quyền sửa, diff UI lệch baseline hoặc phát hiện contract chưa rõ, dừng phần phụ thuộc và báo Codex; vẫn hoàn thành phần độc lập đã được giao. Không tự sửa thuật toán, payload hoặc persistence format để làm test qua. Không tự commit/push/reset/deploy hay sửa dữ liệu production.

## 6. Tiêu chí nghiệm thu theo mức rủi ro

Mọi gói source: lint, typecheck, build, boundary check sau khi C00 thêm, test selection phù hợp và `git diff --check`. Chuyển tests cùng source. Không dùng `build:ci` để thay typecheck local.

| Loại thay đổi | Bằng chứng bắt buộc |
|---|---|
| Chuyển file/import thuần | Public imports resolve, lazy boundary còn nguyên, test đã chuyển vẫn được runner chọn; không thay hành vi. |
| Tách UI | Desktop/mobile, modal/loading/empty/error; giữ colors/gradients/font/padding/icons/shadows/DOM/portal/focus/keyboard/data-tour selectors. |
| Tách state/controller | Selection/filter/URL/mutation/callback/stale response và reset/unmount behavior; không nhân đôi state cùng nguồn. |
| Renderer/media | Iframe sandbox/postMessage/media proxy; front/back vẫn mounted; preview và live patch đúng. |
| Worksheet | Wizard/preview/zoom/preset; A4 portrait/landscape, pagination, QR/strokes và print output đối chiếu baseline. |
| Integration | Anki worker/chunk/retry/resume/DB keys; audio cancel/retry/upload/patch; có bằng chứng companion thật hoặc ghi rõ chưa kiểm tra. |
| Overlay/commerce/access | Source-owned và installed clone; local overrides không đổi source; amount/fee/pricing/status/redirect và role/capability giữ semantics. |
| Study | Undo/resume/offline/retry/quarantine/exit/multi-tab/lease/receipt/note batching; scheduler golden tests và persistence contracts giữ nguyên. |

Ảnh trước/sau dùng cùng viewport, fixture, fonts và animation state. Browser/DevTools dùng profile riêng, ví dụ `C:\Users\chung\.gemini\chrome-profiles\flama-frontend-migration`; không dùng profile cá nhân. Nếu chưa có môi trường hoặc dữ liệu phù hợp, ghi gate còn thiếu và không ghi visual/runtime PASS.

Các luồng auth, statistics, admin và commerce còn ít hoặc không có test colocated. Codex bổ sung kiểm tra hành vi có ý nghĩa tại seam thay đổi hoặc smoke có bằng chứng; không tạo tests chỉ kiểm tra import/tên component cho thao tác chuyển file thuần.

Lệnh từ repo root (PowerShell, environment đã xác minh):

```powershell
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
& .\.venv\Scripts\python.exe scripts/run_tests.py --list-modules
& .\.venv\Scripts\python.exe scripts/run_tests.py --file frontend/src/features/dashboard/pages/DashboardPage.tsx --frontend-only
& .\.venv\Scripts\python.exe scripts/run_tests.py --module browse --frontend-only
& .\.venv\Scripts\python.exe scripts/run_tests.py --module study --frontend-only
git diff --check
```

Trong workspace nhiều thay đổi, ưu tiên `--file` của task; `--changed --frontend-only` có thể kéo cả tests do công việc backend khác chọn. Tên module dashboard thực tế là `decks`, statistics là `analytics`, collaboration là `deck_collaboration`. `npm run test:changed` chưa có trong package hiện tại.

Runner hiện tự khám phá tests trong feature và fallback toàn frontend cho source chưa map. Khi chuyển sang pages/widgets/entities phải cập nhật mapping/discovery để giữ tính chọn lọc; không kết luận tests mới bị bỏ sót chỉ từ số lượng catalog tĩnh. Full suite dùng ở CI/pre-release theo AGENTS.md.

Rollback phần source theo từng gói đã tích hợp, giữ nguyên thay đổi của công việc khác. Không xóa IndexedDB/localStorage để xử lý lỗi migration. Các key/version hiện tại như `flama-study` v2 và `FlamaAnkiSyncDB_v2` v1 được giữ; chuyển vị trí source không phải migration dữ liệu browser.

## 7. Prompt đầu tiên để người dùng giao Gemini

G00 chỉ chuẩn bị bàn giao; gói source đầu tiên của Gemini là G01 khi foundation và quyền sửa file đã sẵn sàng.

```text
Bạn là Gemini, implementation worker chính cho migration cấu trúc frontend Flama.
Workspace: D:\Project\nihongo.
Codex điều phối, chốt contracts, xử lý phần khó và nghiệm thu diff.

Chỉ thực hiện G00 trong:
docs/plans/proposals/FLAMA_FRONTEND_CODEX_GEMINI_EXECUTION_PLAN_2026-10-04.md

Đọc AGENTS.md, skills/flama-frontend-architecture/SKILL.md,
skills/docs-architect/SKILL.md và proposal frontend ngày 03/10.
Đối chiếu code hiện tại; hướng dẫn cũ không thay thế hành vi code.

Mục tiêu G00:
1. Ghi git status/checkpoint và thay đổi có sẵn; không sửa các thay đổi đó.
2. Kiểm kê đủ 22 feature cùng app/layout/components/lib/shared/public pages.
3. Đề xuất mapping source -> target, public exports, caller imports và tests.
4. Ghi routes/aliases/access/layout và query/storage/worker contracts cần giữ.
5. Ghi test/visual baseline có sẵn và phần còn thiếu; không ghi PASS khi chưa chạy.
6. Đề xuất phạm vi G01 nhỏ, gồm file được sửa và caller ngoài phạm vi.

Chỉ được tạo/cập nhật báo cáo:
docs/task/frontend-migration/G00_BASELINE_AND_MAPPING.md
Trong G00 không sửa source, tests, package/config, CI hoặc test runner;
không khởi động backend làm thay đổi DB, không đổi storage/browser data.
Không commit/push/reset/deploy, không mở profile Chrome cá nhân.

Cuối task báo cáo artifact, phát hiện, gate còn thiếu và đề xuất file list G01.
Bàn giao Codex review; chưa tự bắt đầu G01 hoặc task source khác.
```

Nếu người dùng giao Gemini qua CLI ở bước sau, Codex áp dụng task contract/file ownership/diff review của [antigravity worker orchestration](../../../skills/antigravity-cli/references/worker-orchestration.md). Kế hoạch này chưa chạy CLI, kiểm tra tài khoản hoặc đổi tài khoản.

## 8. Điều kiện mở gói chuyển đổi đầu tiên

- Người dùng chấp nhận cách chia việc và cho Gemini bắt đầu G00.
- G00 bàn giao mapping; Codex hoàn thành C00 và mở contracts/file locks cần cho G01.
- Baseline của slice đủ để so sánh; không lấy build PASS thay cho visual/runtime QA.
- Các file CI/test runner đang thay đổi được phối hợp trước khi sửa tooling.

Sau đó Codex giao G01 bằng file list cụ thể, review kết quả, rồi tiếp tục chuỗi task trên trong phạm vi đã duyệt.
