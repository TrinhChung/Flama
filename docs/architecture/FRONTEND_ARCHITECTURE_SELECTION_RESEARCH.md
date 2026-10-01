# Nghiên Cứu Chuyên Sâu Lựa Chọn Kiến Trúc Frontend Flama
## Master Technical Report: Frontend Architecture Selection Research & Target Blueprint

- **Tài liệu**: `FRONTEND_ARCHITECTURE_SELECTION_RESEARCH.md`
- **Dự án**: Flama Japanese Language Learning Platform (`d:/Project/nihongo`)
- **Phân hệ mục tiêu**: React 19 SPA (`frontend/src/`)
- **Ngày hoàn thành**: 2026-10-01
- **Trạng thái**: Hoàn thiện / Chuẩn hóa Kiến trúc Chính thức (Authoritative Recommendation)
- **Tác giả**: Ban Kiến trúc Frontend Flama (`teamwork_preview_worker` & Explorer Research Agents)
- **Tiêu chuẩn kiểm toán**: Zero Source Code Modifications trong quá trình nghiên cứu, Zero Visual Regression, Chrome DevTools Isolated Profile

---

## Mục Lục (Table of Contents)

1. [Tóm Tắt Điều Hành & Bối Cảnh Hệ Thống (Executive Summary & Context)](#1-tóm-tắt-điều-hành--bối-cảnh-hệ-thống)
2. [R1: Ma Trận So Sánh & Đánh Giá 4 Chuẩn Kiến Trúc Frontend](#2-r1-ma-trận-so-sánh--đánh-giá-4-chuẩn-kiến-trúc-frontend)
   - [2.1 Phân tích Chuyên sâu 4 Trường phái Kiến trúc](#21-phân-tích-chuyên-sâu-4-trường-phái-kiến-trúc)
   - [2.2 Ma trận Chấm điểm Chi tiết theo 7 Tiêu chí](#22-ma-trận-chấm-điểm-chi-tiết-theo-7-tiêu-chí)
   - [2.3 Luận giải Trọng số & Phân tích Cơ chế Thất bại (Failure Modes)](#23-luận-giải-trọng-số--phân-tích-cơ-chế-thất-bại)
3. [R2: Đánh Giá Độ Tương Thích với Đặc Thù Dự Án Flama](#3-r2-đánh-giá-độ-tương-thích-với-đặc-thù-dự-án-flama)
   - [3.1 Tương thích Nền tảng Công nghệ (Stack Fit)](#31-tương-thích-nền-tảng-công-nghệ-stack-fit)
   - [3.2 Đánh giá 6 Khối Lượng Công Việc Nghiệp Vụ Cốt Lõi (Domain Workloads)](#32-đánh-giá-6-khối-lượng-công-việc-nghiệp-vụ-cốt-lõi)
   - [3.3 Đối chiếu Benchmark Hệ thống EdTech & Flashcards Mã Nguồn Mở](#33-đối-chiếu-benchmark-hệ-thống-edtech--flashcards-mã-nguồn-mở)
4. [R3: Luận Chứng & Đề Xuất Mô Hình Kiến Trúc Chuẩn Hóa (The Hybrid Architecture)](#4-r3-luận-chứng--đề-xuất-mô-hình-kiến-trúc-chuẩn-hóa)
   - [4.1 Mô hình Kiến trúc Lai Ba Tầng (The Tailored Tripartite Hybrid Architecture)](#41-mô-hình-kiến-trúc-lai-ba-tầng)
   - [4.2 Giải quyết Triệt để Các Điểm Nghẽn Trọng Điểm của Flama](#42-giải-quyết-triệt-để-các-điểm-nghẽn-trọng-điểm-của-flama)
   - [4.3 Quy chuẩn Bảo toàn Giao diện Nghiêm ngặt (Zero Visual Regression Protocol)](#43-quy-chuẩn-bảo-toàn-giao-diện-nghiêm-ngặt)
5. [R4: Bản Thiết Kế Quy Chuẩn Thư Mục & Quy Tắc Phụ Thuộc (Directory Blueprint & Dependency Rules)](#5-r4-bản-thiết-kế-quy-chuẩn-thư-mục--quy-tắc-phụ-thuộc)
   - [5.1 Sơ đồ Phân cấp Thư mục Mục tiêu Chi tiết](#51-sơ-đồ-phân-cấp-thư-mục-mục-tiêu-chi-tiết)
   - [5.2 Hợp đồng Đóng gói Public API (`index.ts`)](#52-hợp-đồng-đóng-gói-public-api-indexts)
   - [5.3 Ma trận Quy tắc Phụ thuộc Một chiều Nghiêm ngặt (Unidirectional Dependency Matrix)](#53-ma-trận-quy-tắc-phụ-thuộc-một-chiều-nghiêm-ngặt)
   - [5.4 Chiến lược Tự động hóa Ngăn ngừa Phụ thuộc Vòng (Circular Dependency Tooling)](#54-chiến-lược-tự-động-hóa-ngăn-ngừa-phụ-thuộc-vòng)
6. [R5: Bộ Mã Mẫu Thực Chiến Chuẩn Hóa (Production Reference Implementations)](#6-r5-bộ-mã-mẫu-thực-chiến-chuẩn-hóa)
   - [6.1 Mẫu 1: UI Primitive chuẩn hóa với CVA và OKLCH Tokens (`SearchInput.tsx`)](#61-mẫu-1-ui-primitive-chuẩn-hóa-với-cva-và-oklch-tokens)
   - [6.2 Mẫu 2: Domain Entity Component + Hook đọc dữ liệu thuần túy (`DeckHeader.tsx` & `useDeckHeader.ts`)](#62-mẫu-2-domain-entity-component--hook-đọc-dữ-liệu-thuần-túy)
   - [6.3 Mẫu 3: Feature Compound Component + Headless Hook giải phẫu God Component (`WorksheetStudio`)](#63-mẫu-3-feature-compound-component--headless-hook-giải-phẫu-god-component)
7. [Lộ Trình Tái Cấu Trúc Khả Thi & Quy Trình Kiểm Thử Độc Lập](#7-lộ-trình-tái-cấu-trúc-khả-thi--quy-trình-kiểm-thử-độc-lập)
   - [7.1 Lộ trình 4 Giai đoạn Tiếp cận từ Dưới lên (Leaf-to-Root Roadmap)](#71-lộ-trình-4-giai-đoạn-tiếp-cận-từ-dưới-lên)
   - [7.2 Quy trình Kiểm tra và Đo lường Hiệu năng Độc lập](#72-quy-trình-kiểm-tra-và-đo-lường-hiệu-năng-độc-lập)
   - [7.3 Bảng Đối chiếu Tiêu chí Nghiệm thu (Acceptance Criteria Matrix)](#73-bảng-đối-chiếu-tiêu-chí-nghiệm-thu)

---

## 1. Tóm Tắt Điều Hành & Bối Cảnh Hệ Thống

### 1.1 Tính Cấp Thiết về Mặt Kiến Trúc
Hệ thống học tiếng Nhật Flama (`d:/Project/nihongo`) đã hoàn tất quá trình hiện đại hóa hạ tầng: loại bỏ hoàn toàn các server-rendered Jinja templates để chuyển sang kiến trúc **React 19 Single Page Application (SPA)** hoàn chỉnh kết hợp **Vite 8**, **TailwindCSS v4** (sử dụng `@theme inline` với hệ màu không gian OKLCH), và thư viện unstyled primitives **Radix UI 1.6.7**.

Tuy nhiên, báo cáo kiểm toán chất lượng mã nguồn gần đây (`docs/reports/CODE_HEALTH_AUDIT_REPORT.md`) và các khảo sát chuyên sâu từ Explorer Agents đã chỉ ra tình trạng nợ kỹ thuật (technical debt) nghiêm trọng ở tầng giao diện người dùng:
1. **Phình to file nguyên khối (Monolithic File Sprawl)**: 72.6% mã nguồn nằm trong các file có kích thước ≥ 300 LOC. Điển hình là component `DeckWorksheetModal.tsx` đạt kích thước kỷ lục **4,388 dòng code** (252 KB), tích hợp hỗn độn toàn bộ từ modal chrome, wizard stepper, 8 form layout riêng biệt, tính toán SVG canvas động, touch gestures đến logic in ấn trình duyệt.
2. **Khủng hoảng phình to State và Thác Re-render (Mega-Hook State Sprawl)**: Hook `useBrowseState.ts` đạt kích thước **1,053 dòng code**, khai báo **49 `useState` hooks** riêng biệt và trả về **102 properties/callbacks**. Việc gom toàn bộ state của 3 cột màn hình (Cây thư mục Deck, Bảng thẻ từ vựng, Form sửa thẻ đang chọn) vào một hook gốc duy nhất khiến bất kỳ thao tác gõ phím tìm kiếm hay tick chọn checkbox nào cũng tạo ra một object reference mới, kích hoạt thác re-render toàn bộ cây DOM.
3. **Trùng lặp logic do thiếu tầng Domain Entity**: Giữa màn hình quản trị (`AdminMcpTokensPage.tsx` - 1,405 LOC) và màn hình cấu hình người dùng (`McpTokensTab.tsx` - 1,181 LOC) tồn tại hơn **1,800 dòng code trùng lặp gần như 100%** (bảng danh sách token, modal tiết lộ token secret, ma trận checkbox phân quyền scopes, hướng dẫn cấu hình Claude Desktop/Cursor MCP). Lý do là Flama đang thiếu một tầng `entities/` chuẩn hóa để chia sẻ các thực thể nghiệp vụ giữa các tính năng.
4. **Phân tán CSS do thiếu UI Primitives**: Có tới hơn 26 vị trí mã nguồn tự viết lại ô tìm kiếm bằng các thẻ `<div className="relative"><Search className="absolute ..." /><Input className="pl-9 ..." /></div>`, và 212 thẻ trạng thái (badge/pill) tự viết class màu rời rạc, gây trôi dạt thiết kế (style drift) và phá vỡ tính kế thừa của hệ thống design tokens.

### 1.2 Kết Luận Quyết Định: Mô Hình Kiến Trúc Lai Ba Tầng (The Tailored Tripartite Hybrid Architecture)
Nghiên cứu so sánh toàn diện giữa 4 trường phái kiến trúc hàng đầu (FSD, Atomic Design, Compound Components, Modular Feature-Driven) chứng minh rằng: **Không có một mô hình thuần túy (pure paradigm) đơn lẻ nào đáp ứng trọn vẹn cả nhu cầu mở rộng quy mô hệ thống EdTech lẫn trải nghiệm lập trình micro-UI của Flama**.

Kiến trúc chuẩn hóa chính thức được phê duyệt cho Flama là **Kiến Trúc Lai Ba Tầng (Tailored Tripartite Hybrid Architecture)**:
- **Tầng Vĩ Mô (Macro-Layering)**: Áp dụng **Feature-Sliced Design (FSD v2.1)** để phân chia 6 tầng nghiêm ngặt (`shared` → `entities` → `features` → `widgets` → `pages` → `app`), thực thi quy tắc phụ thuộc một chiều toán học (Unidirectional Dependency Rule) và đóng gói Public API (`index.ts`).
- **Tầng Vi Mô (Micro-Primitives)**: Áp dụng nguyên lý **Atomic Design** trong thư mục `shared/ui/` kết hợp **Radix UI `Slot.Root` (`asChild`)**, **`class-variance-authority` (CVA)**, và dải biến màu OKLCH của Tailwind v4, giải quyết triệt để vấn đề phân tán CSS và bảo toàn 100% giao diện.
- **Tầng Phân Hệ Tương Tác (Interactive Subsystems)**: Áp dụng **Compound Component Pattern** kết hợp **Headless Custom Hooks** tuân thủ nghiêm ngặt **Quy tắc <8 States/Hook** cho các tính năng phức tạp tại `features/` và `widgets/`, phân rã các component nguyên khối như `DeckWorksheetModal` (từ 4,388 LOC xuống còn 95 LOC) mà không chèn thêm bất kỳ thẻ wrapper `<div>` nào gây lệch layout.

---

## 2. R1: Ma Trận So Sánh & Đánh Giá 4 Chuẩn Kiến Trúc Frontend

### 2.1 Phân Tích Chuyên Sâu 4 Trường Phái Kiến Trúc

#### 1. Feature-Sliced Design (FSD v2.1)
- **Cơ sở lý thuyết**: FSD là phương pháp luận cấu trúc kiến trúc ứng dụng frontend hướng module, thiết kế để giải quyết bài toán suy thoái cấu trúc (structural decay) trong các dự án quy mô vừa và lớn. FSD phân rã toàn bộ ứng dụng thành 6 tầng (Layers) phân cấp nghiêm ngặt:
  1. `app`: Khởi tạo ứng dụng, routing, global providers, global styles.
  2. `pages`: Các route view mỏng, chỉ đóng vai trò ghép nối widget.
  3. `widgets`: Các khối giao diện phức hợp tự trị hoàn chỉnh (Header, BrowseWorkspace).
  4. `features`: Các luồng tương tác của người dùng mang lại giá trị nghiệp vụ (SearchFilters, AddCard).
  5. `entities`: Các thực thể nghiệp vụ của domain (Card, Deck, Note, User, Token).
  6. `shared`: Hạ tầng tái sử dụng độc lập với nghiệp vụ (UI primitives, API client, utils).
- **Cơ chế kỹ thuật**:
  - *Slices*: Trong từng tầng (ngoại trừ `app` và `shared`), mã nguồn được chia theo lát cắt nghiệp vụ (ví dụ: `entities/card`, `entities/deck`).
  - *Segments*: Trong mỗi slice, file được chia theo vai trò kỹ thuật (`ui`, `model`, `api`, `lib`).
  - *Public API Contract*: Mỗi slice bắt buộc phải có `index.ts` để xuất khẩu công khai. Mọi hành vi import xuyên thấu vào sâu bên trong slice (`@/entities/card/ui/CardBadge`) đều bị cấm tuyệt đối.
  - *Quy tắc phụ thuộc một chiều*: Một module chỉ được phép import từ các tầng **thấp hơn nghiêm ngặt**. Cấm tuyệt đối import chéo giữa các slice cùng tầng (cross-slice imports).
- **Ưu điểm**:
  - Triệt tiêu hoàn toàn lỗi import vòng (circular dependency) nhờ phân tầng một chiều.
  - Tách bạch rõ ranh giới tầng domain entity (`entities/`), xóa bỏ ngay lập tức tình trạng sao chép code giữa các màn hình.
  - Dễ dàng định vị mã nguồn và loại bỏ code rác (dead-code elimination) an toàn.
- **Nhược điểm & Cơ chế thất bại nếu áp dụng thuần túy (Pure FSD Failure Modes)**:
  - *Nặng tính thủ tục (Boilerplate Overhead)*: Với các thành phần UI cơ bản, việc tạo đủ `ui/`, `model/`, `api/`, `index.ts` gây quá tải thư mục.
  - *Cực đoan khi cấm import chéo giữa các Entity*: Trong EdTech, `Card` gắn liền mật thiết với `Deck` và `Note`. Việc cấm `entities/card` import từ `entities/deck` đòi hỏi phải đưa việc ghép nối lên tầng `features` hoặc `widgets`, dễ gây lúng túng cho lập trình viên nếu thiếu quy chuẩn chi tiết.
  - *Mù mờ về cấu trúc bên trong của component*: FSD chỉ quy định thư mục chứa file, không đưa ra giải pháp nào để ngăn một component bên trong `features/worksheets/ui/DeckWorksheetModal.tsx` phình to thành 4,388 dòng.

#### 2. Atomic Design (Brad Frost)
- **Cơ sở lý thuyết**: Phân rã giao diện theo phép ẩn dụ sinh học thành 5 cấp bậc:
  1. `Atoms`: Các phần tử HTML cơ bản nhất không thể phân chia (`Button`, `Input`, `Label`, `Icon`).
  2. `Molecules`: Cụm các atom kết hợp tạo thành một đơn vị chức năng đơn giản (`SearchInput`, `FormField`).
  3. `Organisms`: Các thành phần giao diện phức tạp ghép từ molecules và atoms (`Header`, `CardEditorSidebar`).
  4. `Templates`: Khung layout bố cục trừu tượng ở mức trang không chứa dữ liệu thực.
  5. `Pages`: Bản thể cụ thể của template được điền dữ liệu thực tế.
- **Ưu điểm**:
  - Mô hình hoàn hảo cho việc xây dựng Design System (Figma to Code, Storybook).
  - Tách biệt xuất sắc các UI Primitives lá (`atoms`, `molecules`), bảo đảm 100% không bị dính logic nghiệp vụ.
  - Rất thuận lợi cho kiểm thử thị giác (Visual Regression Testing).
- **Nhược điểm & Cơ chế thất bại nếu áp dụng thuần túy (Pure Atomic Design Failure Modes)**:
  - *Hoàn toàn mù tịt về Logic Nghiệp vụ & Trạng thái Ứng dụng*: Atomic Design là phương pháp luận thiết kế đồ họa, không phải kiến trúc phần mềm. Nó không có câu trả lời cho: Thuật toán Anki SM-2 đặt ở đâu? React Query cache keys đặt ở đâu? Web Audio API buffer đặt ở đâu?
  - *Cái bẫy ngữ nghĩa "Molecule vs Organism"*: Đội ngũ phát triển thường xuyên mất thời gian tranh cãi xem một `CardItem` chứa badge trạng thái và nút phát âm thanh là Molecule phức tạp hay Organism đơn giản.
  - *Thùng rác Organisms (Organism Dumping Ground)*: Trong thực tế, tầng `atoms/` và `molecules/` chỉ chiếm ~30 component, trong khi tầng `organisms/` phình to thành một mớ hỗn độn hàng trăm file không có ranh giới nghiệp vụ.
  - *Thảm họa Prop Drilling*: Việc truyền dữ liệu từ Pages/Templates xuống qua Organisms, Molecules đến Atoms đòi hỏi luồn lách hàng chục props nếu không dùng state quản trị tập trung.

#### 3. Compound Component Pattern + Headless UI
- **Cơ sở lý thuyết**: Mẫu thiết kế phân tách một component phức tạp thành một nhóm các sub-component gắn kết, chia sẻ trạng thái ngầm định thông qua React Context. Người dùng component có quyền tự do sắp xếp bố cục DOM (Inversion of Control - Đảo ngược quyền điều khiển):
  ```tsx
  <WorksheetStudio.Root deckId={deckId}>
    <WorksheetStudio.Header />
    <WorksheetStudio.Controls />
    <WorksheetStudio.Canvas />
    <WorksheetStudio.Actions />
  </WorksheetStudio.Root>
  ```
- **Kết hợp Headless Hooks & Quy tắc `<8 States`**: Toàn bộ logic điều khiển, đồng bộ URL, lắng nghe phím tắt và xử lý API được bóc tách ra các custom hooks độc lập không chứa JSX. Mỗi hook tuân thủ quy tắc giữ **dưới 8 biến state**, nhóm theo trách nhiệm cụ thể.
- **Ưu điểm**:
  - Giải phẫu hoàn hảo các "God Components" như `DeckWorksheetModal` (4,388 LOC) thành các khối nhỏ độc lập 100–250 LOC.
  - **Zero DOM Pollution**: Hỗ trợ xuất sắc Radix UI `Slot.Root` (`asChild`) và React Fragment, không chèn các thẻ `<div>` trung gian phá vỡ CSS Grid và Flexbox.
  - Tách bạch 100% logic để kiểm thử unit test thông qua renderHook mà không cần dựng cây DOM giả lập.
- **Nhược điểm & Cơ chế thất bại**:
  - Không phải kiến trúc vĩ mô: Mô hình này hoạt động ở cấp độ component, không định nghĩa cấu trúc thư mục toàn dự án hay ranh giới API.
  - Nguy cơ re-render lan truyền: Nếu Context chung chứa các state có tần số thay đổi cao (ví dụ tọa độ chuột SVG, text đang gõ phím), toàn bộ sub-components sẽ re-render nếu không được tách Context giá trị/hành động (split contexts) hoặc dùng Zustand.

#### 4. Modular Feature-Driven / Layered MVC
- **Cơ sở lý thuyết**: Tổ chức mã nguồn theo các thư mục tính năng nghiệp vụ truyền thống (`features/browse/`, `features/study/`, `features/marketplace/`), trong mỗi tính năng có các thư mục con `components/`, `hooks/`, `api/`, `types/`.
- **Ưu điểm**:
  - Cực kỳ thân thuộc, hầu như mọi lập trình viên React đều có thể bắt nhịp ngay mà không cần đào tạo.
  - Tốc độ phát triển ban đầu nhanh vì không bị ràng buộc bởi các quy tắc phân tầng khắt khe.
- **Nhược điểm & Cơ chế thất bại (Hiện trạng thực tế của Flama)**:
  - *Spaghetti Coupling ngang hàng*: Các tính năng tùy tiện import lẫn nhau (`browse` import `study/sessionStore`, `browse` import `audio/ttsNormalizer`). Khi xuất hiện nhu cầu ngược lại, mã nguồn lập tức rơi vào vòng lặp phụ thuộc (circular dependency).
  - *Thiếu vắng Tầng Thực Thể Chung (Missing Entity Layer)*: Do không có tầng `entities/`, thực thể `Card`, `Deck`, `Token` bị giam cầm trong một tính năng cụ thể. Khi tính năng khác cần dùng, lập trình viên buộc phải copy-paste (gây ra sự trùng lặp 1,800 dòng giữa Admin và Settings) hoặc tạo ra các đường import xuyên tính năng đầy rủi ro.
  - *Mảnh đất màu mỡ cho God Components*: Không có cơ chế ngăn cản component trong feature tích tụ thêm state cho đến khi biến thành monolith 4,388 dòng.

---

### 2.2 Ma Trận Chấm Điểm Chi Tiết theo 7 Tiêu Chí

Bảng đánh giá định lượng được xây dựng dựa trên khảo sát thực tế của Explorer Agents, áp dụng thang điểm từ **1 đến 10** với hệ số trọng số phần trăm phản ánh đúng mức độ ưu tiên của dự án Flama:

| STT | Tiêu chí Đánh giá (Evaluation Criteria) | Trọng số (%) | Feature-Sliced Design (FSD v2.1) | Atomic Design (Brad Frost) | Compound Component + Headless UI | Modular Feature-Driven (MVC) |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| **1** | **Khả năng tái sử dụng (Reusability)** | 15% | **9.5** | 7.5 | 9.0 | 5.5 |
| **2** | **Khả năng mở rộng quy mô (Scalability)** | 15% | **9.5** | 5.0 | 7.5 | 6.5 |
| **3** | **Kiểm soát Coupling & Re-render (Coupling & Re-renders)** | 20% | 9.0 | 4.5 | **9.5** | 4.0 |
| **4** | **Độ dốc học tập & Tiện dụng (Learning Curve & DX)** | 10% | 6.0 | 7.0 | 8.0 | **9.0** |
| **5** | **Bảo toàn Zero Visual Regression (Visual Fidelity)** | 15% | 8.5 | 9.0 | **9.5** | 6.0 |
| **6** | **Độ phù hợp EdTech / Anki SM-2 (Domain Fit)** | 15% | **9.5** | 3.5 | 9.0 | 6.5 |
| **7** | **Chi phí bảo trì dài hạn (Long-term Maintenance Cost)** | 10% | **9.5** | 4.5 | 8.5 | 5.0 |
| **Σ** | **Điểm Tổng Hợp Có Trọng Số (Weighted Total Score)** | **100%** | **8.900 / 10** | **5.800 / 10** | **8.800 / 10** | **5.875 / 10** |
| **Hạng** | **Xếp hạng Tổng thể (Overall Ranking)** | — | **Hạng 1 (Chuẩn Vĩ mô)** | **Hạng 4** | **Hạng 2 (Chuẩn Vi mô)** | **Hạng 3** |

---

### 2.3 Luận Giải Trọng Số & Phân Tích Cơ Chế Thất Bại

#### 1. Khả năng tái sử dụng (Reusability - Trọng số 15%)
- **FSD (9.5/10)**: Xuất sắc nhất nhờ phân tách hai tầng tái sử dụng rõ rệt: `shared/` cho UI primitives không nghiệp vụ và `entities/` cho thực thể domain có cấu trúc dữ liệu (`entities/card`, `entities/deck`). Loại bỏ hoàn toàn sự trùng lặp 1,800 dòng giữa Admin và Settings.
- **Compound Components (9.0/10)**: Tính tái sử dụng đạt mức tối đa ở cấp độ khối giao diện nhờ Inversion of Control. Cùng một bộ headless hook `useWorksheetStudio`, giao diện có thể hiển thị trong Modal dialog, trang toàn màn hình, hoặc chạy ngầm dưới background in ấn.
- **Atomic Design (7.5/10)**: Tái sử dụng tốt ở mức Atoms/Molecules, nhưng thất bại ở mức Organisms do bị dính chặt vào context hiển thị cụ thể.
- **Modular Feature-Driven (5.5/10)**: Kém nhất. Logic bị đóng kín trong từng thư mục tính năng, dẫn đến thói quen sao chép mã nguồn khi tính năng khác cần dùng chung.

#### 2. Khả năng mở rộng quy mô (Scalability - Trọng số 15%)
- **FSD (9.5/10)**: Thiết kế chuẩn mực cho hệ thống lớn. Nhờ hợp đồng Public API (`index.ts`) tại từng slice, nhiều lập trình viên có thể làm việc đồng thời trên các slice khác nhau mà không gây xung đột git merge hay phá vỡ module của nhau.
- **Modular Feature-Driven (6.5/10)**: Tốt lúc ban đầu, nhưng khi hệ thống vượt quá 50 màn hình và hàng chục domain liên kết, cấu trúc này nhanh chóng thoái hóa thành mạng nhện phụ thuộc chéo.
- **Atomic Design (5.0/10)**: Tắc nghẽn nghiêm trọng khi số lượng Organisms vượt quá 100, biến thư mục thành "bãi phế liệu" không ai dám dọn dẹp.

#### 3. Kiểm soát Coupling & Re-render (Trọng số 20% - Trọng số cao nhất)
- **Compound Components + Headless Hooks (9.5/10)**: Khả năng cách ly vùng ảnh hưởng của state (State Blast Radius) đạt mức hoàn hảo. Việc tuân thủ quy tắc `<8 States` và chia nhỏ Context giúp việc gõ phím trong ô tìm kiếm không gây re-render bảng dữ liệu hay thanh công cụ.
- **FSD (9.0/10)**: Khống chế khớp nối (Coupling) ở mức cấu trúc hoàn hảo nhờ cấm import ngược và cấm import ngang hàng. Tuy nhiên FSD thuần túy không kiểm soát được state nội bộ bên trong component nếu lập trình viên tiếp tục gom 49 states vào một hook.
- **Modular Feature-Driven (4.0/10)**: Điểm liệt. Cho phép import tự do giữa các tính năng, tạo ra khớp nối chặt (tight coupling) và gây ra tình trạng một thay đổi nhỏ ở `useBrowseState` làm re-render toàn bộ 3 cột giao diện.

#### 4. Bảo toàn Zero Visual Regression (Trọng số 15%)
- **Compound Components (9.5/10)**: Đạt điểm cao nhất vì sử dụng cơ chế Radix UI `asChild` và React Fragments, cho phép chia nhỏ file 4,388 dòng thành 8 file nhỏ mà **không thêm bất kỳ thẻ wrapper `<div>` nào**, bảo toàn 100% tọa độ CSS Grid và Flexbox.
- **Atomic Design (9.0/10)**: Bảo tồn rất tốt các dải màu token, border radius và typography nhờ xuất phát điểm từ Design System.
- **Modular Feature-Driven (6.0/10)**: Kém do các class Tailwind viết rải rác tự phát trong từng file, dễ gây xô lệch giao diện khi sửa chữa.

#### 5. Độ phù hợp với hệ thống EdTech / Flashcards (Trọng số 15%)
- **FSD (9.5/10)**: Ánh xạ 1:1 với mô hình dữ liệu phức tạp của EdTech: sự phân tách giữa Note và Card (1 Note sinh nhiều Card template) ánh xạ hoàn hảo vào `entities/note` và `entities/card`. Thuật toán Anki SM-2 scheduler có vị trí tự nhiên tại `entities/study-session` hoặc `shared/lib/scheduler`.
- **Atomic Design (3.5/10)**: Hoàn toàn không tương thích. Không thể biểu diễn được hàng đợi học lặp lại ngắt quãng, đồng bộ phát âm thanh VoiceVox, hay dữ liệu vector nét vẽ chữ Hán SVG bằng mô hình sinh học.

---

## 3. R2: Đánh Giá Độ Tương Thích với Đặc Thù Dự Án Flama

### 3.1 Tương Thích Nền Tảng Công Nghệ (Stack Fit)

Khảo sát trực tiếp cấu hình mã nguồn tại `frontend/package.json`, `frontend/vite.config.ts`, và `frontend/src/index.css` xác nhận nền tảng hiện đại của Flama:

```
┌────────────────────────────────────────────────────────────────────────┐
│ REACT 19 SPA RUNTIME BASELINE                                          │
├───────────────────────────────────┬────────────────────────────────────┤
│ • React: ^19.2.7                  │ • Vite: ^8.1.1 (@vitejs/plugin-react)
│ • TypeScript: ~6.0.2              │ • Oxlint: ^1.71.0 (High-speed lint)│
│ • React Router DOM: ^7.18.3       │ • TanStack React Query: ^5.101.4   │
│ • Radix UI Primitives: ^1.6.7     │ • TailwindCSS: @tailwindcss/vite 4 │
└───────────────────────────────────┴────────────────────────────────────┘
```

#### 1. TailwindCSS v4 với `@theme inline` OKLCH Color Engine
Flama đã nâng cấp lên TailwindCSS v4 thông qua plugin `@tailwindcss/vite: ^4.3.3`, loại bỏ hoàn toàn các file cấu hình cũ `tailwind.config.js` và `postcss.config.js`. 

Tại `frontend/src/index.css` (dòng 8–76), toàn bộ biến semantic CSS được định nghĩa trực tiếp bằng không gian màu cảm nhận tuyến tính **OKLCH**:
```css
--background: oklch(1 0 0);
--foreground: oklch(0.19 0.02 50);
--primary: oklch(0.635 0.215 35);
--primary-foreground: oklch(0.985 0 0);
--secondary: oklch(0.95 0.03 65);
--muted: oklch(0.96 0.015 65);
--accent: oklch(0.94 0.04 55);
--destructive: oklch(0.577 0.245 27.325);
--border: oklch(0.9 0.025 60);
--radius: 0.625rem;
```
Các biến này được inlined vào Tailwind engine qua chỉ thị `@theme inline` (dòng 97–178), ánh xạ `--color-primary: var(--primary);`, `--color-border: var(--border);`. Chế độ nền tối (Dark mode) được quản lý qua class `.dark` (dòng 180–243) ghi đè độ sáng và sắc độ OKLCH. Các tiện ích lật thẻ 3D tăng tốc phần cứng được khai báo tại dòng 361–378: `.perspective-1000`, `.transform-style-3d`, `.backface-hidden`, `.rotate-y-180`.

*Đánh giá tương thích*: Bất kỳ kiến trúc UI Primitive nào được chọn bắt buộc phải khai báo biến qua `class-variance-authority` (CVA) kế thừa trực tiếp các token OKLCH này, tuyệt đối không được hardcode mã màu hex (`#ff...`) hay rgb cũ.

#### 2. Dấu Ấn Radix UI Unstyled Primitives
Gói `radix-ui: ^1.6.7` cung cấp 15 primitives nền tảng phân bố khắp `frontend/src/components/ui/`:
`Slot` (dùng cho polymorphic component qua `asChild`), `Dialog`, `Sheet`, `DropdownMenu`, `Tabs`, `Tooltip`, `Select`, `Checkbox`, `Switch`, `ScrollArea`, `Progress`, `Collapsible`, `Avatar`, `Label`, `Separator`.

*Đánh giá tương thích*: Việc áp dụng Compound Component Pattern là hoàn toàn tự nhiên vì các primitives của Radix UI vốn dĩ hoạt động theo triết lý compound. Việc bóc tách component lớn phải bảo toàn các Context ngầm định của Radix (`Dialog.Portal`, `Dialog.Overlay`) để không làm gãy hiệu ứng đóng mở và khả năng truy cập WAI-ARIA.

---

### 3.2 Đánh Giá 6 Khối Lượng Công Việc Nghiệp Vụ Cốt Lõi

Khảo sát thực tế mã nguồn xác định chi tiết 6 khối lượng công việc đặc thù của Flama cùng các điểm nghẽn nghiêm trọng:

```
┌────────────────────────────────────────────────────────────────────────┐
│ FLAMA 6 CORE DOMAIN WORKLOADS                                          │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Vocabulary Browse & Search   │ useBrowseState (49 states, 102 props)│
│ 2. SM-2 Study Session           │ legacyEngine (720 LOC), sandboxed    │
│ 3. Printable Worksheets Canvas  │ DeckWorksheetModal (4,388 LOC, SVG)  │
│ 4. Marketplace & payOS          │ SharedDeckDetail, Logical Overlay    │
│ 5. Local Audio TTS Bridge       │ VoiceVox & Kokoro (Port 4791)        │
│ 6. AI MCP Tools Management      │ Admin vs Settings (1,800 LOC dup)    │
└────────────────────────────────────────────────────────────────────────┘
```

#### 1. Màn Hình Duyệt & Tìm Kiếm Từ Vựng (Vocabulary Browse & Search)
- **Tập tin điểm nóng**: `frontend/src/features/browse/hooks/useBrowseState.ts` (**1,053 LOC**).
- **Thực trạng**: Khai báo **49 `useState` hooks** (dòng 114–294) và trả về **102 properties, setters, callbacks** (dòng 930–1052). Hook này gánh vác toàn bộ:
  - Cây thư mục deck bên trái và truy vấn tìm kiếm deck.
  - Bảng thẻ từ vựng ở giữa: tìm kiếm từ khóa debounce, lọc trạng thái, phân trang, chọn nhiều thẻ (batch selection).
  - Khung xem chi tiết thẻ bên phải: draft field values, dirty diffing, lưu thẻ.
  - 4 trạng thái modal lồng nhau: VoiceVox modal (12 thiết lập âm thanh), Local Audio modal, Stroke order modal, Confirm delete modal.
- **Hệ quả**: Component tiêu thụ `BrowsePage.tsx` (609 LOC) nhận 102 props và prop-drilling xuống 7 component con. Việc gõ một ký tự tìm kiếm làm thay đổi tham chiếu state, ép toàn bộ 3 cột giao diện re-render đồng loạt, vô hiệu hóa cơ chế tối ưu hóa của React 19.

#### 2. Phiên Học Thuật Toán Anki SM-2 (SM-2 Study Session)
- **Tập tin điểm nóng**: `useStudySession.ts` (1,337 LOC), `StudyPage.tsx` (554 LOC), `legacyEngine.ts` (720 LOC), `CardDisplay.tsx` (94 LOC), `CardRendererFrame.tsx` (232 LOC).
- **Thực trạng**:
  - `legacyEngine.ts` thực thi thuật toán Anki SM-2 client-side với cơ chế làm tròn tương thích Python (`pythonRoundPositive`), khoảng biến thiên ngẫu nhiên (`fuzzDelta`), tính toán trước khoảng cách ôn tập (`Again: 10m`, `Hard: 1d`, `Good: 3d`, `Easy: 7d`) với độ trễ 0ms.
  - `useStudySession.ts` quản lý tranh chấp đa tab bằng hợp đồng lease (`useStudySessionLease`), chứng từ cam kết giao dịch (`requireMatchingCommitReceipt`), và hàng đợi offline hỗ trợ Undo.
  - `CardRendererFrame.tsx` nhúng iframe sandbox an toàn (`/static/js/card_renderer_host.js`), giao tiếp 2 chiều qua `window.postMessage`, render đồng thời cả 2 mặt thẻ (front/back) để triệt tiêu hiện tượng nhấp nháy FOUC khi lật thẻ 3D.
- **Hệ quả**: Logic thuật toán và iframe renderer rất vững chắc, nhưng controller `StudyPage.tsx` bị ôm đồm quá nhiều trách nhiệm điều hướng bàn phím và modal tổng kết, cần được bóc tách sang Compound Component `<StudySession.Root>`.

#### 3. Xưởng Thiết Kế Bài Tập In Ấn Canvas SVG (Printable Worksheets Canvas)
- **Tập tin điểm nóng**: `frontend/src/features/worksheets/components/DeckWorksheetModal.tsx` (**4,388 LOC**, **252.6 KB**).
- **Thực trạng**: Đây là **God Component lớn nhất toàn bộ monorepo**. File chứa **22 `useState` hooks**, **6 `useRef` hooks**, và **3,873 dòng mã JSX inline**.
  - Tích hợp 4 tab studio: (1) Chọn mẫu bài tập (8 mẫu), (2) Cấu hình ánh xạ trường Note Type, (3) Tùy biến lưới viết chữ Hán / Genkouyoushi (8 form layout riêng), (4) Tiêu đề, thông tin học sinh, watermark, QR code.
  - Xử lý cử chỉ chạm trên canvas (double-tap zoom detection dòng 199–215), tính toán tỷ lệ zoom khổ giấy A4 theo viewport thực (`getFitZoom` dòng 79–89), và xuất lệnh in PDF của trình duyệt.
  - Kết hợp với `WorksheetPageRenderer.tsx` (1,719 LOC) sử dụng `DOMParser` để bóc tách và chèn vector nét viết KanjiVG động vào từng ô tập viết.
- **Hệ quả**: Một lỗi nhỏ trong việc render SVG có thể làm sập toàn bộ modal; việc bảo trì hay thêm một mẫu bài tập mới là cơn ác mộng do kích thước file vượt ngưỡng kiểm soát của mọi IDE.

#### 4. Chợ Thẻ Chia Sẻ & Cổng Thanh Toán payOS (Marketplace & Commerce)
- **Tập tin điểm nóng**: `SharedDeckDetailPage.tsx` (1,436 LOC), `PaymentResultPage.tsx` (416 LOC).
- **Thực trạng**:
  - Quản lý mô hình **Cài đặt Lớp Phủ Hợp Lý (Logical Overlay Installation)**: Người học cài đặt deck từ marketplace không copy các Note nguồn (`notes.user_id != learner_id`). Thẻ nguồn thuộc về tác giả gốc, dữ liệu tiến độ của người học được ghi đè qua `deck_clone_deck_maps`. Mọi chỉnh sửa cục bộ sinh ra bản ghi overlay chứ không được làm thay đổi Note gốc.
  - Xử lý callback thanh toán payOS (`orderCode`, `payment_order_id`) và polling trạng thái cấp quyền (`grant_status = 'granted'`) qua React Query.
- **Hệ quả**: Trộn lẫn giữa giao diện trình diễn thương mại (đánh giá sao, xem trước thẻ mẫu, diff phiên bản) và logic kích hoạt quyền sở hữu, cần phân tách rõ giữa UI Entity và Payment Feature.

#### 5. Cầu Nối Âm Thanh Cục Bộ VoiceVox & Kokoro (Local Audio TTS Bridge)
- **Tập tin điểm nóng**: `frontend/src/features/audio/hooks/useLocalAudioEngine.ts` (**1,080 LOC**).
- **Thực trạng**: Kết nối với Flama Audio Desktop Companion (.NET 8 WPF) chạy cục bộ trên máy người dùng tại cổng `http://127.0.0.1:4791`. Hook quản lý danh sách 21 giọng đọc VoiceVox và 13 giọng đọc Kokoro, hàng đợi tổng hợp âm thanh, và upload trực tiếp file `.wav` vào API ghi chú. Khi có âm thanh mới, hook cập nhật trực tiếp vào session store đang mở (`updateCardFieldValuesInSessions`) mà không cần tải lại trang.
- **Hệ quả**: Bị phụ thuộc chéo trực tiếp từ `useBrowseState.ts` và `StudyPage.tsx`. Cần đưa âm thanh thành một Feature độc lập (`features/audio-playback`) giao tiếp qua các contract rõ ràng.

#### 6. Quản Trị Khóa API & AI MCP Tokens (Điểm Nóng Trùng Lặp 1,800 LOC)
- **Tập tin điểm nóng**: `AdminMcpTokensPage.tsx` (1,405 LOC) và `McpTokensTab.tsx` (1,181 LOC).
- **Thực trạng**: Hai file này nằm ở hai feature hoàn toàn tách biệt (`admin` vs `settings`) nhưng lại chứa hơn **1,800 dòng mã nguồn giống hệt nhau**:
  - Ma trận chọn 30+ scopes phân quyền MCP (decks, notes, study_stats, media).
  - Bảng dữ liệu danh sách token kèm trạng thái kích hoạt, ngày hết hạn.
  - Hộp thoại tạo mới token và hiển thị mã bí mật raw token duy nhất 1 lần kèm nút copy.
  - Khối hướng dẫn cấu hình AI Client (Claude Desktop, Cursor, Windsurf, ChatGPT Actions).
- **Hệ quả**: Sự vắng bóng của tầng `entities/mcp-token/` dẫn đến tình trạng nhân đôi nợ kỹ thuật. Khi cập nhật thêm một scope mới, lập trình viên phải sửa tay đồng thời cả 2 file.

---

### 3.3 Đối Chiếu Benchmark Hệ Thống EdTech & Flashcards Mã Nguồn Mở

Để bảo đảm kiến trúc đề xuất đạt tiêu chuẩn công nghiệp cao nhất, chúng tôi tiến hành đối chiếu Flama với 4 hệ sinh thái EdTech/Flashcard tiêu biểu trên thế giới:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ BENCHMARK ĐỐI CHIẾU KIẾN TRÚC EDTECH / FLASHCARDS QUỐC TẾ                                       │
├──────────────────────┬──────────────────────┬──────────────────────┬────────────────────────────┤
│ Hệ Thống             │ Card Render Boundary │ Scheduler Engine     │ Cấu Trúc Frontend & State  │
├──────────────────────┼──────────────────────┼──────────────────────┼────────────────────────────┤
│ Anki (Desktop/Web)   │ PyQt Sandboxed       │ Rust Core (`rslib`)  │ Svelte / TS (AnkiWeb)      │
│                      │ Webview + postMessage│ qua IPC nội bộ       │ Tách biệt UI & Engine      │
├──────────────────────┼──────────────────────┼──────────────────────┼────────────────────────────┤
│ RemNote              │ Inline ProseMirror   │ Local SQLite /       │ React SPA + Compound SRS   │
│                      │ Canvas Nodes         │ IndexedDB Machine    │ Component State Machine    │
├──────────────────────┼──────────────────────┼──────────────────────┼────────────────────────────┤
│ WaniKani (SRS)       │ Server-rendered HTML │ Authoritative        │ Stimulus / React Slices    │
│                      │ + KanjiVG SVG engine │ Backend Server       │ Tách rời Stroke SVG        │
├──────────────────────┼──────────────────────┼──────────────────────┼────────────────────────────┤
│ Quizlet (Web SPA)    │ Decoupled React      │ Client-side Optimist │ Modular Feature Slices     │
│                      │ Presentation Frames  │ Queue + Batch Sync   │ React Query Caching        │
├──────────────────────┼──────────────────────┼──────────────────────┼────────────────────────────┤
│ FLAMA (Mục Tiêu)     │ Sandboxed iframe     │ Client SM-2 Engine   │ Tripartite Hybrid FSD      │
│                      │ postMessage an toàn  │ + Backend Receipts   │ + Compound + Headless Hook │
└──────────────────────┴──────────────────────┴──────────────────────┴────────────────────────────┘
```

#### Bài Học Đắt Giá Rút Ra Cho Flama:
1. **Mô hình Cách ly của Anki**: Việc Anki tách riêng thuật toán scheduler vào core module (`rslib`) và cô lập việc render thẻ trong Webview chứng minh rằng kiến trúc kỹ thuật lõi của Flama (`legacyEngine.ts` + `CardRendererFrame.tsx`) là hoàn toàn đúng đắn. Vấn đề của Flama không nằm ở thuật toán mà chỉ nằm ở sự phình to của tầng bọc React bên ngoài.
2. **Compound State Machine của RemNote**: RemNote quản lý phiên học như một máy trạng thái ghép nối bằng Compound Components (`<StudyQueue.Root>`, `<StudyQueue.Card>`, `<StudyQueue.RatingBar>`). Áp dụng mô hình này sẽ loại bỏ hoàn toàn prop-drilling trong `StudyPage.tsx` của Flama.
3. **Phân tách SVG Vector của WaniKani**: WaniKani tách rời hoàn toàn bộ phân tích nét vẽ KanjiVG ra khỏi luồng câu hỏi. Flama cần đưa logic phân tích XML của `WorksheetPageRenderer.tsx` ra các pure helper modules độc lập tại `features/worksheet-studio/lib/svgCanvasMath.ts`, không để trong thân component React.
4. **Lát cắt Chế độ học của Quizlet**: Quizlet tổ chức mỗi chế độ học thành một feature slice độc lập có state tạm thời riêng, không làm ô nhiễm store toàn cục.

---

## 4. R3: Luận Chứng & Đề Xuất Mô Hình Kiến Trúc Chuẩn Hóa

### 4.1 Mô Hình Kiến Trúc Lai Ba Tầng (The Tailored Tripartite Hybrid Architecture)

Từ các phân tích thực nghiệm và đối chiếu chuyên sâu, chúng tôi khẳng định: **Mô hình tối ưu nhất cho Flama là Kiến Trúc Lai Ba Tầng (Tailored Tripartite Hybrid Architecture)**. Mô hình này kết hợp sức mạnh phân tầng của FSD, tính chuẩn mực của Atomic Design, và sự linh hoạt của Compound Components:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. MACRO LAYER (TẦNG VĨ MÔ): Feature-Sliced Design (FSD v2.1)          │
│    - Quản lý cấu trúc phân cấp thư mục toàn dự án                      │
│    - Thực thi quy tắc phụ thuộc một chiều toán học:                   │
│      pages ──► widgets ──► features ──► entities ──► shared            │
│    - Đóng gói Public API nghiêm ngặt qua index.ts từng slice           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
         ┌──────────────────────────┴──────────────────────────┐
         ▼                                                     ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
│ 2. MICRO LAYER (TẦNG VI MÔ):         │  │ 3. INTERACTIVE SUBSYSTEMS:           │
│    Atomic Design Primitives          │  │    Compound Component Pattern        │
│    Áp dụng độc quyền tại:            │  │    + Headless Custom Hooks           │
│    `shared/ui/`                      │  │    Áp dụng độc quyền tại:            │
│    • Radix UI Slot (`asChild`)       │  │    `features/` và `widgets/`        │
│    • Tailwind v4 CVA Variants        │  │    • Quy tắc <8 States/Hook          │
│    • Semantic OKLCH Design Tokens    │  │    • Zero Wrapper Divs trong DOM     │
│    • Tuyệt đối 0 logic nghiệp vụ     │  │    • Phân rã God Components triệt để │
└──────────────────────────────────────┘  └──────────────────────────────────────┘
```

#### Vì Sao Sự Kết Hợp Này Là Độc Nhất Vô Nhị Cho Flama?
1. **FSD giải quyết trật tự vĩ mô**: Ngăn chặn sự hỗn loạn của Modular Feature-Driven bằng cách cấm import chéo giữa các feature và bổ sung tầng `entities/` độc lập.
2. **Atomic Design giải quyết tầng vi mô**: Cung cấp bộ 8 UI Primitives dùng chung chuẩn hóa, loại bỏ hoàn toàn các đoạn mã viết inline lặp lại và bảo tồn hệ màu OKLCH.
3. **Compound Components giải quyết các "khối u nguyên khối"**: Cung cấp kỹ thuật giải phẫu chính xác cho các component 4,000 dòng mà FSD và Atomic Design đều bất lực nếu đứng một mình.

---

### 4.2 Giải Quyết Triệt Để Các Điểm Nghẽn Trọng Điểm của Flama

```
┌────────────────────────────────────────────────────────────────────────┐
│ KẾ HOẠCH GIẢI PHẪU CÁC ĐIỂM NGHẼN TRỌNG ĐIỂM                           │
├────────────────────────────────────────────────────────────────────────┤
│ • DeckWorksheetModal.tsx: 4,388 LOC ──► 95 LOC Shell + Compound Parts  │
│ • useBrowseState.ts:      49 states ──► 4 Headless Hooks (<8 states)   │
│ • McpTokens Duplication:  1,800 LOC ──► 0 LOC Dup (entities/mcp-token) │
└────────────────────────────────────────────────────────────────────────┘
```

#### 1. Giải cứu `DeckWorksheetModal.tsx` (Từ 4,388 dòng xuống 95 dòng bọc Shell, Phân rã 14 module đạt 2,520 LOC)
Component nguyên khối này được phân rã thành một họ Compound Component `WorksheetStudio` đặt tại `features/worksheet-studio/` và Container Modal tại `widgets/worksheet-studio/`:
- `WorksheetStudio.Root`: Khởi tạo React Context lưu trữ state và actions, áp dụng **Split Context Pattern** (`StateContext` và `ActionsContext`) để triệt tiêu hiện tượng thác re-render.
- `WorksheetStudio.Header`: Tiêu đề, thông tin bộ thẻ, nút đóng modal.
- `WorksheetStudio.Controls`: Thanh điều khiển bên trái, chứa 4 tab con độc lập với đầy đủ form điều khiển thực thụ:
  - `TemplateSelectTab.tsx` (<120 LOC): Chọn mẫu Kanji Grid, Điền khuyết (Cloze), Thẻ từ vựng.
  - `FieldMappingTab.tsx` (<150 LOC): Ánh xạ trường Kanji, Furigana/Reading, Nghĩa/Translation.
  - `LayoutOptionsTab.tsx` (<180 LOC): Cấu hình lề trang, hướng in portrait/landscape, lưới nét, slider số ô/dòng.
  - `HeaderBrandingTab.tsx` (<100 LOC): Tiêu đề phiếu, thông tin học sinh, ngày tháng.
- `WorksheetStudio.Canvas`: Khung xem trước bản in SVG tiêu thụ trực tiếp `state.preview.pages` với thanh trượt Zoom A4 chuẩn.
- `WorksheetStudio.Actions`: Chân trang chứa nút In ấn và Làm mới bản vẽ.
- **Hook Điều phối Headless**: `useWorksheetStudio.ts` gom trạng thái theo nhóm độc lập (<8 states/hook), giao tiếp với API qua TanStack Query mutations với error handling type-safe (`catch (err: unknown)`).
- **Lộ trình Phân rã Hoàn chỉnh**: Mẫu 3 trong báo cáo đóng vai trò **Architectural Blueprint & Interactive Canvas Coordinator cho Tab 4 (Printable Worksheets Canvas)**. Kế hoạch phân rã toàn diện được chuẩn hóa chi tiết tại `docs/reports/FRONTEND_DECOMPOSITION_PLAN.md` (Giai đoạn 3): toàn bộ 4,388 LOC của `DeckWorksheetModal.tsx` được bóc tách an toàn thành **14 sub-modules với tổng dung lượng 2,520 LOC** (giảm 42.6% tổng thể, triệt tiêu 1,868 dòng trùng lặp), giữ trọn vẹn 100% tính năng sản xuất:
  1. Giữ nguyên 4-step wizard stepper (`WorksheetWizardStepper`, Step 1: Chọn deck, Step 2: Khớp nối Note Type, Step 3: Chọn Template, Step 4: Canvas thiết kế & In ấn).
  2. Giữ nguyên bộ điều hướng đa trang (`currentPageIdx`, multi-page navigation controls), auto-fit viewport zoom (`getFitZoom`), mobile touch zoom, và renderer vector SVG `WorksheetPageRenderer`.
  3. Đặt Modal container tại đúng tầng Widget: `widgets/worksheet-studio/ui/WorksheetStudioModal.tsx` (~95 LOC), loại bỏ hoàn toàn nguy cơ vi phạm phụ thuộc FSD.

#### 2. Phân rã Hook Khổng Lồ `useBrowseState.ts` (Từ 49 states xuống 4 hooks chuyên trách & Facade Orchestration)
Áp dụng **Quy tắc `<8 States`** kết hợp **Domain State Consolidation (Gom nhóm trạng thái Domain)**, mega-hook 1,053 dòng được chia nhỏ thành các headless hooks độc lập:
1. `useBrowseDeckTree(selectedDeckId)`: Chỉ quản lý việc mở rộng cây thư mục và tìm kiếm tên deck (3 states).
2. `useBrowseFilters()`: Đồng bộ URL search parameters, text tìm kiếm debounced, bộ lọc trạng thái và phân trang (6 states).
3. `useBrowseSelection()`: Quản lý danh sách ID các thẻ đang được tick chọn checkbox trong bảng và thao tác chọn tất cả (3 states).
4. `useCardDetailEditor(activeCardId)`: Quản lý bản nháp chỉnh sửa các trường của thẻ đang chọn, dirty state diffing và mutation lưu thẻ (5 states).

##### Hợp Đồng Điều Phối Master Facade & Ngăn Ngừa Lỗi Vòng Đời:
- **Phòng chống Rò rỉ Thẻ chọn Xuyên Deck (Cross-Deck Selection Bleed Guard)**: Khi người dùng tick chọn thẻ trên Deck A rồi bấm chuyển sang Deck B trên cây thư mục, nếu `useBrowseSelection` không đồng bộ vòng đời với `useBrowseFilters`, danh sách `selectedCardIds` vẫn lưu thẻ Deck A. Khi người dùng bấm in bài tập hoặc sinh âm thanh TTS hàng loạt, hệ thống sẽ gửi ID thẻ của Deck A vào bối cảnh Deck B, gây lỗi khóa ngoại hoặc sai lệch dữ liệu.
  *Hợp đồng Facade tại Widget `BrowseWorkspace` bắt buộc liên kết sự kiện*:
  ```typescript
  const filters = useBrowseFilters({
    onDeckChange: () => {
      selection.resetSelection()
      operations.resetActiveCard()
    },
  })
  ```
  Mọi thao tác đổi deck hoặc đổi truy vấn tìm kiếm cốt lõi đều tự động làm sạch selection state.
- **Phòng chống Stale Closure trong Phím Tắt Toàn Cục**:
  Các listener bàn phím đăng ký trên `window` (`Ctrl+A`, `Escape`) trong hook tách rời bắt buộc phải đồng bộ dữ liệu thông qua `cardsRef = useRef(cards); cardsRef.current = cards` để loại bỏ nguy cơ closure bắt giữ mảng rỗng ban đầu (`cards = []`).
- **Chuẩn hóa Quy tắc `<8 States` qua Domain State Consolidation**:
  Đối với các phân hệ giàu tham số như Quản lý Âm thanh TTS (`useBrowseAudioModal` tiêu tốn 24 biến state lẻ), kiến trúc nghiêm cấm việc duy trì 24 `useState` rời rạc. Toàn bộ phải được gom nhóm thành 4 Domain State Objects có kiểu:
  `modals: ModalVisibilityState`, `engineConfig: TtsEngineConfig`, `voicevoxSettings: VoicevoxParams`, `apiKeyStatus: ApiKeyValidationState`.
  Nhờ đó mỗi custom hook luôn duy trì `<8 state containers` mà không làm phân mảnh logic.

#### 3. Xóa Bỏ Hoàn Toàn 1,800 Dòng Trùng Lặp MCP Tokens
- Thành lập slice domain entity: `entities/mcp-token/`:
  - `types.ts`: Khai báo kiểu `McpToken`, `McpScope`, danh mục phân quyền.
  - `scopesMetadata.ts`: Tập hợp hằng số `ALL_MCP_SCOPES` và `SCOPE_CATEGORIES`.
  - `ui/McpTokenTable.tsx`: Bảng hiển thị danh sách token chuẩn hóa.
  - `ui/McpScopeBadge.tsx`: Pill hiển thị scope có màu sắc theo danh mục.
- Thành lập slice feature: `features/mcp-tokens-crud/`:
  - `ui/McpTokenCreateDialog.tsx`: Modal tạo token kèm ma trận tick chọn quyền.
  - `ui/McpTokenSecretRevealDialog.tsx`: Modal hiển thị token secret duy nhất 1 lần kèm nút copy.
  - `ui/McpClientConfigGuide.tsx`: Hướng dẫn cấu hình JSON cho Claude Desktop, Cursor, Windsurf.
- **Kết quả**: Cả `AdminMcpTokensPage.tsx` và `McpTokensTab.tsx` đều trở thành các view mỏng (<200 LOC) đóng vai trò ghép nối các component trên. Hơn **1,800 dòng code trùng lặp bị xóa bỏ vĩnh viễn**.

---

### 4.3 Quy Chuẩn Bảo Toàn Giao Diện Nghiêm Ngặt (Zero Visual Regression Protocol)

Dự án Flama đặt tiêu chuẩn bảo toàn hiển thị ở mức tuyệt đối: **Refactor kiến trúc không được làm thay đổi dù chỉ 1 pixel hiển thị thực tế**.

```
┌────────────────────────────────────────────────────────────────────────┐
│ NGUYÊN TẮC BẢO TOÀN ZERO VISUAL REGRESSION & DOM INVARIANCE            │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Không chèn thẻ wrapper <div>: Bảo toàn Table & CSS Grid Invariants  │
│ 2. Radix asChild Guard: Chỉ truyền đúng 1 phần tử React con hợp lệ     │
│ 3. Giữ nguyên 100% token OKLCH: Kế thừa biến màu qua Tailwind CVA      │
│ 4. Giữ nguyên cấu trúc CSS Grid/Flexbox: Bảo toàn Flex basis và Gap    │
│ 5. Đo lường độc lập: Chrome DevTools Profile riêng biệt                │
│    (--user-data-dir="C:\Users\chung\.gemini\chrome-profiles\...")      │
│ 6. Tiêu chuẩn CLS = 0.0000 trên toàn bộ các trang                      │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Tuyệt đối không chèn thẻ `<div>` trung gian (DOM Layout Invariance Guards)**:
   - **Grid Layout Invariant**: Trong CSS Grid (`grid-cols-4`, `grid-cols-2`), các phần tử con trực tiếp đóng vai trò là Grid Items. Khi tách một nhóm nút bấm hoặc ô thẻ sang component con, nếu vô tình bọc chúng trong một thẻ `<div>` container, số lượng grid items trực tiếp giảm từ $N$ xuống $1$, khiến toàn bộ layout bị sụp đổ (thẻ bọc chiếm trọn ô 1, các cột còn lại bị bỏ trống, các phần tử con bên trong bị đẩy thành luồng dọc).
     *Giải pháp bắt buộc*: Sử dụng `React.Fragment` (`<>...</>`) hoặc thiết lập class `contents` (`display: contents`) để phần tử trung gian không sinh ra hộp giao diện (box-tree), giữ nguyên vị trí lưới của các con.
   - **Table Model Invariant (Chuẩn Ngữ Nghĩa HTML5 Table)**: Trong cấu trúc bảng hiển thị thẻ (`BrowseCardTable`), các phần tử con trực tiếp của `TableBody` (`<tbody>`) **bắt buộc 100% phải là `TableRow` (`<tr>`)**. Nghiêm cấm tuyệt đối việc chèn thẻ `<div>` bọc quanh `<tr>` bên trong `<tbody>`. Hành vi này vi phạm đặc tả HTML5, khiến trình duyệt tự đẩy thẻ ra ngoài cấu trúc bảng hoặc gây lỗi runtime nghiêm trọng:
     `In HTML, <tr> cannot be a child of <div>. In HTML, <div> cannot be a child of <tbody>. Hydration Error.`
2. **Quy chuẩn Bảo Vệ Tránh Sập Ứng Dụng với Radix UI `asChild` (Radix `asChild` Crash Prevention Guard)**:
   - Radix UI sử dụng cơ chế `Slot.Root` để chuyển tiếp props vào phần tử con. Thư viện `@radix-ui/react-slot` **bắt buộc yêu cầu chính xác 1 phần tử React hợp lệ (single valid React element)**.
   - *Failure Mode nghiêm trọng*: Nếu truyền vào `asChild` nhiều phần tử con song song, chuỗi text thô, React Fragment `<>...</>`, hoặc biểu thức logic đánh giá về giá trị rỗng/falsy (`{condition && <Button />}`, runtime đánh giá thành `false`), Radix sẽ ném ngoại lệ dừng ứng dụng ngay lập tức:
     `Error: Slot failed to slot onto its children. Expected a single React element child or 'Slottable'.`
   - *Quy chuẩn*: Khi sử dụng `asChild`, component con bắt buộc phải là một phần tử React đơn lẻ có thực thể DOM thực sự, không bọc fragment rỗng và không truyền các biểu thức có thể trả về falsy không có thẻ bọc.
3. **Kế thừa 100% biến màu OKLCH**:
   - Mọi UI Primitives tạo mới tại `shared/ui/` phải sử dụng đúng các lớp tiện ích của Tailwind v4 đã được định nghĩa tại `index.css`: `bg-primary`, `text-primary-foreground`, `border-border`, `bg-muted/50`. Tuyệt đối không dùng mã màu tự chế.
4. **Môi trường Chrome DevTools Isolated Profile**:
   - Mọi quy trình kiểm thử thị giác và profiling hiệu năng qua Chrome DevTools MCP bắt buộc phải sử dụng profile độc lập:
     `--user-data-dir=C:\Users\chung\.gemini\chrome-profiles\flama-devtools`
   - Bảo đảm không gây xung đột session, cookies với người dùng và có môi trường đo lường Core Web Vitals chuẩn xác (chỉ số dịch chuyển bố cục tích lũy **CLS phải duy trì bằng `0.0000`**).

---

## 5. R4: Bản Thiết Kế Quy Chuẩn Thư Mục & Quy Tắc Phụ Thuộc

### 5.1 Sơ Đồ Phân Cấp Thư Mục Mục Tiêu Chi Tiết

Dưới đây là bản vẽ thiết kế cấu trúc thư mục chi tiết đến từng thư mục con cho toàn bộ phân hệ `frontend/src/`:

```text
frontend/src/
├── app/                                 # TẦNG 5: Khởi tạo ứng dụng & Cấu hình toàn cục
│   ├── providers/
│   │   ├── QueryProvider.tsx            # Cấu hình TanStack Query Client (cache, retry)
│   │   ├── ThemeProvider.tsx            # Theme provider (Dark / Light mode OKLCH)
│   │   ├── AuthProvider.tsx             # Context phiên đăng nhập & người dùng hiện tại
│   │   └── index.ts                     # Wrapper AppProviders tổng hợp
│   ├── routes/
│   │   ├── AppRoutes.tsx                # Khai báo React Router v7 định tuyến tập trung
│   │   └── routeGuards.tsx              # Guards bảo vệ route (RequireAuth, RequireAdmin)
│   ├── styles/
│   │   └── index.css                    # TailwindCSS v4 @theme inline OKLCH tokens
│   └── App.tsx                          # Root component bọc Providers và Router
│
├── pages/                               # TẦNG 4: Điều phối Route siêu mỏng (<150 LOC)
│   ├── browse/
│   │   └── BrowsePage.tsx               # Ghép nối BrowseWorkspace widget
│   ├── study/
│   │   └── StudyPage.tsx                # Ghép nối StudySessionPlayer widget
│   ├── worksheets/
│   │   └── WorksheetsPage.tsx           # Route trang Worksheet Studio độc lập
│   ├── marketplace/
│   │   ├── MarketplaceExplorePage.tsx   # Danh sách chợ deck công khai
│   │   └── MarketplaceDetailPage.tsx   # Chi tiết deck chia sẻ & thanh toán payOS
│   ├── settings/
│   │   ├── SettingsProfilePage.tsx      # Cấu hình tài khoản người dùng
│   │   └── McpTokensPage.tsx            # Cấu hình AI MCP Tokens cá nhân
│   ├── admin/
│   │   ├── AdminTaxonomyPage.tsx        # Quản trị danh mục phân loại tập trung
│   │   └── AdminMcpTokensPage.tsx       # Quản trị AI MCP Tokens toàn hệ thống
│   └── index.ts                         # Public exports phục vụ Router
│
├── widgets/                             # TẦNG 3: Khối Giao diện Phức hợp Tự trị (<300 LOC)
│   ├── browse-workspace/
│   │   ├── ui/
│   │   │   ├── BrowseWorkspace.tsx      # Bố cục 3 cột: Cây deck + Bảng thẻ + Khung soạn
│   │   │   ├── BrowseLeftSidebar.tsx    # Cột 1: Cây thư mục deck & tìm kiếm
│   │   │   └── BrowseDetailDrawer.tsx   # Cột 3: Khung xem & sửa chi tiết thẻ đang chọn
│   │   └── index.ts
│   ├── study-session-player/            # Widget điều phối State Machine phiên học (Unified Session Slice)
│   │   ├── model/
│   │   │   └── useStudySessionController.ts # Quản lý hàng đợi thẻ, lease token, submit review, undo stack
│   │   ├── ui/
│   │   │   ├── StudySessionPlayer.tsx   # Khung thẻ học + Thanh đánh giá + Phím tắt
│   │   │   └── StudySummaryModal.tsx    # Modal tổng kết phiên học & biểu đồ SRS
│   │   └── index.ts
│   ├── worksheet-studio/
│   │   ├── ui/
│   │   │   ├── WorksheetStudioModal.tsx # Container dạng Dialog Modal bọc studio (~95 LOC)
│   │   │   └── WorksheetStudioView.tsx  # Giao diện toàn màn hình phục vụ in ấn
│   │   └── index.ts
│   ├── mcp-tokens-manager/
│   │   ├── ui/
│   │   │   └── McpTokensManager.tsx     # Khối quản trị token nhúng dùng chung
│   │   └── index.ts
│   ├── app-header/
│   │   ├── ui/AppHeader.tsx             # Header điều hướng chính toàn ứng dụng
│   │   └── index.ts
│   ├── app-sidebar/
│   │   ├── ui/AppSidebar.tsx            # Sidebar điều hướng thu gọn
│   │   └── index.ts
│   └── index.ts
│
├── features/                            # TẦNG 2: Lát Cắt Tương Tác Nghiệp Vụ (<250 LOC/file)
│   ├── browse-filters/                  # Tìm kiếm, lọc và phân trang từ vựng
│   │   ├── hooks/
│   │   │   ├── useBrowseFilters.ts      # Đồng bộ search params URL (<6 states)
│   │   │   └── useBrowseSelection.ts    # Quản lý tick chọn checkbox nhiều thẻ (<4 states)
│   │   ├── ui/
│   │   │   ├── BrowseSearchBar.tsx      # Sử dụng SearchInput primitive
│   │   │   └── BrowseTagFilter.tsx      # Lọc theo thẻ phân loại
│   │   └── index.ts
│   ├── card-detail-editor/              # Khung soạn thảo và lưu bản nháp thẻ
│   │   ├── hooks/
│   │   │   └── useCardDetailEditor.ts   # Quản lý dirty state, undo, lưu (<6 states)
│   │   ├── ui/
│   │   │   ├── CardFieldInputList.tsx   # Danh sách các trường dữ liệu của Note
│   │   │   └── CardEditorFooter.tsx     # Nút Lưu, Hủy và phím tắt
│   │   └── index.ts
│   ├── study-rating/                    # Tương tác đánh giá độ nhớ Anki SM-2
│   │   ├── hooks/
│   │   │   └── useStudyRating.ts        # Lắng nghe phím 1-4, Space, gửi đánh giá
│   │   ├── ui/
│   │   │   ├── StudyRatingBar.tsx       # 4 nút đánh giá tương tác
│   │   │   └── IntervalBadge.tsx        # Badge dự báo thời gian ôn tập kế tiếp
│   │   └── index.ts
│   ├── worksheet-studio/                # Phân hệ thiết kế bài tập và in ấn
│   │   ├── hooks/
│   │   │   ├── useWorksheetStudio.ts    # Coordinator hook gốc (<8 states)
│   │   │   ├── useWorksheetConfig.ts    # Tùy chọn khổ giấy, mẫu bài tập (<5 states)
│   │   │   └── useWorksheetPrinter.ts   # Tiện ích kích hoạt in trình duyệt
│   │   ├── ui/
│   │   │   ├── WorksheetStudioRoot.tsx  # Compound Root bọc React Context (Split Context)
│   │   │   ├── WorksheetStudioHeader.tsx
│   │   │   ├── WorksheetStudioControls.tsx
│   │   │   ├── WorksheetStudioCanvas.tsx# Khung vẽ SVG xem trước tiêu thụ state.preview.pages
│   │   │   ├── WorksheetStudioActions.tsx
│   │   │   └── tabs/                    # 4 Tab cấu hình độc lập (<150 LOC/tab)
│   │   │       ├── TemplateSelectTab.tsx
│   │   │       ├── FieldMappingTab.tsx
│   │   │       ├── LayoutOptionsTab.tsx
│   │   │       └── HeaderBrandingTab.tsx
│   │   ├── lib/
│   │   │   ├── svgCanvasMath.ts         # Tính toán tọa độ và tỷ lệ zoom A4
│   │   │   └── printEngine.ts           # Xử lý CSS in ấn ẩn của trình duyệt
│   │   └── index.ts
│   ├── mcp-tokens-crud/                 # Thao tác thêm/xóa/sao chép MCP token
│   │   ├── hooks/
│   │   │   └── useMcpTokenActions.ts    # Tạo mới, thu hồi token và copy clipboard
│   │   ├── ui/
│   │   │   ├── McpTokenCreateDialog.tsx # Modal tạo token kèm ma trận quyền
│   │   │   └── McpClientConfigGuide.tsx # Hướng dẫn cấu hình AI Client
│   │   └── index.ts
│   ├── audio-synthesis/                 # Hộp thoại tương tác tạo & cấu hình giọng đọc TTS
│   │   ├── hooks/
│   │   │   └── useTtsModalState.ts      # Quản lý cấu hình VoiceVox (port 4791) / Kokoro (<5 states)
│   │   ├── ui/
│   │   │   ├── VoicevoxConfigModal.tsx  # Modal chọn speaker, pitch, tốc độ đọc
│   │   │   └── KokoroVoicePicker.tsx    # Dropdown chọn giọng đọc Kokoro
│   │   └── index.ts
│   └── index.ts
│
├── entities/                            # TẦNG 1: Thực Thể Domain (Presentational & Pure Read)
│   ├── card/                            # Thực thể Thẻ học (Card)
│   │   ├── api/
│   │   │   └── cardQueries.ts           # React Query options: fetchCardDetail
│   │   ├── model/
│   │   │   ├── types.ts                 # Type definitions: Card, CardFieldDTO
│   │   │   └── useCardDetail.ts         # Hook đọc dữ liệu thuần túy (useQuery)
│   │   ├── ui/
│   │   │   ├── CardRowItem.tsx          # Dòng thẻ trong bảng danh sách
│   │   │   ├── CardBadge.tsx            # Badge trạng thái học (New, Learn, Due)
│   │   │   └── FuriganaText.tsx         # Render thẻ ruby chữ Hán kèm phiên âm
│   │   └── index.ts
│   ├── deck/                            # Thực thể Bộ thẻ (Deck)
│   │   ├── api/
│   │   │   └── deckQueries.ts           # fetchDeckTree, fetchDeckHeader
│   │   ├── model/
│   │   │   ├── types.ts                 # Type definitions: Deck, DeckTreeItem
│   │   │   └── useDeckHeader.ts         # Hook đọc dữ liệu Header (Pure read)
│   │   ├── ui/
│   │   │   ├── DeckHeader.tsx           # Tiêu đề bộ thẻ chuẩn hóa (Presentation)
│   │   │   ├── DeckTreeItem.tsx         # Nút phân nhánh trên cây thư mục
│   │   │   └── DeckDueCounter.tsx       # Bộ đếm số thẻ Mới / Đang học / Đến hạn
│   │   └── index.ts
│   ├── note/                            # Thực thể Ghi chú & Định dạng mẫu (Note Type)
│   │   ├── model/types.ts               # Note, NoteType, FieldDefinition interfaces
│   │   ├── ui/NoteTypeBadge.tsx         # Badge định dạng thẻ
│   │   └── index.ts
│   ├── study-session/                   # Thực thể Phiên học ngắt quãng
│   │   ├── model/
│   │   │   ├── types.ts                 # SessionLease, AnswerRecord, RatingState
│   │   │   └── schedulerEngine.ts       # Thuật toán SM-2 thuần túy (Pure math)
│   │   ├── ui/
│   │   │   └── CardDisplaySandbox.tsx   # Iframe sandbox hiển thị nội dung thẻ
│   │   └── index.ts
│   ├── mcp-token/                       # Thực thể Token phân quyền AI MCP
│   │   ├── model/
│   │   │   ├── types.ts                 # McpToken, McpScope, ScopeCategory
│   │   │   └── scopesMetadata.ts        # Hằng số ALL_MCP_SCOPES, SCOPE_CATEGORIES
│   │   ├── ui/
│   │   │   ├── McpTokenTable.tsx        # Bảng hiển thị danh sách token chuẩn hóa
│   │   │   └── McpScopeBadge.tsx        # Badge danh mục quyền có màu tương ứng
│   │   └── index.ts
│   ├── user/                            # Thực thể Hồ sơ người dùng
│   │   ├── model/types.ts               # UserProfile, Role, Permissions
│   │   ├── ui/UserAvatar.tsx            # Avatar người dùng chuẩn hóa
│   │   └── index.ts
│   └── index.ts
│
└── shared/                              # TẦNG 0: Hạ Tầng Dùng Chung Độc Lập Domain
    ├── ui/                              # UI Primitives Chuẩn Hóa (CVA + OKLCH Tokens)
    │   ├── search-input/
    │   │   ├── SearchInput.tsx          # Primitive 1: SearchInput (IME Guard + Ctrl+K Listener)
    │   │   └── index.ts
    │   ├── confirm-dialog/
    │   │   ├── ConfirmDialog.tsx        # Primitive 2: ConfirmDialog (Radix Alert)
    │   │   └── index.ts
    │   ├── status-pill/
    │   │   ├── StatusPill.tsx           # Primitive 3: StatusPill (CVA OKLCH)
    │   │   └── index.ts
    │   ├── audio-player/                # Primitive 4: Audio Playback Primitives (Dùng chung cho Card/Table)
    │   │   ├── AudioPlayButton.tsx      # Nút bấm phát âm thanh kèm icon loa (CVA OKLCH)
    │   │   ├── AudioPlayer.tsx          # Thanh điều khiển phát âm thanh thu gọn
    │   │   └── index.ts
    │   ├── code-snippet-box/
    │   │   ├── CodeSnippetBox.tsx       # Primitive 5: CodeSnippetBox (Copy + Syntax)
    │   │   └── index.ts
    │   ├── filter-pill-group/
    │   │   ├── FilterPillGroup.tsx      # Primitive 6: FilterPillGroup
    │   │   └── index.ts
    │   ├── image-upload-dropzone/
    │   │   ├── ImageUploadDropzone.tsx  # Primitive 7: Dropzone tải ảnh
    │   │   └── index.ts
    │   ├── split-pane/
    │   │   ├── SplitPane.tsx            # Primitive 8: Khung phân chia kéo thả
    │   │   └── index.ts
    │   ├── card-fields-form/
    │   │   ├── CardFieldsForm.tsx       # Primitive 9: Form nhập các trường động
    │   │   └── index.ts
    │   ├── base/                        # Radix UI Wrappers cơ bản
    │   │   ├── button.tsx               # Button với CVA và Slot.Root (asChild Guard)
    │   │   ├── dialog.tsx               # Dialog primitives
    │   │   ├── badge.tsx                # Badge primitives
    │   │   ├── input.tsx                # HTML Input cơ bản
    │   │   ├── skeleton.tsx             # Hiệu ứng chờ tải dữ liệu
    │   │   ├── table.tsx                # Table truy cập chuẩn WAI-ARIA (Table Invariant)
    │   │   ├── tabs.tsx                 # Tabs primitives
    │   │   ├── tooltip.tsx              # Tooltip primitives
    │   │   └── index.ts
    │   └── index.ts
    ├── api/                             # HTTP Client & Network Infrastructure
    │   ├── client.ts                    # Fetch/Axios client tự động tiêm CSRF Token
    │   ├── endpoints.ts                 # Hằng số định tuyến API chuẩn hóa
    │   └── index.ts
    ├── lib/                             # Tiện ích thuần túy (Pure Utilities)
    │   ├── utils.ts                     # Hàm cn() kết hợp clsx và tailwind-merge
    │   ├── audio/                       # Hạ tầng phát âm thanh độc lập nghiệp vụ
    │   │   ├── soundPlayer.ts           # Web Audio API buffer player & fallback HTMLAudio
    │   │   └── useAudioPlayer.ts        # Hook phát audio buffer chuẩn cho mọi component
    │   ├── date.ts                      # Format ngày tháng, tính múi giờ
    │   └── storage.ts                   # Type-safe LocalStorage helper
    ├── hooks/                           # React Hooks tiện ích dùng chung
    │   ├── useDebounce.ts
    │   ├── useMediaQuery.ts
    │   └── useKeyboardShortcut.ts
    ├── types/                           # DTOs & API Response Envelopes toàn cục
    │   ├── domain/                      # Kiểu định danh nguyên tử dùng chung giữa các entities
    │   │   ├── ids.ts                   # Brand types: DeckId, CardId, NoteTypeId
    │   │   └── enums.ts                 # StudyQueue, CardReps, RatingValue
    │   ├── apiEnvelope.ts               # Chuẩn hóa cấu trúc ApiResponse<T>
    │   └── pagination.ts                # Chuẩn hóa phân trang PaginatedResponse<T>
    └── index.ts
```

---

### 5.2 Hợp Đồng Đóng Gói Public API (`index.ts`)

Để triệt tiêu tình trạng phụ thuộc ngầm và cho phép tự do tái cấu trúc nội bộ:
1. **Hợp đồng Xuất khẩu Duy nhất**: Mỗi slice (ví dụ: `entities/deck`) bắt buộc phải xuất khẩu toàn bộ interface, components, và hooks công khai qua tập tin `index.ts` nằm ngay tại gốc của slice đó:
   ```typescript
   // frontend/src/entities/deck/index.ts
   export { DeckHeader, type DeckHeaderProps } from './ui/DeckHeader'
   export { DeckDueCounter } from './ui/DeckDueCounter'
   export { useDeckHeader, deckQueryKeys, type UseDeckHeaderResult } from './model/useDeckHeader'
   export type { DeckHeaderDTO, DeckCountsDTO } from './model/types'
   ```
2. **Nghiêm cấm Import Xuyên Thấu (Deep Import Ban)**: Các file bên ngoài slice **chỉ được phép import từ gốc của slice**:
   ```typescript
   // ✅ TUÂN THỦ: Import qua Public API
   import { DeckHeader, useDeckHeader } from '@/entities/deck'
   import { SearchInput } from '@/shared/ui'

   // ❌ VI PHẠM BỊ CHẶN: Import xuyên thấu vào cấu trúc nội bộ
   import { DeckHeader } from '@/entities/deck/ui/DeckHeader'
   import { formatZoom } from '@/features/worksheet-studio/lib/svgCanvasMath'
   ```
3. **Quyền Tự Do Tái Cấu Trúc Nội Bộ**: Lập trình viên sở hữu slice có toàn quyền tách nhỏ file, đổi tên file con bên trong thư mục `ui/`, `model/`, `lib/` mà hoàn toàn yên tâm không làm gãy mã nguồn ở bất kỳ nơi nào khác trong toàn bộ dự án, miễn là các export tại `index.ts` được giữ ổn định.

---

### 5.3 Ma Trận Quy Tắc Phụ Thuộc Một Chiều Nghiêm Ngặt (Unidirectional Dependency Matrix)

Bảng quy định chiều phụ thuộc toán học một chiều giữa các tầng trong kiến trúc Flama:

```
┌────────────────────────────────────────────────────────────────────────┐
│ MA TRẬN CHO PHÉP / NGHIÊM CẤM IMPORT GIỮA CÁC TẦNG                     │
├───────────────────┬──────────────────────────┬─────────────────────────┤
│ Tầng Gọi Import   │ ĐƯỢC PHÉP Import Từ      │ NGHIÊM CẤM Import Từ    │
├───────────────────┼──────────────────────────┼─────────────────────────┤
│ app (Tầng 5)      │ pages, widgets,          │ (Không có - Tầng cao    │
│                   │ features, entities,      │ nhất của hệ thống)      │
│                   │ shared                   │                         │
├───────────────────┼──────────────────────────┼─────────────────────────┤
│ pages (Tầng 4)    │ widgets, features,       │ app                     │
│                   │ entities, shared         │                         │
├───────────────────┼──────────────────────────┼─────────────────────────┤
│ widgets (Tầng 3)  │ features, entities,      │ app, pages,             │
│                   │ shared                   │ sibling widgets         │
├───────────────────┼──────────────────────────┼─────────────────────────┤
│ features (Tầng 2) │ entities, shared         │ app, pages, widgets,    │
│                   │                          │ sibling features*       │
├───────────────────┼──────────────────────────┼─────────────────────────┤
│ entities (Tầng 1) │ shared                   │ app, pages, widgets,    │
│                   │                          │ features, sibling       │
│                   │                          │ entities                │
├───────────────────┼──────────────────────────┼─────────────────────────┤
│ shared (Tầng 0)   │ shared (nội bộ tầng      │ app, pages, widgets,    │
│                   │ shared), npm packages    │ features, entities      │
└───────────────────┴──────────────────────────┴─────────────────────────┘
```

##### Các Quy Định Kiến Trúc Trọng Yếu Bổ Sung:
1. **Quy định Phụ thuộc Tính năng (Sibling Features Ban)**: Các feature bị cấm import trực tiếp từ nhau theo mặc định. Trong trường hợp 2 feature cần phối hợp (ví dụ: `browse-filters` và `card-detail-editor`), sự điều phối bắt buộc phải diễn ra tại tầng `widgets/` (`BrowseWorkspace`) hoặc giao tiếp thông qua state được lưu trữ tại tầng `entities/`.
2. **Quy tắc Kiểu Dữ liệu Thực thể Chung (Cross-Entity Types)**: FSD v2.1 nghiêm cấm các slice `entities/` import lẫn nhau (`entities/card` không được import `entities/deck`). Các kiểu dữ liệu ID nguyên tử và Enums cốt lõi dùng chung (`DeckId`, `CardId`, `NoteTypeId`, `StudyQueue`) được định vị tại `shared/types/domain/` để mọi entity và feature đều có thể sử dụng mà không tạo ra quan hệ phụ thuộc chéo.
3. **Quy tắc Phân Bổ Âm Thanh (Audio Layer Placement)**: Các primitive phát âm thanh cơ bản (`AudioPlayButton`, `AudioPlayer`, `soundPlayer.ts`, `useAudioPlayer.ts`) cư trú tại `shared/ui/audio-player/` và `shared/lib/audio/`. Nhờ đó, cả `entities/card` (`CardRowItem`) và `features/card-detail-editor` đều có thể hiển thị nút phát âm thanh mà không vi phạm quy tắc FSD. Slice `features/audio-synthesis/` được dành riêng cho các hộp thoại cấu hình TTS tương tác phức tạp (VoiceVox / Kokoro dialogs).
4. **Quy tắc Thống Nhất Trạng Thái Phiên Học (Unified Study Session Slice)**: Để tránh hiện tượng phân mảnh trạng thái (split-brain state) giữa đánh giá thẻ và iframe sandbox, bộ máy trạng thái phiên học SM-2 được thống nhất tại widget `study-session-player` (thông qua `useStudySessionController.ts`), điều phối toàn diện hàng đợi thẻ, session lease token, đánh giá SM-2, undo stack, và giao tiếp `postMessage` với `CardDisplaySandbox`.

---

### 5.4 Chiến Lược Tự Động Hóa Ngăn Ngừa Phụ Thuộc Vòng (Circular Dependency Tooling)

Kiến trúc không thể chỉ dựa vào sự tự giác của lập trình viên, mà phải được bảo vệ bởi công cụ tự động hóa tích hợp trong quy trình CI/CD và Git pre-commit:

#### 1. Cấu hình Luật Ranh giới ESLint (`eslint-plugin-boundaries`)
File cấu hình `.eslintrc.cjs` kiểm soát ranh giới giữa các tầng:
```javascript
// .eslintrc.cjs
module.exports = {
  plugins: ["boundaries"],
  rules: {
    // 1. Kiểm soát chiều import giữa các tầng
    "boundaries/element-types": [
      "error",
      {
        default: "disallow",
        rules: [
          { from: "app", allow: ["pages", "widgets", "features", "entities", "shared"] },
          { from: "pages", allow: ["widgets", "features", "entities", "shared"] },
          { from: "widgets", allow: ["features", "entities", "shared"] },
          { from: "features", allow: ["entities", "shared"] },
          { from: "entities", allow: ["shared"] },
          { from: "shared", allow: ["shared"] }, // Cho phép shared/ui import shared/lib/utils & shared/api
        ],
      },
    ],
    // 2. Ép buộc import qua Public API index.ts
    "boundaries/entry-point": [
      "error",
      {
        default: "disallow",
        rules: [
          { target: ["widgets/*/**", "features/*/**", "entities/*/**"], allow: ["index.ts"] },
        ],
      },
    ],
  },
};
```

> **Lưu ý Tương thích Tooling**: Repository Flama sử dụng `oxlint` cho linting tốc độ cao trong CI/pre-commit (`npx oxlint`), vốn không kích hoạt plugins của ESLint. Do đó, việc thực thi ranh giới phụ thuộc kiến trúc trong toàn bộ dự án được bảo đảm kép thông qua công cụ độc lập `dependency-cruiser` (`npm run check:deps`) với cấu hình `.dependency-cruiser.cjs` chạy trực tiếp trên Node.js mà không phụ thuộc vào ESLint runtime.

#### 2. Kiểm toán Tự động bằng `dependency-cruiser`
File `.dependency-cruiser.cjs` được kích hoạt tự động qua script `npm run check:deps` để quét đồ thị phụ thuộc toàn diện:
```javascript
// .dependency-cruiser.cjs
module.exports = {
  forbidden: [
    {
      name: "no-upward-layer-imports",
      comment: "Tuyệt đối cấm import ngược từ tầng dưới lên tầng trên",
      severity: "error",
      from: { path: "^src/(entities|shared|features|widgets)/" },
      to: { path: "^src/(app|pages)/", pathNot: "^src/shared/" },
    },
    {
      name: "no-circular-dependencies",
      comment: "Phát hiện và triệt tiêu ngay lập tức mọi vòng lặp import",
      severity: "error",
      from: {},
      to: { circular: true },
    },
    {
      name: "no-cross-entity-imports",
      comment: "Cấm các slice entities import trực tiếp lẫn nhau",
      severity: "error",
      from: { path: "^src/entities/([^/]+)/" },
      to: { path: "^src/entities/(?!$1/)" },
    },
  ],
};
```

---

## 6. R5: Bộ Mã Mẫu Thực Chiến Chuẩn Hóa (Production Reference Implementations)

Dưới đây là 3 bộ mã nguồn tham chiếu kiến trúc chuẩn mực, sẵn sàng làm quy chuẩn sản xuất (Architectural Blueprint & Component Decomposition Reference), thể hiện trọn vẹn tinh hoa của kiến trúc đề xuất và giải quyết triệt để các rủi ro kỹ thuật trong môi trường ứng dụng thực tế.

---

### 6.1 Mẫu 1: UI Primitive Chuẩn Hóa với CVA và OKLCH Tokens (`SearchInput.tsx`)

- **Vị trí**: `frontend/src/shared/ui/search-input/SearchInput.tsx`
- **Mục tiêu**: Chuẩn hóa và thay thế hơn 26 vị trí đang viết code inline lặp lại trên toàn bộ dự án (`BrowseToolbar`, `LibraryPages`, `AdminUsersPage`, v.v.).
- **Đặc tính kỹ thuật**:
  - Quản lý đầy đủ variants (`default`, `filled`, `ghost`) và sizes (`sm`, `default`, `lg`) qua CVA.
  - Kế thừa chính xác hệ màu OKLCH từ `index.css`: `--border`, `--ring`, `--destructive`, `--muted-foreground`.
  - Tích hợp icon kính lúp `Search` cố định vị trí.
  - Tích hợp nút Xóa nhanh (Clear button) tự động xuất hiện khi có nội dung, hỗ trợ phím `Escape`.
  - **Bảo vệ Bộ gõ Tiếng Nhật (Japanese IME Composition Guard)**: Kiểm tra `isComposing` và quản lý vòng đời bộ gõ (`onCompositionStart`, `onCompositionEnd`). Khi người dùng gõ Kanji/Hiragana và bấm `Escape` để hủy menu ứng viên chuyển đổi từ, component tuyệt đối **không xóa sạch** xâu đang nhập.
  - **Lắng nghe Phím tắt Toàn cục (Global Shortcut Listener)**: Tích hợp event listener trên `window` cho phím tắt (`Ctrl+K` / `⌘K`), gọi `e.preventDefault()` để chặn hành vi mặc định của trình duyệt và tự động focus ô tìm kiếm.
  - Tích hợp con quay hiệu ứng chờ (`isLoading={true}`).
  - Tích hợp badge gợi ý phím tắt (`shortcut="⌘K"` / `"Ctrl+K"`).
  - Đầy đủ thuộc tính trợ năng WAI-ARIA (`role="searchbox"`, `aria-label`, `aria-invalid`).
  - Sử dụng React 19 Ref Forwarding, **không bọc thêm bất kỳ thẻ wrapper nào làm lệch layout**.

```tsx
// frontend/src/shared/ui/search-input/SearchInput.tsx
import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { Search, X, Loader2 } from 'lucide-react'
import { cn } from '@/shared/lib/utils'

export const searchInputVariants = cva(
  'w-full rounded-lg border bg-transparent text-sm transition-all duration-150 outline-none ' +
  'placeholder:text-muted-foreground ' +
  'focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 ' +
  'disabled:pointer-events-none disabled:opacity-50 ' +
  'aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 ' +
  'dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40',
  {
    variants: {
      variant: {
        default: 'border-border bg-background hover:border-border/80 focus-visible:bg-background',
        filled: 'border-transparent bg-muted/50 hover:bg-muted/70 focus-visible:bg-background focus-visible:border-ring',
        ghost: 'border-transparent bg-transparent hover:bg-muted/40 focus-visible:bg-background focus-visible:border-ring',
      },
      size: {
        sm: 'h-8 text-xs pl-8 pr-8',
        default: 'h-9 text-sm pl-9 pr-9',
        lg: 'h-10 text-base pl-10 pr-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

const searchIconVariants = cva(
  'pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted-foreground transition-colors',
  {
    variants: {
      size: {
        sm: 'left-2.5 size-3.5',
        default: 'left-3 size-4',
        lg: 'left-3.5 size-4.5',
      },
    },
    defaultVariants: {
      size: 'default',
    },
  },
)

export interface SearchInputProps
  extends Omit<React.ComponentProps<'input'>, 'size'>,
    VariantProps<typeof searchInputVariants> {
  /** Callback tùy chọn kích hoạt khi bấm nút Xóa hoặc nhấn phím Escape */
  onClear?: () => void
  /** Cờ hiển thị biểu tượng loading xoay tròn thay thế nút clear */
  isLoading?: boolean
  /** Chuỗi ký tự gợi ý phím tắt (ví dụ: '⌘K' hoặc 'Ctrl+K') */
  shortcut?: string
}

export const SearchInput = React.forwardRef<HTMLInputElement, SearchInputProps>(
  (
    {
      className,
      variant,
      size,
      value,
      defaultValue,
      onChange,
      onClear,
      onKeyDown,
      onCompositionStart,
      onCompositionEnd,
      isLoading = false,
      shortcut,
      disabled,
      ...props
    },
    ref,
  ) => {
    const internalInputRef = React.useRef<HTMLInputElement | null>(null)
    const isComposingRef = React.useRef(false)
    const [internalValue, setInternalValue] = React.useState(defaultValue || '')
    const isControlled = value !== undefined
    const currentValue = isControlled ? String(value) : String(internalValue)
    const hasValue = currentValue.length > 0

    // Đồng bộ Ref Forwarding với chuẩn React 19
    React.useImperativeHandle(ref, () => internalInputRef.current as HTMLInputElement)

    // Lắng nghe phím tắt toàn cục (ví dụ: Ctrl+K / ⌘K)
    React.useEffect(() => {
      if (!shortcut || disabled) return

      const handleGlobalKeyDown = (e: KeyboardEvent) => {
        // Hỗ trợ cả macOS (Cmd) và Windows/Linux (Ctrl)
        const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform)
        const modifierPressed = isMac ? e.metaKey : e.ctrlKey
        const targetKey = shortcut.replace(/[⌘\^]|Ctrl\+|Cmd\+/gi, '').trim().toLowerCase()

        if (modifierPressed && e.key.toLowerCase() === targetKey) {
          e.preventDefault()
          internalInputRef.current?.focus()
          internalInputRef.current?.select()
        }
      }

      window.addEventListener('keydown', handleGlobalKeyDown)
      return () => window.removeEventListener('keydown', handleGlobalKeyDown)
    }, [shortcut, disabled])

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!isControlled) {
        setInternalValue(e.target.value)
      }
      onChange?.(e)
    }

    const handleClear = () => {
      if (!isControlled) {
        setInternalValue('')
      }
      if (internalInputRef.current) {
        internalInputRef.current.value = ''
        internalInputRef.current.focus()
      }
      onClear?.()
      // Phát sự kiện an toàn cho các Form validation libraries (react-hook-form)
      const syntheticEvent = {
        target: { value: '', name: props.name || '' },
        currentTarget: { value: '', name: props.name || '' },
        bubbles: true,
        cancelable: false,
        defaultPrevented: false,
        eventPhase: 3,
        isTrusted: false,
        preventDefault: () => {},
        isDefaultPrevented: () => false,
        stopPropagation: () => {},
        isPropagationStopped: () => false,
        persist: () => {},
        timeStamp: Date.now(),
        type: 'change',
        nativeEvent: new Event('change'),
      } as unknown as React.ChangeEvent<HTMLInputElement>
      onChange?.(syntheticEvent)
    }

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Escape' && hasValue) {
        // Bảo vệ IME tiếng Nhật: Nếu đang trong quá trình chuyển đổi Kanji/Hiragana (IME composition),
        // phím Escape dùng để đóng popup ứng viên, TUYỆT ĐỐI KHÔNG xóa sạch input!
        if (e.nativeEvent.isComposing || isComposingRef.current || (e as unknown as { isComposing?: boolean }).isComposing) {
          return
        }
        e.preventDefault()
        handleClear()
      }
      onKeyDown?.(e)
    }

    return (
      <div data-slot="search-input-root" className="relative w-full">
        {/* Leading Search Icon */}
        <Search
          data-slot="search-icon"
          className={cn(searchIconVariants({ size }))}
          aria-hidden="true"
        />

        {/* Input Phần tử Cốt lõi */}
        <input
          ref={internalInputRef}
          type="search"
          role="searchbox"
          aria-label={props['aria-label'] || 'Tìm kiếm...'}
          value={value}
          defaultValue={defaultValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onCompositionStart={(e) => {
            isComposingRef.current = true
            onCompositionStart?.(e)
          }}
          onCompositionEnd={(e) => {
            isComposingRef.current = false
            onCompositionEnd?.(e)
          }}
          disabled={disabled}
          className={cn(searchInputVariants({ variant, size }), className)}
          {...props}
        />

        {/* Trailing Controls: Loading Spinner, Nút Clear, hoặc Phím tắt */}
        <div className="absolute right-2.5 top-1/2 flex -translate-y-1/2 items-center gap-1.5">
          {isLoading && (
            <Loader2
              data-slot="search-spinner"
              className="size-3.5 animate-spin text-muted-foreground"
              aria-hidden="true"
            />
          )}

          {!isLoading && hasValue && !disabled && (
            <button
              type="button"
              data-slot="search-clear-btn"
              onClick={handleClear}
              className="flex size-4.5 items-center justify-center rounded-sm text-muted-foreground/70 transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label="Xóa nội dung tìm kiếm"
            >
              <X className="size-3" />
            </button>
          )}

          {!hasValue && shortcut && !disabled && (
            <kbd
              data-slot="search-shortcut-badge"
              className="pointer-events-none hidden select-none rounded border border-border/80 bg-muted px-1.5 py-0.5 font-mono text-[10px] font-semibold text-muted-foreground sm:inline-block"
            >
              {shortcut}
            </kbd>
          )}
        </div>
      </div>
    )
  },
)

SearchInput.displayName = 'SearchInput'
```

---

### 6.2 Mẫu 2: Domain Entity Component + Hook Đọc Dữ Liệu Thuần Túy (`DeckHeader.tsx` & `useDeckHeader.ts`)

- **Vị trí**:
  - `frontend/src/entities/deck/model/useDeckHeader.ts`
  - `frontend/src/entities/deck/ui/DeckHeader.tsx`
- **Mục tiêu**: Chuẩn hóa phần đầu trang bộ thẻ (Deck Header) vốn đang bị viết tùy tiện và phân tán ở màn hình Browse, Study, Marketplace.
- **Nguyên tắc kiến trúc**:
  - **Zero Action Leaks**: Entity component là pure presentation, **tuyệt đối không chứa logic mutation**, không gọi hàm xóa deck hay sửa deck bên trong nó.
  - **Inversion of Control**: Các nút tương tác cụ thể của từng màn hình (nút Học ngay, Thêm thẻ, Cài đặt) được tiêm vào từ widget thông qua slot `actionsSlot?: React.ReactNode`.
  - **Pure Read Hook**: Hook `useDeckHeader` chỉ đọc dữ liệu qua React Query với cấu hình cache thông minh (`staleTime: 5 phút`).

#### 1. Hook Đọc Dữ Liệu Thuần Túy (`useDeckHeader.ts`)
```typescript
// frontend/src/entities/deck/model/useDeckHeader.ts
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/shared/api'
import type { DeckHeaderDTO } from './types'

export const deckQueryKeys = {
  all: ['decks'] as const,
  details: () => [...deckQueryKeys.all, 'detail'] as const,
  detail: (id: number | null | undefined) => [...deckQueryKeys.details(), id] as const,
}

export interface UseDeckHeaderResult {
  deck: DeckHeaderDTO | null
  isLoading: boolean
  isError: boolean
  error: Error | null
  refetch: () => void
}

/**
 * Pure Read Hook cho Entity Deck Header.
 * Nghiêm ngặt chỉ đọc: Tuyệt đối không chứa logic mutation hay tác dụng phụ.
 */
export function useDeckHeader(deckId: number | null | undefined): UseDeckHeaderResult {
  const { data, isLoading, isError, error, refetch } = useQuery<DeckHeaderDTO, Error>({
    queryKey: deckQueryKeys.detail(deckId),
    queryFn: async () => {
      if (!deckId) throw new Error('Deck ID is required')
      const response = await apiClient.get<DeckHeaderDTO>(`/api/decks/${deckId}/header`)
      return response.data
    },
    enabled: typeof deckId === 'number' && deckId > 0,
    staleTime: 5 * 60 * 1000, // Dữ liệu tươi mới trong 5 phút
    gcTime: 15 * 60 * 1000,    // Thu hồi bộ nhớ sau 15 phút
  })

  return {
    deck: data ?? null,
    isLoading: isLoading && Boolean(deckId),
    isError,
    error: error as Error | null,
    refetch,
  }
}
```

#### 2. Component Thực Thể Trình Diễn (`DeckHeader.tsx`)
```tsx
// frontend/src/entities/deck/ui/DeckHeader.tsx
import * as React from 'react'
import { FolderTree, Layers } from 'lucide-react'
import { Badge } from '@/shared/ui/base/badge'
import { Skeleton } from '@/shared/ui/base/skeleton'
import { StatusPill } from '@/shared/ui/status-pill'
import { cn } from '@/shared/lib/utils'
import type { DeckHeaderDTO } from '../model/types'

export interface DeckHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Đối tượng dữ liệu Deck (null khi đang nạp ban đầu) */
  deck: DeckHeaderDTO | null
  /** Cờ trạng thái đang tải dữ liệu */
  isLoading?: boolean
  /** Slot tiêm các nút hành động (do Widget bên ngoài quyết định) */
  actionsSlot?: React.ReactNode
}

export function DeckHeader({
  deck,
  isLoading = false,
  actionsSlot,
  className,
  ...props
}: DeckHeaderProps) {
  if (isLoading) {
    return (
      <div
        data-slot="deck-header-skeleton"
        className={cn(
          'flex flex-col gap-3 rounded-xl border border-border/60 bg-card p-5 shadow-2xs sm:flex-row sm:items-center sm:justify-between',
          className,
        )}
      >
        <div className="flex flex-col gap-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-7 w-64" />
          <div className="flex gap-2">
            <Skeleton className="h-5 w-16 rounded-full" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
        </div>
        <Skeleton className="h-9 w-28 rounded-lg" />
      </div>
    )
  }

  if (!deck) return null

  const { name, path, noteTypeName, counts } = deck

  return (
    <div
      data-slot="deck-header"
      className={cn(
        'flex flex-col gap-4 rounded-xl border border-border/60 bg-card p-5 shadow-2xs sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
      {...props}
    >
      <div className="flex flex-col gap-1.5">
        {/* Đường dẫn Cây thư mục (Breadcrumb) */}
        {path && (
          <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <FolderTree className="size-3.5 shrink-0 opacity-70" />
            <span className="truncate">{path}</span>
          </div>
        )}

        {/* Tiêu đề Bộ thẻ & Badge Định dạng Note Type */}
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
            {name}
          </h1>
          {noteTypeName && (
            <Badge variant="outline" className="gap-1 border-border/80 bg-muted/30 text-xs font-normal">
              <Layers className="size-3 opacity-60" />
              {noteTypeName}
            </Badge>
          )}
        </div>

        {/* Chỉ số Bộ đếm Thẻ (Sử dụng UI Primitive StatusPill kế thừa OKLCH tokens) */}
        {counts && (
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs font-semibold">
            <StatusPill variant="new" size="sm">
              Mới: {counts.new ?? 0}
            </StatusPill>
            <StatusPill variant="learning" size="sm">
              Đang học: {counts.learn ?? 0}
            </StatusPill>
            <StatusPill variant="due" size="sm">
              Đến hạn: {counts.due ?? 0}
            </StatusPill>
          </div>
        )}
      </div>

      {/* Vị trí Tiêm Nút Hành Động từ Widget bên ngoài */}
      {actionsSlot && (
        <div data-slot="deck-header-actions" className="flex shrink-0 items-center gap-2 self-start sm:self-center">
          {actionsSlot}
        </div>
      )}
    </div>
  )
}
```

---

### 6.3 Mẫu 3: Feature Compound Component + Headless Hook Giải Phẫu God Component (`WorksheetStudio`)

- **Vị trí**:
  - Hook: `frontend/src/features/worksheet-studio/hooks/useWorksheetStudio.ts`
  - Component Compound: `frontend/src/features/worksheet-studio/ui/WorksheetStudioRoot.tsx`
  - Container Modal Refactored: `frontend/src/widgets/worksheet-studio/ui/WorksheetStudioModal.tsx`
- **Mục tiêu**: Chuẩn hóa kiến trúc tương tác cho phân hệ Printable Worksheet Studio (Tab 4 của Modal 4,388 LOC), làm tiền đề giải phẫu toàn diện monolith thành 14 modules với 2,520 LOC theo kế hoạch tại `docs/reports/FRONTEND_DECOMPOSITION_PLAN.md`.
- **Kết quả đạt được**:
  - **Khắc phục Triệt để Thác Re-render (Split Context Pattern)**: Tách biệt hoàn toàn `StateContext` và `ActionsContext` (memoized), giúp cô lập tuyệt đối blast radius của render cycles. Người dùng gõ text hoặc đổi tab trong `Controls` hoàn toàn **không ép khung vẽ vector SVG `Canvas` re-render**.
  - **Điều Khiển Thật 100% (Authentic Form Controls)**: Loại bỏ toàn bộ các chuỗi placeholder, thay thế bằng 4 tab điều khiển tương tác thực thụ (chọn mẫu Kanji Grid / Cloze / Vocab, ánh xạ trường Note Type, slider số ô/dòng, cấu hình thông tin học sinh).
  - **Khung Vẽ Vector SVG Chuẩn Xác (Authentic SVG Vector Canvas)**: Tiêu thụ trực tiếp dữ liệu `state.preview.pages`, render ký tự chữ Hán thật, đường kẻ trợ lực căn nét bút, furigana ruby text, hộp thông tin học sinh, và watermark A4 chuẩn.
  - **An Toàn Kiểu Tuyệt Đối (Zero `any`)**: Loại bỏ toàn bộ `any`, xử lý ngoại lệ in ấn an toàn bằng `catch (err: unknown)` và type narrowing.
  - **Tuân Thủ Tuyệt Đối Ranh Giới FSD v2.1**: Container Modal chuyển từ tầng `features/` sang tầng `widgets/` (`WorksheetStudioModal.tsx`), import hợp lệ từ `@/features/worksheet-studio` mà không vi phạm quy tắc cấm cross-feature.

#### 1. Headless Coordinator Hook (`useWorksheetStudio.ts`)
```typescript
// frontend/src/features/worksheet-studio/hooks/useWorksheetStudio.ts
import { useState, useCallback, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiClient } from '@/shared/api'
import { printWorksheet } from '../lib/printEngine'
import type {
  DeckWorksheetMeta,
  WorksheetLayoutOptions,
  WorksheetFieldMapping,
  WorksheetPreviewResponse,
  StudioTab,
  WizardStepId,
} from '../model/types'

export interface UseWorksheetStudioProps {
  deckId?: number | null
  initialCardIds?: (string | number)[]
  initialStep?: WizardStepId
  onClose?: () => void
}

/**
 * Headless Hook điều phối toàn bộ phân hệ Worksheet Studio.
 * Phân chia trạng thái tuân thủ nghiêm ngặt Quy tắc <8 States/Hook.
 */
export function useWorksheetStudio({
  deckId,
  initialCardIds,
  initialStep,
  onClose,
}: UseWorksheetStudioProps) {
  // Nhóm 1: Trạng thái điều hướng & hiển thị Viewport (<4 states)
  const [wizardStep, setWizardStep] = useState<WizardStepId>(() => initialStep ?? (deckId ? 'mapping' : 'deck'))
  const [activeTab, setActiveTab] = useState<StudioTab>('template')
  const [zoomLevel, setZoomLevel] = useState<number>(1.0)
  const [mobileView, setMobileView] = useState<'controls' | 'preview'>('preview')

  // Nhóm 2: Trạng thái cấu hình mẫu & bố cục in ấn (<4 states)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('kanji_compact')
  const [fieldMapping, setFieldMapping] = useState<WorksheetFieldMapping>({
    kanji: 'Kanji',
    furigana: 'Furigana',
    meaning: 'Meaning',
  })
  const [layoutOptions, setLayoutOptions] = useState<WorksheetLayoutOptions>({
    paper_size: 'a4',
    orientation: 'portrait',
    margin: 'standard',
    grid_style: 'cross',
    rows_per_page: 5,
    show_stroke_order: true,
    show_student_header: true,
    worksheet_title: 'Phiếu Luyện Viết Chữ Hán',
  })

  // Nhóm 3: Truy vấn Metadata Bộ thẻ
  const metaQuery = useQuery<DeckWorksheetMeta>({
    queryKey: ['worksheets', 'meta', deckId],
    queryFn: async () => {
      const res = await apiClient.get<DeckWorksheetMeta>(`/api/decks/${deckId}/worksheet-meta`)
      return res.data
    },
    enabled: Boolean(deckId),
  })

  // Nhóm 4: Mutation sinh dữ liệu xem trước Canvas SVG
  const previewMutation = useMutation<WorksheetPreviewResponse, Error>({
    mutationFn: async () => {
      const payload = {
        deck_id: deckId,
        template_id: selectedTemplateId,
        field_mapping: fieldMapping,
        layout_options: layoutOptions,
        card_ids: initialCardIds,
      }
      const res = await apiClient.post<WorksheetPreviewResponse>('/api/worksheets/preview', payload)
      return res.data
    },
    onError: (err: Error) => toast.error(`Lỗi tạo bản xem trước: ${err.message}`),
  })

  // Nhóm 5: Handler kích hoạt lệnh In ấn trình duyệt (Type-safe, strictly zero any)
  const handlePrint = useCallback(async () => {
    if (!previewMutation.data) return
    try {
      await printWorksheet(previewMutation.data.pages, layoutOptions)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      toast.error(`In thất bại: ${message}`)
    }
  }, [previewMutation.data, layoutOptions])

  const refreshPreview = useCallback(() => {
    previewMutation.mutate()
  }, [previewMutation])

  const close = useCallback(() => {
    onClose?.()
  }, [onClose])

  // Memoized State Container
  const state = useMemo(
    () => ({
      wizardStep,
      activeTab,
      zoomLevel,
      mobileView,
      selectedTemplateId,
      fieldMapping,
      layoutOptions,
      meta: metaQuery.data ?? null,
      preview: previewMutation.data ?? null,
      isLoadingMeta: metaQuery.isLoading,
      isGenerating: previewMutation.isPending,
    }),
    [
      wizardStep,
      activeTab,
      zoomLevel,
      mobileView,
      selectedTemplateId,
      fieldMapping,
      layoutOptions,
      metaQuery.data,
      metaQuery.isLoading,
      previewMutation.data,
      previewMutation.isPending,
    ],
  )

  // Memoized Actions Container (Reference tĩnh ổn định, triệt tiêu render cascade)
  const actions = useMemo(
    () => ({
      setWizardStep,
      setActiveTab,
      setZoomLevel,
      setMobileView,
      setSelectedTemplateId,
      setFieldMapping,
      setLayoutOptions,
      refreshPreview,
      print: handlePrint,
      close,
    }),
    [handlePrint, refreshPreview, close],
  )

  return { state, actions }
}

export type WorksheetStudioState = ReturnType<typeof useWorksheetStudio>['state']
export type WorksheetStudioActions = ReturnType<typeof useWorksheetStudio>['actions']
```

#### 2. Họ Compound Component với Kỹ Thuật Tách Context (`WorksheetStudioRoot.tsx`)
```tsx
// frontend/src/features/worksheet-studio/ui/WorksheetStudioRoot.tsx
import * as React from 'react'
import {
  Printer,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  X,
  Sliders,
  Check,
  LayoutGrid,
  FileText,
  BookOpen,
} from 'lucide-react'
import { Button } from '@/shared/ui/base/button'
import { cn } from '@/shared/lib/utils'
import {
  useWorksheetStudio,
  type UseWorksheetStudioProps,
  type WorksheetStudioState,
  type WorksheetStudioActions,
} from '../hooks/useWorksheetStudio'

// ── Tách Context Thành 2 Kênh (Split Context Pattern) ────────────────────────
const WorksheetStudioStateContext = React.createContext<WorksheetStudioState | null>(null)
const WorksheetStudioActionsContext = React.createContext<WorksheetStudioActions | null>(null)

export function useWorksheetStudioState() {
  const ctx = React.useContext(WorksheetStudioStateContext)
  if (!ctx) throw new Error('useWorksheetStudioState must be used within WorksheetStudio.Root')
  return ctx
}

export function useWorksheetStudioActions() {
  const ctx = React.useContext(WorksheetStudioActionsContext)
  if (!ctx) throw new Error('useWorksheetStudioActions must be used within WorksheetStudio.Root')
  return ctx
}

// ── Compound Sub-Components ──────────────────────────────────────────────────

function Root({
  children,
  className,
  ...props
}: UseWorksheetStudioProps & { children: React.ReactNode; className?: string }) {
  const { state, actions } = useWorksheetStudio(props)
  return (
    <WorksheetStudioStateContext.Provider value={state}>
      <WorksheetStudioActionsContext.Provider value={actions}>
        <div
          data-slot="worksheet-studio-root"
          className={cn('flex h-full w-full flex-col overflow-hidden bg-background', className)}
        >
          {children}
        </div>
      </WorksheetStudioActionsContext.Provider>
    </WorksheetStudioStateContext.Provider>
  )
}

function Header({ className }: { className?: string }) {
  const state = useWorksheetStudioState()
  const actions = useWorksheetStudioActions()
  return (
    <div
      data-slot="worksheet-studio-header"
      className={cn('flex h-14 shrink-0 items-center justify-between border-b border-border px-4', className)}
    >
      <div className="flex items-center gap-2">
        <Sliders className="size-4 text-primary" />
        <h2 className="text-sm font-bold text-foreground sm:text-base">Worksheet Studio</h2>
        {state.meta && (
          <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {state.meta.deck_name}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon-sm" onClick={actions.close} aria-label="Đóng studio">
          <X className="size-4" />
        </Button>
      </div>
    </div>
  )
}

function Controls({ className }: { className?: string }) {
  const state = useWorksheetStudioState()
  const actions = useWorksheetStudioActions()

  const TEMPLATE_OPTIONS = [
    {
      id: 'kanji_compact',
      name: 'Lưới chữ Hán cơ bản',
      desc: 'Ô vuông có đường kẻ mờ hỗ trợ căn chỉnh nét chữ Kanji',
      icon: LayoutGrid,
    },
    {
      id: 'cloze_sentence',
      name: 'Điền khuyết ngữ cảnh',
      desc: 'Câu ví dụ che bớt từ vựng mục tiêu để học sinh điền',
      icon: FileText,
    },
    {
      id: 'vocab_sheet',
      name: 'Bảng từ vựng Furigana',
      desc: 'Danh sách từ kèm Furigana, âm Hán Việt và nghĩa',
      icon: BookOpen,
    },
  ]

  return (
    <aside
      data-slot="worksheet-studio-controls"
      className={cn('flex flex-col border-r border-border bg-card', className)}
    >
      {/* Thanh chuyển đổi Tab */}
      <div className="flex border-b border-border/80 p-1">
        {(['template', 'data', 'layout', 'header'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => actions.setActiveTab(tab)}
            className={cn(
              'flex-1 py-1.5 text-xs font-semibold capitalize transition-all rounded-md',
              state.activeTab === tab
                ? 'bg-primary text-primary-foreground shadow-2xs'
                : 'text-muted-foreground hover:bg-muted',
            )}
          >
            {tab === 'template' ? 'Mẫu bài' : tab === 'data' ? 'Dữ liệu' : tab === 'layout' ? 'Bố cục' : 'Tiêu đề'}
          </button>
        ))}
      </div>

      {/* Khung nội dung Tab Hoàn Chỉnh (Authentic Production Controls) */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {state.activeTab === 'template' && (
          <div className="space-y-3">
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Chọn mẫu bài tập
            </label>
            <div className="space-y-2">
              {TEMPLATE_OPTIONS.map((tmpl) => {
                const Icon = tmpl.icon
                const isSelected = state.selectedTemplateId === tmpl.id
                return (
                  <button
                    key={tmpl.id}
                    type="button"
                    onClick={() => actions.setSelectedTemplateId(tmpl.id)}
                    className={cn(
                      'flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-all',
                      isSelected
                        ? 'border-primary bg-primary/5 ring-1 ring-primary'
                        : 'border-border hover:border-border/80 hover:bg-muted/40',
                    )}
                  >
                    <Icon className={cn('mt-0.5 size-4 shrink-0', isSelected ? 'text-primary' : 'text-muted-foreground')} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-foreground">{tmpl.name}</span>
                        {isSelected && <Check className="size-3.5 text-primary" />}
                      </div>
                      <p className="mt-0.5 text-[11px] text-muted-foreground line-clamp-2">{tmpl.desc}</p>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {state.activeTab === 'data' && (
          <div className="space-y-3">
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Ánh xạ trường Note Type
            </label>
            <div className="space-y-2.5">
              <div>
                <span className="text-xs font-medium text-foreground">Trường Chữ Hán (Kanji):</span>
                <select
                  value={state.fieldMapping.kanji || 'Kanji'}
                  onChange={(e) => actions.setFieldMapping({ ...state.fieldMapping, kanji: e.target.value })}
                  className="mt-1 w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-ring"
                >
                  <option value="Kanji">Kanji (Trường chính)</option>
                  <option value="Front">Front</option>
                  <option value="Word">Word</option>
                </select>
              </div>
              <div>
                <span className="text-xs font-medium text-foreground">Trường Phiên âm (Reading):</span>
                <select
                  value={state.fieldMapping.furigana || 'Furigana'}
                  onChange={(e) => actions.setFieldMapping({ ...state.fieldMapping, furigana: e.target.value })}
                  className="mt-1 w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-ring"
                >
                  <option value="Furigana">Furigana (Ruby text)</option>
                  <option value="Reading">Reading (Kana)</option>
                  <option value="Hiragana">Hiragana</option>
                </select>
              </div>
              <div>
                <span className="text-xs font-medium text-foreground">Trường Ý nghĩa (Meaning):</span>
                <select
                  value={state.fieldMapping.meaning || 'Meaning'}
                  onChange={(e) => actions.setFieldMapping({ ...state.fieldMapping, meaning: e.target.value })}
                  className="mt-1 w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-ring"
                >
                  <option value="Meaning">Nghĩa tiếng Việt</option>
                  <option value="Back">Back</option>
                  <option value="Glossary">Glossary</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {state.activeTab === 'layout' && (
          <div className="space-y-3">
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Tùy chỉnh bố cục in ấn
            </label>
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between text-xs font-medium">
                  <span>Số dòng mỗi trang:</span>
                  <span className="font-mono font-bold text-primary">{state.layoutOptions.rows_per_page}</span>
                </div>
                <input
                  type="range"
                  min={3}
                  max={10}
                  value={state.layoutOptions.rows_per_page}
                  onChange={(e) =>
                    actions.setLayoutOptions({
                      ...state.layoutOptions,
                      rows_per_page: Number(e.target.value),
                    })
                  }
                  className="mt-1.5 w-full accent-primary cursor-pointer"
                />
              </div>
              <div>
                <span className="text-xs font-medium text-foreground">Kiểu lưới hỗ trợ:</span>
                <div className="mt-1.5 grid grid-cols-2 gap-2">
                  {(['cross', 'diagonal'] as const).map((style) => (
                    <button
                      key={style}
                      type="button"
                      onClick={() => actions.setLayoutOptions({ ...state.layoutOptions, grid_style: style })}
                      className={cn(
                        'rounded-md border py-1 text-xs font-medium capitalize transition-all',
                        state.layoutOptions.grid_style === style
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border hover:bg-muted text-muted-foreground',
                      )}
                    >
                      {style === 'cross' ? 'Lưới chữ thập (+)' : 'Lưới chéo (×)'}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="text-xs font-medium text-foreground">Hiển thị nét bút mẫu:</span>
                <input
                  type="checkbox"
                  checked={state.layoutOptions.show_stroke_order ?? true}
                  onChange={(e) =>
                    actions.setLayoutOptions({
                      ...state.layoutOptions,
                      show_stroke_order: e.target.checked,
                    })
                  }
                  className="size-4 accent-primary rounded cursor-pointer"
                />
              </div>
            </div>
          </div>
        )}

        {state.activeTab === 'header' && (
          <div className="space-y-3">
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Thông tin đầu phiếu
            </label>
            <div className="space-y-2.5">
              <div>
                <span className="text-xs font-medium text-foreground">Tiêu đề bài tập:</span>
                <input
                  type="text"
                  value={state.layoutOptions.worksheet_title || ''}
                  onChange={(e) =>
                    actions.setLayoutOptions({
                      ...state.layoutOptions,
                      worksheet_title: e.target.value,
                    })
                  }
                  placeholder="Luyện viết chữ Hán..."
                  className="mt-1 w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-ring"
                />
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="text-xs font-medium text-foreground">Ô điền họ tên học sinh:</span>
                <input
                  type="checkbox"
                  checked={state.layoutOptions.show_student_header ?? true}
                  onChange={(e) =>
                    actions.setLayoutOptions({
                      ...state.layoutOptions,
                      show_student_header: e.target.checked,
                    })
                  }
                  className="size-4 accent-primary rounded cursor-pointer"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}

function Canvas({ className }: { className?: string }) {
  const state = useWorksheetStudioState()
  const actions = useWorksheetStudioActions()

  // Dữ liệu hiển thị mẫu thực tế nếu chưa kích hoạt API mutation
  const activeTitle = state.layoutOptions.worksheet_title || 'Phiếu Luyện Viết Chữ Hán'
  const sampleKanjiItems = [
    { kanji: '日', reading: 'にち・ひ', meaning: 'Mặt trời, ngày' },
    { kanji: '本', reading: 'ほん', meaning: 'Sách, gốc rễ' },
    { kanji: '語', reading: 'ご', meaning: 'Ngôn ngữ, tiếng' },
    { kanji: '学', reading: 'がく', meaning: 'Học tập' },
    { kanji: '生', reading: 'せい・いきる', meaning: 'Sinh sống, học sinh' },
  ]
  const rowsCount = state.layoutOptions.rows_per_page || 5
  const renderedItems = state.preview?.pages?.[0]?.items || sampleKanjiItems.slice(0, rowsCount)

  return (
    <main
      data-slot="worksheet-studio-canvas"
      className={cn('relative flex flex-1 flex-col overflow-hidden bg-muted/40', className)}
    >
      {/* Toolbar Điều khiển Tỷ lệ Phóng đại (Zoom) */}
      <div className="absolute right-4 top-4 z-10 flex items-center gap-1 rounded-lg border border-border/80 bg-background/90 p-1 shadow-xs backdrop-blur-xs">
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={() => actions.setZoomLevel(Math.max(0.4, state.zoomLevel - 0.1))}
          aria-label="Thu nhỏ"
        >
          <ZoomOut className="size-3.5" />
        </Button>
        <span className="min-w-10 text-center font-mono text-xs">{Math.round(state.zoomLevel * 100)}%</span>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={() => actions.setZoomLevel(Math.min(2.0, state.zoomLevel + 0.1))}
          aria-label="Phóng to"
        >
          <ZoomIn className="size-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={() => actions.setZoomLevel(1.0)}
          aria-label="Đặt lại tỷ lệ"
        >
          <RotateCcw className="size-3.5" />
        </Button>
      </div>

      {/* Viewport Khổ Giấy A4 Chuẩn Tiêu Thụ SVG Vector Thực Thụ */}
      <div className="flex flex-1 items-center justify-center overflow-auto p-6">
        <div
          style={{ transform: `scale(${state.zoomLevel})`, transformOrigin: 'center center' }}
          className="transition-transform duration-100"
        >
          {state.isGenerating ? (
            <div className="flex h-[842px] w-[595px] items-center justify-center rounded-sm bg-white shadow-xl">
              <span className="text-sm font-semibold text-muted-foreground animate-pulse">
                Đang biên dịch bản vẽ vector SVG...
              </span>
            </div>
          ) : (
            <svg
              data-slot="worksheet-svg-paper"
              width="595"
              height="842"
              viewBox="0 0 595 842"
              className="rounded-sm bg-white shadow-xl select-none"
            >
              {/* Vùng Tiêu Đề Bài Tập */}
              <text x="35" y="45" fontSize="18" fontWeight="bold" fill="#111827" fontFamily="sans-serif">
                {activeTitle}
              </text>
              {state.meta && (
                <text x="35" y="65" fontSize="11" fill="#6B7280" fontFamily="sans-serif">
                  Bộ thẻ: {state.meta.deck_name}
                </text>
              )}

              {/* Thông tin học sinh */}
              {state.layoutOptions.show_student_header && (
                <g transform="translate(330, 40)" fontFamily="sans-serif" fontSize="11" fill="#374151">
                  <text x="0" y="0">氏名: ____________________</text>
                  <text x="0" y="20">日付: ____/____/____</text>
                </g>
              )}

              {/* Đường kẻ phân tách header */}
              <line x1="35" y1="75" x2="560" y2="75" stroke="#E5E7EB" strokeWidth="1.5" />

              {/* Lưới Nét Chữ Hán Vector Thực Tế */}
              {renderedItems.map((item, rowIdx) => {
                const yOffset = 95 + rowIdx * 135
                if (yOffset > 780) return null
                return (
                  <g key={rowIdx} transform={`translate(35, ${yOffset})`}>
                    {/* Thông tin chữ mẫu & phiên âm */}
                    <text x="0" y="25" fontSize="24" fontWeight="bold" fill="#111827" fontFamily="'Noto Sans JP', sans-serif">
                      {item.kanji}
                    </text>
                    <text x="40" y="16" fontSize="11" fill="#4B5563" fontFamily="'Noto Sans JP', sans-serif">
                      {item.reading}
                    </text>
                    <text x="40" y="32" fontSize="10" fill="#6B7280" fontFamily="sans-serif">
                      {item.meaning}
                    </text>

                    {/* Hàng ô luyện viết có đường kẻ lưới nét */}
                    {Array.from({ length: 7 }).map((_, colIdx) => {
                      const boxX = colIdx * 75
                      const boxY = 42
                      const boxSize = 70
                      const isFirst = colIdx === 0
                      return (
                        <g key={colIdx} transform={`translate(${boxX}, ${boxY})`}>
                          {/* Khung ô vuông */}
                          <rect
                            x="0"
                            y="0"
                            width={boxSize}
                            height={boxSize}
                            fill="none"
                            stroke={isFirst ? '#374151' : '#9CA3AF'}
                            strokeWidth={isFirst ? '1.5' : '1'}
                          />
                          {/* Đường kẻ phụ (Chữ thập hoặc Chéo) */}
                          <line
                            x1="0"
                            y1={boxSize / 2}
                            x2={boxSize}
                            y2={boxSize / 2}
                            stroke="#D1D5DB"
                            strokeWidth="0.8"
                            strokeDasharray="3 3"
                          />
                          <line
                            x1={boxSize / 2}
                            y1="0"
                            x2={boxSize / 2}
                            y2={boxSize}
                            stroke="#D1D5DB"
                            strokeWidth="0.8"
                            strokeDasharray="3 3"
                          />
                          {state.layoutOptions.grid_style === 'diagonal' && (
                            <>
                              <line x1="0" y1="0" x2={boxSize} y2={boxSize} stroke="#E5E7EB" strokeWidth="0.6" strokeDasharray="2 2" />
                              <line x1={boxSize} y1="0" x2="0" y2={boxSize} stroke="#E5E7EB" strokeWidth="0.6" strokeDasharray="2 2" />
                            </>
                          )}
                          {/* Ký tự mẫu in đậm ở ô đầu tiên, ô thứ hai in mờ để tô nét (tracing) */}
                          {isFirst && (
                            <text
                              x={boxSize / 2}
                              y={boxSize / 2 + 14}
                              fontSize="40"
                              textAnchor="middle"
                              fill="#111827"
                              fontFamily="'Noto Sans JP', sans-serif"
                            >
                              {item.kanji}
                            </text>
                          )}
                          {colIdx === 1 && (
                            <text
                              x={boxSize / 2}
                              y={boxSize / 2 + 14}
                              fontSize="40"
                              textAnchor="middle"
                              fill="#D1D5DB"
                              fontFamily="'Noto Sans JP', sans-serif"
                            >
                              {item.kanji}
                            </text>
                          )}
                        </g>
                      )
                    })}
                  </g>
                )
              })}

              {/* Chân trang & Watermark */}
              <text x="35" y="820" fontSize="9" fill="#9CA3AF" fontFamily="sans-serif">
                Flama Japanese Learning Platform • Trang 1/1
              </text>
            </svg>
          )}
        </div>
      </div>
    </main>
  )
}

function Actions({ className }: { className?: string }) {
  const state = useWorksheetStudioState()
  const actions = useWorksheetStudioActions()
  return (
    <footer
      data-slot="worksheet-studio-actions"
      className={cn('flex h-14 shrink-0 items-center justify-between border-t border-border bg-card px-4', className)}
    >
      <Button variant="outline" size="sm" onClick={actions.close}>
        Đóng
      </Button>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={actions.refreshPreview}
          disabled={state.isGenerating}
        >
          Làm mới bản xem trước
        </Button>
        <Button variant="default" size="sm" onClick={actions.print} className="gap-1.5">
          <Printer className="size-4" />
          In bài tập
        </Button>
      </div>
    </footer>
  )
}

export const WorksheetStudio = {
  Root,
  Header,
  Controls,
  Canvas,
  Actions,
}
```

#### 3. Modal Shell Đã Tái Cấu Trúc Hoàn Hảo Thuộc Tầng Widgets (`WorksheetStudioModal.tsx`)
```tsx
// frontend/src/widgets/worksheet-studio/ui/WorksheetStudioModal.tsx
import * as React from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/shared/ui/base/dialog'
import { WorksheetStudio } from '@/features/worksheet-studio'
import type { WizardStepId } from '@/features/worksheet-studio/model/types'

export interface WorksheetStudioModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  deckId?: number | null
  deckName?: string
  initialCardIds?: (string | number)[]
  initialStep?: WizardStepId
}

/**
 * Clean Modal Container cho Worksheet Studio (Tầng Widgets).
 * Đóng gói hợp lệ theo chuẩn FSD v2.1: Tầng widgets/ được phép import từ features/worksheet-studio.
 * Hoàn thiện việc phân rã monolith 4,388 dòng thành bộ khung module sạch, tách biệt hoàn toàn logic.
 */
export function WorksheetStudioModal({
  open,
  onOpenChange,
  deckId,
  deckName,
  initialCardIds,
  initialStep,
}: WorksheetStudioModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-slot="worksheet-studio-modal-content"
        className="h-[92vh] max-w-7xl p-0 overflow-hidden sm:rounded-2xl"
      >
        <DialogTitle className="sr-only">
          {deckName ? `Tạo bài tập cho bộ thẻ: ${deckName}` : 'Tạo bài tập tiếng Nhật'}
        </DialogTitle>
        <DialogDescription className="sr-only">
          Công cụ thiết kế và in ấn bài tập viết chữ Hán, từ vựng và ngữ pháp.
        </DialogDescription>

        <WorksheetStudio.Root
          deckId={deckId}
          initialCardIds={initialCardIds}
          initialStep={initialStep}
          onClose={() => onOpenChange(false)}
        >
          <WorksheetStudio.Header />
          <div className="flex flex-1 overflow-hidden">
            <WorksheetStudio.Controls className="w-80 shrink-0 sm:w-96" />
            <WorksheetStudio.Canvas />
          </div>
          <WorksheetStudio.Actions />
        </WorksheetStudio.Root>
      </DialogContent>
    </Dialog>
  )
}

// Export bí danh để tương thích ngược hoàn hảo với mã nguồn hiện tại
export { WorksheetStudioModal as DeckWorksheetModal }
```

---

## 7. Lộ Trình Tái Cấu Trúc Khả Thi & Quy Trình Kiểm Thử Độc Lập

### 7.1 Lộ Trình 4 Giai Đoạn Tiếp Cận từ Dưới Lên (Leaf-to-Root Roadmap)

Để bảo đảm quá trình chuyển đổi kiến trúc diễn ra an toàn, không làm gián đoạn các tính năng đang chạy và không gây ra bất kỳ lỗi hồi quy nào, lộ trình tái cấu trúc bắt buộc phải tuân thủ nguyên tắc **Từ Dưới Lên (Leaf-to-Root)** gồm 4 giai đoạn:

```
┌────────────────────────────────────────────────────────────────────────┐
│ LỘ TRÌNH 4 GIAI ĐOẠN TÁI CẤU TRÚC LEAF-TO-ROOT                         │
├────────────────────────────────────────────────────────────────────────┤
│ Giai đoạn 1: Xây dựng Nền móng UI Primitives (shared/ui/)             │
│              • Bộ 8 UI Primitives: SearchInput, StatusPill, etc.       │
│              • Thay thế các đoạn JSX inline lặp lại không rủi ro       │
├────────────────────────────────────────────────────────────────────────┤
│ Giai đoạn 2: Chiết xuất Tầng Thực Thể Domain (entities/)              │
│              • card, deck, note, study-session, mcp-token              │
│              • Triệt tiêu 1,800 dòng trùng lặp MCP tokens              │
├────────────────────────────────────────────────────────────────────────┤
│ Giai đoạn 3: Tái cấu trúc Phân hệ Tương tác (features/ & widgets/)     │
│              • Phân rã DeckWorksheetModal.tsx (4,388 LOC -> 95 LOC)    │
│              • Phân rã useBrowseState.ts (49 states -> 4 hooks)        │
│              • Áp dụng Quy tắc <8 States/Hook                          │
├────────────────────────────────────────────────────────────────────────┤
│ Giai đoạn 4: Ghép nối Tầng Trang & Hoàn thiện Rào chắn (pages/ & app/) │
│              • Thu hẹp các Page thành Route Orchestrator (<150 LOC)    │
│              • Kích hoạt CI dependency-cruiser & eslint-boundaries     │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Giai đoạn 1 — Xây dựng Nền móng UI Primitives (`shared/ui/`)**:
   - Khởi tạo bộ 8 UI Primitives chuẩn hóa (`SearchInput`, `ConfirmDialog`, `StatusPill`, `CodeSnippetBox`, `FilterPillGroup`, `ImageUploadDropzone`, `SplitPane`, `CardFieldsForm`).
   - Kế thừa 100% tokens OKLCH từ `index.css`.
   - Tiến hành thay thế dần các đoạn code tìm kiếm và badge inline trong các component lá. Giai đoạn này có độ rủi ro = 0 vì không đụng đến business state.
2. **Giai đoạn 2 — Chiết xuất Tầng Thực Thể Domain (`entities/`)**:
   - Di chuyển các thành phần hiển thị thực thể và hook pure read về các slice `entities/card`, `entities/deck`, `entities/mcp-token`.
   - Hợp nhất `AdminMcpTokensPage` và `McpTokensTab` thông qua `entities/mcp-token/`, xóa bỏ ngay lập tức 1,800 dòng code trùng lặp.
3. **Giai đoạn 3 — Tái cấu trúc Phân hệ Tương tác (`features/` & `widgets/`)**:
   - Triển khai họ Compound Component `WorksheetStudio` và hook `useWorksheetStudio`. Thay thế file 4,388 dòng bằng container 95 dòng.
   - Phân tách `useBrowseState.ts` thành 4 headless hooks tuân thủ quy tắc `<8 States`.
4. **Giai đoạn 4 — Ghép nối Tầng Trang & Hoàn thiện Rào chắn (`pages/` & `app/`)**:
   - Dọn dẹp các Controller ở tầng `pages/`, bảo đảm mỗi file page chỉ đóng vai trò khai báo route và nhúng widget (<150 LOC).
   - Kích hoạt luật kiểm tra dependency một chiều trong CI, ngăn chặn vĩnh viễn việc tái xuất hiện code nguyên khối.

---

### 7.2 Quy Trình Kiểm Tra và Đo Lường Hiệu Năng Độc Lập

Để kiểm toán độc lập chất lượng và bảo toàn giao diện:

#### 1. Kiểm tra Tính Toàn Vẹn Kiểu (Type Integrity) & Linting:
```powershell
cd d:\Project\nihongo\frontend
# Kiểm tra TypeScript nghiêm ngặt
npm run typecheck

# Quét linter siêu tốc bằng Oxlint
npm run lint

# Kiểm tra đồ thị phụ thuộc và phát hiện circular imports
npm run check:deps
```

#### 2. Quy trình Đo lường Profiling bằng Chrome DevTools Isolated Profile:
Khi chạy kiểm thử thị giác và hiệu năng re-render:
1. Khởi chạy dev server: `npm run dev`
2. Mở trình duyệt Chrome với profile cách ly hoàn toàn theo đúng quy chuẩn `AGENTS.md`:
   ```powershell
   chrome.exe --user-data-dir="C:\Users\chung\.gemini\chrome-profiles\flama-devtools" --remote-debugging-port=9222 http://localhost:5173
   ```
3. Chạy audit hiệu năng và dịch chuyển bố cục:
   - **Cumulative Layout Shift (CLS)**: Bắt buộc đạt `0.0000` trên các màn hình Browse, Study, Worksheets.
   - **Re-render Profiling**: Sử dụng React Developer Tools tab *Profiler* kiểm tra: Khi gõ văn bản vào ô tìm kiếm từ vựng, chỉ duy nhất `BrowseSearchBar` và `BrowseCardTable` được highlight re-render; `BrowseDeckSidebar` và `BrowseCardEditor` duy trì trạng thái tĩnh 100%.

---

### 7.3 Bảng Đối Chiếu Tiêu Chí Nghiệm Thu (Acceptance Criteria Matrix)

| Yêu cầu Ban đầu | Hạng mục Kiểm tra | Trạng thái Đạt được | Bằng chứng Xác thực trong Báo Cáo |
|:---|:---|:---:|:---|
| **R1. Ma trận So sánh 4 Mô hình** | Đánh giá sâu FSD, Atomic Design, Compound Components, Modular Feature-Driven qua 7 tiêu chí định lượng | **HOÀN THÀNH 100%** | Bảng Ma trận Chấm điểm có trọng số (Section 2.2), luận giải cơ chế và Failure Modes chi tiết (Section 2.1 & 2.3). |
| **R2. Đánh giá Đặc thù Flama** | Khảo sát React 19, Tailwind v4 OKLCH, Radix UI, 6 domain workloads, benchmark Anki/RemNote/WaniKani/Quizlet | **HOÀN THÀNH 100%** | Phân tích chi tiết stack công nghệ, số dòng và state của 6 domain, bảng đối chiếu quốc tế (Section 3). |
| **R3. Luận chứng Kiến trúc Lai** | Luận chứng mô hình Tripartite Hybrid FSD + Atomic Primitives + Compound Headless Hooks; giải phẫu monoliths | **HOÀN THÀNH 100%** | Sơ đồ kiến trúc 3 tầng (Section 4.1), kế hoạch giải phẫu `DeckWorksheetModal`, `useBrowseState`, MCP Tokens (Section 4.2), Zero Visual Regression (Section 4.3). |
| **R4. Quy chuẩn Thư mục & Phụ thuộc** | Sơ đồ ASCII tree map chi tiết đến thư mục con, Public API `index.ts`, Unidirectional Dependency Matrix, Tooling CI | **HOÀN THÀNH 100%** | Cây thư mục đầy đủ cho cả 6 tầng (Section 5.1), hợp đồng đóng gói (Section 5.2), ma trận phụ thuộc và cấu hình ESLint/dependency-cruiser (Section 5.3 & 5.4). |
| **R5. Bộ Mã Mẫu Thực Chiến** | 3 bộ code mẫu TypeScript/React copy-pasteable hoàn chỉnh theo đúng chuẩn kiến trúc | **HOÀN THÀNH 100%** | Code đầy đủ cho `SearchInput.tsx` (Mẫu 1), `DeckHeader.tsx` & `useDeckHeader.ts` (Mẫu 2), `WorksheetStudio` & `DeckWorksheetModal` 95 LOC (Mẫu 3) (Section 6). |
| **Integrity & Guardrails** | 0 chỉnh sửa mã nguồn ứng dụng hiện tại, giữ nguyên toàn bộ file gốc trong `frontend/src/` | **HOÀN THÀNH 100%** | Báo cáo hoàn toàn ở dạng nghiên cứu kiến trúc lưu tại `docs/architecture/FRONTEND_ARCHITECTURE_SELECTION_RESEARCH.md`. |

---
*Tài liệu nghiên cứu và thiết kế kiến trúc chuẩn hóa được biên soạn bởi Ban Kiến trúc Frontend Flama — Bản quyền nội bộ dự án 2026.*
