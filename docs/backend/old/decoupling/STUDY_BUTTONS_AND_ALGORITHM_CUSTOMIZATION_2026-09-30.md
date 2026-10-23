# Tùy chỉnh nút học và thuật toán lặp ngắt quãng — hiện trạng và cách sửa

> **Kế hoạch triển khai:** C0 → TD-08, C1 → TD-10, C2 → TD-11, C3 → TD-12, C4 → TD-13 trong [sổ nợ kỹ thuật](../../../task/tech-debt/README.md). C5 (thuật toán mới) thuộc P8.

> Lập 2026-09-30. Loại: điều tra/báo cáo, **Runtime change: none**.
>
> Câu hỏi của chủ sản phẩm: nếu người dùng muốn sửa các nút trong màn học (Hiện đáp án, Học lại/Khó/Tốt/Dễ, phím tắt) hoặc thuật toán lặp (bước học, khoảng cách, FSRS…) thì hiện sửa ở đâu và bằng cách nào; muốn mở cho người dùng thì phải làm gì.
>
> Phương pháp: đọc code tại nhánh `fix/legacy-lease-replay-under-note`, đối chiếu [canonical plan](../../../architecture/study-interaction-trigger-algorithm-plan.md) §6.2, §8, Phụ lục B #8, [vòng đời phiên bản thuật toán](../../../architecture/STUDY_ALGORITHM_RETIREMENT_LIFECYCLE.md) và [xác minh production 2026-08-24](../../../architecture/production-architecture-verification-2026-08-24.md) §8. Chưa đọc lại dữ liệu production; số liệu production lấy từ tài liệu đó.
>
> Liên quan: [đánh giá hành trình người dùng các phase đã xong](./UIUX_COMPLETED_PHASES_USER_JOURNEY_AUDIT_2026-09-30.md) (thứ tự ưu tiên hiện hành, UI P8 xếp cuối).

## 1. Trả lời nhanh

**Hiện người dùng không tự sửa được nút hay thuật toán ở đâu cả.** Không có màn cài đặt, không có API ghi, không có CLI. Mọi người học đang dùng tham số mặc định viết cứng trong code: production 2026-08-24 có 0 preset, 0 dòng cài đặt người dùng, 965/965 deck không gắn preset.

| Người dùng muốn… | Hôm nay | Ai sửa được, sửa ở đâu | Độ khó để mở cho người dùng |
|---|---|---|---|
| Đổi nhãn, màu, cỡ 4 nút | Không | Lập trình viên, `ReviewInteractionControls.tsx` | Thấp (chỉ trình bày) |
| Ẩn khoảng thời gian dưới nút, đổi định dạng `10m`/`1.5m` | Không | Lập trình viên | Thấp |
| Đổi phím tắt (1–4, Space, Z, E, F) | Không | Lập trình viên, `StudyPage.tsx:207-281` | Thấp–trung bình |
| Học 2 nút (Quên / Nhớ) | Không | — | Trung bình (cấu hình Interaction theo chế độ) |
| Template tự thêm nút chấm điểm | **Không, có chủ đích** (ADR phím tắt tin cậy) | — | Không mở |
| Đổi bước học, khoảng tốt nghiệp, hệ số, khoảng tối đa, leech | Backend **đọc** được từ `SchedulerPreset`, nhưng không có đường tạo hoặc gán | Chỉ sửa DB trực tiếp | Trung bình (API + UI + kiểm tra hợp lệ) |
| Đổi giờ sang ngày mới, thời gian học trước | Backend đọc từ `UserSchedulerSettings`, không có đường ghi | Chỉ sửa DB trực tiếp | Thấp–trung bình |
| Giới hạn số thẻ mới / số lượt ôn mỗi ngày | **Không tồn tại trong code** (dù hướng dẫn nói có) | — | Tính năng mới |
| Đổi ease khởi đầu / ease tối thiểu | Không có cột, cứng 2.5 / 1.3 | Lập trình viên | Thấp (thêm field) |
| Bật FSRS, chỉnh retention mong muốn | Có cột nhưng **không bao giờ chạy**; `fsrs` chỉ là nhãn | — | Cao (thuật toán mới, thuộc P8) |
| Sửa công thức thuật toán hiện tại | Không thể sửa tại chỗ | Lập trình viên: tạo phiên bản thuật toán mới | Cao |
| Chọn thuật toán theo deck / theo Note | Không; phiên mới luôn dùng thuật toán mặc định toàn hệ thống | Lập trình viên | Cao |

## 2. Các nút trong màn học

### 2.1 Nơi định nghĩa

Bộ 4 nút không chỉ là giao diện; đây là giao thức xuyên hệ thống (canonical plan §1.3).

| Lớp | Nơi | Nội dung cứng |
|---|---|---|
| Nút và nhãn | `frontend/src/features/study/interactions/ReviewInteractionControls.tsx:54-131` | Nhãn "Học lại / Khó / Tốt / Dễ", màu rose/amber/blue/emerald, số phím 1–4, nhãn khoảng thời gian |
| Nút lật, Hoàn tác, Toàn màn hình | `components/StudyBottomBar.tsx`, `ReviewInteractionControls.tsx` (nút "Hiện đáp án") | Nhãn, vị trí, ẩn/hiện theo cỡ màn hình |
| Phím tắt | `pages/StudyPage.tsx:207-281` | Space/Enter: lật thẻ, **mặt sau = Tốt**; 1–4: đánh giá; Z / Ctrl+Z: hoàn tác; E: sửa; F: toàn màn hình |
| Action ngữ nghĩa | `interactions/reviewInteraction.ts:4-41` | `review.{again,hard,good,easy}` → `scheduler.review.*`, contract `1` |
| Định dạng khoảng thời gian | `scheduler/legacyEngine.ts:610-691` | `<10m` (phút), `12d`, `1.5m` (**tháng**), `2y` |
| Thống kê phiên | `hooks/useStudySession.ts:625-646, 697-718`, `StudyCompletionCard.tsx` | Đếm 4 rating; "Tỉ lệ đúng" = Tốt + Dễ |
| Server | `app/services/study_action_runtime.py:22-23, 59`; `anki_scheduler.py`; `study_session_service.py` | Chỉ nhận đúng 4 giá trị |
| MCP | `app/services/mcp_tool_registry.py:963-968`; `app/validators/mcp.py:760-761` | Enum 4 rating |
| Đồng bộ Anki | `app/services/anki_sync_service.py:837` | ease 1–4 ↔ 4 rating |
| Analytics | `stats_query_repository.py:684, 780`; `admin_analytics_repository.py:86, 338` | "Đúng" = `good`/`easy` |
| Golden vectors | `tests/fixtures/study/legacy-anki-1.0.0-golden-vectors.json` | Đóng băng kết quả **và cả chuỗi nhãn** preview (ví dụ `"1.5m"`) |
| Template (iframe) | [ADR phím tắt tin cậy](../../../architecture/trusted-study-keyboard-boundary-2026-09-07.md) | Không có kênh nào để Template gửi đánh giá hoặc lật thẻ |

Không có cài đặt nào cho người dùng: đã tìm `show_interval`, `button_labels`, keybinding hay preferences trong `app/`, `models/`, `frontend/src/` và không có kết quả.

### 2.2 Ba tầng tùy chỉnh, từ an toàn đến rủi ro

**Tầng 1 — chỉ trình bày, theo từng người học (mở được ngay, không cần phiên bản):**
- ẩn/hiện khoảng thời gian dưới nút;
- định dạng tiếng Việt dựng từ số `seconds`/`days` sẵn có trong `SchedulerPreview` (`scheduler/types.ts:55-60`), ví dụ "<10 phút", "12 ngày", "1,5 tháng". Như vậy sửa luôn chỗ nhập nhằng `m` = phút hay tháng, và không đụng chuỗi `label` mà golden vectors đã đóng băng;
- gán lại phím tắt;
- Space ở mặt sau: "Tốt" hoặc không làm gì (một số người học bấm Space theo quán tính);
- bố cục nút trên di động.

Các lựa chọn này không đổi Action gửi lên server nên không ảnh hưởng tiến độ, MCP hay analytics. Cần nơi lưu tùy chọn hiển thị của người học: một bảng hoặc cột preferences riêng. Không nên dùng `user_scheduler_settings.extra_settings_json` vì bảng đó thuộc thuật toán.

**Tầng 2 — cấu hình Interaction theo chế độ học (cần phiên bản và đóng băng trong phiên):**
- ví dụ chế độ 2 nút "Quên / Nhớ" (chỉ `review.again` và `review.good`), hoặc 3 nút;
- canonical plan §6.2 cho phép: "A Template or mode may configure allowed visual properties while the host keeps the semantic contract";
- cần một cấu hình Interaction có phiên bản gắn vào composition (StudyMode), đóng băng trong snapshot phiên, và server kiểm tra Action nằm trong tập được phép (hiện server nhận cả 4);
- không cần thuật toán mới, vì vẫn là Action của bộ 4 nút.

**Tầng 3 — Action hoặc mức đánh giá mới (thuộc P8):**
- ví dụ thang 5 mức, hoặc "đúng/sai" do máy chấm;
- cần Interaction mới, ánh xạ Trigger mới, có thể cả thuật toán mới;
- đồng thời phải sửa MCP, đồng bộ Anki và analytics (bảng §2.1).

**Không mở:** nút trong Template có quyền ghi tiến độ. Template vẫn được có nút *trình bày* riêng (lật gợi ý, phát âm thanh qua bridge `play_audio`).

### 2.3 Lưu ý khi thay đổi

- Màu nút đang không nhất quán giữa các màn (UX-D3 trong [báo cáo trước](./UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md)). Người dùng không nên chọn màu tùy ý; nên dùng token ngữ nghĩa chung.
- Nhãn "Học lại" (nút) và "Quên" (màn hoàn thành) cần thống nhất trước khi cho người dùng đổi nhãn.
- Đổi hình thức mặc định cần duyệt theo quy tắc Zero Visual Regression.

## 3. Thuật toán lặp ngắt quãng

### 3.1 Thực tế đang chạy

- **Một thuật toán duy nhất:** `legacy-anki/1.0.0`. Server chạy `app/services/anki_scheduler.py` qua registry `app/services/study_algorithm_registry.py:28-30`; client chạy `frontend/src/features/study/scheduler/legacyEngine.ts` qua `algorithmRegistry.ts:11-12`. Hai phía khớp nhau nhờ golden vectors.
- **Phiên mới luôn dùng thuật toán mặc định toàn hệ thống** (`study_session_service.py:132-133, 506-508`). Người dùng hay deck không chọn được thuật toán.
- **Tham số lấy theo ba lớp** (`app/services/scheduler_config_service.py:99-241`):
  1. mặc định cứng `default_deck_options()` (`anki_scheduler.py:80-102`);
  2. `UserSchedulerSettings` của người học;
  3. `SchedulerPreset` gắn vào **đúng deck** đó. Không kế thừa từ deck cha; `SchedulerPreset.is_default` cũng không được đọc.
- **Production không dùng lớp 2 và 3:** 0 preset, 0 dòng cài đặt người dùng, mọi deck có `scheduler_preset_id IS NULL`, 0 dòng FSRS ([xác minh production](../../../architecture/production-architecture-verification-2026-08-24.md) §8.1–8.2).
- **Không có đường ghi nào:** tìm `SchedulerPreset(` và `UserSchedulerSettings(` trong `app/`, `scripts/`, `migrations/` chỉ ra định nghĩa model và các patch schema lúc khởi động. Nhập Anki, Flama Connect, MCP và CLI đều không tạo preset. Nhập từ Anki mang theo tiến độ nhưng không mang deck options.
- **Tham số được đóng băng theo phiên:** policy và config hash lưu trong snapshot và từng thẻ của phiên. Đổi tham số chỉ áp dụng cho phiên mở sau đó, không viết lại lịch hẹn đã có (giống Anki).
- **Deck đã cài dùng tham số của deck local của người học** (`study_session_service.py:606-619`), nên sau này người học chỉnh không ảnh hưởng tác giả.

### 3.2 Bảng tham số

| Tham số | Có cột? | Được đọc khi chạy? | Mặc định hiện hành | Ghi chú |
|---|---|---|---|---|
| Bước học (learning steps) | preset | ✅ | 1 phút, 10 phút | |
| Bước học lại (relearning steps) | preset | ✅ | 10 phút | |
| Khoảng tốt nghiệp | preset | ✅ | 1 ngày | |
| Khoảng khi bấm Dễ | preset | ✅ | 5 ngày | |
| Hệ số Khó | preset `hard_multiplier` | ✅ | 1.2 | |
| Thưởng Dễ | preset `easy_multiplier` | ✅ | 1.3 | |
| Hệ số khoảng (interval modifier) | preset | ✅ | 1.0 | |
| Hệ số khi quên (new interval) | preset `lapse_multiplier` | ✅ | 0.0 | |
| Khoảng tối thiểu sau khi quên | preset | ✅ | 1 ngày | |
| Khoảng tối đa | preset | ✅ | 36500 ngày | |
| Ngưỡng leech / hành động | preset | ✅ | 8 / tạm ngưng | `tag_only` = không tạm ngưng |
| Giờ sang ngày mới | user settings | ✅ | 4:00 | |
| Học trước (learn ahead) | user settings | ✅ | 20 phút | |
| Ease khởi đầu | ❌ | — | 2.5 cứng | Cần thêm field |
| Ease tối thiểu | ❌ | — | 1.3 cứng | Cần thêm field |
| Fuzz | ❌ | — | tắt | |
| Thẻ mới mỗi ngày / lượt ôn tối đa mỗi ngày | ❌ | ❌ | **không giới hạn** | Session nạp tới 5.000 thẻ, hàng đợi lấy mọi thẻ mới (`scheduler/queue.ts:68-120`); số "Mới" trên Dashboard đếm tất cả (`app/repositories/study_repository.py:817-844`) |
| `scheduler_mode = fsrs` | user settings | ⚠️ chỉ là nhãn | legacy | Nhánh FSRS chỉ chạy khi có `fsrsNextStates` (`anki_scheduler.py:691-692`), mà resolver luôn đặt `None`. Chọn `fsrs` vẫn chạy công thức legacy (Phụ lục B #8) |
| `desired_retention`, `fsrs_parameters_json`, `fsrs_short_term_enabled`, `fsrs_reschedule_on_change`, `historical_retention`, `ignore_reviews_before`, `fsrs_allow_short_term` | ✅ | ❌ | — | Cột dự trữ, không được dùng |

### 3.3 Hôm nay muốn đổi thì làm thế nào

**Người học:** không có cách nào.

**Quản trị/vận hành (không khuyến nghị nếu chưa có runbook):**
- tạo dòng trong `scheduler_presets` rồi gán `decks.scheduler_preset_id` cho **từng** deck (không kế thừa sang deck con);
- hoặc tạo dòng `user_scheduler_settings` cho giờ sang ngày mới và thời gian học trước.

Rủi ro: không có kiểm tra hợp lệ ngoài các phép kẹp giá trị trong resolver, không có audit, và mọi phiên mở sau đó bị ảnh hưởng. Tuyệt đối không đặt `scheduler_mode='fsrs'`: sẽ gắn nhãn sai lên lịch sử mà công thức vẫn là legacy.

**Lập trình viên — đổi công thức thuật toán:**
1. **Không được sửa `legacy-anki/1.0.0` tại chỗ.** Golden vectors đóng băng hành vi. Phiên đang mở và job đã nhận phải replay đúng phiên bản đó ([lifecycle](../../../architecture/STUDY_ALGORITHM_RETIREMENT_LIFECYCLE.md)).
2. Tạo phiên bản mới (ví dụ `legacy-anki/1.1.0` hoặc một key khác), cài **cả hai phía** (Python adapter + TS evaluator), kèm golden vectors riêng dùng chung cho hai phía.
3. Đăng ký `active`, chuyển bản cũ `deprecated` → `lease-only` → `retired` sau khi mọi lease 24 giờ và job đã rút hết.
4. Đổi thuật toán mặc định của phiên mới. Với tiến độ Note đã có, dùng lệnh chuyển thuật toán P5-08 (`app/services/study_algorithm_switch_service.py`). Hiện lệnh này **chưa có route và chưa có initializer** cho đích nào (dòng 1-15), nên phải bổ sung, và phải quyết định cách nâng phiên bản trong cùng họ thuật toán.

Tổng thể đây là một năng lực của P8 ("Algorithm mới"), không phải một cài đặt.

## 4. Đề xuất mở cho người dùng (xếp theo thứ tự ưu tiên hiện hành, trước P8)

| Gói | Nội dung | Loại | Phụ thuộc / quyết định | Ước lượng |
|---|---|---|---|---|
| **C0 — Sửa thông tin sai (nhanh)** | Sửa hướng dẫn: bỏ "Số thẻ mới mỗi ngày", "Max Reviews/Day", "Pinned" (`guideData.ts:153-172, 931-937`) và các phím không có; không hiện hoặc đổi nhãn nào gợi ý FSRS đang chạy | Frontend/nội dung | — | 0,5–1 ngày (gộp đợt "Nhất quán") |
| **C1 — Tùy chọn hiển thị nút (tầng 1)** | Ẩn/hiện khoảng thời gian; định dạng tiếng Việt từ số; Space ở mặt sau; gán lại phím tắt | Frontend + lưu preferences | D-C3 | 2–3 ngày |
| **C2 — Cài đặt ôn tập theo deck** | API + UI tạo/sửa preset (chỉ các tham số ✅ ở §3.2), gán preset cho deck với tùy chọn "áp dụng cho cả deck con", cài đặt người dùng (giờ sang ngày mới, học trước), kiểm tra khoảng hợp lệ, xem trước "với cài đặt này thẻ mới sẽ hẹn…" bằng engine hiện có, audit; thông báo "áp dụng từ phiên học sau" | Backend ghi + frontend | D-C1, D-C5; không đổi thuật toán hay phiên bản vì config hash đã được đóng băng theo phiên | 4–6 ngày |
| **C3 — Giới hạn thẻ mới / lượt ôn mỗi ngày** | Tính năng mới: đếm theo ngày (theo mốc giờ sang ngày mới), áp dụng cho hàng đợi phiên, số đếm Dashboard, MCP, deck đã cài | Backend + frontend queue | D-C2; thay đổi hành vi, cần test NOTE/đếm theo Note | 5–8 ngày |
| **C4 — Chế độ 2 nút (tầng 2)** | Cấu hình Interaction theo chế độ học, đóng băng trong phiên, server kiểm tra tập Action | Backend + frontend | D-C3; nên đi cùng đợt "Template & cách học" | 3–5 ngày |
| **C5 — Thuật toán mới / FSRS thật** | Theo §3.3; chọn thuật toán theo deck hoặc chế độ; màn xác nhận chuyển thuật toán dựa trên lịch sử | P8 | D-C4 | kế hoạch riêng |

Gợi ý chèn vào [thứ tự hiện hành](./UIUX_COMPLETED_PHASES_USER_JOURNEY_AUDIT_2026-09-30.md#4-thứ-tự-nâng-cấp-đề-xuất-ui-p8-xếp-cuối):
- C0 và C1 vào đợt "Nhất quán";
- C2 thành một đợt riêng ngay sau "Template & cách học";
- C3 và C4 sau đó;
- C5 cùng P8.

## 5. Quyết định cần chủ sản phẩm

| ID | Câu hỏi | Khuyến nghị |
|---|---|---|
| D-C1 | Preset gắn theo deck (dùng chung cho nhiều deck như Anki) và có kế thừa xuống deck con không? | Có preset dùng chung; khi gán ở deck cha thì mặc định áp dụng cho cả deck con (resolver hiện chỉ đọc đúng deck, nên cần bổ sung kế thừa hoặc ghi xuống từng deck) |
| D-C2 | Có làm giới hạn thẻ mới / lượt ôn mỗi ngày không, đếm theo Note hay theo thẻ, tính theo cây deck? | Có; đếm theo **Note** cho khớp D6-04; tính theo cây deck đang học |
| D-C3 | Tùy chọn nút ở mức người học (tầng 1) hay theo chế độ học (tầng 2)? | Làm tầng 1 trước. Chế độ 2 nút làm theo tầng 2 để server kiểm tra được |
| D-C4 | Xử lý FSRS "chỉ là nhãn" thế nào? | Ẩn khỏi mọi đường người dùng và không cho đặt `scheduler_mode='fsrs'` cho tới khi có thuật toán FSRS thật ở P8 |
| D-C5 | Người học có được chỉnh tham số cho deck đã cài không? | Có. Preset gắn vào deck local của người học nên không ảnh hưởng tác giả; không kế thừa preset của tác giả |

## 6. Kiểm chứng khi triển khai

- C1: test frontend study (định dạng nhãn từ số, cấu hình phím, Space ở mặt sau); golden vectors không đổi.
- C2: test backend cho resolver (kế thừa, clamp, deck đã cài); test phiên đang mở giữ config hash cũ, phiên mới dùng config mới; `python scripts/run_tests.py --module study,decks --backend-only`.
- C3: test hàng đợi và số đếm (Dashboard, phiên, MCP) theo mốc giờ sang ngày mới và múi giờ, với learner NOTE và deck đã cài.
- C4: server từ chối Action ngoài tập cho phép; khôi phục phiên cũ không có cấu hình vẫn chạy.
- Luồng trình duyệt dùng profile Chrome riêng theo `AGENTS.md`.

## 7. Handoff

```text
Task ID: STUDY-BUTTONS-ALGORITHM-CUSTOMIZATION
Primary outcome: bản đồ nơi định nghĩa nút học và tham số thuật toán; cách sửa hiện nay (không có đường cho người dùng); lộ trình C0–C5 và quyết định D-C1..D-C5
Files changed: docs/task/decoupling/STUDY_BUTTONS_AND_ALGORITHM_CUSTOMIZATION_2026-09-30.md (mới); liên kết trong README.md và UIUX_COMPLETED_PHASES_USER_JOURNEY_AUDIT_2026-09-30.md
Runtime change: none
Tests added or updated: none (điều tra)
Known limitations: số liệu preset/FSRS production lấy từ bản xác minh 2026-08-24, chưa đo lại
```
