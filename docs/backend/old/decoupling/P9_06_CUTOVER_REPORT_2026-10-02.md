# P9-06 — Production cutover 2026-10-02

## Phạm vi được duyệt

Chủ sản phẩm yêu cầu xử lý ngay, không đợi 30 ngày, rồi xác nhận chỉ miễn chờ cho lần migration này và **giữ compatibility v2/v3 cùng fallback ordinal**. Vì vậy không retire decoder/execution compatibility, không thay fallback Anki, không thêm chế độ bypass gate lâu dài và không drop `card_progress`. Những yêu cầu này thay phạm vi retirement của kế hoạch ban đầu; không được đánh dấu P9-08/09/10 đã hoàn tất.

Migration dữ liệu hiện có chạy đúng một lần. Profile persisted trong DB khiến enrollment, tạo Note/Card, review, import, reset và sync về sau tự chọn canonical; không cần chạy lại CLI switch. CLI từ chối lần apply tiếp theo bằng `PROFILE_ALREADY_SWITCHED`. Retention membership vẫn giữ tối thiểu 30 ngày; đó là chính sách dữ liệu khác với thời gian chờ cutover vừa được miễn.

## Cutover đã thực hiện

- Release trước freeze: `05e388da8e1277caac0467adfb8078077d12cc79` (#194), đã hỗ trợ canonical.
- Audit trước chuyển: **18/18 learner PASS**, so projection hiện hành với canonical.
- Dry-run: `blockers=[]`; 13.903 Connect ref ánh xạ sang AUTHORITY, 2.062 ref có thay đổi chưa xác nhận chuyển NEEDS_CONFIRMATION.
- Freeze web, Connect và Study worker: `14:44:27Z` đến `14:45:10Z` (43 giây).
- T0 commit: **`2026-10-02T14:44:54Z`**; `CANONICAL_V1`, epoch **2**.
- Có 4 lease v4 sống trước chuyển. Không có lease v2/v3 sống và không có batch chưa hoàn tất; lease v4 qua switch đã có test ở #195.
- Sau mở: ba service active, `/api/health` trả `{"status":"ok"}`.
- Audit sau chuyển: **18/18 learner PASS**, `compared_with_projection=false`.
- Postflight: 0 dòng projection tạo/cập nhật kể từ T0; 15.965 external ref đều có Card/application/ordinal đúng mapping; 0 duplicate ordinal. Đây là kiểm các dòng còn tồn tại, chưa thay SQL trace hay workload review thực tế.
- Readiness v3 đã chạy qua `wsgi_audit.py` với principal MySQL **SELECT-only** được kiểm grant: `legacy_projection_writes=ready`, `projection_cutover=ready`, 0 legacy/unenrolled learner, 0 projection write. `work_drain=waiting` vì 4 lease v4 hợp lệ; các gate retirement chưa xanh vì thiếu telemetry/package coverage, đúng với phạm vi giữ compatibility. Credentials nằm ngoài repo, quyền private; báo cáo `/var/lib/flama/phase9/readiness.json`.

## Backup và recovery

Backup mới được tạo trong freeze, có completion marker và gzip hợp lệ:

- VPS: `/root/backups/flama-pre-p906-20261002T144423Z.sql.gz` (quyền private).
- Kích thước: **123.584.526 byte**.
- SHA-256: `ada26b51d6bc24be94f5664f4e3af0fb00930764ee18ae98e93b33dc7145dc42`.
- Schema: Alembic `20261002_000048`; pre-switch `PROJECTION_V1`, epoch 1; 18 NOTE enrollment, 40.793 subject/projection.
- Watermark: **`binlog.000100`, position `109986`**, được ghi trong dump và manifest.
- Restore MySQL local 8.0.40: **PASS**, 96,968 giây; state/token, availability và receipt orphan đều 0. Database tự sinh đã xóa, DB cấu hình không bị ghi. Artifact riêng ở `output/p9-restore/pre-p906.restore.json`; không commit dump/credentials.
- Restore + PITR trên MySQL **8.0.46** của VPS vào DB tự sinh: **PASS**, restore 88,528 giây, tổng 93,367 giây. Replay đoạn đã chốt `binlog.000100:109986..13776352` khôi phục đúng `CANONICAL_V1`, epoch 2, T0 và 13.903 AUTHORITY / 2.062 NEEDS_CONFIRMATION ref; state/token, availability, receipt orphan, projection write đều 0. DB rehearsal đã xóa, schema `flama` không bị ghi. Binlog giữ riêng cạnh backup, SHA-256 `11547da2d680a0ff093203ed63f92502944075372f244b6f9658298c9a5f2000`. Manifest VPS `.pitr.json`, bản local `output/p9-restore/pre-p906.pitr.json`. Bằng chứng chỉ cho đoạn binlog đã chốt này, không tuyên bố RPO=0 cho mọi thời điểm hay selective repair tùy ý.

Diễn tập binlog phải dùng DB tự sinh cách ly và giữ profile một chiều; không restore đè production. `mysqlbinlog --rewrite-db` được áp dụng trước `--database`, nên filter phải dùng tên target đã rewrite; dùng `--require-row-format` để từ chối DML không có dạng row. [MySQL 8.0 Reference Manual](https://dev.mysql.com/doc/refman/8.0/en/mysqlbinlog.html).

## Hành vi sau migration và phần được giữ

P9-01 retention đã bật trên production sau rehearsal:

- Workload MySQL local: một terminal session 5.000 membership cùng 200 open lease; 5 lượt mỗi lượt tối đa 1.000 membership, giữ đủ 200 lease. Thời gian cả lượt `0,094 / 0,078 / 0,078 / 0,078 / 0,079` giây; max mẫu `0,094 s` là upper bound p95 của mẫu này. Fixture benchmark không có pin; MySQL contract 7/7 kiểm pin/FK riêng. DB probe tự sinh đã xóa.
- Manual production `15:08:48Z`: expire 1 lease cũ; xóa 3.251 membership của 19 terminal session đủ tuổi 30 ngày, 0 pin, 20 lô, 0,974 giây cho cả vòng service. Counts state/subject/token/review/receipt/session/session-commit/projection trước/sau không đổi; delta membership khớp. Lượt chạy lại noop, health OK.
- Unit/timer đã cài và enabled; lịch daily 18:30 UTC + jitter tối đa 10 phút, không chạy bù. Lần tiếp theo được systemd chọn `2026-10-02T18:32:33Z`. Marker phê duyệt lưu ngoài repo, không thêm vào deploy tự động. Chi tiết [runbook retention](../../runbooks/P7_SESSION_RETENTION_RUNBOOK.md).

Các test canonical materialization/lifecycle/review/Connect đã nằm trong 887 test Study + Connect PASS. Chúng kiểm tạo mới không cần projection, direct review/session commit, reset rồi review lại, thêm/xóa Template, nhập Anki, revision fence và overlay. #195 kiểm v4 lease cấp trước switch vẫn commit và retry đúng receipt sau switch, projection không bị ghi.

Regression trong `test_study_new_learner_note_enrollment.py` kiểm apply một lần rồi đăng ký thường và Google mới vẫn NOTE/canonical, không có SQL tới `card_progress`; apply lần hai bị từ chối, epoch không đổi. Đây là bảo đảm migration không trở thành bước thủ công cho các tài khoản về sau.

Compatibility v2/v3 và fallback ordinal được giữ theo yêu cầu. Fence hiện hành vẫn từ chối thực thi legacy lease trên NOTE khi không hợp contract, còn receipt đã commit được trả lại idempotently. Không đổi dữ liệu IndexedDB hay chuyển pending event cũ sang phiên mới.

P9-09/10 còn các dependency thật: model/FK `CardProgress`, metadata startup `create_all`, schema patch, nhánh projection và công cụ reconciliation. Physical drop cần loại hết consumer cùng rehearsal riêng; timestamp zero không làm các dependency này biến mất. Không chờ 30 ngày để tiếp tục migration đã duyệt; cũng không xóa compatibility mà chủ sản phẩm vừa yêu cầu giữ.
