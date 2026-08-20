# Kế hoạch điều tra và triển khai Flama Audio MVP [COMPLETED]

Date: 2026-08-09  
Status: COMPLETED (Đã triển khai hoàn tất ứng dụng Windows .NET WPF và tích hợp frontend)  
Target đầu tiên: Windows 10/11 x64, CPU-only

## 1. Kết luận

Flama Audio nên được thêm như một ứng dụng Windows độc lập trong thư mục `flama-audio/`, dùng .NET 10 LTS, WPF, Generic Host và Kestrel. Service chỉ bind vào `http://127.0.0.1:4791`; port `4790` không dùng vì Flama Connect đã chiếm port đó trong môi trường hiện tại.

Ranh giới được chốt như sau:

```text
React Flama Web
  ├─ đọc Note/Card từ Flama Backend như hiện tại
  ├─ gọi Flama Audio qua một localhost client riêng
  │    └─ Flama Audio -> engine local -> trả WAV Blob
  └─ đổi Blob thành File và upload qua API media hiện tại
       └─ Flask -> MediaAsset + Note.field_values
```

Flama Audio không có model Deck/Card/Note/Media, không nhận cookie hoặc CSRF token của Flask, không đăng nhập Flama Backend và không upload/sync dữ liệu. MVP không cần migration hay thay đổi schema DB.

Các quyết định chính:

| Hạng mục | Quyết định |
|---|---|
| Desktop | .NET 10 LTS, WPF, Generic Host, self-contained `win-x64` |
| Local API | Kestrel, chỉ `127.0.0.1:4791`, API version `v1` |
| Audio MVP | WAV (`audio/wav`) cho cả Japanese và English |
| Japanese | VOICEVOX Engine CPU, tải riêng từ release chính thức, pin version/hash |
| English | Kokoro + ONNX Runtime CPU sau technical/license spike; không ship package có eSpeak chưa được duyệt |
| Engine packages | Signed catalog + manifest, tải/cài/update độc lập với core installer |
| Metadata local | File JSON versioned + filesystem dưới `%LOCALAPPDATA%`; chưa cần DB |
| Browser security | Local Network Access permission, exact-origin CORS, pairing token, không cookie |
| Web integration | Client localhost riêng + helper upload media dùng chung |
| Shared-deck clone | Chưa hỗ trợ media overlay; disable local TTS cho cloned cards trong MVP |
| Web VoiceVox cũ | Giữ nguyên làm fallback trong giai đoạn chuyển đổi |

## 2. Kết quả điều tra codebase

### 2.1 Luồng media hiện tại đã đủ cho MVP

- Endpoint canonical `POST /api/notes/<note_id>/media` nhận multipart `field_name` và `file` tại [`app/api/v1/flashcards/media.py`](../app/api/v1/flashcards/media.py).
- [`flashcard_media_api_service.py`](../app/services/flashcard_media_api_service.py) đã kiểm tra ownership, field media, extension/MIME/magic bytes, giới hạn kích thước, SHA-256, safe path và rollback file khi commit lỗi.
- Endpoint tự tạo `MediaAsset`, cập nhật `Note.field_values[field_name]` và commit. Web không cần PATCH Card/Note lần thứ hai.
- Validator hiện chấp nhận MP3, OGG, WAV và WebM tại [`flashcard_input.py`](../app/validators/flashcard_input.py). WAV là output ít rủi ro nhất vì VOICEVOX trả WAV sẵn và không cần thêm transcoder.
- Renderer đọc `Note` và `MediaAsset` động; `Card` chỉ tham chiếu `note_id`/`template_id`. Không cần sửa model Card.

Hệ quả: backend MVP không cần endpoint “upload TTS” mới và không cần lưu engine/voice vào DB.

### 2.2 TTS hiện tại không phải local engine

- [`tts_provider_service.py`](../app/services/tts_provider_service.py) đang gọi API TTS Quest từ Flask và cần API key; URL hiện được đánh dấu deprecated.
- [`browse_voicevox_service.py`](../app/services/browse_voicevox_service.py) đang trộn tổng hợp remote, ghi file, tạo `MediaAsset` và sửa Note trong cùng một service.
- Luồng này không được tái sử dụng cho Flama Audio. Giữ nút “Web VoiceVox” cũ làm fallback; “VoiceVox Local” đi theo topology mới.

Không cấu hình `127.0.0.1` vào `TtsProviderConfig`: đó sẽ là localhost của máy backend, không phải máy của người dùng.

### 2.3 Điểm tích hợp React đã có sẵn

- [`BrowsePage.tsx`](../frontend/src/features/browse/pages/BrowsePage.tsx) đã có hai menu disabled: `VoiceVox Local` và `Tiếng Anh Local`.
- Card list có `card_id`/`note_id`; card-detail API đã trả `field_values`, field definitions và media. React type hiện cần bổ sung `field_type`/media/capability.
- [`EditCardModal.tsx`](../frontend/src/features/study/components/EditCardModal.tsx) đã có mẫu tạo `FormData` và gọi media endpoint. Logic này nên được tách thành helper dùng chung, không import code Jinja/legacy vào React.
- [`ankiConnectClient.ts`](../frontend/src/lib/ankiConnectClient.ts) là precedent tốt cho typed localhost client, timeout, `AbortController` và status mapping. Chỉ tái sử dụng pattern, không dùng protocol AnkiConnect.
- [`shared/api/client.ts`](../frontend/src/shared/api/client.ts) không phù hợp để gọi Flama Audio vì nó gắn cookie/CSRF và có cơ chế đánh dấu Flask unavailable. Local client phải dùng `fetch` riêng với `credentials: "omit"`.

### 2.4 Flama Connect không được tái sử dụng như runtime

Flama Connect bind `127.0.0.1:4790` nhưng vẫn dùng Flask DB và thực hiện import/sync Note/Deck/Media. Điều đó trái ranh giới Flama Audio.

Chỉ tái sử dụng các nguyên tắc: loopback-only, health contract, token, rate limit, hash, staged write và security headers. Không tái sử dụng process, action protocol, token trong URL, base64 media staging hoặc cấu hình origin wildcard.

### 2.5 Hai giới hạn hiện hữu phải giữ rõ

1. **Clone overlay:** media API chỉ cho owner của source `Note`; repo chưa có clone-media overlay. MVP chỉ bật generate/upload cho note do user sở hữu. Với installed clone, UI trả trạng thái `media_upload_not_supported_for_clone`; không attach asset vào source Note và không tạo full-copy Note.
2. **Media cũ sau regenerate:** upload audio mới thay giá trị field nhưng không tự xóa `MediaAsset` cũ nếu SHA khác. MVP giữ hành vi hiện tại để tránh xóa nhầm asset đang được tham chiếu; cleanup policy là follow-up riêng.

## 3. Kiến trúc Flama Audio

### 3.1 Cấu trúc solution đề xuất

```text
flama-audio/
  Flama.Audio.sln
  Directory.Build.props
  Directory.Packages.props
  src/
    Flama.Audio.App/                 # WPF, tray, Generic Host, composition root
    Flama.Audio.Core/                # use cases, router, contracts, state machine
    Flama.Audio.Api/                 # Kestrel endpoints, auth, CORS, rate limits
    Flama.Audio.Infrastructure/      # catalog, download, install, process, config
    Flama.Audio.Engine.Voicevox/     # VOICEVOX adapter
    Flama.Audio.Engine.Kokoro/       # Kokoro adapter; optional package
    Flama.Audio.Kokoro.Worker/       # isolated ORT CPU worker; optional package
  tests/
    Flama.Audio.Core.Tests/
    Flama.Audio.Api.Tests/
    Flama.Audio.Infrastructure.Tests/
    Flama.Audio.Engine.Tests/
```

WPF chỉ làm UI và host lifecycle; không chứa code gọi VOICEVOX/ONNX trực tiếp. Adapter package chỉ được load từ catalog first-party đã ký. MVP không mở arbitrary third-party plugin loading.

### 3.2 Contracts

Tách lifecycle runtime khỏi package lifecycle:

```csharp
public interface ITtsEngineAdapter
{
    string EngineId { get; }
    Task<EngineHealth> GetHealthAsync(CancellationToken ct);
    Task StartAsync(CancellationToken ct);
    Task StopAsync(CancellationToken ct);
    Task<IReadOnlyList<VoiceDescriptor>> ListVoicesAsync(CancellationToken ct);
    Task<TtsResult> SynthesizeAsync(TtsRequest request, CancellationToken ct);
}

public interface IEnginePackageManager
{
    Task InstallAsync(string engineId, string version, CancellationToken ct);
    Task UpdateAsync(string engineId, string version, CancellationToken ct);
    Task UninstallAsync(string engineId, CancellationToken ct);
    Task<IReadOnlyList<EnginePackageState>> ListAsync(CancellationToken ct);
}
```

Các contract bổ sung: `IEngineCatalog`, `IEngineProcessSupervisor`, `IEngineRouter`, `IPackageVerifier`, `IEngineStateStore`.

`IEngineRouter` ưu tiên `engine_id` rõ ràng; `language` dùng để validate capability, không âm thầm đổi engine. `VoiceDescriptor` phải chứa tối thiểu `voice_id`, locale, display name, supported options, attribution, policy URL/version và trạng thái cần phê duyệt sử dụng.

### 3.3 Local state và package manifest

Không dùng SQL cho metadata nhỏ. Dữ liệu per-user:

```text
%LOCALAPPDATA%\Flama\Audio\
  config\settings.json
  state\installed-engines.json
  state\pairings.json
  engines\<engine-id>\versions\<version>\...
  engines\<engine-id>\active.json
  cache\downloads\...
  staging\...
  logs\...
```

JSON có `schemaVersion`; ghi qua temp file + atomic replace. Không log text được synthesize hay pairing token.

Manifest engine tối thiểu:

- schema version, engine ID, version, locale/capabilities, architecture;
- minimum/maximum compatible core API version;
- danh sách artifact, URL HTTPS, size, SHA-256, extractor type;
- adapter ID, entrypoint/arguments, readiness probe;
- estimated installed/download size;
- license/notice/attribution và terms version;
- signature của Flama cho manifest/catalog.

Catalog ký bằng khóa phát hành của Flama; public key nằm trong core. SHA-256 kiểm tra tính toàn vẹn artifact nhưng không thay thế chữ ký catalog.

### 3.4 Install/update/rollback

1. Resolve một version đã pin; không cài từ alias `latest`.
2. Kiểm tra disk quota và compatibility trước khi tải.
3. Tải vào `.part`; resume bằng HTTP Range cùng ETag/Last-Modified. Nếu server không hỗ trợ hoặc identity đổi, tải lại từ đầu.
4. Verify size + SHA-256 trước khi extract.
5. Extract vào staging cùng volume; chặn path traversal, symlink/reparse point và archive bomb. VOICEVOX cần spike extractor cho format official multipart 7z.
6. Chạy smoke test/readiness probe.
7. Move version directory rồi atomic-swap `active.json`.
8. Giữ một version trước để rollback; xóa version/cache cũ theo quota sau khi bản mới ổn định.

Mỗi engine chỉ có một operation install/update/uninstall tại một thời điểm. Stop engine trước swap; nếu start/health thất bại thì trả active pointer về bản trước.

## 4. Local API và security

### 4.1 Endpoint v1

Base URL cố định: `http://127.0.0.1:4791`.

| Endpoint | Auth | Mục đích |
|---|---|---|
| `GET /health` | Không; dữ liệu tối thiểu | Detect app/API version/pairing state |
| `POST /v1/pairing/start` | Exact Origin | Tạo pairing challenge |
| `GET /v1/pairing/{id}` | Exact Origin | Poll trạng thái, nhận token một lần sau approval |
| `GET /v1/engines` | Pairing token | Installed/available/status/version/update |
| `GET /v1/voices?engine_id=...` | Pairing token | Voices + capabilities + license metadata |
| `POST /v1/tts` | Pairing token | Generate và trả audio binary |

`POST /v1/tts` nhận JSON versioned:

```json
{
  "request_id": "uuid",
  "engine_id": "voicevox",
  "language": "ja-JP",
  "voice_id": "style-id",
  "text": "...",
  "output_format": "wav",
  "options": {
    "speed": 1.0,
    "pitch": 0.0,
    "intonation": 1.0,
    "volume": 1.0
  },
  "engine_options": {}
}
```

Adapter validate option bằng capability schema; không chuyển arbitrary option thành command-line argument. Thành công trả raw `audio/wav` cùng request/engine/voice headers. Lỗi trả `application/problem+json` với stable `code`, `request_id`, `retryable` và message an toàn.

### 4.2 Browser ↔ localhost

Chrome 142+ yêu cầu Local Network Access permission cho public site gọi loopback; PNA preflight cũ không còn là cơ chế chính. Vì vậy:

- Chỉ gọi lần đầu sau thao tác rõ ràng `Kết nối Flama Audio`, không scan port lúc page load.
- Dùng IP literal `127.0.0.1`, không self-signed HTTPS và không cài root certificate.
- Fixed port `4791`; nếu conflict, app báo `PORT_IN_USE` thay vì tự scan port khác.
- Browser-facing Kestrel chỉ bind IPv4 loopback. Child engine dùng port loopback nội bộ riêng và không được frontend gọi trực tiếp.
- Production CSP/reverse proxy phải cho `connect-src http://127.0.0.1:4791`; đây là release gate cần test thật.
- UI phân biệt: permission denied, app stopped, API incompatible, pairing required, engine missing, starting, unhealthy và ready.

### 4.3 Threat controls

- Exact allowlist cho production Flama origins và các origin dev được khai báo trong development build; không wildcard, không auto-trust origin mới, reject `Origin: null`.
- Validate `Host` đúng `127.0.0.1:4791`; bind loopback-only.
- `credentials: "omit"`; không gửi Flask cookie/CSRF/backend bearer token.
- CORS không phải authentication. Token random per pairing, bind với exact origin, chỉ có scope synthesize/read-engine, lưu hash local, rotate/revoke được trong WPF.
- `Authorization: Bearer <local-pairing-token>` và `Content-Type: application/json` buộc mutation đi qua preflight. Có thể trả PNA compatibility header cho browser cũ nhưng không coi đó là auth.
- Giới hạn text, request body, output bytes, queue, timeout và concurrency. CPU engine mặc định một synthesis đang chạy; Web queue tuần tự hoặc tối đa 2 theo capability.
- `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`; không expose stack trace/path/process arguments.
- Single-instance app; engine child thuộc Job Object/process supervisor để được stop khi app thoát bất thường.

## 5. Engine packages

### 5.1 Japanese — VOICEVOX

Adapter flow:

```text
start child process on private loopback port
  -> GET /version + GET /speakers readiness
  -> POST /audio_query?text=...&speaker=<style-id>
  -> map validated speed/pitch/intonation/volume to AudioQuery
  -> POST /synthesis?speaker=<style-id>
  -> validate WAV -> return to core
```

Khởi động CPU-only, explicit host/port, UTF-8 logging và `--disable_mutable_api`; xác minh lại CLI flags với version đã pin trong integration test.

Tại ngày điều tra, stable release là `0.25.2` và Windows CPU artifact khoảng 1.68 GiB. Catalog phải pin tag, artifact list, byte size và GitHub-provided SHA-256; không mirror/repackage trước khi distribution/legal review hoàn tất.

License gate bắt buộc:

- `voicevox_engine` có dual-license LGPL v3/separate license; `voicevox_core` artifact từ 0.16+ dùng MIT nhưng bản cũ có điều khoản khác.
- VVM và output vẫn chịu attribution cùng điều khoản từng voice/character; các voice không có cùng mức cho phép commercial/corporate.
- UI phải hiển thị notice/credit/policy; lưu terms version đã được user chấp nhận. Voice có policy chưa map hoặc cần approval không được gắn nhãn `commercial-safe` mặc định.
- Legal counsel duyệt chiến lược direct-download, notice bundle và nghĩa vụ phân phối trước production release.

### 5.2 English — Kokoro

Upstream Kokoro dùng Python/PyTorch/Misaki; upstream không cung cấp runtime Windows .NET/ONNX chính thức. ONNX conversions và wrappers .NET hiện là community artifacts.

Không chọn trực tiếp KokoroSharp 0.8.0 hoặc sherpa-onnx cho production MVP:

- KokoroSharp 0.8.0 package chứa eSpeak binaries/data và GPLv3 notice; eSpeak có thể được gọi cho English OOV.
- TTS-enabled sherpa-onnx link `piper_phonemize`/eSpeak.
- Source KokoroSharp mới đang loại runtime eSpeak nhưng chưa phải release ổn định; không build production từ floating `main`.

English phase bắt đầu bằng spike có hai candidate:

1. First-party worker dùng `Microsoft.ML.OnnxRuntime` CPU + Kokoro ONNX artifact có provenance/hash + G2P C# đã audit.
2. KokoroSharp/MisakiSharp tại immutable release/commit sau khi SBOM chứng minh artifact không chứa hoặc gọi eSpeak, và quality/license review pass.

Worker chạy persistent, cache một `InferenceSession`, không cần Python/CUDA/GPU và giao tiếp với adapter qua named pipe hoặc một IPC private. Benchmark bắt buộc: cold/warm latency, real-time factor, RAM, 2/4/8-core, output WAV 24 kHz và golden pronunciation set có OOV/numbers/names.

Nếu không candidate nào qua provenance/license/quality gate, ship Japanese MVP trước và giữ English ở trạng thái `not_available`; không nới lỏng gate để đạt checklist.

## 6. Tích hợp Flama Web

Thêm các module nhỏ, tránh tiếp tục phình `BrowsePage.tsx`:

```text
frontend/src/lib/flamaAudioClient.ts
frontend/src/shared/api/noteMedia.ts
frontend/src/features/audio/types.ts
frontend/src/features/audio/localAudioGeneration.ts
frontend/src/features/audio/components/LocalAudioDialog.tsx
```

Thêm `VITE_FLAMA_AUDIO_URL` với default development/production là `http://127.0.0.1:4791`; validate URL luôn là loopback, không cho UI nhập arbitrary remote endpoint.

Flow batch:

1. Nhận selected card IDs từ Browse.
2. Dùng card-detail API hiện tại, dedupe theo `note_id` và lấy field definitions/values.
3. Chỉ cho source `text`, `richtext`, `markdown`; normalize về plain text bằng utility có test. Chỉ cho destination có `field_type=audio`.
4. Bỏ qua card không thuộc user hoặc clone-overlay với reason rõ ràng.
5. Kiểm tra `/health`, pairing, engine và voice.
6. Queue từng note: gọi `/v1/tts`, validate status/MIME/non-empty/size rồi nhận WAV Blob.
7. Chuyển Blob thành `File`, gọi helper multipart tới `POST /api/notes/<note_id>/media` bằng backend client hiện tại.
8. Sau upload thành công, dùng `asset_id`/`url` trả về; không PATCH Note lần hai.
9. Cập nhật progress per-note, hỗ trợ cancel/retry failed items và invalidate browse/card-detail query.
10. Refresh study content artifact nếu card đang có session cache, nhưng bảo toàn review events chưa sync; không xóa toàn bộ active session.

MVP dùng card-detail API hiện tại, không thêm batch preparation endpoint. Nếu profiling cho thấy N+1 là vấn đề, phase sau mới thêm endpoint generic chỉ để resolve/normalize authorized TTS jobs; endpoint đó vẫn không generate hoặc lưu audio.

Backend cần một thay đổi nhỏ không đụng schema: trả capability `can_upload_media`/reason trong browse detail để React chặn clone/admin-other cases trước khi gọi localhost.

## 7. Kế hoạch triển khai theo phase

### Phase 0 — Decision spikes và release gates

- Dựng Kestrel stub và kiểm chứng HTTPS Flama origin -> HTTP loopback trên Chrome/Edge/Firefox hiện hành, gồm Local Network Access prompt, CORS và production CSP.
- Chốt production/dev origin allowlist, port `4791`, pairing UX và API schema v1.
- Xác minh exact VOICEVOX archive/multipart extraction, CLI flags, licenses và character policy catalog.
- Chạy Kokoro candidate/license/SBOM spike; ghi pass/fail, không khóa core vào candidate.
- Chốt Windows code-signing certificate và nơi host signed catalog/engine artifacts.

Exit: không còn unknown có thể làm topology browser-localhost hoặc distribution thất bại.

### Phase 1 — Core, WPF shell, API, abstraction và package manager

- Tạo solution/projects, DI/Generic Host, single-instance, tray và graceful shutdown.
- Implement health/API version, structured errors, config/state store, pairing/auth/CORS/rate limits.
- Implement contracts/router/process supervisor.
- Implement catalog/manifest verify, resume, staged extract, atomic activation, rollback và cache quota bằng fake engine package.
- WPF tối thiểu: service status, version, logs path và engine state; chưa làm UI polish.

Exit: fake engine có thể install/start/list voices/generate/update rollback qua API và test tự động.

### Phase 2 — VOICEVOX package và Japanese E2E

- Tạo signed manifest pin VOICEVOX CPU version.
- Implement install/extract/process/readiness/speakers/synthesis adapter.
- Expose voice policy metadata và settings hợp lệ.
- Test fresh install, interrupted download, start conflict, synthesis, restart, update rollback và uninstall.

Exit: WPF/Core gọi VOICEVOX local và trả WAV đúng contract khi offline sau khi package đã cài.

### Phase 3 — Kokoro package và English E2E

- Chọn candidate chỉ khi Phase 0 gate pass.
- Tạo isolated CPU worker/adapter, model/G2P package, SBOM/notices và benchmark.
- Test pronunciation, deterministic contract, process crash/restart và memory lifecycle.

Exit: không Python/CUDA/GPU/manual runtime, WAV hợp lệ và license inventory được duyệt. Nếu fail, ghi English blocked và tiếp tục Japanese MVP.

### Phase 4 — React bridge và Blob upload

- Tạo dedicated `FlamaAudioClient`, pairing flow và status model.
- Tách `noteMedia` helper; activate hai local menu và thêm `LocalAudioDialog`.
- Implement field validation, note dedupe, queue/progress/cancel/retry, object URL cleanup và query/session refresh.
- Thêm browse capability cho owner-vs-clone; không sửa clone model.
- Giữ Web VoiceVox song song.

Exit: từ React Browse, user-owned Japanese note đi qua localhost -> WAV Blob -> media endpoint -> card render audio. English chạy cùng flow nếu engine đã pass.

### Phase 5 — Engine management UI

- Available/installed engines, download/disk progress, install/update/uninstall/restart.
- Default engine/voice per locale, test textbox/player và license/credit view.
- Clear error recovery cho insufficient disk, hash mismatch, port conflict, engine unhealthy và rollback.

Exit: user không cần CLI, Python hay cài engine thủ công.

### Phase 6 — Hardening và distribution

- Signed MSIX/MSIXBundle + `.appinstaller`, self-contained x64; ARM64 là phase sau.
- Core auto-update tách khỏi engine updater; release channels stable/beta.
- Windows CI build/test/SBOM/sign/publish; real-engine E2E là scheduled/release job, không tải artifact 1.68 GiB trong mọi PR.
- Exclude `flama-audio/` khỏi Linux web release archive trong `.github/workflows/deploy.yml`; thêm Windows workflow riêng.
- Thêm backend request cap tương ứng media max; review orphan-media cleanup policy.
- Security review, dependency scan, logs/telemetry privacy, install/uninstall recovery và release runbook.

Exit: production-signed package, upgrade/rollback test trên clean Windows VM và browser matrix pass.

## 8. Test matrix và Definition of Done

### Automated

- Core: routing/capability validation, state transitions, cancellation, JSON migration.
- API: exact Origin/Host, pairing/revoke, auth, preflight, body/text/output/rate/concurrency limits, problem details.
- Package manager: signature/hash, resume identity, traversal/symlink/archive bomb, disk full, crash recovery, atomic promote và rollback.
- Adapters: mocked contracts trong PR; pinned real-engine E2E trong Windows scheduled/release pipeline.
- React: loopback URL validation, `credentials: omit`, local token nhưng không Flask auth, timeout/abort, MIME/empty Blob, pairing/permission/status states, note dedupe, audio-only destination, partial failure/cancel/retry và `URL.revokeObjectURL`.
- Media helper/backend: Blob -> multipart đúng; WAV create/dedupe/oversize/signature/ownership; clone capability; không PATCH Note lần hai.

### MVP Japanese được coi là xong khi

1. Clean Windows user cài core mà chưa có model/engine lớn.
2. User bấm Install VOICEVOX; download có progress/resume/hash và engine health đạt ready.
3. Flama Web từ production HTTPS xin browser permission, pair đúng origin và phát hiện app.
4. User chọn owned Note, source text, audio destination và VOICEVOX voice.
5. `/v1/tts` trả WAV Blob; Flama Web upload qua media endpoint hiện tại.
6. Backend tạo `MediaAsset`, cập nhật Note và card phát được audio qua media proxy.
7. Khi localhost/engine/upload lỗi, item chưa upload không làm thay đổi backend; item thành công vẫn giữ được và retry phần lỗi hoạt động.
8. Flama Audio không chứa Flask credentials, Deck/Card/Note/Media database hay backend sync code.
9. Installed clone bị chặn rõ ràng; source Note không bị mutate.
10. App restart/update/uninstall engine và rollback bản lỗi hoạt động.

English đạt cùng Definition of Done chỉ sau khi Kokoro runtime, G2P, model provenance và license gate đều pass.

## 9. Các gate còn cần owner/legal quyết định

| Gate | Cần chốt trước |
|---|---|
| Production origins/CSP | Browser spike và release web đầu tiên |
| VOICEVOX redistribution/attribution/character map | Public Japanese release |
| Kokoro ONNX conversion + G2P + eSpeak obligations | Public English release |
| Code-signing certificate, catalog key và artifact host | Installer/update release |
| Orphan audio cleanup policy | Trước khi bật regenerate hàng loạt mặc định |
| Clone media overlay | Chỉ khi muốn hỗ trợ TTS trên installed clone; ngoài MVP này |

## 10. Ngoài phạm vi MVP

- Chinese/French/Korean engines.
- GPU/CUDA support.
- Arbitrary third-party plugin SDK.
- Dynamic browser port discovery/port scanning.
- Flama Audio gọi hoặc đăng nhập Flama Backend.
- Deck/Card/Note/Media database trong desktop app.
- Clone-media overlay hoặc full-copy clone.
- MP3/Opus transcoding; output đầu tiên chỉ WAV.
- Tự động xóa media cũ khi regenerate.

## 11. Nguồn nghiên cứu chính

### Repo

- [`app/api/v1/flashcards/media.py`](../app/api/v1/flashcards/media.py)
- [`app/services/flashcard_media_api_service.py`](../app/services/flashcard_media_api_service.py)
- [`app/validators/flashcard_input.py`](../app/validators/flashcard_input.py)
- [`app/services/browse_voicevox_service.py`](../app/services/browse_voicevox_service.py)
- [`frontend/src/features/browse/pages/BrowsePage.tsx`](../frontend/src/features/browse/pages/BrowsePage.tsx)
- [`frontend/src/lib/ankiConnectClient.ts`](../frontend/src/lib/ankiConnectClient.ts)
- [`frontend/src/shared/api/client.ts`](../frontend/src/shared/api/client.ts)
- [`docs/plans/completed/CLONE_CUTOVER_REPORT.md`](CLONE_CUTOVER_REPORT.md)

### Official/upstream

- [.NET support policy](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core)
- [WPF overview](https://learn.microsoft.com/en-us/dotnet/desktop/wpf/overview/)
- [WPF Generic Host](https://learn.microsoft.com/en-us/dotnet/desktop/wpf/app-development/how-to-use-host-builder)
- [ASP.NET Core Kestrel](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/servers/kestrel?view=aspnetcore-10.0)
- [ASP.NET Core CORS](https://learn.microsoft.com/en-us/aspnet/core/security/cors?view=aspnetcore-10.0)
- [Chrome Local Network Access](https://developer.chrome.com/blog/local-network-access)
- [Local Network Access specification](https://wicg.github.io/local-network-access/)
- [VOICEVOX Engine repository](https://github.com/VOICEVOX/voicevox_engine)
- [VOICEVOX Engine API](https://voicevox.github.io/voicevox_engine/api/)
- [VOICEVOX Engine 0.25.2](https://github.com/VOICEVOX/voicevox_engine/releases/tag/0.25.2)
- [VOICEVOX Core](https://github.com/VOICEVOX/voicevox_core)
- [VOICEVOX VVM terms](https://github.com/VOICEVOX/voicevox_vvm/blob/main/TERMS.txt)
- [VOICEVOX general terms](https://voicevox.hiroshiba.jp/term/)
- [Kokoro upstream](https://github.com/hexgrad/kokoro)
- [Kokoro-82M model](https://huggingface.co/hexgrad/Kokoro-82M)
- [Misaki G2P](https://github.com/hexgrad/misaki)
- [ONNX Runtime C#](https://onnxruntime.ai/docs/get-started/with-csharp.html)
- [KokoroSharp package](https://www.nuget.org/packages/KokoroSharp)
- [eSpeak NG license](https://github.com/espeak-ng/espeak-ng/blob/master/COPYING)
- [MSIX overview](https://learn.microsoft.com/en-us/windows/msix/overview)
- [App Installer auto-update/repair](https://learn.microsoft.com/en-us/windows/msix/app-installer/auto-update-and-repair--overview)

