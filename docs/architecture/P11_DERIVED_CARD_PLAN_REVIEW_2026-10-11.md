# Review kế hoạch Claude Code: P11 Card dẫn xuất — 2026-10-11

> Mode: INVESTIGATE / review proposal. Input: bản kế hoạch người dùng đính kèm trong `Pasted text.txt`. Đối chiếu ứng dụng tại HEAD `cdbd1cc5`, đọc thêm commit P11-0 `1bcfebaa`. Không sửa ứng dụng, schema hoặc dữ liệu thật; không phê duyệt triển khai production.

## Kết luận

Hướng bỏ materialization của mọi cặp Note × application có cơ sở: tiến độ NOTE đã thuộc về learner × Note, và thêm presentation không cần tạo tiến độ riêng. Lưu membership/artifact cho các phiên thực sự mở cũng có cơ sở. Tuy nhiên, proposal chưa đủ để chuyển reader/writer an toàn: có hai phản ví dụ clone đã tái hiện, các identity được hash trong lease/receipt cần giữ nguyên, inventory schema và điều kiện cutover còn thiếu.

Không xác nhận lại các số 41.533 dòng, 100/161 ms, 397/737 ms hoặc dự đoán attach dưới 1 s: input chưa kèm script/dump watermark/EXPLAIN/lock trace để lần review này tái kiểm chứng. Parity trên một dump không chứng minh các semantics temporal, pinned-release, retire/reactivate và partial deletion.

## Findings

### R1 — P1: dùng `application.created_at` làm snapshot cutoff sẽ đổi dữ liệu clone cũ

- **Observed:** Clone fallback hiện kiểm tra `Note.created_at` và `Card.created_at`. Migration 46 backfill application bằng thời điểm migration (`now`), không phải thời điểm Card/template bắt đầu tồn tại. Hai timestamp không tương đương.
- **Evidence:** `app/services/flashcards_share_service.py:3006`, `:3052`; `migrations/versions/20260930_000046_add_study_applications.py:115`, `:135`. Reproducer SQLite: clone trước thời điểm application được tạo, Note/Card đã có từ trước → code hiện tại trả 3, filter đề xuất trả 0.
- **Potential concern:** Kết luận “Card không mang thêm thông tin gì” bỏ qua thời điểm từng presentation được tạo, đặc biệt dữ liệu trước migration application.
- **Impact:** Clone legacy snapshot mất những presentation hợp lệ nếu reader thay Card timestamp bằng application timestamp trực tiếp.
- **Unknowns:** Số install đang dùng timestamp fallback và phân phối timestamp production chưa kiểm chứng. Kế hoạch phải nêu rõ cách bảo toàn cutoff cũ trước khi chuyển reader; chưa chốt phương án schema trong review này.

### R2 — P1: join chỉ application ACTIVE không bảo toàn release đã ghim

- **Observed:** Source scope của install có `template_pins_initialized` chọn application IDs từ `DeckReleaseTemplatePin.applications_json`, không lọc theo status ACTIVE hiện tại. Local-added/owned scope dùng ACTIVE. Tác giả retire application không tự thay manifest của release cũ.
- **Evidence:** `app/services/flashcards_share_service.py:2988`, `:2993`, `:3000`, `:3016`; `models/deck_release_template_pin.py`. Reproducer SQLite: source application RETIRED, release của install vẫn pin nó → reader hiện tại trả 3; join chỉ ACTIVE trả 0.
- **Potential concern:** Proposal dùng một công thức `notes ⋈ applications ACTIVE` cho queue/Browse/count, và mô tả clone snapshot chỉ bằng created_at.
- **Impact:** Mất presentation của release cũ; binding/default/order/presentation source có thể bị lấy từ draft hiện tại thay vì release pin. Đây là thay đổi hành vi overlay, không chỉ tối ưu query.
- **Unknowns:** Chưa kiểm kê toàn bộ dạng legacy/source/local và empty initialized manifest. Gate cần kiểm tra cùng applied release, overlay-added/disabled fields và binding/artifact snapshot, không chỉ đếm Card.

### R3 — P1: alias UUID → pair key chưa đủ bảo toàn replay

- **Observed:** ID là chuỗi ở frontend, nhưng vẫn là identity được dùng trong membership và material hash. Session membership so khớp đúng ID; snapshot hash chứa card payload. Command receipt fingerprint chứa `card_id`; direct replay còn kiểm tra ID của event và index vào projected revisions bằng ID đó.
- **Evidence:** `app/services/study_session_service.py:977`, `:1616`, `:1682`, `:1901`; `app/services/study_authority_receipt_service.py:163`, `:309`; `app/services/study_direct_note_replay_service.py:112`, `:144`, `:159`; `frontend/src/features/study/session/sessionRestore.ts:160`, `:267`.
- **Potential concern:** Đọc ID cũ qua alias rồi thay nó bằng `<note>.<application>` trong response/command của lease hoặc retry cũ sẽ đổi material đã freeze.
- **Impact:** Có thể gặp `CARD_OUTSIDE_SESSION`, `AUTHORITY_OPERATION_REUSED`, mismatch event/receipt hoặc quarantine client. Không rewrite các receipt/fact/snapshot cũ chỉ để đồng nhất ID.
- **Unknowns:** Proposal chưa mô tả cụ thể giữ wire identity cũ và internal normalized identity ra sao. Chưa chứng minh cần wire v5; có thể giữ wire hiện có nếu dual-reader và các hash/lease contracts được bảo toàn, nhưng “không kiểm UUID” chưa chứng minh điều đó.

### R4 — P2: inventory schema thiếu quyết định về Connect/LEGACY và thứ tự mở ID mới

- **Observed:** Có **3** FK tới `cards.id`: `study_session_cards.card_id` CASCADE, `connect_source_card_refs.card_id` SET NULL, `card_progress.card_id` CASCADE. Ba cột này dài 36 ký tự; `review_events.card_id` dài 64. Key gồm hai UUID và dấu chấm dài 73 ký tự.
- **Evidence:** ORM metadata probe; `models/study_session_card.py:18`; `models/connect_source_card_ref.py:37`; `models/card_progress.py:15`; `models/review_event.py:14`.
- **Potential concern:** “Chỉ bỏ 2 FK, nới session/event” chưa giải thích FK thứ ba được giữ làm alias legacy hay retired, và Connect ref lưu pair key hay chỉ lưu Note/ordinal. P11-2 chuyển reader trước P11-3 đổi schema có thể phát ID mới quá sớm.
- **Impact:** Connect ghi key 73 vào cột 36 hoặc session ghi key mới trước expand sẽ thất bại. Nếu giữ LEGACY writer khi alias ngừng tạo, nó không có Card mới để lưu tiến độ.
- **Unknowns:** Không mặc định phải drop cả ba FK: có thể giữ FK `card_progress` trên UUID alias cũ nếu contract LEGACY cho phép. Cần disposition rõ cho từng consumer/cột, schema expand trước khi phát key dài, và DDL rehearsal trên MySQL thật. SQLite không kiểm chứng thuật toán/lock DDL hoặc enforcement độ dài VARCHAR của MySQL.

### R5 — P2: thiếu gate khi dừng ghi và giới hạn rollback

- **Observed:** Code cũ tạo Note/application rồi materialize Card; reader cũ tra bảng Card. Khi P11-4 dừng materialize, các cặp mới không có UUID alias trong bảng cũ.
- **Evidence:** `app/repositories/template_library_repository.py:120`, `:127`; `app/services/template_library_service.py:351`, `:366`; session/Connect/Browse consumers trong [review hiện trạng](CARD_TEMPLATE_DECOUPLING_REVIEW_2026-10-11.md).
- **Potential concern:** Bảng alias chỉ giải quyết ID của dữ liệu đã tồn tại, không làm code cũ hiểu Note/application được tạo sau cutover.
- **Impact:** Rollback application về release chỉ đọc Card có thể làm dữ liệu mới biến mất khỏi luồng học; mixed main/Connect/worker releases có thể hành xử khác nhau.
- **Unknowns:** Proposal chưa có writer manifest=0, deployment gate cho mọi process, restore rehearsal và release thấp nhất được rollback về. Cần đặt các điều kiện này trước P11-4; không suy ra rollback an toàn chỉ vì bảng `cards` vẫn còn.

### R6 — P11-0 có cơ sở trong phạm vi thêm sibling; chưa phải bằng chứng mọi fence thừa

- **Observed:** `prepare_content_expansion` trả plan rỗng và `finalize_content_expansion` chỉ đánh dấu finalized ở HEAD. Scope recheck vẫn chạy locking reads. Commit `1bcfebaa` bỏ expansion helpers và giữ learner fence của Connect khi có removal. Deletion/reset vẫn tombstone progress và hủy session.
- **Evidence:** `app/services/study_content_delete_service.py:65`, `:94`, `:134`, `:214`, `:219`, `:231`; diff commit `1bcfebaa`, đặc biệt `connect/import_cards.py` chỉ bỏ fence khi không có `removed_ids`.
- **Potential concern:** Gọi chung là “gỡ fence chết dưới mọi mô hình” dễ bị áp dụng cả vào deletion/rekey/reset. Số đo khóa mọi dòng trong commit message là evidence được báo cáo, chưa được chạy lại trong lần review này.
- **Impact:** P11-0 nên review/ship riêng với whitelist addition paths và giữ các khóa cần cho mutation khác. Nó vẫn tạo O(N) Card; không thay thế P11-1..4.
- **Unknowns:** Chưa chạy MySQL concurrency probe cho commit này. Gate nên có attach/create-template cùng review của learner khác; tạo/import Note cùng thay attachment; removal/mixed add-remove; rollback transaction; current locks và SQL count. Không khẳng định đã có race regression chỉ từ việc bỏ lock.

### R7 — P2 lỗi viện dẫn: D6-05 đã chọn B, không phải lời hẹn purge của phương án A

- **Observed:** D6-03 đúng là chọn Card occurrence và giữ wire/projection/rollback. Tuy nhiên, update accepted ở đầu P6 ghi D6-05 = B (hard-delete và chuyển lineage sang Note). Câu “purge vật lý để Phase 9” thuộc cột đề xuất A bị thay bởi B.
- **Evidence:** `docs/task/decoupling/P6_EXECUTION_PLAN_2026-09-29.md:3`, `:8`, `:63`, `:65`, `:76`; P10-09 retired rollback code.
- **Potential concern:** Đọc bảng lựa chọn lịch sử mà bỏ update accepted làm sai động cơ và scope đã được duyệt.
- **Impact:** ADR P11 cần lập luận từ authority hiện tại và các consumers còn tồn tại. Việc đóng rollback NOTE→LEGACY gỡ một lý do cũ, không tự xóa nghĩa vụ lease/Connect/release compatibility.
- **Unknowns:** Không có ADR P11 accepted trong input; review không tự đổi quyết định sản phẩm trước đó.

## Counterexamples đã chạy

Fixture `tests/test_study_session_install_usage.py` với SQLite in-memory, 3 source Notes/Card có created_at một ngày trước; application có created_at mới. Legacy case đặt snapshot 12 giờ trước, tương đương install trước application backfill. Pinned case tạo release/template pin trong DB tạm rồi retire application. Probe assertions pass, exit 0:

```json
{
  "legacy_snapshot_case": {"existing_clone_count": 3, "proposed_created_at_filter_count": 0},
  "retired_pinned_case": {"existing_clone_count": 3, "naive_active_join_count": 0},
  "cards_foreign_keys": [
    {"column": "card_progress.card_id", "on_delete": "CASCADE"},
    {"column": "connect_source_card_refs.card_id", "on_delete": "SET NULL"},
    {"column": "study_session_cards.card_id", "on_delete": "CASCADE"}
  ],
  "proposed_pair_key_length": 73
}
```

Đây là probe semantics/inventory, không benchmark P11 implementation, không kiểm tra VPS và không chứng minh dữ liệu production đã có các ca đó. Tám cờ study async/wire/new-learner/note-count/shadow được ép 0 ở process probe; fixture bật NOTE theo contract của nó. Các source/test không bị sửa.

## Điều kiện cần bổ sung vào kế hoạch trước triển khai

1. Pair identity và alias phải có disposition cho lookup, wire, old lease, direct/batch retry, event/fact/receipt và authorization owned/install/local. UUID alias và pair key không được coi là interchangeable ở material đã hash.
2. Parity theo membership và render/binding/availability, không chỉ row count; phải bao gồm pinned retired application, legacy timestamp, zero initialized manifest, repeated occurrence, rename/type change, overlay và partial delete.
3. Schema expand trước khi có writer/response dùng key mới; P11-2 chỉ giữ ID cũ nếu P11-3/schema chưa được deploy.
4. P11-4 chỉ mở khi mọi writer/listener/startup/CLI/Connect/worker đã được kiểm kê và qualify, cùng backup/restore và rollback boundary.
5. Chốt các thay đổi sản phẩm proposal đã nêu: partial Card delete, thứ tự thẻ mới và admin counts. “Chặn xóa một phần” không giải quyết dữ liệu đã thiếu cặp nếu có ca đó; audit cần chặn hoặc có disposition trước cutover, không tự sinh lại presentation người dùng từng xóa.

Trạng thái git: P11-0 có commit `1bcfebaa` trên `worktree-p11-derived-card`, không thuộc HEAD đang review. Worktree P11 đang có nhiều thay đổi chưa commit và đang được Claude xử lý; không chạy test trên trạng thái đang thay đổi hoặc coi nó là release đã hoàn tất. Lần review trước tại HEAD đã có 46 test tập trung PASS; không dùng kết quả đó để chứng nhận implementation P11.

Kết luận review: tiếp tục ADR/P11 theo hướng dẫn xuất; revise R1–R5 trước khi mở reader/writer cutover. P11-0 là thay đổi riêng có cơ sở, cần qualify phạm vi addition/concurrency; các quyết định sản phẩm còn pending phải giữ pending.
