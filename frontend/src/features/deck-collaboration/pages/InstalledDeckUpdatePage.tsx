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
  ShieldCheck,
  Zap,
  Unlink,
} from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/utils'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import {
  applyPreparedInstalledUpdate,
  detachInstalledDeck,
  getInstalledDeckUpdate,
  getInstalledUpdateConflicts,
  getInstalledDeckUpdates,
  markInstalledDeckUpdateSeen,
  prepareInstalledDeckUpdate,
  resolveAllInstalledUpdateConflicts,
  resolveInstalledUpdateConflict,
  updateInstalledDeckSettings,
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
  const hasBase = conflict.base_value !== undefined

  return (
    <Card className={cn(
      'overflow-hidden',
      isResolved ? 'border-emerald-500/35' : 'border-amber-500/35',
    )}>
      <CardHeader className={isResolved ? 'bg-emerald-500/8' : 'bg-amber-500/8'}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-sm font-bold">
              {conflict.note_label || 'Note'} / {conflict.field_name || 'Field'}
            </CardTitle>
            <CardDescription className="text-xs">
              Bản sửa đổi cá nhân (Local) và phiên bản mới từ tác giả (Upstream) cùng thay đổi trường này so với snapshot gốc.
            </CardDescription>
          </div>
          <Badge
            variant="outline"
            className={cn(
              isResolved
                ? 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300 bg-emerald-500/10'
                : 'border-amber-500/40 text-amber-700 dark:text-amber-300 bg-amber-500/10',
            )}
          >
            {isResolved ? <Check className="size-3 mr-1" /> : <ShieldAlert className="size-3 mr-1" />}
            {isResolved ? 'Đã xử lý' : 'Xung đột 3-Way'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
        <div className={cn('grid gap-3', hasBase ? 'grid-cols-1 md:grid-cols-3' : 'grid-cols-1 md:grid-cols-2')}>
          {hasBase ? (
            <div className="overflow-hidden rounded-lg border border-border/70 bg-muted/40">
              <div className="border-b border-border/70 px-3 py-2 text-xs font-semibold text-muted-foreground flex items-center justify-between">
                <span>1. Giá trị ban đầu (Base)</span>
                <span className="text-[10px] text-muted-foreground/70">Snapshot trước</span>
              </div>
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words p-3 text-xs text-muted-foreground font-mono">
                {valuePreview(conflict.base_value)}
              </pre>
            </div>
          ) : null}

          <div className="overflow-hidden rounded-lg border border-blue-500/25 bg-blue-500/6">
            <div className="border-b border-blue-500/20 px-3 py-2 text-xs font-semibold text-blue-700 dark:text-blue-300 flex items-center justify-between">
              <span>{hasBase ? '2. Bản sửa của bạn (Local)' : 'Bản chỉnh sửa của tôi'}</span>
              <span className="text-[10px] text-blue-600/70">Máy của bạn</span>
            </div>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words p-3 text-xs font-mono">
              {valuePreview(conflict.local_value)}
            </pre>
          </div>

          <div className="overflow-hidden rounded-lg border border-emerald-500/25 bg-emerald-500/6">
            <div className="border-b border-emerald-500/20 px-3 py-2 text-xs font-semibold text-emerald-700 dark:text-emerald-300 flex items-center justify-between">
              <span>{hasBase ? '3. Bản phát hành mới (Upstream)' : 'Bản cập nhật từ tác giả'}</span>
              <span className="text-[10px] text-emerald-600/70">Tác giả deck</span>
            </div>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words p-3 text-xs font-mono">
              {valuePreview(conflict.upstream_value)}
            </pre>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant={resolution === 'keep_mine' ? 'default' : 'outline'}
              size="sm"
              disabled={isSaving}
              aria-pressed={resolution === 'keep_mine'}
              onClick={() => onResolve('keep_mine')}
              className={resolution === 'keep_mine' ? 'bg-blue-600 hover:bg-blue-700 text-white' : ''}
            >
              {isSaving && pendingResolution === 'keep_mine'
                ? <LoaderCircle className="animate-spin size-3.5 mr-1" />
                : resolution === 'keep_mine' ? <Check className="size-3.5 mr-1" /> : null}
              Giữ bản của tôi
            </Button>
            <Button
              type="button"
              variant={resolution === 'keep_upstream' ? 'default' : 'outline'}
              size="sm"
              disabled={isSaving}
              aria-pressed={resolution === 'keep_upstream'}
              onClick={() => onResolve('keep_upstream')}
              className={resolution === 'keep_upstream' ? 'bg-emerald-600 hover:bg-emerald-700 text-white' : ''}
            >
              {isSaving && pendingResolution === 'keep_upstream'
                ? <LoaderCircle className="animate-spin size-3.5 mr-1" />
                : resolution === 'keep_upstream' ? <Check className="size-3.5 mr-1" /> : null}
              Nhận bản cập nhật
            </Button>
          </div>
          {isResolved ? (
            <span className="text-xs text-muted-foreground">
              Đã chọn: <strong className="text-foreground">{resolution === 'keep_mine' ? 'Giữ bản của tôi' : 'Dùng bản tác giả'}</strong>
            </span>
          ) : null}
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
    onMutate: () => {
      toast?.loading?.('Đang kiểm tra và chuẩn bị dữ liệu cập nhật…', {
        id: 'installed-deck-update',
        description: 'Hệ thống đang kiểm tra các trường dữ liệu và xung đột phiên bản.',
      })
    },
    onSuccess: (result) => {
      toast?.dismiss?.('installed-deck-update')
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
      toast.error(error instanceof Error ? error.message : 'Không thể chuẩn bị bản cập nhật.', {
        id: 'installed-deck-update',
      })
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

  const resolveAllMutation = useMutation({
    mutationFn: (resolutionMode: 'keep_mine' | 'keep_upstream') => {
      if (!prepared) throw new Error('Phiên kiểm tra xung đột không còn khả dụng.')
      return resolveAllInstalledUpdateConflicts(prepared.rebase_id, resolutionMode)
    },
    onSuccess: (result, resolutionMode) => {
      const resolvedAt = new Date().toISOString()
      setPrepared((current) => {
        if (!current || current.rebase_id !== result.rebase_id) return current
        return {
          ...current,
          status: result.status,
          conflict_count: result.conflict_count,
          resolved_conflict_count: result.resolved_conflict_count,
          conflicts: current.conflicts.map((conflict) =>
            resolvedConflict(conflict, resolutionMode, resolvedAt),
          ),
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
                items: page.items.map((conflict) =>
                  resolvedConflict(conflict, resolutionMode, resolvedAt),
                ),
              })),
            }
          : current,
      )
      toast.success(
        resolutionMode === 'keep_mine'
          ? 'Đã chọn giữ bản của bạn cho tất cả xung đột.'
          : 'Đã chọn nhận bản từ tác giả cho tất cả xung đột.',
      )
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Không thể áp dụng xử lý hàng loạt.')
    },
  })

  const autoUpdateMutation = useMutation({
    mutationFn: (enabled: boolean) => updateInstalledDeckSettings(installId, enabled),
    onSuccess: (updates) => {
      queryClient.setQueryData(['installed-deck-updates', installId], updates)
      void queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
      toast.success(
        updates.auto_update_enabled
          ? 'Đã bật tự động cập nhật cho deck này.'
          : 'Đã tắt tự động cập nhật.',
      )
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Không thể cập nhật tùy chọn tự động cập nhật.')
    },
  })

  const detachMutation = useMutation({
    mutationFn: () => detachInstalledDeck(installId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
      queryClient.invalidateQueries({ queryKey: ['installed-deck-updates', installId] })
      toast.success('Đã tách deck thành công. Deck này hiện là bản sao cá nhân độc lập của bạn.')
      navigate('/installed-decks')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Không thể tách deck.')
    },
  })

  const applyMutation = useMutation({
    mutationFn: () => {
      if (!prepared) throw new Error('Hãy kiểm tra xung đột trước khi cập nhật.')
      return applyPreparedInstalledUpdate(prepared.rebase_id)
    },
    onMutate: () => {
      toast?.loading?.('Đang áp dụng bản cập nhật bộ thẻ…', {
        id: 'installed-deck-update',
        description: 'Đang rebase overlay và nâng cấp phiên bản deck. Vui lòng không đóng trang!',
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['installed-deck-updates', installId] })
      await queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
      toast.success(`Đã cập nhật deck lên phiên bản ${firstPage?.target_release.version_label || ''}.`, {
        id: 'installed-deck-update',
      })
      navigate('/installed-decks')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Không thể áp dụng bản cập nhật.', {
        id: 'installed-deck-update',
      })
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
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">
                  <GitCompare className="mr-1.5 size-3.5" />
                  {firstPage.from_release?.version_label || 'Bản gốc'}
                  <span aria-hidden="true" className="mx-1">→</span>
                  {firstPage.target_release.version_label}
                </Badge>
                {updatesQuery.data.unread_update ? (
                  <Badge>Bản cập nhật mới</Badge>
                ) : null}
              </div>
              <CardTitle className="text-base font-bold">Ghi chú phát hành</CardTitle>
              <CardDescription className="whitespace-pre-wrap text-xs">
                {firstPage.changelog || 'Tác giả không thêm ghi chú chi tiết cho phiên bản này.'}
              </CardDescription>
            </CardHeader>
          </Card>

          {/* Learning Progress Preservation Guarantee */}
          <div className="flex items-start gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-3.5 text-xs text-emerald-900 dark:text-emerald-200">
            <ShieldCheck className="size-5 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-bold text-emerald-800 dark:text-emerald-300">
                Tiến độ học tập luôn được bảo toàn 100%
              </span>
              <p className="text-[11px] text-emerald-700/90 dark:text-emerald-300/90 leading-relaxed">
                Lịch sử ôn tập, thuật toán lặp lại ngắt quãng (SRS/FSRS/SM-2) và trạng thái thẻ học của bạn gắn liền với tài khoản và không bao giờ bị ghi đè khi cập nhật nội dung deck.
              </p>
            </div>
          </div>
        </div>

        <Card className="h-fit lg:sticky lg:top-4">
          <CardHeader>
            <CardTitle className="text-base">Cập nhật có kiểm soát</CardTitle>
            <CardDescription className="text-xs">
              Hệ thống 3-Way Merge tự động bảo vệ các trường bạn đã tự chỉnh sửa.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3.5">
            {/* Auto-update subscriber setting toggle */}
            <div className="flex items-center justify-between gap-2.5 rounded-xl border border-primary/20 bg-primary/5 p-3">
              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                  <Zap className="size-3.5 text-primary shrink-0" />
                  <span>Tự động cập nhật deck</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-tight">
                  Tự động nhận release mới khi tác giả phát hành (nếu không xung đột).
                </p>
              </div>
              <Switch
                checked={Boolean(updatesQuery.data.installation.auto_update_enabled)}
                disabled={autoUpdateMutation.isPending}
                onCheckedChange={(checked) => autoUpdateMutation.mutate(checked)}
                aria-label="Tự động cập nhật deck này"
              />
            </div>

            {!updatesQuery.data.update_available || firstPage.already_applied ? (
              <Alert>
                <Check className="size-4" />
                <AlertTitle>Deck đã ở phiên bản này</AlertTitle>
                <AlertDescription className="text-xs">Không còn nội dung mới cần áp dụng.</AlertDescription>
              </Alert>
            ) : null}

            {!prepared ? (
              <Button
                className="w-full h-10 font-bold text-xs rounded-xl"
                size="lg"
                disabled={prepareMutation.isPending || !updatesQuery.data.update_available}
                onClick={() => prepareMutation.mutate()}
              >
                {prepareMutation.isPending ? (
                  <>
                    <LoaderCircle className="animate-spin mr-1.5 size-4" />
                    Đang kiểm tra 3-way merge…
                  </>
                ) : (
                  <>
                    <RefreshCcw className="mr-1.5 size-4" />
                    Kiểm tra xung đột
                  </>
                )}
              </Button>
            ) : (
              <Button
                className="w-full h-10 font-bold text-xs rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground"
                size="lg"
                disabled={!canApply || applyMutation.isPending || resolveMutation.isPending || resolveAllMutation.isPending}
                onClick={() => applyMutation.mutate()}
              >
                {applyMutation.isPending ? (
                  <>
                    <LoaderCircle className="animate-spin mr-1.5 size-4" />
                    Đang áp dụng cập nhật…
                  </>
                ) : (
                  <>
                    <Check className="mr-1.5 size-4" />
                    Áp dụng phiên bản {firstPage.target_release.version_label}
                  </>
                )}
              </Button>
            )}

            {prepared && prepared.conflict_count > 0 ? (
              <p className={cn(
                'text-xs leading-relaxed tabular-nums font-semibold',
                allConflictsResolved ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300',
              )} aria-live="polite">
                {prepared.resolved_conflict_count}/{prepared.conflict_count} xung đột đã được lưu.
              </p>
            ) : null}

            {/* Detach Deck Action */}
            <div className="pt-2 border-t border-border/60">
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 justify-center h-8"
                disabled={detachMutation.isPending}
                onClick={() => {
                  if (
                    window.confirm(
                      'Bạn có chắc chắn muốn tách bộ deck này khỏi Marketplace?\n\nSau khi tách, deck sẽ trở thành bộ thẻ cá nhân độc lập của bạn, không còn liên kết cập nhật từ tác giả nữa. Tiến độ học và toàn bộ thẻ từ vựng vẫn được bảo toàn 100%.'
                    )
                  ) {
                    detachMutation.mutate()
                  }
                }}
              >
                <Unlink className="size-3.5 mr-1.5" />
                {detachMutation.isPending ? 'Đang tách deck…' : 'Tách thành deck độc lập (Detach)'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {prepared && prepared.conflict_count > 0 ? (
        <section className="space-y-3" aria-labelledby="update-conflicts-title">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="max-w-3xl">
              <h2 id="update-conflicts-title" className="text-lg font-bold flex items-center gap-2">
                <ShieldAlert className="size-5 text-amber-500" />
                Xử lý xung đột 3-Way Merge
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Mỗi lựa chọn được lưu ngay vào bản chuẩn bị rebase.
              </p>
            </div>
            <p className="text-xs font-bold text-muted-foreground tabular-nums" aria-live="polite">
              Đã xử lý {prepared.resolved_conflict_count}/{prepared.conflict_count}
            </p>
          </div>

          {/* Batch Resolution Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-2xl border border-primary/25 bg-primary/5 p-3.5">
            <div className="flex items-center gap-2 text-xs font-bold text-foreground">
              <Zap className="size-4 text-primary shrink-0" />
              <span>Giải quyết nhanh toàn bộ {prepared.conflict_count} xung đột:</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 text-xs font-bold hover:bg-blue-500/10 hover:border-blue-500/40 hover:text-blue-600 rounded-xl"
                disabled={resolveAllMutation.isPending}
                onClick={() => resolveAllMutation.mutate('keep_mine')}
              >
                {resolveAllMutation.isPending && resolveAllMutation.variables === 'keep_mine' ? (
                  <LoaderCircle className="size-3.5 mr-1 animate-spin" />
                ) : null}
                Giữ tất cả bản của tôi
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 text-xs font-bold hover:bg-emerald-500/10 hover:border-emerald-500/40 hover:text-emerald-600 rounded-xl"
                disabled={resolveAllMutation.isPending}
                onClick={() => resolveAllMutation.mutate('keep_upstream')}
              >
                {resolveAllMutation.isPending && resolveAllMutation.variables === 'keep_upstream' ? (
                  <LoaderCircle className="size-3.5 mr-1 animate-spin" />
                ) : null}
                Dùng tất cả bản tác giả
              </Button>
            </div>
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
