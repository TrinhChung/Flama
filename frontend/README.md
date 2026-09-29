# Flama React Frontend

Frontend migration workspace chạy độc lập với Flask trong giai đoạn đầu.

## Stack

- React + TypeScript + Vite
- shadcn/ui (Radix Nova preset)
- Tailwind CSS v4
- TanStack Query
- React Router
- React Hook Form + Zod

## Chạy local

```powershell
cd frontend
npm install
npm run dev
```

Mở `http://127.0.0.1:5173`.

Chạy Flask ở `http://127.0.0.1:4789` trước khi mở frontend. Vite proxy `/api`
sang Flask để session cookie và CSRF hoạt động cùng origin. Đăng nhập bằng tài
khoản thật trong database hiện tại.

Có thể sao chép cấu hình mẫu cho môi trường local:

```powershell
Copy-Item .env.example .env.local
```

`.env.local` không được commit. Với local, giữ `VITE_API_BASE_URL=/api`; Vite
proxy namespace này tới Flask ở `http://127.0.0.1:4789`.

## Deploy Cloudflare Pages

Production **không** để Cloudflare Pages tự build khi push `master`. Nếu Pages tự
build, SPA mới lên trong vài chục giây trong khi backend còn đang chạy CI,
migrate hoặc đã rollback, và màn hình mới gọi vào API chưa tồn tại.

Luồng hiện tại (`.github/workflows/ci.yml`):

1. CI validate toàn bộ.
2. `deploy.yml` deploy backend lên VPS và ghi commit vào `REVISION`;
   `/api/health` trả về `release` là commit đó.
3. `deploy-frontend.yml` build SPA, chạy `scripts/check_backend_release.py`
   rồi mới `wrangler pages deploy`. Gate chặn publish nếu backend đang live còn
   thiếu thay đổi runtime nào (`app/`, `models/`, `migrations/`...) tính đến
   commit frontend. Backend deploy fail hoặc rollback thì frontend giữ nguyên
   bản cũ.

Cấu hình một lần:

- Cloudflare Pages → project → **Settings → Builds & deployments → Branch
  control**: bỏ chọn **Enable automatic production branch deployments**
  (preview branch giữ nguyên nếu cần).
- GitHub Environment `Flama`:
  - secret `CLOUDFLARE_API_TOKEN` (quyền *Account → Cloudflare Pages → Edit*);
  - variable (hoặc secret) `CLOUDFLARE_ACCOUNT_ID`;
  - variable `CLOUDFLARE_PAGES_PROJECT` = tên project Pages;
  - variable `VITE_API_BASE_URL` (mặc định `https://be-flama.stmtp.com/api`),
    tuỳ chọn `VITE_FLAMA_CONNECT_URL`, `VITE_FLAMA_MCP_URL`.

`VITE_*` được Vite nhúng vào bundle lúc build nên không được chứa secret, API
key hoặc thông tin đăng nhập. Frontend tự suy ra backend origin từ
`VITE_API_BASE_URL` cho các asset Flask như `/static/js/card_renderer_host.js`.

Deploy lại thủ công: chạy workflow **Deploy Flama Frontend to Cloudflare
Pages** trên `master`; gate vẫn áp dụng.

Vì backend luôn lên trước, trong vài phút giữa hai bước (và với tab người dùng
đang mở) SPA cũ vẫn gọi backend mới. Thay đổi API phải tương thích ngược với SPA
trước đó: thêm endpoint/field mới trước, chỉ xoá cái cũ ở release sau khi SPA
không còn dùng.

Khi Pages và Flask khác origin, backend vẫn phải:

- cho phép đúng origin Pages/custom domain qua CORS;
- cho phép credential và các header `Content-Type`, `X-CSRF-Token`,
  `X-CSRFToken`;
- cấu hình session cookie phù hợp HTTPS/cross-origin.

Ưu tiên dùng custom domain cùng site, ví dụ `app.example.com` và
`api.example.com`, để session cookie ổn định hơn so với ghép `pages.dev` với
một domain backend không liên quan.

## Kiểm tra

```powershell
npm run lint
npm run typecheck
npm run build
```

Hoặc chạy toàn bộ:

```powershell
npm run check
```

## Kiến trúc

```text
src/
├── app/
│   └── api.ts              # REST adapter cho Flask API
├── components/
│   ├── ui/                 # shadcn primitives do CLI quản lý
│   ├── app-sidebar.tsx     # sidebar-07 được điều chỉnh cho route Flama
│   ├── nav-main.tsx
│   └── nav-user.tsx
├── features/
│   ├── auth/
│   ├── browse/
│   ├── dashboard/
│   ├── study/
│   ├── statistics/
│   ├── library/
│   ├── marketplace/
│   ├── orders/
│   └── admin/
├── layouts/
├── lib/
├── pages/
└── shared/
    ├── api/
    ├── components/
    └── types/
```

Quy ước:

- Page/component không gọi `fetch` trực tiếp.
- TanStack Query gọi qua `app/api.ts`.
- Server state nằm trong query cache; UI state nằm gần component sử dụng nó.
- Form dùng React Hook Form và schema Zod.
- Page route được lazy-load để tách bundle.
- shadcn/ui là nguồn component/style chính; token Flama nằm trong
  `src/index.css`.
- Thêm primitive bằng `npx shadcn@latest add <component>` thay vì tạo bản sao
  CSS/component riêng.
- Không mang Bootstrap hoặc CSS của template Jinja vào React app.

## Route hiện có

- Public: `/`, `/login`, `/register`, `/support`, `/terms`, `/privacy`,
  `/cookies`
- Learning: `/dashboard`, `/statistics`, `/browse`, `/study`
- Content: `/note-types`, `/installed-decks`
- Marketplace: `/marketplace/decks`, `/marketplace/note-types`
- Account: `/orders`
- Admin: `/admin/users`, `/admin/payments`, `/admin/tts`

## Kết nối backend

`src/app/api.ts` gọi REST API thật. `src/shared/api/client.ts` chịu trách nhiệm
gửi Flask session cookie và `X-CSRF-Token` cho mutation. Base URL mặc định là
`/api` và có thể đổi bằng `VITE_API_BASE_URL`. Vite proxy local mặc định tới
`http://127.0.0.1:4789`. Cloudflare Pages chỉ cần cấu hình một biến
`VITE_API_BASE_URL`.

Không đưa business logic của deck overlay, scheduler hoặc payment vào frontend;
REST API vẫn là owner của permission, transaction và validation cuối cùng.
