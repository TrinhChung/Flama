# Native JSON array cleanup — 2026-10-11

## Kết quả local

Đã áp dụng trên MySQL local `nihongo` / server `chungtv`: **25 template, 68 note**, không đổi schema. Tổng số note vẫn 41.533; 108.956 slot array vẫn là JSON list, 4 key thiếu được giữ nguyên. Plan sau apply có 0 thay đổi. Kết quả production được ghi riêng bên dưới.

Source sửa 12 mặt HTML thuộc Default, Advanced Vocabulary và 5 họ typing. Giữ CSS, richtext, audio, script định dạng prose còn dùng `$`. Renderer giữ nguyên contract đưa list vào Mustache; template dùng vòng lặp để nhận ranh giới item và bỏ wrapper tạm trước khi chạy script tương tác. Native item không bị split theo dấu phẩy/chấm phẩy, không mất thứ tự, mục lặp hoặc vị trí rỗng. Legacy string chỉ được tách theo xuống dòng.

Dữ liệu lệch cột đã được đối chiếu từng preimage: 66 note chuyển `Synonym_VI → Antonym`, `Antonym → Word Family`, `Antonym_VI → Note_EN`, `Word Family → Note_VI`. Hai note `failure` có **bản tiếng Việt** của antonym trong `Synonym_VI`, nên chuyển sang `Antonym_VI`; thiếu bản English được giữ rỗng. Không sinh bản dịch mới. Nội dung nguồn được giữ trong field đúng và private plan/backup.

**113 note còn cần biên tập nội dung/bản dịch**, bao gồm các note vừa chuyển cột. Đây không phải 113 note đã làm sạch hoàn toàn. Note `spacious` có lệch nhiều cột và item `bố cục thoáng roomy`; chưa có bằng chứng cho phép đơn giản xóa 3 từ. Nó được giữ nguyên, nằm trong danh sách unresolved.

## Công cụ bàn giao

- `scripts/migrations/native_array_cleanup.py`: `plan`, `apply`, `restore`, `verify`; nhận ID/owner/type và hash template đã duyệt. Không match tên NoteType.
- `scripts/migrations/native_array_manifest_20261011.json`: 79 FieldDef và 25 template có ID cụ thể; FieldDef ngoài scope cutover cũ được đánh dấu optional nếu chưa tồn tại. Nếu có thì vẫn phải khớp owner/type. Không tự mở rộng scope khi production khác local.
- `scripts/migrations/native_array_production_manifest_20261011.json`: scope đã review cho `flama` / `chung`, gồm 20 FieldDef hiện đang là array và 9 template. Giữ nguyên 49 field text/richtext ở các bản sao; bốn template thư viện trên production không gắn NoteType, được kiểm tra bằng ID/owner/input schema. Các khác biệt HTML so với local là định dạng/layout được cutover trước đó; modernize chính nội dung production, giữ CSS/audio/prose của nó. Chỉ private manifest production mới có 68 repair preimage.
- `scripts/migrations/native_array_audit.py`: snapshot/đối soát dữ liệu trước/sau, bao gồm release/checkpoint/pin, clone overrides, card/progress/media, schema field và version template cũ. Chỉ chấp nhận đúng các thay đổi note trong plan; version mới, audit log và working journal là thay đổi dự kiến.
- `output/native-array-cleanup/private-manifest.json`: 68 repair có expected/desired values; **riêng tư, không commit**. Public manifest không chứa nội dung note; mặc định không sửa lệch cột. Muốn áp dụng repair phải dùng manifest riêng và `--include-repairs`.

Plan, audit snapshot, receipt, dump chứa dữ liệu riêng tư hoặc metadata. Đặt ngoài repo trên production, quyền chỉ operator đọc; không đưa lên PR. `--writers-stopped` là xác nhận của operator, không tự dừng service. `apply/restore` lock và kiểm tra mọi row sẽ sửa trước khi ghi; cả nội dung, lịch sử template và working journal commit trong một transaction. Hash toàn JSON note cũng bảo vệ field ngoài scope khỏi bị ghi đè. Backfill giữ cả dòng rỗng ở giữa các item; nếu validation sẽ trim/sanitize nội dung đang lưu thì plan từ chối để review riêng.

Các cờ auto-publish bị tạm tắt trong transaction, giữ đến hết history/publication hooks rồi khôi phục. Không phát hành release mới, không đổi release pin hoặc learner overlays. `working_revision`, dirty journal và thời điểm cập nhật marketplace được phép tăng để phản ánh source đã đổi. Restore tạo version/journal mới, không xóa lịch sử.

## Preflight production

1. Đưa bản code native array và các source template đã kiểm tra vào release triển khai. Không chạy lại `array_cutover.py` cũ để thực hiện cleanup này: đó là cutover sang string mỗi dòng, không phải backfill JSON list.
2. Xác nhận target bằng `SELECT DATABASE(), @@hostname;` trong chính môi trường sẽ chạy migration. Xác nhận code/manifest khớp release, FieldDef đã là `array`. Nếu field còn text hoặc hash template khác, dừng để review diff/điều chỉnh scope; không thay hash cho qua kiểm tra.
3. Dừng toàn bộ writer của app web, Connect, cron/worker, CLI import và các phiên edit. Dùng CLI ở `audit_mode=True`; không khởi động `wsgi.py` để làm preflight vì startup thường chạy maintenance.
4. Tạo **backup production mới**, kiểm tra SHA-256 và restore thử lên DB riêng. Backup local không thay thế được backup production. Ví dụ Bash, dùng credential file riêng đã có của operator:

```bash
umask 077
set -o pipefail
TASK_DIR=/var/backups/flama/native-array-20261011
mkdir -p "$TASK_DIR"
mysqldump --defaults-extra-file=/secure/flama-mysql.cnf \
  --single-transaction --quick --routines --triggers --events --hex-blob \
  --set-gtid-purged=OFF --no-tablespaces "$DB_NAME" \
  | gzip > "$TASK_DIR/before.sql.gz"
gzip -t "$TASK_DIR/before.sql.gz"
sha256sum "$TASK_DIR/before.sql.gz" > "$TASK_DIR/before.sql.gz.sha256"
```

5. Gán `TASK_SERVER` theo hostname vừa đọc và `DB_NAME` theo database thật; dùng env/venv của runtime đã cấu hình credentials. Các đường dẫn trong ví dụ cần điều chỉnh theo host. Tạo snapshot rồi plan mới khi writers đã dừng:

```bash
python scripts/migrations/native_array_audit.py snapshot \
  --snapshot "$TASK_DIR/before-audit.json" \
  --expect-database "$DB_NAME" --expect-server "$TASK_SERVER"

python scripts/migrations/native_array_cleanup.py plan \
  --plan "$TASK_DIR/plan.json" \
  --expect-database "$DB_NAME" --expect-server "$TASK_SERVER"
```

Để sửa 68 note đã review, thay lệnh plan bằng bản có `--manifest "$TASK_DIR/private-manifest.json" --include-repairs`. Chuyển private manifest qua kênh quản trị riêng. Production có preimage khác sẽ bị chặn; không dùng nguyên `local-plan.json` trên production. Legacy array string một item mỗi dòng được chuẩn hóa trước khi đối chiếu repair. String legacy còn dùng delimiter cũ cần review riêng, không đoán split punctuation.

6. Review summary, exact note/template IDs, before/after, unresolved và absent_optional. Không lấy số lượng local làm yêu cầu production phải bằng hệt. Nếu scope khác, phải review lại và rehearsal chính plan production trên DB riêng trước bước ghi.

## Apply và nghiệm thu

Khi plan production đã được duyệt và writers vẫn dừng:

```bash
python scripts/migrations/native_array_cleanup.py apply \
  --plan "$TASK_DIR/plan.json" --receipt "$TASK_DIR/apply-receipt.json" \
  --expect-database "$DB_NAME" --expect-server "$TASK_SERVER" --writers-stopped

python scripts/migrations/native_array_cleanup.py verify \
  --plan "$TASK_DIR/plan.json" \
  --expect-database "$DB_NAME" --expect-server "$TASK_SERVER"

python scripts/migrations/native_array_audit.py verify \
  --snapshot "$TASK_DIR/before-audit.json" --plan "$TASK_DIR/plan.json" \
  --expect-database "$DB_NAME" --expect-server "$TASK_SERVER"
```

Verify phải pass trước khi mở writer. Kiểm tra lại plan để xác nhận không còn note/template cần đổi (dùng manifest/options giống preflight và một tên plan mới). Smoke-test study/browse, typed answers từng item, audio, optional blocks, richtext và template trên source owner lẫn installed clone. Clone pin cũ vẫn dùng release cũ: muốn đưa sửa đổi đến người đã cài deck cần **phát hành release mới và rebase theo quy trình marketplace riêng**, không sửa checkpoint/release cũ trong cleanup.

## Restore

Giữ writers dừng hoặc dừng lại, dùng đúng plan đã apply:

```bash
python scripts/migrations/native_array_cleanup.py restore \
  --plan "$TASK_DIR/plan.json" --receipt "$TASK_DIR/restore-receipt.json" \
  --expect-database "$DB_NAME" --expect-server "$TASK_SERVER" --writers-stopped

python scripts/migrations/native_array_cleanup.py verify --restored \
  --plan "$TASK_DIR/plan.json" \
  --expect-database "$DB_NAME" --expect-server "$TASK_SERVER"

python scripts/migrations/native_array_audit.py verify --restored \
  --snapshot "$TASK_DIR/before-audit.json" --plan "$TASK_DIR/plan.json" \
  --expect-database "$DB_NAME" --expect-server "$TASK_SERVER"
```

Restore kiểm tra postimage toàn row trước khi ghi. Nếu note/template đã được sửa sau apply, lệnh từ chối để bảo vệ cập nhật mới; cần review merge riêng. Không restore cả dump lên DB đang có hoạt động mới.

Nếu tiến trình mất kết nối quanh thời điểm commit, đọc receipt/`.intent`, AuditLog theo checksum và chạy `verify`/audit để xác định trạng thái. Thiếu receipt không chứng minh rollback; không chạy lại apply/restore mù quáng.

## Bằng chứng local và rehearsal

- Fresh backup local: `output/native-array-cleanup/local-before-cleanup.sql.gz`, 113.458.062 bytes; SHA-256 `699d26eaa9b3b74d6d304109686e0b0512059fa7d1a0c8bdb382e4990a14416d`.
- Rehearsal MySQL riêng `nihongo_native_array_rehearsal_20261011`: injected failure rollback, apply, idempotence, restore và apply lại đều kiểm tra; không sửa lịch sử release/pin/các version cũ.
- Audit production bổ sung đã chạy trên rehearsal: **106 bảng được bảo vệ**, 41.533 note được đối soát; bao gồm toàn bộ clone overrides. Snapshot giữ các version lịch sử và phát hiện thay đổi schema/note ngoài plan.
- Local evidence/plan/receipt: `output/native-array-cleanup/local-evidence.json`, `local-plan.json`, `local-apply-receipt.json`. 68 note đúng postimage; mọi note ngoài plan giữ nguyên; 67 version template cũ giữ nguyên; CSS và các bảng release/card/progress/media đối soát bằng hash.
- Backend: 79 tests trong 5 file, 3 skip cho host typing mode đã parked; thêm test audit/backfill sau đó đưa suite cleanup lên 8 test pass. Frontend: 71 tests trong 4 file. Typecheck và production build pass. Test transaction/audit được chạy lại khi thay công cụ.
- Chrome profile riêng: 12 mặt template × 2 viewport (390/1280), **24/24** khớp geometry, màu, gradient, padding, font size, shadow của các element hiển thị khi đối chiếu legacy line strings với native items tương ứng. Fixture không bao phủ mọi dữ liệu người dùng/media.
- Probe dữ liệu thật local: `nǐ hǎo` và `ni hao`, `Tokyo` và `Đông Kinh` được chấp nhận độc lập; đáp án nối comma bị từ chối; En4 3 item tạo 3 row trong một container và một Meaning block.
- Server local được chạy lại qua `wsgi.py` trên 4789 với startup maintenance tắt cho lần khởi động này; không áp dụng migration ở startup.
