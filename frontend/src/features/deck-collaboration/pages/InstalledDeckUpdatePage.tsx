import { useEffect, useRef, useState } from 'react'
import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
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
  getInstalledUpdateConflicts,
  getInstalledDeckUpdates,
  markInstalledDeckUpdateSeen,
  prepareInstalledDeckUpdate,
  resolveInstalledUpdateConflict,
} from '../api'
import { DiffWorkspace } from '../components/DiffWorkspace'
import type {
  DiffFilters,
  InstalledUpdateConflictPage,
  PreparedInstalledUpdate,
  UpdateConflict,
  UpdateConflictResolution,
} from '../types'

const PAGE_SIZE = 100
const CONFLICT_PAGE_SIZE = 100

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

function preparedConflictPage(
  prepared: PreparedInstalledUpdate,
): InstalledUpdateConflictPage | null {
  if (!prepared.conflict_page) return null
  return {
    rebase_id: prepared.rebase_id,
    status: prepared.status,
    conflict_count: prepared.conflict_count,
    resolved_conflict_count: prepared.resolved_conflict_count,
    items: prepared.conflicts,
    page: prepared.conflict_page,
  }
}

function resolvedConflict(
  conflict: UpdateConflict,
  resolution: UpdateConflictResolution,
  resolvedAt: string,
): UpdateConflict {
  return {
    ...conflict,
    resolution_mode: resolution,
    resolved_value: resolution === 'keep_mine'
      ? conflict.local_value
      : conflict.upstream_value,
    resolved_at: resolvedAt,
  }
}

function ConflictCard({
  conflict,
  isSaving,
  pendingResolution,
  onResolve,
}: {
  conflict: UpdateConflict
  isSaving: boolean
  pendingResolution?: UpdateConflictResolution
  onResolve: (resolution: UpdateConflictResolution) => void
}) {
  const resolution = conflict.resolution_mode === 'keep_mine'
    || conflict.resolution_mode === 'keep_upstream'
    ? conflict.resolution_mode
    : undefined
  const isResolved = Boolean(resolution && conflict.resolved_at)
  return (
    <Card className={cn(
      'overflow-hidden',
      isResolved ? 'border-emerald-500/35' : 'border-amber-500/35',
    )}>
      <CardHeader className={isResolved ? 'bg-emerald-500/8' : 'bg-amber-500/8'}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-sm">
              {conflict.note_label || 'Note'} / {conflict.field_name || 'Field'}
            </CardTitle>
            <CardDescription>
              Bản local và release mới cùng sửa field này.
            </CardDescription>
          </div>
          <Badge
            variant="outline"
            className={cn(
              isResolved
                ? 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300'
                : 'border-amber-500/40 text-amber-700 dark:text-amber-300',
            )}
          >
            {isResolved ? <Check /> : <ShieldAlert />}
            {isResolved ? 'Đã xử lý' : 'Xung đột'}
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
            disabled={isSaving}
            aria-pressed={resolution === 'keep_mine'}
            onClick={() => onResolve('keep_mine')}
          >
            {isSaving && pendingResolution === 'keep_mine'
              ? <LoaderCircle className="animate-spin" />
              : resolution === 'keep_mine' ? <Check /> : null}
            Giữ bản của tôi
          </Button>
          <Button
            type="button"
            variant={resolution === 'keep_upstream' ? 'default' : 'outline'}
            disabled={isSaving}
            aria-pressed={resolution === 'keep_upstream'}
            onClick={() => onResolve('keep_upstream')}
          >
            {isSaving && pendingResolution === 'keep_upstream'
              ? <LoaderCircle className="animate-spin" />
              : resolution === 'keep_upstream' ? <Check /> : null}
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
  const [conflictPageIndex, setConflictPageIndex] = useState(0)
  const [prepared, setPrepared] = useState<PreparedInstalledUpdate | null>(null)
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

  const conflictQuery = useInfiniteQuery({
    queryKey: ['installed-update-conflicts', prepared?.rebase_id],
    enabled: Boolean(prepared && prepared.conflict_count > 0),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => getInstalledUpdateConflicts(
      prepared?.rebase_id || '',
      pageParam,
      CONFLICT_PAGE_SIZE,
      signal,
    ),
    getNextPageParam: (page) => page.page.has_more
      ? page.page.next_after_id || undefined
      : undefined,
    staleTime: Infinity,
  })

  const markSeenMutation = useMutation({
    mutationFn: () => markInstalledDeckUpdateSeen(installId, releaseId),
    onSuccess: (updates) => {
      queryClient.setQueryData(['installed-deck-updates', installId], updates)
      void queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
    },
  })

  const firstPage = diffQuery.data?.pages[0]
  const loadedPages = diffQuery.data?.pages || []
  const visiblePageIndex = Math.min(pageIndex, Math.max(loadedPages.length - 1, 0))
  const items = loadedPages[visiblePageIndex]?.items || []
  const loadedConflictPages = conflictQuery.data?.pages || []
  const visibleConflictPageIndex = Math.min(
    conflictPageIndex,
    Math.max(loadedConflictPages.length - 1, 0),
  )
  const visibleConflictPage = loadedConflictPages[visibleConflictPageIndex]
  const visibleConflicts = visibleConflictPage?.items || []

  useEffect(() => {
    setPageIndex(0)
  }, [filters, installId, releaseId])

  useEffect(() => {
    setConflictPageIndex(0)
  }, [prepared?.rebase_id])

  useEffect(() => {
    const pages = conflictQuery.data?.pages
    const latestPage = pages?.[pages.length - 1]
    if (!latestPage) return
    setPrepared((current) => {
      if (
        !current
        || current.rebase_id !== latestPage.rebase_id
        || (
          current.status === latestPage.status
          && current.conflict_count === latestPage.conflict_count
          && current.resolved_conflict_count === latestPage.resolved_conflict_count
        )
      ) {
        return current
      }
      return {
        ...current,
        status: latestPage.status,
        conflict_count: latestPage.conflict_count,
        resolved_conflict_count: latestPage.resolved_conflict_count,
      }
    })
  }, [conflictQuery.data?.pages])

  useEffect(() => {
    const updates = updatesQuery.data
    if (
      !updates?.unread_update
      || updates.installation.available_release?.id !== releaseId
      || !markSeenMutation.isIdle
    ) {
      return
    }
    markSeenMutation.mutate()
  }, [markSeenMutation, releaseId, updatesQuery.data])

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
      const initialConflictPage = preparedConflictPage(result)
      const conflictQueryKey = ['installed-update-conflicts', result.rebase_id] as const
      if (initialConflictPage) {
        queryClient.setQueryData<InfiniteData<InstalledUpdateConflictPage, string | null>>(
          conflictQueryKey,
          { pages: [initialConflictPage], pageParams: [null] },
        )
      } else {
        queryClient.removeQueries({ queryKey: conflictQueryKey, exact: true })
      }
      setPrepared(result)
      setConflictPageIndex(0)
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

  const resolveMutation = useMutation({
    mutationFn: ({
      conflictId,
      resolution,
    }: {
      conflictId: string
      resolution: UpdateConflictResolution
    }) => {
      if (!prepared) throw new Error('Phiên kiểm tra xung đột không còn khả dụng.')
      return resolveInstalledUpdateConflict(prepared.rebase_id, conflictId, resolution)
    },
    onSuccess: (result, variables) => {
      const resolvedAt = new Date().toISOString()
      setPrepared((current) => {
        if (!current || current.rebase_id !== result.rebase_id) return current
        return {
          ...current,
          status: result.status,
          conflict_count: result.conflict_count,
          resolved_conflict_count: result.resolved_conflict_count,
          expected_overlay_revision: result.expected_overlay_revision
            ?? current.expected_overlay_revision,
          conflicts: current.conflicts.map((conflict) => (
            conflict.id === variables.conflictId
              ? resolvedConflict(conflict, variables.resolution, resolvedAt)
              : conflict
          )),
        }
      })
      queryClient.setQueryData<InfiniteData<InstalledUpdateConflictPage, string | null>>(
        ['installed-update-conflicts', result.rebase_id],
        (current) => current
          ? {
              ...current,
              pages: current.pages.map((page) => ({
                ...page,
                status: result.status,
                conflict_count: result.conflict_count,
                resolved_conflict_count: result.resolved_conflict_count,
                items: page.items.map((conflict) => (
                  conflict.id === variables.conflictId
                    ? resolvedConflict(conflict, variables.resolution, resolvedAt)
                    : conflict
                )),
              })),
            }
          : current,
      )
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Không thể lưu cách xử lý xung đột.')
    },
  })

  const applyMutation = useMutation({
    mutationFn: () => {
      if (!prepared) throw new Error('Hãy kiểm tra xung đột trước khi cập nhật.')
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

  const allConflictsResolved = prepared !== null
    && prepared.resolved_conflict_count >= prepared.conflict_count
  const canApply = prepared !== null
    && prepared.status === 'ready'
    && allConflictsResolved

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
                disabled={!canApply || applyMutation.isPending || resolveMutation.isPending}
                onClick={() => applyMutation.mutate()}
              >
                {applyMutation.isPending
                  ? <LoaderCircle className="animate-spin" />
                  : <Check />}
                Áp dụng phiên bản {firstPage.target_release.version_label}
              </Button>
            )}

            {prepared && prepared.conflict_count > 0 ? (
              <p className={cn(
                'text-xs leading-relaxed tabular-nums',
                allConflictsResolved ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300',
              )} aria-live="polite">
                {prepared.resolved_conflict_count}/{prepared.conflict_count} xung đột đã được lưu.
              </p>
            ) : null}
            <p className="text-xs leading-relaxed text-muted-foreground">
              Apply chỉ rebase overlay và nâng release pointer; không tạo lại tiến độ học.
            </p>
          </CardContent>
        </Card>
      </div>

      {prepared && prepared.conflict_count > 0 ? (
        <section className="space-y-3" aria-labelledby="update-conflicts-title">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="max-w-3xl">
              <h2 id="update-conflicts-title" className="text-lg font-semibold">
                Xử lý xung đột
              </h2>
              <p className="text-sm text-muted-foreground">
                Mỗi lựa chọn được lưu ngay. Chọn “Giữ bản của tôi” sẽ tiếp tục lưu field đó trong overlay local.
              </p>
            </div>
            <p className="text-sm text-muted-foreground tabular-nums" aria-live="polite">
              Đã xử lý {prepared.resolved_conflict_count}/{prepared.conflict_count}
            </p>
          </div>

          {conflictQuery.isPending ? (
            <div className="flex min-h-32 items-center justify-center gap-2 rounded-lg border text-sm text-muted-foreground">
              <LoaderCircle className="animate-spin" />
              Đang tải xung đột…
            </div>
          ) : null}

          {conflictQuery.error ? (
            <Alert variant="destructive">
              <ShieldAlert />
              <AlertTitle>Không tải được danh sách xung đột</AlertTitle>
              <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                <span>
                  {conflictQuery.error instanceof Error
                    ? conflictQuery.error.message
                    : 'Hãy thử tải lại trang conflict hiện tại.'}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => void conflictQuery.refetch()}
                >
                  <RefreshCcw />
                  Thử lại
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}

          {visibleConflicts.map((conflict) => (
            <ConflictCard
              key={conflict.id}
              conflict={conflict}
              isSaving={resolveMutation.isPending}
              pendingResolution={
                resolveMutation.variables?.conflictId === conflict.id
                  ? resolveMutation.variables.resolution
                  : undefined
              }
              onResolve={(resolution) => resolveMutation.mutate({
                conflictId: conflict.id,
                resolution,
              })}
            />
          ))}

          {visibleConflictPage ? (
            <nav
              className="flex flex-wrap items-center justify-between gap-3 border-t pt-3"
              aria-label="Phân trang xung đột"
            >
              <p className="text-xs text-muted-foreground tabular-nums">
                Trang {visibleConflictPageIndex + 1} · {visibleConflicts.length} field đang hiển thị
              </p>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={visibleConflictPageIndex === 0 || conflictQuery.isFetchingNextPage}
                  onClick={() => setConflictPageIndex((current) => Math.max(0, current - 1))}
                >
                  Trang trước
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={
                    conflictQuery.isFetchingNextPage
                    || (
                      visibleConflictPageIndex >= loadedConflictPages.length - 1
                      && !conflictQuery.hasNextPage
                    )
                  }
                  onClick={() => {
                    if (visibleConflictPageIndex < loadedConflictPages.length - 1) {
                      setConflictPageIndex((current) => current + 1)
                      return
                    }
                    void conflictQuery.fetchNextPage().then((result) => {
                      if ((result.data?.pages.length ?? 0) > loadedConflictPages.length) {
                        setConflictPageIndex((current) => current + 1)
                      }
                    })
                  }}
                >
                  {conflictQuery.isFetchingNextPage
                    ? <LoaderCircle className="animate-spin" />
                    : null}
                  Trang tiếp
                </Button>
              </div>
            </nav>
          ) : null}
        </section>
      ) : null}

      <DiffWorkspace
        summary={firstPage.summary}
        items={items}
        filters={filters}
        onFiltersChange={(nextFilters) => {
          setFilters(nextFilters)
          setPageIndex(0)
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
            if ((result.data?.pages.length ?? 0) > loadedPages.length) {
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
