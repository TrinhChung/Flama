# KẾ HOẠCH ĐẶC TẢ KỸ THUẬT DI TRÚ FRONTEND FLAMA THEO ĐỊNH HƯỚNG TẬP TRUNG CAO ROI
## (FLAMA FRONTEND HIGH-ROI MASTER ARCHITECTURAL SPECIFICATION PLAN)

- **Tệp tài liệu**: `docs/task/frontend-migration/FLAMA_FRONTEND_HIGH_ROI_SPECIFICATION_PLAN_2026-10-05.md`
- **Phiên bản**: 3.0.0 (High-ROI Architecture Final Draft)
- **Ngày lập**: 2026-10-05 (Asia/Tokyo)
- **Tác giả**: Master Frontend Specification Architect (`worker_spec_writer`)
- **Căn cứ pháp lý & kỹ thuật**:
  - `docs/plans/proposals/FLAMA_FRONTEND_CODEX_GEMINI_EXECUTION_PLAN_2026-10-04.md`
  - `docs/plans/proposals/FLAMA_FRONTEND_STRUCTURE_MIGRATION_PLAN_2026-10-03.md`
  - `docs/task/frontend-migration/G00_CODEX_REVIEW_2026-10-04.md`
  - `docs/task/frontend-migration/FLASHCARD_EXTRACTION_CODEX_REVIEW_2026-10-05.md`
  - Báo cáo khảo sát thực nghiệm: `explorer_survey_1`, `explorer_survey_2`, `explorer_survey_3`
- **Trạng thái**: **HOÀN THIỆN ĐẶC TẢ CHI TIẾT — SẴN SÀNG TRÌNH CODEX THẨM ĐỊNH & PHÊ DUYỆT CHÍNH THỨC (READY FOR CODEX ARCHITECTURAL APPROVAL)**

---

## MỤC LỤC CHI TIẾT

1. [CHƯƠNG 1: TỔNG QUAN ĐIỀU HÀNH & CHIẾN LƯỢC TẬP TRUNG ROI](#chương-1-tổng-quan-điều-hành--chiến-lược-tập-trung-roi)
   - 1.1 Bối cảnh & Thách thức Kiến trúc Monolith
   - 1.2 Chiến lược Tập trung Cao ROI: 84.6% Đóng băng & 15.4% Phẫu thuật Trọng điểm
   - 1.3 Lộ trình Phụ thuộc Tuần tự (Milestone DAG & Phân kỳ Triển khai)
   - 1.4 Ma trận Kiến trúc 6 Tầng FSD Mục tiêu
2. [CHƯƠNG 2: R1 — NỀN MÓNG & GIẢI QUYẾT TRIỆT ĐỂ GATE C00](#chương-2-r1--nền-móng--giải-quyết-triệt-để-gate-c00)
   - 2.1 Bảng Tổng hợp Giải quyết Dứt điểm 8 Findings (R1–R8) của Codex
   - 2.2 Gói C01: Tách Biệt Transport Mạng & Session Bootstrap Độc lập
   - 2.3 Gói G01: Quy chuẩn & Tái tổ chức UI Primitives (30 Shadcn + 8 Flama UI)
3. [CHƯƠNG 3: R2 — ĐIỂM NÓNG #1: PHẪU THUẬT BROWSE WORKSPACE & NOTE EDITOR (FE-11)](#chương-3-r2--điểm-nóng-1-phẫu-thuật-browse-workspace--note-editor-fe-11)
   - 3.1 Giải phẫu Chi tiết God Hook `useBrowseState.ts` (1,051 LOC, 48 useState)
   - 3.2 Cơ chế Re-render Thrashing Cascade Làm Giảm Trải nghiệm Người dùng
   - 3.3 Thiết kế Phân rã 3 Controllers Độc lập + 1 Modal Controller + 1 Facade Tương thích
   - 3.4 Bóc tách Hoàn toàn Browse Khỏi Study Session Store & Di chuyển Card DTOs
   - 3.5 Tái cấu trúc Giao diện UI Browse & Tích hợp Primitive `CardFieldsForm`
   - 3.6 Ngân sách File Size (< 400 LOC) & Checklist Zero Visual Regression
4. [CHƯƠNG 4: R3 — ĐIỂM NÓNG #2: PHẪU THUẬT WORKSHEETS STUDIO & PRINT ENGINE (FE-12, FE-13)](#chương-4-r3--điểm-nóng-2-phẫu-thuật-worksheets-studio--print-engine-fe-12-fe-13)
   - 4.1 Giải phẫu Monolith Khổng lồ `DeckWorksheetModal.tsx` (4,388 LOC) & `WorksheetPageRenderer.tsx` (1,719 LOC)
   - 4.2 Phân rã 5 Bước Studio Wizard Thành Các Component Độc lập Dưới 300 LOC
   - 4.3 Cô lập Hình học Tọa độ Lưới A4 Vào Pure Math Module `gridGeometry.ts` (< 250 LOC)
   - 4.4 Đóng gói Công cụ In Ấn `printEngine.tsx` (< 150 LOC) & Bảo toàn Latch `@media print`
   - 4.5 Chuẩn hóa Các Section Renderers Chuyên biệt
   - 4.6 Bảo đảm Zero Visual Regression Cho Bản In PDF & Xuất Giấy
5. [CHƯƠNG 5: R4 — BẢO VỆ TÍNH BỀN VỮNG PHIÊN HỌC STUDY & CÁCH LY SRS ENGINE (FE-19)](#chương-5-r4--bảo-vệ-tính-bền-vững-phiên-học-study--cách-ly-srs-engine-fe-19)
   - 5.1 Kế thừa Lát cắt `entities/flashcard` và Cổng Cập nhật Nội dung (C02)
   - 5.2 Hợp đồng Bất biến Mẫu Thẻ (Template Immutability Contract in Active Lease)
   - 5.3 Phân rã `StudyPage.tsx` (< 200 LOC) & Các Interaction Hooks Chuyên biệt
   - 5.4 Cách ly Tầng Quản lý Phiên Bền vững (`useStudyCommitAuthority` & `useStudySessionStore`)
6. [CHƯƠNG 6: R5 — CHÍNH SÁCH "ZERO-TOUCH / GIỮ NGUYÊN HIỆN TRẠNG" (>= 70% BẢO TOÀN)](#chương-6-r5--chính-sách-zero-touch--giữ-nguyên-hiện-trạng--70-bảo-toàn)
   - 6.1 Chứng minh Định lượng Toàn vẹn (Proof of 84.6% Frozen Files)
   - 6.2 Danh mục Chi tiết 20 Miền Nghiệp vụ Đóng băng Tuyệt đối
   - 6.3 Chính sách Quản lý Compatibility Shims & Vòng đời Tiêu hủy
7. [CHƯƠNG 7: R6 — KHUNG KIỂM THỬ TỰ ĐỘNG, TIÊU CHÍ NGHIỆM THU & PHÂN ĐỊNH TRÁCH NHIỆM](#chương-7-r6--khung-kiểm-thử-tự-động-tiêu-chí-nghiệm-thu--phân-định-trách-nhiệm)
   - 7.1 Bộ 5 Lệnh Kiểm tra Tự động Bắt buộc (Automated Quality Checklist)
   - 7.2 Script Kiểm tra Ranh giới AST TypeScript (Production AST Boundary Checker)
   - 7.3 Ma trận Phân định Quyền Sở hữu Mã nguồn (Codex vs Gemini Code Ownership)
   - 7.4 Bảng Điểm Tiêu chí Nghiệm thu Tổng hợp (Acceptance Criteria Scorecard)

---

## CHƯƠNG 1: TỔNG QUAN ĐIỀU HÀNH & CHIẾN LƯỢC TẬP TRUNG ROI

### 1.1 Bối cảnh & Thách thức Kiến trúc Monolith
Ứng dụng web Flama React SPA hiện tại (`frontend/src/`) đã xây dựng được một nền tảng công nghệ mạnh mẽ dựa trên React 19, TypeScript, Vite, TanStack Query, TailwindCSS và hệ thống 22 thư mục tính năng (`features/`). Tuy nhiên, trải qua quá trình phát triển nhanh, một số tệp lõi đã phình to vượt tầm kiểm soát, hình thành các "God Components" và "God Hooks" chứa đựng hàng nghìn dòng mã, đan xen phức tạp giữa UI presentation, client state, business logic, network transport và persistence.

Hai điểm nghẽn nghiêm trọng nhất về mặt duy trì mã nguồn và trải nghiệm người dùng hiện nay là:
1. **Browse Workspace Monolith** (`features/browse/hooks/useBrowseState.ts`): Tập trung **1,051 LOC, 48 `useState`**, 7 `useRef`, 7 `useEffect`, 8 `useQuery`, 5 `useMutation`. Mỗi thao tác gõ bàn phím tìm kiếm hay chỉnh sửa một trường dữ liệu đều kích hoạt toàn bộ hook chạy lại, kéo theo chu kỳ re-render toàn diện của cả 3 pane (Deck Tree, Card Table, Note Editor).
2. **Worksheets Studio & Print Monolith** (`features/worksheets/components/DeckWorksheetModal.tsx` với **4,388 LOC** và `WorksheetPageRenderer.tsx` với **1,719 LOC**): Gom cụm toàn bộ một trình soạn thảo in ấn 4 giai đoạn, hàng chục controls cấu hình, mã SVG parsing, thuật toán hình học A4 và CSS print injection vào chung một component khổng lồ.

Bên cạnh đó, phiên học Study (`features/study/`) đòi hỏi tính bất biến khắt khe về mặt thuật toán SRS và đồng bộ hóa ngoại tuyến (offline durability) nhưng đang bị ghép nối lỏng lẻo với các dialog chỉnh sửa thẻ và trình preview.

### 1.2 Chiến lược Tập trung Cao ROI: 84.6% Đóng băng & 15.4% Phẫu thuật Trọng điểm
Thay vì tiến hành một cuộc đại phẫu di chuyển cơ học dàn trải trên toàn bộ 344 tệp mã nguồn (dễ dẫn đến xung đột merge vô tận, phát sinh regressions và làm kiệt quệ tài nguyên đội ngũ), bản kế hoạch này áp dụng chiến lược **High-ROI Concentration (Tập trung Cao ROI)**:

$$\text{ROI} = \frac{\Delta \text{Maintainability} + \Delta \text{Performance} + \Delta \text{Stability}}{\text{Refactoring Blast Radius} \times \text{Risk}}$$

- **Nhóm Đóng băng Tuyệt đối (Zero-Touch Policy - 84.6% Source Files)**: Đóng băng hoàn toàn **291 / 344 tệp source**. Các module tĩnh, đã chạy ổn định hoặc ít rủi ro biến động nghiệp vụ (`guide`, `onboarding`, `support`, `legal`, `auth`, `oauth`, `orders`, `wallet`, `statistics`, `library`, `profile`, `deck-collaboration`, `mcp`, `settings`, `audio`, `import`, `note-types`, `admin`, `marketplace`, `dashboard`) sẽ được **GIỮ NGUYÊN HIỆN TRẠNG 100%**. Mọi liên kết từ bên ngoài sẽ được phân giải thông qua các tệp re-export shims tương thích ngược mà không chạm vào một dòng mã nguồn nào bên trong các module này.
- **Nhóm Phẫu thuật Trọng điểm (High-ROI Hotspots - 15.4% Source Files)**: Dồn toàn bộ năng lực kiến trúc và kiểm thử vào **53 tệp source** thiết yếu, bao gồm:
  1. **Foundation C01 / G01**: Decouple network transport, session bootstrap và quy chuẩn UI primitives.
  2. **Hotspot #1 (Browse Workspace - FE-11)**: Phân rã `useBrowseState.ts` thành 3 controllers chuyên trách + 1 modal controller + 1 facade dưới 250 LOC.
  3. **Hotspot #2 (Worksheets Studio & Print Engine - FE-12, FE-13)**: Phân rã `DeckWorksheetModal.tsx` và `WorksheetPageRenderer.tsx` thành 5 wizard step components (< 300 LOC), trích xuất module toán học `gridGeometry.ts` (< 250 LOC) và công cụ in `printEngine.tsx` (< 150 LOC).
  4. **Study Session Durability (FE-19)**: Khóa chặt hợp đồng Template Immutability và cách ly hoàn toàn UI của `StudyPage.tsx` khỏi SRS state machine và commit authority.

### 1.3 Lộ trình Phụ thuộc Tuần tự (Milestone DAG & Phân kỳ Triển khai)

Lộ trình triển khai được thiết kế theo đồ thị có hướng không chu trình (DAG), đảm bảo mỗi bước đi đều có hợp đồng (Contract) vững chắc làm tiền đề:

```
┌─────────────────────────────────────────────────────────────┐
│                 Gate C00 Resolution (Specs)                 │
│  Giải quyết dứt điểm 8 lưu ý Codex R1–R8 trong G00 Mapping  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
┌───────────────────────────────┐ ┌───────────────────────────┐
│ Gói C01: Transport & Session  │ │ Gói G01: UI Primitives    │
│ • shared/api/client.ts        │ │ • shared/ui/shadcn/ (30)  │
│ • shared/api/bootstrap.ts     │ │ • shared/ui/ (8 Flama)    │
│ • bootstrapQueryKey unify     │ │ • components.json alias   │
└───────────────┬───────────────┘ └─────────────┬─────────────┘
                │                               │
                └──────────────┬────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│       Gói C02: Flashcard Entity & Renderer Boundary         │
│  (Đã hoàn tất nghiệm thu bởi Codex với 69 tests passed)     │
│  • entities/flashcard (model, ui, lib)                      │
│  • Headless port: cardContentUpdates.ts                     │
│  • App composition: studyContentSync.ts                     │
└──────────────────────────────┬──────────────────────────────┘
                               │
        ┌──────────────────────┴──────────────────────┐
        ▼                                             ▼
┌───────────────────────────────┐ ┌───────────────────────────┐
│ Hotspot #1: Browse Workspace  │ │ Hotspot #2: Worksheets    │
│ • useBrowseFilters (<250 LOC) │ │ • 5 Wizard Steps (<300)   │
│ • useBrowseSelection (<120)   │ │ • useWorksheetStudio      │
│ • useBrowseCardEditor (<220)  │ │ • gridGeometry.ts (pure)  │
│ • useBrowseTtsModal (<180)    │ │ • printEngine.tsx (@media)│
│ • useBrowseState Facade (<120)│ │ • Modular Section Render  │
└───────────────┬───────────────┘ └─────────────┬─────────────┘
                │                               │
                └──────────────┬────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│    Gói FE-19: Study Session Durability & SRS Isolation      │
│ • Khóa chặt Template Immutability (no-op authoring update)  │
│ • Decouple StudyPage.tsx (<200 LOC) khỏi durability hooks   │
│ • Tách useStudyCommitAuthority & useStudySessionStore       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│       Verification & AST Boundary Latch Enforcement         │
│ • Typecheck (0 error) | Lint (0 error) | Build:CI (Pass)    │
│ • Modular Test Suite (Pass 100%)                            │
│ • Production TypeScript AST Boundary Script Verify          │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 Ma trận Kiến trúc 6 Tầng FSD Mục tiêu
Kiến trúc tuân thủ nghiêm ngặt mô hình Feature-Sliced Design (FSD) 6 tầng với nguyên tắc: **Tầng trên được phép tiêu thụ tầng dưới; tuyệt đối không import ngược tầng và không import internals của module cùng tầng**.

| Tầng (Layer) | Trách nhiệm Kiến trúc | Thành phần Tiêu biểu | Quy tắc Ranh giới (Boundary Rules) |
|---|---|---|---|
| **1. `app/`** | Khởi tạo ứng dụng, router, providers, global styles, dynamic composition adapters. | `App.tsx`, `providers/`, `router/`, `studyContentSync.ts`. | Có quyền import tất cả các tầng dưới. Không tầng nào được phép import `app/`. |
| **2. `pages/`** | Composition các màn hình (route views) từ widgets và features. Không chứa logic nghiệp vụ nặng. | `BrowsePage.tsx`, `StudyPage.tsx`, `WorksheetsPage.tsx`. | Chỉ được import `widgets/`, `features/`, `entities/`, `shared/`. |
| **3. `widgets/`** | Ghép nối các khối giao diện phức hợp đa tính năng (workspace panes, complex shells). | `BrowseWorkspace.tsx`, `StudyWorkspace.tsx`, `WorksheetStudio.tsx`. | Chỉ được import `features/`, `entities/`, `shared/`. Không import lẫn nhau. |
| **4. `features/`** | Các tương tác nghiệp vụ người dùng cụ thể (controllers, action modals, wizards). | `browse/`, `worksheets/`, `study/`, `import/`, `mcp/`. | Chỉ được import `entities/`, `shared/`. Không import chéo giữa các features. Giao tiếp qua headless ports tại `entities` hoặc events. |
| **5. `entities/`** | Mô hình dữ liệu nghiệp vụ lõi (domain DTOs, schemas, renderers, entity-level queries). | `entities/flashcard/`, `entities/session/`, `entities/deck/`, `entities/user/`. | Chỉ được import `shared/`. Đóng gói public API qua `index.ts`. |
| **6. `shared/`** | Các tiện ích độc lập nghiệp vụ, UI primitives, network transport trung lập, icons. | `shared/ui/shadcn/`, `shared/ui/`, `shared/api/client.ts`, `shared/lib/utils.ts`. | Tầng cơ sở. **Tuyệt đối không import bất kỳ tầng nào phía trên**. Không phụ thuộc domain nghiệp vụ. |

---

## CHƯƠNG 2: R1 — NỀN MÓNG & GIẢI QUYẾT TRIỆT ĐỂ GATE C00

### 2.1 Bảng Tổng hợp Giải quyết Dứt điểm 8 Findings (R1–R8) của Codex
Tại báo cáo thẩm định `G00_CODEX_REVIEW_2026-10-04.md`, Codex đã chỉ ra 8 điểm mâu thuẫn và rủi ro (R1–R8) khiến Gate C00 chưa được nghiệm thu. Dưới đây là phương án giải quyết dứt điểm 100% các vấn đề:

| Finding | Mức độ | Bản chất Vấn đề Trong Báo cáo Cũ | Phương án Khắc phục Chuẩn mực Kiến trúc |
|---|---|---|---|
| **R1** | **P1** | Đề xuất cập nhật `snapshot.templates` và emit `TEMPLATE_UPDATED` trong active study lease, vi phạm contract bất biến phiên học đã test tại `sessionStore.test.ts:127`. | **Khóa chặt Template Immutability**: Phân biệt rạch ròi giữa card-content patch (`updateCardFieldValuesInSessions` cập nhật fields/media ngay lập tức) và template authoring (`updateTemplateInSessions` là no-op trong active lease). Template mới chỉ xuất hiện khi mở phiên mới. Bảo vệ tính toàn vẹn của cryptographic snapshot hash. |
| **R2** | **P1** | Đưa ví dụ `apiJson('/api/bootstrap')` sai backend endpoint (thực tế là `GET /session`) và gọi sai helper (`apiJson` chỉ dùng cho mutations). | **Chuẩn hóa Session Endpoint & Fetcher**: Dùng đúng `apiRequest<SessionResponse>(`${API_BASE_URL}/session`, { includeTimezone: false })`. Giữ nguyên logic map `toBootstrap()` sinh `FrontendBootstrap`. Thống nhất một query key duy nhất `bootstrapQueryKey = ['frontend', 'bootstrap'] as const`. |
| **R3** | **P1** | Vi phạm phân tầng FSD: `McpTokensTab` import widget; `browse`/`audio` import `features/study`; `printEngine` bị hạ xuống `shared/` dù import DTO worksheets; công thức phân tầng bị ngược $N \to < N$. | **Chuẩn hóa Hướng Phụ thuộc**: Phân định rạch ròi: Feature chỉ chứa headless hooks/controllers; Page/Widget làm composition. Giao tiếp giữa Browse/Audio và Study thông qua headless port `entities/flashcard/model/cardContentUpdates.ts` kết hợp `app/studyContentSync.ts`. Giữ `printEngine.tsx` tại `features/worksheets/utils/`. Sửa công thức phân tầng thành ma trận quan hệ chuẩn. |
| **R4** | **P1** | Mâu thuẫn whitelist/blacklist; thiếu quyền sửa file cũ để đặt shim; vị trí Shadcn primitives ghi nước đôi; `components.json` chưa được cập nhật trỏ aliases. | **Tách G01 Thành 2 Pha Cụ thể**: Pha G01.a (tiện ích trung lập: `cn`, `useMobile`, `imageCompression`) và Pha G01.b (30 Shadcn primitives về `shared/ui/shadcn/`). Cấp quyền rõ ràng cho Gemini tạo shim tại các vị trí cũ. Cập nhật `frontend/components.json` trỏ aliases vào `shared/`. Giữ `ankiHtmlSanitizer` trong `lib/` thuộc quyền Codex C06.a. |
| **R5** | **P1** | Sai lệch chữ ký wire: ghi IDs dạng number thay vì string, media dạng object thay vì `StudyMediaArtifact[]`, query key browse thiếu `sortDir`, sai key Marketplace. | **Chuẩn hóa 100% Chữ ký Wire & Cache Identity**: Trích xuất nguyên văn từ code thực tế: ID dạng string, media `StudyMediaArtifact[]`, browse query key `['browse', 'cards', debouncedQuery, selectedDeckId, statusFilter, sortBy, sortDir, page, perPage]`, marketplace key `['marketplace', mode, ...]`. |
| **R6** | **P2** | Thiếu catalog mapping source $\to$ target cụ thể; gán nhầm `entities/support-ticket` cho C05/G05 (worksheets); dùng tên API chưa tồn tại. | **Lập Catalog Mapping 1-to-many Tường minh**: Chỉ định rõ đường dẫn phân rã cho các tệp monolith. Chuyển chủ sở hữu `entities/support-ticket` về nhóm admin/support (G10/G12). Giữ tên API thực tế đang chạy (`renderStudySide`). |
| **R7** | **P2** | Đề xuất DOM snapshot không chứng minh được Zero Visual Regression; quy định characterization test quá rộng không cần thiết cho việc di chuyển file thuần. | **Giao thức Visual Baseline Thực tế**: Thừa nhận khoảng trống visual tự động hiện tại; quy định kiểm tra trực quan đối chiếu ảnh chụp trên cùng fixture/viewport bằng Chrome profile cô lập (`flama-devtools`). Chỉ yêu cầu characterization tests tại các ranh giới có thay đổi trách nhiệm hoặc state machine. |
| **R8** | **P2** | Tự ý ghi "Đã nghiệm thu"; đếm thiếu routes (ghi 52 thay vì 77 direct + 18 redirects = 95); đếm thiếu Shadcn files (ghi 29 thay vì 30); thiếu cookie contract `sidebar_state`. | **Cập nhật Trạng thái & Số liệu Thực nghiệm**: Chuyển trạng thái sang `Ready for Codex Review`. Ghi nhận chuẩn xác: 95 route entries (77 direct + 18 redirects), đúng 30 Shadcn primitives, bổ sung quản lý cookie contract `sidebar_state`. |

### 2.2 Gói C01: Tách Biệt Transport Mạng & Session Bootstrap Độc lập
**Mục tiêu**: Xóa bỏ hoàn toàn Reverse Import từ tầng cơ sở `shared` lên tầng khởi tạo `app`, cách ly network transport và thống nhất session cache.

#### A. Phân tích Điểm nghẽn Hiện tại
Tệp `frontend/src/shared/api/bootstrap.ts` hiện tại có đoạn mã:
```typescript
// VI PHẠM PHÂN TẦNG: shared/api import ngược lên app/api!
import { useQuery } from '@tanstack/react-query'
import { appApi } from '../../app/api' // <-- REVERSE IMPORT
import { setCsrfToken } from './client'

export const bootstrapQueryKey = ['frontend', 'bootstrap'] as const
export async function fetchBootstrap() {
  const payload = await appApi.getBootstrap()
  setCsrfToken(payload.csrf_token)
  return payload
}
```
Trong khi đó, `app/api.ts` (471 LOC) là một gateway monolith chứa các hàm gọi API nghiệp vụ và import các DTOs từ `features/auth`, `features/dashboard`, `features/statistics`. Việc `shared/api/bootstrap.ts` import `app/api.ts` khiến toàn bộ tầng `shared` bị kéo dính vào tầng `app` và tầng `features`, phá vỡ hoàn toàn nguyên tắc phân tầng FSD.

#### B. Thiết kế Kiến trúc Gói C01
Tách trích xuất hàm nạp session độc lập tại `frontend/src/shared/api/session.ts` (hoặc `entities/session/api/bootstrap.ts`):

```typescript
// frontend/src/shared/api/session.ts
import { apiRequest, setCsrfToken } from './client'
import { API_BASE_URL, resolveBackendUrl } from './config'
import type { SessionResponse, FrontendBootstrap } from './types'

export const bootstrapQueryKey = ['frontend', 'bootstrap'] as const

/**
 * Trình fetch session trực tiếp thông qua HTTP transport trung lập.
 * Tuyệt đối không import bất kỳ tệp nào từ app/ hay features/.
 */
export async function fetchSessionBootstrap(): Promise<FrontendBootstrap> {
  const sessionUrl = resolveBackendUrl(`${API_BASE_URL}/session`)
  const payload = await apiRequest<SessionResponse>(sessionUrl, {
    method: 'GET',
    includeTimezone: false, // Backend session endpoint contract
  })

  // Đồng bộ hóa token CSRF cho client HTTP
  if (payload.csrf_token) {
    setCsrfToken(payload.csrf_token)
  }

  // Chuyển đổi sang FrontendBootstrap chuẩn hóa
  return toBootstrap(payload)
}

export function toBootstrap(payload: SessionResponse): FrontendBootstrap {
  return {
    user: payload.user ?? null,
    csrf_token: payload.csrf_token ?? '',
    roles: payload.roles ?? [],
    is_admin: payload.roles?.includes('admin') ?? false,
    links: payload.links ?? {},
    timestamp: Date.now(),
  }
}
```

```typescript
// frontend/src/shared/api/bootstrap.ts (Đã loại bỏ reverse import)
import { useQuery } from '@tanstack/react-query'
import { fetchSessionBootstrap, bootstrapQueryKey } from './session'
import type { FrontendBootstrap } from './types'

export { bootstrapQueryKey, fetchSessionBootstrap }

export function useBootstrap() {
  return useQuery<FrontendBootstrap, Error>({
    queryKey: bootstrapQueryKey,
    queryFn: fetchSessionBootstrap,
    staleTime: Number.POSITIVE_INFINITY,
    gcTime: 1000 * 60 * 60 * 24, // 24 giờ
  })
}
```

**Thành quả nghiệm thu C01**:
1. `git grep "app/api" frontend/src/shared/` trả về 0 kết quả.
2. `bootstrap.test.tsx` không còn cần mock `@/app/api`.
3. 100% các điểm tiêu thụ bootstrap (`useBrowseState.ts`, `useAnkiSyncPage.ts`, `AnkiSyncTab.tsx`, `AvatarUploadModal.tsx`, `EmailVerificationDialog.tsx`, `ProfileEditDialog.tsx`, `VerifyEmailPage.tsx`) đồng nhất sử dụng `bootstrapQueryKey`.

---

### 2.3 Gói G01: Quy chuẩn & Tái tổ chức UI Primitives (30 Shadcn + 8 Flama UI)
**Mục tiêu**: Hợp nhất toàn bộ 30 Shadcn UI primitives đang nằm tại `frontend/src/components/ui/` về `frontend/src/shared/ui/shadcn/`, giữ nguyên 8 Flama UI primitives chuẩn hóa tại `frontend/src/shared/ui/`, cập nhật cấu hình generator `components.json` và thiết lập hệ thống shim tương thích ngược 100%.

#### A. Hiện trạng Phân tán
1. `frontend/src/components/ui/`: Chứa chính xác **30 tệp primitives** Shadcn UI.
2. `frontend/src/shared/ui/`: Chứa **8 tệp Flama UI Primitives** (`SearchInput`, `ConfirmDialog`, `StatusPill`, `CodeSnippetBox`, `FilterPillGroup`, `ImageUploadDropzone`, `SplitPane`, `CardFieldsForm`) + `index.ts`.
3. `frontend/components.json` đang cấu hình:
   ```json
   "aliases": {
     "components": "@/components",
     "utils": "@/lib/utils",
     "ui": "@/components/ui",
     "lib": "@/lib",
     "hooks": "@/hooks"
   }
   ```
   Nếu chỉ di chuyển file mà không cập nhật tệp này, lệnh `npx shadcn@latest add` trong tương lai sẽ tiếp tục sinh component vào `components/ui/`.

#### B. Trình tự Thực thi Gói G01 (2 Pha An toàn)
- **Pha G01.a: Gom cụm Tiện ích Cơ sở (Utilities)**:
  - Chuyển `frontend/src/lib/utils.ts` $\to$ `frontend/src/shared/lib/utils.ts`.
  - Chuyển `frontend/src/hooks/use-mobile.ts` $\to$ `frontend/src/shared/lib/hooks/useMobile.ts`.
  - Chuyển `frontend/src/lib/imageCompression.ts` $\to$ `frontend/src/shared/lib/imageCompression.ts`.
  - Đặt các re-export shims tại vị trí cũ (`frontend/src/lib/utils.ts`, `frontend/src/hooks/use-mobile.ts`, `frontend/src/lib/imageCompression.ts`).
  - *Lưu ý*: Giữ nguyên `lib/ankiHtmlSanitizer.ts` tại `lib/` (thuộc phạm vi gói C06.a của Codex).

- **Pha G01.b: Gom cụm 30 Shadcn Primitives & Cập nhật Generator**:
  - Di chuyển 30 tệp từ `frontend/src/components/ui/*.tsx` sang `frontend/src/shared/ui/shadcn/*.tsx`.
  - Cập nhật imports nội bộ trong 30 tệp này để trỏ về `@/shared/lib/utils`, `@/shared/lib/hooks/useMobile`, và `@/shared/ui/shadcn/*`.
  - Tạo 30 tệp re-export shims tại `frontend/src/components/ui/*.tsx` dạng:
    ```typescript
    // frontend/src/components/ui/button.tsx
    export * from '@/shared/ui/shadcn/button'
    ```
  - Cập nhật `frontend/components.json`:
    ```json
    {
      "$schema": "https://ui.shadcn.com/schema.json",
      "style": "radix-nova",
      "rsc": false,
      "tsx": true,
      "tailwind": {
        "config": "",
        "css": "src/index.css",
        "baseColor": "neutral",
        "cssVariables": true,
        "prefix": ""
      },
      "iconLibrary": "lucide",
      "rtl": false,
      "aliases": {
        "components": "@/components",
        "utils": "@/shared/lib/utils",
        "ui": "@/shared/ui/shadcn",
        "lib": "@/shared/lib",
        "hooks": "@/shared/lib/hooks"
      }
    }
    ```
  - Bảo toàn 8 Flama UI Primitives tại `frontend/src/shared/ui/` và xuất bản qua `frontend/src/shared/ui/index.ts`.

---

## CHƯƠNG 3: R2 — ĐIỂM NÓNG #1: PHẪU THUẬT BROWSE WORKSPACE & NOTE EDITOR (FE-11)

### 3.1 Giải phẫu Chi tiết God Hook `useBrowseState.ts` (1,051 LOC, 48 useState)
Khảo sát thực nghiệm xác nhận `frontend/src/features/browse/hooks/useBrowseState.ts` hiện có **1,051 LOC**, trả về một đối tượng nguyên khối với **86 thuộc tính và phương thức**. Hook này quản lý chính xác **48 lời gọi `useState`** phân bổ qua 7 nhóm chức năng:

```
[Nhóm 1: Cây Thư mục Deck & Lọc Cây - 2 hooks]
- selectedDeckId (dòng 112): ID deck được chọn trong sidebar hoặc URL query.
- deckSearch (dòng 115): Từ khóa tìm kiếm cục bộ trong cây deck.

[Nhóm 2: Bộ lọc Tìm kiếm, Sắp xếp & Phân trang Thẻ - 7 hooks]
- queryText (dòng 118): Chuỗi tìm kiếm người dùng đang nhập thô vào ô input.
- debouncedQuery (dòng 119): Chuỗi tìm kiếm sau khi debounce 400ms.
- statusFilter (dòng 120): Bộ lọc trạng thái thẻ ('all' | 'new' | 'learning' | 'review').
- sortBy (dòng 121): Trường sắp xếp ('word' | 'reading' | 'meaning' | 'status' | 'due').
- sortDir (dòng 122): Hướng sắp xếp ('asc' | 'desc').
- page (dòng 123): Chỉ số trang hiện tại (1-indexed).
- perPage (dòng 124): Số thẻ trên mỗi trang, khởi tạo từ localStorage ('flama_browse_per_page').

[Nhóm 3: Lựa chọn Thẻ & Thao tác Hàng loạt - 1 hook]
- selectedCards (dòng 134): Mảng chứa danh sách cardId đang được tick chọn checkbox.

[Nhóm 4: Điều phối Trạng thái Modals & Công cụ - 10 hooks]
- isTtsModalOpen (dòng 144): Đóng/mở modal VoiceVox Web TTS.
- isLocalAudioModalOpen (dòng 145): Đóng/mở modal Flama Audio Local bridge.
- isStrokeModalOpen (dòng 146): Đóng/mở modal tạo sơ đồ nét bút Kanji.
- strokeModalMode (dòng 147): Chế độ tạo nét bút ('single' | 'batch').
- strokeModalCardId (dòng 148): Card ID mục tiêu cho modal nét bút.
- localAudioEngineId (dòng 149): Engine local audio ('voicevox' | 'kokoro').
- localAudioDefaultVoiceId (dòng 150): Giọng đọc mặc định local audio.
- localAudioTargetCardIds (dòng 151): Danh sách thẻ cần sinh audio.
- isWorksheetModalOpen (dòng 291): Đóng/mở modal xuất phiếu bài tập Worksheet.
- worksheetTargetDeckId (dòng 292), worksheetTargetCardIds (dòng 293): Dữ liệu mục tiêu của worksheet.

[Nhóm 5: Cấu hình VoiceVox Web TTS & Audio Preview - 14 hooks]
- ttsSourceField (dòng 154), ttsDestinationField (dòng 177), ttsCharacter (dòng 200).
- ttsApiKey (dòng 209), isKeySaved (dòng 212), isSavingKey (dòng 213), showApiKey (dòng 214).
- ttsAppendAudio (dòng 216), ttsUseOpus (dòng 225), ttsVolumeScale (dòng 234), ttsPitch (dòng 243).
- ttsSpeed (dòng 252), ttsIntonationScale (dòng 261), ttsInitialSilence (dòng 270), ttsFinalSilence (dòng 279).
- isPreviewing (dòng 288): Trạng thái đang phát âm thanh thử nghiệm VoiceVox.

[Nhóm 6: Chỉnh sửa Thẻ Hiện tại, Form Data & Dirty Tracking - 13 hooks]
- activeCardId (dòng 296): Card ID đang hiển thị trên thanh Sidebar phải (Editor).
- isCreatingCard (dòng 299): Cờ đánh dấu chế độ tạo mới thẻ.
- createNoteTypeId (dòng 300): Note type ID được chọn khi tạo mới thẻ.
- editFieldValues (dòng 323): Object lưu trữ giá trị các trường đang sửa đổi { [fieldName]: value }.
- editDeckId (dòng 324): Deck ID của thẻ đang sửa.
- editTags (dòng 325): Mảng danh sách tags của thẻ đang sửa.
- newTagInput (dòng 326): Chuỗi nhập tag mới trong input.
- initialFieldValues (dòng 329), initialDeckId (dòng 330), initialTags (dòng 331): Snapshot ban đầu để so sánh dirty state.

[Nhóm 7: Điều hướng Giao diện Mobile - 1 hook]
- mobileTab (dòng 303): Tab hiển thị trên điện thoại ('decks' | 'cards' | 'editor').
```

Bên cạnh 48 state hooks, tệp còn chứa:
- **7 `useRef`**: `audioPlayerRef` (audio element), `effectiveNoteTypeNameRef`, `initialUrlDeckSyncedRef` (chống sync lặp URL), `cardsRef`, `selectedCardsCountRef`, `ttsSourceFieldRef`, `ttsDestinationFieldRef`.
- **7 `useEffect`**: Sync URL mount time, debounce tìm kiếm 400ms, fallback note type, lắng nghe phím tắt toàn cục `Ctrl+A`/`Escape`, reset form snapshot khi đổi card, tự động gán trường VoiceVox và sync API key.
- **8 `useQuery`**: `useBootstrap`, `decksQuery`, `noteTypesQuery`, `cardsQuery`, `cardDetailQuery`, `deckSampleQuery`, `ttsProfileQuery`, `ttsVoicesQuery`.
- **5 `useMutation`**: `createMutation` (`POST /notes`), `updateMutation` (`PATCH /browse/cards/:id`), `deleteMutation` (`DELETE /browse/cards/:id`), `bulkDeleteMutation` (`POST /browse/cards/batch-delete`), `generateTtsMutation` (`POST /browse/voicevox/generate`).

### 3.2 Cơ chế Re-render Thrashing Cascade Làm Giảm Trải nghiệm Người dùng
1. Tại `frontend/src/features/browse/pages/BrowsePage.tsx`:
   ```tsx
   export function BrowsePage() {
     const browse = useBrowseState() // <-- ĐIỂM KÍCH HOẠT RE-RENDER TRUNG TÂM
     return (
       <div className="...">
         <BrowseDeckSidebar browse={browse} />
         <BrowseToolbar browse={browse} />
         <BrowseCardTable browse={browse} />
         <BrowseCardEditor browse={browse} />
         <BrowseTtsModal browse={browse} />
         <BrowseStrokeModal browse={browse} />
       </div>
     )
   }
   ```
2. **Cơ chế gây nghẽn (Blast Radius Cascade)**:
   - Trong React, khi bất kỳ `useState` nào trong `useBrowseState` thay đổi, toàn bộ hook được thực thi lại và trả về một object `browse` mang tham chiếu mới hoàn toàn.
   - Khi người dùng gõ 1 ký tự vào ô `newTagInput` hoặc chỉnh sửa 1 trường trong `editFieldValues`, `BrowsePage` re-render ngay lập tức.
   - Do object `browse` đổi tham chiếu và các handler (`handleToggleSelectAllCards`, `handleRevert`, `handleAddTag`...) không được bọc `useCallback`, cơ chế `React.memo` (nếu có) bị vô hiệu hóa 100%.
   - **Hệ quả**: Một phím gõ làm re-render toàn bộ:
     * `BrowseDeckSidebar`: Duyệt đệ quy lại toàn bộ cây thư mục hàng trăm deck.
     * `BrowseCardTable`: Render lại bảng danh sách lên đến 500 thẻ với hàng nghìn DOM elements và badge formatters.
     * `BrowseCardEditor`: Re-render toàn bộ các input và markdown preview.
   - Hơn nữa, việc nhồi nhét 14 state của VoiceVox TTS và 10 state của modals vào chung một hook khiến vòng đời duyệt thẻ bình thường bị ô nhiễm nghiêm trọng bởi các tác vụ ngoại vi chỉ dùng < 5% thời gian.

---

### 3.3 Thiết kế Phân rã: 3 Controllers Độc lập + 1 Modal Controller + 1 Facade Tương thích
Để triệt tiêu hiện tượng re-render lan truyền và đảm bảo toàn bộ tệp đều tuân thủ nghiêm ngặt **ngân sách < 250 LOC**, chúng tôi phân rã `useBrowseState.ts` thành 4 controllers chuyên trách và 1 facade tương thích ngược:

```
frontend/src/features/browse/hooks/
├── useBrowseFilters.ts          # Controller 1: Tìm kiếm, Bộ lọc, Cây Deck & URL Sync (< 250 LOC)
├── useBrowseSelection.ts        # Controller 2: Quản lý Chọn Thẻ (O(1) Set) & Thao tác Hàng loạt (< 120 LOC)
├── useBrowseCardEditor.ts       # Controller 3: Form Chỉnh sửa Thẻ, Snapshot & Dirty Tracking (< 220 LOC)
├── useBrowseTtsModal.ts         # Peripheral: Điều khiển Modal VoiceVox TTS & Preview Audio (< 180 LOC)
└── useBrowseState.ts            # Composite Facade tương thích ngược 100% (< 120 LOC)
```

#### A. Controller 1: Filters, Query, Deck Tree & URL Sync (`useBrowseFilters.ts`)
- **Trách nhiệm**: Quản lý từ khóa tìm kiếm (debounce 400ms), đồng bộ hóa hai chiều với URL search params (`deck_id`, `q`, `status`, `sort_by`, `sort_dir`, `page`), lọc cây deck, quản lý phân trang với `localStorage` persistence, và thực thi `cardsQuery`, `decksQuery`.
- **Kích thước dự kiến**: ~240 LOC (< 250 LOC).
- **Interface Định nghĩa**:
```typescript
export interface BrowseFiltersState {
  // Query & Debounce
  queryText: string
  debouncedQuery: string
  setQueryText: (text: string) => void

  // Deck Selection & Search
  selectedDeckId: number | null
  setSelectedDeckId: (deckId: number | null) => void
  selectedDeck: BrowseDeck | null
  deckSearch: string
  setDeckSearch: (search: string) => void
  handleResetDeckFilter: () => void

  // Status Filter & Sorting
  statusFilter: string
  setStatusFilter: (status: string) => void
  sortBy: string
  sortDir: 'asc' | 'desc'
  toggleSort: (field: string) => void

  // Pagination
  page: number
  setPage: React.Dispatch<React.SetStateAction<number>>
  perPage: number
  handlePerPageChange: (newPerPage: number) => void

  // Server Data
  cards: BrowseCardRow[]
  totalCards: number
  totalPages: number
  isCardsLoading: boolean
  cardsQuery: UseQueryResult<BrowseCardsResponse, Error>
  decks: BrowseDeck[]
  filteredDecks: BrowseDeck[]
  decksQuery: UseQueryResult<{ decks: BrowseDeck[] }, Error>
}
```

#### B. Controller 2: Selection & Bulk Operations (`useBrowseSelection.ts`)
- **Trách nhiệm**: Quản lý tập hợp thẻ được chọn với cấu trúc dữ liệu `Set<string>` cho phép kiểm tra thành viên với độ phức tạp $O(1)$, xử lý chọn/bỏ chọn từng thẻ, chọn tất cả thẻ trang hiện tại, xử lý phím tắt toàn cục (`Ctrl+A` / `Cmd+A` để chọn tất cả, `Escape` để hủy chọn — tự động bỏ qua khi focus trong input/textarea), và thực thi `bulkDeleteMutation` (`POST /browse/cards/batch-delete`).
- **Kích thước dự kiến**: ~120 LOC (< 150 LOC).
- **Interface Định nghĩa**:
```typescript
export interface BrowseSelectionState {
  selectedCards: string[]
  selectedCardIds: Set<string>
  isSelected: (cardId: string) => boolean
  toggleCard: (cardId: string) => void
  setSelectedCards: React.Dispatch<React.SetStateAction<string[]>>
  allSelected: boolean
  toggleSelectAll: () => void
  clearSelection: () => void

  // Bulk Mutations
  bulkDeleteMutation: UseMutationResult<number, Error, string[]>
  handleBulkDelete: (cardIds?: string[]) => Promise<void>
}
```

#### C. Controller 3: Active Card & Form Editor (`useBrowseCardEditor.ts`)
- **Trách nhiệm**: Quản lý `activeCardId`, chế độ tạo thẻ mới (`isCreatingCard`), form values (`editFieldValues`, `editDeckId`, `editTags`), dirty state tracking (`isDirty`) dựa trên snapshot đối chiếu với `initialFieldValues`, tính năng hoàn tác (`handleRevert`), nạp chi tiết thẻ qua `cardDetailQuery`, thực thi `createMutation`, `updateMutation`, `deleteMutation`, và giao tiếp cập nhật phiên học thông qua headless port `updateCardFieldValues`.
- **Kích thước dự kiến**: ~220 LOC (< 250 LOC).
- **Interface Định nghĩa**:
```typescript
export interface BrowseCardEditorState {
  activeCardId: string | null
  setActiveCardId: (id: string | null) => void
  isCreatingCard: boolean
  startCreateCard: () => void
  cancelCreate: () => void
  createNoteTypeId: string | null
  setCreateNoteTypeId: (id: string | null) => void

  // Form State
  editFieldValues: Record<string, string>
  setFieldValue: (name: string, value: string) => void
  setEditFieldValues: React.Dispatch<React.SetStateAction<Record<string, string>>>
  editDeckId: number | null
  setEditDeckId: (deckId: number | null) => void
  editTags: string[]
  newTagInput: string
  setNewTagInput: (input: string) => void
  handleAddTag: () => void
  handleRemoveTag: (tag: string) => void

  // Dirty State & Snapshot
  isDirty: boolean
  handleRevert: () => void

  // Server Integration
  cardDetailQuery: UseQueryResult<CardDetailResponse, Error>
  createMutation: UseMutationResult<any, Error, any>
  updateMutation: UseMutationResult<any, Error, any>
  deleteMutation: UseMutationResult<any, Error, string>
  handleSubmit: () => Promise<void>
  handleDeleteActiveCard: () => Promise<void>
}
```

#### D. Peripheral Controller: VoiceVox TTS Modal Controller (`useBrowseTtsModal.ts`)
- **Trách nhiệm**: Đóng gói toàn bộ 14 state VoiceVox, logic đồng bộ `localStorage` (`ttsSettingsStorage`), truy vấn `ttsProfileQuery`, `ttsVoicesQuery`, mutation sinh audio `generateTtsMutation`, và ref phát âm thanh thử nghiệm. Tách biệt hoàn toàn khỏi render loop của Browse workspace.
- **Kích thước dự kiến**: ~180 LOC (< 200 LOC).

#### E. Composite Facade: Tương thích Ngược 100% (`useBrowseState.ts`)
- **Trách nhiệm**: Ghép nối 4 controllers trên thành một facade duy nhất có chữ ký và shape hoàn toàn tương thích với `useBrowseState` cũ. Đảm bảo toàn bộ các bài unit test hiện hành (`BrowsePage.test.tsx`, `BrowseCardTable.test.tsx`, `bootstrap.test.tsx`) tiếp tục pass 100% mà không cần sửa đổi đồng thời.
- **Kích thước dự kiến**: ~120 LOC (< 150 LOC).

---

### 3.4 Bóc tách Hoàn toàn Browse Khỏi Study Session Store & Di chuyển Card DTOs

#### A. Trạng thái Đã đạt được (Outward Decoupling)
Sau đợt review gói C02 ngày 2026-10-05 của Codex, `useBrowseState.ts` đã **không còn import bất kỳ module nội bộ nào của `features/study`**. Luồng cập nhật thẻ hiện tại được thực thi an toàn thông qua headless mutation port:
```typescript
import { updateCardFieldValues } from '@/entities/flashcard/model/cardContentUpdates'

// Bên trong updateMutation.onSuccess:
await updateCardFieldValues({
  cardId: activeCardId,
  fieldValues: editFieldValues,
  noteId,
})
```
Cổng này giao tiếp với ứng dụng tại `frontend/src/app/studyContentSync.ts` (được cấu hình trước khi router render trong `App.tsx`), đảm bảo tính độc lập tuyệt đối giữa Browse và Study runtime.

#### B. Khắc phục Điểm vi phạm Ngược còn sót lại (Inward Coupling Study -> Browse)
Khảo sát phát hiện tệp `frontend/src/features/study/components/StudyQuickEditDialog.tsx` đang có các import trực tiếp vi phạm FSD:
```typescript
// VI PHẠM: Study import ngược sang Browse!
import { MediaFieldPreview } from '@/features/browse/components/MediaFieldPreview'
import { BrowseStrokeModal } from '@/features/browse/components/BrowseStrokeModal'
import type { CardDetailResponse } from '@/features/browse/hooks/useBrowseState'
```
**Kế hoạch Chuẩn hóa Triệt để**:
1. **Di chuyển Canonical DTOs**: Di chuyển toàn bộ các DTOs (`CardDetailResponse`, `CardDetailField`, `NoteTypeFieldDef`, `NoteTypeSummary`, `BrowseCardRow`, `BrowseCardsResponse`) vào `frontend/src/entities/flashcard/model/types.ts` và export công khai qua `entities/flashcard/index.ts`.
2. **Tiêu thụ Trực tiếp `MediaFieldPreview`**: Cả Browse và Study đều import `MediaFieldPreview` trực tiếp từ `@/entities/flashcard`.
3. **Di chuyển Stroke Order Modal**: Di chuyển component sinh nét chữ Kanji từ `features/browse/components/BrowseStrokeModal.tsx` sang `entities/flashcard/ui/StrokeOrderModal.tsx` (hoặc `features/stroke-order/`), xóa bỏ hoàn toàn liên kết chéo giữa Study và Browse.

---

### 3.5 Tái cấu trúc Giao diện UI Browse & Tích hợp Primitive `CardFieldsForm`
1. Hiện tại, `frontend/src/features/browse/components/BrowseCardEditor.tsx` (644 LOC) đang viết lặp lại 2 lần mã nguồn sinh các thẻ `<Input>`, `<Textarea>`, nhãn trường và preview media (một lần cho chế độ tạo mới tại dòng 257–311, một lần cho thẻ đang sửa tại dòng 507–553).
2. Tích hợp trực tiếp UI primitive chuẩn hóa `frontend/src/shared/ui/CardFieldsForm.tsx` (đã xây dựng ở Phase 1) vào `BrowseCardEditor.tsx`:
   - Thay thế toàn bộ vòng lặp sinh form thủ công bằng `<CardFieldsForm fields={...} values={...} onChange={...} />`.
   - Giảm kích thước `BrowseCardEditor.tsx` từ 644 LOC xuống **~220 LOC**.
3. Tách các thành phần phụ trợ ra khỏi `BrowsePage.tsx` (609 LOC):
   - Trích xuất menu âm thanh inline (dòng 230–365) thành `BrowseAudioDropdownMenu.tsx` (~110 LOC).
   - Trích xuất thanh điều hướng tab di động thành `BrowseMobileTabBar.tsx` (~70 LOC).
   - Đưa kích thước của `BrowsePage.tsx` xuống **~310 LOC**.

### 3.6 Ngân sách File Size (< 400 LOC) & Checklist Zero Visual Regression

#### A. Bảng Ngân sách Dòng mã (LOC Budget Compliance)
| Tệp Mục tiêu Sau Tái cấu trúc | Vai trò Kiến trúc | LOC Dự kiến | Tuân thủ Ngân sách |
|---|---|---|---|
| `hooks/useBrowseFilters.ts` | Controller Bộ lọc & URL Sync | ~240 | < 400 LOC ✅ |
| `hooks/useBrowseSelection.ts` | Controller Chọn & Thao tác Bulk | ~120 | < 400 LOC ✅ |
| `hooks/useBrowseCardEditor.ts` | Controller Soạn thảo Thẻ & Dirty | ~220 | < 400 LOC ✅ |
| `hooks/useBrowseTtsModal.ts` | Controller Modal VoiceVox TTS | ~180 | < 400 LOC ✅ |
| `hooks/useBrowseState.ts` | Composite Facade Tương thích | ~120 | < 400 LOC ✅ |
| `pages/BrowsePage.tsx` | Trang Browse Workspace chính | ~310 | < 400 LOC ✅ |
| `components/BrowseCardEditor.tsx` | Sidebar Chỉnh sửa Thẻ | ~220 | < 400 LOC ✅ |
| `components/BrowseCardTable.tsx` | Bảng Danh sách Thẻ | 175 | < 400 LOC ✅ |
| `components/BrowseDeckSidebar.tsx` | Cây Thư mục Deck | 252 | < 400 LOC ✅ |
| `components/BrowseToolbar.tsx` | Thanh Công cụ Tìm kiếm | 121 | < 400 LOC ✅ |
| `components/BrowsePagination.tsx` | Thanh Phân trang & Jump | 342 | < 400 LOC ✅ |

#### B. Checklist Kiểm tra Zero Visual Regression Cho Browse Workspace
- [ ] **Bố cục 3 Pane Chuẩn xác**:
  * Sidebar trái: `w-full md:w-64 border-r border-border/60 bg-card`.
  * Khung chỉnh sửa phải: Kích thước co giãn lưu trong `localStorage['flama:browse:editor-width']`, mặc định 320px, giới hạn kẹp trong `[280px, min(800px, 60% viewport)]`.
  * Splitter handle: `w-1 cursor-col-resize hover:bg-primary/60 hover:w-1.5 transition-all bg-border/20 z-50`.
- [ ] **Tab Bar Di động (Mobile Viewport < lg)**:
  * Thanh tab nổi dưới đáy màn hình: `h-12 border-t border-border/60 bg-background/95`.
  * Trạng thái active: `text-primary font-bold` so với `text-muted-foreground`.
- [ ] **Định dạng Bảng & Trạng thái Thẻ**:
  * Màu sắc badge trạng thái (`new`, `learning`, `review`, `due`) kế thừa chính xác token OKLCH từ `statusVariant()` và `statusLabel()`.
  * Highlight hàng thẻ đang active: `bg-primary/5 hover:bg-primary/10 border-l-2 border-l-primary`.
- [ ] **Tương tác Bàn phím & Phím tắt**:
  * `Ctrl+A` / `Cmd+A`: Chọn toàn bộ thẻ hiển thị khi con trỏ không nằm trong input/textarea.
  * `Escape`: Hủy chọn toàn bộ thẻ khi số lượng chọn > 0.
  * `Ctrl+Enter` / `Cmd+Enter`: Submit lưu form chỉnh sửa thẻ đang chọn.

---

## CHƯƠNG 4: R3 — ĐIỂM NÓNG #2: PHẪU THUẬT WORKSHEETS STUDIO & PRINT ENGINE (FE-12, FE-13)

### 4.1 Giải phẫu Monolith Khổng lồ `DeckWorksheetModal.tsx` (4,388 LOC) & `WorksheetPageRenderer.tsx` (1,719 LOC)
Worksheets Studio là tính năng biên tập và xuất phiếu luyện viết tiếng Nhật (Kanji stroke practice, vocabulary recall, Genkouyoushi 作文纸 essay, custom tables) có độ phức tạp cao nhất về mặt giao diện và in ấn trong hệ thống Flama:

1. **`DeckWorksheetModal.tsx` (4,388 LOC, 252 KB)**:
   - Điều phối 2 chế độ: Standalone Mode (luyện viết tự do không cần deck) và Deck Mode (liên kết từ vựng trong deck).
   - Bao bọc một Wizard 4 bước, trong đó **Bước 4 (Live Studio) chiếm từ dòng 898 đến 4383 (~3,485 LOC)**:
     * Tab `'template'` (dòng 1032–1130): Chọn mẫu phiếu.
     * Tab `'data'` (dòng 1131–1488): Chọn note type, phạm vi thẻ (`all | first_n | random_n | selected`), cấu hình mapping trường.
     * Tab `'layout'` (dòng 1489–3940, **~2,452 LOC**): Chứa hàng trăm thanh trượt kích thước, checkbox, bộ chọn màu, font chữ, kiểu lưới và cấu hình cột phụ trợ.
     * Tab `'header'` (dòng 3941–4160): Tiêu đề, trường thông tin học sinh, định dạng ngày tháng, watermark chống sao chép.
     * Khung Preview Workbench bên phải (dòng 4198–4382): Phân trang, zoom toolbar, touch swipe gestures và mount `WorksheetPageRenderer`.
   - Nắm giữ 22 `useState` riêng biệt cùng các cache đồng bộ thủ công (`templateOptionsMap`, `templateFieldMappingMap`).

2. **`WorksheetPageRenderer.tsx` (1,719 LOC, 82 KB)**:
   - Trộn lẫn 6 trách nhiệm kiến trúc khác nhau vào trong một component:
     1. Client-side SVG Cache & String Parsing (dòng 27–169).
     2. Sinh mã QR động tại chỗ (dòng 234–254).
     3. **Tính toán tọa độ hình học lưới viết ngay trong vòng lặp render JSX**: tính toán chia cột `compoundItem` (dòng 539–584), `stepItem` (dòng 725–749), standard kanji (dòng 1095–1117), Genkouyoushi essay 20x20 cells (dòng 1597–1676) và custom table (dòng 1325–1481).
     4. CSS print injection (dòng 268–347): Chèn thẻ `<style>` toàn cục trên mỗi trang render.
     5. Watermark rendering theo ma trận chéo (dòng 350–394).
     6. Header & Footer pagination (dòng 395–489 và dòng 1680–1715).

---

### 4.2 Phân rã 5 Bước Studio Wizard Thành Các Component Độc lập Dưới 300 LOC
Chúng tôi bóc tách khối mã 4,388 LOC thành 5 component step độc lập, 1 headless hook điều phối và 1 modal shell mỏng:

```
frontend/src/features/worksheets/
├── components/
│   ├── DeckWorksheetModal.tsx                  # Modal shell & Stepper Coordinator (< 250 LOC)
│   ├── LazyDeckWorksheetModal.tsx              # Dynamic import chunk loader (Giữ nguyên)
│   ├── KanjiGridBox.tsx                        # SVG cell box primitive (Giữ nguyên, 132 LOC)
│   ├── WorksheetWizardStepper.tsx              # Wizard navigation bar (Giữ nguyên, 149 LOC)
│   ├── steps/
│   │   ├── WorksheetTemplatePickerStep.tsx     # Bước 1: Chọn Mẫu Phiếu & Lọc Phân loại (< 250 LOC)
│   │   ├── WorksheetVocabSourceStep.tsx        # Bước 2: Nguồn Từ vựng, Phạm vi & Field Mapping (< 280 LOC)
│   │   ├── WorksheetTypographyStep.tsx         # Bước 3: Font Chữ, Nét Bút, Màu Sắc & Guidelines (< 290 LOC)
│   │   ├── WorksheetPageLayoutStep.tsx         # Bước 4: Khổ A4, Căn Lề, Header, Cột Phụ & Watermark (< 290 LOC)
│   │   └── WorksheetPreviewWorkbench.tsx       # Bước 5: Bàn Preview, Zoom, Gestures & Nút In (< 280 LOC)
│   ├── renderers/
│   │   ├── WorksheetPageRenderer.tsx           # Page Shell Coordinator (< 180 LOC)
│   │   ├── WorksheetHeader.tsx                 # Header & Metadata Học sinh (< 160 LOC)
│   │   ├── WorksheetFooter.tsx                 # Footer, Phân trang, Mã QR & Branding (< 140 LOC)
│   │   ├── WorksheetWatermark.tsx              # Watermark chống trộm (< 120 LOC)
│   │   ├── KanjiWorksheetSection.tsx           # Render phần Kanji chuẩn, ghép & từng bước (< 290 LOC)
│   │   ├── VocabWorksheetSection.tsx           # Render phần Từ vựng & Nhớ từ (< 200 LOC)
│   │   ├── TableWorksheetSection.tsx           # Render Bảng Từ vựng Tùy biến (< 240 LOC)
│   │   └── EssayWorksheetSection.tsx           # Render Giấy Viết Văn Genkouyoushi (< 190 LOC)
│   └── hooks/
│       └── useWorksheetStudio.ts               # Headless State, Preset Sync & Options Cache (< 280 LOC)
└── utils/
    ├── gridGeometry.ts                         # Pure Math: Tọa độ, kích thước A4 & ô viết (< 250 LOC)
    ├── kanjiSvgCache.ts                        # SVG Parser & Cache LRU Client (< 180 LOC)
    ├── printEngine.tsx                         # Runner in ấn trình duyệt (@media print) (< 150 LOC)
    └── worksheetStorage.ts                     # LocalStorage Presets Persistence (Giữ nguyên, 51 LOC)
```

#### Quy chuẩn Chi tiết 5 Bước Wizard:
1. **Bước 1: `WorksheetTemplatePickerStep.tsx` (< 250 LOC)**:
   - Lọc theo phân loại: `all`, `kanji` (Kanji Stroke, Compact, Compound, Step-by-Step), `vocabulary` (Vocab Writing, Recall), `sentence` (Sentence Writing), `essay` (Genkouyoushi 400 ô), `table` (Custom Deck Table).
   - Hiển thị card lựa chọn kèm icon minh họa, mô tả và huy hiệu hướng giấy (`portrait` / `landscape`).
2. **Bước 2: `WorksheetVocabSourceStep.tsx` (< 280 LOC)**:
   - Cây chọn deck, chọn Note Type (khi deck có nhiều note types) và mapping trường từ vựng (`Word`, `Reading`, `Meaning`).
   - Lựa chọn phạm vi thẻ: `all`, `first_n`, `random_n`, `selected` (hỗ trợ truyền sẵn danh sách card ID từ Browse hoặc Deck page).
   - Switch chuyển đổi chế độ in phiếu trống (Standalone mode).
3. **Bước 3: `WorksheetTypographyStep.tsx` (< 290 LOC)**:
   - Kiểu ô lưới: `cross` (+), `diagonal` (米), `square` (口).
   - Kích thước ô viết: thanh trượt từ 22px đến 48px kèm hiển thị số milimét thực tế tương đương trên giấy.
   - Nét bút: bật/tắt sơ đồ nét, bật/tắt số thứ tự nét, chế độ màu nét (`monochrome`, `multicolor`, `same_as_reference`), bộ chọn màu chữ mẫu.
   - Typography nghĩa & cách đọc: bật/tắt furigana, nghĩa, font scale. Bộ ký tự: tiếng Nhật (`ja`), tiếng Trung Giản thể (`zh`), Phồn thể (`zh-hant`).
4. **Bước 4: `WorksheetPageLayoutStep.tsx` (< 290 LOC)**:
   - Căn lề khổ A4: `minimal` (8mm), `compact` (12mm), `standard` (20mm), `wide` (28mm).
   - Hướng giấy (`portrait` / `landscape`), chế độ dàn dòng (`balanced_stretch` vs `max_density`).
   - Cột phụ trợ: loại cột (`dashed_line`, `grid_boxes`, `checkboxes`, `double_line`, `blank`), độ rộng cột.
   - Header & Footer: tiêu đề, tiêu đề phụ, thông tin học sinh, định dạng ngày tháng, watermark chống sao chép.
5. **Bước 5: `WorksheetPreviewWorkbench.tsx` (< 280 LOC)**:
   - Thanh công cụ điều hướng trang, jump trang, thanh zoom (`ZoomIn`, `ZoomOut`, `Fit`).
   - Hỗ trợ thao tác vuốt cảm ứng trên thiết bị di động (`onTouchEnd`).
   - Nút hành động chính: "In / Lưu PDF" kích hoạt `printEngine`.

---

### 4.3 Cô lập Hình học Tọa độ Lưới A4 Vào Pure Math Module `gridGeometry.ts` (< 250 LOC)
Toàn bộ các phép tính toán kích thước vật lý, chuyển đổi milimét sang pixel và phân bổ số ô trên mỗi dòng được bóc tách hoàn toàn khỏi JSX vào module toán học thuần túy `frontend/src/features/worksheets/utils/gridGeometry.ts`:

#### A. Tiêu chuẩn Vật lý Khổ Giấy A4 & Hệ số Chuyển đổi 96 DPI
- Khổ A4 Dọc (Portrait): $210\text{ mm} \times 297\text{ mm}$.
- Khổ A4 Ngang (Landscape): $297\text{ mm} \times 210\text{ mm}$.
- Hệ số chuyển đổi chuẩn CSS (96 CSS pixels per inch, $1\text{ inch} = 25.4\text{ mm}$):
  $$1\text{ mm} = \frac{96}{25.4} \approx 3.779527559\text{ px}$$

#### B. Ma trận Kích thước Vùng Khả dụng (Usable Dimensions Matrix)
| Loại Lề (Margin Type) | Tổng Lề (mm) | Padding Class | Rộng Khả dụng Dọc (mm / px) | Rộng Khả dụng Ngang (mm / px) |
|---|---|---|---|---|
| `minimal` / `ultra_compact` | 8 mm | `p-[4mm]` | 202 mm / 763 px | 289 mm / 1092 px |
| `compact` | 12 mm | `p-[6mm]` | 198 mm / 748 px | 285 mm / 1077 px |
| `standard` | 20 mm | `p-[10mm]` | 190 mm / 718 px | 277 mm / 1046 px |
| `wide` | 28 mm | `p-[14mm]` | 182 mm / 687 px | 269 mm / 1016 px |

#### C. Chữ ký Hàm Toán học Thuần túy trong `gridGeometry.ts`
```typescript
export interface UsableDimensions {
  widthMm: number
  heightMm: number
  widthPx: number
  heightPx: number
  paddingClass: string
}

export function calculateUsableDimensions(
  orientation: 'portrait' | 'landscape',
  marginType: 'minimal' | 'ultra_compact' | 'compact' | 'standard' | 'wide' = 'standard',
): UsableDimensions {
  const isLandscape = orientation === 'landscape'
  const pageW_mm = isLandscape ? 297 : 210
  const pageH_mm = isLandscape ? 210 : 297
  const marginMm = marginType === 'minimal' || marginType === 'ultra_compact' ? 8
    : marginType === 'compact' ? 12
    : marginType === 'wide' ? 28 : 20

  const widthMm = pageW_mm - marginMm
  const heightMm = pageH_mm - marginMm
  const pxFactor = 96 / 25.4

  return {
    widthMm,
    heightMm,
    widthPx: Math.floor(widthMm * pxFactor),
    heightPx: Math.floor(heightMm * pxFactor),
    paddingClass: `p-[${Math.floor(marginMm / 2)}mm]`,
  }
}

export interface KanjiRowLayout {
  fullRowBoxesCount: number
  leftInfoWidth: number
  pillWidth: number
  availableRightWidth: number
  boxSlotWidth: number
  traceCount: number
  practiceCount: number
  fillCount: number
}

export function calculateKanjiRowLayout(
  topComponentWidthPx: number,
  boxSize: number,
  options: WorksheetLayoutOptions,
  item: WorksheetKanjiItem,
): KanjiRowLayout {
  // Thực hiện phân bổ ô viết chính xác không sinh lỗi làm tròn sub-pixel
  // ...
}
```

---

### 4.4 Đóng gói Công cụ In Ấn `printEngine.tsx` (< 150 LOC) & Bảo toàn Latch `@media print`
Tệp `frontend/src/features/worksheets/utils/printEngine.tsx` được bảo toàn và đóng gói chuẩn mực, giữ vững các chốt an toàn (latches) đã kiểm chứng:
1. **DOM Isolation**: Mount vào một phần tử độc lập nằm ngoài cây React chính: `#flama-worksheet-print-root`.
2. **Quy tắc CSS Print Nghiêm ngặt**:
   ```css
   @page {
     size: A4 ${orientation};
     margin: 0;
   }
   html, body {
     margin: 0 !important;
     padding: 0 !important;
     background: #ffffff !important;
   }
   body > * {
     display: none !important;
   }
   body > #${PRINT_ROOT_ID} {
     display: block !important;
   }
   #${PRINT_ROOT_ID} .flama-print-page {
     display: block !important;
     break-after: page;
     page-break-after: always;
   }
   #${PRINT_ROOT_ID} .flama-print-page:last-child {
     break-after: auto;
     page-break-after: auto;
   }
   ```
3. **Asset Readiness Latch (Chốt nạp tài nguyên)**: Phải hoàn tất 3 bước trước khi kích hoạt `window.print()`:
   - Chờ `document.fonts.ready` (đảm bảo font chữ tiếng Nhật, nét bút đã nạp đầy đủ).
   - Duyệt qua toàn bộ thẻ `<img>` trong print root và thực hiện `await img.decode()`.
   - Chờ 2 chu kỳ `requestAnimationFrame` để trình duyệt hoàn tất layout.

### 4.5 Chuẩn hóa Các Section Renderers Chuyên biệt
Tách các nhánh render trong `WorksheetPageRenderer.tsx` thành 4 component con độc lập trong thư mục `renderers/`:
- `KanjiWorksheetSection.tsx`: Render các khối luyện viết chữ Hán đơn lẻ, chữ ghép (compounds) và từng bước nét bút.
- `VocabWorksheetSection.tsx`: Render bảng từ vựng và câu ví dụ luyện nhớ.
- `TableWorksheetSection.tsx`: Render bảng tùy biến với các cột checkbox, dòng kẻ đứt, đường kẻ đôi.
- `EssayWorksheetSection.tsx`: Render giấy viết văn 400 ô Genkouyoushi với khoảng cách hàng và vạch phân chia cột chuẩn mực.

### 4.6 Bảo đảm Zero Visual Regression Cho Bản In PDF & Xuất Giấy
- [ ] Bảo toàn 100% tỷ lệ khung hình và kích thước milimét trên từng trang A4 in ra.
- [ ] Giữ nguyên vị trí chân trang, số trang "Trang X / Y", logo bản quyền và mã QR.
- [ ] Không phát sinh trang trắng thừa ở cuối tài liệu (nhờ rule `:last-child { break-after: auto }`).
- [ ] Font chữ nét bút Kanji hiển thị sắc nét, không bị nhòe hay vỡ nét vector SVG.

---

## CHƯƠNG 5: R4 — BẢO VỆ TÍNH BỀN VỮNG PHIÊN HỌC STUDY & CÁCH LY SRS ENGINE (FE-19)

### 5.1 Kế thừa Lát cắt `entities/flashcard` và Cổng Cập nhật Nội dung (C02)
Ngày 2026-10-05, Codex đã hoàn thành việc bóc tách lát cắt `entities/flashcard` (gồm 8 source files, 7 test files, 69 tests passed). Các ranh giới sau đây đã được thiết lập và phải được kế thừa trọn vẹn:
- `entities/flashcard/ui/CardRendererFrame.tsx`: Bảo toàn iframe sandbox, cơ chế postMessage hai chiều và giữ mounted đồng thời cả hai mặt thẻ Front/Back.
- `entities/flashcard/model/cardContentUpdates.ts`: Headless port cho phép cập nhật field values mà không phụ thuộc module study.
- `app/studyContentSync.ts`: Cầu nối composition nạp động Study persistence và đợi hoàn tất ghi đĩa/IndexedDB.

---

### 5.2 Hợp đồng Bất biến Mẫu Thẻ (Template Immutability Contract in Active Lease)

#### A. Định nghĩa Hợp đồng Cốt lõi
Khi một phiên học Study Session đang mở và nắm giữ khóa Web Locks (`active session lease`), các định nghĩa mẫu thẻ (**`snapshot.templates`**) là **BẤT BIẾN TUYỆT ĐỐI (FROZEN / IMMUTABLE)**. Mọi thao tác chỉnh sửa mã nguồn HTML/CSS của mẫu thẻ trong NoteType Editor hoặc các tab khác đều **CỐ Ý LÀ NO-OP** đối với phiên học đang mở:
```typescript
// frontend/src/features/study/session/sessionStore.ts
export async function updateTemplateInSessions(
  templateId: string,
  updated: UpdatedTemplatePayload,
) {
  // Template definitions and executable sources are immutable for an open lease.
  // The authoring update is visible only after a new session is opened.
  void templateId
  void updated
  // INTENTIONAL NO-OP
}
```

```typescript
// frontend/src/features/study/hooks/useStudySession.ts
const updateTemplateContent = useCallback(async (
  templateId: string,
  updated: UpdatedTemplatePayload,
) => {
  // Template source, version and binding are immutable for an active lease.
  // The saved authoring change becomes visible only in a newly opened one.
  void templateId
  void updated
  // INTENTIONAL NO-OP
}, [])
```

#### B. Cơ sở Kiến trúc Bắt buộc của Hợp đồng
1. **Bảo vệ Tính toàn vẹn Cryptographic Snapshot Hash**:
   - Snapshot của phiên học được định danh duy nhất bởi `snapshot_hash` và `enrollment_epoch`.
   - Nếu client tự ý thay đổi mã template giữa phiên học, snapshot hash trên client sẽ phân kỳ khỏi bản ghi phía server. Khi người dùng submit kết quả học, lệnh commit hoặc batch sync sẽ bị backend từ chối với mã lỗi `INVALID_SNAPSHOT_HASH` hoặc `ENROLLMENT_EPOCH_MISMATCH`.
2. **Bảo vệ Tính Ổn định của Iframe Sandbox**:
   - `CardRendererFrame` nạp mã template vào một iframe bị cô lập bảo mật. Việc thay đổi template giữa chừng có thể làm phá vỡ ngữ cảnh thực thi JavaScript, mất đồng bộ handshake tin nhắn `postMessage`, gây chớp giật giao diện hoặc crash ứng dụng.
3. **Bảo vệ Tính Bền vững của Thuật toán Hoàn tác (Deterministic Undo)**:
   - Phiên học lưu trữ lịch sử trả lời trong mảng `undo_history`. Nếu template bị thay đổi giữa phiên, thao tác Undo sẽ hiển thị lại thẻ theo một định dạng template khác với lúc người dùng thực hiện review thẻ, phá vỡ tính nhất quán dữ liệu.
4. **Phân biệt Rạch ròi Giữa Content và Template**:
   - **Card Content** (giá trị các trường từ vựng, âm thanh, hình ảnh): Cập nhật **động theo thời gian thực** thông qua `updateCardFieldValuesInSessions` và `dispatchStudyCardUpdate`.
   - **Card Template** (cấu trúc HTML, CSS, JavaScript slots): **Đóng băng hoàn toàn** cho đến khi phiên học kết thúc và phiên mới được khởi tạo.

---

### 5.3 Phân rã `StudyPage.tsx` (< 200 LOC) & Các Interaction Hooks Chuyên biệt
Tệp `frontend/src/features/study/pages/StudyPage.tsx` (554 LOC) hiện tại đang trộn lẫn việc render giao diện với việc xử lý phím tắt, bấm giờ độ trễ và chặn điều hướng trình duyệt. Phân rã thành:

```
frontend/src/features/study/
├── pages/
│   └── StudyPage.tsx                          # Pure UI Presentation Shell (< 200 LOC)
├── interactions/
│   ├── useStudyKeyboardShortcuts.ts            # Phím Space/Enter, 1-4, Z, E, F (< 150 LOC)
│   ├── useStudyLatencyTimer.ts                 # performance.now() elapsed timer (< 80 LOC)
│   └── useStudyNavigationGuard.ts              # useBlocker & cảnh báo chưa commit (< 90 LOC)
├── components/
│   ├── StudyHeaderToolbar.tsx                 # Header stats, tiêu đề deck, nút thoát
│   ├── StudyCardRendererFrame.tsx             # Adapter tới @/entities/flashcard/ui/CardDisplay
│   ├── StudyBottomBar.tsx                     # Rating buttons & reveal action
│   ├── StudyQuickEditDialog.tsx               # Modal sửa nhanh trường thẻ trong phiên
│   ├── StudyExitConfirmDialog.tsx             # Modal xác nhận thoát khi còn thẻ uncommitted
│   └── StudySessionConflict.tsx               # Modal cảnh báo tranh chấp lease trên tab khác
```

`StudyPage.tsx` sau khi tái cấu trúc:
```tsx
export function StudyPage() {
  const study = useStudySession()
  const { elapsedMs, resetTimer } = useStudyLatencyTimer(study.card?.id)
  useStudyKeyboardShortcuts({ study, elapsedMs, resetTimer })
  useStudyNavigationGuard(study.hasUncommittedReviews)

  return (
    <div className="flex h-screen flex-col bg-background">
      <StudyHeaderToolbar study={study} />
      <main className="flex-1 overflow-hidden">
        <StudyCardRendererFrame card={study.card} isRevealed={study.isRevealed} />
      </main>
      <StudyBottomBar study={study} elapsedMs={elapsedMs} onAnswer={resetTimer} />
      {/* Dialogs... */}
    </div>
  )
}
```

---

### 5.4 Cách ly Tầng Quản lý Phiên Bền vững (`useStudyCommitAuthority` & `useStudySessionStore`)
Để bảo vệ an toàn cho thuật toán SRS SuperMemo SM-2 và cơ chế commit receipt:
1. **`useStudyCommitAuthority.ts` (< 250 LOC)**:
   - Quản lý giao tiếp với backend commit authority.
   - Xác thực schema biên nhận lệnh `study_authority_command_receipts` (`v1` và `v2`).
   - Quản lý hàng đợi offline retry và phát tín hiệu beacon thoát phiên (`sendBeacon` / `fetch` với `keepalive`).
2. **`useStudySessionStore.ts` (< 250 LOC)**:
   - Quản lý cơ sở dữ liệu IndexedDB `flama-study` (phiên bản v2).
   - Quản lý việc lưu trữ trạng thái phiên học, cách ly phiên lỗi (`quarantineStudySession`) và khôi phục phiên học sau sự cố.
3. **`useStudySession.ts` (Headless Facade < 300 LOC)**:
   - Điều phối giữa Web Locks lease (`useStudySessionLease`), IndexedDB store và Commit Authority.
   - Cung cấp public API tinh gọn: `session`, `view`, `isLoading`, `isBusy`, `error`, `leaseConflict`, `answer`, `prepareDecision`, `undo`, `commit`, `reloadSession`.

---

## CHƯƠNG 6: R5 — CHÍNH SÁCH "ZERO-TOUCH / GIỮ NGUYÊN HIỆN TRẠNG" (>= 70% BẢO TOÀN)

### 6.1 Chứng minh Định lượng Toàn vẹn (Proof of 84.6% Frozen Files)
Để loại trừ rủi ro phân mảnh và bảo toàn tuyệt đối tiến độ dự án, chúng tôi áp dụng chính sách **Zero-Touch** với kiểm chứng định lượng trên toàn bộ cây thư mục mã nguồn `frontend/src/`:

```
TỔNG SỐ LƯỢNG TỆP MÃ NGUỒN FRONTEND:
  - Tổng số tệp TypeScript/TSX: 441 tệp (121,413 LOC)
  - Tệp kiểm thử (Test TS/TSX): 97 tệp (24,742 LOC)
  - Tệp mã nguồn sản xuất (Source TS/TSX): 344 tệp (96,671 LOC)

PHÂN BỔ PHẠM VI REFACTORING:
  - Tệp trong phạm vi Phẫu thuật & Tái cấu trúc: 53 tệp (15.4%)
    (C01 Transport/Bootstrap + G01 Primitives/Aliases + Browse Hotspot + Worksheets Hotspot)
  - Tệp trong diện Đóng băng Giữ nguyên Hiện trạng (Zero-Touch): 291 tệp (84.6%)

KẾT QUẢ ĐẠT ĐƯỢC:
  84.6% >= 70.0% (VƯỢT CHỈ TIÊU BẢO TOÀN TỐI THIỂU 14.6%)
```

### 6.2 Danh mục Chi tiết 20 Miền Nghiệp vụ Đóng băng Tuyệt đối
Toàn bộ mã nguồn thuộc 20 thư mục/miền sau đây được **ĐÓNG BĂNG 100%**, nghiêm cấm mọi hành vi sửa đổi, đổi tên hay refactor "tiện tay" trong đợt di trú này:

| Miền Nghiệp vụ Đóng băng | Số Tệp Source | Dòng Mã (LOC) | Lý do Đóng băng An toàn |
|---|---|---|---|
| 1. `features/guide` | 13 | 3,749 | Module nội dung hướng dẫn tĩnh, hoạt động hoàn hảo, 0 rủi ro state. |
| 2. `features/onboarding` | 7 | 1,577 | Luồng giới thiệu người dùng mới, selectors/storage keys ổn định. |
| 3. `features/support` | 5 | 2,767 | Giao diện hỗ trợ và ticket, liên kết chặt chẽ với backend support API. |
| 4. `data/` (Legal Data) | 1 | 1,000 | Tệp dữ liệu điều khoản pháp lý `legalDocumentsData.ts`, hoàn toàn tĩnh. |
| 5. `features/auth` | 12 | 1,540 | Luồng xác thực đăng nhập/đăng ký cơ bản, đã ổn định. |
| 6. `features/oauth` | 2 | 422 | Luồng OAuth Consent & Provider callbacks, nhạy cảm bảo mật. |
| 7. `features/orders` | 1 | 280 | Quản lý đơn hàng & thanh toán payOS, logic giao dịch quan trọng. |
| 8. `features/wallet` | 6 | 475 | Ví Flama xu & lịch sử số dư, logic tiền tệ nhạy cảm. |
| 9. `features/statistics` | 5 | 887 | Biểu đồ thống kê học tập, timezone calculations đã tối ưu ở backend. |
| 10. `features/library` | 1 | 941 | Thư viện deck cá nhân, hoạt động ổn định. |
| 11. `features/profile` | 13 | 2,294 | Quản lý thông tin cá nhân, avatar upload, creator verification. |
| 12. `features/deck-collaboration` | 9 | 3,892 | Hợp tác biên soạn deck, conflict resolution engine đã test chặt chẽ. |
| 13. `features/mcp` | 9 | 1,733 | Quản lý MCP Tokens đã được tối ưu hoàn tất ở Phase 1 Pilot Migration. |
| 14. `features/settings` | 10 | 3,260 | Cài đặt mục tiêu học tập, Yomitan/AnkiConnect integration settings. |
| 15. `features/audio` | 16 | 4,836 | Flama Audio companion client, WebSocket bridge & audio playback. |
| 16. `features/import` | 17 | 5,242 | Anki import engine, Web Worker, IndexedDB storage. |
| 17. `features/note-types` | 8 | 2,650 | NoteType Editor, đã kết nối sang entity flashcard qua C02. |
| 18. `features/admin` | 22 | 9,231 | Bảng điều khiển quản trị hệ thống, người dùng và phân quyền. |
| 19. `features/marketplace` | 20 | 9,464 | Sàn chia sẻ deck cộng đồng, overlay clone model đã freeze. |
| 20. `features/dashboard` | 12 | 1,726 | Trang chủ Dashboard, heatmap & deck tree đã tối ưu ở đợt trước. |
| **TỔNG CỘNG ĐÓNG BĂNG** | **202** | **59,166** | *(Cùng 89 tệp layout, shell, pages tĩnh khác = 291 tệp)* |

### 6.3 Chính sách Quản lý Compatibility Shims & Vòng đời Tiêu hủy
1. **Nguyên tắc Re-export Shim**: Khi một component hoặc tiện ích được di chuyển sang vị trí mới theo chuẩn FSD, một tệp shim **BẮT BUỘC** phải được tạo tại vị trí cũ để bảo vệ các call-sites trong các module đóng băng:
   ```typescript
   // frontend/src/components/ui/button.tsx (Shim)
   export * from '@/shared/ui/shadcn/button'
   ```
2. **Không Thay đổi Implementation Trong Shim**: Shim chỉ thực hiện re-export thuần túy; tuyệt đối không chèn thêm runtime logic hoặc bọc wrapper mới.
3. **Vòng đời Tiêu hủy Shim (Deprecation Policy)**:
   - Các shims sẽ được duy trì xuyên suốt quá trình thực thi các gói C01, G01, FE-11, FE-12, FE-13, FE-19.
   - Việc dọn dẹp các shims chỉ được thực hiện tại gói nghiệm thu cuối cùng (**Gói C09 / FE-24**) sau khi toàn bộ hệ thống đã vượt qua bài kiểm tra tích hợp toàn diện.

---

## CHƯƠNG 7: R6 — KHUNG KIỂM THỬ TỰ ĐỘNG, TIÊU CHÍ NGHIỆM THU & PHÂN ĐỊNH TRÁCH NHIỆM

### 7.1 Bộ 5 Lệnh Kiểm tra Tự động Bắt buộc (Automated Quality Checklist)
Mỗi gói công việc trước khi bàn giao bắt buộc phải thực thi và vượt qua 100% bộ 5 lệnh kiểm tra chất lượng từ thư mục gốc của repository:

```powershell
# 1. Typecheck: Kiểm tra kiểu dữ liệu TypeScript (Yêu cầu: Exit code 0, 0 errors)
npm --prefix frontend run typecheck

# 2. Linter: Kiểm tra cú pháp và cảnh báo mã nguồn (Yêu cầu: Exit code 0, 0 errors)
npm --prefix frontend run lint

# 3. Build CI: Đóng gói kiểm tra bundle và code splitting (Yêu cầu: Exit code 0, PASS)
npm --prefix frontend run build:ci

# 4. Modular Python Test Runner: Chạy kiểm thử cho các module bị ảnh hưởng
.\.venv\Scripts\python.exe scripts/run_tests.py --module study,browse,audio --frontend-only
# Hoặc chạy kiểm thử đơn lẻ theo file/nhóm:
npm --prefix frontend test -- shared/ui
npm --prefix frontend test -- entities/flashcard app/studyContentSync
npm --prefix frontend test -- DeckWorksheetModal
npm --prefix frontend test -- printEngine

# 5. Production TypeScript AST Boundary Check: Kiểm tra ranh giới phân tầng FSD
npm --prefix frontend test -- contentPatchAdapter.adversarial.test.ts
```

---

### 7.2 Script Kiểm tra Ranh giới AST TypeScript (Production AST Boundary Checker)
Để đảm bảo không có bất kỳ import ngược tầng nào (ví dụ: `shared` import `app` hay `features/browse` import `features/study`), dự án áp dụng script kiểm tra cây cú pháp trừu tượng (TypeScript Compiler API) tương tự cơ chế đã kiểm chứng tại `contentPatchAdapter.adversarial.test.ts`:

```typescript
// scripts/verify-fsd-boundaries.ts
import * as ts from 'typescript'
import * as fs from 'fs'
import * as path from 'path'

interface BoundaryViolation {
  file: string
  line: number
  importPath: string
  reason: string
}

const FORBIDDEN_RULES = [
  {
    sourcePattern: /^frontend\/src\/shared\//,
    forbiddenTarget: /^@\/(app|features|entities|pages|widgets)\//,
    reason: 'Layer Violation: shared/ must NOT import from higher layers.',
  },
  {
    sourcePattern: /^frontend\/src\/entities\//,
    forbiddenTarget: /^@\/(app|features|pages|widgets)\//,
    reason: 'Layer Violation: entities/ must NOT import from higher layers.',
  },
  {
    sourcePattern: /^frontend\/src\/features\/browse\//,
    forbiddenTarget: /^@\/features\/study\//,
    reason: 'Cross-Feature Violation: browse must NOT import study internals directly.',
  },
  {
    sourcePattern: /^frontend\/src\/features\/study\//,
    forbiddenTarget: /^@\/features\/browse\//,
    reason: 'Cross-Feature Violation: study must NOT import browse internals directly.',
  },
]

export function checkFsdBoundaries(rootDir: string): BoundaryViolation[] {
  const violations: BoundaryViolation[] = []
  // Duyệt cây thư mục và phân tích ts.SourceFile...
  // Kiểm tra toàn bộ ts.isImportDeclaration, ts.isExportDeclaration, ts.isCallExpression (dynamic import)
  return violations
}
```

---

### 7.3 Ma trận Phân định Quyền Sở hữu Mã nguồn (Codex vs Gemini Code Ownership)
Để loại trừ triệt để xung đột mã nguồn (merge conflicts) và đảm bảo an toàn tuyệt đối cho hệ thống, trách nhiệm được phân chia rõ ràng theo nguyên tắc:

- **Codex**: Đóng vai trò Kiến trúc sư Trưởng (Lead Architect & Controller Owner). Độc quyền sở hữu các hợp đồng dữ liệu, DTOs, network transport, thuật toán SRS, Web Locks lease, IndexedDB storage, công thức toán học hình học in ấn, và đóng vai trò người duyệt review diff (`Accepted`).
- **Gemini**: Đóng vai trò Chuyên gia Tái cấu trúc Giao diện (UI Implementation Worker). Sở hữu việc bẻ nhỏ các components, wizard steps, form presentation, tách toolbar, responsive mobile tabs, thiết lập shims tương thích và cập nhật cấu hình `components.json`.

| Phân vùng Kiến trúc | Trách nhiệm Sở hữu (Owner) | Danh mục Tệp Sở hữu Độc quyền | Quy tắc An toàn Bắt buộc |
|---|---|---|---|
| **Foundation Transport & Session** | **Codex** | • `shared/api/client.ts`<br>• `shared/api/session.ts`<br>• `shared/api/bootstrap.ts` | Bảo vệ backend endpoint `GET /session`, CSRF token handshake và `bootstrapQueryKey`. |
| **UI Primitives Consolidation** | **Gemini** | • `shared/ui/shadcn/*.tsx`<br>• `shared/lib/utils.ts`<br>• `frontend/components.json`<br>• Shims tại `components/ui/*.tsx` | Bảo toàn 100% token OKLCH, styles Radix UI, và cập nhật chính xác aliases generator. |
| **Browse Controllers & Facade** | **Codex / Joint** | • `features/browse/hooks/useBrowseFilters.ts`<br>• `features/browse/hooks/useBrowseSelection.ts`<br>• `features/browse/hooks/useBrowseCardEditor.ts`<br>• `features/browse/hooks/useBrowseState.ts` | Bảo toàn query keys, cache invalidation, O(1) selection Set và headless sync port. |
| **Browse UI Workspace & Editor** | **Gemini** | • `features/browse/pages/BrowsePage.tsx`<br>• `features/browse/components/BrowseCardEditor.tsx`<br>• `features/browse/components/BrowseAudioDropdownMenu.tsx`<br>• `features/browse/components/BrowseMobileTabBar.tsx` | Tích hợp primitive `CardFieldsForm.tsx`, giữ nguyên layout 3 pane và phím tắt. |
| **Worksheets Geometry & Print Engine** | **Codex** | • `features/worksheets/utils/gridGeometry.ts`<br>• `features/worksheets/utils/printEngine.tsx`<br>• `features/worksheets/utils/kanjiSvgCache.ts` | Đảm bảo tính đúng đắn của công thức toán học tọa độ A4 (96 DPI) và latch `@media print`. |
| **Worksheets Studio Wizard UI** | **Gemini** | • `features/worksheets/components/DeckWorksheetModal.tsx`<br>• `features/worksheets/components/steps/*`<br>• `features/worksheets/components/renderers/*`<br>• `features/worksheets/hooks/useWorksheetStudio.ts` | Phân rã Bước 4 thành 5 step components (< 300 LOC mỗi tệp), bảo toàn kết quả in. |
| **Study Durability Core & SRS Engine** | **Codex** | • `features/study/session/*`<br>• `features/study/hooks/useStudySession.ts`<br>• `features/study/hooks/useStudySessionLease.ts`<br>• `entities/flashcard/model/*` | Khóa chặt Template Immutability, bảo vệ Web Locks lease và IndexedDB quarantine. |
| **Study UI Presentation Shell** | **Gemini** | • `features/study/pages/StudyPage.tsx`<br>• `features/study/interactions/*`<br>• `features/study/components/*` | Đưa `StudyPage.tsx` về < 200 LOC, giữ nguyên phím tắt học thẻ và zero visual regression. |

---

### 7.4 Bảng Điểm Tiêu chí Nghiệm thu Tổng hợp (Acceptance Criteria Scorecard)

Mỗi milestone hoàn tất sẽ được đánh giá trên thang điểm nghiệm thu khách quan:

| Tiêu chuẩn Nghiệm thu | Chỉ số Mục tiêu (Target Metric) | Phương thức Kiểm chứng | Kết quả Kỳ vọng |
|---|---|---|---|
| **1. Tỷ lệ Bảo toàn Zero-Touch** | $\ge 70.0\%$ (Thực tế đạt **84.6%**) | Script phân tích AST toàn bộ tệp source. | Đóng băng nguyên vẹn 291 / 344 tệp source. |
| **2. Giới hạn Kích thước Tệp (LOC Budget)** | Tất cả các tệp mới/tái cấu trúc $< 400\text{ LOC}$ (Step $< 300\text{ LOC}$) | `Measure-Object -Line` trên từng tệp mục tiêu. | 100% tệp tuân thủ ngân sách dòng mã. |
| **3. Type Safety & Linting** | 0 lỗi TypeScript, 0 lỗi linter mới | `npm run typecheck` & `npm run lint`. | Exit code 0 hoàn hảo. |
| **4. Bundle Build & Code Splitting** | Build bundle CI thành công | `npm run build:ci`. | Build hoàn tất trong < 10s, code chunks hợp lệ. |
| **5. Regression Unit & Integration Tests** | 100% tests pass (Study, Browse, Worksheets, Primitives) | Python modular test runner & Vitest. | 0 test failures, 0 regressions. |
| **6. Ranh giới Phân tầng FSD** | 0 lỗi import ngược tầng hoặc xuyên ngang feature | AST Boundary Check script. | Đạt chuẩn 6 tầng FSD tuyệt đối. |
| **7. Hợp đồng Template Immutability** | Template không bị mutate giữa active lease | Unit test `sessionStore.test.ts`. | Template frozen, card content patched live. |
| **8. Zero Visual Regression** | Màu sắc OKLCH, gradient, layout vị trí, font, padding giữ nguyên 100% | Đối chiếu ảnh chụp màn hình Chrome isolated profile. | Giao diện pixel-perfect, không xô lệch bản in PDF. |

---

## KẾT LUẬN & ĐỀ NGHỊ BÀN GIAO

Bản kế hoạch đặc tả kỹ thuật này đã giải quyết toàn diện, triệt để và khả thi 100% các yêu cầu kiến trúc đặt ra:
1. **Hoàn tất chuẩn mực Gate C00**, tháo gỡ dứt điểm 8 findings (R1–R8) của Codex từ đợt review trước.
2. **Thiết lập lộ trình phẫu thuật chi tiết cho 2 điểm nóng cồng kềnh nhất** (`useBrowseState` và `DeckWorksheetModal`), đưa kích thước toàn bộ các tệp thành phần về mức an toàn dưới 300–400 dòng mã.
3. **Bảo vệ tính bền vững của phiên học Study Session**, khóa chặt nguyên tắc Template Immutability và cách ly hoàn toàn SRS state machine.
4. **Bảo toàn 84.6% số tệp mã nguồn ổn định** thông qua chính sách Zero-Touch và hệ thống compatibility shims.
5. **Thiết lập khung kiểm thử tự động 5 bước** cùng script kiểm tra ranh giới AST TypeScript sản xuất.

**Tài liệu này được xuất bản hoàn chỉnh tại `docs/task/frontend-migration/FLAMA_FRONTEND_HIGH_ROI_SPECIFICATION_PLAN_2026-10-05.md` và sẵn sàng để Codex tiến hành thẩm định và phê duyệt chính thức.**
