import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import type { WorksheetLayoutOptions } from '../../../types'

type SetLayoutOptions = React.Dispatch<React.SetStateAction<WorksheetLayoutOptions>>
type BooleanOptionKey = {
  [K in keyof WorksheetLayoutOptions]-?: NonNullable<WorksheetLayoutOptions[K]> extends boolean ? K : never
}[keyof WorksheetLayoutOptions]

/**
 * Checkbox bound to one boolean layout option. `defaultChecked` is the value
 * an unset option renders as (`!== false` options default on).
 */
export function LayoutOptionCheckbox({
  field,
  label,
  defaultChecked,
  layoutOptions,
  setLayoutOptions,
  className = 'flex items-center gap-2 cursor-pointer select-none',
}: {
  field: BooleanOptionKey
  label: ReactNode
  defaultChecked: boolean
  layoutOptions: WorksheetLayoutOptions
  setLayoutOptions: SetLayoutOptions
  className?: string
}) {
  return (
    <label className={className}>
      <input
        type="checkbox"
        checked={layoutOptions[field] ?? defaultChecked}
        onChange={(e) =>
          setLayoutOptions((prev) => ({
            ...prev,
            [field]: e.target.checked,
          }))
        }
        className="rounded text-primary size-3.5"
      />
      <span>{label}</span>
    </label>
  )
}

/** Outline pill in a row of mutually exclusive values (counts, sizes). */
export function OptionPill({
  active,
  onClick,
  className,
  children,
}: {
  active: boolean
  onClick: () => void
  className: string
  children: ReactNode
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={onClick}
      className={`${className} ${
        active
          ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
          : 'bg-background hover:bg-muted text-muted-foreground'
      }`}
    >
      {children}
    </Button>
  )
}

/** Bordered choice tile used for style pickers (line style, box style, colors). */
export function OptionTile({
  active,
  onClick,
  className,
  children,
}: {
  active: boolean
  onClick: () => void
  className: string
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${className} ${
        active
          ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
          : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
      }`}
    >
      {children}
    </button>
  )
}
