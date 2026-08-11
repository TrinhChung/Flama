import { useState } from 'react'
import {
  BookOpen,
  Flame,
  Globe,
  KeyRound,
  MousePointerClick,
  Sparkles,
  Zap,
  Code
} from 'lucide-react'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

import { useYomitanTokenCRUD } from '../hooks/useYomitanTokenCRUD'
import { YomitanAboutTab } from '../components/YomitanAboutTab'
import { YomitanTokensTab } from '../components/YomitanTokensTab'
import { YomitanGuideTab } from '../components/YomitanGuideTab'
import { YomitanMarkersTab } from '../components/YomitanMarkersTab'

export function YomitanTokensPage() {
  const [activeTab, setActiveTab] = useState('about')
  const hookResult = useYomitanTokenCRUD()
  const { query } = hookResult

  if (query.isPending) return <PageLoading label="Đang tải token Yomitan…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="max-w-7xl mx-auto space-y-6 sm:space-y-8 pb-12 px-3 sm:px-6">
      {/* Header & Feature Highlights Bar */}
      <div className="space-y-4 sm:space-y-6">
        <PageHeader
          title="Kết nối Yomitan & Flama Connect"
          description="Tích hợp tiện ích tra từ Yomitan trên trình duyệt với Flama để tự động tạo Flashcard chỉ với 1 cú nhấp chuột."
        />

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
              <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">Kết nối siêu tốc</div>
            </div>
          </div>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full space-y-6">
        {/* Responsive Horizontal Scroll Tab Bar */}
        <div className="overflow-x-auto pb-1 -mx-1 px-1 no-scrollbar">
          <TabsList className="inline-flex w-full sm:w-auto p-1 bg-muted/60 backdrop-blur-md rounded-2xl gap-1">
            <TabsTrigger value="about" className="flex-1 sm:flex-none px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5 transition-all">
              <Sparkles className="size-4 text-amber-500 shrink-0" />
              <span className="hidden sm:inline">Yomitan là gì? (Khuyên dùng)</span>
              <span className="sm:hidden">Tổng quan</span>
            </TabsTrigger>
            <TabsTrigger value="tokens" className="flex-1 sm:flex-none px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5 transition-all">
              <KeyRound className="size-4 text-primary shrink-0" />
              <span className="hidden sm:inline">Quản lý Token</span>
              <span className="sm:hidden">Token</span>
            </TabsTrigger>
            <TabsTrigger value="guide" className="flex-1 sm:flex-none px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5 transition-all">
              <BookOpen className="size-4 text-sky-500 shrink-0" />
              <span className="hidden sm:inline">Hướng dẫn Cài đặt</span>
              <span className="sm:hidden">Hướng dẫn</span>
            </TabsTrigger>
            <TabsTrigger value="markers" className="flex-1 sm:flex-none px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5 transition-all">
              <Code className="size-4 text-purple-500 shrink-0" />
              <span className="hidden sm:inline">Field Markers (55)</span>
              <span className="sm:hidden">Markers</span>
            </TabsTrigger>
          </TabsList>
        </div>

        <YomitanAboutTab onNavigateToTokens={() => setActiveTab('tokens')} />
        <YomitanTokensTab hookResult={hookResult} />
        <YomitanGuideTab />
        <YomitanMarkersTab />
      </Tabs>
    </Page>
  )
}
