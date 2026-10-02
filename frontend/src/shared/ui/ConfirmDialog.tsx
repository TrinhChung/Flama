import * as React from "react"
import { Dialog as DialogPrimitive } from "radix-ui"
import { AlertTriangle, HelpCircle, Loader2, X } from "lucide-react"

import { cva } from "class-variance-authority"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export const confirmDialogVariants = cva(
  "fixed top-1/2 left-1/2 z-50 grid w-full max-w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl bg-popover p-5 text-popover-foreground shadow-lg ring-1 ring-foreground/10 duration-100 outline-none sm:max-w-md data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
  {
    variants: {
      variant: {
        primary: "",
        destructive: "",
      },
    },
    defaultVariants: {
      variant: "primary",
    },
  }
)

export interface ConfirmDialogProps {
  /** Controlled open state */
  open?: boolean
  /** Default open state for uncontrolled mode */
  defaultOpen?: boolean
  /** Open state change callback */
  onOpenChange?: (open: boolean) => void
  /** Trigger element for uncontrolled mode (renders with asChild) */
  trigger?: React.ReactNode
  /** Modal title */
  title: React.ReactNode
  /** Modal description text or custom node */
  description?: React.ReactNode
  /** Action variant: 'primary' (default Flama orange) or 'destructive' (red/rose) */
  variant?: "primary" | "destructive"
  /** Label for confirm button (default: 'Xác nhận') */
  confirmText?: string
  /** Label for cancel button (default: 'Hủy') */
  cancelText?: string
  /** Loading state indicator. Disables all buttons and prevents dismissal */
  isLoading?: boolean
  /** Callback fired when user confirms. Can return a Promise */
  onConfirm: () => void | Promise<void>
  /** Callback fired when user cancels */
  onCancel?: () => void
  /** Optional custom icon override */
  icon?: React.ReactNode
  /** Optional body content rendered below description */
  children?: React.ReactNode
  /** Additional custom class name for dialog content */
  className?: string
}

export function ConfirmDialog({
  open,
  defaultOpen = false,
  onOpenChange,
  trigger,
  title,
  description,
  variant = "primary",
  confirmText = "Xác nhận",
  cancelText = "Hủy",
  isLoading = false,
  onConfirm,
  onCancel,
  icon,
  children,
  className,
}: ConfirmDialogProps) {
  const isControlled = open !== undefined
  const [internalOpen, setInternalOpen] = React.useState(defaultOpen)
  const isOpen = isControlled ? open : internalOpen

  const handleOpenChange = React.useCallback(
    (nextOpen: boolean) => {
      if (isLoading && !nextOpen) return
      if (!isControlled) {
        setInternalOpen(nextOpen)
      }
      onOpenChange?.(nextOpen)
    },
    [isLoading, isControlled, onOpenChange]
  )

  const handleCancel = React.useCallback(() => {
    if (isLoading) return
    onCancel?.()
    handleOpenChange(false)
  }, [isLoading, onCancel, handleOpenChange])

  const handleConfirm = React.useCallback(async () => {
    if (isLoading) return
    const res = onConfirm()
    if (res instanceof Promise) {
      await res
    }
  }, [isLoading, onConfirm])

  return (
    <DialogPrimitive.Root open={isOpen} onOpenChange={handleOpenChange}>
      {trigger && (
        <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
      )}
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          data-slot="dialog-overlay"
          className="fixed inset-0 isolate z-50 bg-black/50 duration-100 supports-backdrop-filter:backdrop-blur-xs data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0"
        />
        <DialogPrimitive.Content
          data-slot="dialog-content"
          onPointerDownOutside={(e) => {
            if (isLoading) {
              e.preventDefault()
            }
          }}
          onEscapeKeyDown={(e) => {
            if (isLoading) {
              e.preventDefault()
            }
          }}
          className={cn(confirmDialogVariants({ variant }), className)}
        >
          <div className="flex items-start gap-3.5">
            {icon ? (
              icon
            ) : variant === "destructive" ? (
              <div
                data-slot="confirm-dialog-icon"
                className="flex size-10 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive"
              >
                <AlertTriangle className="size-5" />
              </div>
            ) : (
              <div
                data-slot="confirm-dialog-icon"
                className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"
              >
                <HelpCircle className="size-5" />
              </div>
            )}
            <div className="flex-1 space-y-1 pr-6">
              <DialogPrimitive.Title
                data-slot="dialog-title"
                className="font-heading text-base font-semibold leading-6 text-foreground"
              >
                {title}
              </DialogPrimitive.Title>
              {description && (
                <DialogPrimitive.Description
                  data-slot="dialog-description"
                  className="text-sm text-muted-foreground leading-normal"
                >
                  {description}
                </DialogPrimitive.Description>
              )}
            </div>
          </div>

          {children && <div className="text-sm">{children}</div>}

          <div
            data-slot="dialog-footer"
            className="mt-2 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"
          >
            <Button
              type="button"
              variant="outline"
              disabled={isLoading}
              onClick={handleCancel}
            >
              {cancelText}
            </Button>
            <Button
              type="button"
              variant={variant === "destructive" ? "destructive" : "default"}
              disabled={isLoading}
              onClick={handleConfirm}
            >
              {isLoading && <Loader2 className="mr-2 size-4 animate-spin" />}
              {confirmText}
            </Button>
          </div>

          <DialogPrimitive.Close asChild disabled={isLoading}>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              disabled={isLoading}
              className="absolute top-3 right-3 text-muted-foreground hover:text-foreground"
              aria-label="Close"
            >
              <X className="size-4" />
              <span className="sr-only">Close</span>
            </Button>
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
