import { useEffect, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { ArrowLeft, ChevronRight, FileDiff, Inbox, LoaderCircle, UserRound } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'
import { getIncomingDeckChangeRequests } from '../api'
import { ChangeRequestStatusBadge } from '../components/ChangeRequestStatusBadge'

const PAGE_SIZE = 30

function formatDate(value?: string | null) {
  if (!value) return 'Chưa rõ thời gian'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Chưa rõ thời gian'
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function ChangeRequestInboxPage() {
  const [searchParams] = useSearchParams()
  const deckItemId = searchParams.get('deck_item_id')?.trim() || null
  const [pageIndex, setPageIndex] = useState(0)
  const query = useInfiniteQuery({
    queryKey: ['incoming-deck-change-requests', deckItemId],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => getIncomingDeckChangeRequests(
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

  if (query.isPending) return <PageLoading label="Đang tải đóng góp chờ duyệt…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page>
      <PageHeader
        title="Đóng góp cần duyệt"
        description={deckItemId
          ? 'Các change request đang chờ duyệt cho shared deck đã chọn.'
          : 'Kiểm tra diff, merge vào working deck hoặc từ chối mà không xóa bản local của người đóng góp.'}
        actions={
          <Button variant="outline" asChild>
            <Link to={deckItemId ? `/marketplace/decks/${deckItemId}` : '/dashboard'}>
              <ArrowLeft />
              Quay lại
            </Link>
          </Button>
        }
      />

      {!items.length ? (
        <EmptyState
          title="Không có đóng góp chờ duyệt"
          description="Change request mới sẽ xuất hiện ở đây sau khi người dùng sync và gửi review."
          action={
            <Button variant="outline" asChild>
              <Link to="/marketplace/decks">Mở Marketplace</Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {items.map((request) => (
            <Card key={request.id} className="transition-colors hover:border-primary/40">
              <CardHeader className="pb-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <CardTitle className="truncate text-base">{request.title}</CardTitle>
                      <ChangeRequestStatusBadge status={request.status} />
                    </div>
                    <CardDescription>
                      {request.deck_item?.title || 'Shared deck'} · gửi {formatDate(request.submitted_at)}
                    </CardDescription>
                  </div>
                  <Button asChild>
                    <Link to={`/flashcards/change-requests/${request.id}`}>
                      Xem diff
                      <ChevronRight />
                    </Link>
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                <Badge variant="secondary">
                  <UserRound />
                  {request.requester.username}
                </Badge>
                <Badge variant="outline">
                  <FileDiff />
                  {request.item_count.toLocaleString('vi-VN')} thay đổi
                </Badge>
                {request.unresolved_conflict_count ? (
                  <Badge variant="destructive">
                    {request.unresolved_conflict_count} xung đột
                  </Badge>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {visiblePageIndex > 0
        || visiblePageIndex < loadedPages.length - 1
        || query.hasNextPage ? (
        <nav className="flex items-center justify-center gap-2" aria-label="Phân trang đóng góp">
          <Button
            type="button"
            variant="outline"
            disabled={visiblePageIndex === 0 || query.isFetchingNextPage}
            onClick={() => setPageIndex((current) => Math.max(0, current - 1))}
          >
            Trang trước
          </Button>
          <span className="px-2 text-xs text-muted-foreground">
            Trang {visiblePageIndex + 1}
          </span>
          <Button
            type="button"
            variant="outline"
            disabled={query.isFetchingNextPage || (
              visiblePageIndex >= loadedPages.length - 1 && !query.hasNextPage
            )}
            onClick={() => {
              if (visiblePageIndex < loadedPages.length - 1) {
                setPageIndex((current) => current + 1)
                return
              }
              void query.fetchNextPage().then((result) => {
                if ((result.data?.pages.length || 0) > loadedPages.length) {
                  setPageIndex((current) => current + 1)
                }
              })
            }}
          >
            {query.isFetchingNextPage ? <LoaderCircle className="animate-spin" /> : null}
            Trang tiếp
          </Button>
        </nav>
      ) : null}

      <div className="sr-only" aria-live="polite">
        <Inbox />
        {items.length} đóng góp chờ duyệt trên trang {visiblePageIndex + 1}
      </div>
    </Page>
  )
}
