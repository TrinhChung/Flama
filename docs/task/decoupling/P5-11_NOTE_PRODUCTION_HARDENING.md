# P5-11 — Gia cố NOTE authority sau R1

> Lập 2026-09-30. Trạng thái: **P5-11a xong (code + kiểm chứng local MySQL)**; P5-11b (mở phiên O(phạm vi), các reader còn khóa) đang làm. Nguồn: [báo cáo tải](../../architecture/DATABASE_ARCHITECTURE_SCALABILITY_REVIEW_2026-09-29.md), [điều tra truy vấn](../../architecture/DATABASE_QUERY_PERFORMANCE_INVESTIGATION_2026-09-29.md), log production 28–30/09.

## 1. Vì sao cần

R1 (29/09) đưa 18/18 learner sang NOTE. Hai lớp lỗi xuất hiện khi dùng thật:

| Bằng chứng | Nguồn | Hệ quả |
|---|---|---|
| 50 % commit phiên học mất vì deadlock khi 4–8 learner học cùng lúc; 27 % đăng ký đồng thời trả 500 | báo cáo tải §3.3–3.4 | Learner phải bấm gửi lại; người mới không tạo được tài khoản |
| Tái hiện local (6 learner × 3 vòng, 10 đăng ký): **9/18 commit lỗi, 9/10 đăng ký lỗi** | `scripts/probe_p5_concurrency_mysql.py` trên code `a7a15cf` | như trên |
| Deadlock trả về HTTP 409 với mã `e3q8` và **nguyên câu SQL trong `message`** | probe + code (`getattr(exc, "code")`) | Lộ cấu trúc SQL cho client; client coi lỗi hạ tầng là xung đột nghiệp vụ |
| `1205 Lock wait timeout` trên `study_progress_subjects … FOR UPDATE`; 7 dashboard + 6 overview trả 504 | journal `flama.service`, nginx 28–30/09 | Bản sửa #171 (reader không khóa) đã merge nhưng **chưa deploy**: CI master của #171 fail, #172 chỉ sửa test nên job deploy bị bỏ qua. Production vẫn chạy `22f8695`. |

## 2. Nguyên nhân gốc

Dưới REPEATABLE READ, `SELECT … FOR UPDATE` trên **một khóa chưa tồn tại** hoặc **một khoảng rỗng** giữ gap lock. Các dòng mới của learner khác nằm cạnh nhau ở cuối index, nên hai transaction cùng giữ một gap rồi cùng chờ insert-intention của nhau. Thiết kế P4/P5 dùng đọc khóa chỉ để có *current read* (xem [P4-07 InnoDB finding](../../architecture/phase-4-native-session-worker-mirror-verification-2026-09-13.md#innodb-isolation-finding)); tuần tự hóa thật sự đến từ khóa cha (User, subject, token, contributor). Gap lock là tác dụng phụ không cần thiết.

Bốn điểm "đọc-khóa-rồi-chèn" gặp trong probe, theo thứ tự lộ ra:

| Bảng | Nơi đọc | Sửa |
|---|---|---|
| `study_authority_enrollments` | `stage_note_authority_enrollment` | Đọc snapshot trước; chỉ `FOR UPDATE` theo PK khi dòng tồn tại. User đã bị khóa FOR UPDATE nên mọi writer tuần tự; snapshot cũ chỉ có thể dẫn tới lỗi khóa chính khi insert (fail closed). |
| `study_progress_lineage_refs` | `finalize_study_authority_evidence` | Khóa theo PK các dòng thấy trong snapshot rồi **chứng minh** chúng là hiện hành: digest tính lại (đúng công thức reconciliation P4-10) phải bằng `contributor.lineage_vector_hash` đọc khóa. Mọi writer lineage cập nhật contributor trong cùng transaction. Lệch → đọc khoảng như cũ. |
| `study_authority_command_receipts` | `_locked_replay`, `read_direct_note_replay` → `lock_operation_receipt` | Receipt thấy trong snapshot → khóa theo PK. Không thấy → chỉ bỏ khóa khi token của subject (đang giữ FOR UPDATE) trong snapshot bằng token hiện hành, tức không có commit nào trên subject sau snapshot; nếu khác → đọc khóa như cũ. |
| `study_progress_history_facts` | `append_native_history_fact` | Luồng NOTE vừa chèn `ReviewEvent` trong chính transaction chưa commit, nên không fact nào đã commit có thể trỏ tới nó: bỏ lookup (`event_created_in_transaction=True`). Ràng buộc unique vẫn chặn trùng. |

Thêm hai lớp bảo vệ:

- `app/services/db_errors.py`: `domain_error_code()` không coi `SQLAlchemyError.code` là mã nghiệp vụ (thay 15 chỗ `getattr(exc, "code")` trong luồng học, MCP, switch). Lỗi DB giờ đi tới handler chung (500, không lộ SQL) hoặc được retry.
- `run_with_deadlock_retry()`: chạy lại tối đa 3 lần khi InnoDB báo 1213 (nạn nhân deadlock đã bị rollback toàn bộ, nên chạy lại không lặp tác dụng phụ). Áp dụng cho commit phiên, mở phiên, trả lời trực tiếp REST, MCP `submit_review`, đăng ký. Không retry 1205.

Không đổi schema, cờ hay mức cô lập; không đổi hợp đồng API ngoài việc deadlock không còn trả 409 `e3q8`.

## 3. Kiểm chứng

| Kiểm chứng | Kết quả |
|---|---|
| `probe_p5_concurrency_mysql.py` 6 learner × 3 vòng × 12 câu, 10 đăng ký — trước sửa | 9 deadlock, 9/18 commit lỗi; 9/10 đăng ký lỗi |
| Cùng probe — sau sửa | **0 deadlock**, 18/18 commit, 10/10 đăng ký vào NOTE, audit PASS mọi learner |
| 8 learner × 5 vòng × 20 câu, 12 đăng ký | 0 deadlock, 40/40 commit, 12/12 đăng ký, audit PASS |
| Thêm 36 câu trả lời trực tiếp REST đồng thời | 0 deadlock, 36/36 |
| `tests/test_study_note_write_gap_locks.py` | hình dạng câu lệnh không khóa dòng vắng; fallback lineage đúng dòng; replay receipt còn nguyên |
| `run_tests.py --module study,auth,connect_mcp --backend-only` | 67 file PASS |
| Probe MySQL direct-replay / study-batch | xem §5 |

Probe mới chạy trong job CI `mysql-contract`.

## 4. Rollback

Chỉ đổi code. Deploy lại release trước theo workflow; không có migration hay dữ liệu cần đảo. Các đường fallback giữ đúng hành vi cũ khi không chứng minh được snapshot.

## 5. Việc còn lại (P5-11b)

1. **Deploy**: merge PR này đưa cả #171 lên production (hết 504 dashboard/overview). Sau deploy chạy lại vòng audit runbook §4.2.4.
2. **Mở phiên O(phạm vi)**: `open_study_session` snapshot tới 5.000 thẻ, khóa subject/token/state từng Note và chèn 1 dòng `study_session_cards` + 1 pin cho mỗi thẻ (≈8 câu SQL/thẻ). Với learner 39.282 thẻ, mỗi lần mở (và mỗi 50 câu, SPA mở lại) là hàng chục nghìn câu lệnh.
3. **Reader còn khóa**: Browse tree/list, `stats_today_future`, `/api/study/next`, MCP đọc (`get_card`, `get_due`…): dùng `load_study_authority_card_reads` khóa FOR UPDATE toàn bộ subject trong phạm vi.
4. **Frontend gửi commit hai lần** (LEGACY v3): sau commit `auto_finish` thành công, `flushOnExit` gửi lại cùng `commit_id` với `final_states` đã cập nhật → 409 `IDEMPOTENCY_KEY_REUSED`. Dữ liệu lần đầu đã lưu; với v4 (`final_states` rỗng) lần gửi lại là replay 200. Chỉ còn ảnh hưởng phiên LEGACY cũ trong IndexedDB.
5. Retention `study_session_cards`/`study_session_authority_pins` thuộc Phase 7.
