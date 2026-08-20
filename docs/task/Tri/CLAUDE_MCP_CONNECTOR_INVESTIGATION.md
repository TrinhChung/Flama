# Task — Điều tra Claude Custom Connector ↔ Flama Remote MCP

## Người thực hiện

**Tri**

## Mục tiêu

Điều tra đầy đủ khả năng kết nối **Claude Custom Connector** với **Flama Remote MCP** qua OAuth, xác định flow nào chạy được với kiến trúc Flama hiện tại, điểm nào còn thiếu, và đề xuất hướng bổ sung tài liệu hoặc code nếu thật sự cần thiết.

Task này ưu tiên **điều tra + test thực tế + kết luận rõ ràng** trước. Không vội sửa kiến trúc OAuth/MCP nếu chưa xác định chính xác yêu cầu của Claude.

---

## Bối cảnh Flama hiện tại

Flama đã có Remote MCP public endpoint và OAuth 2.1/PKCE để AI client truy cập dữ liệu thay mặt đúng user Flama.

Các phần liên quan nên đọc trước:

- `app/routes/mcp.py`
- `app/connect/mcp.py`
- `app/routes/oauth.py`
- `app/services/oauth_service.py`
- `app/services/mcp_auth_service.py`
- `app/services/mcp_access_token_service.py`
- `models/oauth_client.py`
- `models/oauth_authorization_code.py`
- `models/mcp_access_token.py`
- `frontend/src/features/settings/components/McpOAuthTab.tsx`
- `frontend/src/features/settings/components/McpGuideTab.tsx`
- `tests/test_oauth_mcp.py`

Production MCP URL đang được hướng tới:

```text
https://be-flama.stmtp.com/api/mcp
```

OAuth discovery/endpoints hiện có:

```text
/.well-known/oauth-protected-resource
/.well-known/oauth-authorization-server
/.well-known/openid-configuration
/oauth/authorize
/oauth/token
/oauth/revoke
/oauth/userinfo
```

Flama hiện hỗ trợ:

- Authorization Code flow
- PKCE `S256`
- access token
- refresh token
- token revocation
- OAuth access token map về Flama user
- scope cho MCP tools
- pre-registered OAuth clients với một hoặc nhiều redirect URI

Access token hiện có lifetime khoảng 24 giờ và refresh token khoảng 90 ngày. Claude có hỗ trợ token expiration + refresh, nên cần xác nhận flow refresh của Flama tương thích thực tế.

---

## Thông tin đã điều tra sơ bộ về Claude

Claude hiện có **Custom Connector dùng Remote MCP**. Connector được Claude/Anthropic gọi từ cloud, không phải từ localhost của máy người dùng.

Tài liệu Anthropic hiện tại:

- https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp
- https://support.claude.com/en/articles/11503834-build-custom-connectors-via-remote-mcp-servers

Claude Custom Connector hiện cho cấu hình Remote MCP URL và authentication.

Trong UI hiện tại có ba hướng OAuth client đáng điều tra:

1. **Anthropic-hosted client metadata**
2. **Client IDなし / tự động đăng ký** — Dynamic Client Registration (DCR)
3. **Use your own OAuth client** — dùng Client ID/Client Secret đã đăng ký sẵn trên Flama

### Callback URL của Claude

Anthropic hiện công bố callback chính:

```text
https://claude.ai/api/mcp/auth_callback
```

và cảnh báo callback có thể chuyển sang:

```text
https://claude.com/api/mcp/auth_callback
```

Nếu server whitelist redirect URI thì nên đăng ký **cả hai URL trong cùng một OAuth client**.

Ví dụ pre-registered client để test:

```text
Client name:
Claude

Client ID:
claude_flama

Client Secret:
<random strong secret>

Redirect URIs:
https://claude.ai/api/mcp/auth_callback
https://claude.com/api/mcp/auth_callback
```

Không dùng secret mẫu kiểu `flama_secret_2026` trong production.

---

## Flow OAuth kỳ vọng

Claude không biết username/password Flama và cũng không nên nhận password của user.

Flow kỳ vọng:

```text
User add/connect Claude Custom Connector
        ↓
Claude truy cập Flama Remote MCP
        ↓
OAuth discovery
        ↓
/oauth/authorize
        ↓
Flama kiểm tra browser session
        ↓
Nếu chưa login:
Flama redirect user → /login?next=<authorize URL>
        ↓
User login bằng tài khoản Flama
        ↓
quay lại /oauth/authorize
        ↓
Flama OAuth consent
        ↓
User approve scopes
        ↓
Flama tạo authorization code gắn với current Flama user
        ↓
redirect về Claude callback
?code=...&state=...
        ↓
Claude POST /oauth/token
+ authorization code
+ PKCE code_verifier
+ client credentials nếu là confidential client
        ↓
Flama trả access_token + refresh_token
        ↓
Claude gọi /api/mcp
Authorization: Bearer <access_token>
        ↓
Flama map token → user_id + scopes
        ↓
MCP tool chạy đúng context user
```

Điểm cần nhớ:

- `client_id` định danh OAuth client/connector, **không định danh user**.
- `redirect_uri` chỉ xác định nơi browser quay lại sau authorize, **không định danh user**.
- `state` dùng cho OAuth transaction/state validation.
- OAuth access token mới là credential dùng để xác định user khi Claude gọi MCP.

Nhiều user Flama có thể dùng cùng `claude_flama` client và cùng callback URL nhưng nhận token riêng gắn với từng user.

---

## Nhận định sơ bộ về compatibility hiện tại

### 1. Own OAuth Client — có khả năng phù hợp nhất ngay bây giờ

Flama hiện có khả năng admin đăng ký OAuth client với:

- client ID
- client secret
- redirect URIs

và token endpoint hỗ trợ confidential client.

Do đó hướng đầu tiên cần test end-to-end là:

```text
Claude Authentication:
Always required

OAuth Client:
Use your own OAuth client

Client ID:
claude_flama

Client Secret:
<secret>
```

Đây là candidate có khả năng chạy với ít hoặc không cần sửa backend.

### 2. DCR — hiện chưa thấy Flama implement

Claude hỗ trợ Dynamic Client Registration.

Hiện Flama chưa thấy có:

```text
registration_endpoint
/oauth/register
```

Authorization server metadata cũng chưa thấy advertise `registration_endpoint`.

Vì vậy option **Client IDなし / tự động đăng ký** nhiều khả năng chưa hoạt động với Flama hiện tại.

Cần verify bằng tài liệu MCP/OAuth mới nhất và test thực tế trước khi kết luận cuối cùng.

### 3. Anthropic-hosted client metadata — cần nghiên cứu kỹ

UI Claude hiện khuyến nghị lựa chọn dùng **Anthropic-hosted client metadata**.

Flama hiện chưa advertise metadata capability tương ứng và validation `client_id` hiện thiên về ID dạng text đã pre-register, không phải URL client ID.

Cần xác định chính xác:

- Claude đang dùng chuẩn nào cho lựa chọn này;
- có phải Client ID Metadata Document (CIMD) theo MCP OAuth mới hay không;
- authorization server phải advertise field/capability nào;
- client ID có phải URL metadata hay không;
- validation redirect URI/client metadata cần làm thế nào;
- security requirement khi server fetch metadata từ URL bên ngoài;
- cache, timeout, SSRF protection, redirect handling nếu Flama phải fetch metadata.

Không implement trước khi đọc đúng spec hiện tại.

---

# Tasks điều tra

## Task 1 — Xác nhận Claude Custom Connector flow hiện tại

Dùng Claude UI hiện tại và tài liệu Anthropic mới nhất để ghi lại chính xác:

- nơi add Custom Connector;
- Remote MCP URL được nhập ở đâu;
- các mode Authentication;
- ba OAuth client mode hiện có;
- field nào xuất hiện khi chọn từng mode;
- callback URL thực tế Claude sử dụng;
- có yêu cầu scope field hay không;
- có yêu cầu Client Secret hay Client ID riêng hay không.

Nếu UI khác giữa Pro/Max và Team/Enterprise thì ghi rõ.

### Evidence cần lưu

- screenshot hoặc mô tả field;
- link tài liệu Anthropic;
- timestamp/ngày test;
- loại tài khoản Claude dùng để test.

---

## Task 2 — Test `Use your own OAuth client` end-to-end

Đây là flow ưu tiên cao nhất.

Tạo một OAuth client Claude trong Flama với hai redirect URI:

```text
https://claude.ai/api/mcp/auth_callback
https://claude.com/api/mcp/auth_callback
```

Sau đó cấu hình Claude:

```text
Remote MCP URL:
https://be-flama.stmtp.com/api/mcp

Authentication:
Always required

OAuth client:
Use your own OAuth client
```

Ghi lại toàn bộ sequence:

```text
Claude
→ MCP
→ discovery
→ /oauth/authorize
→ Flama login
→ consent
→ Claude callback
→ /oauth/token
→ Bearer token
→ tools/list
→ tools/call
```

### Phải xác nhận

- Flama login page có mở đúng không;
- `next` có giữ đầy đủ authorize request không;
- login xong có quay lại OAuth authorize không;
- consent page có render đúng không;
- PKCE có pass không;
- redirect URI có match exact không;
- Claude có đổi code lấy token thành công không;
- Claude có giữ refresh token không;
- MCP request sau đó có Bearer token không;
- `mcp_auth_service` map đúng user không;
- scope enforcement có hoạt động không;
- tool read/write test có chạy đúng user không.

---

## Task 3 — Xác nhận OAuth discovery mà Claude thực sự gọi

Flama hiện có RFC 9728 protected-resource metadata và authorization-server metadata.

Cần inspect request log hoặc proxy log để xác nhận Claude gọi chính xác endpoint nào và theo thứ tự nào.

Đặc biệt kiểm tra:

```text
/.well-known/oauth-protected-resource
/.well-known/oauth-authorization-server
/.well-known/openid-configuration
```

Kiểm tra `WWW-Authenticate` response khi MCP cần auth.

Trong `app/connect/mcp.py`, 401 hiện set dạng:

```text
Bearer ... resource_metadata=".../.well-known/oauth-protected-resource"
```

Xác nhận Claude hiểu challenge này đúng spec hiện tại.

---

## Task 4 — Kiểm tra endpoint `/api/mcp` và auth timing

Hiện một số MCP methods như `initialize` và `tools/list` có thể chạy khi chưa có auth, trong khi `tools/call` yêu cầu authentication/scope.

Claude UI có option **Always required**.

Cần xác định:

- Claude có chủ động chạy OAuth ngay khi user bấm Connect hay chỉ sau khi nhận 401;
- việc `initialize` / `tools/list` trả 200 khi chưa auth có làm Claude bỏ qua OAuth không;
- Claude có thể discover tools trước rồi mới authenticate khi gọi tool hay không;
- server có nên yêu cầu auth ngay từ initialize hay giữ behavior hiện tại;
- behavior nào đúng MCP auth spec và tương thích cả ChatGPT lẫn Claude.

Không đổi behavior nếu chưa test cả hai client.

---

## Task 5 — Kiểm tra refresh token lifecycle

Anthropic ghi rõ Claude hỗ trợ token expiration và refresh.

Flama hiện có access token khoảng 24h và refresh token khoảng 90 ngày.

Test:

1. authorize thành công;
2. giả lập access token hết hạn hoặc dùng môi trường test với expiry ngắn;
3. quan sát Claude có gọi `grant_type=refresh_token` hay không;
4. verify refresh token rotation/reuse behavior của Flama;
5. verify user không phải login lại;
6. revoke connected app rồi xác nhận Claude bị mất quyền;
7. xác nhận lỗi sau revoke đủ chuẩn để Claude yêu cầu re-auth.

---

## Task 6 — Điều tra Dynamic Client Registration (DCR)

Đọc MCP OAuth/Auth spec mới nhất và Anthropic docs.

Xác định tối thiểu:

- Claude DCR request format;
- required `registration_endpoint` metadata;
- redirect URI registration;
- public/confidential client behavior;
- PKCE requirement;
- client secret generation/rotation;
- cách delete/re-register client;
- Anthropic behavior khi token endpoint trả `401 invalid_client`;
- database/model changes cần thiết nếu Flama hỗ trợ DCR;
- abuse/rate-limit/garbage client registration risk.

Kết luận cuối task:

```text
DCR có đáng implement cho Flama không?
YES / NO / LATER
```

và giải thích lý do.

---

## Task 7 — Điều tra Anthropic-hosted client metadata / CIMD

Xác nhận chính xác mode này dựa trên spec hiện hành.

Nếu là CIMD/client metadata URL, cần điều tra:

- metadata document schema;
- client ID URL rules;
- issuer/origin restrictions nếu có;
- redirect URIs lấy từ document thế nào;
- cache strategy;
- metadata refresh;
- signed metadata có hay không;
- SSRF protection;
- DNS rebinding/private IP protection;
- redirect-following policy;
- timeout + maximum response size;
- fail-closed behavior.

So sánh với model `OAuthClient` hiện tại và xác định có cần persist client hay có thể validate metadata dynamically.

---

## Task 8 — So sánh 3 chiến lược Claude OAuth

Tạo bảng kết luận:

| Mode | Flama hiện hỗ trợ? | Cần thay đổi gì? | Security | UX | Khuyến nghị |
|---|---|---|---|---|---|
| Own OAuth Client | ? | ? | ? | ? | ? |
| DCR | ? | ? | ? | ? | ? |
| Anthropic-hosted metadata/CIMD | ? | ? | ? | ? | ? |

Không mặc định mode Claude đánh dấu "recommended" là mode tốt nhất cho Flama. Cần đánh giá dựa trên complexity, security và maintenance.

---

## Task 9 — So sánh Claude Connector với ChatGPT Connector

Flama UI hiện tập trung nhiều vào ChatGPT.

Cần ghi rõ những phần có thể dùng chung:

```text
Flama OAuth server
Authorization Code + PKCE
access/refresh token
scope model
MCP Bearer auth
connected apps
```

và những phần client-specific:

```text
callback URL
client registration mode
UI setup guide
OAuth metadata expectations
client-specific quirks
```

Mục tiêu là tránh tạo một OAuth implementation riêng cho Claude.

Kiến trúc mong muốn vẫn là:

```text
               Flama OAuth/MCP Core
                       │
          ┌────────────┴────────────┐
          │                         │
      ChatGPT                   Claude
      Connector                 Connector
```

---

## Task 10 — Đề xuất thay đổi UI/documentation sau khi xác nhận flow

Sau khi test xong mới đề xuất chỉnh `McpOAuthTab.tsx` / guide.

Hướng UX dự kiến:

```text
OAuth Connectors

[ ChatGPT ] [ Claude ]
```

Claude guide tối thiểu nên cho user biết:

- MCP Server URL;
- Authentication mode;
- OAuth client mode nên chọn;
- Client ID/Secret nếu dùng own client;
- callback URLs cần whitelist;
- login/consent flow;
- cách disconnect/revoke.

Nếu DCR/CIMD chưa hỗ trợ thì UI/document phải nói rõ, tránh user chọn option Claude không tương thích rồi tưởng Flama lỗi.

---

## Task 11 — Security review

Kiểm tra ít nhất:

- redirect URI exact match;
- PKCE S256;
- authorization code single-use + short expiry;
- `state` preservation;
- client secret storage/hash;
- access token/refresh token storage/hash;
- token revocation;
- scope narrowing;
- cross-user isolation;
- disabled user behavior;
- OAuth client admin ownership/permissions;
- logs không leak token/code/secret;
- callback URL validation;
- CSRF cho login/consent;
- discovery URLs phía reverse proxy;
- `X-Forwarded-Proto` / `X-Forwarded-Host` trust boundary.

Nếu nghiên cứu CIMD/DCR, bổ sung threat model riêng cho dynamic client registration/remote metadata fetch.

---

## Task 12 — Regression matrix

Tối thiểu test:

| Case | Expected |
|---|---|
| Claude own OAuth client + user chưa login | mở Flama login |
| Claude own OAuth client + user đã login | vào consent trực tiếp |
| user approve | callback Claude nhận code |
| user deny | Claude nhận OAuth access_denied |
| wrong redirect URI | reject |
| wrong client secret | reject token exchange |
| wrong PKCE verifier | reject |
| expired auth code | reject |
| reused auth code | reject |
| valid access token | MCP tool chạy đúng user |
| missing required scope | 403 |
| expired access token + valid refresh | refresh thành công |
| revoked refresh/access token | không dùng tiếp được |
| user A token | không đọc/ghi data user B |
| ChatGPT connector hiện tại | không regression |

---

# Deliverable bắt buộc

Kết thúc investigation phải cập nhật chính file này hoặc tạo report bên cạnh với kết luận rõ ràng.

Không kết luận kiểu "có vẻ chạy".

Report phải có:

## 1. Verified working flow

Ví dụ:

```text
Claude Own OAuth Client → WORKING
```

và evidence.

## 2. Unsupported flow

Ví dụ:

```text
DCR → NOT IMPLEMENTED
CIMD → NOT IMPLEMENTED
```

nếu đúng sau khi verify.

## 3. Root incompatibilities

Liệt kê chính xác endpoint/metadata/model/validation nào đang thiếu.

## 4. Recommended target

Chọn một trong:

```text
A. Chỉ support pre-registered OAuth client
B. Pre-registered + DCR
C. Pre-registered + CIMD
D. Pre-registered + DCR + CIMD
```

và giải thích trade-off.

## 5. Required code changes

Chỉ liệt kê sau khi investigation hoàn tất. Chia nhỏ theo backend/frontend/tests/docs.

## 6. Tests cần thêm

Chỉ rõ test file/case.

## 7. Documentation changes

Nêu chính xác phần nào của Flama UI/docs cần bổ sung cho Claude.

---

# Definition of Done

Task investigation chỉ được coi là hoàn thành khi:

- [ ] Đã đọc implementation OAuth/MCP hiện tại của Flama trên `develop`.
- [ ] Đã đọc tài liệu Claude Remote MCP/Custom Connector mới nhất.
- [ ] Đã test Claude `Use your own OAuth client` end-to-end hoặc ghi rõ blocker có evidence.
- [ ] Đã xác nhận callback URL thực tế.
- [ ] Đã xác nhận login → consent → callback → token → MCP flow.
- [ ] Đã xác nhận refresh/revoke behavior.
- [ ] Đã xác định DCR có/không tương thích.
- [ ] Đã xác định Anthropic-hosted metadata/CIMD có/không tương thích.
- [ ] Đã kiểm tra ảnh hưởng tới ChatGPT Connector hiện tại.
- [ ] Đã có security review.
- [ ] Đã có regression matrix.
- [ ] Đã đưa ra recommendation cuối cùng có bằng chứng.

---

## Ghi chú triển khai

Task này là **investigation-first**.

Không thêm DCR, CIMD hoặc thay đổi OAuth behavior chỉ vì Claude UI có option tương ứng. Chỉ implement sau khi xác nhận protocol requirement, threat model và lợi ích UX.

Nếu cần sửa code sau investigation, chia thành task/branch nhỏ riêng và target `develop`; không đẩy thay đổi trực tiếp vào `master`.
