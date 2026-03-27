# ChungBech File Import Guide

Hướng dẫn import file deck dạng ChungBech (Anki `.txt` export) vào hệ thống Flama.

---

## 1. Cấu trúc file ChungBech

File `ChungBechN1__言葉__Bài 01.txt` là một file TSV export từ Anki, có các đặc điểm sau:

### 1.1 Header dòng đầu (Anki metadata)

```
#separator:tab
#html:true
#tags column:16
```

| Header directive      | Ý nghĩa |
|-----------------------|---------|
| `#separator:tab`      | Delimiter là **tab** (`\t`) |
| `#html:true`          | Nội dung các cột chứa **HTML** |
| `#tags column:16`     | Cột số 16 (0-indexed: 15) là cột **tags** |

> **Lưu ý quan trọng:** Các dòng bắt đầu bằng `#` là metadata Anki, không phải dữ liệu thực. Hệ thống import hiện tại coi chúng là header nếu bật `has_header=true`, nhưng sẽ cần skip riêng nếu xử lý đúng.

### 1.2 Cấu trúc 16 cột (Tab-separated)

| Col # | Tên gợi ý       | Ví dụ                          | Ghi chú |
|-------|-----------------|-------------------------------|---------|
| 0     | **deck_tag**    | `N1語彙Riki::Bài 1`           | Anki deck path (không dùng làm deck trong Flama) |
| 1     | **word**        | `配布`                         | Từ vựng chính (**required**) |
| 2     | **reading**     | `はいふ`                       | Furigana |
| 3     | **meaning_vi**  | `Phân phát`                   | Nghĩa tiếng Việt |
| 4     | **definition_jp** | `不特定多数の人に配ること。` | Định nghĩa tiếng Nhật |
| 5     | **definition_vi** | `Phân phát cho nhiều người bất kỳ.` | Định nghĩa tiếng Việt |
| 6     | **example_jp_label** | `チラシ・ビラ・資料...を配布する` | Cụm từ ví dụ (tiếng Nhật) |
| 7     | **example_vi_label** | `Phân phát tờ rơi...`   | Cụm từ ví dụ (tiếng Việt) |
| 8     | **sentence_jp** | `新しくオープンするお店の...`  | Câu ví dụ tiếng Nhật |
| 9     | **sentence_vi** | `Chúng tôi đã phát tờ rơi...` | Câu ví dụ tiếng Việt |
| 10    | **notes_jp**    | `害虫駆除、敵を駆逐など。`    | Ghi chú tiếng Nhật (thường rỗng) |
| 11    | **extra_html**  | HTML content / rỗng            | Extra notes, có thể chứa HTML phức tạp |
| 12    | **image_html**  | `<img alt="..." src="...">`   | HTML tag ảnh (nếu có) |
| 13    | **audio_word**  | `VOICEVOX_後鬼_..._uuid.mp3`  | Filename âm thanh từ vựng |
| 14    | **audio_sentence** | `VOICEVOX_後鬼_..._uuid.mp3` | Filename âm thanh câu ví dụ |
| 15    | **tags**        | (thường rỗng)                  | Anki tags |

### 1.3 Vấn đề multiline trong file

> ⚠️ **Vấn đề nghiêm trọng:** Một số cards có **nội dung HTML spanning nhiều dòng** (ví dụ card `完結` ở cols 11, cards `細心`, `実情`, `重宝`, `会心`, `究明`). CSV reader với `delimiter=\t` xử lý đúng các quoted multiline fields, nhưng file này **không quote** các newline — chúng là literal newlines trong file `.txt`.

Ví dụ card `完結` (word ở cột 1): cột 11 chứa HTML list dài trải qua nhiều dòng vật lý trong file (dòng 34–65 trong file raw). Đây là **Anki-style unquoted multiline** — không phải TSV chuẩn.

---

## 2. Khuyến nghị: Cách import tốt nhất

### 2.1 Pre-processing bắt buộc

Trước khi upload vào trang `/flashcards/import`, cần **tách bỏ các dòng header Anki**:

```python
# Script tiền xử lý (Python)
with open("ChungBechN1__言葉__Bài 01.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Bỏ các dòng bắt đầu bằng '#'
clean_lines = [l for l in lines if not l.startswith("#")]

with open("chungbech_clean.tsv", "w", encoding="utf-8") as f:
    f.writelines(clean_lines)
```

Hoặc dùng PowerShell:

```powershell
Get-Content "ChungBechN1__言葉__Bài 01.txt" | Where-Object { $_ -notmatch "^#" } | Set-Content "chungbech_clean.tsv"
```

### 2.2 Cài đặt Import UI

| Trường               | Giá trị                |
|----------------------|-----------------------|
| **Delimiter mode**   | `tsv` (tab)            |
| **Has header**       | `false` (sau khi đã xóa dòng `#`) |
| **Import mode**      | `upsert` (khuyến nghị) |
| **Uniqueness field** | `word` (cột 1 — từ vựng chính) |

> Chọn note type trong UI như bình thường — các cột sẽ được map tự động theo thứ tự field của note type.

### 2.3 Xử lý audio

Các filename audio (cột 13, 14) dạng:

```
VOICEVOX_後鬼_人間ver._b949e4f4-0c0d-4c34-a156-bb70b495b6c8.mp3
```

Đây là Anki media filenames. Muốn dùng được trong Flama, cần:
1. Copy các file `.mp3` vào thư mục media của Flama.
2. Map cột audio sang field TTS hoặc dùng làm reference.
3. Hoặc bỏ qua (`ignore`) nếu plan là re-generate TTS qua VOICEVOX.

### 2.4 Xử lý HTML content

Các cột có HTML (cột 11, 12) chứa content như:
```html
<img alt="..." src="36978433.jpg">
<ul><li><div>...</div></li></ul>
```

- **Images**: src là Anki media filename, không tự dùng được — bỏ qua hoặc upload ảnh riêng.
- **HTML lists** trong extra notes: Flama hỗ trợ HTML trong fields nếu note type dùng `html` rendering.

---

## 3. Giải pháp dài hạn: Importer riêng cho ChungBech

Nếu dùng thường xuyên, nên viết CLI importer hoặc script chuyên dụng tại `app/cli.py`:

```
flask import-chungbech <file.txt> --deck "N1語彙" --note-type-id <id>
```

CLI đó sẽ:
1. Strip Anki header lines (`#`)
2. Parse TSV với awareness về multiline HTML
3. Map fields theo schema cứng (word → col 1, reading → col 2, etc.)
4. Upsert notes với uniqueness key = `word`
5. Báo cáo số inserted/updated/skipped

---

## 4. Lưu ý về multiline parsing

Hệ thống import hiện tại dùng Python `csv.reader` với `encoding="utf-8-sig"`:
- **Handles quoted multiline**: nếu cell được wrap trong `"..."`, newlines bên trong được xử lý đúng.
- **Unquoted newlines**: File ChungBech có newlines **tidak diquote** trong một số cells → `csv.reader` sẽ cắt sai dòng.

**Kết quả thực tế**: Khoảng 5/31 cards trong Bài 01 có multiline HTML → sẽ bị parse sai thành nhiều rows ngắn → import sẽ báo column count mismatch hoặc skip.

**Giải pháp**: Trước khi import, chạy script strip + re-join:

```python
import re

def fix_chungbech_multiline(raw_text: str) -> str:
    """
    Anki TSV: dòng hợp lệ bắt đầu bằng 'DeckName\t'.
    Nếu dòng không match pattern này, đây là continuation của dòng trước.
    """
    lines = raw_text.splitlines()
    result = []
    for line in lines:
        if line.startswith("#"):
            continue  # skip Anki metadata
        # Dòng mới hợp lệ = bắt đầu bằng deck path (có '::')
        if re.match(r'^[^\t]+::', line):
            result.append(line)
        elif result:
            # Nối vào dòng trước (multiline cell)
            result[-1] += line
    return "\n".join(result)
```

---

## 5. Checklist import nhanh

- [ ] Xóa dòng header `#separator:tab`, `#html:true`, `#tags column:16`
- [ ] Fix multiline cells (nếu cần)
- [ ] Upload file `.tsv` vào `/flashcards/import`
- [ ] Chọn **Delimiter: TSV**, **Has header: No**
- [ ] Chọn note type phù hợp trong UI
- [ ] Chạy **Estimate** trước, kiểm tra số rows hợp lệ
- [ ] Chạy **Execute** (upsert)
