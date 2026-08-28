import { Lock, ShieldCheck } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'

export function PayoutNoticeCard({ message }: { message?: string }) {
  return (
    <Card className="border-border/60 bg-muted/20">
      <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3.5">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <ShieldCheck className="size-5" />
          </div>
          <div className="space-y-1 text-xs">
            <h4 className="font-semibold text-foreground">
              Bảo đảm an toàn số dư & Rút tiền
            </h4>
            <p className="text-muted-foreground leading-relaxed">
              {message ||
                'Chức năng rút tiền trực tiếp về tài khoản ngân hàng đang được chuẩn bị. Toàn bộ doanh thu bán Deck được hạch toán minh bạch và bảo đảm an toàn trên hệ thống Flama.'}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2 self-start rounded-full border border-border/80 bg-background px-3 py-1.5 text-xs text-muted-foreground sm:self-center">
          <Lock className="size-3.5 text-amber-500" />
          <span>Tự động kết toán</span>
        </div>
      </CardContent>
    </Card>
  )
}
