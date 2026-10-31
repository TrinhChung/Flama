import { useMemo, useState } from 'react'
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { useBootstrap } from '@/shared/api/bootstrap'
import { ApiError } from '@/shared/api/client'
import {
  approveDeckChangeRequest,
  getDeckChangeRequest,
  rejectDeckChangeRequest,
  resolveDeckChangeRequestConflict,
  sendDeckContribution,
} from '../api'
import { groupContributionPages } from '../model/noteChanges'
import type {
  ConflictResolutionInput,
  DeckChangeRequest,
  DiffFilters,
  NoteContext,
} from '../types'
import { refetchFromFirstPage } from './refetchFromFirstPage'
import { useReviewSelection } from './useChangeSelection'

const PAGE_SIZE = 100

export function useChangeRequestDetail() {
  const { requestId = '' } = useParams<{ requestId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const bootstrapQuery = useBootstrap()
  const { t } = useTranslation('collaboration')

  const [filters, setFilters] = useState<DiffFilters>({ query: '', changeType: 'all' })
  const [reviewComment, setReviewComment] = useState('')
  const [manualValues, setManualValues] = useState<Record<string, string>>({})

  const query = useInfiniteQuery({
    queryKey: ['deck-change-request', requestId, filters],
    enabled: Boolean(requestId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      getDeckChangeRequest(
        requestId,
        {
          cursor: pageParam,
          limit: PAGE_SIZE,
          changeType: filters.changeType,
          query: filters.query,
        },
        signal,
      ),
    getNextPageParam: (page) => page.page?.next_cursor || undefined,
  })

  const loadedPages = useMemo(() => query.data?.pages || [], [query.data?.pages])
  const request = loadedPages[0]
  // Pages end on whole notes, so loaded pages concatenate into complete notes.
  const grouped = useMemo(
    () => groupContributionPages(loadedPages),
    [loadedPages],
  )
  const noteContexts = useMemo(() => {
    const contexts: Record<string, NoteContext> = {}
    for (const page of loadedPages) Object.assign(contexts, page.notes || {})
    return contexts
  }, [loadedPages])
  const fieldDefs = request?.field_defs || []
  const reviewSelection = useReviewSelection({
    grouped,
    totalItems: request?.item_count || 0,
    resetKey: `${requestId}:${request?.status || ''}`,
  })

  function storeRequest(nextRequest: DeckChangeRequest) {
    queryClient.setQueriesData<InfiniteData<DeckChangeRequest>>(
      { queryKey: ['deck-change-request', requestId] },
      (current) =>
        current
          ? {
              ...current,
              pages: current.pages.map((page) => ({
                ...page,
                ...nextRequest,
                items: page.items,
                conflicts: page.conflicts,
                page: page.page,
              })),
            }
          : current,
    )
    queryClient.setQueriesData<InfiniteData<{ request: DeckChangeRequest | null }>>(
      { queryKey: ['active-deck-change-request', nextRequest.deck_item_id] },
      (current) =>
        current
          ? {
              ...current,
              pages: current.pages.map((page) => ({
                ...page,
                request:
                  nextRequest.status === 'merged' || nextRequest.status === 'rejected'
                    ? null
                    : page.request
                      ? {
                          ...page.request,
                          ...nextRequest,
                          items: page.request.items,
                          conflicts: page.request.conflicts,
                          page: page.request.page,
                        }
                      : nextRequest,
              })),
            }
          : current,
    )
    void refetchFromFirstPage(queryClient, ['active-deck-change-request', nextRequest.deck_item_id])
    void queryClient.invalidateQueries({ queryKey: ['incoming-deck-change-requests'] })
    if (nextRequest.status === 'merged') {
      void queryClient.invalidateQueries({
        queryKey: ['deck-release-preview', nextRequest.deck_item_id],
      })
    }
    void refetchFromFirstPage(queryClient, ['deck-change-request', requestId])
  }

  const resolveMutation = useMutation({
    mutationFn: ({
      conflictId,
      input,
    }: {
      conflictId: string
      input: ConflictResolutionInput
    }) =>
      resolveDeckChangeRequestConflict(
        request?.deck_item_id || '',
        requestId,
        conflictId,
        input,
      ),
    onSuccess: (nextRequest) => {
      storeRequest(nextRequest)
      toast.success(t('detail.toast_resolve_success', 'Đã lưu cách xử lý xung đột.'))
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Không thể xử lý xung đột.'),
  })

  const submitMutation = useMutation({
    mutationFn: () => sendDeckContribution(request?.deck_item_id || '', {
      title: request?.title || '', description: request?.description || '',
      expected_overlay_fingerprint: request?.overlay_fingerprint || '',
    }),
    retry: false,
    onSuccess: (nextRequest) => {
      storeRequest(nextRequest)
      if (nextRequest.status === 'has_conflict') {
        toast.warning(t('detail.toast_sync_conflicts', 'Nội dung gốc đã thay đổi. Hãy xử lý các field xung đột trước khi gửi.'))
      } else {
        toast.success(t('request.toast_submit_success', 'Đã gửi đóng góp tới chủ sở hữu deck.'))
      }
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'CHANGE_REQUEST_STALE') {
        toast.error(t('request.stale_changes', 'Nội dung đã lưu vừa thay đổi. Hãy kiểm tra lại danh sách trước khi gửi.'))
        navigate(`/flashcards/shared-decks/${request?.deck_item_id}/change-request`)
      } else {
        toast.error(error instanceof Error ? error.message : t('request.send_error', 'Không thể gửi đóng góp.'))
      }
    },
    onSettled: () => {
      void refetchFromFirstPage(queryClient, ['deck-change-request', requestId])
    },
  })

  const approveMutation = useMutation({
    mutationFn: (scope: 'selected' | 'all') => approveDeckChangeRequest(
      requestId,
      reviewComment.trim(),
      scope === 'all' ? undefined : reviewSelection.payload,
    ),
    onSuccess: (nextRequest) => {
      storeRequest(nextRequest)
      toast.success(
        t(
          'detail.toast_approve_success',
          'Đã merge đóng góp vào working deck. Thay đổi chưa được publish.',
        ),
      )
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Không thể merge request.'),
  })

  const rejectMutation = useMutation({
    mutationFn: () => rejectDeckChangeRequest(requestId, reviewComment.trim()),
    onSuccess: (nextRequest) => {
      storeRequest(nextRequest)
      toast.success(
        t(
          'detail.toast_reject_success',
          'Đã từ chối request; bản local của người đóng góp vẫn được giữ.',
        ),
      )
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Không thể từ chối request.'),
  })

  const unresolvedConflicts = loadedPages
    .flatMap((page) => page.conflicts || [])
    .filter((conflict) => !conflict.resolved_at)
  const viewerId = bootstrapQuery.data?.user?.id
  const isOwner = Boolean(viewerId && request?.owner?.id && viewerId === request.owner.id)
  const isRequester = Boolean(
    viewerId && request?.requester?.id && viewerId === request.requester.id,
  )
  const isBusy =
    resolveMutation.isPending ||
    submitMutation.isPending ||
    approveMutation.isPending ||
    rejectMutation.isPending

  return {
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
    onLoadMore: () => {
      void query.fetchNextPage()
    },
    hasMore: Boolean(query.hasNextPage),
  }
}
