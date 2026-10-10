import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { AlertCircle, CheckCircle2, Download, GitPullRequest, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmDialog } from '@/shared/ui'
import { useTemplateSubscription } from '../hooks/useTemplateSubscription'
import { ConflictResolutionDialog } from './ConflictResolutionDialog'
import type { ConflictResolution, PendingUpdateDto } from '../model/types'

export interface SubscriberUpdateViewProps {
  templateId: string
  currentVersionId?: string | null
  onSourceChanged?: () => void
}

function formatDate(value: string | null | undefined, lang: string) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(lang === 'en' ? 'en-US' : 'vi-VN', {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date)
}

export function SubscriberUpdateView({
  templateId,
  currentVersionId,
  onSourceChanged,
}: SubscriberUpdateViewProps) {
  const { t, i18n } = useTranslation('card_templates')
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false)
  const [activePendingUpdate, setActivePendingUpdate] = useState<PendingUpdateDto | null>(null)
  const [conflictDialogOpen, setConflictDialogOpen] = useState(false)

  const {
    subscription,
    isLoading,
    isError,
    error,
    refetch,
    updateSettings,
    isUpdatingSettings,
    prepareUpdate,
    isPreparingUpdate,
    applyUpdate,
    isApplyingUpdate,
    resetToUpstream,
    isResettingToUpstream,
  } = useTemplateSubscription(templateId)

  const handleToggleAutoUpdate = async (checked: boolean) => {
    try {
      await updateSettings({ auto_update_enabled: checked })
      toast.success(t('setup.saved'))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('distribution.update_error'))
    }
  }

  const handleStartUpdate = async () => {
    if (!subscription?.current_release?.id) return
    try {
      const pending = await prepareUpdate({
        release_id: subscription.current_release.id,
        expected_applied_release_id: subscription.applied_release_id || undefined,
        expected_current_version_id: currentVersionId || subscription.current_version_id || undefined,
      })

      if (pending.status === 'has_conflict' && Object.keys(pending.conflicts || {}).length > 0) {
        setActivePendingUpdate(pending)
        setConflictDialogOpen(true)
      } else {
        // Ready without conflict, apply directly
        await applyUpdate({
          preparation_id: pending.id,
        })
        toast.success(t('distribution.update_success'))
        onSourceChanged?.()
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('distribution.update_error'))
    }
  }

  const handleApplyResolvedUpdate = async (resolutions: Record<string, ConflictResolution>) => {
    if (!activePendingUpdate) return
    await applyUpdate({
      preparation_id: activePendingUpdate.id,
      resolutions,
    })
    toast.success(t('distribution.update_success'))
    setActivePendingUpdate(null)
    onSourceChanged?.()
  }

  const handleResetToUpstream = async () => {
    try {
      await resetToUpstream()
      toast.success(t('distribution.reset_upstream_success'))
      setResetConfirmOpen(false)
      onSourceChanged?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('distribution.reset_upstream_error'))
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
        {t('detail.loading')}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-destructive/30 p-4 space-y-3">
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : t('library.retry')}
        </p>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          {t('library.retry')}
        </Button>
      </div>
    )
  }

  const appliedRelease = subscription?.applied_release
  const latestRelease = subscription?.current_release
  const updateAvailable = Boolean(subscription?.update_available)

  const getSyncStatusBadge = () => {
    const status = subscription?.last_sync_status
    if (status === 'synced') {
      return (
        <Badge variant="secondary" className="gap-1">
          <CheckCircle2 className="size-3 text-emerald-600" />
          {t('distribution.sync_status.synced')}
        </Badge>
      )
    }
    if (status === 'conflict') {
      return (
        <Badge variant="outline" className="border-amber-500/40 text-amber-600 dark:text-amber-400">
          {t('distribution.sync_status.conflict')}
        </Badge>
      )
    }
    if (status === 'ready') {
      return (
        <Badge variant="default">
          {t('distribution.sync_status.ready')}
        </Badge>
      )
    }
    return (
      <Badge variant="outline">
        {t('distribution.sync_status.unknown')}
      </Badge>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <GitPullRequest className="size-4 text-primary" />
              {t('distribution.subscriber_title')}
            </CardTitle>
            {getSyncStatusBadge()}
          </div>
          <CardDescription className="text-xs">
            {t('distribution.subscriber_description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {/* Release Comparison */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="rounded-lg border bg-muted/20 p-3 space-y-1">
              <span className="text-muted-foreground block">{t('distribution.applied_release')}</span>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-foreground text-sm">
                  {appliedRelease?.version_label || t('distribution.original_release')}
                </span>
                {appliedRelease && (
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                    #{appliedRelease.sequence_no}
                  </Badge>
                )}
              </div>
              {appliedRelease?.published_at && (
                <p className="text-[11px] text-muted-foreground">
                  {formatDate(appliedRelease.published_at, i18n.language)}
                </p>
              )}
            </div>

            <div className="rounded-lg border bg-muted/20 p-3 space-y-1">
              <span className="text-muted-foreground block">{t('distribution.latest_release')}</span>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-foreground text-sm">
                  {latestRelease?.version_label || t('distribution.not_available')}
                </span>
                {latestRelease && (
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                    #{latestRelease.sequence_no}
                  </Badge>
                )}
              </div>
              {latestRelease?.published_at && (
                <p className="text-[11px] text-muted-foreground">
                  {formatDate(latestRelease.published_at, i18n.language)}
                </p>
              )}
            </div>
          </div>

          {/* Update Available Banner */}
          {updateAvailable && (
            <div className="rounded-lg border border-primary/30 bg-primary/5 p-3.5 space-y-2">
              <div className="flex items-center gap-2 text-primary font-medium text-xs">
                <AlertCircle className="size-4" />
                {t('distribution.update_available_title')}
              </div>
              <p className="text-xs text-muted-foreground">
                {t('distribution.update_available_desc')}
              </p>
              {latestRelease?.change_note && (
                <div className="rounded border bg-background/50 p-2 text-xs">
                  <span className="font-medium text-[11px] text-muted-foreground block mb-0.5">
                    {t('distribution.change_note')}:
                  </span>
                  <p className="text-muted-foreground whitespace-pre-wrap">
                    {latestRelease.change_note}
                  </p>
                </div>
              )}
              <Button
                className="w-full gap-2 mt-1"
                onClick={handleStartUpdate}
                disabled={isPreparingUpdate || isApplyingUpdate}
              >
                <Download className="size-4" />
                {isPreparingUpdate ? t('distribution.btn_preparing') : t('distribution.btn_update')}
              </Button>
            </div>
          )}

          {/* Auto-update setting */}
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="space-y-0.5 pr-4">
              <label htmlFor="auto-update-switch" className="text-sm font-medium cursor-pointer">
                {t('distribution.auto_update_label')}
              </label>
              <p className="text-xs text-muted-foreground">
                {t('distribution.auto_update_desc')}
              </p>
            </div>
            <Switch
              id="auto-update-switch"
              checked={Boolean(subscription?.auto_update_enabled)}
              onCheckedChange={handleToggleAutoUpdate}
              disabled={isUpdatingSettings}
              aria-label={t('distribution.auto_update_label')}
            />
          </div>

          {/* Reset to Upstream Button */}
          <div className="pt-2 border-t">
            <Button
              variant="outline"
              size="sm"
              className="w-full text-destructive hover:text-destructive gap-2 border-destructive/30 hover:bg-destructive/10"
              onClick={() => setResetConfirmOpen(true)}
              disabled={isResettingToUpstream}
            >
              <RotateCcw className="size-3.5" />
              {t('distribution.btn_reset_upstream')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Reset Confirmation Dialog */}
      <ConfirmDialog
        open={resetConfirmOpen}
        onOpenChange={setResetConfirmOpen}
        title={t('distribution.reset_upstream_confirm_title')}
        description={t('distribution.reset_upstream_confirm_desc')}
        confirmText={t('distribution.reset_upstream_confirm_btn')}
        cancelText={t('setup.cancel')}
        variant="destructive"
        isLoading={isResettingToUpstream}
        onConfirm={handleResetToUpstream}
      />

      {/* Conflict Resolution Dialog */}
      {activePendingUpdate && (
        <ConflictResolutionDialog
          open={conflictDialogOpen}
          onOpenChange={(open) => {
            setConflictDialogOpen(open)
            if (!open) setActivePendingUpdate(null)
          }}
          pendingUpdate={activePendingUpdate}
          onApply={handleApplyResolvedUpdate}
          isApplying={isApplyingUpdate}
        />
      )}
    </div>
  )
}
