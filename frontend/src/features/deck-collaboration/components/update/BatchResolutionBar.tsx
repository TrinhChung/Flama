import { LoaderCircle, Zap } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import '@/shared/config/i18n'

type BatchResolutionBarProps = {
  conflictCount: number
  isResolvingAll: boolean
  pendingResolutionMode?: 'keep_mine' | 'keep_upstream'
  onResolveAll: (mode: 'keep_mine' | 'keep_upstream') => void
}

export function BatchResolutionBar({
  conflictCount,
  isResolvingAll,
  pendingResolutionMode,
  onResolveAll,
}: BatchResolutionBarProps) {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  return (
    <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-2xl border border-primary/25 bg-primary/5 p-3.5">
      <div className="flex items-center gap-2 text-xs font-bold text-foreground">
        <Zap className="size-4 text-primary shrink-0" />
        <span>
          {t('update.batch_resolve_label', {
            count: conflictCount.toLocaleString(locale),
            defaultValue: `Giải quyết nhanh toàn bộ ${conflictCount.toLocaleString(locale)} xung đột:`,
          })}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 text-xs font-bold hover:bg-blue-500/10 hover:border-blue-500/40 hover:text-blue-600 rounded-xl"
          disabled={isResolvingAll}
          onClick={() => onResolveAll('keep_mine')}
        >
          {isResolvingAll && pendingResolutionMode === 'keep_mine' ? (
            <LoaderCircle className="size-3.5 mr-1 animate-spin" />
          ) : null}
          {t('update.btn_batch_keep_mine', 'Giữ tất cả bản của tôi')}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 text-xs font-bold hover:bg-emerald-500/10 hover:border-emerald-500/40 hover:text-emerald-600 rounded-xl"
          disabled={isResolvingAll}
          onClick={() => onResolveAll('keep_upstream')}
        >
          {isResolvingAll && pendingResolutionMode === 'keep_upstream' ? (
            <LoaderCircle className="size-3.5 mr-1 animate-spin" />
          ) : null}
          {t('update.btn_batch_keep_upstream', 'Dùng tất cả bản tác giả')}
        </Button>
      </div>
    </div>
  )
}
