import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  Award,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Clock,
  Download,
  ExternalLink,
  Eye,
  Heart,
  Layers,
  Loader2,
  MessageSquare,
  Sparkles,
  Star,
  User,
  Zap,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { CardDisplay } from '@/features/study/components/CardDisplay'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'

type AuthorProfile = {
  username?: string
  account_name?: string
  published_count?: number
  total_installs?: number
  avg_rating?: number
}

type ReviewItem = {
  id?: string
  username?: string
  rating: number
  comment?: string | null
  updated_at?: string | null
}

type TestSample = {
  note_id?: string
  word?: string
  reading?: string
  meaning?: string
}

type MarketplaceItemMini = {
  id: string
  title?: string
  name?: string
  price_display?: string
  rating_avg?: number
  author?: { username?: string } | null
  author_filter_token?: string
}

type TemplateItem = {
  id: string
  name: string
  position?: number
}

type SourceNoteType = {
  id: string
  title?: string
  name?: string
  templates?: TemplateItem[]
}

type SharedDeckDetail = {
  id: string
  title?: string
  description?: string | null
  preview_text?: string | null
  primary_category?: string | null
  price_display?: string
  pricing_mode?: string
  rating_avg: number
  rating_count: number
  install_count: number
  updated_at?: string
  created_at?: string
  badges?: string[]
  tags?: string[]
  display_tags?: string[]
  is_installed: boolean
  installed_deck_id?: number | null
  is_owner: boolean
  is_saved: boolean
  can_rate: boolean
  review_submission_count?: number
  review_submissions_remaining?: number
  my_review?: ReviewItem | null
  author?: { id: number; username: string } | null
  author_profile?: AuthorProfile
  author_other_items?: MarketplaceItemMini[]
  related_items?: MarketplaceItemMini[]
  recent_reviews?: ReviewItem[]
  test_samples?: TestSample[]
  source_deck_id?: number | null
  source_note_type_id?: string | null
  source_note_type?: SourceNoteType | null
}

type PreviewResponse = {
  front_html?: string
  back_html?: string
  front_renderer_payload?: unknown
  back_renderer_payload?: unknown
}

export function SharedDeckDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Preview & sample state
  const [activeSampleIndex, setActiveSampleIndex] = useState<number>(0)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [previewSide, setPreviewSide] = useState<'front' | 'back'>('front')

  // Rating state
  const [ratingScore, setRatingScore] = useState<number>(5)
  const [hoverScore, setHoverScore] = useState<number | null>(null)
  const [ratingComment, setRatingComment] = useState<string>('')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null)

  // Detail Query
  const deckQuery = useQuery({
    queryKey: ['shared-deck-detail', id],
    queryFn: () => appApi.get<SharedDeckDetail>(`/api/shared/decks/${id}`),
    enabled: Boolean(id),
  })

  const deck = deckQuery.data
  const samples = deck?.test_samples || []
  const currentSample = samples[activeSampleIndex] || null
  const sourceNoteType = deck?.source_note_type || null
  const templates = sourceNoteType?.templates || []

  // Auto select default template
  useEffect(() => {
    if (templates.length > 0 && !selectedTemplateId) {
      setSelectedTemplateId(templates[0].id)
    }
  }, [templates, selectedTemplateId])

  // Template Preview Query
  const previewQuery = useQuery({
    queryKey: ['shared-deck-preview', id, selectedTemplateId, currentSample?.note_id],
    queryFn: () =>
      appApi.mutate<PreviewResponse>(
        `/api/shared/decks/${id}/templates/${selectedTemplateId}/preview`,
        'POST',
        { note_id: currentSample?.note_id },
      ),
    enabled: Boolean(id && selectedTemplateId),
  })

  // Install Mutation
  const installMutation = useMutation({
    mutationFn: async () => {
      return appApi.mutate<{
        installed_deck_id?: number
        already_installed?: boolean
        payment_required?: boolean
        order?: { id: string; active_attempt?: { checkout_url?: string } }
      }>(`/api/shared/decks/${id}/install`, 'POST')
    },
    onSuccess: (data) => {
      if (data.payment_required && data.order) {
        const checkoutUrl = data.order.active_attempt?.checkout_url
        if (checkoutUrl) {
          window.location.href = checkoutUrl
          return
        }
        navigate(`/orders`)
        return
      }
      queryClient.invalidateQueries({ queryKey: ['shared-deck-detail', id] })
      queryClient.invalidateQueries({ queryKey: ['marketplace'] })
    },
  })

  // Save Mutation
  const saveMutation = useMutation({
    mutationFn: async (isSaved: boolean) => {
      return appApi.mutate(`/api/shared/decks/${id}/save`, isSaved ? 'DELETE' : 'POST')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shared-deck-detail', id] })
    },
  })

  // Rating Mutation
  const rateMutation = useMutation({
    mutationFn: async () => {
      setSubmitError(null)
      setSubmitSuccess(null)
      return appApi.mutate(`/api/shared/decks/${id}/rate`, 'POST', {
        rating: ratingScore,
        comment: ratingComment.trim() || undefined,
      })
    },
    onSuccess: () => {
      setSubmitSuccess('Cảm ơn bạn đã gửi đánh giá!')
      setRatingComment('')
      queryClient.invalidateQueries({ queryKey: ['shared-deck-detail', id] })
    },
    onError: (error: Error) => {
      setSubmitError(error.message || 'Không thể gửi đánh giá.')
    },
  })

  if (deckQuery.isPending) {
    return (
      <Page>
        <PageLoading label="Đang tải chi tiết bộ thẻ..." />
      </Page>
    )
  }

  if (deckQuery.error || !deck) {
    return (
      <Page>
        <PageError error={deckQuery.error || new Error('Không tìm thấy học liệu')} />
      </Page>
    )
  }

  const deckTitle = deck.title || 'Bộ thẻ không tên'
  const authorName =
    deck.author_profile?.account_name ||
    deck.author_profile?.username ||
    deck.author?.username ||
    'Cộng đồng'
  const tagsList = deck.display_tags || deck.tags || []

  // Sample Navigation Handlers
  const handlePrevSample = () => {
    if (!samples.length) return
    setActiveSampleIndex((prev) => (prev - 1 + samples.length) % samples.length)
  }

  const handleNextSample = () => {
    if (!samples.length) return
    setActiveSampleIndex((prev) => (prev + 1) % samples.length)
  }

  const effectiveStar = hoverScore !== null ? hoverScore : ratingScore

  return (
    <Page>
      <PageHeader
        title={deckTitle}
        description={deck.preview_text || deck.description || 'Chi tiết bộ thẻ trên marketplace Flama.'}
        actions={
          <Button variant="outline" size="sm" asChild className="group">
            <Link to="/marketplace/decks">
              <ArrowLeft className="mr-1.5 size-4 group-hover:-translate-x-0.5 transition-transform" />
              Quay lại Marketplace
            </Link>
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Main Left Content Column */}
        <div className="space-y-6">
          {/* Main Card (Strict Theme Token Alignment) */}
          <Card className="relative overflow-hidden border-border bg-card shadow-xs">
            <CardHeader className="space-y-3 pb-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-semibold">
                    {deck.primary_category || 'Tiếng Nhật'}
                  </Badge>
                  {(deck.badges || []).map((badge) => (
                    <Badge key={badge} variant="outline" className="text-xs">
                      <Award className="mr-1 size-3 text-primary" />
                      {badge}
                    </Badge>
                  ))}
                </div>
                <span className="text-xl font-bold text-primary">
                  {deck.price_display || 'Miễn phí'}
                </span>
              </div>

              <CardTitle className="text-2xl font-black tracking-tight text-foreground lg:text-3xl leading-tight">
                {deckTitle}
              </CardTitle>

              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="flex items-center gap-1.5 font-medium text-foreground">
                  <User className="size-4 text-primary" />
                  <span>{authorName}</span>
                </div>
                <span>•</span>
                <span>Xuất bản trên Flama</span>
              </div>
            </CardHeader>

            <CardContent className="space-y-5">
              <p className="text-sm leading-relaxed text-muted-foreground font-normal">
                {deck.description || 'Chưa có mô tả chi tiết cho bộ thẻ này.'}
              </p>

              {tagsList.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {tagsList.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-xs text-muted-foreground">
                      #{tag}
                    </Badge>
                  ))}
                </div>
              ) : null}

              {/* Stat Grid (Theme Token Aligned) */}
              <div className="grid grid-cols-2 gap-3 pt-2 sm:grid-cols-4">
                <div className="rounded-xl border border-border/70 bg-muted/20 p-3.5 text-center">
                  <div className="flex items-center justify-center gap-1 text-xs font-medium text-muted-foreground">
                    <Star className="size-3.5 fill-amber-400 text-amber-500" />
                    <span>Đánh giá</span>
                  </div>
                  <div className="mt-1 flex items-center justify-center gap-1 font-bold text-base text-foreground">
                    <span>{deck.rating_avg.toFixed(1)}</span>
                    <span className="text-xs font-normal text-muted-foreground">({deck.rating_count})</span>
                  </div>
                </div>

                <div className="rounded-xl border border-border/70 bg-muted/20 p-3.5 text-center">
                  <div className="flex items-center justify-center gap-1 text-xs font-medium text-muted-foreground">
                    <Download className="size-3.5 text-primary" />
                    <span>Cài đặt</span>
                  </div>
                  <div className="mt-1 font-bold text-base text-foreground">
                    {deck.install_count.toLocaleString('vi-VN')}
                  </div>
                </div>

                <div className="rounded-xl border border-border/70 bg-muted/20 p-3.5 text-center">
                  <div className="flex items-center justify-center gap-1 text-xs font-medium text-muted-foreground">
                    <Layers className="size-3.5 text-primary" />
                    <span>Thẻ mẫu</span>
                  </div>
                  <div className="mt-1 font-bold text-base text-foreground">
                    {samples.length} từ
                  </div>
                </div>

                <div className="rounded-xl border border-border/70 bg-muted/20 p-3.5 text-center">
                  <div className="flex items-center justify-center gap-1 text-xs font-medium text-muted-foreground">
                    <Clock className="size-3.5 text-muted-foreground" />
                    <span>Cập nhật</span>
                  </div>
                  <div className="mt-1 text-xs font-bold text-foreground">
                    {deck.updated_at ? new Date(deck.updated_at).toLocaleDateString('vi-VN') : 'Mới'}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Section 1: Xem nhanh - Interactive Sample Selector */}
          <Card className="border-border shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-primary/10 text-primary">
                  <Sparkles className="size-5" />
                </div>
                <div>
                  <CardTitle className="text-lg font-bold">Xem nhanh thẻ mẫu</CardTitle>
                  <CardDescription className="text-xs">
                    Bấm chọn từ bất kỳ để nạp vào phần xem trước
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="text-xs font-medium text-muted-foreground">
                {samples.length > 0
                  ? `Đang hiển thị ${samples.length} mẫu ngẫu nhiên từ bộ deck:`
                  : 'Deck này chưa có thẻ mẫu để chọn.'}
              </div>

              {samples.length > 0 ? (
                <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                  {samples.map((sample, idx) => {
                    const isSelected = idx === activeSampleIndex
                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setActiveSampleIndex(idx)}
                        className={`flex flex-col text-left p-3.5 rounded-xl border transition-all text-sm cursor-pointer ${
                          isSelected
                            ? 'bg-primary text-primary-foreground border-primary shadow-xs font-semibold'
                            : 'bg-card text-card-foreground hover:bg-muted/50 border-border'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1">
                          <strong className="font-bold text-base line-clamp-1">
                            {sample.word || `Từ #${idx + 1}`}
                          </strong>
                        </div>
                        <span
                          className={`text-xs mt-1 line-clamp-1 ${
                            isSelected ? 'text-primary-foreground/80 font-normal' : 'text-muted-foreground'
                          }`}
                        >
                          {sample.reading || sample.meaning || 'Chưa có mô tả'}
                        </span>
                      </button>
                    )
                  })}
                </div>
              ) : null}
            </CardContent>
          </Card>

          {/* Section 2: Live Anki Card Previewer */}
          <Card className="border-border shadow-xs overflow-hidden">
            <CardHeader className="pb-3 border-b bg-muted/20">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-primary/10 text-primary">
                    <Eye className="size-5" />
                  </div>
                  <div>
                    <CardTitle className="text-lg font-bold">Xem trước thẻ (Live Preview)</CardTitle>
                    <CardDescription className="text-xs">
                      Mô phỏng hiển thị thẻ Anki
                    </CardDescription>
                  </div>
                </div>

                {/* Controls */}
                <div className="flex flex-wrap items-center gap-2">
                  {sourceNoteType ? (
                    <Button variant="outline" size="sm" asChild className="h-8 text-xs font-semibold">
                      <Link to={`/marketplace/note-types/${sourceNoteType.id}`}>
                        <ExternalLink className="mr-1 size-3.5" />
                        {sourceNoteType.title || sourceNoteType.name || 'NoteType nguồn'}
                      </Link>
                    </Button>
                  ) : null}

                  {templates.length > 1 ? (
                    <NativeSelect
                      value={selectedTemplateId}
                      onChange={(e) => setSelectedTemplateId(e.target.value)}
                      className="h-8 text-xs w-36"
                    >
                      {templates.map((t) => (
                        <NativeSelectOption key={t.id} value={t.id}>
                          {t.name}
                        </NativeSelectOption>
                      ))}
                    </NativeSelect>
                  ) : null}

                  {/* Segment Switch */}
                  <div className="inline-flex rounded-lg border bg-card p-0.5 shadow-2xs">
                    <Button
                      size="sm"
                      variant={previewSide === 'front' ? 'default' : 'ghost'}
                      className="h-7 px-3.5 text-xs font-semibold rounded-md transition-all"
                      onClick={() => setPreviewSide('front')}
                    >
                      Mặt trước
                    </Button>
                    <Button
                      size="sm"
                      variant={previewSide === 'back' ? 'default' : 'ghost'}
                      className="h-7 px-3.5 text-xs font-semibold rounded-md transition-all"
                      onClick={() => setPreviewSide('back')}
                    >
                      Mặt sau
                    </Button>
                  </div>

                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-2.5 text-xs font-medium"
                      onClick={handlePrevSample}
                      disabled={!samples.length}
                      title="Mẫu trước"
                    >
                      <ChevronLeft className="size-3.5 mr-0.5" />
                      Trước
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-2.5 text-xs font-medium"
                      onClick={handleNextSample}
                      disabled={!samples.length}
                      title="Mẫu tiếp theo"
                    >
                      Sau
                      <ChevronRight className="size-3.5 ml-0.5" />
                    </Button>
                  </div>
                </div>
              </div>

              {/* Status Indicator */}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 text-xs text-muted-foreground border-t border-border/50">
                <div className="font-semibold text-foreground flex items-center gap-1.5">
                  <Sparkles className="size-3.5 text-primary" />
                  <span>
                    {samples.length > 0
                      ? `Mẫu ${activeSampleIndex + 1}/${samples.length}: ${(currentSample?.word || '').trim() || 'Từ mẫu'} ${currentSample?.reading ? `(${currentSample.reading})` : ''}`
                      : 'Chưa có từ mẫu'}
                  </span>
                </div>
                {sourceNoteType ? (
                  <span className="text-xs">
                    NoteType: <strong className="text-foreground">{sourceNoteType.title || sourceNoteType.name}</strong>
                  </span>
                ) : null}
              </div>
            </CardHeader>

            <CardContent className="p-4 bg-muted/30">
              <div className="h-[clamp(20rem,50vh,32rem)] min-h-[240px] w-full overflow-hidden rounded-xl border border-border bg-card shadow-xs">
                {previewQuery.isPending ? (
                  <div className="flex h-full flex-col items-center justify-center p-8 space-y-2 text-muted-foreground">
                    <Loader2 className="size-6 animate-spin text-primary" />
                    <span className="text-xs">Đang tải bản xem trước...</span>
                  </div>
                ) : previewQuery.data ? (
                  <CardDisplay
                    cardId={`preview-${id}`}
                    noteId={currentSample?.note_id}
                    side={previewSide}
                    frontPayload={previewQuery.data.front_renderer_payload}
                    backPayload={previewQuery.data.back_renderer_payload}
                    frontHtml={previewQuery.data.front_html}
                    backHtml={previewQuery.data.back_html}
                    scope="shared_deck_preview"
                    scopeId={id}
                  />
                ) : (
                  <EmptyState
                    title="Chưa có xem trước"
                    description="Deck này chưa cấu hình template hoặc không có thẻ mẫu."
                  />
                )}
              </div>
            </CardContent>
          </Card>

          {/* Section 3: Community Reviews */}
          <Card className="border-border shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-primary/10 text-primary">
                  <MessageSquare className="size-5" />
                </div>
                <div>
                  <CardTitle className="text-lg font-bold">Đánh giá & Nhận xét</CardTitle>
                  <CardDescription className="text-xs">
                    Ý kiến từ học viên đã trải nghiệm bộ deck này
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Form */}
              {deck.can_rate ? (
                <div className="rounded-xl border border-border bg-card p-4 space-y-3 shadow-2xs">
                  <div className="font-bold text-sm text-foreground">Gửi đánh giá của bạn</div>
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1" onMouseLeave={() => setHoverScore(null)}>
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          className="p-1 transition-transform hover:scale-110 focus:outline-none cursor-pointer"
                          onMouseEnter={() => setHoverScore(star)}
                          onClick={() => setRatingScore(star)}
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
                      {effectiveStar}/5 sao
                    </span>
                  </div>

                  <Textarea
                    placeholder="Viết nhận xét của bạn..."
                    value={ratingComment}
                    onChange={(e) => setRatingComment(e.target.value)}
                    rows={3}
                  />

                  {submitError ? (
                    <p className="text-xs text-destructive font-medium">{submitError}</p>
                  ) : null}
                  {submitSuccess ? (
                    <p className="text-xs text-primary font-bold">{submitSuccess}</p>
                  ) : null}

                  <Button
                    size="sm"
                    className="font-bold"
                    onClick={() => rateMutation.mutate()}
                    disabled={rateMutation.isPending}
                  >
                    {rateMutation.isPending ? (
                      <Loader2 className="mr-1.5 size-4 animate-spin" />
                    ) : null}
                    Gửi nhận xét
                  </Button>
                </div>
              ) : deck.my_review ? (
                <div className="rounded-xl border bg-muted/30 p-3.5 text-sm space-y-1">
                  <div className="font-bold text-xs text-muted-foreground uppercase">Đánh giá của bạn:</div>
                  <div className="flex items-center gap-1 font-bold text-amber-500">
                    <Star className="size-4 fill-amber-400" />
                    <span>{deck.my_review.rating}/5 sao</span>
                  </div>
                  {deck.my_review.comment ? (
                    <p className="text-foreground pt-1">{deck.my_review.comment}</p>
                  ) : null}
                </div>
              ) : (
                <div className="text-xs text-muted-foreground bg-muted/20 p-3 rounded-xl border">
                  Bạn cần cài đặt học liệu để mở tính năng gửi đánh giá.
                </div>
              )}

              {/* Reviews List */}
              <div className="space-y-3">
                <div className="font-bold text-sm text-foreground">
                  Nhận xét từ học viên ({deck.recent_reviews?.length || 0})
                </div>

                {deck.recent_reviews && deck.recent_reviews.length > 0 ? (
                  <div className="space-y-3">
                    {deck.recent_reviews.map((rev, i) => (
                      <div key={i} className="rounded-xl border border-border p-3.5 text-sm space-y-2 bg-card">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-xs text-foreground">
                            {rev.username || 'Học viên'}
                          </span>
                          <div className="flex items-center gap-1 font-bold text-xs text-amber-500">
                            <Star className="size-3.5 fill-amber-400" />
                            <span>{rev.rating}/5</span>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          {rev.comment || 'Không để lại lời nhắn.'}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title="Chưa có nhận xét"
                    description="Hãy là người đầu tiên đánh giá sau khi cài đặt bộ deck này."
                  />
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Sidebar Column */}
        <div className="space-y-6">
          <Card className="sticky top-6 border-border shadow-xs">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-bold">Hành động</CardTitle>
              <CardDescription className="text-xs">
                Đồng bộ bộ thẻ vào thư viện cá nhân để bắt đầu học.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {deck.is_owner ? (
                <Button className="w-full font-bold" variant="secondary" disabled>
                  <CheckCircle className="mr-1.5 size-4 text-primary" />
                  Bạn là tác giả bộ deck này
                </Button>
              ) : deck.is_installed ? (
                <div className="space-y-2">
                  <Button className="w-full font-bold" variant="outline" disabled>
                    <CheckCircle className="mr-1.5 size-4 text-primary" />
                    Đã cài đặt vào thư viện
                  </Button>
                  {deck.installed_deck_id ? (
                    <Button className="w-full font-bold" asChild>
                      <Link to={`/study?deck_id=${deck.installed_deck_id}`}>
                        <Zap className="mr-1.5 size-4 fill-primary-foreground" />
                        Bắt đầu học ngay
                      </Link>
                    </Button>
                  ) : null}
                </div>
              ) : (
                <Button
                  className="w-full font-bold text-base py-5 shadow-xs"
                  size="lg"
                  onClick={() => installMutation.mutate()}
                  disabled={installMutation.isPending}
                >
                  {installMutation.isPending ? (
                    <Loader2 className="mr-2 size-5 animate-spin" />
                  ) : (
                    <Download className="mr-2 size-5" />
                  )}
                  {deck.pricing_mode === 'paid' ? 'Mua bộ deck' : 'Tải xuống & Cài đặt'}
                </Button>
              )}

              {!deck.is_owner ? (
                <Button
                  className="w-full font-semibold"
                  variant="outline"
                  size="sm"
                  onClick={() => saveMutation.mutate(deck.is_saved)}
                  disabled={saveMutation.isPending}
                >
                  <Heart
                    className={`mr-1.5 size-4 ${
                      deck.is_saved ? 'fill-primary text-primary' : ''
                    }`}
                  />
                  {deck.is_saved ? 'Đã lưu vào danh sách' : 'Lưu bộ deck'}
                </Button>
              ) : null}

              <div className="pt-3 border-t text-xs text-muted-foreground space-y-2">
                <div className="flex items-center gap-2">
                  <User className="size-4 text-primary" />
                  <span>Tác giả: <strong className="text-foreground">{authorName}</strong></span>
                </div>
                {deck.author_profile?.published_count ? (
                  <div className="text-muted-foreground pl-6">
                    Đã xuất bản: <strong className="text-foreground">{deck.author_profile.published_count}</strong> bộ deck
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>

          {/* Related Items Sidebar */}
          {deck.related_items && deck.related_items.length > 0 ? (
            <Card className="border-border shadow-2xs">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-bold">Bộ deck liên quan</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {deck.related_items.map((item) => (
                  <Link
                    key={item.id}
                    to={`/marketplace/decks/${item.id}`}
                    className="group block rounded-xl border border-border p-3 hover:bg-muted/40 transition-colors"
                  >
                    <div className="font-bold text-xs text-foreground group-hover:text-primary transition-colors line-clamp-1">
                      {item.title || item.name || 'Bộ thẻ liên quan'}
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground mt-1.5">
                      <span className="font-semibold text-primary">
                        {item.price_display || 'Miễn phí'}
                      </span>
                      <span className="flex items-center gap-0.5 font-bold text-amber-500">
                        <Star className="size-3 fill-amber-400" />
                        {(item.rating_avg || 0).toFixed(1)}
                      </span>
                    </div>
                  </Link>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </Page>
  )
}
