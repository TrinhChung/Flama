import { Check, LoaderCircle, RefreshCcw, Unlink, Zap } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/utils'
import '@/shared/config/i18n'
import type { PreparedInstalledUpdate } from '../../types'

type UpdateActionSidebarProps = {
  autoUpdateEnabled: boolean
  isAutoUpdatePending: boolean
  onToggleAutoUpdate: (checked: boolean) => void
  updateAvailable: boolean
  alreadyApplied: boolean
  prepared: PreparedInstalledUpdate | null
  isPreparing: boolean
  onPrepare: () => void
  targetVersionLabel: string
  canApply: boolean
  isApplying: boolean
  isResolving: boolean
  onApply: () => void
  isDetaching: boolean
  onDetach: () => void
  allConflictsResolved: boolean
}

export function UpdateActionSidebar({
  autoUpdateEnabled,
  isAutoUpdatePending,
  onToggleAutoUpdate,
  updateAvailable,
  alreadyApplied,
  prepared,
  isPreparing,
  onPrepare,
  targetVersionLabel,
  canApply,
  isApplying,
  isResolving,
  onApply,
  isDetaching,
  onDetach,
  allConflictsResolved,
}: UpdateActionSidebarProps) {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  return (
    <Card className="h-fit lg:sticky lg:top-4">
      <CardHeader>
        <CardTitle className="text-base">
          {t('update.controlled_update_title', 'Cập nhật có kiểm soát')}
        </CardTitle>
        <CardDescription className="text-xs">
          {t(
            'update.controlled_update_desc',
            'Hệ thống 3-Way Merge tự động bảo vệ các trường bạn đã tự chỉnh sửa.',
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3.5">
        {/* Auto-update subscriber setting toggle */}
        <div className="flex items-center justify-between gap-2.5 rounded-xl border border-primary/20 bg-primary/5 p-3">
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
              <Zap className="size-3.5 text-primary shrink-0" />
              <span>{t('update.auto_update_label', 'Tự động cập nhật deck')}</span>
            </div>
            <p className="text-[11px] text-muted-foreground leading-tight">
              {t(
                'update.auto_update_desc',
                'Tự động nhận release mới khi tác giả phát hành (nếu không xung đột).',
              )}
            </p>
          </div>
          <Switch
            checked={Boolean(autoUpdateEnabled)}
            disabled={isAutoUpdatePending}
            onCheckedChange={onToggleAutoUpdate}
            aria-label={t('update.auto_update_label', 'Tự động cập nhật deck')}
          />
        </div>

        {!updateAvailable || alreadyApplied ? (
          <Alert>
            <Check className="size-4" />
            <AlertTitle>
              {t('update.already_applied_title', 'Deck đã ở phiên bản này')}
            </AlertTitle>
            <AlertDescription className="text-xs">
              {t('update.already_applied_desc', 'Không còn nội dung mới cần áp dụng.')}
            </AlertDescription>
          </Alert>
        ) : null}

        {!prepared ? (
          <Button
            className="w-full h-10 font-bold text-xs rounded-xl"
            size="lg"
            disabled={isPreparing || !updateAvailable}
            onClick={onPrepare}
          >
            {isPreparing ? (
              <>
                <LoaderCircle className="animate-spin mr-1.5 size-4" />
                {t('update.checking_3way', 'Đang kiểm tra 3-way merge…')}
              </>
            ) : (
              <>
                <RefreshCcw className="mr-1.5 size-4" />
                {t('update.btn_check_conflicts', 'Kiểm tra xung đột')}
              </>
            )}
          </Button>
        ) : (
          <Button
            className="w-full h-10 font-bold text-xs rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground"
            size="lg"
            disabled={!canApply || isApplying || isResolving}
            onClick={onApply}
          >
            {isApplying ? (
              <>
                <LoaderCircle className="animate-spin mr-1.5 size-4" />
                {t('update.applying_update', 'Đang áp dụng cập nhật…')}
              </>
            ) : (
              <>
                <Check className="mr-1.5 size-4" />
                {t('update.btn_apply_version', {
                  version: targetVersionLabel,
                  defaultValue: `Áp dụng phiên bản ${targetVersionLabel}`,
                })}
              </>
            )}
          </Button>
        )}

        {prepared && prepared.conflict_count > 0 ? (
          <p
            className={cn(
              'text-xs leading-relaxed tabular-nums font-semibold',
              allConflictsResolved
                ? 'text-emerald-700 dark:text-emerald-300'
                : 'text-amber-700 dark:text-amber-300',
            )}
            aria-live="polite"
          >
            {t('update.conflicts_saved_status', {
              resolved: prepared.resolved_conflict_count.toLocaleString(locale),
              total: prepared.conflict_count.toLocaleString(locale),
              defaultValue: `${prepared.resolved_conflict_count}/${prepared.conflict_count} xung đột đã được lưu.`,
            })}
          </p>
        ) : null}

        {/* Detach Deck Action */}
        <div className="pt-2 border-t border-border/60">
          <Button
            variant="ghost"
            size="sm"
            className="w-full text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 justify-center h-8"
            disabled={isDetaching}
            onClick={onDetach}
          >
            <Unlink className="size-3.5 mr-1.5" />
            {isDetaching
              ? t('update.detaching_deck', 'Đang tách deck…')
              : t('update.btn_detach', 'Tách thành deck độc lập (Detach)')}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
