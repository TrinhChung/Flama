import { ArrowLeft, FileDiff, LoaderCircle, RefreshCcw, Send } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import '@/shared/config/i18n'
import { ChangeRequestStatusBadge } from '../components/ChangeRequestStatusBadge'
import { DiffWorkspace } from '../components/DiffWorkspace'
import { useDeckChangeRequest } from '../hooks/useDeckChangeRequest'

export function DeckChangeRequestPage() {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  const {
    deckItemId,
    title,
    setTitle,
    description,
    setDescription,
    filters,
    setFilters,
    pageIndex,
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
    sourcePagesLength,
    draftMutation,
    syncMutation,
    submitMutation,
    onPreviousPage,
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
  if (!summary) {
    return (
      <Page>
        <PageError
          error={new Error(t('request.error_no_diff_data', 'Không có dữ liệu diff đóng góp.'))}
        />
      </Page>
    )
  }

  return (
    <Page size="wide">
      <PageHeader
        title={t('request.title', 'Đóng góp thay đổi')}
        description={t(
          'request.description',
          'Chỉ các chỉnh sửa overlay đã lưu được đưa vào bản nháp. Deck local của bạn vẫn được giữ nếu owner từ chối.',
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

      {activeRequest ? (
        <Alert>
          <FileDiff />
          <AlertTitle className="flex flex-wrap items-center gap-2">
            {t('request.current_request_title', 'Request hiện tại')}
            <ChangeRequestStatusBadge status={activeRequest.status} />
          </AlertTitle>
          <AlertDescription>
            {t('request.current_request_desc', {
              revision: activeRequest.revision,
              count: activeRequest.item_count.toLocaleString(locale),
              defaultValue: `Revision ${activeRequest.revision} · ${activeRequest.item_count.toLocaleString(locale)} thay đổi.`,
            })}{' '}
            <Link className="font-medium" to={`/flashcards/change-requests/${activeRequest.id}`}>
              {t('request.btn_view_detail', 'Mở màn chi tiết')}
            </Link>
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t('request.meta_title', 'Thông tin gửi owner')}</CardTitle>
          <CardDescription>
            {t(
              'request.meta_desc',
              'Tạo hoặc làm mới draft từ trạng thái overlay hiện tại, sau đó sync trước khi gửi.',
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <div className="space-y-2">
            <Label htmlFor="contribution-title">{t('request.field_title_label', 'Tiêu đề')}</Label>
            <Input
              id="contribution-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={t('request.field_title_placeholder', 'Ví dụ: Sửa nghĩa và cách đọc bài 3')}
              disabled={isPendingReview}
              maxLength={255}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="contribution-description">{t('request.field_desc_label', 'Mô tả')}</Label>
            <Textarea
              id="contribution-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={t(
                'request.field_desc_placeholder',
                'Giải thích ngắn lý do và phạm vi thay đổi…',
              )}
              disabled={isPendingReview}
              rows={3}
              maxLength={5000}
            />
          </div>
          <div className="flex flex-wrap gap-2 lg:col-span-2">
            <Button
              type="button"
              variant="outline"
              disabled={isBusy || isPendingReview || !localPreview?.item_count}
              onClick={() => draftMutation.mutate()}
            >
              {draftMutation.isPending ? <LoaderCircle className="animate-spin" /> : <FileDiff />}
              {activeRequest
                ? t('request.btn_refresh_draft', 'Làm mới bản nháp')
                : t('request.btn_create_draft', 'Tạo bản nháp')}
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={isBusy || !activeRequest || isPendingReview}
              onClick={() => syncMutation.mutate()}
            >
              {syncMutation.isPending ? <LoaderCircle className="animate-spin" /> : <RefreshCcw />}
              {t('request.btn_sync', 'Đồng bộ với deck gốc')}
            </Button>
            <Button
              type="button"
              disabled={isBusy || !activeRequest?.can_submit}
              onClick={() => submitMutation.mutate()}
            >
              {submitMutation.isPending ? <LoaderCircle className="animate-spin" /> : <Send />}
              {t('request.btn_submit', 'Gửi đóng góp')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {!hasAnyChanges ? (
        <Alert>
          <AlertTitle>{t('request.no_local_changes_title', 'Chưa có thay đổi local')}</AlertTitle>
          <AlertDescription>
            {t(
              'request.no_local_changes_desc',
              'Hãy sửa và lưu ít nhất một field trong deck clone trước khi tạo đóng góp.',
            )}
          </AlertDescription>
        </Alert>
      ) : (
        <DiffWorkspace
          summary={summary}
          items={allDiffItems}
          filters={filters}
          onFiltersChange={(nextFilters) => {
            setFilters(nextFilters)
          }}
          isFetching={isFetchingDiff}
          isFetchingMore={isFetchingMore}
          hasPrevious={pageIndex > 0}
          onPrevious={onPreviousPage}
          hasMore={pageIndex < sourcePagesLength - 1 || hasNextPage}
          onLoadMore={onLoadMore}
          pageLabel={t('diff.page_label', {
            page: pageIndex + 1,
            defaultValue: `Trang ${pageIndex + 1}`,
          })}
          emptyTitle={t('diff.empty_filter_title', 'Không có thay đổi khớp bộ lọc')}
          emptyDescription={t(
            'diff.empty_filter_desc',
            'Thử chọn loại thay đổi khác hoặc xóa từ khóa tìm kiếm.'
          )}
        />
      )}
    </Page>
  )
}
