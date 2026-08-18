import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TabsContent } from '@/components/ui/tabs'
import { toast } from 'sonner'
import {
  Check,
  Code,
  Copy,
  FolderTree,
  ListPlus,
  MessageSquareCode,
  PlusCircle,
  Search,
  Timer,
  Wrench,
} from 'lucide-react'

type ToolItem = {
  name: string
  title: string
  scope: string
  icon: typeof Wrench
  description: string
  samplePrompt: string
}

const MCP_TOOLS_CATALOG: ToolItem[] = [
  {
    name: 'list_my_decks',
    title: 'Danh sách Bộ thẻ (Decks)',
    scope: 'deck:read',
    icon: FolderTree,
    description: 'Liệt kê toàn bộ các bộ thẻ Flashcard mà bạn sở hữu hoặc có quyền truy cập.',
    samplePrompt: 'Hãy liệt kê cho tôi tất cả các bộ thẻ flashcard tiếng Nhật hiện có trong tài khoản của tôi.',
  },
  {
    name: 'get_deck_tree',
    title: 'Cây thư mục Bộ thẻ',
    scope: 'deck:read',
    icon: FolderTree,
    description: 'Lấy cấu trúc cây thư mục phân cấp cha-con của tất cả các bộ thẻ học tập.',
    samplePrompt: 'Cho tôi xem cấu trúc cây thư mục các bộ thẻ của tôi để tôi biết nên tạo thẻ vào deck con nào.',
  },
  {
    name: 'list_note_types',
    title: 'Danh sách Loại thẻ (Note Types)',
    scope: 'note-type:read',
    icon: Code,
    description: 'Lấy danh sách các Note Types (mẫu định dạng thẻ) có sẵn để chọn cấu trúc trường phù hợp.',
    samplePrompt: 'Hãy kiểm tra xem tôi có những loại Note Type nào (ví dụ: Từ vựng, Hán tự, Ngữ pháp)?',
  },
  {
    name: 'get_note_type_schema',
    title: 'Schema Trường dữ liệu',
    scope: 'note-type:read',
    icon: Code,
    description: 'Xem chi tiết các trường dữ liệu (Word, Reading, Meaning, Example) và mẫu hiển thị của Note Type.',
    samplePrompt: 'Lấy schema chi tiết của note type "Japanese Vocabulary" để biết tôi cần điền những trường nào khi tạo thẻ.',
  },
  {
    name: 'find_notes',
    title: 'Tìm kiếm Thẻ Flashcard',
    scope: 'note:check',
    icon: Search,
    description: 'Tìm kiếm thẻ flashcard trong tài khoản theo từ khóa hoặc nội dung bất kỳ trường nào.',
    samplePrompt: 'Tìm xem trong các bộ thẻ của tôi đã có từ "環境" (kankyou) chưa?',
  },
  {
    name: 'create_note',
    title: 'Tạo 1 Thẻ Flashcard mới',
    scope: 'note:create',
    icon: PlusCircle,
    description: 'Tạo một thẻ học mới vào bộ chỉ định với các trường dữ liệu và tags, tự động sinh thẻ Flashcard.',
    samplePrompt: 'Hãy tạo một thẻ từ vựng vào deck "JLPT N2" với từ: 把握 (はあく - Nắm bắt, thấu hiểu), ví dụ: "状況を正確に把握する".',
  },
  {
    name: 'batch_create_notes',
    title: 'Tạo Thẻ hàng loạt (Batch)',
    scope: 'note:create',
    icon: ListPlus,
    description: 'Tạo nhanh hàng loạt thẻ flashcard (tối đa 50 thẻ) trong cùng một thao tác an toàn.',
    samplePrompt: 'Tạo giúp tôi 5 thẻ từ vựng JLPT N3 về chủ đề du lịch vào deck "N3 Vocabulary".',
  },
  {
    name: 'get_due_card_counts',
    title: 'Thống kê Thẻ đến hạn học',
    scope: 'deck:read',
    icon: Timer,
    description: 'Kiểm tra số lượng thẻ đến hạn ôn tập hôm nay (thẻ mới, thẻ review, thẻ đang học).',
    samplePrompt: 'Hôm nay tôi có bao nhiêu thẻ flashcard cần ôn tập trong các bộ thẻ?',
  },
]

export function McpToolsTab() {
  const [copiedName, setCopiedName] = useState<string | null>(null)

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

  return (
    <TabsContent value="tools" className="space-y-6">
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
            <Wrench className="size-5 text-primary shrink-0" />
            Danh mục 8 Công cụ MCP & Câu lệnh Prompt mẫu
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm">
            AI Assistant sẽ tự động gọi các công cụ này dựa trên câu hỏi hoặc yêu cầu tự nhiên của bạn.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0 space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {MCP_TOOLS_CATALOG.map((tool) => {
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
                      Câu lệnh mẫu cho AI (Prompt):
                    </div>
                    <div className="flex items-center justify-between gap-2 bg-muted/40 p-2 rounded-lg border text-xs text-foreground/90 italic">
                      <span className="line-clamp-2">"{tool.samplePrompt}"</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="shrink-0 h-7 px-2 text-[11px] gap-1"
                        onClick={() => copyPrompt(tool.name, tool.samplePrompt)}
                      >
                        {copiedName === tool.name ? (
                          <Check className="size-3 text-emerald-600" />
                        ) : (
                          <Copy className="size-3" />
                        )}
                        {copiedName === tool.name ? 'Đã chép' : 'Sao chép'}
                      </Button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>
    </TabsContent>
  )
}
