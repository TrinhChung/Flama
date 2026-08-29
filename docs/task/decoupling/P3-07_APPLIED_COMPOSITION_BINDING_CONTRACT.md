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
>
> Preparation status: current responsibility map and deferred decision questions collected on 2026-08-29; P0-03 evidence is now available for the ADR review.

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

## Pre-decision responsibility map — 2026-08-29

This is repository-grounded preparation only. It defines neither final logical policy nor physical schema.

### Current authority and compatibility scaffold

| Concept | Current authority | Observed lifecycle/identity constraint |
|---|---|---|
| Note schema | `NoteType` plus ordered `FieldDef` rows | `FieldDef.id` is stable identity; name is unique only inside a NoteType and is still used by legacy template syntax. |
| Presentation definition | `Template` row owned by exactly one `NoteType` | Mutable HTML/CSS and position; deleting a Template cascades its Cards under current foreign-key semantics. |
| Progress subject | `Card(note_id, template_id)` with unique pair | `CardProgress` belongs to Card; compatibility work must not create a second progress history merely because an application/binding changes. |
| Runtime rendering | `study_artifact_service` resolves effective clone schema/content and freezes versioned template/content artifacts | Overlay field schema/value resolution is release-pinned; Template layout itself is currently a known fail-closed release limitation. |
| Compatibility composition | Derived from current `Template.note_type_id` and `Template.id` | One current Template projects to one `comp:notetype:...:template:...` identity; there is no separate application occurrence identity. |
| NoteType marketplace install | Copies NoteType, FieldDefs and Templates for installer paths | Source/local Template identity mapping is positional in legacy cutover paths, which is insufficient as a future general binding identity. |
| Logical deck overlay | Retains source Note/Card identity and stores field overrides by `source_field_def_id` | Any future application must preserve overlay-only behavior and must not regenerate Cards or mutate source Notes. |
| Session freeze | Stores template/content/policy artifacts and composition references in `study-session.v2` | Future effective application version, binding map and source/local provenance need explicit frozen material before P3-04 can rely on them. |

### Compatibility facts that constrain the ADR

- `Template.note_type_id` cannot be detached in Phase 3; current Card addressing and renderer paths depend on it.
- Current Card uniqueness allows one Card per Note and Template, not repeated applications of the same Template with different bindings.
- Therefore repeated future application cannot be represented by silently creating duplicate current Cards or reusing the same compatibility composition ID without an occurrence discriminator.
- Field rename-safe overlay behavior already uses stable `FieldDef.id`; the target binding contract must preserve that property.
- Existing template authoring may reference field names, so name-to-ID resolution is a compatibility compile/import concern, not the durable binding identity.
- Template/card layout is not yet atomic in deck releases; the ADR must not claim release guarantees that runtime does not provide.

### Questions the ADR must answer

1. What immutable identifier distinguishes reusable definition, definition version, scoped application and repeated binding occurrence?
2. How is the Phase 3 compatibility composition ID derived without inventing a database identity, and when must it remain equal to the existing Template-based ID?
3. Can two applications reference the same definition version in one NoteType, and which application properties must differ to be meaningful?
4. What is the minimum binding value: direct `FieldDef.id` only, or are constants allowed initially? Computed/media transformations should remain explicitly deferred unless required.
5. Which validation errors cover missing required input, wrong NoteType, deleted field, duplicate cardinality, incompatible field type and unresolved legacy name?
6. When a definition is updated, who selects/pins the version, and does editing an installed definition create a private fork before mutation?
7. What happens to active and historical sessions on unpublish, detach or delete, given Card/Template IDs must remain addressable?
8. How are source definition/application IDs projected into an installed overlay while local-added content remains locally owned?
9. Which exact effective material must P3-04 freeze: definition/version, application occurrence, binding IDs, template/content hashes, interaction/trigger and algorithm identities?
10. How do Anki import/export and Flama Connect map current card ordinals/templates without Card regeneration?

### Explicitly deferred physical questions

- Table layout, foreign keys, indexes and Alembic/backfill design.
- Whether definition versions are full snapshots or structural deltas.
- Storage format for binding values and future computed transformations.
- Garbage collection/retention mechanics for unpublished definitions and detached applications.
- Phase 4 migration from compatibility Template/Card projection to any new physical representation.

### Evidence required before ADR approval

- Accepted P0-03 inventory reconciled with current Template/Card/FieldDef and mixed-scope counts.
- Owned, installed-overlay, local-added, import and Connect examples with stable identities traced end to end.
- P3-05 cardinality decision and P3-04 frozen-material requirements.
- At least two alternatives with lifecycle, compatibility and rollback trade-offs; no schema proposal in the Phase 3 decision.

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
