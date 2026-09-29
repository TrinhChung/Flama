# P5 dashboard: review nhánh `perf/p5-dashboard-sql-aggregation` và phương án sửa

> Ngày: 2026-09-29. Phạm vi: review 6 commit sửa truy vấn dashboard/overview (`5fe7755`, `0806a6d`, `4f1e496`, `1f95790`, `97f357e`, `e5e92aa`) so với gốc `9510d11`, đối chiếu với báo cáo điều tra [P5_DASHBOARD_TIMEOUT_USER1_2026-09-29.md](P5_DASHBOARD_TIMEOUT_USER1_2026-09-29.md). Trạng thái được đánh giá tại HEAD `e5e92aa`. Tài liệu này chỉ mô tả phát hiện, nguyên nhân và phương án sửa; **chưa sửa code ứng dụng**. Các đoạn code trong mục 4–5 là phác thảo để định hướng, chưa được chạy.

> **Cập nhật 2026-09-30:** kế hoạch đã được rà soát lại theo kế hoạch decoupling ([mục 7](#7-rà-soát-kế-hoạch-và-điều-chỉnh-theo-decoupling-2026-09-30)) và bước 1–4 đã triển khai ([mục 8](#8-kết-quả-triển-khai-2026-09-30)). Mục 1–6 dưới đây giữ nguyên như lúc review `e5e92aa`.

## 1. Kết luận

**Chưa nên merge ở HEAD `e5e92aa`.**

Phần hiệu năng đã đúng hướng:

- Dashboard đếm bằng một truy vấn SQL không khóa, khoảng 0,7 giây ở quy mô user 1.
- Overview đã bỏ `FOR UPDATE` và các vòng query theo từng card.
- Lỗi overview trả 500 trên MySQL (R1) đã được sửa ở `97f357e`/`e5e92aa`; mình đã kiểm chứng lại trên MySQL 8.0.

Tuy vậy, **cả hai endpoint vẫn không fail-closed khi dữ liệu NOTE lệch** (R2, R9). Đây đúng là điều báo cáo điều tra yêu cầu phải giữ. Cộng thêm các lệch phân loại và hành vi còn tồn tại, nhánh chưa sẵn sàng.

| ID | Mức | Phát hiện | Trạng thái tại `e5e92aa` |
|---|---|---|---|
| R1 | Chặn merge | Overview trả 500 (MySQL 1792) dưới transaction `READ ONLY` | **Đã sửa**: kiểm chứng trên MySQL 8.0, overview/dashboard/today-future NOTE đều trả 200 |
| R2 | Chặn merge | Dashboard NOTE đếm từ `card_progress`, không kiểm tra parity, nên fail-open | **Chưa sửa**: chỉ thêm kiểm tra "có token"; probe vẫn trả 200 với số đếm sai |
| R3 | Cao | Phân loại SQL lệch helper chuẩn (review `due_day` NULL; queue lạ/rỗng) | **Chưa sửa**: tái hiện lại được |
| R4 | Cao | Overview giữ nguyên F2/F3 (N+1, khóa toàn tập, 2 query cấu hình mỗi card) | **Đã sửa phần lớn**, nhưng phát sinh R9–R12 |
| R5 | Trung bình | Admin ở chế độ NOTE nay bị cộng card overlay | **Chưa sửa** |
| R6 | Thấp | Thứ tự ưu tiên `deck_note_types` bị đảo, kết quả không cố định | **Chưa sửa** |
| R7 | Trung bình | Test/CI không có MySQL thật; test NOTE dashboard không còn kiểm tra gì thực chất | **Một phần**: có test không khóa cho overview, nhưng phần MySQL chỉ là mock |
| R8 | Thấp | Code chết, docstring sai, cờ chưa khai báo | **Một phần**: cờ đã khai báo; code chết và docstring vẫn còn |
| **R9** | **Chặn merge** | **Overview NOTE tự động fallback sang `card_progress` khi không có dòng availability nào, nên fail-open** | **Mới**: tái hiện, gốc trả 409, HEAD trả 200 và đếm theo dữ liệu lệch |
| **R10** | Trung bình | `check_note_authority_integrity` quá yếu (chỉ kiểm token) nhưng phạm vi quá rộng (mọi subject của learner) | **Mới** |
| **R11** | Trung bình | Overview NOTE đổi ngữ nghĩa future-due sang thuật toán LEGACY | **Mới**: có thể là mong muốn, nhưng cần quyết định và test |
| **R12** | Thấp | Truy vấn availability của overview không lọc contributor `ACTIVE` hay card còn sống | **Mới** |

Thứ tự sửa đề xuất ở [mục 5](#5-kế-hoạch-sửa-đề-xuất).

## 2. Phạm vi và cách kiểm chứng

### 2.1 Commit được review

| Commit | Nội dung |
|---|---|
| `5fe7755` | Thêm `app/services/deck_aggregation_service.py` và test `tests/test_deck_aggregation_service.py` |
| `0806a6d` | Thêm `read_study_authority_route()` (không khóa), `analytics_read_transaction()` (snapshot READ ONLY), tách `validate_study_authority_projection()` |
| `4f1e496` | Dashboard chuyển sang `aggregate_deck_study_counts`; bọc dashboard và overview trong `analytics_read_transaction()`; `logical_overlay_cards` bỏ lazy-load `card.note` |
| `1f95790` | Cập nhật mapping `scripts/run_tests.py` cho module analytics |
| `97f357e` | Overview dùng `read_study_authority_route`, bỏ reader khóa và vòng `resolve_deck_options` theo card |
| `e5e92aa` | Gọi `check_note_authority_integrity` ở dashboard và overview; `_canonical_future_due_day_counts` mới đọc availability (có fallback `card_progress`); khai báo `STUDY_NOTE_COUNT_ENABLED`; fixture test mặc định tạo token khi enroll |

### 2.2 Cách kiểm chứng

- **SQLite (bộ test hiện có, tại `e5e92aa`):** `python scripts/run_tests.py --module analytics --backend-only` pass 36 test. Nhóm `test_study_note_overlay`, `test_study_session_api`, `test_rest_api_v1`, `test_rest_only_runtime`, `test_deck_api_hierarchical_create` pass 115 test.
- **MySQL 8.0 thật** (Docker `mysql:8.0`, cấu hình mặc định): chạy lại các test NOTE có sẵn trong `tests/test_study_session_api.py` bằng một lớp con đổi `SQLALCHEMY_DATABASE_URI`. Chạy trên gốc `9510d11`, trên `1f95790` (trước bản sửa R1) và trên `e5e92aa`. Ngoài ra chạy SQL thủ công để xác nhận hành vi `READ ONLY` với `FOR SHARE`/`FOR UPDATE`.
- **Probe hành vi (SQLite, dùng fixture có sẵn):** làm lệch riêng `card_progress` của learner NOTE, rồi gọi `/api/dashboard` và `/api/statistics/overview`. So từng trường hợp phân loại giữa `aggregate_deck_study_counts` và `study_repository.counter_bucket_for_progress_values`.
- **Benchmark:** seed MySQL ở quy mô user 1 (1.527 deck, 39.282 note/card/progress, cùng phân bố queue 24.056 NEW / 1.844 learning / 220 relearning / 13.162 review, `field_values` khoảng 1,3 KB/note), đo `aggregate_deck_study_counts` tại `1f95790`.
- Script tái hiện ở [Phụ lục](#9-phụ-lục-tái-hiện).

**Giới hạn:**

- MySQL chạy local, không có độ trễ mạng, không có tải đồng thời hay writer chạy song song.
- Chưa seed các bảng NOTE (`study_progress_*`) ở quy mô 40k, nên chưa benchmark truy vấn availability của overview.
- Benchmark dashboard đo trước `e5e92aa`; commit này chỉ thêm một anti-join kiểm tra token, chưa đo lại.
- Không có thao tác nào trên production.

## 3. Những phần làm tốt, nên giữ

- **Dashboard aggregate:** trên dữ liệu quy mô user 1, `aggregate_deck_study_counts` chạy **1,17 giây lần đầu, 0,63–0,70 giây khi đã warm, 3 câu SQL, không có locking read**. Để so sánh, đường NOTE cũ phải tải toàn bộ Card, lazy-load khoảng 39k Note, và chạy khoảng 78k SELECT token/state kèm `FOR UPDATE` (F1/F2).
- **Overview NOTE (`97f357e`/`e5e92aa`):** không còn `FOR UPDATE`, không còn lazy-load `card.note`, không còn khoảng 78k query `resolve_deck_options` (F3). Chỉ còn một truy vấn availability và một anti-join token.
- **`read_study_authority_route()`** (`app/repositories/study_authority_repository.py:131`): đọc enrollment không khóa; nay dùng cho cả dashboard lẫn overview.
- **`logical_overlay_cards()`**: `add_columns(Note.deck_id)` bỏ lazy-load; Browse (`browse_card_service.py:200`) cũng hưởng lợi.
- **`analytics_read_transaction()`**: dùng một snapshot nhất quán, `READ ONLY`, từ chối nếu còn thay đổi chưa flush. Sau `97f357e`, toàn bộ đường đọc bên trong đã không còn locking read.
- **`STUDY_NOTE_COUNT_ENABLED`** đã được khai báo trong `app/settings.py:209`, mặc định tắt.

### 3.1 Đối chiếu với kế hoạch 5.2 của báo cáo điều tra (tại `e5e92aa`)

| Hạng mục trong báo cáo | Dashboard | Overview |
|---|---|---|
| P0: chọn nhánh NOTE/LEGACY trước khi đếm | Đã làm | Đã làm |
| P0: chỉ đọc cột scalar, không kéo `field_values` | Đã làm | Đã làm |
| P0: load settings/options một lần | Không còn cần | Đã làm (bỏ hẳn) |
| P0: batch token/state, **giữ kiểm tra coverage/generation/revision/hash đầy đủ** | **Chỉ kiểm tra có token** (R2, R10) | **Chỉ kiểm tra có token, kèm fallback legacy** (R9, R10) |
| P0: tách reader analytics khỏi helper khóa | Đã làm | Đã làm |
| P1: tổng hợp bằng canonical availability | **Dùng `card_progress` thay vào** (R2) | Đã làm, nhưng có fallback (R9) |
| P1: telemetry, cache | Chưa | Chưa |
| P1: frontend không chuyển cả app sang `/maintenance` | Chưa | Chưa |

## 4. Phát hiện chi tiết

### R1 — Overview trả 500 trên MySQL dưới transaction `READ ONLY` (đã sửa)

**Hiện tượng (tại `1f95790`).** `GET /api/statistics/overview` trả `500 INTERNAL_ERROR` cho mọi learner NOTE có note đã học. Log có dòng `OperationalError (1792, 'Cannot execute statement in a READ ONLY transaction.') [SQL: SELECT study_progress_subjects ... FOR UPDATE]`.

**Nguyên nhân.** `4f1e496` bọc overview trong `START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY` (`study_analytics_read_service.py:31`), nhưng bên trong vẫn là reader khóa ghi:

```text
build_stats_overview -> _canonical_future_due_day_counts (cũ)
  -> load_study_authority_card_reads -> classify_note_authority_keys(for_update=True)
     -> SELECT study_progress_subjects ... FOR UPDATE   => ERROR 1792
```

Quy tắc của MySQL: trong transaction `READ ONLY`, locking read `FOR UPDATE` trên bảng thường bị từ chối với lỗi 1792, còn `FOR SHARE` vẫn được phép. Mình đã xác nhận bằng SQL thủ công ([Phụ lục A](#a-hành-vi-read-only-trên-mysql-80)). Reader cũ còn có nhánh INSERT token khi thiếu (`study_authority_repository.py:267–275`), nhánh này cũng sẽ bị chặn.

**Trạng thái.** `97f357e` thay `lock_study_authority_route` bằng `read_study_authority_route` (`stats_overview.py:381`) và bỏ reader khóa. Chạy lại trên MySQL 8.0 tại `e5e92aa`: overview, dashboard và today-future của learner NOTE đều trả **200**.

**Việc còn lại để không tái phát.**

- Nguyên tắc: mọi hàm chạy trong `analytics_read_transaction()` phải không khóa và không ghi.
- Test `test_analytics_read_transaction_isolation_and_write_safety` mới chỉ **mock** session MySQL: nó chỉ khẳng định câu `START TRANSACTION` được gửi đi, không chứng minh hành vi thật. Lỗi 1792 chỉ lộ ra khi chạy trên MySQL thật, vì SQLite không render `FOR UPDATE`. Xem [R7](#r7--test-và-ci-chưa-có-mysql-thật).

---

### R2 — Dashboard NOTE vẫn không fail-closed (chặn merge)

**Hiện tượng.** Nếu bản sao tương thích `card_progress` lệch với trạng thái NOTE chuẩn, dashboard vẫn trả 200 và hiển thị số đếm theo dữ liệu lệch.

**Nguyên nhân.**

- **Đường NOTE cũ** (`9510d11`): gọi `load_study_authority_card_reads()`, đọc `study_progress_availability` (dữ liệu chuẩn), rồi kiểm tra từng card bằng `validate_study_authority_projection()`. Hàm này so hash ngữ nghĩa của `card_progress` với state, so generation của contributor và availability với subject, so `live_card_progress_id`/`card_progress_revision` với `card_progress`, và so từng trường availability. Lệch bất kỳ chỗ nào thì route trả **409**.
- **Đường hiện tại** (`deck_aggregation_service.py:187–333`): **cả hai chế độ** đều đọc thẳng `card_progress`. Kiểm tra duy nhất được thêm ở `e5e92aa` là `check_note_authority_integrity()` (`:89`), và hàm này chỉ khẳng định mọi subject có token (xem R10). Không có kiểm tra nào về state, contributor, availability, generation, revision hay hash.
- Điều này đi ngược mục 5.2 và 6.4 của báo cáo điều tra: *"dữ liệu NOTE không được âm thầm thay bằng legacy"*, *"tiêm missing token/state/availability... vẫn fail-closed"*.
- Seam hiện dựa vào `card_progress`, bảng sẽ bị bỏ ở Phase 9. Nghĩa là seam phụ thuộc vào đúng bảng sắp bị xóa.

**Bằng chứng.** Dùng fixture `_enable_existing_state_note_authority(epoch=14)` (đã có token), rồi chỉ sửa `card_progress` thành `queue='review', due_day=0` và gọi `/api/dashboard`:

| | Status | Kết quả |
|---|---|---|
| Gốc `9510d11` | **409** | `AUTHORITY_READ_PARITY_DIVERGED` |
| `1f95790` | **200** | `summary = {new: 0, learning: 0, due: 1}` |
| `e5e92aa` | **200** | `summary = {new: 0, learning: 0, due: 1}`: vẫn đếm theo dữ liệu hỏng, trong khi trạng thái chuẩn là NEW |

**Ảnh hưởng.** Khi hai nguồn còn khớp nhau, số đếm không đổi. Rủi ro nằm ở chỗ **mất khả năng phát hiện**: mirror lỗi, writer quên cập nhật, hay dữ liệu bị sửa tay đều bị che đi, và người học thấy số không khớp với phiên học (phiên học vẫn đọc từ NOTE). Chưa có bằng chứng về parity thực tế giữa `card_progress` và availability của user 1 trên production.

**Cách sửa — phương án A (khuyến nghị): đếm từ canonical availability, kiểm tra toàn vẹn bằng SQL theo tập, kiểm tra hash nội dung ở tác vụ riêng.**

**A.1. Nguồn dữ liệu cho chế độ NOTE.** Mỗi card lấy availability qua contributor `ACTIVE` **thuộc subject của chính learner**. Phải lọc learner *trước* khi LEFT JOIN, vì card nguồn của overlay có thể có contributor của nhiều learner khác nhau (mỗi người cài deck có subject riêng). Nếu JOIN theo `live_card_id` mà không lọc learner, dòng sẽ bị nhân bản.

```python
# Phác thảo — nên đặt trong app/repositories/ (vd. note_analytics_read_repository.py)
learner_availability = (
    select(
        StudyProgressContributor.live_card_id.label("card_id"),
        StudyProgressContributor.id.label("contributor_id"),
        StudyProgressAvailability.normalized_queue.label("queue"),
        StudyProgressAvailability.due_day,
        StudyProgressAvailability.due_at,
        StudyProgressAvailability.is_suspended,
        StudyProgressAvailability.is_buried,
        StudyProgressAvailability.buried_until_day,
    )
    .select_from(StudyProgressSubject)
    .join(StudyProgressContributor, and_(
        StudyProgressContributor.subject_id == StudyProgressSubject.id,
        StudyProgressContributor.contributor_status == "ACTIVE",
    ))
    .join(StudyProgressAvailability, and_(
        StudyProgressAvailability.contributor_id == StudyProgressContributor.id,
        StudyProgressAvailability.subject_id == StudyProgressSubject.id,
    ))
    .where(StudyProgressSubject.learner_user_id == learner_user_id)
    .subquery("learner_availability")
)
# owned_select / overlay_select giữ nguyên phần Card/Note/DeckCloneDeckMap,
# nhưng thay .outerjoin(CardProgress, ...) bằng
#   .outerjoin(learner_availability, learner_availability.c.card_id == Card.id)
# và lấy queue/due/suspended/buried từ learner_availability.
# Card không có dòng availability = note pristine -> NEW (hợp lệ chỉ khi qua I9 bên dưới).
```

Các index hiện có đủ cho đường này: `uq_sp_subject_user_note(learner_user_id, ...)`, `ix_sp_contributor_subject_current(subject_id, subject_generation, contributor_status, id)`, PK availability `contributor_id`, và `ix_sp_contributor_live_card(live_card_id, subject_id)`. Báo cáo điều tra đã đo một phép GROUP BY subject→contributor→availability tương tự cho user 1 trên production: **0,119 giây**. Cột `normalized_queue` có CHECK giới hạn ở `('new','learning','relearning','review')` (`study_progress_contract.py:128`), nên lỗi R3b không xảy ra ở đường NOTE.

**A.2. Kiểm tra toàn vẹn bằng SQL theo tập, không khóa (Tier 1, chạy trong request).** Nên thay `check_note_authority_integrity` bằng một hàm dùng chung cho dashboard và overview, chạy các câu `SELECT 1 ... LIMIT 1` (hoặc gộp bằng `UNION ALL`) trên tập note được đếm. Có vi phạm thì ném `StudyAuthorityReadError` với **cùng mã lỗi** reader khóa đang dùng, để route vẫn trả 409 như cũ.

| # | Kiểm tra trong reader khóa hiện tại | Vị trí gốc | Điều kiện vi phạm bằng SQL | Mã lỗi |
|---|---|---|---|---|
| I1 | Subject có state thì phải có token; token cùng generation và cùng hash với state | `study_authority_repository.py` (`lock_study_authority_subject`) | `t.subject_id IS NULL OR t.subject_generation <> s.subject_generation OR NOT (t.semantic_state_hash <=> st.semantic_state_hash)` | `AUTHORITY_TOKEN_REQUIRED` / `AUTHORITY_GENERATION_DIVERGED` / `AUTHORITY_STATE_DIVERGED` |
| I2 | State cùng generation và `mirror_revision` với subject | như trên | `st.subject_generation <> s.subject_generation OR st.mirror_revision <> s.mirror_revision` | `AUTHORITY_GENERATION_DIVERGED` / `AUTHORITY_STATE_DIVERGED` |
| I3 | Subject gắn với note đang sống | `study_session_authority_pin_service.py:211` | `s.live_note_id IS NULL OR s.live_note_id <> <note_id>` | `DETACHED_AUTHORITY_SUBJECT` |
| I4 | Mọi card anh em của note có state đều có `card_progress` | `load_study_authority_card_reads` (vector sibling) | LEFT JOIN `card_progress` … `cp.id IS NULL` | `INCOMPLETE_AUTHORITY_COMPATIBILITY` |
| I5 | Mỗi card có đúng một contributor `ACTIVE`; số contributor = `s.contributor_count` = số card anh em | như trên | `GROUP BY s.id HAVING COUNT(c.id) <> s.contributor_count OR COUNT(card.id) <> s.contributor_count`, cộng với card không có contributor | `INCOMPLETE_AUTHORITY_COMPATIBILITY` |
| I6 | Mỗi contributor `ACTIVE` có availability; không có availability mồ côi của contributor không `ACTIVE` | như trên | LEFT JOIN availability … `a.contributor_id IS NULL`; và availability join contributor có `contributor_status <> 'ACTIVE'` | `INCOMPLETE_AUTHORITY_COMPATIBILITY` |
| I7 | Contributor khớp generation và khớp `card_progress` | `validate_study_authority_projection` | `c.subject_generation <> s.subject_generation OR c.live_card_progress_id <> cp.id OR c.card_progress_revision <> cp.revision` | `AUTHORITY_READ_PARITY_DIVERGED` |
| I8 | Availability khớp generation, phiên bản projection/schema và hash với state | như trên | `a.subject_generation <> s.subject_generation OR a.projection_version <> 'availability-anchor.v1' OR a.state_schema_version <> <STATE_SCHEMA_VERSION> OR a.semantic_state_hash <> st.semantic_state_hash` | `AUTHORITY_READ_PARITY_DIVERGED` |
| I9 | Note chưa có state (pristine): subject nếu có phải là `NO_CURRENT_PROGRESS`, `contributor_count = 0`, hash NULL; không có contributor `ACTIVE`; không card anh em nào có `card_progress` | `classify_note_authority_keys` | LEFT JOIN state … `st.subject_id IS NULL AND (cp.id IS NOT NULL OR c.id IS NOT NULL OR s.status_code <> 'NO_CURRENT_PROGRESS' …)` | `INCOMPLETE_AUTHORITY_COVERAGE` |

Ghi chú về I8: mapper (`study_progress_shadow_mapper.py`) dùng **cùng một** `semantic_hash` cho `MappedCardProgress.semantic_state_hash` và `AvailabilityProjection.semantic_state_hash`. Vì vậy `a.semantic_state_hash = st.semantic_state_hash` là điều kiện tương đương có thể viết bằng SQL.

Ví dụ một câu kiểm tra (I4 + I6 + I7 + I8 gộp lại):

```sql
SELECT 1
FROM   counted_cards cc                               -- cùng tập card mà dashboard đếm
JOIN   study_progress_subjects s   ON s.learner_user_id = :uid AND s.live_note_id = cc.note_id
JOIN   study_progress_states   st  ON st.subject_id = s.id
LEFT JOIN study_progress_contributors c
       ON c.subject_id = s.id AND c.live_card_id = cc.card_id AND c.contributor_status = 'ACTIVE'
LEFT JOIN study_progress_availability a ON a.contributor_id = c.id AND a.subject_id = s.id
LEFT JOIN card_progress cp ON cp.card_id = cc.card_id AND cp.user_id = :uid
WHERE  c.id IS NULL OR a.contributor_id IS NULL OR cp.id IS NULL
   OR  c.subject_generation <> s.subject_generation
   OR  a.subject_generation <> s.subject_generation
   OR  c.live_card_progress_id <> cp.id
   OR  c.card_progress_revision <> cp.revision
   OR  a.projection_version <> :projection_version
   OR  a.semantic_state_hash <> st.semantic_state_hash
LIMIT 1;
```

**Lưu ý kỹ thuật:**

- `logical_note_key` là `VARBINARY`, còn `notes.id` là chuỗi. Ví dụ trên join theo `live_note_id` (có index `ix_sp_subject_live_note`). Nếu cần join theo `logical_note_key`, phải xử lý chuyển kiểu theo dialect, vì SQLite và MySQL khác nhau.
- Phép so sánh NULL-safe dùng `<=>` trên MySQL; trong SQLAlchemy dùng `is_distinct_from`/`isnot_distinct_from`.
- Phạm vi kiểm tra nên giống reader cũ: dashboard kiểm **tập note đang được đếm** (owned + overlay trong deck đang hiển thị); overview kiểm **mọi note có state của learner**. Xem thêm R10.

**A.3. Phần SQL không làm được (Tier 2, cần quyết định contract).** Có hai kiểm tra chỉ làm được bằng Python:

- Giải mã payload state (codec, hash thuật toán; `study_session_authority_pin_service.py:234`).
- Tính lại hash ngữ nghĩa từ các trường của `card_progress` bằng `map_card_progress()` rồi so với state.

Chính case trong probe R2 (sửa `queue` mà không tăng `revision`) **chỉ bị kiểm tra này bắt**, còn I7 bỏ lọt. Lý do là `CardProgress.revision` được writer tự tăng bằng tay, không phải version column của ORM. Có hai lựa chọn, cần chủ dự án quyết định:

1. **Tách ra audit riêng (khuyến nghị):** dashboard/overview hiển thị số theo NOTE chuẩn, luôn đúng theo authority. Việc lệch của bản sao tương thích được phát hiện bằng CLI có sẵn `flask --app wsgi.py study-authority-read-audit --user-id <id>` (`app/cli.py:391`), chạy định kỳ hoặc sau deploy. Lưu ý CLI này hiện dùng reader khóa, nên phải chạy lúc ít tải hoặc chuyển sang bản không khóa. Báo cáo điều tra cho phép hướng này *nếu* có quyết định contract rõ ràng và có cơ chế hiển thị lỗi hỏng dữ liệu. Quyết định nên được ghi vào runbook P5.
2. **Giữ trong request:** đọc các cột cần thiết của `card_progress` và state theo chunk, không khóa, rồi chạy `map_card_progress()` bằng Python. Cần benchmark ở quy mô 40k trước, vì mỗi dòng phải băm canonical document.

**Phương án B (tối thiểu, không khuyến nghị lâu dài):** giữ việc đếm từ `card_progress`, chỉ thêm I1–I9 (đặc biệt I7 về revision). Ít thay đổi hơn nhưng vẫn phụ thuộc bảng sẽ bị bỏ ở Phase 9, và vẫn bỏ lọt case "sửa không tăng revision".

**Kiểm chứng sau sửa (theo mục 6.4 báo cáo điều tra):**

- Tiêm từng lỗi rồi kỳ vọng 409 đúng mã: thiếu token, thiếu state, thiếu contributor, thiếu availability; lệch generation; lệch `mirror_revision`; lệch revision; lệch hash; subject detached; card anh em thiếu `card_progress`; note pristine có `card_progress`.
- Reader analytics không INSERT/UPDATE: bắt bằng event `before_cursor_execute` trong test.
- Viết lại `test_dashboard_note_counts_are_rebuilt_from_canonical_availability` sao cho **availability và `card_progress` khác nhau có chủ đích** (và hợp lệ theo I1–I9), rồi khẳng định số đếm lấy từ availability.

---

### R3 — Phân loại SQL lệch helper chuẩn (chưa sửa)

Báo cáo điều tra yêu cầu giữ nguyên hành vi đếm ở mọi trường hợp *"NEW/learn/review, due trong tương lai, buried/suspended, midnight/boundary"*. Helper chuẩn là `study_repository.study_bucket_for_progress_values` / `counter_bucket_for_progress_values` (`app/repositories/study_repository.py:332`, `:386`).

| Trường hợp | Helper chuẩn | SQL hiện tại | Kết quả probe (`e5e92aa`) |
|---|---|---|---|
| Suspended | ẩn | ẩn | Khớp |
| `is_buried` và `buried_until_day` NULL hoặc `>= today` | ẩn | ẩn (`NULL < today` là NULL) | Khớp |
| learning/relearning (kể cả chưa đến hạn) | LEARN | LEARN | Khớp |
| Review, `due_day <= today` | DUE | DUE | Khớp |
| **R3a:** review, `due_day` NULL, `due_at` muộn hơn trong hôm nay | **DUE** (vì `_day_index(due_at) <= today`) | **không đếm** (so `due_at <= now_utc`, `deck_aggregation_service.py:318`) | `canonical='review'`, SQL `due: 0` |
| **R3b:** queue rỗng, có khoảng trắng, hoặc giá trị lạ | **NEW** (`normalize_progress_queue` rơi về NEW; có `strip()`) | **không đếm vào ô nào**, nhưng vẫn cộng vào `total` (`:297–305`) | `canonical='new'`, SQL `new: 0` |

**Nguyên nhân.**

- R3a: SQL so `due_at` với *thời điểm hiện tại*, trong khi contract so theo *ngày học* (timezone + day boundary). Cả `_classify_progress_fast` cũ lẫn helper chuẩn đều quy `due_at` về day index.
- R3b: `is_new` chỉ đúng khi `progress_id IS NULL OR norm_queue = 'new'`, và `norm_queue` không `trim`. Helper chuẩn thì xếp mọi giá trị không nhận ra vào NEW.

**Cách sửa.** Truyền vào mốc bắt đầu của ngày học kế tiếp, tính theo UTC, và đảo điều kiện NEW thành "không phải learn và không phải review":

```python
# Caller (dashboard_service.build_dashboard_data):
from app.services.anki_scheduler import _day_index_to_datetime
next_day_start_utc = _day_index_to_datetime(
    today_day_index + 1, boundary_hour, timezone_name=timezone_name
)

# deck_aggregation_service.aggregate_deck_study_counts(..., next_day_start_utc=...)
queue = func.lower(func.trim(func.coalesce(rows.c.queue, "new")))
is_learning = queue.in_(("learn", "learning", "relearning"))
is_review = queue == "review"

is_new = and_(is_active, ~is_learning, ~is_review)  # progress NULL + queue lạ -> NEW
is_learn = and_(is_active, is_learning)
is_due_review = and_(
    is_active,
    is_review,
    or_(
        rows.c.due_day <= today_day_index,
        and_(
            rows.c.due_day.is_(None),
            or_(rows.c.due_at.is_(None), rows.c.due_at < next_day_start_utc),
        ),
    ),
)
```

**Tính tương đương đã kiểm chứng:** `_day_index(due_at) <= today` ⇔ `due_at < _day_index_to_datetime(today + 1, ...)`. Kiểm tra ngẫu nhiên 36.000 mẫu trên `UTC`, `Asia/Tokyo`, `America/Los_Angeles` (có DST), `Asia/Ho_Chi_Minh`, với boundary 0/4/23 giờ: **0 sai lệch**. `_day_index_to_datetime` trả về datetime UTC naive, cùng kiểu với cột `due_at`.

**Kiểm chứng sau sửa.** Thêm test so sánh theo từng card: sinh nhiều tổ hợp (queue × due_day/due_at quanh boundary × suspended/buried × timezone), rồi khẳng định số đếm của `aggregate_deck_study_counts` bằng tổng `counter_bucket_for_progress_values` trên cùng dữ liệu.

---

### R4 — Chi phí overview (F2/F3) (đã sửa phần lớn)

**Trước (`1f95790`):** đường NOTE của overview tải mọi Card có `card_progress` (khoảng 39k), lazy-load `card.note` cho từng card, gọi `resolve_deck_options()` theo từng card (khoảng 78k SELECT), và chạy reader khóa (`FOR UPDATE` toàn tập, khoảng 78k SELECT token/state).

**Hiện tại (`e5e92aa`):** `_canonical_future_due_day_counts` (`stats_overview.py:150`) chạy:

- một anti-join kiểm tra token (`:167`);
- một SELECT `(due_at, due_day, normalized_queue)` trên availability join subject theo `id` + `subject_generation`, lọc theo learner, có due, không suspended (`:181`);
- vòng Python gom theo ngày bằng `_progress_due_local_day`, giống hệt nhánh LEGACY.

Không còn khóa, không còn N+1, và không còn cần deck options (trước đây deck options chỉ tồn tại để thỏa chữ ký của reader cũ, vốn dựng `state`/`state_version` rồi bỏ đi).

**Còn lại:** các vấn đề R9–R12 bên dưới. Ngoài ra:

- Truy vấn tải mọi dòng có due của learner (khoảng 15k với user 1), không lọc theo khoảng thời gian trong SQL. Cách này giống LEGACY và chấp nhận được, nhưng cần đo ở cohort 40k.
- Ngoài phạm vi dashboard: `stats_today_future.py:336`/`:417` (trang Statistics) vẫn dùng reader khóa và options theo từng card. Nó chạy được trên MySQL vì không nằm trong transaction `READ ONLY`, nhưng vẫn có chi phí F2/F3 và sẽ cần cách sửa tương tự.

---

### R5 — Admin ở chế độ NOTE nay bị cộng overlay (chưa sửa)

**Nguyên nhân.** Code cũ:

```python
# LEGACY: installs = [] khi admin_mode -> không đếm overlay
# NOTE:   overlay_cards = ([], {}) if admin_mode else logical_overlay_cards(...)
```

Code mới (`deck_aggregation_service.py:118`) sao chép *điều kiện tải installs* (`if not admin_mode or is_note_mode:`), chứ không sao chép *điều kiện đếm overlay*. Kết quả: admin ở chế độ NOTE giờ bị cộng card overlay, còn trước đây thì không.

**Cách sửa.** Đổi thành `if not admin_mode:`. Thêm test: admin + NOTE + có `DeckInstall logical_overlay` thì số đếm của deck local không bao gồm card nguồn.

---

### R6 — Thứ tự ưu tiên `deck_note_types` bị đảo (chưa sửa)

**Nguyên nhân.** Code cũ lấy note type của **note sở hữu trước** (nhánh NOTE sắp theo `Card.id`), sau đó overlay chỉ `setdefault`. Code mới (`:144–184`) gán overlay trước, rồi chỉ tra note sở hữu cho các deck còn thiếu. Ngoài ra, `GROUP BY deck_id, note_type_id` không có `ORDER BY`, nên deck có nhiều note type cho kết quả không cố định. Có thêm vòng lặp lồng `logical_installs × map_rows` (O(n·m)), dù ở quy mô hiện tại không đáng kể.

**Cách sửa.** Tra note type sở hữu trước với thứ tự cố định (ví dụ `ORDER BY Note.deck_id, Note.created_at, Note.id` và lấy dòng đầu mỗi deck), rồi mới `setdefault` từ overlay. Lập dict `install_id → install` để bỏ vòng lặp lồng. Thêm test cho deck vừa có note sở hữu vừa có mapping overlay.

---

### R7 — Test và CI chưa có MySQL thật

- `test_dashboard_note_counts_are_rebuilt_from_canonical_availability` (`tests/test_study_session_api.py:2038`) vẫn patch `_classify_progress_fast`, nhưng hàm này **là code chết**. Test xanh chỉ vì `card_progress` trùng với availability trong fixture. Tên test hứa kiểm tra "canonical availability", nhưng nội dung không còn kiểm tra điều đó.
- `test_analytics_read_transaction_isolation_and_write_safety` kiểm tra nhánh MySQL bằng `MagicMock`, không có MySQL thật. Vì thế nó không bắt được lớp lỗi như R1.
- Các test mới (`test_note_authority_mode_missing_token_fails_closed`, `test_note_authority_fail_closed_on_dashboard_aggregation`) chỉ tiêm lỗi "thiếu token". Chưa có test cho state, contributor hay availability lệch, cũng như cho nhánh fallback R9.
- CI: `MYSQL_CONTRACT_SOURCE_PATTERNS` (`scripts/run_tests.py:774`) chỉ gồm `migrations/**`, `models/**`, … Với diff của nhánh, `build_ci_change_plan` trả `mysql_contract = False` trong khi `deploy = True`. Kể cả khi chạy, probe `scripts/probe_p1_02_mysql_concurrency.py` cũng không đụng tới analytics.

**Đề xuất:**

1. **Test route-level cấm khóa và cấm ghi** (chạy được trên SQLite): dùng `event.listen(db.engine, "before_execute")` để bắt clause có `_for_update_arg` và các câu INSERT/UPDATE/DELETE trong suốt `client.get("/api/dashboard")` và `client.get("/api/statistics/overview")` với fixture NOTE.
2. **MySQL contract cho analytics:** thêm một probe (ví dụ `scripts/probe_p5_analytics_mysql.py`, hoặc test chạy khi có biến môi trường URI MySQL) gọi hai route với learner NOTE có ít nhất một note đã học, trên MySQL thật. Thêm `app/api/v1/analytics/**`, `app/services/study_analytics_read_service.py`, `app/services/deck_aggregation_service.py`, `app/services/stats_overview.py` vào `MYSQL_CONTRACT_SOURCE_PATTERNS`, và thêm bước chạy probe vào job `mysql-contract` trong `.github/workflows/ci.yml`.
3. Test tiêm lỗi cho R2/R9 (danh sách ở R2), test so khớp cho R3, test cho R5/R6/R11.
4. Đưa các test NOTE analytics vào module `analytics` trong `scripts/run_tests.py`. Hiện chúng nằm trong `test_study_session_api.py` và **không chạy** khi diff chỉ chạm các file analytics: `map_files_to_modules` trả `{'analytics'}` cho `dashboard_service.py`, `deck_aggregation_service.py`, `stats_overview.py`.

---

### R8 — Các điểm nhỏ

- **Code chết:** `_classify_progress_fast` và biến `timezone_obj` trong `dashboard_service.py`. Nên xóa (và sửa test ở R7).
- **Docstring sai:** docstring của seam nói truy vấn dùng `ix_card_progress_user_queue_due_day`, nhưng phép join theo `(card_id, user_id)` thực tế dùng `uq_card_progress_user_card`.
- **`total` lệch đơn vị:** khi bật đếm theo note (`count_by_note`), `total` vẫn là số card trong khi new/learn/due là số note. Cần thống nhất đơn vị, hoặc ghi rõ trong payload.
- **`analytics_read_transaction()` chỉ chặn thay đổi chưa flush.** Thay đổi đã flush mà chưa commit sẽ bị rollback trong im lặng. Hiện chưa có hook nào gây ra trường hợp này: rate limit dùng Redis/bộ nhớ, còn timezone đã commit trước đó. Nên ghi rõ giả định này trong docstring.
- **Fixture test:** `_enable_existing_state_note_authority` nay mặc định tạo token khi `enroll=True` (`tests/test_study_session_api.py:278`). Điều này hợp lý vì kiểm tra token đã được bật. Tham số `include_token=True` ở `:801`, `:833` giờ thừa và có thể bỏ.

---

### R9 — Overview NOTE fallback sang `card_progress` (mới, chặn merge)

**Hiện tượng.** Nếu learner NOTE không có dòng availability nào có due (không suspended), overview âm thầm đếm future-due từ `card_progress`.

**Nguyên nhân.** `stats_overview.py:209–225`:

```python
if not avail_rows:
    # Fallback to compatibility projection card_progress for test fixtures or unmirrored rows
    avail_rows = db.session.execute(select(CardProgress.due_at, CardProgress.due_day, CardProgress.queue) ...)
```

- Comment nói rõ fallback được thêm "cho test fixture hoặc dòng chưa mirror". Tức là code production đang được nới ra để test pass.
- Hai trường hợp kích hoạt fallback: (a) learner NOTE chỉ có thẻ NEW, trường hợp hợp lệ; (b) **availability bị thiếu hoặc mirror hỏng**, đúng trường hợp phải fail-closed. Code không phân biệt được hai trường hợp này.
- Đây chính là điều báo cáo điều tra cấm ở mục 5.2: *"không tự động trả số 0 hoặc fallback legacy khi NOTE không hợp lệ"*.

**Bằng chứng.** Fixture NOTE `epoch=15` (state NEW, availability không có due). Chỉ sửa `card_progress` thành `queue='review', due_day=<hôm nay + 3>`, rồi gọi overview:

| | Status | Ô heatmap ngày 2026-10-02 |
|---|---|---|
| Gốc `9510d11` | **409** `AUTHORITY_READ_PARITY_DIVERGED` | — |
| `e5e92aa` | **200** | `{"cards": 1, "source": "due", "is_future": true}`: đếm theo dữ liệu lệch |

**Cách sửa.**

- Bỏ nhánh fallback. Ở chế độ NOTE, "không có dòng availability có due" nghĩa là 0 thẻ đến hạn, **nếu và chỉ nếu** kiểm tra toàn vẹn A.2 (I1–I9) pass trên mọi note có state của learner. Còn nếu thiếu availability cho contributor `ACTIVE` thì I6 sẽ ném 409.
- Sửa fixture test để tạo availability đầy đủ, thay vì dựa vào fallback. `_enable_existing_state_note_authority` đã tạo availability; các test trong `test_stats_overview.py` cần làm tương tự.
- Thêm test: NOTE + availability rỗng + `card_progress` có due thì kỳ vọng 409 (nếu có contributor `ACTIVE`), hoặc 0 thẻ đến hạn (nếu mọi note đều pristine).

---

### R10 — `check_note_authority_integrity`: kiểm tra quá yếu, phạm vi quá rộng (mới)

**Nguyên nhân.** Hàm (`deck_aggregation_service.py:42`) chỉ tìm một subject bất kỳ của learner **không có token**:

- **Quá yếu:** không kiểm state, contributor, availability, generation, revision hay hash (I2–I9). Probe R2 và R9 đều có token hợp lệ nên lọt qua.
- **Phạm vi quá rộng:** quét **mọi** subject của learner, kể cả subject của note không nằm trong deck đang hiển thị và subject pristine `NO_CURRENT_PROGRESS`. Reader cũ chỉ đòi token cho subject có state trong tập được đọc (và còn tự tạo token nếu thiếu). Chỉ một subject thiếu token ở bất kỳ đâu sẽ làm **cả dashboard lẫn overview** trả 409.
- Chưa có bằng chứng production có subject thiếu token. Báo cáo điều tra ghi user 1 có số token bằng số subject. Nhưng code tạo subject `NO_CURRENT_PROGRESS` trong `study_progress_shadow_mirror_service.py:1392` không tự tạo token, nên cần xác nhận trước khi deploy.

**Cách sửa.**

- Thay bằng bộ kiểm tra A.2, với phạm vi đúng như reader cũ.
- Trước khi deploy, chạy câu đếm chỉ đọc sau trên production để biết bản sửa có chặn nhầm learner nào không:

```sql
SET SESSION MAX_EXECUTION_TIME = 5000;
SELECT s.learner_user_id, s.status_code, COUNT(*) AS subjects_without_token
FROM   study_progress_subjects s
LEFT JOIN study_authority_subject_tokens t ON t.subject_id = s.id
WHERE  t.subject_id IS NULL
GROUP  BY s.learner_user_id, s.status_code;
```

---

### R11 — Overview NOTE đổi ngữ nghĩa future-due (mới, cần quyết định)

**Quan sát.** `_canonical_future_due_day_counts` mới dùng cùng thuật toán với LEGACY (`query_future_due_day_counts`, `stats_query_repository.py:462`), thông qua `_progress_due_local_day`:

| | NOTE cũ (`9510d11`) | NOTE mới (`e5e92aa`) = LEGACY |
|---|---|---|
| Ngày của thẻ review có `due_day` | Theo `due_at` | Theo `due_day` (ordinal ngày học) |
| Quy `due_at` về ngày | Ngày lịch (`astimezone(tz).date()`), không trừ day boundary | Ngày học (`_utc_to_business_day`), có trừ day boundary |
| Thẻ quá hạn (`< start`) | Bỏ qua | **Dồn vào hôm nay** |
| Thẻ review chỉ có `due_day`, không có `due_at` | Bỏ qua | Được đếm |

**Đánh giá.** Đồng nhất NOTE với LEGACY nhiều khả năng là mong muốn, vì rollout P5 hướng tới "NOTE đọc giống LEGACY". Tuy nhiên đây là **thay đổi hành vi nhìn thấy được** trên heatmap: ô "hôm nay" tăng thêm số thẻ quá hạn, và ngày có thể lệch quanh day boundary. Commit không nêu điều này.

**Cách xử lý.** Ghi quyết định vào commit/PR. Thêm test khóa ngữ nghĩa cho NOTE: thẻ quá hạn, `due_at` quanh boundary, thẻ chỉ có `due_day`. Và thêm test cùng dữ liệu cho cả LEGACY lẫn NOTE để khẳng định hai kết quả bằng nhau.

---

### R12 — Truy vấn availability của overview không lọc contributor `ACTIVE`/card còn sống (mới)

**Quan sát.** Truy vấn ở `stats_overview.py:181` join availability với subject theo `id` + `subject_generation`, nhưng không join contributor để lọc `contributor_status = 'ACTIVE'`, và không kiểm card còn tồn tại. Reader cũ chỉ đọc availability của contributor `ACTIVE` gắn với card còn sống.

**Mức độ.** Các writer lifecycle hiện xóa availability khi contributor rời trạng thái `ACTIVE` (`study_progress_lifecycle_mirror_service.py:551`, `:755`, `:2097`; `study_progress_shadow_mirror_service.py:1195`). Nên với dữ liệu đúng, kết quả không đổi. Rủi ro chỉ xuất hiện khi dữ liệu hỏng (availability mồ côi), và khi đó không có gì phát hiện.

**Cách sửa.** Join qua `StudyProgressContributor` với `contributor_status = 'ACTIVE'` và `Card.id = live_card_id` như phác thảo A.1. Hoặc giữ nguyên truy vấn nhưng để I6 (không có availability mồ côi) bắt trường hợp này.

## 5. Kế hoạch sửa đề xuất

Theo ranh giới kiến trúc trong `AGENTS.md`: query nằm ở `app/repositories/*`, điều phối và quản lý transaction ở `app/services/*`, route chỉ xử lý HTTP.

| Bước | Nội dung | File chính | Điều kiện hoàn thành |
|---|---|---|---|
| 0 | Không merge ở HEAD `e5e92aa` | — | — |
| 1 | Tạo repository đọc NOTE analytics không khóa: subquery availability theo learner (A.1) và `assert_note_analytics_integrity()` (I1–I9) thay cho `check_note_authority_integrity` (R10) | `app/repositories/note_analytics_read_repository.py` (mới), `deck_aggregation_service.py` | Test tiêm lỗi trả đúng mã; không có `FOR UPDATE`/INSERT |
| 2 | Dashboard: NOTE đọc từ bước 1; LEGACY giữ `card_progress`; sửa R3, R5, R6; xóa code chết | `deck_aggregation_service.py`, `dashboard_service.py` | Test so khớp R3 pass; test R5/R6 pass; probe R2 trả 409 |
| 3 | Overview: bỏ fallback (R9); lọc contributor `ACTIVE` (R12); gọi kiểm tra bước 1; chốt và test ngữ nghĩa R11 | `stats_overview.py` | Probe R9 trả 409; test ngữ nghĩa NOTE = LEGACY pass |
| 4 | Test và CI (R7) | `tests/`, `scripts/run_tests.py`, `scripts/probe_p5_analytics_mysql.py`, `.github/workflows/ci.yml` | Job `mysql-contract` chạy và xanh cho diff analytics |
| 5 | Chốt contract Tier 2 (A.3) và ghi vào runbook P5; chạy câu SQL ở R10 trên production trước deploy | `docs/runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md` | Có quyết định rõ ràng; không learner nào bị chặn nhầm |
| 6 | Đo lại theo mục 6 báo cáo điều tra (cohort 1k/10k/40k, chạy đơn và đồng thời, kèm review/first-state song song) | — | Đạt tiêu chí mục 6 dưới đây |
| 7 | Việc còn lại của báo cáo điều tra, nên làm PR riêng: frontend F4 (lỗi một widget không đẩy cả app sang `/maintenance`), telemetry request-level, `stats_today_future` (R4) | `frontend/src/shared/api/`, `useDashboardPage.tsx`, `stats_today_future.py` | Theo mục 5.2 P1 của báo cáo điều tra |

## 6. Tiêu chí nghiệm thu (bổ sung cho mục 6 của báo cáo điều tra)

1. Trên MySQL 8.0: dashboard và overview với learner NOTE (có note đã học **và** có thẻ đến hạn) trả 200; không có lỗi 1792, 1205 hay 1213.
2. Route analytics không phát sinh `FOR UPDATE`, `FOR SHARE`, INSERT, UPDATE hay DELETE (test route-level).
3. Tiêm từng lỗi ở danh sách R2 thì trả 409 với mã khớp reader cũ, ở **cả hai** endpoint. Không có trường hợp nào âm thầm trả số đếm, kể cả khi availability rỗng (R9).
4. Số đếm dashboard khớp từng card với `counter_bucket_for_progress_values` trên tập tổ hợp ở R3, kể cả quanh day boundary và các timezone có DST.
5. Overview NOTE và LEGACY cho cùng kết quả trên cùng dữ liệu (nếu chốt R11 theo hướng đồng nhất).
6. Số query của mỗi request không tăng theo số card, đo bằng listener `before_cursor_execute` trên cohort 1k và 40k. Ghi lại con số thực tế làm baseline.
7. Ở cohort khoảng 40k: p95 mỗi API dưới 2 giây khi chạy đơn và dưới 5 giây khi dashboard và overview chạy đồng thời (giữ nguyên mục tiêu của báo cáo điều tra).

## 7. Rà soát kế hoạch và điều chỉnh theo decoupling (2026-09-30)

Kế hoạch mục 5 đúng hướng và giữ nguyên thứ tự. Phương án A (đếm từ canonical availability) khớp [P5 plan](../task/decoupling/P5_EXECUTION_PLAN_2026-09-20.md) §3: learner NOTE đọc state/availability chuẩn, còn `card_progress` chỉ là projection để rollback và sẽ bị bỏ ở Phase 9. Sáu điểm dưới đây điều chỉnh kế hoạch sau khi đối chiếu với code và kế hoạch decoupling.

| # | Điểm | Quyết định | Lý do |
|---|---|---|---|
| K1 | Tier 2 (A.3): so hash nội dung `card_progress` với state | **Chọn A.3 phương án 1**: dashboard/overview không tính lại hash; lệch nội dung của bản sao tương thích do `study-authority-read-audit` phát hiện | Số hiển thị lấy từ NOTE chuẩn nên đúng theo authority kể cả khi bản sao lệch. Vẫn giữ trong request các kiểm tra liên kết với `card_progress` (I4 có dòng, I7 cùng id/revision) vì chúng rẻ và phát hiện writer quên chiếu. Runbook P5 ghi lịch chạy audit. |
| K2 | I1 khi **thiếu** token | **Không coi là vi phạm**; chỉ so generation/hash khi token tồn tại | Reader khóa cũ (`lock_study_authority_subject`, `create_token_if_missing=True`) tự tạo token từ state rồi trả 200. Reader analytics không được ghi, và thiếu token không phải là lệch dữ liệu: writer kế tiếp sẽ tạo token. Trả 409 ở đây là hồi quy so với `9510d11`. |
| K3 | Đếm theo Note (`count_by_note`, `STUDY_NOTE_COUNT_ENABLED`) | **Gỡ khỏi bản sửa này** | D6-04 thuộc [Phase 6](../task/decoupling/P6_EXECUTION_PLAN_2026-09-29.md) và chưa được duyệt; bất biến #9 của [thiết kế P5](phase-5-authority-cutover-design-2026-09-20.md) cấm gộp Card trước Phase 6. Làm ở P6-06 sau khi D6-04 được duyệt. |
| K4 | R11 (ngữ nghĩa future-due của overview NOTE) | **NOTE = LEGACY** (`_progress_due_local_day`, thẻ quá hạn dồn vào hôm nay) | Mục tiêu reader parity NOTE↔LEGACY của P5-07. Bản NOTE ở `9510d11` lệch LEGACY. Có test so hai chế độ trên cùng dữ liệu. |
| K5 | Tra subject theo khóa | Join `logical_note_key = CAST(note_id AS BINARY)` (index `uq_sp_subject_user_note`), không join theo `live_note_id` | Join theo `live_note_id` bỏ sót subject bị detach; reader cũ tìm theo logical key rồi mới báo `DETACHED_AUTHORITY_SUBJECT` (I3). |
| K6 | R3a trong bản nháp chưa commit | Dùng `due_at < mốc đầu ngày học kế tiếp` (so sánh ngặt) | `_day_index(due_at) <= today` ⇔ `due_at < next_day_start`; bản nháp dùng `<=`, lệch đúng tại thời điểm biên. Giữ việc lấy day boundary theo từng user (bản nháp): khớp route học (`resolve_scheduler_runtime_settings`). |

Phạm vi chưa đổi: các reader khóa còn lại (`stats_today_future`, Browse list/tree, `/api/study/next`, trang học deck, MCP study tools, mở phiên v4 tối đa 5.000 thẻ) để PR riêng ở bước 7. Access log production từ 28/09 cho thấy endpoint nặng được dùng là `/api/dashboard` và `/api/statistics/overview`; các endpoint còn lại cần đo trước khi sửa.

## 8. Kết quả triển khai (2026-09-30)

Đã triển khai bước 1–4 của mục 5 theo các điều chỉnh K1–K6.

| ID | Trạng thái | Thay đổi |
|---|---|---|
| R2, R10, R12 | **Đã sửa** | `app/repositories/note_analytics_read_repository.py` (mới): `note_card_rows()` lấy availability của contributor `ACTIVE` theo từng Card và tính mã vi phạm I1–I9 bằng một biểu thức SQL; `subject_vector_violation()` kiểm I5. Mã lỗi trùng reader khóa, route trả 409. `check_note_authority_integrity` bị xóa. |
| R3 | **Đã sửa** | Queue `lower(trim(...))`, queue lạ/rỗng tính là NEW, review chỉ có `due_at` so ngặt với mốc đầu ngày học kế tiếp. Test ngẫu nhiên 480 Card × 4 bối cảnh (UTC, Tokyo, Los Angeles ngày đổi DST, Hồ Chí Minh; boundary 0/4/23) khớp `counter_bucket_for_progress_values`. |
| R5, R6 | **Đã sửa** | Admin không cộng overlay ở cả hai chế độ; Note type lấy từ Note sở hữu cũ nhất trước, rồi mới tới install. |
| R7 | **Đã sửa** | `tests/test_note_analytics_read.py` (17 test, dữ liệu dựng bằng writer NOTE thật: 11 lỗi tiêm, không khóa/không ghi, NOTE = LEGACY cho deck sở hữu và deck cài overlay từ marketplace). `scripts/probe_p5_analytics_mysql.py` chạy bộ này trên MySQL thật, trong transaction `READ ONLY`; đã thêm vào job `mysql-contract` và `MYSQL_CONTRACT_SOURCE_PATTERNS`. |
| R8 | **Đã sửa** | Xóa `_classify_progress_fast`, `timezone_obj`, docstring sai; ghi giả định "đã flush nhưng chưa commit" trong `analytics_read_transaction`. `count_by_note` và `STUDY_NOTE_COUNT_ENABLED` bị gỡ (K3). |
| R9, R11 | **Đã sửa** | Overview NOTE không còn fallback `card_progress`; đọc một lượt (vi phạm + dòng có due); ngữ nghĩa ngày = LEGACY, có test so hai chế độ trên cùng dữ liệu. |

**Kiểm chứng:**

- MySQL 8.0.40 local, DB tạm: `probe_p5_analytics_mysql.py` 17/17 PASS, không có lỗi 1792.
- **Production, chỉ đọc, chưa deploy:** chạy code của working tree từ thư mục tạm trên VPS, bằng `create_app` với mọi cờ `STARTUP_*` tắt, bên trong `analytics_read_transaction()`.

| Learner | Dashboard trước | Dashboard sau | Overview sau | Ba request đồng thời (2 dashboard + overview) |
|---|---|---|---|---|
| User 1 (39.282 Card) | 119,5 s | 1,9 s (10 câu SQL) | 1,6–1,8 s (7 câu SQL) | tối đa 3,6 s mỗi request |
| User 4 | 14,3 s | 0,7–0,8 s | 0,3–0,4 s | — |

  Số đếm của user 1 (new 24.056, learn 2.064, due 12.898) bằng kết quả audit lúc enroll. Trên toàn bộ deck của user 1 và user 4, số đếm theo NOTE bằng đúng số đếm theo `card_progress`, tức projection đang khớp.

**Còn lại:** bước 5 (chạy câu SQL R10 không còn cần, vì K2 cho phép thiếu token; ghi lịch audit vào runbook P5) và bước 7 (các reader khóa còn lại, frontend F4, telemetry).

## 9. Phụ lục: tái hiện

### A. Hành vi `READ ONLY` trên MySQL 8.0

```sql
CREATE TABLE t (id INT PRIMARY KEY, v INT);
INSERT INTO t VALUES (1,1),(2,2);
START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY;
SELECT * FROM t WHERE id=1 FOR SHARE;    -- OK
SELECT * FROM t WHERE id=1 FOR UPDATE;   -- ERROR 1792 (25006): Cannot execute statement in a READ ONLY transaction.
ROLLBACK;
```

### B. Chạy test NOTE analytics có sẵn trên MySQL

```bash
docker run -d --name flama-mysql -p 3307:3306 \
  -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=flama mysql:8.0
```

```python
# mysql_analytics_check.py — chạy từ root repo
import sys, unittest
sys.path.insert(0, ".")
from app import create_app
import tests.test_study_session_api as mod

class MySQLStudySessionApiTests(mod.StudySessionApiTests):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "mysql+pymysql://root:root@127.0.0.1:3307/flama?charset=utf8mb4",
            "WTF_CSRF_ENABLED": False,
            "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False,
        })

suite = unittest.TestSuite(MySQLStudySessionApiTests(n) for n in sys.argv[1:])
unittest.TextTestRunner(verbosity=2).run(suite)
```

```bash
python mysql_analytics_check.py \
  test_statistics_note_future_due_bypasses_legacy_progress_query \
  test_dashboard_note_counts_are_rebuilt_from_canonical_availability \
  test_today_future_note_analytics_bypass_legacy_progress_queries
# 9510d11: cả ba ok. 1f95790: overview 500 (1792). e5e92aa: cả ba ok.
```

Lưu ý: fixture này ở trạng thái NEW (availability không có due), nên tại `e5e92aa` test overview đi qua nhánh fallback R9. Test MySQL ở bước 4 của mục 5 cần fixture có thẻ đến hạn.

### C. Probe fail-open của dashboard (R2)

```python
class Probe(mod.StudySessionApiTests):          # SQLite, dùng fixture có sẵn
    def test_probe_projection_drift(self):
        self._enable_existing_state_note_authority(epoch=14)
        with self.app.app_context():
            progress = CardProgress.query.filter_by(user_id=self.user_id).one()
            progress.queue, progress.due_day = "review", 0   # chỉ làm lệch card_progress
            db.session.commit()
        response = self.client.get("/api/dashboard")
        # 9510d11: 409 AUTHORITY_READ_PARITY_DIVERGED
        # e5e92aa: 200, summary = {new: 0, learning: 0, due: 1}
```

### D. Probe fallback của overview (R9)

```python
class Probe(mod.StudySessionApiTests):
    def test_probe_overview_fallback(self):
        self._enable_existing_state_note_authority(epoch=15)
        today = _day_index(datetime.utcnow(), 4, timezone_name="UTC")
        with self.app.app_context():
            progress = CardProgress.query.filter_by(user_id=self.user_id).one()
            progress.queue, progress.due_day = "review", today + 3   # chỉ làm lệch card_progress
            db.session.commit()
        response = self.client.get("/api/statistics/overview",
                                   query_string={"year": date.fromordinal(today).year, "timezone": "UTC"})
        # 9510d11: 409 AUTHORITY_READ_PARITY_DIVERGED
        # e5e92aa: 200, heatmap[today + 3] = {"cards": 1, "source": "due", ...}
```

### E. Probe phân loại (R3)

Dùng fixture của `tests/test_deck_aggregation_service.py`, với `now = 2026-09-29 12:00 UTC` và learner ở timezone UTC. Kết quả giống nhau ở `1f95790` và `e5e92aa`:

| Card | `counter_bucket_for_progress_values` | `aggregate_deck_study_counts` |
|---|---|---|
| `queue='review', due_day=None, due_at=2026-09-29 20:00` | `review` | `{total: 1, new: 0, learn: 0, due: 0}` |
| `queue=''` | `new` | `{total: 1, new: 0, learn: 0, due: 0}` |

### F. Benchmark dashboard aggregate

Seed trực tiếp vào MySQL 8.0 (tạm tắt `FOREIGN_KEY_CHECKS`) với 1 user, 1.527 deck, 39.282 note/card/`card_progress`, phân bố queue như user 1, `field_values` khoảng 1,3 KB/note, rồi chạy `ANALYZE TABLE`. Gọi `aggregate_deck_study_counts(visible_deck_ids=<1.527 deck>, is_note_mode=True)` tại `1f95790` 5 lần: **1,171 / 0,718 / 0,664 / 0,630 / 0,700 giây**, 3 câu SQL mỗi lần (installs, note type, aggregate). Đây chỉ là số đo của riêng hàm đếm trên máy local, không phải latency đầy đủ của API qua Nginx.
