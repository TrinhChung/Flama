---
name: frontend-architecture
description: Architect, decompose, refactor, and unify React components following Clean Architecture, Feature-Sliced Design (FSD), design tokens, reusable UI primitives (shadcn/ui + Radix UI), and custom hook isolation in frontend/src/.
allowed-tools:
  - "Read"
  - "Write"
  - "Edit"
  - "Bash"
  - "Grep"
  - "Glob"
---

# Frontend Component Architecture & Clean Code Skill

You are a **Principal Frontend Architect** specializing in React 18+, TypeScript, Feature-Sliced Design (FSD), Tailwind CSS, and shadcn/Radix UI systems. Your mission is to eliminate monolithic code, prevent UI duplication, enforce design consistency, and structure components for maximum reusability, testability, and maintainability in `frontend/src/`.

---

## 0. Zero Visual Regression Rule (Bảo toàn thiết kế gốc)

> **CRITICAL RULE**: Khi refactor kiến trúc code (tách hook, bẻ nhỏ component, thay thẻ HTML thô bằng UI Primitives):
> **BẮT BUỘC BẢO TOÀN 100% GIAO DIỆN & THIẾT KẾ BAN ĐẦU** (màu sắc, dải gradient thương hiệu, padding, font size, icon, đổ bóng, layout vị trí).
> - ❌ **CẤM** tự ý thay đổi màu sắc nút bấm, xóa bỏ gradient nhận diện thương hiệu, hoặc biến đổi kiểu dáng sẵn có của người dùng trừ khi người dùng yêu cầu redesign.
> - ✅ Mọi thao tác refactor chỉ tập trung vào: bóc tách logic vào custom hooks, chuẩn hóa thẻ thô sang UI Primitives với styling nguyên bản, nâng cao accessibility (a11y), và chống lặp code.

---

## 1. The 4-Tier Component Hierarchy

Every component in the codebase MUST belong to one of four clear tiers:

```text
┌─────────────────────────────────────────────────────────────┐
│ Tier 4: Pages / Route Views (src/pages/ or features/*/pages)│  <-- Thin view wrappers, route params, layout binding
├─────────────────────────────────────────────────────────────┤
│ Tier 3: Feature Domain (src/features/<domain>/)             │  <-- Domain logic, feature components, feature hooks
├─────────────────────────────────────────────────────────────┤
│ Tier 2: Shared UI Blocks (src/components/shared/ & global)  │  <-- App-wide reusable composite blocks (PageHeader, MetricCard)
├─────────────────────────────────────────────────────────────┤
│ Tier 1: UI Primitives (src/components/ui/)                  │  <-- Stateless primitives (Button, Dialog, Input) + CVA
└─────────────────────────────────────────────────────────────┘
```

### Tier 1: UI Primitives (`frontend/src/components/ui/`)
- **Nature**: Stateless, domain-agnostic, headless/accessible (Radix UI / Lucide).
- **Styling**: Managed strictly through `class-variance-authority` (`cva`) with `variant` and `size` props.
- **Rule**: NEVER write raw HTML `<button>`, `<input>`, `<select>`, `<dialog>`, or custom tooltips in feature code. Always import from `@/components/ui/`.

### Tier 2: Shared UI Blocks (`frontend/src/components/shared/` or global `src/components/`)
- **Nature**: Domain-agnostic composite UI components used across 2+ features.
- **Examples**: `PageHeader`, `EmptyState`, `SearchFilterBar`, `ConfirmDialog`, `MetricCard`, `DataTableWrapper`, `StatusBadge`.
- **Rule**: If a UI layout or composite pattern appears in more than one feature, extract it here immediately.

### Tier 3: Feature Modules (`frontend/src/features/<domain>/`)
Organized by business domain (e.g., `study`, `browse`, `marketplace`, `import`, `audio`, `admin`).
Each feature module must strictly follow this internal structure:
```text
features/<domain>/
├── components/          # Private UI components specific to this feature
├── hooks/               # Domain hooks (data fetching, state machines, business workflows)
├── pages/               # Route pages specific to this domain
├── types.ts             # Domain-specific TypeScript interfaces & DTOs
└── utils/               # Domain-specific helpers & formatters
```

### Tier 4: Route Pages (`frontend/src/pages/` or `features/<domain>/pages/`)
- **Nature**: Thin orchestrators (< 120 lines).
- **Responsibilities**: Read route params, invoke top-level feature hooks/containers, and pass props down.
- **Rule**: A Page component must NEVER contain complex inline business logic, direct API fetch orchestrations, or deeply nested inline JSX.

---

## 2. Component Decomposition & Monolith Refactoring

### The 200-Line Threshold Rule
Any component exceeding **200 lines of code** is a code smell and MUST be evaluated for decomposition into:
1. **Container vs. Presentational**:
   - *Container / Hook*: Handles state, side-effects, API calls, and handlers.
   - *Presentational*: Pure function receiving props and returning JSX.
2. **Sub-component extraction**:
   - Extract list items, table rows, form sections, modal dialogs, toolbar controls into focused sub-components in `components/`.

### Logic Isolation via Custom Hooks
- **No inline side-effect clutter**: Complex `useEffect`, `useState` clusters (> 4 states), and TanStack Query calls must be extracted into dedicated custom hooks in `features/<domain>/hooks/use<FeatureName>.ts` or `src/hooks/`.
- **Return clean APIs**: Custom hooks should expose a semantic API (e.g. `{ data, isLoading, onSave, onFilterChange }`).

---

## 3. Design System & Token Enforcement

### Zero Hardcoding Policy
- ❌ **Forbidden**: Arbitrary hex colors (`#f59e0b`, `bg-[#1e293b]`), arbitrary spacing (`p-[13px]`, `w-[342px]`), uncalibrated font sizes.
- ✅ **Required**: Use CSS variable design tokens and Tailwind theme classes defined in `frontend/src/index.css`:
  - Backgrounds: `bg-background`, `bg-card`, `bg-popover`, `bg-muted`, `bg-accent`
  - Foregrounds: `text-foreground`, `text-muted-foreground`, `text-primary-foreground`
  - Borders: `border-border`, `border-input`
  - Accents/States: `bg-primary`, `bg-destructive`, `text-destructive`, `bg-success`

### Consistent Component Variants with CVA
When creating or refactoring composite components that need multiple visual styles, use `class-variance-authority`:
```typescript
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const cardVariants = cva(
  "rounded-xl border transition-all duration-200",
  {
    variants: {
      variant: {
        default: "bg-card text-card-foreground border-border shadow-xs",
        interactive: "bg-card hover:border-primary/50 hover:shadow-md cursor-pointer",
        highlighted: "bg-primary/5 border-primary/20",
        destructive: "bg-destructive/10 border-destructive/30",
      },
      padding: {
        none: "p-0",
        sm: "p-3",
        md: "p-5",
        lg: "p-7",
      },
    },
    defaultVariants: {
      variant: "default",
      padding: "md",
    },
  }
)
```

---

## 4. Anti-Patterns & Enforcement Checklist

### ❌ Anti-Patterns to Avoid
1. **Monolithic Page Files**: Stacking 500+ lines of markup, state, and fetch logic in one file.
2. **HTML Element Sprawl**: Using raw `<button>`, `<input>`, or `<select>` instead of `@/components/ui/*`.
3. **Copy-Paste UI Islands**: Writing the same Card, Badge, or Audio Player markup in 3 different feature folders.
4. **Prop Drilling Hell**: Passing callbacks through 5 layers instead of using domain context or custom hooks.
5. **Untyped Props**: Using `any` or skipping explicit TypeScript interfaces for component props.
6. **Inline Inline-Styles**: Writing `style={{ margin: 12 }}` instead of Tailwind classes.

### ✅ Quality Checklist for Every Component
- [ ] Component is located in the correct tier (Primitive, Shared, Feature, or Page).
- [ ] File length is concise (target < 150-200 lines).
- [ ] Business logic and queries are isolated into a custom hook.
- [ ] Uses UI primitives from `@/components/ui/` instead of raw HTML elements.
- [ ] Follows design system color/spacing tokens (no arbitrary hex or arbitrary pixel classes).
- [ ] Props are defined with a clean TypeScript interface (`interface [ComponentName]Props`).
- [ ] Multi-state layouts have clear Loading, Error, and Empty states.
- [ ] Accessible (keyboard navigable, aria attributes where needed, focus states).

---

## 5. Architectural Refactoring Workflow

When asked to refactor or build a feature:
1. **Audit & Map**:
   - Inspect existing components in `frontend/src/features/<domain>/` and `frontend/src/components/`.
   - Identify shared UI primitives or patterns that already exist to reuse them.
2. **Extract Base Primitives & Shared Blocks**:
   - If missing, create/extend primitives in `components/ui/` or composite blocks in `components/shared/`.
3. **Extract Domain Logic Hook**:
   - Create `use<Feature>.ts` encapsulating state, queries, and mutations.
4. **Build Decomposed Presentational Components**:
   - Break UI down into sub-components (Header, Body, Card, FilterBar, Dialog).
5. **Assemble Clean Page / Container**:
   - Connect the hook to presentational components with clean prop passing.
6. **Verify Consistency**:
   - Check TypeScript compilation (`tsc --noEmit`) and ensure zero styling regressions.
