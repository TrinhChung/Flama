import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, FileDiff, LoaderCircle, RefreshCcw, Send } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import {
  buildDeckChangeRequestDraft,
  contributionItemToDiffItem,
  filterDiffItems,
  getActiveDeckChangeRequest,
  getLocalDeckChanges,
  submitDeckChangeRequest,
  summarizeDiffItems,
  syncDeckChangeRequest,
} from '../api'
import { ChangeRequestStatusBadge } from '../components/ChangeRequestStatusBadge'
import { DiffWorkspace } from '../components/DiffWorkspace'
import type { DeckChangeRequest, DiffFilters } from '../types'

const PAGE_SIZE = 100

export function DeckChangeRequestPage() {
  const { deckItemId = '' } = useParams<{ deckItemId: string }>()
  const queryClient = useQueryClient()
  const formInitialized = useRef(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [filters, setFilters] = useState<DiffFilters>({ query: '', changeType: 'all' })
  const [pageIndex, setPageIndex] = useState(0)

  const localQuery = useQuery({
    queryKey: ['local-deck-changes', deckItemId],
    enabled: Boolean(deckItemId),
    queryFn: ({ signal }) => getLocalDeckChanges(deckItemId, signal),
  })
  const activeQuery = useQuery({
    queryKey: ['active-deck-change-request', deckItemId],
    enabled: Boolean(deckItemId),
    queryFn: ({ signal }) => getActiveDeckChangeRequest(deckItemId, signal),
  })
  const activeRequest = activeQuery.data?.request || null

  useEffect(() => {
    if (!activeRequest || formInitialized.current) return
    setTitle(activeRequest.title || '')
    setDescription(activeRequest.description || '')
    formInitialized.current = true
  }, [activeRequest])

  const allDiffItems = useMemo(() => {
    const items = activeRequest?.items || localQuery.data?.items || []
    return items.map((item, index) => contributionItemToDiffItem(item, index))
  }, [activeRequest?.items, localQuery.data?.items])
  const summary = useMemo(() => summarizeDiffItems(allDiffItems), [allDiffItems])
  const filteredItems = useMemo(
    () => filterDiffItems(allDiffItems, filters),
    [allDiffItems, filters],
  )
  const pageCount = Math.max(1, Math.ceil(filteredItems.length / PAGE_SIZE))
  const visiblePageIndex = Math.min(pageIndex, pageCount - 1)
  const visibleItems = filteredItems.slice(
    visiblePageIndex * PAGE_SIZE,
    (visiblePageIndex + 1) * PAGE_SIZE,
  )

  useEffect(() => {
    setPageIndex(0)
  }, [filters, allDiffItems.length])

  function storeRequest(request: DeckChangeRequest) {
    queryClient.setQueryData(
      ['active-deck-change-request', deckItemId],
      { request },
    )
  }

  const draftMutation = useMutation({
    mutationFn: () => buildDeckChangeRequestDraft(deckItemId, {
      title: title.trim(),
      description: description.trim(),
    }),
    onSuccess: (request) => {
      storeRequest(request)
      toast.success('Đã tạo bản nháp từ các thay đổi local đã lưu.')
    },
    onError: (error) => toast.error(
      error instanceof Error ? error.message : 'Không thể tạo bản nháp đóng góp.',
    ),
  })

  const syncMutation = useMutation({
    mutationFn: () => syncDeckChangeRequest(deckItemId, activeRequest?.id || ''),
    onSuccess: (request) => {
      storeRequest(request)
      if (request.unresolved_conflict_count) {
        toast.warning(`Có ${request.unresolved_conflict_count} xung đột cần xử lý.`)
      } else {
        toast.success('Bản nháp đã đồng bộ với deck gốc.')
      }
    },
    onError: (error) => toast.error(
      error instanceof Error ? error.message : 'Không thể đồng bộ với deck gốc.',
    ),
  })

  const submitMutation = useMutation({
    mutationFn: () => submitDeckChangeRequest(deckItemId, activeRequest?.id || ''),
    onSuccess: (request) => {
      storeRequest(request)
      toast.success('Đã gửi đóng góp tới chủ sở hữu deck.')
    },
    onError: (error) => toast.error(
      error instanceof Error ? error.message : 'Không thể gửi đóng góp.',
    ),
  })

  if (!deckItemId) {
    return <Page><PageError error={new Error('Thiếu mã shared deck.')} /></Page>
  }
  if (localQuery.isPending || activeQuery.isPending) {
    return <PageLoading label="Đang tải các thay đổi local…" />
  }
  if (localQuery.error || activeQuery.error) {
    return <Page><PageError error={localQuery.error || activeQuery.error} /></Page>
  }

  const isPendingReview = activeRequest?.status === 'pending_review'
  const isBusy = draftMutation.isPending || syncMutation.isPending || submitMutation.isPending

  return (
    <Page className="max-w-[96rem]">
      <PageHeader
        title="Đóng góp thay đổi"
        description="Chỉ các chỉnh sửa overlay đã lưu được đưa vào bản nháp. Deck local của bạn vẫn được giữ nếu owner từ chối."
        actions={
          <Button variant="outline" asChild>
            <Link to={`/marketplace/decks/${deckItemId}`}>
              <ArrowLeft />
              Quay lại deck
            </Link>
          </Button>
        }
      />

      {activeRequest ? (
        <Alert>
          <FileDiff />
          <AlertTitle className="flex flex-wrap items-center gap-2">
            Request hiện tại
            <ChangeRequestStatusBadge status={activeRequest.status} />
          </AlertTitle>
          <AlertDescription>
            Revision {activeRequest.revision} · {activeRequest.item_count.toLocaleString('vi-VN')} thay đổi.
            {' '}
            <Link className="font-medium" to={`/flashcards/change-requests/${activeRequest.id}`}>
              Mở màn chi tiết
            </Link>
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Thông tin gửi owner</CardTitle>
          <CardDescription>
            Tạo hoặc làm mới draft từ trạng thái overlay hiện tại, sau đó sync trước khi gửi.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <div className="space-y-2">
            <Label htmlFor="contribution-title">Tiêu đề</Label>
            <Input
              id="contribution-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Ví dụ: Sửa nghĩa và cách đọc bài 3"
              disabled={isPendingReview}
              maxLength={255}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="contribution-description">Mô tả</Label>
            <Textarea
              id="contribution-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Giải thích ngắn lý do và phạm vi thay đổi…"
              disabled={isPendingReview}
              rows={3}
              maxLength={5000}
            />
          </div>
          <div className="flex flex-wrap gap-2 lg:col-span-2">
            <Button
              type="button"
              variant="outline"
              disabled={isBusy || isPendingReview || !localQuery.data?.item_count}
              onClick={() => draftMutation.mutate()}
            >
              {draftMutation.isPending ? <LoaderCircle className="animate-spin" /> : <FileDiff />}
              {activeRequest ? 'Làm mới bản nháp' : 'Tạo bản nháp'}
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={isBusy || !activeRequest || isPendingReview}
              onClick={() => syncMutation.mutate()}
            >
              {syncMutation.isPending ? <LoaderCircle className="animate-spin" /> : <RefreshCcw />}
              Đồng bộ với deck gốc
            </Button>
            <Button
              type="button"
              disabled={isBusy || !activeRequest?.can_submit}
              onClick={() => submitMutation.mutate()}
            >
              {submitMutation.isPending ? <LoaderCircle className="animate-spin" /> : <Send />}
              Gửi đóng góp
            </Button>
          </div>
        </CardContent>
      </Card>

      {!allDiffItems.length ? (
        <Alert>
          <AlertTitle>Chưa có thay đổi local</AlertTitle>
          <AlertDescription>
            Hãy sửa và lưu ít nhất một field trong deck clone trước khi tạo đóng góp.
          </AlertDescription>
        </Alert>
      ) : (
        <DiffWorkspace
          summary={summary}
          items={visibleItems}
          filters={filters}
          onFiltersChange={setFilters}
          hasPrevious={visiblePageIndex > 0}
          onPrevious={() => setPageIndex((current) => Math.max(0, current - 1))}
          hasMore={visiblePageIndex < pageCount - 1}
          onLoadMore={() => setPageIndex((current) => Math.min(pageCount - 1, current + 1))}
          pageLabel={`Trang ${visiblePageIndex + 1}/${pageCount}`}
          emptyTitle="Không có thay đổi khớp bộ lọc"
          emptyDescription="Thử chọn loại thay đổi khác hoặc xóa từ khóa tìm kiếm."
        />
      )}
    </Page>
  )
}
