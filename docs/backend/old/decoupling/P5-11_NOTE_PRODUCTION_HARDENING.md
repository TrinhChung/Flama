# P5-11 — Gia cố NOTE authority sau R1

> Lập 2026-09-30. Trạng thái: **P5-11a + P5-11b đã deploy production** (PR #173, release `6472e42`, 30/09 ~04:30 UTC; kèm bản sửa dashboard #171). Backup trước merge `/root/backups/flama-pre-pr173-20260930T041022Z.sql.gz`. Sau deploy: audit `study-authority-read-audit` **18/18 PASS**, 0 learner LEGACY; dashboard user 1 (39k thẻ) đo trên production trong transaction READ ONLY **3,1 s** (trước: ~120 s, 504), user 4 0,86 s; journal không có `Lock wait`/deadlock. P5-11c (materialize theo lô) còn mở. Nguồn: [báo cáo tải](../../../architecture/DATABASE_ARCHITECTURE_SCALABILITY_REVIEW_2026-09-29.md), [điều tra truy vấn](../../../architecture/DATABASE_QUERY_PERFORMANCE_INVESTIGATION_2026-09-29.md), log production 28–30/09.

## 1. Vì sao cần

R1 (29/09) đưa 18/18 learner sang NOTE. Hai lớp lỗi xuất hiện khi dùng thật:

| Bằng chứng | Nguồn | Hệ quả |
|---|---|---|
| 50 % commit phiên học mất vì deadlock khi 4–8 learner học cùng lúc; 27 % đăng ký đồng thời trả 500 | báo cáo tải §3.3–3.4 | Learner phải bấm gửi lại; người mới không tạo được tài khoản |
| Tái hiện local (6 learner × 3 vòng, 10 đăng ký): **9/18 commit lỗi, 9/10 đăng ký lỗi** | `scripts/probe_p5_concurrency_mysql.py` trên code `a7a15cf` | như trên |
| Deadlock trả về HTTP 409 với mã `e3q8` và **nguyên câu SQL trong `message`** | probe + code (`getattr(exc, "code")`) | Lộ cấu trúc SQL cho client; client coi lỗi hạ tầng là xung đột nghiệp vụ |
| `1205 Lock wait timeout` trên `study_progress_subjects … FOR UPDATE`; 7 dashboard + 6 overview trả 504 | journal `flama.service`, nginx 28–30/09 | Bản sửa #171 (reader không khóa) đã merge nhưng **chưa deploy**: CI master của #171 fail, #172 chỉ sửa test nên job deploy bị bỏ qua. Production vẫn chạy `22f8695`. |

## 2. Nguyên nhân gốc

Dưới REPEATABLE READ, `SELECT … FOR UPDATE` trên **một khóa chưa tồn tại** hoặc **một khoảng rỗng** giữ gap lock. Các dòng mới của learner khác nằm cạnh nhau ở cuối index, nên hai transaction cùng giữ một gap rồi cùng chờ insert-intention của nhau. Thiết kế P4/P5 dùng đọc khóa chỉ để có *current read* (xem [P4-07 InnoDB finding](../decoupling-phases/phase-4-native-session-worker-mirror-verification-2026-09-13.md#innodb-isolation-finding)); tuần tự hóa thật sự đến từ khóa cha (User, subject, token, contributor). Gap lock là tác dụng phụ không cần thiết.

Bốn điểm "đọc-khóa-rồi-chèn" gặp trong probe, theo thứ tự lộ ra:

| Bảng | Nơi đọc | Sửa |
|---|---|---|
| `study_authority_enrollments` | `stage_note_authority_enrollment` | Đọc snapshot trước; chỉ `FOR UPDATE` theo PK khi dòng tồn tại. User đã bị khóa FOR UPDATE nên mọi writer tuần tự; snapshot cũ chỉ có thể dẫn tới lỗi khóa chính khi insert (fail closed). |
| `study_progress_lineage_refs` | `finalize_study_authority_evidence` | Khóa theo PK các dòng thấy trong snapshot rồi **chứng minh** chúng là hiện hành: digest tính lại (đúng công thức reconciliation P4-10) phải bằng `contributor.lineage_vector_hash` đọc khóa. Mọi writer lineage cập nhật contributor trong cùng transaction. Lệch → đọc khoảng như cũ. |
| `study_authority_command_receipts` | `_locked_replay`, `read_direct_note_replay` → `lock_operation_receipt` | Receipt thấy trong snapshot → khóa theo PK. Không thấy → chỉ bỏ khóa khi token của subject (đang giữ FOR UPDATE) trong snapshot bằng token hiện hành, tức không có commit nào trên subject sau snapshot; nếu khác → đọc khóa như cũ. |
| `study_progress_history_facts` | `append_native_history_fact` | Luồng NOTE vừa chèn `ReviewEvent` trong chính transaction chưa commit, nên không fact nào đã commit có thể trỏ tới nó: bỏ lookup (`event_created_in_transaction=True`). Ràng buộc unique vẫn chặn trùng. |

Thêm hai lớp bảo vệ:

- `app/services/db_errors.py`: `domain_error_code()` không coi `SQLAlchemyError.code` là mã nghiệp vụ (thay 15 chỗ `getattr(exc, "code")` trong luồng học, MCP, switch). Lỗi DB giờ đi tới handler chung (500, không lộ SQL) hoặc được retry.
- `run_with_deadlock_retry()`: chạy lại tối đa 3 lần khi InnoDB báo 1213 (nạn nhân deadlock đã bị rollback toàn bộ, nên chạy lại không lặp tác dụng phụ). Áp dụng cho commit phiên, mở phiên, trả lời trực tiếp REST, MCP `submit_review`, đăng ký. Không retry 1205.

Không đổi schema, cờ hay mức cô lập; không đổi hợp đồng API ngoài việc deadlock không còn trả 409 `e3q8`.

## 3. Kiểm chứng

| Kiểm chứng | Kết quả |
|---|---|
| `probe_p5_concurrency_mysql.py` 6 learner × 3 vòng × 12 câu, 10 đăng ký — trước sửa | 9 deadlock, 9/18 commit lỗi; 9/10 đăng ký lỗi |
| Cùng probe — sau sửa | **0 deadlock**, 18/18 commit, 10/10 đăng ký vào NOTE, audit PASS mọi learner |
| 8 learner × 5 vòng × 20 câu, 12 đăng ký | 0 deadlock, 40/40 commit, 12/12 đăng ký, audit PASS |
| Thêm 36 câu trả lời trực tiếp REST đồng thời | 0 deadlock, 36/36 |
| `tests/test_study_note_write_gap_locks.py` | hình dạng câu lệnh không khóa dòng vắng; fallback lineage đúng dòng; replay receipt còn nguyên |
| `run_tests.py --module study,auth,connect_mcp --backend-only` | 67 file PASS |
| Probe MySQL direct-replay / study-batch | xem §5 |

Probe mới chạy trong job CI `mysql-contract`.

## 3b. P5-11b — bớt round-trip trên đường đọc/mở phiên

Cùng khóa, cùng snapshot, cùng pin; chỉ gom câu lệnh:

| Thay đổi | File |
|---|---|
| `lock_study_authority_subject_rows`: khóa token + state của cả vector subject bằng hai câu `… WHERE subject_id IN (…) FOR UPDATE` theo PK (dòng thấy trong snapshot; subject đã khóa nên chỉ cần record lock), rồi `lock_study_authority_subject(locked_rows=…)` chạy đúng các kiểm tra cũ. Dòng thiếu (tạo token, pristine) đi đường cũ từng subject. | `study_authority_repository.py`, `study_session_authority_pin_service.py` |
| Mở phiên: nạp sẵn `Card.note`, media, Template; `Deck`/deck options nhớ theo deck trong request; `study_session_cards` chèn một câu nhiều dòng; pin của phiên vừa tạo bỏ câu kiểm tra tồn tại (PK vẫn chặn trùng) nên flush theo lô. | `study_session_service.py` |
| Browse tree: `contains_eager(Card.note)`; `/api/study/next`: nạp sẵn Note, deck options theo deck. | `browse_card_service.py`, `routes/flashcards/study.py` |

Đo trên MySQL 8.0.40 local, learner NOTE 1.000 Note (`scripts/bench_p5_session_open_mysql.py`):

| Endpoint | Trước | Sau |
|---|---|---|
| Mở phiên v4 | 11,5 s · 8.823 SQL | **1,9 s · 46 SQL** |
| Browse tree | 4,3 s · 3.036 | 1,2 s · 48 |
| Browse cards | 3,0 s · 2.057 | 1,2 s · 70 |
| `/api/study/next` | 6,4 s · 5.029 | 1,2 s · 54 |
| Commit 50 câu | 2,3 s · 1.414 | 2,2 s · 1.318 (O(câu trả lời), chưa đổi) |
| Mở phiên có 300 Note mới chưa materialize | — | 11,3 s · 6.955 (≈23 SQL/Note) → P5-11c |

## 3b'. P5-11c — materialize Note chưa học theo lô

Production 30/09 (SELECT-only): 10 learner mỗi người có 460–12.014 Note nguồn overlay chưa học (deck marketplace đã cài, chưa có subject NOTE). Mở phiên v4 materialize mọi Note chưa học trong phạm vi (tối đa 5.000 thẻ) trong một request, ≈24 câu SQL/Note qua bộ máy mirror tổng quát: 2.000 Note ≈ 55 s local, vượt timeout 60 s của nginx trên VPS; transaction bị hủy nên lần mở sau lặp lại.

`materialize_pristine_notes` nay gọi `materialize_pristine_notes_bulk` + `finalize_pristine_materialization`: cùng thứ tự khóa (Card chung → subject theo khóa → token), cùng điều kiện từ chối và mã lỗi, cùng các hàm thuần (`map_card_progress`, `build_contributor_evidence`, `canonical_document`), nhưng ghi subject/CardProgress/contributor/availability/state/token bằng câu lệnh theo lô. Đường từng-Note (`materialize_new_note_authority`, tạo Note mới) giữ nguyên.

`tests/test_study_pristine_bulk_materialization.py`: cùng dữ liệu (7 Note, 11 Card, có Note 2 Template, có subject/token pristine sẵn), chạy đường từng-Note rồi rollback, chạy đường theo lô, so **mọi cột** của subject, token, card_progress, contributor, availability, state — khớp tuyệt đối trên SQLite; trên MySQL (id không quay lại sau rollback) khớp mọi cột trừ các trường suy ra từ id. Có ca đối chứng âm (ease khác phải lệch), ca từ chối, và audit đọc PASS. Chạy trong `probe_p5_direct_replay_mysql.py`.

| Mở phiên v4 (MySQL 8.0.40 local) | Trước | Sau |
|---|---|---|
| 500 Note chưa học | 13,4 s · 12.047 SQL | **1,75 s · 62 SQL** |
| 3.000 Note chưa học | ≈80 s (ước) | **8,9 s · 164 SQL** |

Cùng PR: công cụ MCP `get_due_card_counts`, `get_study_queue`, `get_deck_stats` nạp Note lười và gọi `resolve_deck_options` cho từng Card (~3 SQL/Card). Nay nạp Note trong cùng truy vấn (`contains_eager`) và resolve tùy chọn một lần mỗi deck, như P5-11b đã làm cho mở phiên. Learner 3.000 Note (MySQL local): `get_due_card_counts` 11,8 s · 9.040 SQL → **2,2 s · 50 SQL**; `get_study_queue` 23,3 s · 18.090 SQL → **4,4 s · 110 SQL** (`bench_p5_session_open_mysql.py` đo cả hai).

## 3b''. P5-11e — reader đếm/chọn hàng đợi theo tập hợp

Sau R1 mọi reader NOTE đọc authority **có khóa và xác minh từng Card** (≈0,7 ms CPU/Card). Learner 20.000 Note (MySQL local): Browse tree 13,8 s, Browse cards 15,1 s, MCP `get_due_card_counts` 13,5 s, `get_study_queue` 26,7 s; learner lớn nhất production có ~39k thẻ. Dashboard/overview đã đọc tập hợp không khóa từ #171.

- **Browse tree** (NOTE): đếm bằng `aggregate_deck_study_counts` như dashboard (cùng ngữ nghĩa `counter_bucket_for_progress_values`; thêm `owned_by_any_user` cho Browse admin).
- **Browse cards** (NOTE): kiểm toàn vẹn mọi ứng viên bằng luật tập hợp của dashboard (`note_card_rows` + `subject_vector_violation`, cùng mã lỗi); đọc authority đầy đủ, có khóa chỉ cho thẻ của trang.
- **MCP** `get_due_card_counts`/`get_study_queue`: `load_study_authority_availability_snapshot` đọc đúng các giá trị availability mà bộ đọc có khóa trả về (dòng canonical cho Note đã học, suy từ Card cho Note chưa học) rồi gọi chính `summarize_study_authority_queue` → cùng số đếm, cùng thứ tự; thẻ trả về vẫn được đọc đầy đủ. `tests/test_study_availability_snapshot.py` chứng minh availability và tóm tắt hàng đợi bằng đúng bộ đọc có khóa (SQLite + MySQL trong probe overlay).
- **Giữ nguyên** `/api/study/next`: endpoint quyết định thẻ sắp trả lời, có test yêu cầu từ chối khi availability bị sửa lệch mà hash không đổi — chỉ bộ đọc từng thẻ phát hiện được. SPA không dùng endpoint này (0 lượt trong 15 ngày log).

Đánh đổi (giống dashboard): kiểm tra tập hợp phát hiện mọi lệch liên kết (thiếu contributor/availability/projection, sai thế hệ/revision/hash) nhưng không tính lại nội dung projection từng thẻ; phần đó do `study-authority-read-audit` đảm nhận.

| Learner 20.000 Note (MySQL 8.0.40 local, `bench_p5_session_open_mysql.py --notes 20000`) | Trước | Sau |
|---|---|---|
| Browse tree | 13,8 s · 192 SQL | **1,4 s · 17 SQL** |
| Browse cards (trang 50) | 15,1 s · 251 SQL | **1,6 s · 55 SQL** |
| MCP `get_due_card_counts` | 13,5 s · 186 SQL | **4,3 s · 12 SQL** |
| MCP `get_study_queue` | 26,7 s · 382 SQL | **8,2 s · 55 SQL** |
| Dashboard / overview (đối chứng, không đổi) | 1,2 / 1,1 s | 1,1 / 0,9 s |
| `/api/study/next` (giữ nguyên) | 14,1 s | 14–18 s |

## 3c. P5-11d — tạo Note song song (MCP agent) không còn deadlock

Production 29/09 13:33 (release cũ, sau R1): 17 lần `create_note`/`batch_create_notes` qua MCP trả 500, 16 do deadlock 1213 và 1 do lock wait timeout, khi agent tạo Note song song. Tái hiện trên MySQL 8.0.40 với code `master` sau P5-11: 8 lần tạo song song cho một learner → 3 lỗi 1213.

Nguyên nhân: materialize subject NOTE cho Note mới đọc `FOR UPDATE` những dòng chưa tồn tại — subject theo `(learner, logical_note_key)`, token/state, `card_progress`, contributor, availability, lineage của subject/contributor vừa INSERT. Id subject/contributor tăng dần nên các gap lock đó cùng rơi vào supremum cuối index; hai transaction cùng giữ gap lock rồi cùng INSERT → deadlock (kể cả giữa hai learner khác nhau).

Sửa (không đổi schema, mức cô lập hay hợp đồng API):

- `app/repositories/study_inserted_rows.py`: ghi nhận subject/contributor do transaction hiện tại INSERT (gắn với đúng transaction gốc, tự xóa khi commit/rollback, không bao giờ được công nhận ở transaction sau). Dòng con của chúng có FK tới cha chưa commit nên chỉ chính transaction này tạo được; các chỗ đọc chúng (token, state, contributor, availability, lineage) đọc thường, không `FOR UPDATE`. Không đánh dấu ở nhánh upsert `ON DUPLICATE KEY UPDATE` vì PyMySQL chạy `CLIENT_FOUND_ROWS`, rowcount không phân biệt được insert với dòng có sẵn.
- `_materialize_note_authority`: tìm subject bằng đọc thường rồi khóa theo PK nếu có; kiểm `card_progress` bằng đọc thường (unique `(user_id, card_id)` chặn trùng).
- MCP `create_note`/`batch_create_notes` chạy lại khi deadlock như các đường ghi khác của P5-11 (một transaction, một commit).
- Lỗi tiềm ẩn đi kèm: availability lưu `card_created_at` DATETIME(6) từ giá trị `Card.created_at` trong bộ nhớ (có micro-giây) trong khi `cards.created_at` là DATETIME(0) → `study-authority-read-audit` báo "availability evidence is stale" cho mọi Note tạo mới ở NOTE (có từ trước, tái hiện trên code gốc). `finalize_native_mirror` nay đọc lại `created_at` đã lưu của Card vừa tạo (chỉ Card có phần lẻ giây). Production 30/09: 0/40.668 dòng lệch (các lần tạo sau R1 đều đã lỗi), nên không cần sửa dữ liệu.

Kiểm chứng MySQL 8.0.40: 1/8/16 lần tạo song song → 0 deadlock, audit PASS, 0 trường lệch; `probe_p5_concurrency_mysql.py` thêm `--creates` (CI chạy `--creates 8`).

## 4. Rollback

Chỉ đổi code. Deploy lại release trước theo workflow; không có migration hay dữ liệu cần đảo. Các đường fallback giữ đúng hành vi cũ khi không chứng minh được snapshot.

## 5. Việc còn lại

1. ~~**Deploy**~~: xong (#173 `6472e42`, rồi #176–#178), audit 18/18 PASS sau mỗi lần.
2. ~~**P5-11c — materialize Note pristine theo lô**~~: xong, §3b'.
3. **Snapshot cả phạm vi**: phiên vẫn chứa tới 5.000 thẻ (≈2 ms CPU/thẻ, JSON ≈2 KB/thẻ). Nhánh NOTE batch tiếp tục cùng lease sau mỗi lô 50 câu; chỉ transport cũ (v2/v3) mở lại snapshot ([F9-02](../decoupling-phases/phase-9-contraction-investigation-2026-09-30.md#f9-02--snapshot-lớn-còn-tồn-tại-note-rollover-đã-tái-sử-dụng-lease)). Chỉ snapshot hàng đợi trong ngày là thay đổi hợp đồng wire, để sau (P9-07).
4. ~~**Reader vẫn khóa**~~: Browse và MCP đọc theo tập hợp (§3b''). Còn `/api/study/next` (SPA không dùng) giữ bộ đọc từng thẻ có chủ đích; learner 20k Note mất ~15 s.
5. **Frontend gửi commit hai lần** (LEGACY v3): sau commit `auto_finish` thành công, `flushOnExit` gửi lại cùng `commit_id` với `final_states` đã cập nhật → 409 `IDEMPOTENCY_KEY_REUSED`. Dữ liệu lần đầu đã lưu; với v4 (`final_states` rỗng) lần gửi lại là replay 200. Chỉ còn ảnh hưởng phiên LEGACY cũ trong IndexedDB.
6. ~~Retention membership phiên~~: Phase 7, đã chạy 30/09.
7. ~~**Cổng deploy CI**~~: xong trong #173 (so với release deploy thành công gần nhất).
