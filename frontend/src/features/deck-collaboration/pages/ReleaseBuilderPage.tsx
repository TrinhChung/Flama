import { useEffect, useMemo, useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  GitCompare,
  LoaderCircle,
  Rocket,
  Tag,
} from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { createDeckRelease, getReleasePreview } from '../api'
import { DiffWorkspace } from '../components/DiffWorkspace'
import type { DiffFilters } from '../types'

const PAGE_SIZE = 100

function nextVersion(current?: string | null) {
  if (!current) return '1.0.0'
  const match = current.match(/^(\d+)\.(\d+)\.(\d+)$/)
  if (!match) return current
  return `${match[1]}.${match[2]}.${Number(match[3]) + 1}`
}

function newIdempotencyKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `release-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function ReleaseBuilderPage() {
  const { itemId = '' } = useParams<{ itemId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
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
    queryFn: ({ pageParam, signal }) => getReleasePreview(
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
  const items = useMemo(
    () => loadedPages[visiblePageIndex]?.items || [],
    [loadedPages, visiblePageIndex],
  )

  useEffect(() => {
    setPageIndex(0)
  }, [filters])

  useEffect(() => {
    if (versionLabel || !firstPage) return
    setVersionLabel(
      firstPage.suggested_version || nextVersion(firstPage.base_release?.version_label),
    )
  }, [firstPage, versionLabel])

  const publishMutation = useMutation({
    mutationFn: () => createDeckRelease(
      itemId,
      {
        version_label: versionLabel.trim(),
        changelog: changelog.trim(),
        expected_current_release_id: firstPage?.base_release?.id || null,
        expected_working_revision: firstPage?.working_revision ?? null,
      },
      publishIdempotencyKey.current,
    ),
    onSuccess: async (release) => {
      await queryClient.invalidateQueries({
        queryKey: ['deck-release-preview', itemId],
      })
      await queryClient.invalidateQueries({
        queryKey: ['deck-releases', itemId],
      })
      toast.success(`Đã phát hành phiên bản ${release.version_label}.`)
      navigate(`/marketplace/decks/${itemId}`)
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Không thể phát hành phiên bản mới.')
    },
  })

  if (!itemId) {
    return <Page><PageError error={new Error('Thiếu mã deck cần phát hành.')} /></Page>
  }
  if (previewQuery.isPending) {
    return <PageLoading label="Đang tính các thay đổi chưa phát hành…" />
  }
  if (previewQuery.error || !firstPage) {
    return <Page><PageError error={previewQuery.error || new Error('Không có dữ liệu preview.')} /></Page>
  }

  const canPublish = firstPage.has_changes && Boolean(versionLabel.trim())

  return (
    <Page className="max-w-[96rem]">
      <PageHeader
        title="Phát hành phiên bản mới"
        description={firstPage.deck_title
          ? `Kiểm tra diff của “${firstPage.deck_title}” trước khi tạo release bất biến.`
          : 'Kiểm tra diff của working deck trước khi tạo release bất biến.'}
        actions={
          <Button variant="outline" asChild>
            <Link to={`/marketplace/decks/${itemId}`}>
              <ArrowLeft />
              Quay lại deck
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
                {firstPage.base_release?.version_label || 'Chưa có release'}
                <span aria-hidden="true">→</span>
                {versionLabel || 'Phiên bản mới'}
              </Badge>
              <Badge variant="secondary">
                Working revision {firstPage.working_revision ?? '—'}
              </Badge>
            </div>
            <CardTitle>Nội dung phát hành</CardTitle>
            <CardDescription>
              Owner edit chỉ nằm trong working tree. Chỉ thao tác này mới tạo cập nhật cho người đã cài deck.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-[12rem_minmax(0,1fr)]">
            <div className="space-y-2">
              <Label htmlFor="release-version">Phiên bản</Label>
              <div className="relative">
                <Tag className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="release-version"
                  value={versionLabel}
                  onChange={(event) => setVersionLabel(event.target.value)}
                  className="pl-9 font-mono"
                  placeholder="1.1.0"
                  autoComplete="off"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="release-changelog">Ghi chú phát hành</Label>
              <Textarea
                id="release-changelog"
                value={changelog}
                onChange={(event) => setChangelog(event.target.value)}
                placeholder="Tóm tắt các nội dung quan trọng trong phiên bản này…"
                rows={3}
              />
            </div>
          </CardContent>
        </Card>

        <Card className="h-fit lg:sticky lg:top-4">
          <CardHeader>
            <CardTitle className="text-base">Xác nhận phát hành</CardTitle>
            <CardDescription>
              Release được lưu bất biến. Người cài deck sẽ tự chọn thời điểm cập nhật.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!firstPage.has_changes ? (
              <Alert>
                <AlertTitle>Không có thay đổi mới</AlertTitle>
                <AlertDescription>
                  Working deck hiện giống release gần nhất.
                </AlertDescription>
              </Alert>
            ) : null}
            <Button
              className="w-full"
              size="lg"
              disabled={!canPublish || publishMutation.isPending}
              onClick={() => publishMutation.mutate()}
            >
              {publishMutation.isPending
                ? <LoaderCircle className="animate-spin" />
                : <Rocket />}
              Phát hành {versionLabel || 'phiên bản mới'}
            </Button>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Thao tác dùng revision hiện tại để ngăn phát hành nhầm khi deck vừa được sửa ở nơi khác.
            </p>
          </CardContent>
        </Card>
      </div>

      <DiffWorkspace
        summary={firstPage.summary}
        items={items}
        filters={filters}
        onFiltersChange={setFilters}
        isFetching={previewQuery.isFetching}
        isFetchingMore={previewQuery.isFetchingNextPage}
        hasPrevious={visiblePageIndex > 0}
        onPrevious={() => setPageIndex((current) => Math.max(0, current - 1))}
        hasMore={visiblePageIndex < loadedPages.length - 1 || previewQuery.hasNextPage}
        onLoadMore={() => {
          if (visiblePageIndex < loadedPages.length - 1) {
            setPageIndex((current) => current + 1)
            return
          }
          void previewQuery.fetchNextPage().then((result) => {
            if (result.data.pages.length > loadedPages.length) {
              setPageIndex((current) => current + 1)
            }
          })
        }}
        pageLabel={`Trang ${visiblePageIndex + 1}`}
        emptyTitle="Không có thay đổi để phát hành"
        emptyDescription="Hãy đổi bộ lọc hoặc chỉnh sửa deck trước khi tạo release mới."
      />
    </Page>
  )
}
