# Sổ nợ kỹ thuật — UI/UX sau decoupling, mô hình chia sẻ Template, cài đặt ôn tập

> Lập 2026-09-30. Mỗi khoản nợ có một file task riêng theo khuôn của [`docs/task/decoupling/`](../decoupling/README.md): mục tiêu, bằng chứng, file dự kiến, công việc, output, acceptance, verification, rollback, phần không làm.
>
> Nguồn điều tra:
> - [Điều tra UI/UX trước P8](../decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md) — mã `UX-*`, `P8-UI-*`;
> - [Hành trình người dùng các phase đã xong](../decoupling/UIUX_COMPLETED_PHASES_USER_JOURNEY_AUDIT_2026-09-30.md) — mã `T*`, `S*`, `N*`, `D*`, `A*`, và §5b vị trí module hóa Template;
> - [Tùy chỉnh nút học và thuật toán](../decoupling/STUDY_BUTTONS_AND_ALGORITHM_CUSTOMIZATION_2026-09-30.md) — mã `C0..C5`.
>
> Chỉ đạo ưu tiên của chủ sản phẩm (2026-09-30):
> 1. UI cho Phase 8 làm **cuối cùng**.
> 2. Deck và Template dùng **chung cơ chế fork/phát hành/đóng góp**. Phải nghiên cứu tổng quát hóa để không phát triển lặp lại (TD-14).
> 3. **Không coi cơ chế deck hiện tại là chuẩn mực.** Phần nào chưa tốt thì đề xuất nâng cấp. TD-14 §2 đánh giá phản biện 12 điểm yếu (SE-01..SE-12); TD-15 sửa các điểm nền tảng **trước khi** thêm Template vào bộ máy chung.

## 1. Quy ước

| Thuộc tính | Giá trị |
|---|---|
| Mức | **P0** mất công sức người học hoặc kẹt không thoát được · **P1** sai lệch rõ, gây hiểu nhầm, chặn mục tiêu sản phẩm · **P2** nhất quán, chất lượng · **P3** nhỏ hoặc chuẩn bị cho P8 |
| Trạng thái | `TODO` → `IN PROGRESS` → `DONE`; `BLOCKED` kèm lý do; `DECISION` khi đang chờ chủ sản phẩm |
| Hoàn tất | Chỉ khi đủ mọi Output và Acceptance trong file task. Test xanh chưa đủ |
| Handoff | Dùng mẫu ở [decoupling README §5](../decoupling/README.md): Task ID, outcome, files, contract thay đổi, test, lệnh, kết quả, rollback, giới hạn, follow-up |

## 2. Invariants bắt buộc cho mọi khoản

1. Không mất hoặc hỏng dữ liệu learner. Không xóa IndexedDB hàng loạt, không replay tự động event sang phiên khác (khớp P9-08).
2. Giữ mô hình **overlay-only** cho deck chia sẻ: không copy hay mutate Note/Card nguồn, không quay lại clone copy toàn bộ (`AGENTS.md`, [`CLONE_CUTOVER_REPORT.md`](../../plans/completed/CLONE_CUTOVER_REPORT.md)).
3. Iframe Template không bao giờ có quyền lật thẻ, đánh giá hay ghi tiến độ ([ADR phím tắt tin cậy](../../architecture/trusted-study-keyboard-boundary-2026-09-07.md)).
4. Thuật toán được phân giải theo đúng key + version và fail closed. Không sửa `legacy-anki/1.0.0` tại chỗ.
5. Phiên đang mở giữ nguyên Template, binding và config đã đóng băng (P4-00). Thay đổi chỉ áp dụng cho phiên sau.
6. Zero Visual Regression trừ các thay đổi hình thức đã được duyệt trong task.
7. Chạy test theo module (`python scripts/run_tests.py --module …`); `--all` chỉ ở gate tích hợp.
8. Kiểm thử trình duyệt dùng profile Chrome riêng theo `AGENTS.md`.
9. Không thay đổi production (flag, migration, dữ liệu) khi chưa có phê duyệt riêng; migration theo Alembic, có rehearsal MySQL.

## 3. Sổ đăng ký

| ID | Khoản nợ | Mức | Đợt | Phụ thuộc | Lane | Ước lượng | Trạng thái |
|---|---|---|---|---|---|---|---|
| [TD-01](./TD-01_STUDY_LEASE_EXPIRY_AND_ROLLOVER.md) | Phiên quá hạn lease vẫn cho trả lời; `410` không được xử lý | P0 | W1 | TD-02 | FE Study | 2–3 ngày | `DECISION` (D-U1) |
| [TD-02](./TD-02_STUDY_SYNC_FAILURE_RECOVERY.md) | Lỗi đồng bộ vĩnh viễn kẹt vòng quay; thông điệp kỹ thuật | P0 | W1 | — | FE Study | 3–4 ngày | `TODO` |
| [TD-03](./TD-03_STUDY_SESSION_SAFETY_POLISH.md) | Không báo mất lưu bền; nhãn "Thoát không lưu" sai; focus nút; chỉ báo đồng bộ | P1 | W1 | TD-02 | FE Study | 2–3 ngày | `TODO` |
| [TD-04](./TD-04_TEMPLATE_MANAGEMENT_UI.md) | Trình quản lý Template: tạo, đổi tên, xóa, nhân bản, chống mất bản nháp | P1 | W2 | — | FE Note types | 3–4 ngày | `TODO` |
| [TD-05](./TD-05_FIELD_RENAME_TEMPLATE_DEPENDENCIES.md) | Đổi tên Field làm Template render rỗng, không cảnh báo | P1 | W2 | — | BE + FE | 2–3 ngày | `TODO` |
| [TD-06](./TD-06_STUDY_MODE_SELECTOR_AND_COMPLETION.md) | Bộ chọn cách học và màn hoàn thành | P1 | W2 | — | BE đọc + FE Study | 3–5 ngày | `DECISION` (D-U2, D-T3, D-U6) |
| [TD-07](./TD-07_CLONE_PROVENANCE_TRANSPARENCY.md) | Minh bạch nguồn gốc NoteType/Template khi clone; cảnh báo hotfix | P1 | W3 | — | BE đọc + FE | 3–4 ngày | `TODO` |
| [TD-08](./TD-08_GUIDE_AND_COPY_CORRECTNESS.md) | Hướng dẫn sai (phím tắt, Deck Settings, giới hạn/ngày, FSRS) | P1 | W4 | — | FE nội dung | 0,5–1 ngày | `TODO` |
| [TD-09](./TD-09_SEMANTIC_TOKENS_AND_TERMINOLOGY.md) | Token màu trạng thái, thuật ngữ, Việt hóa nhãn | P2 | W4 | — | FE | 2–3 ngày | `TODO` |
| [TD-10](./TD-10_STUDY_DISPLAY_PREFERENCES.md) | Tùy chọn hiển thị nút (khoảng thời gian, phím tắt, Space) | P2 | W4 | TD-09 | FE + BE nhỏ | 2–3 ngày | `DECISION` (D-C3) |
| [TD-11](./TD-11_DECK_SCHEDULING_SETTINGS.md) | Cài đặt ôn tập theo deck (preset) và người dùng; chặn nhãn FSRS | P1 | W4b | — | BE + FE | 4–6 ngày | `DECISION` (D-C1, D-C4, D-C5) |
| [TD-12](./TD-12_DAILY_NEW_AND_REVIEW_LIMITS.md) | Giới hạn thẻ mới / lượt ôn mỗi ngày; phiên quá 5.000 thẻ | P1 | W4b | TD-11 | BE + FE | 5–8 ngày | `DECISION` (D-C2) |
| [TD-13](./TD-13_TWO_BUTTON_INTERACTION_CONFIG.md) | Chế độ 2 nút bằng cấu hình Interaction theo cách học | P2 | W4b | TD-06 | BE + FE | 3–5 ngày | `DECISION` (D-C3) |
| [TD-14](./TD-14_GENERALIZED_SHARE_LIFECYCLE_RESEARCH.md) | **Nghiên cứu + ADR: tổng quát hóa vòng đời chia sẻ** (fork/release/rebase/đóng góp) cho Deck, NoteType, Template | P1 | W5 | — | Kiến trúc | 3–4 ngày | `TODO` |
| [TD-15](./TD-15_SHARE_ENGINE_ENTITY_ADAPTERS.md) | Trích bộ máy chia sẻ thành adapter theo `entity_kind` (không đổi hành vi) | P1 | W5 | TD-14 | BE | 5–8 ngày | `TODO` |
| [TD-16](./TD-16_TEMPLATE_RELEASE_ENTITY_KINDS.md) | Template/application thành entity kind có release, ghim phiên bản (6B #137; thay hotfix #138) | P1 | W5 | TD-15 | BE + FE | 6–9 ngày | `TODO` |
| [TD-17](./TD-17_INSTALL_LOCAL_TEMPLATE_FORK_AND_CONTRIBUTION.md) | Fork Template install-local cho thẻ gốc; gửi đề xuất Template về tác giả | P1 | W5 | TD-16 | BE + FE | 5–8 ngày | `TODO` |
| [TD-18](./TD-18_STANDALONE_TEMPLATE_SLOTS_BINDINGS.md) | Template độc lập có Slot và binding Field → Slot | P2 | W5 | TD-16, TD-05 | BE + FE | 8–12 ngày | `TODO` |
| [TD-19](./TD-19_MARKETPLACE_ON_SHARE_ENGINE.md) | NoteType và Template Marketplace chạy trên bộ máy chung | P2 | W5 | TD-17, TD-18 | BE + FE | 8–12 ngày | `TODO` |
| [TD-20](./TD-20_STUDY_INTERACTION_HOST.md) | Interaction host, event/thống kê tổng quát (P8-00) | P3 | W6 | TD-01, TD-02 | FE Study | 5–8 ngày | `TODO` |
| [TD-21](./TD-21_BROWSE_BY_NOTE.md) | Browse theo Note | P3 | W6 | — | BE + FE Browse | 4–6 ngày | `DECISION` (D-U5) |
| [TD-22](./TD-22_ANALYTICS_OUTCOME_AND_TERMINOLOGY.md) | Analytics theo outcome; tách `StudyMode`/`ReviewKind` | P3 | W6 | TD-20 | BE + FE | 3–4 ngày | `DECISION` (D-U6) |

Đợt:
- **W1** Phiên học an toàn;
- **W2** Template & cách học;
- **W3** Minh bạch clone;
- **W4** Nhất quán;
- **W4b** Cài đặt ôn tập;
- **W5** Module hóa Template trên bộ máy chia sẻ chung;
- **W6** Chuẩn bị P8 (làm cuối).

## 4. Thứ tự và phụ thuộc

```text
W1  TD-02 ──> TD-01
      └────> TD-03
W2  TD-04     TD-05     TD-06
W3  TD-07  (cảnh báo hotfix còn hiệu lực tới khi TD-16 xong)
W4  TD-08     TD-09 ──> TD-10
W4b TD-11 ──> TD-12        TD-06 ──> TD-13
W5  TD-14 ──> TD-15 ──> TD-16 ──> TD-17 ──> TD-19
                              └──> TD-18 ──┘
                    (TD-05 là bước tạm, TD-18 thay thế lâu dài)
W6  TD-20 ──> TD-22        TD-21
```

- W1–W4 chủ yếu là frontend trên API có sẵn, chạy song song được và không chặn P9.
- W5 chạm vùng rủi ro cao (release, overlay, clone); mỗi khoản cần plan theo mẫu P6 và rehearsal MySQL.
- Phối hợp P9: TD-01, TD-02, TD-03 cùng sửa `features/study` với phần frontend của P9-08; TD-20 chồng với P9-09 ("generic types giả định bốn rating"). Xếp lịch để không đổi cùng file song song.

## 5. Quyết định

| Mã | Nội dung | Trạng thái | Khoản bị ảnh hưởng |
|---|---|---|---|
| D-U1 | Phiên sắp hết hoặc đã hết lease | Chờ chốt (khuyến nghị: rollover chủ động; hết hạn thì cách ly + phiên mới) | TD-01 |
| D-U2 | Nhớ cách học đã chọn theo deck | Chờ chốt (khuyến nghị: nhớ ở client, vẫn bấm 1 lần) | TD-06 |
| D-U5 | Browse theo Note khi nào | Chờ chốt | TD-21 |
| D-U6 / D-C | "Tỉ lệ đúng" có tính "Khó" | Chờ chốt | TD-06, TD-22 |
| D-T1 | Người cài deck được sửa Template cho thẻ gốc | **Đã chốt** (#11: fork install-local) | TD-17 |
| D-T2 | Bản cài ghim phiên bản, sửa thì fork | **Đã chốt** (#10) | TD-16, TD-17 |
| D-T3 | Gộp thẻ gốc và thẻ tự thêm trong một phiên | Chờ chốt (#12 cho phép dùng chung Template) | TD-06, TD-17 |
| D-T4 / D-T5 | Template mới sao chép Template đang chọn; cho xóa Template | Khuyến nghị có | TD-04 |
| D-C1..D-C5 | Preset, kế thừa deck con, giới hạn/ngày, tầng tùy chỉnh nút, FSRS, deck đã cài | Chờ chốt | TD-10..TD-13 |
| Điều tra Template §14 #1–#21 | Clone & fork, Slot, binding linh hoạt, áp dụng lặp, Marketplace, soft delete… | **Đã chốt** | TD-16..TD-19 |

Nguồn quyết định Template: [điều tra Template/NoteType §14](../../architecture/template-notetype-decoupling-investigation.md).
