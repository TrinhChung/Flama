import { useEffect, useMemo, useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Check,
  GitCompare,
  LoaderCircle,
  RefreshCcw,
  ShieldAlert,
} from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import {
  applyPreparedInstalledUpdate,
  getInstalledDeckUpdate,
  getInstalledDeckUpdates,
  prepareInstalledDeckUpdate,
  resolveInstalledUpdateConflict,
} from '../api'
import { DiffWorkspace } from '../components/DiffWorkspace'
import type {
  DiffFilters,
  PreparedInstalledUpdate,
  UpdateConflict,
  UpdateConflictResolution,
} from '../types'

const PAGE_SIZE = 100

function newIdempotencyKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `update-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function valuePreview(value: unknown) {
  if (value === null) return '(null)'
  if (value === undefined) return '(không có dữ liệu)'
  if (value === '') return '(chuỗi rỗng)'
  if (typeof value === 'string') return value
  const serialized = JSON.stringify(value, null, 2)
  return serialized === undefined ? String(value) : serialized
}

function ConflictCard({
  conflict,
  resolution,
  onResolve,
}: {
  conflict: UpdateConflict
  resolution?: UpdateConflictResolution
  onResolve: (resolution: UpdateConflictResolution) => void
}) {
  return (
    <Card className="overflow-hidden border-amber-500/35">
      <CardHeader className="bg-amber-500/8">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-sm">
              {conflict.note_label || 'Note'} / {conflict.field_name || 'Field'}
            </CardTitle>
            <CardDescription>
              Bản local và release mới cùng sửa field này.
            </CardDescription>
          </div>
          <Badge variant="outline" className="border-amber-500/40 text-amber-700 dark:text-amber-300">
            <ShieldAlert />
            Xung đột
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="overflow-hidden rounded-lg border border-blue-500/25 bg-blue-500/6">
            <div className="border-b border-blue-500/20 px-3 py-2 text-xs font-semibold text-blue-700 dark:text-blue-300">
              Bản chỉnh sửa của tôi
            </div>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words p-3 text-xs">
              {valuePreview(conflict.local_value)}
            </pre>
          </div>
          <div className="overflow-hidden rounded-lg border border-emerald-500/25 bg-emerald-500/6">
            <div className="border-b border-emerald-500/20 px-3 py-2 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
              Bản cập nhật từ owner
            </div>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words p-3 text-xs">
              {valuePreview(conflict.upstream_value)}
            </pre>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant={resolution === 'keep_mine' ? 'default' : 'outline'}
            onClick={() => onResolve('keep_mine')}
          >
            {resolution === 'keep_mine' ? <Check /> : null}
            Giữ bản của tôi
          </Button>
          <Button
            type="button"
            variant={resolution === 'keep_upstream' ? 'default' : 'outline'}
            onClick={() => onResolve('keep_upstream')}
          >
            {resolution === 'keep_upstream' ? <Check /> : null}
            Nhận bản cập nhật
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function InstalledDeckUpdatePage() {
  const { installId = '', releaseId = '' } = useParams<{
    installId: string
    releaseId: string
  }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<DiffFilters>({
    query: '',
    changeType: 'all',
  })
  const [pageIndex, setPageIndex] = useState(0)
  const [prepared, setPrepared] = useState<PreparedInstalledUpdate | null>(null)
  const [resolutions, setResolutions] = useState<Record<string, UpdateConflictResolution>>({})
  const prepareIdempotencyKey = useRef(newIdempotencyKey())

  const updatesQuery = useQuery({
    queryKey: ['installed-deck-updates', installId],
    enabled: Boolean(installId),
    queryFn: ({ signal }) => getInstalledDeckUpdates(installId, signal),
  })

  const diffQuery = useInfiniteQuery({
    queryKey: ['installed-deck-update-diff', installId, releaseId, filters],
    enabled: Boolean(installId && releaseId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => getInstalledDeckUpdate(
      installId,
      releaseId,
      {
        cursor: pageParam,
        limit: PAGE_SIZE,
        changeType: filters.changeType,
        query: filters.query,
      },
      signal,
    ),
    getNextPageParam: (page) => page.next_cursor || undefined,
  })

  const firstPage = diffQuery.data?.pages[0]
  const loadedPages = diffQuery.data?.pages || []
  const visiblePageIndex = Math.min(pageIndex, Math.max(loadedPages.length - 1, 0))
  const items = useMemo(
    () => loadedPages[visiblePageIndex]?.items || [],
    [loadedPages, visiblePageIndex],
  )

  useEffect(() => {
    setPageIndex(0)
  }, [filters])

  const prepareMutation = useMutation({
    mutationFn: () => prepareInstalledDeckUpdate(
      installId,
      releaseId,
      {
        expected_applied_release_id: updatesQuery.data?.installation.applied_release?.id || null,
        expected_overlay_revision: updatesQuery.data?.installation.overlay_revision ?? null,
        idempotency_key: prepareIdempotencyKey.current,
      },
    ),
    onSuccess: (result) => {
      setPrepared(result)
      setResolutions({})
      if (result.conflict_count) {
        toast.warning(`Có ${result.conflict_count} field cần bạn chọn cách xử lý.`)
      } else {
        toast.success('Đã kiểm tra xong. Bản cập nhật sẵn sàng để áp dụng.')
      }
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Không thể chuẩn bị bản cập nhật.')
    },
  })

  const applyMutation = useMutation({
    mutationFn: async () => {
      if (!prepared) throw new Error('Hãy kiểm tra xung đột trước khi cập nhật.')

      if (prepared.conflicts.length) {
        await Promise.all(prepared.conflicts.map((conflict) => {
          const resolution = resolutions[conflict.id]
          if (!resolution) {
            throw new Error('Vui lòng xử lý tất cả field xung đột.')
          }
          return resolveInstalledUpdateConflict(
            prepared.rebase_id,
            conflict.id,
            resolution,
          )
        }))
      }

      return applyPreparedInstalledUpdate(prepared.rebase_id)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['installed-deck-updates', installId] })
      await queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
      toast.success(`Đã cập nhật deck lên phiên bản ${firstPage?.target_release.version_label || ''}.`)
      navigate('/installed-decks')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Không thể áp dụng bản cập nhật.')
    },
  })

  if (!installId || !releaseId) {
    return <Page><PageError error={new Error('Thiếu mã bản cài hoặc release.')} /></Page>
  }
  if (updatesQuery.isPending || diffQuery.isPending) {
    return <PageLoading label="Đang tải nội dung bản cập nhật…" />
  }
  if (updatesQuery.error || diffQuery.error || !firstPage) {
    return (
      <Page>
        <PageError
          error={updatesQuery.error || diffQuery.error || new Error('Không có dữ liệu cập nhật.')}
        />
      </Page>
    )
  }

  const preparedConflicts = prepared?.conflicts || []
  const allConflictsResolved = Boolean(prepared) && preparedConflicts.every(
    (conflict) => Boolean(resolutions[conflict.id]),
  )
  const canApply = Boolean(prepared) && (
    preparedConflicts.length === 0 || allConflictsResolved
  )

  return (
    <Page className="max-w-[96rem]">
      <PageHeader
        title="Xem bản cập nhật deck"
        description="So sánh release đang học với release mới. Lịch sử học được giữ theo Note/Card gốc."
        actions={
          <Button variant="outline" asChild>
            <Link to="/installed-decks">
              <ArrowLeft />
              Deck đã cài
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">
                <GitCompare />
                {firstPage.from_release?.version_label || 'Bản gốc'}
                <span aria-hidden="true">→</span>
                {firstPage.target_release.version_label}
              </Badge>
              {updatesQuery.data.unread_update ? (
                <Badge>Bản cập nhật mới</Badge>
              ) : null}
            </div>
            <CardTitle>Ghi chú phát hành</CardTitle>
            <CardDescription className="whitespace-pre-wrap">
              {firstPage.changelog || 'Owner không thêm ghi chú cho phiên bản này.'}
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="h-fit lg:sticky lg:top-4">
          <CardHeader>
            <CardTitle className="text-base">Cập nhật có kiểm soát</CardTitle>
            <CardDescription>
              Hệ thống kiểm tra overlap với các field bạn đã sửa trước khi áp dụng.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!updatesQuery.data.update_available || firstPage.already_applied ? (
              <Alert>
                <Check />
                <AlertTitle>Deck đã ở phiên bản này</AlertTitle>
                <AlertDescription>Không còn nội dung mới cần áp dụng.</AlertDescription>
              </Alert>
            ) : null}

            {!prepared ? (
              <Button
                className="w-full"
                size="lg"
                disabled={prepareMutation.isPending || !updatesQuery.data.update_available}
                onClick={() => prepareMutation.mutate()}
              >
                {prepareMutation.isPending
                  ? <LoaderCircle className="animate-spin" />
                  : <RefreshCcw />}
                Kiểm tra xung đột
              </Button>
            ) : (
              <Button
                className="w-full"
                size="lg"
                disabled={!canApply || applyMutation.isPending}
                onClick={() => applyMutation.mutate()}
              >
                {applyMutation.isPending
                  ? <LoaderCircle className="animate-spin" />
                  : <Check />}
                Áp dụng phiên bản {firstPage.target_release.version_label}
              </Button>
            )}

            {prepared?.conflicts.length ? (
              <p className={cn(
                'text-xs leading-relaxed',
                allConflictsResolved ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300',
              )}>
                {Object.keys(resolutions).length}/{prepared.conflicts.length} xung đột đã chọn cách xử lý.
              </p>
            ) : null}
            <p className="text-xs leading-relaxed text-muted-foreground">
              Apply chỉ rebase overlay và nâng release pointer; không tạo lại tiến độ học.
            </p>
          </CardContent>
        </Card>
      </div>

      {prepared?.conflicts.length ? (
        <section className="space-y-3" aria-labelledby="update-conflicts-title">
          <div>
            <h2 id="update-conflicts-title" className="text-lg font-semibold">
              Xử lý xung đột
            </h2>
            <p className="text-sm text-muted-foreground">
              Quyết định riêng cho từng field; chọn “Giữ bản của tôi” sẽ tiếp tục lưu field đó trong overlay local.
            </p>
          </div>
          {prepared.conflicts.map((conflict) => (
            <ConflictCard
              key={conflict.id}
              conflict={conflict}
              resolution={resolutions[conflict.id]}
              onResolve={(resolution) => setResolutions((current) => ({
                ...current,
                [conflict.id]: resolution,
              }))}
            />
          ))}
        </section>
      ) : null}

      <DiffWorkspace
        summary={firstPage.summary}
        items={items}
        filters={filters}
        onFiltersChange={(nextFilters) => {
          setFilters(nextFilters)
          setPageIndex(0)
          setPrepared(null)
          setResolutions({})
        }}
        isFetching={diffQuery.isFetching}
        isFetchingMore={diffQuery.isFetchingNextPage}
        hasPrevious={visiblePageIndex > 0}
        onPrevious={() => setPageIndex((current) => Math.max(0, current - 1))}
        hasMore={visiblePageIndex < loadedPages.length - 1 || diffQuery.hasNextPage}
        onLoadMore={() => {
          if (visiblePageIndex < loadedPages.length - 1) {
            setPageIndex((current) => current + 1)
            return
          }
          void diffQuery.fetchNextPage().then((result) => {
            if (result.data.pages.length > loadedPages.length) {
              setPageIndex((current) => current + 1)
            }
          })
        }}
        pageLabel={`Trang ${visiblePageIndex + 1}`}
        emptyTitle="Không có thay đổi trong bộ lọc"
        emptyDescription="Thử chọn loại thay đổi khác hoặc xóa từ khóa tìm kiếm."
      />
    </Page>
  )
}
