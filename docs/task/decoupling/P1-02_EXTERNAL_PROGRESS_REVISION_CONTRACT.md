# P1-02 — External progress revision and conflict contract

> Phase: 1
>
> Priority: P1
>
> Status: TODO
>
> Dependency: P1-01
>
> Primary lane: Backend Connect / Import / Share

## Mục tiêu

Định nghĩa và áp dụng revision/conflict semantics nhất quán cho các path có thể thay đổi current progress ngoài native Study: Anki snapshot, revlog import, Flama Connect, import/cutover và clone repair.

## Bối cảnh

Native Study dùng lock/revision contract rõ hơn các external mutation paths. Nếu các path ngoài Study cập nhật progress mà không tham gia cùng concurrency rule, offline session hoặc MCP/direct review có thể ghi đè state mới hơn.

## Phạm vi file cần trace

- `app/services/anki_sync_service.py`
- `app/services/anki_import_service.py`
- `app/services/flama_connect_service.py`
- `app/services/connect/`
- `app/services/share/cutover.py`
- `app/services/flashcards_share_service.py`
- `models/connect_*.py`
- progress/review repositories liên quan
- `tests/test_anki_import_api.py`
- `tests/test_flama_connect_mcp.py`
- clone/cutover tests liên quan

## Công việc chi tiết

1. Lập mutation inventory: path, input identity, lock, revision read/write, event provenance, commit owner.
2. Phân biệt rõ:
   - user interaction review;
   - external snapshot replacement;
   - external revlog event import;
   - clone/cutover repair;
   - idempotent no-op sync.
3. Chốt conflict matrix giữa:
   - native direct/MCP;
   - open offline/batch session;
   - Anki snapshot;
   - Anki revlog;
   - import/cutover/repair.
4. Mỗi mutation phải:
   - lock hoặc verify revision theo contract;
   - increment/preserve revision đúng quy tắc;
   - emit typed conflict thay vì last-write-wins ngầm;
   - ghi source/provenance chính xác;
   - không gọi native Action semantics nếu đây là state sync.
5. Giữ idempotency qua external IDs/content hashes hiện có.
6. Định nghĩa behavior khi history incomplete hoặc snapshot cũ hơn current state.
7. Test concurrent native review vs từng external path quan trọng.
8. Test logical overlay identity: source/local Card đều resolve đúng current progress subject hiện tại mà không mutate source content.

## Output đầu ra bắt buộc

- Mutation inventory table đầy đủ.
- Approved conflict/priority matrix.
- Code áp dụng revision semantics cho in-scope paths.
- Typed conflict/result codes và tests.
- Provenance mapping native vs snapshot vs revlog vs repair.
- Remaining unknowns cho production data/history completeness.

## Acceptance criteria

- Không external path nào silently overwrite một newer committed state.
- Idempotent replay không increment revision hoặc tạo duplicate event ngoài contract.
- Open session conflict được phát hiện theo frozen base revision.
- Source/local clone identity không bị collapse sai và source Notes/Cards không bị mutate.
- Không giả nhãn imported snapshot thành native Algorithm execution.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module connect_mcp --backend-only
python scripts/run_tests.py --module decks,flashcards --backend-only
```

## Rollback

Không đổi schema. Có thể feature-flag conflict enforcement theo external path nếu cần rollout, nhưng không được quay lại silent last-write-wins sau khi task được đóng.

## Không làm trong task này

- Không thiết kế learner/Note progress.
- Không reconstruct state từ deleted import staging.
- Không thay đổi clone model thành physical copy.
- Không triển khai Algorithm switching.
