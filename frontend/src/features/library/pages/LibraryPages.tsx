import { ArrowRight, BookOpen, Eye, Layers, Sparkles } from 'lucide-react'
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
        <div className="grid gap-2.5 sm:gap-4 grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {query.data.items.map((item) => (
            <Card
              key={item.id}
              className="group relative flex flex-col justify-between overflow-hidden border-border/40 sm:border-border/80 bg-card/95 p-2.5 sm:p-4 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-lg backdrop-blur-md rounded-xl sm:rounded-2xl"
            >
              <div className="absolute top-0 left-0 right-0 h-1 w-full bg-gradient-to-r from-primary/80 via-orange-500 to-amber-500" />
              
              <div className="flex flex-col flex-1 pt-1">
                <div className="flex items-center justify-between gap-1 mb-1.5">
                  <Badge variant="secondary" className="px-1.5 sm:px-2 py-0.5 text-[9px] sm:text-[11px] font-semibold rounded-md">
                    <Layers className="mr-1 size-3 text-primary" />
                    {item.templates?.length || 0} template
                  </Badge>

                  <Badge variant="outline" className="px-1.5 sm:px-2 py-0.5 text-[9px] sm:text-[11px] font-semibold rounded-md">
                    {item.field_defs?.length || 0} field
                  </Badge>
                </div>

                <h3 className="text-xs sm:text-sm font-bold tracking-tight text-foreground line-clamp-1 group-hover:text-primary transition-colors leading-snug mb-1">
                  {item.name}
                </h3>

                <p className="line-clamp-2 text-[11px] sm:text-xs leading-relaxed text-muted-foreground/90 font-normal mb-2">
                  {item.description || 'Chưa có mô tả cho loại thẻ này.'}
                </p>
              </div>

              <div className="mt-auto pt-2 border-t border-border/40 text-[10px] sm:text-[11px] text-muted-foreground">
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
  const query = useQuery({
    queryKey: ['installed-decks'],
    queryFn: () =>
      appApi.get<{ items: InstalledDeckItem[] }>(
        '/marketplace/installed-decks',
      ),
  })

  if (query.isPending) return <PageLoading label="Đang tải deck đã cài…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="relative min-h-screen px-2.5 sm:px-6 py-4 sm:py-6">
      <AmbientBackground />
      <PageHeader
        title="Deck đã cài"
        description="Quản lý và tiếp tục học các bộ deck bạn đã cài từ Marketplace hoặc sở hữu."
        actions={
          <Button size="sm" className="rounded-xl font-bold text-xs sm:text-sm shadow-xs" asChild>
            <Link to="/marketplace/decks" className="inline-flex items-center gap-1.5">
              <Sparkles className="size-3.5 text-amber-300" />
              <span>Khám phá Marketplace</span>
              <ArrowRight className="size-3.5" />
            </Link>
          </Button>
        }
      />
      {!query.data.items.length ? (
        <EmptyState
          title="Chưa cài deck nào"
          description="Khám phá marketplace và cài một deck để bắt đầu học."
        />
      ) : (
        <div className="grid gap-2.5 sm:gap-4 grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {query.data.items.map((item) => {
            const authorName = item.author?.account_name || item.author?.username || 'Cộng đồng'
            const authorInitial = authorName.charAt(0).toUpperCase()

            return (
              <Card
                key={item.id}
                className="group relative flex flex-col justify-between overflow-hidden border-border/40 sm:border-border/80 bg-card/95 p-2.5 sm:p-4 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-lg backdrop-blur-md rounded-xl sm:rounded-2xl"
              >
                <div className="absolute top-0 left-0 right-0 h-1 w-full bg-gradient-to-r from-primary via-orange-500 to-amber-500" />

                <div className="flex flex-col flex-1 pt-1.5">
                  {/* Title First */}
                  <h3 className="text-xs sm:text-sm font-bold tracking-tight text-foreground line-clamp-1 group-hover:text-primary transition-colors leading-snug mb-1">
                    {item.title}
                  </h3>

                  {/* Author Row */}
                  <div className="flex items-center gap-1 text-[10px] sm:text-[11px] text-muted-foreground mb-1.5">
                    <div className="flex size-3.5 sm:size-4 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[8px] sm:text-[9px]">
                      {authorInitial}
                    </div>
                    <span className="font-semibold text-foreground/80 truncate">
                      {authorName}
                    </span>
                  </div>

                  {/* Description */}
                  <p className="line-clamp-2 text-[11px] sm:text-xs leading-relaxed text-muted-foreground/90 font-normal mb-2">
                    {item.description || 'Chưa có mô tả chi tiết cho bộ deck này.'}
                  </p>

                  {/* Status Badge Row */}
                  <div className="flex items-center justify-between gap-1 mb-2 mt-auto">
                    <Badge
                      variant={item.install_bucket === 'using_now' ? 'default' : 'secondary'}
                      className="px-1.5 sm:px-2 py-0.5 text-[9px] sm:text-[11px] font-semibold rounded-md truncate"
                    >
                      {item.install_bucket === 'using_now'
                        ? 'Đang sử dụng'
                        : item.install_bucket === 'owned'
                          ? 'Deck của bạn'
                          : 'Đã cài'}
                    </Badge>

                    {item.last_sync_status ? (
                      <span className="text-[9px] sm:text-[10px] text-muted-foreground truncate">
                        {item.last_sync_status}
                      </span>
                    ) : null}
                  </div>
                </div>

                {/* Bottom Action */}
                <div className="mt-auto pt-1">
                  {item.installed_deck_id ? (
                    <Link
                      to={`/study?deck_id=${item.installed_deck_id}`}
                      className="flex items-center justify-center gap-1 w-full h-7 sm:h-8 py-1 px-2 font-semibold text-[11px] sm:text-xs shadow-2xs bg-gradient-to-r from-primary via-orange-500 to-amber-500 text-primary-foreground hover:opacity-95 rounded-lg sm:rounded-xl transition-all truncate"
                    >
                      <BookOpen className="size-3 sm:size-3.5 shrink-0" />
                      <span className="truncate">Học ngay</span>
                    </Link>
                  ) : (
                    <Link
                      to={`/marketplace/decks/${item.id}`}
                      className="flex items-center justify-center gap-1 w-full h-7 sm:h-8 py-1 px-2 font-semibold text-[11px] sm:text-xs border border-border/60 hover:border-primary text-foreground rounded-lg sm:rounded-xl transition-all truncate"
                    >
                      <Eye className="size-3 sm:size-3.5 shrink-0" />
                      <span className="truncate">Chi tiết</span>
                    </Link>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </Page>
  )
}

