# Button Component - Flama UI

## 1. Overview

The `Button` component (`frontend/src/components/ui/button.tsx`) is a foundational UI primitive built with Radix UI Slot and Tailwind CSS using `class-variance-authority` (cva). It adheres to the Flama Design System, supporting multiple semantic variants, sizes, and slot composition.

---

## 2. Component Import & Usage

```tsx
import { Button } from "@/components/ui/button"
import { Plus, Trash2 } from "lucide-react"

export function Example() {
  return (
    <div className="flex items-center gap-2">
      <Button variant="default">Primary Action</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="outline">Outline</Button>
      <Button variant="destructive" size="sm">
        <Trash2 className="size-4" />
        Delete
      </Button>
    </div>
  )
}
```

---

## 3. Variants

| Variant | Visual Style | Primary Use Case |
|---|---|---|
| `default` | Primary solid (`bg-primary text-primary-foreground`) | Main Call-To-Action (CTA), Submit, Primary actions |
| `secondary` | Muted solid (`bg-secondary text-secondary-foreground`) | Supporting actions, Secondary modals |
| `outline` | Bordered (`border-border bg-background`) | Neutral actions, Cancel, Filters |
| `ghost` | Transparent with hover highlight | Toolbar buttons, Table row actions |
| `destructive` | Alert tint (`bg-destructive/10 text-destructive`) | Delete, Discard, Revoke actions |
| `link` | Underlined text | Inline navigation links styled as buttons |

---

## 4. Sizes

| Size | Height | Best For |
|---|---|---|
| `default` | `h-8` (32px) | Standard form buttons, header actions |
| `sm` | `h-7` (28px) | Compact cards, inline table controls |
| `xs` | `h-6` (24px) | Badges with actions, tight spaces |
| `lg` | `h-9` (36px) | Prominent landing/study action buttons |
| `icon` | `size-8` | Square icon button |
| `icon-sm` | `size-7` | Small square icon button |
| `icon-xs` | `size-6` | Extra small icon button |
| `icon-lg` | `size-9` | Large icon button |

---

## 5. Composition with `asChild`

When you need a link (e.g. React Router `<Link>`) that looks and behaves like a button, use the `asChild` prop:

```tsx
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"

<Button asChild variant="default">
  <Link to="/study">Start Studying</Link>
</Button>
```
