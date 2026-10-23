# TD-07 — Minh bạch nguồn gốc NoteType/Template khi clone; cảnh báo tác giả trước khi hotfix

> Mức: **P1** · Đợt: W3 · Trạng thái: `TODO`
>
> Phụ thuộc: không · Tạm thời cho tới: TD-16 (bỏ hotfix), TD-17 (fork thật) · Lane: Backend đọc + Frontend Note types / Study / Browse · Ước lượng: 3–4 ngày
>
> Nguồn: N1–N3, D1, D3, A1–A3, S5 ở [hành trình người dùng](../../backend/old/decoupling/UIUX_COMPLETED_PHASES_USER_JOURNEY_AUDIT_2026-09-30.md) §2.3–§2.5.

## Mục tiêu

Trong lúc W5 chưa xong, người dùng phải **hiểu đúng** điều gì xảy ra khi sửa:
- bản sao NoteType từ chợ là bản riêng;
- bản sao đi kèm deck đã cài chỉ áp dụng cho Note tự thêm;
- Template của tác giả đang được người khác dùng, nên hotfix sẽ đổi giao diện của họ.

## Bối cảnh

- API danh sách NoteType đã trả `is_marketplace_install` (`app/services/flashcard_content_service.py:106-113`), nhưng trang Loại thẻ không dùng.
- Nút "Chia sẻ lên Kho" hiện cả với bản sao, dù backend chặn (`NoteTypeDetailPage.tsx:265`, `NoteTypeManagerPage.tsx:375`; `share/note_types.py:287-292`).
- Thẻ gốc render Template tác giả (`study_artifact_service.py:118, 147`).
- Hotfix #138 áp dụng ngay cho người cài (`flashcard_content_service.py:1529-1545`).
- Không có cờ `has_released_dependents` trong `serialize_note_type`.

## Phạm vi file dự kiến

- Backend:
  - `app/services/marketplace_query_service.py` / `flashcard_content_service.py`: thêm `provenance` (`owned` | `marketplace_install` | `deck_install_copy`), `used_by_installed_decks` (danh sách deck đã cài dùng bản sao), `has_released_dependents`, `installer_count` (dựa trên `deck_working_tree_service.note_type_has_shared_release_dependents`).
- Frontend:
  - `features/note-types/pages/NoteTypeManagerPage.tsx`, `NoteTypeDetailPage.tsx` (nhãn, banner, ẩn nút chia sẻ);
  - `features/study/components/StudyHeaderToolbar.tsx` và `features/browse` (dòng "Mẫu thẻ: <tên> · của tác giả");
  - `StudyModeSelector.tsx` (câu chữ cho thẻ tác giả / thẻ tự thêm).

## Công việc chi tiết

1. API trả `provenance` và các cờ trên cho danh sách và chi tiết NoteType.
2. **Danh sách Loại thẻ:** nhãn "Cài từ chợ — bản riêng của bạn" / "Đi kèm deck <tên>"; ẩn "Chia sẻ lên Kho" với bản sao, thay bằng giải thích.
3. **Trang chi tiết bản sao đi kèm deck:** banner "Thay đổi ở đây chỉ áp dụng cho thẻ bạn tự thêm vào <deck>. Thẻ gốc dùng mẫu của tác giả." Gỡ banner này khi TD-17 bật.
4. **Trang chi tiết của tác giả khi có người cài:** banner "Template đang được N người cài dùng. Lưu sẽ đổi giao diện của họ ngay ở phiên sau (tạm thời, trước khi có phát hành Template)"; bắt nhập ghi chú thay đổi và lưu vào audit. Gỡ khi TD-16 bật.
5. **Lỗi `SHARED_SCHEMA_VERSIONING_REQUIRED`** (thêm/xóa Template khi đã phát hành): thông điệp tiếng Việt và hướng tạm thời.
6. **Phiên học / Browse của deck đã cài:** hiện tên mẫu thẻ và nguồn (của tác giả / tùy biến của bạn sau TD-17).
7. **Bộ chọn cách học:** nhóm "Thẻ của tác giả" / "Thẻ bạn thêm" có giải thích (phối hợp TD-06).

## Output đầu ra bắt buộc

Cờ API + test; nhãn/banner/ẩn nút + test; ảnh chụp trước/sau; handoff.

## Acceptance criteria

- Người cài không thấy nút chia sẻ bản sao; thấy đúng nhãn nguồn gốc.
- Tác giả có người cài luôn thấy cảnh báo trước khi lưu Template.
- Các thông điệp lỗi Template trên trang này không còn tiếng Anh.

## Verification

```text
python scripts/run_tests.py --module flashcards,marketplace --backend-only
python scripts/run_tests.py --module flashcards,study,browse --frontend-only
```

## Rollback

Trường API mới là bổ sung (không phá client cũ); revert UI.

## Không làm trong task này

Thay đổi cơ chế render hay fork (TD-16, TD-17).
