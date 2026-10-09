import {
  ArrowLeft,
  GitCompare,
  LoaderCircle,
  RefreshCcw,
  ShieldAlert,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import '@/shared/config/i18n'
import { DiffWorkspace } from '../components/DiffWorkspace'
import { BatchResolutionBar } from '../components/update/BatchResolutionBar'
import { ConflictCard } from '../components/update/ConflictCard'
import { LearningProgressGuarantee } from '../components/update/LearningProgressGuarantee'
import { UpdateActionSidebar } from '../components/update/UpdateActionSidebar'
import { useInstalledDeckUpdate } from '../hooks/useInstalledDeckUpdate'

export function InstalledDeckUpdatePage() {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  const {
    installId,
    releaseId,
    filters,
    setFilters,
    pageIndex,
    conflictPageIndex,
    setPageIndex,
    prepared,
    updatesQuery,
    diffQuery,
    conflictQuery,
    firstPage,
    items,
    loadedConflictPages,
    visibleConflictPage,
    visibleConflicts,
    allConflictsResolved,
    canApply,
    prepareMutation,
    resolveMutation,
    resolveAllMutation,
    autoUpdateMutation,
    detachMutation,
    applyMutation,
    onPreviousConflictPage,
    onNextConflictPage,
    onPreviousDiffPage,
    onNextDiffPage,
    hasMoreDiff,
  } = useInstalledDeckUpdate()

  if (!installId || !releaseId) {
    return (
      <Page>
        <PageError error={new Error('Thiếu mã bản cài hoặc release.')} />
      </Page>
    )
  }
  if (updatesQuery.isPending || diffQuery.isPending) {
    return (
      <PageLoading
        label={t('update.loading', 'Đang tải nội dung bản cập nhật…')}
      />
    )
  }
  if (updatesQuery.error || diffQuery.error || !firstPage) {
    return (
      <Page>
        <PageError
          error={
            updatesQuery.error ||
            diffQuery.error ||
            new Error('Không có dữ liệu cập nhật.')
          }
        />
      </Page>
    )
  }

  const handleDetach = () => {
    const confirmMessage = t(
      'update.confirm_detach',
      'Bạn có chắc chắn muốn tách bộ deck này khỏi Marketplace?\n\nSau khi tách, deck sẽ trở thành bộ thẻ cá nhân độc lập của bạn, không còn liên kết cập nhật từ tác giả nữa. Tiến độ học và toàn bộ thẻ từ vựng vẫn được bảo toàn 100%.',
    )
    if (window.confirm(confirmMessage)) {
      detachMutation.mutate()
    }
  }

  return (
    <Page className="max-w-[96rem]">
      <PageHeader
        title={t('update.title', 'Xem bản cập nhật deck')}
        description={t(
          'update.description',
          'So sánh release đang học với release mới. Lịch sử học được giữ theo Note/Card gốc.',
        )}
        actions={
          <Button variant="outline" asChild>
            <Link to="/installed-decks">
              <ArrowLeft />
              {t('update.btn_installed_decks', 'Deck đã cài')}
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">
                  <GitCompare className="mr-1.5 size-3.5" />
                  {firstPage.from_release?.version_label ||
                    t('update.original_release_label', 'Bản gốc')}
                  <span aria-hidden="true" className="mx-1">
                    →
                  </span>
                  {firstPage.target_release.version_label}
                </Badge>
                {updatesQuery.data.unread_update ? (
                  <Badge>{t('update.new_update_badge', 'Bản cập nhật mới')}</Badge>
                ) : null}
              </div>
              <CardTitle className="text-base font-bold">
                {t('update.changelog_title', 'Ghi chú phát hành')}
              </CardTitle>
              <CardDescription className="whitespace-pre-wrap text-xs">
                {firstPage.changelog ||
                  t(
                    'update.changelog_empty',
                    'Tác giả không thêm ghi chú chi tiết cho phiên bản này.',
                  )}
              </CardDescription>
            </CardHeader>
          </Card>

          {/* Learning Progress Preservation Guarantee */}
          <LearningProgressGuarantee />
        </div>

        <UpdateActionSidebar
          autoUpdateEnabled={Boolean(
            updatesQuery.data.installation.auto_update_enabled,
          )}
          isAutoUpdatePending={autoUpdateMutation.isPending}
          onToggleAutoUpdate={(checked) => autoUpdateMutation.mutate(checked)}
          updateAvailable={Boolean(updatesQuery.data.update_available)}
          alreadyApplied={Boolean(firstPage.already_applied)}
          prepared={prepared}
          isPreparing={prepareMutation.isPending}
          onPrepare={() => prepareMutation.mutate()}
          targetVersionLabel={firstPage.target_release.version_label}
          canApply={canApply}
          isApplying={applyMutation.isPending}
          isResolving={resolveMutation.isPending || resolveAllMutation.isPending}
          onApply={() => applyMutation.mutate()}
          isDetaching={detachMutation.isPending}
          onDetach={handleDetach}
          allConflictsResolved={allConflictsResolved}
        />
      </div>

      {prepared && prepared.conflict_count > 0 ? (
        <section className="space-y-3" aria-labelledby="update-conflicts-title">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="max-w-3xl">
              <h2
                id="update-conflicts-title"
                className="text-lg font-bold flex items-center gap-2"
              >
                <ShieldAlert className="size-5 text-amber-500" />
                {t('update.conflict_section_title', 'Xử lý xung đột 3-Way Merge')}
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {t(
                  'update.conflict_section_desc',
                  'Mỗi lựa chọn được lưu ngay vào bản chuẩn bị rebase.',
                )}
              </p>
            </div>
            <p
              className="text-xs font-bold text-muted-foreground tabular-nums"
              aria-live="polite"
            >
              {t('update.conflicts_resolved_count', {
                resolved: prepared.resolved_conflict_count.toLocaleString(locale),
                total: prepared.conflict_count.toLocaleString(locale),
                defaultValue: `Đã xử lý ${prepared.resolved_conflict_count}/${prepared.conflict_count}`,
              })}
            </p>
          </div>

          {/* Batch Resolution Bar */}
          <BatchResolutionBar
            conflictCount={prepared.conflict_count}
            isResolvingAll={resolveAllMutation.isPending}
            pendingResolutionMode={resolveAllMutation.variables}
            onResolveAll={(mode) => resolveAllMutation.mutate(mode)}
          />

          {conflictQuery.isPending ? (
            <div className="flex min-h-32 items-center justify-center gap-2 rounded-lg border text-sm text-muted-foreground">
              <LoaderCircle className="animate-spin" />
              {t('update.checking_3way', 'Đang tải xung đột…')}
            </div>
          ) : null}

          {conflictQuery.error ? (
            <Alert variant="destructive">
              <ShieldAlert />
              <AlertTitle>
                {t('update.conflict_load_error', 'Không tải được danh sách xung đột')}
              </AlertTitle>
              <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                <span>
                  {conflictQuery.error instanceof Error
                    ? conflictQuery.error.message
                    : t('update.conflict_load_error_desc', 'Hãy thử tải lại trang conflict hiện tại.')}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => void conflictQuery.refetch()}
                >
                  <RefreshCcw />
                  {t('update.retry', 'Thử lại')}
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}

          {visibleConflicts.map((conflict) => (
            <ConflictCard
              key={conflict.id}
              conflict={conflict}
              isSaving={resolveMutation.isPending}
              pendingResolution={
                resolveMutation.variables?.conflictId === conflict.id
                  ? resolveMutation.variables.resolution
                  : undefined
              }
              onResolve={(resolution) =>
                resolveMutation.mutate({
                  conflictId: conflict.id,
                  resolution,
                })
              }
            />
          ))}

          {visibleConflictPage ? (
            <nav
              className="flex flex-wrap items-center justify-between gap-3 border-t pt-3"
              aria-label={t(
                'update.pagination_aria_label',
                'Phân trang xung đột',
              )}
            >
              <p className="text-xs text-muted-foreground tabular-nums">
                {t('update.page_indicator', {
                  page: conflictPageIndex + 1,
                  count: visibleConflicts.length,
                  defaultValue: `Trang ${conflictPageIndex + 1} · ${visibleConflicts.length} field đang hiển thị`,
                })}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={
                    conflictPageIndex === 0 || conflictQuery.isFetchingNextPage
                  }
                  onClick={onPreviousConflictPage}
                >
                  {t('update.btn_prev', 'Trang trước')}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={
                    conflictQuery.isFetchingNextPage ||
                    (conflictPageIndex >= loadedConflictPages.length - 1 &&
                      !conflictQuery.hasNextPage)
                  }
                  onClick={onNextConflictPage}
                >
                  {conflictQuery.isFetchingNextPage ? (
                    <LoaderCircle className="animate-spin" />
                  ) : null}
                  {t('update.btn_next', 'Trang tiếp')}
                </Button>
              </div>
            </nav>
          ) : null}
        </section>
      ) : null}

      <DiffWorkspace
        summary={firstPage.summary}
        items={items}
        filters={filters}
        onFiltersChange={(nextFilters) => {
          setFilters(nextFilters)
          setPageIndex(0)
        }}
        isFetching={diffQuery.isFetching}
        isFetchingMore={diffQuery.isFetchingNextPage}
        hasPrevious={pageIndex > 0}
        onPrevious={onPreviousDiffPage}
        hasMore={hasMoreDiff}
        onLoadMore={onNextDiffPage}
        pageLabel={t('diff.page_label', {
          page: pageIndex + 1,
          defaultValue: `Trang ${pageIndex + 1}`,
        })}
        emptyTitle={t(
          'update.diff_empty_title',
          'Không có thay đổi trong bộ lọc',
        )}
        emptyDescription={t(
          'update.diff_empty_desc',
          'Thử chọn loại thay đổi khác hoặc xóa từ khóa tìm kiếm.',
        )}
      />
    </Page>
  )
}
