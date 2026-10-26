# Release deck — các điểm còn chưa tối ưu sau bản sửa Issue #253

Ngày: 2026-10-26. Baseline code: `73651305` (`fix perfomance relase deck`), nhánh
`fix/deploy-disconnect-cloudflare`. Bối cảnh: tiếp nối
[`ISSUE_253_RELEASE_INVESTIGATION_2026-10-26.md`](ISSUE_253_RELEASE_INVESTIGATION_2026-10-26.md).

Báo cáo này chỉ điều tra, **không sửa code, dữ liệu, schema, index hay cấu hình**.
Mọi phép đo chạy trong transaction `READ ONLY` trên MySQL local, bộ Tettei N1
(`97b15098-89db-4afe-a11d-034cad593fe6`, 10.148 note, 91.281 thay đổi đang chờ).

## 1. Kết luận ngắn

Bản sửa #253 đã giảm preview từ 32,7 giây xuống khoảng 5,2 giây, và dựng + flush
release từ khoảng 136 giây xuống khoảng 26 giây. Vẫn còn 3 nhóm vấn đề:

1. **Journal làm việc không phản ánh đúng dữ liệu (ưu tiên cao nhất, ảnh hưởng cả
   tính đúng lẫn hiệu năng).** Full diff tìm ra 20.224 thay đổi mà journal không ghi
   (đổi tham chiếu media `[sound:…]` sang `/media/proxy/…`). Ngoài ra có 10.146 dòng
   journal đã lỗi thời vì field `reading` bị đổi ngược về `text` mà không ghi journal.
   Dòng lỗi thời đó buộc mọi preview/publish chạy full diff. Nếu nó tình cờ khớp,
   đường sparse sẽ **phát hành thiếu 20 nghìn thay đổi mà không báo lỗi**.
2. **Publish vẫn chạy đồng bộ khoảng 26 giây (local) trong lúc giữ khóa listing.**
   Phần lớn thời gian là INSERT 91 nghìn atoms (13,9 giây) và DELETE journal
   (4,3 giây). Nginx đặt `proxy_read_timeout` mặc định 60 giây. Nếu vượt mốc đó,
   frontend vẫn chuyển cả ứng dụng sang `/maintenance`.
3. **Còn đọc và tính lặp không cần thiết.** Mỗi trang, bộ lọc hay ô tìm kiếm của
   preview đều dựng lại toàn bộ diff (~5,2–5,6 giây). Endpoint trạng thái
   auto-publish dựng cả preview chỉ để đếm (5,0 giây) mỗi lần owner mở trang deck.
   Truy vấn lịch sử vẫn duyệt 162.680 atoms để lấy 312 dòng. Note được đọc qua
   adapter tên field (1,13 giây) dù đọc theo ID chỉ mất 0,03 giây.

Đề xuất thứ tự xử lý ở [mục 5](#5-lộ-trình-đề-xuất). Các sửa rẻ nhất, không cần
schema mới, gồm: sửa writer ghi journal, xử lý lỗi release ở frontend, bỏ preview
khỏi auto-publish status, và loại phần đọc/tính thừa trong preview.

## 2. Phương pháp và giới hạn

- Probe chỉ đọc (`SET TRANSACTION READ ONLY`, chặn mọi câu lệnh không phải
  SELECT/SHOW/EXPLAIN), có request context, rollback ở cuối. Script và kết quả JSON
  nằm trong `output/` (bị gitignore): `release_residual_probe.{py,json}`,
  `sparse_parts_probe.py`, `journal_gap_probe.py`, `untracked_sample_probe.py`.
- MySQL 8.0.40 local. Buffer pool **runtime là 1 GiB** (8 instances, chunk 128 MiB),
  còn `my.ini` đặt mục tiêu 128M. Không đổi cấu hình và không restart. Với 128M hoặc
  trên production, số đọc đĩa và thời gian có thể lớn hơn. Đọc đĩa trong mọi phép đo
  ở đây đều bằng 0, nên thời gian chưa phản ánh chi phí I/O.
- Số liệu publish lấy từ probe sau sửa của phiên trước
  (`output/issue253_publish_after.jsonl`), **không chạy lại** trong lần này để không
  dựng thêm release thử.
- Chưa có số đo production, HTTP log hay HAR. Không suy ra latency production từ
  các số đo này.
- DB local đang ở trạng thái dev/rehearsal. Các sai lệch journal ở mục 4.1 là
  **trạng thái local đã xác minh**. Production có giống vậy không thì chưa kiểm tra.

## 3. Số đo hiện tại (HEAD `73651305`)

### 3.1. Preview và các endpoint đọc

| Phép đo (đường full, vì sparse bị từ chối) | Thời gian | SQL | Logical page reads |
|---|---:|---:|---:|
| Preview lần đầu, `limit=5` | 5,43 s | 188 | 716.302 |
| Trang 2 theo cursor, `limit=100` (lần gọi sau trong cùng request context) | 5,23 s | 17 | 715.659 |
| Lọc `type=field_def` (chỉ 7 dòng kết quả) | 5,23 s | 17 | 715.713 |
| Tìm kiếm `q` không khớp | 5,58 s | 17 | 715.510 |
| `GET /auto-publish` (chỉ để lấy `change_count`) | 5,00 s | 18 | 715.822 |
| Danh sách thay đổi release 1 (162k atoms), trang 1 | 0,026 s | — | — |
| Danh sách thay đổi release 1, có `q` | 0,51 s | — | quét 164.369 dòng PK |

Một lượt chạy dưới `cProfile` mất 9,5 giây (profiler làm chậm); lượt này chỉ dùng để
xem hàm nóng. Tách theo giai đoạn của đường full:

| Giai đoạn | Thời gian | Ghi chú |
|---|---:|---|
| Thử sparse rồi bị từ chối | 0,009 s | Preflight schema journal fail ở field `reading` |
| `reconstruct_release_state(head)` | 1,86 s | 597.152 page reads, tức **83 %** của cả preview |
| `_build_working_state` | 1,91 s | SQL 0,43 s; còn lại là ORM + adapter tên field |
| `_build_atomic_diff` (gồm hash) | 1,19 s | 182.560 lần `_hash_value` |
| Template presentations | 0,017 s | Không đáng kể |

### 3.2. Publish (probe sau sửa, dựng + flush, không commit)

| Giai đoạn | Thời gian |
|---|---:|
| Dựng diff plan | 5,59 s |
| Manifest hash + dựng change rows | ~1,0 s |
| `add_release_changes` (189 INSERT, 91.281 dòng, 13,4 MB JSON before/after) | 13,86 s (cursor 12,83 s) |
| `_sync_memberships` | 0,46 s |
| `clear_dirty_entities` (1 DELETE, 81.218 dòng) | 4,32 s |
| **Tổng tới khi staged** | **25,9 s** |
| Rollback sau đo (thay cho commit) | 6,5 s |

Toàn bộ khoảng này nằm sau `SELECT … FOR UPDATE` trên dòng `deck_marketplace_items`
(`deck_release_service.py:1802-1806`).

## 4. Các điểm chưa tối ưu

### 4.1. Journal bỏ sót và lỗi thời → fallback full, nguy cơ phát hành thiếu

**Bằng chứng** (`output/journal_gap_probe.py`, `untracked_sample_probe.py`):

- Full diff có 91.281 thay đổi, journal có 81.218 dòng.
- **20.224 thay đổi không có trong journal**: `word_audio` 10.072, `example_audio`
  10.072, `image` 77, cộng 3 template presentation. Template được tính riêng, không
  đi qua journal, nên 3 dòng này là bình thường. Mẫu note-field:
  `"[sound:0b7c…3.mp3]"` → `"/media/proxy/c3c9…"`, `"b450…c3ff.jpg"` →
  `"/media/proxy/d706…"`. Cả 10.072 note được cập nhật trong khoảng
  2026-10-25 14:29:52–14:32:10 và không có `audit_logs` tương ứng.
- **10.161 dòng journal không còn tạo thay đổi thực**: 10.145 dòng `reading`, vài
  field khác, và 1 dòng schema. Dòng schema `field_type` của `reading` giữ hash của
  `array` (revision 81, 2026-10-11), trong khi field hiện tại là `text`
  (`field_defs.updated_at` = 2026-10-25 23:29:49). Cùng đợt đó có hàng loạt
  `field_defs` của note type khác được cập nhật lúc 23:28:48. Không có audit log nào
  sau 15:37:45 ngày hôm đó.

**Nguyên nhân đã xác định trong code:**

- `flashcard_media_normalizer.py:116-125` gán `semantic_change=False` cho decision
  `resolved_reference`, tức là đổi tham chiếu sang `/media/proxy/<id>`.
  `:384-391` và `:480-481` chỉ ghi journal cho field có semantic change. Kết quả là
  `notes.field_values` thay đổi mà không có dirty row. Hành vi này khớp với dữ liệu
  quan sát. Tuy vậy, chưa xác nhận được chính lần chạy nào lúc 14:29, vì không có
  bảng hay audit lưu run.
- Writer đổi `reading` về `text` chưa được xác định. Đó không phải
  `field_array_conversion_service`: service này ghi journal sau khi đổi type
  (`:155-163`). Dấu vết cho thấy một script hoặc thao tác ngoài luồng.

**Tác động:**

- Một dòng journal lỗi thời làm `_schema_journal_matches_working_state` trả `False`
  (`deck_release_service.py:1032-1035`). Mọi preview, publish và auto-publish status
  sau đó đều chạy full diff, cho tới khi có một lần publish thành công xóa journal.
- Tính chất fail-closed chỉ bao được các entity **có trong journal**. Thay đổi không
  được ghi journal thì sparse không có cách nào thấy. Nếu dòng schema tình cờ khớp,
  release sẽ thiếu 20.221 thay đổi media. Release còn **phụ thuộc vào đường chạy**:
  cùng trạng thái nguồn, đường full có những thay đổi này còn đường sparse thì không.
- 22 % số atoms của release N1 (20.221/91.281) là các thay đổi media không được ghi
  journal. Chúng góp thẳng vào chi phí INSERT ở mục 4.6.

**Đề xuất (sửa từ nguồn, không thêm lớp guard):**

1. Thống nhất một định nghĩa: thay đổi giá trị nào làm full diff thấy khác thì writer
   đó phải ghi journal. Với media normalizer, cách nhất quán là gọi
   `mark_note_field_batches_changed` cho mọi field thực sự đổi giá trị, không chỉ
   field semantic. Nếu muốn coi việc đổi media ref là không thay đổi nội dung, thì
   full diff cũng phải coi hai biểu diễn là tương đương. Đây là quyết định sản phẩm
   (người học có cần nhận đường dẫn `/media/proxy` mới hay không).
2. Các script ngoài luồng (rollback/restore/migration dữ liệu) chạm vào note hoặc
   field của deck đã phát hành phải dùng helper journal. Nếu không thể, script phải
   tăng `working_revision` và để `dirty_tracking_revision` lùi lại, đúng như
   `mark_note_field_batches_changed` làm với lineage chỉ có tên
   (`deck_working_tree_service.py:400-403`). Khi đó hệ thống biết trước sẽ fallback
   một lần, đồng thời cursor và `expected_working_revision` cũng nhận ra thay đổi.
3. Giữ `journal_gap_probe.py` làm công cụ chẩn đoán chạy tay trước khi phát hành
   lớn hoặc sau script dữ liệu, không đưa vào runtime. Nên có thêm một regression
   test MySQL kiểm tra media normalizer ghi journal đúng.
4. Kiểm tra cùng điều kiện trên production bằng principal chỉ-SELECT trước khi kết
   luận #253 trên production có cùng nguyên nhân fallback.

### 4.2. Publish đồng bộ, dài và giữ khóa

**Hiện trạng:** `POST /releases` dựng lại diff (không dùng lại preview), ghi atoms,
xóa journal, ghi pins, rồi mới commit, tất cả trong một request
(`deck_releases.py:84-142`, `deck_release_service.py:1883-1976`).

**Tác động:**

- Chuỗi timeout trên production: nginx `location /` không đặt `proxy_read_timeout`
  (`deploy/flama.nginx.conf:61`), nên dùng mặc định 60 giây. Phía trên là Cloudflare
  (mặc định 100 giây); Gunicorn `--timeout 120` (`deploy/flama.service:13`). Local đo
  được 26 giây khi có 1 GiB buffer pool và chưa tính commit. Trên VPS với buffer pool
  nhỏ hơn, biên an toàn so với 60 giây chưa được đo.
- Khóa `FOR UPDATE` trên listing giữ suốt quá trình publish. Mọi lần owner sửa note
  hay field trong deck đó (writer cập nhật `working_revision` của cùng dòng) sẽ chờ
  khóa. `innodb_lock_wait_timeout` local là 50 giây, nên import hoặc chỉnh sửa song
  song có thể lỗi lock wait nếu publish chậm hơn.
- Phần dựng diff tốn CPU Python khoảng 5–6 giây. Trên worker `gthread`
  (2 workers × 4 threads), phần này giữ GIL và làm chậm các request khác chạy cùng
  process.
- Khi request bị proxy cắt, backend vẫn có thể commit. Frontend chỉ giữ
  idempotency key trong `useRef` của lần mount (`useReleaseBuilder.ts:38`). Tải lại
  trang tạo key mới, nên lần thử lại không replay mà nhận `RELEASE_HEAD_STALE`.

**Đề xuất:** xem 4.6 (giảm phần ghi), 4.3 (frontend) và mục 5 (điều kiện chuyển sang
job nền). `DeckRelease.status` đã có trạng thái `building`, phù hợp làm trạng thái
của job nếu sau này cần.

### 4.3. Frontend vẫn coi lỗi release là bảo trì toàn hệ thống

- `getReleasePreview`, `createDeckRelease`, `getAutoPublishStatus`
  (`features/deck-collaboration/api.ts:245`, `:282`, `:297`) không truyền
  `reportUnavailable: false`. Khi gặp 502/503/504/521–524 hoặc lỗi mạng,
  `shared/api/client.ts:169-196` gọi `reportBackendUnavailable()`, chuyển cả ứng dụng
  sang `/maintenance` (`shared/api/backendAvailability.ts:5`).
- `main.tsx:14-16` đặt `retry: 1` cho mọi query. Một preview bị cắt ở 60 giây sẽ
  được gửi lại một lần nữa, nhân đôi khối lượng diff nặng trên server.

**Đề xuất (chỉ frontend, rẻ):** truyền `reportUnavailable: false` cho ba lời gọi trên
và hiển thị lỗi ngay trong màn release. Sau khi POST lỗi mạng hoặc timeout, tải lại
danh sách release và head để đối chiếu trước khi cho bấm lại. Lưu idempotency key
theo `(itemId, base_release_id, working_revision)` vào `sessionStorage` để lần thử
lại sau khi reload vẫn replay được. Đặt `retry: 0` cho preview.

### 4.4. Preview dựng lại toàn bộ diff ở mỗi request

`preview_release` gọi `_build_release_diff_plan` rồi mới lọc và cắt trang
(`deck_release_service.py:1450-1475`). Mỗi trang, mỗi lần đổi loại thay đổi, mỗi lần
tìm kiếm (`queryKey` chứa `filters`, xem `useReleaseBuilder.ts:41`) đều tốn lại
~5,2–5,6 giây và ~716 nghìn page reads. Kết quả không đổi, vì `working_revision` và
head vẫn như cũ. Bước tìm kiếm còn `json.dumps` before/after cho từng thay đổi
(`:1394-1402`), tốn thêm khoảng 0,35 giây.

**Đề xuất:** làm 4.5, 4.7 và 4.8 trước để hạ chi phí mỗi lần dựng. Chỉ khi vẫn chậm
mới thêm cache trong process, khóa theo `(item_id, working_revision, head_id)`, có TTL
và giới hạn kích thước. Bộ nhớ của 91 nghìn change dict chưa được đo. Writer ngoài
luồng không tăng `working_revision` sẽ làm cache sai, thêm một lý do để làm 4.1 trước.

### 4.5. Auto-publish status dựng cả preview chỉ để đếm

`get_auto_publish_status` gọi `preview_release(limit=1)` khi
`working_revision > head.source_working_revision`
(`deck_auto_publish_service.py:52-66`). `SharedDeckDetailPage.tsx:210-214` gọi
endpoint này mỗi khi owner mở trang deck, kể cả khi auto-publish đang tắt (N1 đang
tắt). Đo được 5,0 giây. Lỗi bị nuốt và trả về 0.

**Đề xuất:** trả `has_unreleased_changes` từ so sánh revision (miễn phí), hoặc đếm
dirty rows bằng SQL (`working_revision > base`, 0,148 giây và dùng index
`ix_deck_working_dirty_publish` sẵn có) làm con số ước lượng. Số chính xác để màn
release tự tính.

### 4.6. Ghi release: INSERT atoms và DELETE journal

- **INSERT** (13,9 giây cho 91.281 dòng, khoảng 0,14 ms/dòng ở server, đã batch 500
  từ #253). Mỗi dòng phải cập nhật PK cùng 5 secondary index của
  `deck_release_changes` (`uq_…_release_key`, `ix_…_diff_cursor`,
  `ix_…_entity_history`, 2 index FK), và kiểm tra JSON before/after (13,4 MB).
  Đòn bẩy không cần schema: giảm số atoms thừa (mục 4.1, 22 % ở N1) hoặc đưa công
  việc ra khỏi request. Mọi hướng thay đổi index đều phải đi theo quy trình đề xuất
  có `EXPLAIN` và số đo ghi trong `AGENTS.md`. Báo cáo này **không** đề xuất đổi index.
- **DELETE journal** (4,3 giây, `deck_working_tree_service.py:580-583`) chạy trong
  transaction đang giữ khóa, tạo undo lớn (rollback sau đo mất 6,5 giây). Journal chỉ
  hợp lệ trong khoảng `base_revision < working_revision ≤ current`
  (`deck_release_service.py:970-976`). Vì vậy có thể lọc theo revision ngay trong SQL
  khi nạp journal (dùng index `ix_deck_working_dirty_publish` có sẵn), bỏ DELETE khỏi
  đường publish và dọn dòng cũ theo lô sau commit. Upsert theo unique key sẽ tự tái
  sử dụng dòng cũ. Cần sửa đồng bộ `_schema_journal_matches_working_state`, nhánh
  `working_revision == base` và test.

### 4.7. Truy vấn lịch sử khi tái dựng vẫn duyệt toàn bộ atoms baseline

`reconstruct_release_state` nạp lịch sử **trước** checkpoint (`:358-374`). Bộ lọc
`after_checkpoints` là outer join với bảng dẫn xuất GROUP BY
(`deck_release_repository.py:232-242`). `EXPLAIN ANALYZE`: nested loop xử lý
162.680 dòng, mỗi dòng probe bảng dẫn xuất, rồi mới lọc còn 312 dòng; mất 0,73 giây
ở server, khoảng 1,2 giây phía client, và chiếm 83 % page reads của preview. Loader
theo nhóm (`:365-384`) đã có kỹ thuật chặn `DeckRelease.sequence_no > earliest`, nhưng
đường tái dựng toàn deck chưa dùng.

**Đề xuất:** đọc checkpoint trước, lấy sequence checkpoint nhỏ nhất của các note đã
checkpoint, chặn join release theo sequence đó. Note chưa có checkpoint vẫn nạp đủ
lịch sử bằng truy vấn riêng. Không cần index mới. Kiểm chứng bằng SHA-256 của state
như #253 (`46221fe2…`).

### 4.8. Đọc note qua adapter tên field rồi đổi ngược lại ID

`_build_working_state` (`:292-298`) và sparse (`:1117-1122`) đọc `note.field_values`.
Adapter `read_note_named_values` kiểm tra schema/clone scope, deep-copy, xác thực
identity, rồi code release lại đổi tên về ID. Đo trên 10.148 note: **adapter
1,133 giây so với 0,030 giây khi đọc thẳng `field_values_by_id`**. Profiler còn ghi
thêm 170 truy vấn `deck_clone_deck_maps` theo từng deck (N+1, ~0,1 giây), tất cả trả
0 dòng, cùng việc hydrate đủ 11 cột ORM của `Note`.

**Đề xuất:** viết một reader riêng cho source note của owner, trả về giá trị theo
Field ID đã lọc theo field hiện tại của source note type. Fallback về adapter khi
codec khác `field-id.v1` hoặc có `field_values_extras`. Vẫn giữ `raw_field_values`
theo tên cho checkpoint đầu tiên. Cần test parity state, gồm các trường hợp lỗi mà
adapter đang chặn (va chạm nhãn).

### 4.9. Hash và JSON không cần cho preview

`_change_descriptor` tính `before_hash`/`after_hash` cho mọi thay đổi (`:795-796`):
182.560 lần SHA-256 + `json.dumps` cho mỗi preview, tốn 1,18 giây trong profiler
(thực tế ước khoảng 0,6 giây). Preview chỉ trả tối đa 100 item. **Đề xuất:** chỉ tính
hash cho item trong trang, hoặc tính lười khi publish. Manifest hash (0,63 giây) chỉ
cần ở publish.

### 4.10. Đường sparse không rẻ hơn khi thay đổi gần như toàn deck

Nếu journal của N1 hợp lệ, các phần của đường sparse đo riêng là: nạp 81.218 dirty
rows qua ORM 2,36 giây; giá trị base cho 10.148 note 1,72 giây; note hiện tại 0,57
giây; adapter 1,13 giây. Tổng **≥ 5,8 giây trước khi diff**, không nhanh hơn đường
full (5,2 giây). **Đề xuất:** nạp journal bằng Core tuple thay vì ORM, lọc revision
trong SQL (4.6), đọc theo ID (4.8). Chưa đo hiệu quả của Core tuple.

### 4.11. Auto-publish chạy đồng bộ trong mọi request ghi

`_trigger_auto_publish_for_items` (`deck_working_tree_service.py:235-244`) được gọi
sau **mỗi** lần gọi helper journal. Writer theo lô như
`anki_content_normalizer.py:576-580` ghi journal sau mỗi 250 note. Với deck bật
auto-publish, một request có thể tạo nhiều release, và mỗi release lại chạy
`process_subscriber_auto_updates` cho mọi learner bật auto-update ngay trong request
của owner (`deck_auto_publish_service.py:193-215`). Lỗi bị nuốt (`except Exception:
pass` và `except Exception` ở `:217-227`) mà không có savepoint. Nếu publish lỗi sau
khi đã INSERT atoms hoặc gán head, phần đã ghi dở vẫn nằm trong transaction mà
caller sẽ commit. Rủi ro này mới đọc từ code, **chưa có test tái hiện**. Local hiện
có 1/24 listing bật auto-publish và 1/30 install bật auto-update.

**Đề xuất:** gom các item cần auto-publish vào `session.info` rồi publish một lần
trong `before_commit`, giống mẫu `_publish_presentation_mutations` đã có
(`deck_working_tree_service.py:84-91`). Bọc mỗi lần publish trong `begin_nested()`.
Đưa cập nhật subscriber ra khỏi request của owner.

### 4.12. Điểm nhỏ

- `list_note_checkpoints` (10.148 dòng, 0,64 giây) và `list_memberships`
  (10.164 dòng, 0,21 giây) nạp đủ cột, trong khi tái dựng diff không dùng `tags`,
  `content_hash`, `created_at`. Đường full còn nạp lại toàn bộ memberships ở
  `_sync_memberships`.
- Tìm kiếm `q` trong danh sách thay đổi của release dùng `LIKE '%…%'` trên 3 cột, nên
  quét hết các dòng của release (0,51 giây với 162k atoms). Đây là API cho owner và
  learner xem release lớn.
- `get_atomic_changes_between_releases` không có caller nào trong `app/` (chỉ test
  dùng). Hàm này nạp đủ cột của mọi atom giữa hai release, nên đừng dùng nó cho
  luồng runtime mới.

## 5. Lộ trình đề xuất

Phù hợp ràng buộc ngân sách: không bảng/cột/index mới; ưu tiên sửa nguồn gốc.

| Đợt | Việc | Lợi ích ước tính (N1, từ số đo thành phần) | Chi phí/rủi ro |
|---|---|---|---|
| 1 | 4.1: media normalizer ghi journal; quy ước cho script ngoài luồng; kiểm tra production | Đường sparse dùng được lại; release không còn phụ thuộc đường chạy | Thấp; cần quyết định sản phẩm về media ref |
| 1 | 4.3: lỗi release hiển thị tại chỗ, idempotency key bền, `retry: 0` | Hết màn bảo trì giả; retry an toàn | Thấp, chỉ frontend |
| 1 | 4.5: status không gọi preview | −5 giây mỗi lần owner mở trang deck | Thấp |
| 2 | 4.7 + 4.8 + 4.9 | Preview full: khoảng −1,2 s, −1,1 s, −0,6 s; −580k page reads | Trung bình; cần test parity SHA |
| 2 | 4.6: bỏ DELETE journal khỏi đường publish | −4,3 giây trong vùng giữ khóa, undo nhỏ hơn | Trung bình; cần test sparse/fallback |
| 2 | 4.10, 4.11 | Sparse rẻ hơn; tối đa một auto-publish mỗi transaction | Trung bình |
| 3 | Job nền cho release lớn; cache preview (4.4) | Thoát khỏi giới hạn timeout | Cao. Kế hoạch UX hiện tại ghi rõ không dựng job system mới cho luồng một Deck |

**Điều kiện mở đợt 3:** sau đợt 1–2, publish trên production (đo bằng log server)
vẫn gần 60 giây ở p95, hoặc vẫn còn 504 hay lock wait timeout khi phát hành.

## 6. Chưa làm / chưa xác minh

- Chưa đo trên production và chưa có HTTP log của lần lỗi #253.
- Chưa xác định writer đổi `reading` về `text` (2026-10-25 23:29:49). Lần chạy
  media normalizer lúc 14:29–14:32 mới suy ra từ hành vi code và dấu thời gian.
- Chưa chạy lại publish probe; số liệu 3.2 là của phiên trước, sau bản sửa.
- Chưa đo chi phí cập nhật phía learner (`deck_install_rebase_service.prepare_update`)
  sau một release 91 nghìn atoms.
- Mọi lợi ích ở mục 5 là ước tính từ số đo từng thành phần, chưa đo end-to-end.
