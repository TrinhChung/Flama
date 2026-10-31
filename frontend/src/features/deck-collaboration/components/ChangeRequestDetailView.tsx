import { ArrowLeft, ShieldAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import '@/shared/config/i18n'
import { DiffWorkspace } from './DiffWorkspace'
import { ChangeRequestDetailActions } from './detail/ChangeRequestDetailActions'
import { ChangeRequestMetaCard } from './detail/ChangeRequestMetaCard'
import { ContributionConflictCard } from './detail/ContributionConflictCard'
import { useChangeRequestDetail } from '../hooks/useChangeRequestDetail'

export function ChangeRequestDetailView() {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  const {
    requestId,
    query,
    request,
    summary,
    allDiffItems,
    filters,
    setFilters,
    pageIndex,
    reviewComment,
    setReviewComment,
    manualValues,
    setManualValues,
    unresolvedConflicts,
    isOwner,
    isRequester,
    isBusy,
    loadedPagesLength,
    resolveMutation,
    submitMutation,
    approveMutation,
    rejectMutation,
    onPreviousPage,
    onLoadMore,
    hasMore,
  } = useChangeRequestDetail()

  if (!requestId) {
    return (
      <Page>
        <PageError
          error={new Error(t('detail.error_missing_id', 'Thiếu mã change request.'))}
        />
      </Page>
    )
  }
  if (query.isPending) {
    return <PageLoading label={t('detail.loading', 'Đang tải change request…')} />
  }
  if (query.error || !request || !summary) {
    return (
      <Page>
        <PageError
          error={
            query.error ||
            new Error(t('detail.error_not_found', 'Không tìm thấy change request.'))
          }
        />
      </Page>
    )
  }

  return (
    <Page size="wide">
      <PageHeader
        title={request.title}
        description={`${request.deck_item?.title || 'Shared deck'} · ${request.requester.username} → ${request.owner.username}`}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to={`/marketplace/decks/${request.deck_item_id}`}>
                <ArrowLeft />
                {t('detail.btn_shared_deck', 'Shared deck')}
              </Link>
            </Button>
            {isOwner ? (
              <Button variant="outline" asChild>
                <Link to="/flashcards/change-requests/incoming">
                  {t('detail.btn_inbox', 'Đóng góp cần duyệt')}
                </Link>
              </Button>
            ) : isRequester ? (
              <Button variant="outline" asChild>
                <Link to={`/flashcards/shared-decks/${request.deck_item_id}/change-request`}>
                  {t('detail.btn_my_contribution', 'Bản đóng góp của tôi')}
                </Link>
              </Button>
            ) : null}
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <ChangeRequestMetaCard request={request} />

        <ChangeRequestDetailActions
          request={request}
          isOwner={isOwner}
          isRequester={isRequester}
          isBusy={isBusy}
          reviewComment={reviewComment}
          onReviewCommentChange={setReviewComment}
          onApprove={() => approveMutation.mutate()}
          onReject={() => rejectMutation.mutate()}
          onSubmit={() => submitMutation.mutate()}
          isApproving={approveMutation.isPending}
          isRejecting={rejectMutation.isPending}
          isSubmitting={submitMutation.isPending}
        />
      </div>

      {request.can_resolve && unresolvedConflicts.length ? (
        <section className="space-y-3" aria-labelledby="contribution-conflicts-title">
          <div>
            <h2 id="contribution-conflicts-title" className="text-lg font-semibold">
              {t('detail.conflicts_title', 'Xử lý xung đột')}
            </h2>
            <p className="text-sm text-muted-foreground">
              {t(
                'detail.conflicts_desc',
                'So sánh base, upstream và bản local rồi chọn kết quả cho từng field.',
              )}
            </p>
          </div>
          {unresolvedConflicts.map((conflict) => (
            <ContributionConflictCard
              key={conflict.id}
              conflict={conflict}
              manualValue={manualValues[conflict.id] || ''}
              disabled={resolveMutation.isPending}
              onManualValueChange={(value) =>
                setManualValues((current) => ({
                  ...current,
                  [conflict.id]: value,
                }))
              }
              onResolve={(input) =>
                resolveMutation.mutate({
                  conflictId: conflict.id,
                  input,
                })
              }
            />
          ))}
        </section>
      ) : null}

      {request.can_resolve &&
      request.unresolved_conflict_count > 0 &&
      !unresolvedConflicts.length &&
      filters.changeType !== 'conflict' ? (
        <Alert>
          <ShieldAlert />
          <AlertTitle>
            {t('detail.conflict_remaining_title', {
              count: request.unresolved_conflict_count.toLocaleString(locale),
              defaultValue: `Còn ${request.unresolved_conflict_count.toLocaleString(locale)} xung đột`,
            })}
          </AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            {t(
              'detail.conflict_remaining_desc',
              'Chuyển sang bộ lọc xung đột để xử lý theo từng field.',
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                setFilters((current) => ({
                  ...current,
                  changeType: 'conflict',
                }))
              }
            >
              {t('detail.btn_view_conflicts', 'Xem xung đột')}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      <DiffWorkspace
        summary={summary}
        items={allDiffItems}
        filters={filters}
        onFiltersChange={(nextFilters) => {
          setFilters(nextFilters)
        }}
        isFetching={query.isFetching}
        isFetchingMore={query.isFetchingNextPage}
        hasPrevious={pageIndex > 0}
        onPrevious={onPreviousPage}
        hasMore={pageIndex < loadedPagesLength - 1 || hasMore}
        onLoadMore={onLoadMore}
        pageLabel={t('diff.page_label', {
          page: pageIndex + 1,
          defaultValue: `Trang ${pageIndex + 1}`,
        })}
        emptyTitle={t('diff.empty_filter_title', 'Không có thay đổi khớp bộ lọc')}
        emptyDescription={t(
          'diff.empty_filter_desc',
          'Thử chọn loại thay đổi khác hoặc xóa từ khóa tìm kiếm.'
        )}
      />
    </Page>
  )
}
