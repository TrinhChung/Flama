import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Check,
  GitMerge,
  LoaderCircle,
  RefreshCcw,
  Send,
  ShieldAlert,
  X,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useBootstrap } from '@/shared/api/bootstrap'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import {
  approveDeckChangeRequest,
  contributionItemToDiffItem,
  filterDiffItems,
  getDeckChangeRequest,
  rejectDeckChangeRequest,
  resolveDeckChangeRequestConflict,
  submitDeckChangeRequest,
  summarizeDiffItems,
  syncDeckChangeRequest,
} from '../api'
import { ChangeRequestStatusBadge } from '../components/ChangeRequestStatusBadge'
import { DiffWorkspace } from '../components/DiffWorkspace'
import type {
  ChangeRequestConflict,
  ConflictResolutionInput,
  DeckChangeRequest,
  DiffFilters,
} from '../types'

const PAGE_SIZE = 100

function formatValue(value: unknown) {
  if (value === undefined) return '(không có dữ liệu)'
  if (value === null) return '(null)'
  if (value === '') return '(chuỗi rỗng)'
  if (typeof value === 'string') return value
  const serialized = JSON.stringify(value, null, 2)
  return serialized === undefined ? String(value) : serialized
}

function parseManualValue(value: string) {
  const trimmed = value.trim()
  if (!trimmed) return ''
  try {
    return JSON.parse(trimmed) as unknown
  } catch {
    return value
  }
}

function ConflictValue({ label, value, tone }: {
  label: string
  value: unknown
  tone: 'base' | 'mine' | 'upstream'
}) {
  const toneClass = {
    base: 'border-border bg-muted/30',
    mine: 'border-blue-500/25 bg-blue-500/6',
    upstream: 'border-emerald-500/25 bg-emerald-500/6',
  }[tone]
  return (
    <div className={`overflow-hidden rounded-lg border ${toneClass}`}>
      <div className="border-b px-3 py-2 text-xs font-semibold">{label}</div>
      <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words p-3 text-xs">
        {formatValue(value)}
      </pre>
    </div>
  )
}

function ContributionConflictCard({
  conflict,
  manualValue,
  disabled,
  onManualValueChange,
  onResolve,
}: {
  conflict: ChangeRequestConflict
  manualValue: string
  disabled: boolean
  onManualValueChange: (value: string) => void
  onResolve: (input: ConflictResolutionInput) => void
}) {
  return (
    <Card className="overflow-hidden border-amber-500/35">
      <CardHeader className="bg-amber-500/8">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-sm">
              {conflict.conflict_type.replaceAll('_', ' ')} · {conflict.source_ref_id || 'field'}
            </CardTitle>
            <CardDescription>Upstream và bản local cùng thay đổi dữ liệu này.</CardDescription>
          </div>
          <Badge variant="outline" className="border-amber-500/40 text-amber-700 dark:text-amber-300">
            <ShieldAlert />
            Cần quyết định
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
        <div className="grid gap-3 xl:grid-cols-3">
          <ConflictValue label="Base" value={conflict.base_value} tone="base" />
          <ConflictValue label="Bản của tôi" value={conflict.local_value} tone="mine" />
          <ConflictValue label="Deck gốc hiện tại" value={conflict.upstream_value} tone="upstream" />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            onClick={() => onResolve({ resolution_mode: 'keep_mine' })}
          >
            Giữ bản của tôi
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            onClick={() => onResolve({ resolution_mode: 'keep_upstream' })}
          >
            Nhận bản upstream
          </Button>
        </div>
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <div className="space-y-2">
            <Label htmlFor={`manual-${conflict.id}`}>Giá trị thủ công</Label>
            <Textarea
              id={`manual-${conflict.id}`}
              value={manualValue}
              onChange={(event) => onManualValueChange(event.target.value)}
              placeholder="Nhập text hoặc JSON hợp lệ…"
              rows={2}
              disabled={disabled}
            />
          </div>
          <Button
            type="button"
            variant="secondary"
            disabled={disabled}
            onClick={() => onResolve({
              resolution_mode: 'manual',
              resolved_value: parseManualValue(manualValue),
            })}
          >
            Dùng giá trị này
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function ChangeRequestDetailPage() {
  const { requestId = '' } = useParams<{ requestId: string }>()
  const queryClient = useQueryClient()
  const bootstrapQuery = useBootstrap()
  const [filters, setFilters] = useState<DiffFilters>({ query: '', changeType: 'all' })
  const [pageIndex, setPageIndex] = useState(0)
  const [reviewComment, setReviewComment] = useState('')
  const [manualValues, setManualValues] = useState<Record<string, string>>({})

  const query = useQuery({
    queryKey: ['deck-change-request', requestId],
    enabled: Boolean(requestId),
    queryFn: ({ signal }) => getDeckChangeRequest(requestId, signal),
  })
  const request = query.data
  const allDiffItems = useMemo(
    () => request?.items.map((item, index) => contributionItemToDiffItem(item, index)) || [],
    [request?.items],
  )
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

  function storeRequest(nextRequest: DeckChangeRequest) {
    queryClient.setQueryData(['deck-change-request', requestId], nextRequest)
    queryClient.setQueryData(
      ['active-deck-change-request', nextRequest.deck_item_id],
      {
        request: nextRequest.status === 'merged' || nextRequest.status === 'rejected'
          ? null
          : nextRequest,
      },
    )
    void queryClient.invalidateQueries({ queryKey: ['incoming-deck-change-requests'] })
    if (nextRequest.status === 'merged') {
      void queryClient.invalidateQueries({
        queryKey: ['deck-release-preview', nextRequest.deck_item_id],
      })
    }
  }

  const syncMutation = useMutation({
    mutationFn: () => syncDeckChangeRequest(request?.deck_item_id || '', requestId),
    onSuccess: (nextRequest) => {
      storeRequest(nextRequest)
      toast.success(nextRequest.unresolved_conflict_count
        ? 'Đã đồng bộ; vẫn còn xung đột cần xử lý.'
        : 'Đã đồng bộ với deck gốc.')
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : 'Không thể đồng bộ.'),
  })

  const resolveMutation = useMutation({
    mutationFn: ({ conflictId, input }: {
      conflictId: string
      input: ConflictResolutionInput
    }) => resolveDeckChangeRequestConflict(
      request?.deck_item_id || '',
      requestId,
      conflictId,
      input,
    ),
    onSuccess: (nextRequest) => {
      storeRequest(nextRequest)
      toast.success('Đã lưu cách xử lý xung đột.')
    },
    onError: (error) => toast.error(
      error instanceof Error ? error.message : 'Không thể xử lý xung đột.',
    ),
  })

  const submitMutation = useMutation({
    mutationFn: () => submitDeckChangeRequest(request?.deck_item_id || '', requestId),
    onSuccess: (nextRequest) => {
      storeRequest(nextRequest)
      toast.success('Đã gửi request tới owner.')
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : 'Không thể gửi request.'),
  })

  const approveMutation = useMutation({
    mutationFn: () => approveDeckChangeRequest(requestId, reviewComment.trim()),
    onSuccess: (nextRequest) => {
      storeRequest(nextRequest)
      toast.success('Đã merge đóng góp vào working deck. Thay đổi chưa được publish.')
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : 'Không thể merge request.'),
  })

  const rejectMutation = useMutation({
    mutationFn: () => rejectDeckChangeRequest(requestId, reviewComment.trim()),
    onSuccess: (nextRequest) => {
      storeRequest(nextRequest)
      toast.success('Đã từ chối request; bản local của người đóng góp vẫn được giữ.')
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : 'Không thể từ chối request.'),
  })

  if (!requestId) return <Page><PageError error={new Error('Thiếu mã change request.')} /></Page>
  if (query.isPending) return <PageLoading label="Đang tải change request…" />
  if (query.error || !request) {
    return <Page><PageError error={query.error || new Error('Không tìm thấy change request.')} /></Page>
  }

  const unresolvedConflicts = request.conflicts.filter((conflict) => !conflict.resolved_at)
  const viewerId = bootstrapQuery.data?.user?.id
  const isOwner = viewerId === request.owner.id
  const isRequester = viewerId === request.requester.id
  const isBusy = syncMutation.isPending
    || resolveMutation.isPending
    || submitMutation.isPending
    || approveMutation.isPending
    || rejectMutation.isPending

  return (
    <Page className="max-w-[96rem]">
      <PageHeader
        title={request.title}
        description={`${request.deck_item?.title || 'Shared deck'} · ${request.requester.username} → ${request.owner.username}`}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to={`/marketplace/decks/${request.deck_item_id}`}>
                <ArrowLeft />
                Shared deck
              </Link>
            </Button>
            {isOwner ? (
              <Button variant="outline" asChild>
                <Link to="/flashcards/change-requests/incoming">Đóng góp cần duyệt</Link>
              </Button>
            ) : isRequester ? (
              <Button variant="outline" asChild>
                <Link to={`/flashcards/shared-decks/${request.deck_item_id}/change-request`}>
                  Bản đóng góp của tôi
                </Link>
              </Button>
            ) : null}
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <ChangeRequestStatusBadge status={request.status} />
              <Badge variant="outline">Revision {request.revision}</Badge>
              <Badge variant="secondary">{request.item_count.toLocaleString('vi-VN')} thay đổi</Badge>
            </div>
            <CardTitle className="text-base">Mô tả đóng góp</CardTitle>
            <CardDescription className="whitespace-pre-wrap">
              {request.description || 'Người đóng góp không thêm mô tả.'}
            </CardDescription>
          </CardHeader>
          {request.review_comment ? (
            <CardContent>
              <Alert>
                <AlertTitle>Phản hồi từ owner</AlertTitle>
                <AlertDescription className="whitespace-pre-wrap">{request.review_comment}</AlertDescription>
              </Alert>
            </CardContent>
          ) : null}
        </Card>

        <Card className="h-fit lg:sticky lg:top-4">
          <CardHeader>
            <CardTitle className="text-base">Hành động</CardTitle>
            <CardDescription>Action khả dụng phụ thuộc vai trò và trạng thái request.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {request.can_review ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="review-comment">Phản hồi cho người đóng góp</Label>
                  <Textarea
                    id="review-comment"
                    value={reviewComment}
                    onChange={(event) => setReviewComment(event.target.value)}
                    placeholder="Lý do merge hoặc từ chối…"
                    rows={3}
                    maxLength={5000}
                  />
                </div>
                <Button
                  className="w-full"
                  disabled={isBusy}
                  onClick={() => approveMutation.mutate()}
                >
                  {approveMutation.isPending ? <LoaderCircle className="animate-spin" /> : <GitMerge />}
                  Merge vào working deck
                </Button>
                <Button
                  className="w-full"
                  variant="destructive"
                  disabled={isBusy || !reviewComment.trim()}
                  onClick={() => rejectMutation.mutate()}
                >
                  {rejectMutation.isPending ? <LoaderCircle className="animate-spin" /> : <X />}
                  Từ chối request
                </Button>
              </>
            ) : null}

            {request.status === 'needs_sync' || request.status === 'draft' || request.status === 'has_conflict' ? (
              <Button
                className="w-full"
                variant="outline"
                disabled={isBusy || request.can_review}
                onClick={() => syncMutation.mutate()}
              >
                {syncMutation.isPending ? <LoaderCircle className="animate-spin" /> : <RefreshCcw />}
                Đồng bộ lại
              </Button>
            ) : null}
            {request.can_submit ? (
              <Button
                className="w-full"
                disabled={isBusy}
                onClick={() => submitMutation.mutate()}
              >
                {submitMutation.isPending ? <LoaderCircle className="animate-spin" /> : <Send />}
                Gửi owner duyệt
              </Button>
            ) : null}
            {request.status === 'merged' && isOwner ? (
              <Button className="w-full" asChild>
                <Link to={`/creator/decks/${request.deck_item_id}/releases/new`}>
                  <Check />
                  Tạo release mới
                </Link>
              </Button>
            ) : null}
            {request.status === 'pending_review' && isRequester ? (
              <p className="text-xs leading-relaxed text-muted-foreground">
                Đóng góp đang chờ chủ sở hữu duyệt. Deck local của bạn vẫn có thể tiếp tục được chỉnh sửa.
              </p>
            ) : null}
            {request.status === 'merged' && !isOwner ? (
              <p className="text-xs leading-relaxed text-muted-foreground">
                Đóng góp đã được merge vào working deck. Người dùng khác chỉ nhận thay đổi sau khi chủ sở hữu phát hành release mới.
              </p>
            ) : null}
            {request.status === 'rejected' ? (
              <p className="text-xs leading-relaxed text-muted-foreground">
                Request bị từ chối nhưng overlay local của người sửa không bị xóa.
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>

      {request.can_resolve && unresolvedConflicts.length ? (
        <section className="space-y-3" aria-labelledby="contribution-conflicts-title">
          <div>
            <h2 id="contribution-conflicts-title" className="text-lg font-semibold">Xử lý xung đột</h2>
            <p className="text-sm text-muted-foreground">
              So sánh base, upstream và bản local rồi chọn kết quả cho từng field.
            </p>
          </div>
          {unresolvedConflicts.map((conflict) => (
            <ContributionConflictCard
              key={conflict.id}
              conflict={conflict}
              manualValue={manualValues[conflict.id] || ''}
              disabled={resolveMutation.isPending}
              onManualValueChange={(value) => setManualValues((current) => ({
                ...current,
                [conflict.id]: value,
              }))}
              onResolve={(input) => resolveMutation.mutate({
                conflictId: conflict.id,
                input,
              })}
            />
          ))}
        </section>
      ) : null}

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
    </Page>
  )
}
