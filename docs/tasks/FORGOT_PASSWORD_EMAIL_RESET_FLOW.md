# Task: Forgot Password / Reset Password qua email

## Mục tiêu

Thiết kế và triển khai flow **Quên mật khẩu** hoàn chỉnh cho Flama.

Người dùng tại màn đăng nhập có thể yêu cầu khôi phục mật khẩu bằng email. Nếu tài khoản phù hợp, hệ thống gửi một email chứa **link reset password có token ngắn hạn, chỉ dùng một lần**. Người dùng mở link, nhập mật khẩu mới hai lần và hoàn tất đặt lại mật khẩu.

Task này tập trung vào business flow, security, UI/API và lifecycle của reset token.

Hạ tầng gửi email production được tách thành task phụ thuộc:

- `docs/tasks/TRANSACTIONAL_EMAIL_DELIVERY_INFRASTRUCTURE.md`

Không hard-code SMTP/provider trực tiếp vào auth service.

---

## 1. Entry point từ màn Login

Trên màn đăng nhập cần có link rõ ràng:

```text
Quên mật khẩu?
```

Khi nhấn vào sẽ chuyển sang route riêng, ví dụ:

```text
/forgot-password
```

Không mở modal quá phức tạp nếu một route độc lập giúp xử lý trạng thái gửi lại email, accessibility và deep-link tốt hơn.

---

## 2. Màn Forgot Password

Form tối thiểu:

```text
Khôi phục mật khẩu

Nhập email đã đăng ký với Flama.
Chúng tôi sẽ gửi hướng dẫn đặt lại mật khẩu nếu tài khoản phù hợp.

Email
[____________________________]

[ Gửi link khôi phục ]

← Quay lại đăng nhập
```

### UX requirements

- validate format email ở frontend;
- normalize email theo rule hiện tại của Flama;
- disable submit trong lúc request đang pending;
- tránh gửi request nhiều lần khi double-click;
- có trạng thái success rõ ràng;
- cho phép user nhập lại email nếu gõ sai;
- hỗ trợ resend nhưng phải có cooldown/rate limit;
- mobile responsive;
- không tiết lộ account có tồn tại hay không.

---

## 3. Chống account enumeration

Đây là yêu cầu bắt buộc.

Frontend và API không được trả response khác nhau theo kiểu:

```text
Email này không tồn tại.
```

hoặc:

```text
Tài khoản đã đăng ký bằng Google.
```

vì attacker có thể dùng endpoint để dò danh sách account.

Thay vào đó dùng response trung tính, ví dụ:

```text
Nếu email này được liên kết với một tài khoản có thể đặt lại mật khẩu, Flama sẽ gửi hướng dẫn đến email của bạn.
```

Backend có thể xử lý khác nhau bên trong nhưng response public phải có hình dạng và timing hợp lý để giảm khả năng enumeration.

---

## 4. API request reset password

Đề xuất endpoint REST, bám convention hiện tại của Flama:

```text
POST /api/v1/identity/password-reset/request
```

Payload:

```json
{
  "email": "user@example.com"
}
```

Backend flow:

```text
validate request
    ↓
normalize email
    ↓
rate limit
    ↓
lookup account internally
    ↓
check password-reset eligibility
    ↓
create/invalidate token state when applicable
    ↓
enqueue/send reset email
    ↓
return generic response
```

Không gửi token, user id hoặc thông tin account về response của request endpoint.

---

## 5. Password reset token

Không dùng JWT dài hạn hoặc token có thể reuse vô thời hạn chỉ vì dễ triển khai.

Cần thiết kế token có các thuộc tính:

- cryptographically secure random value;
- entropy đủ cao;
- expiration ngắn, configurable;
- one-time use;
- gắn với một user/account cụ thể;
- có khả năng revoke;
- token cũ bị vô hiệu khi user tạo request mới theo policy được chọn;
- không lưu raw token trong database nếu không cần.

### Khuyến nghị storage

Client/email nhận raw token:

```text
random_token
```

Database chỉ lưu dạng hash/digest của token, ví dụ:

```text
SHA-256(random_token)
```

Khi reset:

```text
raw token từ URL
      ↓
hash
      ↓
lookup digest
      ↓
verify expiration / used / revoked / user
```

Nếu database bị lộ thì attacker không được có ngay các reset link còn hiệu lực.

Không log raw reset token.

---

## 6. Model / schema đề xuất

Cần research model hiện tại trước khi quyết định final schema.

Một hướng có thể là `PasswordResetToken`:

```text
id
user_id
token_hash
created_at
expires_at
used_at
revoked_at
requested_ip (optional / privacy-reviewed)
request_user_agent (optional / privacy-reviewed)
```

Có thể không cần một row cho mọi request nếu có thiết kế token/version khác tốt hơn, nhưng phải đáp ứng:

- expiry;
- one-time use;
- revoke;
- audit/debug được;
- không lưu plaintext token.

Index phù hợp cho `token_hash`, `user_id`, expiry cleanup.

---

## 7. Thời hạn token

Không hard-code magic number sâu trong code.

Tạo config, ví dụ:

```text
PASSWORD_RESET_TOKEN_TTL_MINUTES
```

Research thời hạn phù hợp cho Flama. Một khoảng ngắn như 15–60 phút có thể được cân nhắc, nhưng team phải chọn dựa trên UX và security thay vì copy mặc định từ framework.

Email phải nói rõ link có thời hạn.

---

## 8. Reset link

Email chứa URL do server tạo từ canonical frontend origin, ví dụ về mặt cấu trúc:

```text
https://<flama-domain>/reset-password?token=<opaque-token>
```

Không build URL dựa trực tiếp vào request `Host` header không đáng tin cậy.

Dùng config canonical như:

```text
PUBLIC_APP_URL
```

Cần validate môi trường dev/staging/prod để tránh production email gửi link sang localhost hoặc staging.

Reset token không được đưa vào analytics/event tracking.

Nếu frontend/error tracker tự capture full URL thì phải bảo đảm query token được redact.

---

## 9. Màn Reset Password

Route ví dụ:

```text
/reset-password?token=...
```

Form:

```text
Đặt lại mật khẩu

Mật khẩu mới
[........................]

Xác nhận mật khẩu mới
[........................]

[ Đặt lại mật khẩu ]
```

### Validation

- mật khẩu mới bắt buộc;
- confirm password bắt buộc;
- hai giá trị phải trùng nhau;
- áp dụng **cùng password policy** với Register và Change Password;
- không tạo một password policy riêng cho Reset Password.

Tham chiếu task:

- `docs/tasks/CHANGE_PASSWORD_CURRENT_PASSWORD_CONFIRMATION.md`

Nếu password policy hiện tại chưa được centralize thì refactor thành shared backend validator + frontend schema tương ứng.

---

## 10. Validate token khi mở trang

Cần quyết định API contract để frontend biết link còn hợp lệ hay không.

Có thể dùng:

```text
POST /api/v1/identity/password-reset/validate
```

hoặc validate cùng request submit reset nếu không cần preflight.

Nếu có preflight, không trả thông tin user/email không cần thiết.

UI tối thiểu phải xử lý:

- token hợp lệ;
- token hết hạn;
- token đã dùng;
- token bị revoke;
- token malformed;
- server error.

Thông báo expired/invalid có CTA:

```text
Yêu cầu link khôi phục mới
```

---

## 11. API hoàn tất reset

Đề xuất:

```text
POST /api/v1/identity/password-reset/confirm
```

Payload:

```json
{
  "token": "opaque-token",
  "new_password": "...",
  "confirm_password": "..."
}
```

Backend flow phải atomic ở phần critical:

```text
validate input
    ↓
hash token + lookup
    ↓
verify unused/unexpired/not revoked
    ↓
validate password policy
    ↓
confirm password match
    ↓
update password hash
    ↓
mark token used
    ↓
revoke remaining active reset tokens for user
    ↓
apply session-security policy
    ↓
record security event
```

Phải chống race condition để cùng token không thể reset thành công hai lần khi có request concurrent.

---

## 12. Session policy sau reset password

Reset Password khác Change Password vì người thực hiện không chứng minh bằng password hiện tại.

Khuyến nghị security policy mạnh hơn:

- revoke/logout các session đang tồn tại của account sau reset thành công;
- yêu cầu đăng nhập lại bằng mật khẩu mới;
- nếu session architecture hiện tại chưa hỗ trợ revoke theo user thì research `session_version`, session store hoặc token revocation mechanism.

Không auto-login chỉ từ reset link nếu điều đó làm giảm security boundary.

Nếu team chọn auto-login sau reset thì phải có security review riêng và giải thích lý do.

---

## 13. OAuth-only account

Flama có/đang có kế hoạch Google Login nên phải xử lý account không có local password.

Không được leak qua forgot-password response rằng email thuộc OAuth account.

Backend nội bộ cần xác định policy:

### Case A — account có local password

Gửi reset email bình thường.

### Case B — OAuth-only và chưa có password

Research một trong các hướng:

- không tạo reset token; response public vẫn generic;
- hoặc gửi email hướng dẫn đăng nhập bằng provider nếu product muốn hỗ trợ, nhưng không được biến endpoint thành account enumeration.

Flow `Set Password` cho OAuth-only account nên được thiết kế độc lập nếu cần.

---

## 14. Rate limiting / abuse prevention

Forgot password endpoint dễ bị dùng để spam email và dò account.

Cần rate limit đa lớp, không chỉ một counter theo email:

- theo IP;
- theo normalized email/account nội bộ;
- global abuse threshold nếu cần;
- resend cooldown;
- giới hạn số active token.

Reuse login rate-limit infrastructure hiện tại nếu phù hợp.

Không khóa vĩnh viễn chức năng reset chỉ vì attacker spam vào email của nạn nhân.

Có thể thêm CAPTCHA/challenge về sau nếu abuse thực tế cao; không bắt buộc phase đầu nếu rate limit đủ.

---

## 15. Không đồng bộ gửi mail trong critical HTTP path nếu provider chậm

Request reset không nên treo lâu chỉ vì SMTP/provider phản hồi chậm.

Sau khi transactional email infrastructure sẵn sàng, ưu tiên:

```text
request reset
   ↓
create token transaction
   ↓
enqueue mail job
   ↓
return generic success
   ↓
worker sends email
```

Nếu Flama chưa có job queue production, email service phải ít nhất có timeout/retry rõ ràng và task infrastructure phải ghi dependency.

Không retry vô hạn.

---

## 16. Email nội dung reset password

Cần cả HTML + plain text fallback.

Nội dung tối thiểu:

- Flama branding;
- nói rằng có yêu cầu đặt lại mật khẩu;
- CTA `Đặt lại mật khẩu`;
- thời gian hết hạn;
- link fallback dạng text nếu button không hoạt động;
- cảnh báo nếu user không yêu cầu thì có thể bỏ qua;
- support/security contact phù hợp.

Không bao gồm:

- password hiện tại;
- password mới;
- password hash;
- dữ liệu profile không cần thiết.

Email phải render tốt trên mobile và các mail client phổ biến.

---

## 17. Email sau khi reset thành công

Sau reset thành công nên gửi một **security notification** riêng:

```text
Mật khẩu Flama của bạn vừa được đặt lại.
```

Không chứa credential.

Nội dung nên hướng dẫn user liên hệ support nếu họ không thực hiện thao tác này.

Notification này không dùng cùng reset token/link cũ.

Nếu email notification thất bại thì password reset đã commit không được rollback chỉ vì mail gửi lỗi.

---

## 18. Security event / audit

Ghi các event phù hợp, ví dụ:

```text
PASSWORD_RESET_REQUESTED
PASSWORD_RESET_EMAIL_QUEUED
PASSWORD_RESET_COMPLETED
PASSWORD_RESET_TOKEN_REJECTED
PASSWORD_RESET_RATE_LIMITED
```

Không ghi:

- raw reset token;
- password;
- password hash.

PII như IP/user-agent phải theo privacy/log retention policy của Flama.

---

## 19. Cleanup token cũ

Có strategy cleanup các row/token đã:

- expired;
- used;
- revoked.

Không cần xóa ngay lập tức nếu audit cần retention ngắn hạn, nhưng phải có policy rõ ràng để bảng không tăng vô hạn.

Có thể dùng scheduled job sau khi job infrastructure sẵn sàng.

---

## 20. Error handling

Frontend phải phân biệt các lỗi UX cần thiết mà không leak account state:

### Request page

Luôn generic success khi request syntactically hợp lệ, kể cả email không tồn tại.

### Reset page

Có thể hiển thị:

- link không hợp lệ hoặc đã hết hạn;
- link đã được sử dụng;
- password không đạt policy;
- confirm mismatch;
- rate limited;
- lỗi hệ thống.

Không trả stack trace, database error hoặc token hash ra frontend.

---

## 21. Dev / staging test flow

Không yêu cầu developer phải gửi email thật mỗi lần test.

Transactional email task cần hỗ trợ một adapter local/dev, ví dụ:

- console/file sink có redact phù hợp;
- Mailpit/MailHog-like local SMTP sink;
- fake email backend trong test.

Automated tests không gọi provider email thật.

Reset link trong integration test có thể được lấy từ fake outbox/test fixture, không parse production log.

---

## 22. Các file / subsystem cần inspect trước khi code

- `app/routes/auth.py`;
- `app/api/v1/identity/`;
- `app/services/auth_service.py`;
- `app/services/identity_api_service.py`;
- user/account model và password hash field;
- session management;
- CSRF middleware;
- login rate limit service;
- frontend auth routes/pages/hooks/schema;
- Register/Login hiện tại;
- Google Login integration;
- task Change Password;
- transactional email infrastructure.

Ưu tiên đặt canonical logic ở service/API layer thay vì duplicate giữa legacy routes và REST v1.

---

## 23. Tests

### Backend

Tối thiểu:

1. request reset cho local-password account → tạo token + queue mail;
2. email không tồn tại → response public vẫn giống success;
3. OAuth-only account → không leak trạng thái;
4. raw token không được lưu DB;
5. valid token reset thành công;
6. expired token bị reject;
7. used token bị reject;
8. revoked token bị reject;
9. malformed token bị reject;
10. token chỉ dùng được một lần kể cả concurrent request;
11. password policy được enforce;
12. confirm mismatch bị reject;
13. active reset token cũ được revoke theo policy;
14. session revoke policy được thực thi;
15. rate limit hoạt động;
16. không log raw password/token;
17. email send failure không làm leak account state;
18. reset success tạo security event;
19. reset success notification được enqueue nếu email system hoạt động.

### Frontend

- Forgot Password link từ Login;
- email validation;
- loading/disabled state;
- generic success state;
- resend UX;
- reset password form;
- confirm mismatch;
- invalid/expired token state;
- password policy errors;
- success → CTA về Login;
- không lưu token/password vào localStorage.

---

## Deliverables

- `/forgot-password` page.
- Forgot password API.
- Secure password reset token model/lifecycle.
- Reset email generation + enqueue thông qua shared EmailService.
- `/reset-password` page.
- Reset confirmation API.
- Password policy dùng chung.
- Rate limiting / abuse protection.
- Session revocation policy sau reset.
- Security/audit events.
- Reset-success security email.
- Backend/frontend/integration tests.
- Documentation cho token TTL, cleanup và operational troubleshooting.

---

## Acceptance criteria

- User có thể yêu cầu link reset từ Login bằng email.
- API không tiết lộ email/account có tồn tại hay không.
- Reset link chứa token random đủ mạnh, có expiry và chỉ dùng một lần.
- Database không lưu raw reset token.
- User phải nhập mật khẩu mới hai lần và hai giá trị phải khớp.
- Password mới dùng cùng policy với Register/Change Password.
- Token hết hạn/đã dùng/bị revoke không thể đổi password.
- Reset thành công vô hiệu hóa token và áp dụng session-security policy đã định nghĩa.
- Password/token không xuất hiện trong log, analytics hoặc error tracking.
- Email được gửi thông qua shared transactional email subsystem, không hard-code provider vào auth flow.
- Có đầy đủ test cho happy path, abuse path và security-sensitive cases.
