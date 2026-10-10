import * as React from "react"
import { cva } from "class-variance-authority"

import { cn } from "@/lib/utils"

export const splitPaneHandleVariants = cva(
  "relative shrink-0 select-none z-20 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
  {
    variants: {
      orientation: {
        horizontal:
          "w-1 cursor-col-resize hover:w-1.5 hover:bg-primary/60 bg-border/40 active:bg-primary",
        vertical:
          "h-1 cursor-row-resize hover:h-1.5 hover:bg-primary/60 bg-border/40 active:bg-primary",
      },
      isDragging: {
        true: "bg-primary w-1.5 h-1.5",
        false: "",
      },
    },
    defaultVariants: {
      orientation: "horizontal",
      isDragging: false,
    },
  }
)

/** A transparent gutter between panes with a centered grip, for card-based workspaces. */
const gutterHandleClasses = {
  horizontal: "group/split-handle relative z-20 flex w-5 shrink-0 cursor-col-resize touch-none items-center justify-center rounded-full outline-none select-none focus-visible:ring-2 focus-visible:ring-ring",
  vertical: "group/split-handle relative z-20 flex h-5 shrink-0 cursor-row-resize touch-none items-center justify-center rounded-full outline-none select-none focus-visible:ring-2 focus-visible:ring-ring",
} as const
const gutterGripClasses = {
  horizontal: "h-12 w-1",
  vertical: "h-1 w-12",
} as const

type SplitPaneBreakpoint = "md" | "lg"

// Written out in full so Tailwind can see every responsive class.
const RESPONSIVE_CLASSES: Record<SplitPaneBreakpoint, { direction: string; handle: string; sized: string; hidden: string }> = {
  md: { direction: "flex-col md:flex-row", handle: "hidden md:flex", sized: "w-full md:w-(--split-pane-size)", hidden: "hidden md:block" },
  lg: { direction: "flex-col lg:flex-row", handle: "hidden lg:flex", sized: "w-full lg:w-(--split-pane-size)", hidden: "hidden lg:block" },
}

export interface SplitPaneProps {
  /** Primary child pane (Left pane for horizontal, Top pane for vertical) */
  primaryPane: React.ReactNode
  /** Secondary child pane (Right pane for horizontal, Bottom pane for vertical) */
  secondaryPane: React.ReactNode
  /** Split orientation (default: 'horizontal') */
  orientation?: "horizontal" | "vertical"
  /** Unit of defaultSize, minSize, maxSize and step: pixels (default) or percent of the container */
  sizeUnit?: "px" | "percent"
  /** Initial size of the primary pane (default: 320) */
  defaultSize?: number
  /** Minimum allowed size of the primary pane (default: 240) */
  minSize?: number
  /** Maximum allowed size of the primary pane (default: 600) */
  maxSize?: number
  /** Step size for keyboard arrow key navigation (default: 10) */
  step?: number
  /** LocalStorage key for persisting user drag preferences (e.g. 'flama:browse:editor-width') */
  storageKey?: string
  /** Callback fired whenever the pane size changes */
  onSizeChange?: (size: number) => void
  /** Responsive mobile fallback: switches to a single-pane view below `collapseBelow` (default: true) */
  responsive?: boolean
  /** Breakpoint below which a horizontal split shows one pane at a time (default: 'md') */
  collapseBelow?: SplitPaneBreakpoint
  /** Active pane when in mobile responsive mode ('primary' | 'secondary', default: 'primary') */
  mobileActivePane?: "primary" | "secondary"
  /** Disables resizing interaction */
  disabled?: boolean
  /** Divider style: a thin line (default) or a transparent gutter with a grip */
  handleAppearance?: "line" | "gutter"
  /** Accessible name of the divider */
  handleLabel?: string
  /** Additional container CSS class */
  className?: string
  /** Additional primary pane CSS class (e.g. to replace the default `overflow-auto`) */
  primaryClassName?: string
  /** Additional secondary pane CSS class */
  secondaryClassName?: string
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

export function SplitPane({
  primaryPane,
  secondaryPane,
  orientation = "horizontal",
  sizeUnit = "px",
  defaultSize = 320,
  minSize = 240,
  maxSize = 600,
  step = 10,
  storageKey,
  onSizeChange,
  responsive = true,
  collapseBelow = "md",
  mobileActivePane = "primary",
  disabled = false,
  handleAppearance = "line",
  handleLabel = "Kéo để thay đổi kích thước",
  className,
  primaryClassName,
  secondaryClassName,
}: SplitPaneProps) {
  const isHorizontal = orientation === "horizontal"
  const isPercent = sizeUnit === "percent"
  const containerRef = React.useRef<HTMLDivElement | null>(null)
  const stopDraggingRef = React.useRef<(() => void) | null>(null)

  const getInitialSize = React.useCallback(() => {
    if (storageKey && typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem(storageKey)
        if (stored !== null) {
          const parsed = parseFloat(stored)
          if (!isNaN(parsed)) {
            return clamp(parsed, minSize, maxSize)
          }
        }
      } catch {
        // Ignore localStorage errors (security / private mode)
      }
    }
    return clamp(defaultSize, minSize, maxSize)
  }, [storageKey, minSize, maxSize, defaultSize])

  const [size, setSize] = React.useState<number>(getInitialSize)
  const [isDragging, setIsDragging] = React.useState(false)

  // Sync if storageKey changes
  React.useEffect(() => {
    setSize(getInitialSize())
  }, [getInitialSize])

  // A pane unmounted mid-drag must not leave window listeners behind.
  React.useEffect(() => () => stopDraggingRef.current?.(), [])

  const persistSize = React.useCallback(
    (newSize: number) => {
      if (storageKey && typeof window !== "undefined") {
        try {
          localStorage.setItem(storageKey, String(newSize))
        } catch {
          // Ignore storage failures
        }
      }
    },
    [storageKey]
  )

  const updateSize = React.useCallback(
    (newSize: number) => {
      const clamped = clamp(isPercent ? Math.round(newSize * 10) / 10 : newSize, minSize, maxSize)
      setSize(clamped)
      onSizeChange?.(clamped)
      return clamped
    },
    [isPercent, minSize, maxSize, onSizeChange]
  )

  /** Converts a pointer delta in pixels into the configured size unit. */
  const toSizeUnit = React.useCallback(
    (pixels: number) => {
      if (!isPercent) return pixels
      const rect = containerRef.current?.getBoundingClientRect()
      const total = rect ? (isHorizontal ? rect.width : rect.height) : 0
      return total > 0 ? (pixels / total) * 100 : 0
    },
    [isPercent, isHorizontal]
  )

  const handlePointerDown = React.useCallback(
    (e: React.PointerEvent<HTMLDivElement> | React.MouseEvent<HTMLDivElement>) => {
      if (disabled || e.button !== 0) return
      e.preventDefault()
      stopDraggingRef.current?.()
      setIsDragging(true)

      const startCoord = isHorizontal ? e.clientX : e.clientY
      const startSize = size

      function handlePointerMove(moveEvent: PointerEvent | MouseEvent) {
        const currentCoord = isHorizontal ? moveEvent.clientX : moveEvent.clientY
        updateSize(startSize + toSizeUnit(currentCoord - startCoord))
      }

      function removeListeners() {
        window.removeEventListener("pointermove", handlePointerMove)
        window.removeEventListener("pointerup", handlePointerUp)
        window.removeEventListener("mousemove", handlePointerMove)
        window.removeEventListener("mouseup", handlePointerUp)
        stopDraggingRef.current = null
      }

      function handlePointerUp(upEvent: PointerEvent | MouseEvent) {
        const currentCoord = isHorizontal ? upEvent.clientX : upEvent.clientY
        persistSize(updateSize(startSize + toSizeUnit(currentCoord - startCoord)))
        setIsDragging(false)
        removeListeners()
      }

      stopDraggingRef.current = removeListeners
      window.addEventListener("pointermove", handlePointerMove)
      window.addEventListener("pointerup", handlePointerUp)
      window.addEventListener("mousemove", handlePointerMove)
      window.addEventListener("mouseup", handlePointerUp)
    },
    [disabled, isHorizontal, size, updateSize, persistSize, toSizeUnit]
  )

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (disabled) return
      let newSize: number | null = null

      if (isHorizontal) {
        if (e.key === "ArrowLeft") {
          e.preventDefault()
          newSize = size - step
        } else if (e.key === "ArrowRight") {
          e.preventDefault()
          newSize = size + step
        }
      } else {
        if (e.key === "ArrowUp") {
          e.preventDefault()
          newSize = size - step
        } else if (e.key === "ArrowDown") {
          e.preventDefault()
          newSize = size + step
        }
      }

      if (e.key === "Home") {
        e.preventDefault()
        newSize = minSize
      } else if (e.key === "End") {
        e.preventDefault()
        newSize = maxSize
      } else if (e.key === "Enter") {
        e.preventDefault()
        newSize = defaultSize
      }

      if (newSize !== null) {
        const clamped = updateSize(newSize)
        persistSize(clamped)
      }
    },
    [disabled, isHorizontal, size, step, minSize, maxSize, defaultSize, updateSize, persistSize]
  )

  const handleDoubleClick = React.useCallback(() => {
    if (disabled) return
    const clamped = updateSize(defaultSize)
    persistSize(clamped)
  }, [disabled, defaultSize, updateSize, persistSize])

  const layout = RESPONSIVE_CLASSES[collapseBelow]
  const stacks = responsive && isHorizontal
  const containerStyle = { "--split-pane-size": `${size}${isPercent ? "%" : "px"}` } as React.CSSProperties
  const primarySizeClass = isHorizontal
    ? stacks ? layout.sized : "w-(--split-pane-size)"
    : "h-(--split-pane-size)"

  return (
    <div
      ref={containerRef}
      data-slot="split-pane"
      style={containerStyle}
      className={cn(
        "relative flex size-full overflow-hidden",
        isHorizontal ? (stacks ? layout.direction : "flex-row") : "flex-col",
        className
      )}
    >
      {/* Primary Pane */}
      <div
        data-slot="split-pane-primary"
        className={cn(
          "shrink-0 overflow-auto",
          primarySizeClass,
          responsive && mobileActivePane === "secondary" ? layout.hidden : "block",
          primaryClassName
        )}
      >
        {primaryPane}
      </div>

      {/* Resizable Divider Handle */}
      <div
        role="separator"
        tabIndex={disabled ? -1 : 0}
        aria-orientation={orientation}
        aria-valuenow={Math.round(size)}
        aria-valuemin={minSize}
        aria-valuemax={maxSize}
        aria-valuetext={isPercent ? `${Math.round(size)}%` : undefined}
        aria-label={handleLabel}
        data-slot="split-pane-handle"
        data-dragging={isDragging || undefined}
        onPointerDown={handlePointerDown}
        onMouseDown={handlePointerDown}
        onKeyDown={handleKeyDown}
        onDoubleClick={handleDoubleClick}
        className={cn(
          handleAppearance === "gutter"
            ? gutterHandleClasses[orientation]
            : splitPaneHandleVariants({ orientation, isDragging }),
          responsive && (stacks ? layout.handle : "hidden md:flex"),
          disabled && "pointer-events-none opacity-40 cursor-default"
        )}
      >
        {handleAppearance === "gutter" ? (
          <span
            aria-hidden="true"
            className={cn(
              "rounded-full bg-border transition-colors group-hover/split-handle:bg-primary/50 group-focus-visible/split-handle:bg-primary",
              gutterGripClasses[orientation],
              isDragging && "bg-primary"
            )}
          />
        ) : null}
      </div>

      {/* Secondary Pane */}
      <div
        data-slot="split-pane-secondary"
        className={cn(
          "min-h-0 min-w-0 flex-1 overflow-auto",
          responsive && mobileActivePane === "primary" ? layout.hidden : "block",
          secondaryClassName
        )}
      >
        {secondaryPane}
      </div>

      {/* While dragging, a page-wide shield keeps iframes (card previews) from swallowing pointer events. */}
      {isDragging ? (
        <div
          aria-hidden="true"
          data-slot="split-pane-drag-shield"
          className={cn("fixed inset-0 z-50", isHorizontal ? "cursor-col-resize" : "cursor-row-resize")}
        />
      ) : null}
    </div>
  )
}
