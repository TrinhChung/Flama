import { useTranslation } from 'react-i18next'
import { Flame, Globe, MousePointerClick, Zap } from 'lucide-react'

export function YomitanFeatureHighlights() {
  const { t } = useTranslation('settings')

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-3">
      <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
        <div className="p-2 sm:p-2.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0">
          <Zap className="size-4.5 sm:size-5" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] sm:text-xs font-semibold truncate">
            {t('yomitan.highlights.lookup_title')}
          </div>
          <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
            {t('yomitan.highlights.lookup_sub')}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
        <div className="p-2 sm:p-2.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
          <MousePointerClick className="size-4.5 sm:size-5" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] sm:text-xs font-semibold truncate">
            {t('yomitan.highlights.one_click_title')}
          </div>
          <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
            {t('yomitan.highlights.one_click_sub')}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
        <div className="p-2 sm:p-2.5 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 shrink-0">
          <Globe className="size-4.5 sm:size-5" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] sm:text-xs font-semibold truncate">
            {t('yomitan.highlights.immersion_title')}
          </div>
          <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
            {t('yomitan.highlights.immersion_sub')}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
        <div className="p-2 sm:p-2.5 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 shrink-0">
          <Flame className="size-4.5 sm:size-5" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] sm:text-xs font-semibold truncate">
            {t('yomitan.highlights.connect_title')}
          </div>
          <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
            {t('yomitan.highlights.connect_sub')}
          </div>
        </div>
      </div>
    </div>
  )
}
