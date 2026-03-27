# Legacy Payment Expansion Note

Date: 2026-03-28
Status: superseded

This file used to contain a design-stage payment expansion plan written before the repository fully converged on payOS.

It is no longer the canonical source of truth for payment architecture.

Why it was superseded:

- it mixed provider-neutral design with VietQR-oriented assumptions
- it documented `PAYMENTS_VIETQR_*` env vars that are not part of the current setup direction
- it described `/api/payments/providers/vietqr/webhook`, which is not part of the intended payOS-first architecture
- it discussed `payment_transactions` as a target table even though the live repository currently centers payment operations on `PaymentOrder`, `PaymentOrderItem`, `PaymentAttempt`, `PaymentWebhookEvent`, and `PaymentEntitlement`

Use this file only as historical context when you need to understand earlier design thinking.

For current work, use:

- `docs/FLAMA_PAYMENT_ARCHITECTURE.md`
- `docs/SYSTEM_ARCHITECTURE.md`
- `.env_example`
- `app/routes/payments.py`
- `app/services/payment_service.py`
- `app/services/payment/provider/payos_provider.py`

Contributor rule:

- do not restore VietQR-specific env vars, route names, or documentation from the older plan unless there is a new explicit product decision
