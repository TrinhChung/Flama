import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  BookOpen,
  CheckCircle,
  Download,
  Eye,
  Filter,
  Layers,
  Search,
  Sparkles,
  Star,
  X,
  Zap,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page } from '@/shared/components/Page'
import {
  EmptyState,
  PageError,
  PageLoading,
} from '@/shared/components/PageState'

type MarketplaceItem = {
  id: string
  title?: string
  name?: string
  description: string | null
  primary_category: string | null
  rating_avg: number
  install_count: number
  price_display: string
  pricing_mode: string
  is_installed: boolean
  installed_deck_id?: number | null
  author: {
    username?: string
    account_name?: string
  } | null
}

type SortView = 'recommended' | 'newest' | 'popular'

function MarketplacePage({ mode }: { mode: 'decks' | 'note-types' }) {
  const [view, setView] = useState<SortView>('recommended')
  const [queryText, setQueryText] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [category, setCategory] = useState('')
  const endpoint =
    mode === 'decks' ? '/api/shared/decks' : '/api/shared/note-types'
  const sort =
    view === 'recommended' ? 'top_rated' : view === 'newest' ? 'newest' : 'popular'

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(queryText.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [queryText])

  const marketQuery = useQuery({
    queryKey: ['marketplace', mode, debouncedQuery, category, sort],
    queryFn: () =>
      appApi.get<{ items: MarketplaceItem[] }>(endpoint, {
        q: debouncedQuery,
        category,
        sort,
      }),
  })

  const categories = useMemo(
    () =>
      Array.from(
        new Set(
          (marketQuery.data?.items || [])
            .map((item) => item.primary_category)
            .filter((item): item is string => Boolean(item)),
        ),
      ).sort(),
    [marketQuery.data?.items],
  )

  const isFiltered = Boolean(queryText || category)

  return (
    <Page className="space-y-6 relative px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
      {/* Ambient background glow & grid pattern from Login page */}
      <AmbientBackground intensity="vibrant" />

      {/* Hero Banner Header */}
      <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-card/80 p-5 sm:p-7 shadow-md backdrop-blur-xl">
        <div className="relative z-10 space-y-3.5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary font-bold text-[11px] px-2.5 py-0.5">
                  <Sparkles className="mr-1 size-3" />
                  Flama Marketplace
                </Badge>
              </div>
              <h1 className="text-2xl font-black tracking-tight text-foreground sm:text-3xl">
                {mode === 'decks' ? 'Bộ Thẻ Cộng Đồng' : 'Mẫu Thẻ NoteTypes'}
              </h1>
              <p className="max-w-2xl text-xs sm:text-sm leading-relaxed text-muted-foreground">
                {mode === 'decks'
                  ? 'Khám phá bộ thẻ từ cộng đồng với cơ chế Logical Overlay thông minh, bảo toàn thẻ tự tùy chỉnh cá nhân.'
                  : 'Sử dụng các mẫu loại thẻ Anki chuẩn đẹp, tối ưu hiển thị kanji, từ vựng và ngữ pháp cho lộ trình học.'}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant={mode === 'decks' ? 'default' : 'outline'}
                size="sm"
                asChild
                className="font-bold text-xs sm:text-sm h-9 px-3.5 shadow-2xs rounded-xl"
              >
                <Link to="/marketplace/decks">
                  <BookOpen className="mr-1.5 size-3.5" />
                  Bộ Thẻ (Decks)
                </Link>
              </Button>
              <Button
                variant={mode === 'note-types' ? 'default' : 'outline'}
                size="sm"
                asChild
                className="font-bold text-xs sm:text-sm h-9 px-3.5 shadow-2xs rounded-xl"
              >
                <Link to="/marketplace/note-types">
                  <Layers className="mr-1.5 size-3.5" />
                  Loại Thẻ (NoteTypes)
                </Link>
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2.5 border-t border-border/40 text-xs text-muted-foreground">
            <div className="flex items-center gap-3">
              <span>
                Đang hiển thị:{' '}
                <strong className="text-foreground font-bold">
                  {marketQuery.data?.items.length || 0}
                </strong>{' '}
                {mode === 'decks' ? 'bộ thẻ' : 'loại thẻ'}
              </span>
              <span className="hidden sm:inline">•</span>
              <span className="hidden sm:inline-flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400">
                <CheckCircle className="size-3.5" /> Logical Overlay Cutover Ready
              </span>
            </div>

            <Button variant="ghost" size="sm" asChild className="h-8 px-3 text-xs font-semibold text-primary hover:text-primary rounded-lg">
              <Link to={mode === 'decks' ? '/installed-decks' : '/note-types'}>
                {mode === 'decks' ? 'Quản lý deck đã cài →' : 'Quản lý loại thẻ của tôi →'}
              </Link>
            </Button>
          </div>
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <Card className="border-border/80 bg-card/90 backdrop-blur-md shadow-xs rounded-2xl">
        <CardContent className="grid gap-3.5 p-4 sm:p-5 lg:grid-cols-[minmax(0,1fr)_200px_auto] lg:items-end">
          <div className="space-y-1.5">
            <Label htmlFor="marketplace-search" className="text-xs font-bold text-foreground flex items-center gap-1.5">
              <Search className="size-3.5 text-primary" /> Tìm trong marketplace
            </Label>
            <div className="relative">
              <Input
                id="marketplace-search"
                className="pl-8 pr-8 text-xs sm:text-sm h-9 sm:h-10 rounded-xl"
                placeholder="Tên bộ thẻ, tác giả hoặc từ khóa…"
                value={queryText}
                onChange={(event) => setQueryText(event.currentTarget.value)}
              />
              <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              {queryText ? (
                <button
                  type="button"
                  onClick={() => setQueryText('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded-full hover:bg-muted text-muted-foreground hover:text-foreground"
                >
                  <X className="size-3.5" />
                </button>
              ) : null}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="marketplace-category" className="text-xs font-bold text-foreground flex items-center gap-1.5">
              <Filter className="size-3.5 text-primary" /> Danh mục
            </Label>
            <NativeSelect
              id="marketplace-category"
              className="w-full text-xs sm:text-sm font-medium h-9 sm:h-10 rounded-xl"
              value={category}
              onChange={(event) => setCategory(event.currentTarget.value)}
            >
              <NativeSelectOption value="">Tất cả danh mục</NativeSelectOption>
              {categories.map((item) => (
                <NativeSelectOption key={item} value={item}>
                  {item}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>

          <div className="flex items-center gap-2">
            <Tabs value={view} onValueChange={(value) => setView(value as SortView)}>
              <TabsList className="w-full lg:w-auto h-9 sm:h-10 p-1 rounded-xl">
                <TabsTrigger value="recommended" className="text-xs font-semibold px-3.5 py-1 rounded-lg">Đề xuất</TabsTrigger>
                <TabsTrigger value="newest" className="text-xs font-semibold px-3.5 py-1 rounded-lg">Mới nhất</TabsTrigger>
                <TabsTrigger value="popular" className="text-xs font-semibold px-3.5 py-1 rounded-lg">Phổ biến</TabsTrigger>
              </TabsList>
            </Tabs>

            {isFiltered ? (
              <Button
                variant="ghost"
                size="sm"
                className="h-9 sm:h-10 px-2.5 text-xs text-muted-foreground hover:text-foreground rounded-xl"
                onClick={() => {
                  setQueryText('')
                  setCategory('')
                }}
                title="Xóa bộ lọc"
              >
                <X className="size-4" />
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* States */}
      {marketQuery.isPending ? <PageLoading label="Đang tải dữ liệu marketplace…" /> : null}
      {marketQuery.error ? <PageError error={marketQuery.error} /> : null}
      {marketQuery.data && !marketQuery.data.items.length ? (
        <EmptyState
          title="Không tìm thấy học liệu phù hợp"
          description="Thử thay đổi từ khóa tìm kiếm, chọn danh mục khác hoặc sắp xếp lại danh sách."
        />
      ) : null}

      {/* Item Card Grid */}
      {marketQuery.data?.items.length ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {marketQuery.data.items.map((item) => {
            const itemTitle = item.title || item.name || 'Học liệu không tên'
            const detailUrl =
              mode === 'decks'
                ? `/marketplace/decks/${item.id}`
                : `/marketplace/note-types/${item.id}`
            const authorName =
              item.author?.account_name || item.author?.username || 'Cộng đồng'
            const authorInitial = authorName.charAt(0).toUpperCase()

            return (
              <Card
                key={item.id}
                className="group relative flex flex-col overflow-hidden border-border/80 bg-card/95 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-lg backdrop-blur-md rounded-2xl"
              >
                {/* Header Banner Accent */}
                <div className="h-1.5 w-full bg-gradient-to-r from-primary via-orange-500 to-amber-500" />

                <CardHeader className="p-4 sm:p-5 pb-2.5 space-y-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="secondary" className="px-2.5 py-0.5 text-[11px] font-semibold rounded-md">
                      {item.primary_category || 'Khác'}
                    </Badge>

                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-extrabold border ${
                        item.pricing_mode === 'free'
                          ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                          : 'bg-primary/10 text-primary border-primary/30'
                      }`}
                    >
                      {item.price_display}
                    </span>
                  </div>

                  <CardTitle className="text-base font-bold tracking-tight text-foreground line-clamp-1 group-hover:text-primary transition-colors leading-snug">
                    {itemTitle}
                  </CardTitle>

                  {/* Author Row */}
                  <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <div className="flex size-4 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[9px]">
                      {authorInitial}
                    </div>
                    <span className="font-semibold text-foreground/90 line-clamp-1">
                      {authorName}
                    </span>
                  </div>
                </CardHeader>

                <CardContent className="flex-1 px-4 sm:px-5 py-2 space-y-3">
                  <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground font-normal">
                    {item.description || 'Chưa có mô tả chi tiết cho học liệu này.'}
                  </p>

                  <div className="flex items-center justify-between rounded-xl bg-muted/40 px-3 py-2 text-xs font-semibold border border-border/40">
                    <span className="inline-flex items-center gap-1 text-foreground">
                      <Star className="size-3.5 fill-amber-400 text-amber-500" />
                      {item.rating_avg.toFixed(1)}
                    </span>
                    <span className="inline-flex items-center gap-1 text-muted-foreground text-[11px]">
                      <Download className="size-3.5 text-primary" />
                      {item.install_count.toLocaleString('vi-VN')} lượt cài
                    </span>
                  </div>
                </CardContent>

                <CardFooter className="p-4 sm:p-5 pt-1">
                  {mode === 'decks' && item.installed_deck_id ? (
                    <Button className="w-full h-9 sm:h-10 font-bold text-xs sm:text-sm shadow-xs bg-gradient-to-r from-primary via-orange-500 to-amber-500 text-primary-foreground hover:opacity-95 rounded-xl" size="sm" asChild>
                      <Link to={`/study?deck_id=${item.installed_deck_id}`} className="inline-flex items-center justify-center gap-1.5 w-full h-full leading-none">
                        <Zap className="size-3.5 fill-primary-foreground shrink-0" />
                        <span>Bắt đầu học ngay</span>
                      </Link>
                    </Button>
                  ) : item.is_installed ? (
                    <Button className="w-full h-9 sm:h-10 font-bold text-xs sm:text-sm border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 rounded-xl" variant="outline" asChild>
                      <Link to={detailUrl} className="inline-flex items-center justify-center gap-1.5 w-full h-full leading-none">
                        <CheckCircle className="size-3.5 shrink-0" />
                        <span>Đã cài đặt • Xem chi tiết</span>
                      </Link>
                    </Button>
                  ) : (
                    <Button
                      className="w-full h-9 sm:h-10 font-bold text-xs sm:text-sm bg-primary/10 hover:bg-primary text-primary hover:text-primary-foreground border border-primary/25 shadow-xs transition-all duration-200 group-hover:bg-primary group-hover:text-primary-foreground rounded-xl"
                      asChild
                    >
                      <Link to={detailUrl} className="inline-flex items-center justify-center gap-1.5 w-full h-full leading-none">
                        <Eye className="size-3.5 shrink-0" />
                        <span>Xem chi tiết</span>
                        <ArrowRight className="size-3.5 shrink-0 transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </Button>
                  )}
                </CardFooter>
              </Card>
            )
          })}
        </div>
      ) : null}
    </Page>
  )
}

export function SharedDecksPage() {
  return <MarketplacePage mode="decks" />
}

export function SharedNoteTypesPage() {
  return <MarketplacePage mode="note-types" />
}

export { SharedDeckDetailPage } from './SharedDeckDetailPage'
export { SharedNoteTypeDetailPage } from './SharedNoteTypeDetailPage'



