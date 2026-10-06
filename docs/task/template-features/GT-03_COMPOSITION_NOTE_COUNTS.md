# GT-03 — Số note theo kiểu thẻ của deck (`include_counts`, Contract B)

- Owner: Gemini. Reviewer: Claude (review kỹ: file thuộc module study). Milestone: M1. Phụ thuộc: CT-00.
- Loại: backend Python, read-only, additive.

## 1. Bối cảnh

Endpoint `GET /api/study/scopes/<scope_type>/<scope_id>/compositions` nằm trong `app/routes/flashcards/study.py` (hàm `study_scope_compositions`, khoảng dòng 793-837, commit `faa3c7d`). Đoạn cuối hiện tại:

```python
    compositions = list_available_compositions_for_query(
        query,
        clone_scope=clone_scope,
    )
    groups = group_available_compositions(compositions)
    return jsonify({
        "schema_version": COMPOSITION_SCOPE_SCHEMA_VERSION,
        "scope_type": normalized_scope,
        "scope_id": scope_id,
        "cardinality": (
            "zero" if not compositions else "one" if len(compositions) == 1 else "many"
        ),
        "default_composition_id": (
            compositions[0].composition_id if len(compositions) == 1 else None
        ),
        "groups": [group.to_dict() for group in groups],
        "compositions": [c.to_dict() for c in compositions],
    })
```

`request` đã được import ở đầu file (`from flask import jsonify, request, ...`).

Trong `app/services/study_composition_service.py`, hàm `list_available_compositions_for_query(query, *, clone_scope)` (khoảng dòng 231-305) nhóm Card theo `(Card.template_id, Note.deck_id, Note.user_id)` và quy ra `context_kind`:

```python
        context_kind = CONTEXT_OWNED
        if clone_scope is not None:
            is_local = (
                deck_id is not None
                and int(deck_id) in local_deck_ids
                and int(note_user_id) == int(clone_scope.install.user_id)
            )
            context_kind = (
                CONTEXT_INSTALLED_LOCAL if is_local else CONTEXT_INSTALLED_SOURCE
            )
```

Mỗi `AppliedComposition` có `composition_id`, `template_id`, `context_kind`. `AppliedComposition.to_dict()` được freeze vào session học, nên **tuyệt đối không** thêm field vào dataclass này.

## 2. Mục tiêu

1. Thêm hàm `count_notes_by_composition` vào `study_composition_service.py`.
2. Endpoint chỉ thêm key `note_counts` khi query string `include_counts` là `1`, `true` hoặc `yes` (không phân biệt hoa thường). Không có tham số → response giống hệt hiện tại.

## 3. File được sửa

| File | Được làm gì |
|---|---|
| `app/services/study_composition_service.py` | Thêm **một** hàm mới ngay sau `group_available_compositions`. Không sửa hàm nào khác. |
| `app/routes/flashcards/study.py` | Chỉ sửa đoạn `return jsonify({...})` cuối hàm `study_scope_compositions` như §4.2. |
| `tests/test_composition_note_counts.py` | Tạo mới. |
| `tests/test_study_session_install_usage.py` | Chỉ **thêm** một method test ở cuối lớp `StudySessionInstallUsageTests`. Không sửa dòng có sẵn. |

CẤM: `AppliedComposition`, `CompositionGroup`, `list_available_compositions_for_query`, `resolve_composition_selection`, `_build_study_scope_query`, endpoint mở phiên học, frontend, mọi file khác.

## 4. Cài đặt chính xác

### 4.1 Service

```python
def count_notes_by_composition(
    query: Any,
    *,
    clone_scope: flashcards_share_service.CloneDeckScope | None,
    compositions: list[AppliedComposition],
) -> dict[str, int]:
    """Count distinct Notes per composition inside one effective scope query.

    ``compositions`` must come from ``list_available_compositions_for_query``
    for the same query and clone scope. Every composition id gets a count.
    """

    counts = {item.composition_id: 0 for item in compositions}
    if not compositions:
        return counts
    key_to_id = {
        (str(item.template_id), item.context_kind): item.composition_id
        for item in compositions
    }
    eligible_card_ids = (
        query.with_entities(Card.id.label("card_id"))
        .order_by(None)
        .subquery()
    )
    rows = (
        db.session.query(
            Card.template_id,
            Note.deck_id,
            Note.user_id,
            db.func.count(db.distinct(Card.note_id)),
        )
        .join(Note, Card.note_id == Note.id)
        .filter(Card.id.in_(db.session.query(eligible_card_ids.c.card_id)))
        .order_by(None)
        .group_by(Card.template_id, Note.deck_id, Note.user_id)
        .all()
    )
    local_deck_ids = (
        set(clone_scope.local_deck_ids) if clone_scope is not None else set()
    )
    for template_id, deck_id, note_user_id, note_count in rows:
        context_kind = CONTEXT_OWNED
        if clone_scope is not None:
            is_local = (
                deck_id is not None
                and int(deck_id) in local_deck_ids
                and int(note_user_id) == int(clone_scope.install.user_id)
            )
            context_kind = (
                CONTEXT_INSTALLED_LOCAL if is_local else CONTEXT_INSTALLED_SOURCE
            )
        composition_id = key_to_id.get((str(template_id), context_kind))
        if composition_id is None:
            continue
        counts[composition_id] += int(note_count or 0)
    return counts
```

Mỗi Note chỉ có một `deck_id` và một `user_id`, nên cộng số note khác nhau theo từng nhóm `(deck_id, user_id)` là chính xác.

### 4.2 Route

Thay `return jsonify({...})` cuối hàm bằng:

```python
    payload = {
        "schema_version": COMPOSITION_SCOPE_SCHEMA_VERSION,
        "scope_type": normalized_scope,
        "scope_id": scope_id,
        "cardinality": (
            "zero" if not compositions else "one" if len(compositions) == 1 else "many"
        ),
        "default_composition_id": (
            compositions[0].composition_id if len(compositions) == 1 else None
        ),
        "groups": [group.to_dict() for group in groups],
        "compositions": [c.to_dict() for c in compositions],
    }
    include_counts = str(request.args.get("include_counts") or "").strip().lower()
    if include_counts in {"1", "true", "yes"}:
        from app.services.study_composition_service import count_notes_by_composition

        payload["note_counts"] = count_notes_by_composition(
            query,
            clone_scope=clone_scope,
            compositions=compositions,
        )
    return jsonify(payload)
```

Thứ tự key và giá trị của các key cũ không đổi.

## 5. Test bắt buộc

### 5.1 `tests/test_composition_note_counts.py` (service)

Harness: sao chép nguyên `setUp`/`tearDown` của `StudyCompositionServiceTests` trong `tests/test_study_composition_service.py` (dòng 27-95: user, NoteType, `template_1` pos 0 default, `template_2` pos 1, `deck`, `note`, `card_1` = (note, template_1)). Tên lớp `CompositionNoteCountTests`. Import: `count_notes_by_composition`, `list_available_compositions_for_query`, `make_compatibility_composition_id`, `make_installed_composition_id`, `CONTEXT_INSTALLED_SOURCE`, `CONTEXT_INSTALLED_LOCAL` từ `app.services.study_composition_service`.

Truy vấn phạm vi dùng mẫu: `Card.query.join(Note, Card.note_id == Note.id).filter(Note.deck_id == self.deck.id)`.

| Test | Thêm dữ liệu | Kỳ vọng |
|---|---|---|
| `test_owned_single_card` | — | `{comp(nt, template_1): 1}` với `comp = make_compatibility_composition_id` |
| `test_owned_two_templates_counts_notes` | note2 trong `self.deck` có Card(template_1) và Card(template_2); note3 có Card(template_1) | `{comp(t1): 3, comp(t2): 1}` |
| `test_every_composition_has_key` | như test trên | `set(result) == {c.composition_id for c in compositions}` |
| `test_empty_compositions` | query lọc `Card.id == "missing"` | `{}` |
| `test_installed_source_and_local_split` | sao chép phần dữ liệu và `clone_scope = SimpleNamespace(local_deck_ids=[self.deck.id], install=SimpleNamespace(user_id=self.user.id, id="test-install"))` từ `test_discovery_preserves_installed_source_and_local_context` (dòng 173-205 cùng file gốc); query lọc `Card.id.in_([card_1, source_card, foreign_card])` | `{make_installed_composition_id(install_id="test-install", context_kind=CONTEXT_INSTALLED_LOCAL, note_type_id=nt, template_id=t1): 1, ... source t1: 1, ... source t2: 1}` |
| `test_does_not_issue_per_composition_queries` | như test owned 2 template; đếm câu lệnh SQL bằng `event.listen(db.engine, "before_cursor_execute", ...)` quanh lời gọi `count_notes_by_composition` | đúng 1 câu lệnh SELECT |

### 5.2 Route (thêm vào cùng file, lớp riêng `CompositionNoteCountsRouteTests`)

Harness: sao chép `setUpClass`/`setUp`/`tearDown` của `FlashcardApiIntegrationTests` (`tests/test_flashcard_api_integration.py` dòng ~50-90; user admin là chủ deck `self.deck_id`). Tạo NoteType + `FieldDef("Front")` + T1 (pos 0, default) + T2 (pos 1); 2 note trong `self.deck_id`, `user_id=self.user_id`; Card(n1,T1), Card(n2,T1), Card(n1,T2).

| Test | Kỳ vọng |
|---|---|
| `test_no_param_response_unchanged` | `GET /api/study/scopes/deck/<deck_id>/compositions` 200, body không có key `note_counts` |
| `test_include_counts_adds_only_note_counts` | gọi không tham số và có `?include_counts=1`; bỏ `note_counts` khỏi body thứ hai thì hai body bằng nhau; `note_counts == {id_T1: 2, id_T2: 1}` (id lấy từ `compositions` theo `template_id`) |
| `test_include_counts_accepts_true_yes` | `?include_counts=true`, `?include_counts=YES` → có `note_counts` |
| `test_include_counts_zero_ignored` | `?include_counts=0` → không có `note_counts` |

### 5.3 Overlay thật (thêm method vào `tests/test_study_session_install_usage.py`)

```python
    def test_compositions_include_counts_for_installed_deck(self):
        self._install_overlay(3)
        response = self.client.get(
            f"/api/study/scopes/deck/{self.local_deck_id}/compositions?include_counts=1"
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(len(body["compositions"]), 1)
        composition_id = body["compositions"][0]["composition_id"]
        self.assertEqual(body["compositions"][0]["context_kind"], "installed_source")
        self.assertEqual(body["note_counts"], {composition_id: 3})
```

## 6. Kiểm tra

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_composition_note_counts -v
& .\.venv\Scripts\python.exe -m unittest tests.test_study_session_install_usage -v
& .\.venv\Scripts\python.exe -m unittest tests.test_study_composition_service tests.test_study_composition_exit_gate
& .\.venv\Scripts\python.exe scripts/run_tests.py --module study --backend-only
git diff --check
git diff --stat
```

## 7. Ghi chú review cho Claude

- Chặn mọi diff trong `AppliedComposition`/`to_dict`; so JSON không tham số với baseline.
- Kiểm tra quyền: hàm chỉ chạy sau `_build_study_scope_query` nên dùng cùng kiểm soát truy cập.
- Nếu `_install_overlay` cần cờ cấu hình (P5/P10) khiến test overlay không chạy được, Gemini phải báo cáo thay vì sửa fixture.

## 8. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-03. Đọc và làm đúng theo docs/task/template-features/GT-03_COMPOSITION_NOTE_COUNTS.md
(§1–§6). Đọc thêm: AGENTS.md; app/services/study_composition_service.py (toàn file, chỉ sửa
bằng cách THÊM hàm count_notes_by_composition sau group_available_compositions);
app/routes/flashcards/study.py (chỉ hàm study_scope_compositions); tests/test_study_composition_service.py,
tests/test_flashcard_api_integration.py (dòng 1-120), tests/test_study_session_install_usage.py (để sao chép harness).
Chỉ sửa đúng 4 file ở §3. Chạy các lệnh ở §6, báo cáo theo mẫu README §3. Không commit.
```
