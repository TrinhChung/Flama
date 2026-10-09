import { useEffect, useRef, useState } from 'react'
import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
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
import type {
  DiffFilters,
  InstalledUpdateConflictPage,
  PreparedInstalledUpdate,
  UpdateConflict,
  UpdateConflictResolution,
} from '../types'

const PAGE_SIZE = 100
const CONFLICT_PAGE_SIZE = 100

export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `update-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function preparedConflictPage(
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

export function resolvedConflict(
  conflict: UpdateConflict,
  resolution: UpdateConflictResolution,
  resolvedAt: string,
): UpdateConflict {
  return {
    ...conflict,
    resolution_mode: resolution,
    resolved_value:
      resolution === 'keep_mine'
        ? conflict.local_value
        : conflict.upstream_value,
    resolved_at: resolvedAt,
  }
}

export function useInstalledDeckUpdate() {
  const { installId = '', releaseId = '' } = useParams<{
    installId: string
    releaseId: string
  }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { t } = useTranslation('collaboration')

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
    queryFn: ({ pageParam, signal }) =>
      getInstalledDeckUpdate(
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
    queryFn: ({ pageParam, signal }) =>
      getInstalledUpdateConflicts(
        prepared?.rebase_id || '',
        pageParam,
        CONFLICT_PAGE_SIZE,
        signal,
      ),
    getNextPageParam: (page) =>
      page.page.has_more ? page.page.next_after_id || undefined : undefined,
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
        !current ||
        current.rebase_id !== latestPage.rebase_id ||
        (current.status === latestPage.status &&
          current.conflict_count === latestPage.conflict_count &&
          current.resolved_conflict_count === latestPage.resolved_conflict_count)
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
      !updates?.unread_update ||
      updates.installation.available_release?.id !== releaseId ||
      !markSeenMutation.isIdle
    ) {
      return
    }
    markSeenMutation.mutate()
  }, [markSeenMutation, releaseId, updatesQuery.data])

  const prepareMutation = useMutation({
    mutationFn: () =>
      prepareInstalledDeckUpdate(installId, releaseId, {
        expected_applied_release_id:
          updatesQuery.data?.installation.applied_release?.id || null,
        expected_overlay_revision:
          updatesQuery.data?.installation.overlay_revision ?? null,
        idempotency_key: prepareIdempotencyKey.current,
      }),
    onMutate: () => {
      toast?.loading?.(
        t('update.toast_preparing', 'Đang kiểm tra và chuẩn bị dữ liệu cập nhật…'),
        {
          id: 'installed-deck-update',
          description: t(
            'update.toast_preparing_desc',
            'Hệ thống đang kiểm tra các trường dữ liệu và xung đột phiên bản.',
          ),
        },
      )
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
        toast.warning(
          t('update.toast_prepared_conflicts', {
            count: result.conflict_count,
            defaultValue: `Có ${result.conflict_count} field cần bạn chọn cách xử lý.`,
          }),
        )
      } else {
        toast.success(
          t(
            'update.toast_prepared_ready',
            'Đã kiểm tra xong. Bản cập nhật sẵn sàng để áp dụng.',
          ),
        )
      }
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Không thể chuẩn bị bản cập nhật.',
        {
          id: 'installed-deck-update',
        },
      )
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
          expected_overlay_revision:
            result.expected_overlay_revision ?? current.expected_overlay_revision,
          conflicts: current.conflicts.map((conflict) =>
            conflict.id === variables.conflictId
              ? resolvedConflict(conflict, variables.resolution, resolvedAt)
              : conflict,
          ),
        }
      })
      queryClient.setQueryData<InfiniteData<InstalledUpdateConflictPage, string | null>>(
        ['installed-update-conflicts', result.rebase_id],
        (current) =>
          current
            ? {
                ...current,
                pages: current.pages.map((page) => ({
                  ...page,
                  status: result.status,
                  conflict_count: result.conflict_count,
                  resolved_conflict_count: result.resolved_conflict_count,
                  items: page.items.map((conflict) =>
                    conflict.id === variables.conflictId
                      ? resolvedConflict(conflict, variables.resolution, resolvedAt)
                      : conflict,
                  ),
                })),
              }
            : current,
      )
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Không thể lưu cách xử lý xung đột.',
      )
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
        (current) =>
          current
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
          ? t(
              'update.toast_batch_mine',
              'Đã chọn giữ bản của bạn cho tất cả xung đột.',
            )
          : t(
              'update.toast_batch_upstream',
              'Đã chọn nhận bản từ tác giả cho tất cả xung đột.',
            ),
      )
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Không thể áp dụng xử lý hàng loạt.',
      )
    },
  })

  const autoUpdateMutation = useMutation({
    mutationFn: (enabled: boolean) => updateInstalledDeckSettings(installId, enabled),
    onSuccess: (updates) => {
      queryClient.setQueryData(['installed-deck-updates', installId], updates)
      void queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
      toast.success(
        updates.auto_update_enabled
          ? t('update.toast_auto_update_on', 'Đã bật tự động cập nhật cho deck này.')
          : t('update.toast_auto_update_off', 'Đã tắt tự động cập nhật.'),
      )
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Không thể cập nhật tùy chọn tự động cập nhật.',
      )
    },
  })

  const detachMutation = useMutation({
    mutationFn: () => detachInstalledDeck(installId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
      queryClient.invalidateQueries({
        queryKey: ['installed-deck-updates', installId],
      })
      toast.success(
        t(
          'update.toast_detach_success',
          'Đã tách deck thành công. Deck này hiện là bản sao cá nhân độc lập của bạn.',
        ),
      )
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
      toast?.loading?.(
        t('update.toast_apply_loading', 'Đang áp dụng bản cập nhật bộ thẻ…'),
        {
          id: 'installed-deck-update',
          description: t(
            'update.toast_apply_loading_desc',
            'Đang rebase overlay và nâng cấp phiên bản deck. Vui lòng không đóng trang!',
          ),
        },
      )
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['installed-deck-updates', installId],
      })
      await queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
      toast.success(
        t('update.toast_apply_success', {
          version: firstPage?.target_release.version_label || '',
          defaultValue: `Đã cập nhật deck lên phiên bản ${firstPage?.target_release.version_label || ''}.`,
        }),
        {
          id: 'installed-deck-update',
        },
      )
      navigate('/installed-decks')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Không thể áp dụng bản cập nhật.',
        {
          id: 'installed-deck-update',
        },
      )
    },
  })

  const allConflictsResolved =
    prepared !== null &&
    prepared.resolved_conflict_count >= prepared.conflict_count
  const canApply =
    prepared !== null && prepared.status === 'ready' && allConflictsResolved

  const onPreviousConflictPage = () => {
    setConflictPageIndex((current) => Math.max(0, current - 1))
  }

  const onNextConflictPage = () => {
    if (visibleConflictPageIndex < loadedConflictPages.length - 1) {
      setConflictPageIndex((current) => current + 1)
      return
    }
    void conflictQuery.fetchNextPage().then((result) => {
      if ((result.data?.pages.length ?? 0) > loadedConflictPages.length) {
        setConflictPageIndex((current) => current + 1)
      }
    })
  }

  const onPreviousDiffPage = () => {
    setPageIndex((current) => Math.max(0, current - 1))
  }

  const onNextDiffPage = () => {
    if (visiblePageIndex < loadedPages.length - 1) {
      setPageIndex((current) => current + 1)
      return
    }
    void diffQuery.fetchNextPage().then((result) => {
      if ((result.data?.pages.length ?? 0) > loadedPages.length) {
        setPageIndex((current) => current + 1)
      }
    })
  }

  const hasMoreDiff =
    visiblePageIndex < loadedPages.length - 1 || Boolean(diffQuery.hasNextPage)

  return {
    installId,
    releaseId,
    filters,
    setFilters,
    pageIndex: visiblePageIndex,
    conflictPageIndex: visibleConflictPageIndex,
    setPageIndex,
    prepared,
    updatesQuery,
    diffQuery,
    conflictQuery,
    firstPage,
    loadedPages,
    items,
    loadedConflictPages,
    visibleConflictPage,
    visibleConflicts,
    allConflictsResolved,
    canApply,
    prepareMutation,
    resolveMutation,
    resolveAllMutation,
    autoUpdateMutation,
    detachMutation,
    applyMutation,
    onPreviousConflictPage,
    onNextConflictPage,
    onPreviousDiffPage,
    onNextDiffPage,
    hasMoreDiff,
  }
}
