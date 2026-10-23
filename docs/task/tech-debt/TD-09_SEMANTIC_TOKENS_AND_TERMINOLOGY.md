# TD-09 — Token màu trạng thái và đánh giá, bảng thuật ngữ, Việt hóa nhãn

> Mức: **P2** · Đợt: W4 · Trạng thái: `TODO`
>
> Phụ thuộc: không · Chặn: TD-10 · Lane: Frontend (design system) · Ước lượng: 2–3 ngày
>
> Nguồn: UX-D3..D6, UX-E4 ở [điều tra UI/UX trước P8](../../backend/old/decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md). Nối với [task i18n](../../tasks/MULTILINGUAL_I18N_MIGRATION_TASK.md). Skill: `$impeccable`, `$flama-frontend-architecture`.

## Mục tiêu

Theo `PRODUCT.md`: một thuật ngữ, một component và một màu ngữ nghĩa phải mang cùng ý nghĩa trên mọi màn. Không trộn tiếng Anh và tiếng Việt trong cùng màn; không lộ thuật ngữ nội bộ.

## Bối cảnh và bằng chứng

- Màu Mới/Đang học/Đến hạn khác nhau giữa các màn:
  - Dashboard `features/dashboard/components/DeckRow.tsx:186-194`: emerald / **rose** / **orange**;
  - header phiên `features/study/components/StudyHeaderToolbar.tsx:221-235`: emerald / amber / rose;
  - màn hoàn thành `StudyCompletionCard.tsx:255-273`: emerald / amber / rose.

  `DESIGN.md` quy định Learning = amber, Destructive = đỏ.
- Thuật ngữ: nút "Học lại" nhưng màn hoàn thành ghi "Quên" (`StudyCompletionCard.tsx:228`); `DESIGN.md` ghi "Good (Được)" còn UI ghi "Tốt"; "Đã ôn N **thẻ**" thực ra là số **lượt** (dòng 192 và 223).
- Nhãn tiếng Anh: header "Decks / Study / Stats / Import / Browse"; menu deck "Deck Settings / Share Deck / Reset Progress / Delete Deck" (`DeckRow.tsx:210-279`).
- Thuật ngữ nội bộ: "learning step", "cửa sổ học sớm", "Mốc ôn danh nghĩa" (`StudyWaitingCard.tsx:52-53, 66, 93`).
- Hộp thoại đặt lại tiến độ không nói phạm vi theo Note (`dashboard/components/DeckModals.tsx:295`).

## Phạm vi file dự kiến

- `frontend/src/index.css` (token trong `@theme`): `--status-new`, `--status-learning`, `--status-due`, `--rating-again`, `--rating-hard`, `--rating-good`, `--rating-easy` (có cả dark mode).
- Các component trên, cộng `ReviewInteractionControls.tsx`, `StudyWaitingCard.tsx`, `DeckModals.tsx`.
- `DESIGN.md` (cập nhật tên đánh giá và màu cho khớp).
- `frontend/src/shared/` (bảng thuật ngữ dùng chung, nếu chưa có i18n).

## Công việc chi tiết

1. Chốt bảng thuật ngữ (duyệt với chủ sản phẩm):
   - Học lại / Khó / Tốt / Dễ;
   - "lượt ôn" cho số lần trả lời;
   - "Note" hoặc "từ" cho đơn vị tiến độ;
   - "Mới / Đang học / Đến hạn".
2. Định nghĩa token màu, áp dụng cho mọi nơi hiển thị trạng thái hàng đợi và đánh giá; đảm bảo tương phản AA ở cả light/dark.
3. Việt hóa nhãn header phiên học và menu deck. Nếu task i18n đã có khung thì đi qua lớp i18n.
4. Thay thuật ngữ nội bộ bằng câu thường ("Đang chờ tới lượt ôn lại", "Còn N thẻ đang trong bước học").
5. Hộp thoại đặt lại tiến độ nêu rõ: đặt lại tiến độ theo Note trong deck, ảnh hưởng mọi cách học của các Note đó.
6. Cập nhật `DESIGN.md` cho khớp.

## Output đầu ra bắt buộc

Token + áp dụng + ảnh chụp trước/sau cho từng màn đổi màu hoặc nhãn (**cần chủ sản phẩm duyệt**: đây là thay đổi hình thức có chủ đích); `DESIGN.md` cập nhật; handoff.

## Acceptance criteria

- Grep không còn class màu cứng cho trạng thái hàng đợi hoặc đánh giá ngoài token.
- Cùng một trạng thái có cùng màu ở Dashboard, header, màn hoàn thành, màn chờ.
- Không còn nhãn tiếng Anh ở header phiên học và menu deck.

## Verification

```text
python scripts/run_tests.py --module decks,study --frontend-only
```

Kèm kiểm tra trực quan light/dark.

## Rollback

Revert CSS/component.

## Không làm trong task này

Cho người dùng tự chọn màu; khung i18n đầy đủ (thuộc task i18n).
