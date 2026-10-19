# FlamaAudio Windows Release Runbook

## Mục tiêu

Phát hành trực tiếp `FlamaAudio-Portable.exe` ngoài Microsoft Store với một publisher identity ổn định. Pipeline không tắt hoặc bypass Microsoft Defender SmartScreen. Authenticode giúp Windows xác minh publisher và cho phép reputation tích lũy, nhưng không bảo đảm warning biến mất ngay ở release mới.

## Hiện trạng được điều tra ngày 2026-08-11

- App là WPF `WinExe`, target `net8.0-windows`, build bằng .NET SDK 8 trên `windows-latest`.
- Lệnh release là `dotnet publish` cho `win-x64`, `SelfContained=true`, `PublishSingleFile=true`, `IncludeNativeLibrariesForSelfExtract=true` và single-file compression.
- `PublishReadyToRun=false` và `PublishTrimmed=false`. Không có MSBuild release riêng.
- Script Inno Setup `flama-audio/installer/FlamaAudioSetup.iss` tồn tại nhưng installer không được build hoặc phân phối.
- Binary publish gốc là `flama-audio/publish/singlefile/Flama.Audio.App.exe`; bước prepare copy/đổi tên thành final binary `flama-audio/publish/release/FlamaAudio-Portable.exe`.
- Pipeline cũ chạy trên mỗi push `master`, upload EXE chưa ký thẳng lên VPS và không tạo checksum.
- Binary local được kiểm tra tại `flama-audio/publish/singlefile/Flama.Audio.App.exe`: `Status=NotSigned`; signer, subject, issuer và thumbprint đều trống.
- Binary production tải từ endpoint `/api/download/flama-audio` trên domain cũ cũng `Status=NotSigned`; SHA-256 tại thời điểm audit là `91B0B30BE1933640918FCAD7F2847D9E6366823172399102CB24B9359FF2F6B2`. URL hiện tại là `https://api.flama.vn/api/download/flama-audio`; kết quả audit này chưa được kiểm tra lại trên domain mới.
- Endpoint production dùng HTTPS, không redirect, trả `Content-Type: application/x-msdownload`, `Content-Disposition: attachment; filename=FlamaAudio-Portable.exe`, và backend `send_file` không regenerate EXE.

Root cause trực tiếp của warning hiện tại là EXE không có Authenticode publisher identity. Vì vậy SmartScreen chỉ có file-hash reputation và mỗi binary mới lại bắt đầu với hash mới. Metadata Windows cũ cũng dùng tên mặc định `Flama.Audio.App`; project nay cố định Product/Description `FlamaAudio`, Company `Flama` và Copyright `Copyright © Flama`.

## Release flow mới

```text
source tag flama-audio-v*
  -> restore + test
  -> dotnet publish
  -> prepare final FlamaAudio-Portable.exe
  -> Authenticode sign (SHA-256 + RFC 3161 timestamp)
  -> verify with SignTool + Get-AuthenticodeSignature
  -> ZIP the signed EXE
  -> extract ZIP + verify EXE/hash again
  -> create post-package SHA-256 sidecars
  -> publish GitHub Release
  -> copy signed EXE + checksum to Flama server
  -> download from production + verify headers/hash/signature again
```

Không có bước nào ghi lại EXE sau signing. ZIP và checksum chỉ đọc final signed EXE. Bất kỳ verification nào fail đều làm workflow fail; asset chưa qua local gates không được publish/deploy.

## GitHub Environment `Flama`

Tạo hai environment secrets:

- `WINDOWS_SIGNING_CERTIFICATE_BASE64`: toàn bộ PFX được Base64 encode.
- `WINDOWS_SIGNING_CERTIFICATE_PASSWORD`: password của PFX.

Các SSH secrets hiện có vẫn cần cho VPS:

- `SSH_HOST`
- `SSH_PORT`
- `SSH_USER`
- `SSH_PRIVATE_KEY`

Tạo environment variable bắt buộc:

- `WINDOWS_SIGNING_CERTIFICATE_THUMBPRINT`: SHA-1 certificate thumbprint được pin, bỏ khoảng trắng.

Các environment variables tùy chọn:

- `WINDOWS_SIGNING_TIMESTAMP_URL`: mặc định `http://timestamp.digicert.com`, phải là RFC 3161 timestamp endpoint.
- `FLAMA_AUDIO_PRODUCTION_DOWNLOAD_URL`: mặc định `https://api.flama.vn/api/download/flama-audio`.

Giới hạn environment chỉ cho protected tag `flama-audio-v*`, bật required reviewers và không cho self-approval nếu GitHub plan hỗ trợ. Workflow không có trigger PR; production signing secrets không được dùng cho build development/PR.

PFX chỉ được decode vào `$RUNNER_TEMP`, import tạm vào `Cert:\CurrentUser\My`, dùng theo pinned thumbprint rồi xóa file PFX và certificate-store entry trong `finally`. PFX không nằm trong artifact; `*.pfx`, `*.p12`, `*.pvk` và `*.key` cũng bị ignore trong `flama-audio/.gitignore`.

## Certificate và publisher identity

Cần mua/đăng ký một code-signing certificate công khai hợp lệ từ provider có chain tới Windows Trusted Root, hoặc dùng một cloud/hardware signing provider tương đương. Không dùng self-signed certificate cho production và không tạo certificate mới ở mỗi CI run.

Pipeline PFX hiện được cô lập sau `flama-audio/scripts/Sign-WindowsRelease.ps1`; build/package/deploy không phụ thuộc provider. Nếu CA chỉ cấp hardware token/HSM hoặc dùng cloud signing, thay riêng signing adapter này và giữ nguyên `Test-WindowsRelease.ps1` cùng toàn bộ gates sau ký.

Windows hiển thị publisher từ Subject của certificate thật, không lấy từ `<Company>` trong `.csproj`. Owner phải duyệt legal name với CA. Khi gia hạn/rotate certificate, xác nhận Subject vẫn là publisher đã duyệt rồi cập nhật đồng thời PFX và pinned thumbprint; không để CI âm thầm đổi identity.

## Executable inventory và third-party package

Portable release chỉ phân phối một first-party executable: `FlamaAudio-Portable.exe`. Không có helper, updater, bootstrapper, service EXE hoặc first-party native DLL rời; managed/native dependencies được bundle trong single-file container đã ký. Installer không được release.

FlamaAudio có thể tải VOICEVOX Engine của bên thứ ba. Source được pin vào official GitHub release asset `voicevox_engine-windows-cpu-0.14.4.vvpp`, SHA-256 `E425A8F6A7A3B36C7A2646242E23D7E748F23A202FC3D36A07FF7F8E81BD8E50`. App verify hash trước khi extract hoặc chạy `run.exe`; Flama không re-sign binary bên thứ ba. Kokoro path hiện tải model/config/dictionary, không tải executable.

## Tạo release

Tạo annotated tag trên commit đã duyệt:

```powershell
git tag -a flama-audio-v1.0.1 -m "FlamaAudio 1.0.1"
git push origin flama-audio-v1.0.1
```

Manual dispatch chỉ nhận một tag `flama-audio-v*` đã tồn tại và checkout đúng commit của tag. Không dùng workflow này để ký branch build.

GitHub Release chứa:

- `FlamaAudio-Portable.exe`
- `FlamaAudio-Portable.exe.sha256`
- `FlamaAudio-Portable-win-x64.zip`
- `FlamaAudio-Portable-win-x64.zip.sha256`

VPS nhận đúng EXE và sidecar từ release workspace. Server chạy `sha256sum` trước và sau atomic activation. Runner sau đó tải lại URL production, bắt buộc HTTPS/no redirect, kiểm tra Content-Type/filename, SHA-256 và Authenticode.

## Kiểm tra trên Windows

Đặt EXE và sidecar trong cùng thư mục rồi chạy:

```powershell
$exe = ".\FlamaAudio-Portable.exe"
$signature = Get-AuthenticodeSignature -LiteralPath $exe
$signature | Format-List Status, StatusMessage, SignerCertificate, TimeStamperCertificate
if ($signature.Status -ne "Valid") { throw "Authenticode is not valid" }

signtool verify /pa /all /v /tw $exe
if ($LASTEXITCODE -ne 0) { throw "SignTool verification failed" }

$actual = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
$expected = ((Get-Content -LiteralPath "$exe.sha256" -Raw).Trim() -split "\s+")[0]
if ($actual -ne $expected) { throw "SHA-256 mismatch" }
$actual
```

Test download thật:

1. Mở trang Flama bằng Microsoft Edge và tải `FlamaAudio-Portable.exe` từ nút production.
2. Mở `Properties -> Digital Signatures`; publisher phải là Subject của certificate production thật đã được owner duyệt.
3. Chạy các lệnh PowerShell/SignTool trên và so SHA-256 với sidecar hoặc GitHub Release.
4. Xác nhận file tải từ production có cùng SHA-256 với asset GitHub Release.

Một binary mới vẫn có thể tạm thời hiện `isn't commonly downloaded` hoặc `Microsoft Defender SmartScreen prevented an unrecognized app`. SmartScreen dùng cả publisher reputation và file-hash reputation; mục tiêu của pipeline là giữ publisher identity ổn định để reputation có thể tích lũy qua các release, không phải bypass warning.
