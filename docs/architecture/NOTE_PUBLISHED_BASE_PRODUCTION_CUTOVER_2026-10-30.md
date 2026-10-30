# Published Base production cutover — 2026-10-30

Status: **active in production; no-publish soak in progress**.
The runtime and schema expansion were delivered by
[PR #265](https://github.com/TrinhChung/Flama/pull/265), commit
`afbd29eec304ebb970e759f40273b421892b4acc`. Alembic is at
`20261029_000076`. The server flag is enabled for web, Connect and the Study
consumer. All three services and the four existing/new maintenance timers are
active. The deployment lock used during maintenance has been released.

Soak started at **2026-10-30 13:01:18 UTC**. P6 has not run: historical tables,
legacy rollback paths and both backup copies remain available. Do not publish
new content during the coordinated soak. Its completion requires the recorded
[P6 exit checks](NOTE_PUBLISHED_BASE_P6_CHECKLIST_2026-10-30.md), including owner
acceptance and the outstanding Study write/concurrency qualification.

## Reviewed conversion

The owner explicitly approved the updated **six Notes / 23 draft Fields**.
Eight Fields from the earlier 31-Field proposal exactly match applied native-array
script receipts and remain in Base with their current values. The 23 retained
draft Fields have the same Base and author values as the original reviewed list.
See the [preflight](NOTE_PUBLISHED_BASE_PRODUCTION_PREFLIGHT_2026-10-30.md) for
the receipt discovery and successful current-backup rehearsal.

The stopped-writer production manifest matched all reviewed manual content and
all eight script postimages. The operator bound the existing owner approval to
the exact fresh target checksum:

`8863d43894124334ee00bfee47b2d90d79aec3bacace0cbb3970c28849cd7f72`

Its database is `flama`. Full manifests, content-bearing reviews, owner replies,
intent, receipt and fingerprints are private. No Note/Field values or credentials
are included in this report or the repository.

The conversion covers 31,080 published Notes, creates six sparse drafts containing
23 Field deltas, and changes six raw Note payloads. It creates 22 cutover release
heads for current template pins. All 32 installs now read Published Base; automatic
deck publication is disabled. The backlog contains 169,472 script journal entries
and 33 manual entries; only 23 manual values differ from Base and need draft deltas.

## Backup and execution

The existing HTTP/Connect writers, Study consumer, analytics jobs, Study retention
and Note retention timer/oneshot were stopped. Accepted Study work was drained;
none remained. A dedicated systemd guardian held the normal deployment lock from
preparation through apply, validation, enablement and public smoke. No concurrent
deployment could activate a different release during this window.

A fresh quiesced dump was retained on the VPS and downloaded off-host. Gzip CRC,
complete dump footer and the transferred compressed hash were verified:

| Artifact | Evidence |
|---|---|
| Quiesced compressed dump | 237,090,951 bytes |
| SQL payload | 1,468,129,385 bytes |
| Compressed SHA-256 | `7ce3fad16657755bde3930d9701b6a442044794d76b50b9a54e74d61de6cc4f9` |
| SQL SHA-256 | `8d5f195cc587325a3206adb59d1db3a0302ef4b19836f209a136b03fb22e12a5` |

The earlier pre-expansion dump was actually restored on isolated local MySQL and
rehearsed before this maintenance window. The final quiesced dump was checked for
integrity and identical off-host transfer; it has not been separately restored.
Private operator artifacts are under `output/note-base-production/live/` locally
and the restricted VPS directory recorded in `operator-target-private.json`.
The server's pre-enable environment backup remains restricted on the VPS.

Cutover apply used the exact approved SHA and backup reference. It committed an
intent/receipt pair. Before resuming services, the operator verified:

- All **41,874 author Note images** equal their pre-cutover content after merging
  Base and drafts; zero mismatches. Raw Base and install metadata also match.
- All **four personal override rows** match their intended postimages. Only the
  original-release Base hash was backfilled; values, operations, identities and
  last-edit timestamps remain intact.
- Protected Study progress/history, review events, local additions, clone maps
  and media table checksums remain equal.
- All six historical/rebase tables remain present. No index or buffer-pool change
  was made for this rollout.

## Runtime verification

[Master CI and deployment](https://github.com/TrinhChung/Flama/actions/runs/41056615905)
passed. The full backend job ran **2,966 cases** with 85 skips; the separate MySQL
contract job executed all **80 Published Base cases** and its other contracts.
Frontend lint, type checking, tests, SPA/MCP builds and browser fixture checks
passed. Earlier focused failures were corrected before merge; see the preflight.

Production checks passed:

- **35 authenticated in-process GETs** across author and installed Browse/detail,
  search and comparison, with a DML/DDL rejection guard.
- `study-authority-read-audit` for **all 35 NOTE learners**, with zero failing exits
  and the same DML/DDL rejection guard.
- **Four authenticated public HTTPS GETs** covering author detail/Browse and learner
  Browse/comparison. Comparison reports `content_model=published_base`.
  Authentication was staged using application-signed sessions held only in memory;
  this does not qualify the password/Google login flow.
- Public API health, Connect health and anonymous session endpoints return 200.
- The ten media files attached to the reviewed Notes exist with matching SHA-256;
  four public proxy samples return 200 and identical bytes. Other media files were
  not individually rehashed.
- The fresh-copy reviewed-Note renderer check passed **32 template pairs / 64 faces**
  with equal HTML and DOM text, no raw dollar delimiters and no empty faces. This
  supplements the broader prior browser/render evidence.

Cloudflare Workers build `a3d8e60f-3f3e-4b60-bef7-4fda117c17d7` succeeded from
the same commit. Worker `flama-frontend1001`, version
`77b046ac-7339-4f3b-9d0d-1102a5ba29ce`, serves 100% of traffic. Build/deployment
metadata was checked through the [Workers Builds API](https://developers.cloudflare.com/workers/ci-cd/builds/api-reference/).
The public entry is `/assets/index-BVIFABaC.js`; its source map matches all 30
project source modules in that entry, including App. Public CSS bytes equal the
pre-rollout CSS. Local and Cloudflare entry bundles have different byte hashes;
this report does not claim a byte-reproducible build.

The public login page rendered in an isolated Chrome profile with zero console
errors/warnings; the browser was closed afterward. Authenticated browser keep/reset
and desktop/mobile comparisons were qualified locally, as detailed in the
[review response](NOTE_PUBLISHED_BASE_REVIEW_RESPONSE_2026-10-30.md).

At 13:09:47 UTC, all 22 cutover heads were unchanged, all 32 installs used Base,
and the six draft rows still contained exactly 23 deltas. The three service
journals were read successfully through 13:13:51 UTC: 12 messages, zero matching
`[ERROR]` or Python traceback lines. This is an initial operational observation,
not completion of the soak or the full P6 load matrix.

Machine-readable evidence: [production result](NOTE_PUBLISHED_BASE_PRODUCTION_CUTOVER_2026-10-30.json).
Recovery procedure: [cutover/rollback runbook](../runbooks/NOTE_PUBLISHED_BASE_CUTOVER_20261029.md).
