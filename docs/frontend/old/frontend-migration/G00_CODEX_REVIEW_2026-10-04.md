# Codex review kế hoạch G00 của Gemini

- Ngày: 2026-10-04, Asia/Tokyo.
- Tài liệu review: [G00_BASELINE_AND_MAPPING.md](G00_BASELINE_AND_MAPPING.md).
- SHA-256 của bản đã đọc: `48b044e2ce2200f485519604ed9467ae54e980072ef30e4b6174b98470da68e2`.
- Checkout đối chiếu: `docs/p10-09-postflight`, HEAD `7972025edaad284ed89a764ae2bc1959bf80a9f8`.
- Kết luận: **Needs revision. Chưa nghiệm thu G00 làm contract triển khai; chưa mở G01.**
- Phạm vi lần này: review tài liệu, kiểm tra code và tests liên quan; không sửa source hoặc bản G00 của Gemini.

## Những phần có thể giữ

- Inventory 22 feature, 331 source TS/TSX và 82 tệp test phù hợp kiểm kê hiện tại.
- Các hotspot bootstrap, browse, renderer, MCP, Anki/audio và worksheet đã được nhận diện đúng.
- Danh sách đường dẫn router bao quát đủ 95 path/index entries, gồm 77 direct routes và 18 redirects. Con số 52 direct routes ở phần dẫn nhập cần sửa.
- Hướng chia việc Gemini chuyển UI, Codex giữ các contract phức tạp phù hợp kế hoạch phối hợp.
- Tests hiện tại xác nhận baseline cho shared UI/utilities và template immutability; chưa xác nhận kế hoạch mới giữ được các hành vi đó.

## Findings cần sửa trước khi dùng kế hoạch

### R1 — P1: Adapter template làm thay đổi contract phiên học

**Vị trí G00:** mục 3.4.3, đặc biệt dòng 464–473; mục 4.4.D.

Kế hoạch yêu cầu cập nhật `snapshot.templates[templateKey]` và phát `TEMPLATE_UPDATED` cho phiên đang mở. Code hiện tại cố ý không làm việc này:

- [`sessionStore.ts`](../../../frontend/src/features/study/session/sessionStore.ts), hàm `updateTemplateInSessions` tại dòng 616: no-op, template source/version/binding bất biến trong active lease.
- [`useStudySession.ts`](../../../frontend/src/features/study/hooks/useStudySession.ts), `updateTemplateContent` tại dòng 1243: cũng no-op.
- [`sessionStore.test.ts`](../../../frontend/src/features/study/session/sessionStore.test.ts), test tại dòng 127: khóa hành vi content được patch nhưng template giữ nguyên sau authoring update.

Nếu triển khai theo G00, template của snapshot đang học bị đổi ngoài quy trình mở phiên mới, vượt phạm vi migration cấu trúc và phá contract đã được test.

**Yêu cầu sửa:** phân biệt card-content patch và template authoring. Giữ nguyên patch field/media hiện có; template thay đổi chỉ xuất hiện trong phiên mở mới. Adapter ban đầu nên bọc implementation hiện tại, không viết lại thuật toán lưu snapshot hoặc thêm hành vi template broadcast. Giữ cả memory fallback và các guard hiện có. Các hàm/import chưa tồn tại trong ví dụ adapter phải được bỏ hoặc ghi rõ là pseudocode cần Codex thiết kế, không trình bày như code sẵn để port.

### R2 — P1: Ví dụ bootstrap sai endpoint, helper và response mapping

**Vị trí G00:** dòng 353, `apiJson('/api/bootstrap')`.

[`app/api.ts`](../../../frontend/src/app/api.ts), dòng 233–235, thực tế đọc `${API_BASE}/session` bằng `apiRequest<SessionResponse>` rồi chạy `toBootstrap`. [`client.ts`](../../../frontend/src/shared/api/client.ts), dòng 241, định nghĩa `apiJson(url, method, body, init)` cho mutation; không có biến thể GET một tham số.

Copy ví dụ trong G00 sẽ lỗi typecheck và gọi khác contract backend. Trả raw session cũng không tương đương `FrontendBootstrap`: mapping hiện tại bổ sung links, defaults và CSRF state.

**Yêu cầu sửa:** contract mới giữ GET `${API_BASE_URL}/session`, cấu hình backend URL, credentials/CSRF handling và mapping `SessionResponse → FrontendBootstrap`. Thay đổi query key/invalidation thuộc C01, tách riêng khỏi đổi transport; không đổi endpoint theo tên mới của module.

### R3 — P1: Một số mapping và cách ghép module vẫn import ngược tầng

**Vị trí G00:** dòng 270–281, 338, 347, 475–479; whitelist Brand tại dòng 1049.

Ba hướng trong kế hoạch mâu thuẫn quy tắc sáu tầng:

1. Dòng 347 để `features/settings/components/McpTokensTab.tsx` import widget manager. Feature không được import widget; phải chuyển phần composition lên page/widget, còn controller ở feature.
2. Dòng 475–479 để browse/audio feature import public `features/study`, rồi khẳng định đã hết vi phạm FSD. Public export giải quyết deep import, vẫn còn feature-to-feature dependency. Phương án đặt study patch vào `entities/session` cũng không hợp lệ nếu entity phải gọi study internals.
3. Dòng 338 đặt print engine vào `shared/lib/print`. [`printEngine.tsx`](../../../frontend/src/features/worksheets/utils/printEngine.tsx) hiện import `WorksheetPageRenderer` và worksheet DTO; chuyển nguyên khối xuống shared tạo shared → feature/widget dependency.

Ngoài ra, [`Brand.tsx`](../../../frontend/src/shared/components/Brand.tsx) tự gọi bootstrap; [`useTaxonomySchema.ts`](../../../frontend/src/features/marketplace/hooks/useTaxonomySchema.ts) phụ thuộc app API và publish constants. Hai module này cần tách dependency/composition trước khi khẳng định đã nằm đúng tầng sau một lần chuyển file.

**Yêu cầu sửa:** page/widget điều phối qua callback hoặc adapter headless tường minh, hoạt động cả khi StudyPage không mount; giữ study runtime/storage thuộc study. Print pipeline thuộc worksheet domain, chỉ helper in trung lập thật sự mới xuống shared. Brand có thể tách phần trình bày nhận props khỏi phần biết session. Nêu rõ allowlist tạm, owner và gói xóa nếu chuyển từng bước.

Với numbering app=1…shared=6, công thức `N → < N` cũng ngược ví dụ. Sửa thành hướng đúng hoặc chỉ dùng ma trận dependency, tránh tạo boundary checker theo bất đẳng thức sai. Không bắt buộc public root barrel cho mọi shared primitive nếu làm mất lazy boundary; exports phải tường minh.

### R4 — P1: Phạm vi G01 tự mâu thuẫn, thiếu quyền sửa các file cần thiết

**Vị trí G00:** mục 6.2–6.4, dòng 1039–1144.

- Whitelist cho chuyển `ankiHtmlSanitizer` và yêu cầu shim tại file cũ; blacklist lại cấm toàn bộ `frontend/src/lib/anki*`.
- Whitelist chỉ ghi đường dẫn đích cho `cn`, imageCompression và useMobile, nhưng bắt buộc sửa file cũ để tạo shim. File cũ chưa được cấp quyền rõ ràng, trong khi mọi sửa ngoài whitelist bị từ chối.
- Đích primitives còn là `shared/ui/shadcn/` **hoặc** `components/ui/`; chưa chốt một mapping.
- Không cấp quyền/có task phối hợp cho `frontend/components.json`. File này vẫn trỏ generator vào `@/components/ui`, `@/lib/utils`, `@/hooks`; chuyển implementation mà giữ cấu hình sẽ để lần sinh component tiếp theo ghi vào thư mục shim.
- Shim dùng `export *`, không có exports inventory và owner/gói xóa tương ứng, trái convention exports tường minh trong kế hoạch điều phối.

**Yêu cầu sửa:** liệt kê cụ thể source → target → shim cùng tests và người được sửa. Chốt một đích, cấp quyền cấu hình shadcn hoặc giao Codex cập nhật trong cùng checkpoint. Giữ Anki sanitizer trong phạm vi C06.a; nếu muốn hạ helper riêng xuống shared phải có quyết định tách trách nhiệm. Không mở cả Brand, domain DTO và shell trong G01.

### R5 — P1: Baseline wire/cache mô tả sai dữ liệu phải giữ

**Vị trí G00:** dòng 748, 764, 913–928.

- Payload sync ghi `cardId: number`, `noteId: number | null`, media dạng `Record<string, string>`. [`sessionStore.ts`](../../../frontend/src/features/study/session/sessionStore.ts), dòng 471–474, và hook receiver dùng ID **string** cùng `StudyMediaArtifact[]`.
- Browse list query key bỏ `sortDir`, trong khi [`useBrowseState.ts`](../../../frontend/src/features/browse/hooks/useBrowseState.ts), dòng 364, đưa cả `sortBy` và `sortDir` vào key. Dùng bảng rút gọn làm query-key contract mới có thể khiến hai thứ tự sort dùng chung cache.
- `['shared-note-types', query, sort, page]` không phải key list hiện tại; cả decks/note-types catalog dùng key `['marketplace', mode, ...]` trong `MarketplacePages.tsx`.
- Phần TEMPLATE_UPDATED cần phân biệt listener tương thích còn tồn tại với sender hiện tại đang no-op; không mô tả listener như bằng chứng template authoring đang patch active session.

**Yêu cầu sửa:** lấy chữ ký/payload/key đầy đủ trực tiếp từ source, dẫn file/function. Phân biệt baseline hiện hành với contract mục tiêu và ngoại lệ tạm; không ghi các ví dụ rút gọn là danh mục đầy đủ 100%.

## Các điểm cần làm rõ trong cùng bản sửa

### R6 — P2: Mapping chưa đủ để chốt C00 và có owner/gói chưa đúng

Mục 3.2 có số tổng 414, mục 3.3 có mapping theo feature; artifact chưa cung cấp catalog source → target cụ thể cho toàn bộ số file được tuyên bố. Với module cần extraction, cần ghi nhiều phần đích thay vì ép 1-to-1. Không lấy số tổng bằng nhau làm bằng chứng không bỏ sót source/tests.

Public API examples dùng exports chưa có như `renderCardHtml`; renderer hiện export `renderStudySide`. Một số props chưa được export. Có thể đề xuất API mới nhưng phải đánh dấu planned, owner và migration caller, không coi là re-export cơ học.

`entities/support-ticket` gán C05/G05 ở dòng 554, nhưng hai gói đó thuộc worksheet. Sửa owner theo admin/support (G10/G12 và contract Codex trước đó). Mapping auth/account/orders/profile/wallet khác tên slice trong đề xuất điều phối có thể được bàn bạc ở C00; ghi là đề xuất chưa chốt.

### R7 — P2: Tiêu chí visual chưa có bằng chứng và test policy quá rộng

Dòng 1013 đề xuất DOM snapshot/bounding box để đảm bảo Zero Visual Regression. Hai loại kiểm tra này không chứng minh giữ colors/gradient/fonts/shadows; cần ảnh trước/sau với viewport/fixture/fonts/animation state cố định, focus/keyboard/portal checks và profile browser riêng.

G00 phải ghi rõ baseline browser/visual còn thiếu, thay vì chỉ đặt yêu cầu cho tương lai. Không bắt buộc tạo characterization suite cho mọi thao tác chuyển file thuần trong cả 9 feature; chọn seam có thay đổi trách nhiệm/vòng đời hoặc hành vi chưa được bảo vệ. Điều này giữ phù hợp test policy của repo.

### R8 — P2: Trạng thái nghiệm thu và checkpoint cần phản ánh đúng thời điểm

Dòng 17 tự ghi đã nghiệm thu, trong khi quy trình phân công chỉ Codex đóng review. Chuyển sang `Submitted for Codex review / Needs revision`, cập nhật lại khi review qua.

Nhánh/HEAD hiện tại đã khác snapshot P10 cũ; giữ snapshot cũ như lịch sử, bổ sung checkpoint hiện hành trước mỗi gói. Không kết luận rủi ro xung đột triệt tiêu 100% chỉ vì working tree đang sạch.

Sửa các số liệu/nhãn dễ gây hiểu sai: 77 direct routes thay 52; router admin có RequireAuth ở client, backend mới enforce admin role (không tự thêm guard như một phần refactor); có 30 shadcn files thay 29; blacklist ví dụ không có analytics/landing/notifications và phải bao quát orders/profile/wallet. `sidebar_state` cookie cũng là state contract của sidebar nếu G01 chuyển primitive này.

## Hướng sửa G01 để có thể giao Gemini

1. Sau khi C00 chốt boundary/file locks, mở **G01.a**: utilities trung lập (`cn`, useMobile, imageCompression) với source/target/tests/shim tường minh; không chuyển Anki/domain/runtime.
2. **G01.b**: chuyển 30 primitives theo một mapping cố định, sửa imports nội bộ trong target và cấu hình shadcn, giữ JSX/classes/focus/portal behavior. Caller feature chưa chuyển được dùng shim có owner/gói xóa.
3. Shared components đã ở đúng nơi không cần đổi chỉ để tạo diff. Brand, flashcard form/domain DTO và các dependency có bootstrap để owner tương ứng xử lý.
4. Mỗi gói dùng modular test selection gồm primitive tests và consumers thực sự bị ảnh hưởng; có visual baseline trước khi tách UI. Codex kiểm tra lại boundary/lazy imports trước khi Accepted.

Đây là đề xuất chia nhỏ để sửa bản kế hoạch; chưa cấp quyền sửa source và chưa khởi chạy worker.

## Kiểm tra đã thực hiện trong lần review

| Kiểm tra | Kết quả |
|---|---|
| Static inspection + TypeScript AST đối chiếu routes | 95 path/index entries, 77 direct, 18 redirects; không thiếu path trong bảng G00. |
| `scripts/run_tests.py --file` cho 9 shared UI test files, `--frontend-only` | PASS: 43 tests. |
| Runner cho imageCompression/ankiHtmlSanitizer test files | PASS: 10 tests. |
| Runner cho `features/study/session/sessionStore.test.ts` | PASS: 3 tests, gồm template immutability contract. |
| Working tree frontend | Không có source/config thay đổi. |
| Browser/ảnh baseline và implementation của kế hoạch mới | Chưa kiểm tra trong lần review. |

Tổng: **12 tệp test, 56 tests PASS**. Không chạy lại full suite/lint/build vì source không thay đổi; baseline lint/typecheck/build trong G00 và kế hoạch trước không được nâng thành bằng chứng cho migration chưa triển khai.

Gemini cần sửa **R1–R5** và làm rõ **R6–R8** ngay trong G00, chỉ cập nhật tài liệu. Sau bản sửa, Codex review lại rồi chốt C00/phạm vi G01; không tự bắt đầu chuyển source từ bản hiện tại.
