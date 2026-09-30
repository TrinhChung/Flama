# TD-21 — Browse theo Note

> Mức: **P3** (lên P1 ngay khi một Note có từ hai application) · Đợt: W6 · Trạng thái: `DECISION` (D-U5)
>
> Phụ thuộc: không; nên làm trước khi bật áp dụng lặp (TD-18) cho người dùng · Lane: Backend Browse + Frontend Browse · Ước lượng: 4–6 ngày
>
> Nguồn: UX-E1 ở [điều tra UI/UX trước P8](../decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md).

## Mục tiêu

Browse hiển thị theo **Note** (đơn vị tiến độ), liệt kê các cách học đang gắn, và phân biệt rõ "gỡ một cách trình bày" với "xóa Note".

## Bối cảnh

- Browse một dòng mỗi Card, cột cứng "Từ vựng / Đọc / Ý nghĩa", không có cột Template (`frontend/src/features/browse/components/BrowseCardTable.tsx:87-107`).
- Xóa theo Card; xóa Card cuối cùng thì xóa luôn Note (`app/services/browse_card_service.py:1143-1158`).
- Hôm nay 1 Note = 1 Card nên chưa lộ (P6 D6-04). Khi có nhiều application, một Note sẽ hiện nhiều dòng giống nhau.

## Phạm vi file dự kiến

- `app/services/browse_card_service.py`, `app/repositories/browse_card_repository.py`, `app/api/v1/learning/browse.py` (chế độ `group_by=note`, cột động theo FieldDef).
- `features/browse/*` (bảng, trình sửa, thao tác hàng loạt, xóa).

## Công việc chi tiết

1. Chế độ xem theo Note (mặc định sau khi được duyệt):
   - cột động theo FieldDef của NoteType (hoặc Field chính có `identity_role`);
   - trạng thái và đến hạn theo tiến độ Note;
   - cột "Cách học" liệt kê application.
2. Giữ chế độ xem theo Card cho người dùng nâng cao và công cụ hỗ trợ.
3. **Xóa:**
   - "Xóa Note" (xóa nội dung, tiến độ theo chính sách hiện có);
   - "Gỡ cách học này khỏi Note" (chỉ Card của application, tiến độ Note giữ nguyên);
   - câu chữ rõ ràng.
4. Deck đã cài: giữ quy tắc clone hiện có (không sửa nguồn; sửa qua overlay).
5. Hiệu năng: phân trang và đếm theo Note, mục tiêu ngang P5-11e.

## Output đầu ra bắt buộc

API + UI + test (owned, deck đã cài, NoteType nhiều Template); benchmark; handoff.

## Acceptance criteria

- Một Note hai cách học hiện **một** dòng; tiến độ khớp với phiên học.
- Gỡ cách học không đổi tiến độ Note.
- Chế độ theo Card vẫn hoạt động như trước.

## Verification

```text
python scripts/run_tests.py --module browse --backend-only
python scripts/run_tests.py --module browse --frontend-only
```

## Rollback

Flag về chế độ theo Card.

## Không làm trong task này

Sửa cấu trúc field của deck đã cài qua UI (liên quan TD-14..TD-17).
