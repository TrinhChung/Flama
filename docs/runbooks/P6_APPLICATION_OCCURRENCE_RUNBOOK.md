# Runbook Phase 6 — phát hành application occurrence (migration 46) và đếm theo Note

> Lập 2026-09-30. Nguồn: [P6 execution plan](../task/decoupling/P6_EXECUTION_PLAN_2026-09-29.md) §5 (G6-P), §7. Không bước nào ở đây tự chạy trong CI. Lệnh `flama_cli` giống [runbook P5](./P5_NOTE_AUTHORITY_RUNBOOK.md) (systemd-run, user `flama`, `/opt/flama/current`, `/etc/flama/flama.env`).

## 1. Thay đổi khi phát hành

| Hạng mục | Tác động | Dữ liệu learner |
|---|---|---|
| Migration 46 | Tạo `study_applications` (1 occurrence `compat` mỗi Template), thêm `cards.application_id` (+ index, unique `(note_id, application_id)`, FK thêm với `foreign_key_checks=0` để MySQL làm INPLACE), `connect_source_card_refs.note_id` (backfill ngay), `review_events.note_id` (**không** backfill trong migration), ref `card_id` nullable + `ON DELETE SET NULL`, bỏ unique `(note_id, template_id)` | Không đổi giá trị nào đang có; Card ID giữ nguyên |
| Seam `before_flush` | Template/Card mới luôn có occurrence; event/ref mới có `note_id` | — |
| `STUDY_NOTE_COUNT_ENABLED` | Mặc định tắt. Bật: learner NOTE đếm mỗi Note một lần ở dashboard, deck tree, Browse, hàng đợi | Chỉ đổi cách đếm/hiển thị |

`deploy.yml` chạy `flask db upgrade` **khi release cũ vẫn phục vụ**. Trong vài giây đó release cũ có thể tạo Card chưa có occurrence, ref/event chưa có `note_id`. Migration gắn lại lần cuối trước khi kiểm tra và chỉ dừng nếu một Card *có từ trước migration* còn thiếu occurrence; phần còn lại do bước 3.3 xử lý.

Bench quy mô production (MySQL 8.0.40, 40k Card, 130k event, 16k ref, luồng ghi kiểu release cũ chạy song song): migration 6,9 s, lệnh ghi bị chặn lâu nhất 0,82 s, 0 lỗi — chi tiết §5.

## 2. Cổng trước phát hành

- CI xanh trên PR (backend, `mysql-contract` gồm `probe_p6_application_schema_mysql.py` và `bench_p6_migration_mysql.py`).
- INT-04 local: `run_tests.py --all --backend-only`, probe P5 (direct, batch, analytics, numeric, concurrency) + P6 PASS.

## 3. Phát hành

1. **Backup** (deploy không tự backup): `mysqldump --single-transaction --routines --triggers "$DB_NAME" | gzip > /root/flama-pre-p6-$(date -u +%Y%m%dT%H%M%SZ).sql.gz`; kiểm `zcat … | tail -1` có `-- Dump completed`. Không phát hành nếu chưa có backup.
2. Merge PR vào `master` → CI → `deploy.yml`. Kiểm: `readlink -f /opt/flama/current` = SHA mới; `SELECT version_num FROM alembic_version` = `20260930_000046`; `/api/health` 200; log `flama-db-migrate-*` có thể có dòng `[20260930_000046] N Card(s) created during the migration are left for study-phase6-attribution-backfill.` (bình thường).
3. **Backfill attribution** (idempotent, commit từng lô 2000 dòng theo PK, chỉ khóa các dòng đang ghi):
   ```bash
   flama_cli study-phase6-attribution-backfill            # đếm, không ghi
   flama_cli study-phase6-attribution-backfill --apply
   ```
   Kỳ vọng sau `--apply`: `unbound_cards` = `cards_bound`, `duplicate_cards` = `[]`, `unresolved_events` = số event có Card đã bị xóa từ trước (giữ NULL). Chạy lại lần hai phải ra `cards_bound=0`, `refs_attributed=0`, `attributed_events=0`.
   Nếu `duplicate_cards` khác rỗng: release cũ đã tạo hai Card cho cùng Note + Template trong lúc migrate. **Không xóa**; ghi lại ID, kiểm lịch sử của từng Card, xử lý thủ công.
4. Kiểm (SELECT-only):
   ```sql
   SELECT COUNT(*) FROM cards WHERE application_id IS NULL;                        -- 0
   SELECT COUNT(*) FROM cards c JOIN study_applications a ON a.id = c.application_id
    WHERE a.template_id <> c.template_id;                                          -- 0
   SELECT COUNT(*) FROM review_events e JOIN cards c ON c.id = e.card_id
    WHERE e.note_id IS NULL OR e.note_id <> c.note_id;                             -- 0
   SELECT COUNT(*) FROM connect_source_card_refs r JOIN cards c ON c.id = r.card_id
    WHERE r.note_id IS NULL OR r.note_id <> c.note_id;                             -- 0
   ```
   và `flama_cli study-authority-read-audit` (hoặc audit kiến trúc như sau R1) PASS.

## 4. P6-10 — bật đếm theo Note

Sau khi §3 PASS. Nếu mỗi Note có đúng một Card (`SELECT COUNT(*) FROM notes` = `SELECT COUNT(*) FROM cards`) thì số đếm không đổi và bật được ngay; ngược lại theo dõi một ngày không lỗi trước khi bật:

1. So số trước khi bật: ghi lại tổng due/new/learn trên dashboard của vài learner NOTE có NoteType nhiều Template.
2. Thêm `STUDY_NOTE_COUNT_ENABLED=1` vào `/etc/flama/flama.env` (key không do `deploy/sync_managed_env.py` quản lý nên được giữ qua deploy), `systemctl restart flama.service flama-connect.service flama-study-worker.service`.
3. Kiểm: `/api/health` 200; dashboard/deck tree/Browse của learner đó đếm mỗi Note một lần (NoteType 1 Template: số không đổi).
4. Rollback: xóa dòng (hoặc đặt `0`) và restart. Không có dữ liệu nào bị ghi bởi cờ này.

## 5. Số đo

`scripts/bench_p6_migration_mysql.py --notes 20000 --events 130000 --refs 16000` (2026-09-30, MySQL 8.0.40 local; production lúc đó: 40.257 Card, 129.245 event, 15.965 ref). Luồng ghi mô phỏng release cũ: insert event, tạo Note + 2 Card, cập nhật ref, ~200 lệnh/giây.

| Bước | Thời gian | Luồng ghi release cũ (max / p99) | Lỗi ghi |
|---|---|---|---|
| Migration 46 | 6,9 s | 820 ms / 22,9 ms | 0 |
| Backfill `--apply` (130.601 event, 69 lô) | 24,5 s | 275 ms / 39,5 ms | 0 |

Sau cùng: 40.942 Card đều có occurrence, 0 event có Card mà thiếu/sai `note_id`, 0 ref sai Note, 0 Card trùng, số Card/event bằng seed + số dòng luồng ghi đã ghi (không mất dòng). 22 Card do release cũ tạo trong lúc migrate được backfill gắn.

## 6. Kết quả phát hành 2026-09-30

| Bước | Kết quả |
|---|---|
| Backup | `/root/backups/flama-pre-p6-20260930T085454Z.sql.gz` (115 MB, `-- Dump completed`) |
| Deploy | PR #174 merge `3e7fa3a` 08:56 UTC; release lên 09:07:48 UTC; head `20260930_000046`; 24 occurrence cho 24 Template; 0 Card chưa gắn; health 200; 0 phản hồi 5xx sau deploy |
| Backfill `--apply` | 28 s, 65 lô: 128.650 event gắn Note, 595 event có Card đã xóa từ trước giữ NULL; 0 Card/ref/Template cần sửa; chạy lại: 0 thay đổi |
| Kiểm §3.4 | cả 4 truy vấn = 0 |
| Dấu vân tay trước/sau (số dòng + CRC: notes, cards, templates, review_events, card_progress, state/subject NOTE, ref Connect, sessions, session cards, commits) | giống hệt, chỉ `alembic_version` đổi |
| `study-authority-read-audit` | 18/18 learner NOTE PASS (user 1: 194 s) |
| P6-10 | Production có đúng 1 Card mỗi Note (40.257/40.257) nên số không đổi: đo READ ONLY user 1 dashboard 2,56 s → 2,18 s, overview 2,15 → 2,23 s, new/learn/due giống hệt; user 4 0,81 → 0,88 s. Bật `STUDY_NOTE_COUNT_ENABLED=1` 09:15:53 UTC (env cũ: `/etc/flama/flama.env.pre-p6-10`), restart, health 200 |

## 7. Rollback

- Code: deploy lại release trước (schema 46 tương thích ngược: cột mới nullable, release cũ không đọc chúng).
- Migration 46 downgrade chỉ khi thật cần: tự từ chối nếu có occurrence lặp, ref đã mất Card, `note_id` không suy lại được, hoặc Note áp dụng một Template hai lần. Backup ở §3.1 là đường lùi cuối.
