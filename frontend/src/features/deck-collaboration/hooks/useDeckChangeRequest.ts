import { useEffect, useMemo, useRef, useState } from 'react'
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '@/shared/api/client'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import {
  contributionItemToDiffItem,
  getActiveDeckChangeRequest,
  getLocalDeckChanges,
  sendDeckContribution,
  summarizeChangeRequest,
  summarizeLocalChanges,
} from '../api'
import type { DeckChangeRequest, DiffFilters } from '../types'

const PAGE_SIZE = 100

export function useDeckChangeRequest() {
  const { deckItemId = '' } = useParams<{ deckItemId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { t } = useTranslation('collaboration')
  const initializedRequest = useRef<string | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [filters, setFilters] = useState<DiffFilters>({ query: '', changeType: 'all' })
  const [pageIndex, setPageIndex] = useState(0)

  const localQuery = useInfiniteQuery({
    queryKey: ['local-deck-changes', deckItemId, filters],
    enabled: Boolean(deckItemId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      getLocalDeckChanges(
        deckItemId,
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

  const activeQuery = useInfiniteQuery({
    queryKey: ['active-deck-change-request', deckItemId, filters],
    enabled: Boolean(deckItemId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      getActiveDeckChangeRequest(
        deckItemId,
        {
          cursor: pageParam,
          limit: PAGE_SIZE,
          changeType: filters.changeType,
          query: filters.query,
        },
        signal,
      ),
    getNextPageParam: (page) => page.request?.page?.next_cursor || undefined,
  })

  const localPages = localQuery.data?.pages || []
  const activePages = activeQuery.data?.pages || []
  const activeRequest = activePages[0]?.request || null
  const localPreview = localPages[0]
  const isPendingReview = activeRequest?.status === 'pending_review'
  // Show the saved changes that will actually be sent. A matching draft also
  // carries the requester's previous conflict decisions; pending review is frozen.
  const showActiveRequest = Boolean(activeRequest && (isPendingReview ||
    activeRequest.overlay_fingerprint === localPreview?.overlay_fingerprint))
  const sourcePages = showActiveRequest ? activePages : localPages
  const visiblePageIndex = Math.min(pageIndex, Math.max(sourcePages.length - 1, 0))
  const visibleActiveRequest = showActiveRequest
    ? activePages[visiblePageIndex]?.request
    : null
  const visibleLocalPreview = showActiveRequest
    ? null
    : localPages[visiblePageIndex]

  useEffect(() => {
    initializedRequest.current = null
    setTitle('')
    setDescription('')
    setFilters({ query: '', changeType: 'all' })
  }, [deckItemId])

  useEffect(() => {
    if (!activeRequest || initializedRequest.current === activeRequest.id) return
    setTitle(activeRequest.title || '')
    setDescription(activeRequest.description || '')
    initializedRequest.current = activeRequest.id
  }, [activeRequest])

  const allDiffItems = useMemo(() => {
    const items = visibleActiveRequest?.items || visibleLocalPreview?.items || []
    return items.map((item, index) => contributionItemToDiffItem(item, index))
  }, [visibleActiveRequest?.items, visibleLocalPreview?.items])

  const summary = useMemo(
    () =>
      showActiveRequest && activeRequest
        ? summarizeChangeRequest(activeRequest)
        : localPreview
          ? summarizeLocalChanges(localPreview)
          : null,
    [activeRequest, localPreview, showActiveRequest],
  )

  useEffect(() => {
    setPageIndex(0)
  }, [activeRequest?.id, filters, showActiveRequest])

  function storeRequest(request: DeckChangeRequest) {
    queryClient.setQueriesData<InfiniteData<{ request: DeckChangeRequest | null }>>(
      { queryKey: ['active-deck-change-request', deckItemId] },
      (current) =>
        current
          ? {
              ...current,
              pages: current.pages.map((page) => ({
                ...page,
                request: page.request
                  ? {
                      ...page.request,
                      ...request,
                      items: page.request.items,
                      conflicts: page.request.conflicts,
                      page: page.request.page,
                    }
                  : request,
              })),
            }
          : current,
    )
  }

  const submitMutation = useMutation({
    mutationFn: () => sendDeckContribution(deckItemId, {
      title: title.trim(),
      description: description.trim(),
      expected_overlay_fingerprint: localPreview?.overlay_fingerprint || '',
    }),
    retry: false,
    onSuccess: (request) => {
      storeRequest(request)
      if (request.status === 'has_conflict') {
        toast.warning(
          t('request.toast_sync_conflicts', {
            count: request.unresolved_conflict_count,
            defaultValue: `Có ${request.unresolved_conflict_count} xung đột cần xử lý.`,
          }),
        )
        navigate(`/flashcards/change-requests/${request.id}`)
      } else {
        toast.success(
          t('request.toast_submit_success', 'Đã gửi đóng góp tới chủ sở hữu deck.'),
        )
      }
    },
    onError: (error) => {
      toast.error(error instanceof ApiError && error.code === 'CHANGE_REQUEST_STALE'
        ? t('request.stale_changes', 'Nội dung đã lưu vừa thay đổi. Hãy kiểm tra lại danh sách trước khi gửi.')
        : error instanceof Error ? error.message : t('request.send_error', 'Không thể gửi đóng góp.'))
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['local-deck-changes', deckItemId] })
      void queryClient.invalidateQueries({ queryKey: ['active-deck-change-request', deckItemId] })
      void queryClient.invalidateQueries({ queryKey: ['incoming-deck-change-requests'] })
      if (activeRequest) void queryClient.invalidateQueries({ queryKey: ['deck-change-request', activeRequest.id] })
    },
  })

  const isBusy = submitMutation.isPending
  const canSend = Boolean(localPreview?.item_count && !isPendingReview && !isBusy &&
    !localQuery.isFetching && !activeQuery.isFetching)
  const hasAnyChanges = Boolean(showActiveRequest ? activeRequest?.item_count : localPreview?.item_count)
  const isFetchingDiff = showActiveRequest ? activeQuery.isFetching : localQuery.isFetching
  const isFetchingMore = showActiveRequest
    ? activeQuery.isFetchingNextPage
    : localQuery.isFetchingNextPage
  const hasNextPage = showActiveRequest ? activeQuery.hasNextPage : localQuery.hasNextPage

  const onPreviousPage = () => {
    setPageIndex((current) => Math.max(0, current - 1))
  }

  const onLoadMore = () => {
    if (visiblePageIndex < sourcePages.length - 1) {
      setPageIndex((current) => current + 1)
      return
    }
    const previousPageCount = sourcePages.length
    const nextPage = showActiveRequest
      ? activeQuery.fetchNextPage()
      : localQuery.fetchNextPage()
    void nextPage.then((result) => {
      if ((result.data?.pages.length || 0) > previousPageCount) {
        setPageIndex((current) => current + 1)
      }
    })
  }

  return {
    deckItemId,
    title,
    setTitle,
    description,
    setDescription,
    filters,
    setFilters,
    pageIndex: visiblePageIndex,
    localQuery,
    activeQuery,
    activeRequest,
    localPreview,
    allDiffItems,
    summary,
    isPendingReview,
    isBusy,
    canSend,
    hasAnyChanges,
    isFetchingDiff,
    isFetchingMore,
    hasNextPage,
    sourcePagesLength: sourcePages.length,
    submitMutation,
    onPreviousPage,
    onLoadMore,
  }
}
