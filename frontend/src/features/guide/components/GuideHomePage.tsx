import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowRight,
  faBolt,
  faBook,
  faBookBookmark,
  faChevronRight,
  faGraduationCap,
  faLifeRing,
  faMagnifyingGlass,
  faRightLeft,
  faRobot,
  faStore,
  faTableColumns,
  faTriangleExclamation,
  faVolumeHigh,
  faWallet,
} from '@fortawesome/free-solid-svg-icons'
import type { IconDefinition } from '@fortawesome/free-solid-svg-icons'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { GUIDE_CATEGORIES, searchArticles } from '../guideData'

const CATEGORY_FA_ICONS: Record<string, IconDefinition> = {
  Zap: faBolt,
  LayoutDashboard: faTableColumns,
  GraduationCap: faGraduationCap,
  Search: faMagnifyingGlass,
  NotebookTabs: faBookBookmark,
  Store: faStore,
  ArrowRightLeft: faRightLeft,
  Bot: faRobot,
  AudioLines: faVolumeHigh,
  Wallet: faWallet,
  AlertTriangle: faTriangleExclamation,
}

interface GuideHomePageProps {
  searchQuery: string
  onSearchChange: (q: string) => void
}

export function GuideHomePage({ searchQuery, onSearchChange }: GuideHomePageProps) {
  const searchResults = searchQuery ? searchArticles(searchQuery) : []

  return (
    <div className="space-y-8 animate-in fade-in-50 duration-200">
      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-3xl border border-border/80 bg-card p-6 sm:p-8 shadow-xs">
        <div className="relative z-10 max-w-2xl space-y-3">
          <Badge className="bg-primary/10 text-primary border-primary/20 px-3 py-1 font-semibold text-xs rounded-full gap-1.5">
            <FontAwesomeIcon icon={faLifeRing} className="text-xs" />
            <span>Trung Tâm Trợ Giúp &amp; Hướng Dẫn Flama</span>
          </Badge>
          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-foreground">
            Học tập hiệu quả &amp; Làm chủ toàn diện Flama
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
            Khám phá tài liệu hướng dẫn quy trình từng bước, mẹo học tập thông minh và ma trận chẩn đoán sự cố theo hiện tượng thực tế.
          </p>

          {/* Quick Search */}
          <div className="pt-2">
            <div className="relative max-w-lg">
              <FontAwesomeIcon
                icon={faMagnifyingGlass}
                className="text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2 text-sm"
              />
              <Input
                type="search"
                placeholder="Tìm kiếm: gom nhóm deck, phím tắt, Yomitan, sửa lỗi..."
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                className="pl-10 pr-4 h-11 text-xs sm:text-sm rounded-2xl bg-background border-border/80 shadow-xs focus-visible:ring-primary"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Search Results Mode */}
      {searchQuery ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-foreground">
              Kết quả tìm kiếm cho "{searchQuery}" ({searchResults.length})
            </h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSearchChange('')}
              className="text-xs text-muted-foreground rounded-xl"
            >
              Xóa tìm kiếm
            </Button>
          </div>

          {searchResults.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/80 p-8 text-center text-muted-foreground space-y-2">
              <p className="text-sm font-medium">Không tìm thấy tài liệu phù hợp.</p>
              <p className="text-xs">Thử tìm bằng các từ khóa ngắn gọn như: deck, SRS, phím tắt, yomitan, âm thanh, payos...</p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {searchResults.map((art) => {
                const targetUrl =
                  art.categorySlug === 'getting-started' &&
                  (art.slug === 'getting-started' || art.slug === 'core-concepts')
                    ? `/guide/${art.slug}`
                    : `/guide/${art.categorySlug}/${art.slug}`

                return (
                  <Card key={art.slug} className="border-border/80 bg-card hover:border-primary/50 transition-all rounded-2xl shadow-2xs">
                    <CardHeader className="p-4 pb-2">
                      <CardTitle className="text-sm font-bold">
                        <Link to={targetUrl} className="hover:text-primary transition-colors flex items-center justify-between gap-2">
                          <span>{art.title}</span>
                          <FontAwesomeIcon icon={faChevronRight} className="text-xs text-muted-foreground shrink-0" />
                        </Link>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-4 pt-0">
                      <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                        {art.shortDescription}
                      </p>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        <>
          {/* 3-Minute Quickstart Highlight Card */}
          <div className="rounded-2xl border border-primary/30 bg-primary/5 p-5 sm:p-6 flex flex-wrap items-center justify-between gap-4 shadow-xs">
            <div className="flex items-center gap-3.5 min-w-0">
              <div className="size-12 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center shrink-0 shadow-xs">
                <FontAwesomeIcon icon={faBolt} className="text-xl" />
              </div>
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm sm:text-base font-bold text-foreground">
                    Bạn là người mới sử dụng Flama?
                  </h3>
                  <Badge className="bg-primary text-primary-foreground text-[10px] h-4 px-1.5 font-bold">
                    3 phút
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-1">
                  Xem hướng dẫn quy trình 4 bước để hoàn thành phiên học Flashcard đầu tiên và làm quen với Spaced Repetition.
                </p>
              </div>
            </div>

            <Button asChild variant="default" size="sm" className="gap-2 font-bold rounded-xl shrink-0 shadow-xs">
              <Link to="/guide/getting-started">
                <span>Bắt đầu ngay</span>
                <FontAwesomeIcon icon={faArrowRight} className="text-xs" />
              </Link>
            </Button>
          </div>

          {/* Categories Grid */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
                <FontAwesomeIcon icon={faBook} className="text-primary text-base" />
                <span>Danh Mục Chuyên Đề Hướng Dẫn</span>
              </h2>
              <span className="text-xs text-muted-foreground font-medium">
                {GUIDE_CATEGORIES.length} chuyên mục tài liệu
              </span>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {GUIDE_CATEGORIES.map((cat) => {
                const iconDef = CATEGORY_FA_ICONS[cat.iconName] || faBook
                const isTrouble = cat.slug === 'troubleshooting'

                return (
                  <div
                    key={cat.slug}
                    className={`rounded-2xl border p-5 transition-all flex flex-col justify-between space-y-4 shadow-2xs ${
                      isTrouble
                        ? 'border-amber-500/30 bg-amber-500/10 hover:border-amber-500/60'
                        : 'border-border/80 bg-card hover:border-primary/40'
                    }`}
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <div
                          className={`size-10 rounded-xl flex items-center justify-center ${
                            isTrouble
                              ? 'bg-amber-500/20 text-amber-700 dark:text-amber-300'
                              : 'bg-primary/10 text-primary'
                          }`}
                        >
                          <FontAwesomeIcon icon={iconDef} className="text-base" />
                        </div>
                        <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-semibold text-muted-foreground border-border/60">
                          {cat.articles.length} bài viết
                        </Badge>
                      </div>

                      <div>
                        <h3 className="font-bold text-sm text-foreground">
                          {cat.title}
                        </h3>
                        <p className="text-xs text-muted-foreground mt-1 leading-relaxed line-clamp-2">
                          {cat.description}
                        </p>
                      </div>

                      {/* Subarticles previews */}
                      <ul className="space-y-1.5 pt-1">
                        {cat.articles.slice(0, 3).map((art) => {
                          const targetUrl =
                            cat.slug === 'getting-started' &&
                            (art.slug === 'getting-started' || art.slug === 'core-concepts')
                              ? `/guide/${art.slug}`
                              : `/guide/${cat.slug}/${art.slug}`

                          return (
                            <li key={art.slug}>
                              <Link
                                to={targetUrl}
                                className="text-xs text-muted-foreground hover:text-primary transition-colors flex items-center gap-1.5 truncate group"
                              >
                                <span className="size-1.5 rounded-full bg-border group-hover:bg-primary shrink-0 transition-colors" />
                                <span className="truncate font-medium">{art.title}</span>
                              </Link>
                            </li>
                          )
                        })}
                      </ul>
                    </div>

                    <Button asChild variant="ghost" size="sm" className="w-full justify-between text-xs font-semibold h-8 rounded-xl hover:bg-primary/10 hover:text-primary">
                      <Link to={`/guide/${cat.slug}/${cat.articles[0]?.slug || ''}`}>
                        <span>Xem chuyên mục</span>
                        <FontAwesomeIcon icon={faChevronRight} className="text-[10px]" />
                      </Link>
                    </Button>
                  </div>
                )
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

