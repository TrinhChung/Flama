# P2-01 — Iframe `host_command` containment

> Phase: 2
>
> Priority: P0 / Global blocker
>
> Status: COMPLETED
>
> Review verdict round 5 — 2026-08-29: PASSED. Iframe progress bridge đã bị loại bỏ; forged-message và parent-shortcut regression evidence đạt gate.
>
> Dependency: none
>
> Primary lane: Frontend Security / Renderer

## Mục tiêu

Đóng ngay mọi progress-affecting path từ untrusted Template JavaScript trong card iframe tới reveal/answer/undo handlers của parent Study runtime.

## Bối cảnh và threat

`static/js/card_renderer_host.js` hiện cho child iframe gửi `host_command`, parent chuyển thành `flama:host-command`, và `StudyPage` xử lý thành reveal/answer/undo. Source/instance/channel checks xác định đúng iframe nhưng không chứng minh trusted human gesture vì Template script chạy trong cùng iframe có thể tự tạo message hợp lệ.

## Phạm vi file dự kiến

- `static/js/card_renderer_host.js`
- `frontend/src/features/study/pages/StudyPage.tsx`
- `frontend/src/features/study/components/CardRendererHost.test.ts`
- `frontend/src/features/study/pages/StudyPage.test.tsx`
- renderer security documentation/cache revision nếu cần

## Công việc chi tiết

1. Trace toàn bộ `host_command`, `flama:host-command`, `keydown_event` và message listener call graph.
2. Xóa/disable child emission cho reveal/answer/undo.
3. Xóa/disable parent translation/handler tương ứng.
4. Không thay bằng raw action/rating message tên khác.
5. Giữ parent-document shortcuts hiện có khi focus không nằm trong iframe.
6. Xử lý iframe-focused UX an toàn: tạm không hỗ trợ shortcut là acceptable baseline.
7. Thêm negative tests chủ động forge:
   - valid instance/channel/source + `host_command`;
   - arbitrary command/action/rating;
   - legacy `keydown_event`;
   - unrelated frame/source.
8. Assert không reveal, answer, undo, event append hoặc commit.
9. Verify renderer sanitization, CSP và media proxy không bị nới.
10. Cập nhật security contract nêu rõ iframe không có progress capability.

## Output đầu ra bắt buộc

- Progress-affecting iframe bridge bị loại bỏ/khóa.
- Forged-message regression tests.
- Parent shortcut regression tests.
- Security contract/cache revision update nếu behavior/version cần thể hiện.
- Ghi rõ temporary limitation khi focus ở iframe.
- Handoff report.

## Acceptance criteria

- Template JavaScript không thể reveal/answer/undo qua `postMessage`.
- Không generic action/rating/command capability tồn tại trong iframe contract.
- Parent shortcuts và pointer buttons vẫn hoạt động.
- Không visual regression.
- Không nới `sandbox`, CSP hoặc origin/source policy để “fix” shortcut.

## Verification

```text
python scripts/run_tests.py --module study --frontend-only
python scripts/run_tests.py --changed
```

Browser verification phải dùng isolated Chrome profile theo `AGENTS.md`.

## Rollback

Không bật lại bridge cũ khi rollback. Nếu regression UX, giữ containment và sửa parent UX riêng.

## Không làm trong task này

- Không thiết kế bridge keyboard mới.
- Không thêm nonce đơn giản bị lộ trong iframe bootstrap.
- Không thay đổi scheduler/action semantics.
- Không redesign card renderer.
