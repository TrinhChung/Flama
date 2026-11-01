# Direct media upload, Ubuntu staging cleanup and Go stroke generation

Date: 2026-11-01. Implementation contract; production activation requires the matching worker, backend, frontend and private infrastructure configuration.

Media remains on Worker 212. Only generated SVG stroke diagrams are stored on OV. The Flask application owns authentication, note permissions, quotas and MySQL transactions.

## Note media flow

1. The authenticated browser requests `POST /api/media/upload-ticket` with optional `note_id` and `field_name`. Flask issues a bounded, expiring HMAC upload capability and the configured public upload URL.
2. The browser sends the file directly to the Go upload URL with `Authorization: Bearer ...` and no application cookies. File bytes do not pass through Flask. Go validates the format, checks image allocation limits, resizes images to a maximum side of 1600, re-encodes them and writes an owner-scoped stage on 212.
3. Go returns a random `stage_id`, a temporary preview URL and metadata. Editing a field only changes the local form. It does not commit the stage.
4. On note create/update, Browse save or Study quick-edit save, Flask finds staged references, including references inside nested array items and inline Markdown. It rejects another media origin, verifies stage ownership through the internal metadata endpoint, checks field type and quota, and allocates the existing UUID `MediaAsset` identity.
5. Flask sends a private `POST /media/commit` message with the user ID and stage-to-asset UUID mappings. Go promotes bytes into SHA-256 CAS on the same filesystem with `rename`, then persists UUID aliases. No binary bytes are copied back through Flask or OV.
6. The caller commits MySQL and reports success only after Go acknowledges promotion. Stored field values use `/store/<MediaAsset UUID>`; the media gateway serves these aliases from 212.

Generated-audio clients represent an explicit save action. They upload to Go first, then attach the stage through JSON `POST /api/notes/<id>/media`. The batch endpoint accepts JSON receipts and preserves per-item success/failure. Inline Markdown attachment uses `/markdown-media`.

## Wire contracts

Upload ticket response:

```json
{
  "ticket": "signed-upload-capability",
  "upload_url": "https://media.example.com/media/upload",
  "upload_zip_url": "https://media.example.com/media/upload-zip",
  "expires_at": 1793538000,
  "max_bytes": 10485760,
  "staging_ttl_seconds": 86400
}
```

Internal metadata request, authenticated with `X-Internal-Secret`:

```json
{"user_id": 42, "stage_ids": ["stg_0123456789abcdef0123456789abcdef"]}
```

Commit request to `POST /media/commit`, with the same private authentication:

```json
{
  "user_id": 42,
  "items": [{"stage_id": "stg_0123456789abcdef0123456789abcdef", "asset_id": "e2fe658e-1b78-4bb6-a9bd-bce7e1b7b66e"}]
}
```

Both internal endpoints return `items` containing verified stage identity, SHA-256, MIME type, byte count, filename and CAS relative path. A commit receipt also contains the application asset UUID. Public gateway routing must reject internal control endpoints.

## Ubuntu owns abandoned-file cleanup

Stages live under `<MEDIA_STORAGE_ROOT>/staging/stg_<random>/`. Stage directories share the CAS filesystem, so promotion is an atomic rename rather than a second full file write. The Go service holds a BSD directory lock while manipulating a stage; `systemd-tmpfiles` skips locked stage directories.

The requested retention is **one day**. A dedicated `tmpfiles.d` rule ages only the staging subtree; a systemd timer checks it every thirty minutes. Cleanup is periodic, not an exact deletion at the 24-hour boundary. On the inspected Ubuntu host the generic `/tmp` policy was thirty days, so relying on that default would not satisfy this requirement.

Go independently rejects expired stage leases after 86400 seconds. There is no Go background cleanup goroutine. Permanent CAS files, UUID aliases and OV strokes are outside the cleanup rule. Plain `os.CreateTemp` does not automatically remove files when a Go process exits.

Private operational configuration lives in the `infra-vpn` submodule: `flama/tmpfiles/flama-media-staging.conf`, the `flama-media-staging-clean` service/timer, media gateway routing and the stroke receiver service. No production addresses or credentials belong in the public repository.

## ZIP processing

Go accepts direct `POST /media/upload-zip` with a valid upload capability. It checks archive entry count, total uncompressed size, per-entry hard limits, compression ratio and unsafe paths. Accepted media is staged and returned as individual receipts; extraction alone does not commit the assets. The existing Anki import session/package protocol is separate and has not been replaced by this endpoint.

## SVG strokes

With `FLAMA_STROKE_WORKER_ENABLED`, Flask sends only character/locale JSON to `POST /internal/strokes/generate` on 212. Go uses canonical KanjiVG/MMAH data to generate diagrams and transfers the result through an authenticated private request to the OV stroke receiver. The receiver accepts only validated stroke filenames/SVG, writes atomically and exposes metadata checks. Arbitrary user-uploaded SVG is not accepted as note media.

Existing `/store/stroke_<locale>_<hex>.svg` URLs remain stable. Go first checks whether OV already has a diagram. Flask emits available URLs only after confirmed storage and retains note/permission/overlay orchestration. The receiver role initializes neither media CAS nor media upload routes.

## Configuration and activation

Backend settings: `FLAMA_MEDIA_DIRECT_UPLOAD_ENABLED`, `FLAMA_MEDIA_PUBLIC_URL`, `FLAMA_MEDIA_WORKER_URL`, `MEDIA_SHARED_SECRET`, `INTERNAL_SECURITY_SECRET`, `FLAMA_MEDIA_STAGING_TTL_SECONDS=86400`, `FLAMA_STROKE_WORKER_ENABLED`.

Worker settings and role-specific examples are documented in `flama-media/README.md`. Configure exact allowed browser origins. Keep upload signing and private control secrets separate, require the gateway credential on public routes, and expose internal commands only on the private network.

Activate the worker/OV receiver and private routing before enabling the backend flags and deploying the matching frontend. Existing legacy media URLs and files are preserved. This change does not migrate historical media or replace avatar, support attachment, admin image-library or Anki import transports.

## Transaction limits

Go promotion and MySQL are separate systems. A failed Go acknowledgement rolls back the note transaction and does not report success. A failure after Go promotion but before MySQL commit can leave an unreferenced permanent CAS file/UUID alias; it cannot create a successful note reference to a stage awaiting later cleanup. Retried promotions are idempotent, and content is deduplicated. Permanent orphan reconciliation is separate from Ubuntu temporary-file aging.

References: [Go temporary files](https://pkg.go.dev/os#CreateTemp), [Linux rename](https://man7.org/linux/man-pages/man2/rename.2.html), [systemd temporary directories](https://github.com/systemd/systemd/blob/main/docs/TEMPORARY_DIRECTORIES.md).
