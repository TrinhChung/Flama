import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertCircle, CheckCircle2, Download, GitPullRequest, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmDialog } from '@/shared/ui'
import { useSubscriberUpdateView } from '../hooks/useSubscriberUpdateView'
import { ConflictResolutionDialog } from './ConflictResolutionDialog'

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
  const {
    subscription, isLoading, isError, error, refetch, isUpdatingSettings, isPreparingUpdate,
    isApplyingUpdate, isResettingToUpstream, isLegacyUnpinned, appliedRelease, latestRelease,
    updateAvailable, originalListingUrl, activePendingUpdate, resetConfirmOpen, conflictDialogOpen,
    handleResetOpenChange, handleConflictOpenChange, handleToggleAutoUpdate,
    handleStartUpdate, handleApplyResolvedUpdate, handleResetToUpstream,
  } = useSubscriberUpdateView({ templateId, currentVersionId, onSourceChanged })

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

  const getSyncStatusBadge = () => {
    if (isLegacyUnpinned) return <Badge variant="outline">{t('distribution.legacy_unpinned.status')}</Badge>
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
            {t(isLegacyUnpinned ? 'distribution.legacy_unpinned.description' : 'distribution.subscriber_description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {isLegacyUnpinned && (
            <div role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3.5 space-y-2">
              <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400 font-medium text-xs">
                <AlertCircle className="size-4" />
                {t('distribution.legacy_unpinned.title')}
              </div>
              <p className="text-xs text-muted-foreground">{t('distribution.legacy_unpinned.preserved')}</p>
              {originalListingUrl && (
                <>
                  <p className="text-xs text-muted-foreground">{t('distribution.legacy_unpinned.receive_separately')}</p>
                  <Button variant="outline" size="sm" asChild>
                    <Link to={originalListingUrl}>{t('distribution.legacy_unpinned.view_original')}</Link>
                  </Button>
                </>
              )}
              <Button className="w-full gap-2 mt-1" disabled onClick={handleStartUpdate}>
                <Download className="size-4" />
                {t('distribution.btn_update')}
              </Button>
            </div>
          )}

          {/* Release Comparison */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="rounded-lg border bg-muted/20 p-3 space-y-1">
              <span className="text-muted-foreground block">{t('distribution.applied_release')}</span>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-foreground text-sm">
                  {isLegacyUnpinned ? t('distribution.legacy_unpinned.version_unknown') : appliedRelease?.version_label || t('distribution.original_release')}
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
                disabled={isLegacyUnpinned || isPreparingUpdate || isApplyingUpdate}
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
              checked={!isLegacyUnpinned && Boolean(subscription?.auto_update_enabled)}
              onCheckedChange={handleToggleAutoUpdate}
              disabled={isLegacyUnpinned || isUpdatingSettings}
              aria-label={t('distribution.auto_update_label')}
            />
          </div>

          {/* Reset to Upstream Button */}
          <div className="pt-2 border-t">
            <Button
              variant="outline"
              size="sm"
              className="w-full text-destructive hover:text-destructive gap-2 border-destructive/30 hover:bg-destructive/10"
              onClick={() => handleResetOpenChange(true)}
              disabled={isLegacyUnpinned || isResettingToUpstream}
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
        onOpenChange={handleResetOpenChange}
        title={t('distribution.reset_upstream_confirm_title')}
        description={t('distribution.reset_upstream_confirm_desc')}
        confirmText={t('distribution.reset_upstream_confirm_btn')}
        cancelText={t('setup.cancel')}
        variant="destructive"
        isLoading={isResettingToUpstream}
        onConfirm={handleResetToUpstream}
      />

      {/* Conflict Resolution Dialog */}
      {activePendingUpdate && !isLegacyUnpinned && (
        <ConflictResolutionDialog
          open={conflictDialogOpen}
          onOpenChange={handleConflictOpenChange}
          pendingUpdate={activePendingUpdate}
          onApply={handleApplyResolvedUpdate}
          isApplying={isApplyingUpdate}
        />
      )}
    </div>
  )
}
