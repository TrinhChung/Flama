import { GitCompare } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FieldErrorMessage } from './PublishWizardTypes'

interface PublishStep4PricingProps {
  pricingMode: 'free' | 'paid'
  priceAmountMinor: number
  version: string
  isReleaseVersioned: boolean
  deckItemId: string
  fieldErrors: Record<string, string>
  setPricingMode: (mode: 'free' | 'paid') => void
  setPriceAmountMinor: (amount: number) => void
  setVersion: (ver: string) => void
  clearFieldError: (name: string) => void
}

export function PublishStep4Pricing({
  pricingMode,
  priceAmountMinor,
  version,
  isReleaseVersioned,
  deckItemId,
  fieldErrors,
  setPricingMode,
  setPriceAmountMinor,
  setVersion,
  clearFieldError,
}: PublishStep4PricingProps) {
  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Pricing Selector Cards */}
      <div className="space-y-2">
        <Label className="text-xs font-semibold">Mô hình phân phối & Giá bán</Label>
        <div className="grid grid-cols-2 gap-3">
          <div
            onClick={() => setPricingMode('free')}
            className={`p-4 rounded-xl border cursor-pointer transition-all text-center select-none ${
              pricingMode === 'free'
                ? 'border-primary bg-primary/10 text-foreground font-bold ring-2 ring-primary/30'
                : 'border-border bg-card hover:bg-muted/50 text-muted-foreground'
            }`}
          >
            <div className="font-bold text-sm sm:text-base">Miễn phí (Free)</div>
            <div className="text-xs opacity-80 mt-0.5">Chia sẻ tự do tới mọi người</div>
          </div>

          <div
            onClick={() => setPricingMode('paid')}
            className={`p-4 rounded-xl border cursor-pointer transition-all text-center select-none ${
              pricingMode === 'paid'
                ? 'border-primary bg-primary/10 text-foreground font-bold ring-2 ring-primary/30'
                : 'border-border bg-card hover:bg-muted/50 text-muted-foreground'
            }`}
          >
            <div className="font-bold text-sm sm:text-base">Có phí (Paid)</div>
            <div className="text-xs opacity-80 mt-0.5">Nhận thu nhập qua payOS</div>
          </div>
        </div>

        {pricingMode === 'paid' && (
          <div className="space-y-1.5 animate-in fade-in duration-200">
            <Label htmlFor="price" className="text-xs font-semibold">
              Giá bán niêm yết (VNĐ) <span className="text-destructive">*</span>
            </Label>
            <div className="relative">
              <Input
                id="price"
                type="number"
                min="1000"
                step="1000"
                value={priceAmountMinor || ''}
                onChange={(e) => {
                  setPriceAmountMinor(Number(e.target.value))
                  clearFieldError('price')
                }}
                className={`h-11 sm:h-10 text-sm rounded-xl pr-14 font-mono font-semibold ${
                  fieldErrors.price ? 'border-destructive bg-destructive/5' : ''
                }`}
              />
              <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground font-bold">
                VND
              </span>
            </div>
            <FieldErrorMessage error={fieldErrors.price} />
          </div>
        )}
      </div>

      {/* Version */}
      {isReleaseVersioned ? (
        <div className="flex flex-col gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold text-foreground">
              Phiên bản {version || 'hiện tại'} được khóa theo immutable release
            </p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Cập nhật listing không phát hành dữ liệu mới tới những người đã clone deck.
            </p>
          </div>
          <Button type="button" variant="outline" size="sm" asChild>
            <Link to={`/creator/decks/${deckItemId}/releases/new`}>
              <GitCompare className="size-3.5" />
              Tạo release mới
            </Link>
          </Button>
        </div>
      ) : (
        <div className="space-y-1.5">
          <Label htmlFor="version" className="text-xs font-semibold">Phiên bản phát hành</Label>
          <Input
            id="version"
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            className="h-10 text-xs sm:text-sm rounded-xl font-mono"
            placeholder="1.0.0"
          />
        </div>
      )}
    </div>
  )
}
