# CT-02/CT-03 — Codex tiếp nhận implementation của Claude

- Nhánh: `refactor/frontend-fsd-renderer-boundary`, base HEAD `965b565c73f61eb8c0742e030eee434a80cac5cb`.
- Trạng thái: **Accepted (code), Contract A2 sẵn sàng cho Gemini**. Chưa deploy/chạy migration vào database ứng dụng thật; chưa browser gate M2.
- Quyết định: [ADR-T1](../../../architecture/template-version-foundation-adr-2026-10-07.md). Giữ U1–U8 của kế hoạch v2; nền expand chưa phải cutover template độc lập.

## Code đã triển khai

1. Mở rộng `templates` với owner/schema/head, bảng `template_versions` và migration `20261007_000053` sau revision 52. Backfill theo lô giữ nguyên nguồn Unicode/CRLF, timestamp, Template/Card ID; preflight từ chối drift; downgrade từ chối mất lịch sử đã authored.
2. Repository + Session hooks: thu thay đổi ORM khi flush, chụp nguồn cuối trong outer commit. Nhiều flush thành một version; rollback/savepoint hủy đúng thay đổi. Giữ baseline trước sửa cho hàng cũ chưa backfill. Rename/no-op không append; schema có đổi cũng được ghi lịch sử.
3. A2 owner list/get/restore ở `/api/card-templates/<id>/versions` và alias NoteType, schema `template-versions.v2`. Restore compile validation + schema release guard + audit, luôn append bản mới, không đổi Card/progress. PATCH nhận change_note; reset/create có origin và actor REST.
4. Đăng ký model/hooks ở cả main factory và Connect standalone. CLI backfill mặc định dry run. Serializer hiện có thêm `current_version_id`; snapshot chỉ thêm 6 route.
5. Sửa hai blocker CT-R1: rename/refetch metadata không xóa HTML/CSS draft; tự sinh template từ reserved Mustache field name trả validation error trước commit. Tên đặc biệt vẫn dùng được nếu cung cấp nguồn front/back rõ ràng.

Các file code chính:

- `models/template.py`, `models/template_version.py`, `migrations/versions/20261007_000053_add_template_versions.py`.
- `app/repositories/template_version_repository.py`, `app/services/template_version_service.py`, `app/api/v1/flashcards/card_templates.py`.
- Các điểm nối nhỏ: main factory, Connect model registration, flashcards blueprint, content/share services và marketplace serializer.
- `frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx`: chỉ đổi dependency effect đồng bộ draft; DOM/class và editor snapshots giữ nguyên.

## Review bổ sung và lỗi đã sửa

- MySQL REPEATABLE READ: snapshot cũ từ bước owner/template read không nhìn thấy history mới dù khóa Template đã thấy pointer mới. Đọc head bằng current read `FOR UPDATE`, cấp số từ head dưới parent lock; rehearsal hai session xác nhận version 3 và giữ cả hai thay đổi.
- Tránh missing-key gap lock khi chụp version đầu cho hai template khác nhau: không khóa range history rỗng; parent lock + unique sequence giữ tính đúng. Probe phối hợp hai thread trước INSERT xác nhận cả hai version 1, không deadlock.
- Restore refresh ORM identity dưới khóa trước khi xét schema để guard không dùng dữ liệu stale. Baseline pointer update giữ timestamp live sau flush.
- MySQL reflect UNIQUE thành supporting index: validator loại đúng index của constraint đã khai báo, không từ chối schema hợp lệ. Có regression test.
- Strict serializer test GT-02 được cập nhật đúng field mới `current_version_id` và thêm assertion string; không nới thành subset. Route snapshot chỉ có 6 endpoint mới.

## Bằng chứng kiểm tra

| Lệnh/phạm vi | Kết quả |
|---|---|
| `scripts/run_tests.py --module flashcards --backend-only` | 318 test, 24 file PASS |
| `scripts/run_tests.py --file` 11 file artifact/install-usage/study-note-template/authority-pin/study-session/API-route-map/defaults/adversarial/tokens/note-count/versions | 165 test PASS sau cập nhật strict serializer contract |
| `scripts/run_tests.py --file tests/test_template_versions.py tests/test_template_versions_migration.py tests/test_template_note_count.py --backend-only` | 38 test PASS; 21 migration + 12 version + 5 note-count |
| `npm --prefix frontend run test -- src/entities/card-template src/features/note-types` | 114 test, 9 file PASS; editor snapshots không đổi |
| `npm --prefix frontend run typecheck` | PASS |
| `npm --prefix frontend run lint` | Exit 0; còn warning có sẵn ngoài thay đổi |
| `npm --prefix frontend run build:ci` | PASS; warning chunk >500 kB có sẵn |
| Real `wsgi.py` import với SQLite file tạm, schema mới, route match và CLI dry run | PASS |
| Connect-first bootstrap trong process riêng, SQLite memory, không gọi main factory | PASS; ORM nhiều flush tạo một version cuối, owner đúng, creator null nếu không có annotation |
| MySQL probe dưới đây | MySQL **8.0.40**, PASS và cleanup verified |

Tổng các nhóm backend không trùng file: **504 test** (318 + 165 + 21); nhóm 38 là kiểm tra lại hẹp sau sửa. Không dùng kết quả này thay cho full CI/pre-release.

MySQL probe tái chạy được:

```powershell
& .\.venv\Scripts\python.exe docs/task/template-features/tools/verify_template_versions_mysql.py --runtime
```

Probe chỉ tạo schema `flama_template_probe_<uuid>_legacy|orm`, kiểm tra tên/engine trước mọi ghi và cleanup. Chỉ đọc collation cấu hình từ information_schema, không đọc/ghi hàng ứng dụng. Đã kiểm tra legacy upgrade hai lần, downgrade/re-upgrade baseline, guarded downgrade, actual create_all parity, stale RR editor và parallel first-version insert. Hai schema tạm được drop, `cleanup_verified=true`.

## Handoff Gemini

- **GT-10A Ready**: 5 file entity API/types/keys/tests; [prompt](../GT-10A.prompt.txt). Canonical A2 v2, không definition_id. Review xong mới mở GT-10B.
- **GT-15A Ready**: một test file mới, A7/A12–A17; [prompt](../GT-15A.prompt.txt). Không lặp cases đã phủ của Codex; lỗi phải giữ test để reviewer sửa backend.
- **GT-10B** sau review GT-10A: sheet/page phải áp nguồn response restore vào draft, kể cả nguồn giống server/cache. Chỉ invalidate sẽ giữ draft do GT-06 đã được sửa; spec ghi rõ trường hợp này và response muộn khi đổi template.
- Worktree từ HEAD chưa có nền uncommitted. Chạy tuần tự với whitelist trên workspace, hoặc đưa đúng diff nền đã review sang worktree trước khi chạy worker.

## Giới hạn và phần sau

`note_type_id` vẫn NOT NULL, render và artifact freeze giữ cơ chế hiện tại. Không có attachment binding mới, template standalone, user market copy, pin template release hay generic release core. CT-04/06/07/05 còn trong kế hoạch; GT-11/12/13/15D/15E chưa mở vì spec v1 không khớp U1/U2/U6/U7.

Writer ORM đều được capture khi commit. Raw/bulk SQL bỏ qua hooks phải backfill rõ ràng. Creator của writer MCP/Connect/import chưa annotate là null; không suy đoán actor từ owner. Không sửa renderer, scheduler, overlays hoặc các diff MCP/stats đang có của người dùng. Không commit/push.
