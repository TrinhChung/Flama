# Task — Student email verification and Marketplace student benefits

> **Trạng thái:** [x] ĐÃ HOÀN THÀNH (Completed)  
> **Ngày hoàn thành:** 2026-08-28  
> **Target branch:** `develop`  
> **Type:** Product / Frontend / Backend / Marketplace / Account verification  
**Dependency:** Implement **after Google Login / Google Sign-In task** is completed.

## Goal

Introduce a reliable student-status foundation based on verified education email addresses, starting with Vietnamese education domains ending in `.edu.vn`, and allow Marketplace creators to offer student-specific pricing for shared decks.

The feature must not trust an email address merely because it is stored on the account. Student benefits are available only after the email has been verified.

---

## 1. Registration screen — small student hint

On the sign-up screen, add a small non-intrusive hint near the email field:

> Sinh viên? Hãy sử dụng email trường có đuôi `.edu.vn` để có thể nhận các ưu đãi dành cho sinh viên trên Flama.

Requirements:

- This is only a hint, not a requirement to register.
- Normal email addresses continue to work.
- Do not make the registration UI heavier with a large banner/modal.
- After Google Sign-In is available, show the same concept consistently for both normal registration and Google registration when relevant.
- Do not claim the user is a student until the email verification/student eligibility check has succeeded.

---

## 2. Add real email verification state

Current assumption for migration:

- Existing accounts were created before Flama had email-code verification.
- Therefore, **all existing stored emails must initially be treated as unverified** unless there is a deliberately trusted verification source introduced by this task.
- Do not infer `verified = true` simply because the account has been used for a long time.

Introduce explicit account verification state, for example:

```text
email
email_verified_at
email_verification_source
```

or an equivalent model that fits the current account architecture.

Possible verification sources should be extensible, e.g.:

```text
email_code
google_oauth
admin
```

### Email/password registration

Add email verification after signup using a one-time code or secure verification link.

Expected flow:

```text
register
→ account/session can be created according to the existing onboarding design
→ email status = unverified
→ send verification code/link
→ user verifies
→ email_verified_at is set
→ student eligibility can then be evaluated
```

Research resend limits, expiration, brute-force protection and rate limits before implementation.

### Google Login dependency

Because this task is scheduled after Google Login:

- investigate whether a Google identity with `email_verified = true` can safely count as verified email for Flama;
- if accepted, persist the verification source as Google rather than pretending Flama sent an email code;
- historical accounts must still remain unverified unless they subsequently complete an accepted verification flow.

Do not silently mark every existing Gmail/Google-looking address as verified.

---

## 3. Student eligibility model

Phase 1 eligibility rule:

```text
email is verified
AND
normalized email domain ends with `.edu.vn`
```

Examples that should be researched/tested:

```text
student@university.edu.vn
student@sv.university.edu.vn
```

The implementation should NOT spread `endsWith('.edu.vn')` checks throughout frontend/backend code.

Create a centralized eligibility/domain policy so Flama can later support:

- additional Vietnamese university domains;
- university allowlists/exceptions;
- other countries;
- manual/admin verification;
- expiration/re-verification rules if needed.

Suggested conceptual output:

```text
student_status:
- not_eligible
- eligible_unverified_email
- verified_student
```

Exact schema is open for research.

Important: the server is the source of truth for student eligibility.

---

## 4. Account/Profile UI — verification status

Where account email/profile settings are shown, display a clear email status:

```text
Email chưa xác thực
Email đã xác thực
Sinh viên đã xác thực
```

If unverified:

- provide Verify email / Resend verification action;
- explain that student benefits cannot be used until verification completes.

Do not expose internal verification metadata unnecessarily.

---

## 5. Shared Deck creator settings — student benefit

In the create/edit Shared Deck / Marketplace publishing flow, extend the pricing/distribution step.

Current concepts such as:

```text
Free
Paid
```

should remain, but paid creators can optionally configure a student offer.

Suggested UI:

```text
Ưu đãi dành cho sinh viên

( ) Không có ưu đãi
( ) Miễn phí cho sinh viên
( ) Giảm giá cho sinh viên
```

When `Giảm giá cho sinh viên` is selected:

```text
Discount: [ X ] %
```

Validate a sensible range such as `1–100`, with `100%` either normalized to student-free or disallowed in favor of the explicit Free for students option.

If the deck itself is already globally free, hide/disable student pricing because it has no additional effect.

### Creator explanation

Show a short explanation near the option:

> Flama chỉ áp dụng ưu đãi này cho tài khoản đã được xác thực là sinh viên. Giai đoạn đầu, hệ thống xác định sinh viên thông qua email trường đã xác thực có tên miền `.edu.vn`.

Also make clear that simply typing an `.edu.vn` address does not qualify without verification.

---

## 6. Suggested Marketplace pricing model

Research and introduce a model equivalent to:

```text
pricing_mode: free | paid
base_price
student_offer_mode: none | free | percent_discount
student_discount_percent: nullable
```

Do not store only a computed student price if that makes later price edits ambiguous.

Rules should be calculated server-side.

Examples:

```text
Base price: 100,000 VND
Student offer: 30%
Verified student price: 70,000 VND
```

```text
Base price: 100,000 VND
Student offer: free
Verified student price: 0 VND
```

Non-verified users always use normal Marketplace pricing.

---

## 7. Marketplace deck card/detail UX

For decks with a student benefit, surface it without overcrowding the card.

Possible lightweight badge:

```text
Ưu đãi sinh viên
```

The detail page should explain the exact offer, for example:

```text
Miễn phí cho sinh viên đã xác thực
```

or:

```text
Sinh viên đã xác thực được giảm 30%
```

For an eligible but unverified account, show a CTA such as:

```text
Xác thực email trường để nhận ưu đãi
```

For a verified student, show both normal price and actual student price when useful.

Do not reveal discounts by changing only the final number with no explanation.

---

## 8. Checkout/install authorization

Student pricing must never be decided only in React.

At checkout/install time the backend must re-check:

```text
current authenticated user
→ verified email status
→ student eligibility policy
→ deck student offer
→ final authorized price/access
```

A modified client request must not be able to submit:

```text
is_student = true
student_price = 0
```

and receive the benefit.

For `free for students`, installation authorization should still generate the normal ownership/install records expected by Marketplace rather than bypassing those systems.

---

## 9. Existing users migration

Because current accounts did not go through Flama email verification:

- migration/default state for existing users is **unverified**;
- no existing `.edu.vn` account automatically receives student pricing merely because of its current email field;
- user must complete verification or a trusted provider verification flow;
- preserve account access — this migration must not lock existing users out of Flama.

The rollout should distinguish:

```text
authentication/access to Flama
```

from:

```text
email verified / eligible for student benefits
```

Email verification is required for the benefit, not necessarily for basic account access unless another account-security task explicitly changes that policy.

---

## 10. Abuse and edge cases to research

Cover at least:

- disposable/forwarding addresses using misleading subdomains;
- changing account email after student verification;
- user changes from `.edu.vn` to a normal email;
- duplicate accounts using the same student email;
- case normalization and whitespace;
- expired verification code/link;
- resend abuse;
- Google Login account with a school email;
- creator changes/removes student discount after users have already installed/purchased;
- refunds/payment records if student discounts apply to paid decks;
- whether student eligibility should be permanent or periodically revalidated in a future phase.

When the primary email changes, student status must be recomputed/revoked until the new email is verified.

---

## 11. Analytics / admin visibility

Consider tracking non-sensitive product events such as:

```text
email_verification_started
email_verified
student_status_verified
student_offer_enabled
student_offer_used
```

Admin should be able to see verification/student status when investigating payment or abuse issues, without exposing verification codes/tokens.

---

## 12. Tests required

At minimum:

1. Existing user after migration remains able to log in but has `email_verified = false`.
2. Unverified `user@school.edu.vn` does NOT receive student benefit.
3. Verified `user@school.edu.vn` becomes eligible.
4. Verified normal-domain email does not become a student automatically.
5. Student-free deck installs at zero price only for verified eligible users.
6. Student percentage discount is calculated correctly server-side.
7. Client cannot forge student status/discount.
8. Changing verified student email to another email revokes student eligibility until re-verification.
9. Creator can create/edit/remove student offers.
10. Globally free deck does not expose a meaningless student-discount configuration.
11. Verification code/link expiration and resend rate limits work.
12. Google Sign-In verification behavior follows the chosen trusted-source policy.

---

## Acceptance criteria

- Task is implemented after Google Login integration.
- Registration contains a small `.edu.vn` student-benefit hint.
- Flama has an explicit email verification state.
- Existing historical emails are initially considered unverified.
- Student status requires an accepted verified email source plus the education-domain policy.
- `.edu.vn` detection is centralized and extensible rather than scattered through UI code.
- Creators can choose no student benefit, free for students, or X% student discount for paid shared decks.
- Marketplace clearly communicates student benefits.
- Backend, not frontend, authorizes the final student price/free access.
- Email changes invalidate/re-evaluate student status safely.
- The design can later expand beyond `.edu.vn` without a schema rewrite.
