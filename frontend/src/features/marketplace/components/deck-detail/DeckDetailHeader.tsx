import {
  ArrowLeft,
  BookOpen,
  CheckCircle,
  Download,
  ExternalLink,
  FileDiff,
  GraduationCap,
  Heart,
  KeyRound,
  Layers,
  Loader2,
  Star,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useTranslation } from 'react-i18next'

interface DeckDetailHeaderProps {
  id: string
  deck: {
    primary_category?: string | null
    student_offer_mode?: string
    student_discount_percent?: number | null
    distribution_mode?: 'free' | 'paid' | 'course_key'
    requires_access_key?: boolean
    student_discount_applied?: boolean
    price_display?: string
    effective_price_display?: string
    effective_price_amount_minor?: number
    pricing_mode?: string
    author?: { id: number; username: string } | null
    author_profile?: {
      username?: string
      published_count?: number
    }
    updated_at?: string
    description?: string | null
    rating_avg: number
    rating_count: number
    install_count: number
    lesson_count?: number
    note_count?: number
    is_owner: boolean
    is_installed: boolean
    installed_deck_id?: number | null
    is_saved: boolean
    has_student_offer?: boolean
    user_student_status?: string
    course_title?: string | null
    course_description?: string | null
    course_url?: string | null
    course_instructions?: string | null
  }
  authorName: string
  deckTitle: string
  tagsList: string[]
  sampleLength: number
  onSave: () => void
  isSavePending: boolean
  onInstall: () => void
  isInstallPending: boolean
  onOpenRedeemModal: () => void
  ownerBarNode?: React.ReactNode
}

export function DeckDetailHeader({
  id,
  deck,
  authorName,
  deckTitle,
  tagsList,
  sampleLength,
  onSave,
  isSavePending,
  onInstall,
  isInstallPending,
  onOpenRedeemModal,
  ownerBarNode,
}: DeckDetailHeaderProps) {
  const { t, i18n } = useTranslation('marketplace')
  const dateLocale = i18n.language === 'en' ? 'en-US' : 'vi-VN'
  const numberLocale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  return (
    <Card className="border-border shadow-xs overflow-hidden rounded-2xl sm:rounded-3xl">
      <CardHeader className="p-4 sm:p-6 pb-4 sm:pb-5 space-y-3 sm:space-y-4">
        {/* Breadcrumb & Navigation */}
        <div className="flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            asChild
            className="-ml-2 h-8 text-xs font-semibold text-muted-foreground hover:text-foreground rounded-lg"
          >
            <Link to="/marketplace/decks">
              <ArrowLeft className="mr-1.5 size-3.5" />
              {t('detail.back_to_market', 'Quay lại Marketplace')}
            </Link>
          </Button>
        </div>

        {/* Badges & Pricing Strip */}
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
            <Badge
              variant="outline"
              className="text-xs font-bold px-2.5 py-0.5 rounded-full border-border/80 bg-muted/40 text-foreground"
            >
              {deck.primary_category || t('card.general_category', 'Chung')}
            </Badge>
            {deck.student_offer_mode && deck.student_offer_mode !== 'none' && (
              <Badge className="bg-emerald-500/15 text-emerald-700 border-emerald-500/30 dark:text-emerald-300 font-bold shadow-xs">
                <GraduationCap className="mr-1 size-3 text-emerald-600 dark:text-emerald-400" />
                {deck.student_offer_mode === 'free'
                  ? t('publish_deck.step4.student_opt_free', 'Miễn phí cho SV')
                  : t('detail.student_offer.discount_apply', {
                      percent: deck.student_discount_percent,
                      defaultValue: `Giảm ${deck.student_discount_percent}% SV`,
                    })}
              </Badge>
            )}
            {deck.distribution_mode === 'course_key' || deck.requires_access_key ? (
              <Badge className="bg-purple-500/15 text-purple-700 border-purple-500/30 dark:text-purple-300 font-bold shadow-xs">
                <KeyRound className="mr-1 size-3 text-purple-600 dark:text-purple-400" />
                {t('card.course_key_badge', 'Mã khóa học')}
              </Badge>
            ) : null}
          </div>

          {deck.distribution_mode === 'course_key' || deck.requires_access_key ? (
            <span className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-extrabold border bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/30">
              <KeyRound className="size-3.5 text-purple-600 dark:text-purple-400" />
              {t('card.course_key_badge', 'Mã khóa học')}
            </span>
          ) : deck.student_discount_applied ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground line-through font-semibold">
                {deck.price_display}
              </span>
              <span className="inline-flex items-center rounded-full px-3 py-1 text-xs font-extrabold border bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30">
                <GraduationCap className="mr-1 size-3.5 text-emerald-600 dark:text-emerald-400" />
                {deck.effective_price_display || t('card.free', 'Miễn phí')}
              </span>
            </div>
          ) : (
            <span
              className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-extrabold border ${
                deck.pricing_mode === 'free'
                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                  : 'bg-primary/10 text-primary border-primary/30'
              }`}
            >
              {deck.price_display || t('card.free', 'Miễn phí')}
            </span>
          )}
        </div>

        <CardTitle className="text-2xl font-black tracking-tight text-foreground sm:text-3xl lg:text-4xl leading-tight">
          {deckTitle}
        </CardTitle>

        <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-muted-foreground pt-0.5">
          {deck.author?.username || deck.author_profile?.username ? (
            <Link
              to={`/profile/${deck.author?.username || deck.author_profile?.username}`}
              className="flex items-center gap-2 hover:text-primary transition-colors group/author"
            >
              <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-xs ring-1 ring-primary/20 group-hover/author:ring-primary">
                {authorName.charAt(0).toUpperCase()}
              </div>
              <div className="flex items-center gap-1.5 font-semibold text-foreground group-hover/author:text-primary">
                <span>{authorName}</span>
                <span className="text-muted-foreground font-normal hidden sm:inline">
                  ({deck.author_profile?.published_count || 1}{' '}
                  {t('detail.author.published_decks_suffix', 'bộ thẻ đã xuất bản')})
                </span>
              </div>
            </Link>
          ) : (
            <div className="flex items-center gap-2">
              <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-xs ring-1 ring-primary/20">
                {authorName.charAt(0).toUpperCase()}
              </div>
              <div className="flex items-center gap-1.5 font-semibold text-foreground">
                <span>{authorName}</span>
                <span className="text-muted-foreground font-normal hidden sm:inline">
                  ({deck.author_profile?.published_count || 1}{' '}
                  {t('detail.author.published_decks_suffix', 'bộ thẻ đã xuất bản')})
                </span>
              </div>
            </div>
          )}
          <span className="text-muted-foreground/40 hidden sm:inline">•</span>
          <span className="inline-flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md text-[11px]">
            <CheckCircle className="size-3" /> Flama Marketplace
          </span>
          {deck.updated_at ? (
            <>
              <span className="text-muted-foreground/40 hidden sm:inline">•</span>
              <span className="text-muted-foreground text-[11px]">
                {t('common.updated_at', 'Cập nhật')}:{' '}
                {new Date(deck.updated_at).toLocaleDateString(dateLocale)}
              </span>
            </>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="p-4 sm:p-6 pt-0 space-y-4 sm:space-y-5">
        {deck.description ? (
          <p className="text-xs sm:text-sm leading-relaxed text-muted-foreground/90 font-normal">
            {deck.description}
          </p>
        ) : null}

        {tagsList.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {tagsList.map((tag) => (
              <Badge
                key={tag}
                variant="outline"
                className="text-[11px] text-muted-foreground font-medium px-2.5 py-0.5 rounded-md hover:bg-muted/50 transition-colors"
              >
                #{tag}
              </Badge>
            ))}
          </div>
        ) : null}

        {/* Stat Grid */}
        <div className="grid grid-cols-2 gap-2.5 sm:gap-3.5 sm:grid-cols-4">
          <div className="rounded-xl border border-border/80 bg-muted/30 p-3 sm:p-4 text-center transition-all hover:bg-muted/50">
            <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
              <Star className="size-3.5 fill-amber-400 text-amber-500" />
              <span>{t('detail.author.rating', 'Đánh giá')}</span>
            </div>
            <div className="mt-1 flex items-center justify-center gap-1 font-extrabold text-lg sm:text-2xl text-foreground font-mono">
              <span className="tabular-nums">{deck.rating_avg.toFixed(1)}</span>
              <span className="text-xs font-normal text-muted-foreground font-sans tabular-nums">
                ({deck.rating_count})
              </span>
            </div>
          </div>

          <div className="rounded-xl border border-border/80 bg-muted/30 p-3 sm:p-4 text-center transition-all hover:bg-muted/50">
            <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
              <Download className="size-3.5 text-primary" />
              <span>{t('card.install_unit', 'Lượt cài')}</span>
            </div>
            <div className="mt-1 font-extrabold text-lg sm:text-2xl text-foreground tabular-nums font-mono">
              {deck.install_count.toLocaleString(numberLocale)}
            </div>
          </div>

          <div className="rounded-xl border border-border/80 bg-muted/30 p-3 sm:p-4 text-center transition-all hover:bg-muted/50">
            <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
              <BookOpen className="size-3.5 text-primary" />
              <span>{t('card.lesson_unit', 'Bài học')}</span>
            </div>
            <div className="mt-1 font-extrabold text-lg sm:text-2xl text-foreground tabular-nums font-mono">
              {deck.lesson_count ? `${deck.lesson_count} ${t('card.lesson_unit', 'bài')}` : `1 ${t('card.lesson_unit', 'bài')}`}
            </div>
          </div>

          <div className="rounded-xl border border-border/80 bg-muted/30 p-3 sm:p-4 text-center transition-all hover:bg-muted/50">
            <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
              <Layers className="size-3.5 text-primary" />
              <span>{t('card.note_unit', 'Từ vựng')}</span>
            </div>
            <div className="mt-1 font-extrabold text-lg sm:text-2xl text-foreground tabular-nums font-mono">
              {(deck.note_count || sampleLength).toLocaleString(numberLocale)} {t('card.note_unit', 'từ')}
            </div>
          </div>
        </div>

        {/* Integrated Primary Action Area */}
        <div className="pt-3 border-t border-border/60">
          {deck.is_owner ? (
            ownerBarNode
          ) : deck.is_installed ? (
            <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-2.5">
              {deck.installed_deck_id ? (
                <Button
                  className="h-11 sm:h-11 min-h-[44px] px-5 font-bold text-sm shadow-xs bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl transition-all justify-center"
                  asChild
                >
                  <Link to={`/study?deck_id=${deck.installed_deck_id}`}>
                    <BookOpen className="mr-2 size-4" />
                    {t('detail.btn_study_now', 'Bắt đầu học ngay')}
                  </Link>
                </Button>
              ) : null}

              <div className="inline-flex items-center justify-center gap-1.5 h-11 min-h-[44px] px-4 font-bold text-xs sm:text-sm border border-emerald-500/40 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 rounded-xl">
                <CheckCircle className="size-4 text-emerald-500" />
                {t('detail.installed_badge', 'Đã cài đặt vào thư viện')}
              </div>

              <Button
                className="h-11 min-h-[44px] px-4 font-semibold text-xs sm:text-sm rounded-xl justify-center"
                variant="outline"
                asChild
              >
                <Link to={`/flashcards/shared-decks/${id}/change-request`}>
                  <FileDiff className="mr-1.5 size-4" />
                  {t('detail.btn_change_request', 'Đóng góp chỉnh sửa')}
                </Link>
              </Button>

              <Button
                className="h-11 min-h-[44px] px-4 font-semibold text-xs sm:text-sm rounded-xl justify-center"
                variant="outline"
                onClick={onSave}
                disabled={isSavePending}
              >
                <Heart
                  className={`mr-1.5 size-4 ${
                    deck.is_saved ? 'fill-primary text-primary' : ''
                  }`}
                />
                {deck.is_saved
                  ? t('detail.saved_btn', 'Đã lưu')
                  : t('detail.save_btn', 'Lưu bộ deck')}
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {(deck.distribution_mode === 'course_key' || deck.requires_access_key) && (
                <div className="w-full rounded-xl border border-purple-500/30 bg-purple-500/10 p-3.5 sm:p-4 text-xs sm:text-sm text-purple-900 dark:text-purple-300 space-y-2">
                  <div className="flex items-center gap-2 font-bold text-sm sm:text-base text-purple-800 dark:text-purple-200">
                    <GraduationCap className="size-5 text-purple-600 dark:text-purple-400" />
                    <span>{t('detail.course_banner.title', 'Học liệu độc quyền dành cho Khóa học')}</span>
                  </div>
                  <p className="text-xs leading-relaxed text-purple-800/90 dark:text-purple-300/90">
                    {t(
                      'detail.course_banner.desc',
                      'Bộ thẻ này được thiết kế và quản lý bởi giảng viên cho lớp học cụ thể. Học viên cần có Mã kích hoạt (Access Key) từ giảng viên hoặc trung tâm để mở khóa và học tập.'
                    )}
                  </p>
                  {deck.course_title && (
                    <div className="pt-2 border-t border-purple-500/20 text-xs">
                      <span className="font-semibold">{t('publish_deck.step4.course_title_label', 'Khóa học')}: </span>
                      <strong className="font-bold text-purple-900 dark:text-purple-100">{deck.course_title}</strong>
                    </div>
                  )}
                  {deck.course_description && (
                    <p className="text-xs italic text-purple-800/80 dark:text-purple-300/80">
                      {deck.course_description}
                    </p>
                  )}
                  {deck.course_url && (
                    <div className="pt-1 flex items-center gap-1.5 text-xs">
                      <span className="font-semibold">{t('publish_deck.step4.course_url_label', 'Trang thông tin khóa học')}:</span>
                      <a
                        href={deck.course_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 font-bold text-purple-700 dark:text-purple-300 underline hover:text-purple-900 dark:hover:text-purple-100"
                      >
                        <span>{deck.course_url}</span>
                        <ExternalLink className="size-3" />
                      </a>
                    </div>
                  )}
                  {deck.course_instructions && (
                    <div className="pt-2 border-t border-purple-500/20 text-xs">
                      <span className="font-semibold">{t('publish_deck.step4.course_instructions_label', 'Hướng dẫn nhận mã')}: </span>
                      <span>{deck.course_instructions}</span>
                    </div>
                  )}
                </div>
              )}

              {deck.has_student_offer && deck.user_student_status === 'eligible_unverified_email' && (
                <div className="w-full rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-300 flex items-start gap-2">
                  <GraduationCap className="size-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
                  <div className="flex-1 leading-relaxed">
                    <span>{t('detail.student_offer.edu_detected', 'Bạn đang sử dụng email trường học (.edu.vn).')} </span>
                    <Link to="/profile" className="font-bold underline hover:opacity-80">
                      {t('detail.student_offer.verify_email_link', 'Xác thực email trong trang Hồ sơ')}
                    </Link>
                    <span> {t('detail.student_offer.to_receive_offer', {
                      offer: deck.student_offer_mode === 'free'
                        ? t('publish_deck.step4.student_opt_free', 'miễn phí bộ thẻ này')
                        : `giảm ${deck.student_discount_percent}%`,
                      defaultValue: `để nhận ưu đãi ${deck.student_offer_mode === 'free' ? 'miễn phí bộ thẻ này' : `giảm ${deck.student_discount_percent}%`}!`,
                    })}</span>
                  </div>
                </div>
              )}

              <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-3">
                {deck.distribution_mode === 'course_key' || deck.requires_access_key ? (
                  <Button
                    className="h-11 sm:h-12 min-h-[44px] px-6 font-bold text-sm sm:text-base shadow-sm bg-purple-600 hover:bg-purple-700 text-white rounded-xl transition-all justify-center"
                    size="lg"
                    onClick={onOpenRedeemModal}
                  >
                    <KeyRound className="mr-2 size-5" />
                    {t('detail.course_banner.btn_redeem', 'Nhập mã kích hoạt khóa học')}
                  </Button>
                ) : (
                  <>
                    <Button
                      className="h-11 sm:h-12 min-h-[44px] px-6 font-bold text-sm sm:text-base shadow-sm bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl transition-all justify-center"
                      size="lg"
                      onClick={onInstall}
                      disabled={isInstallPending}
                    >
                      {isInstallPending ? (
                        <>
                          <Loader2 className="mr-2 size-5 animate-spin" />
                          {deck.pricing_mode === 'paid' && (!deck.student_discount_applied || deck.effective_price_amount_minor !== 0)
                            ? t('detail.creating_payment', 'Đang tạo thanh toán…')
                            : t('detail.installing', 'Đang cài đặt bộ thẻ…')}
                        </>
                      ) : (
                        <>
                          <Download className="mr-2 size-5" />
                          {deck.pricing_mode === 'paid'
                            ? deck.student_discount_applied && deck.effective_price_amount_minor === 0
                            ? t('detail.download_student_free', 'Tải xuống miễn phí (Ưu đãi Sinh viên)')
                            : deck.student_discount_applied
                            ? `${t('card.buy_deck', 'Mua bộ deck')} • ${deck.effective_price_display} (${t('detail.student_offer.discount_apply', { percent: deck.student_discount_percent, defaultValue: `Đã giảm ${deck.student_discount_percent}%` })})`
                            : `${t('card.buy_deck', 'Mua bộ deck')} • ${deck.price_display}`
                            : t('detail.install_free_btn', 'Tải xuống & Cài đặt miễn phí')}
                        </>
                      )}
                    </Button>

                    <Button
                      className="h-11 sm:h-12 min-h-[44px] px-4 font-semibold text-xs sm:text-sm rounded-xl justify-center border-primary/30 hover:bg-primary/5"
                      variant="outline"
                      onClick={onOpenRedeemModal}
                    >
                      <KeyRound className="mr-1.5 size-4 text-primary" />
                      {t('detail.enter_code_btn', 'Nhập mã kích hoạt')}
                    </Button>
                  </>
                )}

                <Button
                  className="h-11 sm:h-12 min-h-[44px] px-4 font-semibold text-xs sm:text-sm rounded-xl justify-center"
                  variant="outline"
                  onClick={onSave}
                  disabled={isSavePending}
                >
                  <Heart
                    className={`mr-1.5 size-4 ${
                      deck.is_saved ? 'fill-primary text-primary' : ''
                    }`}
                  />
                  {deck.is_saved
                    ? t('detail.saved_to_list', 'Đã lưu vào danh sách')
                    : t('detail.save_btn', 'Lưu bộ deck')}
                </Button>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
