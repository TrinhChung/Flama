import { memo } from 'react'
import { useTranslation } from 'react-i18next'
import { resolveDisplayUrl } from '@/entities/flashcard'
import { fieldValueEditorText, isArrayField, parseArrayValue } from '@/entities/flashcard/fields'
import { cn } from '@/lib/utils'
import type { TextDiffSegment } from '@/shared/lib'
import '@/shared/config/i18n'

const MEDIA_FIELD_TYPES = new Set(['image', 'audio', 'diagram'])

export type FieldValueSide = 'before' | 'after'

const CHANGED_MARK: Record<FieldValueSide, string> = {
  before: 'rounded-sm bg-red-500/20 text-red-900 dark:text-red-100',
  after: 'rounded-sm bg-emerald-500/25 text-emerald-950 dark:text-emerald-50',
}

const CHANGED_FRAME: Record<FieldValueSide, string> = {
  before: 'ring-2 ring-red-500/50',
  after: 'ring-2 ring-emerald-500/60',
}

function mediaLines(value: unknown): string[] {
  return fieldValueEditorText(value)
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function arrayItemText(item: unknown): string {
  return typeof item === 'string' ? item : JSON.stringify(item)
}

/**
 * Read-only note field, shown the way the Browse editor previews it: media as
 * images or players, arrays as lists, text as written. Parts that differ from
 * `compareTo` are marked for `side`.
 */
export const FieldValueView = memo(function FieldValueView({
  value,
  fieldType,
  fieldName,
  side,
  compareTo,
  segments,
}: {
  value: unknown
  fieldType: string
  fieldName: string
  /** Mark differences against `compareTo`; omit for an unchanged field. */
  side?: FieldValueSide
  compareTo?: unknown
  /** Precomputed text diff for this side. */
  segments?: TextDiffSegment[] | null
}) {
  const { t } = useTranslation('collaboration')
  const type = (fieldType || 'text').toLowerCase()

  if (value === undefined || value === null || fieldValueEditorText(value) === '') {
    return (
      <span className="text-xs italic text-muted-foreground">
        {t('notes.value_empty', 'Trống')}
      </span>
    )
  }

  if (MEDIA_FIELD_TYPES.has(type)) {
    const others = new Set(side && compareTo !== undefined ? mediaLines(compareTo) : [])
    const lines = mediaLines(value)
    return (
      <div className={cn(lines.length > 1 && type !== 'audio' ? 'grid grid-cols-2 gap-2' : 'space-y-2')}>
        {lines.map((line, index) => {
          const url = resolveDisplayUrl(line)
          const changed = Boolean(side && !others.has(line))
          if (!url) {
            return (
              <span
                key={`${line}-${index}`}
                className={cn('block break-all font-mono text-[11px] text-muted-foreground', changed && side && CHANGED_MARK[side])}
              >
                {line}
              </span>
            )
          }
          return type === 'audio' ? (
            <audio
              key={`${line}-${index}`}
              controls
              preload="none"
              src={url}
              aria-label={`${fieldName} ${index + 1}`}
              className={cn('h-8 w-full rounded', changed && side && CHANGED_FRAME[side])}
            />
          ) : (
            <img
              key={`${line}-${index}`}
              src={url}
              alt={`${fieldName} ${index + 1}`}
              loading="lazy"
              className={cn(
                'max-h-40 w-full rounded-lg border border-border/40 bg-background object-contain',
                changed && side && CHANGED_FRAME[side],
              )}
            />
          )
        })}
      </div>
    )
  }

  if (isArrayField(type)) {
    const others = new Set(
      side && compareTo !== undefined ? parseArrayValue(compareTo).map(arrayItemText) : [],
    )
    return (
      <ul className="list-disc space-y-0.5 pl-5 text-sm leading-relaxed">
        {parseArrayValue(value).map((item, index) => {
          const itemText = arrayItemText(item)
          const changed = Boolean(side && !others.has(itemText))
          return (
            <li key={`${itemText}-${index}`} className="break-words">
              <span className={cn(changed && side && CHANGED_MARK[side])}>{itemText}</span>
            </li>
          )
        })}
      </ul>
    )
  }

  const valueText = fieldValueEditorText(value)
  return (
    <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
      {segments && side
        ? segments.map((segment, index) => (
            <span key={index} className={cn(segment.changed && CHANGED_MARK[side])}>
              {segment.text}
            </span>
          ))
        : valueText}
    </p>
  )
})
