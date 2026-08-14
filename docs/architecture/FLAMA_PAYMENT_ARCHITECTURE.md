# FLAMA Payment Architecture

Date: 2026-03-28
Status: canonical payment documentation

## 1. Direction

FLAMA is payOS-first.

- payOS is the only intended online payment provider in the current product direction.
- The payment domain is organized around order management, payment attempts, webhook processing, entitlement fulfillment, and admin visibility.
- VietQR is not a parallel or co-equal architecture in this repository.
- Do not add new VietQR-first branching, env vars, route names, or flow documents unless there is a new explicit product decision.

If you need older context, see `docs/historical/FLAMA_PAYMENT_DOMAIN_EXPANSION_PLAN.md`, which is now a legacy note and must not be used as the implementation source of truth.

## 2. Canonical domain model

The live payment domain in this repository is centered on these models:

- `PaymentOrder`
  - Commercial order boundary owned by one user.
  - Stores order status, grant status, totals, timestamps, and merchant order code.
- `PaymentOrderItem`
  - Immutable line-item snapshot for what the user intended to buy.
- `PaymentAttempt`
  - Transaction-facing payment record for one provider session or retry.
  - Stores provider ids, expected payment reference, checkout URL, amount, status, and provider metadata.
- `PaymentWebhookEvent`
  - Raw provider callback log plus idempotency and processing status.
- `PaymentEntitlement`
  - Fulfillment ledger that records what access was granted to the buyer after confirmed payment.

Related marketplace fulfillment rows still live in the flashcards domain:

- `NoteTypeInstall`
- `DeckInstall`

These install rows are fulfillment results. They are not the payment proof. Payment proof lives in the payment domain.

## 3. Status model

The project separates business order state from payment state and webhook state.

### 3.1 Order lifecycle

`PaymentOrder.status`

- `pending_payment`
- `paid`
- `under_review`
- `expired`
- `canceled`
- `failed`
- `refunded`

Meaning:

- Order status answers: "What is the business state of this purchase?"
- It does not answer: "What exact callback or provider session happened most recently?"

### 3.2 Fulfillment lifecycle

`PaymentOrder.grant_status`

- `pending`
- `completed`
- `failed`

Meaning:

- Grant status answers: "Has FLAMA actually granted access after payment?"

### 3.3 Payment attempt lifecycle

`PaymentAttempt.status`

- `created`
- `pending`
- `confirmed`
- `manual_review`
- `expired`
- `canceled`
- `failed`
- `refunded`

Meaning:

- Attempt status answers: "What happened to this provider-side payment session or retry?"
- This is the transaction-facing state admins inspect when something goes wrong.

### 3.4 Webhook processing lifecycle

`PaymentWebhookEvent.processing_status`

- `received`
- `processed`
- `ignored`
- `failed`

Meaning:

- Webhook status answers: "What did FLAMA do with the callback?"

## 4. Current route ownership

### 4.1 User-facing routes

`app/routes/payments.py`

- `GET /payments/marketplace-result`
- `POST /api/payments/orders`
- `GET /api/payments/orders/<order_id>`
- `POST /api/payments/orders/<order_id>/cancel`
- `POST /api/payments/providers/payos/webhook`

`app/routes/user_orders.py`

- `GET /orders`
- `GET /orders/<order_id>`

### 4.2 Admin-facing routes

`app/routes/admin_payments.py`

- `GET /admin/payments`
- `GET /admin/payments/orders`
- `GET /admin/payments/orders/<order_id>`
- `GET /admin/payments/transactions`
- `GET /admin/payments/transactions/<attempt_id>`

Admin payment operations are intentionally isolated from user-role and TTS admin logic.

## 5. Current service boundaries

### 5.1 Core orchestration

`app/services/payment_service.py`

Owns:

- creating or reusing orders for marketplace purchases
- creating payOS checkout sessions
- syncing pending attempts with payOS
- canceling user orders
- processing payOS webhook payloads
- confirming orders and issuing entitlements
- handing off fulfillment into `NoteTypeInstall` and `DeckInstall`

This file is still the write/orchestration center for the payment domain.

### 5.2 payOS provider integration

`app/services/payment/provider/payos_provider.py`

Owns:

- payOS availability checks
- payment link creation
- payment link state lookup
- payOS webhook verification and normalization

Provider-specific logic should remain here or in provider-adjacent helpers. It should not spread into user routes, templates, or unrelated services.

### 5.3 Read/query layer

Current read-focused payment surfaces are split into smaller services:

- `app/services/payment/order_query_service.py`
- `app/services/payment/transaction_query_service.py`
- `app/services/payment/dashboard_service.py`
- `app/services/payment/presenters.py`
- `app/repositories/payment/order_queries.py`
- `app/repositories/payment/transaction_queries.py`
- `app/repositories/payment/dashboard_queries.py`

These modules exist so admin and user history screens do not keep growing `payment_service.py`.

## 6. User-facing behavior

The user side is intentionally simple.

Users can:

- see their order history
- open order detail
- understand the current order/payment state
- continue payment on a still-pending order

Users do not get:

- raw provider payloads
- webhook internals
- reconciliation tools
- admin finance screens

The user-facing order/detail presenters must stay clear and operational, not provider-debug heavy.

## 7. Admin-facing behavior

Admin payment operations are intentionally stronger than the user side.

Admins can:

- monitor payment operations from `/admin/payments`
- review all orders
- review all payment attempts
- inspect webhook failures and manual-review cases
- filter by status, buyer, seller, provider, product type, amount, and date range

The admin dashboard should favor operational usefulness over vanity metrics.

Current emphasis:

- total orders
- paid, pending, failed/expired, refunded, under-review counts
- revenue based on paid orders
- attempt success rate
- recent orders
- recent abnormal attempts
- recent webhook failures
- provider breakdown
- status distributions

## 8. payOS flow

### 8.1 Order creation

When a user tries to buy paid marketplace content:

1. FLAMA checks whether the user already owns the product.
2. FLAMA checks whether a reusable pending order already exists.
3. If an old payOS link is still valid, FLAMA reuses that attempt.
4. If the old payOS link is closed, expired, canceled, or failed, FLAMA closes that attempt and creates a new payOS checkout session.
5. FLAMA returns the order plus checkout info to the client.

### 8.2 Payment confirmation

FLAMA accepts payOS confirmation in two ways:

- direct payOS webhook delivery
- explicit state sync when the user revisits a pending order and FLAMA re-checks payOS

If payOS reports a clean successful payment with the expected amount:

- the attempt becomes `confirmed`
- the order becomes `paid`
- entitlements are created or activated
- fulfillment grants access to the purchased marketplace content
- `grant_status` becomes `completed`

### 8.3 Manual review

Manual review is reserved for abnormal cases such as:

- amount mismatch
- inconsistent provider reference
- signature or event trust issues
- underpaid or ambiguous provider state

Normal payOS success should not go through manual review.

## 9. Webhook rules

FLAMA treats payOS webhook handling as an idempotent, audit-friendly flow.

Rules:

- persist callback evidence through `PaymentWebhookEvent`
- deduplicate by provider/event identity
- resolve the target attempt/order deterministically
- update order and attempt state atomically
- create fulfillment only once
- keep webhook failure history for replay or manual investigation

Canonical webhook endpoint:

- `POST /api/payments/providers/payos/webhook`

There is no canonical VietQR webhook endpoint anymore.

## 10. Configuration

Canonical payment env variables:

- `PAYMENTS_ENABLED`
- `PAYMENTS_PROVIDER=payos`
- `PAYMENTS_PAID_INSTALL_REQUIRED`
- `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED`
- `PAYMENTS_ORDER_EXPIRY_SECONDS`
- `PAYOS_CLIENT_ID`
- `PAYOS_API_KEY`
- `PAYOS_CHECKSUM_KEY`

Notes:

- `PAYMENTS_PROVIDER` exists as a config seam, but the only supported value today is `payos`.
- `PAYMENTS_V1_ENABLED` still exists in code as a backward-compatibility alias. Do not use it in new setup docs or new environments.
- Do not introduce `PAYMENTS_VIETQR_*` variables back into documentation or setup examples.

## 11. Extension rules for future contributors

If you extend the payment domain:

- keep payOS as the current provider direction unless product direction changes explicitly
- extend order management and admin visibility first
- keep provider-specific fields out of route and template logic
- do not merge order status, attempt status, and webhook status into one vague field
- keep user screens simple
- keep admin screens operational

If a second provider is ever reintroduced in the future, that must be a new explicit architecture decision. Do not infer that from legacy VietQR references.

## 12. Non-goals

The current payment documentation does not treat these as active architecture goals:

- VietQR-first flow design
- parallel payOS/VietQR support
- provider comparison docs
- provider-selection UI
- user-facing reconciliation tooling
- user-facing transaction ledger

## 13. Source of truth

For payment work, use these files first:

- `docs/architecture/FLAMA_PAYMENT_ARCHITECTURE.md`
- `docs/architecture/SYSTEM_ARCHITECTURE.md`
- `.env_example`
- `app/routes/payments.py`
- `app/routes/admin_payments.py`
- `app/routes/user_orders.py`
- `app/services/payment_service.py`
- `app/services/payment/provider/payos_provider.py`
- `models/payment_order.py`
- `models/payment_attempt.py`
- `models/payment_webhook_event.py`
- `models/payment_entitlement.py`

Do not use older VietQR-oriented notes as the basis for new implementation.
