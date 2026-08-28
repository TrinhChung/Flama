# Task: Community Standards, Profile Policy & Reporting Flow

## Goal

Create a clear set of community standards for Flama and integrate those standards directly into user profile setup and public profile moderation flows.

The goal is to make acceptable behavior explicit, reduce abusive or policy-violating profile content, and provide a simple reporting path to administrators.

---

## 1. Community Standards / Platform Principles

Create a dedicated Community Standards / Platform Principles document and product page.

Suggested route:

```text
/community-standards
```

The final information architecture should be researched before implementation, but the standards should at minimum cover:

- harassment, threats and abusive behavior
- hate or discriminatory content
- sexual / explicit content inappropriate for the platform
- impersonation and deceptive identity
- spam, scams, misleading links and phishing
- malware or dangerous external links
- illegal content
- copyright / intellectual-property violations
- unauthorized sharing or resale of paid or classroom materials
- abusive marketplace behavior
- manipulation of reviews, ratings, installs or reputation
- misuse of Flama features to attack or disrupt other users
- repeated attempts to bypass moderation actions

Also define the general principle that users are responsible for the content they publish through:

- profile name
- avatar
- biography
- external links
- decks
- deck descriptions
- course information
- reviews
- comments / contribution text if applicable

The policy should be written in simple user-facing language, not only legal language.

---

## 2. Enforcement policy

The Community Standards page should explain that violations may result in enforcement actions depending on severity and repetition.

Possible actions to research and define:

```text
content removal
warning
feature restriction
temporary suspension
marketplace / creator restriction
permanent account ban
```

The UI must clearly state that serious or repeated violations may result in permanent account suspension.

Recommended wording direction:

> Nội dung vi phạm Tiêu chuẩn cộng đồng có thể bị xóa. Tùy theo mức độ vi phạm, tài khoản có thể bị hạn chế, tạm khóa hoặc cấm vĩnh viễn.

Avoid promising automatic permanent bans for every report. Reports must be reviewed by moderation/admin logic.

---

## 3. Integrate Community Standards into Profile Settings

In the user profile settings / edit profile screen, add a visible Community Standards notice near fields that create public content.

At minimum this applies to:

- avatar upload
- display name
- bio / personal introduction
- external links

Add a link:

```text
Xem Tiêu chuẩn cộng đồng
```

which opens `/community-standards`.

Add a warning such as:

> Không đăng ảnh, nội dung hoặc liên kết vi phạm Tiêu chuẩn cộng đồng của Flama. Nếu phát hiện nội dung không phù hợp, vui lòng báo cáo để quản trị viên xem xét. Vi phạm nghiêm trọng hoặc lặp lại có thể dẫn đến khóa tài khoản vĩnh viễn.

The warning should be visible without making the profile form visually heavy.

Research the best UX placement, e.g.:

- compact info banner
- helper text under public-profile section
- policy notice before Save

Do not add multiple duplicated warnings to every individual input.

---

## 4. Report button on public profiles

Add a `Report` / `Báo cáo` action to another user's public profile.

Do not show the report button when viewing your own profile.

Possible placement to research:

```text
Profile header
  ... menu
    Báo cáo người dùng
```

or a secondary action near profile actions.

Avoid making `Report` visually equal to the main profile actions unless product research supports it.

---

## 5. Profile report flow

Clicking `Báo cáo` should open a report form rather than immediately submitting a report.

Suggested reason categories:

- Nội dung xúc phạm / quấy rối
- Giả mạo người khác
- Spam / lừa đảo
- Liên kết nguy hiểm hoặc đáng ngờ
- Nội dung không phù hợp
- Vi phạm bản quyền
- Vi phạm quy định Marketplace / nội dung học tập
- Khác

Allow an optional description field.

Potential payload:

```text
reported_user_id
reporter_user_id
reason_code
description
source = profile
source_url / profile_id
created_at
status
```

Research whether the system should also capture a snapshot of the reported public profile fields at report time so that later profile edits do not destroy moderation evidence.

---

## 6. Admin moderation workflow

Reports must be delivered to an administrator/moderation queue.

Create or extend an admin page for reports.

Suggested route:

```text
/admin/reports
```

Admin should be able to see:

- reported user
- reporting user
- reason
- description
- submitted time
- reported resource / profile link
- relevant evidence or snapshot
- report status
- previous reports against the same account
- moderation history if available

Suggested report statuses:

```text
open
under_review
resolved_no_violation
resolved_action_taken
```

Possible moderation actions should be researched and designed rather than hardcoded only around banning:

- dismiss report
- remove violating profile content
- warn user
- restrict profile editing / public profile
- temporarily suspend
- permanently ban account

Any destructive or permanent moderation action should require an explicit confirmation step.

---

## 7. Abuse prevention

The report system itself must not become an abuse vector.

Research and implement safeguards such as:

- authenticated users only
- rate limit reports
- prevent duplicate repeated reports by the same user for the same target within a short period
- store reporter identity internally but do not expose it to the reported user by default
- audit moderation actions
- prevent users from reporting themselves
- validate report reason and target existence server-side

Do not automatically suspend or ban an account solely because it receives a certain number of reports.

---

## 8. Relationship with Marketplace and creator profiles

Because public profiles will also represent deck creators/contributors, moderation should be designed so profile reports can later coexist with reports for:

```text
user profile
deck listing
review
course link
creator content
```

Research whether one generic report model should support multiple resource types instead of creating a profile-only reporting table that must later be replaced.

Suggested conceptual model:

```text
report
  target_type
  target_id
  reported_user_id
  reporter_user_id
  reason
  description
  status
  moderation metadata
```

Do not over-engineer the first implementation, but avoid a schema that blocks future Marketplace moderation.

---

## 9. Public policy links

Community Standards should be easy to find from more than one location.

Research and consider links from:

- profile settings
- public profile report dialog
- site footer
- Help / Guide
- Marketplace publishing flow where relevant

The source of truth should remain one dedicated Community Standards page rather than duplicating full policy text across screens.

---

## 10. UX / product research required

Before implementation, research moderation and reporting patterns used by mature community and marketplace products.

Focus on:

- where community guideline links are placed during profile editing
- how report actions are surfaced without creating an aggressive UI
- report reason taxonomy
- confirmation and feedback after report submission
- how much enforcement detail is visible to users
- creator reputation / marketplace moderation patterns
- report privacy and reporter anonymity

Use findings to propose a Flama-specific flow rather than copying one platform exactly.

---

## Acceptance criteria

- A dedicated Community Standards / platform principles page exists.
- Profile Settings links clearly to Community Standards.
- Profile Settings warns users not to publish prohibited avatar, bio or external-link content.
- The warning clearly states that serious/repeated violations may lead to permanent account suspension.
- Other users' public profiles expose a `Report` action.
- Reporting opens a form with structured reasons and optional details.
- Reports are persisted and delivered to an administrator moderation queue.
- Admin can review and resolve reports.
- Permanent bans are manual/authorized moderation actions, not triggered automatically from raw report count.
- Reporting has basic rate-limit / abuse protections.
- The design considers future reports for Marketplace decks, reviews and other public resources.
- Relevant UI and moderation patterns are researched before final implementation.

## Scope note

This is a product / frontend / backend moderation task. The implementation may require schema and admin changes, but this task should first define the policy, UX flow and data model before coding the final solution.
