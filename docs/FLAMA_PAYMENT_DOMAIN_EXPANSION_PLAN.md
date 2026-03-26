# Flama Payment Domain Expansion Plan

Date: 2026-03-27
Status: design-only implementation plan

## 1. Executive summary

This repository already has marketplace pricing metadata on `NoteType` and `DeckMarketplaceItem`, plus install rows (`NoteTypeInstall`, `DeckInstall`) that grant access after install. It does not have a real payment boundary. Paid installs currently snapshot `purchase_price_cents` and `purchased_at` without proving that money was actually received.

This plan adds a separate payment domain with:

- `payment_orders` as the commercial checkout boundary
- `payment_order_items` as snapshot line items
- `payment_attempts` as provider-facing payment intents/attempts
- `payment_webhook_events` as raw callback storage plus idempotency boundary
- `payment_entitlements` as the generic grant ledger
- `payment_transactions` as the reconciliation table in the target model, but deferrable from MVP

The plan does not add payment fields to `User`, does not mutate the overlay-only shared deck model, and does not replace `DeckInstall` or `NoteTypeInstall`. Those install tables remain the domain fulfillment rows. Payment proof moves to the new payment tables.

The implementation seam is:

- free content keeps the current install flow
- paid content stops direct install and creates an order first
- successful provider confirmation creates entitlements and then calls the existing non-committing fulfillment services

Because `create_app()` performs `db.create_all()`, schema patching, seeding, and clone cutover on every startup, rollout must use defensive Alembic revisions, feature flags, and staged deployment.

## 2. Repository findings and constraints

### 2.1 Runtime and migration constraints

- Runtime entry is `wsgi.py`, which imports `create_app()` and exports `app`.
- `create_app()` is not passive. On startup it runs:
  - `db.create_all()`
  - `ensure_user_management_schema()`
  - `_ensure_backward_compatible_schema()`
  - `ensure_default_user_roles()`
  - `ensure_default_tts_providers()`
  - clone cutover logic in `flashcards_share`
  - a final `db.session.commit()`
- Flask-Migrate and Alembic exist, but `flask --app wsgi.py db upgrade` still executes full app startup first.
- Practical consequence: new payment revisions must be written in the same defensive style as current migrations and startup patchers. Do not assume Alembic owns first-table creation in this repo.

### 2.2 Current marketplace and install behavior

- Current sellable-looking objects are:
  - `models/note_type.py`
  - `models/deck_marketplace_item.py`
- Current access grant rows are:
  - `models/note_type_install.py`
  - `models/deck_install.py`
- Current paid behavior is not a payment flow:
  - note type install paths write `purchase_price_cents` and `purchased_at`
  - deck install paths write `purchase_price_cents` and `purchased_at`
  - neither path verifies any external transaction

### 2.3 Layering constraints

- Intended boundary is route -> service -> repository, but the live code is mixed.
- Some services commit internally and some routes commit directly.
- This matters for payment confirmation because webhook processing needs a strict transaction boundary.
- New payment code should not be built inside:
  - `app/services/support_donation_service.py`
  - `app/routes/flashcards/__init__.py`
  - route-level commit-owning helpers

### 2.4 Existing domain helpers that can be reused

- Reuse for paid deck fulfillment:
  - `app/services/flashcards_share_service.py::install_shared_deck_item_for_user`
  - this service does not commit by itself and is suitable for orchestration inside a payment transaction
- Reuse for paid note type fulfillment:
  - `app/services/flashcards_share_service.py::ensure_note_type_install_for_user`
  - this service does not commit by itself and is suitable for orchestration inside a payment transaction
- Do not use as webhook fulfillment entrypoints:
  - `install_shared_note_type(...)` service helper
  - route handlers under `app/routes/flashcards/share.py`
  - both are tied to current direct-install behavior and commit ownership that is wrong for webhook orchestration

### 2.5 Operational constraints

- There is no worker queue, scheduler, or job runner in the repo today.
- Scheduled payment maintenance should be implemented as Flask CLI commands and run by external cron, Task Scheduler, or container scheduler.
- Tests mostly run on SQLite, but production uses MySQL. Locking and duplicate protection must be validated on MySQL before production.

### 2.6 Current pricing semantics constraint

- Existing marketplace price fields are named `price_cents`.
- Existing UI labels and input behavior treat them as VNĐ whole-amount values, not literal cents:
  - `templates/flashcards/shared_deck_publish.html` labels price as `VNĐ` and uses `step="1000"`
  - marketplace serializers still render USD-style `"$... / 100"` strings
- Implementation rule:
  - do not rename existing marketplace columns in v1
  - introduce new payment-table fields as `*_amount_minor` or `*_minor`
  - treat current marketplace `price_cents` as the source price integer to convert into payment amounts
  - normalize UI/API display separately as part of payment rollout

## 3. Current user/account model implications

- `User` remains unchanged in v1.
- User is a local session-auth account with:
  - `email`
  - `username`
  - `password_hash`
  - `timezone`
  - `role_id`
  - mirrored `is_admin`
  - `is_disabled`
  - timestamps
- There is no organization, workspace, tenant, or membership model.
- Ownership is per-user across decks, note types, notes, installs, reviews, and TTS profiles.
- There is no email verification, KYC, billing profile, or soft-delete model to build on.

Implementation implications:

- Do not add payment columns to `users`.
- Payment relationships should be:
  - `User 1-N PaymentOrder`
  - `User 1-N PaymentEntitlement`
  - existing `DeckInstall` / `NoteTypeInstall` remain the domain access rows
- The absence of org/team concepts means all order ownership and entitlements should be modeled at user scope only in v1.

## 4. Target payment domain architecture

### 4.1 New backend ownership boundaries

Create a dedicated payment domain:

- `models/payment_order.py`
- `models/payment_order_item.py`
- `models/payment_attempt.py`
- `models/payment_transaction.py`
- `models/payment_webhook_event.py`
- `models/payment_entitlement.py`
- `app/repositories/payment_repository.py`
- `app/services/payment_service.py`
- `app/routes/payments.py`

Admin and backoffice routes should not bloat `app/routes/admin.py` further. Prefer:

- `app/routes/admin_payments.py`

if and when server-rendered admin payment pages are added.

### 4.2 Domain responsibilities

- Marketplace catalog remains where it already exists:
  - `NoteType`
  - `DeckMarketplaceItem`
- Payment domain owns:
  - order creation
  - provider attempt creation
  - callback ingestion
  - idempotency
  - payment confirmation state
  - entitlement issuance
  - manual review state
  - reconciliation records
- Flashcards share domain continues to own:
  - actual install creation
  - clone overlay behavior
  - note type copy/install behavior
  - deck install mapping and local deck creation

### 4.3 Provider model

Provider-agnostic concepts:

- order
- line item
- payment attempt
- webhook event
- entitlement
- optional payment transaction observation
- amount, currency, timestamps, generic statuses

VietQR-provider-specific concepts:

- transfer reference text expected in payment content
- provider `orderCode` or equivalent request id
- provider payment-link id
- provider bank transaction reference
- transaction description content
- counterparty bank/account payload fields
- provider signature or secure token behavior

### 4.4 Provider config in v1

Use environment configuration in v1, not a new provider-config table.

Reason:

- app config is already env-driven
- payment credentials are infrastructure concerns
- `SupportDonationConfig` is a public content/config table, not secret storage
- adding an admin-managed payment provider table now would increase scope without current need

Recommended env variables for v1:

- `PAYMENTS_V1_ENABLED`
- `PAYMENTS_PAID_INSTALL_REQUIRED`
- `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED`
- `PAYMENTS_VIETQR_CLIENT_ID`
- `PAYMENTS_VIETQR_API_KEY`
- `PAYMENTS_VIETQR_WEBHOOK_SECRET`
- `PAYMENTS_VIETQR_ACCOUNT_NO`
- `PAYMENTS_VIETQR_ACCOUNT_NAME`
- `PAYMENTS_VIETQR_BANK_BIN`
- `PAYMENTS_VIETQR_TEMPLATE`
- `PAYMENTS_ORDER_EXPIRY_SECONDS`

Assumption:

- exact env names can change during implementation, but v1 should stay env-driven.

## 5. Proposed tables and relationships

All new business tables should use `String(36)` UUID primary keys with `models.model_uuid.uuid_str` for consistency with `DeckInstall`, `NoteTypeInstall`, and `AuditLog`.

### 5.1 `payment_orders`

Purpose:

- one commercial checkout boundary per user action or resumed unpaid order

Key columns:

- `id`
- `user_id` FK -> `users.id`
- `merchant_order_code` unique
- `status`
- `grant_status`
- `currency_code`
- `subtotal_amount_minor`
- `discount_amount_minor`
- `total_amount_minor`
- `paid_at`
- `closed_at`
- `created_at`
- `updated_at`

Relationships:

- `User 1-N PaymentOrder`
- `PaymentOrder 1-N PaymentOrderItem`
- `PaymentOrder 1-N PaymentAttempt`
- `PaymentOrder 1-N PaymentEntitlement`

Indexes and constraints:

- unique `merchant_order_code`
- index `(user_id, created_at)`
- index `(status, created_at)`
- index `(grant_status, created_at)`

Notes:

- `status` is the commercial state.
- `grant_status` is fulfillment state and must not be inferred from `status`.
- `closed_at` is set when the order reaches a terminal or semi-terminal business end state such as `paid`, `expired`, `failed`, `canceled`, or `refunded`.

### 5.2 `payment_order_items`

Purpose:

- immutable line snapshots for what the user intended to buy

Key columns:

- `id`
- `order_id` FK -> `payment_orders.id`
- `product_type`
- `product_ref_id`
- `quantity`
- `unit_amount_minor`
- `line_total_amount_minor`
- `title_snapshot`
- `product_snapshot_json`
- `created_at`

Relationships:

- `PaymentOrder 1-N PaymentOrderItem`
- `PaymentOrderItem 1-1 PaymentEntitlement`

Indexes and constraints:

- unique `(order_id, product_type, product_ref_id)`
- index `(product_type, product_ref_id)`

Notes:

- Do not add hard foreign keys to every product table.
- `product_type + product_ref_id` is the polymorphic reference.
- Initial `product_type` values:
  - `deck_marketplace_item`
  - `note_type`
- `product_snapshot_json` should capture enough catalog data to preserve history:
  - source title
  - source price integer from marketplace table
  - source `pricing_mode`
  - source `version`
  - source owner id if useful for audit

### 5.3 `payment_attempts`

Purpose:

- provider-facing payment attempt or payment intent for one order

Key columns:

- `id`
- `order_id` FK -> `payment_orders.id`
- `provider_code`
- `payment_method_code`
- `status`
- `amount_minor`
- `currency_code`
- `provider_payment_id`
- `provider_order_code`
- `expected_payment_reference`
- `checkout_url`
- `provider_metadata_json`
- `expires_at`
- `confirmed_at`
- `failed_at`
- `failure_code`
- `failure_message`
- `manual_review_reason`
- `created_at`
- `updated_at`

Relationships:

- `PaymentOrder 1-N PaymentAttempt`
- `PaymentAttempt 1-N PaymentWebhookEvent`
- `PaymentAttempt 1-N PaymentTransaction`
- `PaymentAttempt 1-N PaymentEntitlement`

Indexes and constraints:

- index `(order_id, created_at)`
- index `(status, expires_at)`
- index `expected_payment_reference`
- unique `(provider_code, provider_payment_id)` when provider returns a stable payment id
- unique `(provider_code, provider_order_code)` if the provider guarantees uniqueness

Notes:

- `payment_method_code` should stay generic, for example:
  - `vietqr_transfer`
- `expected_payment_reference` is the merchant-generated transfer content token to match against callback data.
- `provider_metadata_json` stores provider-request artifacts such as QR template, checkout link payload, or provider account metadata.

### 5.4 `payment_transactions`

Purpose:

- immutable provider or bank transaction observations for reconciliation

Key columns:

- `id`
- `payment_attempt_id` nullable FK -> `payment_attempts.id`
- `provider_code`
- `provider_transaction_ref`
- `amount_minor`
- `currency_code`
- `observed_at`
- `payment_reference_text`
- `counterparty_name`
- `counterparty_account`
- `counterparty_bank`
- `raw_data_json`
- `created_at`

Relationships:

- optional `PaymentAttempt N-1 PaymentTransaction`

Indexes and constraints:

- unique `(provider_code, provider_transaction_ref)`
- index `(payment_attempt_id, observed_at)`
- index `(observed_at)`

Notes:

- `payment_attempt_id` is nullable so unmatched or ambiguous callbacks can still be stored for manual reconciliation.
- This table is the target design. It may be deferred from MVP if rollout needs to stay smaller.

### 5.5 `payment_webhook_events`

Purpose:

- raw callback log plus idempotency boundary

Key columns:

- `id`
- `provider_code`
- `event_key`
- `event_type`
- `payment_attempt_id` nullable FK -> `payment_attempts.id`
- `payment_order_id` nullable FK -> `payment_orders.id`
- `signature_valid`
- `processing_status`
- `error_message`
- `payload_json`
- `received_at`
- `processed_at`

Relationships:

- optional link to `PaymentAttempt`
- optional link to `PaymentOrder`

Indexes and constraints:

- unique `(provider_code, event_key)`
- index `(processing_status, received_at)`
- index `(payment_attempt_id, received_at)`
- index `(payment_order_id, received_at)`

Notes:

- Insert this row before any business processing.
- `event_key` should prefer a provider-supplied event id. If the provider does not send one, derive a deterministic key from stable callback fields.

### 5.6 `payment_entitlements`

Purpose:

- generic grant ledger independent from product-specific install tables

Key columns:

- `id`
- `user_id` FK -> `users.id`
- `payment_order_id` FK -> `payment_orders.id`
- `payment_order_item_id` FK -> `payment_order_items.id`
- `payment_attempt_id` nullable FK -> `payment_attempts.id`
- `entitlement_type`
- `resource_type`
- `resource_ref_id`
- `status`
- `granted_at`
- `effective_from`
- `expires_at`
- `revoked_at`
- `grant_data_json`
- `created_at`
- `updated_at`

Relationships:

- `User 1-N PaymentEntitlement`
- `PaymentOrder 1-N PaymentEntitlement`
- `PaymentOrderItem 1-1 PaymentEntitlement`
- optional `PaymentAttempt 1-N PaymentEntitlement`

Indexes and constraints:

- unique `payment_order_item_id`
- index `(user_id, status)`
- index `(resource_type, resource_ref_id)`

Notes:

- Initial `entitlement_type` values:
  - `shared_deck_install`
  - `shared_note_type_install`
- Initial `resource_type` values:
  - `deck_marketplace_item`
  - `note_type`
- `grant_data_json` stores fulfillment outputs, for example:
  - `deck_install_id`
  - `local_deck_id`
  - `note_type_install_id`
  - `installed_note_type_id`

### 5.7 Provider-agnostic vs VietQR-specific data

Provider-agnostic fields:

- `payment_orders.*`
- `payment_order_items.*`
- `payment_attempts.provider_code`
- `payment_attempts.status`
- `payment_attempts.amount_minor`
- `payment_attempts.currency_code`
- `payment_attempts.checkout_url`
- `payment_webhook_events.event_key`
- `payment_webhook_events.payload_json`
- `payment_entitlements.*`

VietQR-specific or likely VietQR-specific fields:

- `payment_attempts.expected_payment_reference`
- `payment_attempts.provider_order_code`
- `payment_attempts.provider_payment_id`
- `payment_transactions.provider_transaction_ref`
- `payment_transactions.payment_reference_text`
- `payment_transactions.counterparty_*`
- callback payload keys such as:
  - `orderCode`
  - `paymentLinkId`
  - `reference`
  - `description`
  - `transactionDatetime`
  - `accountNumber`
  - `counterAccountName`
  - `counterAccountNumber`
  - `counterAccountBankName`

Assumption:

- exact payload fields depend on which VietQR-capable provider is chosen. The implementation must map real provider fields into the generic schema without hard-coding provider-only semantics into table names.

## 6. Status/state transition matrix

Any transition not listed below is invalid.

### 6.1 `payment_orders.status`

| From | To | Trigger | Actor | Notes |
|---|---|---|---|---|
| none | `pending_payment` | order creation | user API | first paid checkout created |
| `pending_payment` | `paid` | exact success confirmation | webhook service | only when payment matches one order exactly |
| `pending_payment` | `under_review` | ambiguous or mismatched callback | webhook service | amount mismatch, reference mismatch, or multiple candidates |
| `pending_payment` | `expired` | active attempt expired and no success | scheduled CLI or lazy expiry | use new CLI command, not in-route ad hoc logic |
| `pending_payment` | `canceled` | user/admin cancel | user action or admin action | only before successful confirmation |
| `pending_payment` | `failed` | final provider/business failure | admin action or provider flow | use when no further attempt should be allowed |
| `under_review` | `paid` | manual approval or exact late-match resolution | admin action or webhook service | only after review passes |
| `under_review` | `failed` | manual rejection | admin action | payment not accepted |
| `under_review` | `canceled` | admin closure | admin action | close without grant |
| `under_review` | `expired` | review timed out with no approval | scheduled CLI or admin action | optional operational policy |
| `expired` | `pending_payment` | user retries and a new attempt is created | user API | same order may be reopened or a new order may be created; pick one policy and keep it consistent |
| `expired` | `paid` | late callback exact match | webhook service | allowed only when no conflicting confirmed order exists |
| `expired` | `under_review` | late callback ambiguous | webhook service | store payment, require review |
| `paid` | `refunded` | future refund flow | admin action or provider flow | not MVP |

Explicit invalid examples:

- `paid -> pending_payment`
- `paid -> canceled`
- `failed -> paid`
- `canceled -> paid`
- `refunded -> paid`

### 6.2 `payment_orders.grant_status`

| From | To | Trigger | Actor | Notes |
|---|---|---|---|---|
| none | `pending` | order creation | user API | default on paid order creation |
| `pending` | `completed` | successful entitlement creation and fulfillment | payment service | preferred normal path |
| `pending` | `failed` | fulfillment failure after payment confirmation | payment service | should be rare if transaction boundary is implemented correctly |
| `failed` | `completed` | retry grant succeeds | admin action or scheduled CLI | idempotent retry path |

Explicit invalid examples:

- `completed -> pending`
- `completed -> failed` without a separate revoke/refund process

### 6.3 `payment_attempts.status`

| From | To | Trigger | Actor | Notes |
|---|---|---|---|---|
| none | `created` | attempt row initialized | payment service | before or during provider request |
| `created` | `pending` | provider link/QR prepared | payment service | checkout ready |
| `created` | `failed` | provider init failed | payment service | no usable QR or checkout link |
| `pending` | `confirmed` | exact success callback | webhook service | signature valid or trusted provider channel |
| `pending` | `manual_review` | mismatch or ambiguity | webhook service | do not discard callback |
| `pending` | `expired` | no success before `expires_at` | scheduled CLI or lazy expiry | do not auto-delete |
| `pending` | `canceled` | user/admin cancel | user action or admin action | before confirmation |
| `pending` | `failed` | explicit provider failure | provider flow or admin action | only when provider sends a terminal failure |
| `manual_review` | `confirmed` | review approves payment | admin action | after manual verification |
| `manual_review` | `failed` | review rejects payment | admin action | payment not accepted |
| `manual_review` | `canceled` | admin closes attempt | admin action | close without grant |
| `expired` | `confirmed` | late callback exact match | webhook service | allowed only if no conflicting confirmed payment exists |
| `expired` | `manual_review` | late callback ambiguous | webhook service | reconciliation needed |
| `confirmed` | `refunded` | future refund flow | admin action or provider flow | not MVP |

Explicit invalid examples:

- `confirmed -> pending`
- `confirmed -> created`
- `failed -> confirmed`
- `canceled -> confirmed`

### 6.4 `payment_entitlements.status`

| From | To | Trigger | Actor | Notes |
|---|---|---|---|---|
| none | `pending` | entitlement row created | payment service | may only be visible transiently if same transaction completes |
| `pending` | `active` | fulfillment succeeds | payment service | normal path |
| `pending` | `revoked` | admin cancels before activation | admin action | uncommon |
| `active` | `expired` | time-bound grant ends | scheduled CLI | future subscription/service use |
| `active` | `revoked` | fraud or manual removal | admin action | remove access |
| `active` | `refunded` | payment refunded and access withdrawn | admin action or provider flow | future flow |

Explicit invalid examples:

- `active -> pending`
- `expired -> active` without a new order or explicit restore policy
- `refunded -> active`

### 6.5 `payment_webhook_events.processing_status`

| From | To | Trigger | Actor | Notes |
|---|---|---|---|---|
| none | `received` | raw callback persisted | webhook route | first DB write |
| `received` | `processed` | business logic completed | payment service | includes exact success and manual-review outcomes |
| `received` | `ignored` | callback authenticated but unsupported or irrelevant | payment service | for example provider ping or unusable event |
| `received` | `failed` | processing exception | payment service | error stored for replay or manual handling |

Explicit invalid examples:

- `processed -> received`
- `ignored -> processed`

Duplicate callback policy:

- duplicates should be stopped by unique `(provider_code, event_key)` before a second event row is inserted
- duplicate delivery does not create a separate `duplicate` state row in MVP

## 7. Webhook/callback processing sequence

### 7.1 Target endpoint shape

Add a provider callback endpoint under the new payments domain, for example:

- `POST /api/payments/providers/vietqr/webhook`

This route must not depend on session auth.

### 7.2 Processing sequence

1. Read raw request body, headers, provider route params, and remote IP.
2. Validate provider identity at the HTTP layer:
   - signature header if provider supports signatures
   - webhook token if provider uses a shared secret token
3. Parse payload into a provider-normalized event object.
4. Derive `event_key`.
   - prefer provider event id
   - fallback to deterministic hash of stable transaction fields
5. Transaction A: persist raw callback first.
   - insert `payment_webhook_events` with:
     - `provider_code`
     - `event_key`
     - `event_type`
     - `signature_valid`
     - `payload_json`
     - `processing_status='received'`
     - `received_at`
   - commit immediately
   - if unique conflict on `(provider_code, event_key)`, return `2xx` and stop
6. Resolve the best target attempt and order.
   - strongest key: provider payment id
   - next: provider order code
   - fallback: expected payment reference plus exact amount
7. Transaction B: process the event atomically.
   - lock the target `payment_attempts` row with `SELECT ... FOR UPDATE`
   - lock the parent `payment_orders` row with `SELECT ... FOR UPDATE`
   - if `payment_transactions` is present, upsert immutable transaction observation
   - validate:
     - exact amount match
     - exact or deterministic reference match
     - one and only one target order/attempt
     - order not already in conflicting terminal state
   - if validation fails but the event is still a real transfer, move attempt/order into review state
   - if validation passes and provider result is successful:
     - move attempt to `confirmed`
     - move order to `paid`
     - create one `payment_entitlements` row per `payment_order_items` row
     - run domain fulfillment
     - set entitlement rows to `active`
     - set order `grant_status='completed'`
     - set `payment_webhook_events.processing_status='processed'`
     - set `processed_at`
   - commit
8. On exception during Transaction B:
   - rollback Transaction B
   - Transaction C: update the already-persisted event row to `failed` with `error_message`
   - return a non-2xx only if the provider requires retry behavior; otherwise return controlled `2xx` once failure is safely logged

### 7.3 What must happen in one DB transaction

The following must happen together in Transaction B:

- locked read of target order and attempt
- status transitions on `payment_attempts`
- status transitions on `payment_orders`
- entitlement creation
- domain fulfillment
- entitlement activation
- webhook event status update

Reason:

- the system must not commit `paid` without a matching grant
- the system must not grant access twice when duplicate callbacks race

### 7.4 What can be retried safely

Safe retries:

- duplicate webhook delivery: blocked by unique `event_key`
- same provider transaction replay: blocked by unique `provider_transaction_ref`
- entitlement retry for `grant_status='failed'`: blocked by unique `payment_order_item_id`
- deck install retry: blocked by existing `DeckInstall(deck_item_id, user_id)` uniqueness
- note type install retry: blocked by existing `NoteTypeInstall(source_note_type_id, user_id)` uniqueness

Unsafe retries:

- route-level helpers that own their own commit
- ad hoc retries that bypass locked order/attempt reads

### 7.5 Locking strategy

Use MySQL row locks in payment service code:

- lock `payment_attempts` target row with `FOR UPDATE`
- lock parent `payment_orders` row with `FOR UPDATE`
- when creating or reusing a pending order for the same user/product, lock the candidate order rows before deciding whether to reuse or create a new one

Why this matters in this repo:

- current code already has retry logic for MySQL deadlocks in shared deck install flows
- payment confirmation adds another concurrency hotspot and must not rely on best-effort application checks alone

### 7.6 Idempotency strategy

Primary idempotency barriers:

- unique `(provider_code, event_key)` on `payment_webhook_events`
- unique `(provider_code, provider_transaction_ref)` on `payment_transactions`
- unique `payment_entitlements.payment_order_item_id`
- existing domain uniqueness on install rows

Secondary idempotency rules:

- if a `paid` order already has `grant_status='completed'`, a repeated exact-success callback should only attach to audit/event history and then return success
- order creation for paid install should reuse an existing non-terminal unpaid order for the same user and product instead of creating unlimited duplicates

### 7.7 Expiration policy

Because the repo has no internal job runner, implement expiration as both:

- explicit CLI command, for example `flask --app wsgi.py payments-expire-stale`
- lazy expiry check when reading or reusing pending orders

Attempt expiration rule:

- if `payment_attempts.status in ('created', 'pending')`
- and `expires_at < now`
- and there is no successful transaction linked to the attempt
- then mark attempt `expired`

Order expiration rule:

- if the active attempt for the order expires
- and there is no other non-terminal attempt on that order
- and the order is not already `paid`, `under_review`, `canceled`, or `failed`
- then mark order `expired`

### 7.8 Late-callback policy

Late callbacks must never be discarded silently.

Auto-confirm late callback when all are true:

- callback resolves to exactly one attempt/order
- amount matches exactly
- transfer/reference token matches exactly
- no other confirmed or refunded payment already owns that provider transaction
- order is not canceled for business reasons that should block acceptance

Move to manual review when any are true:

- amount mismatch
- reference token mismatch
- callback matches more than one unpaid order
- callback arrives after a replacement attempt has already been confirmed
- provider signature is missing or not trustworthy and the provider does not give a stable payment id

Do not auto-grant when:

- order is already refunded
- callback is for a canceled order that should stay closed
- callback cannot be mapped to one order safely

## 8. Entitlement and fulfillment flow

### 8.1 Free vs paid split

Free content:

- preserve current behavior for:
  - `POST /api/shared/note-types/<id>/install`
  - `POST /api/shared/decks/<id>/install`
- the current install logic remains the source of truth
- no payment rows are created

Paid content:

- the same install endpoints become the interception point
- when `pricing_mode == 'paid'`, do not create `DeckInstall` or `NoteTypeInstall` in the request path
- instead:
  1. check for existing fulfilled access first
  2. reuse an existing unpaid order if one already exists
  3. otherwise create a new `payment_orders` + `payment_order_items` + `payment_attempts`
  4. return payment payload to the client

### 8.2 Recommended route behavior for existing install endpoints

For note type install route:

- if free: preserve current `201` install behavior
- if paid and already installed: return existing installed payload
- if paid and payment system enabled: return `202` with order and checkout info
- if paid and payment system disabled: return a safe error such as `PAYMENT_UNAVAILABLE`; never fall back to blind direct install

For deck install route:

- same split as note type install

This preserves the current UI seam while moving paid access control into the payment domain.

### 8.3 Fulfillment sequence after successful payment

1. order and attempt are confirmed
2. create `payment_entitlements` rows in `pending`
3. run product-specific fulfillment
4. write fulfillment outputs into `grant_data_json`
5. mark entitlements `active`
6. mark order `grant_status='completed'`

### 8.4 Deck fulfillment

Use:

- `install_shared_deck_item_for_user(...)`

Rules:

- call it from payment service, not from the route
- keep it inside the payment transaction
- capture returned values in entitlement metadata:
  - `deck_install_id`
  - `local_deck_id`
  - any other stable install identifiers needed for audit

### 8.5 Note type fulfillment

Use:

- `ensure_note_type_install_for_user(...)`

Rules:

- call it from payment service, not from the route
- keep it inside the payment transaction
- capture returned values in entitlement metadata:
  - `note_type_install_id`
  - `installed_note_type_id`

### 8.6 Existing install snapshot fields

`DeckInstall.purchase_price_cents`, `DeckInstall.purchased_at`, `NoteTypeInstall.purchase_price_cents`, and `NoteTypeInstall.purchased_at` may remain for history, but they stop being payment proof.

Implementation rule:

- payment proof lives in:
  - `payment_attempts`
  - `payment_webhook_events`
  - `payment_entitlements`
- install snapshot fields become informational only

## 9. API and service-layer impact

### 9.1 New route surface

Core payment routes in `app/routes/payments.py`:

- `POST /api/payments/orders`
- `GET /api/payments/orders/<order_id>`
- `POST /api/payments/orders/<order_id>/cancel`
- `POST /api/payments/providers/vietqr/webhook`

Optional later route:

- `POST /api/payments/orders/<order_id>/retry`

Existing marketplace install routes that gain interception:

- `POST /api/shared/note-types/<note_type_id>/install`
- `POST /api/shared/decks/<deck_item_id>/install`

### 9.2 New service responsibilities

`app/services/payment_service.py` should own:

- creating or reusing paid orders for marketplace products
- creating provider attempts
- building expected transfer reference strings
- mapping provider payloads into normalized events
- webhook processing
- order and attempt state transitions
- entitlement creation and fulfillment orchestration
- expiration CLI handlers
- retry-grant CLI or admin actions

### 9.3 New repository responsibilities

`app/repositories/payment_repository.py` should own:

- order lookup by user/product/status
- attempt lookup by provider identifiers
- `FOR UPDATE` loading helpers
- webhook event insert and duplicate handling
- transaction upsert helpers
- entitlement lookup and retry helpers

### 9.4 Admin and backoffice scope

Backoffice should be server-rendered Jinja, consistent with the rest of the repo.

Recommended admin pages or APIs:

- orders list
- order detail
- attempts list for an order
- webhook event log
- manual review queue
- retry-grant action
- mark review approved / rejected

Recommended file placement:

- `app/routes/admin_payments.py`
- `templates/admin/payments_*.html`

Reason:

- avoid growing `app/routes/admin.py`, which is already large
- keep payment admin routes isolated from user-role and TTS admin logic

### 9.5 CLI additions

Add Flask CLI commands, because the repo already uses CLI for maintenance:

- `payments-expire-stale`
- `payments-retry-grants`
- optional `payments-replay-webhook --event-id <id>`

### 9.6 Test impact

Add focused tests modeled after existing integration tests:

- `tests/test_payment_order_flow.py`
- `tests/test_payment_webhook_idempotency.py`
- `tests/test_payment_manual_review.py`

Critical regression coverage:

- free shared note type install still works
- free shared deck install still works
- paid install returns order payload instead of install payload
- successful webhook creates exactly one entitlement and one install
- duplicate webhook does not duplicate installs or entitlements
- mismatch webhook goes to review state
- stale expiry command marks pending attempts expired
- late exact callback follows the defined late-callback policy

## 10. Migration and rollout plan

### 10.1 Schema rollout order

Phase 0:

- audit production and staging for published paid items in:
  - `note_types`
  - `deck_marketplace_items`
- do not enable new paid purchase UX until payment gate exists

Phase 1:

- add payment model files
- add defensive Alembic revision for core MVP tables:
  - `payment_orders`
  - `payment_order_items`
  - `payment_attempts`
  - `payment_webhook_events`
  - `payment_entitlements`

Phase 2:

- add payment repository and service
- register payment blueprint
- keep all payment feature flags off

Phase 3:

- add paid install interception in existing shared install routes
- still keep enforcement flags off in production

Phase 4:

- add admin/backoffice and CLI maintenance

Phase 5:

- add `payment_transactions` in a follow-up Alembic revision if MVP was intentionally kept smaller

### 10.2 Defensive migration rules for this repo

Because `create_app()` calls `db.create_all()` before normal app use:

- every payment migration revision must check:
  - table existence
  - column existence
  - index existence
- do not rely on a clean Alembic-only bootstrap path
- do not make destructive schema edits in the same release as the first payment tables

### 10.3 Feature flag stages

Recommended stage flags:

- `PAYMENTS_V1_ENABLED`
- `PAYMENTS_PAID_INSTALL_REQUIRED`
- `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED`

Stage A: schema-only deploy

- all flags off
- app code can load new models safely
- no route behavior change for free content

Stage B: staging order creation

- `PAYMENTS_V1_ENABLED=1`
- `PAYMENTS_PAID_INSTALL_REQUIRED=0`
- `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED=0`
- test direct order creation APIs without marketplace interception

Stage C: staging webhook auto-grant

- `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED=1`
- validate webhook confirmation, duplicate protection, and manual-review routing

Stage D: staging paid install interception

- `PAYMENTS_PAID_INSTALL_REQUIRED=1`
- existing install routes for paid products now return order/checkout payload instead of direct install

Stage E: production schema deploy

- deploy same code
- run `flask --app wsgi.py db upgrade`
- verify app boot completes cleanly after startup side effects
- keep paid interception disabled until validation finishes

Stage F: production payment enablement

- turn on `PAYMENTS_V1_ENABLED`
- validate provider connectivity and webhook delivery
- only then turn on `PAYMENTS_PAID_INSTALL_REQUIRED`
- only then allow publishing paid marketplace items

### 10.4 Safe deployment sequence

1. Backup the production database.
2. Deploy the release artifact containing:
   - payment models
   - defensive Alembic revision
   - payment service/repository
   - feature flags defaulting to off
3. Run `flask --app wsgi.py db upgrade` using that release artifact.
4. Start one application instance and watch startup logs for:
   - schema patcher errors
   - clone cutover warnings
   - payment model import or migration errors
5. Run staging or production smoke checks.
6. Only after validation, enable payment flags in stages.

### 10.5 Staging validation checklist

- `flask --app wsgi.py db upgrade` succeeds
- app boots successfully via:
  - `flask --app wsgi.py run`
  - container path if used
- free note type install still returns install rows only
- free deck install still returns install rows only
- paid note type install returns order payload and does not create `NoteTypeInstall` yet
- paid deck install returns order payload and does not create `DeckInstall` yet
- success webhook:
  - creates one entitlement per line item
  - creates the correct install row
  - sets order `paid`
  - sets grant status `completed`
- duplicate webhook:
  - returns safe success
  - creates no duplicate entitlements
  - creates no duplicate install rows
- mismatch webhook:
  - stores raw event
  - does not grant access
  - moves order/attempt to review state
- expiry CLI:
  - expires stale pending attempts
- late callback policy behaves as defined
- shared deck overlay install behavior is unchanged after successful paid fulfillment

## 11. Rollback and operational safeguards

### 11.1 Rollback principle

Rollback means:

- disable new payment behavior
- preserve all payment history
- never delete financial rows

### 11.2 Safe rollback behavior

If payment rollout must be disabled after go-live:

- keep `PAYMENTS_V1_ENABLED=0`
- keep `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED=0`
- for paid install endpoints, return `PAYMENT_UNAVAILABLE`
- do not fall back to the old blind direct-install path for paid products

This is stricter than the pre-payment code, but it avoids granting paid content without payment proof.

### 11.3 Operational safeguards

- Never use `dev-purge-data --yes` in any environment where payment history matters.
- Log and monitor:
  - webhook processing failures
  - manual-review counts
  - grant retry counts
  - duplicate event conflicts
- Keep webhook raw payload retention long enough for dispute handling and debugging.
- Ensure provider credentials are not stored in public config tables.

### 11.4 Recovery tools

Minimum recovery tools:

- admin retry grant
- CLI retry grant
- admin manual review approve/reject
- CLI expire stale attempts

Optional later recovery tool:

- replay a stored webhook event by id after a bug fix

## 12. Risks, assumptions, and open questions

### 12.1 Risks

- Current startup side effects increase schema rollout risk.
- Payment confirmation depends on strong transaction boundaries, but the repo currently has uneven commit ownership.
- Existing `flashcards_share_service.py` is already overloaded; payment logic must only call into it at narrow fulfillment seams.
- Existing marketplace price semantics are inconsistent:
  - VNĐ in publish UI
  - USD-like formatting in serializer display
- If the chosen VietQR-capable provider does not send stable callback identifiers or trustworthy signatures, manual review volume may be high.

### 12.2 Assumptions

- Assumption: the chosen VietQR provider supports callback delivery or transaction-feed delivery that is good enough to drive asynchronous confirmation.
- Assumption: v1 only needs one-time purchases for marketplace note types and shared decks.
- Assumption: there is no need for org/team billing in v1 because the repo has no tenant model.
- Assumption: v1 can stay env-driven for provider credentials and receiving account config.
- Assumption: no background worker will be introduced for this rollout; CLI plus synchronous webhook processing is acceptable.

### 12.3 Open questions

- Which exact VietQR-capable provider will be used in production?
  - VietQR Payment Request style link
  - direct bank-feed via Casso-like provider
  - another VietQR-compatible gateway
- Does the provider send:
  - a stable event id
  - a stable payment link id
  - a stable transaction reference
  - a signature header
- Should expired orders be reopened in place, or should user retry create a brand new order?
- Should paid content remain install-only products, or will non-install services/features be sold in the same rollout?
- Is `payment_transactions` required in MVP, or acceptable as revision B after core order/callback flow is stable?

## 13. Minimal viable scope vs future-ready scope

### 13.1 Minimal viable scope

Deliver in the first safe rollout:

- new payment domain modules
- new core tables:
  - `payment_orders`
  - `payment_order_items`
  - `payment_attempts`
  - `payment_webhook_events`
  - `payment_entitlements`
- env-driven VietQR provider config
- paid install interception for:
  - note types
  - shared decks
- synchronous webhook confirmation
- generic entitlement ledger
- domain fulfillment through:
  - `ensure_note_type_install_for_user(...)`
  - `install_shared_deck_item_for_user(...)`
- CLI jobs for:
  - stale expiry
  - grant retry
- free install flow unchanged

What MVP does not need:

- refund processing
- multi-item marketplace carts
- org/team billing
- admin-managed provider config
- hard links from install rows back to entitlement rows

### 13.2 Future-ready scope

Add after MVP is stable:

- `payment_transactions` if deferred
- multi-item orders and bundles
- refund and cancel workflows
- subscription or time-bound entitlements
- provider config table if payment providers become admin-managed
- optional nullable backlink columns from:
  - `deck_installs`
  - `note_type_installs`
  - to the entitlement that created them
- richer reconciliation and replay tooling

### 13.3 Final recommendation

For this repository, the correct design is not a single `payments` table and not a full catalog rewrite.

The pragmatic choice is:

- keep the existing catalog where it is
- add an explicit order boundary
- add provider attempts and webhook logging
- add a generic entitlement ledger
- reuse existing install models as fulfillment rows

That is the smallest design that fixes the current "paid but not actually paid" gap without broad destructive changes to `User`, the flashcards overlay model, or the current marketplace catalog.
