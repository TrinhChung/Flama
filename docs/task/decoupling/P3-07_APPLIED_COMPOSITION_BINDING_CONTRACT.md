# P3-07 — Applied composition and binding contract

> Phase: 3
>
> Priority: P0 decision
>
> Status: TODO
>
> Dependency: Phase 0 evidence
>
> Primary lane: Architecture / Template / Study

## Mục tiêu

Chốt responsibility, identity và lifecycle contract cho reusable Template, abstract inputs và NoteType-scoped applied composition trước khi backend/frontend gọi compatibility scaffold là StudyMode hoàn chỉnh.

## Mode và giới hạn

Design-only cho Phase 3. Task này không định nghĩa final SQL, không tạo model/migration và không detach current `Template.note_type_id`.

## Invariants phải giữ

- Một learner/Note progress dùng chung cho mọi applications.
- Template lifecycle không xóa progress.
- Cùng reusable Template có thể apply nhiều lần vào cùng NoteType với binding/config khác nhau.
- Abstract input thuộc reusable definition/version.
- Concrete binding trỏ stable `FieldDef.id`; field name chỉ là label/legacy authoring syntax.
- Installed definition pin version và edit tạo private fork theo copy-on-write.
- Active session freeze effective versions/material.
- Existing Card/Template IDs vẫn addressable cho Anki/Connect/old sessions.

## Công việc chi tiết

1. Trace current responsibilities của Template, Card, renderer, import, marketplace install và clone overlay.
2. Định nghĩa logical identities:
   - reusable definition;
   - immutable version;
   - abstract input declaration;
   - NoteType-scoped application/StudyMode;
   - binding occurrence;
   - effective compatibility composition ID.
3. Định nghĩa cardinality và repeated application semantics.
4. Định nghĩa minimum input compatibility ban đầu:
   - direct FieldDef binding;
   - required/optional/type/cardinality;
   - constants/computed/media transformations được defer rõ.
5. Định nghĩa lifecycle: create/apply/version/pin/fork/edit/unpublish/detach/delete.
6. Định nghĩa authorization/ownership cho author, installer và private fork.
7. Định nghĩa legacy projection:
   - current Template row → one compatibility application;
   - source/local installed identity;
   - Card ordinal/default/import mapping;
   - no Card regeneration.
8. Định nghĩa snapshot material P3-04 cần freeze.
9. So sánh ít nhất:
   - mutate current Template thành global definition;
   - independent definition bind trực tiếp FieldDefs;
   - versioned definition + abstract inputs + scoped application/binding.
10. Ghi những quyết định physical/schema phải defer tới Phase 4+.

## Output đầu ra bắt buộc

- ADR/contract document trong `docs/architecture/`.
- Responsibility/identity/cardinality/lifecycle tables.
- Compatibility composition ID rules cho Phase 3.
- Binding validation/error matrix.
- Marketplace/clone/import/Anki compatibility section.
- Explicit deferred physical-schema questions.

## Acceptance criteria

- Contract biểu diễn repeated application không tạo progress mới.
- Field rename không đổi stable binding identity trong target contract.
- Source/local overlay contexts có effective application resolution rõ.
- Template unpublish/delete không được cascade progress.
- Phase 3 có đủ logical contract để P3-01/P3-04 implement mà không phát minh SQL.
- Ít nhất hai alternatives và trade-offs được ghi.

## Verification

- Đối chiếu model/service/test evidence, đặc biệt `models/template.py`, `models/card.py`, `study_composition_service.py`, share install/overlay và import/Connect paths.
- Không có runtime/schema diff trong task này.

## Rollback

ADR có thể supersede trước Phase 4. Compatibility scaffold tiếp tục dùng current Template/Card authority nếu decision chưa được duyệt.

## Không làm trong task này

- Không tạo bảng/DDL/Alembic revision.
- Không đổi Card uniqueness/cascade.
- Không implement marketplace Template product.
- Không hỗ trợ arbitrary executable Template dependencies.
