import { useEffect, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { getIncomingDeckChangeRequests } from '../api'

const PAGE_SIZE = 30

export function formatDate(value?: string | null, locale = 'vi-VN'): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function useChangeRequestInbox() {
  const [searchParams] = useSearchParams()
  const deckItemId = searchParams.get('deck_item_id')?.trim() || null
  const [pageIndex, setPageIndex] = useState(0)

  const query = useInfiniteQuery({
    queryKey: ['incoming-deck-change-requests', deckItemId],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      getIncomingDeckChangeRequests(
        deckItemId,
        { cursor: pageParam, limit: PAGE_SIZE },
        signal,
      ),
    getNextPageParam: (page) => page.page?.next_cursor || undefined,
  })

  const loadedPages = query.data?.pages || []
  const visiblePageIndex = Math.min(pageIndex, Math.max(loadedPages.length - 1, 0))
  const items = loadedPages[visiblePageIndex]?.items || []

  useEffect(() => {
    setPageIndex(0)
  }, [deckItemId])

  const onPreviousPage = () => {
    setPageIndex((current) => Math.max(0, current - 1))
  }

  const onNextPage = () => {
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

  const hasNextPage =
    visiblePageIndex < loadedPages.length - 1 || Boolean(query.hasNextPage)

  return {
    deckItemId,
    query,
    pageIndex: visiblePageIndex,
    loadedPages,
    items,
    hasNextPage,
    onPreviousPage,
    onNextPage,
  }
}
