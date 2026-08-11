import { useEffect, useState, useMemo } from 'react'
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
  FileDiff,
  GitCompare,
  Heart,
  Layers,
  Loader2,
  MessageSquare,
  Inbox,
  Sparkles,
  Star,
  BookOpen,
  User,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
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
  const templates = useMemo(() => sourceNoteType?.templates || [], [sourceNoteType?.templates])

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
    <Page className="space-y-4 sm:space-y-6 relative px-2.5 sm:px-6 lg:px-8 py-3 sm:py-6">
      <AmbientBackground intensity="subtle" />

      <PageHeader
        title={deckTitle}
        description={deck.preview_text || deck.description || 'Chi tiết bộ thẻ trên marketplace Flama.'}
        actions={
          <Button variant="outline" size="sm" asChild className="group h-8 sm:h-9 px-3 sm:px-3.5 text-xs font-semibold rounded-xl">
            <Link to="/marketplace/decks">
              <ArrowLeft className="mr-1 sm:mr-1.5 size-3.5 group-hover:-translate-x-0.5 transition-transform" />
              Quay lại Marketplace
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:gap-5 lg:grid-cols-[1fr_340px]">
        {/* Main Left Content Column */}
        <div className="space-y-4 sm:space-y-5">
          {/* Main Card */}
          <Card className="relative overflow-hidden border-border/40 sm:border-border/80 bg-card/90 backdrop-blur-md shadow-xs sm:shadow-sm rounded-xl sm:rounded-2xl">
            <div className="h-2 w-full bg-gradient-to-r from-primary via-orange-500 to-amber-500" />
            <CardHeader className="space-y-3 p-3.5 sm:p-6 pb-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-bold rounded-md">
                    {deck.primary_category || 'Tiếng Nhật'}
                  </Badge>
                  {(deck.badges || []).map((badge) => (
                    <Badge key={badge} variant="outline" className="text-xs font-semibold rounded-md">
                      <Award className="mr-1 size-3 text-primary" />
                      {badge}
                    </Badge>
                  ))}
                </div>

                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-extrabold border ${
                    deck.pricing_mode === 'free'
                      ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                      : 'bg-primary/10 text-primary border-primary/30'
                  }`}
                >
                  {deck.price_display || 'Miễn phí'}
                </span>
              </div>

              <CardTitle className="text-2xl font-black tracking-tight text-foreground sm:text-3xl leading-tight">
                {deckTitle}
              </CardTitle>

              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px]">
                    {authorName.charAt(0).toUpperCase()}
                  </div>
                  <span className="font-semibold text-foreground">{authorName}</span>
                </div>
                <span>•</span>
                <span className="flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400">
                  <CheckCircle className="size-3.5" /> Flama Marketplace
                </span>
              </div>
            </CardHeader>

            <CardContent className="p-5 sm:p-6 pt-0 space-y-4">
              <p className="text-xs sm:text-sm leading-relaxed text-muted-foreground font-normal">
                {deck.description || 'Chưa có mô tả chi tiết cho bộ thẻ này.'}
              </p>

              {tagsList.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {tagsList.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-[11px] text-muted-foreground font-medium px-2.5 py-0.5 rounded-md">
                      #{tag}
                    </Badge>
                  ))}
                </div>
              ) : null}

              {/* Stat Grid */}
              <div className="grid grid-cols-2 gap-3 pt-1 sm:grid-cols-4">
                <div className="rounded-xl border border-border/80 bg-muted/30 p-3.5 sm:p-4 text-center transition-all hover:bg-muted/50">
                  <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
                    <Star className="size-3.5 fill-amber-400 text-amber-500" />
                    <span>Đánh giá</span>
                  </div>
                  <div className="mt-1 flex items-center justify-center gap-1 font-extrabold text-base text-foreground">
                    <span>{deck.rating_avg.toFixed(1)}</span>
                    <span className="text-xs font-normal text-muted-foreground">({deck.rating_count})</span>
                  </div>
                </div>

                <div className="rounded-xl border border-border/80 bg-muted/30 p-3.5 sm:p-4 text-center transition-all hover:bg-muted/50">
                  <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
                    <Download className="size-3.5 text-primary" />
                    <span>Lượt cài</span>
                  </div>
                  <div className="mt-1 font-extrabold text-base text-foreground">
                    {deck.install_count.toLocaleString('vi-VN')}
                  </div>
                </div>

                <div className="rounded-xl border border-border/80 bg-muted/30 p-3.5 sm:p-4 text-center transition-all hover:bg-muted/50">
                  <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
                    <Layers className="size-3.5 text-primary" />
                    <span>Xem mẫu</span>
                  </div>
                  <div className="mt-1 font-extrabold text-base text-foreground">
                    {samples.length} từ
                  </div>
                </div>

                <div className="rounded-xl border border-border/80 bg-muted/30 p-3.5 sm:p-4 text-center transition-all hover:bg-muted/50">
                  <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
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

          {/* Section 1: Interactive Sample & Live Previewer */}
          <Card className="border-border shadow-xs overflow-hidden rounded-2xl">
            <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-muted/20">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2.5 rounded-xl bg-primary/10 text-primary">
                    <Eye className="size-5" />
                  </div>
                  <div>
                    <CardTitle className="text-lg font-bold">Xem trước thẻ (Live Previewer)</CardTitle>
                    <CardDescription className="text-xs">
                      Mô phỏng hiển thị Anki Flashcard thực tế
                    </CardDescription>
                  </div>
                </div>

                {/* Controls */}
                <div className="flex flex-wrap items-center gap-2">
                  {sourceNoteType ? (
                    <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 text-xs font-semibold rounded-lg">
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
                      className="h-8 sm:h-9 text-xs font-medium w-36 rounded-lg"
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
                      className="h-8 px-3.5 text-xs font-bold rounded-md transition-all"
                      onClick={() => setPreviewSide('front')}
                    >
                      Mặt trước
                    </Button>
                    <Button
                      size="sm"
                      variant={previewSide === 'back' ? 'default' : 'ghost'}
                      className="h-8 px-3.5 text-xs font-bold rounded-md transition-all"
                      onClick={() => setPreviewSide('back')}
                    >
                      Mặt sau
                    </Button>
                  </div>

                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 px-3 text-xs font-semibold rounded-lg"
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
                      className="h-8 px-3 text-xs font-semibold rounded-lg"
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
              <div className="flex flex-wrap items-center justify-between gap-2 pt-2.5 text-xs text-muted-foreground border-t border-border/50">
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

            {/* Quick Word Select Chips */}
            {samples.length > 0 ? (
              <div className="p-3.5 bg-muted/10 border-b border-border/60">
                <div className="text-xs font-semibold text-muted-foreground mb-2">Chọn nhanh từ mẫu:</div>
                <div className="flex flex-wrap gap-2">
                  {samples.map((sample, idx) => {
                    const isSelected = idx === activeSampleIndex
                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setActiveSampleIndex(idx)}
                        className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-primary text-primary-foreground border-primary shadow-xs'
                            : 'bg-card text-foreground hover:bg-muted border-border/80'
                        }`}
                      >
                        <span>{sample.word || `Từ #${idx + 1}`}</span>
                        {sample.reading ? (
                          <span className={`text-[10px] ${isSelected ? 'opacity-90' : 'text-muted-foreground'}`}>
                            ({sample.reading})
                          </span>
                        ) : null}
                      </button>
                    )
                  })}
                </div>
              </div>
            ) : null}

            <CardContent className="p-4 sm:p-5 bg-muted/30">
              <div className="h-[clamp(20rem,50vh,32rem)] min-h-[250px] w-full overflow-hidden rounded-2xl border border-border bg-card shadow-xs">
                {previewQuery.isPending ? (
                  <div className="flex h-full flex-col items-center justify-center p-8 space-y-2 text-muted-foreground">
                    <Loader2 className="size-6 animate-spin text-primary" />
                    <span className="text-xs font-medium">Đang tải bản xem trước thẻ...</span>
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
          <Card className="border-border shadow-xs rounded-2xl">
            <CardHeader className="p-4 sm:p-5 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2.5 rounded-xl bg-primary/10 text-primary">
                  <MessageSquare className="size-5" />
                </div>
                <div>
                  <CardTitle className="text-lg font-bold">Đánh giá & Nhận xét</CardTitle>
                  <CardDescription className="text-xs">
                    Ý kiến đóng góp từ học viên đã trải nghiệm bộ deck này
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 pt-0 space-y-6">
              {/* Form */}
              {deck.can_rate ? (
                <div className="rounded-2xl border border-border/80 bg-card p-4 space-y-3 shadow-2xs">
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
                    placeholder="Viết nhận xét của bạn về chất lượng từ vựng, kanji hoặc bản xem trước..."
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
                    Gửi nhận xét
                  </Button>
                </div>
              ) : deck.my_review ? (
                <div className="rounded-2xl border border-border bg-muted/20 p-4 text-sm space-y-1">
                  <div className="font-bold text-xs text-muted-foreground uppercase tracking-wider">Đánh giá của bạn:</div>
                  <div className="flex items-center gap-1 font-bold text-amber-500">
                    <Star className="size-4 fill-amber-400" />
                    <span>{deck.my_review.rating}/5 sao</span>
                  </div>
                  {deck.my_review.comment ? (
                    <p className="text-foreground pt-1 text-xs leading-relaxed">{deck.my_review.comment}</p>
                  ) : null}
                </div>
              ) : (
                <div className="text-xs text-muted-foreground bg-muted/20 p-4 rounded-2xl border border-border/80 text-center">
                  Bạn cần tải xuống & cài đặt học liệu để mở tính năng gửi đánh giá.
                </div>
              )}

              {/* Reviews List */}
              <div className="space-y-3">
                <div className="font-bold text-sm text-foreground flex items-center justify-between">
                  <span>Nhận xét từ học viên</span>
                  <Badge variant="outline" className="text-xs font-semibold rounded-md">
                    {deck.recent_reviews?.length || 0} nhận xét
                  </Badge>
                </div>

                {deck.recent_reviews && deck.recent_reviews.length > 0 ? (
                  <div className="space-y-3">
                    {deck.recent_reviews.map((rev, i) => (
                      <div key={i} className="rounded-2xl border border-border/80 p-4 text-sm space-y-2 bg-card shadow-2xs">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px]">
                              {(rev.username || 'H').charAt(0).toUpperCase()}
                            </div>
                            <span className="font-bold text-xs text-foreground">
                              {rev.username || 'Học viên'}
                            </span>
                          </div>
                          <div className="flex items-center gap-1 font-bold text-xs text-amber-500 bg-amber-500/10 px-2.5 py-0.5 rounded-full">
                            <Star className="size-3.5 fill-amber-400" />
                            <span>{rev.rating}/5</span>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed pl-8">
                          {rev.comment || 'Học viên không để lại lời nhắn.'}
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
          <Card className="sticky top-6 border-border shadow-xs overflow-hidden rounded-2xl">
            <div className="h-1.5 w-full bg-primary" />
            <CardHeader className="p-4 sm:p-5 pb-3">
              <CardTitle className="text-base font-bold">Hành động & Cài đặt</CardTitle>
              <CardDescription className="text-xs">
                Đồng bộ bộ thẻ vào thư viện cá nhân bằng Logical Overlay.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 pt-0 space-y-3">
              {deck.is_owner ? (
                <div className="space-y-2">
                  <Button className="w-full h-10 sm:h-11 font-bold text-xs sm:text-sm rounded-xl" variant="secondary" asChild>
                    <Link to={`/creator/decks/${id}/releases/new`}>
                      <GitCompare className="mr-1.5 size-4 text-primary" />
                      Phát hành phiên bản mới
                    </Link>
                  </Button>
                  <Button className="w-full h-9 sm:h-10 font-semibold text-xs sm:text-sm rounded-xl" variant="outline" asChild>
                    <Link to={`/flashcards/change-requests/incoming?deck_item_id=${id}`}>
                      <Inbox className="mr-1.5 size-4" />
                      Đóng góp cần duyệt
                    </Link>
                  </Button>
                </div>
              ) : deck.is_installed ? (
                <div className="space-y-2">
                  <Button className="w-full h-10 sm:h-11 font-bold text-xs sm:text-sm border-emerald-500/40 text-emerald-600 dark:text-emerald-400 rounded-xl" variant="outline" disabled>
                    <CheckCircle className="mr-1.5 size-4" />
                    Đã cài đặt vào thư viện
                  </Button>
                  <Button className="w-full h-9 sm:h-10 font-semibold text-xs sm:text-sm rounded-xl" variant="outline" asChild>
                    <Link to={`/flashcards/shared-decks/${id}/change-request`}>
                      <FileDiff className="mr-1.5 size-4" />
                      Đóng góp chỉnh sửa
                    </Link>
                  </Button>
                  {deck.installed_deck_id ? (
                    <Button className="w-full h-10 sm:h-11 font-bold text-xs sm:text-sm shadow-md bg-gradient-to-r from-primary to-primary/90 rounded-xl" asChild>
                      <Link to={`/study?deck_id=${deck.installed_deck_id}`}>
                        <BookOpen className="mr-1.5 size-4" />
                        Bắt đầu học ngay
                      </Link>
                    </Button>
                  ) : null}
                </div>
              ) : (
                <Button
                  className="w-full h-11 sm:h-12 font-bold text-sm sm:text-base shadow-md bg-gradient-to-r from-primary to-primary/90 hover:opacity-95 text-primary-foreground rounded-xl"
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
                  className="w-full h-9 sm:h-10 font-semibold text-xs sm:text-sm rounded-xl"
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

              <div className="pt-3 border-t border-border/60 text-xs text-muted-foreground space-y-2">
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
                    className="group block rounded-2xl border border-border p-3 hover:bg-muted/40 hover:border-primary/40 transition-all"
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
