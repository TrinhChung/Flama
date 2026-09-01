# Media Field Architecture Design and Migration Plan

> Date: 2026-08-31
> Mode: DESIGN
> Engine: MySQL 8.0 OLTP
> Prerequisite evidence: MEDIA_FIELD_ARCHITECTURE_INVESTIGATION_2026-08-31.md
> Status: implemented and verified in the local environment on 2026-09-01; production deployment/data mutation remains a separate operation

## Implementation record

- Canonical codec: `app/services/media_field_codec.py`.
- Audited/idempotent migration: `media-normalize-fields`; rollback: `media-normalize-rollback`.
- Audit schema head: `20260904_000033`.
- Local Deck 954 apply run: `72ffe5f8-8dd2-4506-b440-e9f8f82bdc3b`.
- Local global apply run: `c1778f72-9508-472c-bc5e-d6a4c36b4dde`.
- Final local dry-run: 21,823 Notes / 85,980 typed media fields, `changed=0`.
- 20,399 unresolved correct-kind legacy references remain quarantined without destructive deletion.
- Browser verification covered multi-image preview/code mode and managed audio playback on Deck 954.

This record does not indicate that the VPS database was migrated or that application code was deployed there.

## 1. Target outcome

Media fields become URL-first typed content:

- Note fields store URLs, not bare MediaAsset IDs, filenames, Anki sound tags, or presentation HTML.
- A plain media field token renders useful default HTML without requiring Template authors to build audio/image tags.
- Template authors can use explicit URL helper tokens for custom HTML.
- Multiple media items use one canonical URL per line, in stable order.
- MediaAsset and the media library manage binary lifecycle and reuse, but Note.field_values remains an ordinary URL content layer without a database foreign key.
- Anki/Connect translates at the system boundary instead of leaking Anki syntax into the canonical Note value.
- Wrong-kind content is rejected on new writes and removed from old data with an audit trail.
- Correct-kind references with missing binaries are quarantined for repair rather than silently deleted.
- Active clone overlays are migrated safely; immutable release facts are not rewritten.

## 2. Domain invariants

### 2.1 Field value invariants

1. A media FieldDef has one family:
   - image and diagram belong to the image family;
   - audio belongs to the audio family.
2. A persisted media field is either empty or a newline-delimited ordered list of canonical URLs.
3. Line endings are normalized to LF.
4. Blank lines are removed.
5. Duplicate URLs are removed while preserving first occurrence order.
6. A persisted media field must not contain:
   - a bare MediaAsset ID;
   - a bare filename;
   - an Anki sound tag;
   - img, audio, source, video, div, or SVG presentation markup;
   - data URLs;
   - arbitrary plain text.
7. New writes fail with a typed validation error when a value is wrong-kind or malformed. They are not silently stored and cleaned later.

### 2.2 URL invariants

Accepted canonical forms:

| Source | Canonical form | Notes |
|---|---|---|
| Note-managed upload/TTS/Anki binary | /media/proxy/MediaAsset-UUID | URL contract; value is not a bare ID |
| Reusable managed library item | /media/library/stable-key.ext | library lifecycle is independent of Note ownership |
| Static stroke compatibility item | /static/strokes/locale/hash.svg | retain only while the static stroke path remains supported |
| Public media | https://public-origin/path | no server-side fetch during validation |

Recommended public URL policy:

- production accepts HTTPS only;
- localhost development may accept HTTP behind an explicit development setting;
- existing external HTTP values, if later discovered, are reported and quarantined instead of silently upgraded;
- the validator never issues HEAD/GET requests to user URLs, avoiding SSRF, privacy leaks, and slow writes.

### 2.3 Binary and library invariants

1. MediaAsset remains authoritative for a Note-owned binary's metadata and storage path.
2. The canonical field value treats /media/proxy/id as a URL string. Note.field_values does not gain a relational MediaAsset FK.
3. Deleting a managed asset must either:
   - fail while an active Note/override URL still references it; or
   - remove only the exact URL item from every active reference in the same transaction.
4. Public URLs do not require MediaAsset rows.
5. Media library rows may be indexed for usage, but deleting a library item must follow the same reference-aware behavior.

### 2.4 Clone and release invariants

1. Source Notes are never mutated when editing an installed logical-overlay clone.
2. Active DeckCloneNoteFieldOverride values follow the same canonical contract as Note.field_values.
3. Immutable release checkpoints, release changes, and historical DCR facts are not rewritten.
4. Historical values are normalized in memory at read/compare boundaries.
5. Representation-only canonicalization must not create a dirty release atom or DCR conflict.
6. Removing wrong-kind or truly invalid content is a semantic change and must be audited and published through normal owner workflow when relevant.

## 3. Evaluated storage alternatives

| Alternative | Advantages | Costs and risks | Decision |
|---|---|---|---|
| Newline-delimited URL string in Note.field_values | Smallest change; copy/paste friendly; compatible with current Record string APIs; stable order; easy Template first-URL helper | codec must own splitting and dedupe; JSON column cannot enforce URL type | Recommended now |
| JSON array stored as each field value | Explicit multiplicity; easier structured client use | breaks current string contract, imports, presenters, clone overrides, release atoms, Mustache context, and many tests | Defer |
| Normalized NoteFieldMedia child table | Strong typing, reverse references, relational integrity | row/write amplification; dynamic FieldDef lifecycle complexity; clone/release redesign; public/library independence becomes coupled | Reject for this migration |

The recommended change preserves notes.field_values as JSON and changes only the value contract for media FieldDefs.

## 4. Canonical codec

Create one pure typed codec owned by app/services, for example media_field_codec.py. Every read and write path must call the same implementation.

### 4.1 Input context

The codec requires:

- FieldDef ID, name, and field_type;
- Note ID and owner context;
- Note-scoped MediaAsset lookup by ID, proxy URL, original filename, and legacy sound tag;
- library/static URL policy;
- operation mode: validate new write, compatibility read, migration classify, or external-boundary translation.

The current normalize_single_media_reference function does not receive field_type and therefore cannot enforce the required invariants.

### 4.2 Typed result

Each input item should return a structured result:

| Property | Purpose |
|---|---|
| canonical_url | normalized URL when valid |
| media_family | image, audio, or unknown |
| source_shape | proxy, library, public, sound_tag, filename, asset_id, HTML, inline_svg, plain_text |
| disposition | keep, normalize, reject, clear, quarantine, materialize |
| reason_code | stable machine-readable reason |
| semantic_change | distinguishes representation change from content change |
| asset_id | optional resolved MediaAsset |

The migration and UI should consume reason codes rather than reimplementing regex rules.

### 4.3 Classification matrix

| Input | Image/diagram field | Audio field | Migration behavior |
|---|---|---|---|
| Valid canonical URL with matching family | keep | keep | no-op |
| Proxy URL resolving to same-Note asset | keep | keep | verify asset MIME and binary |
| Bare same-Note asset ID | normalize to proxy URL | normalize to proxy URL | representation-only |
| Bare same-Note filename | normalize to proxy URL | normalize to proxy URL | representation-only |
| Sound tag containing public/internal URL | extract and normalize if image-family URL | extract and normalize if audio-family URL | representation-only when family matches |
| Sound tag containing same-Note filename | reject as wrong syntax | normalize to proxy URL | representation-only |
| HTML with matching media src values | extract ordered src URLs | extract ordered audio/source src URLs | remove wrapper presentation |
| HTML containing only wrong-family media | clear | clear | semantic invalid-removal with audit |
| Mixed HTML with matching and wrong-family items | retain matching src list; report dropped items | retain matching src list; report dropped items | semantic cleanup |
| Safe inline SVG | materialize to managed image asset, then store proxy URL | clear | never retain inline SVG in canonical field |
| Literal null/None/plain prose | clear | clear | invalid-removal |
| Correct extension but no asset/binary | quarantine | quarantine | do not fabricate a proxy URL |
| Public HTTPS with known wrong extension | reject | reject | wrong-kind |
| Public HTTPS with no useful extension | accept as unknown-family only if field context allows; browser load errors remain visible | same | no server fetch |
| data URL | reject | reject | materialize only through an explicit upload flow |

The extension is supporting evidence, not the only type authority. Managed assets use verified MIME/signature; HTML tags provide strong family evidence; public URLs without extensions remain unverified rather than fetched by the server.

### 4.4 Anki/Connect boundary

Inbound:

1. Resolve Anki sound tag or filename against staged/imported media.
2. Materialize or reuse MediaAsset.
3. Persist /media/proxy/asset-id in Note.field_values.
4. Retain filename, hash, source session, and external IDs in Connect/MediaAsset provenance rows.

Outbound:

1. Resolve the canonical URL to the binary/filename required by Anki.
2. Emit Anki-compatible sound syntax only in the protocol payload.
3. Never write that transport syntax back into Note.field_values.

When an existing asset is reused during re-sync, resolve_import_media must return the resolved asset to the canonical writer instead of merely allowlisting the legacy filename/sound tag.

## 5. Renderer and Template contract

### 5.1 Deterministic token semantics

| Token | Meaning |
|---|---|
| {{Audio}} | safe default audio HTML for all URLs in the field |
| {{Image}} or {{Diagram}} | safe default img HTML; multiple URLs render as a gallery |
| {{Audio_url}} | first canonical audio URL |
| {{Image_url}} | first canonical image URL |
| {{Audio_urls}} | ordered URL list for Mustache iteration |
| {{Image_urls}} | ordered URL list for Mustache iteration |

Advanced Template example:

    {{#Image_urls}}<img class="custom-image" src="{{.}}">{{/Image_urls}}

Required renderer changes:

1. Include audio in automatic double-brace promotion for HTML-producing media fields.
2. Remove _media_field_used_as_url and the context-dependent meaning of the main audio token.
3. Keep the main media token deterministic across every Template.
4. Build field_url from the first normalized URL.
5. Build field_urls as an ordered list.
6. Generate one img/audio element per URL.
7. Keep classes and layout in renderer output/Template, not in field storage.

### 5.2 Existing Template migration

Before changing token semantics:

1. Inventory every Template with a media field inside src, href, or poster.
2. Rewrite custom URL attributes from {{Field}} to {{Field_url}}.
3. Preserve Template HTML/CSS/scripts byte-for-byte outside the placeholder change.
4. Store old/new Template source in the migration audit.
5. Verify rendered front/back equivalence with current attached assets.
6. Replace the default Flama legacy audio block with a plain {{word_audio}} or {{example_audio}} token where no custom UI is required.

Production currently has 17 Templates using audio tags and zero using field_url, so this migration is mandatory.

### 5.3 Public URL sandbox/CSP

External media support is complete only when:

1. server sanitizer permits an approved HTTPS media URL;
2. renderer metadata includes that exact URL;
3. client sanitizer retains it only on media src/poster or HTTPS link href;
4. iframe host normalization preserves it;
5. CSP includes the exact URL or narrowly scoped origin/path source;
6. audio host commands can resolve only URLs present in the current payload allowlist.

normalizeProxyRef should be replaced or split into:

- normalizeInternalMediaRef;
- normalizeApprovedMediaUrl.

The host must not turn an arbitrary iframe-provided URL into an approved source. Approval comes from the server-derived/current renderer payload.

## 6. Browse and editor UX

Create one shared MediaFieldEditor used by Browse quick edit, modal edit, Note forms, and future admin tooling.

### Default preview mode

- Default mode is preview.
- Image/diagram: render every URL as an img in responsive ordered layout.
- Audio: render a controls player for each URL.
- Each item shows remove/reorder controls and load-error state.
- Paste accepts one or many newline-separated URLs.
- Invalid items remain visible in the draft with an inline reason and cannot be saved.

### Eye button

- Returns to the rendered preview.
- Uses the same normalized draft model as the server codec.
- Does not guess that a bare filename is a proxy URL.

### Code button

Recommended behavior:

- show derived safe HTML such as img src and standard class attributes;
- make the generated HTML read-only with copy support;
- keep URL editing in a dedicated URL-source control;
- explain that custom classes/layout belong in the Template using field_url or field_urls.

If editable code view is later required, save must parse only allowed src values back into the URL list. Field-level class/style HTML must never become authoritative.

## 7. Write-path cutover

All of the following writers must persist codec output only:

| Writer | Current problem | Target |
|---|---|---|
| Flashcard single upload | existing asset writes filename; new asset writes ID | proxy URL |
| Flashcard batch upload | existing writes ID; new writes filename | proxy URL |
| Browse VoiceVox | writes filename and blocks audio append | proxy URL list |
| Flama Connect Anki import | writes staged filename or preserves sound tag | proxy URL |
| Yomitan pending audio | writes filename | proxy URL |
| Stroke generator | writes wrapper HTML and accepts any target field | newline image/library URLs; image/diagram target only |
| Browse PATCH and Note APIs | permissive media cleaner | typed codec validation |
| Clone overlay update | accepts generic string delta | typed codec with effective clone FieldDef |
| Media deletion | clears only exact raw ID | reference-aware URL item removal or fail |

Server-side FieldDef type validation is required even when the UI selector is filtered.

## 8. Migration data model and audit

### 8.1 Recommended audit tables

Use a small migration-specific relational audit instead of embedding recovery data in logs:

#### media_field_migration_runs

- id UUID primary key;
- environment/release fingerprint;
- mode dry_run or apply;
- scope user/deck/all;
- status;
- aggregate counters JSON;
- started_at/completed_at.

#### media_field_migration_items

- id bigint primary key;
- run_id FK;
- target_kind: note, clone_override, template;
- target_id;
- field_def_id nullable for legacy history;
- field_name;
- field_type;
- old_value LONGTEXT;
- new_value LONGTEXT;
- disposition;
- reason_code;
- semantic_change boolean;
- created_at.

This table is not a new media source of truth. It is a bounded recovery/audit surface. Retention/drop requires a later explicit operational decision after backup and restore proof.

### 8.2 Why an audit table is justified

- Existing revision 32 has no downgrade.
- Wrong-kind removal is destructive.
- Missing-binary references need a repair queue.
- Template placeholders must change before audio token semantics change.
- JSON updates need a deterministic rollback source.
- More than 20,000 local seed references cannot be safely classified as disposable.

## 9. Staged migration and rollout

### Phase 0: stop the unsafe production path

1. Do not deploy the current revision 20260903_000032 to production.
2. Inventory every environment stamped at revision 32.
3. Production is currently at 20260902_000031; preserve this gate until the replacement path is reviewed.
4. Because local is already stamped at 32, any corrective path must repair stamped environments idempotently.
5. If revision 32 has not reached any shared environment, make it non-mutating before production and add a later corrective revision/CLI for already-stamped developer databases.
6. If another shared environment has applied it, preserve migration history and ship an explicit compensating revision; do not assume downgrade can restore data.

Exit gate: no deployment can execute the current data-rewrite body of revision 32.

### Phase 1: expand with codec, audit, and compatibility reads

1. Add the typed codec and reason codes.
2. Add migration audit tables.
3. Add a read-only audit CLI with user/deck scope, bounded sample IDs, JSON summary, and nonzero exit code on blockers.
4. Add compatibility read normalization for current filename, sound-tag, HTML, and ID values.
5. Do not change persisted values yet.

Exit gate: local and production dry-run counts reproduce the evidence in the investigation report.

### Phase 2: prevent new drift

1. Cut all current media writers over to canonical URLs.
2. Enforce server-side media family.
3. Fix BrowseStrokeModal default recognition for diagram and filter targets by FieldDef type.
4. Enforce the same check in stroke_service.
5. Make stroke output a URL list, not HTML.
6. Reject wrong-kind writes with 422 and a stable reason code.
7. Translate Anki syntax at the Connect boundary.

Exit gate: no supported writer persists a bare ID, filename, sound tag, or HTML media wrapper.

### Phase 3: renderer, Template, CSP, and UI cutover

1. Add deterministic main-token, field_url, and field_urls semantics.
2. Migrate existing custom Template src placeholders to field_url.
3. Simplify default audio Templates.
4. Complete HTTPS support through iframe host and CSP.
5. Replace one-off media preview logic with shared MediaFieldEditor.
6. Add the requested default preview, eye, and derived-code modes.

Exit gate: old custom Templates render equivalently; plain {{Audio}} renders a working control; public HTTPS media works in the sandbox.

### Phase 4: local canary

Run apply mode only for local Deck 954 first.

Expected results:

| Field | Expected migration |
|---|---|
| word_audio | retain 60 proxy URLs |
| image | keep one proxy URL; extract URLs from three HTML fragments; preserve order |
| diagram | extract the image/library URLs from 56 wrappers into newline lists |
| example_audio | clear 56 wrong-kind image HTML values and audit each removal |

Verify:

- Browse default preview;
- code view;
- study front/back;
- custom Template URL helpers;
- Anki re-sync of the same 60 Notes;
- no wrong FieldDef target from stroke generation;
- dry-run is idempotent after apply.

### Phase 5: repair/quarantine missing media

Local:

- quarantine 20,395 seed filenames;
- record that all match static/seed_data and none has a local/prod asset match;
- attempt repair only from an approved Anki collection, backup, or regenerated VoiceVox source;
- convert repaired binaries to MediaAsset proxy URLs;
- do not clear the whole set without explicit operator approval after the repair report.

Production:

- quarantine 120 Deck 2 seed audio filenames;
- clear 116 literal null image/diagram values as invalid seed artifacts;
- parse 14 image HTML rows: 10 known library URL rows are canonicalizable; the four other src shapes remain quarantined until individually classified.

Exit gate: every missing-binary item is repaired or explicitly approved for removal, with old value recoverable from audit.

### Phase 6: production canonical backfill

Canonicalizable production values at the inspected snapshot:

| Class | Count | Action |
|---|---:|---|
| Anki sound tags | 20,138 | resolve same-Note asset and write proxy URL |
| Anki audio filenames | 8,417 | resolve same-Note asset and write proxy URL |
| Anki image filenames | 315 | resolve same-Note asset and write proxy URL |
| Native/other resolved audio filenames | 4,531 | resolve same-Note asset and write proxy URL |
| Missing seed audio filenames | 120 | quarantine, not automatic clear |
| Literal null image/diagram values | 116 | clear with audit |
| Image HTML | 14 | extract/materialize/quarantine by parsed src |

Operational mechanics:

1. Batch by Note primary key, 250-500 Notes per transaction.
2. Use keyset pagination.
3. Lock only the current batch.
4. Re-read and compare old value before update.
5. Write one audit item per changed field.
6. Support dry-run, resume from last ID, deck/user scope, and idempotent retry.
7. Emit counts only; do not emit raw Note content in standard logs.
8. Measure lock wait, transaction time, rows/second, and replication lag if replicas exist.

### Phase 7: clone/release compatibility

1. Backfill current Note.field_values.
2. Backfill active DeckCloneNoteFieldOverride values using the effective source FieldDef.
3. Notes created through DeckCloneAddedNote are covered by the Note pass.
4. Do not update immutable release checkpoints/changes or historical DCR rows.
5. Canonicalize both sides before release/DCR/rebase comparison.
6. Suppress dirty markers for semantically equivalent representation-only rewrites.
7. Mark invalid-removal as a semantic change for current owner/overlay state.
8. Verify source-owner and installed-clone rendering separately.

Exit gate: no fake release diff is produced solely by filename/sound-tag to proxy-URL conversion.

### Phase 8: contract and cleanup

After an observation window with zero legacy writes:

1. Remove _media_field_used_as_url.
2. Remove filename/ID guessing from MediaFieldPreview and renderer write paths.
3. Remove arbitrary HTML/plain-text fallback for typed media fields.
4. Remove comments declaring filename to be canonical.
5. Remove the audio append limitation after multi-value behavior is verified.
6. Retain compatibility reads only for immutable historical releases until their supported lifetime expires.
7. Update FLASHCARD_V2_RUNBOOK.md and SYSTEM_ARCHITECTURE.md to the URL-first contract.

## 10. Release and dirty-journal semantics

The codec needs a semantic-equivalence function.

Examples:

| Old value | New value | Semantic classification |
|---|---|---|
| filename.mp3 with attached asset | /media/proxy/id | equivalent representation |
| sound tag with attached asset | /media/proxy/id | equivalent representation |
| raw asset ID | /media/proxy/id | equivalent representation |
| image wrapper containing two URLs | two newline URLs | equivalent content, presentation removed |
| image HTML in audio field | empty | semantic invalid-removal |
| literal null string | empty | semantic invalid-removal |
| unresolved correct-kind filename | unchanged quarantine | no current content mutation |

Dirty-journal policy:

- representation-only backfill updates storage without emitting a user-authored dirty atom;
- semantic invalid-removal records a system migration audit and participates in the current working tree;
- new user edits always follow normal dirty behavior.

Release hashing/comparison must use canonical semantic values for new operations while continuing to verify old immutable artifacts with their historical raw hashes.

## 11. Rollback and recovery

### Application rollback

- Keep compatibility readers during rollout.
- Feature flags may restore old rendering, but must not restore old writers after canonical writes begin.
- Template migration rollback uses audited old source.

### Data rollback

- Restore Note/override/template old_value from media_field_migration_items by run_id.
- Require target row still equals audited new_value before restoring, preventing overwrite of later user edits.
- Restore in bounded transactions.
- Recompute current dirty state intentionally; never rewrite immutable historical releases.

### Binary recovery

- Canonicalization does not move or delete managed binary files.
- Invalid field cleanup does not delete MediaAsset or files.
- Asset/file garbage collection is a separate project after reference and retention proof.

## 12. Verification matrix

### Codec unit tests

- proxy, library, static, and public HTTPS URLs;
- sound tag containing URL;
- sound tag containing attached filename;
- raw attached ID/filename;
- wrong-kind extension, MIME, tag, and HTML;
- HTML with one/many matching src values;
- mixed matching/wrong-kind HTML;
- inline SVG materialization result;
- literal null/None and plain text;
- missing binary quarantine;
- CRLF normalization, dedupe, and order.

### Backend integration tests

- single/batch upload write the same proxy URL;
- existing-file dedupe writes the same representation;
- VoiceVox writes/append behavior;
- Yomitan and full Anki import/re-sync;
- stroke target image/diagram allow and audio/text reject;
- Browse PATCH and Note API wrong-kind 422;
- delete referenced URL item versus delete unreferenced asset;
- public HTTPS renderer metadata.

### Renderer and Template tests

- plain {{Audio}} produces audio controls;
- custom src={{Audio_url}} receives only a URL;
- multiple image default gallery;
- field_urls Mustache loop;
- current custom audio Template migration equivalence;
- external HTTPS survives sanitizer, iframe host normalization, and CSP;
- arbitrary external URL injected by Template script remains blocked.

### Clone/release tests

- owner Note and installed clone both render canonical media;
- active override backfill does not mutate source Note;
- representation-only conversion produces no release diff;
- wrong-kind removal creates the intended current semantic diff;
- historical release reconstruction remains byte/hash compatible;
- rebase and DCR comparison canonicalize without false conflict.

### Migration tests

- local Deck 954 fixture;
- production-shaped Anki sound-tag/filename fixture;
- seed missing-binary fixture;
- dry-run has no writes;
- apply is idempotent;
- resume after partial batch;
- concurrent edit compare-and-skip;
- audited rollback;
- MySQL 8 execution and lock-duration measurement.

### Browser acceptance

Use the mandatory isolated Chrome profile and verify:

- /browse?deck_id=954 quick editor and modal;
- default eye preview;
- derived code view;
- three-image paste;
- audio controls;
- public HTTPS image/audio;
- broken URL error state;
- study front/back sandbox;
- no console CSP violation for approved media;
- CSP still blocks unapproved origins.

## 13. Acceptance criteria

The project is complete only when all are true:

1. Every supported writer persists only canonical URL lists.
2. Plain media field tokens render useful default HTML.
3. Custom Templates use deterministic field_url/field_urls helpers.
4. Three pasted image URLs render as three images in Browse and study.
5. Wrong-kind new input is rejected and cannot reach the DB.
6. Existing wrong-kind data is cleared with an audit trail.
7. Missing-binary correct-kind references are repaired or explicitly approved for removal.
8. Anki/Connect re-sync remains idempotent and does not reintroduce filenames/sound tags.
9. External HTTPS media works end to end under the iframe CSP.
10. Representation-only migration creates no fake clone/release/DCR changes.
11. Immutable historical releases remain unchanged.
12. Production revision 32 cannot run its current unsafe data rewrite.
13. Focused backend/frontend, MySQL migration, and isolated-browser suites pass.

## 14. Recommended product defaults

These defaults resolve the current ambiguity:

1. Store one URL per line.
2. Allow multiple ordered image and audio URLs.
3. Use HTTPS only for public production media.
4. Make code view derived and copy-only; edit URLs separately.
5. Use field_url for the first URL and field_urls for custom multi-item Templates.
6. Reject wrong-kind new values; do not silently delete user input during an ordinary save.
7. During migration, delete wrong-kind/meaningless values with audit.
8. Quarantine correct-kind missing binaries until repair or explicit purge approval.
