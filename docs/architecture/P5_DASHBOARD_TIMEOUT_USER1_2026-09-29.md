# P5 full NOTE: điều tra dashboard timeout của user 1 và phương pháp xử lý

> Ngày: 2026-09-29. Phạm vi: điều tra production bằng thao tác chỉ đọc, đối chiếu mã nguồn và đề xuất xử lý. Chưa sửa code ứng dụng, cấu hình VPS hoặc authority của learner.

## 1. Kết luận

**Nguyên nhân chính là đường đọc dashboard/thống kê của NOTE thực hiện quá nhiều truy vấn và giữ khóa ghi trên toàn bộ tập tiến độ của learner.** User 1 có **39.282 note/card có canonical state**; dashboard đồng thời gọi hai API cùng đi qua đường đọc này. Nginx hết thời gian chờ, còn backend tiếp tục làm việc và có request thất bại vì chờ khóa MySQL.

Chuỗi lỗi đã đối chiếu được:

```text
Mở Dashboard
  ├─ GET /api/dashboard
  └─ GET /api/statistics/overview?year=2026&timezone=Asia/Tokyo
       ↓ cả hai đọc tập trạng thái NOTE của learner
Tải hàng chục nghìn Card/Note + truy vấn lặp theo từng note/card
       ↓
SELECT ... FOR UPDATE trên subjects/state/token/contributor/availability
       ↓
Xử lý kéo dài + các request tranh chấp khóa
       ├─ Nginx trả 504 trong khi backend còn chạy
       └─ MySQL 1205 → backend trả 500
       ↓
Frontend nhận 504 → reportBackendUnavailable() → /maintenance
```

**Trang “bảo trì” là cách frontend phản ứng với lỗi upstream; không chứng minh server đang bật chế độ bảo trì.** Tại lúc kiểm tra, `flama.service` vẫn active và `/api/health` trả 200 trong khoảng 4,7 ms.

Ưu tiên: khôi phục khả năng sử dụng bằng rollback có kiểm chứng cho user 1 nếu cần ngay; sau đó sửa cả hai đường đọc analytics, loại bỏ truy vấn từng dòng và khóa ghi diện rộng. Tăng timeout hoặc số worker đơn thuần không giải quyết nguyên nhân.

## 2. Bằng chứng trực tiếp từ VPS

### 2.1 Release và môi trường

| Hạng mục | Giá trị quan sát |
|---|---|
| Release `/opt/flama/current` | `22f86956d9496f32d2fea2cbf1ca74a2e82b549a` |
| Checkout điều tra | `9510d11` |
| MySQL | `8.0.46-0ubuntu0.22.04.4` |
| Alembic head | `20260925_000045` |
| Authority | 18 learner đều NOTE, epoch 1 |
| Gunicorn thực chạy | `--workers 2 --threads 4 --worker-class gthread --timeout 120` |
| Pool mỗi worker | size 4, overflow 1, timeout 5 giây |
| MySQL isolation / lock wait | `REPEATABLE-READ` / 50 giây |
| Cờ | v4=1, new-learner-NOTE=1, shadow-write=1, shadow-backfill=0, async-batch=0 |
| Snapshot tài nguyên lúc 13:56 UTC | RAM tổng 7.936 MiB, available 3.989 MiB; service MemoryCurrent khoảng 1,87 GiB; load 1 phút 1,47 |

Đã so SHA-256 sau chuẩn hóa CRLF/LF: các file backend liên quan dưới đây trùng giữa checkout và release VPS: `dashboard_service.py`, `stats_overview.py`, `study_authority_read_service.py`, `study_note_pristine_service.py`, `study_authority_repository.py`, `study_session_authority_pin_service.py`, `scheduler_config_service.py`, `models/card.py`. Phân tích backend vì vậy áp dụng được cho release đang chạy dù SHA tổng khác nhau. Chưa xác minh SHA bundle frontend đang được Cloudflare Pages phục vụ; phần frontend được đối chiếu với repo.

### 2.2 Kích thước dữ liệu user 1

| Dữ liệu | Số lượng |
|---|---:|
| Note sở hữu | 39.282 |
| Card của các note đó | 39.282 |
| CardProgress của learner | 39.282 |
| StudyProgressSubject / State / AuthorityToken | Mỗi bảng 39.282 hàng thuộc learner |
| Active contributor / availability | Mỗi loại 39.282 |
| Deck sở hữu chưa xóa | 1.527 |
| Deck có note | 1.464 |
| DeckInstall | 0 |
| Tổng `OCTET_LENGTH(notes.field_values)` | 52,52 MiB |

Learner khác có progress: user 2 = 443, user 3 = 9, user 4 = 932, user 13 và 16 mỗi người 1. Quy mô của user 1 khiến chi phí theo từng dòng lộ rõ. Không có bằng chứng sự cố riêng của user 1 đến từ installed clone: tài khoản này không có `DeckInstall` tại snapshot.

Một phép GROUP BY chỉ đọc trên canonical availability trả 24.056 NEW, 1.844 learning, 220 relearning, 13.162 review. Đây là **phân bố queue**, không phải số due để hiển thị. NEW vẫn có canonical state nên vẫn đi qua vòng khóa/đọc stateful hiện tại.

### 2.3 Timeline lỗi ngày 29/09, múi giờ UTC

| Thời điểm | Bằng chứng |
|---|---|
| 13:50:42 | OPTIONS cho dashboard và overview xuất hiện cùng thời điểm |
| 13:51:42 | Nginx access log ghi **504 cho cả hai GET**; error log ghi `upstream timed out ... while reading response header from upstream` |
| 13:52:47 | Gunicorn mới ghi dashboard **200**, payload 727.689 byte, sau khi Nginx đã trả 504 |
| 13:53:16 | Nginx ghi thêm dashboard 504 |
| 13:53:57 | Backend dashboard trả **500**, MySQL **1205: Lock wait timeout exceeded** |
| 13:54:31 | Gunicorn ghi overview 200, payload 52.651 byte, sau lần timeout đầu |
| 13:54:59–13:55:00 | Nginx tiếp tục ghi overview/dashboard 504 |
| 13:56:18 | Backend overview trả **500**, cũng MySQL 1205 |
| 13:56:21 | Một dashboard khác kết thúc 200 |

Log hiện tại không có request ID hoặc `$request_time` để đo latency chính xác từng GET. Các mốc cho thấy backend có thể hoàn tất sau khi proxy đã bỏ cuộc; không lấy khoảng OPTIONS→200 làm benchmark chính xác hoặc p95.

Hai traceback 1205 đều chỉ tới:

```text
analytics/routes.py → dashboard_service.py hoặc stats_overview.py
→ study_authority_read_service.py:204
→ study_note_pristine_service.py:59
→ SELECT study_progress_subjects ... FOR UPDATE
```

Ngoài ra có deadlock **1213** lúc 13:33 ở MCP `create_note → materialize_new_note_authority → INSERT study_authority_subject_tokens`. Đây là lỗi đồng thời khác đã quan sát; chưa có lock graph để kết luận cùng blocker với dashboard.

## 3. Phát hiện trong mã nguồn

### F1 — Dashboard tải và xử lý lại toàn bộ dữ liệu khi ở NOTE

- **Quan sát:** [dashboard_service.py](../../app/services/dashboard_service.py), `build_dashboard_data()` chạy query CardProgress và đếm legacy trước, sau đó nhánh NOTE tải toàn bộ Card và thay lại bảng đếm. `card.note.deck_id` kích hoạt lazy load Note; query `.join(Note)` không tự eager-load quan hệ `Card.note`.
- **Bằng chứng:** nhánh NOTE khoảng dòng 243–331; [models/card.py](../../models/card.py):18 khai báo quan hệ không có eager loading. Với tập card 1:1 của user 1 và session chưa chứa Notes, phần này có thể thêm khoảng 39.282 SELECT Note, kéo theo cả `field_values` không cần cho bộ đếm.
- **Ảnh hưởng:** vừa làm phần đếm sẽ bị bỏ đi, vừa tốn round trip, dựng ORM object và RAM. Payload dashboard khoảng 711 KiB cũng đáng tối ưu sau backend.
- **Giới hạn:** chưa đo RSS riêng từng request hoặc số SQL bằng listener trên request thật; 52,52 MiB là kích thước field trong DB, không phải mức tăng RAM đã đo.

### F2 — Reader dùng cho thống kê khóa toàn tập và truy vấn token/state theo từng note

- **Quan sát:** [study_authority_read_service.py](../../app/services/study_authority_read_service.py):204 gọi `classify_note_authority_keys()` với mặc định `for_update=True`; tiếp tục gọi `lock_study_session_authority_subjects()` và khóa contributors/availability.
- **Bằng chứng:** [study_note_pristine_service.py](../../app/services/study_note_pristine_service.py):39 chia chunk 500 nhưng vẫn `FOR UPDATE`. [study_session_authority_pin_service.py](../../app/services/study_session_authority_pin_service.py):142 lặp từng logical note; [study_authority_repository.py](../../app/repositories/study_authority_repository.py):200 lấy token và state bằng **hai SELECT FOR UPDATE riêng mỗi subject**.
- **Ảnh hưởng:** 39.282 subject → **78.564 SELECT token/state cho mỗi lần reader hoàn tất**, cộng query phân loại, sibling/progress, mapping/hash và validation. Đây là phép đếm từ mã nguồn với cardinality thực tế, không phải số query đo riêng một request. Chia chunk 500 ở bước phân loại không làm transaction nhả khóa sau mỗi chunk.
- **Ảnh hưởng đồng thời:** hai API cùng learner chạm các subject giống nhau bằng khóa độc quyền. Giữ khóa qua thời gian đọc/decode toàn tập làm GET có thể chặn GET khác và writer.
- **Giới hạn:** traceback đã xác nhận vị trí chờ khóa; chưa thu được cặp transaction blocker/waiter đúng thời điểm lỗi. Không xóa cơ chế fence của writer/session để chữa triệu chứng này.

### F3 — Overview bổ sung hai query cấu hình cho từng card

- **Quan sát:** [stats_overview.py](../../app/services/stats_overview.py):148, `_canonical_future_due_day_counts()` tải mọi card có progress của learner, không lọc trước theo khoảng thời gian; gọi `resolve_deck_options()` trong comprehension theo từng card.
- **Bằng chứng:** [scheduler_config_service.py](../../app/services/scheduler_config_service.py):97, :142, :154 truy vấn `UserSchedulerSettings.filter_by(...).first()` và `Deck.filter_by(...).first()` mỗi lần; không có cache trong vòng này. Còn có lazy load `card.note` rồi reader ở F2.
- **Ảnh hưởng:** riêng hai query settings/deck thêm **78.564 SELECT** với 39.282 card, dù nhiều card chung deck và cùng user. Sau đó mới lọc `due_at` trong Python. Sửa dashboard mà bỏ overview thì trang vẫn có thể bị đưa sang maintenance.
- **Giới hạn:** con số này là suy ra từ đường chạy; chưa tách thời gian query/network/ORM/decode bằng profiler.

### F4 — Timeout bị biến thành thông báo bảo trì toàn ứng dụng

- **Quan sát:** [useDashboardPage.tsx](../../frontend/src/features/dashboard/hooks/useDashboardPage.tsx):21 tạo dashboardQuery và overviewQuery ngay khi mở trang; không có điều kiện chờ query kia hoàn tất.
- **Bằng chứng:** [backendAvailability.ts](../../frontend/src/shared/api/backendAvailability.ts):5 chứa 502/503/504/521–524. [client.ts](../../frontend/src/shared/api/client.ts):177 gọi `reportBackendUnavailable()` khi gặp các status này. [App.tsx](../../frontend/src/App.tsx):637 chuyển router tới `/maintenance`.
- **Ảnh hưởng:** một API thống kê chậm đủ làm mất toàn bộ trang, kể cả health hoặc phần khác vẫn hoạt động. Các `StudyAuthorityReadError` được analytics route trả 409; còn SQL OperationalError 1205 đi tới handler 500, không phải một mã “maintenance” nghiệp vụ.
- **Giới hạn:** chưa kiểm tra bundle frontend thực tế bằng browser; chuỗi 504 được xác nhận ở Nginx và khớp hành vi người dùng báo cùng mã nguồn repo.

### F5 — Cấu hình timeout không giới hạn được công việc ở backend như mong đợi

- **Quan sát:** `nginx -T` không có override `proxy_read_timeout`; lỗi xuất hiện khoảng 60 giây sau đợt preflight. Nginx mặc định chờ 60 giây giữa các lần đọc upstream. Khi backend chưa gửi header, nó đóng kết nối nếu quá thời gian này. [Tài liệu Nginx](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_read_timeout).
- **Bằng chứng:** service thực chạy `gthread`, timeout 120, có access log 200 sau proxy 504. Với worker không đồng bộ, timeout Gunicorn theo dõi worker còn giao tiếp, không phải deadline cứng cho một request. [Tài liệu Gunicorn](https://docs.gunicorn.org/en/stable/settings.html?highlight=heartbeat#timeout).
- **Ảnh hưởng:** refresh có thể tạo thêm request trong khi request cũ vẫn giữ khóa/tốn tài nguyên. Tăng timeout proxy chỉ kéo dài việc chờ; tăng worker/thread có thể tăng số transaction tranh khóa và RAM.
- **Giới hạn:** snapshot RAM còn khoảng 4 GiB available và service active không loại trừ áp lực tài nguyên ở mọi thời điểm. Chưa có bằng chứng OOM hay cạn connection pool là nguyên nhân chính.

## 4. Đối chứng MySQL và giới hạn kết luận

Performance Schema có các digest sau đang được dùng tới khoảng 13:55–13:56:

| Nhóm SELECT | COUNT_STAR tích lũy |
|---|---:|
| `study_progress_states` | 391.778 |
| `study_authority_subject_tokens` | 327.445 |
| Lazy-load `notes` | 298.194 |
| `user_scheduler_settings` | 180.738 |
| `decks` | 172.705 |

**Đây là bộ đếm tích lũy từ lúc MySQL thu thập/reset digest**, gồm các tác vụ khác; lọc `LAST_SEEN` không biến chúng thành số query riêng của sự cố hoặc user 1. Chúng củng cố dấu hiệu query lặp. Digest SELECT subjects có `MAX_TIMER_WAIT ≈ 50,01 giây` và 2 lỗi, phù hợp lock wait 50 giây và hai traceback 1205.

Các index quan trọng đã có trên production: `uq_sp_subject_user_note(learner_user_id, logical_note_key)`, PK token/state trên `subject_id`, PK availability trên `contributor_id`, cùng index availability theo subject/queue/due. Không có cơ sở coi việc thêm một index chung chung là cách sửa chính.

Một SELECT không khóa, join subject→active contributor→availability và GROUP BY queue cho user 1 hoàn tất trong **0,119 giây**, gồm cả khởi chạy mysql client trên VPS. Đây chỉ là phép đo khả năng tổng hợp dữ liệu, **không phải dashboard tương đương**: chưa xử lý due/day boundary, pristine, quyền/deck tree, overlay, token/hash parity hay kiểm tra corruption. Không dùng query thử này thay trực tiếp reader production.

## 5. Phương pháp xử lý

### 5.1 Khôi phục tạm nếu cần dùng ngay

1. Ngừng refresh liên tục dashboard của user 1; đóng các tab đang tự tải lại để không nối thêm request vào hàng chờ. Chờ request đang chạy kết thúc và kiểm tra transaction/lock wait trước khi thao tác authority.
2. **Phương án ưu tiên khi cần phục hồi ngay: rollback riêng user 1 về LEGACY qua CLI có kiểm chứng lossless.** Xem [runbook P5, mục 4.5](../runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md#45-rollback-một-learner-note--legacy). Chạy dry-run trước; chỉ apply khi kiểm chứng thành công. Dry-run vẫn dựng transaction và lấy khóa, không phải phép SELECT nhẹ; với gần 40.000 subject cần cửa sổ ít tải và phiên quản trị bền vững.
3. Sau rollback, mở lại phiên học mới để lấy authority epoch mới; không xóa pending answers/offline queue. Kiểm tra các phiên cũ nhận stale epoch đúng contract và tiến độ vẫn giữ nguyên.
4. Nếu rollback bị chặn do projection/algorithm hoặc yêu cầu phải giữ NOTE, giữ dữ liệu hiện tại và triển khai bản sửa reader bên dưới. Không sửa `mode_code` bằng SQL.

Các lệnh sau là **hướng dẫn vận hành, chưa được chạy trong lần điều tra này**:

```bash
# Chạy trên VPS bằng tài khoản quản trị trong cửa sổ ít tải.
flama_cli() {
  systemd-run --quiet --wait --collect --pipe \
    --property=User=flama --property=Group=flama \
    --property=WorkingDirectory=/opt/flama/current \
    --property=EnvironmentFile=/etc/flama/flama.env \
    --setenv=STARTUP_RUN_MAINTENANCE=0 \
    /opt/flama/venv/bin/flask --app wsgi.py "$@"
}

# Bước 1: proof rồi rollback transaction; kiểm tra exit code và JSON.
flama_cli study-authority-enrollment --user-id 1 --mode LEGACY

# Bước 2: chỉ chạy sau khi bước 1 pass và đã quyết định rollback.
flama_cli study-authority-enrollment --user-id 1 --mode LEGACY --apply
```

CLI thực tế nằm ở [app/cli.py](../../app/cli.py):288. Cần snapshot/backup hiện hành theo runbook trước thay đổi authority. Nếu báo `LOSSY_LEGACY_PROJECTION`, `UNPROJECTABLE_LEGACY_STATE` hoặc `ROLLBACK_ALGORITHM_NOT_LEGACY`, dừng và sửa tiến; không ép thành LEGACY. Không downgrade schema hoặc deploy mù về code trước NOTE khi DB vẫn có learner NOTE.

Tắt `STUDY_WIRE_V4_ENABLED` hoặc `STUDY_PROGRESS_SHADOW_*` **không chuyển persisted authority về LEGACY**. Giữ contract cần thiết cho learner NOTE khác. Nếu tạm dừng rollout cho tài khoản mới, dùng riêng `STUDY_NEW_LEARNER_NOTE_ENABLED=0`; cờ này không chữa user 1 đã enroll.

### 5.2 Sửa tận gốc — cả dashboard và overview

Các mục dưới là kế hoạch triển khai cần được kiểm chứng, không phải thay đổi đã áp dụng hoặc thiết kế schema mới.

| Ưu tiên | Thay đổi | Điều kiện giữ đúng |
|---|---|---|
| P0 | Chọn nhánh NOTE/LEGACY trước khi chạy bộ đếm dashboard; tránh query/loop legacy rồi bỏ kết quả | Summary và quyền xem deck không đổi |
| P0 | Đọc scalar metadata cần thiết như card ID, note ID, deck ID, note type; nếu cần ORM thì eager-load có giới hạn cột | Không kéo toàn bộ `Note.field_values` cho analytics |
| P0 | Load settings một lần/request, preset/options một lần/deck; áp dụng ở overview | Giữ preset, timezone và boundary đúng user/deck |
| P0 | Thay vòng SELECT token/state từng subject bằng các query batch, kiểm tra coverage/generation/revision/hash đầy đủ | Không bỏ fail-closed hoặc bỏ kiểm tra sibling corruption chỉ để tăng tốc |
| P0 | Tách reader phục vụ tổng hợp khỏi helper cấp session/ghi NOTE đang lấy khóa độc quyền toàn tập | Writer/session vẫn giữ fence, CAS và thứ tự khóa hiện có |
| P1 | Tổng hợp counts/forecast bằng canonical availability với scope chính xác; giảm dữ liệu trả về Python | Giữ trạng thái pristine, suspension/bury, due_day/due_at và overlay scope |
| P1 | Ghi timing từng request, query count, lock wait; thêm cache ngắn sau khi reader đã nhanh | Cache phải tách user/authority epoch/timezone/boundary và invalidation sau mutation |
| P1 | Cải thiện frontend: lỗi một widget có retry cục bộ; kiểm tra backend trước khi chuyển cả app sang maintenance | Không nuốt 401/409 hay lỗi integrity; tránh retry chồng request |

Hướng cần thử cho analytics: transaction đọc ngắn với **một snapshot nhất quán**, batch các hàng cần kiểm tra rồi tổng hợp; tránh khóa ghi trên mọi subject chỉ để đếm. MySQL hỗ trợ consistent nonlocking read, nhưng phải thiết kế rõ việc lấy enrollment/epoch và snapshot vì request Flask có thể đã mở transaction từ bước auth. Không trộn tùy tiện current locking read với dữ liệu từ snapshot cũ. [Tài liệu MySQL](https://dev.mysql.com/doc/refman/8.0/en/innodb-consistent-read.html).

Không sửa bằng cách xóa mọi `.with_for_update()` khỏi helper dùng chung. Tách contract analytics ra trước, kiểm chứng đọc đồng thời với review/enroll/delete/first-state, rồi mới đổi call site. Nếu chuyển full parity audit ra tác vụ riêng, phải có quyết định contract rõ ràng và cơ chế phát hiện/hiển thị corruption; không tự động trả số 0 hoặc fallback legacy khi NOTE không hợp lệ.

Batching giảm query trước là bước sửa ít thay đổi hành vi, nhưng **batching một mình chưa bảo đảm hết tranh khóa**. Nếu vẫn khóa toàn bộ 39.282 subject trong cùng transaction, phải đo lại hold time và concurrency; không tuyên bố xử lý xong chỉ vì request đơn lẻ nhanh hơn.

Không chỉ tuần tự hóa hai query ở frontend: việc này giảm tự tranh khóa trong một tab, nhưng không sửa N+1 và vẫn gặp lại khi mở hai tab hoặc có writer đồng thời. Không ưu tiên tăng worker, bật async study, xóa progress/reseed hoặc nâng RAM để giải quyết lỗi đã thấy.

## 6. Cách kiểm chứng bản sửa

1. Dựng cohort MySQL 8.0.46 riêng: 1.000, 10.000, khoảng 40.000 note/card, tương ứng NOTE có state; thêm tập pristine và note nhiều sibling. Không load-test bằng cách spam user 1 trên VPS đang lỗi.
2. Đo mỗi endpoint đơn lẻ rồi hai endpoint đồng thời; tiếp tục hai tab cùng learner và đọc đồng thời với một review/first-state. Ghi wall time, query count, SQL time, lock wait, peak RSS, status; kiểm tra cả qua Nginx và trực tiếp backend.
3. Dùng cùng `now`, timezone và day boundary để so kết quả với contract hiện có trên dữ liệu kiểm soát: NEW/learn/review, due trong tương lai, buried/suspended, midnight/boundary, pristine, owned/overlay/admin. User 1 không có overlay nhưng bản sửa dùng chung vẫn phải kiểm tra overlay và quyền.
4. Tiêm missing token/state/availability, generation/hash lệch và sibling progress lệch: vẫn fail-closed; dữ liệu NOTE không được âm thầm thay bằng legacy. Reader analytics không được tạo token, materialize state hoặc commit mutation.
5. Đọc cùng lúc enroll/rollback phải nhất quán mode/epoch; write/CAS/idempotent receipt và offline pending events giữ đúng contract.
6. Chạy test theo module, không chạy full suite cho báo cáo này:

   ```bash
   python scripts/run_tests.py --module analytics --backend-only
   python scripts/run_tests.py --module study --backend-only
   # Nếu có thay frontend, chạy nhóm bị ảnh hưởng từ root repo:
   python scripts/run_tests.py --changed --frontend-only
   ```

   Tham khảo test hiện có: [test_stats_overview.py](../../tests/test_stats_overview.py), [test_stats_today_future.py](../../tests/test_stats_today_future.py), [test_study_session_api.py](../../tests/test_study_session_api.py), [test_study_note_overlay.py](../../tests/test_study_note_overlay.py), [test_study_session_authority_pin_service.py](../../tests/test_study_session_authority_pin_service.py). SQLite không chứng minh hết lock behavior của MySQL.
7. **Mục tiêu nghiệm thu đề xuất, chưa đạt/đo:** ở cohort 40.000, p95 mỗi API dưới 2 giây khi chạy đơn và dưới 5 giây khi dashboard/overview chạy đồng thời; không 500/504/1205/1213, không query settings/note/token/state riêng từng dòng, không khóa độc quyền toàn bộ tập learner trong analytics. Đo đủ mẫu sau warm-up và ghi rõ tải/cấu hình.
8. Sau triển khai, smoke user 1 và learner nhỏ, theo dõi lỗi/latency/lock wait; chỉ enroll lại user 1 nếu đã rollback và reader mới đạt yêu cầu. `/api/health` 200 không đủ để kết luận dashboard đã tốt.

## 7. Lệnh chẩn đoán cho lần tái diễn

Chạy read-only, giới hạn thời gian; tránh dump toàn bộ env, cookie, token hoặc nội dung note vào log chia sẻ.

```bash
readlink -f /opt/flama/current
systemctl show flama.service -p ActiveState -p NRestarts -p MemoryCurrent -p ExecStart
journalctl -u flama.service --since '-20min' --no-pager
tail -n 100 /var/log/nginx/error.log
curl --max-time 5 -sS -o /dev/null -w 'http=%{http_code} total=%{time_total}\n' \
  http://127.0.0.1:4789/api/health
```

Trong mysql client của quản trị viên:

```sql
SET SESSION MAX_EXECUTION_TIME = 5000;
SELECT learner_user_id, mode_code, epoch
FROM flama.study_authority_enrollments WHERE learner_user_id = 1;

SELECT trx_mysql_thread_id, trx_state, trx_started, trx_wait_started,
       trx_rows_locked, trx_rows_modified
FROM information_schema.innodb_trx;

SELECT r.OBJECT_NAME, r.INDEX_NAME, r.LOCK_MODE AS waiting_mode,
       w.REQUESTING_THREAD_ID, w.BLOCKING_THREAD_ID
FROM performance_schema.data_lock_waits w
JOIN performance_schema.data_locks r
  ON r.ENGINE = w.ENGINE AND r.ENGINE_LOCK_ID = w.REQUESTING_ENGINE_LOCK_ID
WHERE r.OBJECT_SCHEMA = 'flama';
```

Chụp lock graph **trong lúc request treo**; snapshot sau khi request kết thúc có thể rỗng. Bổ sung `$request_time`, `$upstream_response_time`, request ID vào access log ở đợt sửa để nối browser→Nginx→Flask. Thu query count/timing theo request bằng telemetry không ghi SQL parameters; không bật general query log toàn production lâu dài.

## 8. Việc đã làm và việc còn thiếu

- Đã đọc log production, trạng thái service/health, cấu hình liên quan, schema/index, cardinality và Performance Schema; đối chiếu tám file backend với release. Các truy vấn kiểm tra dữ liệu là SELECT, có giới hạn thời gian cho các phép thống kê.
- Đã xác nhận 504 ở proxy, 1205 ở canonical reader, quy mô user 1 và các vòng query/khóa gây khuếch đại chi phí. Có phép đối chứng tổng hợp queue 0,119 giây, không dùng làm bằng chứng latency của API hoàn chỉnh.
- Chưa chạy lại full dashboard qua tài khoản giả lập trên production vì đường GET hiện tại lấy khóa lớn và có helper có khả năng tạo token nếu thiếu. Chưa chạy enrollment/audit/rollback hoặc restart dịch vụ.
- Chưa có request-level profiler, lock graph tại thời điểm sự cố, frontend deployed SHA hoặc benchmark sau sửa. Chưa chạy test ứng dụng vì thay đổi lần này chỉ là tài liệu.
- Runbook P5 đã có chỉnh sửa sẵn trong working tree trước lúc điều tra; báo cáo này không sửa đè file đó.
