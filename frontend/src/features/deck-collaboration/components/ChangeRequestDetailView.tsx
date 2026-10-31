import { useMemo } from 'react'
import { ArrowLeft, ShieldAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import '@/shared/config/i18n'
import { ChangeRequestDetailActions } from './detail/ChangeRequestDetailActions'
import { ChangeRequestMetaCard } from './detail/ChangeRequestMetaCard'
import { ContributionConflictCard } from './detail/ContributionConflictCard'
import { NoteChangeList } from './notes/NoteChangeList'
import { useChangeRequestDetail } from '../hooks/useChangeRequestDetail'

export function ChangeRequestDetailView() {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  const {
    requestId,
    query,
    request,
    grouped,
    noteContexts,
    fieldDefs,
    reviewSelection,
    filters,
    setFilters,
    reviewComment,
    setReviewComment,
    manualValues,
    setManualValues,
    unresolvedConflicts,
    isOwner,
    isRequester,
    isBusy,
    resolveMutation,
    submitMutation,
    approveMutation,
    rejectMutation,
    onLoadMore,
    hasMore,
  } = useChangeRequestDetail()

  // Conflicts name the note and field they are about, never internal ids.
  const conflictSubjects = useMemo(() => {
    const typesByName = new Map(fieldDefs.map((field) => [field.name, field.field_type]))
    const subjects = new Map<string, { title: string; fieldName: string; fieldType: string }>()
    for (const note of grouped.notes) {
      const noteLabel = note.label || noteContexts[note.noteId]?.label || t('notes.untitled_note', 'Note chưa có tên')
      for (const change of note.changes) {
        if (!change.itemId) continue
        subjects.set(change.itemId, {
          title: `${noteLabel} · ${change.fieldName}`,
          fieldName: change.fieldName,
          fieldType: typesByName.get(change.fieldName) || 'text',
        })
      }
    }
    for (const change of grouped.schema) {
      if (change.itemId) {
        subjects.set(change.itemId, {
          title: `${t('notes.schema_title', 'Cấu trúc trường')} · ${change.fieldName}`,
          fieldName: change.fieldName,
          fieldType: 'text',
        })
      }
    }
    return subjects
  }, [fieldDefs, grouped, noteContexts, t])

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
  if (query.error || !request) {
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

  const deckTitle = request.deck_item?.title || t('detail.btn_shared_deck', 'Shared deck')

  return (
    <Page size="wide">
      <PageHeader
        title={request.title || t('detail.untitled', { deck: deckTitle, defaultValue: `Đóng góp cho “${deckTitle}”` })}
        description={deckTitle}
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
          acceptsEverything={reviewSelection.acceptsEverything}
          selectedCount={reviewSelection.controls.selectedCount}
          onApprove={(scope) => approveMutation.mutate(scope)}
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
                'So sánh bản gốc lúc bạn sửa, bản của bạn và bản tác giả đang có, rồi chọn kết quả cho từng trường.',
              )}
            </p>
          </div>
          {unresolvedConflicts.map((conflict) => {
            const subject = (conflict.item_id && conflictSubjects.get(conflict.item_id)) || {
              title: t('notes.badge_conflict', 'Xung đột'),
              fieldName: '',
              fieldType: 'text',
            }
            return (
              <ContributionConflictCard
                key={conflict.id}
                conflict={conflict}
                title={subject.title}
                fieldName={subject.fieldName}
                fieldType={subject.fieldType}
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
            )
          })}
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
              'Lọc các note có xung đột để xử lý từng trường.',
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

      <NoteChangeList
        grouped={grouped}
        fieldDefs={fieldDefs}
        noteContexts={noteContexts}
        totalNotes={request.note_count ?? grouped.notes.length}
        selection={request.can_review ? reviewSelection.controls : undefined}
        query={filters.query}
        onQueryChange={(nextQuery) => setFilters((current) => ({ ...current, query: nextQuery }))}
        isFetching={query.isFetching}
        isFetchingMore={query.isFetchingNextPage}
        hasMore={hasMore}
        onLoadMore={onLoadMore}
      />
    </Page>
  )
}
