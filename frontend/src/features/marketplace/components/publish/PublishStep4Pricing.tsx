import { GitCompare, GraduationCap } from 'lucide-react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCreditCard, faGift, faKey } from '@fortawesome/free-solid-svg-icons'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { FieldErrorMessage } from './PublishWizardTypes'

interface PublishStep4PricingProps {
  distributionMode: 'free' | 'paid' | 'course_key'
  pricingMode: 'free' | 'paid'
  priceAmountMinor: number
  studentOfferMode: 'none' | 'free' | 'percent_discount'
  studentDiscountPercent: number | null
  courseTitle: string
  courseDescription: string
  courseUrl: string
  courseInstructions: string
  version: string
  isReleaseVersioned: boolean
  deckItemId: string
  fieldErrors: Record<string, string>
  setDistributionMode: (mode: 'free' | 'paid' | 'course_key') => void
  setPricingMode: (mode: 'free' | 'paid') => void
  setPriceAmountMinor: (amount: number) => void
  setStudentOfferMode: (mode: 'none' | 'free' | 'percent_discount') => void
  setStudentDiscountPercent: (percent: number | null) => void
  setCourseTitle: (title: string) => void
  setCourseDescription: (desc: string) => void
  setCourseUrl: (url: string) => void
  setCourseInstructions: (inst: string) => void
  setVersion: (ver: string) => void
  clearFieldError: (name: string) => void
}

export function PublishStep4Pricing({
  distributionMode,
  priceAmountMinor,
  studentOfferMode,
  studentDiscountPercent,
  courseTitle,
  courseDescription,
  courseUrl,
  courseInstructions,
  version,
  isReleaseVersioned,
  deckItemId,
  fieldErrors,
  setDistributionMode,
  setPricingMode,
  setPriceAmountMinor,
  setStudentOfferMode,
  setStudentDiscountPercent,
  setCourseTitle,
  setCourseDescription,
  setCourseUrl,
  setCourseInstructions,
  setVersion,
  clearFieldError,
}: PublishStep4PricingProps) {
  const { t, i18n } = useTranslation('marketplace')
  const calculatedStudentPrice = Math.max(
    0,
    Math.round(priceAmountMinor * (1 - (studentDiscountPercent || 0) / 100))
  )

  const currencyUnit = i18n.language === 'en' ? ' VND' : ' đ'
  const formattedStudentPrice = calculatedStudentPrice.toLocaleString(
    i18n.language === 'en' ? 'en-US' : 'vi-VN'
  ) + currencyUnit

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Distribution Mode Selector Cards */}
      <div className="space-y-3">
        <Label className="text-xs font-semibold">
          {t('publish_deck.step4.section_title', 'Mô hình phân phối & Giá bán')}
        </Label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Free Option */}
          <div
            onClick={() => {
              setDistributionMode('free')
              setPricingMode('free')
              setStudentOfferMode('none')
              setStudentDiscountPercent(null)
            }}
            className={`p-4 rounded-xl border cursor-pointer transition-all text-center select-none ${
              distributionMode === 'free'
                ? 'border-primary bg-primary/5 text-foreground font-bold ring-1 ring-primary/30 shadow-2xs'
                : 'border-border/80 bg-card hover:bg-muted/40 text-muted-foreground'
            }`}
          >
            <div className="flex items-center justify-center mb-1.5 text-muted-foreground">
              <FontAwesomeIcon icon={faGift} className="size-4" />
            </div>
            <div className="font-bold text-sm sm:text-base">
              {t('publish_deck.step4.mode_free_title', 'Miễn phí (Free)')}
            </div>
            <div className="text-xs opacity-80 mt-0.5">
              {t('publish_deck.step4.mode_free_desc', 'Chia sẻ tự do tới mọi người')}
            </div>
          </div>

          {/* Paid Option */}
          <div
            onClick={() => {
              setDistributionMode('paid')
              setPricingMode('paid')
            }}
            className={`p-4 rounded-xl border cursor-pointer transition-all text-center select-none ${
              distributionMode === 'paid'
                ? 'border-primary bg-primary/5 text-foreground font-bold ring-1 ring-primary/30 shadow-2xs'
                : 'border-border/80 bg-card hover:bg-muted/40 text-muted-foreground'
            }`}
          >
            <div className="flex items-center justify-center mb-1.5 text-muted-foreground">
              <FontAwesomeIcon icon={faCreditCard} className="size-4" />
            </div>
            <div className="font-bold text-sm sm:text-base">
              {t('publish_deck.step4.mode_paid_title', 'Có phí (Paid)')}
            </div>
            <div className="text-xs opacity-80 mt-0.5">
              {t('publish_deck.step4.mode_paid_desc', 'Bán qua cổng payOS')}
            </div>
          </div>

          {/* Course Key Option */}
          <div
            onClick={() => {
              setDistributionMode('course_key')
              setPricingMode('free')
              setStudentOfferMode('none')
              setStudentDiscountPercent(null)
            }}
            className={`p-4 rounded-xl border cursor-pointer transition-all text-center select-none ${
              distributionMode === 'course_key'
                ? 'border-primary bg-primary/5 text-foreground font-bold ring-1 ring-primary/30 shadow-2xs'
                : 'border-border/80 bg-card hover:bg-muted/40 text-muted-foreground'
            }`}
          >
            <div className="flex items-center justify-center mb-1.5 text-muted-foreground">
              <FontAwesomeIcon icon={faKey} className="size-4" />
            </div>
            <div className="font-bold text-sm sm:text-base">
              {t('publish_deck.step4.mode_key_title', 'Mã lớp học (Keys)')}
            </div>
            <div className="text-xs opacity-80 mt-0.5">
              {t('publish_deck.step4.mode_key_desc', 'Kích hoạt qua Access Keys')}
            </div>
          </div>
        </div>

        {/* Paid Form Fields */}
        {distributionMode === 'paid' && (
          <div className="space-y-4 pt-1 animate-in fade-in duration-200">
            {/* Listed Base Price */}
            <div className="space-y-1.5">
              <Label htmlFor="price" className="text-xs font-semibold">
                {t('publish_deck.step4.price_label', 'Giá bán niêm yết (VNĐ)')} <span className="text-destructive">*</span>
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
                  {t('publish_deck.step4.student_offer_title', 'Ưu đãi dành cho sinh viên')}
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
                  {t('publish_deck.step4.student_opt_none', 'Không có ưu đãi')}
                </div>
                <div
                  onClick={() => setStudentOfferMode('free')}
                  className={`p-3 rounded-lg border text-xs cursor-pointer select-none text-center transition-all ${
                    studentOfferMode === 'free'
                      ? 'border-primary bg-primary/10 font-bold text-foreground ring-1 ring-primary/40'
                      : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                  }`}
                >
                  {t('publish_deck.step4.student_opt_free', 'Miễn phí cho SV')}
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
                  {t('publish_deck.step4.student_opt_discount', 'Giảm giá (%) cho SV')}
                </div>
              </div>

              {studentOfferMode === 'percent_discount' && (
                <div className="space-y-2 pt-1 animate-in fade-in duration-150">
                  <Label htmlFor="student_discount" className="text-xs font-semibold">
                    {t('publish_deck.step4.student_discount_percent_label', 'Mức giảm giá cho sinh viên (%)')} <span className="text-destructive">*</span>
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
                      {t('publish_deck.step4.student_price_label', 'Giá sinh viên trả:')}{' '}
                      <strong className="text-primary font-bold">
                        {formattedStudentPrice}
                      </strong>
                    </div>
                  </div>
                  <FieldErrorMessage error={fieldErrors.student_discount_percent} />
                </div>
              )}

              {studentOfferMode === 'free' && (
                <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium animate-in fade-in duration-150">
                  {t('publish_deck.step4.student_free_note', 'Sinh viên đã xác thực email trường (.edu.vn) sẽ được tải xuống & cài đặt bộ thẻ này hoàn toàn')}{' '}
                  <strong>0 đ</strong>.
                </p>
              )}

              <p className="text-[11px] leading-relaxed text-muted-foreground/80 pt-1">
                {t('publish_deck.step4.student_policy_note', 'Flama chỉ áp dụng ưu đãi này cho tài khoản đã được xác thực là sinh viên thông qua email trường có đuôi')}{' '}
                <code className="text-[10px] font-semibold bg-muted px-1 py-0.5 rounded text-foreground">.edu.vn</code>.
              </p>
            </div>
          </div>
        )}

        {/* Course Key Form Fields */}
        {distributionMode === 'course_key' && (
          <div className="space-y-4 pt-1 animate-in fade-in duration-200">
            <div className="rounded-xl border border-border/80 bg-muted/30 p-4 space-y-3.5">
              <div className="flex items-center gap-2">
                <GraduationCap className="size-4 text-muted-foreground" />
                <Label className="text-xs font-bold text-foreground">
                  {t('publish_deck.step4.course_info_title', 'Thông tin khóa học & Hướng dẫn nhận mã')}
                </Label>
              </div>

              {/* Course Title */}
              <div className="space-y-1.5">
                <Label htmlFor="course_title" className="text-xs font-semibold">
                  {t('publish_deck.step4.course_title_label', 'Tên khóa học / Lớp học')}
                </Label>
                <Input
                  id="course_title"
                  value={courseTitle}
                  onChange={(e) => setCourseTitle(e.target.value)}
                  placeholder={t('publish_deck.step4.course_title_placeholder', 'VD: Khóa Luyện thi JLPT N2 Cấp tốc 2026')}
                  className="h-10 text-xs sm:text-sm rounded-xl"
                />
              </div>

              {/* Course Description */}
              <div className="space-y-1.5">
                <Label htmlFor="course_description" className="text-xs font-semibold">
                  {t('publish_deck.step4.course_desc_label', 'Mô tả ngắn về khóa học')}
                </Label>
                <Textarea
                  id="course_description"
                  value={courseDescription}
                  onChange={(e) => setCourseDescription(e.target.value)}
                  placeholder={t('publish_deck.step4.course_desc_placeholder', 'VD: Dành riêng cho học viên lớp N2 Online K15. Bao gồm toàn bộ từ vựng và Kanji trọng tâm.')}
                  rows={2}
                  className="text-xs sm:text-sm rounded-xl resize-none"
                />
              </div>

              {/* Course URL */}
              <div className="space-y-1.5">
                <Label htmlFor="course_url" className="text-xs font-semibold">
                  {t('publish_deck.step4.course_url_label', 'Link trang web / Khóa học (nếu có)')}
                </Label>
                <Input
                  id="course_url"
                  type="url"
                  value={courseUrl}
                  onChange={(e) => setCourseUrl(e.target.value)}
                  placeholder={t('publish_deck.step4.course_url_placeholder', 'https://example.com/courses/n2-intensive')}
                  className="h-10 text-xs sm:text-sm rounded-xl"
                />
              </div>

              {/* Course Instructions */}
              <div className="space-y-1.5">
                <Label htmlFor="course_instructions" className="text-xs font-semibold">
                  {t('publish_deck.step4.course_instructions_label', 'Hướng dẫn học viên nhận mã kích hoạt')}
                </Label>
                <Textarea
                  id="course_instructions"
                  value={courseInstructions}
                  onChange={(e) => setCourseInstructions(e.target.value)}
                  placeholder={t('publish_deck.step4.course_instructions_placeholder', 'VD: Học viên liên hệ trợ giảng lớp qua nhóm Zalo hoặc kiểm tra email đăng ký khóa học để lấy mã kích hoạt.')}
                  rows={2}
                  className="text-xs sm:text-sm rounded-xl resize-none"
                />
              </div>

              <p className="text-[11px] leading-relaxed text-muted-foreground pt-1">
                {t('publish_deck.step4.course_hint', 'Gợi ý: Sau khi đăng tải deck, bạn có thể tạo hàng loạt')}{' '}
                <strong>{t('publish_deck.step4.access_keys_bold', 'Mã kích hoạt (Access Keys)')}</strong>{' '}
                {t('publish_deck.step4.course_hint_suffix', 'và theo dõi danh sách học viên đã kích hoạt trong trang chi tiết của bộ deck.')}
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
              {t('publish_deck.step4.version_locked_title', {
                version: version || t('publish_deck.step4.version_current', 'hiện tại'),
                defaultValue: `Phiên bản ${version || 'hiện tại'} được khóa theo immutable release`
              })}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {t('publish_deck.step4.version_locked_desc', 'Cập nhật listing không phát hành dữ liệu mới tới những người đã clone deck.')}
            </p>
          </div>
          <Button type="button" variant="outline" size="sm" asChild>
            <Link to={`/creator/decks/${deckItemId}/releases/new`}>
              <GitCompare className="size-3.5" />
              {t('publish_deck.step4.btn_create_release', 'Tạo release mới')}
            </Link>
          </Button>
        </div>
      ) : (
        <div className="space-y-1.5">
          <Label htmlFor="version" className="text-xs font-semibold">
            {t('publish_deck.step4.version_label', 'Phiên bản phát hành')}
          </Label>
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
