# P9-02b — bằng chứng trước khi gỡ wire và positional mapping

> Chuẩn bị 2026-10-02. Logger mới chỉ bắt đầu có coverage sau khi release chứa nó chạy trên cả web, Connect và worker. Không backdate cửa sổ dựa vào ngày cấp phiên cuối.

`STUDY_RETIREMENT {JSON}` được ghi vào journal khi đi vào `session.issue`, `session.restore`, `session.commit` (gồm replay mất ACK), `worker.batch` với wire cũ hoặc `anki.ordinal` dùng positional fallback. Payload chỉ có schema, entrypoint, wire cố định và UTC; không có token, answer, nội dung Note hay ID của learner/session. Nhánh v4 không log và không có SQL ghi telemetry. Issuance có thể log trước khi transaction commit: đây là overcount bảo thủ.

Giữ journal trên mọi process đủ tối thiểu 30 ngày. Kiểm log rotation, các khoảng downtime/deploy, journal bị thiếu, logger filter/rate limit, binary nào chưa có instrumentation và worker nào dùng logger khác trước khi xác nhận coverage. Số lượng log bằng zero không chứng minh các điều này.

1. Export journal có timestamp UTC cho cả ba unit trong khoảng muốn xét:

   ```bash
   journalctl -u flama -u flama-connect -u flama-study-worker --since '<START UTC>' --until '<END UTC>' -o json > /root/backups/p9-journal.jsonl
   ```

2. Tạo coverage record trong thư mục vận hành riêng (không commit log chứa dữ liệu ứng dụng vào repo):

   ```json
   {
     "start_utc": "<actual deployment/coverage start in ISO UTC>",
     "end_utc": "<journal export end in ISO UTC>",
     "continuous": false,
     "gaps": ["Coverage chưa được kiểm chứng"],
     "covered_entrypoints": ["session.issue", "session.restore", "session.commit", "worker.batch", "anki.ordinal"]
   }
   ```

   Chỉ đặt `continuous=true` và `gaps=[]` sau khi kiểm các điều kiện ở trên; ghi provenance/release/log retention của xác nhận cùng record. Mất segment hoặc process không instrumented thì giữ gap. Không dùng counter trong process hay chỉ ghi ngày last-issued.

3. Thu thập và kiểm gate trên audit app, credential MySQL chỉ SELECT:

   ```bash
   python scripts/collect_study_retirement_observation.py --journal /root/backups/p9-journal.jsonl --coverage /root/backups/p9-coverage.json --output /root/backups/p9-observation.json
   flask --app wsgi_audit.py study-phase9-readiness --observed-at '<END UTC>' --retirement-observation /root/backups/p9-observation.json
   ```

   `--observed-at` trùng chính xác `end_utc`: report là snapshot kết thúc ở đó. Collector ghi SHA-256 của journal/coverage, từ chối event ngoài interval, JSON lỗi, schema/label lạ. Report `unknown` khi thiếu entrypoint, gap, cửa sổ <30 ngày hoặc export chưa phủ đến thời điểm quan sát; usage dương luôn `waiting`. Late restore/retry bắt đầu lại cửa sổ zero-use. Gate không cho phép destructive migration (`destructive_steps_allowed=false`).

Ordinal chỉ xét Card/ref external: native occurrence không cần source ordinal. Detached/dangling ref, missing/mismatched ordinal và duplicate external ordinal đều chặn. Ref detached phải được giải quyết bằng disposition có evidence; không xóa để làm report xanh.

`connect_package_versions` còn `unknown`: API hiện hành chưa chứng minh coverage version của package/client cũ. Log positional không thay thế evidence này. Chưa gỡ fallback, không xóa IndexedDB/pending answers, giữ decoder cho receipt/history. P9-08 chỉ thực hiện sau khi từng nhóm đủ gate; P9-09/10 còn phụ thuộc cutover ổn định, replacement và manifest consumers=0 + restore proof.
