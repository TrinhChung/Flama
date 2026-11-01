# RFC: Flama Distributed Infrastructure & Workload Partitioning Strategy

> **Mã tài liệu**: `FLAMA-RFC-2026-MULTI-AGENT-01`  
> **Trạng thái**: `PROPOSED / OPEN FOR MULTI-AGENT PEER REVIEW`  
> **Tác giả khởi xướng**: Antigravity / Gemini 3.8  
> **Hội đồng Thẩm định mục tiêu**: Claude Code (Opus / Sonnet), OpenAI Codex, Antigravity, Human Owner (`TrinhChung`)  
> **Ngày phát hành**: 2026-10-31  
> **Tài liệu nền tảng**:  
> - [`INFRASTRUCTURE_WORKLOAD_DISTRIBUTION_ORACLE_WORKER212.md`](INFRASTRUCTURE_WORKLOAD_DISTRIBUTION_ORACLE_WORKER212.md) (RFC phân bổ hạ tầng)  
> - [`FLAMA_WORKLOAD_TELEMETRY_AND_RESOURCE_RATIOS_2026-10-31.md`](FLAMA_WORKLOAD_TELEMETRY_AND_RESOURCE_RATIOS_2026-10-31.md) (Số liệu đo đạc thực tế)  
> - [`CONCURRENCY_STRESS_TEST_REPORT.md`](CONCURRENCY_STRESS_TEST_REPORT.md) (Báo cáo Stress test chịu tải)  

---

## 1. Mục Đích & Hướng Dẫn Dành Cho Các Agent Tham Gia Đánh Giá

Tài liệu này tổng hợp toàn bộ **bằng chứng thực nghiệm (Empirical Telemetry)**, **đặc thù phần cứng**, và **các phương án phân bổ hạ tầng** của Flama giữa 3 máy chủ:
- **`chung_hostinger_vps`** (`187.77.131.151`) — Production hiện tại
- **`worker212`** (`132.145.115.226`) — Node Oracle Cloud OCI (Tokyo)
- **`oracle_vps`** (`161.33.193.141`) — Micro Node OCI (Tokyo)

Các Agent (Claude Code, Codex, hoặc subagent) khi đọc tài liệu này cần:
1. Đọc và đối chiếu các số liệu thực chứng tại **Mục 2 và 3**.
2. Phân tích ưu/nhược điểm kỹ thuật của **3 Kịch bản Đề xuất tại Mục 4**.
3. Trả lời và phản biện các **Câu hỏi Quyết định (Decision Gates) tại Mục 5**.
4. Ghi ý kiến đánh giá, phân tích rủi ro và phán quyết (APPROVE / REQUEST_CHANGES / REJECT) theo **Mẫu Thẩm định tại Mục 6**.

---

## 2. Hồ Sơ Hạ Tầng & Kết Quả Đo Đạc Thực Tế

### 2.1 Cấu Hình Phần Cứng Thực Tế Giữa Các Máy Chủ

| Máy chủ | Vị trí địa lý & Mạng | Dòng CPU & Kiến trúc | RAM | Tình trạng hiện tại |
|---|---|---|---|---|
| **Chung Hostinger VPS**<br>`187.77.131.151` | Kuala Lumpur, Malaysia<br>(Hostinger AS47583) | **AMD EPYC 9354P 32-Core**<br>(Kiến trúc **Zen 4 Genoa** x86_64, 6.490 BogoMIPS) | **8 GB** | **Đang chạy Production chính** của `flama.vn` (Web, Connect, DB, Redis). |
| **Worker212**<br>`132.145.115.226` | Tokyo, Nhật Bản<br>(Oracle Cloud OCI AS31898) | **ARM Neoverse-N1**<br>(Kiến trúc Ampere Altra aarch64, 50 BogoMIPS) | **12 GB**<br>*(Trống ~11 GB)* | Máy chủ dự phòng, tài nguyên RAM dồi dào, CPU đơn nhân chậm hơn. |
| **Oracle VPS (Micro)**<br>`161.33.193.141` | Tokyo, Nhật Bản<br>(Oracle Cloud OCI AS31898) | AMD / Intel Micro shape | **1 GB** | Máy nhỏ OCI Always Free, cùng datacenter với Worker212. |

### 2.2 Đo Lường Hiệu Năng Thực Tế (Benchmark & Network Latency)

1. **Hiệu năng Đơn nhân Python (Single-Core IPC)**:
   - Đo phép tính 10 triệu vòng lặp Python (`sum(i*i for i in range(10_000_000))`):
     - **Hostinger (AMD Zen 4)**: **0.568 giây** ⚡
     - **Worker212 (ARM Neoverse)**: **0.895 giây** 🐢 *(Chậm hơn ~58%)*
   - *Hệ quả*: Do Python/Flask bị khóa GIL, các tác vụ tính toán SRS Anki, parse JSON và serialize SQLAlchemy trên AMD Zen 4 nhanh hơn vượt trội.

2. **Độ Trễ Mạng Liên Máy Chủ (Inter-Node RTT Handshake)**:
   - **Worker212 (Tokyo) $\longleftrightarrow$ Oracle VPS (Tokyo)**: **0.67 ms – 1.15 ms** *(Cực nhanh, chung Datacenter OCI)*.
   - **Worker212 (Tokyo) $\longleftrightarrow$ Hostinger VPS (Malaysia)**: **73.56 ms – 73.72 ms** *(Đường cáp biển xuyên biên giới)*.

---

## 3. Bằng Chứng Thực Nghiệm Từ Production (Telemetry Highlights)

Số liệu trích xuất từ **Hostinger Production** trong **13.63 ngày uptime liên tục** (1.178.086 giây, 54.614 HTTP requests, 5.25 triệu câu lệnh MySQL DML):

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                        THÔNG SỐ HOẠT ĐỘNG THỰC TẾ (13.63 NGÀY)                             │
├───────────────────────────────────┬────────────────────────────────────────────────────────┤
│ Tổng lệnh DML thực thi            │ 5,254,453 câu lệnh (4.81M SELECT, 448K INSERT/UPDATE)  │
│ Tỷ lệ Đọc : Ghi Thô (Raw)         │ 91.47% Đọc  :  8.53% Ghi  (~ 10.7 : 1)                 │
│ Tỷ lệ Đọc : Ghi Người Dùng Thực   │ 86.70% Đọc  : 13.30% Ghi  (~ 6.5 : 1)                  │
│ Tỷ lệ Request Media (/media/proxy)│ 16.79% tổng requests (9,170 requests)                  │
│ Băng thông Media Egress           │ 38.47% tổng băng thông (318.71 MB / 828.54 MB)         │
│ Hiệu quả Cache Media (HTTP 304)   │ 78.64% (Client xác thực ETag, 0 byte nhị phân tải lại) │
│ Yomitan Connect (Cổng 4790)       │ 1.55% requests (846 requests, 107K refs, Base64 burst) │
│ AI Agent MCP (Cổng 4789/4790)     │ 2.20% requests (1,199 requests, 24.28 MB)              │
│ Tranh chấp Khóa dòng (Row Locks)  │ 4 lượt row lock waits trong 13.6 ngày (near-zero)      │
│ InnoDB Buffer Pool Hit Rate       │ 98.85% (Cấu hình 2.0 GB RAM, 0 dirty pages)            │
└───────────────────────────────────┴────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Bẫy Phóng đại Khóa (The RTT Lock Inflation Trap)**:  
> Một batch nộp bài học flashcard (`study_worker`) gồm 15–25 câu lệnh SQL tuần tự trong một transaction có `SELECT ... FOR UPDATE`.
> - Trên localhost (0.04ms): Commit hoàn tất trong **6.88 ms** (đạt 145 jobs/giây).
> - Nếu tách Worker qua mạng 74ms sang Tokyo: Commit bị kéo dài thành **336 ms – 1.326 ms** $\to$ **Thời gian giữ khóa dòng InnoDB bị kéo dài tới 193 lần**, throughput sụp đổ xuống **0.3 job/giây** (giảm 480 lần), làm vỡ đê hàng đợi Redis.

---

## 4. Ba Kịch Bản Kiến Trúc Đặt Lên Bàn Cân

```mermaid
flowchart TD
    subgraph Scenario_1 ["KỊCH BẢN 1: HYBRID CORE (KHUYẾN NGHỊ)"]
        H1["Hostinger (AMD Zen 4 - Malaysia)\n• Web API (:4789)\n• Study Worker & Redis\n• MySQL 8.0 Primary\n• Media Storage"]
        W1["Worker212 (ARM 12GB - Tokyo)\n• Connect & Yomitan (:4790, 4w)\n• AI Agent MCP Tools\n• Worksheet SVG & Anki Parser\n• MySQL Read-Replica & Backup"]
        H1 <-.->|WireGuard (74ms RTT)| W1
    end

    subgraph Scenario_2 ["KỊCH BẢN 2: CHUYỂN HẾT SANG TOKYO (OCI)"]
        W2["Worker212 (12GB RAM - Tokyo)\nChạy 100% dịch vụ: Web, DB, Redis, Connect\nCấp MySQL Buffer Pool 4GB RAM"]
        O2["Oracle VPS (1GB)\nNginx Gateway / Monitoring"]
        W2 <--->|LAN 1.1ms| O2
    end

    subgraph Scenario_3 ["KỊCH BẢN 3: ĐỘC CANH TRÊN HOSTINGER"]
        H3["Hostinger (8GB RAM - Malaysia)\nChạy 100% dịch vụ tại chỗ\nTối ưu nội bộ (tăng gthread, LRU cache)\nWorker212 chỉ làm kho backup nguội"]
    end
```

### So Sánh 3 Kịch Bản

| Tiêu chí | Kịch bản 1: Hybrid Core (Đề xuất) | Kịch bản 2: All-in OCI Tokyo | Kịch bản 3: Độc canh Hostinger |
|---|---|---|---|
| **Hiệu năng Lật thẻ Học** | **Tối ưu nhất** (Chạy trên CPU Zen 4, local DB <0.05ms) | Trung bình (Bị giảm 58% tốc độ đơn nhân do CPU ARM) | **Tối ưu nhất** (Chạy trên CPU Zen 4, local DB) |
| **Xử lý Tác vụ Nặng (Worksheet, Anki)** | **Giải phóng hoàn toàn** khỏi Hostinger, chạy trên 12GB RAM của 212 | Gánh toàn bộ trên 212 (cần chia worker slots hợp lý) | Vẫn chia sẻ trần 8 luồng Gunicorn trên Hostinger |
| **Cổng Yomitan & MCP** | Nâng lên **4 workers** trên 212, không nghẽn web chính | Nâng lên 4 workers trên 212 | Bị giới hạn 1 worker trên cổng 4790 Hostinger |
| **Bảo vệ Bộ nhớ MySQL** | Tối đa (Tác vụ quét rác đẩy sang Replica 212) | Tối đa (Cấp hẳn 4GB RAM Buffer Pool cho MySQL) | Giới hạn trong 8GB RAM của Hostinger |
| **Độ trễ Mạng (RTT Impact)** | **An toàn 100%** (Luồng học không đi qua WAN 74ms) | **An toàn 100%** (Tất cả co-located tại Tokyo <1.1ms) | **An toàn 100%** (Chạy nội bộ 1 máy) |
| **Chi phí Vận hành** | Giữ Hostinger + Tận dụng Worker212 miễn phí | **Tiết kiệm nhất** (Hủy Hostinger, chỉ dùng OCI) | Giữ Hostinger, lãng phí 12GB RAM của 212 |
| **Độ phức tạp Kỹ thuật** | Trung bình (Cần đồng bộ tệp media & WireGuard) | Thấp (Chuyển toàn bộ dữ liệu 1 lần) | Thấp nhất (Không đổi kiến trúc) |

---

## 5. Các Câu Hỏi Quyết Định Cần Hội Đồng Agent Phản Biện (Decision Gates)

### Gate 1: Vấn đề Bất đối xứng Lưu trữ Media (Media Storage Siloing)
* **Bối cảnh**: Khi Yomitan/asbplayer chạy trên Worker212 (Tokyo) thêm từ vựng mới kèm audio/video cắt từ phim, tệp được lưu tại `/var/lib/flama/media/` của Worker212. Nhưng người dùng học thẻ trên web `flama.vn` ở Hostinger (Malaysia) sẽ bị lỗi **HTTP 404 Not Found** vì file không có ở Hostinger.
* **Các phương án giải quyết**:
  - **Phương án 1A (Proxy Upload)**: Khi Yomitan gửi audio lên Worker212, Worker212 lưu tạm và stream upload ngay qua WireGuard về Hostinger.
  - **Phương án 1B (Cloud Object Storage)**: Tích hợp Cloudflare R2 hoặc MinIO S3-compatible làm kho lưu trữ media tập trung (zero-egress cost).
  - **Phương án 1C (NFS / SSHFS Mount)**: Mount thư mục `/var/lib/flama/media` giữa 2 máy qua WireGuard (rủi ro đơ filesystem nếu rớt mạng).
* 👉 **Câu hỏi cho Reviewer**: Đâu là phương án bền vững và ít rủi ro nhất?

### Gate 2: Cân Nhắc Giữa CPU Zen 4 vs Dung Lượng RAM 12GB
* **Bối cảnh**: Hostinger có CPU Zen 4 cực mạnh (nhanh hơn 58%) nhưng chỉ có 8GB RAM. Worker212 có tới 12GB RAM (thừa 11GB) nhưng CPU ARM Neoverse-N1 chậm hơn.
* 👉 **Câu hỏi cho Reviewer**: Có nên chấp nhận hiệu năng CPU đơn nhân thấp hơn 58% để chuyển 100% về Worker212 (Kịch bản 2) nhằm tiết kiệm chi phí thuê Hostinger, hay bắt buộc phải giữ Hostinger làm Core (Kịch bản 1)?

### Gate 3: Thời Điểm Kích Hoạt MySQL Read-Replica
* **Bối cảnh**: Tỷ lệ Đọc thực tế là **86.70%**. Tuy nhiên, tranh chấp khóa dòng trên Hostinger hiện tại là cực thấp (chỉ 4 lock waits trong 13.6 ngày), và Buffer Pool hit rate đạt 98.85%.
* 👉 **Câu hỏi cho Reviewer**: Đã cần thiết lập MySQL GTID Read-Replica trên Worker212 ngay bây giờ chưa, hay trước mắt chỉ nên dùng Worker212 cho tác vụ tính toán và sao lưu ngầm (Cold/Warm DR)?

---

## 6. Mẫu Thẩm Định Dành Cho Các Agent Tham Gia Đánh Giá (Review Template)

Các agent vui lòng sao chép khung dưới đây và thêm vào cuối tài liệu hoặc gửi phản hồi độc lập:

```markdown
### [AGENT_NAME / MODEL] Review & Assessment

- **Ngày đánh giá**: YYYY-MM-DD
- **Phán quyết**: [APPROVE / REQUEST_CHANGES / REJECT]
- **Kịch bản lựa chọn**: [Kịch bản 1 / Kịch bản 2 / Kịch bản 3]

#### 1. Đánh giá về Cơ sở Dữ liệu & Tỷ lệ Tải (R1 & Telemetry):
[Nhận xét về tỷ lệ 86.7% Đọc : 13.3% Ghi và bẫy RTT lock inflation]

#### 2. Đánh giá về Media & Cổng Connect/MCP (R2, R3 & Gate 1):
[Phân tích giải pháp lưu trữ Media và việc tách cổng 4790 sang Worker212]

#### 3. Phản biện về Cân bằng Phần cứng (CPU vs RAM - Gate 2):
[Ý kiến về việc chọn AMD Zen 4 hay ARM 12GB RAM làm Primary]

#### 4. Khuyến nghị Bổ sung & Các Rủi ro Chưa Được Đề Cập:
[Liệt kê các ca biên (edge cases), race conditions, hoặc lưu ý vận hành]
```

---

## 7. Bảng Nhật Ký Đánh Giá Của Các Agent (Review Log)

| Thời gian | Agent / Reviewer | Phán quyết | Kịch bản Đề xuất | Tóm tắt Quan điểm |
|---|---|---|---|---|
| 2026-10-31 | **Antigravity (Gemini 3.8)** | **PROPOSED** | Kịch bản 1 (Hybrid Core) | Giữ Core trên AMD Zen 4 (Hostinger), đưa Connect, Worksheet và Backup sang Worker212 qua WireGuard. |
| *Pending* | **Claude Code** | *Pending* | - | *Chờ đánh giá* |
| *Pending* | **OpenAI Codex** | *Pending* | - | *Chờ đánh giá* |
| *Pending* | **Human Owner** (`TrinhChung`) | *Pending* | - | *Chờ phê duyệt quyết định cuối cùng* |
