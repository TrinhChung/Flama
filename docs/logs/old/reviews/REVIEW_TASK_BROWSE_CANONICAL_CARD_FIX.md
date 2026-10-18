# Review Task: Browse Canonical Card Deduplication Fix (Multi-Template NoteType)

- **Task ID**: `REVIEW-BROWSE-01`
- **Assigned To**: Claude / GPT (Codex)
- **Status**: Ready for Review
- **Target Branch**: `feat/typing-back-audio-usage`
- **Target Area**: `app/services/browse_card_service.py`, `tests/test_study_note_overlay.py`
- **Context Report**: [`docs/reports/ISSUE_BROWSE_DUPLICATE_CARDS_MULTI_TEMPLATE.md`](../reports/ISSUE_BROWSE_DUPLICATE_CARDS_MULTI_TEMPLATE.md)

---

## 1. Problem Statement & Root Cause

### Vấn đề thực tế (Production Issue)
Người dùng `chungtv38@gmail.com` vào `/browse`, chọn deck `語彙徹底N1 :: Bài 001` (Deck ID 2071) thì thấy mỗi từ vựng (`阻止`, `保護`, `付き添い`, `見放す`, `合理的`...) bị lặp lại **3 dòng y hệt nhau**. Deck có 60 từ nhưng danh sách trả về tới 180 thẻ.

### Nguyên nhân gốc rễ
1. **Flama ADR P11 (Derived Card)**: `Card = Note ⨝ StudyApplication`. NoteType `Flama Standard Vocabulary` có 3 template active (`Default Flama Flashcard` [is_default=True], `Gõ cách đọc`, `Gõ nghĩa`). Do đó, 60 Note $\times$ 3 Template = 180 Cards.
2. **Browse Query Fan-Out**: Hàm `list_browse_cards` trong `app/services/browse_card_service.py` truy vấn `Card.query.join(Note)` mà không chỉ định template chuẩn đại diện (canonical presentation).
3. **Mặt hiển thị**: Bảng Browse (`BrowseCardTable.tsx`) là bảng từ vựng (Word, Reading, Meaning, Status, Due) theo cấp độ Note, không hiển thị tên template. Kết quả là người dùng thấy 3 dòng trùng lặp hoàn toàn cho mỗi từ.

---

## 2. Changes Made (Những thay đổi đã thực hiện)

### A. Backend Logic: `app/services/browse_card_service.py`
1. **Helper `_resolve_canonical_application_ids()`**:
   - Truy vấn các `StudyApplication` đang `ACTIVE`.
   - Gom nhóm theo `note_type_id`, chọn ra đúng 1 template chuẩn theo thứ tự ưu tiên:
     `order_by(StudyApplication.is_default.desc(), StudyApplication.position.asc(), StudyApplication.id.asc())`.
2. **Scoping Card Query**:
   - Thêm tham số `all_templates` / `include_all_templates` vào `query_args`.
   - Mặc định (`all_templates=False`): Thêm điều kiện lọc `query = query.filter(Card.application_id.in_(canonical_app_ids))`.
   - Khi `all_templates=True`: Bỏ qua bộ lọc, trả về toàn bộ Card occurrences nếu cần kiểm tra chẩn đoán.

### B. Unit & Regression Tests: `tests/test_study_note_overlay.py`
1. **Cập nhật `_assert_readers_share_the_note_row`**:
   - Khẳng định `view["list_total"] == 1` với browse mặc định (note-grain).
   - Khẳng định `all_listing["total"] == 2` khi truyền `all_templates="1"`.
2. **Thêm test mới `test_browse_deduplicates_multi_template_notes_to_canonical_card`**:
   - Kiểm tra trực tiếp ca Note có 2 Template: browse mặc định ra 1 dòng (từ vựng đúng), `all_templates=1` ra đủ 2 dòng.

---

## 3. Checklist for Reviewer (Claude / GPT Codex)

Vui lòng rà soát và đánh giá các khía cạnh sau:

1. **Tính đúng đắn của việc chọn Canonical Template**:
   - Thứ tự ưu tiên `(is_default.desc(), position.asc(), id.asc())` có luôn đảm bảo tính xác định (deterministic) cho mọi NoteType không?
   - Trường hợp NoteType không có template nào có `is_default=True` thì fallback sang `position.asc(), id.asc()` đã an toàn chưa?
2. **Bảo toàn Logical Clone Overlay & Tiến độ học tập**:
   - Các bản clone logical overlay (`DeckInstall`, `deck_clone_note_field_overrides`) và `release_membership` đều gắn theo `Note.id`. Việc lọc Card theo canonical application có gây sót từ hoặc mất override của user nào không?
   - Tiến độ học tập (`study_progress_subjects`) vốn liên kết theo `logical_note_key = cast(Note.id, LargeBinary)`. Các bộ lọc New / Learn / Due và sort by due date có hoạt động nhất quán không?
3. **Hiệu năng câu truy vấn (MySQL & SQLite)**:
   - `_resolve_canonical_application_ids()` chạy 1 query nhẹ trên bảng nhỏ `study_applications` (<100 dòng) và truyền list ID vào `Card.application_id.in_(...)`.
   - Việc này có giúp MySQL đẩy điều kiện xuống view join để loại bỏ fan-out sớm trước khi filesort không? Có rủi ro query plan regression nào không?
4. **Tương thích ngược (Backward Compatibility)**:
   - Việc hỗ trợ `all_templates=1` / `include_all_templates=1` đã đủ để bảo vệ các công cụ audit hoặc luồng cần thấy toàn bộ occurrences chưa?

---

## 4. How to Verify (Hướng dẫn chạy kiểm thử)

```powershell
# 1. Chạy unit tests liên quan đến overlay và browse
.venv\Scripts\python.exe -m unittest tests.test_study_note_overlay

# 2. Chạy toàn bộ frontend tests của browse
npm --prefix frontend test src/features/browse

# 3. Chạy test validation & security
.venv\Scripts\python.exe -m unittest tests.test_flashcard_validation_security tests.test_rest_api_v1
```

---

## 5. Review Output Format

Khi thực hiện review, vui lòng xuất báo cáo đánh giá vào file hoặc phản hồi theo cấu trúc:
- **Verdict**: `APPROVE` / `NEEDS_REVISION`
- **Findings**: Nhận xét chi tiết theo 4 mục checklist trên.
- **Edge Cases & Recommendations** (nếu có): Các trường hợp biên cần lưu ý bổ sung thêm test hoặc tối ưu tiếp.
