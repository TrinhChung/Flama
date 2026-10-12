import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  ArrowRight,
  Check,
  Clapperboard,
  Cloud,
  Code,
  Copy,
  Download,
  ExternalLink,
  Film,
  Heart,
  Info,
  KeyRound,
  Layers,
  Play,
  RotateCw,
  Sparkles,
  Subtitles,
  Volume2,
  Zap,
} from 'lucide-react'

interface CanonicalFieldMapping {
  asbField: string
  flamaField: string
  dataType: string
  role: string
  description: string
  isPrimary?: boolean
}

const CANONICAL_FIELD_MAPPINGS: CanonicalFieldMapping[] = [
  {
    asbField: 'Sentence',
    flamaField: 'Sentence',
    dataType: 'Text',
    role: 'Primary (Required)',
    description: 'Câu thoại tiếng Nhật chứa trong phụ đề video (Dùng để định danh chống trùng lặp)',
    isPrimary: true,
  },
  {
    asbField: 'Word',
    flamaField: 'Word',
    dataType: 'Text',
    role: 'Target Vocabulary',
    description: 'Từ vựng trọng tâm cần học (tự động điền khi rê chuột tra từ bằng Yomitan trên phụ đề)',
  },
  {
    asbField: 'Definition',
    flamaField: 'Definition',
    dataType: 'Text',
    role: 'Glossary / Meaning',
    description: 'Nghĩa tiếng Việt hoặc tiếng Anh của từ vựng trích xuất từ từ điển popup Yomitan',
  },
  {
    asbField: 'Image',
    flamaField: 'Image',
    dataType: 'Image (PNG/WebP)',
    role: 'Video Screenshot',
    description: 'Ảnh chụp màn hình video đúng thời điểm phát câu thoại (tự động tối ưu dung lượng)',
  },
  {
    asbField: 'Audio',
    flamaField: 'Audio',
    dataType: 'Audio (MP3)',
    role: 'Voice Audio Clip',
    description: 'Đoạn audio âm thanh giọng nhân vật nói câu thoại được cắt tự động chính xác',
  },
  {
    asbField: 'Source',
    flamaField: 'Source',
    dataType: 'Text',
    role: 'Context / Title',
    description: 'Tiêu đề video, tên phim hoạt hình anime hoặc tên tệp media đang phát',
  },
  {
    asbField: 'URL',
    flamaField: 'URL',
    dataType: 'Text',
    role: 'Source Link',
    description: 'Đường dẫn liên kết trực tiếp đến video (YouTube, Netflix...) kèm mốc thời gian',
  },
]

export function AsbplayerInteractiveGuide() {
  const { t } = useTranslation('guide')
  const [activeTab, setActiveTab] = useState<'workflow' | 'mapping' | 'preview'>('workflow')
  const [copiedUrl, setCopiedUrl] = useState(false)
  const [copiedMapping, setCopiedMapping] = useState(false)
  const [previewSide, setPreviewSide] = useState<'front' | 'back'>('front')
  const [isPlayingAudio, setIsPlayingAudio] = useState(false)

  const ankiConnectUrl = 'http://localhost:4790/v1/anki-connect'

  const copyAnkiConnectUrl = async () => {
    try {
      await navigator.clipboard.writeText(ankiConnectUrl)
      setCopiedUrl(true)
      window.setTimeout(() => setCopiedUrl(false), 2000)
      toast.success(t('asbplayer.step_4_copied', { defaultValue: 'Đã sao chép Server URL Flama Connect!' }))
    } catch {
      toast.error('Không thể sao chép URL.')
    }
  }

  const copyMappingScheme = async () => {
    try {
      const mappingJson = JSON.stringify(
        {
          deckName: 'Sentences',
          modelName: 'Sentence Card',
          fields: {
            Sentence: 'Sentence',
            Word: 'Word',
            Definition: 'Definition',
            Image: 'Image',
            Audio: 'Audio',
            Source: 'Source',
            URL: 'URL',
          },
        },
        null,
        2,
      )
      await navigator.clipboard.writeText(mappingJson)
      setCopiedMapping(true)
      window.setTimeout(() => setCopiedMapping(false), 2000)
      toast.success(t('asbplayer.mapping_copied', { defaultValue: 'Đã sao chép cấu hình ánh xạ trường!' }))
    } catch {
      toast.error('Không thể sao chép cấu hình.')
    }
  }

  const handleSimulatePlayAudio = () => {
    setIsPlayingAudio(true)
    window.setTimeout(() => {
      setIsPlayingAudio(false)
    }, 2200)
  }

  return (
    <div className="space-y-8 w-full min-w-0">
      {/* 1. Hero & Value Proposition Section */}
      <Card className="overflow-hidden border-rose-500/30 bg-gradient-to-br from-rose-500/10 via-background to-primary/5 shadow-2xs">
        <CardHeader className="p-4 sm:p-6 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="default" className="bg-rose-600 hover:bg-rose-700 text-white font-semibold px-2.5 sm:px-3 py-1 text-xs gap-1.5 shadow-2xs">
              <Heart className="size-3.5 fill-current" /> {t('asbplayer.hero_badge_recommend', { defaultValue: 'Đề xuất cho người học Immersion' })}
            </Badge>
            <Badge variant="outline" className="text-xs border-rose-500/40 text-rose-700 dark:text-rose-300 gap-1.5">
              <Film className="size-3" /> {t('asbplayer.hero_badge_video', { defaultValue: 'Khai thác video & phụ đề' })}
            </Badge>
            <Badge variant="secondary" className="text-xs gap-1.5">
              <Cloud className="size-3 text-primary" /> {t('asbplayer.hero_badge_bridge', { defaultValue: 'Nền tảng Flama Connect' })}
            </Badge>
          </div>
          <div className="space-y-1.5">
            <CardTitle className="text-lg sm:text-xl font-bold tracking-tight flex items-center gap-2 text-foreground">
              <Clapperboard className="size-5 text-rose-500 shrink-0" />
              <span>{t('asbplayer.hero_value_title', { defaultValue: 'Tại sao nên kết hợp asbplayer cùng Flama?' })}</span>
            </CardTitle>
            <CardDescription className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
              {t('asbplayer.subtitle', {
                defaultValue:
                  'Tự động tạo Flashcard kèm âm thanh MP3, ảnh chụp màn hình và câu phụ đề chuẩn xác khi xem video chỉ với 1 phím tắt.',
              })}
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="p-4 sm:p-6 pt-0 space-y-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="group rounded-2xl border bg-card/90 p-4 space-y-2.5 shadow-2xs hover:shadow-md hover:border-rose-500/40 transition-all">
              <div className="p-2.5 rounded-xl bg-rose-500/10 text-rose-600 dark:text-rose-400 w-fit group-hover:scale-105 transition-transform">
                <Subtitles className="size-5" />
              </div>
              <div className="font-bold text-xs sm:text-sm text-foreground">
                {t('asbplayer.pillar_1_title', { defaultValue: 'Khai Thác Phụ Đề Video Tự Động' })}
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t('asbplayer.pillar_1_desc', {
                  defaultValue:
                    'Bắt trọn câu thoại phụ đề, ảnh chụp video và âm thanh cắt chính xác theo dòng thời gian mà không cần thao tác thủ công.',
                })}
              </p>
            </div>

            <div className="group rounded-2xl border bg-card/90 p-4 space-y-2.5 shadow-2xs hover:shadow-md hover:border-sky-500/40 transition-all">
              <div className="p-2.5 rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400 w-fit group-hover:scale-105 transition-transform">
                <Zap className="size-5" />
              </div>
              <div className="font-bold text-xs sm:text-sm text-foreground">
                {t('asbplayer.pillar_2_title', { defaultValue: 'Đồng Bộ Trực Tiếp Qua Flama Connect' })}
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t('asbplayer.pillar_2_desc', {
                  defaultValue:
                    'Flama Connect tiếp nhận dữ liệu khai thác trực tiếp qua cổng kết nối tương thích (/v1/anki-connect). Flashcard được lưu thẳng vào Flama mà không cần phần mềm Anki Desktop.',
                })}
              </p>
            </div>

            <div className="group rounded-2xl border bg-card/90 p-4 space-y-2.5 shadow-2xs hover:shadow-md hover:border-purple-500/40 transition-all">
              <div className="p-2.5 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 w-fit group-hover:scale-105 transition-transform">
                <Sparkles className="size-5" />
              </div>
              <div className="font-bold text-xs sm:text-sm text-foreground">
                {t('asbplayer.pillar_3_title', { defaultValue: 'Kết Hợp Hoàn Hảo Với Yomitan' })}
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t('asbplayer.pillar_3_desc', {
                  defaultValue:
                    'Rê chuột tra từ trên phụ đề video bằng Yomitan để tự động đưa Kanji, Kana và giải nghĩa từ điển vào thẻ cùng lúc với câu và audio.',
                })}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 2. Official Download Links Section */}
      <Card className="rounded-2xl border shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-2">
          <div className="space-y-1">
            <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2">
              <Download className="size-4.5 text-primary" />
              <span>{t('asbplayer.download_title', { defaultValue: 'Link Tải asbplayer Chính Thức' })}</span>
            </CardTitle>
            <CardDescription className="text-xs">
              {t('asbplayer.download_desc', {
                defaultValue: 'Cài đặt tiện ích mở rộng trình duyệt hoặc sử dụng trình phát web asbplayer:',
              })}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-1">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <a
              href="https://chromewebstore.google.com/detail/asbplayer-language-learni/hkbdipohnchifahbgackallnndjgnbdm"
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between rounded-xl border p-3.5 bg-background hover:border-rose-500 hover:bg-rose-500/5 hover:shadow-xs transition-all group"
            >
              <div className="space-y-0.5 min-w-0">
                <div className="font-semibold text-xs sm:text-sm group-hover:text-rose-600 dark:group-hover:text-rose-400 transition-colors truncate">
                  {t('asbplayer.download_chrome', { defaultValue: 'Chrome / Edge / Brave' })}
                </div>
                <div className="text-[11px] text-muted-foreground truncate">
                  {t('asbplayer.download_chrome_desc', { defaultValue: 'Chrome Web Store' })}
                </div>
              </div>
              <ExternalLink className="size-3.5 text-muted-foreground group-hover:text-rose-600 dark:group-hover:text-rose-400 transition-colors shrink-0 ml-2" />
            </a>

            <a
              href="https://addons.mozilla.org/en-US/firefox/addon/asbplayer/"
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between rounded-xl border p-3.5 bg-background hover:border-amber-500 hover:bg-amber-500/5 hover:shadow-xs transition-all group"
            >
              <div className="space-y-0.5 min-w-0">
                <div className="font-semibold text-xs sm:text-sm group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors truncate">
                  {t('asbplayer.download_firefox', { defaultValue: 'Mozilla Firefox' })}
                </div>
                <div className="text-[11px] text-muted-foreground truncate">
                  {t('asbplayer.download_firefox_desc', { defaultValue: 'Firefox Add-ons' })}
                </div>
              </div>
              <ExternalLink className="size-3.5 text-muted-foreground group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors shrink-0 ml-2" />
            </a>

            <a
              href="https://asbplayer.dev"
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between rounded-xl border p-3.5 bg-background hover:border-sky-500 hover:bg-sky-500/5 hover:shadow-xs transition-all group"
            >
              <div className="space-y-0.5 min-w-0">
                <div className="font-semibold text-xs sm:text-sm group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors truncate">
                  {t('asbplayer.download_web', { defaultValue: 'Trình Phát Web asbplayer' })}
                </div>
                <div className="text-[11px] text-muted-foreground truncate">
                  {t('asbplayer.download_web_desc', { defaultValue: 'asbplayer.dev (MKV & Phụ đề)' })}
                </div>
              </div>
              <ExternalLink className="size-3.5 text-muted-foreground group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors shrink-0 ml-2" />
            </a>

            <a
              href="https://github.com/killergerbah/asbplayer"
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between rounded-xl border p-3.5 bg-background hover:border-purple-500 hover:bg-purple-500/5 hover:shadow-xs transition-all group"
            >
              <div className="space-y-0.5 min-w-0">
                <div className="font-semibold text-xs sm:text-sm group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors truncate">
                  {t('asbplayer.download_github', { defaultValue: 'Mã Nguồn GitHub Releases' })}
                </div>
                <div className="text-[11px] text-muted-foreground truncate">
                  {t('asbplayer.download_github_desc', { defaultValue: 'killergerbah/asbplayer' })}
                </div>
              </div>
              <ExternalLink className="size-3.5 text-muted-foreground group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors shrink-0 ml-2" />
            </a>
          </div>
        </CardContent>
      </Card>

      {/* 3. Interactive Workflow Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={(val) => setActiveTab(val as 'workflow' | 'mapping' | 'preview')}
        className="space-y-4"
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b pb-3">
          <div>
            <h3 className="text-base sm:text-lg font-bold text-foreground">
              {t('asbplayer.workflow_tabs_title', { defaultValue: 'Quy Trình & Hướng Dẫn Tương Tác' })}
            </h3>
          </div>
          <TabsList className="bg-muted p-1 rounded-xl">
            <TabsTrigger value="workflow" className="rounded-lg text-xs font-semibold px-3 py-1.5 gap-1.5">
              <Layers className="size-3.5" />
              <span>{t('asbplayer.tab_workflow', { defaultValue: '6 Bước Thiết Lập' })}</span>
            </TabsTrigger>
            <TabsTrigger value="mapping" className="rounded-lg text-xs font-semibold px-3 py-1.5 gap-1.5">
              <Code className="size-3.5" />
              <span>{t('asbplayer.tab_mapping', { defaultValue: 'Bảng Ánh Xạ Trường' })}</span>
            </TabsTrigger>
            <TabsTrigger value="preview" className="rounded-lg text-xs font-semibold px-3 py-1.5 gap-1.5">
              <Film className="size-3.5" />
              <span>{t('asbplayer.tab_preview', { defaultValue: 'Mô Phỏng Thẻ Mẫu' })}</span>
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Tab 1: 6-Step Workflow */}
        <TabsContent value="workflow" className="space-y-4 mt-0">
          <div className="grid gap-3.5">
            {/* Step 1 */}
            <div className="p-4 sm:p-5 rounded-2xl border bg-card shadow-2xs space-y-2">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex size-7 items-center justify-center rounded-xl bg-rose-500 text-white text-xs font-bold shrink-0 shadow-xs">
                    1
                  </div>
                  <h4 className="font-bold text-sm sm:text-base text-foreground">
                    {t('asbplayer.step_1_title', { defaultValue: 'Bước 1: Cài đặt tiện ích asbplayer hoặc mở Web Player' })}
                  </h4>
                </div>
                <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-semibold text-muted-foreground">
                  Extension / Web
                </Badge>
              </div>
              <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed pl-9">
                {t('asbplayer.step_1_desc', {
                  defaultValue:
                    'Cài đặt tiện ích mở rộng asbplayer trên trình duyệt của bạn (Chrome, Edge, Firefox, Brave) để khai thác phụ đề trên YouTube, Netflix, Crunchyroll. Với tệp video lưu trên máy tính, bạn có thể mở trực tiếp tại asbplayer.dev.',
                })}
              </p>
            </div>

            {/* Step 2 */}
            <div className="p-4 sm:p-5 rounded-2xl border bg-card shadow-2xs space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex size-7 items-center justify-center rounded-xl bg-rose-500 text-white text-xs font-bold shrink-0 shadow-xs">
                    2
                  </div>
                  <h4 className="font-bold text-sm sm:text-base text-foreground">
                    {t('asbplayer.step_2_title', {
                      defaultValue: 'Bước 2: Chuẩn bị deck "Sentences" & model "Sentence Card" trên Flama',
                    })}
                  </h4>
                </div>
                <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-semibold text-muted-foreground">
                  Web Flama
                </Badge>
              </div>
              <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed pl-9">
                {t('asbplayer.step_2_desc', {
                  defaultValue:
                    'Hệ thống Flama hỗ trợ tự động khởi tạo bộ thẻ "Sentences" và mẫu thẻ chuyên dụng "Sentence Card" với 7 trường chuẩn chỉ bằng 1 cú nhấp chuột.',
                })}
              </p>
              <div className="pl-9">
                <Button asChild size="sm" variant="outline" className="h-8 gap-2 text-xs font-semibold rounded-xl border-primary/40 text-primary hover:bg-primary/10">
                  <Link to="/settings/asbplayer">
                    <KeyRound className="size-3.5" />
                    <span>{t('asbplayer.step_2_link', { defaultValue: 'Đi đến trang Cài đặt asbplayer để chuẩn bị deck' })}</span>
                  </Link>
                </Button>
              </div>
            </div>

            {/* Step 3 */}
            <div className="p-4 sm:p-5 rounded-2xl border bg-card shadow-2xs space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex size-7 items-center justify-center rounded-xl bg-rose-500 text-white text-xs font-bold shrink-0 shadow-xs">
                    3
                  </div>
                  <h4 className="font-bold text-sm sm:text-base text-foreground">
                    {t('asbplayer.step_3_title', { defaultValue: 'Bước 3: Tạo API Token trên Flama Connect' })}
                  </h4>
                </div>
                <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-semibold text-muted-foreground">
                  Token API
                </Badge>
              </div>
              <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed pl-9">
                {t('asbplayer.step_3_desc', {
                  defaultValue:
                    'Truy cập /settings/asbplayer, chọn preset "Khai thác đa phương tiện (mining-media)" để Flama Connect cấp quyền lưu câu thoại, ảnh chụp và âm thanh MP3. Sao chép API Key được cấp.',
                })}
              </p>
              <div className="pl-9">
                <Button asChild size="sm" variant="outline" className="h-8 gap-2 text-xs font-semibold rounded-xl border-rose-500/40 text-rose-600 dark:text-rose-400 hover:bg-rose-500/10">
                  <Link to="/settings/asbplayer">
                    <Zap className="size-3.5" />
                    <span>{t('asbplayer.step_3_link', { defaultValue: 'Tạo Token tại /settings/asbplayer' })}</span>
                  </Link>
                </Button>
              </div>
            </div>

            {/* Step 4 */}
            <div className="p-4 sm:p-5 rounded-2xl border bg-card shadow-2xs space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex size-7 items-center justify-center rounded-xl bg-rose-500 text-white text-xs font-bold shrink-0 shadow-xs">
                    4
                  </div>
                  <h4 className="font-bold text-sm sm:text-base text-foreground">
                    {t('asbplayer.step_4_title', { defaultValue: 'Bước 4: Cấu hình kết nối Flama Connect trong asbplayer' })}
                  </h4>
                </div>
                <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-semibold text-muted-foreground">
                  Flama Connect
                </Badge>
              </div>
              <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed pl-9">
                {t('asbplayer.step_4_desc', {
                  defaultValue:
                    'Mở Cài đặt (Settings) trong asbplayer ➔ chọn mục "Anki" (tiện ích asbplayer tích hợp qua chuẩn giao thức này) ➔ Bật "Anki integration" ➔ Dán Server URL Flama Connect và mã API Key vào asbplayer ➔ Nhấn "Test Connection" để kiểm tra kết nối với Flama.',
                })}
              </p>

              <div className="pl-9 space-y-2">
                <div className="text-xs font-semibold text-foreground">
                  {t('asbplayer.step_4_url_label', { defaultValue: 'Server URL Flama Connect (Endpoint tương thích):' })}
                </div>
                <div className="flex items-center gap-2 max-w-xl">
                  <code className="flex-1 overflow-x-auto rounded-xl bg-zinc-950 p-2.5 font-mono text-xs text-zinc-100 dark:bg-zinc-900 border border-zinc-800">
                    {ankiConnectUrl}
                  </code>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={copyAnkiConnectUrl}
                    className="h-9 gap-1.5 text-xs font-semibold rounded-xl shrink-0"
                  >
                    {copiedUrl ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
                    <span>
                      {copiedUrl
                        ? t('asbplayer.step_4_copied', { defaultValue: 'Đã sao chép Server URL Flama Connect!' })
                        : t('asbplayer.step_4_copy_btn', { defaultValue: 'Sao chép Server URL' })}
                    </span>
                  </Button>
                </div>
                <div className="rounded-xl border bg-muted/40 p-3 text-xs text-muted-foreground leading-relaxed">
                  <span className="font-semibold text-foreground">
                    {t('asbplayer.step_4_note_title', { defaultValue: 'Lưu ý về mục "Anki" trong asbplayer:' })}
                  </span>{' '}
                  {t('asbplayer.step_4_note_desc', {
                    defaultValue:
                      'asbplayer sử dụng giao thức chuẩn AnkiConnect để giao tiếp với bên ngoài. Nền tảng Flama Connect đóng vai trò máy chủ tiếp nhận độc lập tương thích chuẩn này, lưu trữ toàn bộ thẻ học trực tiếp vào hệ thống Flama mà không cần cài đặt hay mở ứng dụng Anki Desktop.',
                  })}
                </div>
              </div>
            </div>

            {/* Step 5 */}
            <div className="p-4 sm:p-5 rounded-2xl border bg-card shadow-2xs space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex size-7 items-center justify-center rounded-xl bg-rose-500 text-white text-xs font-bold shrink-0 shadow-xs">
                    5
                  </div>
                  <h4 className="font-bold text-sm sm:text-base text-foreground">
                    {t('asbplayer.step_5_title', { defaultValue: 'Bước 5: Cấu hình ánh xạ các trường (Field Mapping)' })}
                  </h4>
                </div>
                <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-semibold text-muted-foreground">
                  Ánh xạ
                </Badge>
              </div>
              <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed pl-9">
                {t('asbplayer.step_5_desc', {
                  defaultValue:
                    'Trong cài đặt Anki của asbplayer, chọn Deck "Sentences" và Note Type "Sentence Card" do Flama Connect chuẩn bị. Ánh xạ lần lượt 7 trường: Sentence, Word, Definition, Image, Audio, Source, URL theo bảng quy chuẩn của Flama.',
                })}
              </p>
              <div className="pl-9 flex flex-wrap gap-2 pt-1">
                <Badge variant="secondary" className="text-xs font-medium">
                  {t('asbplayer.step_5_deck_label', { defaultValue: 'Deck đích: Sentences' })}
                </Badge>
                <Badge variant="secondary" className="text-xs font-medium">
                  {t('asbplayer.step_5_model_label', { defaultValue: 'Model đích: Sentence Card' })}
                </Badge>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setActiveTab('mapping')}
                  className="h-6 text-xs text-primary hover:text-primary/80 gap-1 p-0"
                >
                  <span>Xem bảng chi tiết 7 trường &rarr;</span>
                </Button>
              </div>
            </div>

            {/* Step 6 */}
            <div className="p-4 sm:p-5 rounded-2xl border bg-card shadow-2xs space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex size-7 items-center justify-center rounded-xl bg-rose-500 text-white text-xs font-bold shrink-0 shadow-xs">
                    6
                  </div>
                  <h4 className="font-bold text-sm sm:text-base text-foreground">
                    {t('asbplayer.step_6_title', {
                      defaultValue: 'Bước 6: Khai thác khi xem video bằng phím tắt Ctrl+Shift+X',
                    })}
                  </h4>
                </div>
                <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-semibold text-rose-600 dark:text-rose-400 border-rose-500/30">
                  Ctrl+Shift+X
                </Badge>
              </div>
              <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed pl-9">
                {t('asbplayer.step_6_desc', {
                  defaultValue:
                    'Khi xem video có phụ đề, bấm Ctrl+Shift+X để bắt trọn câu thoại, âm thanh MP3 và ảnh chụp màn hình gửi vào Flama qua Flama Connect. Nếu muốn có từ vựng và nghĩa, hãy rê chuột tra từ bằng Yomitan trên phụ đề trước khi bấm phím tắt!',
                })}
              </p>
              <div className="pl-9 flex flex-wrap gap-2 pt-1">
                <Badge variant="outline" className="font-mono text-xs border-primary/40 text-primary">
                  {t('asbplayer.step_6_shortcut_badge', { defaultValue: 'Phím tắt chính: Ctrl + Shift + X' })}
                </Badge>
                <Badge variant="outline" className="font-mono text-xs border-amber-500/40 text-amber-600 dark:text-amber-400">
                  {t('asbplayer.step_6_nav_badge', { defaultValue: 'Điều hướng phụ đề: A / S / D' })}
                </Badge>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Tab 2: Field Mapping Table */}
        <TabsContent value="mapping" className="space-y-4 mt-0">
          <div className="rounded-2xl border bg-card shadow-2xs overflow-hidden">
            <div className="p-4 sm:p-5 border-b bg-muted/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div>
                <h4 className="font-bold text-sm sm:text-base text-foreground">
                  {t('asbplayer.mapping_table_title', { defaultValue: 'Bảng Quy Chuẩn Ánh Xạ 7 Trường Dữ Liệu' })}
                </h4>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('asbplayer.mapping_table_desc', {
                    defaultValue: 'Ánh xạ các trường từ asbplayer sang mẫu thẻ Sentence Card của Flama để hiển thị tối ưu nhất:',
                  })}
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={copyMappingScheme}
                className="h-8 gap-1.5 text-xs font-semibold rounded-xl shrink-0"
              >
                {copiedMapping ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
                <span>
                  {copiedMapping
                    ? t('asbplayer.mapping_copied', { defaultValue: 'Đã sao chép!' })
                    : t('asbplayer.copy_mapping_btn', { defaultValue: 'Sao chép cấu hình JSON mẫu' })}
                </span>
              </Button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b bg-muted/40 text-foreground font-bold">
                    <th className="py-3 px-4 w-36">
                      {t('asbplayer.mapping_col_asb', { defaultValue: 'Trường asbplayer' })}
                    </th>
                    <th className="py-3 px-4 w-36">
                      {t('asbplayer.mapping_col_flama', { defaultValue: 'Trường Flama' })}
                    </th>
                    <th className="py-3 px-4 w-32">
                      {t('asbplayer.mapping_col_type', { defaultValue: 'Kiểu Dữ Liệu' })}
                    </th>
                    <th className="py-3 px-4">
                      {t('asbplayer.mapping_col_desc', { defaultValue: 'Mô Tả & Chức Năng' })}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {CANONICAL_FIELD_MAPPINGS.map((item, idx) => (
                    <tr key={idx} className="hover:bg-muted/30 transition-colors">
                      <td className="py-2.5 px-4 font-mono font-bold text-foreground">
                        <kbd className="px-2 py-0.5 rounded-md bg-muted border text-[11px] font-mono">
                          {item.asbField}
                        </kbd>
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-primary">
                        <span className="flex items-center gap-1.5">
                          {item.flamaField}
                          {item.isPrimary && (
                            <Badge variant="destructive" className="text-[10px] h-4 px-1 py-0 font-normal">
                              Primary
                            </Badge>
                          )}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-muted-foreground font-mono text-[11px]">
                        {item.dataType}
                      </td>
                      <td className="py-2.5 px-4 text-muted-foreground leading-relaxed">
                        {item.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* First field rule notice */}
          <Alert className="border-rose-500/30 bg-rose-500/5 p-4 rounded-2xl">
            <Info className="size-4.5 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
            <div className="space-y-1 min-w-0">
              <AlertTitle className="text-rose-950 dark:text-rose-200 font-bold text-xs sm:text-sm">
                {t('asbplayer.rule_first_field_title', { defaultValue: 'Quy tắc trường Sentence (Primary Field)' })}
              </AlertTitle>
              <AlertDescription className="text-xs text-rose-900/90 dark:text-rose-300 leading-relaxed">
                {t('asbplayer.rule_first_field_desc', {
                  defaultValue:
                    'Trường Sentence là trường đầu tiên và bắt buộc có nội dung. Flama sử dụng trường này để chống trùng lặp thẻ ghi nhớ trong cùng một Deck.',
                })}
              </AlertDescription>
            </div>
          </Alert>
        </TabsContent>

        {/* Tab 3: Interactive Card Simulator */}
        <TabsContent value="preview" className="space-y-4 mt-0">
          <Card className="rounded-2xl border shadow-2xs overflow-hidden">
            <CardHeader className="p-4 sm:p-5 border-b bg-muted/20">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2">
                    <Film className="size-4.5 text-rose-500" />
                    <span>{t('asbplayer.preview_title', { defaultValue: 'Mô Phỏng Thẻ Mẫu Khai Thác Từ asbplayer' })}</span>
                  </CardTitle>
                  <CardDescription className="text-xs">
                    {t('asbplayer.preview_desc', {
                      defaultValue: 'Xem trước giao diện thẻ Flashcard được tạo tự động trên Flama khi bạn bấm Ctrl+Shift+X:',
                    })}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-1.5 bg-muted p-1 rounded-xl">
                  <Button
                    size="sm"
                    variant={previewSide === 'front' ? 'default' : 'ghost'}
                    onClick={() => setPreviewSide('front')}
                    className="h-7 text-xs font-semibold rounded-lg px-2.5"
                  >
                    {t('asbplayer.preview_toggle_front', { defaultValue: 'Mặt Trước (Front)' })}
                  </Button>
                  <Button
                    size="sm"
                    variant={previewSide === 'back' ? 'default' : 'ghost'}
                    onClick={() => setPreviewSide('back')}
                    className="h-7 text-xs font-semibold rounded-lg px-2.5"
                  >
                    {t('asbplayer.preview_toggle_back', { defaultValue: 'Mặt Sau (Back)' })}
                  </Button>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-4 sm:p-6 space-y-6">
              <div className="max-w-xl mx-auto rounded-2xl border border-border/80 bg-gradient-to-b from-card to-muted/20 p-5 sm:p-6 shadow-sm space-y-5">
                {/* Side Badge */}
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="text-xs font-medium">
                    {previewSide === 'front'
                      ? t('asbplayer.preview_front_badge', { defaultValue: 'Mặt trước: Thử thách khả năng nghe & hiểu' })
                      : t('asbplayer.preview_back_badge', { defaultValue: 'Mặt sau: Giải nghĩa chi tiết & Ngữ cảnh' })}
                  </Badge>
                  <span className="text-[11px] font-mono text-muted-foreground">Sentences / Sentence Card</span>
                </div>

                {/* Simulated Video Frame */}
                <div className="relative overflow-hidden rounded-xl border bg-zinc-950 aspect-video flex flex-col items-center justify-center p-4 text-center group shadow-inner">
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30 pointer-events-none" />
                  
                  {/* Scene visual backdrop representation */}
                  <div className="absolute inset-0 opacity-30 flex items-center justify-center text-zinc-600">
                    <Clapperboard className="size-20 stroke-1" />
                  </div>

                  {/* Subtitle text simulation at bottom */}
                  <div className="absolute bottom-3 inset-x-4 text-center z-10">
                    <span className="inline-block bg-black/75 backdrop-blur-xs text-white px-3 py-1.5 rounded-lg text-sm sm:text-base font-semibold tracking-wide drop-shadow-md">
                      雨が降っているから、<span className="text-amber-300 font-bold underline decoration-amber-400 underline-offset-2">傘</span>を持っていこう。
                    </span>
                  </div>
                </div>

                {/* Audio player bar */}
                <div className="flex items-center justify-between p-3 rounded-xl border bg-muted/40">
                  <div className="flex items-center gap-2.5">
                    <Button
                      size="icon"
                      variant="default"
                      onClick={handleSimulatePlayAudio}
                      className="size-8 rounded-full bg-primary text-primary-foreground shrink-0 shadow-xs"
                      aria-label="Play sample audio"
                    >
                      {isPlayingAudio ? <RotateCw className="size-3.5 animate-spin" /> : <Play className="size-3.5 fill-current ml-0.5" />}
                    </Button>
                    <div className="space-y-0.5">
                      <div className="text-xs font-bold text-foreground flex items-center gap-1.5">
                        <Volume2 className="size-3.5 text-primary" />
                        <span>asbplayer_audio_001422.mp3</span>
                      </div>
                      <div className="text-[10px] text-muted-foreground font-mono">
                        {isPlayingAudio
                          ? t('asbplayer.preview_playing', { defaultValue: 'Đang phát...' })
                          : '00:00 / 00:03 • 44.1kHz MP3'}
                      </div>
                    </div>
                  </div>
                  <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-600 dark:text-emerald-400">
                    Auto-clipped
                  </Badge>
                </div>

                {/* Back side details */}
                {previewSide === 'back' && (
                  <div className="space-y-4 pt-2 border-t border-dashed border-border/80 animate-in fade-in-50 duration-200">
                    {/* Target word breakdown card */}
                    <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3.5 space-y-1">
                      <div className="flex items-center justify-between">
                        <div className="text-base font-bold text-foreground flex items-baseline gap-2">
                          <span className="text-lg text-amber-600 dark:text-amber-400">傘</span>
                          <span className="text-xs font-normal text-muted-foreground">【かさ】</span>
                        </div>
                        <Badge variant="secondary" className="text-[10px] font-semibold">
                          Yomitan Popup
                        </Badge>
                      </div>
                      <p className="text-xs text-foreground/90 leading-relaxed">
                        <strong>(danh từ):</strong> Chiếc ô, cái dù. Vật dụng dùng để che mưa hoặc che nắng.
                      </p>
                    </div>

                    {/* Metadata: Source & URL */}
                    <div className="rounded-xl border bg-muted/20 p-3 text-[11px] space-y-1.5 text-muted-foreground">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-foreground">Source:</span>
                        <span className="font-semibold text-foreground">言の葉の庭 (The Garden of Words) • 00:14:22</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-foreground">URL:</span>
                        <span className="text-primary truncate max-w-[240px]">https://www.netflix.com/watch/8000...</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 4. Quick Action Navigation Strip */}
      <div className="grid gap-3 sm:grid-cols-2 pt-2">
        <Link
          to="/settings/asbplayer"
          className="group flex items-center justify-between p-4 rounded-2xl border bg-card hover:border-rose-500/50 hover:bg-muted/20 transition-all shadow-2xs"
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-rose-500/10 text-rose-600 dark:text-rose-400 shrink-0 group-hover:scale-105 transition-transform">
              <KeyRound className="size-5" />
            </div>
            <div className="space-y-0.5">
              <div className="font-bold text-xs sm:text-sm text-foreground group-hover:text-rose-600 dark:group-hover:text-rose-400 transition-colors">
                {t('asbplayer.quick_link_settings_title', { defaultValue: 'Trang Cài Đặt asbplayer' })}
              </div>
              <p className="text-[11px] text-muted-foreground">
                {t('asbplayer.quick_link_settings_desc', {
                  defaultValue: 'Khởi tạo deck/model, tạo API Token và cấu hình tích hợp',
                })}
              </p>
            </div>
          </div>
          <ArrowRight className="size-4 text-muted-foreground group-hover:text-rose-500 group-hover:translate-x-0.5 transition-all" />
        </Link>

        <Link
          to="/guide/integrations/yomitan"
          className="group flex items-center justify-between p-4 rounded-2xl border bg-card hover:border-primary hover:bg-muted/20 transition-all shadow-2xs"
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-primary/10 text-primary shrink-0 group-hover:scale-105 transition-transform">
              <Sparkles className="size-5" />
            </div>
            <div className="space-y-0.5">
              <div className="font-bold text-xs sm:text-sm text-foreground group-hover:text-primary transition-colors">
                {t('asbplayer.quick_link_yomitan_title', { defaultValue: 'Hướng Dẫn Tích Hợp Yomitan' })}
              </div>
              <p className="text-[11px] text-muted-foreground">
                {t('asbplayer.quick_link_yomitan_desc', {
                  defaultValue: 'Kết hợp tra từ vựng pop-up trên phụ đề video để tối đa hóa hiệu quả',
                })}
              </p>
            </div>
          </div>
          <ArrowRight className="size-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
        </Link>
      </div>
    </div>
  )
}
