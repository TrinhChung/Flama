# Decoupling migration trên local — 2026-10-03

Phạm vi: MySQL 8.0.40 tại `localhost:3306`, database `nihongo`.

## Kết quả hiện tại

Schema đã nâng từ `20260921_000043` lên `20261002_000048`. Toàn bộ
11.259 progress cũ đã backfill thành công, không quarantine, không
unresolvable. Toàn bộ 8 learner `1, 2, 3, 4, 5, 6, 464, 468` đã chuyển
sang NOTE, epoch 1. Audit sau cutover của cả 8 learner đều PASS,
`mismatches=[]`, `compared_with_projection=false`.

**Hoàn tất migration authority/storage trên local:** profile
`CANONICAL_V1`, epoch 2, T0 `2026-10-03T00:13:34Z`
(09:13:34 Asia/Tokyo). Chủ dữ liệu xác nhận local chỉ là test và cho phép
tiếp tục. Đơn `0b3daca1-dd77-4838-a75d-2f84a4a18197` của learner 3
đã được hủy bằng `payment_service.cancel_order_for_user`, sau đó enroll
và audit learner 3 thành công. Dry-run switch không còn blocker.

## Đối chiếu dữ liệu

| Dữ liệu | Trước | Sau | Kiểm chứng |
|---|---:|---:|---|
| Users | 8 | 8 | Hash các cột gốc không đổi |
| Notes | 22.044 | 22.044 | Hash các cột gốc không đổi |
| Cards | 22.044 | 22.044 | Hash các cột gốc không đổi; thêm application binding |
| Progress gốc | 11.259 | 11.259 | Hash toàn bộ giá trị gốc không đổi |
| Tổng CardProgress | 11.259 | 22.046 | Enrollment thêm 10.787 projection mới cho Note chưa học |
| Review events | 61.842 | 61.843 | Hash 61.842 event gốc không đổi; thêm 1 review test |
| NOTE subjects / states / contributors / availability | 0 | 22.046 mỗi bảng | Audit NOTE PASS |

Attribution đã gắn `note_id` cho 61.802 event. 40 event thiếu Card gốc
giữ `note_id=NULL`; không suy đoán Note. Cả 3 deck install vẫn là
`logical_overlay`; learner 4 và 6 đã enroll và audit thành công.
Enrollment hủy 44 phiên cũ đang mở (41 của learner 1, 3 của learner 468);
người học mở phiên v4 mới sau thay đổi epoch.

## Backup và kiểm tra

Artifacts local nằm tại:

```text
C:\Users\chung\.codex\backups\nihongo\20261002T233819Z\
```

- `nihongo-before-decoupling.sql.gz`: backup toàn database trước migration,
  26.427.586 byte; SHA-256
  `69d5f1720ed5586161786e4807e80f44889fd1539c5109e145516e50ae327358`.
- `restore-and-upgrade-rehearsal.json`: restore vào database local tạm,
  so hash dữ liệu gốc và upgrade 43→48 đều PASS; database tạm đã dọn.
- `baseline.json`, `data-verification.json`: cột gốc, counts và hash đối chiếu.
- `operations.jsonl`: kết quả CLI, dry-run/apply, enrollment và audit.
- `local.env.before`: bản cấu hình trước thay đổi, chỉ lưu local.
- `authenticated-smoke.json`, `runtime-health.json`: kiểm tra app sau migration.
- `nihongo-before-canonical-cutover.sql.gz`: backup trong freeze trước P9-06,
  39.734.883 byte; SHA-256
  `f51fc1b07c2f3ce55608b6b1ad00dfc46369232c89b0edcf86a12c19ab517589`.
- `canonical-backup-restore-rehearsal.json`: restore backup P9-06 PASS;
  state/token, availability và receipt orphan đều 0; database tạm đã dọn.
- `canonical-data-verification.json`: hash dữ liệu gốc vẫn khớp sau cutover
  và review test; cả 22.046 CardProgress đứng yên so với thời điểm freeze.
- `canonical-readiness.json`: audit bằng principal SELECT/SHOW VIEW tạm;
  `projection_cutover=ready`, số CardProgress ghi sau T0 = 0.
- `canonical-writer-smoke.json`: review test, retry và mở phiên v4 trên
  learner 468; SQL trace không có truy cập `card_progress`.
- `test-order-cancellation.json`: hủy đúng đơn test đã được cho phép.

Backfill apply hoàn tất trong khoảng 386 giây; enrollment learner 1
(22.041 Note) trong khoảng 504 giây; audit learner 1 khoảng 83 giây.
Các lệnh vận hành dùng `wsgi.py`, tắt startup maintenance/create-all;
backfill apply bật cả shadow write và backfill trong process vận hành.

## Runtime local

`.env` đã bật `STUDY_WIRE_V4_ENABLED`, `STUDY_NEW_LEARNER_NOTE_ENABLED`,
`STUDY_NOTE_COUNT_ENABLED`, `STUDY_PROGRESS_SHADOW_WRITE_ENABLED`.
Backfill, shadow compare và async batch tắt sau migration.

`npm run build` PASS. `wsgi.py` đọc đúng cấu hình; React shell và health
trả 200. Dashboard, statistics và statistics overview của learner 1 trả
200; mở phiên `study-session.v4` trả 201. Sau cutover, một câu trả lời test
và retry cùng operation đều trả 200, authority revision tăng đúng 1 lần,
chỉ thêm 1 review event (ID `65091`), không có SQL đọc/ghi `card_progress`.
Audit lại learner 468 sau review cũng PASS.

- Web / React: `http://127.0.0.1:4789`.
- Flama Connect: `http://127.0.0.1:4790`, `/healthz` trả 200.

Hai process chạy ẩn, không reload; log nằm cùng thư mục artifacts.

## Cutover P9-06 đã thực hiện

1. Dừng web và Connect local để đóng băng ghi.
2. Hủy đơn test được cho phép; dry-run/apply enrollment learner 3 và audit.
3. Backup tại thời điểm freeze; xác nhận kế hoạch switch `blockers=[]`.
4. Chuyển sang `CANONICAL_V1`, audit cả 8 learner, kiểm tra restore backup,
   review/retry/v4 và fingerprint của toàn bộ projection.
5. Khởi động lại web và Connect; kiểm tra health và React shell.

Quy trình đối chiếu với
[runbook P9-06](../runbooks/P9_06_STORAGE_PROFILE_SWITCH_RUNBOOK.md).
Readiness xác nhận `legacy_projection_writes=ready` và
`projection_cutover=ready`. Các gate retirement wire/ordinal/package và
lease đang mở không phải phạm vi migration storage này; compatibility
v2/v3 và fallback ordinal tiếp tục theo phạm vi P9 đã chốt. Switch đã ánh
xạ 11.156 Connect ref sang `AUTHORITY`, 31 ref sang `NEEDS_CONFIRMATION`
theo trạng thái sync hiện có.

Boundary được kiểm tra trong
`app/services/study_authority_enrollment_service.py`,
`app/services/study_storage_profile_service.py` và CLI tại `app/cli.py`;
quy trình đối chiếu với [runbook P5](../runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md).
