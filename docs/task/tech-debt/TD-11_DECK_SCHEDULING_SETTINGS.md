# TD-11 — Cài đặt ôn tập theo deck (preset) và theo người dùng; chặn nhãn FSRS

> Mức: **P1** · Đợt: W4b · Trạng thái: `DECISION` (D-C1, D-C4, D-C5)
>
> Phụ thuộc: không · Chặn: TD-12 · Lane: Backend + Frontend Dashboard/Settings · Ước lượng: 4–6 ngày
>
> Nguồn: C2 ở [tùy chỉnh nút và thuật toán](../../backend/old/decoupling/STUDY_BUTTONS_AND_ALGORITHM_CUSTOMIZATION_2026-09-30.md) §3–§4; UX-E3 ở [điều tra UI/UX trước P8](../../backend/old/decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md).

## Mục tiêu

Người học chỉnh được các tham số mà thuật toán `legacy-anki/1.0.0` **đang thực sự đọc**, theo deck (preset) và theo người dùng. Việc này không tạo phiên bản thuật toán mới, vì config đã được đóng băng theo phiên qua policy/config hash.

## Bối cảnh

- `resolve_deck_options` đọc `SchedulerPreset` và `UserSchedulerSettings` (`app/services/scheduler_config_service.py:99-241`), nhưng không có đường ghi nào trong repo.
- Production (2026-08-24): 0 preset, 0 cài đặt người dùng, 965/965 deck `scheduler_preset_id IS NULL` ([xác minh production §8](../../architecture/production-architecture-verification-2026-08-24.md)).
- Resolver chỉ đọc preset của đúng deck, không kế thừa deck cha; `is_default` không được dùng.
- `scheduler_mode='fsrs'` chỉ là nhãn: công thức vẫn là legacy (`anki_scheduler.py:691-692`).
- Deck đã cài dùng deck local của người học (`study_session_service.py:606-619`).

## Phạm vi file dự kiến

- Backend:
  - service mới `app/services/scheduler_preset_service.py` (CRUD, gán, kế thừa);
  - repository;
  - validator `app/validators/scheduler_settings.py`;
  - API `app/api/v1/decks/routes.py` (gán preset) + `app/api/v1/settings/` (cài đặt người dùng, danh sách preset);
  - `scheduler_config_service.py` (kế thừa theo D-C1).
- Frontend:
  - hộp thoại "Tùy chọn ôn tập" từ menu deck (`features/dashboard/components/DeckRow.tsx`);
  - trang cài đặt chung (giờ sang ngày mới, học trước);
  - xem trước dùng engine client hiện có.
- Không cần migration cho các cột hiện có. Ease khởi đầu và ease tối thiểu cần cột mới (tùy chọn, nếu chủ sản phẩm muốn).

## Công việc chi tiết

1. **API preset:** tạo, sửa, xóa, nhân bản (tên duy nhất theo user); chỉ các tham số ✅ trong bảng §3.2 của báo cáo nguồn.

   | Tham số | Khoảng hợp lệ đề xuất |
   |---|---|
   | Bước học / học lại | 1 giây–7 ngày, tối đa 10 bước |
   | Khoảng tốt nghiệp / Dễ | 1–365 ngày |
   | Hệ số Khó | 0,5–3,0 |
   | Hệ số Dễ | 1,0–3,0 |
   | Interval modifier | 0,5–2,0 |
   | Hệ số khi quên | 0–1 |
   | Khoảng tối thiểu sau quên | ≥ 1 ngày |
   | Khoảng tối đa | 1–36500 ngày |
   | Leech | 0–99; hành động `suspend` / `tag_only` |

2. **Gán preset cho deck:** tùy chọn "áp dụng cho cả deck con" (D-C1). Resolver kế thừa theo chuỗi deck cha nếu chốt kế thừa, có test cho cây sâu.
3. **Cài đặt người dùng:** giờ sang ngày mới (0–23), học trước (0–60 phút). **Không** cho đặt `scheduler_mode='fsrs'`: API từ chối, UI không hiển thị (D-C4).
4. **Deck đã cài:** người học gán preset cho deck local; không kế thừa preset của tác giả (D-C5); không ảnh hưởng tác giả.
5. **UI:**
   - hộp thoại có nhóm "Bước học", "Khoảng cách", "Khi quên", "Thẻ khó nhớ (leech)";
   - mỗi tham số có giải thích ngắn;
   - khung xem trước "Thẻ mới trả lời Tốt → hẹn …" tính bằng engine client với options mới;
   - thông báo "Áp dụng từ phiên học sau".
6. **Audit:** ghi log mọi thay đổi preset/gán/cài đặt.
7. **MCP/Connect:** đọc options qua resolver sẵn có, không cần sửa. Xác nhận bằng test.

## Output đầu ra bắt buộc

API + validator + service + test; UI + test; cập nhật hướng dẫn (bỏ nhãn "Sắp có" của TD-08); handoff.

## Acceptance criteria

- Đổi preset: phiên đang mở giữ config hash cũ; phiên mới dùng config mới (test ghi rõ hash).
- Lịch hẹn đã có không bị viết lại.
- Kế thừa deck con đúng theo D-C1.
- Deck đã cài: tác giả không bị ảnh hưởng.
- Không đường nào đặt được FSRS.

## Verification

```text
python scripts/run_tests.py --module study,decks --backend-only
python scripts/run_tests.py --module decks,study --frontend-only
```

## Rollback

Xóa gán preset (NULL) thì về mặc định cứng; bỏ route.

## Quyết định liên quan

- D-C1: preset dùng chung + kế thừa deck con.
- D-C4: ẩn FSRS.
- D-C5: người học chỉnh deck đã cài.

## Không làm trong task này

Giới hạn/ngày (TD-12); FSRS thật (P8); ease khởi đầu/tối thiểu nếu chưa được duyệt.
