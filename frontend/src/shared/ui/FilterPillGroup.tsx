import * as React from "react"
import { cva } from "class-variance-authority"

import { cn } from "@/lib/utils"

export const filterPillGroupVariants = cva(
  "flex items-center gap-1.5 select-none",
  {
    variants: {
      scrollable: {
        true: "flex-nowrap overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden overscroll-x-contain py-1",
        false: "flex-wrap",
      },
      size: {
        sm: "text-xs",
        md: "text-sm",
      },
    },
    defaultVariants: {
      scrollable: true,
      size: "sm",
    },
  }
)

export const filterPillItemVariants = cva(
  "group inline-flex shrink-0 items-center gap-1.5 font-semibold rounded-full border transition-all cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      active: {
        true: "bg-primary text-primary-foreground border-primary shadow-2xs font-bold",
        false: "bg-card text-muted-foreground border-border/80 hover:bg-muted hover:text-foreground",
      },
      size: {
        sm: "h-7 px-2.5 text-xs [&>svg]:size-3",
        md: "h-8 px-3.5 text-xs sm:text-sm [&>svg]:size-3.5",
      },
    },
    defaultVariants: {
      active: false,
      size: "sm",
    },
  }
)

export const filterPillBadgeVariants = cva(
  "ml-0.5 rounded-full px-1.5 py-0.2 text-[10px] font-bold tabular-nums transition-colors",
  {
    variants: {
      active: {
        true: "bg-primary-foreground/20 text-primary-foreground",
        false: "bg-muted text-muted-foreground group-hover:bg-muted/80 group-hover:text-foreground",
      },
    },
    defaultVariants: {
      active: false,
    },
  }
)

export interface FilterPillOption<T extends string = string> {
  /** Unique identifier / value for the filter option */
  value: T
  /** Visible label for the pill */
  label: React.ReactNode
  /** Optional numeric badge count (e.g. 12 cards, 0 pending) */
  count?: number
  /** Optional semantic status indicator dot color class (e.g. 'bg-emerald-500', 'bg-amber-500') */
  dotColor?: string
  /** Optional icon rendered before the label */
  icon?: React.ComponentType<{ className?: string }>
  /** Disables selection for this specific option */
  disabled?: boolean
}

interface FilterPillGroupBaseProps<T extends string = string> {
  /** List of available filter options */
  options: FilterPillOption<T>[]
  /** Optional label rendered before pills (e.g. 'Trạng thái:') */
  label?: React.ReactNode
  /** Size variant for pills */
  size?: "sm" | "md"
  /** Whether the container enables horizontal scrolling with hidden scrollbar (default: true) */
  scrollable?: boolean
  /** Disables the entire filter group */
  disabled?: boolean
  /** Accessible label for the group */
  "aria-label"?: string
  /** Additional container CSS class */
  className?: string
}

export interface FilterPillGroupSingleProps<T extends string = string>
  extends FilterPillGroupBaseProps<T> {
  /** Selection mode: single-select (default) */
  mode?: "single"
  /** Currently active value */
  value: T
  /** Callback fired when selection changes */
  onChange: (value: T) => void
}

export interface FilterPillGroupMultiProps<T extends string = string>
  extends FilterPillGroupBaseProps<T> {
  /** Selection mode: multi-select */
  mode: "multiple"
  /** Currently active values array */
  value: T[]
  /** Callback fired when selection changes */
  onChange: (value: T[]) => void
}

export type FilterPillGroupProps<T extends string = string> =
  | FilterPillGroupSingleProps<T>
  | FilterPillGroupMultiProps<T>

export function FilterPillGroup<T extends string = string>(props: FilterPillGroupProps<T>) {
  const {
    options,
    label,
    size = "sm",
    scrollable = true,
    disabled = false,
    "aria-label": ariaLabel,
    className,
  } = props

  const isMulti = props.mode === "multiple"
  const itemRefs = React.useRef<(HTMLButtonElement | null)[]>([])

  const enabledOptions = React.useMemo(() => {
    return options.map((opt, idx) => ({ opt, idx })).filter(({ opt }) => !opt.disabled && !disabled)
  }, [options, disabled])

  // Roving tabindex calculation for single-select
  const activeSingleIndex = React.useMemo(() => {
    if (isMulti) return -1
    const singleVal = (props as FilterPillGroupSingleProps<T>).value
    return options.findIndex((opt) => opt.value === singleVal)
  }, [isMulti, options, props])

  const focusableIndex = React.useMemo(() => {
    if (isMulti) return -1
    if (activeSingleIndex >= 0 && !options[activeSingleIndex]?.disabled && !disabled) {
      return activeSingleIndex
    }
    const firstEnabled = enabledOptions[0]
    return firstEnabled !== undefined ? firstEnabled.idx : -1
  }, [isMulti, activeSingleIndex, options, disabled, enabledOptions])

  const handleSingleSelect = React.useCallback(
    (val: T, index: number) => {
      if (disabled) return
      ;(props as FilterPillGroupSingleProps<T>).onChange(val)
      itemRefs.current[index]?.focus()
    },
    [disabled, props]
  )

  const handleMultiToggle = React.useCallback(
    (val: T) => {
      if (disabled) return
      const multiProps = props as FilterPillGroupMultiProps<T>
      const currentValues = multiProps.value || []
      const nextValues = currentValues.includes(val)
        ? currentValues.filter((v) => v !== val)
        : [...currentValues, val]
      multiProps.onChange(nextValues)
    },
    [disabled, props]
  )

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
      if (disabled) return
      const key = e.key

      if (isMulti) {
        if (key === " " || key === "Enter") {
          e.preventDefault()
          const opt = options[currentIndex]
          if (opt && !opt.disabled) {
            handleMultiToggle(opt.value)
          }
        }
        return
      }

      // Single-select roving keyboard navigation
      const currentEnabledPos = enabledOptions.findIndex((item) => item.idx === currentIndex)
      if (currentEnabledPos === -1 && enabledOptions.length === 0) return

      let targetPos = -1

      if (key === "ArrowRight" || key === "ArrowDown") {
        e.preventDefault()
        targetPos = (currentEnabledPos + 1) % enabledOptions.length
      } else if (key === "ArrowLeft" || key === "ArrowUp") {
        e.preventDefault()
        targetPos = (currentEnabledPos - 1 + enabledOptions.length) % enabledOptions.length
      } else if (key === "Home") {
        e.preventDefault()
        targetPos = 0
      } else if (key === "End") {
        e.preventDefault()
        targetPos = enabledOptions.length - 1
      } else if (key === " " || key === "Enter") {
        e.preventDefault()
        const opt = options[currentIndex]
        if (opt && !opt.disabled) {
          handleSingleSelect(opt.value, currentIndex)
        }
        return
      }

      if (targetPos >= 0 && targetPos < enabledOptions.length) {
        const nextItem = enabledOptions[targetPos]
        handleSingleSelect(nextItem.opt.value, nextItem.idx)
        itemRefs.current[nextItem.idx]?.focus()
      }
    },
    [disabled, isMulti, enabledOptions, options, handleMultiToggle, handleSingleSelect]
  )

  if (!options || options.length === 0) {
    return null
  }

  return (
    <div
      role={isMulti ? "group" : "radiogroup"}
      aria-label={ariaLabel}
      data-slot="filter-pill-group"
      className={cn(filterPillGroupVariants({ scrollable, size }), className)}
    >
      {label && (
        <span
          data-slot="filter-pill-label"
          className="text-xs font-semibold text-muted-foreground mr-1 shrink-0"
        >
          {label}
        </span>
      )}
      {options.map((option, index) => {
        const isOptionDisabled = disabled || Boolean(option.disabled)
        const isActive = isMulti
          ? ((props as FilterPillGroupMultiProps<T>).value || []).includes(option.value)
          : (props as FilterPillGroupSingleProps<T>).value === option.value

        const tabIndex = isMulti
          ? isOptionDisabled
            ? -1
            : 0
          : focusableIndex === index
            ? 0
            : -1

        const Icon = option.icon

        return (
          <button
            key={option.value}
            ref={(el) => {
              itemRefs.current[index] = el
            }}
            type="button"
            role={isMulti ? "checkbox" : "radio"}
            aria-checked={isActive}
            disabled={isOptionDisabled}
            tabIndex={tabIndex}
            data-active={isActive ? "true" : "false"}
            onClick={() => {
              if (isOptionDisabled) return
              if (isMulti) {
                handleMultiToggle(option.value)
              } else {
                handleSingleSelect(option.value, index)
              }
            }}
            onKeyDown={(e) => handleKeyDown(e, index)}
            className={cn(
              filterPillItemVariants({
                active: isActive,
                size,
              })
            )}
          >
            {option.dotColor && (
              <span
                data-slot="filter-pill-dot"
                className={cn("size-2 rounded-full shrink-0", option.dotColor)}
                aria-hidden="true"
              />
            )}
            {Icon && (
              <Icon
                className={cn(
                  "shrink-0",
                  size === "sm" ? "size-3" : "size-3.5"
                )}
                aria-hidden="true"
              />
            )}
            <span>{option.label}</span>
            {option.count !== undefined && (
              <span
                data-slot="filter-pill-badge"
                className={cn(filterPillBadgeVariants({ active: isActive }))}
              >
                {option.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
