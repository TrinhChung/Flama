import { useTranslation } from 'react-i18next'
import { Film, Flame, Layers, Video } from 'lucide-react'

export function AsbplayerFeatureHighlights() {
  const { t } = useTranslation('settings')

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-3">
      <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
        <div className="p-2 sm:p-2.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0">
          <Video className="size-4.5 sm:size-5" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] sm:text-xs font-semibold truncate">
            {t('asbplayer.highlights.video_title')}
          </div>
          <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
            {t('asbplayer.highlights.video_sub')}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
        <div className="p-2 sm:p-2.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
          <Film className="size-4.5 sm:size-5" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] sm:text-xs font-semibold truncate">
            {t('asbplayer.highlights.media_title')}
          </div>
          <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
            {t('asbplayer.highlights.media_sub')}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
        <div className="p-2 sm:p-2.5 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 shrink-0">
          <Layers className="size-4.5 sm:size-5" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] sm:text-xs font-semibold truncate">
            {t('asbplayer.highlights.sentences_title')}
          </div>
          <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
            {t('asbplayer.highlights.sentences_sub')}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
        <div className="p-2 sm:p-2.5 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 shrink-0">
          <Flame className="size-4.5 sm:size-5" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] sm:text-xs font-semibold truncate">
            {t('asbplayer.highlights.protocol_title')}
          </div>
          <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
            {t('asbplayer.highlights.protocol_sub')}
          </div>
        </div>
      </div>
    </div>
  )
}
