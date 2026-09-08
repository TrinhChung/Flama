# Kế hoạch triển khai P1 và P2 — 2026-09-07

> Status: COMPLETED 2026-09-08 — P1-03/P1-04 và P2-02..P2-07 đã qua G-END; async batch được containment và v3 issuance vẫn opt-in.
>
> Runtime baseline: `46c03f0`, branch `develop`; HEAD lúc chốt tài liệu: `da52960` (chỉ commit hai thay đổi test/runner đã có khi bắt đầu). Thay đổi async batch cần đối chiếu: `6da743e`.
>
> Phạm vi đã triển khai: 8 task P1-03–P1-04 và P2-02–P2-07, cùng bước tái kiểm chứng các invariant P1-01/P1-02/P2-01 sau thay đổi runtime.
>
> Tài liệu này cập nhật thứ tự và execution slices P1/P2 của [backlog 2026-08-29](./REVIEWED_DETAILED_EXECUTION_BACKLOG_2026-08-29.md). Acceptance criteria trong từng task vẫn là điều kiện bắt buộc. Phase 3 và INT-01 giữ backlog riêng.

## 1. Kết quả cần đạt và baseline

P1 hoàn tất khi mọi native/external writer đang được cho phép chạy tuân thủ cùng progress revision contract, event provenance được validate và lifecycle Algorithm/decoder có quy tắc rõ ràng. P2 hoàn tất khi session mutation được tuần tự hóa, restore fail closed, Interaction phát một semantic Action, keyboard giữ trusted boundary và wire v3 có đường tương thích v2 đã kiểm chứng.

| Nhóm | Trạng thái đã ghi nhận | Công việc trong kế hoạch này |
|---|---|---|
| P1-01, P1-02 | Đã hoàn thành ở baseline trước async worker | Tái kiểm chứng các producer đang chạy; giữ nguyên handoff lịch sử |
| P1-03, P1-04 | COMPLETED 2026-09-08 | Provenance/payload và retirement lifecycle đã có runtime/test evidence |
| P2-01 | Đã hoàn thành containment iframe | Chạy lại security regression tại các mốc frontend |
| P2-02–P2-07 | COMPLETED 2026-09-08 | Sáu task đã triển khai; v3 creation và async admission giữ flag-off mặc định |

Baseline trước triển khai ngày 07/09, tại `46c03f0` cùng hai working-tree changes lúc đó: Study backend **102 pass**, Study frontend **125 pass**, async queue **7 pass** khi chạy riêng. Hai thay đổi trong `StudyQuickEditDialog.test.tsx` và `scripts/run_tests.py` sau đó đã được commit ở `da52960`. Kết quả G-END mới nằm ở mục 14 và completion report.

`test_study_batch_queue.py` và các suite provenance/registry/wire mới đã được thêm vào module Study. Test cục bộ vẫn không chứng minh real Redis, worker lifecycle hoặc concurrency MySQL; vì vậy async admission mặc định tắt. Evidence MySQL trong [P1-02 completed handoff](./completed/P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md) tiếp tục là evidence lịch sử cho contract external writer.

Invariants giữ xuyên suốt: `CardProgress` là progress authority; `ReviewEvent` là history; native core không tự commit; shared deck là `logical_overlay`; exact Algorithm/Trigger version fail closed; giữ UI hiện tại. P1/P2 không thêm model/migration. Bảng `StudySessionBatch` đã được commit là thay đổi có sẵn cần rà soát, không phải bằng chứng Phase 4 đã bắt đầu. Schema/deployment repair của bảng này phải được tách thành prerequisite riêng nếu cần.

## 2. Delta phải xử lý trước khi áp dụng kế hoạch cũ

Các điểm dưới đây được kiểm tra bằng đọc code; mức độ ảnh hưởng production chưa được đo trong lần lập kế hoạch.

| ID | Evidence hiện tại | Hệ quả đối với kế hoạch |
|---|---|---|
| D1 | [Async worker](../../../app/services/study_worker_service.py) gọi `execute_native_review_transition` và `apply_native_review_mutation`, nhưng có vòng replay/transaction riêng. Chưa có cùng kiểm tra base revision, session status/expiry, final state và scope như synchronous commit. | Tái kiểm chứng P1-01/P1-02 trước khi chứng nhận tất cả writer; không chỉ kiểm tra rằng worker gọi shared core. |
| D2 | [Queue service](../../../app/services/study_queue_service.py) pop job khỏi queue, fallback trong process và dùng Redis lock không có owner token. `drain_study_queue` hiện chỉ có caller trong tests theo tìm kiếm repo. Chưa tìm thấy Alembic revision cho `study_session_batches`. | Có gate riêng cho durability, lock ownership, consumer startup và schema readiness nếu giữ async enabled. Chưa thể kết luận có worker production từ code hiện có. |
| D3 | [Hook](../../../frontend/src/features/study/hooks/useStudySession.ts) tự gửi async khi rollover; xử lý mọi response thành công của `/batch` như đã acknowledge, trong khi API trả 202 `enqueued`. | Phân biệt accepted và persisted; không xóa pending events hoặc cộng completed statistics chỉ dựa trên 202. |
| D4 | [Restore normalizer](../../../frontend/src/features/study/session/sessionRestore.ts) không đưa `batch_sequence`/`in_flight_batches` vào object trả về; [engine](../../../frontend/src/features/study/session/studySessionEngine.ts) đánh sequence theo `events.length + 1`, trong khi extract batch loại các event đầu khỏi danh sách này. | P2-02/P2-03 phải bảo toàn pending batch, identity và sequence xuyên rollover/reload, không chỉ validate mảng events còn lại. |
| D5 | `operationRef` còn là boolean marker; controls còn hai callbacks; `ReviewAction` hiện có các trường union độc lập; restore vẫn có ép kiểu số. | P2-02/P2-03/P2-04 cần implementation và test phân biệt được code cũ với code mới. |
| D6 | [Anki `_import_review`](../../../app/services/anki_sync_service.py) đã truyền `anki`/`revlog-v1` ngay lúc tạo event. Native builder vẫn copy payload rộng và gán session/client-event/sequence sau recorder. | Sửa mô tả cũ của P1-03; giữ phần external đã đúng và tập trung final construction, provenance authority, payload limits. |

Đường runtime cần dùng khi triển khai: `wsgi.py -> create_app()`; config qua `app/settings.py`, maintenance qua `app/startup.py`. Các route session/batch/commit đang ở `app/routes/flashcards/study.py`, không chuyển route chỉ để phù hợp sơ đồ kiến trúc cũ.

## 3. Thứ tự triển khai

Thứ tự mặc định cho một người thực hiện:

1. **G0:** cập nhật producer/contract baseline, xử lý quyết định async và kiểm chứng lại P1-01/P1-02/P2-01.
2. **P2-02 → P2-03:** đóng lỗi concurrency và persisted-session correctness ưu tiên P0.
3. **P1-03 → P1-04:** chốt event provenance và version lifecycle trên boundary đã ổn định.
4. **P2-04 → P2-05:** semantic controls và trusted keyboard decision.
5. **P2-06 → P2-07:** chốt Trigger ADR, triển khai wire/version compatibility.
6. **G-END:** review tập trung P1/P2; chuyển evidence sang Phase 3/INT-01.

Dependency bắt buộc: P2-06 nhận output P1-03 + P2-04; P2-07 nhận output P1-04 + P2-03 + P2-06. Việc đưa P2-02/P2-03 lên trước P1-03 là ưu tiên thực thi sau G0, không đổi dependency domain. Có thể chuẩn bị contract backend và fixture frontend độc lập nếu có người phụ trách khác nhau; các thay đổi chung hook/store/session service vẫn merge tuần tự.

Không cần viết lại P1-01/P1-02 từ đầu. G0 và G-END là checkpoint của kế hoạch, không phải parent task mới trong con số 23 task.

## 4. G0 — revalidation và quyết định async

Output: phụ lục baseline với producer table, delta regression cases, quyết định enablement và danh sách prerequisite có owner.

| Slice | Công việc | Acceptance gate |
|---|---|---|
| G0.1 Inventory | Trace REST direct, MCP, synchronous commit, async enqueue/worker, Anki snapshot/revlog, reset và cutover; ghi identity, validation, lock, revision, commit owner, receipt. | Mọi writer có call graph và transaction owner; phân biệt code tồn tại với service thực sự đang vận hành. |
| G0.2 Regression fixtures | Bổ sung test mapping vào module Study khi triển khai; viết failing cases cho D1–D4; ghi rõ baseline working tree/commit. | Test mới bắt được lỗi cần sửa; unit queue xanh không thay thế MySQL/Redis proof. |
| G0.3 Async disposition | Hướng đề xuất: chặn nhận batch async mới và dùng synchronous rollover cho phiên mới cho tới khi readiness/parity đạt. Giữ receipt, payload và pending history đã tồn tại để reconcile; không tự gửi lại bằng sync khi chưa biết batch cũ đã ghi hay chưa. | Có quyết định và hành vi cho phiên mới, client cũ, pending batch, delayed worker và rollback; API guard cùng frontend guard, không chỉ ẩn caller UI. |
| G0.4 Revalidation | Chạy lại invariants P1-01/P1-02 trên các writer được bật, P2-01 forged-message regression. Nếu async tiếp tục enabled, phải hoàn thành toàn bộ gate async bên dưới. | Không còn active writer bypass revision/scope/lease contract; unresolved pending data có recovery path được kiểm chứng. |

Đây là hướng triển khai được đề xuất; chưa tắt endpoint/worker hoặc thay đổi dữ liệu ở lần lập kế hoạch này. Nếu async được giữ enabled, G0 phải có các proof sau trước khi mở rộng P1/P2:

- Accepted job có durable identity `(user, session, batch)` và payload hash; retry cùng identity/hash trả cùng kết quả, khác hash trả conflict. Một event trùng không được khiến cả batch có event mới bị bỏ qua.
- Worker validate lại authorization/scope, status và revision dưới lock; xử lý invalid event như lỗi của batch, không `continue` rồi ghi phần còn lại. Reset/cutover/suspend hoặc direct/MCP/Anki write sau enqueue phải gây typed conflict theo hợp đồng, không tự replay lên state mới.
- Chốt thứ tự `batch_sequence`, session-global event sequence và progress revision checkpoint. Final commit phải xử lý hết pending batches theo thứ tự hoặc trả trạng thái chờ rõ ràng; partial async batch và synchronous commit không cạnh tranh ghi cùng session.
- Phân biệt admission trước lease deadline với processing sau admission; đặt processing deadline hữu hạn. Client giữ events cho tới khi có durable completion/failure receipt và có thể hỏi lại kết quả sau mất response.
- Redis lock có owner-safe release; job bị pop rồi process chết hoặc không lấy được lock vẫn recover được. DB receipt là căn cứ chống ghi trùng, không dựa riêng vào cache/lock TTL. Fallback in-memory không được đại diện durability trong nhiều process.
- Xác minh worker entrypoint/supervision và schema bằng môi trường MySQL/Redis disposable. DDL cần thiết là prerequisite riêng; P1/P2 không tự thêm migration để vượt scope.

Rollback G0 giữ synchronous path đã kiểm chứng cho phiên mới, dừng admission async mới theo rollout contract và giữ khả năng tra cứu/reconcile batch đã nhận. Không xóa queue/table/history hay tự gọi mọi batch đã nhận là thành công.

## 5. P1-03 — ReviewEvent provenance và payload

Spec: [P1-03](./completed/P1-03_REVIEW_EVENT_PROVENANCE.md). Owner: Backend Study/Connect/Audit. Entry gate: G0 đạt, P1-01/P1-02 invariants giữ nguyên.

| Slice | Công việc cụ thể | Output |
|---|---|---|
| P1-03.1 | Cập nhật producer inventory gồm async worker; phân biệt native REST/MCP/session với external revlog/snapshot/repair. Snapshot hoặc repair không có review event không bị ép tạo event mới. | Before/after inventory và field-authority table. |
| P1-03.2 | Định nghĩa envelope versioned trong `payload_json` hiện có; source do trusted adapter xác định, algorithm/config/action do runtime xác định, session metadata do session owner xác định. Client không được tự nhận source/provenance. | Contract native/external/legacy, allowlist và stable error mapping REST/MCP/import. |
| P1-03.3 | Validate trước mutation; truyền final provenance qua recorder/repository constructor ngay từ đầu. Giữ native mutation core không commit, giữ transaction/savepoint semantics của external import. | Một validation/construction seam; loại broad payload persistence và create-then-relabel còn tồn tại. |
| P1-03.4 | Audit classify complete/missing/conflicting/legacy-unknown; test malformed, oversized, spoofed source và parity. | Bounded payload tests, no-partial-write proof và handoff. |

Giới hạn đề xuất để triển khai kiểm thử: persisted envelope tối đa 16 KiB UTF-8, depth 4, tối đa 64 phần tử/container, string thường 1.024 ký tự; identity có giới hạn riêng theo field hiện có. Chốt các hằng số này bằng fixture inventory trước khi merge; không truncate identity/hash hoặc silently coerce malformed number. Giữ transport cap hiện tại 5 MiB/5.000 events; giới hạn event không thay thế giới hạn aggregate. Không persist raw answer HTML/media/token hoặc trường dư ngoài allowlist.

Files chính: `study_service.py`, `study_session_service.py`, `study_worker_service.py`, `anki_sync_service.py`, `app/repositories/review_event_repository.py`, validator/recorder đang được các producer gọi, `study_architecture_audit_service.py`. Đọc `models/review_event.py` để khớp schema; không thêm column.

Gate: native producer có cùng provenance bắt buộc, external không bị gán Action native; spoofed/oversized/malformed request trả typed error; progress/event/dirty effects không ghi một phần trong native transaction. Import vẫn giữ unit savepoint và partial-success behavior hiện hành. Legacy thiếu thông tin vẫn đọc được, không backfill dữ liệu suy diễn.

Rollback: giữ reader nhận legacy + new envelope đã phát hành; revert writer/validator đồng bộ, không rewrite historical events. Verification: Study backend + Connect/MCP; thêm decks/flashcards nếu thực sự chạm reset/cutover/import ownership.

## 6. P1-04 — Algorithm và decoder retirement

Spec: [P1-04](./completed/P1-04_ALGORITHM_VERSION_RETIREMENT.md). Owner: Backend/Frontend contract. Triển khai sau P1-03; phối hợp với P2-03 vì chung restore/registry files.

1. **P1-04.1:** inventory exact server adapter, worker adapter, client evaluator, snapshot/event/state/config decoders; giữ `legacy-anki/1.0.0` và golden vectors hiện có.
2. **P1-04.2:** viết support matrix và retirement runbook: `active` cho session mới; `deprecated` vẫn hỗ trợ nhưng chờ hết thời gian cấp mới; `lease-only` không cấp mới nhưng xử lý lease/job hợp lệ; `retired` không execute, history vẫn đọc được.
3. **P1-04.3:** registry introspection và typed availability check nhất quán cho open, restore, commit và worker. Không tìm được exact version thì fail closed.
4. **P1-04.4:** test new session, old valid lease, retired restore, history read và deployment rollback; ghi retirement evidence thay vì chỉ đặt ngày xóa code.

Retention dùng các mốc thực tế: latest supported lease expiry (TTL hiện tại 24 giờ) + safety margin; latest processing deadline của accepted jobs nếu async enabled; rollback-support deadline. Chỉ retire sau mốc lớn nhất và không còn work hợp lệ. Safety margin/rollback window phải ghi thành giá trị cụ thể trong ADR khi có số liệu triển khai; chưa giả định IndexedDB cũ đã biến mất. Detail retention 30 ngày không đồng nghĩa phải giữ executable replay 30 ngày.

Files: `app/services/study_algorithm_registry.py`, `frontend/src/features/study/scheduler/algorithmRegistry.ts`, session/worker validity checks, restore tests và runbook. Gate: active supported lease/job còn xử lý được, unknown version không fallback, expired/retired data có error/quarantine ổn định. Rollback: phục hồi exact artifact/registry entry, giữ version ID đã phát hành. Verification: Study backend/frontend và worker cases nếu enabled.

## 7. P2-02 — mutex cho mọi session mutation

Spec: [P2-02](./completed/P2-02_FRONTEND_SESSION_MUTEX.md). Owner: Frontend Study. Entry gate: G0 đã chốt async lifecycle/sequence/receipt contract.

1. **P2-02.1:** inventory answer, undo, restore/open, retry, normal/auto/keepalive commit, takeover/conflict recovery, batch extraction, receipt reconciliation và các thao tác cập nhật persisted session từ quick edit/template cache.
2. **P2-02.2:** một synchronous acquire theo owner token + session/lease generation trước khi đọc state sẽ mutate; release chỉ khi token khớp. Click trùng trả busy/no-op theo callback contract; lifecycle/receipt work cần retry/defer có kiểm soát, không bị bỏ mất.
3. **P2-02.3:** đưa hook và persisted store writes liên quan qua cùng ownership boundary. Background HTTP có thể chạy ngoài critical section với immutable payload; extraction/persist và acknowledgment phải acquire riêng và kiểm tra generation. Không áp dụng response cũ vào session vừa takeover.
4. **P2-02.4:** xử lý page exit dựa trên state lấy sau acquire, không dùng snapshot tạo trước lúc chờ; xác định undo boundary với event đã gửi. Lỗi/abort/unmount không release lock của operation mới, không xóa durable pending work.
5. **P2-02.5:** thêm same-tick/deferred-promise tests: answer+answer, answer+undo, restore+answer, commit+answer, retry+undo, extraction+answer, receipt+undo, pagehide+answer, takeover+late response và stale `finally`.

Files: `useStudySession.ts` và tests, session engine/store/lease helpers, relevant cache update callers. Giữ cross-tab lease hiện có; mutex trong tab không thay lease giữa các tab. Nếu async còn được support, 202 chỉ đánh dấu accepted; statistics/completed receipt và outbox removal phải theo G0 contract.

Gate: tối đa một local mutation owner; không duplicate event/send bởi cùng gesture; live state và durable pending state khớp sau lỗi/reload; ít nhất một test mới fail với implementation cũ. UI, reveal và preview giữ nguyên. Rollback theo một boundary đồng bộ, không để marker và mutex cùng authoritative; pending data vẫn đọc/recover được. Verification: Study frontend.

## 8. P2-03 — restore validation và quarantine

Spec: [P2-03](./completed/P2-03_RESTORE_VALIDATION_QUARANTINE.md). Owner: Frontend Session Storage. Thực hiện sau P2-02 để dùng cùng mutation ownership.

| Slice | Nội dung | Gate cụ thể |
|---|---|---|
| P2-03.1 | Inventory persisted v2, pending commit và pending batch hiện có; giữ `batch_sequence`/`in_flight_batches` khi normalize/save/load. | Round-trip không mất pending work; thiếu metadata không được đổi thành “không có history”. |
| P2-03.2 | Validate UUID/uniqueness, strict numeric types, sequence, scope/session/card membership, exact policy/algorithm, semantic metadata all-or-none và lease-bounded offset. | Cấm duplicate/gap/reorder, string-number coercion, non-finite/overflow và partial semantic mismatch trước hydration. |
| P2-03.3 | Full v2 event log giữ `1..N`. Nếu support pending partial batches, kiểm tra toàn logical log/checkpoint theo G0, không bắt từng fragment tự bắt đầu 1 và không renumber event IDs/sequences. | Same event không nằm ở cả pending batch và active suffix; không replay phần đã được server xác nhận. |
| P2-03.4 | Atomic move active → quarantine, bounded size và một record/scope; load phải nhận ra quarantine hiện có cả sau reload. IDB abort/quota failure có stable blocked state. | Repeated restore không tự mở session thay thế hoặc recommit invalid data. |
| P2-03.5 | Valid current/legacy/pending fixtures + invalid matrix + crash/reload/storage-failure integration. | Valid legacy metadata thiếu toàn bộ vẫn normalize; ambiguous history bị giữ lại để chẩn đoán. |

Đối chiếu scope key với user/scope mà caller yêu cầu; kiểm tra association trên envelope hiện có, không bắt legacy event tự có một field session ID chưa từng tồn tại. Offset lấy lease material của snapshot, không suy từ thời điểm reload. Quarantine reason ổn định và metadata chẩn đoán không chứa answer content; raw evidence cục bộ phải bị giới hạn theo documented storage policy.

Files: `sessionRestore.ts`, `sessionStore.ts`, engine/types nếu cần và hook integration tests. Rollback giữ additive IndexedDB compatibility, không tự đưa quarantined row trở lại active store. Verification: Study frontend, gồm lossless pending-batch round-trip.

## 9. P2-04 — một semantic Interaction callback

Spec: [P2-04](./completed/P2-04_SEMANTIC_INTERACTION_CONTRACT.md). Owner: Frontend Study UI. Dùng busy/undo semantics đã chốt ở P2-02.

1. **P2-04.1:** inventory controls, bottom bar, page và keyboard callers; chốt discriminated Action identity để không tạo tổ hợp như `review.good` với Trigger `again`.
2. **P2-04.2:** reusable UI chỉ emit `onReviewAction`; bỏ public `onAnswer` và phụ thuộc raw scheduler rating khỏi Action UI contract. Interval labels là display data.
3. **P2-04.3:** Action → legacy rating ở một named adapter tại session boundary; event/trigger identity đối chiếu P1-03. Cập nhật caller/type tests cùng lượt, không duy trì hai callbacks sau merge.
4. **P2-04.4:** single-emission và exact-mapping tests cho cả bốn nút, reveal/disabled/undo/keyboard; so sánh trước/sau trên mobile/desktop.

Files: `interactions/reviewInteraction.ts`, `ReviewInteractionControls.tsx`, `StudyBottomBar.tsx`, `StudyPage.tsx`, adapter và tests. Gate: một gesture tạo đúng một action, raw rating chỉ nằm ở compatibility boundary; giữ button order/labels/colors/gradient/spacing/font/icons/shadows/layout. Rollback type/caller/adapter đồng bộ; không đổi backend wire trong task này. Verification: Study frontend + visual evidence với browser profile riêng.

## 10. P2-05 — trusted keyboard decision

Spec: [P2-05](./completed/P2-05_TRUSTED_KEYBOARD_UX.md). Owner: Frontend Security. Dependency: P2-01 + P2-04.

1. **P2-05.1:** ADR threat model cho sandbox/origin, same-realm Template JS, forged messages, event synthesis/monkey patch, editable content và IME.
2. **P2-05.2:** so sánh no-bridge với browser-enforced isolated input mechanism. Hướng đề xuất là giữ no-bridge: parent UI hỗ trợ phím tắt, focus trong iframe không forward Action lên parent.
3. **P2-05.3:** verify parent/iframe focus, input/textarea/contenteditable, IME, key repeat, modifier, focus transition và forged frame messages bằng browser profile riêng; lưu evidence.

Gate: Template không thể reveal/answer/undo hoặc gây progress write qua message. Không dùng nonce/child-supplied `isTrusted`/`event.source` như chứng minh user input. Task có thể đóng bằng no-bridge ADR + tests; shortcut trong iframe chỉ được triển khai nếu có trust proof tương ứng. Rollback luôn về no-bridge, không phục hồi `host_command` cũ. Verification: Study frontend + real browser, không dùng Chrome profile cá nhân.

## 11. P2-06 — Trigger Runtime design checkpoint

Spec: [P2-06](./completed/P2-06_TRIGGER_RUNTIME_DESIGN.md). Owner: Backend/contract design. Dependency: P1-03 + P2-04. Đây là task thiết kế, không tự triển khai generic dispatcher.

1. **P2-06.1:** map Action → allowlisted built-in Trigger → exact Algorithm → non-committing native mutation core. Bao gồm sync adapter và worker adapter nếu worker được bật.
2. **P2-06.2:** ADR so sánh permanent four-rating adapter với minimal exact-version dispatcher; typed input/output, authorization owner, version/error/idempotency matrix, client-evaluates/server-verifies boundary.
3. **P2-06.3:** chốt một primary transaction owner cho progress/event/required effects. Async review queue là transport của primary command, không phải secondary Trigger effect. Follow-up chỉ dispatch sau primary commit; deferred nếu cần durable storage mới ngoài scope.
4. **P2-06.4:** ghi accepted/deferred decision và bounded implementation slice nếu cần. P2-07 chỉ bắt đầu khi required semantics có đường execute/verify thực tế; nếu ADR chọn dispatcher mới, hoàn tất follow-up đó trước v3 rollout.

Output: ADR trong `docs/architecture/`, responsibility table, primary/follow-up sequence, approved identities và phần defer Phase 3/4. Gate: không arbitrary handler name/custom code, không thêm progress authority, unknown Trigger/version fail closed, retry không nhân đôi required effects. Documentation-only slice không cần chạy runtime tests; implementation follow-up phải có Study parity/idempotency tests. Chỉ đánh dấu P2-06 completed khi decision đã được review, không phải khi mới có draft ADR.

## 12. P2-07 — wire v3 và v2 lease compatibility

Spec: [P2-07](./completed/P2-07_WIRE_V3_LEGACY_V2_POLICY.md). Owner: Backend + Frontend contract. Dependency: P1-04 + P2-03 + P2-06.

| Slice | Công việc | Output/gate |
|---|---|---|
| P2-07.1 | Freeze inventory `study-session.v2`, `study-commit.v1`, `study-batch.v1`, job và receipt shapes; chốt bảng mapping từng version với pinned session. | Không coi snapshot version là version chung cho mọi envelope. |
| P2-07.2 | V3 yêu cầu Action identity/version, Trigger identity/version, Algorithm/config, session/event/sequence; Python/TS dùng discriminated validators và shared valid/invalid fixtures. | Reject missing/mismatched/unknown identity trước mutation; session binding là authoritative, không tin client chọn decoder khác. |
| P2-07.3 | Deploy server và worker dual-reader trước; giữ client creation v2 mặc định; chỉ bật v3 creation sau compatibility gate. | Supported readers đã có trên mọi consumer, không chỉ HTTP server. |
| P2-07.4 | Đo active v2 leases, accepted jobs nếu có, unsupported/restore outcomes bằng metadata không chứa answer content. Retirement theo P1-04. | Không hết hỗ trợ chỉ vì đã qua 24 giờ kể từ deploy. |
| P2-07.5 | Test deployment/rollback matrix, cập nhật API/retention runbook và handoff. | Old/new client, restore, delayed job và rollback có kết quả xác định. |

Version matrix tối thiểu:

| Trường hợp | Kết quả yêu cầu |
|---|---|
| Client v2 → dual-reader server | Open/restore/commit hợp lệ theo window; semantic metadata partial không được chấp nhận ngầm. |
| Client v3 → dual-reader server | Pinned v3 contract, mandatory metadata và exact dispatcher/adapter. |
| Client mới restore IndexedDB v2 | Dùng v2 decoder trong supported window, không rewrite IDs hoặc heuristic upgrade wire. |
| Client mới → server cũ | Capability check chỉ tạo version server hỗ trợ; không gửi v3 rồi retry mù thành v2. |
| Unknown wire/Trigger/Algorithm | Typed failure/quarantine, không fallback latest. |
| V2 hết hạn hoặc retired | History giữ readable; không tự replay vào lease mới. |
| Rollback sau khi đã cấp v3 leases | Tắt tạo v3 mới nhưng rollback target vẫn giữ v3 reader/exact artifacts; không quay về binary chỉ biết v2. |
| Worker xử lý job được nhận trước deploy | Pinned version và processing deadline vẫn được kiểm chứng; chỉ áp dụng khi async enabled. |

Files: session routes/service, worker/queue envelopes nếu supported, frontend types/engine/restore/queries/registry và contract tests. Snapshot v3 dùng metadata storage hiện có; bất kỳ schema prerequisite nào phải tách ra. Gate: toàn bộ matrix pass, existing v2 lease không mất dữ liệu, new v3 không thiếu semantic metadata và rollback giữ reader cho versions còn sống. Không contract v2 hoặc xóa executable trong task này khi retirement evidence chưa đủ.

## 13. File ownership, verification và closeout

| File/boundary dùng chung | Thứ tự merge |
|---|---|
| `study_service.py`, event recorder/repository | G0 regression/hardening nếu cần → P1-03 → P2-06 follow-up nếu được chọn |
| `study_session_service.py`, session routes, worker | G0 → P1-03 → P1-04 → P2-07 |
| `useStudySession.ts`, engine/store/restore/types | G0 containment nếu cần → P2-02 → P2-03 → P1-04 integration → P2-04 → P2-07 |
| Controls/page/keyboard | P2-04 → P2-05; giữ P2-01 regression |
| `scripts/run_tests.py` | Một thay đổi mapping tập trung ở G0, bảo toàn unrelated working-tree edits |

Verification khi triển khai, chạy từ repo root trên Windows; dùng Python của `.venv` vì alias `python` hiện trỏ Microsoft Store:

```powershell
.venv\Scripts\python.exe scripts/run_tests.py --module study --backend-only
.venv\Scripts\python.exe scripts/run_tests.py --module study --frontend-only
.venv\Scripts\python.exe scripts/run_tests.py --module connect_mcp --backend-only
.venv\Scripts\python.exe scripts/run_tests.py --module decks,flashcards --backend-only
.venv\Scripts\python.exe scripts/run_tests.py --changed
```

Chỉ chọn module bị ảnh hưởng theo từng task. Cho tới khi mapping được bổ sung, worker có focused fallback `.venv\Scripts\python.exe -m unittest tests.test_study_batch_queue`; sau đó runner phải chọn cả suite này. Tất cả regression suite mới cần thêm vào mapping, không chỉ test queue. `.venv`/unittest không chứng minh real Redis/MySQL: cần disposable multi-connection/multi-process tests khi thay conflict/queue behavior. Startup/schema prerequisite, nếu có, phải kiểm tra `wsgi.py`/Docker trong môi trường disposable; audit production dùng đường audit read-only đã chốt ở P0-03.

**G-END — tiêu chí bàn giao P1/P2:**

- Tám task có output, acceptance evidence và rollback tương ứng; task thiết kế có decision đã review, runtime task có test đúng branch hành vi.
- Các invariant P1-01/P1-02/P2-01 được tái kiểm chứng trên writer/consumer được phép chạy. Async enabled hoặc contained có disposition và pending-data proof rõ ràng.
- Study backend/frontend, Connect/MCP và các module thực sự bị chạm đều pass; mapping không bỏ sót tests mới. Visual/keyboard tests có isolated-browser evidence; concurrency gate có evidence đúng DB/queue khi áp dụng.
- Không duplicate event builder, không broad unvalidated history payload, không hai UI callbacks, không marker mutex giả, không invalid restore hydration, không unknown-version fallback.
- Handoff ghi commit, working-tree scope, API changes, commands/results, known limitations và follow-up IDs. Chỉ sau gate mới đổi status/move task vào `completed/` và sửa tracker links.
- G-END chỉ bàn giao P1/P2. Phase 3, INT-01 và approval riêng cho schema vẫn cần hoàn tất trước khi xem xét Phase 4.

## 14. G-END completion — 2026-09-08

Tám task trong phạm vi kế hoạch đã hoàn tất theo code/test evidence. Báo cáo
canonical: [P1/P2 execution closeout](./completed/P1_P2_EXECUTION_CLOSEOUT_2026-09-08.md).

G0 chọn containment: frontend không tạo async rollover mới; `/batch` và
`commit?async` trả `ASYNC_BATCH_DISABLED` theo mặc định. Code worker/dual reader
được giữ để đọc dữ liệu/version đã phát hành, nhưng không được xem là production
ready nếu chưa có migration, owner-safe Redis lock, supervised consumer, durable
receipt reconciliation và disposable MySQL/Redis proof.

G-END đã chạy Study backend, Study frontend, Connect/MCP, Deck/Flashcards,
frontend typecheck/lint, focused owner-note regression và `git diff --check`.
Browser keyboard evidence dùng isolated Playwright session. Không có model,
migration, progress authority, overlay model hoặc CSS/layout nào bị thay đổi.

P1/P2 hoàn tất không đồng nghĩa Phase 0–3 hoàn tất. Bước tiếp theo vẫn là các
quyết định P3-05/P3-07, sau đó P3-01..P3-06 và cuối cùng INT-01.
