import { ArrowLeft, ChevronRight, FileDiff, Inbox, LoaderCircle, UserRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'
import '@/shared/config/i18n'
import { ChangeRequestStatusBadge } from '../components/ChangeRequestStatusBadge'
import { formatDate, useChangeRequestInbox } from '../hooks/useChangeRequestInbox'

export function ChangeRequestInboxPage() {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'
  const {
    deckItemId,
    query,
    pageIndex,
    loadedPages,
    items,
    hasNextPage,
    onPreviousPage,
    onNextPage,
  } = useChangeRequestInbox()

  if (query.isPending) {
    return <PageLoading label={t('inbox.loading', 'Đang tải đóng góp chờ duyệt…')} />
  }
  if (query.error) {
    return (
      <Page size="wide">
        <PageError error={query.error} />
      </Page>
    )
  }

  const description = deckItemId
    ? t('inbox.description_scoped', 'Các change request đang chờ duyệt cho shared deck đã chọn.')
    : t(
        'inbox.description_all',
        'Kiểm tra diff, merge vào working deck hoặc từ chối mà không xóa bản local của người đóng góp.',
      )

  return (
    <Page>
      <PageHeader
        title={t('inbox.title', 'Đóng góp cần duyệt')}
        description={description}
        actions={
          <Button variant="outline" asChild>
            <Link to={deckItemId ? `/marketplace/decks/${deckItemId}` : '/dashboard'}>
              <ArrowLeft />
              {t('inbox.btn_back', 'Quay lại')}
            </Link>
          </Button>
        }
      />

      {!items.length ? (
        <EmptyState
          title={t('inbox.empty_title', 'Không có đóng góp chờ duyệt')}
          description={t(
            'inbox.empty_desc',
            'Change request mới sẽ xuất hiện ở đây sau khi người dùng sync và gửi review.',
          )}
          action={
            <Button variant="outline" asChild>
              <Link to="/marketplace/decks">{t('inbox.btn_open_marketplace', 'Mở Marketplace')}</Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {items.map((req) => {
            const formattedDate = formatDate(req.submitted_at, locale)
            const dateText = formattedDate
              ? t('inbox.submitted_date', {
                  date: formattedDate,
                  defaultValue: `gửi ${formattedDate}`,
                })
              : t('inbox.unknown_time', 'Chưa rõ thời gian')

            return (
              <Card key={req.id} className="transition-colors hover:border-primary/40">
                <CardHeader className="pb-3">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <CardTitle className="truncate text-base">{req.title}</CardTitle>
                        <ChangeRequestStatusBadge status={req.status} />
                      </div>
                      <CardDescription>
                        {req.deck_item?.title || 'Shared deck'} · {dateText}
                      </CardDescription>
                    </div>
                    <Button asChild>
                      <Link to={`/flashcards/change-requests/${req.id}`}>
                        {t('inbox.btn_view_diff', 'Xem diff')}
                        <ChevronRight />
                      </Link>
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <Badge variant="secondary">
                    <UserRound />
                    {req.requester.username}
                  </Badge>
                  <Badge variant="outline">
                    <FileDiff />
                    {t('inbox.card_items', {
                      count: req.item_count.toLocaleString(locale),
                      defaultValue: `${req.item_count.toLocaleString(locale)} thay đổi`,
                    })}
                  </Badge>
                  {req.unresolved_conflict_count ? (
                    <Badge variant="destructive">
                      {t('inbox.card_conflicts', {
                        count: req.unresolved_conflict_count,
                        defaultValue: `${req.unresolved_conflict_count} xung đột`,
                      })}
                    </Badge>
                  ) : null}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {pageIndex > 0 || pageIndex < loadedPages.length - 1 || hasNextPage ? (
        <nav
          className="flex items-center justify-center gap-2"
          aria-label={t('inbox.pagination_aria_label', 'Phân trang đóng góp')}
        >
          <Button
            type="button"
            variant="outline"
            disabled={pageIndex === 0 || query.isFetchingNextPage}
            onClick={onPreviousPage}
          >
            {t('inbox.btn_prev', 'Trang trước')}
          </Button>
          <span className="px-2 text-xs text-muted-foreground">
            {t('inbox.page_indicator', {
              page: pageIndex + 1,
              defaultValue: `Trang ${pageIndex + 1}`,
            })}
          </span>
          <Button
            type="button"
            variant="outline"
            disabled={query.isFetchingNextPage || (!hasNextPage && pageIndex >= loadedPages.length - 1)}
            onClick={onNextPage}
          >
            {query.isFetchingNextPage ? <LoaderCircle className="animate-spin" /> : null}
            {t('inbox.btn_next', 'Trang tiếp')}
          </Button>
        </nav>
      ) : null}

      <div className="sr-only" aria-live="polite">
        <Inbox />
        {t('inbox.sr_inbox_count', {
          count: items.length,
          page: pageIndex + 1,
          defaultValue: `${items.length} đóng góp chờ duyệt trên trang ${pageIndex + 1}`,
        })}
      </div>
    </Page>
  )
}
