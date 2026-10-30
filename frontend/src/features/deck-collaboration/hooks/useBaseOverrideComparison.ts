import { useState } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ApiError } from '@/shared/api/client'
import { getBaseOverrideComparison, keepBaseOverride, resetBaseOverride } from '../api/baseComparisonApi'
import type { BaseOverrideComparison } from '../model/baseComparisonTypes'

export function useBaseOverrideComparison(installId: string) {
  const client = useQueryClient()
  const [pageIndex, setPageIndex] = useState(0)
  const queryKey = ['installed-base-overrides', installId]
  const comparison = useInfiniteQuery({
    queryKey,
    enabled: Boolean(installId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => getBaseOverrideComparison(installId, pageParam, signal),
    getNextPageParam: (page) => page.next_cursor || undefined,
    retry: false,
  })
  const pages = comparison.data?.pages || []
  const visibleIndex = Math.min(pageIndex, Math.max(0, pages.length - 1))
  const page = pages[visibleIndex]
  const refresh = async () => {
    setPageIndex(0)
    await client.resetQueries({ queryKey })
  }
  const mutationOptions = {
    onSuccess: async () => {
      await Promise.all([
        refresh(),
        client.invalidateQueries({ queryKey: ['browse'] }),
        client.invalidateQueries({ queryKey: ['browse-notes'] }),
        client.invalidateQueries({ queryKey: ['installed-decks'] }),
      ])
    },
    onError: (error: Error) => {
      toast.error(error instanceof Error ? error.message : 'Không thể bỏ phần sửa riêng.')
      if (error instanceof ApiError && error.status === 409) void refresh()
    },
  }
  const reset = useMutation({
    ...mutationOptions,
    mutationFn: (overrideId: string) => {
      if (!page) throw new Error('Chưa tải dữ liệu so sánh.')
      return resetBaseOverride(installId, overrideId, page.overlay_revision)
    },
  })
  const keep = useMutation({
    ...mutationOptions,
    mutationFn: (item: BaseOverrideComparison) => {
      if (!page) throw new Error('Chưa tải dữ liệu so sánh.')
      return keepBaseOverride(installId, item.id, page.overlay_revision, item.current_base_hash)
    },
  })
  const next = async () => {
    if (visibleIndex < pages.length - 1) {
      setPageIndex(visibleIndex + 1)
    } else if (comparison.hasNextPage) {
      const result = await comparison.fetchNextPage()
      if (!result.isError) setPageIndex(visibleIndex + 1)
    }
  }
  return { comparison, page, pageIndex: visibleIndex, reset, keep, refresh, next,
    previous: () => setPageIndex(Math.max(0, visibleIndex - 1)),
    hasNext: visibleIndex < pages.length - 1 || comparison.hasNextPage }
}
