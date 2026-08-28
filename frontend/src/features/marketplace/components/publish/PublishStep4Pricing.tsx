import { GitCompare, GraduationCap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FieldErrorMessage } from './PublishWizardTypes'

interface PublishStep4PricingProps {
  pricingMode: 'free' | 'paid'
  priceAmountMinor: number
  studentOfferMode: 'none' | 'free' | 'percent_discount'
  studentDiscountPercent: number | null
  version: string
  isReleaseVersioned: boolean
  deckItemId: string
  fieldErrors: Record<string, string>
  setPricingMode: (mode: 'free' | 'paid') => void
  setPriceAmountMinor: (amount: number) => void
  setStudentOfferMode: (mode: 'none' | 'free' | 'percent_discount') => void
  setStudentDiscountPercent: (percent: number | null) => void
  setVersion: (ver: string) => void
  clearFieldError: (name: string) => void
}

export function PublishStep4Pricing({
  pricingMode,
  priceAmountMinor,
  studentOfferMode,
  studentDiscountPercent,
  version,
  isReleaseVersioned,
  deckItemId,
  fieldErrors,
  setPricingMode,
  setPriceAmountMinor,
  setStudentOfferMode,
  setStudentDiscountPercent,
  setVersion,
  clearFieldError,
}: PublishStep4PricingProps) {
  const calculatedStudentPrice = Math.max(
    0,
    Math.round(priceAmountMinor * (1 - (studentDiscountPercent || 0) / 100))
  )

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Pricing Selector Cards */}
      <div className="space-y-3">
        <Label className="text-xs font-semibold">Mô hình phân phối & Giá bán</Label>
        <div className="grid grid-cols-2 gap-3">
          <div
            onClick={() => {
              setPricingMode('free')
              setStudentOfferMode('none')
              setStudentDiscountPercent(null)
            }}
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
            <div className="text-xs opacity-80 mt-0.5">Bán nội dung có thu phí</div>
          </div>
        </div>

        {pricingMode === 'paid' && (
          <div className="space-y-4 pt-1 animate-in fade-in duration-200">
            {/* Listed Base Price */}
            <div className="space-y-1.5">
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

            {/* Student Offer Card */}
            <div className="rounded-xl border border-border/80 bg-muted/30 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <GraduationCap className="size-4 text-primary" />
                <Label className="text-xs font-bold text-foreground">
                  Ưu đãi dành cho sinh viên
                </Label>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <div
                  onClick={() => setStudentOfferMode('none')}
                  className={`p-3 rounded-lg border text-xs cursor-pointer select-none text-center transition-all ${
                    studentOfferMode === 'none'
                      ? 'border-primary bg-primary/10 font-bold text-foreground ring-1 ring-primary/40'
                      : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                  }`}
                >
                  Không có ưu đãi
                </div>
                <div
                  onClick={() => setStudentOfferMode('free')}
                  className={`p-3 rounded-lg border text-xs cursor-pointer select-none text-center transition-all ${
                    studentOfferMode === 'free'
                      ? 'border-primary bg-primary/10 font-bold text-foreground ring-1 ring-primary/40'
                      : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                  }`}
                >
                  Miễn phí cho SV
                </div>
                <div
                  onClick={() => {
                    setStudentOfferMode('percent_discount')
                    if (!studentDiscountPercent) setStudentDiscountPercent(30)
                  }}
                  className={`p-3 rounded-lg border text-xs cursor-pointer select-none text-center transition-all ${
                    studentOfferMode === 'percent_discount'
                      ? 'border-primary bg-primary/10 font-bold text-foreground ring-1 ring-primary/40'
                      : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                  }`}
                >
                  Giảm giá (%) cho SV
                </div>
              </div>

              {studentOfferMode === 'percent_discount' && (
                <div className="space-y-2 pt-1 animate-in fade-in duration-150">
                  <Label htmlFor="student_discount" className="text-xs font-semibold">
                    Mức giảm giá cho sinh viên (%) <span className="text-destructive">*</span>
                  </Label>
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="relative w-36">
                      <Input
                        id="student_discount"
                        type="number"
                        min="1"
                        max="99"
                        value={studentDiscountPercent || ''}
                        onChange={(e) => {
                          const val = Number(e.target.value)
                          setStudentDiscountPercent(val > 0 ? val : null)
                          clearFieldError('student_discount_percent')
                        }}
                        className="h-10 text-sm rounded-xl pr-8 font-mono font-semibold"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground font-bold">
                        %
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Giá sinh viên trả:{' '}
                      <strong className="text-primary font-bold">
                        {calculatedStudentPrice.toLocaleString('vi-VN')} đ
                      </strong>
                    </div>
                  </div>
                  <FieldErrorMessage error={fieldErrors.student_discount_percent} />
                </div>
              )}

              {studentOfferMode === 'free' && (
                <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium animate-in fade-in duration-150">
                  Sinh viên đã xác thực email trường (.edu.vn) sẽ được tải xuống & cài đặt bộ thẻ này hoàn toàn <strong>0 đ</strong>.
                </p>
              )}

              <p className="text-[11px] leading-relaxed text-muted-foreground/80 pt-1">
                Flama chỉ áp dụng ưu đãi này cho tài khoản đã được xác thực là sinh viên thông qua email trường có đuôi <code className="text-[10px] font-semibold bg-muted px-1 py-0.5 rounded text-foreground">.edu.vn</code>.
              </p>
            </div>
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
