# Bảng Theo Dõi Công Việc Đang Xử Lý Dở & Kế Hoạch Bàn Giao (2026-10-12)

> **Mục đích:** Tài liệu này ghi nhận tập trung toàn bộ các hạng mục code đã xong nhưng chưa merge vào `master`, các phần việc đang xử lý dở trong các worktree, và các lỗi test suite phát sinh cần giải quyết nhằm tránh bỏ sót khi chuyển đổi ngữ cảnh làm việc.

---

## 1. Danh Sách Code Đã Làm Xong — Chờ Merge Vào `master`

* **Nhánh nguồn:** `feat/typing-back-audio-usage` (đã push lên `origin/feat/typing-back-audio-usage`).
* **Trạng thái:** Hoàn tất, đã tự kiểm thử, chờ tạo PR / merge vào `master`.
* **Gồm 7 commit:**
  1. `fbe0fca5` — **asbplayer:** Tách module asbplayer độc lập với Yomitan, có trang cấu hình và hướng dẫn tương tác.
  2. `9b5db52e` — **UI/UX Mobile:** Tối ưu hóa modal chọn Template và ẩn language switcher trên header mobile.
  3. `cdbd1cc5` — **Study Preparation:** Tự động chọn sẵn template và ghi nhớ tùy chọn chuẩn bị học tập (Study Preparation) theo mặc định (1-click study).
  4. `a1a67ce4` — **Hiệu năng Note Type:** Tối ưu hóa danh sách compact Note Type và tiến trình gắn Template vào NoteType.
  5. `cc1abef0` — **Báo cáo mảng bản địa:** Tài liệu nghiệm thu và manifest dọn dẹp mảng Native JSON Array trên production.
  6. `abd962d5` — **Browse Code View:** Bổ sung chế độ xem Normal & JSON code view cho các trường mảng `array` trong Browse Cards.
  7. `e14d78db` — **Native JSON Array Storage:** Nâng cấp lưu trữ mảng JSON bản địa và cơ chế render Mustache `{{#field}}{{.}}{{/field}}`.

---

## 2. Các Hạng Mục Đang Xử Lý Dở (In-Progress)

### A. Dọn Dẹp Legacy Models & Branching (Worktree: `nihongo-legacy-retirement`)
* **Nhánh:** `refactor/legacy-retirement-20261012`
* **Công việc đã làm:**
  - Audit 100% dữ liệu Local và VPS: Xác nhận 32/32 user đã ở `NOTE` mode (`CONSOLIDATED_V1`), không còn user/progress legacy nào cần migrate.
  - Xóa bỏ 4 model vật lý: `models/card_progress.py`, `models/column_preference.py`, `models/study_progress_backfill_*.py`.
  - Cắt bỏ hơn 5.300 dòng code rẽ nhánh fallback legacy trong các service và repository (`study_service.py`, `browse_card_service.py`, `study_worker_service.py`, `startup_schema.py`).
  - Đã chuẩn bị sẵn các migration:
    - `20261012_000058_retire_unused_backfill_models.py` (Retire 4 model backfill & column preferences)
    - `20261012_000059_retire_card_progress.py` (Retire bảng card_progress)
    - `20261012_000060_retire_template_origin.py` (Drop quan hệ Template origin)
    - `20261012_000061_index_note_due_selection.py` (Tối ưu index range scan cho queue queries)
* **Điểm nghẽn dở dang cần fix (Test Suite Blockers):**
  - Chạy `python scripts/run_tests.py --module study` phát hiện **81 lỗi test** (`FAILED (failures=7, errors=74)`):
    1. **`ModuleNotFoundError: No module named 'models.card_progress'`**: Các file test cũ (`test_deck_count_projection.py`, `test_study_session_api.py`, `test_scheduler_schema.py`, `test_study_direct_note_replay.py`,...) vẫn còn câu lệnh `import CardProgress`.  
       👉 *Cần làm:* Thay thế bằng `study_note_fixtures.py` hoặc cập nhật assertions sang `StudyProgressSubject`.
    2. **Mã lỗi `409 STUDY_AUTHORITY_MIGRATION_REQUIRED`**: Do đã ngắt bỏ hoàn toàn fallback legacy, mọi learner bắt buộc phải có enrollment `CONSOLIDATED_V1`. Một số test fixtures cũ tạo user mà không tạo enrollment bản ghi tương ứng.  
       👉 *Cần làm:* Bổ sung auto-enrollment trong các test fixtures tương ứng.

---

### B. Kiến Trúc Thẻ Dẫn Xuất — P11 Derived Cards (Worktree: `p11-derived-card`)
* **Nhánh:** `worktree-p11-derived-card`
* **Công việc đã làm:**
  - Commit `1bcfebaa`: Gỡ bỏ learner fence chết khỏi Card expansion (P11-0).
  - Soạn thảo migration `20261011_000057_derive_cards_from_occurrences.py`.
  - Xây dựng cơ chế `PresentationAlias` và đã pass 26 unit tests trên SQLite (`test_derived_card_retirement_migration.py`, `test_derived_card_retirement_scope.py`).
* **Công việc dở dang cần hoàn tất:**
  - Hoàn tất chỉnh sửa trên 87 file đang modified chưa commit trong worktree.
  - Chuyển đổi toàn bộ các consumer (Browse, Session, Template Library, Flama Connect protocol) sang sử dụng thẻ dẫn xuất thay cho truy vấn bảng `cards`.
  - Hợp nhất (rebase/merge) với nhánh dọn dẹp legacy `refactor/legacy-retirement-20261012`.

---

## 3. Các File Tài Liệu & Script Nghiệm Thu Mới (Cần Commit Tránh Thất Lạc)

Các file này hiện đã được soạn thảo đầy đủ nhưng đang ở trạng thái **Untracked** trong git working directory:

1. [`docs/architecture/LEGACY_MODEL_CLEANUP_REVIEW_2026-10-12.md`](file:///d:/Project/nihongo/docs/architecture/LEGACY_MODEL_CLEANUP_REVIEW_2026-10-12.md): Báo cáo rà soát 110 model, xác định 4 model chết, `CardProgress` và `Template` origin.
2. [`docs/plans/LEGACY_PROGRESS_RETIREMENT_PLAN_2026-10-12.md`](file:///d:/Project/nihongo/docs/plans/LEGACY_PROGRESS_RETIREMENT_PLAN_2026-10-12.md): Kế hoạch thực thi 6 đợt từ R0 đến R5 dọn dẹp legacy.
3. [`docs/tasks/STUDY_BROWSE_LEGACY_BRANCHING_PERFORMANCE_ISSUES.md`](file:///d:/Project/nihongo/docs/tasks/STUDY_BROWSE_LEGACY_BRANCHING_PERFORMANCE_ISSUES.md): Khảo sát 2 điểm nghẽn hiệu năng lớn do legacy gây ra (Divergence Check trong Browse & Predicate `OR` trong Study Queue).
4. [`docs/architecture/P11_DERIVED_CARD_PLAN_REVIEW_2026-10-11.md`](file:///d:/Project/nihongo/docs/architecture/P11_DERIVED_CARD_PLAN_REVIEW_2026-10-11.md): Báo cáo review rủi ro R1..R7 của P11.
5. [`docs/architecture/artifacts/legacy_progress_retirement_20261012/`](file:///d:/Project/nihongo/docs/architecture/artifacts/legacy_progress_retirement_20261012/): Chứa các artifact bằng chứng audit Local và VPS.
6. [`scripts/audit_legacy_progress_retirement.py`](file:///d:/Project/nihongo/scripts/audit_legacy_progress_retirement.py) & [`tests/test_legacy_progress_retirement_audit.py`](file:///d:/Project/nihongo/tests/test_legacy_progress_retirement_audit.py): Công cụ audit tự động và 12 tests đã pass.

---

## 4. Thứ Tự Hành Động Khuyến Nghị Tiếp Theo (Next Steps Checklist)

- [ ] **Bước 1 (Commit Docs & Tooling):** Commit các file tài liệu kiến trúc, script audit và kế hoạch đang untracked vào nhánh làm việc để lưu vết an toàn trong git.
- [ ] **Bước 2 (Merge 7 commit sẵn sàng):** Mở PR / merge 7 commit trên `feat/typing-back-audio-usage` vào `master` để đóng gói các tính năng asbplayer, mobile UX và native array.
- [ ] **Bước 3 (Sửa lỗi test trên nhánh legacy):**
  - Cập nhật các file test còn import `models.card_progress`.
  - Cập nhật fixture để learner có enrollment `CONSOLIDATED_V1`.
  - Đảm bảo `python scripts/run_tests.py --module study` pass 100%.
- [ ] **Bước 4 (Hợp nhất P11 & Legacy Retirement):** Ghép nối derived cards vào nhánh legacy retirement, chạy rehearsal trên MySQL Local trước khi triển khai lên VPS.
