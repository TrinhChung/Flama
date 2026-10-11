import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowRight, BookOpen, Layers, Zap } from 'lucide-react'

export function AsbplayerDocumentationSection() {
  const { t } = useTranslation('settings')

  return (
    <div className="rounded-2xl border bg-card/60 p-4 sm:p-5 space-y-3 shadow-2xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          <BookOpen className="size-3.5 text-primary" />
          <span>{t('asbplayer.docs.title')}</span>
        </div>
        <Link
          to="/guide/integrations/asbplayer"
          className="text-xs text-primary hover:underline font-medium flex items-center gap-1"
        >
          <span>{t('asbplayer.docs.view_all')}</span>
          <ArrowRight className="size-3" />
        </Link>
      </div>

      <div className="grid gap-2 sm:grid-cols-3 pt-1">
        <Link
          to="/guide/integrations/asbplayer"
          className="group flex items-start gap-3 p-3 rounded-xl hover:bg-muted/60 transition-colors"
        >
          <div className="p-2 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
            <BookOpen className="size-4" />
          </div>
          <div className="min-w-0 space-y-0.5">
            <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors flex items-center gap-1">
              <span>{t('asbplayer.docs.card1_title')}</span>
              <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-primary" />
            </div>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              {t('asbplayer.docs.card1_desc')}
            </p>
          </div>
        </Link>

        <Link
          to="/guide/integrations/asbplayer#mapping"
          className="group flex items-start gap-3 p-3 rounded-xl hover:bg-muted/60 transition-colors"
        >
          <div className="p-2 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
            <Layers className="size-4" />
          </div>
          <div className="min-w-0 space-y-0.5">
            <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors flex items-center gap-1">
              <span>{t('asbplayer.docs.card2_title')}</span>
              <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-purple-500" />
            </div>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              {t('asbplayer.docs.card2_desc')}
            </p>
          </div>
        </Link>

        <Link
          to="/guide/integrations/asbplayer#shortcuts"
          className="group flex items-start gap-3 p-3 rounded-xl hover:bg-muted/60 transition-colors"
        >
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
            <Zap className="size-4" />
          </div>
          <div className="min-w-0 space-y-0.5">
            <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors flex items-center gap-1">
              <span>{t('asbplayer.docs.card3_title')}</span>
              <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-amber-500" />
            </div>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              {t('asbplayer.docs.card3_desc')}
            </p>
          </div>
        </Link>
      </div>
    </div>
  )
}
