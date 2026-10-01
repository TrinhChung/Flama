import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

export const statusPillVariants = cva(
  "inline-flex items-center justify-center font-medium border transition-colors select-none whitespace-nowrap",
  {
    variants: {
      variant: {
        new: "bg-sky-500/10 text-sky-700 border-sky-500/20 dark:bg-sky-500/20 dark:text-sky-400 dark:border-sky-500/30",
        learning:
          "bg-amber-500/10 text-amber-700 border-amber-500/20 dark:bg-amber-500/20 dark:text-amber-400 dark:border-amber-500/30",
        review:
          "bg-purple-500/10 text-purple-700 border-purple-500/20 dark:bg-purple-500/20 dark:text-purple-400 dark:border-purple-500/30",
        due: "bg-destructive/10 text-destructive border-destructive/20 dark:bg-destructive/20 dark:text-destructive dark:border-destructive/30",
        active:
          "bg-emerald-500/10 text-emerald-700 border-emerald-500/20 dark:bg-emerald-500/20 dark:text-emerald-400 dark:border-emerald-500/30",
        pending:
          "bg-yellow-500/15 text-yellow-800 border-yellow-500/25 dark:bg-yellow-500/20 dark:text-yellow-400 dark:border-yellow-500/30",
        revoked:
          "bg-muted text-muted-foreground border-border/80 dark:bg-muted/60 dark:text-muted-foreground dark:border-border/60",
        failed:
          "bg-rose-500/10 text-rose-700 border-rose-500/20 dark:bg-rose-500/20 dark:text-rose-400 dark:border-rose-500/30",
      },
      size: {
        sm: "h-5 px-2 text-[10px] gap-1 rounded-full",
        md: "h-6 px-2.5 text-xs gap-1.5 rounded-full",
      },
    },
    defaultVariants: {
      variant: "new",
      size: "sm",
    },
  }
)

export type StatusPillVariant = NonNullable<VariantProps<typeof statusPillVariants>["variant"]>

export interface StatusPillProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof statusPillVariants> {
  /** Whether to render a leading status dot indicator */
  dot?: boolean
  /** Animation style of the dot: 'solid' (static) or 'pulse' (animated ping) */
  dotStyle?: "solid" | "pulse"
  /** Polymorphic render prop (Radix Slot) */
  asChild?: boolean
}

export const StatusPill = React.forwardRef<HTMLSpanElement, StatusPillProps>(
  (
    {
      className,
      variant = "new",
      size = "sm",
      dot = false,
      dotStyle = "solid",
      asChild = false,
      children,
      ...props
    },
    ref
  ) => {
    if (asChild) {
      return (
        <Slot.Root
          ref={ref}
          className={cn(statusPillVariants({ variant, size }), className)}
          {...props}
        >
          {children}
        </Slot.Root>
      )
    }

    return (
      <span
        ref={ref}
        data-slot="status-pill"
        data-variant={variant}
        className={cn(statusPillVariants({ variant, size }), className)}
        {...props}
      >
        {dot && (
          <span
            data-slot="status-pill-dot"
            className="relative flex size-1.5 shrink-0"
            aria-hidden="true"
          >
            {dotStyle === "pulse" && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 bg-current" />
            )}
            <span className="relative inline-flex size-1.5 rounded-full bg-current" />
          </span>
        )}
        {children}
      </span>
    )
  }
)

StatusPill.displayName = "StatusPill"
