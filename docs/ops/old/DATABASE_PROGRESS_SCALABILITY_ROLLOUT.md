# Rollout database progress scalability

> Cập nhật: 2026-10-15. [Implementation/evidence](../architecture/DATABASE_PROGRESS_SCALABILITY_IMPLEMENTATION_2026-10-14.md), [báo cáo gốc](../architecture/DATABASE_PROGRESS_SCALABILITY_REPORT_2026-10-13.md). Head `20261014_000068`. Phiên xử lý này không chạy deploy hoặc sửa configured source.

## 1. Field cutover trong maintenance window

Field ID là authority bắt buộc ở code mới, không có dual-write flag. Startup không archive/backfill. Dừng mọi writer: HTTP, Connect, Study consumer, projection services/timers, import/CLI/maintenance jobs. Backup schema/data/media và xác nhận restore riêng trước production maintenance.

Deployment workflow đã đặt writer stop trước migration, rồi mới bootstrap/activate services. Nếu chạy thủ công trong release mới, dùng environment/venv của release:

```bash
python deploy/migrate_database.py --writers-quiesced
```

Entrypoint dùng audit factory không chạy startup maintenance. Với legacy named schema, nó upgrade đến66, chạy bounded offline preparation/verify, rồi upgrade67/68. Với schema đã canonical, chạy migrations còn lại. Không chạy plain `flask db upgrade` qua67 trên populated named schema chưa chuẩn bị.

Nếu cần kiểm tra/tạm dừng preparation theo batch, sau upgrade66:

```bash
export STARTUP_RUN_MAINTENANCE=0 STARTUP_RUN_DB_CREATE_ALL=0 STARTUP_RUN_CLONE_CUTOVER=0
flask --app wsgi.py db upgrade 20261014_000066
python scripts/cutover_field_value_identity.py --batch-size 200 --max-batches 1
python scripts/cutover_field_value_identity.py --apply --writers-quiesced --batch-size 200 --max-batches 10
python scripts/cutover_field_value_identity.py --apply --writers-quiesced --batch-size 200
python scripts/cutover_field_value_identity.py --verify
flask --app wsgi.py db upgrade
```

Lệnh migration thủ công phải dùng audit factory hoặc đặt `STARTUP_RUN_MAINTENANCE=0 STARTUP_RUN_DB_CREATE_ALL=0 STARTUP_RUN_CLONE_CUTOVER=0`; ưu tiên entrypoint deploy phía trên. Dry-run không ghi. Resume dựa trên committed archive rows; schema đổi sau capture hoặc row changed sẽ bị chặn. Giữ writers dừng xuyên suốt expand/preparation/contraction.

Pending/failed rename jobs cần quyết định rõ trước khi archive. File JSON ánh xạ job ID → `archive_as_abandoned` được truyền qua `--rename-job-dispositions <file>` ở deploy/cutover entrypoint. Chỉ dùng sau kiểm tra giá trị/schema thực tế; tool giữ nguyên job evidence và disposition, không giả định completed.

Manifest phải chứng minh full Note/media/override/job coverage, source/canonical checksum, schema/ledger fingerprint và quiescence. Unproven historical override label thành explicit typed extra, không tự gán sang Field mới. Review dispositions trước activate. Nếu gate fail, sửa provenance/disposition trong maintenance flow; không bỏ gate hay mở dual-write.

Sau67 kiểm tra: không có `notes.field_values`/`field_rename_jobs`; codec/maps nonnull; media/overrides unique theo scoped identity; retained Field ledger không cascade theo source Field deletion. Smoke owned và installed clone browse/edit/search/import/media/study; arrays giữ JSON list. Field rename phải chỉ đổi metadata và template binding, không scan/rewrite Notes.

## 2. Deck/due projections

Các flags quản lý rollout reader/derived projection, không thay Field authority:

```dotenv
DECK_COUNT_WRITE_ENABLED=1
DECK_COUNT_READ_MODE=raw
DECK_COUNT_PREWARM_USER_IDS=1
FORECAST_SUMMARY_READ_MODE=raw
FORECAST_SUMMARY_READ_USER_IDS=1
```

Phủ writer ở mọi process, rồi invalidate/prewarm:

```bash
flask --app wsgi.py deck-counts-invalidate --apply
flask --app wsgi.py analytics-counts-prewarm --configured
flask --app wsgi.py analytics-counts-prewarm --configured --apply --max-decks 100 --max-buckets 4096
```

Job có `has_more/next_after_deck_id`; tiếp tục keyset chunks bằng `deck-counts-prewarm --after-deck-id <cursor> --max-decks 100 --apply`. Default forecast là collection union, dedup overlapping installs. Scope deck statistics cần đủ subtree IDs:

```bash
flask --app wsgi.py forecast-summary-prewarm --user-id 1 --deck-id 10 --deck-id 11 --apply
```

Chỉ bật `DECK_COUNT_READ_MODE=summary`/`FORECAST_SUMMARY_READ_MODE=summary` sau parity/coverage và target workload qualification. Reader kiểm tra source/local revisions, release pin, overlay/maps, authority/policy/day; unknown recovery scopes vẫn raw. Raw Connection/maintenance ngoài covered Session hooks phải invalidate rõ.

## 3. History writer chỉ dùng durable outbox

Không còn `REVIEW_ANALYTICS_WRITE_MODE` hoặc synchronous review bucket writer. Covered source transactions ghi event/fact/receipt và outbox; worker update daily buckets/checkpoint/applied marker atomically.

```dotenv
REVIEW_ANALYTICS_WRITE_ENABLED=1
REVIEW_ANALYTICS_READ_MODE=raw
REVIEW_ANALYTICS_READ_USER_IDS=1
```

```bash
flask --app wsgi.py review-analytics-backfill --user-id 1 --apply --chunk-size 500
flask --app wsgi.py review-analytics-outbox-status --max-users 20
flask --app wsgi.py review-analytics-drain --pending --max-users 20 --max-revisions 100
flask --app wsgi.py review-analytics-drain --pending --max-users 20 --max-revisions 100 --apply
flask --app wsgi.py review-analytics-reconcile --user-id 1
```

Worker timer: oneshot sau1s inactive, capped learners/revisions/payload, flock tránh runner trùng. Pending discovery ưu tiên learner có row cũ nhất. Gap/hash/policy mismatch làm generation DIRTY; correction/delete/bulk cần rebuild, không đoán delta. Không lấy MAX event ID làm coverage.

Local B8 đã PASS (+3.122ms/+5.685% both), local concurrent-worker lag p95 ~1.059s. Trước production canary vẫn đo actual lag/backlog/write cost/pool/resources. Bật history `summary` theo allowlist sau reconcile; reader chỉ phục vụ exact khi applied revision bằng source revision và verification/policy đúng. Applied outbox chưa có retention tự động.

## 4. Summary chưa ready

Sau khi toàn scope canary ready, có thể đặt:

```dotenv
ANALYTICS_REQUIRE_READY_USER_IDS=1
```

Summary miss/lag của learner trong list trả HTTP409, `ANALYTICS_SUMMARY_NOT_READY`, `Retry-After: 60`. Dashboard/overview/today-future/study-time không trả zero/stale hoặc raw scan thay exact summary. Raw/shadow vẫn là read oracle/recovery. Không mở strict canary ngoài worker coverage.

## 5. Rollback và qualification

Reader recovery: đổi về `raw`, clear strict list. Giữ compatible history writer/worker cho đến khi committed backlog được drain/verified. Deploy rollback dừng writers, kiểm tra Study/history gates trước restore code/environment.

Sau Field contraction, `deploy/check_field_code_rollback.py --writers-quiesced --previous-release <path>` đọc schema và từ chối binary không tuyên bố codec `field-id.v1`/canonical resolver. Không khôi phục named store trong runtime. Quay về pre67 cần full backup restore vào database riêng và media/history/session consistency; archive value restore probe chỉ chứng minh raw Note payload/legacy shadow bytes, không chứng minh full application restore.

Giữ ledger/archive/manifest và frozen historical artifacts. Không generic downgrade populated feed/Field storage; không xóa source Notes/progress/events/receipts. Retention chỉ triển khai sau replay/undo/retry horizons và restore qualification.

Qualification tool mặc định dry-run. Lệnh dưới chỉ copy configured loopback source sang generated schema rồi migrate bản sao; fingerprint source trước/sau, không sửa source:

```bash
python scripts/qualify_progress_scalability_mysql.py --run --cutover-only --output docs/architecture/artifacts/field_identity_full_snapshot_mysql_20261014.json
```

Bỏ `--cutover-only` để chạy read benchmark theo full workload. Fresh schema, historical Field cutover, actual SQL consumers, forecast và outbox probes được nối vào CI MySQL. Failed fixtures/artifacts giữ để chẩn đoán; chỉ cleanup nonce-owned schemas sau xác minh đúng tên.

Với source còn named store, qualification phải qua full pre-DDL archive/live equality gate. Với source đã ở schema canonical và có ghi mới, tool kiểm tra live codec/nonnullable identities và immutable archive/manifest riêng; không buộc dữ liệu live tiếp tục bằng snapshot lúc cutover. Recheck ngày15 đã xác nhận cả dữ liệu mới và checksum archive; xem implementation tracker để đối chiếu các lượt kiểm tra trước đó.
