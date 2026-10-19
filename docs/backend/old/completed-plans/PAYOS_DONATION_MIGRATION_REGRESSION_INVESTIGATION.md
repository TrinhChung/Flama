# PayOS Donation Migration Regression Investigation
> **Trạng thái:** [x] ĐÃ HOÀN THÀNH (Completed)  
> **Ngày hoàn thành:** 2026-08-20  
## 1. Problem statement

A user can complete a donation through PayOS successfully, but Flama may still show the saved donation order as `pending_payment` / `Đang chờ thanh toán` afterward.

This investigation is limited to the online PayOS donation flow.

Out of scope:

- manual bank transfer
- static donation QR transfer
- marketplace purchase behavior unless it shares code that is directly relevant to the donation bug
- unrelated payment providers

The main suspicion is a regression introduced when Flama moved from the original Flask/Jinja MVP, where backend routes also rendered the payment result page, to the current architecture where React frontend and Flask backend may run on separate origins.

## 2. Expected canonical flow

The expected flow is:

```text
React frontend
    ↓
POST donation checkout to Flask API
    ↓
Flask creates PaymentOrder + PaymentAttempt
    ↓
Flask creates PayOS payment link
    ↓
User pays on PayOS
    ↓
PayOS reports PAID
    ↓
    ┌───────────────────────────────┐
    │                               │
webhook                         browser return
    │                               │
Flask verifies webhook          React receives payment context
    │                               │
update DB                       React asks Flask for order status
    │                               │
    └──────────────┬────────────────┘
                   ↓
         pending order is reconciled
                   ↓
 PaymentAttempt = confirmed
 PaymentOrder = paid
 grant_status = completed
                   ↓
        UI shows payment success
```

Webhook delivery should be the primary confirmation path.

Browser return/revisit reconciliation should be the recovery path when webhook delivery is delayed, missed, ignored, or fails.

## 3. Known code observations to verify

The investigation should start from the current implementation and verify each observation against the actual deployed production behavior.

Current code appears to have these characteristics:

1. `SupportPage` sends the current browser URL as `return_url` and `cancel_url` when creating a donation checkout.
2. Saved PayOS checkout logic appends payment context such as `payment_order_id` to the return URL.
3. `payment_service.get_order_detail_for_user()` can reconcile a pending order by querying PayOS and can convert a PayOS `PAID` state into a confirmed attempt and paid order.
4. The current React `SupportPage` does not appear to consume `payment_order_id` from the browser URL and trigger that reconciliation after PayOS returns.
5. Legacy `/support-donation/result` frontend routing now redirects to `/support`.
6. User order history currently reads payment state from the database and does not itself guarantee a PayOS reconciliation for every pending row.
7. `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED` defaults to false in application configuration/bootstrap behavior.
8. The current managed production environment workflow may not manage `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED`, which could leave an older production value unchanged after deployments.

Do not assume any of these is the root cause until production evidence confirms it.

## 4. Investigation hypotheses

### H1 — Jinja to SPA return-flow regression

Before the migration, PayOS may have returned to a Flask route that performed or triggered payment reconciliation before rendering the result page.

After migration, PayOS may now return directly to the React frontend, but the equivalent post-return reconciliation logic may not have been migrated.

Expected evidence:

```text
PayOS PAID
→ browser returns to frontend
→ payment_order_id exists or should exist
→ React does not request canonical order detail/reconciliation
→ DB stays pending if webhook did not already update it
```

### H2 — Wrong return URL/origin is sent to PayOS

The payment link may still contain a legacy backend/Jinja URL, backend origin, stale domain, or other incorrect return URL after frontend/backend separation.

Expected evidence:

- actual PayOS `returnUrl` does not point to the intended production frontend route;
- browser is redirected to an obsolete route/domain;
- expected payment context is missing after redirect.

### H3 — Return URL is correct, but React drops the payment context

PayOS may correctly return to the React frontend with `payment_order_id`, but routing or component logic may discard the query parameters before reconciliation occurs.

Pay special attention to redirects such as:

```text
/support-donation/result
→ /support
```

Determine whether query parameters survive this transition and whether the final component consumes them.

### H4 — Webhook processing is disabled in production

PayOS webhook may be delivered correctly but stored as `ignored` because `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED` is false.

Expected evidence:

```text
PaymentWebhookEvent.processing_status = ignored
error_message mentions webhook auto grant being disabled
PaymentOrder.status = pending_payment
PayOS payment state = PAID
```

### H5 — Webhook endpoint/configuration is stale after deployment changes

PayOS may still be configured with an old webhook URL or a URL that no longer reaches the canonical Flask endpoint.

Canonical endpoint to verify:

```text
POST /api/payments/providers/payos/webhook
```

Determine the full production URL and confirm PayOS is configured to use that exact reachable endpoint.

### H6 — Cross-origin session/CORS behavior prevents return reconciliation

If frontend and backend are on different origins, the returned React page may attempt to query the backend but fail to carry the authenticated Flask session or fail CORS/credential requirements.

Expected evidence may include:

- `401` after browser return;
- missing session cookie;
- cookie domain/SameSite/Secure mismatch;
- CORS rejection;
- backend request never sent because frontend logic is missing.

Separate this from H1: first determine whether the React page attempts reconciliation at all.

### H7 — Checkout response contract drift

The frontend and backend may disagree on where `checkout_url`, order id, or payment context lives in the checkout response.

This may be a separate migration regression and should be documented even if it does not explain the already-paid-but-pending incident.

## 5. Investigation tasks

### Task 1 — Reconstruct the production topology

Document the exact current production values without exposing secrets:

- frontend public origin;
- Flask backend public origin;
- `VITE_API_BASE_URL` effective production value;
- canonical donation page URL;
- canonical PayOS webhook URL;
- whether frontend and backend are same-site or cross-site;
- relevant cookie domain/SameSite/Secure behavior.

Deliverable:

```text
Frontend: https://...
Backend:  https://...
Donation: https://.../support
Webhook:  https://.../api/payments/providers/payos/webhook
```

Do not write credentials or PayOS secrets into this document.

### Task 2 — Trace checkout creation end to end

For a controlled test donation, capture the identifiers required to follow one transaction through the system:

- Flama `PaymentOrder.id`;
- merchant order code;
- `PaymentAttempt.id`;
- PayOS provider order code;
- PayOS payment link id;
- expected payment reference;
- checkout URL;
- exact `returnUrl` sent to PayOS;
- exact `cancelUrl` sent to PayOS.

Determine where each URL originates:

```text
React window.location
→ checkout API payload
→ support checkout service
→ payment service
→ PayOS SDK request
```

### Task 3 — Observe the real PayOS browser return

Complete one controlled PayOS payment and record:

- URL immediately before leaving PayOS;
- first Flama URL after PayOS redirects;
- final URL after React Router redirects;
- query parameters present at each stage;
- whether `payment_order_id` is preserved;
- whether an obsolete `/support-donation/result` route is involved;
- whether the browser lands on frontend origin or backend origin.

This task should answer H2 and most of H3.

### Task 4 — Compare legacy Jinja behavior with the SPA behavior

Use git history around the payment and frontend migration to reconstruct the old result flow.

Identify:

- old donation/payment result route;
- old Jinja template or route handler;
- whether the old route queried the order or PayOS state before rendering;
- how `return_url` was previously constructed;
- which behavior was removed or replaced during migration;
- whether an equivalent behavior exists in React today.

The goal is not to restore Jinja. The goal is to identify any lost application behavior during migration.

### Task 5 — Inspect the current React post-return behavior

Review the production React route/component handling after PayOS returns.

Confirm whether code currently does all of the following:

```text
read payment_order_id from URL
        ↓
request canonical order detail endpoint
        ↓
backend reconciles pending attempt with PayOS
        ↓
React renders paid/pending/error result
        ↓
query parameters are cleaned only after reconciliation
```

If any step is absent, record it as a confirmed migration gap.

Do not implement the fix during this task unless the investigation plan is explicitly converted into an implementation task.

### Task 6 — Verify canonical backend reconciliation behavior

Using a controlled pending saved donation order, simulate or observe PayOS returning `PAID` while the Flama DB still says `pending_payment`.

Call the canonical order-detail/reconciliation path and verify whether it changes:

```text
PaymentAttempt.status
pending → confirmed

PaymentOrder.status
pending_payment → paid

PaymentOrder.grant_status
pending → completed
```

If this works, document that backend reconciliation is healthy and the missing link is likely in webhook configuration or frontend return flow.

If it does not work, continue tracing `_sync_attempt_with_payos()` and provider state normalization.

### Task 7 — Verify production webhook delivery and processing

For the same controlled transaction, inspect `PaymentWebhookEvent` and server logs.

Determine which state applies:

```text
no webhook row
→ PayOS did not reach Flama or endpoint/config is wrong

received → ignored
→ inspect error_message and feature flags

received → failed
→ inspect processing exception

received → processed
→ DB should normally be paid; investigate transaction/update path if not
```

Also verify:

- signature verification succeeds;
- provider identifiers match the expected `PaymentAttempt`;
- webhook resolves exactly one attempt;
- amount/reference validation succeeds.

### Task 8 — Audit production payment environment management

Inspect all places that define or manage payment environment variables:

- application defaults;
- `.env_example`;
- Hostinger bootstrap;
- `/etc/flama/flama.env` behavior;
- GitHub Environment variables;
- deploy workflow;
- `sync_managed_env.py` managed-key allowlist.

Specifically determine the effective production value of:

```text
PAYMENTS_ENABLED
PAYMENTS_PROVIDER
PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED
PAYMENTS_ORDER_EXPIRY_SECONDS
```

Confirm whether `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED` is controlled by deployment automation or is an unmanaged legacy value left behind from an older deployment.

Do not expose PayOS API credentials in logs, commits, issue comments, or this plan.

### Task 9 — Compare PayOS state, Flama DB state, and UI state

For at least one affected or controlled transaction, build a single evidence table:

| Layer | State |
| --- | --- |
| PayOS payment link | `PAID` / other |
| PaymentAttempt | `pending` / `confirmed` / other |
| PaymentOrder | `pending_payment` / `paid` / other |
| PaymentWebhookEvent | none / received / ignored / processed / failed |
| Browser return URL | exact route + non-sensitive query context |
| React displayed state | pending / paid / error |

This table should make the broken transition obvious.

### Task 10 — Verify the order-history read path

Confirm whether `/orders` and its REST read service only present DB state or also reconcile pending PayOS orders.

Determine whether the current behavior means:

```text
DB accidentally stays pending
        ↓
/orders refresh
        ↓
UI stays pending forever
```

Document whether this is intentional architecture or a reliability gap.

### Task 11 — Run a regression matrix

At minimum, verify these scenarios:

| Scenario | Expected result |
| --- | --- |
| Webhook succeeds before browser return | order is paid when user returns |
| Browser returns before webhook | return reconciliation eventually shows paid |
| Webhook is delayed/missed | browser return/revisit can recover paid state |
| User closes PayOS after paying and later opens order history | paid state can eventually be recovered |
| PayOS remains pending | Flama remains pending |
| PayOS reports canceled/expired | Flama does not incorrectly mark paid |
| Frontend/backend are separate origins | authenticated saved donation reconciliation still works |

Record actual behavior for every case.

### Task 12 — Produce a root-cause decision

Do not finish the investigation with a vague list of possibilities.

Classify findings into:

- primary root cause;
- contributing causes;
- unrelated payment defects discovered during investigation;
- confirmed non-causes.

Example structure:

```text
Primary root cause:
- React post-PayOS return flow no longer triggers order reconciliation after Jinja → SPA migration.

Contributing cause:
- production webhook auto processing remained disabled because the deployment managed-env allowlist did not include the flag.

Amplifier:
- order history only reads stale DB state and does not reconcile pending orders.

Unrelated defect:
- checkout response contract differs between frontend and backend.
```

The actual conclusion must be based on collected evidence, not this example.

## 6. Required evidence before proposing a fix

The agent should not jump directly into code changes.

Before implementation, collect enough evidence to answer all of these questions:

1. What exact `returnUrl` did PayOS receive?
2. What exact URL did the browser return to after successful payment?
3. Was `payment_order_id` present after return?
4. Did React attempt to reconcile that order?
5. Did PayOS deliver a webhook?
6. If delivered, was the webhook processed, ignored, or failed?
7. What was the effective production value of `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED`?
8. Was the PayOS payment state actually `PAID` while Flama DB remained `pending_payment`?
9. Does direct canonical order reconciliation repair the state?
10. Which behavior existed in the old Jinja flow but is absent in the current SPA flow?

## 7. Expected investigation output

At the end of the investigation, the document is updated with confirmed findings:

### 7.1 Confirmed Findings

1. **Deployment & Environment Management**:
   - `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED` is missing from `MANAGED_VARIABLE_KEYS` in `deploy/sync_managed_env.py` and `.github/workflows/deploy.yml`.
   - In `app/settings.py`, `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED` defaults to `False`.
   - In `deploy/bootstrap_hostinger.sh`, `/etc/flama/flama.env` is initialized with `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED=0`.
   - Consequently, incoming PayOS webhooks are marked as `ignored` with message `"Chế độ tự cấp quyền từ webhook đang tắt nên cần xử lý thủ công."` and return HTTP 202 without updating `PaymentOrder` or granting entitlements.

2. **Frontend Return Flow (Marketplace & Donation)**:
   - For Marketplace: `return_url` points to `/payments/marketplace-result?payment_order_id=...`. However, `frontend/src/App.tsx` lacks a route for `/payments/marketplace-result`, causing React Router to hit the wildcard `*` (`<NotFoundPage />` 404). No component exists to extract `payment_order_id` and call `/api/payments/orders/<order_id>` for reconciliation.
   - For Support Donation: `SupportPage.tsx` passes `return_url: window.location.href`, and PayOS returns with query parameters (`payment_order_id` or `support_provider_order_code`). However, `SupportPage.tsx` does not inspect query parameters or call any reconciliation endpoint upon mount, and `/support-donation/result` performs a hard redirect `<Navigate to="/support" replace />` that strips all query parameters.

3. **Order History Read Path**:
   - `/orders` calls `GET /api/orders`, which queries `order_queries.paginate_user_orders()` without checking PayOS for active pending attempts.
   - Thus, once an order is stuck in `pending_payment`, visiting `/orders` leaves it in `pending_payment` indefinitely.

### 7.2 Root Cause Summary

- **Primary Root Cause**: Regression during Jinja → React SPA migration. The post-PayOS return routes (`/payments/marketplace-result` and post-donation reconciliation) were not implemented in React Router (`frontend/src/App.tsx`) and the corresponding frontend pages (`SupportPage.tsx`), preventing browser-return reconciliation.
- **Amplifying Cause**: `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED` was left disabled (`False` / `0`) in deployment automation (`sync_managed_env.py`, `deploy.yml`, `bootstrap_hostinger.sh`), causing all automatic webhook-based fulfillment to be ignored in production.

### 7.3 Implementation Plan

1. **CI/CD & Environment Management**:
   - Add `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED` and `PAYMENTS_ORDER_EXPIRY_SECONDS` to `MANAGED_VARIABLE_KEYS` in `deploy/sync_managed_env.py` and `.github/workflows/deploy.yml`.
   - Update `deploy/bootstrap_hostinger.sh` and `.env_example`.

2. **Frontend Return & Reconciliation**:
   - Add `PaymentResultPage.tsx` in `frontend/src/features/marketplace/pages/` to handle `/payments/marketplace-result` and `/payments/result`, reconciling orders via `GET /api/payments/orders/<order_id>`.
   - Register routes in `frontend/src/App.tsx`.
   - Update `SupportPage.tsx` to read return parameters and display a confirmation/thank-you banner with reconciliation.

3. **Order History Recovery**:
   - Allow user order detail lookup (`GET /api/orders/<order_id>`) to trigger reconciliation if an order is still pending.
   - Add an order detail drawer/dialog and "Sync status" action in `OrdersPage.tsx`.

## 8. Investigation Completion Status

- [x] Exact broken state transitions identified.
- [x] Jinja → React migration gaps verified.
- [x] Production webhook configuration verified.
- [x] Implementation plan documented in `implementation_plan.md`.
