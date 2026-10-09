import type { ReactNode } from 'react'

/**
 * Field settings and the input preview: stacked in narrow detail cards, side by side once
 * the card (an `@container`) is wide enough, so large screens use the full setup shell width.
 */
export function FieldFormColumns({ settings, preview }: { settings: ReactNode; preview?: ReactNode }) {
  return (
    <div className="grid gap-4 @4xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] @4xl:items-start @4xl:gap-6">
      <div className="min-w-0 space-y-4">{settings}</div>
      {preview && (
        <div className="min-w-0 @4xl:rounded-xl @4xl:border @4xl:border-border/70 @4xl:p-4 @4xl:[&>section]:border-t-0 @4xl:[&>section]:pt-0">
          {preview}
        </div>
      )}
    </div>
  )
}
