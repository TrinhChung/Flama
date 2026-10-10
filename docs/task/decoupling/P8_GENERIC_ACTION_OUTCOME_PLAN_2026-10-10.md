# Kế hoạch mức 3 — Action và outcome tổng quát (bỏ giả định bốn rating)

> **Trạng thái: để dành, chưa lên lịch.** Lập 2026-10-10 theo yêu cầu chủ sản phẩm, để triển khai khi đủ điều kiện ở §3. Loại: kế hoạch, **Runtime change: none**. Không có code, migration hay flag.
>
> Căn cứ: [canonical plan §6–§8](../../architecture/study-interaction-trigger-algorithm-plan.md#6-generic-interaction-component-role), [P8/P9 readiness §2](./P8_P9_READINESS_2026-09-30.md#2-phase-8--cần-chủ-sản-phẩm-chọn-năng-lực-đầu-tiên), [P9 closeout](./P9_CLOSEOUT_2026-10-03.md) (P9-09 "generic rating" chưa làm vì chưa có replacement; kế hoạch này chính là replacement đó). Kiểm kê §4 đọc tại `ea6d68fe`.

## 1. Mục tiêu

Hiện mọi tầng học đều giả định đúng bốn rating `again/hard/good/easy`: từ nút, phím tắt, wire, Trigger, interface Algorithm, đến event, analytics, MCP và đồng bộ Anki. Mức 3 tách giả định đó khỏi phần generic:

- Interaction phát được Action ngoài bốn rating, có payload phiên bản hóa (ví dụ outcome đúng/sai/gần đúng, thang 5 mức).
- Trigger và Algorithm nhận input tổng quát. Algorithm khai báo loại input nó chấp nhận và từ chối (fail closed) loại không hỗ trợ.
- Bốn rating trở thành **một adapter built-in**, hành vi giữ nguyên từng byte (golden vectors không đổi).
- Event, thống kê và màn hoàn thành tính theo outcome của chế độ, không ép vào bốn ô.

Ngoài phạm vi: evaluator/verifier cho trắc nghiệm và gõ có chấm tự động (§6.3 canonical plan; trắc nghiệm đang hoãn), chuỗi trigger nối tiếp (§7.5), code tùy ý của người dùng, đơn vị tiến độ theo mục kiến thức (cách C), thuật toán mới (FSRS thật). Các năng lực này *dùng* mức 3 nhưng có kế hoạch riêng.

## 2. Ba mức nới contract bốn nút

| Mức | Nội dung | Kế hoạch |
|---|---|---|
| 1. Hiển thị | Ẩn/hiện khoảng thời gian, định dạng tiếng Việt, phím tắt, hành vi Space | Gói C1 trong tài liệu tùy chỉnh nút học (nhánh của PR #179, chưa có trên master) |
| 2. Tập con nút theo chế độ | StudyMode khai báo `allowed_actions` (ví dụ 2 nút chỉ gửi `again`/`good`), server kiểm tra | Gói C4 |
| **3. Action/outcome tổng quát** | **Tài liệu này** | Để dành |

Mức 1 và 2 dùng lại bốn Action sẵn có nên không cần mức 3. Nên làm mức 2 trước: nó tạo sẵn chỗ đóng băng tập Action trong snapshot phiên mà mức 3 sẽ dùng.

## 3. Điều kiện kích hoạt

Chỉ mở kế hoạch này khi có **năng lực đầu tiên được duyệt cần input khác bốn rating**, ví dụ:

- gõ đáp án có chấm tự động (outcome đúng/sai/gần đúng);
- trắc nghiệm được mở lại theo điều kiện ở readiness §2;
- thang đánh giá khác bốn mức;
- thuật toán mới có input không phải bốn rating.

Khi kích hoạt, lập kế hoạch thực thi cho năng lực đó song song; mức 3 là nền, không giao riêng mà không có người dùng.

## 4. Hiện trạng — nơi giả định bốn rating

Ảnh chụp tại `ea6d68fe`. Gói L3-00 phải kiểm kê lại bằng trace trước khi sửa.

| Tầng | Nơi | Giả định |
|---|---|---|
| Action/Trigger server | `app/services/study_action_runtime.py:22-23, 83-98` | `REVIEW_RATINGS` cố định; ánh xạ cứng `review.x` → `scheduler.review.x`, contract `1` |
| Interface Algorithm | `app/services/study_algorithm_registry.py:143-164`; `app/services/anki_scheduler.py:9` | `transition(CardState, DeckOptions, now, answer: Answer)`; `previews` trả `dict[Answer, …]` |
| Wire | `app/validators/study_session_wire.py:299-310`; client `session/wireContract.ts:202-274` | Event bắt buộc có `rating` thuộc bốn giá trị |
| Receipt/preview | `app/services/study_authority_receipt_service.py:82` | `direct_previews` phải có đúng bốn khóa |
| Trạng thái FSRS kế tiếp | `app/services/study_policy_service.py:70-73`; `study_session_service.py:438-441`; client `scheduler/types.ts:52` | Khóa theo bốn rating |
| REST | `app/validators/flashcard_input.py:731` | Chỉ nhận bốn giá trị |
| MCP | `app/services/mcp_tool_registry.py:965-970`; `app/validators/mcp.py:760`; `app/services/mcp/study_tools.py:400` | Enum bốn rating |
| Đồng bộ Anki | `app/services/anki_sync_service.py:771, 850` | ease 1–4 ↔ bốn rating |
| Lưu trữ | `models/review_event.py:40` | `rating` là `NOT NULL`; `study_progress_history_facts.action_key` đã nullable (`models/study_progress_history_fact.py:53`) |
| Analytics | `app/services/review_analytics_policy.py:143`; `app/repositories/review_analytics_repository.py:32`; `stats_query_repository.py:745, 841`; `admin_analytics_repository.py:86, 338`; `app/services/stats_overview.py:332` | "Đúng" = `good`/`easy` (kể cả `3`/`4` cũ) |
| Frontend types | `frontend/src/features/study/types.ts:8, 95, 246-266, 368`; `interactions/reviewInteraction.ts:11-41`; `scheduler/types.ts:65-66` | `Record<Rating, …>` là hình dạng chung của event, preview, outcome, thống kê |
| Frontend engine | `scheduler/legacyEngine.ts:16, 168, 232` | Bốn rating |
| UI | `interactions/ReviewInteractionControls.tsx`; `hooks/useStudyKeyboardShortcuts.ts`; `components/StudyCompletionCard.tsx`, `StudyCompletionBreakdown.tsx`, `StudyCompletionStatsGrid.tsx`; `hooks/useStudySession.ts` | Bốn nút, phím 1–4, đếm bốn rating |
| Golden vectors | `tests/fixtures/study/legacy-anki-1.0.0-golden-vectors.json` | Đóng băng kết quả và chuỗi preview theo bốn rating |

## 5. Thiết kế đích (đề xuất)

1. **Action envelope.** Mỗi Action có `action_key`, `action_contract_version` và `payload` theo schema phiên bản hóa. Bốn rating là Action `review.{again,hard,good,easy}` contract `1` như hiện tại (không đổi key để lịch sử đọc được). Action mới, ví dụ `answer.outcome` với payload `{outcome: correct|incorrect|partial}`, đi kèm contract riêng.
2. **Trigger contract khai báo input.** Mỗi Trigger định nghĩa schema payload, Algorithm input mà nó tạo ra và cách xử lý khi Algorithm không hỗ trợ. Ánh xạ outcome → input của `legacy-anki` (nếu có) là quyết định sản phẩm D-L3-02, không suy diễn trong code.
3. **Interface Algorithm tổng quát.** `transition(state, config, now, input)` với `input` là kiểu có phân biệt (discriminated), `previews` khóa theo `action_key`. Registry ghi loại input mỗi phiên bản Algorithm chấp nhận. `legacy-anki/1.0.0` được bọc bằng adapter nhận đúng input bốn rating; không sửa công thức, không đổi phiên bản.
4. **Snapshot phiên.** Phiên đóng băng tập Action/Trigger cho phép (mở rộng từ `allowed_actions` của mức 2) cùng contract version; server từ chối Action ngoài tập.
5. **Wire.** Thêm phiên bản wire mới mang Action envelope. v4 giữ nguyên; v2/v3 vẫn theo quyết định giữ compatibility ở P9. Session đã mở tiếp tục dùng wire của nó.
6. **Lưu trữ (chỉ expand).** Migration additive: cột outcome/action trên `review_events` nullable, `rating` chuyển nullable chỉ khi có Action không phải rating (quyết định D-L3-05). Không viết lại dòng lịch sử. Event bốn rating vẫn ghi `rating` như cũ.
7. **Analytics.** Định nghĩa "đúng" theo outcome, với ánh xạ cố định cho rating (`good`/`easy` = đúng) để số cũ không đổi. Gộp với quyết định D-U6 về "Tỉ lệ đúng".
8. **Adapter ngoài.** MCP giữ tool rating như adapter; công cụ generic theo câu hỏi mở 16.3 #12. Đồng bộ Anki chỉ hiểu ease 1–4: event không phải rating được ánh xạ hoặc không xuất (D-L3-04).
9. **Frontend.** Kiểu event/preview/outcome/thống kê generic; bốn rating chỉ còn trong component built-in. Trùng phạm vi với Interaction host (P8-UI-1) và event/thống kê tổng quát (P8-UI-2); làm chung một đợt.

## 6. Quyết định cần chủ sản phẩm

| ID | Câu hỏi | Gợi ý ban đầu |
|---|---|---|
| D-L3-01 | Tập outcome chung (đúng/sai/gần đúng? mức tự tin?) | Bắt đầu với đúng/sai/gần đúng; mở rộng bằng contract version mới |
| D-L3-02 | Outcome ánh xạ vào `legacy-anki` thế nào, hay bắt buộc Algorithm mới | Không ánh xạ ngầm. Nếu ánh xạ, ghi rõ trong Trigger contract và có golden vectors; cân nhắc cảnh báo khoảng ôn bị kéo dài (lý do hoãn trắc nghiệm) |
| D-L3-03 | Màn hoàn thành và thống kê theo chế độ hiển thị gì | Theo outcome của chế độ; tổng hợp chung chỉ dùng số lượt và "đúng" |
| D-L3-04 | Event không phải rating có xuất sang Anki không | Không xuất, hoặc ánh xạ cố định có ghi chú; quyết định trước khi bật năng lực đầu tiên |
| D-L3-05 | `review_events.rating` chuyển nullable hay luôn ghi rating tương đương | Nullable cho Action mới; giữ nguyên cho bốn rating |
| D-L3-06 | MCP có công cụ generic không | Giữ adapter rating; generic khi có người dùng MCP cần |

## 7. Work package

Mỗi gói là một PR riêng, có test và (nếu đụng lưu trữ) probe MySQL. L3-02/L3-03 không đổi hành vi nên có thể giao trước năng lực đầu tiên.

| ID | Nội dung | Phụ thuộc | Kết quả |
|---|---|---|---|
| L3-00 | Kiểm kê lại callsite bằng trace; baseline golden vectors và số liệu analytics | §3 kích hoạt | Danh sách callsite cuối cùng |
| L3-01 | ADR Action envelope, Trigger contract, input Algorithm; chốt D-L3-01..06 | L3-00 | ADR được duyệt |
| L3-02 | Backend: registry Action/Trigger generic, bốn rating thành adapter built-in | L3-01 | Không đổi hành vi; test cũ xanh |
| L3-03 | Interface Algorithm generic, previews theo `action_key`, registry khai báo input; adapter `legacy-anki` | L3-02 | Golden vectors không đổi cả hai phía |
| L3-04 | Migration expand cho event/history; repository đọc cả hai dạng | L3-01 | Probe MySQL nâng cấp từ head production, dữ liệu cũ không đổi |
| L3-05 | Wire mới + validator + snapshot tập Action cho phép; client wireContract | L3-02, mức 2 | v4 và v2/v3 vẫn qua test |
| L3-06 | Frontend: kiểu generic, Interaction host, thống kê và màn hoàn thành theo outcome | L3-05, P8-UI-1/2 | Zero visual regression cho chế độ bốn nút |
| L3-07 | Analytics/dashboard theo outcome | L3-04 | Số liệu bốn rating trùng baseline L3-00 |
| L3-08 | MCP, đồng bộ Anki/Connect theo D-L3-04/06 | L3-04 | Event bốn rating đồng bộ như cũ |
| INT-L3 | Tích hợp: backend `--all`, frontend, build, golden vectors hai phía, probe MySQL, luồng trình duyệt | L3-02..08 | Đủ điều kiện cho năng lực đầu tiên |

## 8. Bất biến

- Không mất hoặc hỏng dữ liệu learner; không viết lại `review_events` hay history đã có.
- Hành vi bốn rating và `legacy-anki/1.0.0` giữ nguyên từng byte; golden vectors hiện có không sửa.
- Phiên đang mở và job đã nhận replay đúng contract đã đóng băng.
- Template/iframe không có quyền ghi tiến độ (ADR phím tắt tin cậy).
- Tiến độ vẫn một dòng cho mỗi learner × Note (quyết định 1).
- Đồng bộ Anki của event bốn rating không đổi.

## 9. Kiểm chứng

- `python scripts/run_tests.py --module study,flashcards,connect_mcp` cho từng gói; `--all` ở INT-L3.
- Golden vectors client/server cho mọi adapter (bốn rating và Action mới).
- Probe MySQL cho L3-04 theo mẫu P6/P10.
- Luồng trình duyệt dùng profile Chrome riêng theo `AGENTS.md`.

## 10. Handoff

```text
Task ID: P8-L3-GENERIC-ACTION-OUTCOME
Primary outcome: kế hoạch để dành cho Action/outcome tổng quát; kiểm kê callsite bốn rating; quyết định D-L3-01..06; work package L3-00..L3-08/INT-L3
Files changed: docs/task/decoupling/P8_GENERIC_ACTION_OUTCOME_PLAN_2026-10-10.md (mới); liên kết trong README.md, P8_P9_READINESS_2026-09-30.md, canonical plan Phase 8
Runtime change: none
Tests added or updated: none (kế hoạch)
Known limitations: kiểm kê §4 dựa trên grep tại ea6d68fe, L3-00 phải trace lại; gói C1/C4 (mức 1–2) nằm trong tài liệu tùy chỉnh nút học chưa có trên master
```
