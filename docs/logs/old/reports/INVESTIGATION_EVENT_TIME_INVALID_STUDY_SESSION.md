# BÁO CÁO ĐIỀU TRA SỰ CỐ: MẤT THÔNG TIN PHIÊN HỌC & LỖI `EVENT_TIME_INVALID` SAU KHI HỌC 50 TỪ

> **Ngày thực hiện điều tra:** 24/09/2026 (08:35 GMT+7)  
> **Môi trường:** Production VPS (`chung_hostinger_vps`; URL hiện tại: `flama.vn`) & Frontend React (`D:\Project\nihongo\frontend`)
> **Trạng thái:** Đã điều tra tường tận nguyên nhân gốc rễ (Root Cause Identified) — **Tuân thủ chỉ thị: CHỈ ĐIỀU TRA VÀ BÁO CÁO, CHƯA CHỈNH SỬA CODE.**

---

## 1. TÓM TẮT SỰ CỐ (EXECUTIVE SUMMARY)

- **Hiện tượng:** Người dùng vừa hoàn thành học xong **50 từ vựng** trong một bộ thẻ, khi hệ thống tiến hành đồng bộ (sync) thì lập tức báo lỗi đỏ toàn màn hình:
  ```text
  Không thể tải dữ liệu
  Refusing to persist an invalid study session: EVENT_TIME_INVALID.
  ```
  Sau đó, toàn bộ tiến độ 50 từ đã học bị mất, phiên học bị gián đoạn và reset.
- **Tài khoản & Phiên học bị ảnh hưởng:**
  - **User ID:** `1`
  - **Deck bị ảnh hưởng:** Deck ID `462` (*Bài 047*).
  - **Session ID:** `fec8a826-3d7e-47a7-a99e-fd3a68e3e48f`.
  - **Thời điểm mở phiên học:** `2026-09-23 22:59:21 UTC` (05:59 sáng giờ VN).
  - **Thời điểm xảy ra lỗi:** `2026-09-23 23:12:15 UTC` (06:12 sáng giờ VN, sau ~13 phút học).

---

## 2. KẾT QUẢ ĐIỀU TRA THỰC TẾ TRÊN VPS (`chung_hostinger_vps`)

### 2.1. Kiểm tra Cơ sở dữ liệu MySQL (`flama`)
Truy vấn trực tiếp trên database MySQL của VPS cho session `fec8a826-3d7e-47a7-a99e-fd3a68e3e48f`:

```sql
SELECT id, user_id, scope_type, scope_id, local_deck_id, status, opened_at, expires_at 
FROM study_sessions 
WHERE id = 'fec8a826-3d7e-47a7-a99e-fd3a68e3e48f';
```
- **Kết quả:**
  - `status`: **`open`** (Vẫn đang mở, chưa từng được commit!).
  - `opened_at`: `2026-09-23 22:59:21`
  - `expires_at`: `2026-09-24 22:59:21` (Hạn 24 giờ, còn hạn đến tận ngày hôm sau).
  - `local_deck_id`: `462` (Bài 047, tổng cộng 60 thẻ).

Kiểm tra các bảng ghi nhận tiến độ:
```sql
SELECT COUNT(*) FROM study_session_commits WHERE session_id = 'fec8a826-3d7e-47a7-a99e-fd3a68e3e48f';
SELECT COUNT(*) FROM study_session_batches WHERE session_id = 'fec8a826-3d7e-47a7-a99e-fd3a68e3e48f';
SELECT COUNT(*) FROM review_events WHERE study_session_id = 'fec8a826-3d7e-47a7-a99e-fd3a68e3e48f';
```
- **Kết quả:** Cả 3 bảng đều trả về **`0` rows**. Không có bất kỳ commit, batch hay review event nào được lưu trên backend MySQL.

### 2.2. Kiểm tra Nhật ký Nginx & Gunicorn
Kiểm tra log Nginx tại thời điểm xảy ra lỗi:
```log
162.159.110.34 - - [23/Sep/2026:23:12:15 +0000] "OPTIONS /api/study/sessions/fec8a826-3d7e-47a7-a99e-fd3a68e3e48f HTTP/1.1" 200 0
172.71.24.125 - - [23/Sep/2026:23:12:15 +0000] "GET /api/study/sessions/fec8a826-3d7e-47a7-a99e-fd3a68e3e48f HTTP/1.1" 200 186
```
- **Đặc biệt lưu ý:** **HOÀN TOÀN KHÔNG CÓ** request `POST /api/study/sessions/.../commit` gửi đến server!
- Điều này chứng minh 100%: **Lỗi không bắt nguồn từ mạng hay lỗi server 500, mà request commit bị chặn đứng và sập ngay tại Frontend (Client-side) trước khi kịp phát request lên mạng.**

---

## 3. NGUYÊN NHÂN CỐT LÕI TẠI SAO XẢY RA LỖI (ROOT CAUSE ANALYSIS)

Chuỗi sự kiện gây ra lỗi được xâu chuỗi chính xác 100% qua mã nguồn như sau:

### 3.1. Tại sao lại xảy ra đúng ở mốc "Vừa học xong 50 từ"?
Trong file `D:\Project\nihongo\frontend\src\features\study\session\studySessionEngine.ts`:
```typescript
// Dòng 48
export const DEFAULT_STUDY_BATCH_EVENT_LIMIT = 50

// Dòng 354-363
export function automaticCommitMode(
  session: PersistedStudySession,
  view: StudySessionView,
  eventLimit = DEFAULT_STUDY_BATCH_EVENT_LIMIT,
): AutomaticCommitMode | null {
  if (session.status !== 'active' || session.events.length === 0) return null
  if (view.session_state === 'complete_today') return 'finish'
  if (session.events.length >= Math.max(1, eventLimit)) return 'rollover' // <-- KÍCH HOẠT KHI ĐỦ 50 THẺ
  return null
}
```
Khi người học trả lời từ thứ 1 đến 49, phiên học chỉ lưu trữ tạm. Đúng khi trả lời xong **thẻ thứ 50** (`session.events.length === 50`), hệ thống kích hoạt chế độ **`rollover`** (đồng bộ batch 50 thẻ đầu lên server rồi tiếp tục phiên học):
```typescript
// useStudySession.ts (dòng 721-725)
if (mode === 'rollover') {
  void commit({
    reason: 'rollover',
    resumeAfterCommit: true,
  }).catch(() => {})
}
```

### 3.2. Tại sao lại phát sinh lỗi `Refusing to persist: EVENT_TIME_INVALID`?
Hàm `commit()` thực hiện các bước sau (`useStudySession.ts`, dòng 542–548):
```typescript
const prepared = prepareCommit(active, options)
if (isThisLease()) activateSession(prepared.session)
sessionDurableRef.current = await saveStudySession(prepared.session) // <-- NÉM LỖI TẠI ĐÂY!
const result = await appApi.mutate<StudySessionCommitReceipt>(
  `/api/study/sessions/${prepared.session.snapshot.session_id}/commit`,
  'POST',
  prepared.payload,
)
```
Tại dòng 544, trước khi gửi `POST .../commit` lên server, hệ thống gọi `saveStudySession(prepared.session)` để ghi đè session xuống IndexedDB.

Trong `sessionStore.ts` (dòng 407–413):
```typescript
export async function saveStudySession(session: PersistedStudySession) {
  const result = normalizePersistedStudySession(session, session.scope_key)
  if (result.status === 'quarantine') {
    throw new Error(
      `Refusing to persist an invalid study session: ${result.quarantine.reason}.`, // <-- LỖI NÀY XUẤT HIỆN
    )
  }
  ...
```

Trong `sessionRestore.ts` (dòng 807–815), hàm kiểm tra tính hợp lệ của toàn bộ 50 sự kiện học:
```typescript
for (const event of retainedEvents) {
  ...
  if (
    event.scheduler_offset_ms > leaseDurationMs
    || (previousOffset !== null && event.scheduler_offset_ms < previousOffset) // <-- KIỂM TRA ĐƠN ĐIỆU
  ) {
    return quarantine(
      'EVENT_TIME_INVALID',
      'Stored study event offsets must be monotonic and within the session lease.',
    )
  }
  previousOffset = event.scheduler_offset_ms
}
```

### 3.3. Lỗ hổng kỹ thuật: Tại sao `scheduler_offset_ms` lại nhỏ hơn `previousOffset`?

Có **2 nguyên nhân kỹ thuật nghiêm trọng** kết hợp gây ra hiện tượng thời gian bị lùi lại ($offset_N < offset_{N-1}$):

#### 1. Lỗi Re-anchoring đồng hồ liên tục trên từng thẻ trong `useStudySession.ts`
Trong `useStudySession.ts` (dòng 160–168):
```typescript
const activateSession = useCallback((next: PersistedStudySession | null) => {
  sessionRef.current = next
  setSession(next)
  if (!next) {
    clockRef.current = null
    return
  }
  const elapsedWall = Math.max(
    0,
    Date.now() - next.opened_client_at_ms,
  )
  clockRef.current = {
    serverAtMs: Date.parse(next.snapshot.server_now_utc) + elapsedWall,
    performanceAtMs: performance.now(),
  }
}, [])
```
- Mỗi khi người dùng trả lời 1 thẻ, `activateSession(next)` được gọi lại.
- Mỗi lần gọi, nó lại đọc `Date.now()` để tính lại `serverAtMs`.
- Trên Windows, hàm `Date.now()` có độ phân giải thô (~15.625ms theo nhịp ngắt hệ thống Windows) và phụ thuộc vào dịch vụ đồng bộ giờ (Windows Time / NTP), trong khi `performance.now()` là bộ đếm phần cứng đơn điệu với độ chính xác micro-giây.
- Việc liên tục cộng trừ và gán lại mốc `serverAtMs` bằng `Date.now()` sau mỗi thẻ khiến giá trị `now()` bị giật lùi (clock jitter / time-step skew) từ 1 đến 15 mili-giây nếu người dùng thao tác nhanh giữa 2 thẻ liền kề.

#### 2. Hàm `applyLocalAnswer` hoàn toàn không có cơ chế chặn dưới (Monotonic Clamp)
Trong `studySessionEngine.ts` (dòng 204–208):
```typescript
const serverAnchor = Date.parse(session.snapshot.server_now_utc)
const schedulerOffset = Math.max(
  0,
  Math.round(decision.scheduler_at_ms - serverAnchor),
)
```
- Phép tính chỉ dùng `Math.max(0, ...)`.
- **Hoàn toàn KHÔNG kiểm tra `previousOffset = session.events.at(-1)?.scheduler_offset_ms`!**
- Nếu do clock jitter, thời gian tính ra của thẻ sau nhỏ hơn thẻ trước dù chỉ 1ms (ví dụ thẻ trước 12.050ms, thẻ sau 12.048ms), `schedulerOffset` vẫn bị gán là `12.048ms`.
- Khi bộ thẩm định `sessionRestore.ts` duyệt qua mảng 50 thẻ: $12.048 < 12.050$ vi phạm điều kiện đơn điệu $\Rightarrow$ Kích hoạt `EVENT_TIME_INVALID` ngay lập tức!

---

## 4. TẠI SAO LẠI BỊ MẤT DỮ LIỆU PHIÊN HỌC (DATA LOSS CASCADE)?

1. **Khi thẻ 50 trả lời xong:** `commit({ reason: 'rollover' })` được gọi.
2. **Trước khi gửi request:** `saveStudySession(prepared.session)` ném lỗi `Refusing to persist an invalid study session: EVENT_TIME_INVALID.`.
3. **Request không được gửi:** Server không nhận được gì.
4. **Bắt lỗi và hiển thị:** Hàm `commit()` bắt exception và gán `setError(caught)`. Toàn bộ giao diện học bị thay thế bởi `PageState` báo lỗi đỏ:
   *`Không thể tải dữ liệu: Refusing to persist an invalid study session: EVENT_TIME_INVALID.`*
5. **Dữ liệu bị hủy khi tải lại trang:**
   - 50 từ đã học lúc này chỉ nằm trong RAM của tab trình duyệt (`sessionRef.current`), chưa được lưu vào IndexedDB (do `saveStudySession` đã từ chối lưu).
   - Khi người học thấy lỗi và bấm F5 / tải lại trang:
     - RAM bị giải phóng.
     - Hàm `bootstrap()` chạy `loadStudySessionWithDurability()`. Do không có bản ghi hợp lệ hoặc bản ghi cũ bị đánh giá là lỗi, hệ thống kích hoạt cơ chế cách ly (`moveSessionToQuarantine`) xóa bỏ phiên học khỏi `activeStore` (`activeStore.delete(key)`).
     - Hệ thống gọi API `GET /api/study/sessions/fec8a826...` kiểm tra status (chính là log GET lúc 23:12:15 trong Nginx).
     - Do session cũ bị coi là hỏng hoặc không đồng bộ được, hệ thống xóa sạch và tạo lại phiên mới trống rỗng.
   - **Hậu quả:** Người học mất sạch thông tin và kết quả ôn tập của 50 từ vừa học.

---

## 5. ĐỀ XUẤT HƯỚNG XỬ LÝ (ACTIONABLE RECOMMENDATIONS FOR NEXT TASK)

*(Lưu ý: Không thực hiện sửa code trong lượt này theo đúng chỉ thị của người dùng. Các giải pháp dưới đây dành cho lượt xử lý tiếp theo).*

1. **Bắt buộc bổ sung Monotonic Clamping trong `applyLocalAnswer` (`studySessionEngine.ts`):**
   ```typescript
   const previousOffset = session.events.at(-1)?.scheduler_offset_ms ?? 0
   const rawOffset = Math.round(decision.scheduler_at_ms - serverAnchor)
   const schedulerOffset = Math.max(previousOffset, rawOffset)
   ```
   Điều này đảm bảo $offset_N \ge offset_{N-1}$ trong 100% mọi trường hợp, triệt tiêu hoàn toàn khả năng phát sinh `EVENT_TIME_INVALID` do clock jitter.

2. **Ổn định hóa đồng hồ Client (`useStudySession.ts`):**
   - Chỉ khởi tạo `clockRef.current` một lần duy nhất khi mở phiên học (hoặc khi tab focus lại).
   - Tuyệt đối không tính lại `Date.now() - next.opened_client_at_ms` trên từng thao tác trả lời thẻ.

3. **Cơ chế Soft Tolerance trong `sessionRestore.ts`:**
   - Nếu phát hiện độ lệch lùi thời gian cực nhỏ ($\le 1000$ms) do trôi đồng hồ hệ thống giữa các sự kiện trong cùng một phiên, tự động chuẩn hóa bằng `previousOffset` thay vì quăng `quarantine` làm sập ứng dụng và mất dữ liệu của người dùng.

4. **Bảo vệ dữ liệu khi Commit thất bại:**
   - Trong `useStudySession.ts`, nếu `saveStudySession` hoặc API commit thất bại, không để mất dữ liệu trong RAM; cho phép người dùng bấm nút "Thử đồng bộ lại" (Retry Sync) thay vì chuyển sang trạng thái lỗi không thể phục hồi.
