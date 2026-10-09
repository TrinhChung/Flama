import { useState } from 'react'
import { useTranslation } from 'react-i18next'
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
import { getMasterPrompt, getExampleVocabPrompt } from './guide/guidePrompts'

export interface NoteTypeAiGuideModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function NoteTypeAiGuideModal({ open, onOpenChange }: NoteTypeAiGuideModalProps) {
  const { t, i18n } = useTranslation('note_types')
  const [activeTab, setActiveTab] = useState('prompt')
  const [copiedMaster, setCopiedMaster] = useState(false)
  const [copiedExample, setCopiedExample] = useState(false)

  const masterPrompt = getMasterPrompt(i18n.language)
  const exampleVocabPrompt = getExampleVocabPrompt(i18n.language)

  const copyToClipboard = (text: string, isExample = false) => {
    navigator.clipboard.writeText(text).then(() => {
      if (isExample) {
        setCopiedExample(true)
        setTimeout(() => setCopiedExample(false), 2000)
      } else {
        setCopiedMaster(true)
        setTimeout(() => setCopiedMaster(false), 2000)
      }
      toast.success(t('ai_modal.toast_title', 'Đã sao chép prompt vào Clipboard!'), {
        description: t('ai_modal.toast_desc', 'Hãy mở ChatGPT, Claude hoặc Gemini và dán prompt này vào.'),
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
                {t('ai_modal.dialog_title', 'Hướng Dẫn & Prompt AI Tạo Template NoteType')}
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                {t('ai_modal.dialog_desc', 'Dùng AI (ChatGPT, Claude, Gemini) tạo mẫu thẻ Flashcard đúng chuẩn Flama trong 1 phút.')}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="p-4 sm:p-6 overflow-y-auto flex-1 space-y-4">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid grid-cols-2 sm:grid-cols-4 w-full h-auto p-1 mb-4 rounded-xl bg-muted/60 gap-1">
              <TabsTrigger value="prompt" className="h-8 sm:h-9 text-xs font-semibold rounded-lg">
                {t('ai_modal.tab_prompt', '🤖 Prompt AI')}
              </TabsTrigger>
              <TabsTrigger value="tech" className="h-8 sm:h-9 text-xs font-semibold rounded-lg">
                {t('ai_modal.tab_tech', '⚙️ Công Nghệ')}
              </TabsTrigger>
              <TabsTrigger value="steps" className="h-8 sm:h-9 text-xs font-semibold rounded-lg">
                {t('ai_modal.tab_steps', '🚀 Các Bước')}
              </TabsTrigger>
              <TabsTrigger value="rules" className="h-8 sm:h-9 text-xs font-semibold rounded-lg">
                {t('ai_modal.tab_rules', '⚠️ Tránh Lỗi')}
              </TabsTrigger>
            </TabsList>

            {/* TAB 1: MASTER PROMPT */}
            <TabsContent value="prompt" className="space-y-4 mt-0">
              <div className="p-3 rounded-xl bg-primary/5 border border-primary/20 text-xs text-foreground flex items-start gap-2.5">
                <Lightbulb className="size-4 text-primary shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-primary">{t('ai_modal.simple_usage_title', 'Cách sử dụng đơn giản:')}</span>{' '}
                  {t(
                    'ai_modal.simple_usage_desc',
                    'Sao chép Master Prompt dưới đây, sửa phần [YÊU CẦU CỦA TÔI] theo ý bạn rồi gửi cho AI. AI sẽ tự viết đầy đủ danh sách trường, Front HTML, Back HTML và CSS đúng chuẩn Flama.'
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-foreground">
                    {t('ai_modal.master_heading', '📋 Master Prompt Chuẩn:')}
                  </span>
                  <Button
                    size="sm"
                    onClick={() => copyToClipboard(masterPrompt)}
                    className="h-8 px-3 text-xs font-bold rounded-xl shadow-xs"
                  >
                    {copiedMaster ? <Check className="size-3.5 mr-1 text-emerald-300" /> : <Copy className="size-3.5 mr-1" />}
                    {copiedMaster ? t('ai_modal.copied_master', 'Đã sao chép') : t('ai_modal.copy_master', 'Sao chép Master Prompt')}
                  </Button>
                </div>
                <pre className="p-3.5 rounded-xl bg-muted/60 border border-border/80 font-mono text-[11px] leading-relaxed text-foreground/90 overflow-x-auto max-h-56 select-all whitespace-pre-wrap">
                  {masterPrompt}
                </pre>
              </div>

              <div className="space-y-2 pt-2 border-t">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-foreground">
                    {t('ai_modal.example_heading', '💡 Ví dụ mẫu [YÊU CẦU CỦA TÔI] cho Thẻ Từ Vựng:')}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => copyToClipboard(exampleVocabPrompt, true)}
                    className="h-7 px-2.5 text-[11px] font-semibold rounded-lg"
                  >
                    {copiedExample ? <Check className="size-3 mr-1 text-emerald-500" /> : <Copy className="size-3 mr-1" />}
                    {copiedExample ? t('ai_modal.copied_example', 'Đã chép ví dụ') : t('ai_modal.copy_example', 'Sao chép ví dụ này')}
                  </Button>
                </div>
                <pre className="p-3 rounded-xl bg-muted/40 border border-border/60 font-mono text-[11px] leading-relaxed text-muted-foreground overflow-x-auto max-h-36 whitespace-pre-wrap">
                  {exampleVocabPrompt}
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
  const { t } = useTranslation('note_types')
  return (
    <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent p-4 sm:p-5 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start sm:items-center gap-3">
          <div className="p-2.5 rounded-xl bg-primary/20 text-primary shrink-0 mt-0.5 sm:mt-0">
            <Bot className="size-5" />
          </div>
          <div className="space-y-0.5">
            <h4 className="text-sm font-bold text-foreground flex items-center gap-1.5">
              {t('manager.header.ai_prompt_banner_title', 'Tạo Template Bằng AI Trong 1 Phút')}
              <Badge variant="secondary" className="text-[10px] py-0 px-1.5 bg-primary/10 text-primary border-primary/20">
                {t('editor.badge_new', 'Mới')}
              </Badge>
            </h4>
            <p className="text-xs text-muted-foreground">
              {t('manager.header.ai_prompt_banner_desc', 'Không cần biết lập trình! Dùng Prompt chuẩn cho ChatGPT / Claude để tự thiết kế mẫu thẻ Flashcard đúng ý bạn.')}
            </p>
          </div>
        </div>

        <Button
          onClick={onOpenGuide}
          size="sm"
          className="h-8 sm:h-9 px-3.5 text-xs font-bold rounded-xl shadow-xs shrink-0 bg-primary text-primary-foreground hover:bg-primary/90"
        >
          <Bot className="size-3.5 mr-1.5" />
          {t('manager.header.ai_prompt_banner_btn', 'Mở Hướng Dẫn & Prompt AI')}
        </Button>
      </div>
    </div>
  )
}
