# Skill — Flama Database Architecture

Tài liệu này là cẩm nang hướng dẫn điều tra, phân tích và tiến hóa kiến trúc cơ sở dữ liệu MySQL cho các AI Coding Agent (**Antigravity**, **Codex**, **Tri**, **San**, v.v.) khi làm việc trong repository Flama.

---

## 🎯 Mục đích & Triết lý Cốt lõi

Flama là hệ thống học ngôn ngữ theo mô hình OLTP dựa trên **MySQL 8.0** và **SQLAlchemy / Flask-Migrate**. Cơ sở dữ liệu bao gồm các phân hệ: quản lý note, template thẻ tùy biến, thuật toán lặp lại ngắt quãng (Spaced Repetition), marketplace chia sẻ và cài đặt deck theo mô hình clone overlay, và cầu nối đồng bộ ngoại vi (Flama Connect, AnkiConnect, Yomitan, MCP).

### 3 Nguyên tắc Bắt buộc:
1. **Follow the Data, Not the Code**: Tập trung vào dữ liệu tĩnh (tables, columns, types, constraints, ownership) và dữ liệu động (dataflow, lineage, sync streams, rebase, replay). Các class Service/Repository chỉ là bằng chứng thể hiện luồng đọc/ghi.
2. **Tách Biệt Tuyệt Đối Giữa Điều Tra (INVESTIGATE) và Thiết Kế (DESIGN)**: Một yêu cầu điều tra, giải thích, audit hoặc trace luồng **KHÔNG BAO GIỜ** được tự ý biến thành một đề xuất viết lại schema hay sửa đổi code.
3. **Căn Cứ Bằng Chứng (Evidence-Grounded)**: Mọi kết luận phải dựa trên bằng chứng cụ thể trong repository theo thứ bậc tin cậy. Không suy diễn hoặc bịa đặt Foreign Key / Invariant khi code không có.

---

## 🧭 Hai Chế Độ Hoạt Động (Modes of Operation)

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│ INVESTIGATE Mode (Mặc định khi điều tra / phân tích)                               │
│ Từ khóa kích hoạt: "investigate", "review", "audit", "trace", "explain", "check"   │
│ Đầu ra: Schema thực tế, bằng chứng, hệ thống ghi nhận, rủi ro, điểm chưa rõ.      │
│ NGHIÊM CẤM: Không tự ý sửa code, không đổi migration, không đề xuất schema mới.   │
└───────────────────────────────────────────────────────────────────────────────────┘
                                         │
                       (Người dùng yêu cầu thiết kế / refactor)
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│ DESIGN Mode (Chỉ kích hoạt khi có yêu cầu thiết kế rõ ràng)                       │
│ Từ khóa kích hoạt: "design", "refactor", "propose schema", "migrate", "evolve"    │
│ Đầu ra: Invariants, target schema, phân tích trade-offs MySQL, kế hoạch migration.│
│ BẮT BUỘC: Dựa trên điều tra đã xác thực, cam kết không mất dữ liệu (Zero Data Loss) │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Thứ Bậc Bằng Chứng (Evidence Hierarchy)

Khi xác minh sự thật về schema và dữ liệu, hãy tuân thủ thứ tự ưu tiên:

```
1. Database Migrations (migrations/versions/*.py)         [Chân lý schema cao nhất]
2. Database Models (models/*.py)                          [Khai báo ánh xạ ORM]
3. Table Constraints (__table_args__, PK, FK, Unique)     [Ràng buộc quan hệ thực tế]
4. Repository/Service Writes (db.session.add/commit)      [Nơi thực hiện ghi dữ liệu]
5. Repository/Service Reads (queries, joined loads)       [Mẫu truy vấn & tiêu thụ]
6. API Handlers & Validators (app/api/*, app/validators/*)[Hợp đồng dữ liệu I/O]
7. Test Assertions (tests/test_*.py)                      [Kỳ vọng vận hành thực tế]
8. External Sync & Imports (Connect, Yomitan, Anki)       [Ánh xạ dữ liệu ngoại vi]
9. Maintenance & CLI (app/startup.py, app/cli.py)         [Vá lỗi, seed, cutover]
10. Frontend Client State (frontend/src/*)                [Giao diện tiêu thụ]
11. Documentation (docs/*, AGENTS.md, docstrings)         [Ý định thiết kế; cần đối chiếu code]
```

---

## 🔍 Trình Tự Đánh Giá Schema (10-Step Lens)

Khi thẩm định bất kỳ phân hệ dữ liệu nào trong Flama, luôn đi theo thứ tự ưu tiên từ cốt lõi đến kỹ thuật:

```
1. Định danh thực thể (Entity Identity)  -> UUID vs Integer vs Name vs External Key?
2. Quyền sở hữu (Ownership)              -> User, Deck, NoteType hay Session sở hữu? Cascade ra sao?
3. Quan hệ (Relationships)              -> 1:1, 1:N, N:M? Foreign Key rõ ràng hay ngầm định?
4. Nguồn chân lý (Source of Truth)       -> Bảng nào là gốc? Đâu là snapshot, cache, overlay delta?
5. Ràng buộc bất biến (Invariants)       -> Ràng buộc nghiệp vụ nào bắt buộc giữ vững?
6. Vòng đời dữ liệu (Lifecycle)          -> Tạo, sửa, đồng bộ, rebase, release, xóa mềm, dọn dẹp?
7. Tính mở rộng (Extensibility)          -> Thêm loại tương tác, thuật toán mới có cần đổi DDL không?
8. Tính tương thích (Compatibility)      -> Tương thích ngược với clone overlay và external sync?
9. An toàn chuyển đổi (Migration Safety) -> Có thể chuyển đổi an toàn không downtime, không mất data?
10. Chỉ mục & Hiệu năng (Indexes/Access) -> Composite indexes cho hot paths (chỉ xét khi ảnh hưởng thiết kế).
```

---

## 🗂️ Bản Đồ 10 Cụm Thực Thể Flama (Domain Entity Landscape)

### 1. Nội dung Flashcard & Schema (`models/`)
- **`NoteType`** (`note_types`): Khung định nghĩa schema (chứa FieldDefs, Templates) + Gốc xuất bản Marketplace. Unique `(user_id, name)`.
- **`FieldDef`** (`field_defs`): Định nghĩa trường dữ liệu ổn định với `id` (UUID). Unique `(note_type_id, name)` và `(note_type_id, identity_role)`.
- **`Template`** (`templates`): Mẫu hiển thị mặt trước/sau (`front_html`, `back_html`, `shared_css`). Chứa placeholder Mustache tham chiếu theo tên trường (`{{Word}}`).
- **`Note`** (`notes`): Bản ghi nội dung gốc của người dùng. Chứa `field_values` (JSON dict ánh xạ tên trường $\rightarrow$ giá trị).
- **`Card`** (`cards`): Hình chiếu (projection) xác định 1:1 giữa `(note_id, template_id)`. Ràng buộc bởi `uq_cards_note_template`.
- **`MediaAsset`** (`media_assets`): File ảnh/âm thanh vật lý gắn với Note. Unique `(note_id, sha256, field_name)`.
- **`FieldRenameJob`** (`field_rename_jobs`): Nhật ký tiến độ ghi lại quá trình sửa key trong `notes.field_values` khi đổi tên trường.

### 2. Cây Thư Mục & Tổ Chức Deck
- **`Deck`** (`decks`): Cây thư mục cha-con (`parent_id`). Có thể gắn `note_type_id` mặc định và `scheduler_preset_id`.

### 3. Scheduler & Tiến Độ Học Tập (Spaced Repetition)
- **`CardProgress`** (`card_progress`): Trạng thái học tập của từng user trên từng card (`queue`, `due_at`, `due_day`, `interval_days`, `ease_factor`, `memory_stability`, `memory_difficulty`, `revision`). Unique `(user_id, card_id)`.
- **`SchedulerPreset`** (`scheduler_presets`): Bộ cấu hình tham số thuật toán (Legacy SM-2, FSRS parameters). Unique `(user_id, name)`.
- **`UserSchedulerSettings`** (`user_scheduler_settings`): Cấu hình chung của user (`scheduler_mode`, giờ qua ngày, thời gian học trước).
- **`ReviewEvent`** (`review_events`): Sự kiện đánh giá học tập bất biến (analytics fact). Ghi lại trạng thái trước/sau và `payload_json`. **Cố tình không đặt FK** tới `deck_id` và `note_type_id` để cho phép xóa deck/notetype mà không mất lịch sử thống kê.
- **`StudySession`** / **`StudySessionCard`** / **`StudySessionCommit`**: Phiên học nhóm (batch session) với frozen config hash, snapshot tiến độ ban đầu, xác thực replay trên server và biên lai commit chống trùng lặp (idempotent).

### 4. Marketplace, Release & Clone Overlay
- **`DeckMarketplaceItem`** (`deck_marketplace_items`): Bản ghi phát hành deck lên chợ chia sẻ. Unique `source_deck_id`.
- **`DeckRelease`** (`deck_releases`): Node phiên bản phát hành bất biến (DAG sequence) với `manifest_hash`.
- **`DeckReleaseChange`** (`deck_release_changes`): Delta thay đổi nguyên tử đa hình `(entity_kind, entity_id, field_def_id, property_key)`.
- **`DeckReleaseNoteCheckpoint`** (`deck_release_note_checkpoints`): Snapshot nội dung note tại một mốc release.
- **`DeckInstall`** (`deck_installs`): Bản ghi cài đặt deck theo **mô hình Pointer/Overlay** (`clone_mode="logical_overlay"`). Không copy Note/Card gốc.
- **`DeckCloneDeckMap`** (`deck_clone_deck_maps`): Ánh xạ cây thư mục deck nguồn sang cây deck của người cài.
- **`DeckCloneNoteFieldOverride`** (`deck_clone_note_field_overrides`): Ghi đè giá trị từng trường của note nguồn. Ràng buộc kép trên `source_field_def_id` và `field_name`.
- **`DeckCloneAddedNote`** / **`DeckCloneAddedFieldDef`**: Note hoặc Field riêng do người cài tự bổ sung vào deck cài đặt.
- **`DeckInstallRebase`** (`deck_install_rebases`): Quá trình 3-way merge `(base_release, target_release, local_overlay)` khi cập nhật bản mới từ tác giả.
- **`DeckChangeRequest`** (`deck_change_requests`): Đề xuất đóng góp chỉnh sửa từ người cài gửi ngược lại cho tác giả deck gốc.

### 5. Flama Connect & Đồng Bộ Ngoại Vi
- **`ConnectSourceDeckRef`** / **`ConnectSourceNoteRef`** / **`ConnectSourceCardRef`**: Bảng ánh xạ định danh ngoại vi (Anki, Yomitan) với thực thể Flama nội bộ.
- **`ConnectPendingMedia`** / **`ConnectImportMedia`**: Khu vực lưu tạm (staging) file âm thanh/hình ảnh trước khi materialize thành `MediaAsset`.

---

## 📋 Bộ Checklist Kiểm Tra Kiến Trúc Trọng Điểm

### 1. Kiến trúc Trường Dữ liệu (Field Architecture)
- [ ] Định danh trường là `FieldDef.id` (UUID) hay `FieldDef.name` (String)?
- [ ] Khi đổi tên trường, `notes.field_values` được migrate ra sao? Placeholder `{{Field}}` trong Template và `MediaAsset.field_name` có bị đứt gãy không?
- [ ] Bảng `DeckCloneNoteFieldOverride` có duy trì đồng thời `source_field_def_id` và `field_name` để tương thích không?

### 2. Tách lớp NoteType / Note / Template / Card
- [ ] `Note` có bị rò rỉ mã HTML giao diện hoặc tiến độ học tập vào trong không?
- [ ] `Card` có đảm bảo là hình chiếu thuần túy 1:1 của `(Note, Template)` không?
- [ ] Các loại bài tập mới (trắc nghiệm, nối từ, gõ chữ, nghe phát âm) có thể biểu diễn qua Template sandbox mà không cần đẻ thêm bảng quan hệ cứng không?

### 3. Scheduler & Spaced Repetition
- [ ] Trạng thái học tập chung (`queue`, `due_day`, `interval_days`) có tách bạch với tham số riêng của thuật toán (`ease_factor` của SM-2, `memory_stability` của FSRS) không?
- [ ] `ReviewEvent` có bảo toàn tính bất biến (append-only fact) và hỗ trợ xóa Deck mà không mất log không?

### 4. Marketplace & Clone Overlay
- [ ] Cài đặt deck có đảm bảo **chỉ tạo overlay** mà tuyệt đối không nhân bản (copy) dữ liệu `notes`/`cards` gốc không?
- [ ] Cập nhật rebase 3 chiều có xử lý xung đột chính xác giữa thay đổi của tác giả và ghi đè của người học không?

---

## 🚀 Cẩm Nang Migration MySQL 5 Pha (Zero-Downtime Playbook)

Khi cần refactor schema trong **DESIGN** mode, bắt buộc thiết kế theo quy trình 5 pha:

```
Pha 1: EXPAND (Mở rộng)
├── Tạo bảng mới hoặc thêm cột mới dưới dạng nullable=True qua Alembic.
└── Triển khai code hỗ trợ ghi kép (Dual-Write) vào cả cấu trúc cũ và mới.
      │
Pha 2: BACKFILL (Nạp bù dữ liệu)
├── Chạy CLI batch script nạp dữ liệu cũ sang cấu trúc mới theo từng lô nhỏ.
└── Xác minh tính toàn vẹn 100% giữa dữ liệu cũ và mới.
      │
Pha 3: DUAL-READ & VALIDATE (Đọc kép & Thẩm định)
├── Triển khai code ưu tiên đọc cấu trúc mới, fallback về cấu trúc cũ nếu thiếu.
└── Đánh giá hiệu năng truy vấn và kiểm thử hồi quy.
      │
Pha 4: CUTOVER (Chuyển đổi chính thức)
├── Chuyển toàn bộ luồng đọc và ghi sang cấu trúc mới.
└── Ngừng ghi/đọc cấu trúc cũ.
      │
Pha 5: CONTRACT (Thu hẹp & Dọn dẹp)
├── Tạo migration Alembic drop cột/bảng cũ đã deprecated.
└── Dọn dẹp code fallback và logic tương thích cũ.
```

---

## 📝 Định Dạng Báo Cáo Chuẩn

Khi hoàn thành điều tra hoặc thiết kế, xuất kết quả ra tài liệu trong `docs/architecture/`:
- Điều tra: `docs/architecture/database-architecture-investigation.md`
- Thiết kế: `docs/architecture/database-architecture-design.md`

### Mẫu Trình Bày Mỗi Phát Hiện (Finding Format):
```markdown
### [Tiêu đề phát hiện: Ví dụ: Đổi tên trường chưa cập nhật Template placeholder]

- **Observed**: [Hành vi thực tế quan sát được trong mã nguồn]
- **Evidence**: [Đường dẫn file, tên class model, migration, hoặc tên test cụ thể]
- **Potential concern**: [Rủi ro kiến trúc, nguy cơ xung đột, hoặc vi phạm ranh giới thực thể]
- **Impact**: [Tác động khi xảy ra lỗi: mất dữ liệu, cache hỏng, lỗi sync, chặn migration]
- **Unknowns**: [Điểm chưa thể khẳng định từ repo: phân bổ data thực tế trên production, v.v.]

<!-- CHỈ THÊM PHẦN DƯỚI TRONG CHẾ ĐỘ DESIGN MODE -->
- **Alternatives Considered**: [Các phương án kiến trúc thay thế đã cân nhắc]
- **Trade-offs**: [Đánh giá được/mất về dung lượng MySQL, độ phức tạp, locking]
- **Recommendation**: [Đề xuất kiến trúc tối ưu nhất kèm lý do]
- **Migration Implications**: [Kế hoạch migration tương thích ngược không gián đoạn]
```
