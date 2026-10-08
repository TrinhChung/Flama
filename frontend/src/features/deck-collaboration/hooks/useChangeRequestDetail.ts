import { useEffect, useMemo, useState } from 'react'
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { useBootstrap } from '@/shared/api/bootstrap'
import {
  approveDeckChangeRequest,
  contributionItemToDiffItem,
  getDeckChangeRequest,
  rejectDeckChangeRequest,
  resolveDeckChangeRequestConflict,
  submitDeckChangeRequest,
  summarizeChangeRequest,
  syncDeckChangeRequest,
} from '../api'
import type {
  ConflictResolutionInput,
  DeckChangeRequest,
  DiffFilters,
} from '../types'

const PAGE_SIZE = 100

export function useChangeRequestDetail() {
  const { requestId = '' } = useParams<{ requestId: string }>()
  const queryClient = useQueryClient()
  const bootstrapQuery = useBootstrap()
  const { t } = useTranslation('collaboration')

  const [filters, setFilters] = useState<DiffFilters>({ query: '', changeType: 'all' })
  const [pageIndex, setPageIndex] = useState(0)
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

  const loadedPages = query.data?.pages || []
  const request = loadedPages[0]
  const visiblePageIndex = Math.min(pageIndex, Math.max(loadedPages.length - 1, 0))
  const visibleRequest = loadedPages[visiblePageIndex]
  const allDiffItems = useMemo(
    () =>
      visibleRequest?.items.map((item, index) =>
        contributionItemToDiffItem(item, index),
      ) || [],
    [visibleRequest?.items],
  )
  const summary = useMemo(
    () => (request ? summarizeChangeRequest(request) : null),
    [request],
  )

  useEffect(() => {
    setPageIndex(0)
  }, [filters, requestId])

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
    void queryClient.invalidateQueries({
      queryKey: ['active-deck-change-request', nextRequest.deck_item_id],
    })
    void queryClient.invalidateQueries({ queryKey: ['incoming-deck-change-requests'] })
    if (nextRequest.status === 'merged') {
      void queryClient.invalidateQueries({
        queryKey: ['deck-release-preview', nextRequest.deck_item_id],
      })
    }
    void queryClient.invalidateQueries({ queryKey: ['deck-change-request', requestId] })
  }

  const syncMutation = useMutation({
    mutationFn: () => syncDeckChangeRequest(request?.deck_item_id || '', requestId),
    onSuccess: (nextRequest) => {
      storeRequest(nextRequest)
      toast.success(
        nextRequest.unresolved_conflict_count
          ? t('detail.toast_sync_conflicts', 'Đã đồng bộ; vẫn còn xung đột cần xử lý.')
          : t('detail.toast_sync_success', 'Đã đồng bộ với deck gốc.'),
      )
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Không thể đồng bộ.'),
  })

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
    mutationFn: () => submitDeckChangeRequest(request?.deck_item_id || '', requestId),
    onSuccess: (nextRequest) => {
      storeRequest(nextRequest)
      toast.success(t('detail.toast_submit_success', 'Đã gửi request tới owner.'))
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Không thể gửi request.'),
  })

  const approveMutation = useMutation({
    mutationFn: () => approveDeckChangeRequest(requestId, reviewComment.trim()),
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

  const unresolvedConflicts = (visibleRequest?.conflicts || []).filter(
    (conflict) => !conflict.resolved_at,
  )
  const viewerId = bootstrapQuery.data?.user?.id
  const isOwner = Boolean(viewerId && request?.owner?.id && viewerId === request.owner.id)
  const isRequester = Boolean(
    viewerId && request?.requester?.id && viewerId === request.requester.id,
  )
  const isBusy =
    syncMutation.isPending ||
    resolveMutation.isPending ||
    submitMutation.isPending ||
    approveMutation.isPending ||
    rejectMutation.isPending

  const onPreviousPage = () => {
    setPageIndex((current) => Math.max(0, current - 1))
  }

  const onLoadMore = () => {
    if (visiblePageIndex < loadedPages.length - 1) {
      setPageIndex((current) => current + 1)
      return
    }
    void query.fetchNextPage().then((result) => {
      if ((result.data?.pages.length || 0) > loadedPages.length) {
        setPageIndex((current) => current + 1)
      }
    })
  }

  const hasMore = visiblePageIndex < loadedPages.length - 1 || Boolean(query.hasNextPage)

  return {
    requestId,
    query,
    request,
    visibleRequest,
    summary,
    allDiffItems,
    filters,
    setFilters,
    pageIndex: visiblePageIndex,
    reviewComment,
    setReviewComment,
    manualValues,
    setManualValues,
    unresolvedConflicts,
    isOwner,
    isRequester,
    isBusy,
    loadedPagesLength: loadedPages.length,
    syncMutation,
    resolveMutation,
    submitMutation,
    approveMutation,
    rejectMutation,
    onPreviousPage,
    onLoadMore,
    hasMore,
  }
}
