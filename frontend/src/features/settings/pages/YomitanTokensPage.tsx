import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  Code,
  Flame,
  Globe,
  HelpCircle,
  MousePointerClick,
  Zap,
} from 'lucide-react'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'

import { useYomitanTokenCRUD } from '../hooks/useYomitanTokenCRUD'
import { YomitanTokensTab } from '../components/YomitanTokensTab'

export function YomitanTokensPage() {
  const hookResult = useYomitanTokenCRUD()
  const { query } = hookResult

  if (query.isPending) return <PageLoading label="Đang tải token Yomitan…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="max-w-7xl mx-auto space-y-6 sm:space-y-8 pb-12 px-3 sm:px-6">
      {/* Header & Feature Highlights Bar */}
      <div className="space-y-4 sm:space-y-6">
        <PageHeader
          title="Quản lý Token Yomitan & Flama Connect"
          description="Tích hợp tiện ích tra từ Yomitan trên trình duyệt với Flama để tự động tạo Flashcard chỉ với 1 cú nhấp chuột."
          actions={
            <ContextHelpButton
              guidePath="/guide/integrations/yomitan"
              guideTitle="Hướng dẫn kết nối Yomitan"
              troubleshootPath="/guide/troubleshooting/yomitan"
              troubleshootTitle="Khắc phục lỗi Yomitan"
              label="Hướng dẫn kết nối"
            />
          }
        />

        {/* Top Quick Explanatory Links */}
        <div className="flex flex-wrap items-center gap-2 pt-0.5 text-xs">
          <span className="text-muted-foreground font-medium text-[11px]">Tra cứu nhanh:</span>
          <Link
            to="/guide/integrations/yomitan"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-sky-500/10 hover:border-sky-500/40 hover:text-sky-600 dark:hover:text-sky-400 transition-all font-medium text-[11px]"
          >
            <BookOpen className="size-3 text-sky-500" />
            <span>Cài đặt & Tải tiện ích</span>
          </Link>
          <Link
            to="/guide/integrations/yomitan-markers"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-purple-500/10 hover:border-purple-500/40 hover:text-purple-600 dark:hover:text-purple-400 transition-all font-medium text-[11px]"
          >
            <Code className="size-3 text-purple-500" />
            <span>Bảng 55 Field Markers</span>
          </Link>
          <Link
            to="/guide/troubleshooting/yomitan"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-amber-500/10 hover:border-amber-500/40 hover:text-amber-600 dark:hover:text-amber-400 transition-all font-medium text-[11px]"
          >
            <HelpCircle className="size-3 text-amber-500" />
            <span>Dùng trên Di động & Sửa lỗi</span>
          </Link>
        </div>

        {/* Quick Highlights Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-3">
          <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
            <div className="p-2 sm:p-2.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0">
              <Zap className="size-4.5 sm:size-5" />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] sm:text-xs font-semibold truncate">Tra từ 0.1s</div>
              <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">Popup di chuột / chạm</div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
            <div className="p-2 sm:p-2.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
              <MousePointerClick className="size-4.5 sm:size-5" />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] sm:text-xs font-semibold truncate">Tạo thẻ 1-Click</div>
              <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">Tự động điền dữ liệu</div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
            <div className="p-2 sm:p-2.5 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 shrink-0">
              <Globe className="size-4.5 sm:size-5" />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] sm:text-xs font-semibold truncate">Học Đắm mình</div>
              <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">Web PC & Mobile</div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-2xs">
            <div className="p-2 sm:p-2.5 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 shrink-0">
              <Flame className="size-4.5 sm:size-5" />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] sm:text-xs font-semibold truncate">Flama Connect</div>
              <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">Kết nối đám mây</div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Token Management Component */}
      <YomitanTokensTab hookResult={hookResult} />

      {/* Contextual Reference / Documentation Strip */}
      <div className="rounded-2xl border bg-card/60 p-4 sm:p-5 space-y-3 shadow-2xs">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            <BookOpen className="size-3.5 text-primary" />
            <span>Tài liệu & Hướng dẫn tham chiếu</span>
          </div>
          <Link
            to="/guide/integrations/yomitan"
            className="text-xs text-primary hover:underline font-medium flex items-center gap-1"
          >
            <span>Xem tất cả</span>
            <ArrowRight className="size-3" />
          </Link>
        </div>

        <div className="grid gap-2 sm:grid-cols-3 pt-1">
          <Link
            to="/guide/integrations/yomitan"
            className="group flex items-start gap-3 p-3 rounded-xl hover:bg-muted/60 transition-colors"
          >
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
              <BookOpen className="size-4" />
            </div>
            <div className="min-w-0 space-y-0.5">
              <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                <span>Cài đặt & Tải Yomitan</span>
                <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-primary" />
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Từng bước cài đặt extension trên Chrome/Firefox và cấu hình Server URL.
              </p>
            </div>
          </Link>

          <Link
            to="/guide/integrations/yomitan-markers"
            className="group flex items-start gap-3 p-3 rounded-xl hover:bg-muted/60 transition-colors"
          >
            <div className="p-2 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
              <Code className="size-4" />
            </div>
            <div className="min-w-0 space-y-0.5">
              <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors flex items-center gap-1">
                <span>Bảng 55 Field Markers</span>
                <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-purple-500" />
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Danh mục toàn bộ markers {'{expression}'}, {'{furigana}'}... để gán mẫu thẻ.
              </p>
            </div>
          </Link>

          <Link
            to="/guide/troubleshooting/yomitan"
            className="group flex items-start gap-3 p-3 rounded-xl hover:bg-muted/60 transition-colors"
          >
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
              <HelpCircle className="size-4" />
            </div>
            <div className="min-w-0 space-y-0.5">
              <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors flex items-center gap-1">
                <span>Di động & Xử lý sự cố</span>
                <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-amber-500" />
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Hướng dẫn dùng trên Kiwi Browser, Firefox Android và sửa lỗi kết nối.
              </p>
            </div>
          </Link>
        </div>
      </div>
    </Page>
  )
}
