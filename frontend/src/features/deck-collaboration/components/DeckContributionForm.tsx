import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/shared/ui'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import '@/shared/config/i18n'
import {
  ContributionMetaCard,
  ContributionSendCard,
  ContributionMobileBar,
} from './contribution'
import { NoteChangeList } from './notes/NoteChangeList'
import { useDeckChangeRequest } from '../hooks/useDeckChangeRequest'

export function DeckContributionForm() {
  const { t } = useTranslation('collaboration')

  const {
    deckItemId,
    title,
    setTitle,
    description,
    setDescription,
    query,
    setQuery,
    localQuery,
    activeQuery,
    activeRequest,
    localPreview,
    grouped,
    noteContexts,
    fieldDefs,
    totalNotes,
    selectionControls,
    hasSelection,
    isPendingReview,
    isBusy,
    canSend,
    hasAnyChanges,
    isFetchingDiff,
    isFetchingMore,
    hasNextPage,
    submitMutation,
    onLoadMore,
  } = useDeckChangeRequest()

  if (!deckItemId) {
    return (
      <Page>
        <PageError
          error={new Error(t('request.error_missing_deck_id', 'Thiếu mã shared deck.'))}
        />
      </Page>
    )
  }
  if (localQuery.isPending || activeQuery.isPending) {
    return <PageLoading label={t('request.loading', 'Đang tải các thay đổi local…')} />
  }
  if (localQuery.error || activeQuery.error) {
    return (
      <Page>
        <PageError error={localQuery.error || activeQuery.error} />
      </Page>
    )
  }
  if (!localPreview) {
    return (
      <Page>
        <PageError
          error={new Error(t('request.error_no_diff_data', 'Không có dữ liệu diff đóng góp.'))}
        />
      </Page>
    )
  }

  const effectiveTotalNotes = selectionControls?.totalCount ?? totalNotes
  const effectiveSelectedNotes = selectionControls?.selectedCount ?? totalNotes

  return (
    <Page size="wide" className={hasAnyChanges ? 'pb-20 md:pb-0' : undefined}>
      <PageHeader
        title={t('request.title', 'Đóng góp thay đổi')}
        description={t(
          'request.description',
          'Xem lại những thay đổi bạn đã lưu rồi gửi cho tác giả duyệt. Phần sửa riêng của bạn vẫn được giữ.',
        )}
        actions={
          <Button variant="outline" asChild>
            <Link to={`/marketplace/decks/${deckItemId}`}>
              <ArrowLeft />
              {t('request.btn_back', 'Quay lại deck')}
            </Link>
          </Button>
        }
      />

      <div className="space-y-6">
        {/* Top Header: Proportional Layout (Left Wide Form + Right Compact Send Card) */}
        <div className="grid items-stretch gap-4 md:grid-cols-[minmax(0,1fr)_21rem]">
          <ContributionMetaCard
            title={title}
            onTitleChange={setTitle}
            description={description}
            onDescriptionChange={setDescription}
            totalNotes={effectiveTotalNotes}
            isPendingReview={isPendingReview}
            isBusy={isBusy}
          />

          <ContributionSendCard
            activeRequest={activeRequest}
            totalNotes={effectiveTotalNotes}
            selectedNotes={effectiveSelectedNotes}
            hasSelection={hasSelection}
            hasLocalChanges={Boolean(localPreview.item_count)}
            isPendingReview={isPendingReview}
            isBusy={isBusy}
            isSending={submitMutation.isPending}
            canSend={canSend}
            onSend={() => submitMutation.mutate()}
          />
        </div>

        {/* Changes Section: 100% Full Width for Maximum Diff Reading Space */}
        {!hasAnyChanges ? (
          <Alert>
            <AlertTitle>{t('request.no_local_changes_title', 'Chưa có thay đổi đã lưu')}</AlertTitle>
            <AlertDescription>
              {t(
                'request.no_local_changes_desc',
                'Hãy sửa và lưu ít nhất một field trong deck đã cài, sau đó quay lại trang này. Tiêu đề và mô tả chỉ dùng để giải thích đóng góp.',
              )}
            </AlertDescription>
          </Alert>
        ) : (
          <NoteChangeList
            grouped={grouped}
            fieldDefs={fieldDefs}
            noteContexts={noteContexts}
            totalNotes={totalNotes}
            selection={selectionControls}
            query={query}
            onQueryChange={setQuery}
            isFetching={isFetchingDiff}
            isFetchingMore={isFetchingMore}
            hasMore={hasNextPage}
            onLoadMore={onLoadMore}
          />
        )}
      </div>

      {/* Floating Bottom Bar on Mobile (< 768px) so user can submit without scrolling back to top */}
      {hasAnyChanges ? (
        <ContributionMobileBar
          totalNotes={effectiveTotalNotes}
          selectedNotes={effectiveSelectedNotes}
          canSend={canSend}
          isSending={submitMutation.isPending}
          isBusy={isBusy}
          isPendingReview={isPendingReview}
          onSend={() => submitMutation.mutate()}
        />
      ) : null}
    </Page>
  )
}
