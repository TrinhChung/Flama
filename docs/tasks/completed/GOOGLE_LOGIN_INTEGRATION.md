# Task — Tích hợp đăng nhập bằng Google vào Flama

## Người thực hiện

**Tri**

## Mục tiêu

Nghiên cứu và triển khai khả năng **Sign in with Google** cho Flama theo hướng an toàn, có thể mở rộng thêm provider khác sau này, đồng thời không phá flow đăng nhập hiện tại và không gây regression cho OAuth/MCP Connector của ChatGPT/Claude.

Task này cần chia thành các phần nhỏ, test độc lập và merge vào `develop` theo từng checkpoint an toàn. Không làm trực tiếp trên `master`.

---

# 1. Bối cảnh hiện tại của Flama

Flama hiện đang dùng login truyền thống bằng email/password và Flask-Login.

Các file cần đọc trước:

- `app/routes/auth.py`
- `app/services/auth_service.py`
- `app/services/login_rate_limit_service.py`
- `app/utils/redirects.py`
- `models/user.py`
- `frontend/src/features/auth/pages/LoginPage.tsx`
- các migration liên quan tới `users`
- các test auth/login hiện tại

Một số điểm quan trọng trong implementation hiện tại:

- User được tìm theo `email` khi login.
- Session được tạo bằng `login_user(user)`.
- Login hỗ trợ `?next=...` và dùng `resolve_safe_next_url()` để quay lại flow trước đó.
- `User.email` đang unique và non-null.
- `User.username` đang unique và non-null.
- `User.password_hash` hiện đang **non-null**, nên không thể đơn giản tạo social-only user mà không quyết định cách xử lý schema/auth model.
- User disabled không được phép login.

Google login phải hòa vào session model hiện tại thay vì tạo một auth stack riêng.

---

# 2. Phân biệt hai vai trò OAuth trong Flama

Đây là điểm rất dễ nhầm khi triển khai.

Flama hiện đã đóng vai trò **OAuth Authorization Server** cho ChatGPT/Claude Remote MCP:

```text
ChatGPT / Claude
      ↓
Flama /oauth/authorize
      ↓
Flama cấp access token cho connector
```

Còn khi thêm Google Login, Flama sẽ đóng vai trò **OAuth/OIDC Client** của Google:

```text
Flama
  ↓
Google Authorization Server / OpenID Provider
  ↓
Google xác thực user
  ↓
Flama nhận identity của user
```

Hai flow này độc lập nhưng phải phối hợp được với nhau.

Kiến trúc mong muốn:

```text
Google
  ↓ OIDC login
Flama user session
  ↓
Flama application
  │
  └── có thể tiếp tục OAuth authorize cho ChatGPT/Claude
```

Không dùng Google access token làm MCP token và không để ChatGPT/Claude nhận Google credential.

---

# 3. Flow đăng nhập Google mong muốn

Flow cơ bản:

```text
User mở /login
      ↓
[Continue with Google]
      ↓
Flama tạo OAuth/OIDC authorization request
      ↓
redirect tới Google
      ↓
User chọn/đăng nhập Google account
      ↓
Google callback về Flama
      ↓
Flama validate:
- state
- authorization code
- issuer
- audience/client_id
- nonce nếu dùng
- token signature
- token expiry
- email_verified
      ↓
Flama xác định user nội bộ
      ↓
login_user(user)
      ↓
restore safe `next`
      ↓
Dashboard hoặc flow trước đó
```

Không coi email từ browser/client là trusted identity. Identity phải lấy từ token/response đã được xác thực từ Google.

---

# Task 1 — Nghiên cứu chuẩn Google Identity/OIDC hiện tại

Đọc tài liệu Google Identity mới nhất tại thời điểm triển khai và xác định chính xác flow phù hợp cho server-side Flask application.

Cần trả lời:

- nên dùng OAuth 2.0 Authorization Code + OpenID Connect hay Google Identity Services flow nào;
- endpoint discovery nào nên dùng;
- có cần PKCE cho web app này không;
- `state` bắt buộc xử lý thế nào;
- `nonce` nên dùng thế nào;
- cách verify ID Token chuẩn;
- claim nào được phép dùng làm stable identity;
- `sub` có phải identifier chính cần lưu hay không;
- cách xử lý `email` và `email_verified`;
- token nào thực sự cần lưu;
- có cần Google refresh token không nếu mục tiêu chỉ là login;
- revoke/logout phía Google có cần thiết không.

### Nguyên tắc ban đầu

Nếu chỉ dùng Google để **authenticate user**, ưu tiên không xin scope/API permission không cần thiết.

Mục tiêu tối thiểu thường chỉ cần identity cơ bản tương ứng OpenID/email/profile. Agent phải verify lại theo tài liệu Google hiện hành trước khi implement.

---

# Task 2 — Chọn mô hình identity trong database

Không nên vội thêm `google_id` trực tiếp vào `users` nếu Flama có khả năng hỗ trợ thêm GitHub, Apple, Microsoft hoặc provider khác sau này.

Nghiên cứu ít nhất hai phương án.

## Option A — Fields trực tiếp trên `users`

Ví dụ:

```text
google_sub
google_email
```

Ưu điểm:

- đơn giản;
- ít table.

Nhược điểm:

- khó mở rộng nhiều provider;
- coupling user model với Google.

## Option B — External identity table

Ví dụ logical model:

```text
UserIdentity
------------
id
user_id
provider        = google
provider_sub    = Google `sub`
provider_email
created_at
updated_at
```

Unique constraint nên cân nhắc:

```text
(provider, provider_sub) UNIQUE
```

Có thể bổ sung metadata tối thiểu nếu thực sự cần.

### Deliverable

Chọn A hoặc B và giải thích trade-off.

Khuyến nghị ban đầu: **ưu tiên Option B** nếu không làm tăng complexity quá mức, vì đây là boundary sạch hơn cho social login.

---

# Task 3 — Quyết định chiến lược `password_hash`

`users.password_hash` hiện đang non-null.

Phải quyết định rõ cách hỗ trợ user chỉ đăng nhập bằng Google.

Các phương án cần đánh giá:

### A. Cho phép `password_hash = NULL`

```text
local-password user
→ password_hash != NULL

Google-only user
→ password_hash = NULL
```

Khi login password:

```text
password_hash is NULL
→ không cho password login
```

### B. Tạo random unusable password cho social-only user

Không khuyến nghị nếu chỉ dùng để né migration/schema design.

### C. Bắt user tạo password ngay khi tạo tài khoản qua Google

UX kém và làm mất ý nghĩa social login.

### Deliverable

Chốt strategy, migration và regression test tương ứng.

---

# Task 4 — Quyết định account linking policy

Đây là phần security quan trọng nhất.

Các case phải định nghĩa rõ.

## Case A — Google identity đã link với Flama user

```text
(provider=google, sub=XYZ)
      ↓
user_id=123
      ↓
login user 123
```

Đây là flow chính.

## Case B — Chưa có identity, email chưa tồn tại trong Flama

Có thể tạo user mới nếu product policy cho phép Google signup.

Phải xác định:

- username tạo thế nào;
- conflict username xử lý thế nào;
- role mặc định;
- timezone mặc định;
- onboarding có cần hay không.

## Case C — Chưa có identity nhưng email đã tồn tại trong Flama

Không được xử lý mơ hồ.

Cần quyết định một trong các policy:

### Policy 1 — Auto-link verified email

Chỉ cân nhắc nếu:

```text
Google email_verified == true
AND normalized email exact match
```

Phải security-review kỹ trước khi chọn.

### Policy 2 — Explicit linking

Nếu email đã tồn tại:

```text
Google login
→ yêu cầu user login Flama hiện tại
→ xác nhận link Google account
```

An toàn hơn nhưng UX phức tạp hơn.

### Policy 3 — Chỉ cho link Google từ Account Settings

User phải login bằng password trước rồi mới link Google.

### Deliverable

Chọn policy rõ ràng và viết regression tests chống account takeover.

---

# Task 5 — Thiết kế backend routes/service

Không nhét toàn bộ Google logic vào `app/routes/auth.py`.

Cần đề xuất boundary rõ ràng, ví dụ:

```text
route/controller
      ↓
google_auth_service
      ↓
identity repository
      ↓
User/UserIdentity models
```

Logical routes có thể là:

```text
GET /auth/google
GET /auth/google/callback
```

Tên endpoint cuối cùng có thể thay đổi theo convention của repo.

Service nên chịu trách nhiệm tối thiểu:

- build authorization URL;
- generate/store transaction state;
- exchange authorization code;
- verify ID token/claims;
- resolve/link/create Flama user;
- trả user cho route;
- không tự redirect UI nếu có thể tránh coupling.

Route chịu trách nhiệm:

- HTTP request/response;
- login_user();
- redirect;
- flash/UI errors;
- safe `next` handling.

---

# Task 6 — Preserve `next` qua Google round trip

Flow login hiện tại dùng `?next=...`.

Google login tuyệt đối không được làm mất context này.

Ví dụ:

```text
/oauth/authorize?...connector params...
      ↓
Flama chưa login
      ↓
/login?next=<original oauth authorize URL>
      ↓
Continue with Google
      ↓
Google
      ↓
/auth/google/callback
      ↓
Flama login session
      ↓
original /oauth/authorize
      ↓
consent
```

Không đưa raw arbitrary URL từ callback thẳng vào redirect.

Phải tái sử dụng hoặc tương thích với `resolve_safe_next_url()` / safe redirect policy hiện có.

### Test bắt buộc

```text
Claude/ChatGPT connector
→ Flama login
→ Sign in with Google
→ quay lại OAuth authorize
→ consent
→ connector callback
```

Nếu flow này hỏng thì Google Login chưa đạt Definition of Done.

---

# Task 7 — State/nonce/session transaction storage

Không chỉ append `next` tùy tiện vào Google callback URL.

Thiết kế transaction context an toàn, có thể chứa tối thiểu:

```text
state
nonce
next
created_at / expiry
```

Có thể dùng signed server session nếu phù hợp với kiến trúc hiện tại.

Cần chống:

- login CSRF;
- replay;
- state fixation;
- arbitrary redirect injection;
- callback replay nếu có thể.

State phải random đủ mạnh và single-use theo flow hợp lý.

---

# Task 8 — Google Client configuration

Xác định config/environment variables cần có.

Ví dụ logical config:

```text
GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET
GOOGLE_OAUTH_REDIRECT_URI
```

Không hard-code secret trong source code.

Cần document:

- Google Cloud project setup;
- OAuth consent screen;
- authorized JavaScript origins nếu thực sự cần;
- authorized redirect URI;
- localhost/development callback;
- production callback;
- secret rotation.

Cần kiểm tra frontend/backend production đang khác origin như thế nào trước khi chốt callback domain.

---

# Task 9 — Frontend Login UI

Cập nhật `frontend/src/features/auth/pages/LoginPage.tsx` sau khi backend flow đã được thiết kế.

UX tối thiểu:

```text
Email
Password
[Đăng nhập]

──────── hoặc ────────

[Continue with Google]
```

Không tự implement form nhập Google credentials.

Button chỉ bắt đầu redirect tới backend Google auth endpoint.

Phải preserve query `next` khi user bắt đầu Google login.

Responsive/mobile phải không regression.

---

# Task 10 — Registration behavior

Phải quyết định Google login có đồng thời là Google signup hay không.

## Option A

```text
Google account chưa có Flama user
→ tạo account tự động
```

## Option B

```text
Google account chưa có Flama user
→ không tạo
→ yêu cầu register trước
```

Với sản phẩm consumer như Flama, Option A có UX tốt hơn nhưng phải làm rõ:

- username generation;
- duplicate username;
- default role;
- terms/privacy consent nếu cần;
- disabled/domain-block policy;
- audit event.

Không implement ngầm mà không document product behavior.

---

# Task 11 — Disabled/deleted users

Google authentication thành công không có nghĩa Flama phải cho login.

Nếu identity map tới user:

```text
is_disabled = true
```

thì login phải bị từ chối tương tự password login.

Không tự tạo user mới nếu provider identity trước đó map tới account đã bị disable/delete theo policy mà không có review rõ ràng.

---

# Task 12 — Logout semantics

Xác định rõ:

```text
Logout Flama
!=
Logout Google account toàn browser
```

Thông thường logout Flama chỉ cần xóa Flama session.

Không redirect user sang logout toàn bộ Google account trừ khi có requirement rõ ràng.

Document behavior để tránh hiểu sai.

---

# Task 13 — Security review

Kiểm tra tối thiểu:

- exact redirect URI registration;
- HTTPS production callback;
- state validation;
- nonce validation nếu dùng OIDC ID Token flow;
- issuer validation;
- audience/client ID validation;
- token signature verification;
- expiry validation;
- `sub` dùng làm stable provider identity;
- `email_verified` trước khi tin email;
- không trust profile fields từ browser;
- no open redirect qua `next`;
- no token/code/secret trong logs;
- client secret chỉ server-side;
- session fixation protection;
- disabled user handling;
- duplicate identity handling;
- race condition khi hai callback đồng thời tạo cùng user;
- database unique constraints chống duplicate link;
- account takeover risk khi auto-link email.

---

# Task 14 — Không lưu token nếu không cần

Nếu mục tiêu chỉ là **Sign in with Google**:

```text
Google authenticates identity
      ↓
Flama creates its own session
```

Không mặc định persist Google access token/refresh token vào DB.

Chỉ lưu token nếu có requirement thật sự gọi Google APIs sau này.

Nếu không cần Google APIs, giảm credential retention càng nhiều càng tốt.

---

# Task 15 — Tests backend

Phải thêm test ít nhất cho các case:

| Case | Expected |
|---|---|
| bắt đầu Google login | redirect đúng Google auth flow |
| invalid/missing state | reject |
| state expired/reused | reject theo design |
| provider token invalid | reject |
| wrong issuer | reject |
| wrong audience | reject |
| expired ID token | reject |
| email not verified | không auto-link/create theo policy |
| known Google `sub` | login đúng user |
| new Google user | create hoặc reject theo policy |
| existing same email | behavior đúng account-linking policy |
| disabled Flama user | reject |
| duplicate callback race | không tạo duplicate identity/user |
| malicious `next` external URL | không redirect ra ngoài |
| valid safe `next` | restore đúng |
| logout | Flama session bị clear |

Mock Google network boundary thay vì test phụ thuộc internet trong unit test.

---

# Task 16 — Regression với login password hiện tại

Google login không được phá:

- register bằng email/password;
- login bằng email/password;
- login rate limit;
- disabled account;
- logout;
- session loading;
- admin permissions;
- safe `next` redirect.

Đặc biệt nếu `password_hash` chuyển nullable, tất cả code gọi `check_password()` phải xử lý social-only account an toàn.

---

# Task 17 — Regression với ChatGPT/Claude MCP OAuth

Đây là cross-feature bắt buộc test.

### Password login path

```text
Connector
→ /oauth/authorize
→ /login
→ password login
→ authorize
→ consent
→ callback
```

### Google login path

```text
Connector
→ /oauth/authorize
→ /login
→ Google login
→ Google callback
→ /oauth/authorize
→ consent
→ connector callback
→ MCP access token
```

Hai path phải cho ra cùng một Flama `current_user` / user ID và không làm lẫn Google token với Flama MCP OAuth token.

---

# Task 18 — Migration strategy

Nếu schema thay đổi:

- tạo Alembic migration chuẩn;
- không thêm production schema patch vào app startup;
- migration phải chạy được trên DB hiện tại;
- existing password users không mất dữ liệu;
- unique/index constraints phải có tên rõ ràng;
- downgrade strategy phải được cân nhắc.

Nếu thêm `UserIdentity`, cần foreign key + index + unique constraint phù hợp.

---

# Task 19 — Observability / audit

Bổ sung log/audit event đủ để debug nhưng không leak credential.

Ví dụ event logic:

```text
google_login_started
google_login_success
google_login_failed
google_identity_linked
google_user_created
```

Không log:

```text
authorization code
access token
refresh token
ID token
client secret
```

Nếu Flama đã có audit infrastructure thì tái sử dụng thay vì tạo hệ thống riêng.

---

# Task 20 — Documentation

Sau khi implementation ổn định, bổ sung tài liệu:

- cách tạo Google OAuth/OIDC client;
- redirect URI dev/prod;
- env vars;
- local development;
- account linking behavior;
- login/signup behavior;
- logout behavior;
- troubleshooting callback mismatch;
- interaction với connector OAuth.

Không đưa real client secret vào docs/example commit.

---

# Phân chia implementation đề xuất

Không làm toàn bộ trong một branch lớn.

Ví dụ:

```text
develop
  ↓
feature/google-auth-model
  ↓ test + merge

develop
  ↓
feature/google-auth-backend
  ↓ test + merge

develop
  ↓
feature/google-login-ui
  ↓ test + merge

develop
  ↓
test/google-auth-regression
  ↓ test + merge

develop
  ↓
docs/google-login
```

Nếu model/backend không thể tách độc lập an toàn, có thể gộp phần bắt buộc nhưng branch vẫn phải có scope rõ ràng.

Không push trực tiếp vào `master`.

---

# Deliverable cuối

Khi hoàn thành phải ghi rõ:

## Architecture

```text
Google OIDC
   ↓
Google auth service
   ↓
External identity mapping
   ↓
Flama User
   ↓
Flask-Login session
```

## Account policy

- Google login có tạo account mới không?
- existing email được auto-link hay explicit link?
- social-only account có password_hash thế nào?
- user có thể thêm password sau này không?
- unlink Google khi account không còn password xử lý thế nào?

## Security decisions

- state
- nonce
- PKCE
- ID token validation
- email verification
- redirect handling

## Regression evidence

- password login;
- Google login;
- disabled user;
- registration;
- ChatGPT OAuth connector;
- Claude OAuth connector.

---

# Definition of Done

- [x] Đã đọc auth implementation hiện tại trên `develop`.
- [x] Đã đọc Google Identity/OIDC docs mới nhất.
- [x] Đã chọn data model cho external identity.
- [x] Đã quyết định strategy cho nullable/non-null `password_hash`.
- [x] Đã chốt account-linking policy.
- [x] Đã implement state/nonce/token validation đúng chuẩn.
- [x] Không lưu Google token nếu không có requirement.
- [x] Google login tạo được Flama session đúng user.
- [x] Safe `next` được preserve qua Google round trip.
- [x] Password login không regression.
- [x] Disabled user không thể bypass bằng Google.
- [x] ChatGPT/Claude OAuth authorize vẫn chạy sau Google login.
- [x] Backend tests xanh.
- [x] Frontend tests/build xanh.
- [x] Migration chạy sạch trên DB hiện tại.
- [x] Không leak secret/token vào logs/docs.
- [x] Documentation được cập nhật.

---

## Nguyên tắc triển khai

Ưu tiên **identity mapping sạch + session Flama hiện tại**, không biến Google login thành một hệ thống auth song song.

Google chỉ xác thực danh tính. Sau callback thành công, mọi authorization bên trong Flama vẫn phải dựa trên Flama `User`, role, permission và session hiện có.
