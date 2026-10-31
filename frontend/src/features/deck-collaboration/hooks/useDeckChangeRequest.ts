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
  getActiveDeckChangeRequest,
  getLocalDeckChanges,
  sendDeckContribution,
} from '../api'
import { groupContributionPages, type ContributionChange } from '../model/noteChanges'
import type { DeckChangeRequest, NoteContext, NoteContextPage } from '../types'
import { refetchFromFirstPage } from './refetchFromFirstPage'
import { useContributionSelection } from './useChangeSelection'

const PAGE_SIZE = 100

function mergeNoteContexts(pages: NoteContextPage[]) {
  const contexts: Record<string, NoteContext> = {}
  for (const page of pages) Object.assign(contexts, page.notes || {})
  return contexts
}

export function useDeckChangeRequest() {
  const { deckItemId = '' } = useParams<{ deckItemId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { t } = useTranslation('collaboration')
  const initializedRequest = useRef<string | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [query, setQuery] = useState('')
  const filters = useMemo(() => ({ query, changeType: 'all' as const }), [query])

  const localQuery = useInfiniteQuery({
    queryKey: ['local-deck-changes', deckItemId, filters],
    enabled: Boolean(deckItemId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      getLocalDeckChanges(
        deckItemId,
        { cursor: pageParam, limit: PAGE_SIZE, changeType: filters.changeType, query: filters.query },
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
        { cursor: pageParam, limit: PAGE_SIZE, changeType: filters.changeType, query: filters.query },
        signal,
      ),
    getNextPageParam: (page) => page.request?.page?.next_cursor || undefined,
  })

  const localPages = useMemo(() => localQuery.data?.pages || [], [localQuery.data?.pages])
  const activePages = useMemo(
    () => (activeQuery.data?.pages || []).flatMap((page) => (page.request ? [page.request] : [])),
    [activeQuery.data?.pages],
  )
  const activeRequest = activePages[0] || null
  const localPreview = localPages[0]
  const isPendingReview = activeRequest?.status === 'pending_review'
  // A pending contribution is frozen, so show what was sent. Otherwise show
  // every saved edit so the contributor can choose which notes to send.
  const sourcePages: Array<NoteContextPage & { items: ContributionChange[] }> = isPendingReview
    ? activePages
    : localPages

  useEffect(() => {
    initializedRequest.current = null
    setTitle('')
    setDescription('')
    setQuery('')
  }, [deckItemId])

  useEffect(() => {
    if (!activeRequest || initializedRequest.current === activeRequest.id) return
    setTitle(activeRequest.title || '')
    setDescription(activeRequest.description || '')
    initializedRequest.current = activeRequest.id
  }, [activeRequest])

  const grouped = useMemo(
    () => groupContributionPages(sourcePages),
    [sourcePages],
  )
  const noteContexts = useMemo(() => mergeNoteContexts(sourcePages), [sourcePages])
  const fieldDefs = sourcePages[0]?.field_defs || []
  const totalNotes = (isPendingReview ? activeRequest?.note_count : localPreview?.note_count)
    ?? grouped.notes.length

  const selection = useContributionSelection({
    grouped,
    totalNotes,
    resetKey: `${deckItemId}:${localPreview?.overlay_fingerprint || ''}`,
  })

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
      selection: selection.payload,
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
      void refetchFromFirstPage(queryClient, ['local-deck-changes', deckItemId])
      void refetchFromFirstPage(queryClient, ['active-deck-change-request', deckItemId])
      void queryClient.invalidateQueries({ queryKey: ['incoming-deck-change-requests'] })
      if (activeRequest) void refetchFromFirstPage(queryClient, ['deck-change-request', activeRequest.id])
    },
  })

  const sourceQuery = isPendingReview ? activeQuery : localQuery
  const isBusy = submitMutation.isPending
  const canSend = Boolean(localPreview?.item_count && !isPendingReview && !isBusy &&
    selection.hasSelection && !localQuery.isFetching && !activeQuery.isFetching)
  const hasAnyChanges = Boolean(isPendingReview ? activeRequest?.item_count : localPreview?.item_count)

  return {
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
    selectionControls: isPendingReview ? undefined : selection.controls,
    hasSelection: selection.hasSelection,
    isPendingReview,
    isBusy,
    canSend,
    hasAnyChanges,
    isFetchingDiff: sourceQuery.isFetching,
    isFetchingMore: sourceQuery.isFetchingNextPage,
    hasNextPage: Boolean(sourceQuery.hasNextPage),
    submitMutation,
    onLoadMore: () => {
      void sourceQuery.fetchNextPage()
    },
  }
}
