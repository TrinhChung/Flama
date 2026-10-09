import { useEffect, useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { createDeckRelease, getReleasePreview } from '../api'
import type { DiffFilters } from '../types'

const PAGE_SIZE = 100

export function nextVersion(current?: string | null): string {
  if (!current) return '1.0.0'
  const match = current.match(/^(\d+)\.(\d+)\.(\d+)$/)
  if (!match) return current
  return `${match[1]}.${match[2]}.${Number(match[3]) + 1}`
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `release-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function useReleaseBuilder() {
  const { itemId = '' } = useParams<{ itemId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { t } = useTranslation('collaboration')

  const [filters, setFilters] = useState<DiffFilters>({
    query: '',
    changeType: 'all',
  })
  const [pageIndex, setPageIndex] = useState(0)
  const [versionLabel, setVersionLabel] = useState('')
  const [changelog, setChangelog] = useState('')
  const publishIdempotencyKey = useRef(newIdempotencyKey())

  const previewQuery = useInfiniteQuery({
    queryKey: ['deck-release-preview', itemId, filters],
    enabled: Boolean(itemId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      getReleasePreview(
        itemId,
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

  const firstPage = previewQuery.data?.pages[0]
  const loadedPages = previewQuery.data?.pages || []
  const visiblePageIndex = Math.min(pageIndex, Math.max(loadedPages.length - 1, 0))
  const items = loadedPages[visiblePageIndex]?.items || []

  useEffect(() => {
    setPageIndex(0)
  }, [filters, itemId])

  useEffect(() => {
    if (versionLabel || !firstPage) return
    setVersionLabel(
      firstPage.suggested_version || nextVersion(firstPage.base_release?.version_label),
    )
  }, [firstPage, versionLabel])

  const publishMutation = useMutation({
    mutationFn: () =>
      createDeckRelease(
        itemId,
        {
          version_label: versionLabel.trim(),
          changelog: changelog.trim(),
          expected_current_release_id: firstPage?.base_release?.id || null,
          expected_working_revision: firstPage?.working_revision ?? null,
        },
        publishIdempotencyKey.current,
      ),
    onMutate: () => {
      toast?.loading?.(
        t('release.toast_publishing', 'Đang tạo và đóng gói bản phát hành…'),
        {
          id: 'deck-publish',
          description: t(
            'release.toast_publishing_desc',
            'Hệ thống đang snapshot toàn bộ flashcard và cấu trúc deck.',
          ),
        },
      )
    },
    onSuccess: async (release) => {
      await queryClient.invalidateQueries({
        queryKey: ['deck-release-preview', itemId],
      })
      await queryClient.invalidateQueries({
        queryKey: ['deck-releases', itemId],
      })
      toast.success(
        t('release.toast_publish_success', {
          version: release.version_label,
          defaultValue: `Đã phát hành phiên bản ${release.version_label}.`,
        }),
        { id: 'deck-publish' },
      )
      navigate(`/marketplace/decks/${itemId}`)
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : t('release.toast_publish_error', 'Không thể phát hành phiên bản mới.'),
        { id: 'deck-publish' },
      )
    },
  })

  const onPreviousPage = () => {
    setPageIndex((current) => Math.max(0, current - 1))
  }

  const onLoadMore = () => {
    if (visiblePageIndex < loadedPages.length - 1) {
      setPageIndex((current) => current + 1)
      return
    }
    void previewQuery.fetchNextPage().then((result) => {
      if ((result.data?.pages.length ?? 0) > loadedPages.length) {
        setPageIndex((current) => current + 1)
      }
    })
  }

  const canPublish = Boolean(firstPage?.has_changes && versionLabel.trim())
  const hasMore = visiblePageIndex < loadedPages.length - 1 || Boolean(previewQuery.hasNextPage)

  return {
    itemId,
    filters,
    setFilters,
    pageIndex: visiblePageIndex,
    versionLabel,
    setVersionLabel,
    changelog,
    setChangelog,
    previewQuery,
    firstPage,
    items,
    canPublish,
    publishMutation,
    onPreviousPage,
    onLoadMore,
    hasMore,
  }
}
