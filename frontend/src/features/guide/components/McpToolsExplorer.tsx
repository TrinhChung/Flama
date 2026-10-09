import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { EmptyState } from '@/shared/components/PageState'
import { toast } from 'sonner'
import {
  BarChart,
  BookOpen,
  Check,
  Code,
  Copy,
  Edit,
  FolderTree,
  Image as ImageIcon,
  Layers,
  ListPlus,
  MessageSquareCode,
  PlusCircle,
  RefreshCw,
  Search,
  Share2,
  Timer,
  UploadCloud,
  Wrench,
  Zap,
} from 'lucide-react'

export type ToolCategory = 'all' | 'decks' | 'shared' | 'notes' | 'note_types' | 'study' | 'media'

export interface McpToolItem {
  name: string
  title: string
  scope: string
  category: ToolCategory
  icon: typeof Wrench
  description: string
  samplePrompt: string
}

export const MCP_TOOLS_CATALOG: McpToolItem[] = [
  // Decks
  {
    name: 'list_my_decks',
    title: 'Danh sách Bộ thẻ',
    scope: 'deck:read',
    category: 'decks',
    icon: FolderTree,
    description: 'Liệt kê toàn bộ các bộ thẻ Flashcard mà bạn sở hữu hoặc đã cài đặt trong tài khoản Flama.',
    samplePrompt: 'Hãy liệt kê cho tôi tất cả các bộ thẻ flashcard tiếng Nhật hiện có trong tài khoản của tôi.',
  },
  {
    name: 'get_deck_tree',
    title: 'Cây thư mục Bộ thẻ',
    scope: 'deck:read',
    category: 'decks',
    icon: FolderTree,
    description: 'Lấy cấu trúc cây thư mục phân cấp cha-con của tất cả các bộ thẻ học tập.',
    samplePrompt: 'Cho tôi xem cấu trúc cây thư mục các bộ thẻ của tôi để tôi biết nên tạo thẻ vào deck con nào.',
  },
  {
    name: 'create_deck',
    title: 'Tạo Bộ thẻ mới',
    scope: 'deck:write',
    category: 'decks',
    icon: PlusCircle,
    description: 'Tạo mới một bộ thẻ flashcard học tập (có thể chỉ định bộ thẻ cha).',
    samplePrompt: 'Tạo giúp tôi một bộ thẻ mới tên là "JLPT N1 Grammar" nằm trong thư mục "Tiếng Nhật Cao Cấp".',
  },
  {
    name: 'update_deck',
    title: 'Đổi tên & Sửa Bộ thẻ',
    scope: 'deck:write',
    category: 'decks',
    icon: Edit,
    description: 'Đổi tên bộ thẻ, cập nhật mô tả học tập hoặc di chuyển sang bộ thẻ cha khác.',
    samplePrompt: 'Đổi tên bộ thẻ ID 12 thành "N2 Mimikara Oboeru" và thêm mô tả ngắn.',
  },

  // Shared Decks & Marketplace
  {
    name: 'list_shared_decks',
    title: 'Danh mục Shared Decks',
    scope: 'deck-share:read',
    category: 'shared',
    icon: Share2,
    description: 'Tìm kiếm và lọc các bộ thẻ đã chia sẻ trên Marketplace (theo tag, danh mục, từ khóa).',
    samplePrompt: 'Tìm giúp tôi các bộ thẻ chia sẻ trên chợ Flama có chủ đề "IT Nihongo" hoặc "Business Japanese".',
  },
  {
    name: 'get_shared_deck',
    title: 'Chi tiết Bộ thẻ chia sẻ',
    scope: 'deck-share:read',
    category: 'shared',
    icon: Share2,
    description: 'Xem chi tiết thông tin bộ thẻ chia sẻ, mô tả, đánh giá và cấu trúc các deck con.',
    samplePrompt: 'Lấy thông tin chi tiết bộ thẻ chia sẻ ID 5 để xem đã phát hành những phiên bản nào.',
  },
  {
    name: 'list_shared_deck_notes',
    title: 'Xem Nội dung Thẻ chia sẻ',
    scope: 'deck-share:read',
    category: 'shared',
    icon: BookOpen,
    description: 'Duyệt xem nội dung các thẻ ghi nhớ trong bộ thẻ đã chia sẻ để AI review và cải thiện chất lượng.',
    samplePrompt: 'Xem danh sách 20 thẻ đầu tiên trong shared deck ID 3 để kiểm tra câu ví dụ tiếng Nhật.',
  },
  {
    name: 'share_deck',
    title: 'Đăng tải Chia sẻ Bộ thẻ',
    scope: 'deck-share:write',
    category: 'shared',
    icon: UploadCloud,
    description: 'Đưa một bộ thẻ cá nhân lên sàn chia sẻ Flama với tiêu đề, mô tả và cấu hình hiển thị.',
    samplePrompt: 'Chia sẻ bộ thẻ "500 Từ vựng N3 Hay Gặp" của tôi lên Marketplace dạng Miễn phí.',
  },
  {
    name: 'publish_deck_release',
    title: 'Phát hành Phiên bản mới (Release)',
    scope: 'deck-share:write',
    category: 'shared',
    icon: UploadCloud,
    description: 'Phát hành phiên bản chính thức (snapshot release) cho bộ thẻ chia sẻ kèm ghi chú cập nhật.',
    samplePrompt: 'Phát hành release phiên bản v1.1.0 cho bộ thẻ ID 4 kèm ghi chú "Bổ sung thêm âm thanh & ví dụ".',
  },

  // Notes & Sync
  {
    name: 'find_notes',
    title: 'Tìm kiếm Thẻ Flashcard',
    scope: 'note:check',
    category: 'notes',
    icon: Search,
    description: 'Tìm kiếm thẻ flashcard trong tài khoản theo từ khóa hoặc nội dung bất kỳ trường nào.',
    samplePrompt: 'Tìm xem trong các bộ thẻ của tôi đã có từ "環境" (kankyou) chưa?',
  },
  {
    name: 'create_note',
    title: 'Tạo 1 Thẻ Flashcard mới',
    scope: 'note:create',
    category: 'notes',
    icon: PlusCircle,
    description: 'Tạo một thẻ học mới vào bộ chỉ định với các trường dữ liệu và tags, tự động sinh thẻ Flashcard.',
    samplePrompt: 'Hãy tạo một thẻ từ vựng vào deck "JLPT N2" với từ: 把握 (はあく - Nắm bắt, thấu hiểu), ví dụ: "状況を正確に把握する".',
  },
  {
    name: 'update_note',
    title: 'Chỉnh sửa Thẻ ghi nhớ',
    scope: 'note:update',
    category: 'notes',
    icon: Edit,
    description: 'Cập nhật lại giá trị các trường dữ liệu (nghĩa, ví dụ, kanji) hoặc thêm bớt tags.',
    samplePrompt: 'Cập nhật thẻ ghi nhớ ID 108: thêm câu ví dụ mới và bổ sung tag "kinh-te".',
  },
  {
    name: 'batch_create_notes',
    title: 'Tạo Thẻ hàng loạt (Batch)',
    scope: 'note:create',
    category: 'notes',
    icon: ListPlus,
    description: 'Tạo nhanh hàng loạt thẻ flashcard (tối đa 50 thẻ) trong cùng một thao tác an toàn.',
    samplePrompt: 'Tạo giúp tôi 5 thẻ từ vựng JLPT N3 về chủ đề du lịch vào deck "N3 Vocabulary".',
  },
  {
    name: 'sync_notes',
    title: 'Đồng bộ Thẻ từ bên ngoài',
    scope: 'note:sync',
    category: 'notes',
    icon: RefreshCw,
    description: 'Đồng bộ hai chiều danh sách thẻ từ các nguồn bên ngoài, hỗ trợ tạo deck tự động.',
    samplePrompt: 'Đồng bộ hóa 10 thẻ từ vựng mới học trên Yomitan/Kindle vào Flama.',
  },

  // Note Types
  {
    name: 'list_note_types',
    title: 'Danh sách Loại thẻ (Note Types)',
    scope: 'note-type:read',
    category: 'note_types',
    icon: Layers,
    description: 'Lấy danh sách các Note Types (mẫu định dạng thẻ) có sẵn để chọn cấu trúc trường phù hợp.',
    samplePrompt: 'Hãy kiểm tra xem tôi có những loại Note Type nào (ví dụ: Từ vựng, Hán tự, Ngữ pháp)?',
  },
  {
    name: 'get_note_type_schema',
    title: 'Schema Trường dữ liệu',
    scope: 'note-type:read',
    category: 'note_types',
    icon: Code,
    description: 'Xem chi tiết các trường dữ liệu (Word, Reading, Meaning, Example) và mẫu hiển thị của Note Type.',
    samplePrompt: 'Lấy schema chi tiết của note type "Japanese Vocabulary" để biết tôi cần điền những trường nào khi tạo thẻ.',
  },

  // Study & Analytics
  {
    name: 'get_due_card_counts',
    title: 'Thống kê Thẻ đến hạn học',
    scope: 'deck:read',
    category: 'study',
    icon: Timer,
    description: 'Kiểm tra số lượng thẻ đến hạn ôn tập hôm nay (thẻ mới, thẻ review, thẻ đang học).',
    samplePrompt: 'Hôm nay tôi có bao nhiêu thẻ flashcard cần ôn tập trong các bộ thẻ?',
  },
  {
    name: 'record_card_review',
    title: 'Ghi nhận Kết quả Ôn tập',
    scope: 'study:write',
    category: 'study',
    icon: Zap,
    description: 'Ghi nhận đánh giá ôn tập (Again, Hard, Good, Easy) vào thuật toán SRS của Flama.',
    samplePrompt: 'Ghi nhận kết quả ôn tập thẻ ID 205 là "Good" với thời gian trả lời 4 giây.',
  },
  {
    name: 'get_study_stats',
    title: 'Xem Thống kê Học tập & Streak',
    scope: 'stats:read',
    category: 'study',
    icon: BarChart,
    description: 'Truy vấn số liệu chuỗi ngày học liên tục (streak), tổng số thẻ đã nhớ và biểu đồ tương lai.',
    samplePrompt: 'Cho tôi xem thống kê học tập tuần này và streak hiện tại của tôi là bao nhiêu ngày.',
  },

  // Media
  {
    name: 'search_media_assets',
    title: 'Tìm kiếm Thư viện Ảnh',
    scope: 'media:read',
    category: 'media',
    icon: ImageIcon,
    description: 'Tìm kiếm ảnh minh họa theo từ khóa trong thư viện hình ảnh Flama.',
    samplePrompt: 'Tìm trong thư viện ảnh xem có hình minh họa cho từ "富士山" (Núi Phú Sĩ) không.',
  },
]

const CATEGORY_FILTERS = [
  { key: 'all', label: 'Tất cả công cụ' },
  { key: 'decks', label: 'Bộ thẻ (Decks)' },
  { key: 'shared', label: 'Chia sẻ & Release' },
  { key: 'notes', label: 'Thẻ & Đồng bộ' },
  { key: 'study', label: 'SRS & Thống kê' },
  { key: 'note_types', label: 'Mẫu Note Types' },
  { key: 'media', label: 'Thư viện ảnh' },
]

export function McpToolsExplorer() {
  const { t } = useTranslation('guide')
  const [copiedName, setCopiedName] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')

  const copyPrompt = async (name: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedName(name)
      window.setTimeout(() => setCopiedName(null), 2000)
      toast.success(`Đã sao chép câu lệnh mẫu cho ${name}.`)
    } catch {
      toast.error('Không thể sao chép.')
    }
  }

  const filteredTools = MCP_TOOLS_CATALOG.filter((tool) => {
    const matchesCategory = selectedCategory === 'all' || tool.category === selectedCategory
    const q = searchQuery.toLowerCase().trim()
    const matchesSearch =
      !q ||
      tool.name.toLowerCase().includes(q) ||
      tool.title.toLowerCase().includes(q) ||
      tool.description.toLowerCase().includes(q) ||
      tool.scope.toLowerCase().includes(q)
    return matchesCategory && matchesSearch
  })

  return (
    <div className="space-y-6 w-full min-w-0">
      <Card className="rounded-2xl border shadow-2xs min-w-0 overflow-hidden">
        <CardHeader className="p-4 sm:p-6 pb-3 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
                <Wrench className="size-5 text-primary shrink-0" />
                <span>{t('mcp.catalog_title')}</span>
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm mt-1">
                AI Assistant sẽ tự động gọi các công cụ này dựa trên câu hỏi hoặc yêu cầu tự nhiên của bạn.
              </CardDescription>
            </div>
            <div className="w-full sm:w-64">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                <Input
                  placeholder={t('mcp.search_tools')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 h-9 text-xs rounded-xl"
                />
              </div>
            </div>
          </div>

          {/* Filter Pills */}
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {CATEGORY_FILTERS.map((filter) => (
              <Button
                key={filter.key}
                type="button"
                variant={selectedCategory === filter.key ? 'default' : 'outline'}
                size="sm"
                className="text-xs h-7 px-2.5 rounded-lg font-medium"
                onClick={() => setSelectedCategory(filter.key)}
              >
                {filter.label}
              </Button>
            ))}
          </div>
        </CardHeader>

        <CardContent className="p-4 sm:p-6 pt-2 space-y-4">
          {!filteredTools.length ? (
            <EmptyState
              title="Không tìm thấy công cụ phù hợp"
              description="Hãy thử đổi từ khóa tìm kiếm hoặc chọn danh mục khác."
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {filteredTools.map((tool) => {
                const Icon = tool.icon
                return (
                  <div
                    key={tool.name}
                    className="rounded-2xl border bg-card p-4 sm:p-5 space-y-3 shadow-2xs hover:border-primary/40 transition-colors flex flex-col justify-between"
                  >
                    <div className="space-y-2.5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2.5">
                          <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary shrink-0">
                            <Icon className="size-4" />
                          </div>
                          <div>
                            <div className="font-bold text-xs sm:text-sm text-foreground">{tool.title}</div>
                            <div className="font-mono text-[11px] text-muted-foreground">{tool.name}</div>
                          </div>
                        </div>
                        <Badge variant="outline" className="font-mono text-[10px] shrink-0">
                          {tool.scope}
                        </Badge>
                      </div>

                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {tool.description}
                      </p>
                    </div>

                    <div className="space-y-1.5 pt-2 border-t">
                      <div className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1">
                        <MessageSquareCode className="size-3 text-primary" />
                        <span>{t('mcp.sample_prompt')}:</span>
                      </div>
                      <div className="flex items-center justify-between gap-2 bg-muted/40 p-2 rounded-lg border text-xs text-foreground/90 italic">
                        <span className="line-clamp-2">"{tool.samplePrompt}"</span>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="shrink-0 h-7 px-2 text-[11px] gap-1 hover:bg-background"
                          onClick={() => copyPrompt(tool.name, tool.samplePrompt)}
                        >
                          {copiedName === tool.name ? (
                            <Check className="size-3 text-emerald-600" />
                          ) : (
                            <Copy className="size-3" />
                          )}
                          <span>{copiedName === tool.name ? t('article.copied') : t('mcp.copy_prompt')}</span>
                        </Button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
