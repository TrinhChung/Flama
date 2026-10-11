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

## Kết quả production

Hoàn tất ngày 2026-10-11 sau [PR #228](https://github.com/TrinhChung/Flama/pull/228), release backend `fde1cd882abe3cfc4158e473a8c53da2dd71de36`. [CI và deploy](https://github.com/TrinhChung/Flama/actions/runs/38132211112) pass backend, frontend, MySQL, Redis, SPA và health/readiness. Commit native `655c19dd` được tạo trong worktree riêng từ master `edcccd85`; bảy file sửa hiệu năng attach template/Card và commit P11 `1bcfebaa` không nằm trong diff hoặc ancestry của release.

Frontend Worker `flama-frontend1001` build thành công từ cùng master SHA; version lúc cutover `b7403850-cb3a-44c5-bcda-4529ada2a880`. Chrome profile riêng tải trang đăng nhập, API session trả 200, không có lỗi console.

Target đã xác minh là MySQL `flama` / server `chung`. Rehearsal `flama_native_array_rehearsal_20261011` được restore từ backup production mới; injected rollback, apply, idempotence, restore và audit 106 bảng/41.510 note đều pass. Sau khi backend triển khai xong, dừng HTTP, Connect, Study worker, retention timer và retention service trước backup cuối, plan và transaction.

- **41.199 note** được backfill, bao gồm **68 repair** đã đối chiếu preimage; **9 template** được modernize; không đổi schema. 108.893 slot hiện tại đều là JSON `ARRAY`, không còn chuỗi ở 20 FieldDef thuộc scope.
- Toàn bộ **41.510 note** được đối chiếu postimage: note trong plan đúng hash, note ngoài plan giữ nguyên. 106 bảng được bảo vệ, bao gồm Card/progress/media, release/checkpoint, field schema, install và clone overrides, giữ nguyên hash.
- Card vẫn có 111.728 row; template vẫn có 34 row. **42 version template cũ** giữ nguyên; 9 version mới đưa tổng số lên 51. CSS/input schema không đổi. 49 field text/richtext trên các bản sao giữ nguyên kiểu.
- **70.818 slot STRING trong checkpoint lịch sử** giữ nguyên. 28 install vẫn có 27 release pin. Không publish/rebase release trong cleanup. Alembic vẫn ở `20261010_000056`.
- Plan sau apply có 0 note/0 template cần đổi. Web, Connect, Study worker và retention timer đã active; HTTP health, Connect health và worker shared readiness pass.

Backup cuối: `/var/backups/flama/native-array-20261011/before-stopped.sql.gz`, **118.105.739 bytes**, gzip đã kiểm tra; SHA-256 `177df8f2d86c173b3dcb074e84861e75260c1c47fb82816e8925d6726250cb5e`. Directory 0700, dump/plan/receipt/snapshot 0600. Backup rehearsal được giữ riêng, 118.105.741 bytes; SHA-256 `2e74018930c9c3afedb98d21b566924aa7609ee8fd5e24c88c0c666dbbf1cb50`.

Private `plan.json`, `before-audit.json`, `apply-receipt.json`, `idempotent-plan.json`, `production-evidence.json` và `private-manifest.json` nằm cùng directory backup. Checksum plan production: `6f9bdd6078956c96bf696e505d8bd183f93f3bd5ed70907194437840d1e63ec9`. Không dùng checksum/plan rehearsal cho production.

Smoke sau restart chặn DML trong process kiểm tra: browse owner trả native lists và render template mới; browse installed clone đọc release hiện có, giữ pin. Chrome chạy HTML do runtime production render: note En4 thật có 4 collocation pair, một container và một Meaning block; bốn template typing với binding giả lập chấp nhận riêng `Tokyo`/`Đông Kinh`, từ chối đáp án nối comma. Dictation được kiểm tra bằng input/Enter theo flow của nó. So sánh 13 mặt HTML production ở viewport 390/1280 có **26/26** geometry/style khớp legacy strings với native lists; fixture typing được gắn binding, không render input trống. Không gọi attach-template hoặc ghi câu trả lời study khi smoke.

**113 note vẫn cần biên tập nội dung/bản dịch**; dữ liệu thiếu hoặc chưa đủ bằng chứng không được tự dịch/xóa. Installed clone đang pin release cũ tiếp tục đọc nội dung lịch sử; phát hành/rebase bản mới là quy trình marketplace riêng.

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
  --manifest scripts/migrations/native_array_production_manifest_20261011.json \
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
