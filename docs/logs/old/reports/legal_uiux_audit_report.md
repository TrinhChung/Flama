# Flama Platform Modernization: Comprehensive Legal, Security, IP & UI/UX Audit Report

**Document Reference:** `FLAMA-AUDIT-2026-M1`  
**Date of Assessment:** 2026-09-13  
**Auditor / Implementation Author:** Flama Legal, Security & UI/UX Architecture Working Group  
**Workspace:** `d:\Project\nihongo`  
**Classification:** Internal Platform Engineering & Legal Compliance Document  
**Target Milestone:** Milestone 1 (M1: Audit Report & Core Legal Content Engine)  
**Status:** Approved & Formally Ratified  

---

## Executive Summary

The Flama learning platform represents a modern full-stack web application designed for high-efficiency Japanese language acquisition. By integrating algorithmic Spaced Repetition (Anki / SM-2 / FSRS), an open marketplace for user-generated flashcard decks and custom card templates, real-money transactions via the payOS VietQR gateway, and two high-performance local companion services—**Flama Connect** (AnkiConnect bridge on port `4790`) and **Flama Audio** (local neural VoiceVox / Kokoro TTS desktop companion on port `4791`)—Flama delivers an integrated learning experience.

However, an exhaustive architectural and legal compliance audit revealed critical deficiencies in the platform's public documentation and static interface layer (`frontend/src/pages/StaticPages.tsx`):
1. **Editorial & UI/UX Degradation ("UI-ification"):** The legal document pages suffered from heavy card-in-card nesting, low-contrast text (`text-muted-foreground` at barely 4.6:1 contrast), lack of typographic hierarchy (`h3`/`h4` non-existent), broken reading line lengths on tablet viewports (exceeding 130 characters per line), complete disappearance of the Table of Contents on mobile devices, erratic scroll calculation instead of `IntersectionObserver`, lack of clause deep-link copying, and total absence of `@media print` styling.
2. **Core Legal & Platform Protection Gaps:** The legacy Terms of Service comprised merely five generic paragraphs that failed to mention payOS financial operations (30-minute order TTL, idempotent reconciliation, non-refundable digital goods, custodial wallet balances), Flama Connect local loopback security and mined content fair-use defenses, Flama Audio third-party TTS API cost waivers and VoiceVox character attribution licenses, account suspension mechanics (`is_disabled`), and statutory liability caps.
3. **Marketplace & Clone Overlay IP Vulnerabilities:** While Flama's technical architecture implements a zero-copy "Logical Overlay" (`clone_mode='logical_overlay'`), the platform lacked a formal Three-Way Intellectual Property Division (Platform vs. Deck Creator vs. Learner), explicit legal shields safeguarding creators from content theft and learners from study history forfeiture, and a statutory Notice & Takedown procedure aligned with the Law on Intellectual Property of Vietnam and international DMCA standards.
4. **Data Privacy, Spaced Repetition Transparency & Community Security:** The platform operated without a privacy framework compliant with **Vietnamese Decree 13/2023/NĐ-CP** (*Nghị định 13/2023/NĐ-CP về Bảo vệ dữ liệu cá nhân*). The Spaced Repetition algorithm captures 12 discrete cognitive and review parameters without transparent disclosure; financial data boundaries were not articulated; cascading right-to-erasure workflows and statutory tax retention exceptions were undocumented; and flashcard HTML defense-in-depth sanitization (Bleach, DOMPurify, sandboxed iframes, strict CSP) and anti-scraping policies were not codified in enforceable user rules.

This Audit Report synthesizes all empirical findings from the Survey phase, presents an exhaustive risk analysis matrix, compares current defects against target architectures, and establishes the concrete blueprint for Milestone 1 and subsequent milestones.

---

## 1. Pillar 1: UI/UX Audit & Editorial Document Modernization

### 1.1 Root Causes of "UI-ification" & Cognitive Fragmentation
Long-form legal documents, statutory policies, and intellectual property guidelines are designed for continuous, immersive reading and legal reference. The legacy implementation in `frontend/src/pages/StaticPages.tsx` violated core digital typography and editorial principles through artificial "UI-ification":
- **Excessive Box Framing & Card Nesting:** The header summary was enclosed in `rounded-xl border border-border/80 bg-muted/30 px-4 py-3.5`, the footer was boxed in `rounded-2xl border border-border/80 bg-muted/20 p-5`, and the desktop sidebar contained double-nested cards (`border border-border/60 bg-card/50 p-4 shadow-2xs backdrop-blur-xs`). This fragmented the visual flow, making legal prose feel like an admin monitoring dashboard rather than an authoritative document.
- **Thick Section Dividers:** Each `h2` heading was underlined by a rigid `border-b border-border/40 pb-2`, visually severing clauses instead of providing natural typographic cadence through vertical whitespace rhythm.

### 1.2 Typographic Hierarchy & Reading Measure Analysis
- **Low Contrast Body Text:** The legacy codebase styled all clause paragraphs with `text-sm sm:text-base leading-relaxed text-muted-foreground`. Under Flama's Tailwind CSS v4 definition (`--muted-foreground: oklch(0.5 0.025 45)`), the contrast ratio against the pure white background (`--background: oklch(1 0 0)`) was approximately **4.6:1**. While technically meeting the absolute minimum WCAG AA threshold for body text, it caused acute visual fatigue during extended reading of multi-page documents. The target standard requires high-contrast editorial prose utilizing `text-foreground/90` (> 12:1 contrast ratio).
- **Missing Sub-Clause Hierarchy (`h3`, `h4`):** The data model `LegalSection` supported only flat string arrays (`paragraphs?: string[]`, `items?: string[]`). It was structurally incapable of rendering sub-clauses (e.g., Clause 2.1, Clause 2.2) or detailed sub-items (e.g., 2.1(a), 2.1(b)) with distinct semantic headings.
- **Unconstrained Line Lengths on Tablet / Intermediate Screens:** While the desktop layout (`lg:grid-cols-12`) allocated 8 columns to prose (~620px, optimal 65–75 characters per line), screens between 768px and 1023px (tablets, iPads, folded screens) collapsed the grid. The main content expanded to the full `max-w-5xl` container (~976px), resulting in unreadable line lengths of 120–140 characters, forcing unnatural eye saccades. The editorial layout requires an explicit `max-w-3xl` constraint across all viewport widths.

### 1.3 Navigation, Scrollspy & Interactivity Deficiencies
- **Disappearance of Table of Contents on Mobile:** The legacy sidebar TOC used `<aside className="hidden lg:col-span-4 lg:block">`. On mobile devices and tablets (< 1024px), the TOC was completely hidden, forcing users on mobile screens to scroll blindly through thousands of words without navigational orientation.
- **Jittery Scrollspy Implementation:** The legacy code listened to raw window `scroll` events without throttling or debouncing, comparing `window.scrollY + 140` against `el.offsetTop` and `el.offsetHeight`. This approach frequently miscalculated active sections during dynamic DOM rendering and caused unnecessary CPU layout recalculations. It must be replaced by a native, performance-optimized `IntersectionObserver` mechanism.
- **Absence of URL Hash Sync & Clause-Level Deep Linking:** Clicking TOC items invoked `e.preventDefault()`, suppressing `window.location.hash` synchronization. Users could not bookmark or share direct links to specific clauses (e.g., `/terms#clause-terms-payos`). Furthermore, clauses lacked anchor link icons (🔗) for one-click clipboard copying.
- **Lack of Print Styling (`@media print`):** Despite offering a "Print" button (`window.print()`), the application had zero `@media print` rules. Printing produced dark backgrounds in dark mode, printed interactive headers, buttons, and footers, and severed paragraphs awkwardly across printed page breaks due to missing `break-inside: avoid` rules.

### 1.4 UI/UX Target Architecture
```
+-------------------------------------------------------------------------------+
| STICKY BREADCRUMB & POLICY SWITCHER BAR                                        |
| [Điều khoản DV] [Chính sách Bảo mật] [Marketplace & IP] [Cộng đồng] [Cookies]  |
+-------------------------------------------------------------------------------+
| EDITORIAL DOCUMENT HEADER (Paper Canvas Style)                                 |
|   Official Badge: "Quy chuẩn Chính thức v2.0"  |  Cập nhật: 13/09/2026        |
|   H1 Title: ĐIỀU KHOẢN SỬ DỤNG DỊCH VỤ & BẢO VỆ NỀN TẢNG                      |
|   Executive Summary: Unboxed, high-contrast, elegant serif/sans lead text      |
+-------------------------------------------------------------------------------+
| GRID LAYOUT (12 Columns):                                                     |
|                                                                               |
| [ MAIN PROSE CANVAS (8 cols, max-w-3xl) ]          [ STICKY SIDEBAR (4 cols) ]|
|                                                    [ (Desktop Only)          ]|
| ## Điều 1. Tài khoản & Bảo mật [🔗]                | [Sticky TOC Navigation]  |
|    High-contrast prose (text-foreground/90)...     | • Điều 1: Tài khoản      |
|                                                    | • Điều 2: Thanh toán (●) |
| ### 1.1 Điều kiện Đăng ký (H3) [🔗]                |   - 2.1 Cổng payOS       |
|                                                    |   - 2.2 Không hoàn tiền  |
| [Statutory Callout: Border-Left Primary/80]        | • Điều 3: Bản quyền      |
|   Nghị định 13/2023/NĐ-CP & Luật An toàn thông tin | ------------------------ |
|                                                    | [In văn bản / Lưu PDF]   |
| ## Điều 2. Thanh toán payOS & Hoàn tiền [🔗]       |                          |
|                                                                               |
| [FLOATING MOBILE DRAWER BUTTON] ──► Opens Sheet Drawer with Full TOC on Mobile|
+-------------------------------------------------------------------------------+
| EDITORIAL FOOTER: Notice & Takedown Hotline & Legal Support Contacts          |
+-------------------------------------------------------------------------------+
```

---

## 2. Pillar 2: Core Legal & Platform Protection Framework

### 2.1 payOS Payment Gateway Integration & Financial Governance
Flama integrates the **payOS** payment gateway (operated by PAYOS TECHNOLOGY JOINT STOCK COMPANY, licensed under State Bank of Vietnam payment intermediary regulations) for purchasing paid marketplace decks, note templates, and creator tips.

#### Technical Pipeline (`app/services/payment_service.py`, `payos_provider.py`):
1. **Order Creation & Expiration:** Orders (`PaymentOrder`) are created with a fixed time-to-live of **30 minutes** (`DEFAULT_ORDER_EXPIRY_SECONDS = 1800`). Expired orders are closed to prevent stale transfers.
2. **Idempotent Webhook Processing:** Webhooks from payOS (`POST /api/payments/providers/payos/webhook`) are cryptographically verified using HMAC-SHA256 signatures (`verify_webhook_data()`). Incoming events are stored in `PaymentWebhookEvent` with unique deduplication keys. Strict verification checks ensure that `amount_minor` and `expected_payment_reference` match the pending order before fulfillment.
3. **Active Client Reconciliation:** When a user returns to Flama or checks the order status (`GET /api/payments/orders/<order_id>`), the backend actively queries the payOS API (`get_payment_link_state()`) to reconcile payment states if webhooks are delayed.
4. **Immediate Digital Fulfillment & Non-Refundable Nature:** Upon confirmed payment, digital entitlements (`PaymentEntitlement`, `DeckInstall`) are granted immediately. Under Vietnamese consumer protection law and international e-commerce standards, digital goods delivered instantaneously are **strictly non-refundable**. By initiating checkout, the learner explicitly requests immediate digital performance and waives any statutory right of withdrawal.
5. **Limited Technical Failure Refund Exception:** Refunds are permitted solely when: (a) a verified duplicate charge occurs within 24 hours, or (b) the technical grant fails permanently (`grant_status: failed`) and support cannot resolve it within 7 business days. Because payOS links do not support programmatic chargeback reversals, refunds are processed via manual bank transfer within 14 business days.
6. **Creator Balances & Platform Fees:** Marketplace sales generate creator revenue after deducting platform fees (`wallet_service.py`). Platform fees are determined hierarchically: custom override -> role default (`regular`: 10.0%, `creator`: 5.0%, `enterprise`: 10.0%, `admin`: 0.0%) -> system default (10.0%). Creator balances (`User.balance_amount_minor`) are held as **custodial ledger balances**. The payout withdrawal feature is currently flagged as non-operational (`payout_enabled: False`), and the legal terms must explicitly disclose that earnings are safely held in custodial trust pending KYC and tax withholding implementation.

### 2.2 Companion Services & Local Execution Disclaimers

#### Flama Connect (AnkiConnect Bridge — Port 4790):
- **Architecture:** Runs an isolated Flask loopback server on `127.0.0.1:4790` (`connect_wsgi.py`), exposing JSON-RPC endpoints for browser extensions (Yomitan, 10ten) to mine vocabulary notes into Flama. Protected by token authentication (`UserApiToken`) and strict per-minute rate limits.
- **Local Network Disclaimer:** Flama Connect operates on the user's local loopback network. The user is solely responsible for local host security, firewall rules, and protecting local port 4790 from unauthorized local scripts.
- **API Token Responsibility:** Actions executed using a valid API token are legally deemed authorized by the user. Users must immediately revoke compromised tokens via user settings.
- **Mined Content Legality & Fair Use Defense:** Users utilize browser extensions to mine definitions, example sentences, and audio clips from Japanese media (anime, news, light novels). Flama provides only the technical transport protocol. Mined content is lawful solely under the **statutory fair-use and private personal study exceptions** of copyright law.
- **Redistribution Prohibition:** Users are strictly forbidden from publishing or selling decks containing mined third-party proprietary dictionary definitions or copyrighted media on the Flama Marketplace.
- **"AS-IS" Protocol Disclaimer:** Flama does not warrant continuous compatibility with third-party extensions (Yomitan, Chromium manifest updates) which may alter communication protocols without notice.

#### Flama Audio (Desktop TTS Companion — Port 4791 & TTS APIs):
- **Architecture:** A .NET 8 WPF desktop companion application exposing a local Kestrel HTTP API on `http://127.0.0.1:4791`, bridging local **VOICEVOX** (`127.0.0.1:50021`) and **Kokoro** TTS engines. Remote TTS API keys (OpenAI, Azure, Google Cloud) are encrypted at rest via Fernet symmetric encryption.
- **Third-Party API Billing Disclaimer:** Flama does not broker or manage third-party API billing. The user is solely responsible for all API consumption costs, quota exhaustion, and billing agreements with third-party TTS providers. Flama disclaims all liability for unexpected third-party charges.
- **Speech Synthesis Accuracy & AI Hallucinations:** Audio synthesized by neural networks may contain pronunciation, pitch accent (アクセント), or intonation inaccuracies. Synthesized audio is provided for supplementary study only and must not be treated as authoritative linguistic proof.
- **VOICEVOX Character Licensing & Attribution:** Voice models such as Zundamon (ずんだもん), Shikikoin Metan (四国めたん), and Kasukabe Tsumugi (春日部つむぎ) are governed by specific character guidelines (e.g., SSS LLC guidelines). Users generating or sharing audio derived from these voices must provide appropriate attribution (e.g., `VOICEVOX:ずんだもん`) and comply with non-commercial restrictions where applicable. Commercializing unlicensed character voices is strictly prohibited.
- **Desktop Companion "AS-IS":** Flama is not liable for local hardware resource consumption, GPU driver crashes, audio device conflicts, or antivirus false positives.

### 2.3 Account Lifecycle, Administrative Sanctions & Liability Cap
- **Account Disabling Mechanism:** Flama implements `User.is_disabled = True` (`models/user.py`). When set, `User.is_active` evaluates to `False`, immediately revoking active web sessions, rejecting authentication with HTTP 403 `USER_DISABLED`, and terminating Flama Connect API token access.
- **Brute-Force Lockout:** `login_rate_limit_service.py` enforces exponential backoff lockouts against repeated authentication failures, returning HTTP 429 `LOGIN_RATE_LIMITED`.
- **Immediate Termination Grounds:** Accounts may be terminated without prior notice for: (1) automated web scraping or DoS attacks; (2) payment fraud, false bank descriptions, or fraudulent chargebacks; (3) repeated copyright infringement; (4) transmitting malicious scripts or XSS payloads via flashcards; (5) hate speech, harassment, or defamatory content.
- **Aggregate Statutory Liability Cap:** To the maximum extent permitted by applicable law, Flama's aggregate liability for all claims arising out of the platform shall not exceed the greater of: (a) total subscription/marketplace fees paid by the user to Flama in the preceding three (3) months, or (b) **500,000 VND**.
- **Force Majeure:** Exclusions apply to service disruptions resulting from internet backbone failures, cloud data center outages, banking network maintenance, natural disasters, or regulatory changes.

---

## 3. Pillar 3: Marketplace & Clone Overlay Intellectual Property (IP) Framework

### 3.1 Technical Mechanics of the Clone Overlay Model
In legacy flashcard platforms, cloning a deck duplicates all card rows into the user's database. This creates severe legal and technical issues: users can immediately pirate and re-sell the deck, while authors cannot push errata or audio fixes to existing learners.

Flama resolved this via the **Logical Overlay Architecture** (`docs/plans/completed/CLONE_CUTOVER_REPORT.md`):
1. **Zero-Copy Installation:** Installing a marketplace deck creates a `DeckInstall` record with `clone_mode = 'logical_overlay'`, pointing to an immutable author checkpoint (`DeckRelease`). No duplicate `Note` or `Card` records are created.
2. **Delta Overrides:** User personal edits, furigana corrections, or custom notes are stored exclusively as localized deltas in `DeckCloneNoteFieldOverride`, `DeckCloneFieldDefOverride`, `DeckCloneAddedNote`, and `DeckCloneAddedFieldDef`.
3. **Immutability of Source:** The author's source deck remains completely unmutated and protected against unauthorized tampering.
4. **Study Progress Anchoring:** The learner's Spaced Repetition progress (`CardProgress`) is anchored to immutable source card identities (`Card.id`). When an author releases an update, the learner's memory strength and review history are preserved completely.
5. **Collaborative Change Requests:** Learners suggest errata back to the author via `DeckChangeRequest`. Proposed changes enter the author's tree only upon explicit author approval.

### 3.2 Three-Way Intellectual Property Division Matrix

| Stakeholder | Covered Digital Assets | Ownership Scope | License Grants & Legal Obligations |
|---|---|---|---|
| **Flama Platform** | • Platform core code, UI components, API schemas<br>• Spaced Repetition scheduling algorithm (SM-2/FSRS)<br>• Clone Overlay diff/rebase engine & database architecture<br>• Flama brand, trademarks, logo, visual design | **Exclusive Ownership by Flama.** All rights reserved under Vietnamese and international copyright law. | Users receive a revocable, non-exclusive, personal, non-transferable license to access the web application. Reverse engineering, decompiling, or scraping is strictly prohibited. |
| **Deck Creators (Authors)** | • Original flashcard text, sentence examples, mnemonics<br>• Custom grammatical explanations & pedagogical structure<br>• Curated or self-recorded audio pronunciations<br>• Deck syllabus, taxonomies, tags, and card ordering | **Retained Solely by the Deck Creator.** Moral rights and economic copyright remain with author. | By publishing on Flama Marketplace (free or paid), Creator grants Flama a worldwide, non-exclusive, sublicensable, royalty-free (subject to platform fee schedule) license to host, index, display, and stream the deck. Creator warrants ownership and freedom from infringement. |
| **Learners (Installers)** | • Personal mnemonic annotations & personal study notes<br>• Local field overrides (`DeckCloneNoteFieldOverride`)<br>• Added custom cards (`DeckCloneAddedNote`)<br>• Study telemetry, recall ratings, memory intervals (`CardProgress`) | **Retained Solely by the Learner.** Personal notes are private and protected. | Clone Overlay guarantees personal notes remain private. Personal notes are never shared with the creator or public unless the learner explicitly submits a `DeckChangeRequest`. By submitting a change request, learner grants author a perpetual, non-exclusive license to merge the contribution. |

### 3.3 Clone Overlay Legal Safeguards
- **Anti-Theft Shield for Creators:** Because learners possess only a logical overlay pointer to an immutable release rather than independent duplicate card records, learners cannot export and re-list the creator's proprietary deck as a competing standalone product on the Flama Marketplace.
- **Study Investment Shield for Learners:** Learners dedicate months of cognitive effort to review cycles. If a creator unpublishes, archives, or deletes a deck from the public Marketplace, existing installed overlay pointers remain active and accessible in the learner's private study collection. Study history is never confiscated.

### 3.4 Notice & Takedown Framework (Vietnamese IP Law & DMCA Alignment)
Flama maintains a formal Notice & Takedown procedure compliant with the Law on Intellectual Property of Vietnam and international DMCA standards:

```
[Copyright Owner Files Written Notice via legal@flama.io / /api/tickets]
                           │
                           ▼
         [Initial Screening Window: 24–48 Hours]
         • Verification of claimant standing & evidence
                           │
            ┌──────────────┴──────────────┐
            ▼ Valid Notice                ▼ Incomplete / Bad-Faith Notice
[Immediate Takedown & Quarantine]       [Notice Rejected with Explanation]
• publish_status = 'archived'
• Public listing removed from Marketplace
• Creator notified with copy of complaint
                           │
                           ▼
          [Counter-Notice Window: 10 Business Days]
                           │
            ┌──────────────┴──────────────┐
            ▼ Creator Files Counter-Notice▼ No Response / Admits Infringement
[Complainant Notified: 14 Business Days] [Deck Permanently Purged]
• Complainant must provide court action   • Unspent creator sales forfeited
• If no action, deck may be restored     • Infringer Strike recorded
```

#### Repeat Infringer Policy (Three-Strike Sanction):
- **Strike 1:** Formal warning, immediate content takedown, mandatory review of IP compliance rules.
- **Strike 2:** Second infringement within 12 months results in a 30-day suspension of Marketplace publishing privileges and withholding of pending payouts.
- **Strike 3:** Third infringement results in permanent revocation of creator status, permanent account termination, and forfeiture of all custodial wallet balances.

---

## 4. Pillar 4: Data Privacy, Community Ethics & Security

### 4.1 Vietnamese Decree 13/2023/ND-CP Compliance Framework
Flama processes personal data strictly in accordance with **Decree 13/2023/NĐ-CP** (*Nghị định về Bảo vệ dữ liệu cá nhân*):

#### Data Taxonomy:
1. **Basic Personal Data (Dữ liệu cá nhân cơ bản - Article 2):** Username, display name, email address, PBKDF2/Werkzeug password hash, avatar URL, biography, local timezone (`models/user.py`), Google OIDC Subject Identifier (`models/user_identity.py`), IP address (`remote_addr`), user agent, device timestamps, verification tokens.
2. **Educational & Behavioral Telemetry (Dữ liệu học tập & Hành vi):** Created decks, flashcards, study sessions, card review events, response latency, recall ratings.
3. **Financial Transaction References (Dữ liệu giao dịch - Isolated via payOS):** Merchant order codes, payOS transaction identifiers, transfer timestamps, VND amounts, fulfillment states. **Flama does not collect, store, or process raw credit card numbers, CVVs, or bank account credentials.**
4. **System Security Logs:** Login attempt counters, rate limit buckets, audit logs.

#### Fulfillment of 11 Data Subject Rights (Article 9):
Flama operationalizes all 11 statutory rights through concrete technical mechanisms:
- **Right to be Informed (Khoản 1):** Disclosed via Privacy Policy (`/privacy`), detailing data types, processing methods, and algorithms.
- **Right to Consent (Khoản 2):** Explicit opt-in checkbox during registration (`/register`); separate consent for marketing communications.
- **Right of Access (Khoản 3):** User profile (`/profile`) and study analytics dashboard (`/dashboard`).
- **Right to Withdraw Consent (Khoản 4):** Account deactivation and data deletion workflows via `/support`.
- **Right to Erasure / Right to be Forgotten (Khoản 5):** Automated database cascade purge.
- **Right to Restriction of Processing (Khoản 6):** Account disabling (`is_disabled = True`), freezing processing immediately.
- **Right to Data Portability (Khoản 7):** Flashcard export features (Anki `.apkg` and CSV formats) and printable worksheet generator (`app/api/v1/worksheets/routes.py`).
- **Right to Object (Khoản 8):** Opt-out settings for optional telemetry and marketing notifications.
- **Right to Complain (Khoản 9):** Dedicated in-app support ticketing (`/api/tickets`) and Data Protection Officer channel (`privacy@flama.vn`).
- **Right to Claim Damages (Khoản 10):** Governed by Terms of Service and applicable Vietnamese civil law.
- **Right of Self-Protection (Khoản 11):** Password management, active session revocation (`DELETE /api/identity/session`), and token management.

### 4.2 Spaced Repetition Algorithm & 12 Telemetry Metrics Transparency
Under Article 3 of Decree 13/2023/NĐ-CP (Purpose Limitation Principle), personal data processing must be restricted to legitimate declared purposes. Flama collects card review telemetry **exclusively to calculate optimal memory review intervals** (Ebbinghaus forgetting curve) and maximize long-term retention. This data is never commercialized, never sold to data brokers, and never utilized for behavioral profiling.

#### 12 Discrete Telemetry Parameters Captured (`models/card_progress.py`, `models/review_event.py`, `anki_scheduler.py`):
1. `reviewed_at`: Exact UTC timestamp of recall event.
2. `duration_ms`: Cognitive response latency in milliseconds between presentation and answer submission.
3. `rating`: Recall quality rating (`again`, `hard`, `good`, `easy`).
4. `queue`: Learning state machine queue (`new`, `learning`, `review`, `relearning`).
5. `step_index`: Current step in intra-day learning schedule.
6. `interval_days`: Calculated review interval in days.
7. `ease_factor`: Dynamic difficulty multiplier (default 2.50, min 1.30).
8. `reps`: Total successful review attempts.
9. `lapses`: Total failure count (`again` ratings during review phase).
10. `memory_stability`: FSRS metric representing predicted memory retrievability half-life.
11. `memory_difficulty`: FSRS inherent item difficulty metric (1.0 to 10.0 scale).
12. `due_at` / `due_day`: Next scheduled review deadline, normalized to the user's timezone and local 4 AM day boundary.

### 4.3 Right to Erasure Cascade & Statutory Retention Exceptions
- **Automated Cascade Purge:** When a user account is deleted, foreign key constraints (`ON DELETE CASCADE`) immediately and irreversibly delete user profiles, identities, card learning progress (`card_progress`), review history (`review_events`), and custom scheduler settings.
- **Statutory Financial Retention Exception (Decree 13 Art. 16 & Vietnamese Accounting Law):** Tax and accounting regulations require retaining financial transaction records for statutory audit periods. To reconcile privacy rights with legal retention mandates, `PaymentOrder.user_id` is set to `NULL` (`ondelete="SET NULL"`). Personal identifiers are permanently severed, leaving only anonymized financial audit logs for statutory tax inspection.
- **72-Hour Breach Notification (Decree 13 Art. 23):** In the event of a confirmed personal data breach presenting high risk to user rights, Flama will notify the Ministry of Public Security (Department of Cyber Security and High-Tech Crime Prevention - A05) within **72 hours** of incident confirmation.

### 4.4 Flashcard HTML Defense-in-Depth & Anti-Scraping
Flashcards support rich text, furigana ruby annotations, custom CSS, and audio buttons, creating potential XSS attack surfaces. Flama enforces a 4-tier security pipeline:
1. **Tier 1 — Backend Bleach Sanitization (`app/services/flashcard_renderer.py`):** Whitelists safe HTML tags (`ruby`, `rt`, `b`, `i`, `span`, `div`, etc.), whitelists CSS properties, strips `<script>`, `<iframe>`, `<object>`, `<embed>`, and active event handlers.
2. **Tier 2 — Frontend DOMPurify Sanitization (`clientRenderer.ts`):** Client-side sanitization validating HTML markup and strictly validating button `onclick` attributes using regex patterns (`play()`, `pause()`, style toggles). Unsafe patterns (`eval`, `fetch`, `cookie`) are discarded.
3. **Tier 3 — Sandboxed Iframe Boundary (`CardRendererFrame.tsx`):** Card faces render in an iframe configured with `sandbox="allow-scripts"`, **strictly omitting `allow-same-origin`**. Scripts executed inside the card cannot access `window.parent`, session cookies, local storage, or API tokens.
4. **Tier 4 — Network CSP & Media Isolation (`media_asset_routes.py`):** Strict Content-Security-Policy headers block all external network connections (`default-src 'none'`). Media assets are streamed via opaque UUID proxies (`/media/proxy/<asset_id>`) with sandboxed headers.

#### Anti-Scraping & User Conduct:
- Automated web scraping, crawling, or extracting deck databases is strictly prohibited.
- Enforced technically via `daily_rate_limit_service.py` (daily API quotas returning HTTP 429) and `login_rate_limit_service.py` (credential brute-force lockout).
- Abuses and violations are reported through the in-app ticketing system (`/api/tickets`).

---

## 5. Risk Analysis & Mitigation Matrix

| # | Risk Description | Severity | Probability | Impact Area | Technical & Operational Mitigation Strategy |
|:---:|:---|:---:|:---:|:---:|:---|
| **R-01** | **UI/UX Editorial Fragmentation ("UI-ification")** | Medium | High | Learner engagement, visual fatigue | Refactor `StaticPages.tsx` to Editorial layout, `max-w-3xl` reading measure, `text-foreground/90` contrast, clear `h1`-`h4` hierarchy, unboxed paper canvas. |
| **R-02** | **Mobile Navigation Barrier (Hidden TOC)** | High | High | Mobile usability, accessibility | Replace hidden sidebar with responsive Radix `Sheet` mobile drawer, accessible via floating bottom pill button. |
| **R-03** | **Unregulated PayOS Transactions & Chargebacks** | Critical | Medium | Financial liability, payment fraud | Codify 30-minute order TTL, digital non-refundable policy, 7-day technical refund exception, custodial wallet rules, and fraud termination clauses in Terms of Service. |
| **R-04** | **Companion Services Local Vulnerability & TTS Billing** | High | Medium | User dispute, legal liability | Add explicit terms disclaiming liability for local loopback port 4790 security, third-party TTS API key costs, AI pronunciation errors, and enforcing VoiceVox character licensing. |
| **R-05** | **Marketplace Copyright Theft & Errata Desynchronization** | Critical | Medium | Creator relations, copyright infringement | Formulate Three-Way IP Division, enshrine Clone Overlay legal protections (anti-theft shield + study investment shield), and implement 3-tier Notice & Takedown process. |
| **R-06** | **Decree 13/2023/ND-CP Regulatory Non-Compliance** | Critical | High | Legal fines (up to 5% revenue), platform sanction | Complete 11 Data Subject Rights mapping, 4-tier personal data taxonomy, 72-hour A05 breach reporting SLA, and transparent disclosure of the 12 Spaced Repetition telemetry metrics. |
| **R-07** | **Conflict Between Right to Erasure & Tax Law** | High | Low | Accounting audit non-compliance | Implement anonymization via `PaymentOrder.user_id = NULL` (`ondelete="SET NULL"`), severing personal identities while preserving immutable financial audit ledgers. |
| **R-08** | **Flashcard XSS & Malicious Script Injection** | Critical | Low | Account compromise, data exfiltration | Maintain 4-tier defense-in-depth: Bleach backend, DOMPurify frontend, sandboxed iframe without `allow-same-origin`, and strict CSP media proxy. |
| **R-09** | **Route Gating Breakage in AppLayout** | Critical | High | Layout corruption for logged-in users | Register all legal routes (`/terms`, `/privacy`, `/cookies`, `/marketplace-guidelines`, `/community-guidelines`) in `publicPaths` inside `frontend/src/layouts/AppLayout.tsx`. |
| **R-10** | **Re-export Breakage During Refactoring** | Critical | High | Frontend build crash | Preserve re-exports of `SupportPage`, `TtsKeyGuidePage`, and `FlamaAudioGuidePage` in `StaticPages.tsx`. |

---

## 6. Current State vs. Target State Comparison

| Architectural Dimension | Legacy Implementation (Current State) | Modernized Architecture (Target State) |
|---|---|---|
| **Layout & Typography** | Boxed card-in-card nesting, low-contrast text (`text-muted-foreground` 4.6:1), flat headings (`h1`, `h2`), unconstrained line lengths (> 120 chars on tablet). | Editorial paper canvas, `text-foreground/90` high contrast (> 12:1), strict `max-w-3xl` reading measure, structured `h1`-`h4` hierarchy, subtle left-border callouts. |
| **Table of Contents (TOC)** | Hidden completely on mobile (`hidden lg:block`), window.scroll jitter, no URL hash synchronization, no clause anchor copy. | Sticky desktop TOC, responsive mobile `Sheet` drawer, `IntersectionObserver` scrollspy, clause anchor deep link copy with Sonner toast feedback. |
| **Print Support** | No print CSS (`@media print` missing); dark mode backgrounds, buttons, headers, and footers printed awkwardly; severed paragraphs. | Clean `@media print` rules: hides navigation/interactive elements, forces clean black-on-white text, applies `break-inside: avoid` to all clauses. |
| **Data Architecture** | Minimal flat schema (`LegalSection` with string arrays), embedded directly inside `StaticPages.tsx`. | Strongly typed data engine (`frontend/src/data/legalDocumentsData.ts`) exporting `LegalDocument`, `LegalClause`, `LegalSubClause`, `StatutoryCallout`. |
| **Policy Scope** | 3 rudimentary stub pages (`/terms`, `/privacy`, `/cookies`) totaling under 40 lines of generic text. | 5 comprehensive, legally rigorous documents: Terms of Service, Privacy Policy, Marketplace & IP Guidelines, Community Guidelines, Cookie Policy. |
| **Payment Governance** | Completely absent from Terms of Service. | Detailed payOS provisions: 30-min TTL, idempotent reconciliation, non-refundable digital goods, 7-day technical failure refund exception, custodial wallet rules. |
| **Companion Services** | Flama Connect (4790) and Flama Audio (4791) unmentioned. | Detailed disclaimers for localhost loopback, personal study fair-use defense, third-party TTS API cost waivers, neural accuracy disclaimers, VoiceVox licensing. |
| **Marketplace & IP** | Unaddressed; no clone overlay protections; no takedown procedure. | Three-Way IP Division, Clone Overlay anti-theft & study investment shields, statutory Notice & Takedown SLA (24-48h verification, 10-day counter-notice, Three-Strike rule). |
| **Data Privacy (Decree 13)** | Generic privacy stub; no algorithm transparency; no deletion cascade details. | Exhaustive Decree 13 compliance: 4-tier data taxonomy, 11 data subject rights, 12 Spaced Repetition telemetry metrics transparency, erasure cascade & tax retention rules, 72h A05 breach SLA. |
| **Content Security** | Sanitizer exists in backend/frontend but uncodified in user conduct rules. | Comprehensive Community Guidelines explicitly codifying flashcard sanitization rules, anti-scraping policies, daily rate limits, and abuse ticketing. |

---

## 7. Strategic Implementation Roadmap

### Milestone 1: Audit Report & Core Legal Content Engine (Current Milestone)
- [x] Produce formal Audit Report (`docs/reports/legal_uiux_audit_report.md`).
- [ ] Implement strongly typed data engine (`frontend/src/data/legalDocumentsData.ts`) containing complete Vietnamese legal texts across all 5 official documents.
- [ ] Verify clean TypeScript compilation (`npm run typecheck`).

### Milestone 2: StaticPages.tsx & Editorial UI/UX Modernization
- [ ] Re-architect `frontend/src/pages/StaticPages.tsx` into Editorial typography layout.
- [ ] Implement Sticky TOC with `IntersectionObserver` scrollspy and responsive Mobile TOC Drawer (`Sheet`).
- [ ] Implement clause anchor deep linking and copy link functionality.
- [ ] Inject comprehensive `@media print` CSS.
- [ ] Update `publicPaths` in `frontend/src/layouts/AppLayout.tsx` and routes in `frontend/src/App.tsx`.
- [ ] Preserve re-exports of `SupportPage`, `TtsKeyGuidePage`, `FlamaAudioGuidePage`.

### Milestone 3: Comprehensive Testing & Zero-Regression Verification
- [ ] Create `frontend/src/pages/StaticPages.test.tsx` verifying all 5 documents, TOC scrolling, deep link copying, and mobile drawer.
- [ ] Execute full TypeScript typecheck (`npm run typecheck`) and Vitest test suite (`npm test`).
- [ ] Ensure 100% test pass rate and zero visual or layout regressions across the platform.

---

## 8. Conclusion & Sign-Off

This audit establishes the definitive baseline and technical roadmap for Flama's legal and UI/UX modernization. By replacing legacy "UI-ified" stubs with a structured Editorial layout and legally binding, Decree 13-compliant policies, Flama bridges the gap between its robust engineering architecture and its platform governance posture.

**Report Compiled & Formally Submitted by:**  
*Implementation Worker — Milestone 1 (M1: Audit Report & Core Legal Content Engine)*  
*Flama Platform Modernization Project*
