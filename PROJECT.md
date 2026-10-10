# Project: Flama End-User i18n Localization (Remaining Modules)

## Architecture
Flama is a full-stack Japanese language learning platform featuring a React 19 SPA frontend with Feature-Sliced Design (FSD) architecture, Flask REST backend, and Yomitan/MCP companion services.

This project completes the bilingual internationalization (i18n) across all remaining end-user screens in the React SPA frontend, supporting Vietnamese (`vi`, default) and English (`en`) with 100% key parity, zero visual regression, TypeScript type safety, and automated stress testing.

### Subsystems:
1. **Central i18n Core (`frontend/src/shared/config/i18n/`)**:
   - Central registration in `index.ts` and type-safety definitions in `types.ts`.
   - Locales in `locales/vi/` and `locales/en/` across 6 new namespaces: `profile`, `wallet`, `card_templates`, `audio`, `guide`, `onboarding`.
   - Comprehensive dictionary parity test suite: `translationKeys.test.ts` (static AST verification) and `i18n.stress.test.tsx` (runtime parity & non-empty assertion).
2. **User Profile & Wallet Subsystem (`frontend/src/features/profile/`, `frontend/src/features/wallet/`)**:
   - `features/profile/`: Profile page, hero card, badges, contributions, creator portfolio tabs, edit dialogs, avatar upload modal, email verification dialog, and Zod password validation schema.
   - `features/wallet/`: Wallet overview, platform fees, summary cards, payout notices, and transaction history table with filters.
3. **Card Template Ecosystem Subsystem (`frontend/src/features/template-library/`, `template-versions/`, `template-distribution/`)**:
   - `features/template-library/`: Template library catalog, template details, create dialog, apply wizard, field mapping editor, template applications panel, and input schema editor.
   - `features/template-versions/`: Template version history sheet and diff view.
   - `features/template-distribution/`: Distribution panel integration.
4. **Audio, Knowledge Base & Onboarding Subsystem (`frontend/src/features/audio/`, `guide/`, `onboarding/`)**:
   - `features/audio/`: Deck audio generator page, local engine connection gate, generation dialogs, rule cards, queue monitor, and batch progress list.
   - `features/guide/`: Knowledge base guides, navigation header, search, category sidebar, Yomitan marker explorer, MCP tools catalog, and reusable `ContextHelpButton`.
   - `features/onboarding/`: Onboarding welcome modal, hero cards, spotlight tours, and curated study targets/subjects (eliminating settings leakage).

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Central Namespace Registration & Types | Register `profile`, `wallet`, `card_templates`, `audio`, `guide`, `onboarding` in `index.ts` and `types.ts` | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Profile Dictionary (`profile.json`) | 100% symmetric bilingual dictionaries for User Profile (~50 keys) | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Wallet Dictionary (`wallet.json`) | 100% symmetric bilingual dictionaries for Wallet & Balances (~25 keys) | M1 | ORIGINAL_REQUEST §R1 |
| 4 | Card Templates Dictionary (`card_templates.json`) | 100% symmetric bilingual dictionaries for Template Ecosystem (126 keys) | M1 | ORIGINAL_REQUEST §R1 |
| 5 | Audio Dictionary (`audio.json`) | 100% symmetric bilingual dictionaries for Deck Audio Generator (~40 keys) | M1 | ORIGINAL_REQUEST §R1 |
| 6 | Guide Dictionary (`guide.json`) | 100% symmetric bilingual dictionaries for Knowledge Base (~50 keys) | M1 | ORIGINAL_REQUEST §R1 |
| 7 | Onboarding Dictionary (`onboarding.json`) | 100% symmetric bilingual dictionaries for User Onboarding & Targets (~55 keys) | M1 | ORIGINAL_REQUEST §R1 |
| 8 | i18n Stress & Parity Test Suite | Expand `i18n.stress.test.tsx` to assert 100% leaf parity and non-empty values across all 25 namespaces | M1 | ORIGINAL_REQUEST §R3 |
| 9 | User Profile Localization | Connect `useTranslation('profile')` in all 10 components, modals, tabs, and Zod password schema | M2 | ORIGINAL_REQUEST §R1 |
| 10 | ProfileEditDialog Pragmatic FSD Refactor | Decompose 670-line god-component into Info, Social, and Password sub-tabs | M2 | ORIGINAL_REQUEST §R2 |
| 11 | Wallet & Balances Localization | Connect `useTranslation('wallet')` in `WalletPage`, `WalletSummaryCard`, `PayoutNoticeCard`, `WalletTransactionsTable` | M2 | ORIGINAL_REQUEST §R1 |
| 12 | Template Library Localization | Connect `useTranslation('card_templates')` in library pages, search, filters, cards, and detail page | M3 | ORIGINAL_REQUEST §R1 |
| 13 | Template Dialogs & Wizards Localization | Connect `useTranslation('card_templates')` in `CreateTemplateDialog`, `ApplyTemplateWizard`, `FieldMappingEditor` | M3 | ORIGINAL_REQUEST §R1 |
| 14 | Template Applications & Versions Localization | Connect `useTranslation('card_templates')` in `TemplateApplicationsPanel`, `TemplateInputSchemaEditor`, `TemplateVersionHistorySheet` | M3 | ORIGINAL_REQUEST §R1 |
| 15 | Deck Audio Generator Localization | Connect `useTranslation('audio')` in `DeckAudioGeneratorPage`, connection gate, rule cards, queue monitor | M4 | ORIGINAL_REQUEST §R1 |
| 16 | Knowledge Base Guide Localization | Connect `useTranslation('guide')` in `GuidePage`, search, sidebar, Yomitan & MCP explorers, and `ContextHelpButton` | M4 | ORIGINAL_REQUEST §R1 |
| 17 | User Onboarding & Settings Coupling Fix | Connect `useTranslation('onboarding')` in modal, hero card, tour, and localize `constants.ts` to prevent Settings leak | M4 | ORIGINAL_REQUEST §R1 |
| 18 | Zero Visual Regression & Parity Verification | Ensure identical layout, padding, fonts, and instant language toggle without page reload | M5 | ORIGINAL_REQUEST §R2 |
| 19 | Full E2E & Production Build Verification | Pass Vitest test runner (`npm test`), TypeScript check (`npm run typecheck`), and Vite build (`npm run build`) | M5 | ORIGINAL_REQUEST Acceptance Criteria |
| 20 | Independent Victory Review & Forensic Audit | Multi-agent review (2 reviewers), adversarial challenge (2 challengers), and forensic audit (1 auditor) | M6 | ORIGINAL_REQUEST Coordination Rules |

---

## Milestones
| # | Name | Scope | Dependencies | Status | Subagent / Outputs |
|---|------|-------|-------------|--------|---------------------|
| 1 | Central i18n Foundation & All 6 Dictionaries | Create all 6 pairs of locale JSONs (`profile`, `wallet`, `card_templates`, `audio`, `guide`, `onboarding`), register in `index.ts` & `types.ts`, and expand `i18n.stress.test.tsx` | none | DONE | worker_o4_m1: 12 locale JSONs, index.ts, types.ts, i18n.stress.test.tsx (24/24 tests pass, typecheck 0 errors) |
| 2 | Profile & Wallet Localization | Localize all components in `features/profile/` and `features/wallet/`, decompose `ProfileEditDialog`, update schemas | M1 | DONE | worker_o4_m2: 14 components localized, ProfileEditDialog decomposed into 3 FSD subcomponents, schemas backward-compatible (15/15 tests pass, typecheck 0 errors) |
| 3 | Card Template Ecosystem Localization | Localize all components in `features/template-library/`, `features/template-versions/`, `features/template-distribution/` | M1 | DONE | worker_o4_m3: 10 components localized, new TemplateLocalization.test.tsx added (18 test files/233 tests pass, typecheck 0 errors) |
| 4 | Audio, Guide & Onboarding Localization | Localize all components in `features/audio/`, `features/guide/`, `features/onboarding/`, resolve Settings data leak | M1 | DONE | worker_o4_m4: 17 components localized, reactive getters for constants.ts, new guide.test.tsx added (6 test files/36 tests pass, typecheck 0 errors) |
| 5 | E2E Integration, Typecheck & Production Build | Run full Vitest test suites, full TypeScript typecheck, and Vite production build | M2, M3, M4 | DONE | worker_o4_m5: TEST_READY.md published, 185 tests passed across Tiers 1-4, typecheck 0 errors, Vite production build succeeded in 4.29s |
| 6 | Independent Review, Challenge & Forensic Audit | Independent verification by 2 Reviewers, 2 Challengers, and 1 Forensic Auditor | M5 | DONE | Forensic Auditor CLEAN, Reviewer 1 APPROVE; Remediation Worker resolved all review items (Yomitan key collision, Onboarding modal/hero/constants, Audio page/gate, Guide dropdown/explorer); all test suites pass, typecheck 0 errors, build 0 errors |

---

## Interface Contracts
### Central i18n Resource Map (`src/shared/config/i18n/`)
- `index.ts`:
  - `resources.vi`: { ..., profile, wallet, card_templates, audio, guide, onboarding }
  - `resources.en`: { ..., profile, wallet, card_templates, audio, guide, onboarding }
  - `ns`: ['common', ..., 'profile', 'wallet', 'card_templates', 'audio', 'guide', 'onboarding']
- `types.ts`:
  - `I18nResources` interface extends with `profile: typeof profile`, `wallet: typeof wallet`, `card_templates: typeof card_templates`, `audio: typeof audio`, `guide: typeof guide`, `onboarding: typeof onboarding`.
  - Type-safe `useTranslation(namespace)` autocomplete for all feature components.

### Feature Boundaries & File Ownership
- **Milestone 1**: Owns `frontend/src/shared/config/i18n/` (all new locale JSONs, `index.ts`, `types.ts`, `i18n.stress.test.tsx`).
- **Milestone 2**: Owns `frontend/src/features/profile/` and `frontend/src/features/wallet/`.
- **Milestone 3**: Owns `frontend/src/features/template-library/`, `frontend/src/features/template-versions/`, `frontend/src/features/template-distribution/`.
- **Milestone 4**: Owns `frontend/src/features/audio/`, `frontend/src/features/guide/`, `frontend/src/features/onboarding/`.
- **Milestone 5**: Full repository validation across `frontend/`.

---

## Code Layout
- Central i18n: `frontend/src/shared/config/i18n/`
  - `locales/vi/*.json` and `locales/en/*.json`
  - `index.ts`, `types.ts`, `translationKeys.test.ts`, `i18n.stress.test.tsx`
- Features:
  - `frontend/src/features/profile/`
  - `frontend/src/features/wallet/`
  - `frontend/src/features/template-library/`
  - `frontend/src/features/template-versions/`
  - `frontend/src/features/template-distribution/`
  - `frontend/src/features/audio/`
  - `frontend/src/features/guide/`
  - `frontend/src/features/onboarding/`
