# Sự cố deploy Flama ngày 2026-10-19

Ngày điều tra: 2026-10-19. Múi giờ trình bày: JST (UTC+9).
Phạm vi ban đầu: điều tra chỉ đọc trên VPS, GitHub Actions và Cloudflare API. Sau khi người dùng yêu cầu sửa, đã thực hiện phục hồi ở mục cuối; các bằng chứng bên dưới mô tả trạng thái trước phục hồi.

## Kết luận

Hai pipeline độc lập được kích hoạt bởi merge PR #236, commit `4cd403079b7dae06bda526e26807a4b5a682dce9`, đều thất bại ở bước triển khai:

1. **Backend mất kết nối SSH trong lúc migration dài đang chạy.** Migration tiếp tục ở systemd và hoàn tất thay đổi DB, nhưng phần activation qua SSH không hoàn tất. Ba dịch vụ Flama vẫn bị dừng, còn symlink trỏ release cũ. Đây là nguyên nhân trực tiếp API/Connect trả 502.
2. **Cloudflare Workers build frontend thành công, deploy thất bại trong auto-configuration của Wrangler.** npm báo `Cannot read properties of null (reading 'edgesOut')` khi công cụ tự bổ sung dependency/cấu hình Vite. Bản frontend cũ tiếp tục được phục vụ.

Tại thời điểm kiểm tra khoảng **20:07 JST**, VPS vẫn hoạt động, Nginx và MySQL đang chạy, API và Connect vẫn dừng. Thời gian gián đoạn đã vượt 10 giờ. Không thấy OOM hoặc reboot trong cửa sổ sự cố đã kiểm tra.

## Timeline từ bằng chứng

| Thời điểm JST | Sự kiện | Nguồn |
|---|---|---|
| 09:50:49 | Merge PR #236 vào `master`, commit `4cd403079b7dae06bda526e26807a4b5a682dce9` | GitHub PR API |
| 09:50:52 | GitHub CI và Cloudflare Workers build được kích hoạt | GitHub Actions; Cloudflare Builds API |
| 09:52:14 | Cloudflare: `Success: Build command completed` | Build `eb863ce9-6f5f-4e00-aa70-5c8d45f96a85` |
| 09:52:16 | `npx wrangler deploy` tải Wrangler `4.151.1` | Cloudflare build log |
| 09:52:34 | Auto-configuration Vite thất bại: npm `edgesOut`; chưa deploy phiên bản frontend mới | Cloudflare build log |
| 10:05:05–10:05:14 | Workflow dừng lần lượt web, Connect và Study worker | VPS journal |
| 10:05:14 | Systemd khởi chạy `deploy/migrate_database.py --writers-quiesced` | VPS journal |
| 10:05:17 | Migration tới revision 66; bắt đầu chuẩn bị archive/cutover | GitHub deploy log; manifest DB |
| 10:09:33 | SSH báo `client_loop: send disconnect: Broken pipe`; GitHub step thoát `255` | GitHub deploy log |
| 10:10:54 | Manifest Field ID ghi `verified_at` | DB, truy vấn chỉ đọc |
| 10:11:44 | Cutover ghi `completed_at`, DB tới revision 68; transient migration process thoát `120` | DB; VPS journal |
| 20:01–20:07 | API/Connect 502; ba dịch vụ inactive; symlink vẫn release cũ | HTTP probes; systemctl; readlink; Nginx error log |

## Backend: trạng thái và nguyên nhân gián đoạn kéo dài

### Trạng thái đã xác nhận

- `flama.service`: `inactive/dead`, dừng lúc 10:05:08 JST.
- `flama-connect.service`: `inactive/dead`, dừng lúc 10:05:11 JST.
- `flama-study-worker.service`: `inactive/dead`, dừng lúc 10:05:14 JST.
- Cả ba có `Result=success`: chúng được dừng có chủ đích, không phải tự crash ở thời điểm đó.
- Nginx và MySQL vẫn `active/running`; VPS uptime từ 2026-10-17. Snapshot RAM khả dụng khoảng 6.3 GB, ổ đĩa dùng khoảng 25%.
- Kết nối loopback tới `127.0.0.1:4789` và `127.0.0.1:4790` bị từ chối.
- Nginx ghi `connect() failed (111)` tới upstream `127.0.0.1:4789` cho `/api/health`.
- Public probes: `flama.vn/` trả 200; `api.flama.vn/api/health` và `connect.flama.vn/healthz` trả 502.

### DB và code đang lệch phiên bản

- `alembic_version = 20261014_000068`.
- `notes.field_values` đã bị loại bỏ; còn `field_values_by_id`, `field_values_codec`, `field_values_extras`.
- Manifest `field-id.v1` có `state=contracted`, `writers_quiesced=1`, `archive_count=75513`, `note_count=41568`, `media_count=33944`, `override_count=0`.
- `/opt/flama/current` vẫn trỏ `/opt/flama/releases/c1dfa6e88bcac074649fec9579a6314674a9f51b`.
- Release mới đã unpack ở `/opt/flama/releases/4cd403079b7dae06bda526e26807a4b5a682dce9`.
- Release mới khai báo `LIVE_FIELD_VALUE_CODEC = "field-id.v1"`; release đang được symlink chọn không có capability này.
- File managed environment đã staging giống hệt `/etc/flama/flama.env`; cả staged file lẫn rollback backup vẫn còn.

**Khôi phục phải dùng code tương thích Field ID.** Chỉ bật lại các service với symlink hiện tại sẽ đưa binary cũ lên DB đã contract. Phương án hiện có là tiếp tục activation của release mới sau migration; quay về schema cũ cần một quy trình restore đã kiểm chứng riêng.

Manifest cho thấy bước archive/verify đã hoàn tất. Lượt điều tra này chưa thực hiện đối soát toàn bộ dữ liệu hay diễn tập restore, nên không kết luận toàn bộ dữ liệu đã được kiểm chứng độc lập.

### Lỗ hổng trong thiết kế deploy

- [Activate release](../../../.github/workflows/deploy.yml) chạy bằng một remote `bash -s` gắn với phiên SSH.
- Workflow dừng các writer trước migration, sau đó gọi `systemd-run --wait --collect --pipe` cho migration. Migration là tiến trình systemd riêng nhưng activation/cleanup vẫn thuộc shell SSH.
- Cutover thực tế mất khoảng **6 phút 30 giây**, dài hơn khoảng im lặng 4 phút 16 giây trước khi SSH đứt. `prepare_cutover` không gửi tiến độ trong đoạn log đó.
- Lệnh SSH activation không đặt `ServerAliveInterval`/`ServerAliveCountMax`. VPS có `ClientAliveInterval=0`. Đây là yếu tố rủi ro; bằng chứng hiện tại chưa chỉ ra chính xác thiết bị mạng/hop nào làm mất kết nối.
- Cleanup chỉ dựa vào `trap cleanup EXIT` trong remote shell. Không có coordinator phục hồi độc lập với phiên SSH để đưa release tương thích lên sau khi DB đã thay đổi.
- Không thấy thông báo rollback trong deploy log và các file cleanup vẫn còn. Có thể xác nhận cleanup/activation không hoàn tất; không đủ log để khẳng định chính xác trap bị bỏ qua hay tự thất bại trên pipe đã đóng.
- [Guard rollback](../../../deploy/check_field_code_rollback.py) sẽ từ chối binary cũ sau contract. Guard này bảo vệ dữ liệu, nhưng pipeline vẫn cần đường phục hồi tiến về release mới khi rollback không còn an toàn.

Transient migration process kết thúc `120` sau khi DB/manifest đã ghi hoàn tất. Mã này phù hợp với lỗi flush standard streams lúc Python thoát sau khi pipe bị đóng, theo [tài liệu Python](https://docs.python.org/3.10/library/sys.html#sys.exit). Đây là **suy luận**, không phải traceback đã thu được: `--pipe` đưa output về SSH nên journal không giữ được stderr đầy đủ của process.

## Cloudflare: deploy frontend thất bại riêng

Frontend thực tế chạy trên **Workers**, worker `flama-frontend1001`, custom domain `flama.vn`. Mô tả Pages trong một số tài liệu repo không phản ánh triển khai hiện tại.

### Bằng chứng từ Builds API

- Build lỗi: `eb863ce9-6f5f-4e00-aa70-5c8d45f96a85`, commit merge `4cd403079b7dae06bda526e26807a4b5a682dce9`, root `/frontend`.
- `npm run build` thành công. Lỗi nằm ở deploy command `npx wrangler deploy`.
- Wrangler phát hiện Vite và bắt đầu tự cài `wrangler`, `@cloudflare/vite-plugin`, sửa scripts và tạo `wrangler.jsonc` trong build container.
- Bước cài đặt đó thất bại với `npm error Cannot read properties of null (reading 'edgesOut')`.
- Lượt thành công trước: build `ef0834e0-b8be-460e-8d89-4d2021b3a273`, commit `c1dfa6e88bcac074649fec9579a6314674a9f51b`, Wrangler `4.150.0`, Node `24.18.0`, npm `10.9.2`.
- Lượt lỗi: Wrangler `4.151.1`, Node `24.21.0`, npm `10.9.2`.
- `frontend/package.json`, `frontend/package-lock.json` và `frontend/vite.config.ts` không đổi giữa hai commit. Repo không có Wrangler config và không pin Wrangler trong devDependencies.
- Deployment frontend đang active vẫn là deployment ngày 2026-10-14 JST, version `4227378e-12ac-49db-a71a-4631fc6a6ac9`.

Đã xác nhận toolchain deploy thay đổi ngoài lockfile và auto-configuration phát sinh lỗi. Chưa có npm debug log nội bộ của build container để quy chính xác lỗi `edgesOut` cho Node, Wrangler, npm cache hay dependency resolver; không khẳng định chỉ đổi một version sẽ chắc chắn sửa được.

Cloudflare frontend thất bại trước khi backend bị dừng hơn 12 phút. Cùng một commit kích hoạt hai lỗi riêng; không có bằng chứng Cloudflare build làm VPS tắt dịch vụ. API 502 được xác nhận tới tận Nginx/upstream đang dừng.

## Khoảng trống kiểm chứng trước merge

- GitHub CI của commit merge đã qua backend, frontend, MySQL, Redis và SPA contract. Job `deploy / deploy` thất bại sau đó.
- Các test deploy hiện có kiểm tra thứ tự lệnh, guard, shell syntax và một số failure path; chưa mô phỏng mất SSH khi migration vẫn chạy ở systemd.
- Fixture cutover nhỏ không tái hiện khoảng im lặng nhiều phút với 41.568 notes và 33.944 media trên VPS.
- CI frontend không chạy đúng đường Workers auto-configuration/dependency installation của `npx wrangler deploy` trên Cloudflare.
- Lượt review PR trước chưa kiểm chứng hai đường thất bại này.

## Phương án phục hồi và ngăn tái diễn

Các bước dưới đây là kế hoạch, **chưa thực thi**.

1. **P0 — khôi phục backend bằng release tương thích DB 68.** Xác nhận manifest/release/env, tiếp tục các bước cài unit và activation của release `4cd403079b7dae06bda526e26807a4b5a682dce9`, chuyển symlink, đưa web/Connect/Study lên theo cấu hình đã duyệt. Kiểm tra health loopback, health public, trạng thái worker và một luồng đọc note. DB đã tới head nên điểm tiếp tục nằm sau migration.
2. **P0 — phục hồi frontend theo deploy tường minh.** Khai báo Worker name, thư mục asset `dist` và SPA fallback trong Wrangler config của repo; pin CLI cùng lockfile; kiểm tra `wrangler deploy --dry-run` trong workspace riêng rồi deploy. Phiên bản 4.150.0 là mốc từng thành công để tham chiếu, không phải bản đã được kiểm thử lại cho recovery hiện tại.
3. **P1 — giao toàn bộ deploy cho process bền vững trên VPS.** Một coordinator systemd có lock server-side, trạng thái theo phase, stdout/stderr vào journal; SSH chỉ kích hoạt và theo dõi, có thể kết nối lại. Migration và activation cần chung cơ chế điều phối, không chỉ migration sống sót sau mất SSH.
4. **P1 — recovery theo capability DB/code.** Sau contract, phục hồi tiến về code mới; chỉ rollback binary khi guard xác nhận schema tương thích. Lưu kết quả terminal và health để phát hiện trạng thái bỏ dở.
5. **P1 — bổ sung keepalive và tiến độ.** Đặt SSH keepalive, heartbeat cutover, budget theo dữ liệu thực tế. Keepalive giảm rủi ro ngắt nhưng không thay thế coordinator bền vững.
6. **P1 — regression test cho ngắt transport.** Cắt SSH sau quiescence, trong backfill, sau contract và trước activation; chứng minh hệ thống đi tới một trạng thái phục hồi được. Bổ sung kiểm tra đúng cấu hình Workers/CLI của production.

## Nguồn và giới hạn

- [GitHub Actions run sau merge](https://github.com/TrinhChung/Flama/actions/runs/39182606644).
- [Job deploy thất bại](https://github.com/TrinhChung/Flama/actions/runs/39182606644/job/117841470277).
- Workflow [deploy.yml](../../../.github/workflows/deploy.yml), [migration entry point](../../../deploy/migrate_database.py), [rollback guard](../../../deploy/check_field_code_rollback.py), [unit web](../../../deploy/flama.service).
- VPS: journal, systemctl, readlink/stat, metadata schema và manifest cutover đọc trực tiếp; không đọc nội dung note hay xuất credential.
- Cloudflare: Workers scripts/domains/deployments và [Builds API](https://developers.cloudflare.com/workers/ci-cd/builds/api-reference/), chỉ dùng GET.
- Còn thiếu: nguyên nhân transport SSH tại hop mạng cụ thể; stderr đầy đủ của migration process; npm debug log trong build container; kiểm thử restore dữ liệu độc lập.

## Phục hồi sau khi người dùng yêu cầu sửa

- **20:26:36 JST:** phục hồi backend hoàn tất dưới unit systemd riêng. Trước khi chuyển release đã xác nhận DB head `20261014_000068`, manifest `contracted`, env staging giống env đang dùng, app factory production khởi động thụ động và model `Note` đọc được giá trị canonical. Không chạy lại migration hay hạ schema.
- Đồng bộ bootstrap admin không thay đổi tài khoản; cài unit từ release `4cd403079b7dae06bda526e26807a4b5a682dce9`, chuyển `/opt/flama/current`, bật web/Connect/Study và timer. Loopback health và worker readiness đều qua; API/Connect public trả 200.
- **20:35:41–20:35:46 JST:** diễn tập transport bằng tác vụ mô phỏng trên VPS, không truy cập app/DB. Chủ động kill SSH client sau khi systemd nhận tác vụ; coordinator vẫn hoàn tất sau ngắt kết nối, journal và trạng thái `succeeded health` còn đọc được từ kết nối mới.
- **20:36:55 JST:** Cloudflare kích hoạt frontend version `402575aa-1ef5-4ea8-b9ab-dea9d471c4a8` ở 100%, deployment `ae6cb9cf-e368-416a-bb1d-5a3a21ca2c36`. Build dùng API URL production, Wrangler `4.150.0` đã pin và config asset/SPA tường minh. Không chạy auto-configuration hay cài plugin Vite lúc deploy.
- HTML public khớp byte với bản build mới; `/`, `/login` và entry JS/CSS trả 200. Web, Connect và Study worker đều active.
- Bản sửa repo đưa toàn bộ activation vào coordinator systemd với server lock, trạng thái theo phase và journal; SSH chỉ khởi chạy/theo dõi và tự kết nối lại. Lỗi giữ lại env/payload phục vụ recovery, guard vẫn chặn rollback code không tương thích sau contract. CI bổ sung Wrangler dry run, Node và Wrangler được pin. Xem [Deployment and recovery](../DEPLOY_RECOVERY.md).

Kết quả kiểm tra cục bộ: 79 tooling tests qua (gồm rollback, giữ file recovery và mất SSH khi start/theo dõi); các test Study/Field deployment safety qua; `npm ci`, production typecheck/build và Wrangler dry run qua. Lint không có lỗi, còn các cảnh báo đã có từ trước.
