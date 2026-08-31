# Media Field Architecture Investigation

> Date: 2026-08-31
> Mode: INVESTIGATE
> Engine: MySQL 8.0 OLTP
> Scope: image/audio/diagram field values, MediaAsset, Anki/Connect provenance, renderer, Browse editor, stroke generation, migrations, clone/release compatibility

## 1. Executive summary

The current media subsystem has multiple representations for the same concept and multiple writers that choose different representations. A media field may currently contain a bare MediaAsset UUID, original filename, Anki sound tag, proxy URL, library URL, public URL, HTML fragment, inline SVG, plain text, or multiple newline-separated values.

The main conclusions are:

1. Deck 954 in the local database has 60 Anki-imported Notes and 61 attached MediaAssets. The wrong image HTML in example_audio is a post-import cross-field mutation, not an Anki media-loss issue.
2. Production Anki/Connect media is materially healthier than the local development snapshot. All 28,555 resolved Anki audio asset paths checked on the VPS exist on disk.
3. The 20,395 unresolved local audio filenames are not arbitrary user mistakes. Every value matches a filename checked into static/seed_data. They were loaded without binary assets or Connect provenance.
4. Production has a smaller equivalent seed-data problem: 120 audio filenames in Deck 2 have no MediaAsset, staging row, or matching filesystem basename.
5. The current migration revision 20260903_000032 is applied locally but not in production. It does not establish a URL-only contract and is unsafe as the final production migration.
6. Public HTTPS URLs are accepted by parts of the backend and React sanitizer, but the iframe host removes them before building the CSP allowlist. External media is therefore not supported end to end.
7. Existing production Templates still depend on custom audio HTML: 17 of 20 Templates contain an audio tag, none uses a field_url helper, and 16 contain scripts.

~~~mermaid
flowchart LR
    ANKI[Anki or Yomitan] --> STAGING[Connect import staging]
    STAGING --> ASSET[MediaAsset plus binary file]
    STAGING --> NOTE[Note.field_values JSON]
    UPLOAD[Upload or TTS] --> ASSET
    UPLOAD --> NOTE
    STROKE[Stroke generator] --> NOTE
    NOTE --> RENDER[Server and client renderer]
    ASSET --> PROXY[/media/proxy asset id]
    RENDER --> HOST[Sandbox iframe host and CSP]
    PROXY --> HOST
    PUBLIC[Public URL] --> NOTE
    PUBLIC -. currently dropped .-> HOST
~~~

## 2. Scope and safety

### Local

The local MySQL database, repository code, current uncommitted worktree, focused tests, and configured media root were inspected read-only. The local application endpoints on ports 5173 and 4789 responded successfully.

The in-app browser could not be attached because no browser instance was available. Therefore the Browse page was not clicked interactively during this audit. The exact Deck 954 state was reconstructed from the database, API/runtime code, and React component behavior.

### Production VPS

Production was inspected through the configured SSH alias chung_hostinger_vps at the user's direction.

Only read operations were used:

- release and systemd metadata inspection;
- deployed source inspection;
- MySQL SELECT and information_schema queries;
- aggregate media/provenance classification;
- filesystem existence and reference-set checks.

The audit did not:

- import the Flask application on production;
- run startup maintenance;
- run Alembic;
- run DDL or DML;
- restart or reload a service;
- modify a production or workspace file;
- print database credentials or user identity data.

Production evidence is a point-in-time snapshot at 2026-08-31T10:44:14Z.

## 3. Systems of record and ownership

| Data | Current authoritative store | Identity and ownership | Important consumers |
|---|---|---|---|
| Field schema | field_defs | UUID FieldDef owned by NoteType; runtime JSON key remains FieldDef.name | validators, editor, renderer, clone schema |
| Current Note media value | notes.field_values JSON | string keyed by FieldDef.name | Browse, study, import, release diff |
| Note-owned binary metadata | media_assets | UUID MediaAsset owned by Note; field association is mutable field_name | proxy route, media editor, renderer lookup |
| Managed binary | configured media root | storage_path from MediaAsset or Connect staging rows | proxy/download and import materialization |
| Anki Note provenance | connect_source_note_refs | source_key plus external_note_id to Note | idempotent import/update |
| Anki staged media | connect_import_media | import session plus filename and hash | materialize_import_media |
| Active clone edit | deck_clone_note_field_overrides | source FieldDef identity plus compatibility field name | effective clone content |
| Historical published content | release checkpoints and release changes | immutable release facts | installed clone reconstruction, rebase, DCR |
| Card presentation | templates | front_html, back_html, shared_css | server/client Mustache renderer |

Note.field_values has no relational foreign key to MediaAsset. The association is inferred from a string value plus the Note's media_assets collection.

## 4. Data snapshots

### 4.1 Local database

| Metric | Result |
|---|---:|
| Notes | 21,823 |
| MediaAssets | 2,427 |
| Nonblank media-field values | 22,841 |
| ConnectSourceNoteRefs | 11,187 |
| ConnectImportMedia rows | 4,242 |
| Files in app/static/uploads/flashcard_media | 9,144 |

Local nonblank media values:

| Field family and shape | Count | Same-Note asset resolution |
|---|---:|---:|
| Audio proxy URLs | 2,196 | 2,196 |
| Audio bare filename/opaque value | 20,395 | 0 |
| Audio HTML | 56 | 0 |
| Image/diagram proxy URLs | 77 | not reclassified in this slice |
| Image/diagram HTML | 63 | HTML-derived |
| Image/diagram plain text | 48 | 0 |
| Image/diagram opaque token | 6 | 0 |

All 20,395 unresolved bare audio values:

- have no Note-level ConnectSourceNoteRef;
- have no ConnectSourceDeckRef;
- do not match any local MediaAsset filename;
- do not match any production MediaAsset filename when compared by SHA-256;
- do not have a corresponding Note directory in the configured local media root;
- exactly match 20,395 distinct VoiceVox filenames in static/seed_data;
- were concentrated on 2026-07-20, with 20,326 values created that day.

This is seed content with missing binary materialization, not evidence of users entering random values into audio fields.

### 4.2 Local Deck 954

Deck 954 contains:

| Item | Result |
|---|---:|
| Direct Notes | 60 |
| Notes with Anki source provenance | 60 |
| Import session state | anki / importing |
| Notes with a MediaAsset | 60 |
| MediaAssets | 61 |

The NoteType media fields are image, diagram, word_audio, and example_audio.

| Field | Current distribution |
|---|---|
| word_audio | 60 internal proxy URLs |
| image | 56 blank; 3 HTML image fragments; 1 internal proxy URL |
| diagram | 56 stroke HTML wrappers; 4 blank |
| example_audio | 56 copies of stroke image HTML; 4 blank |

The exact failure path is visible in code:

- frontend/src/features/browse/components/BrowseStrokeModal.tsx:111-121 does not recognize the exact field name diagram and falls back to the last Note field.
- The last field for this NoteType is example_audio.
- The target selector is not restricted to image/diagram FieldDefs.
- app/services/strokes/stroke_service.py:239-244 only checks that target_field is nonempty.
- app/services/strokes/stroke_service.py:295-328 writes generated HTML directly into the selected JSON field without verifying its FieldDef type.

### 4.3 Production VPS

Production fingerprint:

| Metric | Result |
|---|---|
| Active release | /opt/flama/releases/848b093936ce97b45003d325de8473168ecc2f1c |
| Alembic head | 20260902_000031 |
| MySQL | 8.0.46 |
| Media root | /var/lib/flama/media |
| Notes | 18,358 |
| MediaAssets | 33,434 |
| Media FieldDefs | 61 |
| ConnectSourceNoteRefs | 15,742 rows; 15,727 distinct current Notes |
| ConnectImportMedia | 19,712 |

Production Deck 954 exists but is empty and has no descendant Decks. It is not the same data scope as local Deck 954.

#### Production Anki/Connect values

| Field family and representation | Count | Resolves to same-Note MediaAsset |
|---|---:|---:|
| Anki audio sound tag | 20,138 | 20,138 |
| Anki audio bare filename | 8,417 | 8,417 |
| Anki image bare filename | 315 | 315 |
| Native/other audio bare filename | 4,651 | 4,531 |

Binary verification:

| Check | Result |
|---|---:|
| MediaAsset storage paths | 33,434 total; 33,434 exist; 0 missing |
| ConnectImportMedia storage paths | 19,712 total; 19,712 exist; 0 missing |
| ConnectImportPackage storage paths | 276 total; 276 exist; 0 missing |
| Files under production media root | 55,404 |
| Files referenced by the inspected media/staging tables | 53,422 |
| Unreferenced files | 1,982 |
| Resolved Anki audio asset paths | 28,555 total; 28,555 exist |
| Resolved native/other audio asset paths | 4,531 total; 4,531 exist |

The 1,982 unreferenced files were only counted. Their lifecycle and provenance were not established, and they were not deleted.

#### Production unresolved seed values

The 120 unresolved native audio values are all 59-character MP3 filenames in Deck 2:

- 60 word_audio;
- 60 example_audio;
- 0 match any MediaAsset filename;
- 0 match ConnectImportMedia;
- 0 match a filesystem basename.

The production image/diagram plain values are:

- 60 diagram values containing the literal JSON string null;
- 56 image values containing the literal JSON string null.

Production also has 14 image HTML fragments:

- every row has exactly one img tag;
- 10 src attributes use a media library URL;
- 4 use another non-proxy, non-public, non-data representation.

#### Production Template usage

| Metric | Result |
|---|---:|
| Templates | 20 |
| Templates containing an audio tag | 17 |
| Templates using a field_url helper | 0 |
| Templates containing word_audio token | 10 |
| Templates containing example_audio token | 17 |
| Templates containing script | 16 |

The deployed default legacy Template still uses custom audio tags, buttons, and playback scripts rather than treating a plain audio field token as the default player.

## 5. Architectural findings

### 5.1 Media field storage has no single canonical representation

- **Observed**: A media field can contain raw IDs, filenames, sound tags, internal URLs, HTML, inline SVG, public URLs, plain text, or newline lists.
- **Evidence**: notes.field_values distributions above; app/services/flashcard_media_api_service.py:117-168 and 338-396; app/services/browse_voicevox_service.py:386-405; app/services/flama_connect_media_service.py:508-563 and 618-621.
- **Potential concern**: Every consumer has its own compatibility parser and guesses whether a token is an ID, filename, URL, or HTML.
- **Impact**: Rendering differs by write path; delete and migration logic cannot reliably identify references; invalid cross-kind values survive validation.
- **Unknowns**: Other deployments may contain representations not present in local or production snapshots.

### 5.2 Anki sound tags and filenames are valid provenance-bearing references

- **Observed**: Production contains both sound tags and bare filenames that resolve to same-Note assets and real files.
- **Evidence**: 20,138 sound tags, 8,417 Anki audio filenames, and 315 Anki image filenames all resolve; all corresponding MediaAsset paths exist.
- **Potential concern**: A migration that treats non-URL values as invalid would delete valid imported media.
- **Impact**: Large-scale data loss for Anki-synced users.
- **Unknowns**: Whether every external Anki client can accept URL-only values on the next bidirectional sync requires protocol-level verification.

### 5.3 Connect re-sync preserves two representations for the same asset

- **Observed**: materialize_import_media writes staged.filename. When a later import references an already-existing asset without a matching staged row, resolve_import_media accepts both filename and sound tag but does not rewrite the field.
- **Evidence**: app/services/flama_connect_media_service.py:459-505 and 508-563; deployed production source matches the local implementation.
- **Potential concern**: Idempotent re-sync can alternate or preserve filename versus sound-tag representations.
- **Impact**: Representation-only release diffs, inconsistent editor display, and migration ambiguity.
- **Unknowns**: The exact client/version sequence responsible for each production sound tag was not reconstructed.

### 5.4 Missing binary is distinct from wrong media kind

- **Observed**: Local seed audio filenames are semantically audio-shaped but have no asset or binary. Deck 954 example_audio contains image HTML and is semantically wrong-kind.
- **Evidence**: 20,395 exact static/seed_data matches versus 56 image-HTML values in an audio field.
- **Potential concern**: A two-state valid/invalid migration cannot distinguish repairable missing media from content that must be removed.
- **Impact**: Either broken references remain forever or potentially recoverable references are deleted.
- **Unknowns**: An external backup or original Anki collection may still contain the seed audio binaries.

### 5.5 Stroke generation can mutate any field type

- **Observed**: Frontend fallback selected example_audio and backend accepted it as a target.
- **Evidence**: BrowseStrokeModal.tsx:111-121; stroke_service.py:239-244 and 295-328; Deck 954 distribution.
- **Potential concern**: UI heuristics are acting as the only type boundary.
- **Impact**: Wrong-kind data is committed and marked as a real Note field change.
- **Unknowns**: Other decks may have been affected with different target-field orderings.

### 5.6 General Note validation permits wrong-kind and arbitrary text

- **Observed**: The media value cleaner accepts rich HTML and then falls back to sanitized plain text. It is not passed the FieldDef media family when cleaning an individual reference.
- **Evidence**: app/validators/flashcard_input.py:381-424 and 529-533.
- **Potential concern**: An audio field can accept image HTML; an image field can accept descriptive prose.
- **Impact**: New invalid values continue to enter the database after a backfill.
- **Unknowns**: Some clients may rely on the permissive fallback for legacy data.

### 5.7 Audio Template semantics are context-dependent

- **Observed**: Audio is excluded from automatic double-brace HTML promotion. The renderer changes the meaning of the main field token when it detects that the Template uses the field in src or href.
- **Evidence**: app/services/flashcard_renderer.py:369-393 and 931-942.
- **Potential concern**: The same token can mean default player HTML in one Template and URL text in another.
- **Impact**: A user cannot reliably insert the audio field once and get a player; Template migration is difficult to reason about.
- **Unknowns**: Custom Templates outside production may depend on this overload.

### 5.8 Public URL support stops at the iframe host

- **Observed**: Backend metadata and the React sanitizer recognize HTTP/HTTPS media, but normalizeProxyRef in the iframe host returns only internal proxy/library/static paths or opaque IDs.
- **Evidence**: app/services/flashcard_renderer.py:803-820; frontend/src/features/study/renderer/clientRenderer.ts:47-59; static/js/card_renderer_host.js:49-97, 149-210, and 264-316.
- **Potential concern**: External URLs disappear from allowed_media_urls and are absent from img-src/media-src CSP.
- **Impact**: Public image/audio may appear valid in one preview path and fail in the actual sandboxed renderer.
- **Unknowns**: Browser mixed-content behavior for existing HTTP URLs is not represented in current data because no public URL values were found.

### 5.9 Multiple-image UI does not match the requested code view

- **Observed**: MediaFieldPreview splits newline values and shows a preview, but code mode edits the raw URL list rather than displaying derived img tags.
- **Evidence**: frontend/src/features/browse/components/MediaFieldPreview.tsx:36-41 and 89-96.
- **Potential concern**: It conflates canonical data editing with generated presentation HTML.
- **Impact**: The code button does not show the code users expect, and editing generated classes would conflict with a URL-only storage contract.
- **Unknowns**: Product behavior for editing versus copying generated HTML is not yet explicit.

### 5.10 Delete only recognizes one legacy representation

- **Observed**: Media deletion clears a field only when the whole value equals asset.id.
- **Evidence**: app/services/flashcard_media_api_service.py:474-480.
- **Potential concern**: Filename, sound-tag, proxy URL, and multi-value references remain dangling.
- **Impact**: Deleted library items can leave broken card content.
- **Unknowns**: No reverse-reference index exists for public or library URLs.

### 5.11 Revision 20260903_000032 is not a complete canonical migration

- **Observed**: The migration scans every string in every Note field, uses a global asset-id-to-filename lookup, converts raw UUIDs to filenames, and has no downgrade.
- **Evidence**: migrations/versions/20260903_000032_migrate_stroke_and_media_urls_in_notes.py:28-53 and 56-116.
- **Potential concern**: It ignores FieldDef type and Note ownership, moves away from URL-only storage, and can mutate non-media fields.
- **Impact**: Production deployment would not satisfy the requested contract and could create unrelated data changes.
- **Unknowns**: Production is still at revision 20260902_000031, so the exact impact of revision 32 has not occurred there.

### 5.12 Clone/release history cannot be rewritten as ordinary current data

- **Observed**: Installed decks use logical overlay; current local clone edits live in DeckCloneNoteFieldOverride; releases/checkpoints are immutable reconstruction facts.
- **Evidence**: docs/plans/completed/CLONE_CUTOVER_REPORT.md; app/services/flashcards_share_service.py; clone/release models.
- **Potential concern**: A global JSON rewrite can create fake owner dirty changes, change release hashes, or mutate historical installed content.
- **Impact**: Spurious marketplace releases, rebase conflicts, or broken clone reconstruction.
- **Unknowns**: The inspected databases did not contain a meaningful population of media-bearing active clone overrides, so larger deployment distributions remain unverified.

## 6. Current test evidence and gaps

Observed local test results before this report:

- scripts/run_tests.py --changed: 405 tests executed; one route-map snapshot failure expected 229 routes but observed 230 because POST /api/browse/cards/batch-delete was added.
- tests.test_flashcard_media_normalizer plus tests.test_flashcard_renderer: 37 passed.
- MediaFieldPreview.test.tsx plus clientRenderer.test.ts: 15 passed.

The passing tests do not prove:

- plain {{Audio}} renders a default audio player;
- public HTTPS media survives iframe-host normalization and CSP;
- wrong-kind field input is rejected;
- stroke target type is enforced server-side;
- MediaAsset deletion removes all URL-list references;
- migration preserves Anki/Connect provenance and clone/release semantics.

## 7. Open questions and needs verification

1. Are the missing seed audio binaries available in an original Anki collection, backup, or external archive?
2. Must Flama export/sync URL-only values back to Anki, or should the Connect boundary translate canonical URLs back to Anki sound tags?
3. Should public HTTP be accepted at all, or only HTTPS outside localhost development?
4. Is the media code view copy-only, or should users be allowed to edit generated HTML and have only src values parsed back?
5. Should one audio field support multiple ordered URLs like image fields?
6. What retention policy applies to the 19,712 staging media rows and 1,982 currently unreferenced production files?
7. Are any deployments already stamped at revision 20260903_000032 besides the inspected local database?
