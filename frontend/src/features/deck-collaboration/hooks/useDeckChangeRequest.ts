import { useEffect, useMemo, useRef, useState } from 'react'
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import {
  buildDeckChangeRequestDraft,
  contributionItemToDiffItem,
  getActiveDeckChangeRequest,
  getLocalDeckChanges,
  submitDeckChangeRequest,
  summarizeChangeRequest,
  summarizeLocalChanges,
  syncDeckChangeRequest,
} from '../api'
import type { DeckChangeRequest, DiffFilters } from '../types'

const PAGE_SIZE = 100

export function useDeckChangeRequest() {
  const { deckItemId = '' } = useParams<{ deckItemId: string }>()
  const queryClient = useQueryClient()
  const { t } = useTranslation('collaboration')
  const formInitialized = useRef(false)
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
  const sourcePages = activeRequest ? activePages : localPages
  const visiblePageIndex = Math.min(pageIndex, Math.max(sourcePages.length - 1, 0))
  const visibleActiveRequest = activeRequest
    ? activePages[visiblePageIndex]?.request
    : null
  const visibleLocalPreview = activeRequest
    ? null
    : localPages[visiblePageIndex]
  const localPreview = localPages[0]

  useEffect(() => {
    if (!activeRequest || formInitialized.current) return
    setTitle(activeRequest.title || '')
    setDescription(activeRequest.description || '')
    formInitialized.current = true
  }, [activeRequest])

  const allDiffItems = useMemo(() => {
    const items = visibleActiveRequest?.items || visibleLocalPreview?.items || []
    return items.map((item, index) => contributionItemToDiffItem(item, index))
  }, [visibleActiveRequest?.items, visibleLocalPreview?.items])

  const summary = useMemo(
    () =>
      activeRequest
        ? summarizeChangeRequest(activeRequest)
        : localPreview
          ? summarizeLocalChanges(localPreview)
          : null,
    [activeRequest, localPreview],
  )

  useEffect(() => {
    setPageIndex(0)
  }, [activeRequest?.id, filters])

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
    void queryClient.invalidateQueries({
      queryKey: ['active-deck-change-request', deckItemId],
    })
  }

  const draftMutation = useMutation({
    mutationFn: () =>
      buildDeckChangeRequestDraft(deckItemId, {
        title: title.trim(),
        description: description.trim(),
      }),
    onSuccess: (request) => {
      storeRequest(request)
      toast.success(
        t('request.toast_draft_created', 'Đã tạo bản nháp từ các thay đổi local đã lưu.'),
      )
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : 'Không thể tạo bản nháp đóng góp.',
      ),
  })

  const syncMutation = useMutation({
    mutationFn: () => syncDeckChangeRequest(deckItemId, activeRequest?.id || ''),
    onSuccess: (request) => {
      storeRequest(request)
      if (request.unresolved_conflict_count) {
        toast.warning(
          t('request.toast_sync_conflicts', {
            count: request.unresolved_conflict_count,
            defaultValue: `Có ${request.unresolved_conflict_count} xung đột cần xử lý.`,
          }),
        )
      } else {
        toast.success(
          t('request.toast_sync_success', 'Bản nháp đã đồng bộ với deck gốc.'),
        )
      }
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : 'Không thể đồng bộ với deck gốc.',
      ),
  })

  const submitMutation = useMutation({
    mutationFn: () => submitDeckChangeRequest(deckItemId, activeRequest?.id || ''),
    onSuccess: (request) => {
      storeRequest(request)
      toast.success(
        t('request.toast_submit_success', 'Đã gửi đóng góp tới chủ sở hữu deck.'),
      )
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : 'Không thể gửi đóng góp.',
      ),
  })

  const isPendingReview = activeRequest?.status === 'pending_review'
  const isBusy = draftMutation.isPending || syncMutation.isPending || submitMutation.isPending
  const hasAnyChanges = Boolean(activeRequest?.item_count || localPreview?.item_count)
  const isFetchingDiff = activeRequest ? activeQuery.isFetching : localQuery.isFetching
  const isFetchingMore = activeRequest
    ? activeQuery.isFetchingNextPage
    : localQuery.isFetchingNextPage
  const hasNextPage = activeRequest ? activeQuery.hasNextPage : localQuery.hasNextPage

  const onPreviousPage = () => {
    setPageIndex((current) => Math.max(0, current - 1))
  }

  const onLoadMore = () => {
    if (visiblePageIndex < sourcePages.length - 1) {
      setPageIndex((current) => current + 1)
      return
    }
    const previousPageCount = sourcePages.length
    const nextPage = activeRequest
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
    hasAnyChanges,
    isFetchingDiff,
    isFetchingMore,
    hasNextPage,
    sourcePagesLength: sourcePages.length,
    draftMutation,
    syncMutation,
    submitMutation,
    onPreviousPage,
    onLoadMore,
  }
}
