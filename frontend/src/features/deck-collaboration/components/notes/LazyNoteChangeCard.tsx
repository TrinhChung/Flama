import { memo } from 'react'
import { useNearViewport } from '@/shared/hooks'
import { NoteChangeCard, type NoteChangeCardProps } from './NoteChangeCard'

// Rough height before a note was ever shown: header, column titles, one row per change.
function estimatedHeight(props: NoteChangeCardProps) {
  return 92 + props.note.changes.length * 88
}

/**
 * A note card mounted only near the viewport. Far away it is an empty card of
 * the same height, so ticking "select all" on hundreds of notes re-renders
 * only what is on screen.
 */
export const LazyNoteChangeCard = memo(function LazyNoteChangeCard({
  eager = false,
  ...props
}: NoteChangeCardProps & {
  /** The first notes of the list render without waiting to be observed. */
  eager?: boolean
}) {
  const { ref, near, height } = useNearViewport<HTMLDivElement>(undefined, eager)
  return (
    <div ref={ref}>
      {near ? (
        <NoteChangeCard {...props} />
      ) : (
        <div
          aria-hidden="true"
          className="rounded-xl border bg-card shadow-xs"
          style={{ height: height ?? estimatedHeight(props) }}
        />
      )}
    </div>
  )
})
