# TD-20 — Interaction host cho màn học; event và thống kê tổng quát (P8-00)

> Mức: **P3** (xếp cuối theo chỉ đạo; là điều kiện tiên quyết của P8) · Đợt: W6 · Trạng thái: `TODO`
>
> Phụ thuộc: TD-01, TD-02 (phiên an toàn); phối hợp P9-09 · Chặn: TD-22, năng lực P8 đầu tiên · Lane: Frontend Study (+ Backend wire) · Ước lượng: 5–8 ngày
>
> Nguồn: UX-C1, UX-C5, UX-E5 và P8-UI-1..3 ở [điều tra UI/UX trước P8](../../backend/old/decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md); canonical plan §6, §14.3. Skill: `$flama-frontend-architecture`.

## Mục tiêu

Tách `StudyPage` thành **host** + **Interaction component**, sao cho thêm chế độ (trắc nghiệm, gõ, nghe) chỉ cần viết component mới. Bộ 4 nút hiện tại là instance đầu tiên, giữ nguyên hình thức.

## Bối cảnh

- `StudyPage` tự giữ `revealedCardKey`, `decisionState`, keymap 1–4 (`frontend/src/features/study/pages/StudyPage.tsx:31-35, 114-158, 207-281`).
- Event có `rating` bắt buộc (`types.ts:229-238`).
- Thống kê cục bộ đếm 4 rating, lặp 2 lần (`hooks/useStudySession.ts:625-646, 697-718`).
- Host chưa có nút nghe lại; âm thanh chỉ phát qua `play_audio` của Template (`static/js/card_renderer_host.js:1028-1035`).

## Phạm vi file dự kiến

- Mới: `features/study/interactions/host/` (contract, host, registry), `interactions/fourRating/` (component đầu tiên).
- Sửa: `pages/StudyPage.tsx`, `components/StudyBottomBar.tsx`, `hooks/useStudySession.ts`, `types.ts`, `session/*` (event tổng quát với adapter 4 rating), `components/StudyCompletionCard.tsx` (thống kê theo outcome).

## Công việc chi tiết

1. **Contract host ↔ component:**
   - vòng đời `present → respond → feedback → emitAction`;
   - host sở hữu mutex, gating, phím tắt tin cậy, trạng thái bận;
   - component khai báo phím nó dùng và Action phát ra.
2. Chuyển bộ 4 nút thành component (keymap, previews, reveal nằm trong component). **Zero Visual Regression**, có ảnh chụp.
3. **Event tổng quát:**
   - `action_key` + payload phiên bản hóa;
   - `rating` chỉ còn trong adapter 4 nút;
   - đọc được wire hiện có (v4) không đổi;
   - phối hợp P9-09 để không làm hai lần.
4. Thống kê phiên theo outcome (một hàm dùng chung, bỏ phần lặp).
5. Bề mặt nhập liệu tin cậy ngoài iframe (khung chung cho ô gõ và phương án trắc nghiệm sau này); nút "Nghe lại" ở host gọi media của thẻ qua bridge hiện có.
6. Test: toàn bộ test `features/study` hiện có xanh không cần sửa kỳ vọng hành vi; thêm test contract.

## Output đầu ra bắt buộc

Host + contract + component 4 nút + event tổng quát + thống kê outcome + nút nghe lại; ảnh chụp trước/sau; handoff.

## Acceptance criteria

- Người học không thấy khác biệt nào (ảnh chụp + test).
- Thêm một component giả lập trong test không cần sửa `StudyPage`.
- Payload commit/batch của bộ 4 nút giống hệt trước.

## Verification

```text
python scripts/run_tests.py --module study --frontend-only
python scripts/run_tests.py --module study --backend-only
```

## Rollback

Revert frontend. Wire không đổi.

## Không làm trong task này

Năng lực P8 cụ thể (trắc nghiệm/gõ), verifier server.
