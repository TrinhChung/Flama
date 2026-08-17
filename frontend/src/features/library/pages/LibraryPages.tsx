import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, BookOpen, Eye, HelpCircle, Layers, Sparkles } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import {
  EmptyState,
  PageError,
  PageLoading,
} from '@/shared/components/PageState'
import { SpotlightTour, type TourStep } from '@/shared/components/SpotlightTour'

const DECKS_STORAGE_KEY = 'flama_installed_decks_spotlight_tour_v1'

type NoteTypeItem = {
  id: string
  name: string
  description: string | null
  field_defs?: unknown[]
  templates?: unknown[]
  updated_at: string | null
}

type MarketplaceAuthor = {
  username?: string
  account_name?: string
}

type InstalledDeckItem = {
  id: string
  title: string
  description: string | null
  author: MarketplaceAuthor | null
  installed_deck_id: number | null
  install_bucket: 'using_now' | 'installed' | 'owned'
  last_sync_status: string | null
}

function formatUpdatedAt(value: string | null) {
  if (!value) return 'Chưa có thời gian cập nhật'
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function NoteTypesPage() {
  const query = useQuery({
    queryKey: ['note-types'],
    queryFn: () => appApi.get<{ items: NoteTypeItem[] }>('/note-types'),
  })

  if (query.isPending) return <PageLoading label="Đang tải loại thẻ…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="relative min-h-screen px-2.5 sm:px-6 py-4 sm:py-6">
      <AmbientBackground />
      <PageHeader
        title="Loại thẻ"
        description="Quản lý field, template và quy cách hiển thị flashcard."
      />
      {!query.data.items.length ? (
        <EmptyState
          title="Chưa có loại thẻ"
          description="Tạo note type đầu tiên hoặc cài một mẫu từ marketplace."
        />
      ) : (
        <div className="grid gap-3 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {query.data.items.map((item) => (
            <Card
              key={item.id}
              className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-md rounded-2xl"
            >
              <div className="flex flex-col flex-1 space-y-2">
                <div className="flex items-center justify-between gap-1.5 mb-1">
                  <Badge variant="secondary" className="px-2 py-0.5 text-xs font-semibold rounded-md">
                    <Layers className="mr-1 size-3 text-primary" />
                    {item.templates?.length || 0} template
                  </Badge>

                  <Badge variant="outline" className="px-2 py-0.5 text-xs font-semibold rounded-md">
                    {item.field_defs?.length || 0} field
                  </Badge>
                </div>

                <h3 className="text-sm sm:text-base font-bold tracking-tight text-foreground line-clamp-1 group-hover:text-primary transition-colors leading-snug">
                  {item.name}
                </h3>

                <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground font-normal">
                  {item.description || 'Chưa có mô tả cho loại thẻ này.'}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-border/60 text-xs text-muted-foreground">
                Cập nhật {formatUpdatedAt(item.updated_at)}
              </div>
            </Card>
          ))}
        </div>
      )}
    </Page>
  )
}

export function InstalledDecksPage() {
  const [tourOpen, setTourOpen] = useState(false)

  const query = useQuery({
    queryKey: ['installed-decks'],
    queryFn: () =>
      appApi.get<{ items: InstalledDeckItem[] }>(
        '/marketplace/installed-decks',
      ),
  })

  const items = query.data?.items || []

  const tourSteps: TourStep[] = useMemo(() => {
    const steps: TourStep[] = [
      {
        target: '[data-tour="decks-header"]',
        title: '📚 1. Quản Lý Bộ Thẻ Đã Cài',
        content:
          'Nơi quản lý toàn bộ các bộ thẻ (Decks) bạn đã cài đặt từ Marketplace hoặc do chính bạn sở hữu để bắt đầu ôn luyện.',
        placement: 'bottom',
      },
      {
        target: '[data-tour="marketplace-explore-btn"]',
        title: '🛍️ 2. Khám Phá Kho Bộ Thẻ Marketplace',
        content:
          'Bấm vào đây để duyệt qua hàng trăm bộ thẻ từ vựng, ngữ pháp, Kanji... chất lượng cao do cộng đồng Flama chia sẻ.',
        placement: 'bottom',
      },
    ]

    if (items.length > 0) {
      steps.push(
        {
          target: '[data-tour="deck-card-first"]',
          title: '🎴 3. Thông Tin Bộ Thẻ (Deck Card)',
          content:
            'Hiển thị tiêu đề bộ thẻ, tên tác giả đóng góp, trạng thái học tập (Đang sử dụng / Đã cài) và mô tả vắn tắt.',
          placement: 'top',
        },
        {
          target: '[data-tour="deck-action-btn"]',
          title: '🚀 4. Nút "Học Ngay" (Spaced Repetition)',
          content:
            'Bấm nút này để bắt đầu phiên ôn tập với thuật toán Lặp lại ngắt quãng thông minh (Anki SM-2 / FSRS) giúp ghi nhớ sâu và lâu bền.',
          placement: 'top',
        },
      )
    } else {
      steps.push({
        target: '[data-tour="installed-decks-grid"]',
        title: '📦 3. Khu Vực Bộ Thẻ Cá Nhân',
        content:
          'Sau khi cài đặt bộ thẻ từ Marketplace, các bộ thẻ sẽ xuất hiện tại đây để bạn bắt đầu học và theo dõi tiến độ.',
        placement: 'top',
      })
    }

    return steps
  }, [items.length])

  // Auto-launch spotlight tour for first-time visitors with no installed decks
  useEffect(() => {
    if (query.isSuccess) {
      const completed = localStorage.getItem(DECKS_STORAGE_KEY)
      if (!completed && items.length === 0) {
        const timer = setTimeout(() => {
          setTourOpen(true)
        }, 500)
        return () => clearTimeout(timer)
      }
    }
  }, [query.isSuccess, items.length])

  if (query.isPending) return <PageLoading label="Đang tải deck đã cài…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="relative min-h-screen px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
      <AmbientBackground intensity="subtle" />
      <div data-tour="decks-header">
        <PageHeader
          title="Deck đã cài"
          description="Quản lý và tiếp tục học các bộ deck bạn đã cài từ Marketplace hoặc sở hữu."
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setTourOpen(true)}
                className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl"
              >
                <HelpCircle className="size-3.5 mr-1.5 text-primary" />
                Tour Hướng Dẫn
              </Button>
              <Button
                size="sm"
                data-tour="marketplace-explore-btn"
                className="h-8 sm:h-9 px-3.5 rounded-xl font-bold text-xs sm:text-sm shadow-xs"
                asChild
              >
                <Link to="/marketplace/decks" className="inline-flex items-center gap-1.5">
                  <Sparkles className="size-3.5" />
                  <span>Khám phá Marketplace</span>
                  <ArrowRight className="size-3.5" />
                </Link>
              </Button>
            </div>
          }
        />
      </div>
      {!items.length ? (
        <div data-tour="installed-decks-grid">
          <EmptyState
            title="Chưa cài deck nào"
            description="Khám phá marketplace và cài một deck để bắt đầu học."
          />
        </div>
      ) : (
        <div className="grid gap-3 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {items.map((item, index) => {
            const authorName = item.author?.account_name || item.author?.username || 'Cộng đồng'
            const authorInitial = authorName.charAt(0).toUpperCase()

            return (
              <Card
                key={item.id}
                data-tour={index === 0 ? 'deck-card-first' : undefined}
                className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-md rounded-2xl"
              >
                <div className="flex flex-col flex-1 space-y-2">
                  {/* Status Badge Row */}
                  <div className="flex items-center justify-between gap-1.5">
                    <Badge
                      variant={item.install_bucket === 'using_now' ? 'default' : 'secondary'}
                      className="px-2 py-0.5 text-xs font-semibold rounded-md truncate"
                    >
                      {item.install_bucket === 'using_now'
                        ? 'Đang sử dụng'
                        : item.install_bucket === 'owned'
                          ? 'Deck của bạn'
                          : 'Đã cài'}
                    </Badge>

                    {item.last_sync_status ? (
                      <span className="text-xs text-muted-foreground truncate">
                        {item.last_sync_status}
                      </span>
                    ) : null}
                  </div>

                  {/* Title */}
                  <h3 className="text-sm sm:text-base font-bold tracking-tight text-foreground line-clamp-1 group-hover:text-primary transition-colors leading-snug">
                    <Link to={`/marketplace/decks/${item.id}`} className="hover:underline">
                      {item.title}
                    </Link>
                  </h3>

                  {/* Author Row */}
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <div className="flex size-4 sm:size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px]">
                      {authorInitial}
                    </div>
                    <span className="font-medium text-foreground/80 truncate">
                      {authorName}
                    </span>
                  </div>

                  {/* Description */}
                  <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground font-normal">
                    {item.description || 'Chưa có mô tả chi tiết cho bộ deck này.'}
                  </p>
                </div>

                {/* Bottom Action */}
                <div className="mt-4 pt-3 border-t border-border/60">
                  {item.installed_deck_id ? (
                    <Button
                      size="sm"
                      asChild
                      data-tour={index === 0 ? 'deck-action-btn' : undefined}
                      className="w-full h-8 sm:h-9 text-xs font-bold rounded-xl shadow-xs"
                    >
                      <Link to={`/study?deck_id=${item.installed_deck_id}`}>
                        <BookOpen className="mr-1.5 size-3.5" />
                        Học ngay
                      </Link>
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      asChild
                      data-tour={index === 0 ? 'deck-action-btn' : undefined}
                      className="w-full h-8 sm:h-9 text-xs font-semibold rounded-xl"
                    >
                      <Link to={`/marketplace/decks/${item.id}`}>
                        <Eye className="mr-1.5 size-3.5" />
                        Chi tiết
                      </Link>
                    </Button>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Interactive Spotlight Tour for Installed Decks */}
      <SpotlightTour
        steps={tourSteps}
        isOpen={tourOpen}
        onClose={() => {
          localStorage.setItem(DECKS_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
        onComplete={() => {
          localStorage.setItem(DECKS_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
      />
    </Page>
  )
}

