# Flama Audio — Local TTS Service

**Flama Audio** là ứng dụng Windows Desktop (.NET 8 WPF & Kestrel HTTP API) cung cấp dịch vụ tổng hợp giọng nói tiếng Nhật (VOICEVOX Engine) chạy cục bộ tại địa chỉ `http://127.0.0.1:4791`. Ứng dụng tích hợp trực tiếp với **Flama Web** để tự động sinh file phát âm (WAV Blob) và gắn vào thẻ từ vựng (Flashcard Notes) mà không cần dùng remote API Key hay gửi dữ liệu ra bên ngoài.

---

## 📋 Yêu cầu hệ thống (Prerequisites)

- **Hệ điều hành:** Windows 10 / Windows 11 (x64)
- **Runtime / SDK:** [.NET 8.0 SDK](https://dotnet.microsoft.com/download/dotnet/8.0) hoặc `.NET 8 Desktop Runtime`
- **VOICEVOX Engine (Tùy chọn):** 
  - Đã cài đặt và chạy VOICEVOX Engine tại `http://127.0.0.1:50021`.
  - Nếu chưa bật VOICEVOX Engine local, ứng dụng sẽ tự động sử dụng danh sách nhân vật mặc định (Zundamon, Shikikoin Metan, Kasukabe Tsumugi...) để đáp ứng kết nối.

---

## 🛠️ Hướng dẫn Khởi chạy & Build

### 1. Chạy trong môi trường Development (trực tiếp qua dotnet CLI)

Mở Terminal tại thư mục gốc dự án `nihongo/`:

```bash
dotnet run --project flama-audio/src/Flama.Audio.App/Flama.Audio.App.csproj
```

### 2. Build & Publish ra file thực thi (.exe)

Nếu bạn muốn build ra bản phát hành đóng gói:

```bash
dotnet publish flama-audio/src/Flama.Audio.App/Flama.Audio.App.csproj -c Release -o flama-audio/publish
```

Sau khi publish hoàn tất, file chạy thực thi nằm tại:
`flama-audio/publish/Flama.Audio.App.exe`

---

## 🔐 Hướng dẫn Kết nối & Ghép nối (Pairing Flow)

1. Khởi chạy ứng dụng **Flama Audio Desktop** (`Flama.Audio.App.exe`).
   - Cửa sổ ứng dụng sẽ hiển thị trạng thái `Local Endpoint: http://127.0.0.1:4791`.
2. Khởi chạy **Flama Web** (`http://localhost:5173` hoặc server Flask).
3. Mở trang **Browse (Từ vựng)** trên Flama Web, chọn một hoặc nhiều thẻ từ vựng.
4. Trên thanh công cụ hàng loạt, bấm menu **Tạo âm thanh** ➔ chọn **VoiceVox Local**.
5. Nhấn nút **Yêu cầu ghép nối** trên Web Modal.
6. Ứng dụng **Flama Audio Desktop** sẽ **tự động nảy lên trên màn hình (Activate)** và cập nhật yêu cầu ghép nối trong danh sách:
   - Bấm nút **Phê duyệt** bên cạnh yêu cầu của web.
7. Giao diện Web sẽ tự động nhận Token bảo mật (`flama_audio_pairing_token`) và tải danh sách nhân vật đọc.
8. Tùy chỉnh thông số đọc (Speed, Pitch, Intonation, Volume) rồi nhấn **Tạo audio**.

---

## 📡 Danh sách Local API Endpoints (`http://127.0.0.1:4791`)

| Endpoint | Method | Auth | Mô tả |
|---|---|---|---|
| `/health` | GET | Không | Kiểm tra trạng thái ứng dụng, phiên bản và các TTS engines |
| `/v1/pairing/start` | POST | Exact Origin | Tạo thử thách ghép nối (Pairing Challenge) từ Web |
| `/v1/pairing/{id}` | GET | Exact Origin | Poll kiểm tra trạng thái phê duyệt và nhận Pairing Token |
| `/v1/engines` | GET | Bearer Token | Danh sách các TTS Engine packages đã cài đặt |
| `/v1/voices?engine_id=voicevox` | GET | Bearer Token | Lấy danh sách giọng đọc/styles của VOICEVOX |
| `/v1/tts` | POST | Bearer Token | Tổng hợp văn bản thành âm thanh WAV Blob |

---

## 📂 Cấu trúc dự án (`flama-audio/`)

```text
flama-audio/
├── Flama.Audio.sln                  # Visual Studio Solution File
├── .gitignore                        # Cấu hình bỏ qua bin, obj, publish, state local
├── README.md                         # Tài liệu hướng dẫn setup & kiến trúc
├── publish/                          # Thư mục chứa bản build thực thi Flama.Audio.App.exe
├── src/
│   ├── Flama.Audio.Core/             # Interfaces (ITtsEngineAdapter, IPairingManager), Models (TtsRequest, VoiceDescriptor)
│   ├── Flama.Audio.Infrastructure/   # Lưu trữ state local (%LOCALAPPDATA%\Flama\Audio\), PairingManager, EngineRouter
│   ├── Flama.Audio.Engine.Voicevox/  # VOICEVOX Engine Adapter (AudioQuery, Synthesis, Fallback voices)
│   ├── Flama.Audio.Api/              # Kestrel Local API Server, Endpoints, CORS/PNA/PairingAuth Middlewares
│   └── Flama.Audio.App/              # WPF Application, System Tray Host, MainWindow UI
└── tests/
    └── Flama.Audio.Tests/            # xUnit Test Suite cho Core, Router & Pairing logic
```

---

## 🧪 Chạy Kiểm thử (Unit Tests)

Chạy bộ test tự động của .NET:

```bash
dotnet test flama-audio/Flama.Audio.sln
```
