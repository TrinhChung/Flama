import { ArrowLeft, GitCompare, LoaderCircle, Rocket, Tag } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import '@/shared/config/i18n'
import { DiffWorkspace } from '../components/DiffWorkspace'
import { useReleaseBuilder } from '../hooks/useReleaseBuilder'

export function ReleaseBuilderPage() {
  const { t } = useTranslation('collaboration')
  const {
    itemId,
    filters,
    setFilters,
    pageIndex,
    versionLabel,
    setVersionLabel,
    changelog,
    setChangelog,
    previewQuery,
    firstPage,
    items,
    canPublish,
    publishMutation,
    onPreviousPage,
    onLoadMore,
    hasMore,
  } = useReleaseBuilder()

  if (!itemId) {
    return (
      <Page>
        <PageError
          error={new Error(t('release.error_missing_deck_id', 'Thiếu mã deck cần phát hành.'))}
        />
      </Page>
    )
  }
  if (previewQuery.isPending) {
    return (
      <PageLoading
        label={t('release.loading_calculating', 'Đang tính các thay đổi chưa phát hành…')}
      />
    )
  }
  if (previewQuery.error || !firstPage) {
    return (
      <Page>
        <PageError
          error={
            previewQuery.error ||
            new Error(t('release.error_no_preview_data', 'Không có dữ liệu preview.'))
          }
        />
      </Page>
    )
  }

  const pageDescription = firstPage.deck_title
    ? t('release.description_deck', {
        title: firstPage.deck_title,
        defaultValue: `Kiểm tra diff của “${firstPage.deck_title}” trước khi tạo release bất biến.`,
      })
    : t(
        'release.description_working',
        'Kiểm tra diff của working deck trước khi tạo release bất biến.',
      )

  const defaultVersionText = t('release.badge_new_version', 'Phiên bản mới')
  const defaultNoReleaseText = t('release.badge_no_release', 'Chưa có release')

  return (
    <Page size="wide">
      <PageHeader
        title={t('release.title', 'Phát hành phiên bản mới')}
        description={pageDescription}
        actions={
          <Button variant="outline" asChild>
            <Link to={`/marketplace/decks/${itemId}`}>
              <ArrowLeft />
              {t('release.back_to_shared', 'Quay lại deck')}
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">
                <GitCompare />
                {firstPage.base_release?.version_label || defaultNoReleaseText}
                <span aria-hidden="true">→</span>
                {versionLabel || defaultVersionText}
              </Badge>
              <Badge variant="secondary">
                {t('release.working_revision', {
                  revision: firstPage.working_revision ?? '—',
                  defaultValue: `Working revision ${firstPage.working_revision ?? '—'}`,
                })}
              </Badge>
            </div>
            <CardTitle>{t('release.content_title', 'Nội dung phát hành')}</CardTitle>
            <CardDescription>
              {t(
                'release.content_desc',
                'Owner edit chỉ nằm trong working tree. Chỉ thao tác này mới tạo cập nhật cho người đã cài deck.',
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-[12rem_minmax(0,1fr)]">
            <div className="space-y-2">
              <Label htmlFor="release-version">{t('release.version_label', 'Phiên bản')}</Label>
              <div className="relative">
                <Tag className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="release-version"
                  value={versionLabel}
                  onChange={(event) => setVersionLabel(event.target.value)}
                  className="pl-9 font-mono"
                  placeholder={t('release.version_placeholder', '1.1.0')}
                  autoComplete="off"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="release-changelog">{t('release.changelog_label', 'Ghi chú phát hành')}</Label>
              <Textarea
                id="release-changelog"
                value={changelog}
                onChange={(event) => setChangelog(event.target.value)}
                placeholder={t(
                  'release.changelog_placeholder',
                  'Tóm tắt các nội dung quan trọng trong phiên bản này…',
                )}
                rows={3}
              />
            </div>
          </CardContent>
        </Card>

        <Card className="h-fit lg:sticky lg:top-4">
          <CardHeader>
            <CardTitle className="text-base">{t('release.confirm_title', 'Xác nhận phát hành')}</CardTitle>
            <CardDescription>
              {t(
                'release.confirm_desc',
                'Release được lưu bất biến. Người cài deck sẽ tự chọn thời điểm cập nhật.',
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!firstPage.has_changes ? (
              <Alert>
                <AlertTitle>{t('release.no_changes_title', 'Không có thay đổi mới')}</AlertTitle>
                <AlertDescription>
                  {t('release.no_changes_desc', 'Working deck hiện giống release gần nhất.')}
                </AlertDescription>
              </Alert>
            ) : null}
            <Button
              className="w-full"
              size="lg"
              disabled={!canPublish || publishMutation.isPending}
              onClick={() => publishMutation.mutate()}
            >
              {publishMutation.isPending ? (
                <>
                  <LoaderCircle className="animate-spin" />
                  {t('release.btn_publishing', {
                    version: versionLabel || defaultVersionText,
                    defaultValue: `Đang phát hành ${versionLabel || defaultVersionText}…`,
                  })}
                </>
              ) : (
                <>
                  <Rocket />
                  {t('release.btn_publish', {
                    version: versionLabel || defaultVersionText,
                    defaultValue: `Phát hành ${versionLabel || defaultVersionText}`,
                  })}
                </>
              )}
            </Button>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {t(
                'release.revision_warning',
                'Thao tác dùng revision hiện tại để ngăn phát hành nhầm khi deck vừa được sửa ở nơi khác.',
              )}
            </p>
          </CardContent>
        </Card>
      </div>

      <DiffWorkspace
        summary={firstPage.summary}
        items={items}
        filters={filters}
        onFiltersChange={setFilters}
        isFetching={previewQuery.isFetching}
        isFetchingMore={previewQuery.isFetchingNextPage}
        hasPrevious={pageIndex > 0}
        onPrevious={onPreviousPage}
        hasMore={hasMore}
        onLoadMore={onLoadMore}
        pageLabel={t('diff.page_label', {
          page: pageIndex + 1,
          defaultValue: `Trang ${pageIndex + 1}`,
        })}
        emptyTitle={t('release.diff_empty_title', 'Không có thay đổi để phát hành')}
        emptyDescription={t(
          'release.diff_empty_desc',
          'Hãy đổi bộ lọc hoặc chỉnh sửa deck trước khi tạo release mới.',
        )}
      />
    </Page>
  )
}
