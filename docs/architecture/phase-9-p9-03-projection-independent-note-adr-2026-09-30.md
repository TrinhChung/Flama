# ADR P9-03 — NOTE authority không phụ thuộc projection `card_progress`

> Trạng thái: **Đề xuất, chờ review** (gate P9-03 của [P9 plan](../task/decoupling/P9_EXECUTION_PLAN_2026-09-30.md#p9-03--hợp-đồng-canonical-không-phụ-thuộc-projection)). Lập 2026-09-30 từ code master `5709b64`, [kiểm kê trace P9-00](../task/decoupling/P9-00_CARDPROGRESS_INVENTORY_2026-09-30.md) và [bàn giao production](../task/decoupling/P9-00_PRODUCTION_HANDOFF_2026-09-30.md). Quyết định chủ sản phẩm đã chốt: D9-01 (NOTE đầy đủ → backup → cắt ghi song song → giảm tải), D9-02 (NOTE giữ dữ liệu mới, sửa bằng bổ sung từ backup). Đề xuất D9-08 (cắt toàn hệ thống trong freeze) được H-01 ủng hộ: 18 tài khoản, 4 learner hoạt động trong 30 ngày.

## 1. Hiện trạng (code)

Đường ghi NOTE (`study_authority_write_service.apply_study_authority_material_write`) tính trạng thái mới rồi:

1. mã hóa ngược sang projection legacy (`study_authority_projection_encoder`) cho **mọi** Card sibling;
2. dùng dòng `card_progress` đã khóa làm **CAS baseline** (`revision`, raw hash) và ghi đè giá trị projection vào chúng;
3. semantic hash của state lấy từ `map_card_progress(projection)`;
4. mirror (`finalize_native_mirror`) tạo/cập nhật contributor với evidence **raw từ dòng CardProgress** (`source_progress_id`, `live_card_progress_id`, `card_progress_revision`, `raw_payload`, `raw_progress_hash`) và availability từ mapping.

`map_card_progress` chỉ cần giá trị các trường (queue, due, interval, ease, reps, lapses, suspend/bury, memory…) cộng `Card.created_at`/`card_id`; nó **đòi `id` dương** chỉ để dựng raw evidence. State canonical đã chứa `reps`, `lapses`, lịch hẹn và cờ; availability suy hoàn toàn từ state + Card.

Production 30/09: 40.671 contributor, tất cả ACTIVE, `subject_generation` = 1 ở mọi subject; 0 nhóm trùng `(subject_id, subject_generation, logical_card_key)`; 16.474 lineage ref; 215 history fact.

## 2. Quyết định đề xuất — phương án A của P9 plan §4

### 2.1 Profile lưu trữ toàn hệ thống

Thêm bảng một dòng `study_authority_storage_profile` (`profile_code` ∈ {`PROJECTION_V1`, `CANONICAL_V1`}, `epoch`, `switched_at`). Mọi writer/reader NOTE đọc profile **dưới fence enrollment hiện có** (khóa chung dòng profile như dòng User). Chuyển `PROJECTION_V1 → CANONICAL_V1` chỉ bằng lệnh CLI trong write freeze (P9-06), khóa độc quyền dòng profile. Không có profile theo learner (D9-08). Process không hiểu `CANONICAL_V1` phải từ chối ghi (fail closed): deploy toàn bộ binaries hỗ trợ trước khi chuyển.

### 2.2 Adapter thuần thay cho dòng CardProgress

Tách từ `map_card_progress` một hàm thuần `project_note_card(state_payload, *, burial, card_id, card_created_at) -> (availability, semantic_hash)` và `encode_projection_values(state) -> dict` (đã có trong encoder) **không cần** `id`/dòng DB. `burial` là cặp (`is_buried`, `buried_until_day`) vì hai giá trị này nằm trong semantic hash nhưng **không** nằm trong Algorithm State (§2.8). Hai đường cũ/mới gọi cùng hàm; code mapping hiện tại trở thành oracle parity (P9-04 so sánh kết quả hai đường trên cùng dữ liệu khi projection còn cập nhật).

### 2.3 Evidence contributor không có CardProgress

Migration 47 (**expand**, không đổi giá trị cũ):

| Cột/ràng buộc | Thay đổi | Kiểm chứng trước khi áp |
|---|---|---|
| `evidence_kind` | Thêm, `NOT NULL DEFAULT 'LEGACY_PROJECTION'`, CHECK ∈ {`LEGACY_PROJECTION`, `CANONICAL`} | Mọi dòng cũ = `LEGACY_PROJECTION` |
| `source_progress_id`, `card_progress_revision`, `raw_schema_version`, `storage_codec`, `raw_payload`, `raw_payload_size`, `raw_progress_hash` | Nới NULL; CHECK cặp: `evidence_kind='LEGACY_PROJECTION'` ⇒ tất cả NOT NULL; `CANONICAL` ⇒ tất cả NULL | Không dòng nào NULL hôm nay |
| Unique `(subject_id, subject_generation, logical_card_key)` | Thêm **trước** khi nới `source_progress_id` (MySQL cho nhiều NULL trong unique cũ) | Production: 0 nhóm trùng |
| `live_card_progress_id` | Giữ nguyên (FK SET NULL, unique); `CANONICAL` luôn NULL | — |
| `pointer_status` | Không tái dùng cho evidence | — |

Contributor `CANONICAL`: `logical_card_key`, `live_card_id`, `subject_generation`, `lineage_vector_hash`, `history_completeness_code`, `current_provenance_code`, `contributor_status` như hiện tại. Availability giữ bảng và composite FK hiện có, giá trị từ §2.2. Dòng cũ giữ nguyên đến P9-10.

### 2.4 CAS và trình tự ghi (profile `CANONICAL_V1`)

Một transaction: fence enrollment + profile → khóa subject → token/state (đã có) → CAS bằng `authority_revision` + `semantic_state_hash` của token (đã là CAS thật; dòng CardProgress hôm nay chỉ là kiểm chứng thừa) → ghi state, token, availability từng Card sibling (UPSERT theo contributor), ReviewEvent/history fact/receipt như hiện hành. **Không** SELECT/INSERT/UPDATE `card_progress`. Sibling set lấy từ `cards` của Note + contributor ACTIVE của generation hiện tại (thay `lock_study_authority_siblings` đọc CardProgress).

### 2.5 Pristine, Note mới, lifecycle

- Pristine = không có `study_progress_states` cho subject (bỏ điều kiện "không có CardProgress" trong `classify_note_authority_keys` ở profile mới; dòng CardProgress cũ của Note pristine không tồn tại theo invariant I9).
- Materialize Note mới/pristine: tạo subject/state/token/contributor `CANONICAL`/availability; không tạo CardProgress (bỏ nhu cầu "chèn CardProgress để lấy id").
- Reset/delete/sibling expansion/clone rekey: thay mọi chỗ đọc CardProgress để tìm learner bị ảnh hưởng (`collect_learner_ids`, `discover_content_learner_ids`) bằng subject/contributor. Cascade xóa CardProgress lịch sử vẫn chạy như **cleanup**, không phải writer.

### 2.6 Connect/Anki (F9-06, H-05)

- Thêm `connect_source_card_refs.applied_authority_revision BIGINT NULL` và `applied_local_revision_state ENUM('LEGACY_CARD_PROGRESS','AUTHORITY','NEEDS_CONFIRMATION')`.
- Ở cutover, 15.965 ref hiện có (100% có `applied_local_revision` = `CardProgress.revision`) chuyển `NEEDS_CONFIRMATION`: không có ánh xạ chứng minh được từ revision projection sang authority revision. Lần sync kế tiếp của ref đó so snapshot: khớp state hiện tại → ghi `AUTHORITY` + revision hiện tại; khác → trả `LOCAL_PROGRESS_CHANGED` (hoặc áp khi `force`), không ghi đè im lặng.
- Codec snapshot Anki → state dùng §2.2, không dựng input từ dòng CardProgress; Card chưa có CardProgress import được.

### 2.7 Readers

Reader NOTE (P9-04) chỉ đọc subject/state/token/contributor/availability; kiểm linkage mới: contributor `CANONICAL` phủ đúng Card sống, availability generation/hash = state; `LEGACY_PROJECTION` giữ kiểm cũ cho đến khi hết. Thống kê `reps` marketplace = Σ theo subject `state.reps` × số Card sống trong phạm vi (bằng tổng projection hôm nay vì mọi sibling mang cùng state). Browse lọc/sắp theo availability. Audit canonical thay thế (F9-08) tính lại availability/semantic hash bằng §2.2 từ state và so dòng đã lưu.

### 2.8 Giá trị hiện chỉ có trong projection

Writer NOTE hôm nay lấy một phần giá trị projection từ **dòng CardProgress của Card được trả lời** (`study_authority_command_service._projection_metadata` → `LegacyProjectionMetadata`, "Compatibility values deliberately omitted from Algorithm State") và từ baseline từng sibling. Bỏ CardProgress thì mỗi giá trị cần nguồn canonical riêng:

| Giá trị projection | Hôm nay lấy từ | Production 30/09 (SELECT) | Nguồn ở `CANONICAL_V1` |
|---|---|---|---|
| `interval_days` (làm tròn) | review: `_round_review_interval(state.intervalDays, deck options)`; khác: `round(state.intervalDays)` | 40.671/40.671 dòng có `interval_days = FLOOR(interval_days_raw + 0.5)`; max 801 | **Suy ra, không lưu**: hàm thuần `rounded_interval_days(state)` tái tạo đúng encoder. Scheduler đã clamp `intervalDays` theo deck options trước khi ghi (`anki_scheduler._set_review_due`), nên clamp lại là đồng nhất. Reader stats/MCP (ngưỡng mature ≥ 21) gọi hàm này thay cột. |
| `is_buried`, `buried_until_day` | CardProgress của Card được trả lời, áp cho mọi sibling; nằm trong semantic hash | 0 dòng buried ở `card_progress` lẫn `study_progress_availability`; chỉ import Anki/Connect đặt được (queue -2/-3), không API/UI nào bury | **Availability là nguồn**: writer đọc burial từ availability đã khóa của Card được trả lời (hôm nay bằng projection, audit read 18/18 PASS), giữ nguyên cho mọi sibling; semantic hash vẫn gồm burial. Import Anki/Connect ghi burial vào availability qua cùng adapter. |
| `last_leech_lapses` | Card được trả lời; `state.leeched` của mapping suy từ nó | 0 dòng > 0 | **Không lưu**: `state.leeched` là nguồn; chỉ encoder projection cần giá trị này. |
| `last_leech_at` | như trên | 0 dòng khác NULL; không reader API/UI | **Không lưu**; nếu sau này cần hiển thị, lấy thời điểm của history fact đầu tiên có `leeched` = true. |
| `last_review_event_id` | baseline từng sibling | — | ReviewEvent/history fact do writer stage. `pointer_status` của contributor `CANONICAL`: `VALID` khi writer vừa stage event cho Card đó, giữ nguyên cho sibling, `ABSENT` khi pristine. |
| `revision`, `updated_at` | CAS projection, `projected_at` | — | `authority_revision` của token; `updated_at` của state/availability. |

Hệ quả: CardProgress không còn là nguồn của giá trị nào; mọi giá trị trên có nguồn canonical hoặc suy ra được từ state, và contract test (§4.1) phủ cả burial khác mặc định và state leeched.

### 2.9 Phủ các tình huống của gate P9-03

| Tình huống | Hôm nay dựa vào CardProgress ở đâu | Ở `CANONICAL_V1` |
|---|---|---|
| Tạo Note/Card mới, Template add, sibling expansion | Chèn CardProgress để lấy `id` cho contributor | §2.5: subject/state/token/contributor `CANONICAL`/availability, không CardProgress |
| Trả lời (REST direct, MCP, session commit v4) | Lock sibling CardProgress làm CAS baseline | §2.4. Lease v4 của NOTE chỉ ghim `authority_revision` + semantic hash (`base_progress_revision` = 0, không đọc CardProgress khi mở phiên), nên lease mở trước khi chuyển profile vẫn commit đúng sau khi chuyển: **không cần wire mới** (plan P9-03 mục 4). |
| Mất ACK, gửi lại commit | Không | Replay/receipt/`SESSION_ALREADY_COMMITTED` được trả trước mọi kiểm tra authority (PR #180); receipt không chứa revision CardProgress. |
| Reset, xóa Card/Note | Tìm learner bị ảnh hưởng qua CardProgress | §2.5: tìm qua subject/contributor. Xóa Card: contributor `DETACHED`, availability xóa theo cascade như hiện hành. |
| Note không còn Card | — | Subject/state/history giữ nguyên, 0 contributor ACTIVE, 0 availability ⇒ không vào hàng học. Thêm lại Card ⇒ contributor `CANONICAL` + availability từ state còn giữ. Note chưa từng có Card: không có subject cho đến Card đầu tiên. |
| Đổi thuật toán (`study_algorithm_switch_service`) | Metadata lấy từ CardProgress sibling đầu; "rollback window" bắt state đích round-trip qua mọi dòng CardProgress | Burial từ availability (§2.8); kiểm state đích bằng adapter §2.2 cho mọi Card sống thay cho round-trip. State cũ vẫn nằm trong history fact của lần đổi. |
| Overlay/clone rekey (`prepare_clone_rekey_mirror`) | Join CardProgress để tìm Card/learner | Tìm qua contributor `live_card_id` ∈ `card_id_map`; chuyển contributor/availability sang Card mới như hiện hành. |
| Import và re-sync Connect/Anki | Fence `applied_local_revision` = `CardProgress.revision`; codec dựng input từ dòng CardProgress | §2.6. |
| Contributor `LEGACY_PROJECTION` có sẵn | Raw evidence phải khớp dòng CardProgress sống | Sau khi chuyển, raw evidence là **lịch sử** (mô tả dòng CardProgress ở lần projection cuối). Reader/writer `CANONICAL_V1` không so với CardProgress và không cập nhật các cột raw; `live_card_progress_id` giữ đến P9-10. |
| Rollback | — | Profile chỉ đi một chiều; không quay về `PROJECTION_V1` vì projection đã đứng yên từ T0. Rollback code chỉ về release hiểu `CANONICAL_V1` (release P9-03a phải chạy production trước khi chuyển); một revert xóa migration 47 làm `flask db upgrade` báo không tìm thấy revision nên deploy dừng trước bước restart. Sự cố dữ liệu: bổ sung từ backup + binlog theo D9-02, không ghi đè state mới hơn. |
| Bổ sung dữ liệu thiếu trước T0 (plan P9-03 mục 5) | — | Trước khi chuyển: `study-phase9-readiness` `FULL_NOTE_PASS` và `study-authority-read-audit` PASS toàn bộ learner chứng minh canonical = projection; không giá trị nào chỉ có ở CardProgress (§2.8; burial/leech trên production = 0). |

## 3. Phương án bị loại

- **Giữ ghi CardProgress nhưng bỏ đọc**: không giảm tải ghi (mục tiêu D9-01), vẫn sai khi projection lệch.
- **Id giả cho `source_progress_id`**: plan cấm; phá ý nghĩa FK/lineage.
- **Phương án B (availability theo subject)**: đổi rộng queue/order/topology; để đợt sau nếu A không đủ.

## 4. Kiểm chứng bắt buộc (gate P9-03 → P9-04/05)

1. Contract test: cùng state, đường cũ (`map_card_progress` trên projection) và mới (§2.2) cho availability + semantic hash giống hệt — mọi queue, suspend/bury (kể cả `buried_until_day`), learning steps, relearning, due_at/due_day, memory state, state leeched; Note 1 và nhiều Card. `rounded_interval_days(state)` bằng `interval_days` của encoder ở mọi case, và bằng cột trên bản sao production (đã đo: 0 lệch).
2. Migration 47 trên SQLite + MySQL tạm: upgrade/idempotent/downgrade từ chối khi có dòng `CANONICAL`; unique mới không vi phạm trên bản sao dữ liệu production (đã đếm: 0 trùng).
3. Fixture **không có bảng CardProgress dữ liệu** chạy được reader/writer profile `CANONICAL_V1`.
4. Connect: ref `NEEDS_CONFIRMATION` + học trên Flama rồi sync cùng snapshot → `LOCAL_PROGRESS_CHANGED`; snapshot khớp → chuyển `AUTHORITY`; `force` ghi và tạo history.
5. Mixed version: node không hiểu `CANONICAL_V1` từ chối ghi sau khi profile chuyển.

## 5. Kế hoạch triển khai kéo theo

P9-03a adapter thuần + contract test (không schema, không đổi hành vi) → P9-03b migration 47 + profile table (profile mặc định `PROJECTION_V1`, không đổi hành vi) → P9-04 readers đọc canonical ở cả hai profile, parity với projection còn cập nhật → P9-05/05b writers theo profile → P9-06 backup/restore proof, freeze, chuyển profile, `study-phase9-readiness --projection-since T0` = 0.
