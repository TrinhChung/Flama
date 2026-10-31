# Review triển khai Single Published Base (2026-10-29)

- **Phạm vi:** nhánh `feat/note-published-base-20261029` tại `3471d7cf` (commit `d4925854` và
  `3471d7cf`).
- **Đối chiếu với:**
  [kế hoạch](NOTE_LEVEL_VERSIONING_PLAN_2026-10-28.md) và
  [ADR](NOTE_PUBLISHED_BASE_IMPLEMENTATION_2026-10-29.md).
- **Người review:** Claude Code. Tài liệu này chỉ ghi nhận xét, chưa sửa code.
- **Người đọc:** agent (Codex) sẽ sửa nhánh này. Mỗi mục có bằng chứng (file:dòng trên
  `3471d7cf`), ảnh hưởng, hướng sửa và tiêu chí nghiệm thu.

> Review lịch sử ngày 29/10, trước cutover. Kết quả xử lý các nhận xét nằm trong
> [bản phản hồi ngày 30/10](NOTE_PUBLISHED_BASE_REVIEW_RESPONSE_2026-10-30.md);
> trạng thái triển khai nằm trong [báo cáo production](NOTE_PUBLISHED_BASE_PRODUCTION_CUTOVER_2026-10-30.md).
> Các đường dẫn worktree và dữ liệu diễn tập bên dưới mô tả thời điểm review;
> nhiều bản sao đã được dọn theo [nhật ký 31/10](NOTE_PUBLISHED_BASE_CLEANUP_2026-10-31.md).

## Đã kiểm chứng

- 4 bộ test MySQL mới đều qua: **56 test, OK, 90,9 s**. Lệnh chạy:

  ```bash
  env STUDY_WIRE_V4_ENABLED= STUDY_ASYNC_BATCH_ENABLED= STUDY_NEW_LEARNER_NOTE_ENABLED= \
    STUDY_NOTE_COUNT_ENABLED= STUDY_PROGRESS_SHADOW_WRITE_ENABLED= \
    STUDY_PROGRESS_SHADOW_READ_ENABLED= STUDY_PROGRESS_SHADOW_COMPARE_ENABLED= \
    FLAMA_MYSQL_TESTS=1 .venv/Scripts/python.exe -m unittest \
    tests.test_note_drafts_mysql tests.test_note_base_reader_mysql \
    tests.test_note_base_publish_mysql tests.test_note_base_cutover_mysql
  ```

- Đo riêng thời gian đọc và ghi qua property `note.field_values` khi bật và tắt cờ. Script
  và kết quả ở Phụ lục A.

## Phần đã tốt, giữ nguyên

- Ghi đi qua hook flush có sẵn. Ghi hàng loạt và SQL thô vào `notes` vẫn bị chặn.
- Publish không truy vấn `deck_installs`: 47 câu SQL cho 1 note, ở cả 100 lẫn 1.000
  install.
- Diễn tập trên bản copy production ngày 29/10:
  - 41.874 note khớp tuyệt đối giữa Base + nháp và bản cũ;
  - rollback khôi phục đúng hash.
- Migration 76 chỉ thêm đúng các cột đã duyệt, dùng `ALGORITHM=INSTANT`, không có index
  phụ.
- Các chốt của chủ dự án được làm đúng:
  - lần lưu sau thắng;
  - note không ai tham chiếu thì xoá cứng lúc publish;
  - gỡ ảnh không xoá file;
  - auto-publish trả 410;
  - giữ buffer pool 1 GB;
  - lệnh publish theo note type (E6).

## Thứ tự ưu tiên

| # | Mức | Điểm | Đã đo? |
|---|---|---|---|
| R1 | **Sửa trước cutover** | Đọc và ghi qua property chậm theo bình phương số note trong session | Có (Phụ lục A) |
| R2 | **Sửa trước cutover** | Property cộng nháp cho mọi người đọc, nên một đường learner bị sót sẽ lộ nháp | Đọc code |
| R3 | **Sửa trước cutover** | Mỗi lần learner trả lời thẻ, code duyệt mọi install của learner | Đọc code, chưa đo |
| R4 | Đo trước cutover | Benchmark chưa đo latency của từng request và bỏ qua phía tác giả | Đọc harness |
| R5 | Đo trước cutover | Search/sort của tác giả chạy 2 subquery nháp cho mỗi field của mỗi note | Đọc code, chưa đo |
| R6 | Đo trước cutover | Mỗi lần tác giả lưu là khoá mọi listing cùng note type (18 listing) | Đọc code, chưa đo |
| R7 | Nhỏ | `notes.updated_at` không đổi khi lưu nháp | Đọc code |
| R8 | Vận hành | Job retention chưa có lịch chạy | Đọc code |
| R9 | Vận hành | Hai đường code chạy song song tới P6 | Đếm |
| R10 | Quy trình | PR lẫn khoảng 2.000 dòng di chuyển FSD ở frontend | Đếm |
| R11 | Chủ dự án | Duyệt manifest 6 note thành nháp trước P4 | Không phải việc của agent |

---

## R1. Đọc và ghi qua property chậm theo bình phương số note (sửa trước cutover)

### Bằng chứng trong code

- `get_note_draft` ([note_draft_service.py:163](../../app/services/note_draft_service.py)):
  - Ở mỗi lần gọi, nó dựng lại danh sách **mọi** `Note` trong `session.identity_map` (dòng
    172).
  - Sau đó gọi `load_note_drafts`. Hàm này dựng lại tập `ids` (dòng 150), tính
    `ids - cache.keys()`, và duyệt `session.new | dirty | deleted` (dòng 157).
  - Kết quả: mỗi lần đọc tốn O(N), N lần đọc tốn O(N²) phép tính trong Python.
- `get_note_draft` được gọi ở mọi lần đọc `note.field_values`, qua
  `read_note_named_values` ([field_value_runtime_service.py:169-172](../../app/services/field_value_runtime_service.py)),
  và ở mọi lần ghi, qua `encode_pending_note_values` (dòng 230-231).
- Cache nháp bị xoá toàn bộ:
  - sau **mỗi** lần flush (`_finish_encoded_notes`,
    [field_value_identity_hooks.py:301-311](../../app/services/field_value_identity_hooks.py));
  - và ở dòng 315-325, 329-333.
  - Hệ quả: vòng lặp flush từng note phải truy vấn lại nháp cho mọi note đã nạp, với một
    danh sách `IN` không chia lô (`note_draft_service.py:155`).

### Số đo

Đo trên DB MySQL tạo riêng bằng fixture của repo, buffer pool 1 GB:

| Số note trong session | Đọc hết qua property, cờ tắt | Cờ bật | Vòng sửa + flush từng note, cờ tắt | Cờ bật |
|---:|---:|---:|---:|---:|
| 500 | 0,023 s (3 truy vấn) | 0,353 s (4) | 500 note: 7,5 s (4.000) | 15,5 s (6.000) |
| 2.000 | 0,075 s | **6,142 s** | 1.000 note: 12,2 s (8.000) | **50,0 s** (12.000) |
| 5.000 | 0,365 s | **30,826 s** | 1.000 note: 11,2 s (8.000) | **40,3 s** (12.000) |

- Ở cột đọc, số truy vấn gần như không đổi (3 so với 4). Thời gian tăng là do Python quét
  identity map.

### Ảnh hưởng

Các đường của tác giả đọc hoặc ghi nhiều note trong một session:
- `browse_voicevox_service.py:414`: TTS hàng loạt, flush từng note;
- worksheet (`worksheets/worksheet_service.py:113, 689, 1164, 1172`);
- `flashcard_audio_scan_service`, `image_crawl_service`, `field_array_conversion_service`;
- công cụ MCP batch.

Deck N1 có 10.148 note.

Benchmark của nhánh không phát hiện được lỗi này, vì chỉ đo từng trang 20 note.

### Hướng sửa

1. Trong `get_note_draft`, tra `note.id` trong cache trước. Có rồi thì trả luôn, không
   quét gì. Chỉ khi thiếu mới gom các id còn thiếu của note đã nạp và truy vấn một lần,
   theo lô 500. Tổng chi phí cho một trang hoặc một batch còn O(N).
2. Theo dõi `NoteDraft` đang pending theo `note_id`, ví dụ trong `session.info` cập nhật ở
   `before_flush` hoặc khi `stage_note_delete`/redirect tạo nháp, thay vì duyệt
   `session.new | dirty | deleted` ở mỗi lần đọc.
3. Không xoá toàn bộ cache sau mỗi flush:
   - Chỉ cập nhật hoặc xoá các entry có `NoteDraft` vừa được ghi hay xoá trong flush đó
     (`redirect_published_note_writes` đã biết danh sách này).
   - Xoá toàn bộ khi transaction kết thúc và khi rollback là đủ.
4. Giữ nguyên ngữ nghĩa nháp. Không thêm cache toàn process, đúng ADR.

### Nghiệm thu

- Chạy lại Phụ lục A:
  - đọc 5.000 note khi bật cờ ≤ 2 lần thời gian khi tắt cờ (≈ ≤ 1 s);
  - vòng sửa 1.000 note: số truy vấn mỗi note ≤ số khi tắt cờ + 2, và thời gian ≤ 1,5 lần.
- Thêm test MySQL: đọc `field_values` của 2.000 note đã publish trong một session thì
  số SELECT vào `note_drafts` ≤ ceil(2000/500).
- Toàn bộ 56 test hiện có vẫn pass.

---

## R2. Property cộng nháp cho mọi người đọc (sửa trước cutover)

### Bằng chứng trong code

- `get_note_draft` ([note_draft_service.py:163](../../app/services/note_draft_service.py))
  không xét người xem.
- `read_note_named_values` luôn cộng nháp khi bật cờ.
- Kế hoạch §3.2 chỉ yêu cầu đường learner *không dùng* property trên note nguồn.
  - Nhánh này đã chuyển các đường đã biết: `share/overlay`, `study_artifact_service`,
    Browse, `connect/identity_lookup`.
  - Nhưng việc bảo vệ chỉ dựa vào quy ước. Một đường learner bị sót, hoặc viết mới sau
    này, sẽ trả bản nháp chưa publish cho learner.
  - Đó là hướng lỗi nguy hiểm, vi phạm #263 mục 6.

### Hướng sửa

1. Trong `get_note_draft`:

   ```python
   actor = author_view_user_id()   # note_base_context.py:68
   if actor is not None and actor != note.user_id:
       return None                 # người xem không phải chủ note: chỉ thấy Base
   ```

   - Job không có request context (actor `None`) giữ hành vi hiện tại.
   - Job nên bọc trong `note_author_view(owner_id)` khi cần thấy nháp.
2. Phía ghi: nếu actor khác chủ của một note đã publish mà có nháp, `redirect_published_note_writes`
   sẽ tính delta từ Base, nên dễ đè mất nháp của tác giả.
   - Cách sửa: báo lỗi xung đột (`FieldIdentityConflict`), trừ khi đang ở
     `base_maintenance`.
   - Trước khi chọn, rà các đường admin hoặc ghi hộ (admin mode, change request merge do
     tác giả chạy thì actor là chủ note nên không bị ảnh hưởng).
3. Ghi vào ADR rằng admin xem note của người khác sẽ thấy Base.

### Nghiệm thu

Test MySQL với note đã publish và có nháp:
- learner đăng nhập đọc `note.field_values` của note nguồn: nhận Base;
- tác giả đăng nhập: nhận Base + nháp;
- job dùng `note_author_view(owner)`: nhận Base + nháp;
- người không phải chủ ghi qua property vào note đó: bị từ chối, nháp không đổi.

---

## R3. Học một thẻ phải duyệt mọi install của learner (sửa trước cutover)

### Bằng chứng trong code

- Ở chế độ Base, `resolve_clone_scope_for_card`
  ([share/overlay.py:478-496](../../app/services/share/overlay.py)) làm như sau:
  - nạp **mọi** install `logical_overlay` của user;
  - với từng install, gọi `resolve_clone_scope_for_local_deck`, gồm truy vấn
    `DeckCloneDeckMap` và duyệt cây deck theo từng tầng trong `expanded_source_deck_mapping`
    (`effective_note_reader.py`);
  - rồi chạy `query_clone_scope_cards(scope)...first()`.
- Hàm này được gọi ở **mỗi lần trả lời thẻ** không thuộc user
  (`app/routes/flashcards/study.py:1119-1120`) và ở Browse
  (`browse_card_service.py:124`).
- Cách cũ chỉ cần một truy vấn có lọc:
  `find_logical_overlay_installs_for_card(user_id, source_deck_id)`.

### Hướng sửa

1. Lọc install trước, bằng điều kiện rẻ:
   - `source_owner_user_id == card.note.user_id`;
   - `source_note_type_id == card.note.note_type_id`.
2. Tính một lần chuỗi deck tổ tiên của `card.note.deck_id`, chỉ khoảng vài truy vấn theo
   độ sâu. Chỉ giữ install có `source_deck_id` nằm trong chuỗi đó.
3. Chỉ dựng scope và chạy kiểm tra thẻ cho install còn lại, thường là 1.

### Nghiệm thu

- Test đếm SQL của một lần trả lời thẻ, cho learner có 1 install và có 5 install: số câu
  SQL không tăng theo số install, chênh lệch tối đa 1–2 câu.
- Kết quả scope giống hệt cách hiện tại. Các test overlay và study hiện có vẫn pass.

---

## R4. Benchmark chưa đo được latency thật (đo trước cutover)

### Bằng chứng

- `scripts/bench_note_published_base_mysql.py:241` chạy `ThreadPoolExecutor` 10 thread
  trong **một** process Python.
  - Mỗi ô có 10 mẫu cho mỗi thao tác.
  - Thứ tự cố định: legacy chạy trước rồi mới tới published_base (dòng 318).
- Kết quả chế độ Base:
  - thông lượng 5–7 request/s;
  - CPU Python khoảng 0,1 s mỗi request, nên p50/p95 chủ yếu là thời gian xếp hàng chờ
    GIL;
  - Browse p50 0,86–0,96 s, Search 1,8–3,1 s, Study 0,83–1,33 s;
  - Study chậm hơn legacy ở 4/6 ô.
- Còn thiếu:
  - latency của một request đơn lẻ, kèm số lượt đọc trang;
  - phía tác giả khi có nháp: harness không có thao tác tác giả nào;
  - publish nhiều note: mới đo 1 note;
  - nguyên nhân của trường hợp legacy 0 override mất 235–345 s (chưa có EXPLAIN).

### Hướng sửa

1. **Chạy tuần tự 1 VU.** Ghi theo từng request:
   - thời gian (ms);
   - chênh lệch `Innodb_buffer_pool_read_requests` và `Innodb_buffer_pool_reads`;
   - số câu SQL.

   Đổi luân phiên thứ tự hai chế độ.
2. **Kịch bản tác giả** trên 10k note, với 0, 200 và 2.000 nháp: trang Browse, search
   toàn field, sort theo word.
3. **Publish 10, 1.000 và 10.000 nháp.** Ghi:
   - thời gian;
   - số câu SQL;
   - thời gian giữ khoá: `innodb_row_lock_time` hoặc
     `performance_schema.data_lock_waits`.
4. **Đo đồng thời** bằng nhiều process (gunicorn hoặc multiprocessing), không dùng thread
   trong một process.
5. **Ràng buộc khi đo:**
   - giữ buffer pool 1 GB theo chốt của chủ dự án, không resize;
   - không thêm index.

### Nghiệm thu

- Bảng số đo mới thay cho bảng p95 trong `NOTE_PUBLISHED_BASE_REHEARSAL_2026-10-29.md`.
- Ghi rõ phần nào là thời gian SQL, phần nào là thời gian Python.

---

## R5. Search và sort phía tác giả: 2 subquery nháp cho mỗi field (đo trước cutover)

### Bằng chứng trong code

- `note_field_json_expression`
  ([field_value_query_repository.py:32-46](../../app/repositories/field_value_query_repository.py))
  tạo, cho **mỗi** field identity:
  - một `EXISTS` vào `note_drafts` (`op='remove'`);
  - một scalar subquery (`op='set'`), tương quan theo từng note.
- `note_values_search_condition` (dòng 178-200) áp biểu thức này lên mọi FieldDef của note
  type, tức 2 × K lần tra PK cho mỗi note.
- Ngoài ra còn `_EffectiveExtras` (dòng 104-131), dùng `JSON_TABLE` và `JSON_OBJECTAGG`.
- Sort theo word (`owned_note_word_expression`, `browse_card_repository.py:54-75`) dùng cùng
  biểu thức cho từng field text.
- Kế hoạch chỉ tính 1 LEFT JOIN nháp cho mỗi note.

### Hướng sửa (đo trước theo R4, không thêm index)

- Nhánh owned chỉ LEFT JOIN `note_drafts` **một lần** cho mỗi note, rồi dựng biểu thức từ
  `d.field_values_by_id`, bỏ subquery tương quan.
- Hoặc tối thiểu, đặt trước một nhánh tắt
  `CASE WHEN <note không có nháp> THEN base ELSE ... END`, để note không có nháp (gần như
  tất cả) không phải chạy biểu thức nháp.

### Nghiệm thu

- Ghi EXPLAIN và số lượt đọc trang cho search tác giả trên deck cỡ N1, với 0 và 200 nháp.
- Mục tiêu ≤ khoảng 1,2 lần so với khi tắt cờ.
- Các test search tác giả, public và clone hiện có vẫn pass.

---

## R6. Mỗi lần tác giả lưu, khoá mọi listing cùng note type (đo trước cutover)

### Bằng chứng trong code

- `lock_and_bump_note_listings`
  ([note_draft_service.py:85-110](../../app/services/note_draft_service.py)) chạy ở mọi
  flush có note thay đổi (`field_value_identity_hooks.py:103`).
  - Nó `SELECT ... FOR UPDATE` **mọi** `deck_marketplace_items` có cùng
    `(owner, note_type)`, rồi mới lọc listing nào phủ deck của note.
- Trên production, một note type được 18 listing dùng chung. Vì vậy mỗi lần lưu của tác
  giả, MCP hay Connect đều khoá cả 18 dòng.
- Publish giữ khoá dòng listing cùng dòng NoteType trong suốt transaction
  (`note_base_publish_service.py:131-134`).
- Theo ADR, ghi override của learner cũng khoá NoteType trước.
- Hệ quả:
  - mọi lần lưu của tác giả phải chờ khi bất kỳ listing nào trong 18 đang publish;
  - mọi lần sửa override của learner trên cả 18 listing cũng phải chờ publish xong.
- Thời gian khoá của một lần publish lớn chưa được đo (xem R4).

### Hướng sửa

- Khi chỉ đổi note (không đổi schema): tính tập deck tổ tiên trước (code đã tính sau khi
  khoá), rồi chỉ khoá các listing có `source_deck_id` nằm trong tập đó.
- Khi đổi FieldDef: giữ khoá mọi listing của note type như hiện nay.
- Giữ thứ tự khoá đã ghi trong ADR (listing → NoteType → Note → nháp) để không phát sinh
  deadlock.

### Nghiệm thu

Test MySQL hai kết nối:
- Kết nối A đang publish listing A (giữ khoá).
- Kết nối B lưu nháp một note thuộc listing B, cùng note type. B không phải chờ A.

Test deadlock hiện có vẫn pass.

---

## R7. `notes.updated_at` không đổi khi lưu nháp (nhỏ)

- `_CONTENT` có `updated_at` ([note_draft_service.py:22-23](../../app/services/note_draft_service.py)),
  và bị đặt lại về giá trị Base ở dòng 277-278.
- Vì vậy thứ tự phụ trong Browse (`browse_note_repository.py:294`) và `updated_at` trả về
  (dòng 41) vẫn hiện thời điểm của Base, không phải lần sửa nháp gần nhất.
- **Sửa:**
  - Nhánh owned sắp xếp theo `author_note_column("updated_at")`.
  - Payload của tác giả trả `max(note.updated_at, draft.updated_at)`.
- **Nghiệm thu:** sửa nháp một note thì note đó lên đầu trong thứ tự phụ, và ngày sửa
  hiển thị đổi theo.

## R8. Retention chưa có lịch chạy (vận hành)

- Hiện chỉ có lệnh CLI `note-base-retention` (`app/cli.py:464-469`). Không có timer hay
  cron nào trong `deploy/`.
- Đề xuất:
  - thêm timer chạy hằng ngày: `--apply`, lặp `--after` cho tới khi `next_cursor` rỗng;
  - ghi log số dòng đã xoá;
  - cập nhật runbook.
- Câu `Note.deleted_at <= cutoff` không có index, nên quét khoảng 41k note mỗi lần. Chạy
  mỗi ngày một lần thì chấp nhận được. Không thêm index.

## R9. Hai đường code song song tới P6 (vận hành)

- Có 110 chỗ gọi `published_base_enabled()` trong 36 file. Runtime legacy (rebase, atom,
  dirty journal) vẫn còn nguyên.
- Backend đang +3.118/−167 dòng. Phần giảm khoảng 11.000 dòng (kế hoạch §7.2) chỉ có ở P6.
- Đề xuất:
  - chốt ngày làm P6 ngay sau soak;
  - tạo issue checklist liệt kê 36 file có nhánh theo cờ;
  - code mới không thêm nhánh legacy nữa.

## R10. PR lẫn phần di chuyển FSD ở frontend (quy trình)

- Phần frontend có 63 file, +2.745/−2.162 dòng. Phần lớn là di chuyển theo FSD:
  - `App.tsx` chuyển sang `app/App.tsx`, file cũ thành shim;
  - `DeckCard*` chuyển sang `entities/marketplace-deck`, file cũ re-export;
  - tách `SharedDeckDetailPage`;
  - `InstalledDecksPage` chuyển sang `pages/installed-decks`.
- Việc này đúng quy tắc "FSD khi chạm file" trong `AGENTS.md`. Nhưng `App.tsx` là cửa vào
  của mọi route, mà kiểm tra trình duyệt chỉ làm trên màn so sánh.
- Đề xuất:
  - tách các commit di chuyển FSD sang PR riêng;
  - nếu giữ chung, smoke tất cả route cấp một ở desktop và mobile, chụp ảnh trước/sau
    (profile Chrome riêng), để giữ Zero Visual Regression.

## R11. Việc của chủ dự án trước P4 (không phải việc của agent)

- Bản copy production mới cho ra **6 note** cần thành nháp, gồm 31 field khác biệt.
- Chủ dự án duyệt manifest riêng trong `output/note-base-rehearsal/fresh/`. Thư mục này nằm
  ngoài Git và không được đưa vào báo cáo công khai.

---

## Ràng buộc khi sửa

- Không thêm hay đổi index khi chưa được chủ dự án duyệt (guardrail trong `AGENTS.md`).
- Không đổi buffer pool. Chạy test và đo trên MySQL local, không dùng SQLite.
- Giữ mô hình overlay-only: không copy note cho learner, không ghi vào note nguồn từ luồng
  clone.
- Chỉ sửa trong worktree `D:/Project/nihongo-note-base-20261029`, không đụng checkout chính
  `D:/Project/nihongo`.
- Chạy test với 7 cờ `STUDY_*` để rỗng (xem lệnh ở đầu tài liệu).
- Chỉ commit hoặc push khi chủ dự án yêu cầu.

## Phụ lục A. Script đo property

- Chạy từ gốc worktree.
- Script tạo DB MySQL riêng qua `NoteBaseMySQLTestCase` và xoá DB đó khi chạy xong.
- Hàng "cờ tắt" seed `published_at` giống hệt hàng "cờ bật", để so sánh cùng dữ liệu.

```bash
env STUDY_WIRE_V4_ENABLED= STUDY_ASYNC_BATCH_ENABLED= STUDY_NEW_LEARNER_NOTE_ENABLED= \
  STUDY_NOTE_COUNT_ENABLED= STUDY_PROGRESS_SHADOW_WRITE_ENABLED= \
  STUDY_PROGRESS_SHADOW_READ_ENABLED= STUDY_PROGRESS_SHADOW_COMPARE_ENABLED= \
  FLAMA_MYSQL_TESTS=1 PYTHONPATH=. .venv/Scripts/python.exe path/to/bench_draft_property.py
```

```python
"""Measure author property reads with many Notes in one session (flag on vs off)."""
import sys
import time
import unittest
from datetime import datetime

from sqlalchemy import event

from app.services.note_base_context import published_base_write
from models import db
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from tests.study_note_fixtures import create_note_user

SIZES = (500, 2000, 5000)


class _Bench:
    def _seed(self, count):
        owner = create_note_user(db.session, username=f"bench-{count}", email=f"bench-{count}@example.invalid")
        nt = NoteType(user_id=owner.id, name="Bench")
        db.session.add(nt)
        db.session.flush()
        word = FieldDef(note_type_id=nt.id, name="Word", field_type="text", position=0)
        deck = Deck(owner_user_id=owner.id, note_type_id=nt.id, name="Bench deck")
        db.session.add_all([word, deck])
        db.session.flush()
        notes = [Note(user_id=owner.id, note_type_id=nt.id, deck_id=deck.id, field_values={"Word": f"w{i}"}, tags=[])
                 for i in range(count)]
        db.session.add_all(notes)
        db.session.flush()
        with published_base_write("bench"):
            now = datetime.utcnow()
            for note in notes:
                note.published_at = now
            db.session.flush()
        db.session.commit()
        deck_id = deck.id
        db.session.remove()
        return deck_id

    def _queries(self):
        counter = {"n": 0}
        def before(*_a, **_k):
            counter["n"] += 1
        event.listen(db.engine, "before_cursor_execute", before)
        return counter, lambda: event.remove(db.engine, "before_cursor_execute", before)

    def test_bench(self):
        for count in SIZES:
            deck_id = self._seed(count)
            notes = Note.query.filter(Note.deck_id == deck_id).all()
            counter, stop = self._queries()
            t0 = time.perf_counter()
            for note in notes:
                _ = note.field_values
            read_s, read_q = time.perf_counter() - t0, counter["n"]
            stop()
            db.session.rollback()
            # Batch write loop that flushes per note, like browse_voicevox_service.
            notes = Note.query.filter(Note.deck_id == deck_id).limit(min(count, 1000)).all()
            counter, stop = self._queries()
            t0 = time.perf_counter()
            for index, note in enumerate(notes):
                values = note.field_values
                values["Word"] = f"edit{index}"
                note.field_values = values
                db.session.flush()
            write_s, write_q = time.perf_counter() - t0, counter["n"]
            stop()
            db.session.rollback()
            db.session.remove()
            print(f"flag={self.FLAG} notes={count:>5} read_all={read_s:7.3f}s queries={read_q:>5} | "
                  f"write_loop({len(notes)})={write_s:7.3f}s queries={write_q:>6}", flush=True)


class BenchOn(_Bench, NoteBaseMySQLTestCase):
    FLAG = True
    APP_CONFIG = {"NOTE_PUBLISHED_BASE_ENABLED": True}


class BenchOff(_Bench, NoteBaseMySQLTestCase):
    FLAG = False
    APP_CONFIG = {"NOTE_PUBLISHED_BASE_ENABLED": False}


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "-v"])
```

Kết quả gốc của lần chạy ngày 2026-10-29 (MySQL 8.0.40, buffer pool 1 GB):

```text
flag=False notes=  500 read_all=  0.023s queries=    3 | write_loop(500)=  7.458s queries=  4000
flag=False notes= 2000 read_all=  0.075s queries=    3 | write_loop(1000)= 12.248s queries=  8000
flag=False notes= 5000 read_all=  0.365s queries=    3 | write_loop(1000)= 11.214s queries=  8000
flag=True  notes=  500 read_all=  0.353s queries=    4 | write_loop(500)= 15.511s queries=  6000
flag=True  notes= 2000 read_all=  6.142s queries=    4 | write_loop(1000)= 50.046s queries= 12000
flag=True  notes= 5000 read_all= 30.826s queries=    4 | write_loop(1000)= 40.330s queries= 12000
```
