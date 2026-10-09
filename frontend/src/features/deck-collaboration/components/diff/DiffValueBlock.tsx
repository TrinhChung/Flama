import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import '@/shared/config/i18n'
import type { DiffValue } from '../../types'

const MAX_RENDERED_DIFF_CHARS = 20_000
const MAX_RENDERED_DIFF_LINES = 200

type CollabT = ReturnType<typeof useTranslation<'collaboration'>>['t']

function valueToText(value: DiffValue, t: CollabT): string {
  if (value === undefined) return t('diff.value_no_data')
  if (value === null) return t('diff.value_null')
  if (value === '') return t('diff.value_empty')
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  const serialized = JSON.stringify(value, null, 2)
  return serialized === undefined ? String(value) : serialized
}

export function DiffValueBlock({
  value,
  side,
}: {
  value: DiffValue
  side: 'before' | 'after'
}) {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'
  const text = valueToText(value, t)
  const characterPreview = text.slice(0, MAX_RENDERED_DIFF_CHARS)
  const previewLines = characterPreview.split('\n')
  const lines = previewLines.slice(0, MAX_RENDERED_DIFF_LINES)
  const isTruncated = text.length > characterPreview.length
    || previewLines.length > lines.length
  const isBefore = side === 'before'

  return (
    <div
      className={cn(
        'overflow-x-auto border-y font-mono text-xs leading-5',
        isBefore
          ? 'border-red-500/20 bg-red-500/8'
          : 'border-emerald-500/20 bg-emerald-500/8',
      )}
    >
      {lines.map((line, index) => (
        <div
          key={index}
          className="grid min-w-max grid-cols-[2.25rem_1rem_minmax(0,1fr)] px-2"
        >
          <span
            aria-hidden="true"
            className="select-none border-r border-foreground/10 pr-2 text-right text-muted-foreground/70"
          >
            {index + 1}
          </span>
          <span
            aria-hidden="true"
            className={cn(
              'select-none text-center font-semibold',
              isBefore ? 'text-red-700 dark:text-red-300' : 'text-emerald-700 dark:text-emerald-300',
            )}
          >
            {isBefore ? '-' : '+'}
          </span>
          <span className="whitespace-pre-wrap break-words pr-3">{line || ' '}</span>
        </div>
      ))}
      {isTruncated ? (
        <p className="border-t border-foreground/10 px-3 py-2 text-xs text-muted-foreground">
          {t('diff.truncated_lines', {
            lines: MAX_RENDERED_DIFF_LINES.toLocaleString(locale),
            chars: MAX_RENDERED_DIFF_CHARS.toLocaleString(locale),
          })}
        </p>
      ) : null}
    </div>
  )
}
