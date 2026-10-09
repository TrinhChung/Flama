# E2E Test Infra: Flama End-User i18n Localization

## Test Philosophy
- Opaque-box & contract-driven verification for internationalization (i18n).
- 100% dictionary leaf-key parity between `vi` and `en` without undefined, null, or empty string values.
- Dynamic instant switching via `LanguageSwitcher` without page reload.
- Zero visual regression across all screen breakpoints and interaction flows.

---

## Feature Inventory & Test Matrix
| # | Feature / Namespace | Tier 1 (Parity & Non-Empty) | Tier 2 (Boundaries & Edge Keys) | Tier 3 (Cross-Component Links) | Tier 4 (E2E Render & Switch) |
|---|---------------------|:---------------------------:|:-------------------------------:|:------------------------------:|:----------------------------:|
| 1 | `profile` | ≥5 tests | ≥5 tests | ✓ | ✓ |
| 2 | `wallet` | ≥5 tests | ≥5 tests | ✓ | ✓ |
| 3 | `card_templates` | ≥5 tests | ≥5 tests | ✓ | ✓ |
| 4 | `audio` | ≥5 tests | ≥5 tests | ✓ | ✓ |
| 5 | `guide` | ≥5 tests | ≥5 tests | ✓ | ✓ |
| 6 | `onboarding` | ≥5 tests | ≥5 tests | ✓ | ✓ |

---

## Test Architecture
- **Static AST Contract Suite**: `frontend/src/shared/config/i18n/translationKeys.test.ts`
  - Parses all TypeScript JSX/TS files with TypeScript compiler API.
  - Verifies that every key referenced by `useTranslation(ns)` and `t('...')` exists in both `resources.vi[ns]` and `resources.en[ns]`.
- **Runtime Parity & Stress Suite**: `frontend/src/shared/config/i18n/i18n.stress.test.tsx`
  - Deep-compares leaf keys between `vi` and `en` for all 25 registered namespaces.
  - Asserts 0 missing keys, 0 undefined values, 0 empty strings (`""`), and symmetrical data types.
  - Tests dynamic language switching (`i18n.changeLanguage('en')` -> `i18n.changeLanguage('vi')`) with React components.
- **Unit & Component Regression Suites**:
  - `src/features/profile/`: `ProfileEditDialog.test.tsx`, `schemas.test.ts`.
  - `src/features/template-library/`: 7 test files (252 tests in template domain).
  - `src/features/audio/` & `src/features/onboarding/`: `onboarding.test.tsx`.
- **Typecheck & Production Build**:
  - `npm --prefix frontend run typecheck` (`tsc --noEmit`).
  - `npm --prefix frontend run build` (Vite production bundle build).

---

## Coverage Thresholds
- **Tier 1 (Feature Coverage)**: All 6 new namespaces (`profile`, `wallet`, `card_templates`, `audio`, `guide`, `onboarding`) tested for 100% leaf-key presence.
- **Tier 2 (Boundary & Corner)**: No empty strings (`""`), no missing nested objects, no dangling keys.
- **Tier 3 (Cross-Feature Combinations)**: Settings and Onboarding inter-operation verified with zero leakage of Vietnamese strings when English is selected.
- **Tier 4 (Real-World Application Scenarios)**: Language switching dynamically updates UI across Profile, Wallet, Templates, Audio, Guide, and Onboarding with 0 errors and zero visual glitch.
