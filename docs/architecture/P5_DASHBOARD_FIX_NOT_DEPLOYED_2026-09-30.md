# P5: dashboard vẫn chậm sau khi merge #171/#172 — bản sửa chưa được deploy

> Ngày: 2026-09-30 (UTC 2026-09-29 23:35–23:50). Phạm vi: điều tra production và GitHub Actions bằng thao tác chỉ đọc. Chưa deploy, chưa sửa CI hay cấu hình VPS. Bối cảnh đường đọc cũ: [P5_DASHBOARD_TIMEOUT_USER1_2026-09-29.md](P5_DASHBOARD_TIMEOUT_USER1_2026-09-29.md); bản sửa: [P5_DASHBOARD_SQL_AGGREGATION_REVIEW_2026-09-29.md](P5_DASHBOARD_SQL_AGGREGATION_REVIEW_2026-09-29.md).

## 1. Kết luận

**Production vẫn chạy release `22f8695` (trước #171). Bản sửa dashboard/overview chưa bao giờ được deploy, nên màn dashboard vẫn đi qua reader khóa cũ.** Code không có lỗi: chạy chính commit `master` (`a7a15cf`) trên dữ liệu production cho user 1 mất 2,3 s (dashboard) và 2,5 s (overview).

Bản sửa bị kẹt vì cổng deploy trong CI chỉ nhìn diff của **lần push hiện tại**:

```text
merge #171 (46ac5f9)  plan: deploy=true   → mysql-contract FAIL (test flaky) → deploy skipped
merge #172 (a7a15cf)  plan: deploy=false  → CI xanh                          → deploy skipped
                      (diff 46ac5f9..a7a15cf chỉ có tests/test_note_analytics_read.py)
```

`deploy` được tính từ `diff(github.event.before, github.sha)`, không so với release đang chạy. Một push có code runtime mà không deploy được sẽ không bao giờ lên production nếu push kế tiếp chỉ sửa test/docs.

Xử lý: deploy `master` thủ công ngay (§5.1), rồi sửa cổng deploy để so với lần deploy thành công gần nhất (§5.2).

## 2. Timeline (UTC; JST = UTC+9)

| Thời điểm | Sự kiện | Nguồn |
|---|---|---|
| 29/09 12:57 | Deploy `22f8695` thành công. Đây là deployment thành công cuối cùng của môi trường `Flama` | GitHub Deployments `6735313671` |
| 20:11:45 | `apt-daily-upgrade` chạy. `flama.service` restart 20:12:26, MySQL restart 20:12:45 (buffer pool nguội). Không phải nguyên nhân | `journalctl` |
| 23:04:56 | Merge #171 → CI run `36643250239`: plan `deploy=true`; `mysql-contract` fail ở `test_overlay_install_dashboard_and_overview_equal_legacy` (so nguyên payload chứa `move_token` ký theo giây) → `deploy` skipped | GitHub Actions |
| 23:23:51 | Merge #172 (chỉ sửa test) → CI run `36644980731`: `changed_files = ["tests/test_note_analytics_read.py"]`, `deploy=false` → mọi job xanh, `deploy` skipped lúc 23:34:07 | log job `changes` |
| 23:34–23:37 (08:34–08:37 JST) | Mở dashboard: `/api/dashboard` 3 lần 504, 1 lần 200; `/api/statistics/overview` 2 lần 504, 2 lần 200 | nginx `access.log` |
| 23:36:28 | `/opt/flama/current` → `releases/22f86956…` | VPS |
| 23:38–23:40 | MySQL đang chạy truy vấn của reader cũ: một `SELECT` trên `study_progress_subjects` chạy ≥ 47 s, tiếp theo là một câu khác ≥ 21 s, cùng các câu `SELECT … FROM study_progress_states WHERE subject_id = 8579 FOR UPDATE` theo từng subject | `information_schema.processlist` |
| 23:44:53–23:45:06 | Chạy code `a7a15cf` chỉ-đọc trên dữ liệu production: user 1 dashboard 2,29 s, overview 2,47 s | §3.5 |

## 3. Bằng chứng

### 3.1 Release đang chạy khác `master`

- `readlink -f /opt/flama/current` → `/opt/flama/releases/22f86956d9496f32d2fea2cbf1ca74a2e82b549a`.
- Deployment `Flama` gần nhất có trạng thái `success` cũng là `22f86956`.
- Khác biệt runtime `22f8695..a7a15cf` gồm 9 file, tất cả trong `app/`. Không đổi `requirements.txt`, `models/`, `migrations/`, nên deploy chỉ thay code, không có migration:
  - `app/api/v1/analytics/routes.py`
  - `app/repositories/logical_overlay_scope_repository.py`
  - `app/repositories/note_analytics_read_repository.py`
  - `app/repositories/study_authority_repository.py`
  - `app/services/dashboard_service.py`
  - `app/services/deck_aggregation_service.py`
  - `app/services/stats_overview.py`
  - `app/services/study_analytics_read_service.py`
  - `app/services/study_authority_read_service.py`

### 3.2 Cổng deploy trong CI

- `.github/workflows/ci.yml` đặt `TEST_DIFF_BASE: ${{ github.event.pull_request.base.sha || github.event.before }}`. Với push lên `master`, đó là commit ngay trước lần push.
- `scripts/run_tests.py` `build_ci_change_plan()` tính `"deploy": matches_any(DEPLOY_RUNTIME_SOURCE_PATTERNS)` trên đúng diff đó. Comment ở đó ghi rõ ý đồ: *"Test/docs-only merges must not deploy."*
- Job `deploy` cần `needs: [changes, frontend, backend, spa-contract, redis-contract, mysql-contract]` và `needs.changes.outputs.deploy == 'true'`.

Hệ quả: lần push #171 có `deploy=true` nhưng một job validation fail; lần push #172 xanh nhưng `deploy=false`. Không có bước nào so `github.sha` với release đang chạy, nên code runtime của #171 bị bỏ rơi. Ý đồ "không deploy khi chỉ sửa test" đúng cho từng push đơn lẻ, sai khi push trước chưa deploy được.

Output của job `changes` ở run `36644980731`:

```json
{
  "changed_files": ["tests/test_note_analytics_read.py"],
  "deploy": false,
  "frontend": true,
  "mysql_contract": true,
  "redis_contract": true,
  "spa_contract": true
}
```

### 3.3 Request của màn dashboard

Màn dashboard (`frontend/src/features/dashboard/hooks/useDashboardPage.tsx`) gọi ba API: `GET /api/session`, `GET /api/dashboard`, `GET /api/statistics/overview?year=…&timezone=…`. Hai API sau chính là hai route mà #171 sửa.

nginx ghi thời điểm **kết thúc** request. Không có `proxy_read_timeout` trong `/etc/nginx/`, nên nginx dùng mặc định 60 s và trả 504 (578 byte). Các request 504 lúc 23:35:20 và 23:35:27 bắt đầu khoảng 23:34:20, tức ngay sau khi CI xanh.

```text
23:35:13 GET /api/statistics/overview … 200
23:35:20 GET /api/dashboard            504
23:35:20 GET /api/statistics/overview … 504
23:35:27 GET /api/statistics/overview … 504
23:35:27 GET /api/dashboard            504
23:36:01 GET /api/dashboard            200
23:36:14 GET /api/statistics/overview … 200
23:37:01 GET /api/dashboard            504
```

Gunicorn chạy `--workers 2 --threads 4 --worker-class gthread --timeout 120`, tức 8 slot xử lý. Sau khi nginx trả 504, backend vẫn tiếp tục tính và giữ khóa. Mỗi lần tải lại trang cộng thêm một phép tính khóa dài, nên chỉ một người dùng cũng có thể chiếm phần lớn app. Chi tiết ở F4/F5 của tài liệu 29/09.

### 3.4 MySQL lúc đang tải dashboard

Mẫu `information_schema.processlist` (user `flama` không có quyền `PROCESS`, nên không xem được `innodb_trx`):

```text
23:38:50 id=29 t=32 executing | SELECT study_progress_subjects.id, study_progress_subjects.learner_use…
23:39:05 id=29 t=47 executing | (cùng câu)
23:39:45 id=23 t=1  executing | SELECT study_progress_subjects.id, …
23:40:05 id=23 t=21 executing | (cùng câu)
…        id=23 t=0  SELECT study_progress_states.… FROM study_progress_states
                    WHERE study_progress_states.subject_id = 8579 FOR UPDATE
```

Các câu này khớp với `load_study_authority_card_reads` ở release `22f8695`: `classify_note_authority_keys`, rồi `lock_study_session_authority_subjects` khóa và đọc state từng subject, rồi contributor `with_for_update()`. Code mới trong analytics không còn đường đi này.

### 3.5 Code `master` trên dữ liệu production (chỉ đọc)

Cách làm:
- `git archive a7a15cf app models wsgi.py`, giải nén vào `/tmp` trên VPS.
- Chạy bằng user `flama`, env `/etc/flama/flama.env` và venv production, qua `systemd-run` như runbook.
- Gọi `build_dashboard_data` và `build_stats_overview` trong `analytics_read_transaction()` (`START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY`), rồi so số NOTE với số đếm từ `card_progress` trên cùng phạm vi.
- Đã xóa thư mục tạm sau khi đo.

| User | Dashboard | Overview | Tóm tắt | NOTE = projection |
|---|---|---|---|---|
| 1 | 2,29 s | 2,47 s | new 24.056, learn 2.064, due 12.905; future due 15.018 | ✅ |
| 4 | 1,01 s | 0,32 s | new 10.228, learn 128, due 665; future due 793 | ✅ |

So sánh: đường đọc cũ mất 119,5 s cho dashboard user 1 (đo 29/09).

## 4. Yếu tố phụ (không phải nguyên nhân sự cố này)

| # | Quan sát | Ảnh hưởng | Đề xuất |
|---|---|---|---|
| S1 | `innodb_buffer_pool_size` = 128 MB, giá trị mặc định của MySQL. VPS có 8 GB RAM (còn khoảng 4 GB khả dụng), 2 vCPU; database 1,2 GB | Các bảng dashboard chạm tới (`notes` 123 MB, `study_progress_contributors` 51 MB, `cards` 33 MB, `card_progress` 33 MB, `study_progress_subjects` 24 MB, `study_progress_states` 24 MB, `study_progress_availability` 13 MB, `study_authority_subject_tokens` 5,5 MB) cộng lại khoảng 300 MB, lớn hơn buffer pool. Từ lần restart 20:12: 170.821 lần đọc đĩa trên 16,7 triệu lần đọc (trượt khoảng 1%). Overview còn đọc `review_events` (98 MB) | Sau khi deploy, đo lại rồi cân nhắc tăng lên 1–2 GB, sau khi kiểm tra ngân sách RAM của các dịch vụ khác trên VPS dùng chung. Đo trước và sau bằng cùng script |
| S2 | `apt-daily-upgrade` restart MySQL và Flama (29/09 20:12 UTC) | Gián đoạn ngắn và buffer pool nguội sau mỗi lần nâng cấp gói | Đặt khung giờ cho unattended-upgrades vào lúc ít tải |
| S3 | Dịch vụ `tooldeploy-facebook-sync.service` (dự án khác trên cùng VPS) crashloop khoảng 15 s một lần vì `SyntaxError`; bộ đếm restart đã tới 93.816 | Liên tục tạo tiến trình mới trên máy 2 vCPU | Ngoài phạm vi Flama; báo chủ dịch vụ đó |
| S4 | Browse (cây và danh sách), `/api/statistics/today-future`, `/api/study/next`, trang học deck, MCP study tools vẫn dùng reader khóa và nạp toàn bộ Card của learner | Không nằm trên màn dashboard, nhưng dự kiến chậm tương tự với user 1 (chưa đo trên production để tránh khóa dữ liệu của user 1) | PR tiếp theo, dùng lại `note_analytics_read_repository` |

## 5. Xử lý

### 5.1 Ngay: deploy `master`

`deploy.yml` có `workflow_dispatch`, và job chỉ chạy trên `refs/heads/master`. `RELEASE_ID` là `github.sha`, tức head của `master` (`a7a15cf`). Deploy có health check và tự rollback symlink về release cũ khi không healthy.

```bash
gh workflow run deploy.yml --ref master
gh run watch "$(gh run list --workflow deploy.yml -L 1 --json databaseId --jq '.[0].databaseId')"
```

Kiểm chứng sau deploy:

1. `readlink -f /opt/flama/current` là `/opt/flama/releases/a7a15cf77807e9f78a80af3a2c50d69d2db0e331`.
2. Mở dashboard. nginx phải trả `200` cho `/api/dashboard` và `/api/statistics/overview`, không còn `504`.
3. Không còn truy vấn `… FOR UPDATE` trên `study_progress_*` khi mở dashboard (`processlist`).
4. Chạy `study-authority-read-audit` cho mọi learner NOTE lúc ít tải ([runbook §4.4](../runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md)).

### 5.2 Chống tái diễn: cổng deploy so với lần deploy thành công gần nhất

Đề xuất sửa trong `.github/workflows/ci.yml` và `scripts/run_tests.py`:

1. Job `changes` (chỉ khi push lên `master`) lấy SHA của deployment `Flama` gần nhất có trạng thái `success` qua GitHub Deployments API. Cần quyền `deployments: read`. Job `deploy` dùng `environment: Flama` nên GitHub đã tự ghi các bản ghi này.
2. `--ci-plan` nhận base đó (ví dụ `DEPLOY_DIFF_BASE`) và tính `deploy` trên `diff(DEPLOY_DIFF_BASE, github.sha)`. Validation vẫn dùng diff của event như hiện nay.
3. Nếu không lấy được base (API lỗi, chưa có deployment), dùng diff của event như hôm nay và in cảnh báo.
4. Test: push chỉ sửa test sau một push runtime chưa deploy phải cho `deploy=true`; push chỉ sửa docs/test khi release đã khớp phải cho `deploy=false`.

Trong lúc chưa sửa: sau mỗi lần merge vào `master`, kiểm tra job `deploy` ra **success**. Nếu ra **skipped** trong khi `master` có code runtime chưa deploy, chạy §5.1.

## 6. Việc đã làm và việc còn lại

| Việc | Trạng thái |
|---|---|
| Xác định release đang chạy, log nginx, processlist, cổng deploy CI | Xong (chỉ đọc) |
| Đo code `a7a15cf` trên dữ liệu production | Xong; đã xóa file tạm trên VPS |
| Deploy `master` (§5.1) | Xong qua PR #173 (release `6472e42`, 30/09 04:22 UTC) |
| Smoke và audit sau deploy | Xong: audit 18/18 PASS, dashboard user 1 ~3 s; từ 04:22 UTC không còn 5xx trong nginx |
| Sửa cổng deploy (§5.2) | Xong trong #173 (`DEPLOYED_RELEASE_SHA` từ GitHub Deployments, `run_tests.py --ci-plan`) |
| S1–S3 | Đề xuất; chưa làm (ngoài code) |
| S4 | `/api/study/next` đã bỏ N+1 trong #173; Browse, today-future, MCP vẫn qua reader khóa — theo dõi, chưa có 5xx |
