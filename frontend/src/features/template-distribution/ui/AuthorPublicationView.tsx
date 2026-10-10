import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { CheckCircle2, Clock, Tag, UploadCloud } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useTemplatePublication } from '../hooks/useTemplatePublication'
import { PublishReleaseDialog } from './PublishReleaseDialog'

export interface AuthorPublicationViewProps {
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

export function AuthorPublicationView({
  templateId,
  currentVersionId,
  onSourceChanged,
}: AuthorPublicationViewProps) {
  const { t, i18n } = useTranslation('card_templates')
  const [publishDialogOpen, setPublishDialogOpen] = useState(false)

  const {
    publication,
    releases,
    isLoading,
    isError,
    error,
    refetch,
    updateSettings,
    isUpdatingSettings,
    publishRelease,
    isPublishing,
  } = useTemplatePublication(templateId)

  const handleToggleAutoPublish = async (checked: boolean) => {
    try {
      await updateSettings({ auto_publish_enabled: checked })
      toast.success(t('setup.saved'))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('distribution.publish_error'))
    }
  }

  const handlePublish = async (body: { version_label: string; change_note?: string }) => {
    await publishRelease({
      version_label: body.version_label,
      change_note: body.change_note,
      expected_current_release_id: publication?.current_release?.id ?? null,
      expected_current_version_id: currentVersionId ?? publication?.current_version_id ?? null,
    })
    toast.success(t('distribution.publish_success', { version: body.version_label }))
    onSourceChanged?.()
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

  const currentRelease = publication?.current_release

  return (
    <div className="space-y-6">
      {/* Overview Card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <UploadCloud className="size-4 text-primary" />
              {t('distribution.author_title')}
            </CardTitle>
            {publication?.has_unpublished_changes ? (
              <Badge variant="outline" className="border-amber-500/40 text-amber-600 dark:text-amber-400">
                {t('distribution.unpublished_changes_badge')}
              </Badge>
            ) : (
              <Badge variant="secondary" className="gap-1">
                <CheckCircle2 className="size-3 text-emerald-600" />
                {t('distribution.up_to_date_badge')}
              </Badge>
            )}
          </div>
          <CardDescription className="text-xs">
            {t('distribution.author_description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {/* Current release summary */}
          <div className="rounded-lg border bg-muted/20 p-3 space-y-1.5">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{t('distribution.current_release')}</span>
              {currentRelease && (
                <span>{formatDate(currentRelease.published_at, i18n.language)}</span>
              )}
            </div>
            {currentRelease ? (
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-foreground text-sm">
                    {currentRelease.version_label}
                  </span>
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                    #{currentRelease.sequence_no}
                  </Badge>
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4">
                    {currentRelease.publish_mode === 'automatic'
                      ? t('distribution.publish_mode_auto')
                      : t('distribution.publish_mode_manual')}
                  </Badge>
                </div>
                {currentRelease.change_note && (
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                    {currentRelease.change_note}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground italic">
                {t('distribution.no_release_yet')}
              </p>
            )}
          </div>

          {/* Auto-publish setting */}
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="space-y-0.5 pr-4">
              <label htmlFor="auto-publish-switch" className="text-sm font-medium cursor-pointer">
                {t('distribution.auto_publish_label')}
              </label>
              <p className="text-xs text-muted-foreground">
                {t('distribution.auto_publish_desc')}
              </p>
            </div>
            <Switch
              id="auto-publish-switch"
              checked={Boolean(publication?.auto_publish_enabled)}
              onCheckedChange={handleToggleAutoPublish}
              disabled={isUpdatingSettings}
              aria-label={t('distribution.auto_publish_label')}
            />
          </div>

          {/* Publish action button */}
          <div className="pt-1">
            <Button
              className="w-full gap-2"
              onClick={() => setPublishDialogOpen(true)}
              disabled={isPublishing || isUpdatingSettings}
            >
              <Tag className="size-4" />
              {t('distribution.publish_button')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Release History */}
      <div className="space-y-3">
        <h4 className="text-sm font-semibold flex items-center gap-2">
          <Clock className="size-4 text-muted-foreground" />
          {t('distribution.release_history_title')}
          <span className="text-xs font-normal text-muted-foreground">
            ({releases.length})
          </span>
        </h4>

        {releases.length === 0 ? (
          <div className="rounded-xl border border-dashed p-6 text-center text-xs text-muted-foreground">
            {t('distribution.release_history_empty')}
          </div>
        ) : (
          <div className="space-y-2">
            {releases.map((rel) => (
              <div
                key={rel.id}
                className="rounded-xl border p-3 text-xs space-y-1.5 hover:bg-muted/10 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-foreground">
                      {rel.version_label}
                    </span>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                      #{rel.sequence_no}
                    </Badge>
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4">
                      {rel.publish_mode === 'automatic'
                        ? t('distribution.publish_mode_auto')
                        : t('distribution.publish_mode_manual')}
                    </Badge>
                  </div>
                  <span className="text-muted-foreground">
                    {formatDate(rel.published_at, i18n.language)}
                  </span>
                </div>
                {rel.change_note ? (
                  <p className="text-muted-foreground leading-relaxed whitespace-pre-wrap">
                    {rel.change_note}
                  </p>
                ) : (
                  <p className="text-muted-foreground italic text-[11px]">
                    {t('distribution.no_change_note')}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <PublishReleaseDialog
        open={publishDialogOpen}
        onOpenChange={setPublishDialogOpen}
        onPublish={handlePublish}
        isPublishing={isPublishing}
      />
    </div>
  )
}
