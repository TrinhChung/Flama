# Review bản tối ưu release deck do Gemini thực hiện

Ngày: 2026-10-26. Đối tượng: các thay đổi **chưa commit** trên `73651305`, nhánh
`fix/deploy-disconnect-cloudflare`, file sửa lúc 20:38–20:57. Phạm vi review gồm
`app/services/deck_release_service.py`, `app/repositories/deck_release_repository.py`,
`app/services/deck_auto_publish_service.py`, `app/services/deck_working_tree_service.py`,
`app/services/flashcard_media_normalizer.py` và
`tests/test_deck_release_performance_mysql.py`.

Ngoài phạm vi: các thay đổi MCP/template cùng nằm trong working tree, và các thư mục
frontend chưa track (`features/deck-versioning`, `deck-review-merge`,
`cascading-sync`, `entities/card-diff`, `entities/deck-version`). Các thư mục này
chưa được nối vào luồng release.

Báo cáo trước: [`RELEASE_DECK_RESIDUAL_OPTIMIZATION_AUDIT_2026-10-26.md`](RELEASE_DECK_RESIDUAL_OPTIMIZATION_AUDIT_2026-10-26.md)
(dưới đây gọi là "audit", ví dụ audit 4.7).

> **Cập nhật cùng ngày:** đã sửa 4.1, 4.2 và 4.3. Hiện 79/79 test pass và parity N1
> vẫn đạt; xem [mục 7](#7-cập-nhật-sau-khi-sửa-41-42-43). Các mục 4.4–4.9 và dư địa ở
> mục 5 vẫn còn nguyên.

## 1. Kết luận

**Chưa nên merge nguyên trạng** (đánh giá trước khi sửa). Phần tối ưu đọc có hiệu quả thật và cho kết quả
giống hệt code cũ trên bộ N1. Tuy vậy, bản sửa tạo ra **2 lỗi đúng-sai mới** (đã tái
hiện bằng test, code cũ pass) và làm **1 test hiện có fail**.

| | Kết quả |
|---|---|
| Parity N1 (manifest, change rows kèm hash, state tái dựng, giá trị note, item preview) | Giống hệt code cũ |
| Preview N1 | ~2,3–2,8 lần nhanh hơn; page reads −70 % (716k → 217k) |
| `GET /auto-publish` | 7,65 s → 0,05 s |
| Test release liên quan (77 test, MySQL opt-in) | 76 pass, **1 fail** |
| Lỗi mới | **2 lỗi đúng-sai** ở note không có checkpoint (mục 4.1, 4.2) |

Cả hai lỗi sửa được bằng một thay đổi nhỏ mà **không mất phần tăng tốc của N1** (mục 4.1).

## 2. Gemini đã làm gì

| Thay đổi | Ứng với audit | Đánh giá |
|---|---|---|
| Media normalizer ghi journal cho mọi giá trị đổi, cả khi rollback | 4.1 (sửa từ nguồn) | Đúng hướng. Cách này mặc nhiên chọn **giao đường dẫn `/media/proxy` mới cho learner** qua release; đây là quyết định sản phẩm, cần bạn xác nhận |
| Đọc note thẳng theo `field_values_by_id`, chỉ lấy đúng các cột cần | 4.8 | Tốt; không còn 170 lookup clone-map; working state 2,7 s → 1,2 s |
| Đọc checkpoint trước, chặn lịch sử theo sequence | 4.7 | Tốt với note có checkpoint; **sai với note không có checkpoint** (4.1, 4.2) |
| Hash tính lười (chỉ cho trang preview hoặc khi publish) | 4.9 | Tốt; parity hash đạt |
| Journal/checkpoint/membership đọc bằng Core tuple; ghi checkpoint/membership theo batch | 4.10, 4.12 | Tốt; có một rủi ro nhỏ về đồng bộ với ORM (4.8) |
| Sparse bỏ qua khi có > 5000 dirty rows | 4.10 | Hợp lý cho N1; ngưỡng tuyệt đối (4.9) |
| Sparse fail-closed khi field không có trong journal nhưng giá trị khác | 4.1 | Rẻ, nhưng chỉ phủ các note đã có trong journal, và là một lớp guard (4.9) |
| Auto-publish status không dựng preview khi > 200 dirty rows | 4.5 | Nhanh; số hiển thị đổi nghĩa (4.4) |
| Auto-publish bọc trong `begin_nested()` | 4.11 | Đúng hướng; làm fail 1 test (4.3) |

**Chưa làm:** frontend (audit 4.3), DELETE journal và INSERT atoms ở đường publish
(4.6), auto-publish chạy theo từng batch và cập nhật subscriber đồng bộ (4.11), cache
preview (4.4).

## 3. Kiểm chứng đã chạy

- Test (`FLAMA_MYSQL_TESTS=1`, đã để trống 7 cờ `STUDY_*`): `test_deck_release_api`,
  `test_deck_release_performance_mysql`, `test_deck_auto_publish_and_auto_update`,
  `test_deck_install_rebase_flow`, `test_owner_note_dirty_tracking_services`,
  `test_flashcard_media_normalizer`, `test_template_deck_release`,
  `test_deck_release_schema`. Kết quả: 77 test, 1 fail (mục 4.3).
- Repro MySQL chỉ rollback: `output/test_release_review_repro.py`, chạy cả trên code
  mới lẫn một worktree tạm ở `HEAD`. Worktree đã xóa sau khi chạy.
- Parity và hiệu năng trên N1: `output/parity_perf_probe.py`, transaction
  `READ ONLY`, 3 vòng xen kẽ cũ/mới, lấy giá trị nhỏ nhất. Kết quả JSON:
  `output/gemini_review_parity_{head,new}.json`.

| Phép đo N1 (min 3 vòng) | HEAD | Gemini | SQL | Logical reads |
|---|---:|---:|---:|---:|
| Preview lần đầu, limit 100 | 9,25 s | 3,28 s | 188 → 17 | 716k → 217k |
| Preview trang 2 | 7,51 s | 3,10 s | 17 → 17 | 716k → 217k |
| Preview có tìm kiếm | 6,78 s | 3,73 s | 17 → 17 | 716k → 217k |
| Auto-publish status | 7,65 s | 0,05 s | 18 → 3 | 716k → 0,5k |
| Dựng diff (publish) + change rows có hash | 6,73 s | 4,07 s | — | — |
| `reconstruct_release_state(head)` | 2,24 s | 1,00 s | 4 → 5 | 597k → 99k |
| `_build_working_state` | 2,75 s | 1,22 s | 6 → 5 | ~118k |
| Giá trị theo ID của mọi note tại head | 2,07 s | 1,95 s | 66 | ~163k |

Lúc đo máy đang chịu tải từ tiến trình khác (node ~1 GB, Codex), nên số tuyệt đối
của HEAD cao hơn lần đo trước (khoảng 5,2–5,4 s). Chỉ nên so tương đối giữa hai cột.
Buffer pool runtime là 1 GiB, không phải 128M. Đường publish không được chạy lại,
nên không có số đo ghi.

## 4. Lỗi và rủi ro, xếp theo mức độ

### 4.1. CAO — Note không có checkpoint bị mất giá trị sau khi chuyển deck

`_get_note_field_values_by_id_for_ids_at_release` (`deck_release_service.py:726-731`)
gán mốc lịch sử của note không có checkpoint là
`introduced_sequence - 1` của **membership đang hiệu lực**. Membership được tạo lại mỗi
khi `source_deck_id` hoặc metadata của note thay đổi, ví dụ khi chuyển note sang
subdeck khác (`browse_card_service.py:1590-1611` ghi remove/add). Thao tác này không
sinh atom giá trị, nên mọi atom trước đó bị bỏ qua.

**Repro** `test_moved_note_without_checkpoint_keeps_values`: publish 1, thêm note,
publish 2, chuyển note sang subdeck và sửa note khác, publish 3. Code mới trả `{}`;
HEAD trả đủ `Word`/`Values`.

**Phạm vi ảnh hưởng:** hàm này phục vụ phần learner đọc release.
`share/overlay.py:697`, `browse_note_service.py:115`, `browse_card_service.py:1019`,
`change_request/preview.py:288`, `connect/identity_lookup.py:61` và sample
marketplace đều dùng nó. Learner sẽ thấy note rỗng với mọi note được thêm sau release
đầu tiên rồi chuyển deck. Sparse diff cũng dùng hàm này làm giá trị base; nhờ guard mới,
sparse tự fallback sang full, nên release không sai nhưng chậm hơn.

### 4.2. CAO — Tái dựng state sai khi mọi note còn lại đều không có checkpoint và đã chuyển deck

`reconstruct_release_state` (`:452-463`) lấy `min_note_field_seq` là giá trị nhỏ nhất
trong các `introduced_sequence`. Khi mọi note đang hiệu lực đều không có checkpoint và
đều đã chuyển deck, mốc này vượt qua atom đầu tiên của chúng.

**Repro** `test_reconstruct_when_only_moved_uncheckpointed_notes_remain`: xóa các note
ban đầu, chuyển các note thêm sau. Code mới trả `{A: {}, B: {Word}}`; HEAD trả đủ giá
trị. State base sai thì lần full diff kế tiếp sẽ sinh các atom `add` giả.

**Cách sửa cho cả 4.1 và 4.2:** với note không có checkpoint, dùng lại mốc 0 (đọc đủ
lịch sử) như HEAD; giữ mốc `checkpoint + 1` cho note có checkpoint. N1 có checkpoint
cho cả 10.148 note, nên phần tăng tốc của N1 không bị ảnh hưởng. Sửa như vậy cũng
tránh số query tăng theo số `introduced_sequence` khác nhau trong
`list_note_field_history_for_ids`, vốn chạy một query cho mỗi nhóm. Nên đưa hai repro
vào `tests/test_deck_release_performance_mysql.py`.

### 4.3. TRUNG BÌNH — 1 test fail: `test_independent_session_publication_rolls_back_with_source_edit`

SQLAlchemy 2.0.48 chạy `before_commit` cả khi commit một transaction lồng nhau
(`SessionTransaction._prepare_impl`: `if self._parent is None or self.nested`). Khi
`with db.session.begin_nested()` trong auto-publish kết thúc, listener `before_commit`
của test chạy ngay giữa lúc publish. Test ném lỗi, auto-publish bắt lỗi và rollback
savepoint, rồi lần commit ngoài thấy release chưa được tạo.

Listener của app (`deck_working_tree_service:84`, `deck_count_projection_service:213`,
`review_analytics_projection_service:224`, `template_version_service:92`) đều bỏ qua
khi đang ở transaction lồng nhau, nên chưa thấy ảnh hưởng ở runtime. Nhưng CI sẽ đỏ.

**Cách sửa:** cho listener trong test bỏ qua khi
`session.in_nested_transaction()`. Không bỏ savepoint.

### 4.4. TRUNG BÌNH-THẤP — Số đếm của auto-publish status không nhất quán

Khi có > 200 dirty rows, endpoint trả số dirty rows. N1 trả 81.218, trong khi số thay
đổi thật là 91.281 (journal thiếu ~20k atom media, thừa ~10k dòng `reading` không
còn thay đổi thật). Khi có ≤ 200 dirty rows, endpoint vẫn dựng cả preview; nếu journal
lỗi thời thì đó là đường full (~5 s) mỗi lần owner mở trang deck.

**Đề xuất:** trả `has_unreleased_changes` dạng boolean, coi số dirty rows chỉ là ước
lượng ("khoảng N"), và không bao giờ dựng preview trong endpoint này.

### 4.5. THẤP — Fallback âm thầm trả `{}` cho note không đúng codec

`_extract_source_note_values` (`:307`) với Row từ query chỉ lấy cột (không có thuộc
tính `field_values`) sẽ trả `{}`. Full diff khi đó sinh atom `remove` cho mọi field của
note, trong khi adapter cũ báo `FieldIdentityError`. DB local có 41.870/41.870 note
dùng `field-id.v1`, không có `extras`, cột `NOT NULL` có default, nên hiện đây là nhánh
không bao giờ chạy tới. **Nên báo lỗi thay vì trả rỗng.**

### 4.6. THẤP — Hành vi full diff đổi khi field bị xóa rồi tạo lại cùng tên

Đường full giờ dùng `include_raw_values=False`, nên fallback theo tên trong
`_build_atomic_diff` không còn gán giá trị hiện tại cho ID field cũ cùng tên. Trước
đây ID cũ không sinh atom; giờ sinh `remove` cho ID cũ và `add` cho ID mới. Hành vi mới
khớp với đường sparse, nhưng là thay đổi chưa có test. Cần chốt hành vi nào là đúng.

### 4.7. THẤP — Trường hợp biên khi không có membership nào đang hiệu lực

`list_memberships(active_at_sequence=...)` trả rỗng khi release không còn note/field
nào. Khi đó `if memberships` rơi vào chế độ tương thích dữ liệu cũ: note từ checkpoint
xuất hiện lại, và `_min_note_field_sequence_after_checkpoints` dùng heuristic giả định
checkpoint chỉ có ở sequence 1.

### 4.8. THẤP — Ghi membership bằng Core không đồng bộ với ORM trong cùng transaction

`_sync_memberships` (đường full) giờ retire/insert bằng Core. Các object membership
ORM đã nạp trước đó trong cùng session (ví dụ field_def memberships của
`_release_field_context`) vẫn giữ `removed_sequence = None` cho tới khi commit. Với
publish thủ công thì không sao, vì commit ngay sau đó. Với auto-publish, việc cập nhật
subscriber chạy trong cùng transaction và có thể đọc membership cũ khi release xóa
field.

### 4.9. Ghi chú nhỏ

- Ngưỡng `dirty_count > 5000` là số tuyệt đối. Với deck 50k note mà chỉ sửa 5.001
  field, hệ thống phải đọc toàn bộ 50k note. Nên so với kích thước deck.
- `lru_cache(16384)` cho hash giá trị nguyên thủy ít tác dụng: phần lớn giá trị là duy
  nhất hoặc là list (không cache được), lại giữ tới 16k chuỗi trong mỗi worker.
- Guard "field không có trong journal" chỉ phủ các note đã có trong journal. Thay đổi
  không ghi journal trên note khác vẫn không bị phát hiện. Đây là một lớp guard, trong
  khi bạn ưu tiên sửa writer.
- `semantic_fields` trong media normalizer giờ chứa mọi field có thay đổi, nên tên
  biến gây hiểu nhầm.

## 5. Dư địa còn lại để cải thiện

| Hạng mục | Hiện trạng | Hướng xử lý |
|---|---|---|
| Ghi release: INSERT 91k atoms + DELETE journal | 13,9 s + 4,3 s (probe trước; Gemini không đổi phần này) | Lọc journal theo revision rồi bỏ DELETE khỏi đường publish (audit 4.6); job nền khi production chạm ngưỡng |
| Preview vẫn dựng lại toàn bộ diff cho mỗi trang/bộ lọc/tìm kiếm | ~3,1–3,7 s mỗi lần (máy đang tải) | Cache theo `(item, working_revision, head)` có TTL; đo bộ nhớ trước |
| Frontend chuyển sang `/maintenance` khi release lỗi; `retry: 1`; idempotency key mất khi reload | Chưa đổi | Audit 4.3 (chỉ frontend, rẻ) |
| Auto-publish tạo một release cho mỗi batch; cập nhật subscriber đồng bộ | Chỉ thêm savepoint | Gom về `before_commit` một lần mỗi transaction (audit 4.11) |
| N1 vẫn chạy full vì journal `reading` lỗi thời | Writer chưa xác định; lần publish thành công kế tiếp sẽ xóa journal | Tìm script ngoài luồng (audit 4.1) |
| Hash khi publish | 1,5 s cho 91k change rows | Nhỏ; để sau |

## 6. Thứ tự đề xuất

1. Sửa 4.1/4.2 (mốc 0 cho note không có checkpoint) và thêm hai repro vào test MySQL.
2. Sửa listener của test ở 4.3, chạy lại 8 suite trên.
3. Chốt cách hiển thị số đếm ở 4.4, và quyết định có giao đường dẫn media mới cho
   learner không (mục 2).
4. Sau đó mới tiếp tục dư địa ở mục 5, theo thứ tự: frontend, DELETE journal,
   gom auto-publish.

Giới hạn: parity chỉ kiểm trên N1, nơi mọi note có checkpoint ở sequence 1 và chỉ có 2
release. Các trường hợp biên ở mục 4 đều nằm ngoài dạng dữ liệu này. Chưa đo trên
production.

## 7. Cập nhật sau khi sửa 4.1, 4.2, 4.3

Đã sửa (chưa commit):

- `deck_release_service.py`, trong `reconstruct_release_state`: note không có
  checkpoint luôn góp mốc 1, nghĩa là phát lại lịch sử từ 0, thay vì dùng
  `introduced_sequence` của membership.
- `deck_release_service.py`, trong `_get_note_field_values_by_id_for_ids_at_release`:
  bỏ mốc `introduced_sequence - 1`. Note không có checkpoint dùng mốc mặc định 0 của
  `list_note_field_history_for_ids`.
- `tests/test_deck_release_performance_mysql.py`: thêm helper `_subdeck`/`_move`
  (ghi journal theo cách browse ghi khi chuyển deck) và 2 regression test:
  `test_moved_note_without_checkpoint_keeps_values_written_before_the_move`,
  `test_reconstruct_replays_history_when_only_moved_notes_without_checkpoint_remain`.
- `tests/test_template_deck_release.py`: listener `abort_commit` bỏ qua khi đang ở
  transaction lồng nhau, tức lần release SAVEPOINT của auto-publish.

Kiểm chứng:

- Chạy lại 8 suite ở mục 3 (`FLAMA_MYSQL_TESTS=1`): **79 test, OK**, gồm 2 test mới.
  Hai kịch bản này fail trên code Gemini trước khi sửa và pass trên `HEAD`.
- Probe N1 trên code đã sửa: mọi digest (summary/items preview, manifest hash,
  change rows, state tái dựng, giá trị theo ID, working state) khớp `HEAD`. Phần tăng
  tốc giữ nguyên: preview 3,05–3,77 s với 17 SQL và ~217k logical reads; tái dựng
  0,91 s với 98,5k reads (máy vẫn có tải khác).

Đánh đổi: deck có **bất kỳ** note đang hiệu lực nào không có checkpoint (tức có note
thêm sau release đầu) sẽ quay về truy vấn lịch sử cũ khi tái dựng toàn deck. Chi phí
khi đó bằng `HEAD`, không tệ hơn trước khi Gemini sửa. Nếu muốn tăng tốc cả trường hợp
này, có thể tách truy vấn: atoms `≥ checkpoint + 1` cho note có checkpoint, cộng đủ
lịch sử theo ID cho note không có checkpoint. Chưa làm.
