import { useState } from 'react'
import {
  BookOpen,
  Check,
  CheckCircle2,
  Code,
  Compass,
  Copy,
  Download,
  ExternalLink,
  Flame,
  Globe,
  Heart,
  HelpCircle,
  Info,
  KeyRound,
  MousePointerClick,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Trash2,
  Zap,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { FLAMA_CONNECT_URL } from '@/config/env'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'

type IntegrationToken = {
  id: number
  name: string
  token_prefix: string
  scopes: string[]
  status: 'active' | 'expired' | 'revoked' | string
  expires_at: string | null
  last_used_at: string | null
  created_at: string
  token?: string
}

type TokensResponse = {
  items: IntegrationToken[]
  policy: {
    default_expiry_days: number
    allowed_expiry_days: number[]
    allow_no_expiry: boolean
  }
}

type MarkerCategory = 'term' | 'kanji' | 'both'

interface MarkerItem {
  name: string
  category: MarkerCategory
  description: string
  example?: string
}

const MARKER_LIST: MarkerItem[] = [
  // Term markers
  { name: '{audio}', category: 'term', description: 'Audio âm thanh phát âm của từ vựng từ các nguồn audio khả dụng (nếu có).' },
  { name: '{cloze-body-kana}', category: 'term', description: 'Cách đọc Kana cho từ thể cloze ({cloze-body}).' },
  { name: '{conjugation}', category: 'term', description: 'Chuỗi chia từ (conjugation path) từ từ inflected ban đầu về từ gốc.' },
  { name: '{expression}', category: 'term', description: 'Từ vựng biểu diễn bằng Kanji (nếu không có Kanji sẽ sử dụng Kana). Khuyên dùng làm marker cho trường đầu tiên của thẻ từ vựng.', example: '日本語' },
  { name: '{furigana}', category: 'term', description: 'Từ dạng Kanji có hiển thị Furigana phía trên.', example: '日本語[にほんご]' },
  { name: '{furigana-plain}', category: 'term', description: 'Từ dạng Kanji có hiển thị Furigana bên cạnh trong ngoặc vuông.', example: '日本語[にほんご]' },
  { name: '{glossary}', category: 'term', description: 'Danh sách đầy đủ các nghĩa / định nghĩa của từ vựng.' },
  { name: '{glossary-brief}', category: 'term', description: 'Danh sách định nghĩa của từ ở định dạng ngắn gọn, súc tích hơn.' },
  { name: '{glossary-no-dictionary}', category: 'term', description: 'Danh sách định nghĩa của từ, ngoại trừ nhãn tên từ điển bị ẩn.' },
  { name: '{glossary-first}', category: 'term', description: 'Định nghĩa đầu tiên của từ vựng.' },
  { name: '{glossary-plain}', category: 'term', description: 'Danh sách định nghĩa của từ chỉ sử dụng HTML cho các đoạn ngắt dòng.' },
  { name: '{glossary-plain-no-dictionary}', category: 'term', description: '{glossary-plain} ngoại trừ nhãn tên từ điển bị ẩn.' },
  { name: '{glossary-first-brief}', category: 'term', description: 'Định nghĩa đầu tiên của từ ở định dạng ngắn gọn hơn.' },
  { name: '{glossary-first-no-dictionary}', category: 'term', description: 'Định nghĩa đầu tiên của từ, ngoại trừ nhãn từ điển bị ẩn.' },
  { name: '{part-of-speech}', category: 'term', description: 'Thông tin từ loại của từ (Danh từ, Động từ, Tính từ,...).' },
  { name: '{phonetic-transcriptions}', category: 'term', description: 'Danh sách phiên âm ngữ âm cho từ vựng.' },
  { name: '{pitch-accents}', category: 'term', description: 'Danh sách ký hiệu hạ giọng trọng âm (downstep notations) cho từ.' },
  { name: '{pitch-accent-graphs}', category: 'term', description: 'Danh sách biểu đồ trọng âm (pitch accent graphs) cho từ.' },
  { name: '{pitch-accent-graphs-jj}', category: 'term', description: 'Danh sách biểu đồ trọng âm cho từ (được thiết kế theo phong cách Jidoujisho).' },
  { name: '{pitch-accent-positions}', category: 'term', description: 'Danh sách các vị trí hạ giọng trọng âm của từ ở dạng số.' },
  { name: '{pitch-accent-categories}', category: 'term', description: 'Danh sách phân loại nhóm trọng âm của từ (ví dụ: heiban, kifuku, atamadaka, odaka, nakadaka).' },
  { name: '{reading}', category: 'term', description: 'Cách đọc Kana cho từ, hoặc để trống đối với các từ mà biểu thức (expression) chính là cách đọc.', example: 'にほんご' },
  { name: '{single-glossary-DICT-NAME}', category: 'term', description: 'Tương tự {glossary}, nhưng chỉ lấy nội dung từ một từ điển duy nhất. Tên từ điển có thể cần điều chỉnh theo tùy chọn menu.' },
  { name: '{single-glossary-DICT-NAME-brief}', category: 'term', description: 'Xem {single-glossary-DICT-NAME} và {glossary-brief}.' },
  { name: '{single-glossary-DICT-NAME-no-dictionary}', category: 'term', description: 'Xem {single-glossary-DICT-NAME} và {glossary-no-dictionary}.' },
  { name: '{single-glossary-DICT-NAME-plain}', category: 'term', description: 'Xem {single-glossary-DICT-NAME} và {glossary-plain}.' },
  { name: '{single-glossary-DICT-NAME-plain-no-dictionary}', category: 'term', description: 'Xem {single-glossary-DICT-NAME} và {glossary-plain-no-dictionary}.' },
  { name: '{tags}', category: 'term', description: 'Thẻ ngữ pháp và cách sử dụng cung cấp thông tin chi tiết về từ.' },

  // Kanji markers
  { name: '{character}', category: 'kanji', description: 'Ký tự Unicode đại diện cho chữ Hán (Kanji) hiện tại. Khuyên dùng làm marker cho trường đầu tiên của thẻ Kanji.', example: '日' },
  { name: '{glossary}', category: 'kanji', description: 'Danh sách nghĩa / định nghĩa của chữ Hán.' },
  { name: '{kunyomi}', category: 'kanji', description: 'Cách đọc Kunyomi (âm Nhật) của chữ Hán, thể hiện bằng Hiragana.', example: 'ひ, び, か' },
  { name: '{onyomi}', category: 'kanji', description: 'Cách đọc Onyomi (âm Hán) của chữ Hán, thể hiện bằng Katakana.', example: 'ニチ, ジツ' },
  { name: '{onyomi-hiragana}', category: 'kanji', description: 'Cách đọc Onyomi (âm Hán) của chữ Hán, thể hiện bằng Hiragana.', example: 'にち, じつ' },
  { name: '{stroke-count}', category: 'kanji', description: 'Số nét vẽ của ký tự chữ Hán.', example: '4' },

  // Both markers
  { name: '{clipboard-image}', category: 'both', description: 'Hình ảnh được lưu trong bộ nhớ tạm (clipboard) của hệ thống (nếu có).' },
  { name: '{clipboard-text}', category: 'both', description: 'Đoạn văn bản được lưu trong bộ nhớ tạm (clipboard) của hệ thống (nếu có).' },
  { name: '{cloze-body}', category: 'both', description: 'Từ vựng dạng bị biến đổi ban đầu như khi xuất hiện trước khi được Yomitan đưa về dạng từ điển.' },
  { name: '{cloze-prefix}', category: 'both', description: 'Trích đoạn của câu {sentence} tính từ đầu câu cho đến trước {cloze-body}.' },
  { name: '{cloze-suffix}', category: 'both', description: 'Trích đoạn của câu {sentence} tính từ sau {cloze-body} cho đến hết câu.' },
  { name: '{dictionary}', category: 'both', description: 'Tên gốc của từ điển tạo nên thẻ ghi nhớ.' },
  { name: '{dictionary-alias}', category: 'both', description: 'Tên hiển thị của từ điển tạo nên thẻ ghi nhớ.' },
  { name: '{document-title}', category: 'both', description: 'Tiêu đề trang web nơi từ vựng hoặc chữ Hán xuất hiện.' },
  { name: '{frequencies}', category: 'both', description: 'Thông tin tần suất xuất hiện / độ phổ biến của từ vựng hoặc chữ Hán.' },
  { name: '{frequency-harmonic-rank}', category: 'both', description: 'Thứ hạng trung bình điều hòa về độ phổ biến. Mặc định là 9999999 khi không tìm thấy dữ liệu (mức độ sử dụng cực thấp).' },
  { name: '{frequency-harmonic-occurrence}', category: 'both', description: 'Số lần xuất hiện trung bình điều hòa. Mặc định là 0 khi không tìm thấy dữ liệu (mức độ sử dụng cực thấp).' },
  { name: '{frequency-average-rank}', category: 'both', description: 'Thứ hạng trung bình cộng về độ phổ biến. Mặc định là 9999999 khi không tìm thấy dữ liệu.' },
  { name: '{frequency-average-occurrence}', category: 'both', description: 'Số lần xuất hiện trung bình cộng. Mặc định là 0 khi không tìm thấy dữ liệu.' },
  { name: '{single-frequency-DICT-NAME}', category: 'both', description: 'Tất cả dữ liệu tần suất từ từ điển được chọn dưới dạng danh sách.' },
  { name: '{single-frequency-number-DICT-NAME}', category: 'both', description: 'Con số tần suất đơn từ từ điển được chọn không kèm định dạng dữ liệu.' },
  { name: '{screenshot}', category: 'both', description: 'Ảnh chụp màn hình trang web tại thời điểm từ vựng hoặc chữ Hán được thêm vào.' },
  { name: '{search-query}', category: 'both', description: 'Truy vấn tìm kiếm đầy đủ được hiển thị trên trang tìm kiếm hoặc popup.' },
  { name: '{popup-selection-text}', category: 'both', description: 'Đoạn văn bản đang được chọn / bôi đen trên trang tìm kiếm hoặc popup.' },
  { name: '{sentence}', category: 'both', description: 'Câu văn, trích dẫn hoặc cụm từ chứa từ vựng/chữ Hán từ nội dung nguồn.' },
  { name: '{sentence-furigana}', category: 'both', description: 'Câu văn hoặc trích dẫn chứa từ/Kanji có thêm Furigana dạng HTML.' },
  { name: '{sentence-furigana-plain}', category: 'both', description: 'Câu văn hoặc trích dẫn chứa từ/Kanji có thêm Furigana trong dấu ngoặc vuông [...].' },
  { name: '{url}', category: 'both', description: 'Địa chỉ URL của trang web nơi từ vựng hoặc chữ Hán xuất hiện.' },
  { name: '{url-plain}', category: 'both', description: 'Địa chỉ URL thô ({url}) không chứa HTML.' },
]

function displayDate(value: string | null) {
  return value ? new Date(value).toLocaleString('vi-VN') : 'Không hết hạn'
}

export function YomitanTokensPage() {
  const queryClient = useQueryClient()
  const queryKey = ['integration-tokens'] as const
  const [name, setName] = useState('Yomitan - PC cá nhân')
  const [expiry, setExpiry] = useState('180')
  const [issued, setIssued] = useState<IntegrationToken | null>(null)
  const [copied, setCopied] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('about')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'term' | 'kanji' | 'both'>('all')

  const issuedConnectUrl = issued?.token
    ? `${FLAMA_CONNECT_URL.replace(/\/+$/, '')}/${encodeURIComponent(issued.token)}`
    : null

  const query = useQuery({
    queryKey,
    queryFn: () => appApi.get<TokensResponse>('/integration-tokens'),
  })

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey })
  }

  const createMutation = useMutation({
    mutationFn: () => appApi.mutate<{ item: IntegrationToken }>('/integration-tokens', 'POST', {
      name: name.trim(),
      expires_in_days: expiry === 'none' ? null : Number(expiry),
    }),
    onSuccess: async ({ item }) => {
      setIssued(item)
      await refresh()
      toast.success('Đã tạo token Flama Connect thành công.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const revokeMutation = useMutation({
    mutationFn: (id: number) => appApi.mutate(`/integration-tokens/${id}`, 'DELETE'),
    onSuccess: async () => {
      await refresh()
      toast.success('Token đã được thu hồi ngay lập tức.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const rotateMutation = useMutation({
    mutationFn: (id: number) => appApi.mutate<{ item: IntegrationToken }>(`/integration-tokens/${id}/rotate`, 'POST', {
      expires_in_days: expiry === 'none' ? null : Number(expiry),
    }),
    onSuccess: async ({ item }) => {
      setIssued(item)
      await refresh()
      toast.success('Đã thu hồi token cũ và tạo token mới.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const copy = async (label: string, value: string) => {
    await navigator.clipboard.writeText(value)
    setCopied(label)
    window.setTimeout(() => setCopied(null), 1800)
    toast.success(`Đã sao chép ${label.startsWith('{') ? label : ''} vào bộ nhớ tạm.`)
  }

  const filteredMarkers = MARKER_LIST.filter((m) => {
    const matchesCategory = selectedCategory === 'all' || m.category === selectedCategory
    const q = searchQuery.trim().toLowerCase()
    const matchesSearch =
      !q ||
      m.name.toLowerCase().includes(q) ||
      m.description.toLowerCase().includes(q) ||
      (m.example && m.example.toLowerCase().includes(q))
    return matchesCategory && matchesSearch
  })

  const countTerm = MARKER_LIST.filter((m) => m.category === 'term').length
  const countKanji = MARKER_LIST.filter((m) => m.category === 'kanji').length
  const countBoth = MARKER_LIST.filter((m) => m.category === 'both').length

  if (query.isPending) return <PageLoading label="Đang tải token Yomitan…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="max-w-7xl mx-auto space-y-8 pb-12">
      {/* Header & Feature Highlights Bar */}
      <div className="space-y-6">
        <PageHeader
          title="Kết nối Yomitan & Flama Connect"
          description="Tích hợp tiện ích tra từ Yomitan trên trình duyệt với Flama để tự động tạo Flashcard chỉ với 1 cú nhấp chuột."
        />

        {/* Quick Highlights Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="flex items-center gap-3 p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-xs">
            <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <Zap className="size-5" />
            </div>
            <div>
              <div className="text-xs font-semibold">Tra từ 0.1s</div>
              <div className="text-[11px] text-muted-foreground">Popup ngay khi di chuột</div>
            </div>
          </div>

          <div className="flex items-center gap-3 p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-xs">
            <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <MousePointerClick className="size-5" />
            </div>
            <div>
              <div className="text-xs font-semibold">Tạo thẻ 1-Click</div>
              <div className="text-[11px] text-muted-foreground">Tự động điền thông tin</div>
            </div>
          </div>

          <div className="flex items-center gap-3 p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-xs">
            <div className="p-2.5 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400">
              <Globe className="size-5" />
            </div>
            <div>
              <div className="text-xs font-semibold">Đắm mình Immersion</div>
              <div className="text-[11px] text-muted-foreground">Đọc báo, manga, anime sub</div>
            </div>
          </div>

          <div className="flex items-center gap-3 p-3.5 rounded-xl border bg-card/60 backdrop-blur-sm shadow-xs">
            <div className="p-2.5 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400">
              <Flame className="size-5" />
            </div>
            <div>
              <div className="text-xs font-semibold">Flama Connect</div>
              <div className="text-[11px] text-muted-foreground">Kết nối siêu tốc 1-Click</div>
            </div>
          </div>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full space-y-6">
        {/* Responsive Horizontal Scroll Tab Bar */}
        <div className="overflow-x-auto pb-1 -mx-1 px-1 no-scrollbar">
          <TabsList className="inline-flex w-auto min-w-full sm:min-w-0 p-1.5 bg-muted/60 backdrop-blur-md rounded-2xl gap-1">
            <TabsTrigger value="about" className="px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-2 transition-all">
              <Sparkles className="size-4 text-amber-500" /> Yomitan là gì? (Khuyên dùng)
            </TabsTrigger>
            <TabsTrigger value="tokens" className="px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-2 transition-all">
              <KeyRound className="size-4 text-primary" /> Quản lý Token
            </TabsTrigger>
            <TabsTrigger value="guide" className="px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-2 transition-all">
              <BookOpen className="size-4 text-sky-500" /> Hướng dẫn Cài đặt
            </TabsTrigger>
            <TabsTrigger value="markers" className="px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-2 transition-all">
              <Code className="size-4 text-purple-500" /> Field Markers ({MARKER_LIST.length})
            </TabsTrigger>
          </TabsList>
        </div>

        {/* TAB 0: ABOUT YOMITAN & RECOMMENDED */}
        <TabsContent value="about" className="space-y-6">
          <Card className="overflow-hidden border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-background to-primary/5 shadow-md">
            <CardHeader className="p-6 md:p-8 space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="default" className="bg-amber-500 hover:bg-amber-600 text-white font-semibold px-3 py-1 text-xs gap-1.5 shadow-xs">
                  <Heart className="size-3.5 fill-current" /> Highly Recommended (おすすめ - Khuyên dùng)
                </Badge>
                <Badge variant="outline" className="text-xs border-amber-500/40 text-amber-700 dark:text-amber-300">
                  Must-have extension cho người học tiếng Nhật
                </Badge>
              </div>
              <div className="space-y-2">
                <CardTitle className="text-2xl md:text-3xl font-bold tracking-tight flex items-center gap-3">
                  <Compass className="size-8 text-primary shrink-0" />
                  <span>Tiện ích Yomitan & Công cụ đắm mình tiếng Nhật</span>
                </CardTitle>
                <CardDescription className="text-sm md:text-base leading-relaxed max-w-4xl text-muted-foreground">
                  Yomitan là tiện ích mở rộng (browser extension) tra từ pop-up tốc độ cao trên trình duyệt web, là phiên bản kế thừa nâng cấp và duy trì tích cực của <strong>Yomichan</strong> huyền thoại.
                </CardDescription>
              </div>
            </CardHeader>

            <CardContent className="p-6 md:p-8 pt-0 space-y-8">
              {/* Feature Cards Grid */}
              <div className="space-y-4">
                <h3 className="font-bold text-base md:text-lg flex items-center gap-2 text-foreground">
                  <Zap className="size-5 text-amber-500" /> Tại sao bạn RẤT NÊN DÙNG Yomitan khi học tiếng Nhật?
                </h3>

                <div className="grid gap-5 md:grid-cols-3">
                  <div className="group rounded-2xl border bg-card/90 p-5 space-y-3 shadow-xs hover:shadow-md hover:border-amber-500/40 transition-all">
                    <div className="p-3 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 w-fit group-hover:scale-105 transition-transform">
                      <MousePointerClick className="size-6" />
                    </div>
                    <div className="font-bold text-base">Tra từ siêu tốc 0.1s</div>
                    <p className="text-xs md:text-sm text-muted-foreground leading-relaxed">
                      Rê chuột (hover) lên từ tiếng Nhật trên bất kỳ trang web nào (báo chí NHK, manga, sub anime web, blog), cửa sổ popup sẽ hiện ngay Furigana, nghĩa Hán Việt/Anh, phiên âm và âm thanh MP3.
                    </p>
                  </div>

                  <div className="group rounded-2xl border bg-card/90 p-5 space-y-3 shadow-xs hover:shadow-md hover:border-emerald-500/40 transition-all">
                    <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 w-fit group-hover:scale-105 transition-transform">
                      <CheckCircle2 className="size-6" />
                    </div>
                    <div className="font-bold text-base">Tạo Flashcard 1-Click</div>
                    <p className="text-xs md:text-sm text-muted-foreground leading-relaxed">
                      Nhấp nút <strong>+</strong> trong cửa sổ tra từ, toàn bộ từ vựng, Kana, nghĩa, phát âm audio MP3 và câu ví dụ trên trang web tự động gửi thẳng vào Deck Flama của bạn qua Flama Connect.
                    </p>
                  </div>

                  <div className="group rounded-2xl border bg-card/90 p-5 space-y-3 shadow-xs hover:shadow-md hover:border-sky-500/40 transition-all">
                    <div className="p-3 rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400 w-fit group-hover:scale-105 transition-transform">
                      <Globe className="size-6" />
                    </div>
                    <div className="font-bold text-base">Học Đắm mình (Immersion)</div>
                    <p className="text-xs md:text-sm text-muted-foreground leading-relaxed">
                      Không còn ngắt quãng tư duy do gõ tay từng từ vào ứng dụng tra từ điển. Giúp bạn tự tin đọc và thưởng thức nội dung tiếng Nhật thực tế của người bản xứ mỗi ngày.
                    </p>
                  </div>
                </div>
              </div>

              {/* Download Buttons Section */}
              <div className="rounded-2xl border bg-card p-6 space-y-4 shadow-xs">
                <div className="space-y-1">
                  <h4 className="font-bold text-base flex items-center gap-2">
                    <Download className="size-5 text-primary" /> Hướng dẫn Tải & Cài đặt Yomitan
                  </h4>
                  <p className="text-xs text-muted-foreground">Chọn trình duyệt bạn đang sử dụng để cài đặt extension Yomitan chính thức:</p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <a
                    href="https://chromewebstore.google.com/detail/yomitan/gkgemgainhhaloainhgfppmadnhpikan"
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between rounded-xl border p-4 bg-background hover:border-primary hover:bg-primary/5 hover:shadow-sm transition-all group"
                  >
                    <div className="space-y-0.5">
                      <div className="font-semibold text-sm group-hover:text-primary transition-colors">Chrome / Edge / Brave</div>
                      <div className="text-xs text-muted-foreground">Chrome Web Store</div>
                    </div>
                    <ExternalLink className="size-4 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                  </a>

                  <a
                    href="https://addons.mozilla.org/en-US/firefox/addon/yomitan/"
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between rounded-xl border p-4 bg-background hover:border-primary hover:bg-primary/5 hover:shadow-sm transition-all group"
                  >
                    <div className="space-y-0.5">
                      <div className="font-semibold text-sm group-hover:text-primary transition-colors">Mozilla Firefox</div>
                      <div className="text-xs text-muted-foreground">Firefox Add-ons</div>
                    </div>
                    <ExternalLink className="size-4 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                  </a>

                  <a
                    href="https://github.com/yomitan-dev/yomitan"
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between rounded-xl border p-4 bg-background hover:border-primary hover:bg-primary/5 hover:shadow-sm transition-all group"
                  >
                    <div className="space-y-0.5">
                      <div className="font-semibold text-sm group-hover:text-primary transition-colors">Mã nguồn GitHub</div>
                      <div className="text-xs text-muted-foreground">yomitan-dev/yomitan</div>
                    </div>
                    <ExternalLink className="size-4 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                  </a>
                </div>
              </div>

              {/* Next Steps CTA */}
              <div className="rounded-2xl border bg-muted/30 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1">
                  <h4 className="font-bold text-base flex items-center gap-2">
                    <BookOpen className="size-5 text-primary" /> Bạn đã tải Yomitan thành công?
                  </h4>
                  <p className="text-xs md:text-sm text-muted-foreground">
                    Bước tiếp theo là tạo API Token và cấu hình Server URL trong Yomitan để bắt đầu bắn từ vựng sang Flama.
                  </p>
                </div>
                <Button size="lg" className="shrink-0 font-semibold shadow-xs" onClick={() => setActiveTab('tokens')}>
                  <KeyRound className="mr-2 size-5" /> Sang Quản lý Token ngay
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 1: TOKENS MANAGEMENT */}
        <TabsContent value="tokens" className="space-y-6">
          <Card className="shadow-xs">
            <CardHeader className="p-6">
              <CardTitle className="text-lg font-bold">Tạo API Token Flama Connect</CardTitle>
              <CardDescription className="text-xs md:text-sm">
                Mỗi thiết bị hoặc trình duyệt nên dùng 1 token riêng để dễ dàng theo dõi và thu hồi bảo mật khi cần thiết.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-6 pt-0 space-y-6">
              <div className="grid gap-4 md:grid-cols-[1fr_240px_auto] md:items-end">
                <div className="space-y-2">
                  <Label htmlFor="connect-token-name" className="text-xs font-semibold">Tên thiết bị / Trình duyệt</Label>
                  <Input
                    id="connect-token-name"
                    value={name}
                    maxLength={120}
                    placeholder="Ví dụ: Yomitan - Chrome PC"
                    className="h-10"
                    onChange={(event) => setName(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="connect-token-expiry" className="text-xs font-semibold">Thời hạn hiệu lực</Label>
                  <NativeSelect
                    id="connect-token-expiry"
                    className="w-full h-10"
                    value={expiry}
                    onChange={(event) => setExpiry(event.target.value)}
                  >
                    <NativeSelectOption value="30">30 ngày</NativeSelectOption>
                    <NativeSelectOption value="90">90 ngày</NativeSelectOption>
                    <NativeSelectOption value="180">180 ngày (mặc định)</NativeSelectOption>
                    <NativeSelectOption value="365">365 ngày</NativeSelectOption>
                    <NativeSelectOption value="none">Không hết hạn</NativeSelectOption>
                  </NativeSelect>
                </div>
                <Button h-10 size="lg" disabled={!name.trim() || createMutation.isPending} onClick={() => createMutation.mutate()}>
                  <KeyRound className="mr-2 size-4" /> Tạo token mới
                </Button>
              </div>

              <Alert className="border-sky-500/30 bg-sky-50/50 dark:bg-sky-950/20">
                <ShieldAlert className="size-4 text-sky-600 dark:text-sky-400" />
                <AlertTitle className="text-sky-900 dark:text-sky-200 text-sm font-semibold">Cấu hình nhanh trong Yomitan</AlertTitle>
                <AlertDescription className="mt-1 text-xs text-sky-800 dark:text-sky-300">
                  Tạo token rồi dán toàn bộ URL được cấp vào ô <strong>Server URL</strong> trong phần tích hợp của Yomitan (không cần nhập API Key riêng). Xem hướng dẫn chi tiết tại tab <strong>Hướng dẫn Cài đặt</strong>.
                </AlertDescription>
              </Alert>

              {issuedConnectUrl ? (
                <Alert className="border-amber-500/50 bg-amber-50 dark:bg-amber-950/30 p-4">
                  <ShieldAlert className="size-5 text-amber-600 dark:text-amber-400 shrink-0" />
                  <div className="space-y-2 w-full">
                    <AlertTitle className="text-amber-900 dark:text-amber-200 font-bold text-sm">
                      Sao chép URL này ngay — Flama sẽ không hiển thị lại URL đầy đủ sau khi bạn rời trang!
                    </AlertTitle>
                    <AlertDescription className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-1">
                      <code className="min-w-0 flex-1 break-all rounded-lg border bg-background p-3 text-xs font-mono select-all">
                        {issuedConnectUrl}
                      </code>
                      <Button variant="default" className="shrink-0 bg-amber-600 hover:bg-amber-700 text-white" onClick={() => copy('connect-url', issuedConnectUrl)}>
                        {copied === 'connect-url' ? <Check className="mr-2 size-4 text-white" /> : <Copy className="mr-2 size-4" />}
                        {copied === 'connect-url' ? 'Đã sao chép' : 'Sao chép URL'}
                      </Button>
                    </AlertDescription>
                  </div>
                </Alert>
              ) : null}
            </CardContent>
          </Card>

          {/* Tokens List */}
          <Card className="shadow-xs">
            <CardHeader className="p-6 flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-lg font-bold">Danh sách Token đã tạo</CardTitle>
                <CardDescription className="text-xs">Các API Key đang hoạt động hoặc đã thu hồi của tài khoản</CardDescription>
              </div>
              <Button size="sm" variant="outline" onClick={refresh} title="Tải lại danh sách">
                <RefreshCw className="size-3.5 mr-1" /> Làm mới
              </Button>
            </CardHeader>
            <CardContent className="p-6 pt-0">
              {!query.data.items.length ? (
                <EmptyState title="Chưa có token Yomitan" description="Hãy tạo token đầu tiên để kết nối tiện ích Yomitan với Flama." />
              ) : (
                <div className="overflow-x-auto rounded-xl border">
                  <Table>
                    <TableHeader className="bg-muted/50">
                      <TableRow>
                        <TableHead>Tên thiết bị</TableHead>
                        <TableHead>Trạng thái</TableHead>
                        <TableHead>Hết hạn</TableHead>
                        <TableHead>Lần dùng gần nhất</TableHead>
                        <TableHead className="text-right">Thao tác</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {query.data.items.map((token) => (
                        <TableRow key={token.id} className="hover:bg-muted/30">
                          <TableCell>
                            <div className="font-semibold text-sm">{token.name}</div>
                            <code className="text-[11px] text-muted-foreground">{token.token_prefix}…</code>
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                token.status === 'active'
                                  ? 'default'
                                  : token.status === 'revoked'
                                  ? 'destructive'
                                  : 'secondary'
                              }
                              className="text-[11px]"
                            >
                              {token.status === 'active' ? 'Đang hoạt động' : token.status === 'revoked' ? 'Đã thu hồi' : token.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs">{displayDate(token.expires_at)}</TableCell>
                          <TableCell className="text-xs">
                            {token.last_used_at ? displayDate(token.last_used_at) : 'Chưa từng sử dụng'}
                          </TableCell>
                          <TableCell className="text-right">
                            {token.status === 'active' ? (
                              <div className="flex justify-end gap-1">
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  disabled={rotateMutation.isPending}
                                  onClick={() =>
                                    window.confirm('Thu hồi token cũ và tạo token mới với tên này?') &&
                                    rotateMutation.mutate(token.id)
                                  }
                                >
                                  <RefreshCw className="mr-1 size-3.5 text-muted-foreground" /> Tạo lại
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="text-destructive hover:text-destructive hover:bg-destructive/10"
                                  disabled={revokeMutation.isPending}
                                  onClick={() =>
                                    window.confirm('Bạn có chắc chắn muốn thu hồi token này ngay lập tức?') &&
                                    revokeMutation.mutate(token.id)
                                  }
                                >
                                  <Trash2 className="mr-1 size-3.5" /> Thu hồi
                                </Button>
                              </div>
                            ) : null}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 2: GUIDELINES */}
        <TabsContent value="guide" className="space-y-6">
          <Card className="shadow-xs">
            <CardHeader className="p-6">
              <CardTitle className="text-xl font-bold flex items-center gap-2">
                <Sparkles className="size-5 text-primary" /> Hướng dẫn kết nối Yomitan với Flama Connect
              </CardTitle>
              <CardDescription className="text-xs md:text-sm">
                Flama Connect cho phép tự động gửi từ vựng, Kana, nghĩa, âm thanh MP3 và câu ví dụ từ tiện ích Yomitan trực tiếp vào bộ thẻ Flama của bạn.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-6 pt-0 space-y-8">
              {/* Step Flow */}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-2xl border bg-card p-5 space-y-3 relative">
                  <div className="flex items-center gap-3">
                    <span className="flex size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground text-sm font-bold shadow-xs">1</span>
                    <span className="font-bold text-sm">Tạo API Token</span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Vào tab <strong>Quản lý Token</strong>, nhập tên thiết bị (vd: <em>Chrome PC</em>), bấm <strong>Tạo token mới</strong> và sao chép đường dẫn Server URL.
                  </p>
                </div>

                <div className="rounded-2xl border bg-card p-5 space-y-3 relative">
                  <div className="flex items-center gap-3">
                    <span className="flex size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground text-sm font-bold shadow-xs">2</span>
                    <span className="font-bold text-sm">Cài đặt Yomitan</span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Mở tiện ích Yomitan trên thanh công cụ trình duyệt &rarr; bấm <strong>Settings</strong> (Cài đặt) &rarr; cuộn xuống phần <strong>Integration / Connect</strong>.
                  </p>
                </div>

                <div className="rounded-2xl border bg-card p-5 space-y-3 relative">
                  <div className="flex items-center gap-3">
                    <span className="flex size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground text-sm font-bold shadow-xs">3</span>
                    <span className="font-bold text-sm">Dán Server URL</span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Bật công tắc <strong>Enable integration / Custom server</strong>. Tại ô <strong>Server URL</strong>, dán URL đã copy ở Bước 1. *(Không cần nhập API key riêng)*.
                  </p>
                </div>

                <div className="rounded-2xl border bg-card p-5 space-y-3 relative">
                  <div className="flex items-center gap-3">
                    <span className="flex size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground text-sm font-bold shadow-xs">4</span>
                    <span className="font-bold text-sm">Cấu hình & Tạo thẻ</span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Mở <strong>Configure card templates...</strong> để gán các Field Markers vào các trường của Deck. Khi tra từ, bấm <strong>+</strong> để tạo thẻ lập tức!
                  </p>
                </div>
              </div>

              {/* Unique first field rule */}
              <Alert className="border-blue-500/30 bg-blue-50/50 dark:bg-blue-950/20 p-5 rounded-2xl">
                <Info className="size-5 text-blue-600 dark:text-blue-400 shrink-0" />
                <div className="space-y-2">
                  <AlertTitle className="text-blue-900 dark:text-blue-200 font-bold text-sm">
                    Quy tắc trường đầu tiên (Unique First Field Requirement)
                  </AlertTitle>
                  <AlertDescription className="text-xs text-blue-800 dark:text-blue-300 leading-relaxed">
                    Hệ thống yêu cầu <strong>trường đầu tiên (first field)</strong> của mẫu thẻ phải chứa giá trị duy nhất để phòng tránh tạo các thẻ ghi nhớ trùng lặp:
                    <ul className="mt-2 list-disc list-inside space-y-1 font-medium">
                      <li>Đối với thẻ từ vựng (Terms): Khuyên dùng marker <code className="bg-background px-1.5 py-0.5 rounded text-foreground font-mono">{'{expression}'}</code> cho trường đầu tiên.</li>
                      <li>Đối với thẻ chữ Hán (Kanji): Khuyên dùng marker <code className="bg-background px-1.5 py-0.5 rounded text-foreground font-mono">{'{character}'}</code> cho trường đầu tiên.</li>
                    </ul>
                  </AlertDescription>
                </div>
              </Alert>

              {/* Media Constraints & Security */}
              <div className="rounded-2xl border p-5 space-y-3 bg-card">
                <h4 className="font-bold text-sm flex items-center gap-2">
                  <HelpCircle className="size-4 text-muted-foreground" /> Lưu ý về Media & Bảo mật
                </h4>
                <ul className="text-xs text-muted-foreground space-y-2 list-disc list-inside leading-relaxed">
                  <li>
                    <strong>Âm thanh phát âm (Audio):</strong> Flama Connect tự động tiếp nhận file MP3 phát âm dung lượng tối đa <strong>1 MB</strong> gửi từ Yomitan.
                  </li>
                  <li>
                    <strong>Hình ảnh & Video:</strong> Hiện chưa hỗ trợ nhúng tự động ảnh chụp/video qua webhook Flama Connect.
                  </li>
                  <li>
                    <strong>Bảo mật Token:</strong> Server URL chứa token riêng tư của bạn. Hãy bảo vệ URL và thu hồi ngay nếu nghi ngờ lộ URL.
                  </li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 3: FIELD MARKERS REFERENCE */}
        <TabsContent value="markers" className="space-y-6">
          <Card className="shadow-xs">
            <CardHeader className="p-6 space-y-4">
              <div>
                <CardTitle className="text-xl font-bold flex items-center gap-2">
                  <Code className="size-5 text-purple-500" /> Tra cứu Field Markers Yomitan & Flama
                </CardTitle>
                <CardDescription className="text-xs md:text-sm">
                  Khi tạo thẻ, Yomitan sẽ tự động thế các Field Markers dưới đây bằng thông tin tra cứu thực tế từ từ điển đã cài. Nhấp vào bất kỳ marker nào để sao chép nhanh!
                </CardDescription>
              </div>

              {/* Search bar & Category Filters */}
              <div className="flex flex-col md:flex-row gap-3 pt-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                  <Input
                    placeholder="Tìm kiếm marker ({expression}, furigana, audio, sentence...)"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10 h-10 rounded-xl"
                  />
                </div>
                <div className="flex gap-1.5 overflow-x-auto pb-1 md:pb-0 no-scrollbar">
                  <Button
                    size="sm"
                    variant={selectedCategory === 'all' ? 'default' : 'outline'}
                    onClick={() => setSelectedCategory('all')}
                    className="rounded-xl"
                  >
                    Tất cả ({MARKER_LIST.length})
                  </Button>
                  <Button
                    size="sm"
                    variant={selectedCategory === 'term' ? 'default' : 'outline'}
                    onClick={() => setSelectedCategory('term')}
                    className="rounded-xl"
                  >
                    Từ vựng ({countTerm})
                  </Button>
                  <Button
                    size="sm"
                    variant={selectedCategory === 'kanji' ? 'default' : 'outline'}
                    onClick={() => setSelectedCategory('kanji')}
                    className="rounded-xl"
                  >
                    Chữ Hán ({countKanji})
                  </Button>
                  <Button
                    size="sm"
                    variant={selectedCategory === 'both' ? 'default' : 'outline'}
                    onClick={() => setSelectedCategory('both')}
                    className="rounded-xl"
                  >
                    Dùng chung ({countBoth})
                  </Button>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-6 pt-0">
              {!filteredMarkers.length ? (
                <EmptyState
                  title="Không tìm thấy marker phù hợp"
                  description="Hãy thử thay đổi từ khóa tìm kiếm hoặc chọn danh mục khác."
                />
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {filteredMarkers.map((marker) => (
                    <div
                      key={marker.name}
                      onClick={() => copy(marker.name, marker.name)}
                      className="group relative flex flex-col justify-between gap-3 rounded-2xl border bg-card p-4 transition-all hover:border-purple-500/50 hover:shadow-md cursor-pointer"
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <code className="font-mono text-sm font-bold text-purple-600 dark:text-purple-400 bg-purple-500/10 px-2.5 py-1 rounded-lg group-hover:bg-purple-600 group-hover:text-white transition-colors">
                            {marker.name}
                          </code>
                          <Badge
                            variant="outline"
                            className="text-[10px] uppercase font-semibold tracking-wide shrink-0"
                          >
                            {marker.category === 'term'
                              ? 'Từ vựng'
                              : marker.category === 'kanji'
                              ? 'Chữ Hán'
                              : 'Dùng chung'}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed">{marker.description}</p>
                      </div>

                      {marker.example ? (
                        <div className="pt-2 border-t flex items-center justify-between text-[11px] text-muted-foreground">
                          <span>Ví dụ: <code className="text-foreground bg-muted px-1.5 py-0.5 rounded font-mono">{marker.example}</code></span>
                          <span className="text-xs opacity-80 group-hover:opacity-100 transition-opacity text-purple-600 dark:text-purple-400 font-semibold flex items-center gap-1">
                            {copied === marker.name ? <Check className="size-3 text-green-600" /> : <Copy className="size-3" />}
                            {copied === marker.name ? 'Đã chép' : 'Sao chép'}
                          </span>
                        </div>
                      ) : (
                        <div className="flex justify-end text-[11px] pt-1">
                          <span className="text-xs opacity-80 group-hover:opacity-100 transition-opacity text-purple-600 dark:text-purple-400 font-semibold flex items-center gap-1">
                            {copied === marker.name ? <Check className="size-3 text-green-600" /> : <Copy className="size-3" />}
                            {copied === marker.name ? 'Đã chép' : 'Sao chép'}
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </Page>
  )
}
