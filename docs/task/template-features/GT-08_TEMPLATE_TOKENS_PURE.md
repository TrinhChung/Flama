# GT-08 — Python thuần: trích/đổi tên biến Mustache trong template và hash nội dung

- Owner: Gemini. Reviewer: Claude (review đối kháng bắt buộc). Milestone: M2 (chạy song song từ đợt 0). Phụ thuộc: CT-00.
- Loại: module Python mới, không import Flask/DB, có test bảng.
- Người dùng các hàm: CT-02/CT-03 (hash version, backfill), CT-06 (input schema, materialize binding), CT-05 (cờ upstream thay đổi).

## 1. Bối cảnh

Renderer dùng `chevron` (Mustache, delimiter mặc định `{{ }}`) và tham chiếu field theo **tên** (`app/services/flashcard_renderer.py`, `render_template_pair`, `build_render_context`). Context có thêm khóa `<Field>_url` và `<Field>_urls` cho field media. Tên field có thể chứa dấu cách, dấu chấm (`a.b` là tên phẳng), ký tự Unicode (`漢字`, `Nghĩa`). Không có hỗ trợ filter kiểu Anki (`{{text:X}}`) hay `{{FrontSide}}`: các chuỗi đó chỉ là tên biến bình thường với Mustache.

## 2. Mục tiêu

Tạo `app/services/template_tokens.py` với 4 hàm và 1 exception, không phụ thuộc Flask, SQLAlchemy hay model.

## 3. File được tạo (không sửa file nào khác)

| File | Nội dung |
|---|---|
| `app/services/template_tokens.py` | Module §4. |
| `tests/test_template_tokens.py` | Test §5 (`unittest`, không cần app/DB). |

## 4. Hợp đồng chính xác

```python
class TemplateTokenError(ValueError):
    def __init__(self, code: str, message: str) -> None: ...
    # thuộc tính: self.code

def extract_variable_names(source: str | None) -> list[str]: ...
def rewrite_variable_names(source: str | None, mapping: dict[str, str]) -> str: ...
def base_variable_name(name: str, known_names: set[str]) -> str: ...
def template_content_hash(front_html: str | None, back_html: str | None, shared_css: str | None) -> str: ...
```

### 4.1 Nhận diện tag

Dùng một regex duy nhất, DOTALL, ưu tiên triple trước:

```python
_TAG_RE = re.compile(r"\{\{\{(?P<triple>.*?)\}\}\}|\{\{(?P<body>.*?)\}\}", re.DOTALL)
```

Với mỗi match theo thứ tự xuất hiện:

1. Nhóm `triple`: tên = nội dung đã `strip()`. Rỗng hoặc `.` → bỏ qua.
2. Nhóm `body`: bỏ khoảng trắng đầu. Rỗng → bỏ qua. Ký tự đầu (sigil):
   - `!` (comment) hoặc `>` (partial) → bỏ qua cả tag.
   - `=` (đổi delimiter) → raise `TemplateTokenError("DELIMITER_CHANGE_UNSUPPORTED", "Delimiter change tags are not supported.")`.
   - `#`, `^`, `/`, `&` → tên = phần sau sigil, `strip()`.
   - ký tự khác → tên = toàn bộ body `strip()`.
   - Tên rỗng hoặc `.` → bỏ qua.
3. Ghi nhận **vị trí bắt đầu/kết thúc của riêng phần tên** trong `source` (không gồm dấu cách, sigil, ngoặc). Hàm rewrite chỉ thay đúng đoạn này.

Tag nằm trong `<script>`/`<style>` vẫn được xử lý như mọi tag khác.

### 4.2 `extract_variable_names`

Trả danh sách tên theo thứ tự xuất hiện đầu tiên, không trùng. `None` hoặc `""` → `[]`.

### 4.3 `rewrite_variable_names`

- Kiểm tra `mapping` trước: mỗi giá trị phải là `str`, khác rỗng sau `strip()`, bằng chính nó sau `strip()`, không chứa `{` hoặc `}`; sai → `ValueError`.
- Duyệt các tag theo §4.1. Với tên `n`:
  - `n in mapping` → thay bằng `mapping[n]`;
  - ngược lại nếu `n` kết thúc `_urls` và `n[:-5] in mapping` → `mapping[n[:-5]] + "_urls"`;
  - ngược lại nếu `n` kết thúc `_url` và `n[:-4] in mapping` → `mapping[n[:-4]] + "_url"`;
  - ngược lại giữ nguyên.
- Mọi ký tự ngoài đoạn tên được giữ nguyên từng byte (kể cả khoảng trắng trong tag, comment, partial). Thay thế đồng thời (không áp mapping hai lần): `{"A": "B", "B": "A"}` trên `{{A}}{{B}}` cho `{{B}}{{A}}`.
- Đổi delimiter → `TemplateTokenError` như §4.1.

### 4.4 `base_variable_name`

`name in known_names` → `name`; ngược lại kết thúc `_urls` và `name[:-5] in known_names` → `name[:-5]`; ngược lại kết thúc `_url` và `name[:-4] in known_names` → `name[:-4]`; còn lại → `name`.

### 4.5 `template_content_hash`

```python
payload = {"front_html": front_html or "", "back_html": back_html or "", "shared_css": shared_css or ""}
digest = hashlib.sha256(
    json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
).hexdigest()
```

Không chuẩn hóa khoảng trắng/xuống dòng. Giá trị vàng (bắt buộc khớp):
`template_content_hash("{{Word}}", "{{Word}}<hr>{{Meaning}}", "") == "7848287f04a3dc0ce90078c66bc73ee7f1e184d47f03e922a595baa6e1f7f698"`.

## 5. Test bắt buộc (`tests/test_template_tokens.py`)

Dùng `subTest` cho bảng. Mọi kỳ vọng dưới đây đã được Claude kiểm chứng bằng bản cài đặt tham chiếu.

### 5.1 `extract_variable_names`

| Input | Kỳ vọng |
|---|---|
| `<div>{{Word}}</div>` | `["Word"]` |
| `{{ Word }} {{Word}}` | `["Word"]` |
| `{{{Meaning}}}` | `["Meaning"]` |
| `{{& Meaning}}` | `["Meaning"]` |
| `{{#Audio}}<b>{{Audio}}</b>{{/Audio}}{{^Audio}}none{{/Audio}}` | `["Audio"]` |
| `{{! comment {{Hidden}} }}x{{Word}}` | `["Word"]` |
| `{{> partial}}{{Word}}` | `["Word"]` |
| `{{#list}}{{.}}{{/list}}` | `["list"]` |
| `{{Meaning VN}}` | `["Meaning VN"]` |
| `{{a.b}}{{a}}` | `["a.b", "a"]` |
| `<img src="{{Image_url}}">{{#Image_urls}}{{.}}{{/Image_urls}}` | `["Image_url", "Image_urls"]` |
| `{{漢字}}<hr>{{Nghĩa}}` | `["漢字", "Nghĩa"]` |
| `<script>var w='{{Word}}';</script>` | `["Word"]` |
| `""` và `None` | `[]` |
| `{{}} {{ }}` | `[]` |
| `"{{!multi\nline}}{{B}}{{A}}"` | `["B", "A"]` |
| `{{=<% %>=}}` | raise `TemplateTokenError`, `code == "DELIMITER_CHANGE_UNSUPPORTED"` |

### 5.2 `rewrite_variable_names`

| Source | Mapping | Kỳ vọng |
|---|---|---|
| `<div>{{Word}}</div>` | `{"Word": "Kanji"}` | `<div>{{Kanji}}</div>` |
| `{{ Word }}\|{{{ Word }}}\|{{& Word}}` | `{"Word": "Kanji"}` | `{{ Kanji }}\|{{{ Kanji }}}\|{{& Kanji}}` |
| `{{# Audio }}x{{/ Audio}}{{^Audio}}y{{/Audio}}` | `{"Audio": "Sound"}` | `{{# Sound }}x{{/ Sound}}{{^Sound}}y{{/Sound}}` |
| `{{Image_url}} {{#Image_urls}}{{.}}{{/Image_urls}}` | `{"Image": "Pic"}` | `{{Pic_url}} {{#Pic_urls}}{{.}}{{/Pic_urls}}` |
| `{{Image_url}}` | `{"Image": "Pic", "Image_url": "Other"}` | `{{Other}}` |
| `{{! Word }}{{> Word}}{{Word}}` | `{"Word": "K"}` | `{{! Word }}{{> Word}}{{K}}` |
| `{{a.b}}{{a}}` | `{"a": "x"}` | `{{a.b}}{{x}}` |
| `{{Words}}{{Word}}` | `{"Word": "K"}` | `{{Words}}{{K}}` |
| `{{Meaning}}` | `{"Word": "K"}` | `{{Meaning}}` |
| `<script>var w='{{Word}}';</script>` | `{"Word": "語"}` | `<script>var w='{{語}}';</script>` |
| `{{prompt}}<hr>{{answer}}` | `{"prompt": "Kanji", "answer": "Meaning VN"}` | `{{Kanji}}<hr>{{Meaning VN}}` |
| `{{A}}{{B}}` | `{"A": "B", "B": "A"}` | `{{B}}{{A}}` |

(Ký tự `\|` trong bảng là dấu `|` thật.)

Thêm:

- **Round-trip:** với mọi source ở bảng 5.1 (trừ case delimiter), `rewrite_variable_names(s, {n: n for n in extract_variable_names(s)}) == s`.
- **Mapping không hợp lệ:** `{"Word": ""}`, `{"Word": "a}b"}`, `{"Word": " K"}`, `{"Word": "{x"}` đều raise `ValueError`.
- **None:** `rewrite_variable_names(None, {})` == `""`.

### 5.3 `base_variable_name`

| Gọi | Kỳ vọng |
|---|---|
| `("Image_url", {"Image"})` | `"Image"` |
| `("Image_urls", {"Image"})` | `"Image"` |
| `("Image_url", {"Image", "Image_url"})` | `"Image_url"` |
| `("Foo_url", {"Image"})` | `"Foo_url"` |
| `("Word", {"Word"})` | `"Word"` |

### 5.4 `template_content_hash`

- Giá trị vàng ở §4.5.
- `template_content_hash(None, None, None) == template_content_hash("", "", "")`.
- Đổi 1 ký tự ở bất kỳ tham số nào → hash khác; hoán đổi front/back → hash khác.
- Kết quả dài 64, chỉ gồm `0-9a-f`.

## 6. Kiểm tra

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_template_tokens -v
& .\.venv\Scripts\python.exe -c "import app.services.template_tokens as m; print(sorted(n for n in dir(m) if not n.startswith('_')))"
git diff --check
git status --short
```

Lệnh thứ hai phải in đúng các tên public: `TemplateTokenError`, `base_variable_name`, `extract_variable_names`, `rewrite_variable_names`, `template_content_hash` (có thể kèm tên module import như `hashlib`, `json`, `re`; báo cáo nguyên văn).

## 7. Ghi chú review cho Claude

- Chạy thêm round-trip trên toàn bộ template thật (dump `templates.front_html/back_html` local) ở CT-02: identity mapping phải trả lại đúng chuỗi.
- So với `chevron`: comment kết thúc ở `}}` đầu tiên; xác nhận bằng một test so khớp `chevron.render` khi CT-06 dùng hàm cho materialize.

## 8. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-08. Đọc và làm đúng theo docs/task/template-features/GT-08_TEMPLATE_TOKENS_PURE.md (§1–§6).
Module mới KHÔNG import flask, sqlalchemy, models hay app.* khác; chỉ dùng hashlib, json, re, typing.
Mọi giá trị kỳ vọng trong bảng §5 phải được dùng nguyên văn; nếu cài đặt của bạn cho kết quả khác,
sửa cài đặt (không sửa kỳ vọng) và nêu trong báo cáo. Chỉ tạo 2 file ở §3. Báo cáo theo README §3. Không commit.
```
