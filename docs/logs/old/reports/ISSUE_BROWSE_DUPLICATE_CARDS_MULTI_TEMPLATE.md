# BÁO CÁO ĐIỀU TRA NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE ANALYSIS)
## Issue: Hiện tượng lặp thẻ (Duplicate Rows) trên màn hình Duyệt thẻ (Browse) trên Production

- **Mã định danh:** `ISSUE-BROWSE-001`
- **Tài khoản ghi nhận:** `chungtv38@gmail.com`
- **Môi trường:** Production (`flama` trên VPS Hostinger) đối chiếu Local Development (`nihongo`)
- **Phạm vi phản ánh:** Màn hình Duyệt thẻ (`/browse`), deck `語彙徹底N1` -> `Bài 001`.
- **Hiện tượng:** Khi người dùng mở trang Duyệt thẻ, các từ vựng như `見放す`, `合理的`, `刑罰`, `本論`, `行進`... đều xuất hiện lặp lại đúng **3 dòng giống hệt nhau** liên tiếp trong bảng danh sách.

---

## 1. Kết luận sơ bộ (Executive Summary)

1. **Dữ liệu trong Database có bị nhân bản / lặp không?**
   - **HOÀN TOÀN KHÔNG BỊ LẶP DỮ LIỆU TRONG DATABASE.**
   - Trong bảng `notes` (cả trên Database Production lẫn Local), mỗi từ vựng (`見放す`, `合理的`, `刑罰`, `本論`...) thuộc deck `Bài 001` chỉ tồn tại **DUY NHẤT 1 BẢN GHI `Note`**.
   - Tổng số từ vựng của `Bài 001` trên DB chính xác là **60 Notes**, không có bản ghi Note nào bị nhân đôi hay nhân ba.

2. **Tại sao lại hiển thị đúng 3 dòng giống hệt nhau cho mỗi từ trên màn hình Duyệt thẻ?**
   - **Bản chất hệ thống:** Flama xây dựng mô hình Flashcard hiện đại theo ADR P11 (kế thừa triết lý Anki):
     $$\text{Card} = \text{Note} \bowtie \text{StudyApplication (ACTIVE)}$$
     - `Note`: Là đơn vị dữ liệu ngữ nghĩa (Semantic Unit), lưu nội dung từ vựng (`word`, `reading`, `meaning`, `hanviet`...).
     - `StudyApplication` / `Template`: Là mẫu hiển thị / dạng bài tập (Presentation Type / Test Mode).
     - `Card`: Là thể hiện suy biến (Derived Presentation Instance) khi một Note được gán qua một StudyApplication đang hoạt động.
   - **Thực tế trên Production:** Vào ngày **11/10/2026**, NoteType `Flama Standard Vocabulary` (ID: `e2f310a8-ecb3-4446-8a93-4c258e52b132`) của deck `語彙徹底N1` đã được gắn thêm 2 Template bài tập mới:
     1. `Default Flama Flashcard` (Flashcard truyền thống)
     2. `Gõ cách đọc` (Luyện gõ Furigana/Reading - tạo lúc 06:28:56 UTC ngày 11/10/2026)
     3. `Gõ nghĩa` (Luyện gõ Meaning - tạo lúc 06:35:01 UTC ngày 11/10/2026)
     - Cả 3 Template này đều đang ở trạng thái `status_code = 'ACTIVE'`.
     - Vì NoteType có **3 Active Templates**, nên mỗi 1 Note tự động sinh ra **3 Cards** độc lập (tương ứng với 3 bài học khác nhau trong phiên học).
     - Deck `Bài 001` có 60 Notes $\rightarrow$ sinh ra đúng **180 Cards** ($60 \times 3$).

3. **Nguyên nhân code sai (Architectural Grain Mismatch):**
   - **API Backend hoạt động ở cấp độ Thẻ (Card-grain):** API `/api/v1/learning/browse` truy vấn bảng `Card` (`Card.query.join(Note)`), trả về 3 phần tử Card riêng biệt cho 3 dạng bài tập (kèm `card.template` = "Default Flama Flashcard", "Gõ cách đọc", "Gõ nghĩa").
   - **Bảng Frontend hiển thị theo tư duy Bản ghi (Note-grain) nhưng thiếu cột Template:**
     - Component [`BrowseCardTable.tsx`](file:///d:/Project/nihongo/frontend/src/features/browse/components/BrowseCardTable.tsx) duyệt qua mảng `cards`, nhưng **hoàn toàn KHÔNG hiển thị cột Tên Template / Dạng thẻ (`card.template` / `card.card_type`)**.
     - Bảng chỉ render: `card.word`, `card.reading`, `card.meaning`, `card.status`, `card.due_label`. Do 3 Card của cùng 1 Note có chung các giá trị này từ Note gốc, nên 3 hàng hiển thị trên UI trở nên **HOÀN TOÀN GIỐNG NHAU 100%**.
   - **Pane bên phải gây hiểu lầm nghiêm trọng:**
     - Header của pane bên phải ghi là **"Chi tiết Note"** và hiển thị form chỉnh sửa các trường của `Note`. Dù người dùng click vào dòng Card nào trong 3 dòng, bên phải đều hiện form Note giống hệt nhau, khiến người dùng kết luận rằng hệ thống bị "nhân bản 3 bản ghi Note giống nhau".

---

## 2. Bằng chứng điều tra chi tiết từ Database Production (VPS Hostinger)

Chúng tôi đã thực hiện truy vấn trực tiếp và đối soát độc lập trên môi trường Production (`chung_hostinger_vps`, database `flama`):

### 2.1. Kiểm tra bản ghi Note trong bảng `notes` (Deck `Bài 001` - ID: 416)

```sql
SELECT n.id, n.deck_id, JSON_UNQUOTE(JSON_EXTRACT(n.field_values, '$.word')) AS word
FROM notes n
WHERE n.deck_id = 416 AND JSON_EXTRACT(n.field_values, '$.word') IN ('見放す', '合理的', '刑罰', '本論', '行進');
```

**Kết quả từ DB Production:**
| Note ID | Deck ID | Word | Ghi chú |
| :--- | :--- | :--- | :--- |
| `074d6f38-0972-4e90-b7ec-6ab595527d69` | `416` (Bài 001) | `見放す` | **Duy nhất 1 bản ghi** |
| `07fa1676-9290-4731-8a34-8a8c2ed9080a` | `416` (Bài 001) | `合理的` | **Duy nhất 1 bản ghi** |
| `890d20b2-d6e1-42c7-ad20-8f0637007270` | `416` (Bài 001) | `刑罰` | **Duy nhất 1 bản ghi** |
| `e094e431-8ec1-4b09-8914-ba0c05e307e6` | `416` (Bài 001) | `本論` | **Duy nhất 1 bản ghi** |
| `bcedc941-66ae-4e26-b101-3fd1fb7b5c92` | `416` (Bài 001) | `行進` | **Duy nhất 1 bản ghi** |

👉 **Khẳng định:** Không có bất kỳ sự trùng lặp bản ghi Note nào trong database.

---

### 2.2. Kiểm tra các `StudyApplication` gắn với NoteType của `語彙徹底N1`

NoteType của deck là `e2f310a8-ecb3-4446-8a93-4c258e52b132` (`Flama Standard Vocabulary`).

```sql
SELECT sa.id AS application_id, sa.template_id, t.name AS template_name, sa.status_code, sa.created_at
FROM study_applications sa
JOIN templates t ON sa.template_id = t.id
WHERE sa.note_type_id = 'e2f310a8-ecb3-4446-8a93-4c258e52b132';
```

**Kết quả từ DB Production:**
| Application ID | Template ID | Template Name | Status | Created At (UTC) |
| :--- | :--- | :--- | :--- | :--- |
| `e47485cc-84a8-41ae-8836-5dec2e7b9963` | `e0cb18b2-881d-4b46-a567-dc5db14d661f` | **Default Flama Flashcard** | `ACTIVE` | 2026-09-30 09:06:36 |
| `92f75b12-b3fa-4de7-b8d0-848cd66f53f0` | `5c460ccb-5714-48ac-830b-1f74cc611bee` | **Gõ cách đọc** | `ACTIVE` | 2026-10-11 06:28:56 |
| `2ebd52e0-18de-428c-a802-4010da5161a6` | `ef8757fb-f5c8-4670-83e6-3feef962beff` | **Gõ nghĩa** | `ACTIVE` | 2026-10-11 06:35:01 |

👉 **Điểm then chốt:** NoteType này đang có **3 StudyApplications cùng ở trạng thái `ACTIVE`**.

---

### 2.3. Kiểm tra kết quả gọi API `list_browse_cards` trên Production với user `chungtv38@gmail.com`

Khi gọi API `/browse/cards?deck_id=2071` (Deck cài đặt cục bộ `Bài 001` của user `chungtv38@gmail.com` trỏ qua overlay tới source deck 416):

```text
PROD deck 2071 total cards: 180 (60 notes * 3 templates)
Items returned:
  Card ID: 0c24db77...2ebd52e0 | Note ID: 0c24db77... | Template: Gõ nghĩa | Word: 阻止
  Card ID: 0c24db77...92f75b12 | Note ID: 0c24db77... | Template: Gõ cách đọc | Word: 阻止
  Card ID: 0c24db77...e47485cc | Note ID: 0c24db77... | Template: Default Flama Flashcard | Word: 阻止
  Card ID: 9f78ef1e...2ebd52e0 | Note ID: 9f78ef1e... | Template: Gõ nghĩa | Word: 保護
  Card ID: 9f78ef1e...92f75b12 | Note ID: 9f78ef1e... | Template: Gõ cách đọc | Word: 保護
  Card ID: 9f78ef1e...e47485cc | Note ID: 9f78ef1e... | Template: Default Flama Flashcard | Word: 保護
  ...
  Card ID: e094e431...2ebd52e0 | Note ID: e094e431... | Template: Gõ nghĩa | Word: 本論
  Card ID: e094e431...92f75b12 | Note ID: e094e431... | Template: Gõ cách đọc | Word: 本論
  Card ID: e094e431...e47485cc | Note ID: e094e431... | Template: Default Flama Flashcard | Word: 本論
```

Mỗi Note sinh ra 3 Card với ID dạng `<note_id>.<application_id>`.

---

## 3. Phân tích Nguyên nhân Gốc rễ trong Mã nguồn (Code Root Cause)

### 3.1. Phép ánh xạ trong Backend (`models/card.py` & `vocabulary_repository.py`)

Trong [`models/card.py`](file:///d:/Project/nihongo/models/card.py#L158-L189):
```python
_pair_join = _notes.join(_applications, _applications.c.note_type_id == _notes.c.note_type_id)
# Mỗi Note nhân với số StudyApplication của NoteType
```

Khi trả về dữ liệu trong [`app/repositories/vocabulary_repository.py`](file:///d:/Project/nihongo/app/repositories/vocabulary_repository.py#L451-L493):
```python
def build_browse_row(card_obj: Card, ...):
    note_obj = card_obj.note
    display_triplet = note_display_triplet(note_obj)
    # word, reading, meaning lấy từ note_obj
    return {
        "card_id": card_obj.id,
        "note_id": note_obj.id,
        "template": card_obj.template.name if card_obj.template else "Card",
        "card_type": f"{note_type_name} / {template_name}",
        "word": display_triplet["word"],
        "reading": display_triplet["reading"],
        "meaning": display_triplet["meaning"],
        "status": status_code,
        "due_label": browse_due_label(...),
    }
```
Backend **CÓ** trả về `template` và `card_type`, nhưng các thông tin chính như `word`, `reading`, `meaning` là thuộc tính của `Note`.

### 3.2. Thiếu sót nghiêm trọng trên Giao diện Frontend ([`BrowseCardTable.tsx`](file:///d:/Project/nihongo/frontend/src/features/browse/components/BrowseCardTable.tsx))

Giao diện bảng hiện tại định nghĩa các cột:
```tsx
<TableHeader>
  <TableRow>
    <TableHead><Checkbox /></TableHead>
    <TableHead>Word</TableHead>
    <TableHead>Reading</TableHead>
    <TableHead>Meaning</TableHead>
    <TableHead>Status</TableHead>
    <TableHead>Due</TableHead>
  </TableRow>
</TableHeader>
```
Và render từng hàng:
```tsx
cards.map((card) => (
  <TableRow key={card.card_id}>
    <TableCell><Checkbox /></TableCell>
    <TableCell>{card.word}</TableCell>
    <TableCell>{card.reading}</TableCell>
    <TableCell>{card.meaning}</TableCell>
    <TableCell><Badge>{statusLabel(card.status)}</Badge></TableCell>
    <TableCell>{card.due_label}</TableCell>
  </TableRow>
))
```

**Sai lầm kiến trúc giao diện:**
1. **Hoàn toàn bỏ qua trường `card.template`**: Người dùng không thể biết hàng thứ nhất là bài "Gõ nghĩa", hàng thứ hai là "Gõ cách đọc", hàng thứ ba là "Flashcard".
2. **Không có chế độ phân định "Duyệt theo Note" vs "Duyệt theo Card"**:
   - Khi người dùng muốn xem từ vựng để tra cứu/sửa từ vựng: họ cần chế độ **Duyệt theo Note (Notes Mode)** — 1 từ vựng = 1 dòng duy nhất.
   - Khi người dùng muốn xem tiến độ ôn tập SRS của từng dạng bài tập: họ cần chế độ **Duyệt theo Card (Cards Mode)** — mỗi dạng bài = 1 dòng, nhưng **bắt buộc phải có cột Template** để người dùng biết thẻ này là thẻ gì.
3. **Pane biên tập bên phải ghi "Chi tiết Note"**:
   - Thực chất form bên phải đang sửa dữ liệu bảng `notes`. Khi bấm vào Card 1, Card 2, hay Card 3, bên phải đều hiện cùng 1 Note `本論`. Nếu sửa trường `Word` ở Card 1 và Lưu, cả 3 Card đều đổi theo. Điều này càng làm người dùng hoang mang vì tưởng rằng DB có 3 bản sao chép lặp.

---

## 4. Đề xuất Giải pháp Kiến trúc Chuẩn (Không vá víu "if-else")

Để xử lý tận gốc vấn đề theo chuẩn kiến trúc Flashcard quốc tế (tương tự Anki và RemNote), hệ thống cần triển khai giải pháp chuẩn gồm 2 giai đoạn:

### Giai đoạn 1: Bổ sung định danh Thẻ trên giao diện Chế độ Card (Zero-loss Immediate Fix)
1. **Bổ sung cột "Dạng thẻ" (Template / Card Type) vào [`BrowseCardTable.tsx`](file:///d:/Project/nihongo/frontend/src/features/browse/components/BrowseCardTable.tsx)**:
   - Hiển thị rõ tên template bằng Badge tinh gọn, ví dụ:
     - `本論` — `Default Flashcard`
     - `本論` — `Gõ cách đọc`
     - `本論` — `Gõ nghĩa`
   - Giúp người học lập tức hiểu được tại sao có 3 dòng: đây là 3 dạng bài tập khác nhau của cùng 1 từ vựng, mỗi dòng có tiến độ học SRS riêng (`Đang học`, `Chưa học`, `Hạn ôn`).
2. **Cập nhật Pane bên phải ([`BrowseCardEditor.tsx`](file:///d:/Project/nihongo/frontend/src/features/browse/components/BrowseCardEditor.tsx))**:
   - Header hiển thị rõ: `Chi tiết Thẻ: [Tên Template]` kèm liên kết `Thuộc Note: [Tên từ vựng]`.
   - Hiển thị tab hoặc thông tin chuyển đổi giữa các Thẻ (Cards) của cùng một Note.

### Giai đoạn 2: Bổ sung Chế độ Chuyển đổi "Duyệt theo Note" vs "Duyệt theo Thẻ" (Notes Mode vs Cards Mode)
1. **Thiết kế công tắc chuyển chế độ (View Mode Toggle)** trên Toolbar:
   - **Chế độ Bản ghi (Notes View - Mặc định cho tra cứu từ vựng)**:
     - API hỗ trợ query theo `Note-grain` (Group by `note_id` hoặc endpoint `/browse/notes`), mỗi Note chỉ hiển thị duy nhất **1 dòng**.
     - Cột trạng thái hiển thị trạng thái tổng hợp của Note.
     - Số lượng dòng hiển thị đúng bằng số từ vựng trong bài (Bài 001 hiển thị đúng 60 dòng).
   - **Chế độ Thẻ (Cards View - Dành cho quản lý tiến độ SRS chuyên sâu)**:
     - Hiển thị chi tiết từng Card cho từng Template (180 dòng).
     - Cho phép tạm hoãn (Suspend), đặt lại tiến độ (Reset SRS) riêng cho từng dạng bài tập.

---

## 5. Bảng tổng hợp đối soát dữ liệu

| Tiêu chí đối soát | Database Local | Database Production | Ghi chú |
| :--- | :--- | :--- | :--- |
| Số bản ghi Note cho từ `本論` ở `Bài 001` | **1 Note** | **1 Note** | Không duplicate trong DB |
| Tổng số Note trong deck `Bài 001` | **60 Notes** | **60 Notes** | Không duplicate trong DB |
| Số StudyApplication của NoteType `Flama Standard Vocabulary` | **1 Template** | **3 Templates** | Prod gắn thêm 2 template ngày 11/10 |
| Số Card sinh ra từ `Bài 001` | **60 Cards** | **180 Cards** | $60 \text{ Notes} \times 3 \text{ Templates}$ |
| Cột Template trên bảng Browse Frontend | **Không có** | **Không có** | Gây ra hiện tượng nhìn như lặp |
| Nguyên nhân lỗi | **Kiến trúc UI / View Mode** | **Kiến trúc UI / View Mode** | Không phải do lỗi dữ liệu DB |
