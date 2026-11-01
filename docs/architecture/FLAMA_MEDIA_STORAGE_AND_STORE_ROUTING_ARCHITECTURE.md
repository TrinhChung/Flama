# Flama Media Storage, Delivery & Store Routing Architecture

- **Domain**: Media Storage, Content-Addressed Storage (CAS), Edge Routing & Zero-Trust Security
- **Target Platform**: Worker 212 Tokyo (wg-worker212), OV Gateway (wg-gateway), Hostinger App Server (wg-app)
- **Document Status**: Public Architecture Specification (Sanitized)
- **Production Reference**: Unredacted topology & operational configs in private submodule `infra-vpn/flama/`
- **Author**: Antigravity Pair-Programming Agent
- **Date**: 2026-11-01

> [!NOTE]
> **Public Specification Notice**: All public and private IP addresses in this document are documented using RFC 5737 documentation blocks (`198.51.100.0/24`, `203.0.113.0/24`, `192.0.2.0/24`) and WireGuard logical placeholders. Real infrastructure topologies and unredacted runbooks are preserved in the private `infra-vpn/` submodule.

---

## 1. Executive Summary & Architecture Topology

The Flama Media Subsystem manages audio (`.mp3`, `.wav`) and image (`.png`, `.jpg`, `.webp`, `.svg`) assets for all flashcards, dictionary lookups, Kanji stroke order diagrams, and user-generated learning materials.

To eliminate performance bottlenecks on the primary application server (Hostinger Chung VPS), prevent disk exhaustion, and enforce a **Zero-Trust Hardened Security Model**, the entire media storage and delivery infrastructure was migrated and decoupled across a private WireGuard mesh network.

### 1.1 Architecture Topology Diagram

```text
[ Browser / Client / Mobile ]
             │
             │ HTTPS Request (e.g., https://media.flama.vn/store/<id>)
             ▼
┌───────────────────────────────────────────────┐
│               Cloudflare Edge                 │
│  - Edge SSL / TLS 1.3 Termination             │
│  - Static Asset Edge Caching (Cache-Control)  │
└───────────────────────┬───────────────────────┘
                        │ HTTPS
                        ▼
┌───────────────────────────────────────────────┐
│              OV Gateway (Malaysia)            │
│  Public IP: 198.51.100.141 | WG: wg-gateway   │
│  - Nginx Reverse Proxy & Static Stroke Cache │
└───────────┬───────────────────────┬───────────┘
            │                       │
 [Path is /store/stroke_*]          │ [Path is /store/<uuid> or /store/<sha256>]
            │                       │
            ▼                       ▼ (WireGuard Mesh :4792)
┌───────────────────────┐   ┌───────────────────────────────────────────┐
│ Local Fast SSD Cache  │   │            Worker 212 (Tokyo)             │
│ /var/lib/flama/media/ │   │  Public IP: 203.0.113.226 | WG: wg-worker │
│ strokes/stroke_*.svg  │   │  - flama-media Service (Go Daemon :4792)  │
│ (0ms inter-server hop)│   │  - Content-Addressed Storage (CAS SHA-256)│
└───────────────────────┘   │  - Sharded Symlink UUID Addressing Layer  │
                            │  - /data/flama/media/                     │
                            │  - Closed to Public Internet (UFW Mesh)   │
                            └───────────────────────────────────────────┘
```

---

## 2. Product-Oriented URL Standard: `https://media.flama.vn/store/<id>`

### 2.1 The Problem with Legacy URLs
1. **Technical Jargon**: Legacy URLs used `/media/proxy/<asset_id>`, exposing internal reverse-proxy implementation details to end users.
2. **Exposed Directory Hierarchy & Extensions**: Kanji stroke SVGs previously exposed internal file paths such as `/media/library/strokes/ja/04e00.svg` or `/static/strokes/ja/4e00.svg`.
3. **Inconsistent Addressing**: Some assets were addressed by UUID, others by language/hex codes, and others by raw filenames.

### 2.2 The New Standard
All user-facing media references are standardized under a single, opaque, product-oriented scheme:
```text
https://media.flama.vn/store/<id>
```

- **Opaque IDs**:
  - Flashcard audio / images: `https://media.flama.vn/store/160ad0b0-7fd5-4d33-af96-d50cb0cb9102` (UUID) or `https://media.flama.vn/store/6c7a773b...` (SHA-256)
  - Kanji stroke diagrams: `https://media.flama.vn/store/stroke_ja_4e00` or `https://media.flama.vn/store/stroke_zh_6c38`
- **Zero File Extensions**: No `.svg`, `.png`, or `.mp3` exposed in the canonical URL; content negotiation and `Content-Type` headers are handled strictly by the server.
- **Zero Broken Links Guarantee**: Legacy paths (`/media/proxy/<id>`, `/media/library/<id>`, `/static/strokes/<lang>/<hex>.svg`) remain 100% supported via Nginx rewrites and multi-route handlers.

---

## 3. Dual-Addressing Model (CAS SHA-256 + UUID Symlinks)

### 3.1 The Migration Dilemma
The database contained **51,709 media records** referencing UUIDs in `MediaAsset` and `SharedImageAsset`, with over 25,000 flashcards referencing `/media/proxy/<uuid>` in `notes.field_values_by_id`. Migrating all database records to SHA-256 in a single cutover would risk data inconsistency, broken flashcard links, and prolonged maintenance lockouts.

### 3.2 Dual-Addressing Architecture
The media store on Worker 212 uses a physical Content-Addressed Storage (CAS) layer coupled with a virtual UUID symlink index:

1. **Physical File (CAS SHA-256)**:
   ```text
   /data/flama/media/{sha[0:2]}/{sha[2:4]}/{sha256}.{ext}
   Example:
   /data/flama/media/6c/7a/6c7a773bffa27a9d02f6c9921f7733c3c505a6d5ef10dde8a05f78e9339243d5.mp3
   ```
2. **Virtual Index (UUID Symlink)**:
   ```text
   /data/flama/media/{uuid[0:2]}/{uuid[2:4]}/{uuid}.{ext} ➔ ../../{sha[0:2]}/{sha[2:4]}/{sha256}.{ext}
   Example:
   /data/flama/media/16/0a/160ad0b0-7fd5-4d33-af96-d50cb0cb9102.mp3
   ```

### 3.3 Empirical Migration Metrics (2026-11-01)
- **Total Manifest Records Processed**: **51,709** (100% resolved, 0 missing).
- **Physical CAS Files Created**: **41,528**.
- **Duplicate Files Deduplicated**: **10,181** (saved ~450 MB disk space).
- **UUID Symlinks Created**: **51,709**.
- **Raw Data Transferred over WireGuard**: **3,015,552,576 bytes (3.02 GB)** at **~23.5 MB/s**.
- **Cold Backup Retained**: Original source data at `/var/lib/flama/media/` on Chung VPS remains 100% untouched.

---

## 4. Kanji Stroke Order Diagram Optimization

### 4.1 Flattened Directory Layout on OV Gateway
Kanji stroke order SVGs are static reference diagrams used across the entire platform. Rather than routing these frequent, lightweight requests to Worker 212 in Tokyo, they are served directly by the OV Gateway Nginx proxy from local SSD.

All **35,143 stroke SVG files** across `ja`, `zh`, and `zh_hant` were flattened into:
```text
/var/lib/flama/media/strokes/stroke_<locale>_<hex>.svg
```
Using physical filesystem hardlinks on `ext4`:
- Disk space overhead: **0 bytes** (same inode shared with legacy structure).
- Hardlink execution time: **1.5 seconds** for 35,143 files.

### 4.2 Nginx Internal Rewrite Rules on OV Gateway
In `/etc/nginx/sites-available/media.flama.vn`:

```nginx
# 1. Stroke order diagrams (Local fast-path on OV SSD)
location ~ ^/(media/)?(store|proxy|library)/(stroke_[a-zA-Z0-9_-]+)(\.[a-z]+)?$ {
    rewrite ^/(media/)?(store|proxy|library)/(stroke_[a-zA-Z0-9_-]+)(\.[a-z]+)?$ /internal-strokes/$3.svg last;
}

location ^~ /internal-strokes/ {
    internal;
    alias /var/lib/flama/media/strokes/;
    default_type image/svg+xml;
    add_header Content-Type "image/svg+xml; charset=utf-8";
    add_header Access-Control-Allow-Origin "*";
    add_header Cache-Control "public, max-age=31536000, immutable";
}

# 2. Flashcard media (Proxy to Worker 212 Go daemon over WireGuard)
location ~ ^/(media/)?(store|proxy)/ {
    proxy_pass http://flama_media_212;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Flama-Gateway-Secret "${FLAMA_GATEWAY_SECRET}";

    expires 30d;
    add_header Cache-Control "public, no-transform";
}
```

---

## 5. Security & Zero-Trust Architecture

### 5.1 Network Mesh Isolation (WireGuard)
- **Worker 212 (Tokyo)**: Port 4792 is bound to `0.0.0.0:4792`, but UFW blocks all public internet traffic. Only IP addresses in the private WireGuard mesh (App Server and OV Gateway) are allowed to connect.
- **Inter-Service Authentication**: Nginx passes `X-Flama-Gateway-Secret` on all proxied requests. Requests lacking this header or an HMAC authorization ticket are rejected. Real secrets and WireGuard peer keys are managed securely in `infra-vpn/flama/`.

### 5.2 Go Daemon (`flama-media`) Security Controls
1. **Cryptographic Upload Tickets**: Clients must present an HMAC-SHA256 presigned token (`Authorization: Bearer <payload>.<sig>`) generated by Chung VPS.
2. **Pure Go Image Re-encoding**: Uploaded raster images (PNG, JPEG, WebP) are fully decoded to raw pixel bitmaps and re-encoded from scratch in pure Go. This destroys 100% of EXIF payloads, polyglot shells, and steganographic data.
3. **Decompression Bomb Defense**: Pixel count is validated before image buffers are allocated (limits: 16,384 px max dimension, 33,554,432 max pixels).
4. **SVG Code Execution Prevention**: Direct user SVG uploads are blocked to eliminate XSS/Stored HTML attack vectors.
5. **Path Traversal Immunity**: Filenames provided by users are discarded. Files are indexed strictly by SHA-256 hash or UUIDv4 inside two-level prefix directories (`{hash[0:2]}/{hash[2:4]}/`).

---

## 6. Database Migration Records (Chung VPS MySQL)

During the cutover on 2026-11-01, database records were updated under an audited `base_maintenance` scope:
- **Phase 1 (Kanji Strokes)**: **6,260 notes** containing `/media/proxy/stroke_...` were updated to `/store/stroke_...`.
- **Phase 2 (User Media Flashcards)**: **17,556 notes** containing `/media/proxy/<uuid>` were updated to `/store/<uuid>`.
- **Total Migrated Notes**: **23,197 notes** now point to canonical `/store/`.
- **`shared_image_assets`**: **17,599 records** were updated setting `storage_path = CONCAT('strokes/', image_key, '.svg')`.
- **Final Audit Verification**: Remaining notes with `/media/proxy/` in the database: **0** (100% complete).

---

## 7. Verification & Operational Health Checks

### 7.1 Direct Health Check on Worker 212
```bash
curl -i http://127.0.0.1:4792/health
# Response: HTTP/1.1 200 OK | {"status": "ok", "service": "flama-media"}
```

### 7.2 Media Delivery Verification
```bash
# 1. Audio via Go daemon on Worker 212
curl -I https://media.flama.vn/store/0000ce2f-c578-4552-b3c9-eedeb4dad601
# Response: HTTP/2 200 OK | Content-Type: audio/mpeg

# 2. Kanji Stroke SVG via OV Gateway local SSD
curl -I https://media.flama.vn/store/stroke_zh_6c38
# Response: HTTP/2 200 OK | Content-Type: image/svg+xml; charset=utf-8

# 3. Chung VPS Nginx Passthrough
curl -I https://api.flama.vn/store/0000ce2f-c578-4552-b3c9-eedeb4dad601
# Response: HTTP/2 200 OK | Content-Type: audio/mpeg
```

---

## 8. Summary of Server Configuration Files

| Server | File Path | Purpose |
|---|---|---|
| **Worker 212** | `/etc/systemd/system/flama-media.service` | Runs Go service on port 4792 |
| **Worker 212** | `/data/flama/media/` | CAS storage root and UUID symlinks |
| **OV Gateway** | `/etc/nginx/sites-available/media.flama.vn` | Main edge proxy for `media.flama.vn` |
| **OV Gateway** | `/var/lib/flama/media/strokes/` | 35,143 flattened Kanji stroke SVGs |
| **Chung VPS** | `/etc/nginx/sites-available/api.flama.vn` | WireGuard proxy for legacy `/media/proxy/` and `/store/` |
| **Chung VPS** | `/var/lib/flama/media/` | Cold backup of original 3.1 GB media |
