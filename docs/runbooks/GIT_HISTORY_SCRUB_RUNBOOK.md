# Hướng Dẫn & Runbook Thanh Lọc Toàn Diện Lịch Sử Git
## (Git History Scrubbing Evaluation & Operational Runbook)

- **Mã tài liệu**: `RB-SEC-20261101-01`
- **Phiên bản**: `1.0.0-PROD`
- **Ngày phát hành**: 2026-11-01
- **Phân loại**: Hướng dẫn Vận hành & Phục hồi An ninh Hạ tầng (Security Incident Remediation Runbook)
- **Căn cứ điều tra**: Báo cáo Kiểm toán Rò rỉ Lịch sử Git `REP-SEC-20261101-01` (`docs/reports/2026-11-01_GIT_HISTORY_LEAK_INVESTIGATION_REPORT.md`)
- **Kho chứa áp dụng**: `https://github.com/TrinhChung/Flama.git` (Public Repository)
- **Mức độ khẩn cấp**: **P0 - CRITICAL**
- **Trách nhiệm thực thi**: Quản trị viên Kho lưu trữ (Repository Administrator / Lead DevOps)

---

## Mục Lục

1. [Tổng Quan & Bối Cảnh Sự Cố (Overview & Incident Context)](#1-tổng-quan--bối-cảnh-sự-cố-overview--incident-context)
2. [So Sánh Đa Chiều & Đánh Giá Các Phương Án Kỹ Thuật (Tooling Evaluation & Trade-off Analysis)](#2-so-sánh-đa-chiều--đánh-giá-các-phương-án-kỹ-thuật-tooling-evaluation--trade-off-analysis)
   - 2.1. Phương án 1: `git-filter-repo` (Khuyến nghị chính thức của Git Project)
   - 2.2. Phương án 2: `BFG Repo-Cleaner`
   - 2.3. Phương án 3: `Tạo Fresh Repo` (Orphan Branch / New Init)
   - 2.4. Ma trận so sánh đa chiều (Comparison Matrix)
   - 2.5. Kết luận lựa chọn giải pháp tối ưu
3. [Chuẩn Bị & Sao Lưu Tuyệt Đối An Toàn (Pre-scrubbing Prerequisites & Safe Backup)](#3-chuẩn-bị--sao-lưu-tuyệt-đối-an-toàn-pre-scrubbing-prerequisites--safe-backup)
   - 3.1. Quy trình đóng băng commit (Freeze Window Protocol)
   - 3.2. Tạo Git Bundle toàn vẹn (Full Git Bundle Backup)
   - 3.3. Tạo Mirror Clone cô lập (Isolated Mirror Clone)
   - 3.4. Xác minh tính toàn vẹn của bản sao lưu (Verification & Checksums)
4. [Cài Đặt Môi Trường & Thiết Lập Bản Đồ Ánh Xạ Chuỗi (Tooling Setup & Replacement Mapping)](#4-cài-đặt-môi-trường--thiết-lập-bản-đồ-ánh-xạ-chuỗi-tooling-setup--replacement-mapping)
   - 4.1. Cài đặt `git-filter-repo`
   - 4.2. Thiết lập file ánh xạ thay thế chuỗi chuẩn RFC 5737 (`replace-text.txt`)
5. [Quy Trình Thực Thi Thanh Lọc Từng Bước (Step-by-Step Scrubbing Execution)](#5-quy-trình-thực-thi-thanh-lọc-từng-bước-step-by-step-scrubbing-execution)
   - 5.1. Khởi tạo không gian làm việc cô lập (Isolated Scrubbing Scratchpad)
   - 5.2. Thực thi thanh lọc chuỗi nhạy cảm trên toàn bộ lịch sử
   - 5.3. Xử lý các đường dẫn file nhạy cảm lịch sử (Sensitive Paths Cleanup)
   - 5.4. Dọn dẹp Reflog và thu gom rác bộ nhớ (Garbage Collection)
6. [Bộ Kịch Bản Kiểm Tra & Đối Soát Hậu Thanh Lọc (Post-Filter Automated Verification Suite)](#6-bộ-kịch-bản-kiểm-tra--đối-soát-hậu-thanh-lọc-post-filter-automated-verification-suite)
   - 6.1. Kiểm tra đối soát bằng lệnh Git chuyên dụng
   - 6.2. Script một chạm kiểm tra toàn diện cho Linux/macOS (`verify_history_clean.sh`)
   - 6.3. Script một chạm kiểm tra toàn diện cho Windows PowerShell (`Verify-HistoryClean.ps1`)
   - 6.4. Đối soát tính nguyên vẹn của submodule `infra-vpn` và nhánh chính
7. [Tái Cấu Hình Remote & Force Push Có Kiểm Soát (Remote Re-binding & Controlled Force Push)](#7-tái-cấu-hình-remote--force-push-có-kiểm-soát-remote-re-binding--controlled-force-push)
   - 7.1. Tái liên kết Remote Origin
   - 7.2. Kiểm tra đối chiếu trước khi push (Sanity Pre-push Check)
   - 7.3. Thực hiện Force Push an toàn lên GitHub
8. [Hướng Dẫn Đồng Bộ Dành Cho Cộng Tác Viên (Collaborator Rebase & Recovery Runbook)](#8-hướng-dẫn-đồng-bộ-dành-cho-cộng-tác-viên-collaborator-rebase--recovery-runbook)
   - 8.1. Trường hợp 1: Lập trình viên KHÔNG CÓ commit dở dang (Clean Working Copy)
   - 8.2. Trường hợp 2: Lập trình viên ĐANG CÓ nhánh tính năng dở dang (In-flight Feature Branches)
   - 8.3. Sơ đồ cơ chế hoạt động của `git rebase --onto`
9. [Các Hành Động An Ninh Hậu Kỳ & Tẩy Sạch Cache GitHub (Post-scrubbing Security Hardening)](#9-các-hành-động-an-ninh-hậu-kỳ--tẩy-sạch-cache-github-post-scrubbing-security-hardening)
   - 9.1. Tẩy sạch bộ nhớ đệm commit mồ côi trên GitHub (GitHub Cached Commit Refs Purge)
   - 9.2. Quy trình xoay vòng bí mật thực tế trên các cụm máy chủ (Server Secrets Rotation)
10. [Kế Hoạch Dự Phòng & Phục Hồi Thất Bại (Rollback & Disaster Recovery Plan)](#10-kế-hoạch-dự-phòng--phục-hồi-thất-bại-rollback--disaster-recovery-plan)

---

## 1. Tổng Quan & Bối Cảnh Sự Cố (Overview & Incident Context)

Theo kết quả điều tra chi tiết tại báo cáo `REP-SEC-20261101-01`, kho mã nguồn công khai `https://github.com/TrinhChung/Flama.git` đã trải qua các đợt rò rỉ thông tin hạ tầng nghiêm trọng trong lịch sử Git gồm **1,197 commits**, đỉnh điểm là việc merge Pull Request #279 vào nhánh `master` lúc 10:44:36 +0900 ngày 01/11/2026.

### Danh Mục Tài Nguyên Nhạy Cảm Bắt Buộc Phải Thanh Lọc:
1. **3 Địa chỉ IP Public máy chủ thật**:
   - `187.77.131.151` (Hostinger Chung VPS - Kuala Lumpur)
   - `161.33.193.141` (Oracle OV Gateway - Micro Instance)
   - `132.145.115.226` (Tokyo Worker 212 - Ampere ARM)
2. **Khóa bí mật chia sẻ cổng phân phối (Shared Gateway Secret Token)**:
   - `flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4`
3. **Mạng riêng ảo nội bộ WireGuard Mesh**:
   - Dải mạng `10.10.0.0/24` và các địa chỉ IP `10.10.0.4`, `10.10.0.5`, `10.10.0.6`
4. **Thông tin định danh quản trị & Khóa OAuth**:
   - Email quản trị cá nhân: `chungtrinh2k2@gmail.com`
   - Google OAuth Client ID Production: `992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com`
   - Prefix Google Client ID: `992185847654-b1aekjqb7dh3hddetgve8qfps17nro08`
5. **Thư mục cấu hình hạ tầng production**:
   - Thư mục `deploy/` (23 file gồm cấu hình Nginx thật, đường dẫn chứng chỉ SSL cá nhân/Let's Encrypt, systemd units và scripts root). Cấu hình này hiện đã được di dời sang submodule private `infra-vpn/flama/`.

> [!WARNING]
> **Nguyên tắc cốt lõi của Runbook**: Viết lại lịch sử Git (Rewriting Git History) là một thao tác **thay đổi toàn bộ SHA-1 commit hash** từ commit đầu tiên chứa dữ liệu rò rỉ trở đi. Mọi thao tác phải tuân thủ nghiêm ngặt quy trình cô lập môi trường, sao lưu đa lớp và kiểm tra đối soát trước khi force push lên remote repository.

---

## 2. So Sánh Đa Chiều & Đánh Giá Các Phương Án Kỹ Thuật (Tooling Evaluation & Trade-off Analysis)

Để loại bỏ triệt để các chuỗi bí mật và file nhạy cảm khỏi lịch sử Git, nhóm kỹ thuật đã phân tích và đánh giá 3 phương án công nghệ hiện nay:

### 2.1 Phương án 1: `git-filter-repo` (Khuyên dùng chính thức)
- **Nguồn gốc & Công nghệ**: Được phát triển bằng Python bởi Elijah Newren, là công cụ được chính tổ chức **Git Project** khuyên dùng chính thức thay thế cho công cụ cổ điển đã bị khai tử `git filter-branch`.
- **Cơ chế hoạt động**: Sử dụng giao thức `git fast-export` / `git fast-import` kết hợp xử lý stream dữ liệu ở tầng thấp trong bộ nhớ.
- **Ưu điểm**:
  - Hỗ trợ thay thế chuỗi văn bản (`--replace-text`) cực kỳ mạnh mẽ, chính xác trong cả blob file lẫn commit message.
  - Tự động viết lại commit hash, cập nhật commit parent pointers, gán nhãn, bảo toàn commit author, email, timestamp và commit signature (nếu không đổi).
  - Tự động phát hiện và xử lý an toàn commit tip, reflog, và bảo vệ người dùng bằng cách tự động xóa remote references tránh vô tình push nhầm khi chưa kiểm tra.
  - Hỗ trợ xử lý submodule và giữ nguyên cấu trúc liên kết cây git mà không làm hỏng gitlinks.
  - Tốc độ xử lý vượt trội (nhanh gấp 10-50 lần so với `git filter-branch`).
- **Nhược điểm**: Đòi hỏi môi trường chạy có Python 3.8+ và Git 2.22.0+.

### 2.2 Phương án 2: `BFG Repo-Cleaner`
- **Nguồn gốc & Công nghệ**: Được viết bằng Java/Scala bởi Roberto Tyley.
- **Cơ chế hoạt động**: Tối ưu hóa đặc biệt cho việc tìm kiếm và xóa bỏ các tệp tin có kích thước lớn (`large blobs`) hoặc thay thế chuỗi đơn giản.
- **Ưu điểm**:
  - Tốc độ thực thi cực nhanh trên các repository dung lượng lớn chứa nhiều file nhị phân nặng.
  - Cú pháp lệnh đơn giản, dễ tiếp cận.
- **Nhược điểm & Giới hạn**:
  - **Không chạm vào commit gần nhất (HEAD)**: BFG theo thiết kế bảo vệ không bao giờ chỉnh sửa commit tip (`HEAD`), đòi hỏi người dùng phải tự commit sửa tay trước.
  - **Khả năng thay thế chuỗi hạn chế**: Không hỗ trợ regex nâng cao, xử lý commit messages kém linh hoạt hơn `git-filter-repo`.
  - Phụ thuộc vào môi trường Java Runtime Environment (JRE).
  - Khả năng xử lý phân nhánh phức tạp (với 66 remote branches và submodule như Flama) dễ phát sinh lỗi mồ côi commit hoặc lệch con trỏ submodule.

### 2.3 Phương án 3: `Tạo Fresh Repo` (Orphan Branch / New Init)
- **Cơ chế hoạt động**: Tạo một commit gốc mới hoàn toàn không có cha (`git checkout --orphan master_fresh` hoặc xóa `.git` và `git init`), thêm toàn bộ mã nguồn hiện tại đã làm sạch vào rồi force push.
- **Ưu điểm**: 100% sạch sẽ dữ liệu lịch sử, không còn bất kỳ dấu vết cũ nào; dung lượng repo giảm tối đa.
- **Hậu quả & Nhược điểm cực kỳ nghiêm trọng**:
  - **Đứt gãy 100% lịch sử**: Mất toàn bộ **1,197 commits** phát triển từ tháng 10/2025.
  - **Mất hoàn toàn `git blame`**: Lập trình viên không thể tra cứu ai đã viết đoạn code nào, khi nào và vì lý do gì.
  - **Mất toàn bộ PR context và issue link**: Toàn bộ liên kết commit hash với 279 Pull Requests và issues trên GitHub bị đứt gãy hoàn toàn.
  - **Phá hủy tác quyền (Authorship)**: Không còn ghi nhận công sức đóng góp của từng thành viên trong quá khứ.
  - Làm gián đoạn hoàn toàn tất cả 66 nhánh nhánh tính năng đang phát triển song song.

---

### 2.4 Ma Trận So Sánh Đa Chiều (Comparison Matrix)

| Tiêu Chí Đánh Giá | `git-filter-repo` (Đề xuất tối ưu) | `BFG Repo-Cleaner` | `Tạo Fresh Repo` (Init mới) |
| :--- | :--- | :--- | :--- |
| **Tính triệt để** | **Tuyệt đối (100%)**: Thay thế sạch trong blob, commit tree và commit message. | **Khá (85-90%)**: Bỏ qua HEAD commit, xử lý commit message hạn chế. | **Tuyệt đối (100%)**: Xóa sạch toàn bộ quá khứ. |
| **Bảo tồn lịch sử (1,197 commits)** | **Hoàn hảo**: Giữ nguyên toàn bộ cấu trúc commit, timestamps, tác giả, cây merge. | **Tốt**: Giữ cấu trúc lịch sử, nhưng có thể lệch tip. | **PHÁ HỦY 100%**: Mất toàn bộ lịch sử, blame, tác quyền, PR context. |
| **Thay thế chuỗi IP/Secret chính xác** | **Xuất sắc**: File `replace-text.txt` hỗ trợ regex, literal string, RFC 5737. | **Cơ bản**: Thay thế chuỗi bằng `***REMOVED***`, hạn chế tùy biến. | **Không áp dụng**: Chỉ giữ trạng thái file hiện tại trên đĩa. |
| **Tốc độ thực thi** | **Rất nhanh**: ~5-15 giây cho 1,197 commits của Flama. | **Rất nhanh**: ~3-8 giây. | Tức thì (~1 giây). |
| **Tác động 25 nhánh local / 66 remote** | **Đồng bộ toàn diện**: Tùy chọn `--all` tự động viết lại mọi nhánh song song chuẩn xác. | Khó kiểm soát tip của từng nhánh trong số 66 branches. | Toàn bộ 66 nhánh remote trở thành vô nghĩa, phải tạo lại từ đầu. |
| **Hỗ trợ Submodule (`infra-vpn`)** | **An toàn**: Giữ nguyên gitlink và tree references của submodule. | Tiềm ẩn rủi ro corrupt gitlinks của submodule. | Phải cấu hình submodule lại từ đầu. |
| **Mức độ phức tạp & An toàn** | **Cao cấp & An toàn**: Tự động gỡ remote để chống push nhầm, kiểm soát chặt chẽ. | Trung bình, đòi hỏi cài đặt JRE. | Thao tác thô bạo, rủi ro con người cao. |
| **Khuyến nghị chính thức** | **KHUYÊN DÙNG CHÍNH THỨC** (Official Git Project Recommendation). | Chỉ dùng khi cần lọc file lớn đơn giản. | **KHÔNG KHUYÊN DÙNG** (Anti-pattern đối với sản phẩm đang hoạt động). |

---

### 2.5 Kết Luận Lựa Chọn Giải Pháp Tối Ưu

> [!TIP]
> **Giải pháp tối ưu được chỉ định**: Sử dụng **`git-filter-repo`** kết hợp với file cấu hình quy tắc thay thế chuỗi chuẩn hóa **`replace-text.txt`**.
> Phương án này vừa đảm bảo loại bỏ 100% chuỗi nhạy cảm và file rò rỉ, vừa bảo tồn trọn vẹn giá trị lịch sử 1,197 commits, quyền tác giả, ngữ cảnh phát triển và tính toàn vẹn của submodule `infra-vpn`.

---

## 3. Chuẩn Bị & Sao Lưu Tuyệt Đối An Toàn (Pre-scrubbing Prerequisites & Safe Backup)

Trước khi thực hiện bất kỳ thao tác viết lại lịch sử nào, bắt buộc phải thiết lập chốt bảo vệ dữ liệu đa tầng để đảm bảo **Khả năng phục hồi nguyên trạng 100%** trong trường hợp phát sinh sự cố.

### 3.1 Quy Trình Đóng Băng Commit (Freeze Window Protocol)
1. **Thông báo toàn đội ngũ**:
   - Gửi thông báo trên kênh trao đổi kỹ thuật (Discord/Slack/Telegram) trước ít nhất 1 giờ:
     ```text
     [THÔNG BÁO KHẨN - ĐÓNG BĂNG REPOSITORY FLAMA]
     Thời gian bắt đầu: [YYYY-MM-DD HH:mm UTC+7]
     Thời gian dự kiến: 60 phút.
     Lý do: Thực thi quy trình thanh lọc an ninh lịch sử Git (Git History Scrubbing).
     Yêu cầu:
     - DỪNG TOÀN BỘ việc push commit mới lên GitHub (origin).
     - Không merge bất kỳ Pull Request nào.
     - Giữ nguyên các nhánh tính năng cục bộ trên máy cá nhân theo hướng dẫn tại Mục 8.
     ```
2. **Khóa tạm thời các nhánh bảo vệ trên GitHub (Branch Protection Rules)**:
   - Truy cập: `https://github.com/TrinhChung/Flama/settings/branches`
   - Đảm bảo nhánh `master` tạm thời cho phép Administrator Force Push (bỏ tích "Do not allow force pushes" trong thời gian chạy runbook, sẽ kích hoạt lại ngay sau khi hoàn tất).

---

### 3.2 Tạo Git Bundle Toàn Vẹn (Full Git Bundle Backup)

Git Bundle đóng gói toàn bộ commits, branches, tags và objects thành một file nhị phân duy nhất, độc lập và có khả năng khôi phục nguyên vẹn kho chứa bất kỳ lúc nào.

#### Trên Linux / macOS / Git Bash:
```bash
# 1. Chuyển vào thư mục gốc của repository Flama hiện tại
cd /path/to/nihongo

# 2. Tạo bản sao lưu bundle toàn bộ references (--all)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
git bundle create ../flama_backup_full_${TIMESTAMP}.bundle --all

# 3. Xác minh tính toàn vẹn của bundle vừa tạo
git bundle verify ../flama_backup_full_${TIMESTAMP}.bundle
```

#### Trên Windows (PowerShell):
```powershell
# 1. Chuyển vào thư mục gốc repository
Set-Location -Path "d:\Project\nihongo"

# 2. Tạo bản sao lưu bundle toàn bộ references
$Timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
git bundle create "..\flama_backup_full_${Timestamp}.bundle" --all

# 3. Xác minh tính toàn vẹn của bundle
git bundle verify "..\flama_backup_full_${Timestamp}.bundle"
```

---

### 3.3 Tạo Mirror Clone Cô Lập Dự Phòng (Isolated Mirror Clone)

Tạo một bản sao lưu dạng bare mirror clone từ GitHub remote để lưu trữ dự phòng độc lập:

```bash
# Tạo thư mục sao lưu dự phòng ở ngoài workspace hiện tại
cd ..
git clone --mirror https://github.com/TrinhChung/Flama.git flama_backup_mirror.git

# Xác nhận số lượng nhánh và đối tượng đã được mirror đầy đủ
cd flama_backup_mirror.git
git show-ref --heads
cd ..
```

---

### 3.4 Xác Minh Tính Toàn Vẹn & Tạo Mã Checksum (Checksums Verification)

Lưu trữ mã hash SHA-256 của các file backup để phục vụ đối soát phục hồi:

#### Trên Linux / macOS:
```bash
sha256sum flama_backup_full_*.bundle > flama_backup_checksums.txt
cat flama_backup_checksums.txt
```

#### Trên Windows (PowerShell):
```powershell
Get-FileHash -Path ..\flama_backup_full_*.bundle -Algorithm SHA256 | Format-List
```

---

## 4. Cài Đặt Môi Trường & Thiết Lập Bản Đồ Ánh Xạ Chuỗi (Tooling Setup & Replacement Mapping)

### 4.1 Cài Đặt `git-filter-repo`

Công cụ yêu cầu Python 3.8+ và Git 2.22+.

#### Cài đặt qua `pip` (Áp dụng cho mọi hệ điều hành - Khuyến nghị):
```bash
# Cài đặt hoặc nâng cấp bản mới nhất của git-filter-repo
python -m pip install --upgrade git-filter-repo

# Kiểm tra công cụ đã được cài đặt thành công và hiển thị phiên bản
git-filter-repo --version
```

#### Cài đặt qua Package Managers thay thế:
- **macOS (Homebrew)**: `brew install git-filter-repo`
- **Ubuntu/Debian**: `sudo apt-get install git-filter-repo`
- **Windows (Scoop)**: `scoop install git-filter-repo`
- **Windows (Chocolatey)**: `choco install git-filter-repo`

---

### 4.2 Thiết Lập File Ánh Xạ Thay Thế Chuỗi Chuẩn RFC 5737 (`replace-text.txt`)

Tạo một file văn bản mang tên `replace-text.txt` trong thư mục chuẩn bị thực thi. Cú pháp của `git-filter-repo --replace-text` tuân theo định dạng:
```text
<chuỗi_cũ_cần_tìm>==><chuỗi_mới_thay_thế>
```
Nếu có dấu cách hoặc regex, `git-filter-repo` xử lý nguyên văn ký tự theo chuẩn UTF-8.

#### Nguyên Tắc Tuân Thủ Tiêu Chuẩn RFC 5737:
Tất cả các địa chỉ IP Public thật của máy chủ được thay thế tương ứng bằng các dải địa chỉ thử nghiệm được tổ chức IETF quy định tại **RFC 5737**, đảm bảo tính chân thực của tài liệu kỹ thuật mà không bao giờ định tuyến tới máy chủ thực tế trên toàn cầu:
- `192.0.2.0/24` (TEST-NET-1)
- `198.51.100.0/24` (TEST-NET-2)
- `203.0.113.0/24` (TEST-NET-3)

#### Nội Dung Chuẩn Xác 100% Của File `replace-text.txt`:
```text
# ==============================================================================
# FLAMA GIT-FILTER-REPO OFFICIAL REPLACEMENT MAPPING RULES (RFC 5737 COMPLIANT)
# ==============================================================================

# 1. BẢN ĐỒ THAY THẾ ĐỊA CHỈ IP PUBLIC MÁY CHỦ THẬT (RFC 5737)
187.77.131.151==>192.0.2.151
161.33.193.141==>198.51.100.141
132.145.115.226==>203.0.113.226

# 2. BẢN ĐỒ THAY THẾ KHÓA BÍ MẬT CỔNG GIAO TIẾP (SHARED GATEWAY SECRET)
flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4==>[REDACTED_GATEWAY_SECRET]

# 3. BẢN ĐỒ THAY THẾ GOOGLE OAUTH CLIENT ID VÀ TIỀN TỐ CLIENT ID
992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com==>[REDACTED_OAUTH_CLIENT_ID]
992185847654-b1aekjqb7dh3hddetgve8qfps17nro08==>[REDACTED_OAUTH_CLIENT_PREFIX]

# 4. BẢN ĐỒ THAY THẾ EMAIL QUẢN TRỊ VIÊN CÁ NHÂN
chungtrinh2k2@gmail.com==>noreply@flama.vn

# 5. BẢN ĐỒ THAY THẾ CÁC FALLBACK URL NỘI BỘ WIREGUARD TRONG CODE/DOCS
http://10.10.0.6:4792==>http://127.0.0.1:4792
ubuntu@10.10.0.6==>ubuntu@wg-worker212-ip
```

> [!NOTE]
> Thứ tự sắp xếp trong `replace-text.txt`: Chuỗi dài hơn phải được đặt trước chuỗi ngắn hơn (ví dụ: Google OAuth Client ID đầy đủ `.apps.googleusercontent.com` đặt trước chuỗi prefix ngắn `992185847654-b1aekjqb7dh3hddetgve8qfps17nro08`) để tránh hiện tượng thay thế một phần làm sót hậu tố.

---

## 5. Quy Trình Thực Thi Thanh Lọc Từng Bước (Step-by-Step Scrubbing Execution)

> [!CAUTION]
> **QUY TẮC BẢO VỆ WORKSPACE**:
> Tuyệt đối **KHÔNG** chạy `git-filter-repo` trực tiếp trong thư mục làm việc hàng ngày của bạn!
> Phải luôn tạo một bản **fresh clone cô lập** sang thư mục tạm thời để thao tác.

### 5.1 Khởi Tạo Không Gian Làm Việc Cô Lập (Isolated Scratchpad)

#### Trên Linux / macOS:
```bash
# Di chuyển ra thư mục làm việc cha
cd ..

# Clone một bản sao mới từ chính thư mục local hiện tại (hoặc từ mirror backup)
git clone flama_backup_mirror.git flama-filter-workspace
cd flama-filter-workspace

# Đảm bảo tất cả các remote branches đều được theo dõi cục bộ để filter áp dụng toàn bộ
git checkout master
```

#### Trên Windows (PowerShell):
```powershell
Set-Location -Path ".."
# Clone bản làm việc cô lập từ mirror hoặc repo hiện tại
git clone "flama_backup_mirror.git" "flama-filter-workspace"
Set-Location -Path "flama-filter-workspace"
git checkout master
```

---

### 5.2 Thực Thi Thanh Lọc Chuỗi Nhạy Cảm Trên Toàn Bộ Lịch Sử

Sao chép file `replace-text.txt` đã chuẩn bị ở Bước 4 vào thư mục gốc của `flama-filter-workspace`.

```bash
# Chạy git-filter-repo để thay thế chuỗi trên TOÀN BỘ 1,197 commits và tất cả branches
git-filter-repo --replace-text replace-text.txt --force
```

#### Giải thích các tham số:
- `--replace-text replace-text.txt`: Đọc bản đồ thay thế và quét qua từng file trong từng commit tree, thực hiện thay thế nội dung byte-by-byte và cập nhật lại SHA hash của commit.
- `--force`: Cho phép thực thi trên repo vừa clone (bỏ qua cảnh báo an toàn mặc định của git-filter-repo).

Quá trình xử lý sẽ hiển thị tiến trình tương tự:
```text
Parsed 1197 commits
Scanned 1197 commits
Writing updated commits...
Committed 1197 commits
Completely finished after 8.42 seconds.
```

---

### 5.3 Xử Lý Các Đường Dẫn File Nhạy Cảm Lịch Sử (Sensitive Paths Cleanup)

Nếu cần loại bỏ hoàn toàn các file cấu hình deploy nhạy cảm lịch sử hoặc tài liệu nghiên cứu rủi ro cũ (`docs/architecture/INFRASTRUCTURE_WORKLOAD_DISTRIBUTION_ORACLE_WORKER212.md`), chạy thêm lệnh lọc đường dẫn:

```bash
# Ví dụ: Xóa bỏ file tài liệu chứa IP cũ khỏi toàn bộ lịch sử (nếu chưa được thay thế chuỗi)
git-filter-repo --path docs/architecture/INFRASTRUCTURE_WORKLOAD_DISTRIBUTION_ORACLE_WORKER212.md --invert-paths --force
```

> [!NOTE]
> Do bước 5.2 đã thay thế toàn bộ IP và secret trong tất cả các file thành chuỗi RFC 5737 và `[REDACTED_*]`, việc giữ lại cấu trúc file tài liệu giúp bảo toàn ngữ cảnh kiến trúc mà không gây rò rỉ bất kỳ bí mật nào.

---

### 5.4 Dọn Dẹp Reflog Và Thu Gom Rác Bộ Nhớ (Garbage Collection)

Sau khi `git-filter-repo` hoàn tất, công cụ tự động làm sạch reflog. Tuy nhiên, để đảm bảo các object cũ không còn nằm trong cơ sở dữ liệu git local:

```bash
# Hủy toàn bộ log tham chiếu cũ
git reflog expire --expire=now --all

# Thu gom rác và tối ưu hóa nén kho chứa
git gc --prune=now --aggressive
```

---

## 6. Bộ Kịch Bản Kiểm Tra & Đối Soát Hậu Thanh Lọc (Post-Filter Automated Verification Suite)

Trước khi thực hiện force push, kho chứa đã lọc phải trải qua bộ kiểm tra đối soát với kết quả **100% PASS** (Không tìm thấy bất kỳ chuỗi rò rỉ nào trong toàn bộ lịch sử commit).

### 6.1 Kiểm Tra Đối Soát Bằng Lệnh Git Chuyên Dụng

Chạy thử nghiệm tìm kiếm sự xuất hiện của các chuỗi bí mật trong toàn bộ lịch sử commit (`git log -S`):

```bash
# 1. Kiểm tra 3 IP Public thật:
git log --all -S "187.77.131.151"
git log --all -S "161.33.193.141"
git log --all -S "132.145.115.226"

# 2. Kiểm tra Gateway Secret Token:
git log --all -S "flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4"

# 3. Kiểm tra Google OAuth Client ID Production:
git log --all -S "992185847654-b1aekjqb7dh3hddetgve8qfps17nro08"

# 4. Kiểm tra Email Cá Nhân Quản Trị:
git log --all -S "chungtrinh2k2@gmail.com"
```

> **Yêu cầu tiêu chuẩn**: Tất cả các lệnh trên phải trả về kết quả **rỗng (không có commit nào được hiển thị)**.

---

### 6.2 Script Một Chạm Kiểm Tra Toàn Diện Cho Linux / macOS (`verify_history_clean.sh`)

Lưu script sau thành file `verify_history_clean.sh` và thực thi:

```bash
#!/usr/bin/env bash
# ==============================================================================
# FLAMA POST-SCRUBBING AUTOMATED SECURITY VERIFICATION SUITE
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=================================================================${NC}"
echo -e "${BLUE}        BẮT ĐẦU KIỂM TRA ĐỐI SOÁT LỊCH SỬ GIT FLAMA              ${NC}"
echo -e "${BLUE}=================================================================${NC}"

TOTAL_LEAKS=0

# Danh sách tất cả chuỗi nhạy cảm bị cấm xuất hiện trong lịch sử
SENSITIVE_PATTERNS=(
    "187.77.131.151"
    "161.33.193.141"
    "132.145.115.226"
    "flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4"
    "992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com"
    "992185847654-b1aekjqb7dh3hddetgve8qfps17nro08"
    "chungtrinh2k2@gmail.com"
)

for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    echo -n "Kiểm tra chuỗi: [$pattern] ... "
    MATCH_COUNT=$(git log --all -S "$pattern" --oneline | wc -l)
    if [ "$MATCH_COUNT" -gt 0 ]; then
        echo -e "${RED}[FAILED] - Phát hiện $MATCH_COUNT commit chứa rò rỉ!${NC}"
        git log --all -S "$pattern" --oneline
        TOTAL_LEAKS=$((TOTAL_LEAKS + MATCH_COUNT))
    else
        echo -e "${GREEN}[PASSED - SẠCH SẼ]${NC}"
    fi
done

echo -e "\nKiểm tra chuỗi trên cây thư mục hiện tại (Working Tree)..."
for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    GREP_COUNT=$(git grep -I "$pattern" 2>/dev/null | wc -l || true)
    if [ "$GREP_COUNT" -gt 0 ]; then
        echo -e "${RED}[FAILED] - Phát hiện chuỗi [$pattern] trên file đĩa!${NC}"
        TOTAL_LEAKS=$((TOTAL_LEAKS + GREP_COUNT))
    fi
done

echo -e "${BLUE}-----------------------------------------------------------------${NC}"
if [ "$TOTAL_LEAKS" -eq 0 ]; then
    echo -e "${GREEN}>>> TUYỆT VỜI: 100% LỊCH SỬ GIT ĐÃ ĐƯỢC LÀM SẠCH HOÀN TOÀN! <<<${NC}"
    echo -e "${GREEN}>>> ĐỦ ĐIỀU KIỆN TIẾN HÀNH BƯỚC RE-BIND REMOTE VÀ FORCE PUSH.  <<<${NC}"
    exit 0
else
    echo -e "${RED}>>> CẢNH BÁO NGUY HIỂM: CÒN $TOTAL_LEAKS ĐIỂM RÒ RỈ CHƯA ĐƯỢC XỬ LÝ! <<<${NC}"
    echo -e "${RED}>>> TUYỆT ĐỐI KHÔNG FORCE PUSH. KIỂM TRA LẠI FILE replace-text.txt! <<<${NC}"
    exit 1
fi
```

---

### 6.3 Script Một Chạm Kiểm Tra Toàn Diện Cho Windows PowerShell (`Verify-HistoryClean.ps1`)

Lưu script sau thành file `Verify-HistoryClean.ps1` và thực thi:

```powershell
<#
==============================================================================
 FLAMA POST-SCRUBBING AUTOMATED SECURITY VERIFICATION (POWERSHELL)
==============================================================================
#>
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "        BẮT ĐẦU KIỂM TRA ĐỐI SOÁT LỊCH SỬ GIT FLAMA             " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$TotalLeaks = 0
$SensitivePatterns = @(
    "187.77.131.151",
    "161.33.193.141",
    "132.145.115.226",
    "flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4",
    "992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com",
    "992185847654-b1aekjqb7dh3hddetgve8qfps17nro08",
    "chungtrinh2k2@gmail.com"
)

foreach ($pattern in $SensitivePatterns) {
    Write-Host -NoNewline "Kiểm tra chuỗi: [$pattern] ... "
    $commits = git log --all -S "$pattern" --oneline
    if ($commits) {
        $count = ($commits | Measure-Object).Count
        Write-Host "[FAILED] - Phát hiện $count commit rò rỉ!" -ForegroundColor Red
        $TotalLeaks += $count
    } else {
        Write-Host "[PASSED - SẠCH SẼ]" -ForegroundColor Green
    }
}

Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan
if ($TotalLeaks -eq 0) {
    Write-Host ">>> XÁC NHẬN: 100% LỊCH SỬ GIT ĐÃ ĐƯỢC THANH LỌC HOÀN TOÀN! <<<" -ForegroundColor Green
    Write-Host ">>> ĐỦ ĐIỀU KIỆN TIẾN HÀNH BƯỚC RE-BIND REMOTE VÀ FORCE PUSH. <<<" -ForegroundColor Green
    exit 0
} else {
    Write-Host ">>> CẢNH BÁO: PHÁT HIỆN $TotalLeaks ĐIỂM RÒ RỈ! DỪNG NGAY LẬP TỨC! <<<" -ForegroundColor Red
    exit 1
}
```

---

### 6.4 Đối Soát Tính Nguyên Vẹn Của Submodule `infra-vpn` Và Nhánh Chính

Xác minh cấu trúc của submodule private và tính toàn vẹn của nhánh:

```bash
# 1. Kiểm tra cấu hình submodule trong .gitmodules
git submodule status

# 2. Kiểm tra commit số lượng trên nhánh master đã lọc
git rev-list --count HEAD
# Kỳ vọng: ~1,176 commits (bảo toàn trọn vẹn số lượng commit ban đầu)

# 3. Xem 5 commit gần nhất để kiểm tra metadata (author, message, date)
git log -n 5 --pretty=format:"%h - %an <%ae> (%ad): %s"
```

---

## 7. Tái Cấu Hình Remote & Force Push Có Kiểm Soát (Remote Re-binding & Controlled Force Push)

`git-filter-repo` theo thiết kế bảo vệ nghiêm ngặt sẽ **tự động xóa bỏ URL của remote `origin`** khỏi cấu hình kho chứa để ngăn chặn việc vô tình push lịch sử đã sửa khi chưa kiểm tra cẩn thận.

### 7.1 Tái Liên Kết Remote Origin

```bash
# Thêm lại remote origin trỏ về repository chính thức trên GitHub
git remote add origin https://github.com/TrinhChung/Flama.git

# Kiểm tra lại cấu hình remote
git remote -v
```

---

### 7.2 Kiểm Tra Đối Chiếu Trước Khi Push (Sanity Pre-push Check)

```bash
# Kiểm tra danh sách các nhánh cục bộ đã sẵn sàng
git branch -a

# Kiểm tra đảm bảo không có uncommitted changes
git status
```

---

### 7.3 Thực Hiện Force Push An Toàn Lên GitHub

> [!WARNING]
> **THAO TÁC CÓ TÍNH CHẤT KHÔNG THỂ HOÀN TÁC TRÊN GITHUB**:
> Lệnh dưới đây sẽ ghi đè toàn bộ tham chiếu của tất cả các nhánh (`--all`) trên kho chứa GitHub bằng lịch sử đã được làm sạch. Chỉ thực hiện khi các bước kiểm tra ở Mục 6 đã đạt **100% PASSED**.

```bash
# 1. Force push toàn bộ các nhánh đã được làm sạch lên GitHub
git push origin --force --all

# 2. Force push toàn bộ tags (nếu có trong tương lai)
git push origin --force --tags
```

Sau khi hoàn tất, nhánh `master` và toàn bộ 66 nhánh trên GitHub sẽ sở hữu lịch sử commit mới hoàn toàn không chứa bất kỳ địa chỉ IP hay Secret nào.

---

## 8. Hướng Dẫn Đồng Bộ Dành Cho Cộng Tác Viên (Collaborator Rebase & Recovery Runbook)

Sau khi repository remote bị force push viết lại lịch sử, kho chứa cục bộ của các cộng tác viên và lập trình viên trong đội ngũ sẽ ở trạng thái **lệch gốc commit (diverged history)**. Nếu cộng tác viên chạy `git pull` hoặc `git merge`, Git sẽ hòa trộn nhánh cũ và nhánh mới, **làm xuất hiện trở lại các commit chứa dữ liệu rò rỉ vào repository**.

Tất cả thành viên trong nhóm BẮT BUỘC thực hiện một trong hai quy trình phục hồi dưới đây tùy thuộc vào trạng thái làm việc cục bộ của họ:

---

### 8.1 Trường Hợp 1: Lập Trình Viên KHÔNG CÓ Commit Dở Dang (Clean Working Copy)

Dành cho lập trình viên chỉ đọc mã nguồn, đang ở nhánh `master` hoặc các commit đã được push/merge lên remote trước đó.

Thực hiện chuỗi lệnh sau trong thư mục làm việc cục bộ:

```bash
# 1. Kéo toàn bộ tham chiếu mới từ GitHub về máy
git fetch origin

# 2. Chuyển sang nhánh master
git checkout master

# 3. Đưa nhánh master cục bộ trỏ chuẩn xác vào origin/master mới
git reset --hard origin/master

# 4. Xóa bỏ hoàn toàn toàn bộ reflog cũ chứa commit rò rỉ
git reflog expire --expire=now --all

# 5. Dọn dẹp và thu gom rác bộ nhớ cục bộ
git gc --prune=now
```

---

### 8.2 Trường Hợp 2: Lập Trình Viên ĐANG CÓ Nhánh Tính Năng Dở Dang (In-flight Feature Branches)

Dành cho lập trình viên đang phát triển dở một tính năng trên nhánh cục bộ (ví dụ: nhánh `feature/my-new-feature`) chứa các commit cá nhân **chưa từng được push lên remote**.

### 8.3 Sơ Đồ Cơ Chế Hoạt Động Của `git rebase --onto`

```text
[LỊCH SỬ CŨ BỊ RÒ RỈ TRÊN MÁY DEV]:
  A --- B (Chứa Secret) --- C (Chứa IP) ─── D (Commit mới của Dev 1) ─── E (Commit mới của Dev 2)
                            ▲               [Nhánh feature cục bộ: feature/my-new-feature]
                            │
               [Điểm rẽ nhánh cũ: OLD_BASE]

[LỊCH SỬ MỚI ĐÃ LÀM SẠCH TRÊN GITHUB]:
  A' --- B' (Đã Redact) --- C' (Đã Redact)
                            ▲
                            │
              [Gốc lịch sử mới: origin/master]

════════════════════════════════════════════════════════════════════════════════════════
QUY TRÌNH DI CHUYỂN BẰNG: git rebase --onto origin/master OLD_BASE feature/my-new-feature
════════════════════════════════════════════════════════════════════════════════════════

[KẾT QUẢ SAU REBASE --ONTO]:
  A' --- B' --- C' ─── D' ─── E'  [Nhánh feature được cấy ghép an toàn lên lịch sử sạch!]
                      (Các commit mới giữ nguyên nội dung, không kéo theo rò rỉ cũ)
```

#### Các Bước Thực Hiện Chi Tiết Cho Lập Trình Viên:

```bash
# Bước 1: Fetch toàn bộ lịch sử mới đã được thanh lọc
git fetch origin

# Bước 2: Xác định commit cha cũ (commit cuối cùng trước khi bắt đầu tạo nhánh feature)
# Giả sử commit đó có hash là abc1234 (hoặc tag / ref cũ)
OLD_BASE="abc1234"

# Bước 3: Cấy ghép các commit mới của nhánh feature lên đỉnh của origin/master sạch
git rebase --onto origin/master $OLD_BASE feature/my-new-feature

# Bước 4: Kiểm tra lại các commit trên nhánh feature để đảm bảo không mang theo secret cũ
git log -n 5 --oneline

# Bước 5: Tiếp tục công việc phát triển và push bình thường
git push origin feature/my-new-feature --force-with-lease
```

---

## 9. Các Hành Động An Ninh Hậu Kỳ & Tẩy Sạch Cache GitHub (Post-scrubbing Security Hardening)

Thanh lọc lịch sử Git bằng `git-filter-repo` và force-push giải quyết 95% vấn đề. Tuy nhiên, 5% còn lại nằm ở cơ chế lưu trữ nội bộ của GitHub và việc vô hiệu hóa thực tế các thông số đã phơi bày.

### 9.1 Tẩy Sạch Bộ Nhớ Đệm Commit Mồ Côi Trên GitHub (GitHub Cached Commit Refs Purge)

GitHub duy trì một cơ chế bộ nhớ đệm nội bộ gọi là **Cached Commit Views**. Kể cả khi nhánh đã bị force push, bất kỳ ai có link URL commit hash cũ (ví dụ: `https://github.com/TrinhChung/Flama/commit/0ee1a4097...`) vẫn có thể xem được nội dung commit cho đến khi GitHub chạy garbage collection nội bộ.

#### Hai Phương Pháp Tẩy Sạch Triệt Để:

#### Phương Pháp A: Chuyển Đổi Trạng Thái Repository (Nhanh nhất - Khuyên dùng)
1. Truy cập: `https://github.com/TrinhChung/Flama/settings`
2. Kéo xuống phần **Danger Zone** -> Chọn **Change repository visibility**.
3. Chuyển repository thành **Private**.
   - *Tác động*: Khi chuyển sang Private, GitHub tự động dọn sạch các cache view công khai, ngắt kết nối các fork công khai mồ côi và làm mới reflog cache.
4. Đợi khoảng 5-10 phút.
5. Chuyển lại trạng thái repository thành **Public** (nếu đây là dự án mã nguồn mở).
6. Thử truy cập lại link commit cũ: `https://github.com/TrinhChung/Flama/commit/0ee1a4097...` ➔ Kết quả kỳ vọng: **404 Not Found**.

#### Phương Pháp B: Liên Hệ Hỗ Trợ GitHub (GitHub Support Ticket)
Nếu không muốn đổi visibility:
- Gửi yêu cầu qua [GitHub Support Portal](https://support.github.com/contact):
  - Tiêu đề: *Request to clear cached commits and unreachable objects after secret scrubbing*.
  - Nội dung: Cung cấp link repo `https://github.com/TrinhChung/Flama` và yêu cầu GitHub chạy `git gc --prune=now` trên máy chủ lưu trữ của họ.

---

### 9.2 Quy Trình Xoay Vòng Bí Mật Thực Tế Trên Các Cụm Máy Chủ (Server Secrets Rotation)

Việc viết lại lịch sử Git chỉ bảo vệ kho mã nguồn. Toàn bộ các bí mật đã lộ trên Internet phải được coi là **đã bị xâm phạm (compromised)** và bắt buộc phải được xoay vòng ngay lập tức trên hạ tầng thật:

1. **Xoay Vòng Gateway Secret Token**:
   - Sinh token ngẫu nhiên mới với 256-bit entropy:
     ```bash
     openssl rand -hex 32
     ```
   - Cập nhật giá trị mới vào file cấu hình bảo mật `/etc/flama/flama.env` trên Hostinger Chung VPS và Worker 212.
   - Cập nhật cấu hình proxy header trong Nginx trên OV Gateway (`media.flama.vn`).
   - Khởi động lại service `flama-media` và `nginx`.

2. **Cấu Hình Tường Lửa UFW Ngăn Chặn Truy Cập Trực Tiếp (WAF Bypass Mitigation)**:
   - Trên **Hostinger Chung VPS** (`187.77.131.151`):
     - Chặn truy cập trực tiếp từ Internet vào cổng Gunicorn `4789`, MySQL `3306`, Redis `6379`.
     - Chỉ cho phép IP WireGuard `10.10.0.0/24` và các dải IP chính thức của Cloudflare truy cập HTTP/HTTPS:
       ```bash
       sudo ufw default deny incoming
       sudo ufw allow in on wg0
       sudo ufw allow 22/tcp
       sudo ufw reload
       ```
   - Trên **Tokyo Worker 212** (`132.145.115.226`):
     - Chặn hoàn toàn cổng `4792` từ Internet, chỉ cho phép nhận request từ OV Gateway qua IP WireGuard `10.10.0.5`.

3. **Thu Hồi & Tạo Mới Khóa SSH / SSL**:
   - Thay thế toàn bộ SSH keys cá nhân trên các máy chủ Ubuntu.
   - Gia hạn lại chứng chỉ SSL Let's Encrypt cho các domain `flama.vn`, `api.flama.vn`, `media.flama.vn`.

4. **Xoay Vòng Google OAuth Client Secret & Rà Soát Redirect URIs**:
   - Truy cập [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
   - Kiểm tra toàn bộ danh sách Authorized JavaScript Origins và Authorized Redirect URIs.
   - Thu hồi Client Secret cũ nếu có nghi ngờ và tạo bộ thông tin định danh mới.

---

## 10. Kế Hoạch Dự Phòng & Phục Hồi Thất Bại (Rollback & Disaster Recovery Plan)

Nếu trong quá trình chạy `git-filter-repo` phát sinh sự cố không mong muốn (mất commit, lỗi cú pháp hoặc hỏng cây liên kết), thực hiện khôi phục ngay lập tức từ bản backup đã tạo ở Mục 3:

### 10.1 Khôi Phục Nhanh Từ Git Bundle
```bash
# 1. Xóa thư mục làm việc bị lỗi
cd ..
rm -rf flama-filter-workspace

# 2. Khôi phục lại kho chứa nguyên trạng từ file Git Bundle
git clone flama_backup_full_*.bundle flama-restored
cd flama-restored

# 3. Đặt lại remote origin
git remote set-url origin https://github.com/TrinhChung/Flama.git

# 4. Kiểm tra đối soát lịch sử
git log -n 5 --oneline
```

### 10.2 Khôi Phục Remote GitHub Từ Mirror Clone
Nếu lỡ force push lên GitHub nhưng phát hiện lỗi:
```bash
cd flama_backup_mirror.git

# Force push ngược toàn bộ mirror backup trở lại GitHub
git push --mirror https://github.com/TrinhChung/Flama.git
```

Kho chứa trên GitHub sẽ được khôi phục nguyên vẹn 100% như thời điểm trước khi can thiệp.

---

*Tài liệu Runbook này được biên soạn và kiểm chứng theo chuẩn an ninh DevSecOps của Dự Án Flama — Cập nhật lần cuối: 2026-11-01.*
