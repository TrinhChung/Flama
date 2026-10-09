import { Loader2, MessageSquare, Star } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { EmptyState } from '@/shared/components/PageState'
import { useTranslation } from 'react-i18next'

interface ReviewItem {
  id?: string
  username?: string
  rating: number
  comment?: string | null
  updated_at?: string | null
}

interface SharedNoteTypeReviewsProps {
  canRate: boolean
  ratingScore: number
  setRatingScore: (score: number) => void
  hoverScore: number | null
  setHoverScore: (score: number | null) => void
  effectiveStar: number
  ratingComment: string
  setRatingComment: (comment: string) => void
  submitError: string | null
  submitSuccess: string | null
  rateMutation: {
    mutate: () => void
    isPending: boolean
  }
  recentReviews?: ReviewItem[]
}

export function SharedNoteTypeReviews({
  canRate,
  setRatingScore,
  setHoverScore,
  effectiveStar,
  ratingComment,
  setRatingComment,
  submitError,
  submitSuccess,
  rateMutation,
  recentReviews,
}: SharedNoteTypeReviewsProps) {
  const { t } = useTranslation('marketplace')

  return (
    <Card className="border-border shadow-xs rounded-2xl">
      <CardHeader className="p-4 sm:p-5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2.5 rounded-xl bg-primary/10 text-primary">
            <MessageSquare className="size-5" />
          </div>
          <CardTitle className="text-lg font-bold">
            {t('notetype_detail.community_reviews_title', 'Đánh giá từ cộng đồng')}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-4 sm:p-5 pt-0 space-y-6">
        {canRate ? (
          <div className="rounded-2xl border border-border/80 bg-card p-4 space-y-3 shadow-2xs">
            <div className="font-bold text-sm text-foreground">
              {t('detail.reviews.form_title', 'Gửi đánh giá của bạn')}
            </div>
            <div className="flex items-center gap-3">
              <div className="flex gap-1" onMouseLeave={() => setHoverScore(null)}>
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    className="p-1 transition-transform hover:scale-110 focus:outline-none cursor-pointer"
                    onMouseEnter={() => setHoverScore(star)}
                    onClick={() => setRatingScore(star)}
                    aria-label={`${star} sao`}
                  >
                    <Star
                      className={`size-6 ${
                        star <= effectiveStar
                          ? 'fill-amber-400 text-amber-500'
                          : 'text-muted-foreground/30'
                      }`}
                    />
                  </button>
                ))}
              </div>
              <span className="text-sm font-bold text-foreground">
                {effectiveStar}/5 {t('detail.reviews.star_unit', 'sao')}
              </span>
            </div>

            <Textarea
              placeholder={t(
                'notetype_detail.review_placeholder',
                'Viết nhận xét của bạn về thiết kế cấu trúc thẻ này...'
              )}
              value={ratingComment}
              onChange={(e) => setRatingComment(e.target.value)}
              rows={3}
              className="text-xs sm:text-sm leading-relaxed rounded-xl"
            />

            {submitError ? (
              <p className="text-xs text-destructive font-medium">{submitError}</p>
            ) : null}
            {submitSuccess ? (
              <p className="text-xs text-emerald-600 dark:text-emerald-400 font-bold">{submitSuccess}</p>
            ) : null}

            <Button
              size="sm"
              className="h-9 px-4 font-bold text-xs sm:text-sm shadow-2xs rounded-xl"
              onClick={() => rateMutation.mutate()}
              disabled={rateMutation.isPending}
            >
              {rateMutation.isPending ? (
                <Loader2 className="mr-1.5 size-4 animate-spin" />
              ) : null}
              {t('notetype_detail.btn_submit_review', 'Gửi nhận xét')}
            </Button>
          </div>
        ) : null}

        <div className="space-y-3">
          {recentReviews && recentReviews.length > 0 ? (
            <div className="space-y-3">
              {recentReviews.map((rev, i) => (
                <div key={i} className="rounded-2xl border border-border/80 p-4 text-sm space-y-2 bg-card shadow-2xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px]">
                        {(rev.username || 'H').charAt(0).toUpperCase()}
                      </div>
                      <span className="font-bold text-xs text-foreground">
                        {rev.username || t('detail.reviews.default_student', 'Học viên')}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 font-bold text-xs text-amber-500 bg-amber-500/10 px-2.5 py-0.5 rounded-full">
                      <Star className="size-3.5 fill-amber-400" />
                      <span>{rev.rating}/5</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed pl-8">
                    {rev.comment || t('detail.reviews.no_comment', 'Học viên không để lại lời nhắn.')}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title={t('detail.reviews.empty_reviews_title', 'Chưa có nhận xét')}
              description={t('notetype_detail.reviews_empty', 'Chưa có đánh giá nào cho cấu trúc thẻ này.')}
            />
          )}
        </div>
      </CardContent>
    </Card>
  )
}
