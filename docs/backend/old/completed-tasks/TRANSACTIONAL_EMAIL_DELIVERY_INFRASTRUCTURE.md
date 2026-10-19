# Task: Transactional Email Infrastructure cho Flama

> **Trạng thái:** [x] ĐÃ HOÀN THÀNH (Completed)  
> **Ngày hoàn thành:** 2026-08-28  
> **Target branch:** `develop`  

## Mục tiêu

Thiết kế một **hạ tầng gửi email transactional dùng chung** cho Flama thay vì mỗi chức năng tự kết nối SMTP hoặc tự gọi provider riêng.

Subsystem này trước mắt phục vụ:

- Forgot Password / Reset Password;
- thông báo password changed/reset;
- email verification khi đăng ký;
- thông báo security/account;
- payment/order notification;
- support/moderation notification;
- các email hệ thống khác trong tương lai.

Task liên quan trực tiếp:

- `docs/tasks/FORGOT_PASSWORD_EMAIL_RESET_FLOW.md`
- `docs/tasks/CHANGE_PASSWORD_CURRENT_PASSWORD_CONFIRMATION.md`

---

## 1. Nguyên tắc kiến trúc

Business service không được biết chi tiết SMTP/API provider.

Ví dụ auth service không làm:

```text
smtp.login(...)
smtp.sendmail(...)
```

hoặc gọi SDK provider trực tiếp.

Thay vào đó tạo abstraction kiểu:

```text
EmailService
  └─ send(message/template + recipient + variables)

EmailProvider
  ├─ LocalDevEmailProvider
  ├─ SMTPEmailProvider
  └─ ProductionTransactionalProvider
```

Tên class/module cụ thể phải bám convention codebase hiện tại, không bắt buộc đúng tên trên.

Mục tiêu là sau này đổi provider mà không sửa Forgot Password, Payment hoặc Notification business logic.

---

## 2. Research và lựa chọn provider production

Trước khi code production adapter cần so sánh ít nhất các nhóm sau:

### A. Managed transactional email API

Ví dụ để research tại thời điểm triển khai:

- AWS SES;
- Postmark;
- Resend;
- SendGrid;
- Mailgun;
- provider tương đương phù hợp region/cost của Flama.

### B. SMTP relay

Có thể dùng SMTP interface của một provider transactional nếu phù hợp.

### Không nên dùng làm production architecture

- Gmail cá nhân;
- password của mailbox cá nhân;
- SMTP relay không có deliverability/monitoring rõ ràng;
- credential hard-code trong repo.

### Tiêu chí đánh giá

- chi phí theo volume;
- free/dev allowance nếu có;
- domain verification;
- SPF/DKIM support;
- DMARC compatibility;
- bounce/complaint webhook;
- API/SMTP reliability;
- retry semantics;
- rate limit;
- delivery event logging;
- support cho region hiện tại;
- data/privacy requirements;
- SDK quality cho Python;
- vendor lock-in;
- khả năng migrate provider;
- support HTML + plain text;
- template API của provider có cần dùng hay nên giữ template trong Flama.

Không chọn provider chỉ vì setup nhanh nhất.

Deliverable của bước research phải ghi rõ provider được chọn và lý do.

---

## 3. Khuyến nghị tách template khỏi provider

Ưu tiên để Flama sở hữu email template/source thay vì đặt toàn bộ business template trong dashboard của provider.

Lợi ích:

- version control trong Git;
- review được thay đổi nội dung;
- test được;
- provider-independent;
- staging/dev render giống production;
- hỗ trợ localization về sau.

Provider chỉ chịu trách nhiệm delivery.

Có thể dùng template engine hiện có nếu an toàn/phù hợp; không tạo thêm template engine nặng nếu không cần.

---

## 4. Email message contract

Xây dựng contract chung, ví dụ về mặt dữ liệu:

```text
TransactionalEmail
- template_key
- recipient
- variables
- locale
- category
- correlation_id
- metadata allowlist
```

Renderer tạo:

```text
subject
html_body
text_body
```

Sau đó provider gửi message đã render.

Không cho arbitrary user input trở thành header như `From`, `Reply-To`, subject hoặc raw HTML mà không validation/sanitization phù hợp.

---

## 5. Email categories

Định nghĩa category để theo dõi và policy khác nhau, ví dụ:

```text
security.password_reset
security.password_changed
identity.email_verification
billing.payment_receipt
billing.payment_issue
community.moderation
system.notification
```

Không dùng một string tùy ý ở mọi nơi.

Category giúp:

- metrics;
- rate limiting;
- retry policy;
- debugging;
- suppression rules;
- preference system trong tương lai.

Security-critical email không nên bị tắt chỉ vì user unsubscribe marketing.

Transactional email phải được tách khỏi marketing email.

---

## 6. Domain gửi mail

Không dùng địa chỉ cá nhân làm sender production.

Research domain/subdomain phù hợp, ví dụ về mặt kiến trúc:

```text
flama domain
  └─ transactional mail subdomain
```

Có thể dùng:

```text
no-reply@<verified-domain>
support@<verified-domain>
security@<verified-domain>
```

Tên cuối cùng phụ thuộc domain chính thức của Flama.

Cần xác định:

- From name: `Flama`;
- From address;
- Reply-To policy;
- support address;
- envelope sender / return-path nếu provider hỗ trợ.

Không để user-controlled input inject mail header.

---

## 7. DNS / deliverability setup

Kế hoạch production phải bao gồm DNS, không dừng ở việc có API key.

Tối thiểu research/configure:

### SPF

Cho phép provider đã chọn gửi thay domain/subdomain của Flama.

### DKIM

Bật domain signing bằng record do provider cấp.

### DMARC

Thiết lập policy phù hợp theo từng phase.

Ban đầu có thể bắt đầu ở monitoring policy nếu cần để quan sát, sau đó tăng enforcement khi hệ thống ổn định.

### Return-Path / MAIL FROM

Nếu provider hỗ trợ custom MAIL FROM/return-path thì research cấu hình phù hợp để alignment tốt hơn.

### DNS verification checklist

Không đánh dấu production-ready cho đến khi provider xác nhận domain/DKIM thành công.

Ghi runbook cách kiểm tra DNS và troubleshooting.

---

## 8. Secrets / environment configuration

Provider credential chỉ được lấy từ secret/environment config.

Ví dụ các config có thể cần:

```text
EMAIL_PROVIDER
EMAIL_FROM_ADDRESS
EMAIL_FROM_NAME
EMAIL_REPLY_TO
PUBLIC_APP_URL
EMAIL_API_KEY / EMAIL_SMTP_* tương ứng provider
EMAIL_ENABLED
EMAIL_ENVIRONMENT
```

Tên final phải bám config convention của Flama.

Không commit:

- API key;
- SMTP password;
- provider secret;
- production webhook signing secret.

Dev/staging/prod phải có credential riêng.

Không dùng production credential trên local developer machine nếu không cần.

---

## 9. Environment safety

Đây là yêu cầu quan trọng để staging/local không gửi nhầm mail cho user thật.

Thiết kế environment policy:

### Test

Dùng fake provider/in-memory outbox.

### Local development

Dùng local mail sink hoặc dev adapter.

Ví dụ research:

- Mailpit;
- MailHog-like SMTP sink;
- local fake outbox.

### Staging

Có thể dùng sandbox/provider test mode hoặc recipient allowlist.

### Production

Chỉ production provider + verified domain.

Cần có guard để staging không thể vô tình gửi đến arbitrary production recipient nếu cấu hình sai.

Ví dụ:

```text
EMAIL_RECIPIENT_ALLOWLIST
EMAIL_REDIRECT_ALL_TO
```

cho non-production, tùy architecture phù hợp.

---

## 10. Queue / asynchronous delivery

Không buộc HTTP request phải chờ provider gửi mail xong nếu không cần.

Target architecture:

```text
business transaction
      ↓
create email/outbox job
      ↓
commit business state
      ↓
worker sends email
      ↓
record delivery result
```

Cần research job infrastructure hiện tại của Flama.

Nếu Redis/job worker đang được triển khai cho các pipeline khác thì ưu tiên dùng chung abstraction đó thay vì tạo queue thứ hai riêng cho email.

Không được giả định Redis worker đã tồn tại nếu codebase chưa có.

Nếu phase đầu chưa có async queue, provider adapter cần timeout chặt và kiến trúc phải cho phép migrate sang queue mà không đổi business API.

---

## 11. Outbox / reliability

Research có cần **database outbox pattern** hay không.

Vấn đề cần giải quyết:

```text
password reset token commit thành công
           ↓
process crash trước khi enqueue mail
           ↓
user không bao giờ nhận email
```

Một hướng:

```text
DB transaction
  ├─ password reset state
  └─ email_outbox row
          ↓
worker poll/enqueue
          ↓
send provider
```

Không bắt buộc áp dụng outbox đầy đủ ngay nếu hệ thống hiện tại nhỏ, nhưng task phải đánh giá failure window và chọn cơ chế rõ ràng.

Security-critical emails như password reset cần reliability tốt hơn email thông báo thông thường.

---

## 12. Email delivery state

Nếu lưu email job/outbox, status có thể gồm:

```text
PENDING
PROCESSING
SENT
DELIVERED (nếu provider webhook hỗ trợ)
FAILED
BOUNCED
COMPLAINED
SUPPRESSED
```

Không nhất thiết mọi provider cung cấp toàn bộ lifecycle.

Tách:

- `sent`: provider chấp nhận message;
- `delivered`: provider xác nhận delivery;

không coi hai khái niệm này là một.

---

## 13. Retry policy

Không retry tất cả lỗi giống nhau.

Phân loại:

### Transient

Ví dụ timeout, 5xx provider, temporary connection issue.

→ retry exponential backoff + max attempts.

### Permanent

Ví dụ invalid recipient syntax, rejected domain, template validation bug, invalid credential.

→ không retry vô hạn.

Cần dead-letter/failed state hoặc admin/monitoring alert cho lỗi dài hạn.

Retry phải idempotent ở mức phù hợp và hạn chế gửi duplicate email.

---

## 14. Deduplication / idempotency

Một business event không nên vô tình gửi 5 email vì request retry.

Research correlation/idempotency key, ví dụ:

```text
email event key = event_type + business_entity_id + version
```

Password reset có nuance riêng: user chủ động request nhiều lần có thể hợp lệ, nên dedupe phải theo request/event id chứ không chặn tất cả email cùng category.

Không dedupe bằng recipient + subject đơn giản.

---

## 15. Bounce / complaint handling

Nếu provider hỗ trợ webhook/event callback thì triển khai hoặc lên phase rõ ràng cho:

- delivered;
- hard bounce;
- soft bounce;
- complaint/spam;
- rejected;
- deferred.

Webhook phải:

- verify signature/provider authenticity;
- idempotent;
- không tin payload tùy ý;
- log correlation id/provider message id;
- không leak credential.

### Suppression

Hard bounce/complaint có thể cần suppression để tránh tiếp tục gửi vô hạn tới địa chỉ không hợp lệ.

Security flow phải cân nhắc kỹ nếu suppress email khiến user không thể reset password; cần support recovery path.

---

## 16. Email address verification

Hạ tầng này phải reusable cho task email verification sau đăng ký.

Không trộn:

```text
email_verified
```

với:

```text
provider delivered an email
```

`delivered` không có nghĩa user đã xác minh ownership.

Email verification cần token riêng và business flow riêng.

---

## 17. HTML email security

Email template phải được control bởi Flama.

Không render raw arbitrary HTML từ user-generated profile/deck/review vào email nếu chưa sanitize.

Escape variables theo context.

Links phải dùng canonical `PUBLIC_APP_URL` và internal route builder, không ghép URL từ untrusted Host header.

Không nhúng secret/token vào tracking pixel hoặc third-party analytics.

---

## 18. Plain text fallback

Mọi security-critical email phải có plain-text version bên cạnh HTML.

Ví dụ password reset:

```text
Đặt lại mật khẩu Flama

Mở liên kết sau để đặt lại mật khẩu:
https://...

Liên kết sẽ hết hạn sau ...
```

Không dựa hoàn toàn vào button HTML.

---

## 19. Localization

Thiết kế template để sau này có thể hỗ trợ locale:

```text
vi
ja
en
...
```

Không cần dịch tất cả ngay trong task này nếu product chưa có requirement, nhưng contract nên có `locale` hoặc fallback strategy.

Fallback phải deterministic, ví dụ default locale của product.

Không để thiếu translation làm worker crash vô hạn.

---

## 20. Template structure

Đề xuất cấu trúc version-control, ví dụ:

```text
app/email/templates/
  base/
  password_reset/
    subject.*
    html.*
    text.*
  password_changed/
  email_verification/
```

Không bắt buộc đúng folder trên; chọn theo architecture hiện tại.

Cần base layout chung:

- Flama logo/brand text;
- body container;
- CTA style;
- footer;
- support info.

Security mail cần đơn giản, tránh layout quá nặng.

---

## 21. Preview / development tooling

Developer cần cách xem email trước khi gửi production.

Research một trong các hướng:

- local preview route chỉ bật ở dev;
- CLI render template ra HTML;
- Storybook-like preview nếu hợp stack;
- local mail sink UI.

Không tạo public unauthenticated production endpoint cho phép render/send arbitrary email template.

---

## 22. Monitoring / metrics

Theo dõi tối thiểu:

```text
email_jobs_created_total{category}
email_send_success_total{category,provider}
email_send_failure_total{category,provider,error_class}
email_retry_total
email_bounce_total
email_complaint_total
email_queue_age_seconds
email_delivery_latency
```

Tên metric final theo monitoring convention hiện tại.

Không gắn raw recipient email làm metric label vì cardinality + privacy.

---

## 23. Logging

Log structured metadata phù hợp:

- internal email job id;
- category;
- provider;
- provider message id;
- attempt number;
- status;
- correlation/business event id.

Không log:

- email body đầy đủ nếu chứa token;
- reset token;
- verification token;
- API key;
- SMTP credential.

Recipient email nếu cần troubleshooting phải theo PII logging policy; ưu tiên user id hoặc masked/hash representation khi đủ dùng.

---

## 24. Admin / operational visibility

Research một màn admin hoặc operational view tối thiểu cho email jobs nếu volume tăng.

Có thể hiển thị:

- category;
- recipient masked;
- status;
- created/sent timestamps;
- attempts;
- provider error class;
- correlation entity;
- resend/retry action có permission nếu thực sự cần.

Không hiển thị raw token/password trong admin.

Không cho admin chỉnh arbitrary HTML rồi gửi mail dưới danh nghĩa Flama trong phase này.

---

## 25. Provider webhooks

Nếu dùng webhook thì endpoint cần:

- route riêng;
- signature verification;
- timestamp/replay protection nếu provider hỗ trợ;
- idempotency dựa provider event id;
- strict parsing;
- rate limit/WAF strategy phù hợp;
- observability;
- raw payload retention chỉ khi thật sự cần và theo privacy policy.

Không dùng CSRF user-session cho provider webhook; xác thực theo provider signature.

---

## 26. Failure behavior của business flow

Phải định nghĩa rõ từng loại email có criticality khác nhau.

### Password reset request

Nếu token đã tạo nhưng email queue fail, cần reliability/recovery rõ ràng; user-facing response vẫn không được leak account existence.

### Password changed notification

Password change thành công không được rollback chỉ vì notification email failed.

### Payment receipt

Payment state không phụ thuộc việc email gửi thành công.

Business transaction và notification delivery phải được decouple đúng mức.

---

## 27. Security review

Trước production cần review:

- mail header injection;
- template injection;
- secret management;
- reset/verification token leakage;
- logging leakage;
- open redirect trong email link;
- Host-header poisoning;
- provider webhook spoofing;
- account enumeration interaction;
- email flooding/spam abuse;
- staging gửi nhầm user production;
- compromised provider API key rotation.

---

## 28. Credential rotation / incident response

Runbook cần có:

```text
provider key bị lộ
   ↓
revoke key
   ↓
create replacement
   ↓
update secret store
   ↓
restart/reload service
   ↓
verify delivery
   ↓
review provider logs
```

Không yêu cầu code deploy chỉ để thay credential nếu deployment architecture cho phép secret rotation độc lập.

---

## 29. Test strategy

### Unit tests

- email template render;
- HTML escaping;
- required variable validation;
- provider adapter mapping;
- retry classification;
- idempotency/dedupe;
- environment recipient guard.

### Integration tests

- fake/local SMTP/provider;
- queue/outbox lifecycle;
- worker success/failure/retry;
- webhook signature verification;
- bounce event idempotency.

### E2E

Forgot Password:

```text
request reset
→ fake inbox receives email
→ click reset link
→ set password
→ old password invalid/new password valid
```

Automated CI không gửi email thật ra Internet.

---

## 30. Rollout plan

### Phase 1 — Investigation

- inspect deployment/config stack;
- inspect Redis/job infrastructure hiện tại;
- estimate email volume;
- compare providers;
- chọn production provider;
- chọn sender domain/subdomain;
- document cost/security/deliverability decision.

### Phase 2 — Core abstraction

- EmailService contract;
- template renderer;
- local/fake provider;
- config/secrets interface;
- unit tests.

### Phase 3 — Production provider

- provider adapter;
- verified sender domain;
- SPF/DKIM;
- DMARC plan;
- staging test;
- production secret setup.

### Phase 4 — Queue/reliability

- async queue/worker nếu infrastructure hỗ trợ;
- retry/backoff;
- outbox assessment/implementation;
- metrics/logging.

### Phase 5 — Delivery events

- webhook verification;
- delivered/bounce/complaint state;
- suppression policy;
- alerts/dashboard.

### Phase 6 — Integrations

- Forgot Password;
- Email Verification;
- password/security notifications;
- payment/order emails;
- các feature khác.

---

## Deliverables

- Provider research + ADR/decision note.
- Shared `EmailService`/provider abstraction.
- Local/test email backend.
- Production transactional email adapter.
- Environment/secret configuration.
- Version-controlled HTML + text templates.
- Sender domain setup guide.
- SPF/DKIM setup.
- DMARC rollout plan.
- Queue/retry strategy.
- Outbox reliability decision.
- Delivery/bounce/complaint handling plan.
- Structured logs + metrics.
- Security review checklist.
- Credential rotation/runbook.
- Tests.

---

## Acceptance criteria

- Business modules không gọi SMTP/provider SDK trực tiếp.
- Có một shared email abstraction dùng được cho auth, payment và notification.
- Local/test không cần credential production và không gửi email thật ra ngoài.
- Production credential không nằm trong Git.
- Sender domain được verify và DKIM hoạt động trước production rollout.
- SPF/DMARC strategy được document rõ.
- Email security-critical có cả HTML và plain-text fallback.
- Reset/verification token không bị log trong email delivery logs.
- Có timeout/retry policy và không retry vô hạn.
- Staging có guard chống gửi nhầm user production.
- Hệ thống có observability đủ để phân biệt queued/sent/failed/bounced khi provider hỗ trợ.
- Provider có thể được thay đổi mà không phải rewrite Forgot Password/business logic.
- CI tests dùng fake/local provider, không gọi email provider production.
