# ADR P10 — Gộp tiến độ NOTE về một dòng cho mỗi learner × Note

> Trạng thái: **Đề xuất, đã được chủ sản phẩm yêu cầu triển khai (2026-10-03)**. Thay thế phương án B của [ADR P4-03](./phase-4-algorithm-state-availability-adr-2026-09-12.md) §4 (state tách 1:1 khỏi envelope; availability theo contributor) và phần contributor/availability/token của [ADR P4-05](./phase-4-physical-shadow-schema-adr-2026-09-13.md) và [ADR P9-03](./phase-9-p9-03-projection-independent-note-adr-2026-09-30.md). Giữ nguyên các quyết định sản phẩm của [kế hoạch gốc](./study-interaction-trigger-algorithm-plan.md) §16.1. Kế hoạch thực thi: [P10](../task/decoupling/P10_EXECUTION_PLAN_2026-10-03.md).

## 1. Bối cảnh và bằng chứng

Sau cutover P9-06 (`CANONICAL_V1`, 2026-10-02), tiến độ của một learner với một Note nằm ở năm bảng quan hệ 1:1: `study_progress_subjects`, `study_progress_states`, `study_authority_subject_tokens`, `study_progress_contributors`, `study_progress_availability`. Production 2026-10-03 (SELECT-only):

| Bằng chứng | Giá trị |
|---|---|
| Số dòng mỗi bảng | 40.795 = 40.795 = 40.795 = 40.795 = 40.795 |
| Note có đúng một Card | 40.265/40.265 (100%); 0 subject nhiều contributor |
| Subject có các thẻ khác queue/due | 0 |
| Một câu trả lời trong commit phiên | ≈ 18,6 SQL, 10 dòng ghi; UPDATE trên subject, state (2 lần), token, contributor, availability |
| Dashboard user 1 (39.284 thẻ) | 2,16 s; SQL 1,96 s; câu đếm join 7 bảng × 39.284 dòng (0,91 s) và câu kiểm vector (0,62 s, luôn 0 dòng) |

Lý do P4-03/P4-05 chọn tách bảng đều thuộc giai đoạn chuyển đổi: ghi song song cạnh `card_progress`, bằng chứng lossless để đối chiếu từng dòng projection, quay lại LEGACY, và khả năng fan-in nhiều `card_progress` vào một Note. Sau P9-06 các lý do này không còn: projection đứng yên, rollback LEGACY bị đóng (D9-02), đếm theo Note từ P6 (D6-04), mỗi câu trả lời vẫn ghi cả năm bảng nên việc tách không giảm lần ghi nào. Việc chẻ bảng còn sinh ra kiểm tra chéo hash/generation/revision trên mọi lần đọc (nhóm lỗi `AUTHORITY_*_DIVERGED`, `INCOMPLETE_AUTHORITY_*`).

Trong code, queue/due/suspended đều suy từ state của Note (`study_note_card_projection.project_note_card`); burial dùng chung cho mọi sibling (ADR P9-03 §2.8). Thứ tự thẻ (`card_created_at`, `card_order_key`) là thuộc tính của Card, đã có trong bảng `cards`.

## 2. Quyết định

### 2.1 Một dòng tiến độ cho mỗi learner × Note

`study_progress_subjects` trở thành dòng tiến độ duy nhất (giữ tên bảng để mọi FK hiện có — receipt, pin, history fact, lifecycle event — không đổi). Migration expand thêm các cột:

| Nhóm | Cột | Nguồn khi chuyển |
|---|---|---|
| State | `algorithm_key`, `algorithm_version`, `state_schema_version`, `storage_codec`, `state_payload` (JSON), `state_payload_size`, `algorithm_state_hash`, `semantic_state_hash` | `study_progress_states` |
| CAS | `authority_revision` (BIGINT, 0 khi chưa có state) | `study_authority_subject_tokens` |
| Availability (theo Note) | `projection_version`, `normalized_queue`, `due_day`, `due_at`, `is_suspended`, `is_buried`, `buried_until_day` | availability của contributor ACTIVE (giống nhau trên mọi sibling) |
| Lịch sử/nguồn gốc | `history_completeness_code`, `current_provenance_code` | contributor ACTIVE (một Note một Card: lấy trực tiếp; nhiều Card: mức đầy đủ thấp nhất) |

Giữ: `id`, `learner_user_id`, `logical_note_key`, `live_note_id`, `subject_generation`, `status_code`, `created_at`, `updated_at`. Các cột chỉ phục vụ bằng chứng chuyển đổi (`mirror_revision`, `contributor_count`, `authority_vector_hash`, `lineage_vector_hash`, `mapper_version`, `last_mirrored_at`) không còn được đọc ở profile mới và bị bỏ ở bước contraction.

Ràng buộc trên chính dòng thay cho kiểm tra chéo: nhóm state, `semantic_state_hash`, `authority_revision > 0` và nhóm availability cùng có hoặc cùng NULL; độ dài hash 32; `normalized_queue` thuộc danh sách chuẩn hóa.

### 2.2 Availability contract

Giữ projection chuẩn hóa đã được P4-03 chấp nhận (`normalized_queue` ∈ {new, learning, relearning, review}, `due_day`, `due_at`, suspended/buried anchors) và `projection_version`. Mỗi Algorithm chiếu state của nó sang các cột này; không có cột riêng của thuật toán. Phase 8 thêm trạng thái (ví dụ `completed` cho thuật toán không lặp lại) bằng cách mở rộng danh sách chuẩn hóa và tăng `projection_version`, không thêm bảng hay cột theo thuật toán. Không lưu boolean `eligible_now` (P4-03 Finding 3).

### 2.3 Card không mang tiến độ

Thứ tự trong hàng đợi lấy từ `cards.created_at`, `cards.id`. Thêm, xóa, sắp lại Template không ghi gì vào tiến độ: Card mới tự thuộc tiến độ của Note. Quyết định sản phẩm số 1–2 (một tiến độ chung cho mỗi learner × Note) và quy tắc một composition mỗi phiên giữ nguyên. Nếu sau này cần tiến độ riêng theo kiểu tương tác, đó là quyết định sản phẩm mới.

### 2.4 Ghi và CAS

Một transaction: fence enrollment + profile (như hiện tại) → khóa dòng tiến độ `FOR UPDATE` (một câu cho mọi Note của commit) → CAS bằng `authority_revision` + `semantic_state_hash` → **một UPDATE** ghi state, revision và availability → ReviewEvent (đã gắn `note_id`), history fact, receipt như hiện tại. Không còn contributor, availability, token, lineage ref; history fact mới để `contributor_id` NULL, khớp theo `subject_id` + `subject_generation` + `logical_card_key`.

Lease v4 ghim `authority_revision` + hash: giá trị được chép nguyên khi chuyển nên lease cấp trước vẫn commit đúng sau khi chuyển.

### 2.5 Vòng đời

| Thao tác | Ở profile mới |
|---|---|
| Note chưa học (pristine) | Không có dòng, hoặc dòng `NO_CURRENT_PROGRESS` không state; mở phiên v4 materialize một dòng (bulk INSERT) |
| Thêm/xóa Template, Card | Không ghi tiến độ |
| Reset tiến độ | Tăng `subject_generation` và ghi state ban đầu theo deck options, giữ đúng hành vi reset NOTE hiện tại; history giữ nguyên |
| Xóa Note, NoteType, deck | Giữ đúng hành vi tombstone/detach hiện tại trên cùng dòng; history và receipt giữ nguyên |
| Đổi thuật toán | UPDATE identity + state + revision trên cùng dòng; history cut dùng `history_completeness_code` của dòng |
| Anki/Connect snapshot | Fence bằng `authority_revision` (như P9-05d); ghi state, provenance `CONNECT_PROGRESS_SNAPSHOT`, completeness tương ứng |
| Overlay/clone rekey | Ánh xạ `live_note_id`/`logical_note_key` của dòng, không còn di chuyển contributor theo Card |

### 2.6 Chuyển đổi

Thêm storage profile `CONSOLIDATED_V1`, chuyển một chiều `CANONICAL_V1 → CONSOLIDATED_V1` bằng CLI trong write freeze ngắn như P9-06: khóa độc quyền dòng profile, chép tập hợp (một UPDATE JOIN) từ state/token/availability/contributor sang dòng subject, kiểm đối chiếu đầy đủ (số dòng, hash, revision, availability tính lại từ state bằng `project_note_card`), tăng epoch. Process không hiểu profile mới từ chối ghi (fail closed, giống P9-03). Không có đường quay lại; sự cố xử lý bằng sửa tiến và bổ sung từ backup + binlog (D9-02).

### 2.7 Đọc

Dashboard, overview, Browse, `/api/study/next`, MCP, thống kê hôm nay/tương lai, reps marketplace đọc `notes ⋈ study_progress_subjects` (cộng `cards` khi cần thứ tự hoặc Card cụ thể). Không còn kiểm tra chéo trên đường đọc; audit offline (`study-authority-read-audit`, readiness) tính lại availability từ state và so với cột đã lưu.

## 3. Phương án bị loại

| Phương án | Lý do |
|---|---|
| Giữ năm bảng, chỉ tối ưu câu đọc | Giảm được đọc (đã đo 3×) nhưng giữ 6 UPDATE/câu và kiểm tra chéo; không giải quyết gốc |
| Bảng mới `study_note_progress`, bỏ `study_progress_subjects` | Phải đổi mọi FK (receipt, pin, history, lifecycle) và subject id trong lease đang sống; không thêm lợi ích |
| Quay lại cột theo thuật toán như `card_progress` | Phá decoupling: thuật toán mới phải đổi schema |
| Index/cache | Chủ sản phẩm yêu cầu tối ưu thiết kế và truy vấn trước; giữ làm bước sau nếu số đo yêu cầu |

## 4. Hệ quả

- Đọc: dashboard từ 7 bảng còn `notes` ⋈ một bảng; hàng đợi và Browse tương tự.
- Ghi: mỗi câu trả lời một UPDATE tiến độ thay cho sáu; số dòng ghi khoảng 10 → 4–5.
- Bỏ được ở contraction: `study_progress_states`, `study_authority_subject_tokens`, `study_progress_contributors`, `study_progress_availability`, `study_progress_lineage_refs`, cùng công cụ chỉ phục vụ chuyển đổi (mirror, backfill, reconciliation P4). Việc gỡ `card_progress`, nhánh LEGACY và profile `PROJECTION_V1` cần quyết định riêng của chủ sản phẩm vì liên quan phạm vi compatibility đã giữ ở P9.
- Không đổi: wire v2/v3/v4, receipt, pin, ReviewEvent, history fact, ordinal Connect, overlay-only.

## 5. Kiểm chứng bắt buộc

1. Cùng dữ liệu, hai profile cho kết quả đọc giống hệt (dashboard, overview, Browse, hàng đợi, MCP, thống kê) trên fixture và trên bản khôi phục production.
2. Bộ test Study/Connect/Decks/Flashcards/Marketplace/Analytics chạy dưới `CONSOLIDATED_V1` với guard: không SQL nào chạm bốn bảng cũ và `card_progress` (trừ DELETE dọn dẹp đã khai báo).
3. Writer matrix: trả lời trực tiếp/MCP/phiên/batch, mất ACK, Note mới, Template thêm/xóa, reset, xóa, đổi thuật toán, Anki/Connect, overlay; không mất/nhân đôi câu trả lời.
4. MySQL: probe đồng thời, replay, switch trên bản khôi phục production; A/B ghi/đọc so với `CANONICAL_V1`.
5. Switch: dry-run không blocker, kiểm đối chiếu 100%, lease v4 qua switch vẫn commit đúng.
