import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  Check,
  Code2,
  Copy,
  HelpCircle,
  Layers,
  Lightbulb,
  Plus,
  Sparkles,
  Volume2,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import { SpotlightTour, type TourStep } from '@/shared/components/SpotlightTour'

const GUIDE_STORAGE_KEY = 'flama_guide_spotlight_tour_v1'

const GUIDE_TOUR_STEPS: TourStep[] = [
  {
    target: '[data-tour="guide-header"]',
    title: '📘 1. Trung Tâm Hướng Dẫn & Prompt AI',
    content:
      'Trang tài liệu toàn diện này giúp bạn tạo ra bất kỳ mẫu Flashcard nào ưng ý cho Flama mà không cần biết viết code.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="guide-tabs"]',
    title: '📑 2. Điều Hướng Các Chủ Đề Hướng Dẫn',
    content:
      'Chuyển nhanh giữa 4 chuyên mục: Prompt AI Mẫu, Công Nghệ Thẻ, Quy Trình 4 Bước và Quy Tắc Vàng Tránh Lỗi.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="guide-master-prompt"]',
    title: '🤖 3. Master Prompt Chuẩn Hóa Cho AI',
    content:
      'Bấm nút "Sao Chép Toàn Bộ Prompt" để copy mẫu chỉ thị chuẩn rồi gửi cho ChatGPT / Claude / Gemini tạo sẵn HTML/CSS cho bạn.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="guide-example-prompts"]',
    title: '💡 4. Các Mẫu Yêu Cầu Thực Tế',
    content:
      'Tham khảo và sao chép nhanh các prompt mẫu cho Thẻ Từ Vựng hoặc Thẻ Ngữ Pháp JLPT có sẵn.',
    placement: 'top',
  },
  {
    target: '[data-tour="guide-start-btn"]',
    title: '🚀 5. Bắt Đầu Tạo Note Type Ngay',
    content:
      'Sau khi có mã code từ AI, bấm nút này để quay lại trang Quản lý Loại Thẻ và áp dụng mẫu thiết kế của bạn.',
    placement: 'bottom',
  },
]

const MASTER_PROMPT = `Bạn là một chuyên gia thiết kế Flashcard học ngôn ngữ trên nền tảng Flama (sử dụng chuẩn Mustache Template, HTML5, CSS3 và JavaScript trong iframe sandbox).

Nhiệm vụ của bạn là dựa vào [YÊU CẦU CỦA TÔI], hãy thiết kế:
1. Danh sách các Trường dữ liệu (Field Definitions) cần tạo trong Note Type (gồm Tên trường và Loại trường: text / richtext / audio / image / markdown...).
2. Mã Front HTML (Mặt trước).
3. Mã Back HTML (Mặt sau).
4. Mã Shared CSS (Định dạng kiểu dáng chung).

YÊU CẦU KỸ THUẬT BẮT BUỘC ĐỂ KHÔNG BỊ LỖI:
- Đặt tên trường dữ liệu theo chuẩn snake_case chữ thường (ví dụ: word, reading, meaning, audio_word, example_jp, example_vi).
- Sử dụng cú pháp Mustache {{Tên_Trường}} hoặc {{{Tên_Trường}}} (nếu là richtext).
- Mọi khối có điều kiện ẩn hiện bắt buộc dùng: {{#Tên_Trường}} ... {{/Tên_Trường}}.
- Đóng mở thẻ HTML chuẩn xác: Mọi thẻ HTML mở bên trong block Mustache {{#...}} PHẢI ĐƯỢC ĐÓNG trước {{/...}}.
- Khung thẻ mặt trước căn giữa bằng Flexbox (không dùng style height: 100vh).
- Các trường Audio phải tạo thẻ <audio id="..." src="{{Tên_Trường}}"></audio> và nút bấm loa 🔊 tương ứng.
- Nếu có script tự động phát âm tuần tự trong thẻ <script>, phải kiểm tra phần tử tồn tại trước khi phát (safePlay).
- Thiết kế giao diện hiện đại, tinh tế, font chữ rõ ràng, phân cấp thị giác đẹp mắt, hỗ trợ hiển thị đẹp trên cả mobile và desktop.

[YÊU CẦU CỦA TÔI]:
- Mục đích thẻ: (Ví dụ: Thẻ học Ngữ pháp JLPT N2 / Thẻ học Kanji N1 / Thẻ học từ vựng Y tế...)
- Các thông tin tôi muốn có trên thẻ:
  + Mặt trước: (Ví dụ: Mẫu ngữ pháp lớn màu đỏ nổi bật, nút nghe audio câu ví dụ tiêu biểu)
  + Mặt sau: (Ví dụ: Ý nghĩa, Cấu trúc ngữ pháp, Giải thích chi tiết, 2 ví dụ có câu dịch và audio, phần phân biệt với ngữ pháp tương đương)
- Phong cách giao diện: (Ví dụ: Tối giản, tông màu xanh dương đậm thanh lịch, font chữ Nhật Bản rõ nét)`

const EXAMPLE_VOCAB_PROMPT = `[YÊU CẦU CỦA TÔI]:
- Mục đích thẻ: Học từ vựng JLPT kèm âm Hán Việt và ví dụ đời sống.
- Mặt trước: Từ vựng Kanji to ở giữa, nút loa phát âm từ vựng.
- Mặt sau:
  + Hiển thị lại Kanji kèm Furigana và Âm Hán Việt.
  + Ý nghĩa tiếng Việt (chữ đậm màu xanh).
  + Câu ví dụ tiếng Nhật + Câu dịch tiếng Việt + Audio phát âm câu ví dụ.
  + Ghi chú / Từ đồng nghĩa (nếu có mới hiện).
  + Script tự động đọc: Đọc từ vựng trước, sau đó tự đọc câu ví dụ.
- Phong cách: Sang trọng, bo góc tròn, màu sắc hiện đại.`

const EXAMPLE_GRAMMAR_PROMPT = `[YÊU CẦU CỦA TÔI]:
- Mục đích thẻ: Học Ngữ pháp JLPT N1 nâng cao.
- Mặt trước: Mẫu ngữ pháp màu đỏ nổi bật ở giữa.
- Mặt sau:
  + Tiêu đề ngữ pháp + Nút Audio đọc mẫu câu.
  + Ý nghĩa tiếng Việt + Cấu trúc ngữ pháp (màu xanh lá).
  + Ghi chú / Giải thích chi tiết.
  + Ví dụ hội thoại thông thường + dịch nghĩa.
  + Ví dụ trích dẫn văn học (Câu trích dẫn, Tác phẩm, Tác giả, Bản dịch) - chỉ hiện khi có dữ liệu.
  + Mục phân biệt / so sánh với mẫu câu gần nghĩa.
- Phong cách: Rõ ràng, dễ đọc, tương phản tốt.`

export function NoteTypeGuidePage() {
  const [copiedMaster, setCopiedMaster] = useState(false)
  const [copiedVocab, setCopiedVocab] = useState(false)
  const [copiedGrammar, setCopiedGrammar] = useState(false)
  const [tourOpen, setTourOpen] = useState(false)

  // Auto-launch guide tour for first-time visitors
  useEffect(() => {
    const completed = localStorage.getItem(GUIDE_STORAGE_KEY)
    if (!completed) {
      const timer = setTimeout(() => {
        setTourOpen(true)
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [])

  const copyToClipboard = (text: string, type: 'master' | 'vocab' | 'grammar') => {
    navigator.clipboard.writeText(text).then(() => {
      if (type === 'master') {
        setCopiedMaster(true)
        setTimeout(() => setCopiedMaster(false), 2000)
      } else if (type === 'vocab') {
        setCopiedVocab(true)
        setTimeout(() => setCopiedVocab(false), 2000)
      } else {
        setCopiedGrammar(true)
        setTimeout(() => setCopiedGrammar(false), 2000)
      }
      toast.success('Đã sao chép vào Clipboard!', {
        description: 'Hãy mở ChatGPT, Claude hoặc Gemini và dán prompt này vào.',
      })
    })
  }

  return (
    <Page className="w-full max-w-6xl px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
      <AmbientBackground intensity="subtle" />

      {/* Standardized Flama PageHeader */}
      <div data-tour="guide-header">
        <PageHeader
          title="Hướng Dẫn Tạo Note Type & Prompt AI"
          description="Toàn bộ kiến thức công nghệ và công cụ Prompt chuẩn giúp bạn tự thiết kế mẫu thẻ Flashcard hoàn hảo mà không cần biết code."
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
              <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl">
                <Link to="/flashcards/note-types">
                  <ArrowLeft className="size-3.5 mr-1.5" /> Quản lý NoteTypes
                </Link>
              </Button>
              <Button
                size="sm"
                asChild
                data-tour="guide-start-btn"
                className="h-8 sm:h-9 px-3 text-xs font-bold rounded-xl shadow-xs"
              >
                <Link to="/flashcards/note-types">
                  <Plus className="size-3.5 mr-1.5" /> Tạo Loại Thẻ Ngay
                </Link>
              </Button>
            </div>
          }
        />
      </div>

      {/* Main Tabs Container */}
      <Tabs defaultValue="prompt" className="space-y-6">
        <div data-tour="guide-tabs">
          <TabsList className="grid grid-cols-2 sm:grid-cols-4 w-full h-11 p-1 rounded-2xl bg-muted/60">
            <TabsTrigger value="prompt" className="text-xs sm:text-sm font-semibold rounded-xl">
              🤖 Prompt AI Mẫu
            </TabsTrigger>
            <TabsTrigger value="tech" className="text-xs sm:text-sm font-semibold rounded-xl">
              ⚙️ Công Nghệ Thẻ
            </TabsTrigger>
            <TabsTrigger value="steps" className="text-xs sm:text-sm font-semibold rounded-xl">
              🚀 Các Bước Làm
            </TabsTrigger>
            <TabsTrigger value="rules" className="text-xs sm:text-sm font-semibold rounded-xl">
              ⚠️ Quy Tắc Tránh Lỗi
            </TabsTrigger>
          </TabsList>
        </div>

        {/* TAB 1: MASTER PROMPT */}
        <TabsContent value="prompt" className="space-y-6">
          <Card data-tour="guide-master-prompt" className="border-border/80 shadow-xs rounded-2xl bg-card">
            <CardHeader className="p-4 sm:p-6 pb-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1">
                  <CardTitle className="text-base sm:text-lg font-bold text-foreground flex items-center gap-2">
                    <Sparkles className="size-4 text-primary" /> Master Prompt Chuẩn Hóa
                  </CardTitle>
                  <CardDescription className="text-xs sm:text-sm text-muted-foreground">
                    Sao chép khung lệnh dưới đây, điền mong muốn của bạn vào cuối rồi gửi cho ChatGPT / Claude / Gemini.
                  </CardDescription>
                </div>
                <Button
                  onClick={() => copyToClipboard(MASTER_PROMPT, 'master')}
                  className="h-9 px-4 text-xs font-bold rounded-xl shadow-xs shrink-0 bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  {copiedMaster ? <Check className="size-3.5 mr-1.5 text-emerald-300" /> : <Copy className="size-3.5 mr-1.5" />}
                  {copiedMaster ? 'Đã sao chép Prompt' : 'Sao chép Master Prompt'}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-4 sm:p-6 pt-0 space-y-4">
              <div className="relative">
                <pre className="p-4 rounded-xl bg-muted/60 border border-border/80 font-mono text-xs leading-relaxed text-foreground select-all whitespace-pre-wrap max-h-96 overflow-y-auto">
                  {MASTER_PROMPT}
                </pre>
              </div>

              <div className="p-3.5 rounded-xl bg-primary/5 border border-primary/20 text-xs text-foreground flex items-start gap-2.5">
                <Lightbulb className="size-4 text-primary shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-primary">Mẹo nhanh:</span> Sau khi AI phản hồi, bạn sẽ nhận được: <strong>(1) Danh sách trường</strong> để nhập vào trang Quản lý Trường, và <strong>(2) Mã Front/Back/CSS</strong> để dán vào trang Template.
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Examples Grid */}
          <div data-tour="guide-example-prompts" className="grid md:grid-cols-2 gap-5">
            <Card className="border-border/80 shadow-xs rounded-2xl bg-card flex flex-col justify-between">
              <CardHeader className="p-4 sm:p-5 pb-2">
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="text-xs font-semibold text-primary border-primary/30">
                    Ví Dụ 1: Từ Vựng JLPT
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(EXAMPLE_VOCAB_PROMPT, 'vocab')}
                    className="h-7 px-2.5 text-xs font-medium rounded-lg hover:bg-muted"
                  >
                    {copiedVocab ? <Check className="size-3 mr-1 text-emerald-500" /> : <Copy className="size-3 mr-1" />}
                    {copiedVocab ? 'Đã chép' : 'Sao chép'}
                  </Button>
                </div>
                <CardTitle className="text-sm font-bold text-foreground mt-2">
                  Thẻ từ vựng có Kanji, Furigana, Hán Việt & Audio câu ví dụ
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 sm:p-5 pt-0">
                <pre className="p-3 rounded-xl bg-muted/40 border border-border/60 font-mono text-[11px] leading-relaxed text-muted-foreground whitespace-pre-wrap">
                  {EXAMPLE_VOCAB_PROMPT}
                </pre>
              </CardContent>
            </Card>

            <Card className="border-border/80 shadow-xs rounded-2xl bg-card flex flex-col justify-between">
              <CardHeader className="p-4 sm:p-5 pb-2">
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                    Ví Dụ 2: Ngữ Pháp Nâng Cao
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(EXAMPLE_GRAMMAR_PROMPT, 'grammar')}
                    className="h-7 px-2.5 text-xs font-medium rounded-lg hover:bg-muted"
                  >
                    {copiedGrammar ? <Check className="size-3 mr-1 text-emerald-500" /> : <Copy className="size-3 mr-1" />}
                    {copiedGrammar ? 'Đã chép' : 'Sao chép'}
                  </Button>
                </div>
                <CardTitle className="text-sm font-bold text-foreground mt-2">
                  Thẻ ngữ pháp có Cấu trúc, Trích dẫn văn học & Phân biệt mẫu câu
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 sm:p-5 pt-0">
                <pre className="p-3 rounded-xl bg-muted/40 border border-border/60 font-mono text-[11px] leading-relaxed text-muted-foreground whitespace-pre-wrap">
                  {EXAMPLE_GRAMMAR_PROMPT}
                </pre>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* TAB 2: TECHNOLOGY & SYNTAX */}
        <TabsContent value="tech" className="space-y-6">
          <div className="grid sm:grid-cols-3 gap-4">
            <Card className="p-4 border-border/80 rounded-2xl space-y-2 bg-card">
              <div className="p-2 w-fit rounded-xl bg-primary/10 text-primary">
                <Code2 className="size-5" />
              </div>
              <h4 className="text-sm font-bold text-foreground">Mustache Template Engine</h4>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Flama sử dụng chuẩn Mustache tiêu chuẩn. Dữ liệu từ vựng được tự động điền vào các thẻ <code className="text-primary font-mono">{`{{Tên_Trường}}`}</code>.
              </p>
            </Card>

            <Card className="p-4 border-border/80 rounded-2xl space-y-2 bg-card">
              <div className="p-2 w-fit rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                <Volume2 className="size-5" />
              </div>
              <h4 className="text-sm font-bold text-foreground">Hệ Thống Âm Thanh & Audio</h4>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Hỗ trợ phát âm file mp3 an toàn qua nút bấm loa 🔊 hoặc script tự động đọc nối tiếp từ vựng đến câu ví dụ.
              </p>
            </Card>

            <Card className="p-4 border-border/80 rounded-2xl space-y-2 bg-card">
              <div className="p-2 w-fit rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400">
                <Layers className="size-5" />
              </div>
              <h4 className="text-sm font-bold text-foreground">Iframe Sandbox An Toàn</h4>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Mỗi thẻ được hiển thị trong môi trường cô lập, giúp giao diện co giãn hoàn hảo trên cả điện thoại di động và máy tính.
              </p>
            </Card>
          </div>

          <Card className="border-border/80 shadow-xs rounded-2xl bg-card">
            <CardHeader className="p-4 sm:p-5 pb-2">
              <CardTitle className="text-sm font-bold text-foreground">6 Loại Trường Dữ Liệu Được Hỗ Trợ</CardTitle>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 pt-2">
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="default" className="text-xs font-mono">text</Badge>
                    <span className="text-xs font-bold text-foreground">Chữ thuần</span>
                  </div>
                  <p className="text-xs text-muted-foreground">Từ vựng, chữ Kanji, nghĩa ngắn, phiên âm Romaji, tên tác giả...</p>
                </div>

                <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs font-mono">richtext</Badge>
                    <span className="text-xs font-bold text-foreground">Văn bản định dạng</span>
                  </div>
                  <p className="text-xs text-muted-foreground">Chữ có bôi đậm, in nghiêng, đổi màu, gạch chân, danh sách gạch đầu dòng.</p>
                </div>

                <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs font-mono">audio</Badge>
                    <span className="text-xs font-bold text-foreground">File âm thanh</span>
                  </div>
                  <p className="text-xs text-muted-foreground">File phát âm từ vựng, câu ví dụ, trích dẫn âm thanh (mp3, wav, m4a).</p>
                </div>

                <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs font-mono">image</Badge>
                    <span className="text-xs font-bold text-foreground">Hình ảnh</span>
                  </div>
                  <p className="text-xs text-muted-foreground">Ảnh minh họa ý nghĩa từ vựng, hình vẽ ngữ cảnh thực tế.</p>
                </div>

                <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs font-mono">markdown</Badge>
                    <span className="text-xs font-bold text-foreground">Định dạng Markdown</span>
                  </div>
                  <p className="text-xs text-muted-foreground">Đoạn văn dài, bảng biểu so sánh, công thức ngữ pháp phức tạp.</p>
                </div>

                <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs font-mono">diagram</Badge>
                    <span className="text-xs font-bold text-foreground">Sơ đồ / Biểu đồ</span>
                  </div>
                  <p className="text-xs text-muted-foreground">Sơ đồ cây cấu trúc câu, biểu đồ ngữ nghĩa trực quan.</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 3: STEP BY STEP */}
        <TabsContent value="steps" className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <Card className="p-4 sm:p-5 border-border/80 rounded-2xl bg-card space-y-2">
              <div className="flex items-center gap-3">
                <div className="size-7 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0">
                  1
                </div>
                <h4 className="text-sm font-bold text-foreground">Tạo Loại Thẻ (Note Type)</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed pl-10">
                Truy cập <strong>Quản lý NoteTypes</strong>, nhập tên loại thẻ mới (ví dụ: <em>Từ vựng N3</em>) và bấm <strong>Tạo NoteType</strong>.
              </p>
            </Card>

            <Card className="p-4 sm:p-5 border-border/80 rounded-2xl bg-card space-y-2">
              <div className="flex items-center gap-3">
                <div className="size-7 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0">
                  2
                </div>
                <h4 className="text-sm font-bold text-foreground">Tạo Các Trường Dữ Liệu</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed pl-10">
                Bấm vào <strong>Quản lý Trường</strong>, thêm các trường theo bảng do AI cung cấp (chọn đúng tên trường và loại trường).
              </p>
            </Card>

            <Card className="p-4 sm:p-5 border-border/80 rounded-2xl bg-card space-y-2">
              <div className="flex items-center gap-3">
                <div className="size-7 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0">
                  3
                </div>
                <h4 className="text-sm font-bold text-foreground">Dán Mã Front / Back / CSS</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed pl-10">
                Vào trang <strong>Chi tiết Template</strong>, dán lần lượt <strong>Front HTML</strong>, <strong>Back HTML</strong>, <strong>Shared CSS</strong> rồi bấm <strong>Lưu Template</strong>.
              </p>
            </Card>

            <Card className="p-4 sm:p-5 border-border/80 rounded-2xl bg-card space-y-2">
              <div className="flex items-center gap-3">
                <div className="size-7 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold text-xs flex items-center justify-center shrink-0">
                  4
                </div>
                <h4 className="text-sm font-bold text-foreground">Xem Trước Trực Tiếp (Live Preview)</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed pl-10">
                Khung bên phải sẽ tự động hiển thị mẫu thẻ mô phỏng. Bấm lật <strong>Mặt trước / Mặt sau</strong> và kiểm tra nút loa 🔊 để nghiệm thu.
              </p>
            </Card>
          </div>
        </TabsContent>

        {/* TAB 4: RULES */}
        <TabsContent value="rules" className="space-y-4">
          <div className="space-y-3">
            <Card className="p-4 border-amber-500/30 bg-amber-500/5 rounded-2xl space-y-1.5">
              <h4 className="text-sm font-bold text-amber-900 dark:text-amber-200 flex items-center gap-2">
                ⚠️ 1. Đóng/Mở thẻ HTML cân xứng trong Mustache
              </h4>
              <p className="text-xs text-amber-800 dark:text-amber-300/90 leading-relaxed">
                Khi mở thẻ <code className="font-mono bg-amber-500/10 px-1 py-0.5 rounded">{`<div>`}</code> bên trong điều kiện <code className="font-mono bg-amber-500/10 px-1 py-0.5 rounded">{`{{#Tên_Trường}}`}</code>, bắt buộc phải đóng <code className="font-mono bg-amber-500/10 px-1 py-0.5 rounded">{`</div>`}</code> <strong>trước khi</strong> đóng <code className="font-mono bg-amber-500/10 px-1 py-0.5 rounded">{`{{/Tên_Trường}}`}</code>.
              </p>
            </Card>

            <Card className="p-4 border-blue-500/30 bg-blue-500/5 rounded-2xl space-y-1.5">
              <h4 className="text-sm font-bold text-blue-900 dark:text-blue-200 flex items-center gap-2">
                💡 2. Quy tắc đặt tên trường dữ liệu
              </h4>
              <p className="text-xs text-blue-800 dark:text-blue-300/90 leading-relaxed">
                Nên dùng chữ thường không dấu, nối bằng dấu gạch dưới (VD: <code className="font-mono bg-blue-500/10 px-1 py-0.5 rounded">word</code>, <code className="font-mono bg-blue-500/10 px-1 py-0.5 rounded">audio_word</code>, <code className="font-mono bg-blue-500/10 px-1 py-0.5 rounded">example_vi</code>) để đảm bảo tính tương thích cao nhất.
              </p>
            </Card>

            <Card className="p-4 border-emerald-500/30 bg-emerald-500/5 rounded-2xl space-y-1.5">
              <h4 className="text-sm font-bold text-emerald-900 dark:text-emerald-200 flex items-center gap-2">
                ✨ 3. Tránh style height: 100vh
              </h4>
              <p className="text-xs text-emerald-800 dark:text-emerald-300/90 leading-relaxed">
                Ở Mặt trước, dùng Flexbox căn giữa: <code className="font-mono bg-emerald-500/10 px-1 py-0.5 rounded">style="min-height: 200px; display: flex; align-items: center; justify-content: center;"</code> giúp giao diện co giãn mượt trên cả điện thoại và máy tính.
              </p>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Interactive Spotlight Tour for Guide Page */}
      <SpotlightTour
        steps={GUIDE_TOUR_STEPS}
        isOpen={tourOpen}
        onClose={() => {
          localStorage.setItem(GUIDE_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
        onComplete={() => {
          localStorage.setItem(GUIDE_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
      />
    </Page>
  )
}
