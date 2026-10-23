# TD-15 — Trích bộ máy chia sẻ thành adapter theo `entity_kind` và nâng cấp nền tảng

> Mức: **P1** · Đợt: W5 · Trạng thái: `TODO`
>
> Phụ thuộc: TD-14 (ADR) · Chặn: TD-16, TD-17, TD-18, TD-19 · Lane: Backend + Database (+ Frontend diff) · Ước lượng: 5–8 ngày
>
> Skill: `$flama-backend-architecture`, `$flama-database-architecture`, `$mysql`, `$flama-frontend-architecture`.

## Mục tiêu

Biến bộ máy chia sẻ của deck thành **engine chung + adapter theo `entity_kind`** mà **không đổi hành vi hiện tại**. Đồng thời nâng cấp các điểm yếu nền tảng mà ADR TD-14 quyết định sửa trước khi thêm kind mới (dự kiến SE-01, SE-02, SE-05, SE-08, SE-12). Sau task này, thêm một kind chỉ cần một adapter + test + renderer diff.

## Bối cảnh

- Logic theo kind đang rải ở nhiều nơi:
  - `_local_overlay_for_change` (`app/services/deck_install_rebase_service.py:564-604`);
  - `_load_local_overlays` (dòng 534-561);
  - `VISIBLE_ENTITY_KINDS` (`deck_release_service.py:30`);
  - `CHANGE_REQUEST_CHANGE_TYPES` (`app/services/change_request/helpers.py:60-67`);
  - các hàm `mark_*_changed` (`deck_working_tree_service.py:96-197`);
  - renderer ở `frontend/src/features/deck-collaboration/components/DiffWorkspace.tsx`.
- Vật chứa gắn cứng `deck_item_id` / `deck_install_id` (TD-14 SE-01).
- Chưa có chứng nhận MySQL ở quy mô 10k–50k và publish còn đồng bộ ([Deck CR plan §17–18](../../backend/old/completed-plans/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md)).

## Phạm vi file dự kiến

- Mới: `app/services/share_engine/` gồm `adapters.py` (contract + registry), `kinds/note.py`, `kinds/note_field.py`, `kinds/field_def.py`, `kinds/field_order.py`, `package.py` (nếu ADR chọn phương án A).
- Sửa: `deck_release_service.py`, `deck_working_tree_service.py`, `deck_install_rebase_service.py`, `change_request/{helpers,lifecycle,merge,preview,serializers}.py`, `share/overlay.py`, các repository `deck_release_repository.py`, `deck_install_rebase_repository.py`, `deck_change_request_repository.py`.
- Model/migration (theo ADR): `share_packages`, `share_installs`, `share_entity_lineage`; cột `package_id`/`package_install_id` bổ sung, backfill từ deck item/install.
- Frontend: `features/deck-collaboration/components/DiffWorkspace.tsx` → registry renderer theo kind.

## Công việc chi tiết

1. **Bộ fixture chuẩn trước khi sửa:** chụp đầu ra hiện tại của preview release, diff, prepare/apply rebase, conflicts, change request draft/merge trên bộ dữ liệu cố định (owned + install + local override + nhiều release). Đây là thước đo "không đổi hành vi".
2. Định nghĩa contract adapter theo ADR: identity, serialize/hash chuẩn hóa, đọc tại release, projection cho install, overlay read/write/prune, xung đột, change type đóng góp, merge, retire, `diff_descriptor`, `progress_impact`.
3. Chuyển 4 kind hiện có sang adapter. Thay các nhánh `if entity_kind == …` bằng registry; bỏ hằng số danh sách kind rải rác.
4. **Chỉ khóa theo ID ổn định (SE-05):**
   - ghi overlay/change luôn kèm `field_def_id`;
   - đường fallback theo tên chỉ còn để **đọc** dữ liệu cũ, có đếm số lần dùng (log/metric);
   - lập danh sách dòng cũ thiếu ID để backfill.
5. **Vật chứa trung lập (SE-01)** theo ADR:
   - phương án A: tạo `share_packages`/`share_installs`, backfill 1:1 từ `DeckMarketplaceItem`/`DeckInstall`;
   - service nội bộ dùng package id; API công khai và tên bảng `deck_*` giữ nguyên;
   - thêm `share_entity_lineage` (local → source, source release).
6. **Chứng nhận MySQL và publish bất đồng bộ (SE-08):**
   - benchmark theo Deck CR plan §17 (10k/50k Note, mật độ change, 1k install);
   - publish lớn chuyển sang job có idempotency + trạng thái; head swap nguyên tử.
7. **Renderer diff theo kind (SE-12):** registry phía frontend; 4 kind hiện có giữ đúng hình hiện tại.
8. Cập nhật tài liệu: ADR "đã triển khai", Deck CR plan trỏ tới engine mới.

## Output đầu ra bắt buộc

- Engine + registry + 4 adapter; không còn logic theo kind nằm ngoài adapter (kiểm bằng grep).
- Migration mở rộng (nếu có) + backfill + rehearsal MySQL 8 (upgrade, chạy song song release cũ, downgrade).
- Kết quả benchmark MySQL, kèm so sánh với ngưỡng.
- Fixture "trước/sau" giống hệt nhau.

## Acceptance criteria

- Mọi suite liên quan xanh, fixture chuẩn trùng khớp từng byte trên payload API: `decks`, `deck_collaboration`, `marketplace`, `flashcards`, `browse`.
- Không Note, Card, `CardProgress` hay trạng thái NOTE nào bị đổi bởi migration hoặc refactor.
- Đường fallback theo tên chỉ đọc, có metric.
- Thêm một kind giả lập trong test (ví dụ `demo_prop`) chỉ cần một file adapter + test, và chạy qua được release → install → rebase → change request.

## Verification

```text
python scripts/run_tests.py --module decks,deck_collaboration,marketplace,flashcards,browse --backend-only
python scripts/run_tests.py --module deck_collaboration --frontend-only
```

Thêm probe MySQL 8 cho migration/backfill và benchmark; ghi lệnh và kết quả vào handoff.

## Rollback

Refactor code rollback bằng revert. Migration theo mẫu mở rộng: bảng/cột mới không được đọc khi tắt flag engine; downgrade xóa bảng mới, không đụng bảng `deck_*`.

## Không làm trong task này

Không thêm kind mới (TD-16+), không đổi UI người dùng ngoài renderer diff tương đương, không đổi NoteType marketplace.
