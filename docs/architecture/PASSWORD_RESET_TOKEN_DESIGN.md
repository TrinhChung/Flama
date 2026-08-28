# Password Reset Token Database Design

> Date: 2026-08-28 | Mode: DESIGN | Engine: MySQL 8.0 (OLTP)

## Invariants

- A reset secret is cryptographically random and expires after a configured interval.
- The database stores only its SHA-256 digest, never the secret placed in the URL.
- A token can be used successfully at most once.
- Issuing a new token revokes every still-active older token for the same user.
- Password update and token consumption commit in the same database transaction.

## Observed state

Before this change, `app/services/identity_api_service.py` generated a signed,
stateless token. Expiration was enforced, but the token could not be revoked and
could be reused until expiration. There was no password-reset persistence model
or migration.

## Alternatives considered

1. Continue using a signed stateless token and add a password-version claim.
   This avoids a table, but still couples revocation to user state and provides
   little operational visibility.
2. Store an opaque random token digest in a dedicated table. This adds a small
   indexed write per request and gives explicit expiry, revocation, and one-time
   consumption semantics.

The dedicated table is selected. Password reset is a low-volume security flow,
so its small write amplification is preferable to implicit revocation state.

## Target schema and lifecycle

`password_reset_tokens` is the authoritative reset-token state. It is owned by
`users` through a foreign key with `ON DELETE CASCADE`. `token_hash` is unique;
`user_id` and active-state fields support revocation; `expires_at` supports
periodic cleanup.

The migration is an additive expand step and requires no backfill. Application
code begins writing and reading the table after deployment. A future cleanup job
may delete expired/consumed rows without changing the authentication contract.
