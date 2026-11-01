# Kế hoạch và Runbook Thiết lập MySQL 8.0 Master-Slave (GTID-Based)
## Giữa VPS Chính (Master) và Máy Chủ 212 (Slave / Read-Only Replica)

- **Domain**: Infrastructure & Database Operations
- **Hệ thống**: Flama Production Database
- **Phiên bản MySQL**: MySQL 8.0 (InnoDB engine, utf8mb4)
- **Kiến trúc**: Single-Primary Asynchronous Replication sử dụng GTID (Global Transaction Identifier)
- **Máy chủ Master**: VPS Chính (Hostinger Production VPS)
- **Máy chủ Slave**: Máy chủ 212 (Dedicated Read-Only Replica Server)
- **Trạng thái**: Kế hoạch vận hành & Hướng dẫn kỹ thuật chuẩn (Production Runbook)

---

## 1. Tổng quan kiến trúc & Mục tiêu triển khai

### 1.1. Bối cảnh & Mục tiêu
Theo phân tích đo lường workload Flama (`docs/architecture/FLAMA_WORKLOAD_TELEMETRY_AND_RESOURCE_RATIOS_2026-10-31.md`), hệ thống có tỷ lệ đọc chiếm tới **91.47%** tổng lưu lượng cơ sở dữ liệu. Nhằm giảm tải CPU, I/O và giải phóng bộ nhớ đệm InnoDB Buffer Pool trên VPS chính, mô hình Master-Slave được triển khai với:
- **VPS Chính (Master / Primary)**: Tiếp nhận toàn bộ truy vấn ghi (INSERT, UPDATE, DELETE), các transaction ACID quan trọng của phiên học (Study Review, Session Commit, Outbox Event Drain), và quản lý schema migrations qua Alembic.
- **Máy Chủ 212 (Slave / Replica)**: Hoạt động ở chế độ nghiêm ngặt **Read-Only / Super Read-Only**, đồng bộ dữ liệu thời gian thực từ Master qua binary log với GTID. Đảm nhận các truy vấn đọc nặng: tra cứu từ vựng (`/api/v1/browse/*`), marketplace explore (`/api/v1/marketplace/*`), export dữ liệu và các tác vụ báo cáo quản trị.
- **Dự phòng thảm họa (Disaster Recovery / Hot Standby)**: Sẵn sàng thăng cấp thành Primary khi VPS chính cần bảo trì phần cứng hoặc gặp sự cố mạng diện rộng.

### 1.2. Sơ đồ luồng nhân bản dữ liệu (Replication Topology)

```text
┌────────────────────────────────────────────────────────┐
│                   VPS CHÍNH (MASTER)                   │
│  - server-id = 1                                       │
│  - IP: <MASTER_VPS_IP>                                 │
│  - MySQL 8.0 (Port 3306)                               │
│  - Ghi binary log: mysql-bin.xxxxxx (ROW format)       │
│  - GTID: <MASTER_UUID>:1-N                             │
│                                                        │
│  [Flama Web / Study Worker] ──(Ghi & Đọc quan trọng)──┐│
└───────────────────────────┬────────────────────────────┘
                            │ Binary Log Event Stream
                            │ (TCP Port 3306 - SSL/TLS)
                            │ User: repl_user
                            ▼
┌────────────────────────────────────────────────────────┐
│                   MÁY CHỦ 212 (SLAVE)                  │
│  - server-id = 212                                     │
│  - IP: <SLAVE_212_IP>                                  │
│  - MySQL 8.0 (Port 3306)                               │
│  - read_only = ON & super_read_only = ON               │
│  - Relay Log: mysql-relay-bin.xxxxxx                   │
│  - GTID Auto-Positioning: ON                           │
│                                                        │
│  [Tra cứu Browse / Báo cáo] ──(Đọc tải nặng)──────────┘│
└────────────────────────────────────────────────────────┘
```

### 1.3. Chiến lược định tuyến ứng dụng và phân luồng Đọc/Ghi (Application Traffic Routing)
Hiện tại, Flama backend cấu hình kết nối DB qua tệp `/etc/flama/flama.env` với biến đơn `DB_HOST` (`app/settings.py`). Để khai thác tối đa Máy chủ 212 làm Read Replica mà không gây xung đột kiến trúc, lộ trình định tuyến được phân định theo 3 phương án:
1. **Phương án tức thì (Tác vụ nền & Báo cáo độc lập)**: Các tiến trình nền như export dữ liệu (`scripts/export_*`), cronjob kiểm kê, tác vụ báo cáo quản trị hoặc worker phân tích thống kê nặng được cấu hình biến môi trường riêng `DB_READ_HOST=<SLAVE_212_IP>` hoặc kết nối trực tiếp vào Máy chủ 212.
2. **Phương án ngắn hạn (ProxySQL Database Middleware)**: Cài đặt ProxySQL làm proxy trung gian ngay trên VPS chính hoặc Máy chủ 212. ProxySQL tự động phân tích câu lệnh SQL: mọi truy vấn `SELECT` thông thường từ endpoints browse/marketplace được định tuyến tự động sang Máy chủ 212 (Port 3306), trong khi các transaction `SELECT ... FOR UPDATE`, `INSERT`, `UPDATE`, `DELETE` luôn chuyển tới Master. Backend Flama chỉ cần giữ nguyên `DB_HOST=127.0.0.1:6033` (cổng ProxySQL) mà không phải sửa code ứng dụng.
3. **Phương án dài hạn (SQLAlchemy Binds & Dynamic Routing Session)**: Mở rộng `app/settings.py` để hỗ trợ `SQLALCHEMY_BINDS` hoặc triển khai `RoutingSession` trong SQLAlchemy, tự động chuyển luồng `get_bind()` sang replica khi thực hiện truy vấn đọc trong route read-only.

---

## 2. Cấu hình chi tiết MySQL (`my.cnf` / `mysqld.cnf`)

Tệp cấu hình mặc định trên Ubuntu thường nằm tại `/etc/mysql/mysql.conf.d/mysqld.cnf` hoặc `/etc/mysql/my.cnf`.

### 2.1. Cấu hình trên VPS Chính (Master)

Mở tệp cấu hình trên VPS Master:
```bash
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf
```

Thêm hoặc điều chỉnh các tham số sau trong khối `[mysqld]`:

```ini
[mysqld]
# --- Định danh máy chủ ---
server-id                = 1

# --- Cấu hình Mạng & Kết nối ---
# Cho phép MySQL lắng nghe trên địa chỉ IP công khai hoặc IP mạng riêng VPN (WireGuard/Tailscale)
# Tuyệt đối bảo vệ bằng UFW firewall (xem mục 3.1)
bind-address             = 0.0.0.0
port                     = 3306

# --- Cấu hình Binary Logging ---
log_bin                  = /var/log/mysql/mysql-bin.log
binlog_format            = ROW
binlog_row_image         = FULL
max_binlog_size          = 500M
binlog_expire_logs_seconds = 604800   # Lưu trữ binary log trong 7 ngày (MySQL 8.0)
sync_binlog              = 1          # Đảm bảo an toàn ACID tối đa cho Master

# --- Cấu hình GTID (Global Transaction Identifier) ---
gtid_mode                = ON
enforce_gtid_consistency = ON

# --- Phạm vi Database nhân bản (Cảnh báo quan trọng) ---
# KHUYẾN NGHỊ: KHÔNG bật binlog_do_db trên Master. Trong MySQL, binlog_do_db phụ thuộc vào cơ chế
# database ngữ cảnh (USE db); nếu truy vấn hoặc migration không gọi 'USE flama' trước, sự kiện sẽ
# BỊ BỎ SÓT âm thầm khỏi binlog, làm lệch dữ liệu replica. Hãy để Master ghi đầy đủ binary log,
# và nếu cần lọc database trên Slave, hãy cấu hình 'replicate_wild_do_table = flama.%' trên Slave.
# binlog_do_db             = flama

# --- Tối ưu hóa InnoDB cho Master ---
innodb_flush_log_at_trx_commit = 1
# Lưu ý về Buffer Pool: Trên môi trường dev local của Flama, innodb_buffer_pool_size được cố ý đặt 128M
# để bẫy truy vấn quét rộng/N+1. Nhưng trên VPS Production Hostinger, hãy cấp phát theo dung lượng RAM thực tế:
# VPS 4GB RAM: 2G; VPS 8GB RAM: 4G-5G (khoảng 50-70% RAM máy chủ chuyên dụng cho MySQL).
innodb_buffer_pool_size        = 2G
```

Khởi động lại MySQL trên Master để áp dụng cấu hình:
```bash
sudo systemctl restart mysql
sudo systemctl status mysql
```

---

### 2.2. Cấu hình trên Máy Chủ 212 (Slave / Replica)

Mở tệp cấu hình trên Máy chủ 212:
```bash
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf
```

Thêm hoặc điều chỉnh các tham số sau trong khối `[mysqld]`:

```ini
[mysqld]
# --- Định danh máy chủ (Duy nhất, không trùng với Master) ---
server-id                = 212

# --- Cấu hình Mạng ---
bind-address             = 0.0.0.0
port                     = 3306

# --- Chế độ Bảo vệ Chống Ghi (Read-Only Guard) ---
# read_only: Chặn mọi user thông thường ghi dữ liệu
# super_read_only: Chặn cả user có quyền SUPER/SYSTEM_VARIABLES_ADMIN (kể cả root) ghi dữ liệu.
# Chỉ duy nhất luồng replication applier thread mới được phép cập nhật dữ liệu.
# CẢNH BÁO VẬN HÀNH: Trong quy trình đồng bộ snapshot ban đầu (Mục 4.3), root sẽ tạm thời tắt cờ này
# bằng 'SET GLOBAL super_read_only = 0' để nạp dữ liệu dump, sau đó bật lại trước khi START REPLICA.
read_only                = 1
super_read_only          = 1

# --- Cấu hình GTID ---
gtid_mode                = ON
enforce_gtid_consistency = ON

# --- Lọc Database trên Slave (Tùy chọn khuyến nghị an toàn thay vì lọc trên Master) ---
# Chỉ replicate các bảng thuộc schema flama, an toàn tuyệt đối với mọi ngữ cảnh câu lệnh
# replicate_wild_do_table = flama.%

# --- Cấu hình Binary Log & Relay Log ---
log_bin                  = /var/log/mysql/mysql-bin.log
binlog_format            = ROW
binlog_row_image         = FULL
max_binlog_size          = 500M
binlog_expire_logs_seconds = 604800   # Lưu trữ binary log trong 7 ngày (phòng ngừa đầy đĩa khi bật log_replica_updates)
relay_log                = /var/log/mysql/mysql-relay-bin.log
log_replica_updates      = ON        # MySQL 8.0.26+ (tương đương log_slave_updates trong bản cũ)
relay_log_recovery       = ON        # Tự động phục hồi relay log an toàn nếu Slave bị mất điện đột ngột

# --- Tối ưu hóa Thực thi Song song (MTS - Multi-Threaded Replica) ---
# Giảm thiểu tối đa Replication Lag khi Master thực hiện ghi dữ liệu hàng loạt
replica_parallel_workers = 4         # Số luồng apply song song (điều chỉnh theo số vCPU của máy 212)
replica_parallel_type    = LOGICAL_CLOCK
replica_preserve_commit_order = ON   # Bảo toàn tuyệt đối thứ tự commit giao dịch giống như Master
replica_pending_jobs_size_max = 1073741824 # 1GB hàng đợi coordinator, tránh nghẽn khi Master ghi lô lớn

# --- Giới hạn Timeout & Phục hồi Kết nối ---
replica_net_timeout      = 60

# --- Tối ưu hóa InnoDB cho Slave ---
# Trên Slave có thể nới lỏng flush log để tăng tốc độ ghi relay log
innodb_flush_log_at_trx_commit = 2
sync_binlog              = 0
# Cấp phát 50-70% RAM của Máy chủ 212 cho Buffer Pool để tối ưu hóa truy vấn đọc từ vựng/marketplace
# Ví dụ máy 212 có 8GB RAM thì cấu hình 4G-5G:
innodb_buffer_pool_size        = 4G
```

Khởi động lại MySQL trên Máy chủ 212:
```bash
sudo systemctl restart mysql
sudo systemctl status mysql
```

---

### 2.3. Bảng giải thích chi tiết các tham số cấu hình cốt lõi

| Tham số | Giá trị Master | Giá trị Slave 212 | Ý nghĩa và Ràng buộc kỹ thuật |
|---|---|---|---|
| `server-id` | `1` | `212` | Định danh nguyên vẹn duy nhất cho từng node trong cụm. Trùng ID sẽ làm đứt kết nối replication ngay lập tức. |
| `gtid_mode` | `ON` | `ON` | Bật định danh giao dịch toàn cầu. Mỗi transaction trên Master được gán 1 mã duy nhất (`UUID:Sequence`). Loại bỏ hoàn toàn sự phụ thuộc vào tọa độ file/offset thủ công (`binlog-file` và `position`). |
| `enforce_gtid_consistency` | `ON` | `ON` | Ngăn chặn các câu lệnh SQL không an toàn với GTID (ví dụ: `CREATE TABLE ... SELECT`, hoặc tạo temporary table bên trong transaction). |
| `log_bin` | Bật | Bật | Ghi lại mọi biến động dữ liệu. Bắt buộc trên Master để stream cho Slave; khuyến nghị bật trên Slave để sẵn sàng làm Master dự phòng. |
| `binlog_format` | `ROW` | `ROW` | Ghi lại chính xác sự thay đổi của từng dòng dữ liệu (Row-Based Replication). Đảm bảo tính nhất quán tuyệt đối, tránh sai lệch do hàm bất định (ví dụ: `UUID()`, `NOW()`). |
| `binlog_expire_logs_seconds` | `604800` (7 ngày) | `604800` (7 ngày) | Tự động dọn dẹp các binary log file cũ hơn 7 ngày trên cả 2 node, triệt tiêu nguy cơ cạn kiệt dung lượng đĩa khi `log_replica_updates = ON`. |
| `max_binlog_size` | `500M` | `500M` | Giới hạn dung lượng tối đa của một file binary log trước khi tự động xoay vòng sang file mới. |
| `read_only` | `0` (Mặc định) | `1` | Ngăn các tài khoản không có quyền SUPER ghi dữ liệu vào Slave. |
| `super_read_only` | `0` (Mặc định) | `1` | Ràng buộc bảo vệ cấp cao nhất: Ngăn chặn cả tài khoản `root` và DBA ghi dữ liệu trực tiếp lên Slave, triệt tiêu nguy cơ lệch GTID (data drift). |
| `relay_log_recovery` | - | `ON` | Đảm bảo tính toàn vẹn relay log khi máy chủ 212 gặp sự cố phần cứng hoặc khởi động lại đột ngột. |
| `replica_preserve_commit_order` | - | `ON` | Bắt buộc thứ tự commit giao dịch trên MTS Worker trùng khớp 100% với thứ tự trên Master, tránh đọc dữ liệu dị thường. |
| `replica_pending_jobs_size_max` | - | `1073741824` | Giới hạn bộ nhớ đệm (1GB) cho coordinator phân bổ event tới workers, ngăn ngừa lỗi tràn bộ đệm khi có transaction lớn. |

---

## 3. Thiết lập Mạng & Tài khoản Replication Bảo mật

### 3.1. Cấu hình Tường lửa (Firewall UFW) trên VPS Master
Cổng MySQL 3306 **tuyệt đối không mở công khai cho toàn bộ Internet** (`0.0.0.0/0`). Chỉ cho phép địa chỉ IP cụ thể của Máy chủ 212 kết nối:

```bash
# Thực hiện trên VPS Master:
# Thay <SLAVE_212_IP> bằng địa chỉ IP tĩnh thực tế của Máy chủ 212
sudo ufw allow from <SLAVE_212_IP> to any port 3306 proto tcp comment "Allow MySQL Replica from 212"
sudo ufw reload
sudo ufw status verbose
```

*Lưu ý khuyến nghị kiến trúc:* Nếu có kết nối VPN nội bộ (như WireGuard/Tailscale) giữa VPS Master và Máy chủ 212, hãy cấu hình `bind-address` theo IP VPN của Master và cho phép kết nối qua interface VPN tương ứng để toàn bộ dữ liệu binary log truyền qua đường hầm mã hóa an toàn.

---

### 3.2. Tạo tài khoản Replication chuyên biệt trên Master
Đăng nhập vào MySQL trên VPS Master bằng quyền `root`:
```bash
sudo mysql -u root -p
```

Thực thi các lệnh SQL sau để tạo tài khoản có đặc quyền tối thiểu (`REPLICATION SLAVE`):

```sql
-- 1. Tạo user replication chuyên biệt với mật khẩu mạnh (16+ ký tự an toàn)
CREATE USER 'repl_user'@'<SLAVE_212_IP>' 
  IDENTIFIED WITH caching_sha2_password BY '<STRONG_REPLICATION_PASSWORD>';

-- 2. Chỉ cấp quyền tối thiểu cần thiết cho replication
GRANT REPLICATION SLAVE ON *.* TO 'repl_user'@'<SLAVE_212_IP>';

-- 3. Cấu hình bảo mật đường truyền:
-- [Trường hợp A: Kết nối qua Internet công cộng] Bắt buộc mã hóa SSL (Khuyến nghị):
ALTER USER 'repl_user'@'<SLAVE_212_IP>' REQUIRE SSL;
-- [Trường hợp B: Kết nối qua VPN nội bộ WireGuard/Tailscale] Nếu chọn không dùng SSL (SOURCE_SSL=0),
-- KHÔNG chạy lệnh REQUIRE SSL ở trên, để tránh lỗi Access Denied khi kết nối.

-- 4. Nạp lại bảng phân quyền
FLUSH PRIVILEGES;

-- 5. Kiểm tra quyền của tài khoản vừa tạo
SHOW GRANTS FOR 'repl_user'@'<SLAVE_212_IP>';
```

---

### 3.3. Kiểm tra kết nối mạng từ Máy Chủ 212 sang Master
Trên Máy chủ 212, thực hiện kiểm tra kết nối tầng mạng và xác thực tài khoản:

```bash
# Kiểm tra mở cổng TCP 3306 từ Máy chủ 212 tới Master
nc -zv <MASTER_VPS_IP> 3306
# Hoặc: telnet <MASTER_VPS_IP> 3306

# Kiểm tra độ trễ mạng (RTT) và tương thích MTU qua đường hầm VPN (WireGuard/Tailscale)
# WireGuard thường có MTU 1420 bytes (so với 1500 chuẩn). Cần kiểm tra cờ Do Not Fragment (DF)
# để đảm bảo các event binlog lớn không bị âm thầm rớt gói:
ping -c 4 <MASTER_VPS_IP>
ping -c 4 -M do -s 1392 <MASTER_VPS_IP>  # Kiểm tra MTU 1420 (1392 payload + 28 bytes ICMP/IP header)

# Thử đăng nhập MySQL từ Máy chủ 212 vào Master bằng repl_user
mysql -u repl_user -h <MASTER_VPS_IP> -p -e "SELECT 1;"
```
*Kết quả mong đợi:* Kết nối thành công và trả về giá trị `1`.

---

## 4. Quy trình Đồng bộ Dữ liệu Ban đầu (Initial Data Sync)

Quy trình này tạo một snapshot dữ liệu toàn vẹn từ Master và khôi phục sang Máy chủ 212 mà **không làm gián đoạn hay khóa bảng ghi** của ứng dụng Flama đang hoạt động (Online Non-blocking Snapshot).

### 4.1. Tạo bản Snapshot nhất quán trên Master bằng `mysqldump`
Trên VPS Master, chạy lệnh `mysqldump` với cơ chế transaction của InnoDB:

```bash
# Thực hiện trên VPS Master:
mysqldump -u root -p \
  --single-transaction \
  --quick \
  --triggers \
  --routines \
  --events \
  --set-gtid-purged=ON \
  --max-allowed-packet=512M \
  --databases flama \
  | gzip -c > /tmp/flama_initial_dump.sql.gz
```

#### Giải thích các cờ quan trọng bắt buộc:
1. `--single-transaction`: Thiết lập mức cô lập giao dịch `REPEATABLE READ` và phát lệnh `START TRANSACTION WITH CONSISTENT SNAPSHOT`. Cho phép đọc dữ liệu nhất quán của tất cả các bảng InnoDB mà **không khóa bảng**, ứng dụng web vẫn ghi (INSERT, UPDATE) bình thường trong suốt quá trình backup.
   - **Phòng ngừa xung đột Metadata Lock (MDL) và DDL**: Cờ `--single-transaction` không khóa bảng đọc/ghi (SELECT/INSERT/UPDATE), nhưng nó giữ MDL trên từng bảng khi truy cập. Nếu trong lúc dump có lệnh DDL (`ALTER TABLE`, Alembic migration `deploy/migrate_database.py` hoặc `flask db upgrade`) được thực thi trên Master, dump sẽ bị gãy với `ERROR 1412 (HY000): Table definition has changed, please retry transaction` hoặc làm nghẽn toàn bộ hàng đợi ghi. BẮT BUỘC đảm bảo không có migration nào chạy trong lúc dump.
2. `--quick`: Đọc từng dòng từ bảng thay vì nạp toàn bộ vào bộ nhớ, tránh cạn kiệt RAM trên VPS.
3. `--set-gtid-purged=ON`: **Yếu tố cốt lõi của GTID replication**. Cờ này sẽ ghi câu lệnh `SET @@GLOBAL.gtid_purged='<GTID_SET>'` vào đầu tệp dump. Khi restore sang Máy chủ 212, Slave sẽ biết chính xác các transaction nào đã tồn tại trong snapshot, từ đó khi bắt đầu replicate, nó sẽ chỉ yêu cầu Master truyền tiếp các transaction phát sinh sau thời điểm snapshot.
4. `--max-allowed-packet=512M`: Đảm bảo không bị ngắt kết nối do các trường dữ liệu lớn (JSON rich-text, array token âm thanh trong `notes.field_values`).
5. `--databases flama`: Chỉ định rõ schema Flama cần nhân bản. Bản dump sẽ tự sinh câu lệnh tạo schema và `USE flama;`.

Kiểm tra dung lượng tệp dump:
```bash
ls -lh /tmp/flama_initial_dump.sql.gz
```

---

### 4.2. Truyền tệp Snapshot sang Máy Chủ 212
Sử dụng `scp` hoặc `rsync` an toàn qua SSH:

```bash
# Thực hiện từ VPS Master (hoặc kéo từ Máy chủ 212):
scp /tmp/flama_initial_dump.sql.gz <USER>@<SLAVE_212_IP>:/tmp/
```

Sau khi truyền xong, xóa tệp tạm trên Master để giải phóng dung lượng đĩa:
```bash
rm /tmp/flama_initial_dump.sql.gz
```

---

### 4.3. Khôi phục dữ liệu lên Máy Chủ 212
Đăng nhập vào Máy chủ 212 để thực hiện khôi phục:

```bash
# 1. Tạm thời tắt super_read_only trên Máy chủ 212 để cho phép root import dữ liệu snapshot
# (Vì super_read_only = 1 sẽ chặn cả user root/SUPER thực hiện bất kỳ lệnh DDL/DML nào)
mysql -u root -p -e "SET GLOBAL super_read_only = 0; SET GLOBAL read_only = 0;"

# 2. Đảm bảo dừng replica, làm sạch schema cũ và đặt lại GTID (nếu Máy chủ 212 đã từng vận hành trước đây)
# Phải dừng replica trước khi RESET REPLICA ALL để tránh lỗi ERROR 1198.
# Tắt sql_log_bin để lệnh DROP DATABASE (nếu có schema cũ) không sinh ra binlog hay GTID rác.
# (MySQL 8.0.23+ khuyến nghị dùng RESET BINARY LOGS AND GTIDS thay thế cú pháp cũ RESET MASTER)
mysql -u root -p -e "STOP REPLICA; RESET REPLICA ALL; SET SESSION sql_log_bin = 0; DROP DATABASE IF EXISTS flama; RESET BINARY LOGS AND GTIDS;"

# 3. Nạp dữ liệu snapshot từ tệp gzip (Bản dump đã chứa 'CREATE DATABASE IF NOT EXISTS flama' và 'SET @@GLOBAL.GTID_PURGED')
zcat /tmp/flama_initial_dump.sql.gz | mysql -u root -p --max-allowed-packet=512M

# 4. KHỞI TẠO TÀI KHOẢN ỨNG DỤNG FLAMA TRÊN MÁY CHỦ 212 (BẮT BUỘC)
# Lưu ý quan trọng: Tệp dump chỉ chứa schema flama, KHÔNG chứa bảng mysql.user từ Master.
# Để các worker nền, ProxySQL hoặc ứng dụng Flama (DB_USER) có thể kết nối tra cứu từ vựng/marketplace
# và sẵn sàng cho kịch bản Failover mà không bị lỗi "Access Denied", ta BẮT BUỘC tạo user ngay lúc này
# (khi super_read_only đang tạm tắt, vì super_read_only = 1 sẽ chặn lệnh CREATE USER).
#
# CẢNH BÁO BẢO VỆ GTID (BẮT BUỘC SET SESSION sql_log_bin = 0):
# Do Máy chủ 212 đã bật log_bin, nếu không tắt ghi binlog ở cấp session, lệnh CREATE USER/GRANT
# sẽ được ghi vào binlog của Slave 212 và sinh ra Errant GTID mang UUID của 212 (<SLAVE_212_UUID>:1-N).
# Điều này sẽ làm sai lệch gtid_executed ở Mục 4.4 và gây rủi ro split-brain khi failback.
mysql -u root -p <<SQL
-- Tắt ghi binary log trong phiên này để KHÔNG sinh ra Errant GTID trên Slave 212:
SET SESSION sql_log_bin = 0;

-- Khởi tạo tài khoản flama_user cho cả kết nối từ xa (%) và kết nối cục bộ (localhost, 127.0.0.1):
CREATE USER IF NOT EXISTS 'flama_user'@'%' IDENTIFIED WITH caching_sha2_password BY '<DB_PASSWORD>';
CREATE USER IF NOT EXISTS 'flama_user'@'localhost' IDENTIFIED WITH caching_sha2_password BY '<DB_PASSWORD>';
CREATE USER IF NOT EXISTS 'flama_user'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY '<DB_PASSWORD>';

-- Cấp quyền đọc toàn bộ dữ liệu schema flama (và cấp quyền ghi dự phòng khi thăng cấp primary):
GRANT SELECT, SHOW VIEW ON flama.* TO 'flama_user'@'%';
GRANT ALL PRIVILEGES ON flama.* TO 'flama_user'@'%';

GRANT SELECT, SHOW VIEW ON flama.* TO 'flama_user'@'localhost';
GRANT ALL PRIVILEGES ON flama.* TO 'flama_user'@'localhost';

GRANT SELECT, SHOW VIEW ON flama.* TO 'flama_user'@'127.0.0.1';
GRANT ALL PRIVILEGES ON flama.* TO 'flama_user'@'127.0.0.1';

FLUSH PRIVILEGES;
SQL

# 5. Kích hoạt lại ngay lập tức chế độ bảo vệ chống ghi nghiêm ngặt
mysql -u root -p -e "SET GLOBAL read_only = 1; SET GLOBAL super_read_only = 1;"

# 6. Dọn dẹp tệp dump sau khi import thành công
rm /tmp/flama_initial_dump.sql.gz
```

---

### 4.4. Xác minh trạng thái GTID sau khi nạp Snapshot
Kiểm tra xem GTID từ Master đã được thiết lập đúng vào `gtid_purged` và `gtid_executed` trên Máy chủ 212 chưa:

```bash
mysql -u root -p -e "SELECT @@GLOBAL.gtid_executed\G"
```
*Kết quả mong đợi:* Giá trị `gtid_executed` chứa tập hợp UUID của Master cùng dải transaction (ví dụ: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:1-15024`).

---

## 5. Khởi tạo và Kích hoạt Replication trên Máy Chủ 212

Đăng nhập vào MySQL trên Máy chủ 212:
```bash
sudo mysql -u root -p
```

### 5.1. Thiết lập Nguồn Replication (Replication Source)
MySQL 8.0 giới thiệu cú pháp chuẩn mới `CHANGE REPLICATION SOURCE TO` (thay thế cho cú pháp cũ `CHANGE MASTER TO`). Sử dụng `SOURCE_AUTO_POSITION = 1` để Slave tự động định vị vị trí transaction tiếp theo dựa trên GTID:

```sql
-- Dừng tiến trình replica nếu đang chạy
STOP REPLICA;

-- Cấu hình trỏ tới VPS Master sử dụng GTID Auto-Positioning
CHANGE REPLICATION SOURCE TO
  SOURCE_HOST = '<MASTER_VPS_IP>',
  SOURCE_PORT = 3306,
  SOURCE_USER = 'repl_user',
  SOURCE_PASSWORD = '<STRONG_REPLICATION_PASSWORD>',
  SOURCE_AUTO_POSITION = 1,
  SOURCE_SSL = 1,                     -- [Khuyến nghị] Bắt buộc 1 nếu repl_user có REQUIRE SSL (Internet công cộng)
  -- SOURCE_SSL = 0, SOURCE_GET_PUBLIC_KEY = 1, -- Dành cho VPN nội bộ không dùng SSL (Yêu cầu repl_user không có REQUIRE SSL)
  SOURCE_CONNECT_RETRY = 10,           -- Thử kết nối lại sau 10 giây nếu mất mạng
  SOURCE_RETRY_COUNT = 86400;          -- Số lần thử lại tối đa

-- Khởi động các tiến trình replication (I/O thread & SQL thread)
START REPLICA;
```

*(Ghi chú tương thích: Trên các bản MySQL 8.0.x trước 8.0.23, có thể dùng cú pháp `CHANGE MASTER TO MASTER_HOST='...', MASTER_AUTO_POSITION=1; START SLAVE;` tương đương).*

---

## 6. Hướng dẫn Kiểm tra và Vận hành (Verification & Health Check)

### 6.1. Kiểm tra Trạng thái Replication
Thực hiện lệnh sau trên Máy chủ 212:
```sql
SHOW REPLICA STATUS\G
```
*(Hoặc `SHOW SLAVE STATUS\G`)*

### 6.2. Bộ chỉ số Tiêu chuẩn Hoạt động Bình thường (Healthy Checklist)

Kiểm tra kỹ các dòng sau trong output của `SHOW REPLICA STATUS\G`:

```text
*************************** 1. row ***************************
             Replica_IO_State: Waiting for source to send event
                  Source_Host: <MASTER_VPS_IP>
                  Source_User: repl_user
                  Source_Port: 3306
                Connect_Retry: 10
             Source_Log_File: mysql-bin.000004
         Read_Source_Log_Pos: 125432
              Relay_Log_File: mysql-relay-bin.000002
               Relay_Log_Pos: 5421
        Relay_Source_Log_File: mysql-bin.000004
           Replica_IO_Running: Yes           <--- [BẮT BUỘC: Yes] Kết nối & nhận binlog tốt
          Replica_SQL_Running: Yes           <--- [BẮT BUỘC: Yes] Áp dụng transaction vào DB tốt
                Last_IO_Errno: 0             <--- [BẮT BUỘC: 0] Không có lỗi I/O thread
                Last_IO_Error:               <--- [BẮT BUỘC: Trống] Không có thông báo lỗi I/O
               Last_SQL_Errno: 0             <--- [BẮT BUỘC: 0] Không có lỗi SQL applier thread
               Last_SQL_Error:               <--- [BẮT BUỘC: Trống] Không có thông báo lỗi SQL
        Seconds_Behind_Source: 0             <--- [BẮT BUỘC: <= 5] Thời gian trễ replication (0 = đồng bộ tức thì)
                Auto_Position: 1             <--- [BẮT BUỘC: 1] Đang dùng GTID auto positioning
           Retrieved_Gtid_Set: <UUID>:1-15050
            Executed_Gtid_Set: <UUID>:1-15050
```

| Chỉ số quan trọng | Giá trị tiêu chuẩn | Ý nghĩa vận hành |
|---|---|---|
| `Replica_IO_Running` | **`Yes`** | I/O Thread đã kết nối thành công tới Master và đang lắng nghe luồng binary log. Nếu là `No` hoặc `Connecting`, xem mục 7.1. |
| `Replica_SQL_Running` | **`Yes`** | SQL Applier Thread đang đọc relay log và thực thi các câu lệnh vào database của Slave. Nếu là `No`, xem mục 7.2. |
| `Seconds_Behind_Source` | **`0`** (hoặc `< 5s`) | Độ trễ giữa thời gian commit trên Master và thời điểm thực thi xong trên Slave. Nếu tăng liên tục, xem mục 7.3. |
| `Auto_Position` | **`1`** | Xác nhận đang vận hành theo cơ chế GTID Auto-Positioning. |
| `Last_IO_Errno` & `Last_SQL_Errno` | **`0`** | Không có bất kỳ lỗi cú pháp, kết nối hay dữ liệu nào. |

---

### 6.3. Kiểm tra Tính Bất biến Ghi trên Máy Chủ 212 (Read-Only Verification)
Thử thực hiện thao tác tạo bảng hoặc ghi dữ liệu trên Máy chủ 212 để đảm bảo quy tắc an toàn:

```sql
-- Kiểm tra biến hệ thống
SELECT @@global.read_only, @@global.super_read_only;
-- Cả hai giá trị phải trả về 1

-- Thử ghi dữ liệu bằng tài khoản thông thường hoặc root
USE flama;
CREATE TABLE test_read_only (id INT);
```
*Kết quả mong đợi:* MySQL phải từ chối câu lệnh với thông báo lỗi:
```text
ERROR 1290 (HY000): The MySQL server is running with the --super-read-only option so it cannot execute this statement
```

---

### 6.4. Truy vấn Giám sát Nâng cao qua Performance Schema
Để theo dõi chi tiết độ trễ từng luồng worker và độ trễ mạng:

```sql
-- 1. Kiểm tra trạng thái của các luồng Multi-Threaded Applier
SELECT 
    THREAD_ID, SERVICE_STATE, LAST_ERROR_NUMBER, LAST_ERROR_MESSAGE
FROM performance_schema.replication_applier_status_by_worker;

-- 2. Kiểm tra độ trễ mạng của luồng I/O
SELECT 
    CHANNEL_NAME, SERVICE_STATE, LAST_HEARTBEAT_TIMESTAMP, RECEIVED_TRANSACTION_SET
FROM performance_schema.replication_connection_status;
```

---

## 7. Sổ tay Xử lý Sự cố (Troubleshooting Runbook)

### 7.1. Sự cố 1: Lỗi kết nối mạng & Firewall Port 3306
#### Triệu chứng:
`SHOW REPLICA STATUS\G` hiển thị:
- `Replica_IO_Running: Connecting` hoặc `Replica_IO_Running: No`
- `Last_IO_Error: error connecting to master 'repl_user@<MASTER_VPS_IP>:3306' - retry-time: 10 retries: 86400 message: Can't connect to MySQL server on '<MASTER_VPS_IP>' (110 "Connection timed out" hoặc 111 "Connection refused")`

#### Nguyên nhân & Các bước khắc phục:
1. **Kiểm tra UFW trên Master**:
   Cổng 3306 chưa mở cho IP của Máy chủ 212.
   ```bash
   # Trên VPS Master:
   sudo ufw status | grep 3306
   # Nếu thiếu, thêm lại:
   sudo ufw allow from <SLAVE_212_IP> to any port 3306 proto tcp
   sudo ufw reload
   ```
2. **Kiểm tra `bind-address` trên Master**:
   Nếu trong `/etc/mysql/mysql.conf.d/mysqld.cnf` trên Master vẫn để `bind-address = 127.0.0.1`, MySQL sẽ từ chối mọi kết nối từ bên ngoài.
   - Sửa thành `bind-address = 0.0.0.0` (hoặc IP VPN nội bộ).
   - Khởi động lại MySQL: `sudo systemctl restart mysql`.
3. **Kiểm tra thông tin tài khoản replication**:
   Có thể sai mật khẩu hoặc IP trong mệnh đề `CREATE USER 'repl_user'@'...'`.
   ```sql
   -- Trên VPS Master:
   SELECT user, host, plugin FROM mysql.user WHERE user = 'repl_user';
   -- Nếu IP bị sai, cập nhật lại:
   RENAME USER 'repl_user'@'old_ip' TO 'repl_user'@'<SLAVE_212_IP>';
   ```
4. **Kiểm tra lại từ Máy chủ 212**:
   ```sql
   -- Trên Máy chủ 212, sau khi khắc phục mạng:
   STOP REPLICA;
   START REPLICA;
   ```

---

### 7.2. Sự cố 2: Bất đồng bộ GTID / Xung đột Giao dịch (Data Drift / Transaction Conflict)
#### Triệu chứng:
- `Replica_IO_Running: Yes` nhưng `Replica_SQL_Running: No`
- `Last_SQL_Error: Coordinator stopped because there were error(s) in the worker(s)... Error 'Duplicate entry ... for key ...' (Error code 1062)` hoặc `Error 'Key not found' (Error code 1032)`.

#### Nguyên nhân:
Dữ liệu trên Máy chủ 212 từng bị chỉnh sửa thủ công trước khi bật `super_read_only`, hoặc snapshot ban đầu không hoàn toàn đồng bộ, dẫn đến xung đột khi SQL Applier cố gắng thực thi câu lệnh INSERT/UPDATE từ binary log của Master.

#### Khắc phục Chuẩn cho GTID (Inject Empty Transaction):
*Cảnh báo:* Với GTID, **tuyệt đối không dùng** `SET GLOBAL sql_slave_skip_counter = 1` (MySQL sẽ báo lỗi `ERROR 1858: sql_slave_skip_counter cannot be used with GTID`). Ta bắt buộc dùng kỹ thuật bơm giao dịch rỗng (**Empty Transaction Injection**) để bỏ qua transaction lỗi:

1. **Xác định chính xác mã GTID gây lỗi**:
   Tra cứu trong trường `Last_SQL_Error` của `SHOW REPLICA STATUS\G`:
   Ví dụ thông báo lỗi ghi:
   ```text
   ... The slave coordinator and worker threads are stopped, possibly leaving data in inconsistent state. A failure occurred during host ... GTID '5b6b1588-b45a-11ee-8e86-0242ac120002:15432'
   ```
   GTID gây lỗi ở đây là `5b6b1588-b45a-11ee-8e86-0242ac120002:15432`.

2. **Bơm transaction rỗng vào Slave để đánh dấu giao dịch này đã được thực thi**:
   *Cảnh báo đặc biệt về `super_read_only`:* Lệnh `COMMIT` ghi nhận GTID rỗng vào binary log và bảng `mysql.gtid_executed`. Do đó, nếu `super_read_only = 1` đang bật, lệnh `COMMIT` của user root sẽ bị chặn ngay lập tức với lỗi `ERROR 1290 (HY000)`. BẮT BUỘC phải tạm thời tắt `super_read_only = 0`, thực hiện commit rỗng, rồi bật lại `super_read_only = 1` trước khi khởi động lại replica:

   ```sql
   -- Trên Máy chủ 212:
   STOP REPLICA;
   
   -- 1. Tạm thời tắt super_read_only để session root được phép commit GTID rỗng
   SET GLOBAL super_read_only = 0;
   
   -- 2. Đặt transaction tiếp theo thành chính GTID bị lỗi
   SET GTID_NEXT = '5b6b1588-b45a-11ee-8e86-0242ac120002:15432';
   
   -- 3. Tạo một transaction rỗng và commit
   BEGIN;
   COMMIT;
   
   -- 4. Trả lại chế độ tự động cho GTID
   SET GTID_NEXT = 'AUTOMATIC';
   
   -- 5. Kích hoạt lại ngay lập tức chế độ bảo vệ chống ghi nghiêm ngặt
   SET GLOBAL super_read_only = 1;
   
   -- 6. Khởi động lại replication
   START REPLICA;
   ```

3. **Kiểm tra lại trạng thái**:
   ```sql
   SHOW REPLICA STATUS\G
   ```
   Kiểm tra `Replica_SQL_Running` đã trở lại `Yes` và `Last_SQL_Errno` là `0`.

*Ghi chú:* Nếu xảy ra xung đột trên hàng loạt transaction (data drift diện rộng), giải pháp an toàn và nhanh nhất là thực hiện lại quy trình đồng bộ ban đầu (Mục 4) bằng bản dump mới nhất.

---

### 7.3. Sự cố 3: Hiện tượng Replication Lag kéo dài (`Seconds_Behind_Source` tăng cao)
#### Triệu chứng:
- Cả `Replica_IO_Running` và `Replica_SQL_Running` đều là `Yes`.
- `Seconds_Behind_Source` liên tục tăng (vượt quá 30 giây, thậm chí hàng giờ).
- Người dùng đọc từ Máy chủ 212 phản ánh dữ liệu bị trễ so với Master.

#### Nguyên nhân:
1. Master thực thi một transaction quá lớn (ví dụ: batch update/insert hàng chục nghìn dòng dữ liệu, import dữ liệu từ vựng lớn).
2. SQL thread trên Slave bị quá tải do chạy đơn luồng (single-threaded).
3. Đĩa cứng (Disk I/O) trên Máy chủ 212 chậm hơn Master.
4. **Tắc nghẽn Metadata Lock (MDL) khi Master chạy Migration DDL**: Khi Alembic migration (`deploy/migrate_database.py` hoặc `flask db upgrade`) chạy lệnh `ALTER TABLE` trên Master, sự kiện DDL này được truyền sang Máy chủ 212. Nếu trên Máy chủ 212 đang có một truy vấn `SELECT` dài (tra cứu browse, báo cáo) đang đọc bảng đó, lệnh DDL trên Slave sẽ rơi vào trạng thái `Waiting for table metadata lock`. Trạng thái này sẽ **chặn toàn bộ** các transaction cập nhật dữ liệu tiếp theo của SQL thread, khiến `Seconds_Behind_Source` tăng vọt.
5. Tràn bộ đệm hàng đợi coordinator (`replica_pending_jobs_size_max`) khi nhận transaction có kích thước lớn.

#### Các bước khắc phục:
1. **Kiểm tra và ngắt tắc nghẽn Metadata Lock (MDL) trên Máy chủ 212**:
   ```sql
   SHOW FULL PROCESSLIST;
   -- Tìm thread có trạng thái 'Waiting for table metadata lock'.
   -- Sau đó tìm các query SELECT đang chạy kéo dài trên cùng bảng (State: Sending data / Executing) và kill:
   KILL <QUERY_PROCESS_ID>;
   ```

2. **Kích hoạt và tối ưu hóa Multi-Threaded Applier (MTS)**:
   Nếu cấu hình chưa bật MTS hoặc worker quá ít:
   ```sql
   STOP REPLICA;
   SET GLOBAL replica_parallel_type = 'LOGICAL_CLOCK';
   SET GLOBAL replica_parallel_workers = 4; -- hoặc 8 tùy theo số core CPU của Máy 212
   SET GLOBAL replica_preserve_commit_order = ON;
   SET GLOBAL replica_pending_jobs_size_max = 1073741824; -- Tăng lên 1GB tránh nghẽn coordinator
   START REPLICA;
   ```

3. **Tối ưu hóa ghi tạm thời cho Slave trong đợt lag cao**:
   ```sql
   SET GLOBAL sync_binlog = 0;
   SET GLOBAL innodb_flush_log_at_trx_commit = 2;
   ```

---

### 7.4. Sự cố 4: VPS Master bị cạn kiệt dung lượng đĩa do Binary Log
#### Triệu chứng:
Ổ cứng của VPS Master đạt ngưỡng 95% - 100% dung lượng, dịch vụ MySQL có nguy cơ bị dừng đột ngột.

#### Nguyên nhân:
Binary log được sinh ra với tốc độ cao nhưng chưa đến thời hạn tự động dọn dẹp (`binlog_expire_logs_seconds`).

#### Khắc phục an toàn:
1. **Kiểm tra GTID và file binlog mà Slave 212 đang đọc**:
   ```sql
   -- Trên Máy chủ 212:
   SHOW REPLICA STATUS\G
   -- Xem trường: Relay_Source_Log_File (Ví dụ: mysql-bin.000015)
   ```
2. **Dọn dẹp an toàn trên Master**:
   *Tuyệt đối không xóa binary log đang được Slave đọc.* Chỉ xóa các log file cũ hơn file Slave đang cần:
   ```sql
   -- Trên VPS Master:
   PURGE BINARY LOGS TO 'mysql-bin.000015';
   -- Hoặc xóa các log cũ hơn 3 ngày trước:
   PURGE BINARY LOGS BEFORE NOW() - INTERVAL 3 DAY;
   ```

---

## 8. Kế hoạch Dự phòng Chuyển đổi Sự cố (Disaster Recovery & Failover)

Trong trường hợp VPS Master bị thảm họa phần cứng hoặc mất mạng kéo dài và cần thăng cấp Máy chủ 212 thành Primary Database để duy trì hoạt động:

### 8.1. Các bước thăng cấp Máy chủ 212 thành Master tạm thời
1. Đảm bảo Máy chủ 212 đã áp dụng hết toàn bộ relay log nhận được:
   ```sql
   -- Dừng luồng nhận dữ liệu
   STOP REPLICA IO_THREAD;
   
   -- CẢNH BÁO VẬN HÀNH QUAN TRỌNG:
   -- Khi IO_THREAD dừng, MySQL sẽ hiển thị 'Seconds_Behind_Source: NULL'. Đây là hành vi bình thường.
   -- Để xác nhận SQL thread đã thực thi cạn kiệt toàn bộ relay log, hãy chạy 'SHOW REPLICA STATUS\G'
   -- và kiểm tra trường:
   -- Replica_SQL_Running_State: Replica has read all relay log; waiting for more updates
   -- (Hoặc 'Slave has read all relay log; waiting for more updates' trên các bản cũ).
   
   -- Khi trạng thái trên xuất hiện, dừng hoàn toàn tiến trình replica:
   STOP REPLICA;
   ```
2. Gỡ bỏ hoàn toàn trạng thái replication:
   ```sql
   RESET REPLICA ALL;
   ```
3. Mở khóa ghi bằng cách tắt chế độ read-only:
   ```sql
   SET GLOBAL super_read_only = 0;
   SET GLOBAL read_only = 0;
   ```
4. Cập nhật file cấu hình `/etc/mysql/mysql.conf.d/mysqld.cnf` trên Máy chủ 212 để duy trì khi reboot:
   ```ini
   read_only = 0
   super_read_only = 0
   ```
5. Chuyển cấu hình `DB_HOST` trong `/etc/flama/flama.env` của backend Flama trỏ sang IP của Máy chủ 212, đồng thời kích hoạt 4 systemd timers ghi nhận dữ liệu định kỳ trên Máy chủ 212:
   ```bash
   # Cập nhật DB_HOST trỏ sang IP Máy chủ 212 trên các worker nếu cần, sau đó khởi động lại service:
   sudo systemctl restart flama.service flama-connect.service flama-study-worker.service

   # Kích hoạt 4 systemd timers định kỳ (trước đó bị tắt trên Slave read-only để tránh lỗi 1290):
   sudo systemctl start flama-analytics-counts.timer flama-review-analytics-worker.timer flama-note-base-retention.timer flama-study-retention.timer
   ```

### 8.2. Quy trình Hoàn trả và Tái lập VPS Master (Failback to Primary VPS)
Sau khi phần cứng hoặc sự cố trên VPS Master đã được khắc phục hoàn toàn, để đưa VPS Master trở lại làm Primary mà không làm mất mát bất kỳ dữ liệu nào đã phát sinh trên Máy chủ 212 trong thời gian hoạt động độc lập:

1. **Kiểm tra và Xử lý Giao dịch Lạc lối (Errant Transactions Check - BẮT BUỘC)**:
   - Trong mô hình nhân bản bất đồng bộ (Asynchronous Replication), nếu VPS Master bị sập nguồn đột ngột, có thể tồn tại transaction đã commit cục bộ trên Master nhưng chưa kịp stream sang Slave 212.
   - Lấy tập `gtid_executed` từ Máy chủ 212:
     ```sql
     -- Trên Máy chủ 212:
     SELECT @@GLOBAL.gtid_executed;
     ```
   - Đối chiếu trên VPS Master để tìm transaction chỉ có trên Master:
     ```sql
     -- Trên VPS Master (thay chuỗi GTID lấy từ 212 vào):
     SELECT GTID_SUBTRACT(@@GLOBAL.gtid_executed, '<SLAVE_212_GTID_EXECUTED>');
     ```
   - **Đánh giá kết quả**:
     - *Nếu kết quả rỗng (`""`)*: Tuyệt vời! VPS Master không có giao dịch lạc lối. Tiến hành bước 2 ngay.
     - *Nếu kết quả chứa GTID (ví dụ `<MASTER_UUID>:15025`)*: VPS Master có giao dịch chưa kịp đồng bộ sang 212 trước khi sập. Kỹ sư cần kiểm tra transaction đó bằng `mysqlbinlog`. Nếu là dữ liệu không quan trọng hoặc có thể bỏ qua, hãy thực hiện kỹ thuật Empty Transaction Injection (Mục 7.2) trên Máy chủ 212 cho chính GTID đó trước khi kết nối; nếu dữ liệu đã phân kỳ lớn, hãy coi Máy chủ 212 là Single Source of Truth và tạo bản snapshot mới từ Máy chủ 212 để khôi phục lại VPS Master theo Mục 4.

2. **Thiết lập VPS Master làm Replica tạm thời trỏ tới Máy chủ 212**:
   - Nhờ cơ chế GTID, VPS Master biết chính xác giao dịch cuối cùng mà nó đã commit trước khi gặp sự cố và chỉ cần kéo tiếp các transaction mới được ghi trên Máy chủ 212.
   - Tạo user replication trên Máy chủ 212 cấp cho IP của VPS Master:
     ```sql
     CREATE USER 'repl_user'@'<MASTER_VPS_IP>' IDENTIFIED WITH caching_sha2_password BY '<STRONG_REPLICATION_PASSWORD>';
     GRANT REPLICATION SLAVE ON *.* TO 'repl_user'@'<MASTER_VPS_IP>';
     FLUSH PRIVILEGES;
     ```
   - Mở UFW port 3306 trên Máy chủ 212 cho IP VPS Master:
     ```bash
     sudo ufw allow from <MASTER_VPS_IP> to any port 3306 proto tcp
     ```
   - Trên VPS Master, BẢO VỆ CHỐNG GHI NGHIÊM NGẶT và trỏ nguồn nhân bản sang Máy chủ 212:
     ```sql
     -- BẮT BUỘC: Khóa ghi trên Master trong lúc đóng vai trò Replica tạm thời để bắt kịp dữ liệu,
     -- ngăn ngừa tuyệt đối các tiến trình nền commit làm lệch chuỗi GTID:
     SET GLOBAL super_read_only = 1;
     SET GLOBAL read_only = 1;

     CHANGE REPLICATION SOURCE TO
       SOURCE_HOST = '<SLAVE_212_IP>',
       SOURCE_PORT = 3306,
       SOURCE_USER = 'repl_user',
       SOURCE_PASSWORD = '<STRONG_REPLICATION_PASSWORD>',
       SOURCE_AUTO_POSITION = 1,
       SOURCE_SSL = 1;
     START REPLICA;
     ```

3. **Chờ đồng bộ bắt kịp hoàn toàn**:
   - Chạy `SHOW REPLICA STATUS\G` trên VPS Master cho tới khi `Seconds_Behind_Source = 0` và `Replica_IO_Running: Yes`, `Replica_SQL_Running: Yes`.

4. **Thực hiện chuyển đổi luồng ghi trong cửa sổ bảo trì ngắn (Quiesced Cutover - 1 đến 2 phút)**:
   - Tạm dừng các tiến trình backend và 4 systemd timers trên Máy chủ 212:
     ```bash
     # Dừng timers ghi dữ liệu định kỳ trên Máy chủ 212:
     sudo systemctl stop flama-analytics-counts.timer flama-review-analytics-worker.timer flama-note-base-retention.timer flama-study-retention.timer

     # Dừng dịch vụ ứng dụng:
     sudo systemctl stop flama.service flama-connect.service flama-study-worker.service
     ```
   - Khóa ghi hoàn toàn trên Máy chủ 212 để không phát sinh thêm transaction:
     ```sql
     SET GLOBAL super_read_only = 1;
     SET GLOBAL read_only = 1;
     ```
   - Trên VPS Master, XẢ CẠN RELAY LOG AN TOÀN trước khi gỡ bỏ replication (Phòng ngừa mất dữ liệu ngầm):
     ```sql
     -- 1. Dừng luồng nhận I/O để ngắt nhận thêm binary log event
     STOP REPLICA IO_THREAD;

     -- 2. Kiểm tra xác nhận SQL applier thread đã thực thi cạn kiệt toàn bộ relay log:
     SHOW REPLICA STATUS\G
     -- BẮT BUỘC kiểm tra trường:
     -- Replica_SQL_Running_State: Replica has read all relay log; waiting for more updates
     -- (Và Seconds_Behind_Source: NULL)

     -- 3. Khi SQL thread đã cạn relay log, dừng hoàn toàn và gỡ bỏ replication:
     STOP REPLICA;
     RESET REPLICA ALL;

     -- 4. Mở khóa ghi bình thường cho VPS Master:
     SET GLOBAL super_read_only = 0;
     SET GLOBAL read_only = 0;
     ```
   - Đặt lại cấu hình `DB_HOST=127.0.0.1` trong `/etc/flama/flama.env` trên VPS Master và khởi động lại dịch vụ cùng 4 timers:
     ```bash
     sudo systemctl restart flama.service flama-connect.service flama-study-worker.service
     sudo systemctl start flama-analytics-counts.timer flama-review-analytics-worker.timer flama-note-base-retention.timer flama-study-retention.timer
     ```

5. **Tái kích hoạt Máy chủ 212 làm Slave trở lại**:
   - Trên Máy chủ 212, cấu hình lại nguồn replication trỏ về VPS Master:
     ```sql
     CHANGE REPLICATION SOURCE TO
       SOURCE_HOST = '<MASTER_VPS_IP>',
       SOURCE_PORT = 3306,
       SOURCE_USER = 'repl_user',
       SOURCE_PASSWORD = '<STRONG_REPLICATION_PASSWORD>',
       SOURCE_AUTO_POSITION = 1,
       SOURCE_SSL = 1;
     START REPLICA;
     ```
   - Cập nhật lại file `/etc/mysql/mysql.conf.d/mysqld.cnf` trên Máy chủ 212 với `read_only = 1` và `super_read_only = 1`.
   - Đảm bảo 4 systemd timers trên Máy chủ 212 ở trạng thái tắt (`stopped` / `disabled`) khi đóng vai trò Read-Only Replica.

---

### 8.3. Tương thích với Scripts Vận hành và Cronjob trong Repository (`scripts/`, `deploy/`)

| Thành phần / Script | Bản chất vận hành | Tương tác & Quy tắc với Replication Master-Slave |
|---|---|---|
| `deploy/migrate_database.py` | Schema migration (Alembic) qua Flask-Migrate khi deploy release mới | Chạy trên Master với cờ `--writers-quiesced`. Toàn bộ DDL (`ALTER TABLE`, `CREATE TABLE`) và cập nhật bảng `alembic_version` được ghi vào binary log và tự động replicate an toàn sang Máy chủ 212 qua GTID. **Lưu ý:** Cần tránh các truy vấn SELECT báo cáo kéo dài trên Slave trong lúc deploy để không gây tắc nghẽn Metadata Lock (MDL). |
| `scripts/run_p5_vps_preflight.py` | Kiểm tra audit bundle sau deploy trên VPS | Tạo user tạm thời `p5audit_*` trên localhost và drop ngay sau khi chạy xong trong `finally`. Khi chạy trên Master, các lệnh DDL user này replicate sang Slave bình thường. |
| `scripts/probe_p9_backup_restore_mysql.py` | Diễn tập phục hồi snapshot trên database tạm | Script tự động tạo cơ sở dữ liệu tạm thời cô lập dạng `flama_p9_restore_<timestamp>_<hex>` và kiểm tra binlog watermark (`-- CHANGE REPLICATION SOURCE TO`), tuyệt đối từ chối chạy trên `DB_NAME`. Hoàn toàn an toàn và không ảnh hưởng tới replication đang chạy. |
| `scripts/reseed_db.*` | Reset và nạp seed dữ liệu mẫu cho dev/staging | Chứa lệnh phá hủy dữ liệu `flask dev-purge-data --yes`. **TUYỆT ĐỐI NGHIÊM CẤM** chạy script này trên môi trường Production (cả Master lẫn Slave). |
| 4 High-Frequency Timers (`deploy/activate_release.sh`) | Systemd timers: `analytics-counts`, `review-analytics-worker`, `note-base-retention`, `study-retention` | Chỉ kích hoạt trên node Primary (VPS Master). Trên Máy chủ 212 (Read Replica), 4 timers này **bắt buộc phải dừng** (`systemctl stop`) để tránh phát sinh lỗi `ERROR 1290 (super-read-only)`. Khi failover sang 212, khởi động lại các timer này; khi failback, dừng trên 212 và bật lại trên Master. |

---

## 9. Checklist Nghiệm thu và Bàn giao (Acceptance Checklist)

Trước khi đưa vào vận hành sản xuất chính thức, kỹ sư vận hành phải tích đủ các mục kiểm tra sau:

- [ ] Cấu hình `server-id = 1` trên Master và `server-id = 212` trên Slave.
- [ ] Cả Master và Slave đã bật `gtid_mode = ON` và `enforce_gtid_consistency = ON`.
- [ ] `binlog_format = ROW` đã được kích hoạt trên cả 2 node.
- [ ] Cả Master và Máy chủ 212 đã cấu hình `binlog_expire_logs_seconds = 604800` và `max_binlog_size = 500M` để bảo vệ dung lượng đĩa khi `log_replica_updates = ON`.
- [ ] Máy chủ 212 đã kích hoạt `read_only = 1` và `super_read_only = 1`.
- [ ] Tài khoản `repl_user` được tạo với quyền tối thiểu `REPLICATION SLAVE` và giới hạn đúng IP của Máy chủ 212.
- [ ] UFW trên Master chỉ mở cổng 3306 cho IP Máy chủ 212; đã kiểm tra MTU và ping gói lớn (1392 bytes) qua đường hầm VPN.
- [ ] Snapshot ban đầu được dump bằng cờ `--single-transaction` và `--set-gtid-purged=ON`.
- [ ] Khi nạp snapshot trên Máy chủ 212, đã chạy `SET SESSION sql_log_bin = 0;` để xóa schema cũ và tạo tài khoản `flama_user`, triệt tiêu hoàn toàn nguy cơ sinh Errant GTID trên Slave.
- [ ] Lệnh `CHANGE REPLICATION SOURCE TO` được cấu hình với `SOURCE_AUTO_POSITION = 1`.
- [ ] Lệnh `SHOW REPLICA STATUS\G` cho kết quả:
  - `Replica_IO_Running: Yes`
  - `Replica_SQL_Running: Yes`
  - `Seconds_Behind_Source: 0`
- [ ] Thử nghiệm ghi dữ liệu trên Slave bằng lệnh INSERT/CREATE TABLE bị chặn chính xác bởi lỗi 1290 (super-read-only).
- [ ] Đã khởi tạo tài khoản ứng dụng Flama (`flama_user` cho `%`, `localhost`, `127.0.0.1`) trên Máy chủ 212.
- [ ] Thử nghiệm tạo 1 bản ghi mới trên Master và kiểm tra dữ liệu xuất hiện ngay lập tức trên Slave (< 1 giây).
- [ ] Nắm rõ quy trình đối chiếu GTID_SUBTRACT để phát hiện và xử lý errant transactions trước khi failback.
- [ ] Nắm rõ quy trình xả cạn relay log (`STOP REPLICA IO_THREAD` và chờ `Replica has read all relay log`) trước khi chạy `RESET REPLICA ALL` trong cutover failback.
- [ ] Đã cấu hình chỉ bật 4 systemd timers ghi nhận dữ liệu định kỳ trên Primary, tắt trên Read Replica.
