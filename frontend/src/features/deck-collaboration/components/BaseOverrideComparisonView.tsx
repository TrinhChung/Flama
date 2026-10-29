import { ArrowLeft, Check, GitCompare, LoaderCircle, RefreshCcw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useBaseOverrideComparison } from '../hooks/useBaseOverrideComparison'

function ComparisonValue({ value, absent, label }: { value: unknown; absent: boolean; label: string }) {
  return <pre className="min-h-16 whitespace-pre-wrap break-words rounded-lg bg-muted/50 p-3 text-sm font-sans">
    {absent ? label : typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
  </pre>
}

export function BaseOverrideComparisonView({ installId }: { installId: string }) {
  const { t } = useTranslation('collaboration')
  const { comparison, page, pageIndex, reset, keep, refresh, next, previous, hasNext } = useBaseOverrideComparison(installId)
  if (comparison.isPending) return <PageLoading label={t('base_comparison.loading', 'Đang tải phần bạn sửa riêng…')} />
  if (comparison.error && !page) return <Page><PageError error={comparison.error} /></Page>
  if (!page) return <Page><PageError error={new Error('Không có dữ liệu so sánh.')} /></Page>
  const absent = t('base_comparison.absent', 'Không có giá trị')
  return <Page size="wide">
    <PageHeader
      title={t('base_comparison.title', 'So sánh phần sửa riêng')}
      description={page.deck_title}
      actions={<Button variant="outline" asChild><Link to="/installed-decks"><ArrowLeft />{t('update.btn_installed_decks', 'Deck đã cài')}</Link></Button>}
    />
    <Alert>
      <GitCompare />
      <AlertTitle>{t('base_comparison.priority_title', 'Phần bạn sửa riêng luôn được giữ')}</AlertTitle>
      <AlertDescription>{t('base_comparison.priority_description', 'Bạn nhận nội dung mới ngay khi tác giả phát hành. Ở field bạn đã sửa, giá trị riêng của bạn được ưu tiên. Bỏ phần sửa riêng để dùng bản tác giả mới nhất.')}</AlertDescription>
    </Alert>
    {comparison.error ? <Alert variant="destructive"><AlertDescription className="flex items-center justify-between gap-3"><span>{comparison.error.message}</span><Button variant="outline" onClick={() => void refresh()}><RefreshCcw />{t('update.retry', 'Thử lại')}</Button></AlertDescription></Alert> : null}
    {page.items.length === 0 ? <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">{t('base_comparison.empty', 'Bạn chưa có phần sửa riêng. Nội dung đang dùng là bản tác giả đã phát hành mới nhất.')}</CardContent></Card> : null}
    {page.items.map((item) => <Card key={item.id}>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <CardTitle className="text-base">{item.field_name || item.field_identity}</CardTitle>
            <div className="flex flex-wrap gap-2">
              {item.base_changed ? <Badge variant="secondary">{t('base_comparison.base_changed', 'Bản gốc đã thay đổi')}</Badge> : null}
              {item.note_deleted || item.field_deleted ? <Badge variant="outline">{item.note_deleted ? t('base_comparison.note_deleted', 'Tác giả đã xoá note') : t('base_comparison.field_deleted', 'Tác giả đã xoá field')}</Badge> : null}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
          {item.base_changed ? <Button variant="outline" size="sm" disabled={reset.isPending || keep.isPending || comparison.isFetching}
            onClick={() => keep.mutate(item)}>
            {keep.isPending && keep.variables?.id === item.id ? <LoaderCircle className="animate-spin" /> : <Check />}
            {t('base_comparison.keep', 'Giữ bản của tôi')}
          </Button> : null}
          <Button variant="outline" size="sm" disabled={reset.isPending || keep.isPending || comparison.isFetching}
            onClick={() => reset.mutate(item.id)}>
            {reset.isPending && reset.variables === item.id ? <LoaderCircle className="animate-spin" /> : <RefreshCcw />}
            {t('base_comparison.reset', 'Bỏ phần sửa riêng')}
          </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2"><h3 className="text-xs font-semibold text-muted-foreground">{t('base_comparison.latest_base', 'Bản tác giả mới nhất')}</h3><ComparisonValue value={item.base_value} absent={!item.base_exists} label={absent} /></div>
        <div className="space-y-2"><h3 className="text-xs font-semibold text-primary">{t('base_comparison.your_value', 'Phần bạn sửa riêng')}</h3><ComparisonValue value={item.personal_value} absent={item.operation === 'remove'} label={t('base_comparison.removed_value', 'Bạn đã xoá giá trị này')} /></div>
      </CardContent>
    </Card>)}
    <nav className="flex flex-wrap items-center justify-between gap-3 border-t pt-3" aria-label={t('base_comparison.pagination', 'Phân trang phần sửa riêng')}>
      <p className="text-xs text-muted-foreground">{t('diff.page_label', { page: pageIndex + 1, defaultValue: `Trang ${pageIndex + 1}` })}</p>
      <div className="flex gap-2">
        <Button variant="outline" disabled={pageIndex === 0 || comparison.isFetching} onClick={previous}>{t('update.btn_prev', 'Trang trước')}</Button>
        <Button variant="outline" disabled={!hasNext || comparison.isFetching} onClick={() => void next()}>{comparison.isFetchingNextPage ? <LoaderCircle className="animate-spin" /> : null}{t('update.btn_next', 'Trang tiếp')}</Button>
      </div>
    </nav>
  </Page>
}
