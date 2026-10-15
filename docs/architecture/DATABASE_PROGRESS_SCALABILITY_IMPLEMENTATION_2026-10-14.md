# Database progress scalability — implementation tracker

> Cập nhật: 2026-10-15. Theo [báo cáo gốc](DATABASE_PROGRESS_SCALABILITY_REPORT_2026-10-13.md). **Đã đóng hai task implementation/qualification local: Field cutover và writer B8.** Phiên xử lý này chỉ ghi các DB fixture, không chạy deploy hoặc sửa configured source. [Runbook](../runbooks/DATABASE_PROGRESS_SCALABILITY_ROLLOUT.md).

## Trạng thái các task

| Task | Kết quả |
|---|---|
| Field storage cutover | Một authority live: `field_values_by_id` + codec `field-id.v1` + explicit extras. Migration 67 bỏ cột `notes.field_values` và bảng `field_rename_jobs`; runtime bỏ dual-write flag, model/job và script shadow backfill. |
| Writer/reader/search/media cutover | REST, MCP, Connect, import, edit/study, browse/search, clone/rebase/change request và media dùng scoped identity. Tên là adapter ở ranh giới API/template. Rename thay metadata, không đọc/ghi toàn bộ Notes. |
| Historical Field data | Migration 66 và offline preparation lưu raw JSON, captured schema, typed canonical payload, checksum và manifest; 67 chỉ contract sau full coverage gate. Ledger giữ identity đã xóa; frozen release/session/receipt/audit giữ nguyên bytes/codec lịch sử. |
| Writer performance B8 | Một đường durable outbox; đã bỏ synchronous review bucket writer và `REVIEW_ANALYTICS_WRITE_MODE`. MySQL local 240 samples/mode đạt cả ≤5 ms và ≤10% added p95; worker local lag p95 dưới 2 s. |
| Deck/due/history readers | Snapshot/readiness/worker của đợt trước vẫn áp dụng; production canary, resource budget và retention là các qualification vận hành riêng. |

## Field ID là authority duy nhất

[Runtime resolver](../../app/services/field_value_runtime_service.py) dựng name view từ schema hiện hành, không fallback sang cột cũ. [Hooks](../../app/services/field_value_identity_hooks.py) chạy bắt buộc cho mọi ORM writer; bulk identity writes phải qua scoped adapter. Schema cache dùng chung trong transaction, tránh lookup NoteType/clone theo từng Note.

Owned/local Note dùng FieldDef ID của chính NoteType; source Note dùng source ID; clone-added field có namespace `added:<install_id>:<field_id>`. Override và media có `field_identity_key` làm binding/uniqueness, tên và source ID cũ chỉ là advisory lịch sử. Clone edit giữ overlay-only, không đổi source Note.

Xóa rồi tạo lại cùng tên tạo identity khác. Giá trị retired vẫn nằm dưới ID cũ và không được gán sang Field mới. Extras giữ rõ là dữ liệu chưa khai báo; không tạo UUID giả hoặc tự nhập extras vào Field vừa thêm. Missing/null/empty, primitive types, JSON list lồng và duplicates giữ nguyên.

Schema/content/overlay revisions chặn stale writes. REST/MCP nhận expected revisions; React browse/study giữ revisions lúc bắt đầu edit. Mapper CAS bảo vệ concurrent content/overlay updates. API trả 409 để reload khi nội dung/schema thay đổi; stale label được kiểm tra trước normalizer.

SQL search chỉ xét nội dung values hiện hành và extras, không tìm UUID/structural keys/retired values. Đây là content search contract; query từng khớp tên key do cast toàn JSON không được coi là parity nội dung.

Media binding sống theo identity khi rename. Pinned release/render/hash dùng captured historical schema. Undo media audit cần scoped ledger/asset proof, từ chối recycled/ambiguous hoặc Field tạo sau audit. Frozen audit/release/session payload không bị rewrite.

## Migrations và deployment

Head: `20261014_000068`.

- 63: additive identity columns/revisions, giữ nguyên lịch sử migration.
- 64: rebuildable forecast headers/buckets.
- 65: durable review-history feed/head.
- 66: retained identity ledger, immutable archive và cutover manifest.
- 67: verified contraction của named Note storage/rename jobs, canonical nonnull values và identity uniqueness/FK detachment cho overlays/media.
- 68: covering index cho oldest-pending learner discovery; MySQL `INPLACE, LOCK=NONE`, bounded metadata lock.

[Deployment entrypoint](../../deploy/migrate_database.py) chạy expand → archive/verify → contract khi toàn bộ writers đã dừng; không backfill lúc app boot. Workflow dừng HTTP, Connect, Study và projection units trước migration. Fresh deployment bỏ qua units chưa tồn tại; stop failure không được coi là quiesced.

[Old-code rollback guard](../../deploy/check_field_code_rollback.py) từ chối binary chỉ hiểu named storage sau 67. Muốn quay lại schema cũ phải restore backup riêng có đủ schema/data; không dùng generic downgrade hoặc tái tạo một live legacy store.

## MySQL qualification

Các probe chỉ ghi generated loopback schemas; configured source được fingerprint trước/sau. Fresh chain qua head68: 113 runtime tables + alembic_version, không seed users/subjects, không tái tạo retired Card/progress/named Field tables. [Fresh schema proof](artifacts/progress_scalability_fresh_field_contract_mysql_20261014.json).

Field contract [probe và isolated restore](artifacts/field_identity_cutover_mysql_nullable_restore_final_20261014.json) PASS: bounded crash/resume, archive coverage/checksums, physical contraction, source/added overrides, SQL NULL/JSON null shadow state, original raw named bytes restore vào database riêng. Đây là archive value restore rehearsal, không thay thế full application backup restore.

[Consumer MySQL proof](artifacts/field_value_consumers_mysql_final_20261014.json): 9/9 PASS, gồm Unicode/native arrays, nested numeric/bool content search, key exclusion, typed Connect identity, metadata-only rename, stable media, pinned hashes và recycled labels. Các artifact lỗi trước khi sửa được giữ để đối chiếu.

Full snapshot [recheck MySQL](artifacts/field_identity_full_snapshot_recheck_mysql_20261015.json) PASS: 41.534 live Notes, 33.936 media, 159 owned identity definitions; immutable archive giữ 41.533 Notes, 33.934 media và một rename job tại thời điểm cutover. Snapshot nguồn ngày15 đã ở head68; có thêm dữ liệu mới hợp lệ sau cutover. Source fingerprint trước/sau lượt copy không đổi; hai nonce-owned fixture schemas đã được xóa và kiểm tra.

[Lượt ngày14](artifacts/field_identity_full_snapshot_mysql_20261014.json) đã thực hiện đủ65→68 trên bản sao 41.533 Notes/33.934 media, contract/checksum PASS, nhưng overall FAIL vì fingerprint users/decks nguồn đổi trong khoảng chạy. [Lượt ngày15 ban đầu](artifacts/field_identity_full_snapshot_mysql_20261015.json) bị công cụ dùng nhầm pre-DDL equality gate cho live data sau cutover; recheck sửa đúng invariant, không sửa dữ liệu hoặc archive để làm pass. Các artifact âm được giữ.

Full snapshot không có historical override rows; source/added override provenance được chứng minh bằng isolated MySQL contract probe riêng. Legacy override thiếu stable provenance được giữ bằng typed `extra:` identity thay vì đoán mapping sang Field hiện hành. Timestamp bằng nhau ở DATETIME0 không chứng minh thứ tự; dữ liệu vẫn được archive losslessly.

## Writer B8 và worker

[Final benchmark](artifacts/review_projection_runtime_chronology_mysql_20261014.json), MySQL 8.0.40, isolated actual NOTE command fixture, 240 balanced randomized samples/mode:

| Mode | Command p95 | Added p95 | Added % | B8 |
|---|---:|---:|---:|---|
| Baseline | 54.912 ms | — | — | Reference |
| History outbox | 55.383 ms | 0.471 ms | 0.858% | PASS |
| History + deck invalidation | 58.034 ms | 3.122 ms | 5.685% | PASS |

B8 so sánh chênh lệch p95 giữa các mode theo budget trong kế hoạch. Paired per-round delta p95 vẫn nhiễu (9.111 ms history / 10.665 ms both), được lưu nguyên; không tuyên bố đạt một paired-tail SLO khác. Benchmark cuối sửa fixture chronology để đúng timestamp normalization của native review; các kết quả âm và diagnostic trước đó được giữ.

Writer capture snapshot từ flush sẵn có; unsafe/noncanonical SQL semantics dùng bounded DB reload. Cached Core outbox insert và atomic MySQL learner head giảm overhead; event/fact/receipt/outbox cùng transaction. Source revision được serialize theo commit order, không lấy MAX event ID làm coverage.

[Final outbox proof](artifacts/review_analytics_outbox_runtime_mysql_20261014.json): 33/33 MySQL contracts PASS. [Worker lag evidence](artifacts/review_projection_runtime_chronology_mysql_20261014.json) với 30 real commits và worker loop 1 s: lag p95 1058.557 ms, max 1102.237 ms; counters, revisions, state hashes và raw/summary parity đúng. Source/worker rollback, SAVEPOINT, gap/tamper, concurrency, retry và lost acknowledgement được kiểm tra.

Worker chọn learner theo pending row cũ nhất; index tránh đọc JSON payload khi discovery. EXPLAIN vẫn có aggregate temporary/filesort; không tuyên bố discovery constant-cost hoặc capacity vô hạn.

## Bằng chứng đọc thống kê của đợt trước

Các số sau là benchmark lịch sử trên fixture head64, 10 repetitions, cùng clock/snapshot; không phải phép đo lại ở head68. Dataset learner mẫu có 39.353 Notes, 119.223 events, 1.537 visible decks. Ready reads đạt payload parity và không issue raw history/progress SELECT, DML hoặc row locks.

| Operation | Raw p95 | Ready summary p95 |
|---|---:|---:|
| Overview | 1955.53 ms | 77.35 ms |
| Today/future | 2420.15 ms | 64.26 ms |
| Study-time/history | 306.31 ms | 15.89 ms |
| Dashboard, 1.537 decks | 1668.78 ms | 374.98 ms |
| Dashboard, 100 nodes | 609.66 ms | 57.57 ms |

[Full workload evidence](artifacts/progress_scalability_qualification_mysql_20261014.json), [100-node stage](artifacts/progress_scalability_dashboard_scope_mysql_20261014.json). Scope 100 nodes dùng parent-closed synthetic visibility override chỉ trong benchmark; whole dashboard 1.537 decks vượt scope đề xuất ≤100. Không suy ra production hit rate hoặc target concurrency từ những số này.

## Phạm vi còn cần qualification vận hành

Hai implementation task không giữ song song named live storage hay sync/async history writer. Read recovery/raw oracle và immutable historical artifacts phục vụ kiểm chứng/rollback dữ liệu, không phải một Field writer legacy thứ hai.

Benchmark local không chứng minh production traffic SLO. Canary thực tế, multi-user/pool/cold-cache/resource budgets, H 10k→100k→1m, cache hit rate trong active study và history/archive retention/full backup restore thuộc rollout vận hành. Count/due hiện dùng dependency stamps + worker rebuild; incremental subject delta và bounded recent tail là scope riêng trong báo cáo gốc.

Validation cuối: modular backend `flashcards,templates,deck_collaboration,connect_mcp,study,analytics,core` — 173 suites, 1.996 tests, PASS (7 skips). Các thay đổi guard/qualification/media rollback sau lúc nạp bộ test được kiểm lại bằng 76 focused tests, PASS. React browse/study 28 tests PASS; TypeScript + Vite production build PASS. Smoke entrypoint `wsgi:app` với SQLite isolated: HTTP200, normal boot không tạo tables, explicit schema creation chỉ có canonical Field store. `git diff --check` PASS. [Validation manifest](artifacts/progress_scalability_completion_validation_20261015.json).
