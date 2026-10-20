import type { WorksheetLayoutOptions } from '../../types'

type WorksheetLocale = NonNullable<WorksheetLayoutOptions['locale']>

const LOCALE_OPTIONS: { locale: WorksheetLocale; flag: string; label: string; textClass: string }[] = [
  { locale: 'zh', flag: '🇨🇳', label: 'Tiếng Trung (Giản thể)', textClass: 'text-[11px]' },
  { locale: 'zh-hant', flag: '🇹🇼', label: 'Tiếng Trung (Phồn thể)', textClass: 'text-[10px]' },
  { locale: 'ja', flag: '🇯🇵', label: 'Tiếng Nhật', textClass: 'text-[11px]' },
]

/** Quick switch between simplified Chinese, traditional Chinese and Japanese stroke data. */
export function StudioLocaleSwitcher({
  locale,
  onChange,
}: {
  locale: WorksheetLocale | undefined
  onChange: (locale: WorksheetLocale) => void
}) {
  const activeLocale = locale || 'ja'
  return (
    <div className="mx-3 mt-3 p-1 bg-muted/80 rounded-xl border border-border/70 flex items-center gap-1 shrink-0">
      {LOCALE_OPTIONS.map((option) => (
        <button
          key={option.locale}
          type="button"
          onClick={() => onChange(option.locale)}
          className={`flex-1 py-1.5 px-1.5 rounded-lg ${option.textClass} sm:text-xs font-semibold flex items-center justify-center gap-1 transition-all ${
            activeLocale === option.locale
              ? 'bg-background text-foreground shadow-xs font-bold text-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          <span>{option.flag}</span>
          <span>{option.label}</span>
        </button>
      ))}
    </div>
  )
}
