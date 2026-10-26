# MCP NoteType and template authoring review — 2026-10-27

## Findings and changes

The existing MCP surface already supported NoteType discovery, creation, rename,
field changes, attached-template edits, impact previews, and deck/note creation.
Field rename preserves FieldDef identity; named note values follow the new name.
The missing surface was the independent reusable template library, typed update
payloads, and a discoverable sequence connecting these operations.

The MCP registry now also exposes:

| Tool | Purpose |
| --- | --- |
| `list_card_templates` | Search/filter a paginated personal library, without source |
| `get_card_template` | Inspect declared inputs, content version and active usages; source is opt-in |
| `create_card_template` | Save an owned reusable definition with typed inputs |
| `update_card_template` | Rename or edit source/inputs through the existing version service |
| `attach_card_template` | Map template inputs to the owned NoteType's field IDs |
| `update_template_application` | Change one occurrence's bindings, display name, position or default flag |

These adapters use `template_library_service`; they do not introduce another
renderer or persistence model. Private reads require `note-type:read`; writes
require `note-type:write`. Ownership and binding scope are checked by the existing
services. Published shared-schema changes retain the MCP guard and return
`SHARED_SCHEMA_VERSIONING_REQUIRED` rather than bypassing release restrictions.

NoteType update/impact schemas now describe full lists and deltas, including
field type, required status, position, identity and field/template rename selectors.
Validation rejects malformed values, foreign field references, duplicate names
and invalid primary identity configuration before writing. Full-list metadata
changes appear in impact previews. Input schemas/bindings participate in stale
preview detection. Template `expected_current_version_id` checks content revisions;
metadata-only renames do not create a new content version.

## Recommended sequence

Read `get_flama_documentation(topic="note-type-authoring")` or the MCP resource
`flama://docs/note-type-authoring` for the complete sequence and payload examples:

1. Discover/create a NoteType; read its fields and stable IDs with
   `get_note_type_schema(include_templates=true)`.
2. Discover a reusable template or preview a raw candidate with explicit samples.
3. Create/update the reusable definition, then attach it with explicit input bindings.
4. Preview the attached occurrence with `note_type_id` and `application_id`.
5. Create a deck using the NoteType and create/read back notes/cards.
6. Use impact preview and its token before field removal or presentation retirement.
   Removing populated fields still requires explicit user confirmation.

Creation/update responses omit source; request source only when needed. Library
listing defaults to page 1 with 24 items. Binding edits replace the binding map.

## Preview review and remaining work

For [#257](https://github.com/TrinhChung/Flama/issues/257), validation reports from
`preview_note_type_template` use `valid=false` with structured `checks` and
`diagnostics` in a normal tool result. This prevents MCP connectors from replacing
the report with an exception on `isError=true`. Mutation failures retain `isError`;
authentication, authorization and service failures remain errors. Empty front
source emits `EMPTY_FRONT_TEMPLATE` as a warning and can still render.

Array storage, existing array data, type inference, bindings and array mismatch
warnings are deliberately unchanged at the user's request. The array item in
#257 remains deferred. No migration, index or renderer contract changes are made.

For [#248](https://github.com/TrinhChung/Flama/issues/248) and
[#116](https://github.com/TrinhChung/Flama/issues/116), browser appearance and
interactions remain client review work. Server syntax/render checks do not prove
interaction correctness; `study_browser` and `interaction` remain `not_run`.
This change does not add a headless browser or alter MCP App packaging.

## Verification

- Pure contracts: `python scripts/run_tests.py --file tests/test_mcp_authoring.py tests/test_template_authoring.py --backend-only`.
- HTTP integration: `python scripts/probe_mcp_authoring_mysql.py --env-file <existing-local-env>`.
  The probe asserts local MySQL, forbids DDL, creates a uniquely named disposable
  user and owned content, exercises the authoring sequence and negative cases,
  then deletes only that fixture. It never seeds or edits existing users' notes.
- The registry must be deployed before connected clients can use the new tools;
  refresh/reconnect clients that cache `tools/list` or the documentation topic enum.

Implementation references: `app/services/mcp/template_tools.py`,
`app/validators/mcp_authoring.py`, `app/services/mcp/note_type_tools.py`,
`app/services/mcp/public_search_tools.py` and `app/services/mcp_tool_registry.py`.
