# Task: Đổi mật khẩu với xác thực mật khẩu hiện tại và xác nhận mật khẩu mới

## Mục tiêu

Thiết kế và triển khai lại màn **Đổi mật khẩu** theo flow an toàn, yêu cầu người dùng xác thực mật khẩu hiện tại trước khi thay đổi mật khẩu.

Form đổi mật khẩu phải có đủ 3 trường:

1. **Mật khẩu hiện tại**
2. **Mật khẩu mới**
3. **Xác nhận mật khẩu mới**

Không cho phép đổi mật khẩu chỉ bằng một trường mật khẩu mới khi người dùng đang đăng nhập.

---

## 1. UI / UX màn đổi mật khẩu

Tạo hoặc cập nhật màn đổi mật khẩu trong khu vực Settings / Account Security phù hợp với Information Architecture hiện tại.

Form tối thiểu:

```text
Mật khẩu hiện tại
[........................]

Mật khẩu mới
[........................]

Xác nhận mật khẩu mới
[........................]

[ Đổi mật khẩu ]
```

### Yêu cầu UX

- Cả 3 trường mặc định là `type=password`.
- Có thể có nút show/hide password riêng cho từng trường.
- Không submit khi dữ liệu chưa hợp lệ.
- Hiển thị lỗi ngay tại field phù hợp thay vì chỉ toast chung chung.
- Khi đang submit phải disable nút để tránh gửi nhiều request.
- Không giữ giá trị password trong localStorage/sessionStorage.
- Sau khi đổi thành công phải clear toàn bộ các field password khỏi form state.

---

## 2. Validation phía frontend

Frontend chỉ dùng validation để cải thiện UX; backend vẫn phải kiểm tra lại toàn bộ điều kiện.

### Mật khẩu hiện tại

- bắt buộc nhập.

### Mật khẩu mới

- bắt buộc nhập;
- áp dụng password policy hiện tại của Flama;
- nếu Flama hiện chưa có password policy thống nhất thì cần research và chuẩn hóa policy dùng chung cho Register / Change Password / Reset Password;
- không cho phép mật khẩu mới giống mật khẩu hiện tại.

Không tự đặt policy quá phức tạp chỉ để tăng hình thức. Ưu tiên độ dài tối thiểu hợp lý và hỗ trợ password manager/passphrase.

### Xác nhận mật khẩu mới

Phải khớp chính xác với `new_password`.

Ví dụ lỗi:

```text
Mật khẩu xác nhận không khớp với mật khẩu mới.
```

---

## 3. Backend API contract

Endpoint đổi mật khẩu phải nhận tối thiểu:

```json
{
  "current_password": "...",
  "new_password": "...",
  "confirm_password": "..."
}
```

Có thể không bắt buộc gửi `confirm_password` xuống backend nếu kiến trúc frontend/backend hiện tại có quy ước khác, nhưng khuyến nghị backend vẫn validate confirmation để tránh phụ thuộc hoàn toàn vào frontend.

Backend phải thực hiện theo thứ tự logic:

```text
authenticated user
      ↓
validate request
      ↓
verify current_password
      ↓
validate new password policy
      ↓
new_password == confirm_password
      ↓
new_password != current_password
      ↓
hash new password
      ↓
update password atomically
      ↓
security/audit handling
```

Không bao giờ log `current_password`, `new_password` hoặc `confirm_password`.

---

## 4. Xác thực mật khẩu hiện tại

Backend phải verify `current_password` bằng password hash hiện có của tài khoản.

Nếu sai:

- không thay đổi bất kỳ dữ liệu nào;
- trả lỗi rõ ràng nhưng không leak thông tin nội bộ;
- frontend hiển thị tại trường `Mật khẩu hiện tại`.

Ví dụ:

```text
Mật khẩu hiện tại không chính xác.
```

Cần sử dụng hàm password verification hiện có, không tự tạo cơ chế hash/compare mới nếu hệ thống đã có abstraction.

---

## 5. Hash mật khẩu mới

- Sử dụng password hashing mechanism hiện tại của Flama.
- Không lưu plaintext.
- Không tự implement cryptography.
- Nếu hệ thống đang dùng framework helper cho password hashing thì tiếp tục dùng cùng chuẩn.

Cần kiểm tra xem password hash hiện tại có cần migration/rehash khi user đổi mật khẩu hay không.

---

## 6. Session sau khi đổi mật khẩu

Cần research và quyết định rõ policy session sau khi đổi mật khẩu.

Khuyến nghị:

### Session hiện tại

Có thể giữ session hiện tại để UX không bị gián đoạn, vì user vừa xác thực lại bằng `current_password`.

### Các session khác

Nên nghiên cứu khả năng revoke/logout các session khác của cùng tài khoản sau khi đổi mật khẩu.

Mục tiêu:

```text
Nếu account đã bị đăng nhập trên thiết bị lạ
→ user đổi mật khẩu
→ session lạ không nên tiếp tục tồn tại vô thời hạn.
```

Nếu session architecture hiện tại chưa hỗ trợ revoke theo user/session version thì ghi dependency và đề xuất phase sau, không fake chức năng ở frontend.

---

## 7. Tài khoản đăng nhập bằng Google/OAuth

Cần kiểm tra trường hợp user được tạo bằng Google Login hoặc provider khác và **chưa từng thiết lập password nội bộ**.

Không được hiển thị form yêu cầu `current_password` nếu tài khoản thực tế không có password để xác thực.

Research flow phù hợp, ví dụ:

- user password account → `Change Password`;
- OAuth-only account → `Set Password` sau một bước xác minh phù hợp;
- account có cả password + Google → dùng flow Change Password bình thường.

Phần này cần bám vào identity model hiện tại của Flama.

---

## 8. Rate limiting và chống brute force

Endpoint đổi mật khẩu là endpoint nhạy cảm vì nó cho phép thử `current_password`.

Cần:

- áp dụng rate limit;
- xem xét reuse login rate limit/security infrastructure hiện tại;
- không cho attacker thử mật khẩu cũ với tốc độ cao khi đã có session bị chiếm quyền;
- ghi security event khi có nhiều lần verify current password thất bại bất thường.

Không khóa account quá dễ chỉ vì vài lần nhập sai do người dùng bình thường.

---

## 9. CSRF / authentication security

Nếu Flama đang dùng cookie/session auth:

- endpoint phải yêu cầu authenticated session;
- request thay đổi mật khẩu phải đi qua CSRF protection hiện tại;
- không cho GET hoặc query string thay đổi password;
- chỉ dùng method phù hợp như POST/PATCH.

Không đưa password vào URL, analytics payload hoặc error tracking metadata.

---

## 10. Thông báo sau khi đổi mật khẩu

Sau khi thành công:

```text
Mật khẩu đã được thay đổi thành công.
```

Nghiên cứu thêm notification/email bảo mật:

> Mật khẩu tài khoản Flama của bạn vừa được thay đổi.

Email không chứa mật khẩu mới hoặc bất kỳ credential nào.

Nếu hệ thống notification/email chưa có infrastructure phù hợp thì ghi dependency, không bắt buộc block phase đầu.

---

## 11. Audit / security event

Nên ghi security event tối thiểu:

- user id;
- event type: `PASSWORD_CHANGED`;
- timestamp;
- session/request metadata phù hợp;
- IP / user-agent nếu policy hệ thống cho phép.

Tuyệt đối không ghi password hoặc password hash vào audit payload.

Có thể sử dụng dữ liệu này về sau cho màn Security Activity.

---

## 12. Error handling

Cần phân biệt tối thiểu:

- current password sai;
- password mới không đạt policy;
- confirm password không khớp;
- password mới giống password cũ;
- session hết hạn;
- tài khoản không hỗ trợ flow Change Password;
- lỗi server/database.

Không trả raw stack trace hoặc hash-related error ra frontend.

---

## 13. Kiểm tra code hiện tại trước khi triển khai

Trước khi code cần kiểm tra:

- user/account model;
- password hash field;
- auth service;
- register/login/reset-password flow;
- password policy hiện tại;
- session management;
- CSRF middleware;
- login rate limiting;
- settings/profile/account-security routes;
- frontend auth schemas/forms hiện có.

Ưu tiên reuse abstraction hiện tại thay vì tạo password logic riêng cho từng màn.

---

## 14. Tests

### Backend

Tối thiểu test:

1. đổi mật khẩu thành công với current password đúng;
2. current password sai → reject;
3. confirm password không khớp → reject;
4. password mới không đạt policy → reject;
5. password mới giống password hiện tại → reject;
6. unauthenticated request → reject;
7. CSRF invalid → reject nếu áp dụng;
8. password hash thực sự thay đổi sau success;
9. mật khẩu cũ không login được sau khi đổi;
10. mật khẩu mới login được;
11. OAuth-only account được xử lý đúng policy;
12. không leak password trong log/error response.

### Frontend

- required validation;
- confirm mismatch;
- backend current-password error hiển thị đúng field;
- submit disabled/pending;
- success state;
- password fields được clear sau success;
- show/hide password hoạt động đúng.

---

## Deliverables

- Màn Change Password với 3 trường bắt buộc.
- API đổi mật khẩu yêu cầu xác thực mật khẩu hiện tại.
- Validation password mới + confirm password.
- Password policy dùng chung với auth flows khác nếu phù hợp.
- Error handling rõ ràng.
- Security/rate-limit/CSRF review.
- Xử lý rõ OAuth-only accounts.
- Tests backend/frontend.
- Tài liệu ngắn về session policy sau password change.

---

## Acceptance criteria

- Người dùng không thể đổi mật khẩu nếu không nhập đúng mật khẩu hiện tại.
- Người dùng phải nhập mật khẩu mới hai lần.
- Hai giá trị mật khẩu mới phải trùng nhau.
- Mật khẩu mới phải đạt password policy của Flama.
- Không cho phép dùng lại chính mật khẩu hiện tại trong lần đổi đó.
- Password được hash bằng cơ chế hiện tại trước khi lưu.
- Không có password/plaintext/password hash bị ghi vào log hoặc response.
- Flow hoạt động đúng với CSRF/auth/session architecture hiện tại.
- Tài khoản OAuth-only không bị đưa vào một flow yêu cầu mật khẩu cũ mà họ chưa từng có.
- Có test cho các happy path và failure path chính.
