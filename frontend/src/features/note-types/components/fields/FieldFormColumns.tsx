import type { ReactNode } from 'react'

/**
 * Field settings and the input preview: stacked in narrow detail cards, side by side once
 * the card (an `@container`) is wide enough, so large screens use the full setup shell width.
 */
export function FieldFormColumns({ settings, preview }: { settings: ReactNode; preview?: ReactNode }) {
  return (
    <div className="grid gap-4 @xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] @xl:items-start @xl:gap-5">
      <div className="min-w-0 space-y-3.5 sm:space-y-4">{settings}</div>
      {preview && (
        <div className="min-w-0 @xl:rounded-xl @xl:border @xl:border-border/70 @xl:p-3.5 @xl:[&>section]:border-t-0 @xl:[&>section]:pt-0">
          {preview}
        </div>
      )}
    </div>
  )
}
