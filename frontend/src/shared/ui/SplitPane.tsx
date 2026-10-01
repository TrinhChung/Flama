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

export interface SplitPaneProps {
  /** Primary child pane (Left pane for horizontal, Top pane for vertical) */
  primaryPane: React.ReactNode
  /** Secondary child pane (Right pane for horizontal, Bottom pane for vertical) */
  secondaryPane: React.ReactNode
  /** Split orientation (default: 'horizontal') */
  orientation?: "horizontal" | "vertical"
  /** Initial size in pixels of the primary pane (default: 320) */
  defaultSize?: number
  /** Minimum allowed size in pixels of the primary pane (default: 240) */
  minSize?: number
  /** Maximum allowed size in pixels of the primary pane (default: 600) */
  maxSize?: number
  /** Step size in pixels for keyboard arrow key navigation (default: 10) */
  step?: number
  /** LocalStorage key for persisting user drag preferences (e.g. 'flama:browse:editor-width') */
  storageKey?: string
  /** Callback fired whenever the pane size changes */
  onSizeChange?: (size: number) => void
  /** Responsive mobile fallback: switches to stacked or single-pane view on screens <768px (default: true) */
  responsive?: boolean
  /** Active pane when in mobile responsive mode ('primary' | 'secondary', default: 'primary') */
  mobileActivePane?: "primary" | "secondary"
  /** Disables resizing interaction */
  disabled?: boolean
  /** Additional container CSS class */
  className?: string
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

export function SplitPane({
  primaryPane,
  secondaryPane,
  orientation = "horizontal",
  defaultSize = 320,
  minSize = 240,
  maxSize = 600,
  step = 10,
  storageKey,
  onSizeChange,
  responsive = true,
  mobileActivePane = "primary",
  disabled = false,
  className,
}: SplitPaneProps) {
  const isHorizontal = orientation === "horizontal"

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
      const clamped = clamp(newSize, minSize, maxSize)
      setSize(clamped)
      onSizeChange?.(clamped)
      return clamped
    },
    [minSize, maxSize, onSizeChange]
  )

  const handlePointerDown = React.useCallback(
    (e: React.PointerEvent<HTMLDivElement> | React.MouseEvent<HTMLDivElement>) => {
      if (disabled) return
      e.preventDefault()
      setIsDragging(true)

      const startCoord = isHorizontal ? e.clientX : e.clientY
      const startSize = size

      const handlePointerMove = (moveEvent: PointerEvent | MouseEvent) => {
        const currentCoord = isHorizontal ? moveEvent.clientX : moveEvent.clientY
        const delta = currentCoord - startCoord
        updateSize(startSize + delta)
      }

      const handlePointerUp = (upEvent: PointerEvent | MouseEvent) => {
        const currentCoord = isHorizontal ? upEvent.clientX : upEvent.clientY
        const delta = currentCoord - startCoord
        const finalSize = updateSize(startSize + delta)
        persistSize(finalSize)

        setIsDragging(false)
        window.removeEventListener("pointermove", handlePointerMove)
        window.removeEventListener("pointerup", handlePointerUp)
        window.removeEventListener("mousemove", handlePointerMove)
        window.removeEventListener("mouseup", handlePointerUp)
      }

      window.addEventListener("pointermove", handlePointerMove)
      window.addEventListener("pointerup", handlePointerUp)
      window.addEventListener("mousemove", handlePointerMove)
      window.addEventListener("mouseup", handlePointerUp)
    },
    [disabled, isHorizontal, size, updateSize, persistSize]
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

  const primaryStyle: React.CSSProperties = isHorizontal
    ? { width: `${size}px`, flexShrink: 0 }
    : { height: `${size}px`, flexShrink: 0 }

  return (
    <div
      data-slot="split-pane"
      className={cn(
        "relative flex size-full overflow-hidden",
        isHorizontal ? "flex-col md:flex-row" : "flex-col",
        className
      )}
    >
      {/* Primary Pane */}
      <div
        data-slot="split-pane-primary"
        style={primaryStyle}
        className={cn(
          "overflow-auto",
          responsive && mobileActivePane === "secondary" ? "hidden md:block" : "block"
        )}
      >
        {primaryPane}
      </div>

      {/* Resizable Divider Handle */}
      <div
        role="separator"
        tabIndex={disabled ? -1 : 0}
        aria-orientation={orientation}
        aria-valuenow={size}
        aria-valuemin={minSize}
        aria-valuemax={maxSize}
        aria-label="Kéo để thay đổi kích thước"
        data-slot="split-pane-handle"
        onPointerDown={handlePointerDown}
        onMouseDown={handlePointerDown}
        onKeyDown={handleKeyDown}
        onDoubleClick={handleDoubleClick}
        className={cn(
          splitPaneHandleVariants({
            orientation,
            isDragging,
          }),
          responsive && "hidden md:flex",
          disabled && "pointer-events-none opacity-40 cursor-default"
        )}
      />

      {/* Secondary Pane */}
      <div
        data-slot="split-pane-secondary"
        className={cn(
          "flex-1 overflow-auto",
          responsive && mobileActivePane === "primary" ? "hidden md:block" : "block"
        )}
      >
        {secondaryPane}
      </div>
    </div>
  )
}
