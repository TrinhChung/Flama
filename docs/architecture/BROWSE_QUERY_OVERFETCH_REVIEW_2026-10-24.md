# Browse: dữ liệu tải thừa và SQL còn có thể tối ưu

Ngày: 2026-10-24. Mốc review ban đầu: `83face76`. Phần khảo sát bên dưới ghi lại tình trạng tại mốc này; trạng thái triển khai mới nhất ở phần tiếp theo.

## Cập nhật triển khai

Đã xử lý **Q1, Q2, Q3, Q4, Q6, Q7, Q8**. Giữ API detail đầy đủ cho caller cũ; React Browse dùng `view=editor` để chỉ lấy dữ liệu editor cần. Không thay markup/CSS của màn Browse.

- **Q1:** selected deck hoàn toàn thuộc learner chỉ đọc subtree đó; cây mixed/foreign vẫn dùng resolver cũ. Detail đọc đúng tên deck; clone detail chỉ resolve installs có mapping phù hợp, giữ thứ tự ưu tiên và fallback install cũ.
- **Q2/Q3:** release readers chỉ SELECT các cột dựng content/schema cần; schema/history bất biến được dùng lại trong cùng request. Không thêm cache xuyên request.
- **Q4:** bỏ DISTINCT ở aggregate có duy nhất nhánh owned/admin; vẫn deduplicate khi có nhiều nhánh install.
- **Q6/Q8:** editor bỏ schema trùng và media metadata không dùng, không dựng live content rồi ghi đè cho clone; editor/TTS/SVG dùng chung detail cache key. API cũ vẫn trả payload đầy đủ.
- **Q7:** thêm index `notes(user_id, deck_id)` qua migration `20261024_000073`. Đã thử upgrade, downgrade, upgrade lặp trên schema MySQL tạm, sau đó upgrade DB local từ `20261020_000071` và xác minh index. DDL dùng `ALGORITHM=INPLACE, LOCK=NONE`, giới hạn chờ metadata lock 15 giây. Khi deploy cần chạy Alembic upgrade theo quy trình hiện hành.

**Q5 còn tồn tại:** search toàn collection nhiều installs vẫn chạm giới hạn statement 5 giây. Đã thử field relation dùng JSON_TABLE, tách nhánh UNION và gom lịch sử bằng window query. Các phương án làm SQL ngắn hơn nhưng chưa đạt hiệu năng đủ tốt trên collection lớn; đã loại toàn bộ code thử nghiệm này khỏi thay đổi cuối. Không thêm bảng search/cache hoặc cơ chế đồng bộ mới chỉ để xử lý case này.

Đo lại lượng dữ liệu bằng cùng probe DBAPI (một sample có instrumentation, detail mới dùng `view=editor`):

| Case | SQL trước → sau | DB values trước → sau | JSON trước → sau |
|---|---:|---:|---:|
| Owned selected, 20 rows | 21 → 20 | 157.508 → 44.167 B | 4.262 → 4.262 B |
| Clone selected, 20 rows | 37 → 33 | 154.106 → 48.500 B | 4.021 → 4.021 B |
| Collection nhiều installs, 100 rows | 104 → 96 | 1.131.464 → 463.521 B | 21.782 → 21.782 B |
| Detail owned | 19 → 16 | 119.551 → 5.112 B | 5.082 → 2.863 B |
| Detail clone | 81 → 41 | 154.358 → 68.519 B | 5.196 → 2.927 B |

Benchmark service MySQL, một warmup và ba samples mỗi case: owned selected median **365,9 → 58,7 ms**; sidebar owned **1.321,0 → 1.062,2 ms**. Hai case này giữ cùng payload hash. Đây là kết quả local, không phải HTTP/p95 hay cam kết production. Không suy ra mọi thao tác Browse đều nhanh hơn: search selected không có kết quả gần như không đổi và search toàn collection vẫn chậm.

Phép thử index riêng trên schema tạm chỉ copy các cột identity/user/deck, cùng phân bố dữ liệu: DISTINCT deck IDs median **113,4 → 24,5 ms**, 10 samples sau warmup, hash kết quả giữ nguyên. Đây không phải benchmark toàn ứng dụng hay bản sao đầy đủ row layout.

Kiểm tra tính đúng: **24 tests MySQL** (11 Note Browse, 13 compatibility), chạy bổ sung hai case mới cho PATCH editor/revision và loại install không liên quan; **71 tests frontend**, typecheck, lint các thư mục thay đổi và production build đều pass. Sáu case benchmark đều ổn định. So sánh với baseline ban đầu có hai case hash khác; chạy lại code HEAD cho riêng các module của task trong tiến trình chỉ đọc, giữ nguyên dữ liệu và dependency hiện tại, cho kết quả khớp cả sáu case. Không coi hai hash khác ở lần đo đầu là bằng chứng tương đương.

[Evidence triển khai đã rút gọn](BROWSE_QUERY_OVERFETCH_REVIEW_2026-10-24.implementation.evidence.json) lưu số đo, hash và trạng thái kiểm chứng; không lưu content, credentials hoặc SQL parameters.

## Kết quả chính

Các việc nhỏ đáng làm trước: **thu hẹp scope khi mở một Note; bỏ DISTINCT dư ở sidebar không có clone; chỉ SELECT các cột release thực sự cần; dùng lại schema release trong cùng request**. Search trên toàn collection clone vẫn là điểm chậm lớn nhất, nhưng cần thử query riêng trước khi chọn cách sửa.

Đường React Browse hiện tại đã đọc Note trực tiếp. Không còn JOIN Card/Template/StudyApplication trong list mặc định và counters được đo. Phần dư chủ yếu là **đọc quá rộng, đọc lặp và SELECT full ORM rows**, không phải có một bảng legacy lớn có thể xóa JOIN ngay.

| ID | Việc có thể tối ưu | Ưu tiên / phạm vi | Bằng chứng chính |
|---|---|---|---|
| Q1 | Thu hẹp deck/install scope cho selected-deck và Note detail | P1; detail owned nhỏ, clone/selected scope vừa | Mở 1 Note owned vẫn tải 1.534 Deck và chạy DISTINCT qua Notes của learner; clone detail resolve cả 7 installs |
| Q2 | Thu gọn cột đọc trong release history/checkpoints | P1 về dữ liệu dư; nhỏ–vừa | Một query 1.168 change rows có khoảng 561,8 KB giá trị; khoảng 431,0 KB thuộc cột reader này không đọc |
| Q3 | Dùng lại field schema/history của cùng release trong request | P2; nhỏ–vừa | List clone 20 rows và clone detail đều đọc cùng 80 field changes hai lần |
| Q4 | Bỏ DISTINCT của scope sidebar khi chỉ có nhánh owned | P2; nhỏ, đã thử chỉ đọc | Aggregate median 497,7 → 426,2 ms; payload giữ nguyên; plan giảm vị trí temporary từ 3 xuống 1 |
| Q5 | Giảm SQL search và tách nhánh scope clone phù hợp | P1 về độ chậm; vừa–lớn | Count search 490.137 ký tự, 508 SELECT, 353 JOIN clauses; chạm giới hạn statement 5 giây |
| Q6 | Thu gọn Note detail và phần ORM phục vụ nó | P2; nhỏ–vừa | `fields`/`note_type_fields` trùng schema khoảng 2 KB; Browse không dùng `media_assets`; clone còn dựng live values rồi ghi đè |
| Q7 | Thử covering index cho truy vấn tìm deck đang giữ Notes | P2; cần migration nếu phép thử tốt | DISTINCT deck_id dùng index user_id rồi temporary; DB local chưa có `(user_id, deck_id)` |
| Q8 | Dùng chung cache key detail giữa editor/TTS/SVG | P2; nhỏ | Cùng Note detail có ba query keys, nên có thể gọi lại cùng endpoint khi chuyển công cụ |

## Phạm vi và cách đo

- Theo caller React: `GET /api/browse/notes?view=rows`, `/api/browse/notes/:id`, `/api/browse/decks?view=notes`, `/api/note-types?compact=1`. Đọc thêm các consumer editor, TTS, SVG, worksheet và Study quick edit để không nhầm payload dùng chung.
- MySQL local 8.0.40, audit factory không chạy maintenance; chặn SQL ghi khi gọi service, rollback sau mỗi case. Không seed, migrate hoặc thay đổi dữ liệu.
- 11 case được bắt SQL tại DBAPI, gồm owned/clone list, sidebar, detail, compact NoteType và search. Mỗi case là **một sample có instrumentation**, không phải HTTP/load benchmark hay p95. Mẫu A: 39.338 Notes và 1.534 Deck; mẫu B: 14.835 Notes nhìn thấy, 290 Deck và 7 installs.
- `DB values` là tổng độ dài UTF-8 của giá trị trong buffered DBAPI rows, không gồm protocol overhead; đây là ước lượng lượng dữ liệu đọc vào Python. `JSON` là response chưa nén. Không dùng tỷ lệ giữa hai cột làm tỷ lệ CPU hoặc latency.
- Thử Q4 riêng: một warmup mỗi phương án, ba samples xen kẽ, chỉ thay SQL của audit process cho nhánh owned duy nhất. Không áp dụng lên ứng dụng.
- [Evidence đã rút gọn](BROWSE_QUERY_OVERFETCH_REVIEW_2026-10-24.evidence.json) giữ query shape, projection bytes, phase timings, EXPLAIN summaries và index inventory; không chứa SQL text, parameters, Note content hoặc credentials.

| Case | SQL statements | JSON chưa nén | DB values ước lượng |
|---|---:|---:|---:|
| Owned selected, 20 rows | 21 | 4.262 B | 157.508 B |
| Clone selected, 20 rows | 37 | 4.021 B | 154.106 B |
| Collection nhiều installs, 100 rows | 104 | 21.782 B | 1.131.464 B |
| Detail owned | 19 | 5.082 B | 119.551 B |
| Detail clone | 81 | 5.196 B | 154.358 B |
| Sidebar owned | 13 | 597.091 B | 185.551 B |
| Sidebar nhiều installs | 58 | 113.595 B | 117.621 B |
| NoteTypes compact | 3 | 16.164 B | 13.494 B |

## Q1 — Đọc toàn scope để xử lý một phần rất nhỏ

**Observed:** `_build_browse_query()` thu thập mọi Deck accessible trước khi lọc deck đã chọn. `_build_browse_detail_payload()` cũng tạo lookup tên từ toàn scope. Owned detail đã kiểm ownership trực tiếp, nhưng sau đó vẫn tải lại cây để lấy tên một deck.

**Evidence:** [query scope](../../app/services/browse_card_service.py#L444), [detail payload](../../app/services/browse_card_service.py#L1581), [deck collection](../../app/repositories/vocabulary_repository.py#L666), [clone authorization](../../app/services/browse_note_service.py#L154). Mẫu owned đọc 1.534 Deck, khoảng 107,7 KB giá trị, kèm DISTINCT trả 1.469 deck IDs. Truy vấn DISTINCT riêng mất khoảng 109–131 ms ở các case detail/list; count của selected deck chỉ khoảng 4,7 ms. Clone detail resolve cả 7 installs và tổng 81 statements.

**Có thể làm:** ưu tiên owned detail lấy đúng deck name/options cần sau bước authorization. Tiếp theo thu hẹp selected-deck scope và tìm install ứng viên theo source/local mapping trước khi chạy resolver. Với toàn collection, batch installs/maps thay vì lặp ancestor/subtree/release reads.

**Giới hạn:** selected scope vẫn phải giữ foreign ancestors, Note-holding decks, deleted-deck rules và fallback install cũ. Nhiều installs cùng source phải giữ thứ tự chọn hiện hành. Không đơn giản bỏ mọi check và tin `deck_id` từ client. Các lần gọi `collect_accessible_browse_decks()` trong cùng request đã có cache; hai lần gọi hàm không đồng nghĩa hai lượt SQL.

## Q2 — Release reader lấy cả những cột không dùng

**Observed:** `list_note_field_history_for_ids()` và `list_release_history_changes()` trả full `DeckReleaseChange`. Checkpoint reader cũng tải full entity. Browse chỉ cần một phần thuộc tính để dựng values/schema, nhưng vẫn nhận metadata của diff/audit.

**Evidence:** [history repository](../../app/repositories/deck_release_repository.py#L180), [selected Note history](../../app/repositories/deck_release_repository.py#L282), [runtime reader](../../app/services/deck_release_service.py#L561). Mẫu page 100 clone Notes có một query trả 1.168 change rows, khoảng 561.784 B. Những cột reader đó sử dụng — id, sequence, Note/Field identity, operation, after_value — chiếm khoảng 130.792 B; phần còn lại khoảng **430.992 B**, gồm `sort_key`, `change_key`, hashes, `before_value`, release/source/audit metadata. Đây là bytes có thể khảo sát cắt, chưa phải latency đã tiết kiệm.

**Có thể làm:** dùng projection/load options cho reader Browse, giữ thứ tự và identity cần thiết. Thu gọn checkpoint columns tương tự. Đây là bước ít phức tạp hơn tạo bảng preview/search cache.

**Giới hạn:** các repository helper còn phục vụ reader/diff khác. Không cắt cột ở helper dùng chung mà chưa kiểm caller; deferred attributes bị chạm lại sẽ sinh query lẻ. Native arrays và release history phải giữ nguyên.

## Q3 — Cùng schema release được đọc hai lần

**Observed:** `_page_overlay_values()` lấy values; reader values tự dựng field schema tại release. Sau đó `_clone_overlay_fields()` gọi `build_clone_schema_view()`, nơi lại dựng schema đó. Cache schema overlay hiện có không chia sẻ phần lịch sử mà value reader vừa tải.

**Evidence:** [page values](../../app/services/browse_note_service.py#L86), [field schema reader](../../app/services/deck_release_service.py#L521), [value reader](../../app/services/deck_release_service.py#L577), [overlay schema](../../app/services/share/overlay.py#L508). Clone selected đọc 80 field-change rows khoảng 29,4 KB hai lần, kèm field membership reads. Clone detail có cùng mẫu lặp. Page 100 trải qua bốn release có tám lượt đọc field history cùng query shape; các release khác nhau vẫn cần dữ liệu riêng.

**Có thể làm:** truyền schema/history đã tải cho bước sau hoặc reuse theo release identity trong cùng request. Chỉ cần reuse dữ liệu bất biến đang đọc trong request, chưa cần cache xuyên request, Redis hay cơ chế invalidation mới.

**Giới hạn:** schema source tại release và schema sau local overlay là hai lớp khác nhau; chỉ dùng chung phần release, không trộn schema của các installs có overlay khác nhau.

## Q4 — DISTINCT dư trong sidebar không có clone

**Observed:** `deck_counts()` luôn thêm DISTINCT cho `(note_id, deck_id, card_count)`. Khi chỉ có nhánh owned, query nguồn không JOIN làm nhân dòng và `Note.id` đã là primary key; DISTINCT không thêm tính đúng. Với UNION các installs thì vẫn có thể cần dedup.

**Evidence:** [scope builder](../../app/repositories/browse_note_repository.py#L152), DISTINCT tại dòng 168. Thử chỉ đọc, cùng payload hash trong cả sáu measured samples:

| Phương án | Aggregate median | Toàn sidebar service median | Vị trí `using_temporary_table` trong EXPLAIN |
|---|---:|---:|---:|
| Hiện tại | 497,7 ms | 1.011,0 ms | 3 |
| Bỏ DISTINCT ở nhánh owned duy nhất | 426,2 ms | 954,1 ms | 1 |

**Có thể làm:** điều kiện hóa DISTINCT khi nguồn thực sự có khả năng nhân dòng. Đây là thay đổi nhỏ có phép thử thực tế, khoảng 14% ở aggregate trong mẫu local; chưa triển khai lên app.

**Giới hạn:** chưa chứng minh có thể bỏ ở nhánh nhiều installs. Số vị trí temporary là plan summary, không phải số bảng tạm thực tế được đo lúc chạy; ba samples không phải SLA production.

## Q5 — SQL search clone vẫn phình lớn trước LIMIT

**Observed:** sau tối ưu `83face76`, mỗi effective field vẫn có correlated reads cho checkpoint/history/override. Chúng được lặp theo install, field và điều kiện visibility. Count chạy toàn scope trước page query.

**Evidence:** [clone projections](../../app/services/browse_card_service.py#L570), [effective-field expression](../../app/repositories/browse_card_repository.py#L123). Case search không có kết quả trên 7 installs: **490.137 ký tự SQL, 508 SELECT và 353 mệnh đề JOIN trong một statement**, không phải 353 bảng khác nhau. EXPLAIN chứa Note table access `ALL`, nhiều correlated plan nodes và temporary/filesort; đây không phải actual execution loops. MySQL error 3024 tại ngưỡng statement 5 giây do probe đặt. Chưa đến hydrate/editor nên không thể sửa bằng cắt vài field response.

**Có thể làm:** thử thu hẹp/tách owned và installed candidate branches để tránh full Note scan; đo lại trước. Sau đó thử chia sẻ checkpoint/effective-value work trong query. Chọn phương án có payload/count/order tương đương và thời gian tốt hơn; chưa chốt CTE, index tìm kiếm hay materialized table.

**Giới hạn:** release membership, pinned content và overlay đều có tác dụng thật. Không bỏ JOIN release chỉ để câu SQL ngắn, không lấy author working JSON thay pinned values và không lọc sau LIMIT. Ít subquery hơn chưa tự chứng minh nhanh hơn.

## Q6 — Detail còn payload/ORM dư

**Observed:** detail trả cả `fields` và `note_type_fields`; React Browse dùng `fields`. Trong mẫu 16 fields, riêng schema lặp khoảng 2.040–2.056 B trên response khoảng 5,1–5,2 KB. Browse không đọc `media_assets` hoặc `media_disabled_reason`; `NoteFieldEditor` dùng field values và proxy references. Detail loader còn lấy full NoteType, và clone detail dựng live values/preview trước khi ghi đè bằng release/overlay.

**Evidence:** [detail loader](../../app/repositories/browse_note_repository.py#L44), [serializer](../../app/repositories/vocabulary_repository.py#L523), [clone replacement](../../app/services/browse_card_service.py#L1698), [Browse editor](../../frontend/src/features/browse/components/BrowseCardEditForm.tsx#L169). Probe thấy mỗi detail có một media query, full NoteType query 25 cột và một lần decode live Note values kể cả clone. List clone pinned đã tránh load/decode author working JSON; không báo lại việc đó là lỗi của list.

**Có thể làm:** thu gọn serializer/loader dành cho Note editor, giảm schema lặp và cột marketplace của NoteType; xử lý pinned clone trước bước dựng live detail. Mẫu hiện tại source JSON một Note chỉ khoảng 935 B, nên riêng việc bỏ JSON này chưa phải ưu tiên latency cao.

**Giới hạn:** Study quick edit vẫn dùng `media_assets` qua API Card legacy; cần giữ contract đó. Media proxy/field identity không được bỏ. Trước khi xóa wire fields của Note API phải kiểm thêm caller ngoài React; audit này chứng minh consumer trong repo, không chứng minh không có client bên ngoài.

## Q7 — Covering index còn thiếu cho truy vấn scope thường gặp

**Observed:** `SELECT DISTINCT notes.deck_id ... WHERE notes.user_id = ? AND deck_id IS NOT NULL` dùng `ix_notes_user_id`, có temporary. Index inventory MySQL thực tế chỉ có PK và ba index đơn trên user_id, deck_id, note_type_id; chưa có index kết hợp user/deck.

**Evidence:** [Note-holding deck lookup](../../app/repositories/vocabulary_repository.py#L686), index inventory trong evidence. Truy vấn xuất hiện ở owned list, detail và sidebar; mẫu đọc ra 1.469 deck IDs và mất trên 100 ms.

**Có thể làm:** thử candidate `(user_id, deck_id)` trên schema MySQL riêng để kiểm covering/grouping, so sánh EXPLAIN và latency. Nếu tốt mới tạo migration. Việc thu hẹp scope ở Q1 có thể loại hẳn nhu cầu chạy query trong một số luồng, nên làm Q1 trước.

**Giới hạn:** chưa tạo index, chưa đo speedup của candidate. Phải tính chi phí ghi và kích thước index; không suy luận cứ có composite index là giải quyết search clone.

## Q8 — Cùng detail API nhưng cache tách theo công cụ

**Observed:** editor dùng `['browse', 'card-detail', id]`; TTS sample dùng `card-detail-sample`; SVG dùng `stroke-modal-card-detail`. Cùng endpoint/DTO có thể bị gọi lại khi chuyển từ công cụ sang editor hoặc giữa công cụ, dù response trước còn fresh.

**Evidence:** [editor](../../frontend/src/features/browse/hooks/useBrowseEditor.ts#L89), [TTS](../../frontend/src/features/browse/hooks/useBrowseTts.ts#L34), [SVG](../../frontend/src/features/browse/hooks/useBrowseStrokeModal.ts#L48).

**Có thể làm:** dùng chung key factory cho Note detail và invalidation tương ứng, giữ nguyên điều kiện bật query. Một request clone detail hiện có thể kéo 81 SQL ở mẫu local, nên tránh được request lặp đáng giá hơn cắt vài chuỗi response.

**Giới hạn:** đây là finding từ code consumer/cache keys, chưa đo request trùng bằng browser trong phiên này. Cần giữ canonical Note identity, save invalidation và draft behavior.

## JOIN nào cần giữ, việc nào chưa đáng ưu tiên

| Bảng/nhóm | Đánh giá trên luồng hiện tại |
|---|---|
| Card / Template / StudyApplication | Không có trên list/counters mới được đo; không cần mở lại việc loại bỏ đã xong |
| `study_progress_subjects` | JOIN phục vụ status, suspended và due order/counters; `status=all` vẫn dùng suspended predicate, không thể bỏ JOIN theo tên filter |
| `decks` | JOIN ở `sort_by=deck` có mục đích; SELECT full scope để lấy tên một deck mới là phần dư Q1 |
| Release / checkpoint / change / membership | Cần cho published status, pinned values và visibility; tối ưu projection, reuse và query shape theo Q2/Q3/Q5 |
| NoteType / FieldDef / media | Schema editor có mục đích; full marketplace columns, schema lặp và media payload không dùng có thể thu gọn theo Q6 |

- NoteTypes đã dùng compact và chỉ ba queries, khoảng 31 ms trong sample. Tuy nhiên ORM vẫn tải full NoteType: taxonomy metadata/description/pricing/rating không được compact serializer dùng. Đây là việc nhỏ có thể gom khi chạm loader; không phải nút thắt chính. Không đánh đổi trải nghiệm mở form để tiết kiệm vài KB khi chưa cần.
- List Note vẫn gọi `build_browse_row()` để dựng `card_type`, `note_type`, `template`, `queue`, `due_at`, `updated_at` rồi `_row()` bỏ các trường đó. Đây là xử lý/chuỗi dư có thể dọn khi sửa serializer. `BrowseNoteReference.template = None`, nên việc dựng chuỗi này không có nghĩa còn query bảng Template.
- Authority phase list khoảng 18–48 ms ở các sample; reader có lock/hash/parity checks thật. Chưa có lý do ưu tiên viết reader Study mới hoặc bỏ validation chỉ để giảm query count.
- Sidebar owned response khoảng 597 KB chưa nén nhưng các trường path/type metadata có consumer thật. Chưa đo compression hoặc HTTP nên chưa đề xuất đổi contract thành tree lazy-load/dictionary.
- Chưa tìm thấy bằng chứng N+1 theo từng Note trong list. 104 queries ở page nhiều installs tập trung vào scope và mỗi release/install; không được gọi chung là 100 query cho 100 rows.

## Phạm vi kiểm chứng còn lại

Đã review code, bắt SQL đọc thực tế, EXPLAIN và thử Q4 chỉ đọc. Chưa triển khai candidate, chưa chạy regression suite cho thay đổi sản phẩm vì không sửa app; chưa kiểm HTTP/browser, production/load, concurrency hoặc rehearsal migration. Hai script probe local nằm tại `.tmp/browse-sql-review-20261024.py` và `.tmp/browse-sql-review-experiments-20261024.py`; cần chọn lại IDs khi dùng database khác. Không dùng dữ liệu một sample làm cam kết hiệu năng.
