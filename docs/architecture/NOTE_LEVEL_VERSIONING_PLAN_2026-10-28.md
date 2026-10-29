# Kế hoạch: `notes` là Published Base, tác giả và learner cùng "Base + phần mình sửa"

Ngày: 2026-10-28. Cập nhật 2026-10-29: **đã có implementation sau cờ và diễn tập
MySQL local; chưa cutover production**. Xem [ADR triển khai](NOTE_PUBLISHED_BASE_IMPLEMENTATION_2026-10-29.md)
và [bằng chứng diễn tập](NOTE_PUBLISHED_BASE_REHEARSAL_2026-10-29.md).
P4 production và P6 thu gọn lịch sử còn chờ gate vận hành; các quyết định bên dưới
giữ nguyên. Không thêm index phụ.

Hợp đồng sản phẩm nằm ở [TrinhChung/Flama#263](https://github.com/TrinhChung/Flama/issues/263),
bản viết lại ngày 2026-10-28 với tiêu đề "single published base + persistent user
overlay + soft delete". Tài liệu này là kế hoạch triển khai cho issue đó. Chỗ nào hai
bên khác nhau thì issue thắng.

Số liệu lấy từ bản copy production `flama_prod_rehearsal_20261025_idx` trên MySQL
local, mọi truy vấn chạy trong transaction READ ONLY. Code đối chiếu trên nhánh
`feat/flama-audio-edge-tts-20261027`.

## 1. Quyết định

### Đã chốt (chủ dự án và #263)

1. **`notes` chính là Published Base (D4 = B).**
   - Learner đọc `notes` cộng override của mình.
   - Tác giả đọc `notes` cộng bản nháp của mình.
   - Publish đổ bản nháp vào `notes` trong một transaction, rồi tăng
     `content_revision`.
   - Learner thấy ngay sau khi publish. Bản nháp chưa publish không bao giờ lộ ra.
2. **Bỏ version history, pinning, rollback và rebase.**
   - Không còn learner đứng lại ở release cũ.
   - Không có three-way merge hay luồng xử lý conflict.
   - Rollback chỉ còn ở mức vận hành, bằng backup DB.
3. **Bản nháp của tác giả lưu theo note**, đúng ý ban đầu: mỗi note đã publish có tối
   đa 1 dòng nháp, sửa tiếp thì ghi đè lên dòng đó.
4. **Override của learner lưu theo field**, theo #263: `note_id + field_identity` thắng
   Base. Kế hoạch giữ nguyên `deck_clone_note_field_overrides` vì những lý do sau:
   - Bảng đang 0 dòng trên production.
   - Bảng đã có unique `(install, note, field_identity_key)`, nên sửa lại là upsert.
   - Bảng đã có `set`/`remove`, tức là phân biệt được "xoá giá trị" với "xoá override".
   - SQL search/sort hiện tại đã join theo identity.
5. **Soft delete cho Note và Field.**
   - Giữ identity, override và tiến độ học. Không tái sử dụng ID.
   - Note đã bị tác giả xoá không tự hiện lại cho learner. Giữ nó làm thẻ cá nhân là
     tính năng fork riêng.
6. **Không copy deck và không fan-out theo subscriber** khi install hay publish.
7. **Xoá và retention:**
   - Tác giả xoá note mà không learner nào có tiến độ hay override trên note đó: xoá
     cứng ngay lúc publish.
   - Note còn được tham chiếu thì soft delete, để giữ tiến độ và override.
   - Retention 90 ngày áp cho phần còn lại, gồm field đã xoá và override trỏ vào note
     đã xoá.
8. **Giữ change request**, và giữ nhãn phiên bản kèm changelog dưới dạng metadata.
9. **Có dấu "bản gốc đã thay đổi" và một màn so sánh riêng**, không chen vào màn học.
   Override vẫn thắng.
10. **Schema chuyển luôn trong đợt này** sang snapshot `published_schema_json` (§3.5).
11. **Deck con mới của tác giả (D3):** thư mục riêng của learner chỉ được tạo khi learner
    thao tác. Trước đó, note của deck con mới hiện dưới thư mục gần nhất đã map (§4).
12. **Đã duyệt bảng và cột ở §8 (D1).**
13. **Cutover (D6):**
    - Nội dung hiện tại của user 1 trở thành Base, gồm cả các thay đổi do script
      (native array, dọn dữ liệu, sinh diagram).
    - Các bản cũ trước native array trong lịch sử release bị bỏ, không giữ làm rác.
    - Riêng các chỗ user 1 sửa tay mà chưa publish được giữ lại thành bản nháp.
    - Chi tiết ở §7.1.
14. **Chốt sau rà soát ngày 2026-10-28 (§9):**
    - Giữ nút Publish.
    - Sửa nháp ở hai nơi thì lần lưu sau thắng.
    - Note không ai tham chiếu thì xoá cứng lúc publish.
    - Gỡ ảnh không xoá file; một batch dọn ảnh sẽ làm sau.
    - Bỏ cài đặt auto-publish.
    - Đo baseline ở buffer pool 1 GB.

### Giả định, đề xuất đóng (§9 mục U5)

- Overlay cấu trúc của learner giữ nguyên và vẫn nằm trong effective view:
  `deck_clone_added_field_defs`, `deck_clone_field_def_overrides`,
  `deck_clone_field_order_overrides`, `deck_clone_added_notes`.
- Cả 4 bảng đều 0 dòng trên bản copy production, nên không có dữ liệu phải chuyển.

## 2. Hiện trạng và chi phí

| Bảng | Dòng | Dung lượng | Vai trò |
|---|---:|---:|---|
| `notes` | 41.623 | 108 MB | Nội dung, hiện là bản làm việc của tác giả |
| `deck_release_changes` | 164.259 | 214 MB | Atom theo field: 162.368 `note_field add`, 256 `note_field set`, 1.627 `field_def`, 8 `template` |
| `deck_working_dirty_entities` | 251.438 | 218 MB | Nhật ký sửa chưa publish, theo (note, field) |
| `deck_release_note_checkpoints` | 30.834 | 70 MB | Snapshot lúc publish đầu, key theo **tên** field |
| `deck_release_entity_memberships` | 31.159 | 21 MB | 30.834 dòng note, 325 dòng field |
| `deck_clone_note_field_overrides` | 0 | — | Override của learner |

Các số liệu khác:

- 22 listing, đều của user 1. 29 install của 15 user. 9 install đang ở release cũ hơn
  `current_release_id`.
- Không có note nào thuộc nhiều listing. Listing lớn nhất (N1) có 10.148 note trong
  171 deck.
- **Backlog chưa publish:** 251.438 dòng dirty journal, nhóm theo thời điểm ghi cuối
  của từng (note, field). Audit log không ghi lại thao tác sửa note, nên chỉ phân loại
  được theo thời điểm và theo field bị đổi.

| Thời điểm | Dòng (note, field) | Note | Nguồn | Khi cutover |
|---|---:|---:|---|---|
| 2026-10-23 12:00–12:06 UTC | 179.696 | 30.897 | Script native array | Thành Base |
| 2026-10-11 | 70.922 | 30.796 | Script dọn dữ liệu (NA-03) | Thành Base |
| 2026-09-01 và 09-04, chỉ field `diagram` | 594 | 594 | Sinh diagram hàng loạt (Kanji N1) | Thành Base (đã xác nhận, D7) |
| 08-28, 08-31, 09-06, 10-16 | 47 | 7 | Sửa tay trên note đã publish | Thành nháp |
| Note tạo mới chưa publish | — | 71 | 3 note trong listing N1, 68 note trong hai listing chưa có release | Giữ `published_at` null |
- **Code chạm tới:**
  - 21 file đang ghi giá trị note, trong đó 16 file gọi dirty journal;
  - khoảng 40 file đọc giá trị note (177 chỗ);
  - các repository SQL của Browse và search.

### 2.1 Điểm yếu của kiến trúc cũ, tài nguyên đang tốn và cách mô hình mới bỏ đi

Đo lại ngày 2026-10-28 trên cùng listing N1 và cùng 20 note đầu tiên:

- Phía cũ chạy đúng 5 câu SQL mà `_get_note_field_values_by_id_for_ids_at_release`
  ([deck_release_service.py:675](../../app/services/deck_release_service.py)) gửi
  đi ở release hiện hành.
- Phía mới đọc `notes` cùng LEFT JOIN override.
- Cache ấm, lấy lượt thứ 3. Buffer pool đang chạy 1 GB, nhưng số lượt đọc trang
  không phụ thuộc kích thước pool.
- Thời gian chỉ tính SQL, chưa gồm phần ghép giá trị bằng Python.

| Điểm yếu cũ | Đang tốn (bản copy 25/10) | Mô hình mới |
|---|---|---|
| **Lưu lịch sử giá trị theo từng field** (atom, checkpoint, membership) | 305 MB (214 + 70 + 21), gần gấp 3 `notes` (108 MB). Mỗi atom khoảng 1,4 KB và đi qua 6 index. Checkpoint là bản copy đầy đủ của note lúc publish lần đầu, khoảng 2,2 KB mỗi note | Bỏ hẳn. Base chính là `notes`, không có bản copy thứ hai |
| **Nhật ký bẩn theo (note, field)** | 218 MB, 251.438 dòng, 5 index, khoảng 0,9 KB mỗi dòng. Mỗi lần sửa k field của một note thì upsert k dòng. Đợt native array sinh 179.696 dòng cho 30.897 note | Mỗi note đang sửa có 1 dòng nháp |
| **Learner đọc phải dựng lại giá trị theo release** | Một trang 20 note cần 5 câu SQL, **7.425 lượt đọc trang**, 15 ms SQL, chưa kể Python. Cả request Browse khoảng 905 ms, trong đó dựng giá trị ~159 ms, count ~190 ms, page ~395 ms. Search toàn collection chạm giới hạn 5 giây | Một trang 20 note cần 1 câu SQL, **64 lượt đọc trang**, 1 ms. Count 17 ms, search 52–57 ms, sort 74 ms (11–52 nghìn lượt đọc trang cho 10k note) |
| **Publish ghi atom cho từng field** | Lần publish đầu của N1 ghi 162.448 atom. Publish backlog hiện tại theo cách cũ sẽ ghi thêm khoảng 251 nghìn atom, ước tính ~350 MB qua 6 index | Publish chỉ cập nhật các note có nháp. Backlog thành Base lúc cutover mà không phải ghi thêm |
| **Việc theo từng install** (prepare, rebase, conflict, fan-out) | Mỗi lần xem diff cập nhật N1 mất 410–455 ms và 501.722 lượt đọc trang; nhánh gộp nhiều release vượt 15 giây. Publish lặp qua từng install (hiện 29) | Không có việc nào theo install. Màn so sánh chỉ đọc override (hiện 0 dòng) |
| **Install đứng ở release cũ** | 9/29 install, buộc phải giữ toàn bộ lịch sử. Learner ở bản cũ vẫn thấy `$` thô | Mọi install đọc Base hiện hành |
| **Độ phức tạp code** | 59 file trong `app/` nhắc tới `DeckRelease`, `applied_release_id`, checkpoint hoặc membership. Đây là grep thô, có thể lẫn vài chỗ không liên quan | Release chỉ còn là metadata: nhãn, changelog, template pin |

Các số trên khác scope với nhau (một listing so với cả collection của learner), nên
không phải tỉ lệ tăng tốc chính xác cho cả request. Số end-to-end sẽ đo ở P0 và P3.

## 3. Mô hình mới

```text
                 notes  (= Published Base)
                 + published_at, deleted_at, content_revision
                 + deck_marketplace_items.published_schema_json
                    │                         │
     LEFT JOIN note_drafts (PK note_id)   LEFT JOIN deck_clone_note_field_overrides
                    │                         │
          Tác giả: Base + nháp         Learner: Base + override + note/field tự thêm
                    │
        PUBLISH (1 transaction): đổ nháp vào notes, xoá nháp,
        set published_at cho note mới, ghi lại schema snapshot
```

### 3.1 Bản nháp của tác giả: `note_drafts` (tên tạm)

| Cột | Ý nghĩa |
|---|---|
| `note_id` | PK, FK `notes.id` cascade. Mỗi note tối đa 1 dòng |
| `field_values_by_id` (JSON) | Chỉ các field khác Base, key theo FieldDef ID |
| `tags` (JSON, null) | Null nghĩa là không đổi |
| `deck_id` (null) | Chuyển deck trong nháp. Null nghĩa là không chuyển |
| `op` | `edit` hoặc `delete` |
| `updated_at` | |

- **Không chống ghi đè trên nháp:** lần lưu sau thắng. Mỗi người chỉ có 1 bản, và tự
  chịu trách nhiệm khi sửa cùng lúc ở hai nơi (§9 mục U1).
  - Lưu nháp không tăng `notes.content_revision`. Số này chỉ tăng khi publish.
  - Không có cột revision trong `note_drafts`.

- **Chỉ note đã publish** (`notes.published_at IS NOT NULL`) mới có nháp. Note mới hoặc
  note chưa publish vẫn được sửa thẳng vào `notes`, và learner không thấy vì
  `published_at` còn null.
- **Sửa lại:** cập nhật dòng nháp. Field nào sửa về đúng giá trị Base thì bỏ key đó.
  Nháp không còn gì thì xoá dòng.
- **Bảng này thay cho dirty journal của note:** chính các dòng nháp là tập note bẩn.

### 3.2 Một cửa ghi và một cửa đọc

Phương án B chỉ an toàn khi không còn đường nào ghi thẳng vào Base hay đọc bỏ qua bản
nháp. Code hiện đã có sẵn một cửa ghi và một cửa đọc chung cho ORM, nên không cần sửa
từng writer và reader (rà soát ngày 2026-10-28, §9 mục E1).

**Cửa ghi: hook flush có sẵn.**

- Mọi writer đều gán `note.field_values = ...`. Giá trị được mã hoá trong hook
  `before_flush` `maintain_field_identity`
  ([field_value_identity_hooks.py:75](../../app/services/field_value_identity_hooks.py)).
- `guard_bulk_identity_writes` (cùng file, dòng 279) đã chặn UPDATE/INSERT hàng loạt
  và SQL thô vào `notes`.
- Việc chuyển hướng làm ngay trong hook đó:
  - Note chưa publish thì ghi `notes`.
  - Note đã publish thì ghi phần khác Base vào `note_drafts`, rồi trả `notes` về Base.
  - Chỉ ngữ cảnh publish, hoặc `base_maintenance` có audit, mới được ghi Base.
- Hook là đường ghi duy nhất, nên nó cũng là chốt fail-closed. Không cần thêm listener
  thứ hai.
- P0 vẫn phân loại 21 writer, để biết writer nào là *bảo trì kỹ thuật* (ví dụ chuẩn
  hoá đường dẫn media) cần chạy trong `base_maintenance`.

**Cửa đọc của tác giả: property có sẵn.**

- 131 chỗ trong 42 file đọc qua property `note.field_values`, tức là qua
  `read_note_named_values`
  ([field_value_runtime_service.py:157](../../app/services/field_value_runtime_service.py)).
  Chỉ 9 file đọc thẳng `field_values_by_id`.
- Cộng nháp ngay trong hàm đó. Nháp được nạp theo lô một lần cho cả session, để tránh
  N+1.
- Response ngay sau khi lưu đọc lại qua property, nên tự thấy bản nháp.
- Các repository SQL của Browse, search và count (`browse_note_repository`,
  `field_value_query_repository`, …) phải tự LEFT JOIN nháp.
- Nếu sót một chỗ, tác giả thấy Base thay vì bản vừa sửa. Không mất dữ liệu, nhưng sai
  hiển thị, nên mỗi bề mặt cần một test có sẵn bản nháp.

**Cửa đọc của learner `effective_note_reader` (tên tạm):**

- Learner đọc Base cộng override và note/field tự thêm. Trang marketplace công khai
  đọc Base.
- Hiện chỉ 8 file gọi hàm dựng giá trị theo release (`get_note_*_at_release`), cộng
  các repository SQL Browse của learner.
- Đường learner không được đọc `note.field_values` của note nguồn, vì property này sẽ
  cộng nháp. P0 phải xác nhận điều này, và test phía learner phải có sẵn bản nháp.

### 3.3 Đọc

- Trong **một transaction đọc**, thực hiện lần lượt:
  1. Xác định scope.
  2. Lấy candidate IDs.
  3. Phân trang.
  4. Batch lấy Base và lớp sửa của trang đó.
- Đọc trong một transaction thì cả request thấy cùng một snapshot InnoDB, nên không
  bao giờ thấy publish mới áp được một nửa.
- **Learner:**
  - Lọc `published_at IS NOT NULL AND deleted_at IS NULL` trong scope deck.
  - Giá trị `f` = `COALESCE(<override f>, JSON_EXTRACT(n.field_values_by_id, '$."f"'))`,
    kèm ngữ nghĩa `remove`.
- **Tác giả:**
  - Giá trị `f` = `COALESCE(JSON_EXTRACT(d.field_values_by_id, '$."f"'), JSON_EXTRACT(n.field_values_by_id, '$."f"'))`.
  - Ẩn các note có nháp `op = 'delete'`.
- Search, sort và count dùng cùng biểu thức này trước khi phân trang.
- Learner đọc schema từ `published_schema_json`, cache được theo `content_revision`.
- Template: learner dùng template pin của release hiện hành. Cơ chế này giữ nguyên:
  tác giả sửa `templates` trực tiếp, còn publish chụp sang `template_releases` (15
  dòng) và `deck_release_template_pins` (14 dòng). Không có bảng nháp template riêng.

### 3.4 Publish

- **Preview:** chỉ liệt kê nháp, note mới và thay đổi schema của listing. Không phải
  tính diff trên toàn deck.
- **Publish trong 1 transaction:**
  1. Đổ từng nháp vào `notes`: field, tags, `deck_id`. Tăng `notes.content_revision`
     và xoá nháp. Với `op = 'delete'`:
     - không learner nào có tiến độ hay override trên note: xoá cứng note;
     - còn được tham chiếu: set `deleted_at`.
  2. Set `published_at` cho note mới trong scope.
  3. Ghi lại `published_schema_json`.
  4. Tạo `DeckRelease` mang label, changelog, counts, template pin và
     `idempotency_key`.
  5. Cập nhật `current_release_id`.
  6. Bump `deck_count_content_revisions`.
  - `content_revision` của listing là `sequence_no` của release hiện hành.
- **Không ghi gì theo từng install.**
  - Reader của learner dùng `item.current_release_id` thay cho `applied_release_id`.
  - Bỏ `process_subscriber_auto_updates()`, `prepare_update` và
    `apply_prepared_update`.
  - Bỏ cài đặt auto-publish của listing (§9 mục E4). Tác giả luôn bấm Publish.
- **Quy tắc biên:**
  - Base theo note. Nếu hai listing lồng nhau cùng chứa một note, publish một listing
    là đổi Base cho cả hai. Production hiện không có trường hợp này.
  - Một note đã publish được nháp chuyển sang listing khác sẽ hiện ở listing đích ngay
    lần publish đó.

### 3.5 Schema và soft delete

- **Schema dùng snapshot:** tác giả sửa `field_defs` trực tiếp. Learner đọc
  `deck_marketplace_items.published_schema_json`, gồm id, tên, kiểu, vị trí, required,
  properties, đã xoá hay chưa, được ghi lại khi publish.
  - Schema chỉ có 22 JSON nhỏ, nên snapshot rẻ hơn nhiều so với đổi đường ghi schema
    sang nháp.
- **FieldDef cần `deleted_at` riêng:** FieldDef là định nghĩa cột dùng chung cho mọi
  note. Xoá field là đổi 1 dòng, không phải sửa hàng nghìn note. Giá trị và override
  vẫn giữ theo ID nên khôi phục được.
  - Tác giả xoá field thì phía tác giả ẩn ngay, còn learner vẫn thấy cho tới khi
    publish.
- **Note:**
  - Xoá trong nháp là `op = 'delete'`.
  - Lúc publish:
    - note không learner nào có tiến độ hay override thì xoá cứng;
    - note còn được tham chiếu thì set `notes.deleted_at`, giữ override và tiến độ của
      learner nhưng không hiện ở view thường.
- **Thay hai guard 409 hiện tại:**
  - `SHARED_ENTITY_RETIRE_REQUIRED` ở `flashcard_content_service.py:695`;
  - `note_has_shared_release_dependents()` ở `deck_working_tree_service.py:538`.
- **Retention 90 ngày:**
  - Field đã soft delete và không còn override tham chiếu: xoá cứng.
  - Note đã soft delete mà hết tham chiếu (ví dụ learner gỡ deck): xoá cứng.
  - Override trỏ vào entity đã xoá: xoá.
  - Tiến độ học giữ theo chính sách hiện có.
- **Ảnh và âm thanh trong field:** gỡ khỏi field chỉ bỏ tham chiếu, không xoá asset
  hay file (§9 mục U2). Việc xoá để dành cho một batch quét ảnh không dùng, làm sau.

### 3.6 Dấu thay đổi, màn so sánh, change request

- **Override của learner có thêm `base_hash`:** hash giá trị Base lúc learner sửa.
  - Dấu thay đổi hiện khi `hash(Base f) != base_hash` và override khác Base.
  - Dấu được tính lúc đọc, chỉ trên các override.
- **Màn so sánh:** dùng lại route và layout danh sách của `InstalledDeckUpdatePage`.
  - "Giữ bản của tôi" cập nhật `base_hash`. "Dùng bản tác giả" xoá override.
  - Màn học không hiện phần này.
- **Change request:**
  - Diff là override của learner so với Base.
  - Tác giả merge thì giá trị ghi vào nháp, rồi publish lên Base.
  - Bỏ phần "contributor vẫn pinned release" (`change_request/merge.py:461`).

## 4. Hành vi theo từng loại nội dung

| Nội dung | Tác giả sửa | Base (learner thấy) | Effective của learner |
|---|---|---|---|
| Giá trị field | Nháp (note đã publish) hoặc `notes` (note mới) | `notes.field_values_by_id` | Base + override |
| Tags | Nháp `tags` | `notes.tags` | Base. Learner không sửa tag clone, giữ chặn hiện tại |
| Note thuộc listing | Note mới: `published_at` null. Xoá: nháp `delete` | `published_at` có giá trị, `deleted_at` null, nằm trong scope deck | + `deck_clone_added_notes` |
| Chuyển deck | Nháp `deck_id` | `notes.deck_id` | Map qua `DeckCloneDeckMap` |
| FieldDef | `field_defs` trực tiếp, `deleted_at` | `published_schema_json` | + added/override/order của learner |
| Cây deck con | `decks` của tác giả | Deck của các note đã publish | Thư mục riêng tạo lúc install. Deck con mới hiện dưới thư mục gần nhất đã map; thư mục riêng chỉ tạo khi learner thao tác (D3) |
| Template | `templates` trực tiếp | `template_releases` qua pin của release hiện hành | Như hiện nay |
| Note type (tên, ứng dụng học) | Như hiện nay | Ngoài phạm vi, vẫn chặn khi đã publish | Như hiện nay |

## 5. Những gì sẽ bỏ

- **Backend:**
  - prepare/rebase/apply/conflict;
  - API diff cập nhật;
  - vòng auto-update theo subscriber;
  - dựng giá trị và field def theo release (`deck_release_service.py:675`,
    `_release_field_context`);
  - dirty journal;
  - các cột `auto_update_enabled`, `sync_mode`, `pending_conflict_count`,
    `applied_release_id`, `base_snapshot_at`: ngừng dùng trước, xoá khi dọn dẹp;
  - auto-publish: `deck_auto_publish_service`, lời gọi lúc commit trong
    `deck_working_tree_service`, và các cột `auto_publish_enabled`,
    `last_auto_published_at`, `last_auto_publish_error` của listing.
- **Bảng, ở P6:**
  - `deck_release_changes`. P0 phải kiểm tra 8 atom `template` có còn được dùng không;
  - `deck_release_note_checkpoints`;
  - `deck_release_entity_memberships`;
  - `deck_working_dirty_entities`;
  - `deck_install_rebases` và `deck_install_rebase_conflicts`.
- **Frontend:**
  - phần cập nhật, rebase và conflict trong `features/deck-collaboration`;
  - kiểm tra `features/cascading-sync` và `features/deck-review-merge`;
  - áp quy tắc di cư FSD cho mọi file chạm tới.
- **Dung lượng:** khoảng 520 MB bảng lịch sử sẽ mất, và không cần thêm bản copy Base.
  Bản nháp chỉ có dòng cho các note đang sửa.

## 6. Hiệu năng dự kiến

**Phép đo thử ngày 2026-10-28, đọc thẳng `notes` như learner sẽ đọc theo B:**

- Chỉ chạy SQL thô trên listing N1: 10.148 note, 171 deck.
- Truy vấn LEFT JOIN override theo một install không có override.
- Cache ấm, lấy lượt chạy thứ 3.
- Buffer pool **đang chạy ở 1 GB**, không persisted, khác mục tiêu 128M. Mình không tự
  đổi. Số lượt đọc trang không phụ thuộc kích thước pool.

| Thao tác (mô hình mới) | Thời gian | Lượt đọc trang |
|---|---:|---:|
| Trang 1, 20 note, đủ JSON | 2,0 ms | 800 |
| Count toàn listing | 17,2 ms | 11.389 |
| Search một field + count | 52,2 ms | 44.543 |
| Search một field + trang 1 | 56,7 ms | 52.549 |
| Sort theo field + trang 1 | 74,2 ms | 44.543 |

**Số đo hiện tại**, lấy từ các báo cáo trước. Các số này khác scope và khác ngày, nên
không phải tỉ lệ tăng tốc chính xác.

| Thao tác hiện tại | Số đo | Nguồn |
|---|---|---|
| Learner duyệt collection, 7 install, 20/trang | Khoảng 905 ms service. Trong đó count ~190 ms, page/content ~395 ms, dựng giá trị release ~159 ms | `BROWSE_REQUEST_DATA_AUDIT_2026-10-25.md` |
| Search toàn collection của learner | Câu count dài 490 nghìn ký tự, chạm giới hạn 5 giây | `BROWSE_QUERY_OVERFETCH_REVIEW_2026-10-24.md` |
| Trang diff cập nhật N1, release 1 → 2 | 410–455 ms, 501.722 lượt đọc trang. Nhánh gộp nhiều release > 15 giây | `installed-deck-update-query-review-2026-10-27.md` |
| Publish lần đầu N1 | Ghi 162.448 atom, cộng membership và checkpoint | Bảng §2 |

**Dự kiến:**

- **Learner:**
  - SQL của learner giống hệt SQL tác giả đang chạy hôm nay, cộng một LEFT JOIN
    override. Phần dựng giá trị release biến mất.
  - Phần còn lại của 905 ms (scope, tiến độ, serialize) không đổi. Phải đo end-to-end.
- **Tác giả:**
  - Thêm LEFT JOIN `note_drafts` theo PK. Bảng nháp nhỏ, nên dự kiến chỉ thêm vài tới
    vài chục ms khi search/sort quét 10k note. Chưa đo, vì bảng chưa tồn tại.
- **Publish:**
  - Preview chỉ đọc bản nháp.
  - Publish cập nhật đúng số note có nháp và không lặp qua install.
  - Republish toàn bộ 10k note (như #253) là khoảng 10k lần UPDATE trên `notes` trong
    một transaction. Chưa đo, sẽ đo ở P3.
- **Trang cập nhật:** bỏ. Màn so sánh chỉ đọc override của learner.
- **Giới hạn còn lại:**
  - Search và sort vẫn quét mọi note trong scope (khoảng 44–52 nghìn lượt đọc trang
    cho 10k note).
  - Theo #263, chỉ thêm projection hay index khi load test chứng minh cần.

## 7. Các giai đoạn

| Giai đoạn | Việc (mục trong #263) | Kiểm chứng |
|---|---|---|
| **P0 Inventory + baseline** | (1) Phân loại 21 writer (tác giả sửa / bảo trì), khoảng 40 reader và các SQL repository (bề mặt tác giả / learner / công khai), cùng mọi chỗ đọc `DeckRelease`, checkpoint, `DeckReleaseChange`, `applied_release_id`. Viết ADR. Đo baseline end-to-end ở buffer pool đang chạy (1 GB, §9 mục U7). | Danh sách file và phân loại. Bảng số đo gồm thời gian, `Innodb_buffer_pool_read_requests`, `Innodb_buffer_pool_reads` |
| **P1 Cửa ghi/đọc, chưa đổi hành vi** | Đặt điểm chuyển hướng vào hook flush và property đọc có sẵn (§3.2), thêm LEFT JOIN nháp vào các repository SQL, gom 8 file learner về `effective_note_reader`. Cờ tắt thì hành vi y như hôm nay. | Test hiện có pass. Payload trước và sau giống nhau. |
| **P2 Mở rộng schema** | Migration tạo `note_drafts` và các cột ở §8. Backfill `published_schema_json` và `published_at` từ release hiện hành. Code chưa dùng. | Schema snapshot khớp `get_field_defs_at_release(current)`. `published_at` khớp membership. |
| **P3 Hoàn thiện sau cờ** | Reader learner trên Base, D3, ghi nháp, publish mới, listener fail-closed. Chạy migration cutover (D6) trên bản copy production mới. | (a) Learner ở release hiện tại: render và DOM cũ/mới giống nhau. (b) Với mọi note, Base + nháp của tác giả bằng đúng `notes` cũ. (c) Bảng ngữ nghĩa #263. (d) Đo publish. |
| **P4 Cutover production** | Dừng ghi, dump, chạy migration D6, bật cờ, tắt API cập nhật/rebase. 9 install được đưa lên Base mới nhất. Có giai đoạn soak không publish: cả 22 listing đều của user 1 nên dễ phối hợp. | Smoke render. Script rollback đã diễn tập. |
| **P5 Soft delete + phần learner** | `deleted_at`, thay hai guard 409, job retention, dấu thay đổi, màn so sánh, change request. | Test cho cả tác giả sở hữu trực tiếp và bản cài clone. |
| **P6 Thu gọn** | Xoá code và bảng ở §5. Load test theo ma trận #263 (10k note, 100/1.000 install, 0/20/1.000 override, 10–100 VU, buffer pool 128 MB và 1/2 GB). | Báo cáo trước/sau |

- **Rollback:**
  - Trước lần publish đầu theo mô hình mới: chạy script đổ nháp ngược vào `notes` rồi
    deploy code cũ. Các bảng release cũ vẫn còn nguyên.
  - Sau lần publish đó: chỉ còn backup.

### 7.1 Migration cutover (D6)

Chạy trên bản copy production mới trước, rồi mới chạy trên production lúc đã dừng ghi
và đã dump. Các bước:

1. **Phân loại lại backlog trên dữ liệu mới**, vì production đã đổi so với bản copy
   ngày 25/10.
   - Ưu tiên receipt chính xác: native array có plan/receipt theo từng (note, field)
     trong `/var/backups/flama/native-array-split-20261023/`.
   - Script nào không có receipt thì dùng khung thời gian ở §2.
   - Mọi (note, field) còn lại coi là sửa tay.
   - Xuất danh sách note sẽ thành nháp để chủ dự án duyệt. Trên bản copy 25/10 chỉ có
     khoảng 7 note.
2. **Note đã publish có sửa tay:**
   - Field sửa tay được đưa về giá trị ở release hiện hành, và giá trị hiện tại được ghi
     vào `note_drafts`.
   - Các field khác của note đó giữ nội dung hiện tại làm Base.
   - Tác giả vẫn thấy đúng như trước, vì Base cộng nháp bằng `notes` hiện tại.
3. **Mọi note khác giữ nguyên `notes`.**
   - Note đang là thành viên release hiện hành được set `published_at`.
   - 71 note chưa publish giữ `published_at` null.
4. **Schema:** `published_schema_json` lấy từ `field_defs` hiện tại, vì schema cũng đi
   theo nội dung hiện tại.
5. **Template:** tạo `DeckRelease` "cutover" với template pin là template hiện hành của
   tác giả (loại đã hiểu native array).
   - Learner đang ở release có pin cũ sẽ nhận giá trị array. Template chưa hiểu array
     sẽ in `String(array)`.
   - Diff DOM sau render ở P3 phải xác nhận không có chuỗi `$` thô hay mảng bị nối bằng
     dấu phẩy.
6. **Learner:** override đang 0 dòng, nên không có gì phải chuyển. Toàn bộ 29 install
   lên Base mới, và nhận luôn đợt native array cùng các lần dọn dữ liệu.
7. **Bỏ lịch sử cũ:** xoá các bảng ở §5 (gồm các bản trước native array) sau khi hết
   giai đoạn soak. Bản dump trước cutover là bản lưu duy nhất của lịch sử đó.

**Giới hạn:** một field bị sửa tay rồi sau đó bị script chạm lại sẽ được tính là
script, nên phần sửa tay đó đi vào Base. Nguyên nhân là dirty journal chỉ giữ thời
điểm ghi cuối.
- Chạy test bằng `python scripts/run_tests.py --module ...`. Migration chạy trên MySQL
  local.

### 7.2 Ước lượng khối lượng code (2026-10-28)

**Cách tính:**
- Phần xoá lấy từ số dòng thật (`wc -l`) của các file và hàm sẽ bỏ.
- Phần mới hoặc sửa là ước lượng theo từng việc, sai số khoảng ±30%.
- Không tính migration sinh tự động hay file dữ liệu.

**Theo loại:**

| Phần | Xoá | Mới hoặc sửa |
|---|---:|---:|
| Backend | ~6.200 | ~3.800 (mới ~2.500, sửa ~1.300) |
| Frontend | ~1.400 | ~700 |
| Test | ~3.500 | ~2.000 |
| **Tổng** | **~11.100** | **~6.500** |

Code giảm ròng khoảng 4.600 dòng. Phần khó và rủi ro nhất là khoảng 3.800 dòng backend
mới hoặc sửa.

**Backend xoá, khoảng 6.200 dòng:**
- `deck_install_rebase_service` (1.386), `deck_install_rebase_repository` (531),
  model rebase và conflict (186).
- `deck_release_service`: khoảng 2.000 trên 2.410 dòng. Gồm dựng lại theo release, diff
  atom và sparse, membership, checkpoint, danh sách thay đổi giữa hai release. Chỉ giữ
  phần serialize và danh sách release.
- `deck_release_repository`: khoảng 700 trên 854 dòng.
- `deck_working_tree_service`: khoảng 500 trên 608 dòng (dirty journal, lời gọi
  auto-publish).
- `deck_auto_publish_service` (242).
- Model atom, checkpoint, membership và dirty journal (304).
- Endpoint cập nhật, rebase và danh sách thay đổi trong `installations.py` và
  `deck_releases.py`: khoảng 300.

**Backend mới, khoảng 2.500 dòng:**

| Việc | Dòng |
|---|---:|
| Model `note_drafts`, migration mở rộng ở P2 và thu gọn ở P6 | ~480 |
| Chuyển hướng ghi trong hook flush, ngữ cảnh publish và `base_maintenance` | ~200 |
| Cộng nháp trong `read_note_named_values`, nạp theo lô | ~120 |
| Cửa đọc learner: Base + override + note tự thêm + schema snapshot | ~350 |
| Publish mới: preview nháp, đổ nháp, xoá cứng/soft delete, snapshot, metadata release | ~300 |
| Soft delete: lọc chung kiểu Card, 5 chỗ xoá hàng loạt, thay 2 guard 409, job retention | ~400 |
| Dấu thay đổi `base_hash` và API màn so sánh | ~200 |
| Script cutover D6 và script rollback | ~500 |

**Backend sửa, khoảng 1.300 dòng:**
- `share/overlay.py`: khoảng 300.
- Repository Browse (`browse_card`, `browse_search`, `browse_note`,
  `field_value_query`): khoảng 360.
- `browse_card_service` và `browse_note_service`: khoảng 150.
- Change request (`merge.py`, `preview.py`): khoảng 200.
- Khoảng 30 file có vài lời gọi rải rác (dirty journal, `_at_release`, guard): khoảng
  300.

**Frontend:**
- Xoá khoảng 1.400 dòng:
  - `useInstalledDeckUpdate` (524), `ConflictCard` (199), `UpdateActionSidebar` (178);
  - phần cập nhật và rebase trong `api.ts` và `types.ts`, khoảng 400;
  - UI cài đặt auto-publish, khoảng 100.
- Mới hoặc sửa khoảng 700 dòng:
  - màn so sánh dựng lại từ layout `InstalledDeckUpdatePage`, khoảng 400;
  - `ReleaseBuilderPage` đổi sang danh sách nháp, khoảng 150;
  - dấu thay đổi trong Browse, khoảng 100.
- Có thể xoá thêm `features/cascading-sync` (780) và `features/deck-review-merge`
  (3.703). Hai slice này không có chỗ nào import ngoài chính thư mục và test của chúng,
  tức đã là code chết từ trước. Việc xoá không bắt buộc cho kế hoạch, nên không tính
  vào bảng.

**Test:**
- Xoá hoặc viết lại khoảng 3.500 dòng:
  - `test_deck_install_rebase_flow` (1.087), `test_owner_note_dirty_tracking_services`
    (776), `test_deck_auto_publish_and_auto_update` (448);
  - `test_deck_release_performance_mysql` (374), `test_deck_release_schema` (131);
  - khoảng 600 trên 909 dòng của `test_deck_release_api`.
- Mới khoảng 2.000 dòng:
  - bảng ngữ nghĩa #263;
  - cách ly nháp trên từng bề mặt;
  - soft delete, publish và diễn tập cutover.

**Theo giai đoạn:**

| Giai đoạn | Mới hoặc sửa | Xoá |
|---|---:|---:|
| P1 Cửa ghi/đọc | ~1.000 | 0 |
| P2 Mở rộng schema | ~430 | 0 |
| P3 Learner trên Base, publish mới, script cutover | ~2.600 | 0 |
| P4 Cutover production | Vận hành, gần như không có code | 0 |
| P5 Soft delete, dấu thay đổi, màn so sánh, frontend | ~2.300 | 0 |
| P6 Thu gọn và load test | ~350 | ~11.100 |

## 8. Index, cột và ràng buộc (đã duyệt 2026-10-28, chưa thêm)

Chủ dự án đã duyệt đúng phạm vi dưới đây. Thêm index hay cột nào khác vẫn phải duyệt
riêng theo guardrail trong `AGENTS.md`.

| Thay đổi | Workload và lý do |
|---|---|
| Bảng `note_drafts`, PK `note_id`, không index phụ | Đọc: phía tác giả LEFT JOIN theo PK; publish đi từ index `notes.deck_id` rồi tra PK. Ghi: mỗi lần tác giả sửa note đã publish, mỗi note 1 dòng (thay cho 1 dòng mỗi field ở dirty journal). Dòng bị xoá khi publish. |
| `notes.published_at` | Learner lọc sau index `deck_id`. Không index. |
| `notes.deleted_at`, `field_defs.deleted_at` | Soft delete theo #263. Không index. |
| `deck_marketplace_items.published_schema_json` | 22 dòng. Chỉ ghi khi publish. |
| `deck_clone_note_field_overrides.base_hash` | Phục vụ dấu thay đổi. Bảng đang 0 dòng. |

- DDL thêm 2 cột vào `notes` (41.6k dòng, 108 MB) cần kiểm tra ALGORITHM=INSTANT trên
  MySQL 8.
- Ở P6, khi xoá bảng cũ, các index trên 4 bảng lịch sử cũng mất theo.

## 9. Rà soát trước khi triển khai (2026-10-28)

§2.1 là phần mô hình mới bỏ được. Mục này là phần mô hình mới còn kém hiệu quả hoặc
kế hoạch còn chưa rõ, kèm chi phí. D7 đã chốt: đợt sinh `diagram` ngày 01/09 và 04/09
được tính là script và đưa vào Base.

### 9.1 Kém hiệu quả, kèm chi phí

| # | Điểm | Chi phí | Đề xuất |
|---|---|---|---|
| E1 | Bản kế hoạch trước định chuyển 21 writer và khoảng 40 reader sang cửa mới | P1 chạm khoảng 60 file | Đặt chuyển hướng vào hai cửa có sẵn (§3.2). P1 còn 2 hook, các repository SQL và 8 file learner. **Đã sửa trong kế hoạch** |
| E2 | Search, sort và count của learner vẫn quét mọi note trong scope | N1: 44–52 nghìn lượt đọc trang, 52–74 ms mỗi lần | Giữ như #263: chỉ thêm projection hay index khi load test chứng minh cần |
| E3 | Publish theo B ghi lại JSON của từng note có nháp | Mỗi dòng `notes` khoảng 2,7 KB, qua 4 index. Republish 10k note ghi lại khoảng 27 MB trong một transaction, và khoá 10k dòng note của tác giả trong lúc đó | Ghi theo lô qua một adapter được `guard_bulk_identity_writes` cho phép. Đo ở P3. Bình thường mỗi lần publish chỉ vài note |
| E4 | Cài đặt auto-publish của listing | Chỉ listing thử "Test âm thanh" (1 install) bật | **Đã chốt:** bỏ cài đặt này. Việc "learner tự nhận cập nhật" vốn đã biến mất, vì publish ghi thẳng vào Base |
| E5 | Soft delete buộc mọi reader lọc `deleted_at`, kể cả phía tác giả. Kế hoạch trước chỉ nói phía learner | 42 file ORM cùng các repository SQL. 5 chỗ xoá hàng loạt (`Note.query…delete`: 2 chỗ trong `deck_management_service`, `delete_notes_by_ids`, 2 chỗ trong seeding) đi vòng qua flush | Dùng lại mẫu của Card: `with_loader_criteria` trong `do_orm_execute` ([card.py:224](../../models/card.py)) lọc mọi ORM SELECT ở một chỗ; repository SQL lọc tay; các chỗ xoá hàng loạt chạm note đã publish chuyển sang soft delete. **Đã chốt:** note không ai tham chiếu thì xoá cứng ngay lúc publish, nên chỉ note có tiến độ hoặc override mới thành tombstone (hiện 4.069 dòng tiến độ của 7 learner trên note nguồn) |
| E6 | Schema snapshot theo listing, trong khi 18 listing dùng chung 1 note type | Đổi schema phải publish 18 lần, giống hôm nay. Không tốn thêm tài nguyên | Thêm thao tác "publish mọi listing của note type này" |

### 9.2 Chưa rõ hoặc còn thiếu

| # | Vấn đề | Bằng chứng | Đề xuất |
|---|---|---|---|
| U1 | Tác giả mở cùng một note ở hai nơi (hai tab, hoặc Browse trong lúc MCP đang sửa). Không liên quan giữa các user: mỗi learner có override riêng, và phía learner đã có `overlay_revision` | Browse, MCP và màn sửa nhanh khi học gửi `expected_content_revision`. Server so với `notes.content_revision` ([note_value_precondition_service.py](../../app/services/note_value_precondition_service.py)). Nếu bản sửa vào nháp mà `notes` không đổi, phép so này luôn qua, nên lần lưu sau đè lần trước | **Đã chốt:** chấp nhận lần lưu sau thắng, vì sửa cùng lúc ở hai nơi là lỗi của người sửa. Mỗi người chỉ giữ 1 bản. Không thêm cột, bỏ `base_content_revision`. Phép so `expected_content_revision` hiện có giữ nguyên, và chỉ còn báo khi có publish xen giữa lúc mở và lúc lưu |
| U2 | Ảnh và âm thanh nằm trong field của note (ảnh ở field hình, audio TTS…), khi tác giả gỡ ra trước lúc publish | `delete_media` xoá ngay `MediaAsset` cùng file ([flashcard_media_api_service.py:471](../../app/services/flashcard_media_api_service.py)). Nhưng Base learner đang xem vẫn trỏ tới ảnh đó, nên learner thấy ảnh hỏng cho tới lần publish | **Đã chốt:** gỡ ảnh khỏi field chỉ bỏ tham chiếu, không xoá asset hay file. Sau này làm một batch quét và xoá ảnh không dùng. Batch đó phải coi ảnh còn được Base, nháp hoặc override trỏ tới là đang dùng |
| U3 | Template | Kế hoạch trước ghi "bản nháp template", nhưng không có bảng đó | Giữ cơ chế `template_releases` có sẵn. **Đã sửa §3.3 và §4** |
| U4 | Rollback trước lần publish đầu chưa đủ bước | Code cũ publish từ dirty journal, và dựng giá trị cho learner từ atom. Release "cutover" không có atom | Script rollback phải: đổ nháp ngược vào `notes`; tạo lại dòng dirty journal cho các field có nháp; trả `current_release_id` và `applied_release_id` về giá trị trước cutover; xoá release cutover |
| U5 | Giả định về overlay cấu trúc ở §1 mâu thuẫn với "không còn câu hỏi mở" | Cả 4 bảng đều 0 dòng. `deck_clone_deck_maps` có 2.368 dòng | Đóng giả định: giữ nguyên bảng và hành vi. Bộ lọc learner `published_at IS NOT NULL` phải UNION thêm note learner tự thêm, vì các note này luôn có `published_at` null |
| U6 | Cờ ở P1–P3 | Dữ liệu chỉ chuyển một chiều, từ dirty journal sang nháp | Cờ chỉ dùng cho test và cho bước cutover. Không bật tắt qua lại trên production, không ghi song song |
| U7 | Buffer pool khi đo baseline P0 | Buffer pool đang chạy 1 GB (8 × 128 MB), không persisted | **Đã chốt:** để nguyên 1 GB. Vẫn ghi số lượt đọc trang cạnh thời gian, vì số này không phụ thuộc kích thước pool |

### 9.3 Phương án đã cân nhắc và không chọn

"Base thưa":
- `notes` vẫn là bản tác giả đang sửa.
- Lần đầu sửa một note đã publish, hook chép giá trị cũ của note đó sang một bảng thưa.
- Learner đọc `COALESCE(override, bản cũ, notes)`.

Phương án này rẻ hơn ở bước publish (chỉ xoá dòng) và cutover (không đụng `notes`).
Không chọn vì hai lý do:
- **Hướng lỗi nguy hiểm hơn.** Sót một chỗ đọc của learner là learner thấy nội dung
  chưa publish, vi phạm yêu cầu cách ly nháp của #263. Với B, sót một chỗ chỉ làm tác
  giả thấy Base: sai hiển thị nhưng không lộ dữ liệu.
- **Lợi thế chi phí không còn lớn.** Sau E1, phần code thêm của B chỉ còn 2 hook và
  vài repository.

### 9.4 Kết quả

Ngày 2026-10-28 chủ dự án đã chốt mọi mục trong bảng:
- U1, U2, U7 ở §9.2;
- E4, E5 ở §9.1;
- **Giữ nút Publish**, đúng như #263 mục 6: bản sửa nằm trong `note_drafts` tới khi
  tác giả bấm Publish, bấm xong là learner thấy ngay.

Không còn câu hỏi mở. Bước tiếp theo là P0 (inventory, ADR, baseline).
