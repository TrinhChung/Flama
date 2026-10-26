# Issue #253 — Điều tra phát hành bộ Tettei N1

Ngày báo cáo: 2026-10-26 (Asia/Tokyo). Issue: <https://github.com/TrinhChung/Flama/issues/253>.
Baseline code: `4863b860a05865fd88893cdcb4392512cd4ab143`.

**Cập nhật sau triển khai:** đã sửa trong checkout local, chưa deploy production.
Preview N1 đo lại còn 6,715 giây; dựng và flush release còn khoảng 25,9 giây
(không commit dữ liệu N1). Chi tiết thay đổi và kiểm chứng ở mục cuối báo cáo.

## Kết luận cho quản lý

Đã xác nhận luồng preview/phát hành đồng bộ xử lý quá nhiều dữ liệu trên bộ
Tettei N1. Preview local mất 42,4 giây; dựng và flush một release thử mất khoảng
136 giây, chưa tính commit. Có 91.281 thay đổi và 91.287 câu INSERT được thực thi.

Ngoài khối lượng thay đổi lớn, journal của field `reading` còn giữ hash của kiểu
`array`, trong khi field hiện tại là `text`. Bộ so sánh phát hiện sai lệch sau khi
đã đọc dữ liệu để so sánh nhanh, rồi dựng lại toàn bộ lịch sử deck.

Đây là bằng chứng mạnh cho giả thuyết request vượt thời gian chờ của tầng proxy
hoặc kết nối. Chưa có HTTP status, HAR hoặc log của lần lỗi được báo cáo, nên
chưa xác nhận chính xác request GET preview hay POST publish bị ngắt, tầng nào
ngắt, hoặc mốc timeout đang áp dụng. Không kết luận hệ thống thực sự đang bảo trì.

Frontend hiện chuyển toàn ứng dụng sang `/maintenance` khi API gặp lỗi mạng hoặc
status 502/503/504/521/522/523/524. Vì vậy một request release thất bại cũng có
thể tạo đúng màn hình người dùng mô tả.

## Phạm vi và dữ liệu đã xác minh

- Người dùng xác nhận: mở bộ Tettei N1 10.000 từ, bấm phát hành bản mới, chờ rồi
  thấy thông báo server đang bảo trì.
- DB local: MySQL 8.0.40, database `nihongo`, kết nối localhost.
- Listing: `97b15098-89db-4afe-a11d-034cad593fe6`,
  `JLPT N1 語彙徹底 – 10,000語`, source deck `415`, owner user ID `1`.
- Không có username đúng bằng `user1`; listing phù hợp thuộc user ID 1.
- Có 10.148 source note; head là release `1.0.1`, sequence 2,
  `b6c457ec-0748-4024-b717-c1f046516b08`.
- Working revision và dirty tracking revision đều bằng 121; head giữ revision 80.
- Có 81.218 dirty entity rows. So sánh đầy đủ tạo 91.281 thay đổi:
  71.036 note-field từ chuỗi sang list, 20.235 note-field chuỗi sang chuỗi,
  7 thay đổi kiểu field và 3 template presentation additions.
- List là dữ liệu native hợp lệ của Flama; không phải lỗi kiểu dữ liệu cần ép về chuỗi.

## Đường đi và điểm nghẽn

1. `DeckDetailOwnerBar.tsx` dẫn tới `/creator/decks/:id/releases/new`.
   `useReleaseBuilder.ts` tải GET `/api/marketplace/decks/:id/releases/preview`.
   Khi submit, POST `/api/marketplace/decks/:id/releases` dựng lại diff trong
   cùng request trước khi commit.
2. `_try_build_sparse_diff()` đọc journal, memberships, lịch sử và note hiện tại.
   Lần đo publish mất 21,638 giây trước khi trả về `None`.
3. Field `reading` (`cfe0d506-f625-4db3-b249-960126870f51`) có journal revision 81,
   hash `9b2a3448…` = hash của `array`; giá trị thực tế là `text`, hash `1e1d0f25…`.
   Trace xác định nhánh return tại `deck_release_service.py:1116`.
   Chưa xác định writer/lần sửa tạo sai lệch; không có audit tương ứng trong
   khoảng đã kiểm tra. Không quy trách nhiệm cho một API hoặc migration cụ thể.
4. `_build_content_release_diff_plan()` fallback sang
   `reconstruct_release_state()` và `_build_working_state()`, rồi so sánh đầy đủ.
   Riêng reconstruct mất 9,253 giây; tổng dựng diff mất 34,617 giây.
5. `add_release_changes()` đưa toàn bộ 91.281 ORM rows vào session bằng `add_all`.
   Query đầu của `_sync_memberships()` kích hoạt autoflush. Khoảng này mất
   86,561 giây; không được diễn giải toàn bộ thời gian đó là query memberships.
   Bộ đếm ghi nhận 91.287 INSERT statements cho cả lần publish.
6. Preview tính toàn bộ diff và summary trước khi cắt trang; `limit=5` chỉ giảm
   response, không giới hạn công việc dựng diff.

Nguồn code: `app/services/deck_release_service.py`,
`app/repositories/deck_release_repository.py`,
`app/api/v1/marketplace/deck_releases.py`,
`frontend/src/features/deck-collaboration/{api.ts,hooks/useReleaseBuilder.ts}`,
`frontend/src/shared/api/{client.ts,backendAvailability.ts}`, `frontend/src/App.tsx`.

## Phép đo local

| Phép đo | Kết quả |
|---|---:|
| Kiểm tra điều kiện listing | Đạt, 1,064 giây |
| Preview, chỉ đọc, limit 5 | 42,4 giây; 301 SQL statements |
| Preview: chênh lệch logical page reads | 11.259.654 |
| Preview: chênh lệch disk page reads | 10.710 |
| Dựng và flush release, không commit | Khoảng 136 giây |
| Publish probe SQL | 343 SELECT; 91.287 INSERT; 6 UPDATE; 1 DELETE; 2 SHOW |
| Thời gian cursor của INSERT | 65,660 giây |
| Thời gian cursor của DELETE journal | 8,706 giây |
| Publish: chênh lệch logical/disk page reads | 31.022.837 / 2.863 |

Đây là các lượt đo chẩn đoán, không phải benchmark production. Publish có
instrumentation và một probe read-only chạy đồng thời trong một phần giai đoạn
ghi; các counter buffer pool là global nên có thể gồm workload khác. Thời gian
SQL cursor không gồm toàn bộ thời gian fetch, ORM và xử lý Python.

Runtime buffer pool là 1 GiB, 8 instances, chunk 128 MiB; `my.ini` cấu hình 128M,
persisted variables không có override buffer pool. Không đổi cấu hình hoặc
restart MySQL. Không suy rộng các số đo này thành hiệu năng ở runtime 128M.

## Kiểm chứng rollback và giới hạn

Probe gọi `publish_release()` trong transaction local, chặn commit bằng event,
chặn DDL, rồi rollback trong `finally`. Không gọi API publish để commit thật.

Sau rollback và một lần đọc kiểm tra độc lập: vẫn 2 release, không có release
chưa published, không có diagnostic release; head, working revision, dirty
tracking revision và 81.218 dirty rows giữ nguyên. Không sửa code ứng dụng,
migration, index hoặc cấu hình. Rollback có thể để lại khoảng trống auto-increment.

Artifacts chẩn đoán local (trong `output/`, không thuộc bản sửa ứng dụng):
`issue253_publish_probe.py`, `issue253_publish_probe.jsonl`,
`issue253_sparse_fallback.json`. Không tự chạy lại probe trên production.

Chưa kiểm chứng trạng thái dữ liệu production sau lần lỗi ban đầu. Một gateway
timeout không tự chứng minh transaction backend đã rollback hoặc đã commit;
cần đối chiếu head/idempotency và log trước khi khẳng định kết quả phát hành.

## Hướng xử lý tiếp theo

1. Lấy Network status/timing và log cùng thời điểm trên môi trường xảy ra lỗi,
   phân biệt GET preview với POST publish; đối chiếu release head và request key.
2. Tối ưu ghi release theo batch, giữ nguyên transaction, idempotency và release
   bất biến. Đo lại cả chi phí ghi và preview với fixture nhiều thay đổi.
3. Kiểm tra writer tạo journal lệch hash; kiểm tra tính hợp lệ rẻ trước các bước
   tái dựng lịch sử đắt tiền. Không bỏ kiểm tra hash hoặc sửa trực tiếp journal
   chỉ để ép chạy nhanh.
4. Đánh giá background job có trạng thái tiến độ cho release lớn; giữ nguyên
   cơ chế chỉ công bố head sau khi hoàn tất thành công.
5. Cho lỗi release/timeout hiển thị tại workflow phù hợp; tránh diễn giải một
   request lỗi thành thông báo bảo trì toàn hệ thống.

Tại thời điểm điều tra ban đầu chưa triển khai bản sửa. Kết quả triển khai local
được cập nhật ở cuối báo cáo. Không thêm index hoặc tăng buffer pool.

## Điều tra bổ sung: vì sao 91 nghìn thay đổi lại lâu

Số lượng là 91.281 **change rows**, trên 10.148 note. Thời gian lớn xuất phát từ
cách thực hiện thao tác, không thể suy ra chỉ từ số lượng note.

### Ghi từng dòng vì cần ID cho ORM object

`add_release_changes()` dùng `Session.add_all()` với các object có khóa chính
auto-increment chưa có giá trị. SQLAlchemy 2.0.48/MySQL dialect tại máy này có
`insert_returning=False`, `insert_executemany_returning=False` và
`use_insertmanyvalues_wo_returning=False`. Đường flush ORM thực thi từng INSERT,
lấy primary key rồi gắn lại cho từng object; `add_all()` không đồng nghĩa với
một multi-row INSERT ở đây.

Đã đối chứng cùng 2.000 historical note-field rows lấy từ N1 release 1.0.0,
trên chính bảng hiện tại, giữ nguyên index/constraint, mỗi lượt tạo release
`building` tạm rồi rollback. Thứ tự ORM → batch → batch → ORM:

| Cách ghi | Số INSERT phía server | Tổng thời gian | Thời gian INSERT phía MySQL |
|---|---:|---:|---:|
| ORM add_all, lượt 1 | 2.000 | 1,6240 giây | 0,810449 giây |
| Core batch 500, lượt 1 | 4 | 0,2331 giây | 0,176511 giây |
| Core batch 500, lượt 2 | 4 | 0,2041 giây | 0,148962 giây |
| ORM add_all, lượt 2 | 2.000 | 1,4004 giây | 0,728041 giây |

Thời gian phía MySQL lấy từ bộ đếm per-thread trong
`performance_schema.events_statements_summary_by_thread_by_event_name`, không
đánh đồng với thời gian cursor phía Python. Bình quân batch nhanh hơn khoảng
6,9 lần về tổng thời gian và 4,7 lần về thời gian INSERT trong server. Giảm số
lần gọi giúp giảm cả xử lý statement phía server và chi phí driver/giao tiếp.

Trong full publish probe ban đầu, tổng 65,66 giây cursor INSERT chia cho 91.287
câu chỉ khoảng 0,72 ms/câu; từng câu không nhất thiết chậm, nhưng tổng số lần
thực thi tuần tự quá lớn. Đây là một transaction, không phải commit từng dòng.
Chưa đo trọn bộ 91.281 change rows bằng cách batch; không ngoại suy thời gian
hoàn tất release từ mẫu 2.000 dòng, vì payload và các bước còn lại khác nhau.

### Query lịch sử đọc rộng lặp lại theo từng nhóm

`_get_note_field_values_by_id_for_ids_at_release()` chia IDs thành nhóm 500 và
gọi `list_note_field_history_for_ids()` cho từng nhóm.

`EXPLAIN ANALYZE` chỉ đọc trên nhóm đầu 500 active note IDs cho thấy:

- MySQL chọn index hiện có `ix_deck_release_changes_diff_cursor`, lookup theo
  `(release_id, entity_kind)`, rồi mới lọc `entity_id IN (...)`.
- Lookup có trung bình 81.300 rows mỗi loop, 2 loops: khoảng 162.600 dòng lịch
  sử được xét cho một nhóm 500 note; kết quả chỉ còn 8.012 dòng.
- Thời gian toàn query mẫu khoảng 423 ms tại server, chưa có fetch/decode/ORM.
- Ước lượng ở lookup chỉ 405 rows trong khi thực tế 81.300 rows/loop. Chưa xác
  định nguyên nhân chênh lệch là statistics hay phân bố dữ liệu; chưa chạy
  `ANALYZE TABLE` hoặc thay đổi cấu hình/index.

Với 10.148 note, vòng lặp có 21 nhóm. Khi mỗi nhóm dùng cách đọc rộng trên,
khối lượng xét lịch sử tăng lên khoảng 3,4 triệu lượt dòng, trước khi fallback
lại đọc toàn bộ lịch sử. Giới hạn nhóm 500 không bảo đảm chỉ đọc 500 note ở tầng
access path. Đây là điểm cần sửa scope/query và kiểm tra kế hoạch thực thi.

Artifacts bổ sung: `output/issue253_write_comparison.py`,
`output/issue253_write_comparison.json`, `output/issue253_history_explain.txt`.
Các phép đo bổ sung chạy tuần tự, không dùng probe tracing song song. Đã xác
nhận toàn bộ release thử rollback; release head/count và dirty journal giữ nguyên.

## Audit bổ sung: dữ liệu đọc thừa và nhánh legacy

Đã trace một request preview thực tế ở service, có request context và transaction
MySQL read-only. Kết quả: 32,675 giây, 300 SQL statements và 478.063 lượt dòng
trả về client DB (bao gồm các lần đọc lại), để trả 5 dòng preview cùng summary.

### 1. Đọc atoms đã được checkpoint bao phủ — đã xác minh bằng đối chứng

Release 1 có 10.148 checkpoint và 162.368 note-field atoms. Tại head release 2,
checkpoint đã bao phủ toàn bộ 162.368 atoms này; chỉ 232 note-field atoms sau
checkpoint cần replay. Tuy vậy:

- Nhánh sparse tải cả 162.600 note-field history rows, rồi bỏ atoms cũ trong
  Python. Loader này có 21 lần gọi, tổng 13,347 giây trong lượt audit.
- Sau khi hash không khớp, nhánh full lại tải 162.680 history rows gồm 80 field
  schema atoms và 162.600 note-field atoms; tiếp tục bỏ 162.368 note atoms cũ.
- Tổng cộng 324.736 lượt history rows được tải trong hai nhánh rồi không replay.
  Đây là over-fetch của truy vấn tái dựng, không phải lý do xóa lịch sử release.

Probe chỉ đọc thay riêng loader SQL trong tiến trình chẩn đoán bằng điều kiện
loại note atoms có sequence không mới hơn checkpoint gần nhất của từng note.
Giữ nguyên service tái dựng và toàn bộ dữ liệu DB:

| Tái dựng cùng head release 2 | Loader hiện tại | Loader loại atoms đã checkpoint |
|---|---:|---:|
| History rows trả về | 162.680 | 312 = 80 schema + 232 note |
| Thời gian | 8,687 giây | 1,535 giây |
| Note / field trong kết quả | 10.148 / 16 | 10.148 / 16 |

SHA-256 của toàn bộ dataclass state, bao gồm values, schema và metadata note,
khớp hoàn toàn: `46221fe20b6debddb6491c106eeab0e98398edcb0141f7d2c92ee70aa91815fe`.
Chưa áp dụng thay đổi loader vào code ứng dụng. Chưa đo end-to-end sau sửa.

Nguồn: `deck_release_service.py:342`, `:580`, các vòng lặp bỏ qua history dựa
trên `checkpoint_sequence`, và `deck_release_repository.py:181`, `:295`.

### 2. Full reconstruction tải nhiều cột không dùng

`list_release_history_changes(content_only=False)` trả đủ 17 mapped columns
cho 162.680 rows. Riêng 5 cột không được nhánh tái dựng state sử dụng có tổng
độ dài nội dung như sau:

| Cột | Byte nội dung tại DB |
|---|---:|
| change_key | 13.662.848 |
| sort_key | 17.404.568 |
| before_hash | 14.848 |
| after_hash | 10.411.520 |
| before_value | 661.757 |
| Tổng | 42.155.541 (~42,16 MB) |

Đây là tổng `OCTET_LENGTH` của các giá trị, không phải phép đo chính xác wire
bytes hoặc memory footprint, và không cộng riêng với số liệu over-fetch rows
để tránh tính trùng. Ngoài các cột này, release_id, request-item reference và
created_at cũng không phục vụ vòng tái dựng state hiện tại.

Loader dirty journal tải đủ 14 columns cho 81.218 rows, bao gồm base_hash,
metadata_json và timestamps không được `_try_build_sparse_diff()` sử dụng.
Note loaders cũng tải tags/timestamps/content_revision dù một số thuộc tính
không đi vào diff republish. Các hàm này có consumer khác, gồm initial checkpoint;
projection cần theo đúng consumer và giữ source_deck_id cho note thiếu checkpoint.

### 3. Đi vòng qua adapter tên field và đọc lại cùng note

10.148 live note đều dùng codec `field-id.v1`. Không có extra field hoặc retained
field ID ngoài schema hiện tại trong bộ này. Tuy nhiên sparse và full cùng đọc
10.148 note, tổng 20.296 lượt; mỗi lượt gọi `Note.field_values` để đổi ID sang tên,
deep-copy values, rồi code release đổi tên trở lại ID.

Adapter này còn kiểm tra clone scope: trace có 20.296 lần gọi helper và 170 SQL
lookup `deck_clone_deck_maps`, tất cả trả 0 dòng. Tổng cursor time các lookup
chỉ 0,0608 giây tại local: đây là công việc thừa trong owned-source scope đã đo,
nhưng không phải điểm nghẽn chính so với history. Historical checkpoint vẫn lưu
theo tên field; việc giải mã checkpoint phải giữ schema tại đúng release.

Nguồn: `deck_release_service.py:266`, `:961`,
`field_value_runtime_service.py:44`, `:89`, `:157`.

### 4. Chọn sample cũng đọc toàn bộ membership

`build_release_sample_cache_from_release(limit=5)` tải 10.148 note memberships
không có ID filter, lọc/sort trong Python để chọn 20 note, rồi tạo 5 samples.
Probe trên head hiện tại xác nhận 5 samples, 0,423 giây. Đây là over-fetch riêng
của bước sample cache, nhỏ hơn nhiều so với history, không phải thời gian của
toàn request publish. Nguồn: `marketplace_query_service.py:731`.

### Legacy nào thực sự được sử dụng

- Trace preview chỉ đọc 14 bảng: deck_clone_deck_maps, deck_marketplace_items,
  deck_release_changes, deck_release_entity_memberships,
  deck_release_note_checkpoints, deck_release_template_pins, deck_releases,
  deck_working_dirty_entities, decks, field_defs, note_types, notes,
  study_applications, templates. Không query Card/Progress/Review/Level/Topic/Lesson
  cũ trong request này.
- Live `notes` chỉ có store ID hiện tại; cột persisted `notes.field_values` không
  tồn tại. `checkpoint.field_values` là payload lịch sử hợp lệ, không phải một
  store live song song.
- 12 deck installs của listing đều `logical_overlay` và có applied release;
  không quan sát legacy full-copy hoặc install chưa pin trong dữ liệu listing.
- Head đã tồn tại nên nhánh initial-release `has_legacy_install_without_release()`
  không được gọi. Có note memberships đầy đủ nên nhánh compatibility thiếu
  membership cũng không phải đường chạy của N1.
- Publish template pin vẫn có guard provenance kiểm tra receipt legacy qua
  note_type_installs. Probe read-only trên cả 3 active template đều cho origin
  authored, không có source_template_id, không có legacy candidate install.
  Guard này kiểm tra quyền phân phối template; không tải cả kho note legacy.
- Source subtree gồm 171 deck, không có deck đã soft-delete hoặc owner khác
  trong tập đã đo. Không thấy dữ liệu ngoài subtree/owner trộn vào trường hợp N1.

Kết luận: có over-fetch lớn từ atoms lịch sử cũ đã checkpoint, projection quá
rộng và đọc lặp; chưa có bằng chứng luồng này kéo thêm kho legacy Card/Progress
hay bản clone full-copy. Điểm cần xử lý trước là lọc history theo checkpoint
ngay tại SQL, projection đúng consumer, rồi tránh đọc lại sau khi journal fail.

Artifacts bổ sung: `output/issue253_read_audit.py`, `issue253_read_audit.json`,
`issue253_checkpoint_parity.py`, `issue253_checkpoint_parity.json`,
`issue253_read_inventory.json`, `issue253_sample_scope.json` (đều trong output/).
Toàn bộ audit này chỉ đọc; release head vẫn là 1.0.1, 2 release, 81.218 dirty rows.

## Bản sửa local và kết quả kiểm chứng

Đã thay đổi:

- `app/repositories/deck_release_repository.py`: tùy chọn loại note atoms đã
  checkpoint trong truy vấn tái dựng; projection đủ cột phục vụ reconstruction;
  bound lịch sử theo checkpoint từng note và release sequence cho truy vấn
  theo nhóm; projection journal; SELECT note IDs có limit cho sample cache;
  INSERT change mappings theo batch 500 trong transaction do service sở hữu.
- `app/services/deck_release_service.py`: dùng truy vấn đã lọc; đọc checkpoint
  trước history; kiểm tra nhóm schema journal nhỏ trước khi tải note journal/
  lịch sử; tạo change mappings thay vì 91 nghìn ORM objects cần lastrowid.
- `app/services/marketplace_query_service.py`: chọn tối đa 20 IDs ở SQL khi tạo
  5 sample, giữ đúng visibility interval tại release đang dựng.
- `tests/test_deck_release_performance_mysql.py`: 4 regression tests opt-in
  (`FLAMA_MYSQL_TESTS=1`) trên MySQL loopback hiện có. Không DDL; fixture và
  service commits nằm trong SAVEPOINTs của một outer transaction luôn rollback.
  `scripts/run_tests.py` đưa file này vào module decks.

Các API history/diff giữ toàn bộ atoms; chỉ consumer tái dựng state lọc phần đã
nằm trong checkpoint. Giữ lịch sử null → initial cho receipt legacy và full
history cho note chưa có checkpoint. Không sửa data, schema, index, HTTP/CSRF,
frontend, cơ chế idempotency hay release pin của người học.

### Đo lại trên đúng N1, 10.148 note / 91.281 thay đổi

| Phép đo | Trước | Sau |
|---|---:|---:|
| Preview có request context | 32,675 giây | 6,715 giây |
| Preview SQL statements | 300 | 190 |
| Preview rows trả về DB client | 478.063 | 31.003 |
| Preview logical page reads delta | 11.677.086 | 716.269 |
| Preview disk page reads delta | 0 | 0 |
| Dựng và flush release, không commit | ~136,1 giây | ~25,9 giây |
| Tổng lượt cursor INSERT khi publish | 91.287 | 189 |
| Cursor INSERT time | 65,660 giây | 12,832 giây |
| Publish logical/disk page reads delta | 31.022.837 / 2.863 | 7.328.614 / 103 |

Số đo trước/sau là chẩn đoán local, không phải latency cam kết trên production.
Lượt publish trước có một probe tracing chạy đồng thời trong một phần giai đoạn
ghi, như đã ghi ở phần giới hạn. Cả hai giữ runtime buffer pool 1 GiB; mục tiêu
my.ini vẫn 128M và không thay đổi/restart để benchmark. Lượt publish không gồm
durable commit; rollback sau đo không được tính vào thời gian dựng release.

Kiểm tra độc lập sau sửa:

- SHA-256 toàn bộ head release state vẫn khớp baseline
  `46221fe20b6debddb6491c106eeab0e98398edcb0141f7d2c92ee70aa91815fe`.
- Đọc chọn toàn bộ 10.148 note tại head mất 1,597 giây; 21 history queries chỉ
  trả tổng 232 rows, thay cho 162.600 rows. Values theo Field ID khớp toàn bộ
  state tái dựng đầy đủ; logical/disk page reads delta là 163.652 / 0.
- Preview giữ summary 91.281 thay đổi, gồm 71.036 string → list, 20.235 string
  → string, 7 schema changes và 3 template additions.
- N1 publish probe đã dựng đủ change rows rồi rollback; head vẫn 1.0.1,
  2 releases, working/tracking revision 121 và 81.218 dirty journal rows.

### Tests

Chạy qua `scripts/run_tests.py`, tổng **60 passed, 1 skipped**:

- Release API: 13 passed.
- MySQL regressions mới: 4 passed — mixed/missing checkpoints, legacy baseline,
  nested arrays, schema journal preflight, lỗi batch thứ hai rollback sạch,
  retry/idempotency, sample limit và membership intervals.
- Template release/pins, clone và owner dirty tracking: 32 passed.
- Auto-publish và shared state: 11 passed; 1 test Redis integration được skip
  vì môi trường không cấu hình REDIS_URL.

Artifacts mới: `output/issue253_read_after.json`,
`issue253_publish_after.jsonl`, `issue253_after_parity.json`, và các manifests
`issue253-{release,mysql,related,auto-shared}-tests.json` trong output/.

Còn lại: phép đo production và kết quả HTTP thực tế sau deploy; quá trình đóng
gói release lớn vẫn đồng bộ. Adapter tên field chung vẫn được giữ để bảo toàn
ngữ nghĩa schema/overlay; lần đọc live note lặp do sparse fail đã được tránh.
