import { useState } from 'react'
import {
  Bot,
  Check,
  Code2,
  Copy,
  Lightbulb,
  Volume2,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

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

export interface NoteTypeAiGuideModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function NoteTypeAiGuideModal({ open, onOpenChange }: NoteTypeAiGuideModalProps) {
  const [activeTab, setActiveTab] = useState('prompt')
  const [copiedMaster, setCopiedMaster] = useState(false)
  const [copiedExample, setCopiedExample] = useState(false)

  const copyToClipboard = (text: string, isExample = false) => {
    navigator.clipboard.writeText(text).then(() => {
      if (isExample) {
        setCopiedExample(true)
        setTimeout(() => setCopiedExample(false), 2000)
      } else {
        setCopiedMaster(true)
        setTimeout(() => setCopiedMaster(false), 2000)
      }
      toast.success('Đã sao chép prompt vào Clipboard!', {
        description: 'Hãy mở ChatGPT, Claude hoặc Gemini và dán prompt này vào.',
      })
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl sm:max-w-3xl max-h-[90vh] flex flex-col p-0 overflow-hidden rounded-2xl">
        <DialogHeader className="p-5 pb-3 border-b border-border/80 bg-muted/20">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-primary/10 text-primary shrink-0">
              <Bot className="size-5" />
            </div>
            <div>
              <DialogTitle className="text-base sm:text-lg font-bold text-foreground">
                Hướng Dẫn & Prompt AI Tạo Template NoteType
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                Dùng AI (ChatGPT, Claude, Gemini) tạo mẫu thẻ Flashcard đúng chuẩn Flama trong 1 phút.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="p-4 sm:p-6 overflow-y-auto flex-1 space-y-4">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid grid-cols-2 sm:grid-cols-4 w-full h-auto p-1 mb-4 rounded-xl bg-muted/60 gap-1">
              <TabsTrigger value="prompt" className="h-8 sm:h-9 text-xs font-semibold rounded-lg">
                🤖 Prompt AI
              </TabsTrigger>
              <TabsTrigger value="tech" className="h-8 sm:h-9 text-xs font-semibold rounded-lg">
                ⚙️ Công Nghệ
              </TabsTrigger>
              <TabsTrigger value="steps" className="h-8 sm:h-9 text-xs font-semibold rounded-lg">
                🚀 Các Bước
              </TabsTrigger>
              <TabsTrigger value="rules" className="h-8 sm:h-9 text-xs font-semibold rounded-lg">
                ⚠️ Tránh Lỗi
              </TabsTrigger>
            </TabsList>

            {/* TAB 1: MASTER PROMPT */}
            <TabsContent value="prompt" className="space-y-4 mt-0">
              <div className="p-3 rounded-xl bg-primary/5 border border-primary/20 text-xs text-foreground flex items-start gap-2.5">
                <Lightbulb className="size-4 text-primary shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-primary">Cách sử dụng đơn giản:</span> Sao chép <strong>Master Prompt</strong> dưới đây, sửa phần <code>[YÊU CẦU CỦA TÔI]</code> theo ý bạn rồi gửi cho AI. AI sẽ tự viết đầy đủ danh sách trường, Front HTML, Back HTML và CSS đúng chuẩn Flama.
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-foreground">📋 Master Prompt Chuẩn:</span>
                  <Button
                    size="sm"
                    onClick={() => copyToClipboard(MASTER_PROMPT)}
                    className="h-8 px-3 text-xs font-bold rounded-xl shadow-xs"
                  >
                    {copiedMaster ? <Check className="size-3.5 mr-1 text-emerald-300" /> : <Copy className="size-3.5 mr-1" />}
                    {copiedMaster ? 'Đã sao chép' : 'Sao chép Master Prompt'}
                  </Button>
                </div>
                <pre className="p-3.5 rounded-xl bg-muted/60 border border-border/80 font-mono text-[11px] leading-relaxed text-foreground/90 overflow-x-auto max-h-56 select-all whitespace-pre-wrap">
                  {MASTER_PROMPT}
                </pre>
              </div>

              <div className="space-y-2 pt-2 border-t">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-foreground">💡 Ví dụ mẫu [YÊU CẦU CỦA TÔI] cho Thẻ Từ Vựng:</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => copyToClipboard(EXAMPLE_VOCAB_PROMPT, true)}
                    className="h-7 px-2.5 text-[11px] font-semibold rounded-lg"
                  >
                    {copiedExample ? <Check className="size-3 mr-1 text-emerald-500" /> : <Copy className="size-3 mr-1" />}
                    {copiedExample ? 'Đã chép ví dụ' : 'Sao chép ví dụ này'}
                  </Button>
                </div>
                <pre className="p-3 rounded-xl bg-muted/40 border border-border/60 font-mono text-[11px] leading-relaxed text-muted-foreground overflow-x-auto max-h-36 whitespace-pre-wrap">
                  {EXAMPLE_VOCAB_PROMPT}
                </pre>
              </div>
            </TabsContent>

            {/* TAB 2: TECH & SYNTAX */}
            <TabsContent value="tech" className="space-y-4 mt-0">
              <div className="grid sm:grid-cols-2 gap-3">
                <Card className="p-3.5 border-border/80 rounded-xl space-y-1.5 bg-card">
                  <div className="flex items-center gap-2 font-bold text-xs text-foreground">
                    <Code2 className="size-4 text-primary" /> Template Engine: Mustache
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Dùng thẻ <code className="text-primary font-mono">{`{{Tên_Trường}}`}</code> để hiển thị dữ liệu. Dùng <code className="text-primary font-mono">{`{{{Tên_Trường}}}`}</code> nếu trường là mã HTML/RichText.
                  </p>
                </Card>

                <Card className="p-3.5 border-border/80 rounded-xl space-y-1.5 bg-card">
                  <div className="flex items-center gap-2 font-bold text-xs text-foreground">
                    <Volume2 className="size-4 text-emerald-500" /> Hệ Thống Âm Thanh & Audio
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Hỗ trợ thẻ <code className="font-mono text-foreground">{`<audio id="..." src="{{Tên_Audio}}"></audio>`}</code> kèm nút bấm loa hoặc script tự động đọc tuần tự.
                  </p>
                </Card>
              </div>

              <div className="space-y-2">
                <span className="text-xs font-bold text-foreground">Các Loại Trường Dữ Liệu Hỗ Trợ:</span>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  <div className="p-2 rounded-lg border border-border/70 bg-muted/20 text-xs">
                    <Badge variant="outline" className="text-[10px] mb-1">text</Badge>
                    <p className="text-[11px] text-muted-foreground">Chữ thuần, từ vựng, kanji</p>
                  </div>
                  <div className="p-2 rounded-lg border border-border/70 bg-muted/20 text-xs">
                    <Badge variant="outline" className="text-[10px] mb-1">richtext</Badge>
                    <p className="text-[11px] text-muted-foreground">Định dạng bôi đậm, màu sắc</p>
                  </div>
                  <div className="p-2 rounded-lg border border-border/70 bg-muted/20 text-xs">
                    <Badge variant="outline" className="text-[10px] mb-1">audio</Badge>
                    <p className="text-[11px] text-muted-foreground">File phát âm mp3/wav</p>
                  </div>
                  <div className="p-2 rounded-lg border border-border/70 bg-muted/20 text-xs">
                    <Badge variant="outline" className="text-[10px] mb-1">image</Badge>
                    <p className="text-[11px] text-muted-foreground">Ảnh minh họa, sơ đồ</p>
                  </div>
                  <div className="p-2 rounded-lg border border-border/70 bg-muted/20 text-xs">
                    <Badge variant="outline" className="text-[10px] mb-1">markdown</Badge>
                    <p className="text-[11px] text-muted-foreground">Bài viết Markdown dài</p>
                  </div>
                  <div className="p-2 rounded-lg border border-border/70 bg-muted/20 text-xs">
                    <Badge variant="outline" className="text-[10px] mb-1">diagram</Badge>
                    <p className="text-[11px] text-muted-foreground">Biểu đồ, sơ đồ cấu trúc</p>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* TAB 3: STEP BY STEP */}
            <TabsContent value="steps" className="space-y-3 mt-0">
              <div className="space-y-2.5">
                <div className="flex gap-3 items-start p-3 rounded-xl border border-border/80 bg-card">
                  <div className="size-6 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
                    1
                  </div>
                  <div className="text-xs space-y-0.5">
                    <span className="font-bold text-foreground">Tạo NoteType Mới</span>
                    <p className="text-muted-foreground">Nhập tên NoteType (VD: Từ vựng JLPT N2) và bấm <strong>Tạo NoteType</strong>.</p>
                  </div>
                </div>

                <div className="flex gap-3 items-start p-3 rounded-xl border border-border/80 bg-card">
                  <div className="size-6 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
                    2
                  </div>
                  <div className="text-xs space-y-0.5">
                    <span className="font-bold text-foreground">Tạo Các Trường Dữ Liệu (Fields)</span>
                    <p className="text-muted-foreground">Bấm <strong>Quản lý Trường</strong>, thêm các trường theo danh sách AI đã liệt kê (chọn đúng loại text, richtext, audio...).</p>
                  </div>
                </div>

                <div className="flex gap-3 items-start p-3 rounded-xl border border-border/80 bg-card">
                  <div className="size-6 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
                    3
                  </div>
                  <div className="text-xs space-y-0.5">
                    <span className="font-bold text-foreground">Dán Mã Front / Back / CSS</span>
                    <p className="text-muted-foreground">Quay lại trang chi tiết Template, dán mã <strong>Front HTML</strong>, <strong>Back HTML</strong> và <strong>Shared CSS</strong> do AI sinh ra rồi bấm <strong>Lưu Template</strong>.</p>
                  </div>
                </div>

                <div className="flex gap-3 items-start p-3 rounded-xl border border-border/80 bg-card">
                  <div className="size-6 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
                    4
                  </div>
                  <div className="text-xs space-y-0.5">
                    <span className="font-bold text-foreground">Xem Trước Trực Tiếp (Live Preview)</span>
                    <p className="text-muted-foreground">Khung Live Preview bên phải sẽ hiển thị mẫu thẻ mô phỏng. Bạn có thể lật mặt trước/mặt sau và bấm thử loa 🔊 để nghiệm thu.</p>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* TAB 4: RULES */}
            <TabsContent value="rules" className="space-y-3 mt-0 text-xs">
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-900 dark:text-amber-200 space-y-1.5">
                <span className="font-bold block">1. Quy tắc đóng/mở thẻ HTML trong Mustache:</span>
                <p className="text-[11px] leading-relaxed">
                  Nếu mở thẻ <code className="font-mono">{`<div>`}</code> bên trong điều kiện <code className="font-mono">{`{{#Tên_Trường}}`}</code>, bắt buộc phải đóng <code className="font-mono">{`</div>`}</code> <strong>trước khi</strong> đóng <code className="font-mono">{`{{/Tên_Trường}}`}</code> để tránh vỡ giao diện.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-900 dark:text-blue-200 space-y-1.5">
                <span className="font-bold block">2. Đặt tên trường chuẩn:</span>
                <p className="text-[11px] leading-relaxed">
                  Nên đặt tên trường chữ thường không dấu nối bằng gạch dưới (như <code className="font-mono">word</code>, <code className="font-mono">audio_word</code>, <code className="font-mono">example_jp</code>).
                </p>
              </div>

              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-900 dark:text-emerald-200 space-y-1.5">
                <span className="font-bold block">3. Tránh style height: 100vh:</span>
                <p className="text-[11px] leading-relaxed">
                  Ở mặt trước, dùng Flexbox căn giữa: <code className="font-mono">style="min-height: 200px; display: flex; align-items: center; justify-content: center;"</code> để co giãn mượt trên mọi kích thước màn hình.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-900 dark:text-purple-200 space-y-1.5">
                <span className="font-bold block">4. Sơ đồ thứ tự nét Kanji & Hanzi:</span>
                <p className="text-[11px] leading-relaxed">
                  Nhúng trường chứa sơ đồ nét bằng 3 dấu ngoặc nhọn <code className="font-mono">{`{{{StrokeDiagram}}}`}</code> vào Back Template (bọc trong <code className="font-mono">{`{{#StrokeDiagram}}...{{/StrokeDiagram}}`}</code>). Bạn có thể định dạng CSS <code className="font-mono">.flama-stroke-diagram img &#123; width: 72px; height: 72px; border-radius: 8px; &#125;</code> tùy ý!
                </p>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function NoteTypeAiGuideBanner({ onOpenGuide }: { onOpenGuide: () => void }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent p-4 sm:p-5 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start sm:items-center gap-3">
          <div className="p-2.5 rounded-xl bg-primary/20 text-primary shrink-0 mt-0.5 sm:mt-0">
            <Bot className="size-5" />
          </div>
          <div className="space-y-0.5">
            <h4 className="text-sm font-bold text-foreground flex items-center gap-1.5">
              Tạo Template Bằng AI Trong 1 Phút
              <Badge variant="secondary" className="text-[10px] py-0 px-1.5 bg-primary/10 text-primary border-primary/20">
                Mới
              </Badge>
            </h4>
            <p className="text-xs text-muted-foreground">
              Không cần biết lập trình! Dùng Prompt chuẩn cho ChatGPT / Claude để tự thiết kế mẫu thẻ Flashcard đúng ý bạn.
            </p>
          </div>
        </div>

        <Button
          onClick={onOpenGuide}
          size="sm"
          className="h-8 sm:h-9 px-3.5 text-xs font-bold rounded-xl shadow-xs shrink-0 bg-primary text-primary-foreground hover:bg-primary/90"
        >
          <Bot className="size-3.5 mr-1.5" />
          Mở Hướng Dẫn & Prompt AI
        </Button>
      </div>
    </div>
  )
}
