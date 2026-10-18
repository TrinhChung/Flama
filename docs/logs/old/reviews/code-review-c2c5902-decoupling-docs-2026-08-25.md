# Code Review — Commit `c2c5902` "decoupling alogrithm"

> Ngày review: 2026-08-25
> Người review: Claude Code (Sonnet 5) — high effort, 8 finder angles + verify pass
> Phạm vi: toàn bộ diff của commit `c2c5902d6ad7b1adf0b3d47be33eee8abf2d551a` trên `develop`
> Trạng thái các phát hiện: **CHƯA SỬA** (tính đến ngày review)

---

## 1. Tổng quan commit

Commit gần như **thuần tài liệu + agent skill mới**, không đụng code runtime:

| Nhóm | File |
|---|---|
| Cấu hình | `.gitignore` (thêm exception `!skills/flama-database-architecture/`), `AGENTS.md` (đăng ký skill mới) |
| Index docs | `docs/README.md` (thêm mục 5 — Agent Skills) |
| Tài liệu kiến trúc | `docs/architecture/database-architecture-investigation.md` (689 dòng), `post-decoupling-system-recommendations.md` (104), `production-architecture-verification-2026-08-24.md` (346), `study-interaction-trigger-algorithm-plan.md` (1373), `template-notetype-decoupling-investigation.md` (804) |
| Skill (bản tiếng Việt) | `docs/skills/DATABASE_ARCHITECTURE.md` (189) |
| Skill (bản tiếng Anh) | `skills/flama-database-architecture/SKILL.md` (246) + `agents/openai.yaml` + 3 file `references/` |

**Đánh giá chung: chất lượng rất tốt.** Các tài liệu điều tra được ground bằng trích dẫn `file:line` cụ thể, và phần lớn đã được đối chiếu trực tiếp với code — đều khớp chính xác (xem mục 3).

---

## 2. Các phát hiện (6)

### 2.1 ⚠️ [CONFIRMED — correctness] SKILL.md bịa tên class không tồn tại `ConnectSourceNoteTypeRef`

- **Vị trí:** `skills/flama-database-architecture/SKILL.md:144`
- **Observed:** Danh sách "External Identity Bridges" liệt kê `ConnectSourceNoteTypeRef`, nhưng class thực tế là **`ConnectNoteTypeRef`** (`models/connect_note_type_ref.py:9`). Chính `docs/architecture/database-architecture-investigation.md:508` dùng đúng tên `ConnectNoteTypeRef` → hai tài liệu trong cùng commit mâu thuẫn nhau.
- **Impact:** Agent theo skill sẽ grep `ConnectSourceNoteTypeRef`, không thấy gì, và có thể kết luận sai rằng bridge NoteType chưa tồn tại — vi phạm đúng nguyên tắc "No Fabricated Relations" mà chính skill này đặt ra.
- **Đề xuất sửa:** đổi thành `ConnectNoteTypeRef` (kiểm tra thêm cả bản tiếng Việt và `flama_entity_landscape.md` — bản landscape đang dùng đúng tên).

### 2.2 ⚠️ [CONFIRMED — correctness] Link chết `file:///d:/Project/nihongo/...` trong doc recommendations

- **Vị trí:** `docs/architecture/post-decoupling-system-recommendations.md:62`
- **Observed:** Link tới `vocabulary.py` dùng URI tuyệt đối `file:///d:/Project/nihongo/app/routes/vocabulary.py` — trỏ tới checkout trên **máy của người viết**, không phải repo này. File thật nằm tại `app/routes/vocabulary.py` (948 dòng, tồn tại trong repo).
- **Impact:** Link hỏng với mọi người đọc (GitHub UI, contributor khác, agent); đồng thời lộ cấu trúc thư mục máy cá nhân (`d:/Project/nihongo`).
- **Đề xuất sửa:** đổi thành link tương đối `../../app/routes/vocabulary.py` hoặc chỉ ghi path dạng code.

### 2.3 ⚠️ [CONFIRMED — correctness] Đánh số đề xuất mâu thuẫn giữa các mục trong cùng doc

- **Vị trí:** `docs/architecture/post-decoupling-system-recommendations.md` (mục 1–2 vs mục 3, dòng ~93)
- **Observed:**
  - Mindmap (mục 1) và "Đề xuất 1–5" (mục 2): 1=Search Engine, 2=FSRS Optimizer, 3=Phân rã vocabulary.py, 4=Session Revocation, 5=Offline-First.
  - Ma trận đánh giá (mục 3): 1=Phân rã vocabulary.py, 2=Session Revocation, 3=FSRS, 4=Offline, 5=Search.
- **Impact:** Nói "kích hoạt Đề xuất 2" sẽ ra **FSRS** theo mục 2 nhưng **Session Revocation** theo mục 3 — tham chiếu bằng số trong doc bị nhập nhằng.
- **Đề xuất sửa:** thống nhất một thứ tự đánh số cho cả 3 mục.

### 2.4 ⚠️ [CONFIRMED — correctness] Evidence hierarchy ghi `cli.py` — path thật là `app/cli.py`

- **Vị trí:** `skills/flama-database-architecture/SKILL.md:71`
- **Observed:** Bậc 9 của evidence hierarchy ghi "`app/startup.py, cli.py`" nhưng repo **không có `cli.py` ở root** — file thật là `app/cli.py`. Bản tiếng Việt (`docs/skills/DATABASE_ARCHITECTURE.md:53`) ghi đúng.
- **Impact:** Agent tìm `cli.py` ở root sẽ không thấy và bỏ qua tầng bằng chứng maintenance/cutover.
- **Đề xuất sửa:** đổi thành `app/cli.py`.

### 2.5 ⚠️ [CONFIRMED — reuse/duplication] Skill bị duplicate ở 2 file, đã bắt đầu drift

- **Vị trí:** `skills/flama-database-architecture/SKILL.md` (EN) vs `docs/skills/DATABASE_ARCHITECTURE.md` (VI)
- **Observed:** Hai file duy trì song song cùng nội dung (modes, evidence hierarchy, 10-step lens, entity map, migration playbook) mà **không có ghi chú file nào là nguồn chuẩn**. Drift đã xuất hiện: `cli.py` vs `app/cli.py`, danh sách trigger keyword DESIGN mode khác nhau, entity list khác nhau nhẹ.
- **Impact:** Mỗi lần sửa skill phải sửa 2 chỗ; quên một chỗ là hai bản lệch nhau âm thầm.
- **Đề xuất sửa:** chọn 1 file làm source of truth (khuyến nghị `SKILL.md` vì agent load trực tiếp), file kia chỉ giữ tóm tắt + link; hoặc thêm banner "bản dịch tham khảo — nguồn chuẩn là SKILL.md" vào bản tiếng Việt.

### 2.6 ⚡ [PLAUSIBLE — security-hygiene] Chi tiết hạ tầng production nằm trong repo

- **Vị trí:** `docs/architecture/production-architecture-verification-2026-08-24.md:13` và mục 3
- **Observed:** Doc ghi SSH alias `chung_hostinger_vps` (lộ nhà cung cấp hosting), tên service (`flama.service`, `flama-connect.service`), port nội bộ 4789/4790, đường dẫn deploy `/opt/flama/current`, hash release đang chạy. **Không có credential nào bị lộ.**
- **Impact:** Repo hiện có vẻ private (GitHub API trả 404 khi truy vấn ẩn danh) nên rủi ro đang ở mức tiềm ẩn. Nhưng nếu sau này repo được public (ví dụ mở marketplace) thì đây là bản đồ hạ tầng miễn phí cho attacker.
- **Đề xuất:** cân nhắc redact alias/provider, hoặc chuyển doc này ra ngoài repo / vào private notes. Ít nhất nên ghi chú vào checklist "trước khi public repo".

---

## 3. Những gì đã kiểm chứng và ĐÚNG (không phải finding)

Để lần sau đọc lại đỡ nghi ngờ, các claim sau đã được đối chiếu trực tiếp với code và **khớp chính xác**:

- `uq_cards_note_template` trên `(note_id, template_id)` — `models/card.py:23`
- `uq_field_defs_note_type_name` + `uq_field_defs_note_type_identity_role` — `models/field_def.py:38-39`
- `uq_media_assets_note_sha_field` `(note_id, sha256, field_name)` — `models/media_asset.py:25`
- `uq_card_progress_user_card` + các cột `due_day`, `interval_days_raw`, `memory_stability`, `revision` — `models/card_progress.py`
- `ReviewEvent` không có FK tới `deck_id`/`note_type_id` (cột plain, nullable) — `models/review_event.py:12-13`
- `DeckInstall.clone_mode` default `"logical_overlay"`, `overlay_revision` BigInteger — `models/deck_install.py:27,67`
- Phân bố UUID vs Integer ID đúng như bảng trong SKILL.md (Note/Card/FieldDef/NoteType/Release/Install/Media = UUID; Deck/User/Progress/Preset = Integer)
- Các trích dẫn `file:line` trong `study-interaction-trigger-algorithm-plan.md` và `template-notetype-decoupling-investigation.md` (spot-check ~10 điểm: `models/template.py:7-22`, `models/card.py:9-24`, `_create_cards` tại `flashcard_content_service.py:1291-1298`, `StudySessionEvent` tại `frontend/src/features/study/types.ts:150-158`, hằng số session tại `study_session_service.py:54-68`, v.v.) — tất cả khớp
- Toàn bộ ~50 entity trong `references/flama_entity_landscape.md` đều tồn tại trong `models/`
- Các anchor link `references/architectural_checklists.md#...` trong SKILL.md đều resolve đúng heading
- Link `docs/README.md` → `BRANCH_STRATEGY.md` hợp lệ (file đã tồn tại từ commit `001c356`)
- Pattern `.gitignore` (`skills/*` + `!skills/flama-database-architecture/`) hoạt động đúng

## 4. Ghi chú

- Lỗi chính tả trong commit message: "alogrithm" → "algorithm" (không sửa được nữa, chỉ ghi nhận).
- Diff thêm vài dòng trắng thừa cuối `AGENTS.md` và `.gitignore` — quá nhỏ, không tính finding.
