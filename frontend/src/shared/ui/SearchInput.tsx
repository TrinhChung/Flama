import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Search, X, Loader2 } from "lucide-react"

import { cn } from "@/lib/utils"

export const searchInputVariants = cva(
  "w-full rounded-lg border bg-transparent text-sm transition-all duration-150 outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&::-webkit-search-cancel-button]:appearance-none [&::-webkit-search-decoration]:appearance-none",
  {
    variants: {
      variant: {
        default:
          "border-border bg-background hover:border-border/80 focus-visible:bg-background",
        filled:
          "border-transparent bg-muted/50 hover:bg-muted/70 focus-visible:bg-background focus-visible:border-ring",
        ghost:
          "border-transparent bg-transparent hover:bg-muted/40 focus-visible:bg-background focus-visible:border-ring",
      },
      size: {
        sm: "h-8 text-xs pl-8 pr-8",
        default: "h-9 text-sm pl-9 pr-9",
        lg: "h-10 text-base pl-10 pr-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export const searchIconVariants = cva(
  "pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted-foreground transition-colors",
  {
    variants: {
      size: {
        sm: "left-2.5 size-3.5",
        default: "left-3 size-4",
        lg: "left-3.5 size-4.5",
      },
    },
    defaultVariants: {
      size: "default",
    },
  }
)

export interface SearchInputProps
  extends Omit<React.ComponentProps<"input">, "size">,
    VariantProps<typeof searchInputVariants> {
  /** Optional callback fired when the clear button or unescaped Escape is pressed */
  onClear?: () => void
  /** Loading flag to replace clear button with an animated spinner */
  isLoading?: boolean
  /** Keyboard shortcut hint string (e.g. '/' or 'Ctrl+K' or '⌘K') */
  shortcut?: string
  /** Optional className for the outer container */
  containerClassName?: string
}

export const SearchInput = React.forwardRef<HTMLInputElement, SearchInputProps>(
  (
    {
      className,
      containerClassName,
      variant,
      size = "default",
      value,
      defaultValue,
      onChange,
      onClear,
      onKeyDown,
      onCompositionStart,
      onCompositionEnd,
      isLoading = false,
      shortcut,
      disabled,
      type = "search",
      ...props
    },
    ref
  ) => {
    const inputRef = React.useRef<HTMLInputElement>(null)
    React.useImperativeHandle(ref, () => inputRef.current as HTMLInputElement)

    const isControlled = value !== undefined
    const [internalValue, setInternalValue] = React.useState<string>(
      defaultValue !== undefined ? String(defaultValue) : ""
    )
    const currentValue = isControlled ? String(value ?? "") : internalValue
    const hasValue = currentValue.length > 0

    const isComposingRef = React.useRef(false)

    const handleClear = React.useCallback(() => {
      if (!isControlled) {
        setInternalValue("")
      }
      if (inputRef.current) {
        inputRef.current.value = ""
        inputRef.current.focus()

        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype,
          "value"
        )?.set
        nativeInputValueSetter?.call(inputRef.current, "")

        const inputEvt = new Event("input", { bubbles: true })
        inputRef.current.dispatchEvent(inputEvt)

        const changeEvt = new Event("change", { bubbles: true })
        inputRef.current.dispatchEvent(changeEvt)
      }
      onClear?.()
    }, [isControlled, onClear])

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      const isComposing =
        e.nativeEvent.isComposing ||
        isComposingRef.current ||
        (e as unknown as { isComposing?: boolean }).isComposing

      if (e.key === "Escape" && hasValue) {
        if (isComposing) {
          return // Swallow Escape so IME popup closes without wiping search text
        }
        e.preventDefault()
        handleClear()
        return
      }

      if (e.key === "Enter" && isComposing) {
        return // Swallow Enter so IME commits candidate without triggering parent search submit
      }

      onKeyDown?.(e)
    }

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!isControlled) {
        setInternalValue(e.target.value)
      }
      onChange?.(e)
    }

    // Global keyboard shortcut listener (e.g. Ctrl+K, Cmd+K, or /)
    React.useEffect(() => {
      if (!shortcut || disabled) return

      const normalized = shortcut.toLowerCase()
      const isKShortcut =
        normalized.includes("k") &&
        (normalized.includes("ctrl") || normalized.includes("cmd") || normalized.includes("⌘"))
      const isSlashShortcut = normalized === "/"

      const handleGlobalKeyDown = (e: KeyboardEvent) => {
        if (disabled) return

        if (isKShortcut && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
          e.preventDefault()
          inputRef.current?.focus()
          inputRef.current?.select()
          return
        }

        if (isSlashShortcut && e.key === "/") {
          const activeTag = document.activeElement?.tagName?.toLowerCase()
          const isEditable = (document.activeElement as HTMLElement)?.isContentEditable
          if (activeTag !== "input" && activeTag !== "textarea" && !isEditable) {
            e.preventDefault()
            inputRef.current?.focus()
            inputRef.current?.select()
          }
        }
      }

      window.addEventListener("keydown", handleGlobalKeyDown)
      return () => {
        window.removeEventListener("keydown", handleGlobalKeyDown)
      }
    }, [shortcut, disabled])

    return (
      <div
        data-slot="search-input-wrapper"
        className={cn("relative flex items-center w-full", containerClassName)}
      >
        <Search
          data-slot="search-icon"
          className={cn(searchIconVariants({ size }))}
          aria-hidden="true"
        />
        <input
          ref={inputRef}
          type={type}
          value={isControlled ? value : internalValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onCompositionStart={(e) => {
            isComposingRef.current = true
            onCompositionStart?.(e)
          }}
          onCompositionEnd={(e) => {
            isComposingRef.current = false
            onCompositionEnd?.(e)
          }}
          disabled={disabled}
          className={cn(searchInputVariants({ variant, size }), className)}
          {...props}
        />
        <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {isLoading ? (
            <Loader2
              data-slot="search-spinner"
              className="size-4 animate-spin text-muted-foreground"
              aria-label="Loading"
            />
          ) : hasValue && !disabled ? (
            <button
              type="button"
              data-slot="search-clear-btn"
              onClick={handleClear}
              aria-label="Clear search input"
              tabIndex={-1}
              className="inline-flex size-4.5 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:text-foreground focus:outline-none"
            >
              <X className="size-3.5" />
            </button>
          ) : shortcut && !disabled ? (
            <kbd
              data-slot="search-shortcut-badge"
              className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground opacity-100"
            >
              {shortcut}
            </kbd>
          ) : null}
        </div>
      </div>
    )
  }
)

SearchInput.displayName = "SearchInput"
