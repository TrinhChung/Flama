# Decoupling autopilot log

Trạng thái: STOP

> Scheduled task `decoupling-autopilot` (Claude app, chạy local) kích hoạt lúc 0h, 4h, 9h, 14h, 19h giờ Tokyo; lần chạy thật đầu tiên là 04:00 ngày 29/09/2026. Đổi dòng trên thành `Trạng thái: STOP` để tạm dừng.
>
> Autopilot không commit/push. Snapshot byte-exact của worktree nằm ở `refs/autopilot/*` (không đụng HEAD/index):
> - Liệt kê: `git for-each-ref refs/autopilot`
> - Xem autopilot đã đổi gì: `git diff --stat <snapshot-start> <snapshot-end>` (chỉ so snapshot với snapshot; so với HEAD sẽ lệch EOL)
> - Xóa hết snapshot: `git for-each-ref --format='delete %(refname)' refs/autopilot | git update-ref --stdin`

## Cần user quyết định

1. **Flama Audio workflow test (chặn commit release candidate, ngoài Phase 5).** Thay đổi chưa commit ở `.github/workflows/flama-audio-release.yml` xóa step `Upload verified workflow artifact`; `tests/test_flama_audio_release_workflow.py:91` (`test_pfx_is_ephemeral_and_never_uploaded`) split theo tên step đó nên `IndexError`. Phương án: (a) giữ step upload-artifact (revert phần xóa trong workflow); (b) bỏ step và sửa test để assert không có `.pfx` trong mọi step `upload-artifact`/`gh release upload` của workflow. Đề xuất: (b) nếu việc bỏ artifact là cố ý (release asset đã được `gh release download` + verify lại), ngược lại (a). Autopilot không tự sửa vì là thay đổi của user.
2. **Mở lại autopilot hay không.** Code Phase 5 cho R0 đã xong và INT-03 xanh local; việc còn lại là R0 deploy LEGACY, R1 canary theo runbook (P5-10), rerun probe consumer với Redis thật (cần cài Redis), shared-release versioning/multi-learner shared template và policy history cho Algorithm (Phase 8). Tất cả cần production hoặc quyết định của user nên log đã chuyển `STOP`. Khi có việc code mới (Phase 6+ hoặc lỗi từ canary), cập nhật bảng "Thứ tự" trong P5 plan hoặc thêm plan mới rồi đổi lại `Trạng thái: RUN`.

## Nhật ký chạy (mới nhất ở cuối)

- 2026-09-29 ~09:15 JST SKIP: shell (Bash) liên tục bị auto-mode classifier trả "no verdict" (8 lần), không chạy được kiểm tra BUSY 3b, snapshot hay test. Các cổng khác đã qua: không có session đang chạy (gần nhất 23:28Z, cách hơn 40 phút), nhánh `develop`, không có lock hay merge, 5h=69%, weekly=23%. Ghi chú cho lần sau: header P5 plan ghi "INT-03 local xanh" nhưng dòng G5-X ở §2 và README (INT-03 "PLANNED ONLY") vẫn ghi chưa chạy, cần đối chiếu trước khi chọn việc.
- 2026-09-29 14:12–14:15 JST RUN → STOP. Cổng: không session nào đang chạy (gần nhất 09:15 JST), worktree IDLE 292m, nhánh `develop`, không lock, 5h=1%, weekly=25%. Snapshot start `refs/autopilot/20260929T051301Z-start`, end `refs/autopilot/20260929T051352Z-end`; `git diff --stat` start→end rỗng (autopilot không sửa code). Ngữ cảnh: P5 plan §1/§2/§5 và README đã thống nhất (G5-X/INT-03 PASS local 2026-09-29, P5-04..P5-09 DONE code), ghi chú lệch trạng thái của lần 09:15 đã được giải quyết. Kiểm chứng nhẹ: `python -m unittest tests.test_study_algorithm_switch tests.test_study_note_overlay` 15 tests OK; `tests.test_flama_audio_release_workflow` 9 tests, 1 ERROR (đúng lỗi ngoài Phase 5 mà G5-X đã ghi, chi tiết ở "Cần user quyết định" #1). Việc còn lại đều cần production/deploy, Redis thật hoặc quyết định của user nên đổi `Trạng thái: STOP`. Bước tiếp theo (user): xử lý test Flama Audio, commit release candidate, deploy R0 LEGACY rồi R1 canary theo `docs/runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md`.
