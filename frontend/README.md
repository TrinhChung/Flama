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
`/api/v1` và có thể đổi bằng `VITE_API_BASE_URL`. Vite proxy mặc định tới
`http://127.0.0.1:4789`; đổi bằng `VITE_FLASK_ORIGIN` khi Flask chạy cổng khác.

Không đưa business logic của deck overlay, scheduler hoặc payment vào frontend;
REST API vẫn là owner của permission, transaction và validation cuối cùng.
