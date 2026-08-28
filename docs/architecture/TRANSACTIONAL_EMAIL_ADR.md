# Transactional Email Provider and Delivery ADR

Status: accepted for Phase 2 implementation; production rollout remains gated on domain and
credential setup.  
Decision date: 2026-08-28.

## Decision

Flama will own the email contract, rendering, environment guards, and template sources.
Business services must call the shared email service and must not import a provider SDK or SMTP
client directly.

The transactional delivery layer standardizes directly on the **Resend HTTP API adapter** (`ResendHttpProvider`).
The intermediate Cloudflare Worker gateway was removed in favor of direct, typed provider integration.
The provider boundary remains replaceable so AWS SES, Postmark, or dedicated SMTP can be introduced in the future
without rewriting password reset, identity, payment, or moderation services.

Reasons for standardizing on Resend:

- Resend offers a mature direct API, idempotency key, provider message ID, and delivery events;
- Avoids extra hop and separate operational maintenance of an intermediate Cloudflare Worker proxy;
- Native compatibility with Python standard library HTTP client without external SDK dependencies;
- Robust HTML/text rendering and environment safety controls (allowlist / redirect / fail-closed).

Primary sources:

- [Resend transactional pricing](https://resend.com/docs/knowledge-base/what-is-resend-pricing)
- [Resend domain verification](https://resend.com/docs/dashboard/domains/introduction)
- [Resend sending regions](https://resend.com/docs/dashboard/domains/regions)
- [Resend send API and idempotency](https://resend.com/docs/api-reference/emails/send-email)
- [Resend delivery event types](https://resend.com/docs/webhooks/event-types)

## Alternatives

**AWS SES** has materially lower raw per-message cost and strong AWS-native event publishing. It
also requires more account, sandbox, IAM/SMTP, configuration-set, and deliverability operations.
It becomes the preferred cost review when Flama's volume or existing AWS footprint justifies that
overhead. See [SES pricing](https://aws.amazon.com/ses/pricing/) and
[SES event publishing](https://docs.aws.amazon.com/ses/latest/dg/event-publishing-send-email.html).

**Postmark** is a strong transactional-delivery alternative with SMTP/API support, message
streams, authentication features, and event webhooks. Its developer allowance is smaller than
Resend's current low-volume allowance. See [Postmark pricing](https://postmarkapp.com/pricing/)
and [Postmark webhooks](https://postmarkapp.com/developer/api/webhooks-api).

Personal Gmail, Gmail via Cloudflare Worker proxy, or personal mailbox credentials are explicitly
rejected for production architecture.

## Phase 2 contract

Implement now:

- typed transactional message and rendered-message contracts;
- a version-controlled HTML and plain-text renderer;
- memory/fake delivery for tests;
- a safe local logging or disabled provider that never logs message bodies or tokens;
- Resend direct HTTP adapter with bounded timeout and idempotency-key support;
- recipient redirect/allowlist guards outside production;
- configuration validation and focused tests;
- template keys for password reset and password-changed notifications.

Do not implement in this phase:

- a public preview/send endpoint;
- production DNS mutations or secret creation;
- a database outbox or background worker before the persistence contract is approved;
- provider webhooks, suppression state, or an admin delivery dashboard;
- marketing email.

Synchronous delivery is a temporary Phase 2 seam. Security flows must expose delivery failure to
their orchestrator without leaking account existence or token values. Password changes and
payment state must not roll back solely because a notification fails.

## Configuration contract

All values come from environment-backed Flask config:

- `EMAIL_ENABLED`
- `EMAIL_PROVIDER` (`memory`, `disabled`, or `resend`)
- `EMAIL_ENVIRONMENT` (`test`, `local`, `staging`, or `production`)
- `EMAIL_FROM_ADDRESS`
- `EMAIL_FROM_NAME`
- `EMAIL_REPLY_TO`
- `EMAIL_RECIPIENT_ALLOWLIST`
- `EMAIL_REDIRECT_ALL_TO`
- `EMAIL_RESEND_API_KEY`
- `EMAIL_PROVIDER_TIMEOUT_SECONDS`
- `EMAIL_PROVIDER_MAX_ATTEMPTS`
- `EMAIL_PROVIDER_RETRY_BACKOFF_SECONDS`
- `PUBLIC_APP_URL`

Production must fail closed if email is enabled but the selected provider credential, sender, or
canonical public URL is missing. Non-production must not send to arbitrary recipients unless an
allowlist or redirect policy explicitly permits them.

## Production gate

Production email remains blocked until all items pass:

1. Choose a transactional sending subdomain under the official Flama domain.
2. Verify the provider-supplied SPF and DKIM records.
3. Add and monitor DMARC, beginning with a reporting policy before stronger enforcement.
4. Confirm From, Reply-To, return-path, and support-address ownership.
5. Store the provider API key only in the deployment secret environment.
6. Send staging tests through a recipient allowlist or redirect.
7. Verify HTML and plain-text delivery without leaking reset tokens in logs.
8. Document key rotation and rollback.

Webhook delivery state, database outbox, bounce/complaint suppression, and operational metrics are
follow-up phases. The synchronous seam retries only transient failures with a bounded exponential
backoff; permanent failures are never retried. `sent` means provider acceptance, never proof of
mailbox delivery.
