# GT-01 — Nội dung mặc định của template theo field thật của NoteType

- Owner: Gemini. Reviewer: Claude. Milestone: M1. Phụ thuộc: CT-00.
- Loại: backend Python, thay đổi nhỏ, có test mới.

## 1. Vấn đề

Khi tạo NoteType có `field_defs` nhưng không gửi `template`, hoặc khi tạo template mới không gửi `front_html`/`back_html`, backend luôn dùng `{{Word}}`. NoteType không có field `Word` sẽ sinh thẻ trống.

Code hiện tại trong `app/services/flashcards_share_service.py` (đã đối chiếu tại commit `faa3c7d`):

```python
# trong create_note_type(...), khoảng dòng 223-226
    template_payload = payload.get("template") or {}
    front_html = (template_payload.get("front_html") or "{{Word}}").strip()
    back_html = (template_payload.get("back_html") or "{{Word}}").strip()
    shared_css = (template_payload.get("shared_css") or "").strip()
```

```python
# trong create_template(...), khoảng dòng 264-267
    name = (payload.get("name") or "").strip() or f"Card {Template.query.filter_by(note_type_id=note_type.id).count() + 1}"
    front_html = (payload.get("front_html") or "{{Word}}").strip()
    back_html = (payload.get("back_html") or "{{Word}}").strip()
    shared_css = (payload.get("shared_css") or "").strip()
```

Trong `create_note_type`, danh sách field đầu vào là biến `input_fields` (list dict có `name`, `position`); vị trí thật được ghi bằng `int(row.get("position", idx))`. Khi không có `field_defs`, `input_fields` mặc định là một field `Word`.

Renderer **không** hỗ trợ `{{FrontSide}}`, nên không được dùng token đó.

*Cập nhật 2026-10-10:* renderer đã hỗ trợ `{{FrontSide}}` (`FRONT_SIDE_TOKEN_RE` trong `app/services/flashcard_renderer.py`). Nội dung mặc định vẫn không cần token này.

## 2. Mục tiêu

Thêm một helper thuần và dùng nó ở đúng hai chỗ trên. Không đổi hành vi khi người gọi đã gửi `front_html`/`back_html`.

## 3. File được sửa

| File | Được làm gì |
|---|---|
| `app/services/flashcards_share_service.py` | Thêm hàm `default_template_sources` ngay trên `def create_note_type(`; sửa đúng 2 dòng `front_html`/`back_html` trong `create_note_type` và 2 dòng trong `create_template`. Không sửa dòng nào khác. |
| `tests/test_template_default_content.py` | Tạo mới. |

CẤM: `app/services/share/note_types.py` (bản trùng lặp cũ, ngoài phạm vi), `app/services/mcp/**`, `app/services/connect/**`, `app/services/flashcard_content_service.py`, frontend, mọi test khác.

## 4. Hợp đồng chính xác

```python
def default_template_sources(field_rows: list[tuple[int, str]]) -> tuple[str, str]:
    """Return (front_html, back_html) for a new template.

    field_rows: (position, name) of the NoteType's fields, any order.
    """
```

Quy tắc (theo đúng thứ tự):

1. Bỏ các phần tử có `name` rỗng sau `strip()`.
2. Sắp xếp ổn định theo `(position, name)` tăng dần.
3. Không còn phần tử nào → trả `("{{Word}}", "{{Word}}")` (giữ hành vi cũ).
4. `first = "{{" + names[0] + "}}"`.
5. Có ít nhất 2 tên → `back = first + "<hr>" + "{{" + names[1] + "}}"`; ngược lại `back = first`.
6. Trả `(first, back)`. Không thêm khoảng trắng, xuống dòng hoặc HTML khác.

Sửa trong `create_note_type`:

```python
    template_payload = payload.get("template") or {}
    default_front, default_back = default_template_sources(
        [
            (int(row.get("position", idx)), str(row.get("name") or "").strip())
            for idx, row in enumerate(input_fields)
        ]
    )
    front_html = (template_payload.get("front_html") or default_front).strip()
    back_html = (template_payload.get("back_html") or default_back).strip()
```

Sửa trong `create_template` (biến `note_type` đã có sẵn ở đầu hàm):

```python
    default_front, default_back = default_template_sources(
        [(int(field.position or 0), str(field.name or "")) for field in note_type.field_defs]
    )
    front_html = (payload.get("front_html") or default_front).strip()
    back_html = (payload.get("back_html") or default_back).strip()
```

Không đổi cách tính `name`, `shared_css`, `position`, `is_default`, việc tạo `Card`, audit, commit.

## 5. Test bắt buộc (`tests/test_template_default_content.py`)

Harness: sao chép **nguyên** `setUpClass`, `setUp` (gồm đăng nhập `self.client.post("/login", ...)`) và `tearDown` của `FlashcardApiIntegrationTests` trong `tests/test_flashcard_api_integration.py` (dòng ~50-90). Đặt tên lớp `TemplateDefaultContentTests`. Không import lớp đó (để không chạy lại test của nó).

Phần A — unit cho helper (gọi trực tiếp `from app.services.flashcards_share_service import default_template_sources`):

| Test | Input | Kỳ vọng |
|---|---|---|
| `test_helper_two_fields` | `[(0,"Kanji"),(1,"Meaning"),(2,"Audio")]` | `("{{Kanji}}", "{{Kanji}}<hr>{{Meaning}}")` |
| `test_helper_sorts_by_position` | `[(1,"Meaning"),(0,"Kanji")]` | `("{{Kanji}}", "{{Kanji}}<hr>{{Meaning}}")` |
| `test_helper_single_field` | `[(0,"Front")]` | `("{{Front}}", "{{Front}}")` |
| `test_helper_skips_blank_names` | `[(0,"  "),(1,"Back")]` | `("{{Back}}", "{{Back}}")` |
| `test_helper_empty_falls_back` | `[]` | `("{{Word}}", "{{Word}}")` |
| `test_helper_keeps_unicode_name` | `[(0,"漢字"),(1,"Nghĩa")]` | `("{{漢字}}", "{{漢字}}<hr>{{Nghĩa}}")` |

Phần B — qua REST:

| Test | Thao tác | Kỳ vọng |
|---|---|---|
| `test_create_note_type_without_template_uses_fields` | `POST /api/note-types` với `{"name":"NT A","field_defs":[{"name":"Kanji","field_type":"text","position":0,"required":true},{"name":"Meaning","field_type":"text","position":1}]}` (không có `template`) | 201; `templates[0].front_html == "{{Kanji}}"`, `back_html == "{{Kanji}}<hr>{{Meaning}}"` |
| `test_create_note_type_explicit_template_unchanged` | như trên nhưng `"template":{"front_html":"<b>{{Meaning}}</b>","back_html":"X"}` | `front_html == "<b>{{Meaning}}</b>"`, `back_html == "X"` |
| `test_create_template_defaults_to_fields` | tạo NoteType như test đầu, rồi `POST /api/note-types/<id>/templates` với `{"name":"Card 2"}` | 201; `front_html == "{{Kanji}}"`, `back_html == "{{Kanji}}<hr>{{Meaning}}"`, `name == "Card 2"` |
| `test_create_template_partial_payload` | `POST .../templates` với `{"front_html":"{{Meaning}}"}` | `front_html == "{{Meaning}}"`, `back_html == "{{Kanji}}<hr>{{Meaning}}"` |
| `test_create_note_type_default_fields_still_word` | `POST /api/note-types` với `{"name":"NT B"}` | `front_html == "{{Word}}"`, `back_html == "{{Word}}"` |

## 6. Kiểm tra

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_template_default_content -v
& .\.venv\Scripts\python.exe -m unittest tests.test_flashcard_api_integration
& .\.venv\Scripts\python.exe scripts/run_tests.py --module flashcards --backend-only
git diff --check
git diff --stat
```

`git diff --stat` chỉ được có 2 file ở §3.

## 7. Ghi chú review cho Claude (không gửi Gemini)

- Chặn mọi thay đổi ở `share/note_types.py` (bản trùng lặp); ghi nhận follow-up riêng nếu cần đồng bộ.
- Kiểm tra `note_type.field_defs` trong `create_template` đã được load (NoteType đã commit trước đó); test REST ở §5 là bằng chứng.
- MCP/Connect có fallback riêng (investigation §4.1); không đưa vào task này.

## 8. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-01. Đọc và làm đúng theo docs/task/template-features/GT-01_DEFAULT_TEMPLATE_CONTENT.md
(§1–§6). Đọc thêm: AGENTS.md; app/services/flashcards_share_service.py (hàm
create_note_type và create_template); tests/test_flashcard_api_integration.py (dòng 1-120,
chỉ để sao chép harness).
Chỉ sửa: app/services/flashcards_share_service.py (đúng các dòng nêu ở §4) và tạo
tests/test_template_default_content.py.
Chạy các lệnh ở §6, báo cáo theo mẫu README §3. Không commit.
```
