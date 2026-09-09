import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Printer, ArrowLeft, Sparkles, FileEdit, LayoutGrid, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { DeckWorksheetModal } from '../components/DeckWorksheetModal'

export function WorksheetsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const paramDeckId = searchParams.get('deckId') || searchParams.get('deck_id')
  const paramDeckName = searchParams.get('deckName') || searchParams.get('deck_name')
  const initialDeckId = useMemo(() => {
    if (!paramDeckId) return null
    const parsed = Number(paramDeckId)
    return Number.isFinite(parsed) ? parsed : null
  }, [paramDeckId])
  const [isStudioOpen, setIsStudioOpen] = useState<boolean>(true)

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/60 pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <div className="size-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shadow-xs">
              <Printer className="size-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
                  Mẫu giấy luyện viết & In bài tập (A4)
                </h1>
                <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 font-semibold">
                  Tự do & Không cần Deck
                </Badge>
              </div>
              <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
                Tạo trang trắng làm văn tiêu chuẩn (Genkō Yōshi / 作文纸 400 ô), ô chữ Hán, ô chữ thập để in ra luyện viết tay bằng bút mực.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/dashboard')}
            className="h-9 gap-1.5 text-xs font-semibold rounded-lg"
          >
            <ArrowLeft className="size-3.5" />
            <span>Quay lại</span>
          </Button>
          <Button
            size="sm"
            onClick={() => setIsStudioOpen(true)}
            className="h-9 gap-1.5 text-xs font-bold rounded-lg shadow-sm"
          >
            <Sparkles className="size-3.5" />
            <span>Mở Live Studio</span>
          </Button>
        </div>
      </div>

      {/* Feature Highlights Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
        <Card className="border-border/70 hover:border-primary/50 transition-all hover:shadow-xs">
          <CardHeader className="pb-2">
            <div className="size-8 rounded-lg bg-rose-500/10 text-rose-600 dark:text-rose-400 flex items-center justify-center mb-1">
              <FileEdit className="size-4" />
            </div>
            <CardTitle className="text-sm font-bold">Giấy làm văn 400 ô (Genkō Yōshi)</CardTitle>
            <CardDescription className="text-xs">
              Chuẩn 作文纸 20 cột × 20 dòng kèm dải đệm ngang giữa các hàng, dòng ghi họ tên và ngày tháng.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground space-y-1.5 pt-1 border-t border-border/40">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>In trang trắng sạch đẹp 100%</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>Hỗ trợ điền bài văn mẫu & tô chữ mờ</span>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsStudioOpen(true)}
              className="w-full mt-2 h-7.5 text-xs font-semibold"
            >
              Mở mẫu 400 ô &rarr;
            </Button>
          </CardContent>
        </Card>

        <Card className="border-border/70 hover:border-primary/50 transition-all hover:shadow-xs">
          <CardHeader className="pb-2">
            <div className="size-8 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center mb-1">
              <LayoutGrid className="size-4" />
            </div>
            <CardTitle className="text-sm font-bold">Lưới kẻ ô chữ Hán (Kanji Grid)</CardTitle>
            <CardDescription className="text-xs">
              Lưới ô chữ thập (+), hoa thị (*), ô trơn để luyện tập cấu trúc nét viết tay chữ Hán và Kana.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground space-y-1.5 pt-1 border-t border-border/40">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>Tuỳ chỉnh kích thước ô 28px - 44px</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>Màu mực xám than photocopy chuẩn nét</span>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsStudioOpen(true)}
              className="w-full mt-2 h-7.5 text-xs font-semibold"
            >
              Xem mẫu ô chữ Hán &rarr;
            </Button>
          </CardContent>
        </Card>

        <Card className="border-border/70 hover:border-primary/50 transition-all hover:shadow-xs">
          <CardHeader className="pb-2">
            <div className="size-8 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center mb-1">
              <Printer className="size-4" />
            </div>
            <CardTitle className="text-sm font-bold">Xuất file PDF & In ngay A4</CardTitle>
            <CardDescription className="text-xs">
              Tích hợp cơ chế print styling tự động căn lề chuẩn 0mm, không bị vỡ hàng, không thừa trang trắng.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground space-y-1.5 pt-1 border-t border-border/40">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>Khổ giấy A4 Dọc (Portrait) chuẩn</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>Xem trước trực tiếp theo thời gian thực</span>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsStudioOpen(true)}
              className="w-full mt-2 h-7.5 text-xs font-semibold"
            >
              In ngay &rarr;
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Standalone Live Studio Modal */}
      <DeckWorksheetModal
        open={isStudioOpen}
        onOpenChange={setIsStudioOpen}
        deckId={initialDeckId}
        deckName={paramDeckName || undefined}
      />
    </div>
  )
}
