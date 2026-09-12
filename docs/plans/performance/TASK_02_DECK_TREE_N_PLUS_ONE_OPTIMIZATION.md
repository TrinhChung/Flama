# Kế hoạch Tối ưu #02: Khắc phục Triệt để N+1 Query tại Cây Thư mục Deck Browse

> **Mã Task:** `PERF-TREE-02`  
> **Mức độ ưu tiên:** 🟠 P1 (High - Ảnh hưởng trực tiếp độ trễ trang Browse cho mọi người dùng)  
> **Trạng thái:** DỰ THẢO CHỜ DUYỆT (PROPOSED)  
> **Phạm vi tác động:** Repository Vocabulary (`vocabulary_repository.py`), API v1 Decks Tree (`browse_bp.get("/decks/tree")`)  
> **Tài liệu tham chiếu:** [`app/repositories/vocabulary_repository.py`](file:///d:/Project/nihongo/app/repositories/vocabulary_repository.py#L612-L800), [`app/services/browse_card_service.py`](file:///d:/Project/nihongo/app/services/browse_card_service.py#L150-L195)

---

## 1. Vấn đề Kỹ thuật Cần Giải quyết

### 1.1 Hiện trạng mã nguồn
Tại [`app/repositories/vocabulary_repository.py`](file:///d:/Project/nihongo/app/repositories/vocabulary_repository.py#L708-L797), hàm `build_browse_deck_tree_payload` tính toán số lượng thẻ (`total`, `new`, `learn`, `due`) cho toàn bộ cây thư mục bộ thẻ của người dùng.

Với các bộ thẻ Marketplace đã cài đặt (`DeckInstall`), mã nguồn đang duyệt qua từng install:
```python
# vocabulary_repository.py:708-760
for install in logical_installs:
    # 1. Query n+1: Tìm ánh xạ deck con
    map_rows = DeckCloneDeckMap.query.filter_by(deck_install_id=install.id).all()
    
    # 2. Query n+1: Thực hiện câu aggregation nặng
    clone_counts_query = (
        db.session.query(
            Note.deck_id,
            db.func.count(Card.id).label("total"),
            db.func.sum(db.case((is_new, 1), else_=0)).label("new"),
            db.func.sum(db.case((is_learn, 1), else_=0)).label("learn"),
            db.func.sum(db.case((is_due_review, 1), else_=0)).label("due"),
        )
        .select_from(Card)
        .join(Note, Card.note_id == Note.id)
        .outerjoin(progress_alias, progress_join)
        .filter(Note.deck_id.in_(source_to_local.keys()))
        .group_by(Note.deck_id)
    )
```

Đặc biệt, tại dòng 780:
```python
# vocabulary_repository.py:779-797 (VÒNG LẶP TRÙNG LẶP)
if logical_installs:
    for install in logical_installs:
        map_rows = DeckCloneDeckMap.query.filter_by(deck_install_id=install.id).all()
        # Duyệt lại lần thứ 2 chỉ để lấy source_note_type_id!
```

### 1.2 Điểm nghẽn
1. **Lỗi N+1 kép:** Mỗi `DeckInstall` bắn thêm 2 câu SQL riêng biệt (1 câu lấy `DeckCloneDeckMap` và 1 câu `GROUP BY` join 3 bảng `Card` + `Note` + `CardProgress`).
2. **Vòng lặp thừa (Duplicate Loop):** Vòng lặp thứ hai quét lại toàn bộ `DeckCloneDeckMap` một lần nữa cho từng install.
3. **Độ trễ tăng tuyến tính theo số Deck cài đặt:** Người dùng cài càng nhiều bộ thẻ từ Marketplace, trang Browse càng mở chậm. Với 15 bộ thẻ đã cài, tổng số query lên tới **46 câu lệnh SQL** cho một lần load Sidebar!

---

## 2. Giải pháp Kỹ thuật (Technical Mechanism)

Chuyển đổi hoàn toàn từ $O(M)$ câu lệnh truy vấn sang $O(1)$ câu lệnh gộp (Batch Fetching & Python In-memory Rollup):

```text
TRƯỚC KHI TỐI ƯU (N+1 Queries):
[Install 1] ──► SELECT DeckCloneDeckMap ──► SELECT SUM(...) GROUP BY Note.deck_id
[Install 2] ──► SELECT DeckCloneDeckMap ──► SELECT SUM(...) GROUP BY Note.deck_id
...
[Install M] ──► SELECT DeckCloneDeckMap ──► SELECT SUM(...) GROUP BY Note.deck_id
[Install 1..M Lặp lại] ──► SELECT DeckCloneDeckMap (Lặp thừa)
==> Tổng cộng: 1 (gốc) + 2M + M = 1 + 3M queries

SAU KHI TỐI ƯU (Batch Aggregation - O(1)):
1. SELECT * FROM deck_clone_deck_maps WHERE deck_install_id IN (:all_install_ids)
2. SELECT Note.deck_id, COUNT(Card.id), SUM(is_new), SUM(is_learn), SUM(is_due)
   FROM cards JOIN notes LEFT JOIN card_progress
   WHERE (:disjunction_of_install_conditions)
   GROUP BY Note.deck_id
3. Phân bổ kết quả vào local_deck_id bằng Dictionary trong RAM Python (< 1ms)
==> Tổng cộng: 1 (gốc) + 1 (batch map) + 1 (batch count) = ĐÚNG 3 QUERIES CỐ ĐỊNH!
```

### Chi tiết thay đổi mã nguồn
1. **Gộp lấy Map (Dùng UUID String & Invariant Overlap Guard):**
   ```python
   install_ids = [str(inst.id) for inst in logical_installs if inst.id is not None]
   all_maps = (
       DeckCloneDeckMap.query.filter(DeckCloneDeckMap.deck_install_id.in_(install_ids))
       .all()  # Bỏ .order_by() để tránh filesort không cần thiết
   )
   
   # Nhóm map theo deck_install_id (UUID String) và bảo vệ bằng Invariant Overlap Guard
   maps_by_install: dict[str, dict[int, int]] = defaultdict(dict)
   source_to_install: dict[int, str] = {}
   has_overlap = False

   for row in all_maps:
       if (
           row.deck_install_id
           and row.source_deck_id is not None
           and row.local_deck_id is not None
           and int(row.local_deck_id) in scoped_ids
       ):
           sid = int(row.source_deck_id)
           lid = int(row.local_deck_id)
           iid = str(row.deck_install_id)

           # Overlap guard
           prev_iid = source_to_install.get(sid)
           if prev_iid is not None and prev_iid != iid:
               has_overlap = True
               continue

           source_to_install[sid] = iid
           maps_by_install[iid][sid] = lid
   ```
2. **Gộp Aggregate Count (Bảo lưu Snapshot Semantics):**
   - Tạo disjunction `db.or_(*install_conditions)` dựa trên các điều kiện của từng install (source_deck_ids, source_owner_user_id, base_snapshot_at/installed_at).
   - Nếu phát hiện `has_overlap == True` (dữ liệu legacy bất thường), fallback an toàn về vòng lặp per-install để bảo toàn 100% độ chính xác.
3. **Loại bỏ triệt để vòng lặp dòng 779-797:**
   - Tận dụng `maps_by_install` đã có sẵn trong bộ nhớ, không truy vấn lại DB.
4. **Lưu ý kiến trúc Decoupling & Tách Task #2B:**
   - Task #2 này thuần túy tối ưu hiệu năng và bảo lưu logic đếm theo snapshot hiện có.
   - Việc đồng bộ số đếm theo `release_note_membership_filter` (Release-Membership correctness) được bóc tách riêng thành Task #2B để tránh mở rộng phạm vi (scope creep).

---

## 3. Tính toán Định lượng Cụ thể (Quantitative Impact)

* Giả sử người dùng cài đặt $M = 15$ bộ Deck từ Marketplace:

| Tiêu chí đo lường | Trước khi tối ưu ($O(M)$) | Sau khi tối ưu ($O(1)$) | Mức độ cải thiện |
|---|---|---|:---:|
| **Số câu lệnh truy vấn MySQL** | $1 + 15 \times 3 = \mathbf{46\text{ queries}}$ | $\mathbf{3\text{ queries}}$ | **Giảm 93.5% số query** |
| **Độ trễ truyền mạng (Round-trip)** | $46 \times 3\text{ms} = \mathbf{138\text{ms}}$ | $3 \times 3\text{ms} = \mathbf{9\text{ms}}$ | **Giảm đáng kể latency** |
| **Tải CPU / Connection trên MySQL** | 46 lần parse câu lệnh SQL | 3 lần parse câu lệnh SQL | **Giảm tải MySQL** |

*Lưu ý: Thời gian xử lý API thực tế và kế hoạch thực thi sẽ được đo lường chính xác thông qua benchmark và EXPLAIN ANALYZE.*

---

## 4. Kế hoạch Triển khai (Checklist)

- [ ] **Repository:** Refactor hàm `build_browse_deck_tree_payload` trong [`app/repositories/vocabulary_repository.py`](file:///d:/Project/nihongo/app/repositories/vocabulary_repository.py).
- [ ] **Repository:** Loại bỏ vòng lặp `DeckCloneDeckMap` dư thừa thứ hai ở dòng 780.
- [ ] **Testing:** Chạy test suite `tests/test_deck_*.py` và `tests/test_flashcards_share.py` để đảm bảo số đếm thẻ (`total`, `new`, `learn`, `due`) khớp 100% không bị sai lệch dữ liệu.
- [ ] **Benchmark:** Đo đạc số lượng query thực tế trước và sau khi sửa.
