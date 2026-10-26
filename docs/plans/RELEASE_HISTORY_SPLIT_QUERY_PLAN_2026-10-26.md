# Kế hoạch tách truy vấn lịch sử release cho note không có checkpoint

Ngày: 2026-10-26. Baseline: commit `09e0dc81`
(`perf(release): read release history and source notes by checkpoint and field ID`).
Trạng thái: **đã triển khai bước 1–4** (xem [mục 8](#8-kết-quả-triển-khai)). Bước 0
(đo production) chưa làm. Không thêm bảng, cột hay index.

Liên quan: [`RELEASE_DECK_GEMINI_OPTIMIZATION_REVIEW_2026-10-26.md`](../logs/RELEASE_DECK_GEMINI_OPTIMIZATION_REVIEW_2026-10-26.md) (mục 7).

## 1. Vấn đề

Release chỉ ghi checkpoint cho note có mặt ở **release đầu tiên**. Note thêm sau đó
không có checkpoint. Sau bản sửa 4.1/4.2, những note này phải phát lại toàn bộ lịch sử
(mốc 0) vì membership của chúng được tạo lại khi chuyển deck mà không sinh atom giá
trị mới.

Hiện có hai đường đọc bị ảnh hưởng.

**A. Tái dựng toàn deck** (`reconstruct_release_state`, `deck_release_service.py:452-470`).
Chỉ cần một note đang hiệu lực không có checkpoint là `min_note_field_seq = 1`, và
`list_release_history_changes` (`deck_release_repository.py:359`) quay về truy vấn cũ.
Truy vấn cũ duyệt **toàn bộ atom của deck** rồi mới lọc theo checkpoint. Với deck cỡ N1,
đó là 162.680 dòng để giữ lại vài trăm, mất ~0,73 s ở server và ~1,2 s phía client, cùng
~600k logical reads. Đây là chi phí của mỗi preview/publish đi đường full.

**B. Đọc giá trị theo nhóm note** (`list_note_field_history_for_ids`,
`deck_release_repository.py:601-640`). Đường này phục vụ learner (overlay, browse),
change request, Connect và giá trị base của sparse diff. Nhóm note không có checkpoint
dùng `DeckRelease.sequence_no > 0`, nên join bắt đầu từ `deck_releases`.

`EXPLAIN ANALYZE` trên N1 (500 note ID, release 1):

| Dạng truy vấn | Plan MySQL chọn | Dòng duyệt | Thời gian |
|---|---|---:|---:|
| Join `deck_releases` (dạng hiện tại), ID có atom | `ix_deck_release_changes_diff_cursor (release_id, entity_kind)` rồi lọc `entity_id` | 162.368 | 1,245 s |
| Như trên, ID không có atom nào | như trên | 162.368 | 0,349 s |
| `release_id IN (…)` không join, ID có atom | range trên `ix_deck_release_changes_entity_history (entity_kind, entity_id, …)` | 8.000 | 0,066 s |
| Như trên, ID không có atom | range trên index đó | 0 | 0,010 s |
| Join kèm hint `INDEX(ix_…_entity_history)` | range rồi lookup PK `deck_releases` | 8.000 | 0,048 s |

Kết luận đo: chi phí nằm ở **cách join khiến MySQL đi từ `deck_releases`**, không phải
do thiếu index. Index `ix_deck_release_changes_entity_history` đã có sẵn và được chọn
khi bỏ join.

**Mức độ phổ biến:** trong DB local, cả 22 listing đều có 0 note đang hiệu lực mà không
có checkpoint, nên hiện chưa gặp đường chậm này ở local. Bất kỳ deck nào thêm note sau
release đầu sẽ gặp. Số deck như vậy trên production **chưa đo** (bước 0 bên dưới).

## 2. Mục tiêu và bất biến

- Note không có checkpoint vẫn phát lại **đủ lịch sử từ mốc 0**. Không suy mốc từ
  membership.
- Note có checkpoint chỉ đọc atom có sequence > checkpoint của nó.
- Kết quả giữ nguyên từng byte: state tái dựng, giá trị theo ID, manifest/change rows.
- Không thêm hay đổi index, không DDL, không đổi định dạng release. Ưu tiên không dùng
  index hint.
- Chi phí đọc tỉ lệ với số atom **cần dùng**, không theo tổng số atom lịch sử của deck.

## 3. Thiết kế

### 3.1. Helper chung: atom note-field theo ID, không join `deck_releases`

Thêm vào repository một hàm, ví dụ `list_note_field_atoms_for_ids`:

1. Lấy danh sách release đã publish của deck trong khoảng sequence cần đọc, chỉ cột `id`
   và `sequence_no`. Truy vấn này nhỏ: số dòng bằng số release.
2. Chạy `SELECT … FROM deck_release_changes WHERE release_id IN (:ids) AND
   entity_kind = 'note_field' AND entity_id IN (:chunk)`, chia theo nhóm 500 ID.
   Không join `deck_releases`, để MySQL chọn range trên `ix_…_entity_history`.
3. Trả về Row cùng các cột với `_build_history_changes_query(content_only=True)`, sắp
   theo `(release_sequence_no, id)`.

Hai lưu ý cần ghi trong code:

- Danh sách release lấy theo trạng thái `published` và `deck_item_id`, nên điều kiện
  publish/deck vẫn đầy đủ như khi join.
- Deck có rất nhiều release làm `IN` dài ra. Đặt ngưỡng; nếu vượt thì chia khoảng
  sequence, hoặc chuyển sang lọc `release_sequence_no BETWEEN` kèm điều kiện deck
  (đo lại trước khi chọn).

### 3.2. Đường A: tái dựng toàn deck

Trong `reconstruct_release_state`, sau khi đã có `latest_checkpoints` và
`active_note_ids`:

- `m` = nhỏ nhất của `checkpoint + 1`, **chỉ tính trên note có checkpoint**. Không có
  note nào có checkpoint thì `m = 1`.
- **Truy vấn 1 (schema):** atom `field_def`/`template` đến `target_sequence`. Đã có
  trong nhánh mới của `list_release_history_changes`.
- **Truy vấn 2 (note có checkpoint):** atom `note_field` ở release có sequence ≥ m.
  Giữ cách chặn join `DeckRelease.sequence_no >= m`. Plan hiện tại tốt vì chỉ chạm các
  release mới. **Bỏ** outer join với bảng dẫn xuất `_latest_note_checkpoint_sequences`
  (GROUP BY toàn bộ checkpoint của deck, ~35–46 ms ở N1): reconstruct đã có
  `latest_checkpoints` và đã bỏ atom ≤ checkpoint trong Python
  (`deck_release_service.py`, vòng `for change in note_changes`).
- **Truy vấn 3 (note không có checkpoint):** dùng helper 3.1 cho các note đang hiệu lực
  không có checkpoint, giới hạn ở release có sequence **< m**. Atom ≥ m của các note này
  đã nằm trong truy vấn 2, nên hai tập không trùng và không cần khử trùng.
- Gộp ba tập, sắp theo `(release_sequence_no, id)` như hiện tại.

Thay đổi giao diện gợi ý: `list_release_history_changes(...,
min_note_field_sequence=m, full_history_note_ids=[...])`. Repository chạy truy vấn 3
khi danh sách khác rỗng. Bỏ heuristic `_min_note_field_sequence_after_checkpoints`
(`deck_release_repository.py:285`), vì nó giả định checkpoint chỉ có ở sequence 1.
Caller không có membership thì đi đường cũ, tường minh.

### 3.3. Đường B: đọc giá trị theo nhóm note

Trong `list_note_field_history_for_ids`:

- Nhóm có checkpoint (`seq > 0`): giữ nguyên, vì join bị chặn bởi
  `DeckRelease.sequence_no > seq` và chỉ chạm release mới.
- Nhóm `seq = 0` (không có checkpoint): chuyển sang helper 3.1 thay vì join.

Phần này độc lập với đường A, có thể tách thành PR riêng nếu muốn giảm rủi ro.

### 3.4. Phương án đã cân nhắc, không chọn lúc này

| Phương án | Lý do không chọn |
|---|---|
| Suy mốc từ `introduced_sequence` của membership (cách Gemini dùng) | Sai khi chuyển deck: membership được tạo lại mà không có atom (lỗi 4.1/4.2 đã tái hiện) |
| Suy mốc từ membership **đầu tiên** của note | Đúng với dữ liệu ghi bằng code hiện tại, nhưng phụ thuộc cách backfill membership cho release cũ; không chứng minh được với dữ liệu legacy |
| Ghi checkpoint cho mọi note mới khi release | Giải quyết tận gốc cho release sau này, nhưng đổi định dạng release, tăng write amplification, release cũ vẫn cần backfill. Để dành nếu đo production cho thấy note không có checkpoint chiếm đa số |
| Thêm index hoặc dùng index hint | Không cần: bỏ join là MySQL đã chọn index có sẵn. Hint chỉ là dự phòng nếu plan đổi trên production |

## 4. Các bước triển khai

0. **Đo production (chỉ đọc, principal SELECT-only):** số listing có note đang hiệu
   lực mà không có checkpoint, số note như vậy, số release mỗi deck, và `EXPLAIN` hai
   dạng truy vấn trên deck lớn nhất. Nếu gần như không có deck nào, ưu tiên đường B
   (learner đọc) trước đường A.
1. Viết helper 3.1, kèm test MySQL so kết quả với truy vấn join hiện tại trên cùng
   fixture (cùng tập dòng, cùng thứ tự).
2. Đổi đường B (3.3). Chạy test release và overlay/browse liên quan.
3. Đổi đường A (3.2): thêm `full_history_note_ids`, bỏ outer join checkpoint trong
   nhánh tách, bỏ heuristic.
4. Đo lại N1 và một fixture có note không checkpoint (mục 5), rồi cập nhật báo cáo.

## 5. Kiểm chứng

**Test MySQL** (`tests/test_deck_release_performance_mysql.py`, rollback-only):

- Giữ 2 regression hiện có về note chuyển deck không có checkpoint.
- **Parity tách/không tách:** fixture gồm note có checkpoint, note thêm sau release 1,
  note chuyển deck, note bị xóa rồi thêm lại, field bị xóa. So
  `reconstruct_release_state` theo đường tách với kết quả đường cũ (ép
  `min_note_field_sequence=1`) ở **mọi** release.
- **Parity đường B:** `get_note_field_values_by_id_for_ids_at_release` trước/sau trên
  cùng fixture, gồm note không có membership (nhánh tương thích).
- **Kiểm đường đi:** đếm SQL hoặc patch repository để chắc đường tách được dùng khi có
  note không checkpoint, và truy vấn 3 không chạy khi danh sách rỗng.
- Thứ tự gộp: một note có atom ở cả hai phía của `m`.

**Đo hiệu năng** (theo `AGENTS.md`: ghi cả thời gian lẫn delta
`Innodb_buffer_pool_read_requests` và `Innodb_buffer_pool_reads`):

- N1: digest khớp `09e0dc81`; tái dựng không chậm hơn (~0,9–1,0 s, ~98k reads).
- Fixture rollback-only cỡ lớn, ví dụ 5.000 note ở release 1 cộng 500 note thêm sau:
  tái dựng và đọc giá trị trước/sau. Kỳ vọng số dòng duyệt ≈ số atom của 500 note cộng
  atom ở release mới, thay vì toàn bộ atom release 1.
- Ghi rõ runtime buffer pool (local đang 1 GiB, mục tiêu `my.ini` 128M) và tải máy lúc
  đo.

**Suite cần chạy lại:** cùng 8 suite trong báo cáo review: `test_deck_release_api`,
`test_deck_release_performance_mysql`, `test_deck_auto_publish_and_auto_update`,
`test_deck_install_rebase_flow`, `test_owner_note_dirty_tracking_services`,
`test_flashcard_media_normalizer`, `test_template_deck_release`,
`test_deck_release_schema`. Thêm test overlay/browse nếu đổi đường B.

## 6. Rủi ro và rollback

- **Optimizer đổi plan** theo statistics hoặc kích thước `IN`: theo dõi bằng `EXPLAIN`
  trong probe. Nếu production chọn plan xấu, hint `INDEX(ix_…_entity_history)` là dự
  phòng; không thêm index.
- **Gộp sai thứ tự hoặc trùng atom** làm state sai: được chặn bởi test parity ở mọi
  release.
- **Deck có rất nhiều release** làm `release_id IN` dài: đặt ngưỡng chia khoảng (3.1).
- **Rollback:** thay đổi chỉ ở tầng đọc, không đụng dữ liệu hay schema. Revert commit
  là quay về hành vi `09e0dc81`.

## 7. Ước tính lợi ích

Chưa đo end-to-end; số dưới đây suy từ `EXPLAIN ANALYZE` của từng truy vấn.

- Đường A: với deck cỡ N1 có note thêm sau release đầu, tái dựng tránh duyệt ~162k atom
  (~0,7 s server, ~1,2 s client, ~500k logical reads mỗi preview/publish đi đường full).
  Truy vấn 3 tốn khoảng 0,01–0,07 s mỗi nhóm 500 note.
- Đường B: mỗi nhóm 500 note không có checkpoint giảm từ ~0,35–1,25 s xuống
  ~0,01–0,07 s. Lợi ích nhân theo số nhóm mỗi lần learner hoặc owner đọc.

Probe dùng cho kế hoạch: `output/split_plan_probe.py` (chỉ đọc; `output/` bị gitignore).

## 8. Kết quả triển khai

**Code** (chưa có bước 0 đo production):

- `deck_release_repository.py`
  - Thêm `list_note_field_atoms_for_ids`: lấy release ID đã publish của deck trong
    khoảng sequence, rồi lọc `release_id IN (…)` theo nhóm 500 Note ID, không join
    `deck_releases`.
  - `list_release_history_changes` nhận `full_history_note_ids`. Nhánh tách chỉ chạy
    khi caller truyền `min_note_field_sequence`, và không còn outer join bảng dẫn xuất
    checkpoint.
  - Xóa heuristic `_min_note_field_sequence_after_checkpoints`. Caller không có
    membership đi đường cũ, tường minh.
  - `list_note_field_history_for_ids`: nhóm `seq = 0` (kể cả khi không truyền
    `checkpoint_sequences`) đi qua helper. Nhóm có checkpoint giữ join chặn theo
    sequence.
- `deck_release_service.py` (`reconstruct_release_state`): `m` chỉ tính trên note có
  checkpoint; note đang hiệu lực không có checkpoint đi vào `full_history_note_ids`.
  Atom ≤ checkpoint vẫn bị bỏ trong vòng replay Python.
- `tests/test_deck_release_performance_mysql.py`: thêm
  `test_split_history_matches_full_scan_for_notes_without_checkpoint`. Test dựng
  5 release (note thêm sau, chuyển subdeck, rời listing rồi quay lại). Ở mỗi release,
  test so `reconstruct_release_state` theo đường tách với đường quét cũ, so giá trị
  đường B với state, và chặn `_latest_note_checkpoint_sequences` trong đường tách.

**Kiểm chứng:**

- Kiểm tra bằng đột biến: patch helper trả rỗng thì 4 test fail (gồm 2 regression về
  chuyển deck và test parity ở release 2–5).
- 13 suite, 182 test, OK: 8 suite release cùng `test_browse_notes_mysql`,
  `test_browse_mysql_contract`, `test_deck_change_request_flow`, `test_flama_connect`,
  `test_field_identity_cutover`, với `FLAMA_MYSQL_TESTS=1` và
  `FLAMA_BROWSE_MYSQL_TESTS=1`. Một lần chạy song song với benchmark 30k note bị lock
  wait; chạy lại khi không có tải song song thì pass.
- SQL thật của helper trên N1 (500 note, release 1): range trên
  `ix_deck_release_changes_entity_history`, 34,8 ms ở server cho 8.000 dòng.
- N1: mọi digest (preview, manifest, change rows, state, giá trị theo ID) khớp `HEAD`
  trước bản tối ưu. Tái dựng 0,81 s (trước khi tách 0,91 s), nhờ bỏ bảng dẫn xuất
  checkpoint. Mọi note của N1 đều có checkpoint nên không đi qua truy vấn 3.

**Benchmark fixture rollback-only** (`output/split_benchmark.py`; baseline atomic như
N1; min 3 lần; buffer pool runtime 1 GiB; máy có tải khác):

| Fixture | Phép đo | Đường cũ | Đường tách |
|---|---|---:|---:|
| 5.002 + 500 note (11k atom) | Tái dựng | 0,306 s / 81k reads | 0,352 s / 37k reads |
| | Đọc 500 note không checkpoint | 0,087 s / 40k reads | 0,071 s / 10k reads |
| 30.002 + 2.000 note (64k atom) | Tái dựng | 2,661 s / 477k reads | 1,984 s / 212k reads |
| | Đọc 2.000 note không checkpoint | 1,367 s / 816k reads | 0,416 s / 46k reads |

Với deck nhỏ, tái dựng theo đường tách có thể chậm hơn vài chục ms vì phải chạy thêm
truy vấn nhỏ, dù số reads giảm hơn một nửa. Lợi ích tăng theo số atom lịch sử. Chưa đo
phía ghi, vì thay đổi chỉ nằm ở tầng đọc.
