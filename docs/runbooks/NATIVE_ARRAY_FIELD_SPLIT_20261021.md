# Tách trường text sang native array — diễn tập 2026-10-21

Diễn tập trên bản sao production mới nhất, **chưa chạy trên production**. Production lúc lấy dump: code `cec70bc3`, Alembic `20261014_000068`, MySQL `flama` / server `chung`.

## 1. Diễn tập migrate trước

Dump `mysqldump --single-transaction` lúc 2026-10-20 23:13 UTC (186 MB gzip, SHA-256 `5f42db18…85d8cf`, kiểm `Dump completed`), restore vào DB riêng `flama_prod_rehearsal_20261021` trên MySQL local (230 s, 114 bảng, 41.613 note). Chạy đúng entry point deploy `deploy/migrate_database.py --writers-quiesced`:

| Bước | Thời gian | Kết quả |
| --- | --- | --- |
| `000068 → 000069` (template marketplace listing) | 7 s | ALGORITHM=INSTANT/INPLACE |
| `000069 → 000071` (note type releases, template sync jobs — **chưa commit, của agent khác**) | 9 s | 2 bảng, 2 cột mới |
| `000071 → 000072` (sửa lệch schema, bên dưới) | < 5 s | |
| Thứ tự của nhánh: `000068 → 000069 → 000072` (restore dump mới) | ~24 s kể cả khởi động app | Chỉ `alembic_version` đổi; `mcp_access_tokens`, `payment_orders` khớp chuỗi dựng mới |

Fingerprint (row count + CRC theo cột gốc) của 114 bảng trước/sau: **không bảng nào đổi dữ liệu**, chỉ `alembic_version`.

### Lệch schema chỉ có trên production

So schema production sau migrate với một DB dựng mới từ chuỗi migration (`scripts/bootstrap_historical_schema.py` + upgrade): các bảng cũ do `db.create_all()` thời trước tạo có hình dạng cũ mà chuỗi migration không sửa.

- `mcp_access_tokens.expires_at` NOT NULL. Token "không hết hạn" (`expires_in_days` rỗng hoặc 0) ghi NULL nên **lỗi 500** trên production. Bảng còn thiếu unique `refresh_token_hash`, index `client_id`, `refresh_token_expires_at` và FK `client_id → oauth_clients` (SET NULL).
- `payment_orders.user_id` có FK `ON DELETE CASCADE`: xoá user sẽ xoá luôn lịch sử thanh toán. Model và chuỗi migration dùng `SET NULL`.

Migration `20261021_000072_repair_legacy_schema_drift.py` kiểm tra trước rồi mới sửa: DB dựng mới không đổi gì. Nếu gặp bản ghi trùng hoặc mồ côi thì dừng để operator xem. Trên bản sao: 7 token, 3 refresh hash, không trùng, không mồ côi. Sau sửa, ORM lệch production từ 18 xuống 11 điểm, phần còn lại vô hại: độ rộng VARCHAR của enum, index thường trùng với index unique, JSON nullable, DOUBLE/Float.

**Thứ tự migration:** 000072 nối thẳng sau `20261019_000069` và được commit cùng nhánh array. Số 000070/000071 đã dành cho tính năng note type release của agent khác (chưa commit). Trong checkout chính, 000070 của họ được nối lại sau `20261021_000072`, nên chuỗi vẫn một head: 069 → 072 → 070 → 071. Cũng trong checkout chính đã sửa lỗi SQLite của 000070: `op.create_foreign_key` chỉ chạy trên MySQL. Hai sửa đổi đó nằm trong file chưa commit của họ.

Với thứ tự này, DB dev `nihongo` (đang ở `000071`) được Alembic coi là đã qua 000072, nên `db upgrade` sẽ không chạy bản sửa trên DB đó. DB dev cũng có cùng lệch như production (kiểm 2026-10-21), nên cần sửa riêng, ví dụ gọi `upgrade()` của migration này trong một Alembic context trỏ tới `nihongo`. Production không bị ảnh hưởng: nó ở `000068` và sẽ đi `069 → 072`.

## 2. Phạm vi chuyển sang array

Cả 22 deck chia sẻ đều của user 1, với 28 lượt cài. Trên production không có override nào của người clone (0 note/field override, 0 field thêm).

**Đợt 1 (đã diễn tập):** note type `Flama Standard Vocabulary` (`e2f310a8…`, 35.112 note, 18 deck chia sẻ, 20 lượt cài). Gồm `meaning_jp`, `meaning_vi`, `usage_jp`, `usage_vi`, `example_jp`, `example_vi`, và 6 trường cùng tên của `Flama Standard Vocabulary Clone` (0 note, vì dùng chung template Default). Manifest: `scripts/migrations/field_array_split_manifest_20261021.json`.

Chỉ tách ở những chỗ người học đã thấy là xuống dòng: `<br>`, newline (renderer in thành `<br>`), và `$`, ký tự template Default tự đổi thành `<br>` qua `auto-split`. Không tách dấu phẩy hay chấm phẩy. Item giữ rich-text an toàn. Dấu phân tách nằm **bên trong** thẻ HTML không cắt phần tử mà được đổi tại chỗ thành `<br>`. Vị trí rỗng được giữ nguyên.

Giữ nguyên richtext: `additional_note_*` (văn xuôi, `<ul><li>` lồng).

**Đợt 2 (đã diễn tập):** manifest `scripts/migrations/field_array_split_manifest_wave2_20261021.json`.
- En4Everyone (`6b2a8fec…`, 4.122 note, deck 382 và 1447, 5 lượt cài): `Word Family`, `Example`, `Example_VI`. Tách theo `<br>`, xuống dòng và `;`, vì template Advanced Vocabulary auto-split theo `/;\s*/`. **Không tách `$`**: ở bộ này `$` là tiền thật (`$25,000`). `;` của thực thể HTML (`&amp;`, `&nbsp;`) không bao giờ bị tách.
- 文法N1 (`4fc2eb8e…`, 90 note, deck 1398, 3 lượt cài): `meaning`, `structure`, `notes`, `additional_example`, `example_vi`. Tách theo `<br>` và xuống dòng. Template Grammar & Literary Quotes có 1 người subscribe. Bản sao của họ chỉ đổi khi họ tự cập nhật, và chuỗi cũ vẫn hiển thị như trước.
- Giữ text: `Note_EN`/`Note_VI` (văn xuôi, `;` là dấu câu); `note_jp`/`note_vi` (cấu trúc lồng `■`/`・` và dòng `-` rác).

## 3. Công cụ

- `scripts/migrations/field_array_split.py` gồm `plan`, `apply`, `restore`, `verify`, `release`. Cơ chế giống `native_array_cleanup.py`: ghim ID/owner/kiểu nguồn của field, hash template đã duyệt, khoá row, kiểm preimage/postimage, tắt auto-publish trong transaction, ghi template version, audit log, journal dirty. Plan dừng nếu: có note của user khác, có clone override `field_type`, có item mà validator sẽ đổi khác ngoài escape thực thể, hoặc template có attachment ngoài phạm vi.
- Plan **cho phép duy nhất** việc validator escape `&`/`<`/`>` thành entity (chữ hiển thị giữ nguyên), vì đây đúng là dạng app lưu khi người dùng tự gõ. 87 giá trị bị ảnh hưởng.
- `native_array_templates.modernize_v2`: item `{{{.}}}` giữ markup, nâng được template đã có v1 (đổi initializer tại chỗ). Holder mang `data-native-array-legacy="$"`: một chuỗi legacy đơn lẻ còn chứa `$` sẽ để formatter cũ của template xử lý. Lý do: 22/27 release cũ **không có template pin**, nên clone pin release cũ render bằng template live của chủ deck với dữ liệu chuỗi cũ.
- `release --update-installs none|at_head|all` phát hành release cho mọi deck item đang published của note type và cập nhật install. **Lưu ý:** release gồm mọi thay đổi chưa phát hành của chủ deck (trước khi chuyển đã có hàng nghìn entity dirty tồn đọng), không chỉ phần array.

## 4. Kết quả diễn tập trên bản sao production

Plan: 12 field, 35.112 note, 3 template (`Default Flama Flashcard`, `Gõ cách đọc`, `Gõ nghĩa`), 0 override clone, 0 đổi schema.

Số item sau khi tách, áp quy tắc dọn và bản sửa (run 3):

| Trường | 0 item | 1 | 2 | 3 | ≥4 | bỏ vị trí trống | tách số thứ tự |
| --- | --- | --- | --- | --- | --- | --- | --- |
| meaning_jp | 22 | 31.997 | 2.846 | 237 | 7 | 11 | 9 |
| meaning_vi | 22 | 32.553 | 2.382 | 149 | 4 | 9 | 17 |
| usage_jp | 2.455 | 29.363 | 1.287 | 1.277 | 727 | 2 | 0 |
| usage_vi | 2.494 | 29.616 | 1.215 | 1.134 | 650 | 2 | 45 |
| example_jp | 21 | 12.146 | 18.842 | 4.094 | 9 | 0 | 0 |
| example_vi | 30 | 12.145 | 18.842 | 4.094 | 1 | 0 | 0 |

Không còn item rỗng. Xem mục "Danh sách cần biên tập" bên dưới.

Giao dịch trên MySQL (lượt 1): lỗi giả ở note thứ 20.000 rollback sạch. Apply 197 s, verify postimage đạt, plan lại bị từ chối (field đã là array). Restore 183 s, verify preimage đạt, apply lại 205 s, verify đạt. Lượt 2 (restore dump mới, code đã sửa): apply 230 s, verify đạt. Sau apply chỉ đổi `notes`, `field_defs`, `templates` (+9 version), `note_types.field_schema_revision`, `deck_working_dirty_entities` (+173.700), `deck_marketplace_items.working_revision`, `audit_logs`, và 6 identity definition của note type Clone rỗng. Card, tiến độ học, review, release, checkpoint, install, override và media không đổi.

### Kiểm tra hiển thị (lượt 2)

Render bằng đúng đường đi của study (`build_effective_study_card` + `render_template_pair`), cho owner và 20 lượt cài. Sau đó chạy script của từng mặt card trong jsdom và so DOM cuối đã chuẩn hoá khoảng trắng. Mẫu xác định: 1/25 card cộng mọi note có ca đặc biệt, tổng 7.530 card owner và 1.924 card qua clone.

| So sánh | Mặt card | Kết quả |
| --- | --- | --- |
| Trước → sau apply. Owner: chỉ cho phép `$` → xuống dòng trong khối đã chuyển của 2 template gõ. Clone (vẫn ở release cũ): phải giống hệt | 18.908 | **18.908 khớp**, 0 lỗi script |
| Sau release + cập nhật: clone so với owner cùng card (bỏ media) | 1.038 card | **1.038 khớp** |

Khác biệt trước→sau release của clone (390 mặt) là nội dung tồn đọng mà release mang tới, ví dụ ảnh `diagram` chủ deck thêm sau release cũ. Đó không phải thay đổi do array.

Release (lượt 2): 17 deck đã published được phát hành bản mới, có template pin. `--update-installs all`: **19/19 install cập nhật, 0 xung đột**. Install `legacy_snapshot` đọc note live nên không cần cập nhật. Mỗi install nhận tới 81.428 thay đổi. Với deck 415: 60.888 thay đổi là 6 trường array; 20.305 là `reading`/`translation_vi` từ cleanup 2026-10-11 chưa từng phát hành (NA-03); còn lại là vài sửa media/hán việt. `deck_release_changes` tăng từ 156k lên 396k dòng.

### Đợt 2

Chạy trên cùng DB sau đợt 1. Plan: 8 field, 4.212 note, 3 template (`Advanced Vocabulary Card`, `Gõ chép chính tả`, `Grammar & Literary Quotes Card`), 0 override, không giá trị nào bị chặn. `Word Family` thường có 4–5 item. Apply 24 s, verify đạt.

- Trước → sau apply: **5.782/5.782 mặt card khớp**. `Gõ chép chính tả` trước đây in nguyên `;` giữa các câu trong `Example`/`ExampleTranslation`, giờ mỗi câu một dòng. Template Advanced Vocabulary hiển thị y như cũ.
- Release 3 deck. **8/8 install cập nhật, 0 xung đột** (456–14.073 thay đổi mỗi install). Clone so với owner: **433/433 card khớp** (bỏ media).
- Harness truyền `media_assets=[]`. Audio của clone là ID media trần nên chỉ hiện khi có media của note, mà route study vẫn luôn truyền media đó. Khung audio thiếu trong so sánh vì vậy không phải lỗi production.

### Danh sách cần biên tập

Lần rà đầu có 1.551 note bị đánh dấu. Sau khi phân loại, phần lớn được xử lý ngay trong plan bằng quy tắc đã duyệt; plan vẫn kiểm preimage và `restore` hoàn tác được như phần còn lại.

| Nhóm | Note | Xử lý |
| --- | --- | --- |
| Vị trí trống do dấu phân tách thừa, giá trị rác `<li><br></li>` | 24 | `drop_blank_items`: bỏ item không có chữ hay media |
| Một bên là 1 item đánh số inline (`① … ②`, `(1) … (2)`, `1. … 2.`), đúng bằng số item bên kia | 71 | `split_numbered_pairs`: tách trước từng số, chỉ khi số chạy đúng 1..n từ đầu item |
| En4 `Example`/`Example_VI`: `;` là dấu câu (`reliable; moreover, …`), từng bị cắt thành 2 dòng | 30 item | Separator `;sentence`: không tách trước chữ thường |
| Lỗi dữ liệu thật (câu tiếng Nhật nằm ở cột tiếng Việt, cột bị đảo, hai câu nối bằng ` - ` hoặc `;`) | 15 | Tệp sửa riêng tư `--repairs` (26 bản sửa, kiểm `expected`) |

Tệp sửa riêng tư `output/native-array-rehearsal-20261021/repairs-20261021-wave{1,2}.private.json` chứa nội dung note, **không commit**. Trong đó có 10 câu là **bản dịch nháp do Claude soạn**, dùng cho các câu ví dụ trước đây không có bản dịch. Khi chạy production, chuyển tệp này qua kênh quản trị như private manifest ngày 10/11; production khác preimage thì plan sẽ dừng.

Sau xử lý, cặp `example`/`Example` lệch số item còn **0**. `content-review-20261021.csv` (riêng tư) xếp theo ưu tiên:

| Ưu tiên | Số | Việc |
| --- | --- | --- |
| 1. Bản dịch nháp | 10 | Duyệt câu dịch trước khi apply production |
| 2. Hai bên chia ý khác nhau | 28 | Chủ deck đọc lại; không ảnh hưởng hiển thị |
| 3. `meaning_vi`/`usage_vi` là một câu giải thích tổng hợp, `jp` liệt kê nhiều ý | 1.437 | Không phải lỗi: hai cột không dịch theo từng ý, template hiển thị riêng từng khối |
| 4. Đã sửa cấu trúc | 16 | Để biết |

**Cần chủ deck xác nhận (chưa sửa):** attachment `Gõ nghĩa` của `Flama Standard Vocabulary` gắn input `ExampleTranslation` (tiêu đề "Bản dịch ví dụ") vào `additional_note_vi`, còn `Gõ cách đọc` gắn vào `example_vi`. Vì thế card `Gõ nghĩa` hiện ghi chú so sánh dưới tiêu đề "Bản dịch ví dụ" cho mọi note có `additional_note_vi` (khoảng 32 nghìn). Nếu đây là nhầm, chỉ cần đổi `input_bindings` của attachment đó; không đụng tới dữ liệu note.

Kiểm hiển thị run 3 (dump mới, code nhánh, cả 2 đợt kèm bản sửa): **20.190 mặt card**; 19.923 khớp tuyệt đối; **267 khác biệt đều thuộc 124 note chủ ý sửa**; 0 khác biệt ngoài dự kiến; 0 lỗi script.

Template v2 cũng đánh dấu khối `auto-split` bao quanh holder (template Advanced Vocabulary đặt `Example` trong `<span>` bên trong khối đó). Nhờ vậy formatter cũ không cắt `;` của item array hay của thực thể `&amp;` thêm lần nữa.

### Editor array trong Browse

Item lưu theo cách validator escape (`R&amp;D`). Trước đây chế độ dòng và xem trước hiện nguyên entity. `ArrayFieldInput` nay hiện `R&D`, `1 < 2`, `->` như người dùng gõ. Khi lưu, server escape lại y như cũ. `&lt;` đứng trước chữ cái được giữ nguyên để chữ `<b>` không thành thẻ. Chế độ Code vẫn hiện đúng giá trị lưu.

### Lỗi phát hiện ở lượt 1 và đã sửa

- **Renderer server bỏ item rỗng** (lỗi đã có từ trước): chevron bỏ thân section khi item falsy, còn mustache.js vẫn render. Array có vị trí rỗng bị lệch giữa server và trình duyệt, cột ghép cặp lệch hàng khi render ở server. Lúc diễn tập có 15 note thuộc các array chuyển trước đó bị ảnh hưởng. Đã sửa: `_MustacheEmptyItem` trong `app/services/flashcard_renderer.py`, có test.
- **`\n` dạng ký tự**: renderer cũ in chuỗi gạch chéo + `n` thành `<br>` (173 giá trị). Bộ tách nay coi nó là xuống dòng.
- **Tách xuyên thẻ HTML**: `<li><br></li>` bị cắt đôi. Bộ tách nay chỉ tách ngoài phần tử.
- **Escape thực thể**: `R&D` → `R&amp;D` (87 giá trị) được chấp nhận vì chữ hiển thị giữ nguyên.

## 5. Trình tự cho production (khi được duyệt)

1. Deploy nhánh array (renderer, công cụ, template v2, editor, migration 000072). Deploy chạy `069 → 072`.
2. Dừng writer (web, Connect, Study worker, retention, CLI), backup mới, `SELECT DATABASE(), @@hostname`.
3. `field_array_split.py plan`, chạy lần lượt manifest đợt 1 rồi đợt 2, mỗi lần kèm `--repairs <tệp riêng tư của đợt đó>` (đã duyệt 10 câu dịch nháp). Plan phải khớp hash template, số note và field stats ở trên. Nếu template đã đổi, có giá trị mới không chuyển được, hoặc preimage của một bản sửa đã đổi, plan sẽ dừng để review lại. Xem danh sách `review`.
4. `apply --writers-stopped --receipt …`, rồi `verify`. Mở lại writer, smoke test owner/clone.
5. Quyết định chính sách clone (`--update-installs`), rồi `release`. Smoke test browse/study trên clone.
6. Restore bằng `restore` với đúng plan đã apply, làm trước bước `release`. Release đã phát hành thì không thu hồi được.

Plan, receipt, dump chứa dữ liệu người dùng: để ngoài repo, quyền chỉ operator đọc.
