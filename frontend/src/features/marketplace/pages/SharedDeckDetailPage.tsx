import { useEffect, useState, useMemo } from 'react'
import {
  ArrowLeft,
  Award,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  Eye,
  FileDiff,
  GitCompare,
  Heart,
  KeyRound,
  Layers,
  Loader2,
  MessageSquare,
  Inbox,
  Sparkles,
  Star,
  BookOpen,
  EyeOff,
  Edit3,
  Globe,
  Lock,
  Search,
  Zap,
  Clock,
  AlertCircle,
  GraduationCap,
} from 'lucide-react'
import { toast } from 'sonner'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { DeckAccessKeysManager } from '../components/keys/DeckAccessKeysManager'
import { RedeemDeckKeyModal } from '../components/keys/RedeemDeckKeyModal'
import { getAutoPublishStatus, updateAutoPublishSetting } from '@/features/deck-collaboration/api'
import { Switch } from '@/components/ui/switch'

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
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { CardDisplay } from '@/features/study/components/CardDisplay'
import { Page } from '@/shared/components/Page'
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

type LessonItem = {
  id: number
  name: string
  parent_id: number | null
  depth: number
  is_root: boolean
  direct_note_count: number
  direct_card_count: number
  note_count: number
  card_count: number
  total_note_count: number
  total_card_count: number
  has_children: boolean
}

type SharedDeckDetail = {
  id: string
  title?: string
  description?: string | null
  preview_text?: string | null
  primary_category?: string | null
  version?: string
  price_display?: string
  pricing_mode?: string
  rating_avg: number
  rating_count: number
  install_count: number
  note_count?: number
  card_count?: number
  lesson_count?: number
  total_decks?: number
  has_subdecks?: boolean
  lessons?: LessonItem[]
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
  student_offer_mode?: string
  student_discount_percent?: number | null
  has_student_offer?: boolean
  student_preview_display?: string
  student_preview_price_minor?: number
  effective_price_amount_minor?: number
  effective_price_display?: string
  discount_amount_minor?: number
  student_discount_applied?: boolean
  user_student_status?: string
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
  publish_status?: 'private' | 'published' | 'unlisted' | 'archived'
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
  const [searchParams] = useSearchParams()
  const urlCode = searchParams.get('code') || searchParams.get('key') || ''

  // Key management and redemption states
  const [isRedeemModalOpen, setIsRedeemModalOpen] = useState(false)
  const [showKeyManager, setShowKeyManager] = useState(false)

  // Preview & sample state
  const [activeSampleIndex, setActiveSampleIndex] = useState<number>(0)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [previewSide, setPreviewSide] = useState<'front' | 'back'>('front')
  const [lessonSearch, setLessonSearch] = useState<string>('')

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

  // Filter lessons based on search query
  const displayLessons = useMemo(() => {
    const allLessons = deck?.lessons || []
    const subLessons = allLessons.length > 1 ? allLessons.filter((l) => !l.is_root) : allLessons
    if (!lessonSearch.trim()) return subLessons
    const query = lessonSearch.trim().toLowerCase()
    return subLessons.filter((l) => l.name.toLowerCase().includes(query))
  }, [deck?.lessons, lessonSearch])

  // Auto select default template
  useEffect(() => {
    if (templates.length > 0 && !selectedTemplateId) {
      setSelectedTemplateId(templates[0].id)
    }
  }, [templates, selectedTemplateId])

  // Auto open redeem modal if URL contains key/code parameter
  useEffect(() => {
    if (urlCode && deck && !deck.is_owner && !deck.is_installed) {
      setIsRedeemModalOpen(true)
    }
  }, [urlCode, deck])


  // Auto-Publish Query & Mutation for Deck Owner
  const autoPublishQuery = useQuery({
    queryKey: ['shared-deck-auto-publish', id],
    queryFn: ({ signal }) => getAutoPublishStatus(id!, signal),
    enabled: Boolean(id && deck?.is_owner),
  })

  const autoPublishMutation = useMutation({
    mutationFn: (enabled: boolean) => updateAutoPublishSetting(id!, enabled),
    onSuccess: (status) => {
      queryClient.setQueryData(['shared-deck-auto-publish', id], status)
      queryClient.invalidateQueries({ queryKey: ['shared-deck-detail', id] })
      queryClient.invalidateQueries({ queryKey: ['deck-releases', id] })
      toast.success(
        status.auto_publish_enabled
          ? 'Đã bật chế độ tự động phát hành phiên bản mới.'
          : 'Đã tắt chế độ tự động phát hành.',
      )
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Không thể cập nhật cấu hình tự động phát hành.')
    },
  })

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
    onMutate: () => {
      const lessonText = deck?.lesson_count ? `${deck.lesson_count} bài học` : ''
      const noteText = deck?.note_count ? `${deck.note_count.toLocaleString('vi-VN')} từ vựng` : ''
      const countSummary = [lessonText, noteText].filter(Boolean).join(' • ')

      toast?.loading?.('Đang khởi tạo và cài đặt bộ thẻ…', {
        id: 'shared-deck-install',
        description: countSummary
          ? `Đang thiết lập ${countSummary} vào thư viện của bạn. Vui lòng không đóng trình duyệt!`
          : 'Đối với bộ thẻ lớn (nhiều bài học hoặc từ vựng), quá trình có thể mất từ 10-30 giây. Vui lòng không đóng trình duyệt!',
      })
    },
    onSuccess: (data) => {
      toast?.dismiss?.('shared-deck-install')
      if (data.payment_required && data.order) {
        const checkoutUrl = data.order.active_attempt?.checkout_url
        if (checkoutUrl) {
          window.location.href = checkoutUrl
          return
        }
        navigate(`/orders`)
        return
      }
      toast.success('Cài đặt bộ thẻ thành công!')
      queryClient.invalidateQueries({ queryKey: ['shared-deck-detail', id] })
      queryClient.invalidateQueries({ queryKey: ['marketplace'] })
      queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (error: Error) => {
      toast.error('Không thể cài đặt bộ thẻ', {
        id: 'shared-deck-install',
        description:
          error.message ||
          'Đã có lỗi xảy ra trong quá trình cài đặt. Vui lòng thử lại sau ít phút.',
      })
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
  const publishStatusMutation = useMutation({
    mutationFn: async (newStatus: 'private' | 'published' | 'unlisted' | 'archived') => {
      return appApi.mutate<SharedDeckDetail>(`/api/shared/decks/${id}`, 'PATCH', {
        publish_status: newStatus,
      })
    },
    onSuccess: (data) => {
      toast.success(
        data.publish_status === 'private'
          ? 'Đã thu hồi bộ deck khỏi Marketplace!'
          : 'Đã cập nhật trạng thái xuất bản bộ deck!'
      )
      queryClient.invalidateQueries({ queryKey: ['shared-deck-detail', id] })
      queryClient.invalidateQueries({ queryKey: ['marketplace'] })
    },
    onError: (error: Error) => {
      toast.error('Không thể cập nhật trạng thái', { description: error.message })
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

      {/* Top Breadcrumb Navigation & Back Action */}
      <div className="flex items-center justify-between gap-3 pb-0.5">
        <nav className="flex items-center gap-1.5 text-xs text-muted-foreground overflow-hidden text-ellipsis whitespace-nowrap">
          <Link
            to="/marketplace/decks"
            className="hover:text-foreground transition-colors font-medium hover:underline"
          >
            Marketplace
          </Link>
          <ChevronRight className="size-3.5 shrink-0 opacity-50" />
          <span className="font-medium text-foreground/70 truncate hidden xs:inline">
            {deck.primary_category || 'Tiếng Nhật'}
          </span>
          <ChevronRight className="size-3.5 shrink-0 opacity-50 hidden xs:inline" />
          <span className="font-semibold text-foreground truncate max-w-[160px] sm:max-w-xs md:max-w-md">
            {deckTitle}
          </span>
        </nav>

        <Button
          variant="outline"
          size="sm"
          asChild
          className="group shrink-0 h-8 sm:h-9 px-3 sm:px-3.5 text-xs font-semibold rounded-xl"
        >
          <Link to="/marketplace/decks">
            <ArrowLeft className="mr-1 sm:mr-1.5 size-3.5 group-hover:-translate-x-0.5 transition-transform" />
            <span className="hidden sm:inline">Quay lại Marketplace</span>
            <span className="sm:hidden">Quay lại</span>
          </Link>
        </Button>
      </div>

      <div className="space-y-4 sm:space-y-6">
        {/* Main Hero Card with Integrated Actions & Author Info */}
        <Card className="border-border/80 bg-card shadow-xs rounded-2xl overflow-hidden">
          <CardHeader className="space-y-3.5 p-4 sm:p-6 pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2.5">
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
                {deck.is_owner && (
                  <Badge
                    variant="outline"
                    className={`text-xs font-bold px-2 py-0.5 rounded-md ${
                      deck.publish_status === 'published'
                        ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                        : deck.publish_status === 'unlisted'
                        ? 'border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400'
                        : 'border-destructive/30 bg-destructive/10 text-destructive'
                    }`}
                  >
                    {deck.publish_status === 'published' ? (
                      <>
                        <Globe className="mr-1 size-3 text-emerald-500" />
                        Đang hiển thị
                      </>
                    ) : deck.publish_status === 'unlisted' ? (
                      <>
                        <Globe className="mr-1 size-3 text-blue-500" />
                        Không công khai
                      </>
                    ) : (
                      <>
                        <Lock className="mr-1 size-3 text-destructive" />
                        Riêng tư (Đã thu hồi)
                      </>
                    )}
                  </Badge>
                )}
                {deck.has_student_offer && (
                  <Badge className="bg-emerald-500/15 text-emerald-700 border-emerald-500/30 dark:text-emerald-400 font-semibold shadow-xs">
                    <GraduationCap className="mr-1 size-3 text-emerald-600 dark:text-emerald-400" />
                    {deck.student_offer_mode === 'free'
                      ? 'Miễn phí cho SV'
                      : `Giảm ${deck.student_discount_percent}% SV`}
                  </Badge>
                )}
              </div>

              {deck.student_discount_applied ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground line-through font-semibold">
                    {deck.price_display}
                  </span>
                  <span className="inline-flex items-center rounded-full px-3 py-1 text-xs font-extrabold border bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30">
                    <GraduationCap className="mr-1 size-3.5 text-emerald-600 dark:text-emerald-400" />
                    {deck.effective_price_display || 'Miễn phí'}
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
                  {deck.pricing_mode === 'free' ? (
                    <Sparkles className="mr-1 size-3" />
                  ) : null}
                  {deck.price_display || 'Miễn phí'}
                </span>
              )}
            </div>

            <CardTitle className="text-2xl font-black tracking-tight text-foreground sm:text-3xl lg:text-4xl leading-tight">
              {deckTitle}
            </CardTitle>

            <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-muted-foreground pt-0.5">
              <div className="flex items-center gap-2">
                <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-xs ring-1 ring-primary/20">
                  {authorName.charAt(0).toUpperCase()}
                </div>
                <div className="flex items-center gap-1.5 font-semibold text-foreground">
                  <span>{authorName}</span>
                  <span className="text-muted-foreground font-normal hidden sm:inline">
                    ({deck.author_profile?.published_count || 1} bộ thẻ đã xuất bản)
                  </span>
                </div>
              </div>
              <span className="text-muted-foreground/40 hidden sm:inline">•</span>
              <span className="inline-flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md text-[11px]">
                <CheckCircle className="size-3" /> Flama Marketplace
              </span>
              {deck.updated_at ? (
                <>
                  <span className="text-muted-foreground/40 hidden sm:inline">•</span>
                  <span className="text-muted-foreground text-[11px]">
                    Cập nhật: {new Date(deck.updated_at).toLocaleDateString('vi-VN')}
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

            {/* Stat Grid (2x2 on mobile, 4 columns on tablet & desktop) */}
            <div className="grid grid-cols-2 gap-2.5 sm:gap-3.5 sm:grid-cols-4">
              <div className="rounded-xl border border-border/80 bg-muted/30 p-3 sm:p-4 text-center transition-all hover:bg-muted/50">
                <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
                  <Star className="size-3.5 fill-amber-400 text-amber-500" />
                  <span>Đánh giá</span>
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
                  <span>Lượt cài</span>
                </div>
                <div className="mt-1 font-extrabold text-lg sm:text-2xl text-foreground tabular-nums font-mono">
                  {deck.install_count.toLocaleString('vi-VN')}
                </div>
              </div>

              <div className="rounded-xl border border-border/80 bg-muted/30 p-3 sm:p-4 text-center transition-all hover:bg-muted/50">
                <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
                  <BookOpen className="size-3.5 text-primary" />
                  <span>Bài học</span>
                </div>
                <div className="mt-1 font-extrabold text-lg sm:text-2xl text-foreground tabular-nums font-mono">
                  {deck.lesson_count ? `${deck.lesson_count} bài` : '1 bài'}
                </div>
              </div>

              <div className="rounded-xl border border-border/80 bg-muted/30 p-3 sm:p-4 text-center transition-all hover:bg-muted/50">
                <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
                  <Layers className="size-3.5 text-primary" />
                  <span>Từ vựng</span>
                </div>
                <div className="mt-1 font-extrabold text-lg sm:text-2xl text-foreground tabular-nums font-mono">
                  {(deck.note_count || samples.length).toLocaleString('vi-VN')} từ
                </div>
              </div>
            </div>

            {/* Integrated Primary Action Area */}
            <div className="pt-3 border-t border-border/60">
              {deck.is_owner ? (
                <div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:flex lg:flex-wrap items-center gap-2 sm:gap-2.5">
                  <Button
                    variant="secondary"
                    size="sm"
                    className="h-10 sm:h-10 min-h-[40px] px-4 rounded-xl text-xs font-bold shadow-2xs justify-center"
                    asChild
                  >
                    <Link to={`/creator/decks/${id}/releases/new`}>
                      <GitCompare className="mr-1.5 size-3.5 text-primary" />
                      Phát hành phiên bản mới
                    </Link>
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    className="h-10 sm:h-10 min-h-[40px] px-4 rounded-xl text-xs font-bold justify-center"
                    asChild
                  >
                    <Link to={`/flashcards/change-requests/incoming?deck_item_id=${id}`}>
                      <Inbox className="mr-1.5 size-3.5" />
                      Đóng góp cần duyệt
                    </Link>
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    className="h-10 sm:h-10 min-h-[40px] px-4 font-bold text-xs rounded-xl justify-center"
                    asChild
                  >
                    <Link to={`/marketplace/decks/publish?deck_id=${deck.source_deck_id}&deck_item_id=${deck.id}&edit=1`}>
                      <Edit3 className="mr-1.5 size-3.5 text-primary" />
                      Chỉnh sửa thông tin
                    </Link>
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    className={`h-10 sm:h-10 min-h-[40px] px-4 font-bold text-xs rounded-xl justify-center transition-all ${
                      showKeyManager ? 'bg-primary/10 border-primary text-primary' : ''
                    }`}
                    onClick={() => setShowKeyManager(!showKeyManager)}
                  >
                    <KeyRound className="mr-1.5 size-3.5 text-primary" />
                    {showKeyManager ? 'Ẩn Quản lý Mã' : 'Mã lớp học (Keys)'}
                  </Button>

                  {deck.publish_status === 'published' || deck.publish_status === 'unlisted' ? (
                    <Button
                      variant="destructive"
                      size="sm"
                      className="h-10 sm:h-10 min-h-[40px] px-4 font-bold text-xs rounded-xl justify-center"
                      onClick={() => {
                        if (
                          window.confirm(
                            'Bạn có chắc chắn muốn thu hồi bộ thẻ này khỏi Marketplace?\n\nNgười dùng khác sẽ không thể tìm thấy hoặc cài đặt bộ thẻ này nữa.'
                          )
                        ) {
                          publishStatusMutation.mutate('private')
                        }
                      }}
                      disabled={publishStatusMutation.isPending}
                    >
                      <EyeOff className="mr-1.5 size-3.5" />
                      Thu hồi bộ deck
                    </Button>
                  ) : (
                    <Button
                      variant="default"
                      size="sm"
                      className="h-10 sm:h-10 min-h-[40px] px-4 font-bold text-xs rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white justify-center"
                      onClick={() => publishStatusMutation.mutate('published')}
                      disabled={publishStatusMutation.isPending}
                    >
                      <Globe className="mr-1.5 size-3.5" />
                      Xuất bản lại
                    </Button>
                  )}
                </div>

                {/* Creator Auto-Publish Management Panel */}
                {autoPublishQuery.data ? (
                  <div className="mt-4 rounded-2xl border border-primary/20 bg-primary/5 p-4 sm:p-4.5 space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                          <Zap className="size-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="text-xs sm:text-sm font-bold text-foreground">
                              Tự động phát hành (Auto-Publish)
                            </h4>
                            <Badge
                              variant={autoPublishQuery.data.auto_publish_enabled ? 'default' : 'secondary'}
                              className="text-[10px] px-1.5 py-0 font-bold"
                            >
                              {autoPublishQuery.data.auto_publish_enabled ? 'BẬT' : 'TẮT'}
                            </Badge>
                          </div>
                          <p className="text-[11px] sm:text-xs text-muted-foreground leading-normal mt-0.5">
                            Khi bật, các thay đổi từ deck gốc sẽ tự động đóng gói thành release mới và thông báo đến người học.
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-muted-foreground">
                          {autoPublishQuery.data.auto_publish_enabled ? 'Đang bật' : 'Đang tắt'}
                        </span>
                        <Switch
                          checked={autoPublishQuery.data.auto_publish_enabled}
                          disabled={autoPublishMutation.isPending}
                          onCheckedChange={(checked) => autoPublishMutation.mutate(checked)}
                          aria-label="Bật hoặc tắt tự động phát hành"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-2.5 border-t border-primary/15 text-xs">
                      <div className="flex items-center gap-1.5 text-muted-foreground">
                        <Clock className="size-3.5 text-primary shrink-0" />
                        <span>
                          Phiên bản: <strong className="text-foreground">{autoPublishQuery.data.current_release?.version_label || deck.version || '1.0.0'}</strong>
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 text-muted-foreground">
                        <GitCompare className="size-3.5 text-primary shrink-0" />
                        <span>
                          Đang chờ: <strong className="text-foreground">{autoPublishQuery.data.pending_changes_count} thay đổi</strong>
                        </span>
                      </div>
                      {autoPublishQuery.data.last_auto_published_at ? (
                        <div className="flex items-center gap-1.5 text-muted-foreground truncate">
                          <span>Đã phát hành: <strong className="text-foreground">{new Date(autoPublishQuery.data.last_auto_published_at).toLocaleString('vi-VN')}</strong></span>
                        </div>
                      ) : null}
                    </div>

                    {autoPublishQuery.data.last_auto_publish_error ? (
                      <div className="flex items-center gap-1.5 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-xs text-destructive">
                        <AlertCircle className="size-3.5 shrink-0" />
                        <span>Lỗi phát hành gần nhất: {autoPublishQuery.data.last_auto_publish_error}</span>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : deck.is_installed ? (
                <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-2.5">
                  {deck.installed_deck_id ? (
                    <Button
                      className="h-11 sm:h-11 min-h-[44px] px-5 font-bold text-sm shadow-xs bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl transition-all justify-center"
                      asChild
                    >
                      <Link to={`/study?deck_id=${deck.installed_deck_id}`}>
                        <BookOpen className="mr-2 size-4" />
                        Bắt đầu học ngay
                      </Link>
                    </Button>
                  ) : null}

                  <div className="inline-flex items-center justify-center gap-1.5 h-11 min-h-[44px] px-4 font-bold text-xs sm:text-sm border border-emerald-500/40 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 rounded-xl">
                    <CheckCircle className="size-4 text-emerald-500" />
                    Đã cài đặt vào thư viện
                  </div>

                  <Button
                    className="h-11 min-h-[44px] px-4 font-semibold text-xs sm:text-sm rounded-xl justify-center"
                    variant="outline"
                    asChild
                  >
                    <Link to={`/flashcards/shared-decks/${id}/change-request`}>
                      <FileDiff className="mr-1.5 size-4" />
                      Đóng góp chỉnh sửa
                    </Link>
                  </Button>

                  <Button
                    className="h-11 min-h-[44px] px-4 font-semibold text-xs sm:text-sm rounded-xl justify-center"
                    variant="outline"
                    onClick={() => saveMutation.mutate(deck.is_saved)}
                    disabled={saveMutation.isPending}
                  >
                    <Heart
                      className={`mr-1.5 size-4 ${
                        deck.is_saved ? 'fill-primary text-primary' : ''
                      }`}
                    />
                    {deck.is_saved ? 'Đã lưu' : 'Lưu bộ deck'}
                  </Button>
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {deck.has_student_offer && deck.user_student_status === 'eligible_unverified_email' && (
                    <div className="w-full rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-300 flex items-start gap-2">
                      <GraduationCap className="size-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
                      <div className="flex-1 leading-relaxed">
                        <span>Bạn đang sử dụng email trường học (.edu.vn). </span>
                        <Link to="/profile" className="font-bold underline hover:opacity-80">
                          Xác thực email trong trang Hồ sơ
                        </Link>
                        <span> để nhận ưu đãi {deck.student_offer_mode === 'free' ? 'miễn phí bộ thẻ này' : `giảm ${deck.student_discount_percent}%`}!</span>
                      </div>
                    </div>
                  )}

                  <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-3">
                    <Button
                      className="h-11 sm:h-12 min-h-[44px] px-6 font-bold text-sm sm:text-base shadow-sm bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl transition-all justify-center"
                      size="lg"
                      onClick={() => installMutation.mutate()}
                      disabled={installMutation.isPending}
                    >
                      {installMutation.isPending ? (
                        <>
                          <Loader2 className="mr-2 size-5 animate-spin" />
                          {deck.pricing_mode === 'paid' && (!deck.student_discount_applied || deck.effective_price_amount_minor !== 0)
                            ? 'Đang tạo thanh toán…'
                            : 'Đang cài đặt bộ thẻ…'}
                        </>
                      ) : (
                        <>
                          <Download className="mr-2 size-5" />
                          {deck.pricing_mode === 'paid'
                            ? deck.student_discount_applied && deck.effective_price_amount_minor === 0
                              ? 'Tải xuống miễn phí (Ưu đãi Sinh viên)'
                              : deck.student_discount_applied
                              ? `Mua bộ deck • ${deck.effective_price_display} (Đã giảm ${deck.student_discount_percent}%)`
                              : `Mua bộ deck • ${deck.price_display}`
                            : 'Tải xuống & Cài đặt miễn phí'}
                        </>
                      )}
                    </Button>

                  <Button
                    className="h-11 sm:h-12 min-h-[44px] px-4 font-semibold text-xs sm:text-sm rounded-xl justify-center border-primary/30 hover:bg-primary/5"
                    variant="outline"
                    onClick={() => setIsRedeemModalOpen(true)}
                  >
                    <KeyRound className="mr-1.5 size-4 text-primary" />
                    Nhập mã kích hoạt
                  </Button>

                    <Button
                      className="h-11 sm:h-12 min-h-[44px] px-4 font-semibold text-xs sm:text-sm rounded-xl justify-center"
                      variant="outline"
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
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Creator Access Keys Management Section */}
        {deck.is_owner && showKeyManager && (
          <div className="animate-in fade-in slide-in-from-top-4 duration-300">
            <DeckAccessKeysManager deckItemId={id!} deckTitle={deck.title || ''} />
          </div>
        )}



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

            {/* Quick Word Select Chips with Smooth Horizontal Scroll */}
            {samples.length > 0 ? (
              <div className="p-3 sm:p-3.5 bg-muted/10 border-b border-border/60">
                <div className="text-xs font-semibold text-muted-foreground mb-1.5 flex items-center justify-between">
                  <span>Chọn nhanh từ mẫu:</span>
                  <span className="text-[11px] font-normal text-muted-foreground">({samples.length} mẫu)</span>
                </div>
                <div
                  className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none touch-pan-x overscroll-x-contain"
                  style={{ WebkitOverflowScrolling: 'touch' }}
                >
                  {samples.map((sample, idx) => {
                    const isSelected = idx === activeSampleIndex
                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setActiveSampleIndex(idx)}
                        className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
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

          {/* Section 2: Deck Lessons & Word Counts Breakdown */}
          <Card className="border-border shadow-xs overflow-hidden rounded-2xl">
            <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-muted/20">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2.5 rounded-xl bg-primary/10 text-primary">
                    <BookOpen className="size-5" />
                  </div>
                  <div>
                    <CardTitle className="text-lg font-bold flex flex-wrap items-center gap-2">
                      <span>Cấu trúc bài học & từ vựng</span>
                      {deck.lesson_count ? (
                        <Badge variant="secondary" className="text-xs font-bold rounded-md">
                          {deck.lesson_count} bài
                        </Badge>
                      ) : null}
                      <Badge variant="outline" className="text-xs font-bold rounded-md text-primary border-primary/30">
                        {(deck.note_count || samples.length).toLocaleString('vi-VN')} từ vựng
                      </Badge>
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Chi tiết danh sách các bài học và số lượng từ vựng trong bộ thẻ này.
                    </CardDescription>
                  </div>
                </div>

                {deck.lessons && deck.lessons.length > 3 ? (
                  <div className="relative w-full sm:w-60">
                    <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
                    <Input
                      placeholder="Tìm kiếm bài học..."
                      value={lessonSearch}
                      onChange={(e) => setLessonSearch(e.target.value)}
                      className="h-8 pl-8 text-xs rounded-lg"
                    />
                  </div>
                ) : null}
              </div>
            </CardHeader>

            <CardContent className="p-4 sm:p-5 pt-4 space-y-2.5">
              {displayLessons.length > 0 ? (
                <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                  {displayLessons.map((lesson, idx) => (
                    <div
                      key={lesson.id}
                      className="flex items-center justify-between p-3 rounded-xl border border-border/80 bg-card hover:bg-muted/30 transition-colors shadow-2xs gap-3"
                      style={{ paddingLeft: `${Math.max(12, (lesson.depth || 0) * 16 + 12)}px` }}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary font-bold text-xs">
                          {lesson.depth > 0 ? '•' : idx + 1}
                        </div>
                        <span className="font-bold text-xs sm:text-sm text-foreground truncate">
                          {lesson.name}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <Badge
                          variant="secondary"
                          className="font-bold text-xs px-2.5 py-0.5 rounded-md bg-primary/10 text-primary hover:bg-primary/15"
                        >
                          <Layers className="mr-1 size-3" />
                          {lesson.note_count.toLocaleString('vi-VN')} từ
                        </Badge>
                        {lesson.card_count && lesson.card_count !== lesson.note_count ? (
                          <Badge variant="outline" className="text-xs font-semibold text-muted-foreground rounded-md">
                            {lesson.card_count.toLocaleString('vi-VN')} thẻ
                          </Badge>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : lessonSearch ? (
                <div className="text-center py-6 text-xs text-muted-foreground">
                  Không tìm thấy bài học nào phù hợp với từ khóa &ldquo;{lessonSearch}&rdquo;.
                </div>
              ) : (
                <div className="flex items-center justify-between p-4 rounded-xl border border-border/80 bg-muted/20 text-xs">
                  <span className="font-semibold text-foreground">1 bài học tổng hợp</span>
                  <Badge variant="secondary" className="font-bold text-xs">
                    {(deck.note_count || samples.length).toLocaleString('vi-VN')} từ vựng
                  </Badge>
                </div>
              )}
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

          {/* Related Items Section */}
          {deck.related_items && deck.related_items.length > 0 ? (
            <Card className="border-border shadow-xs rounded-2xl overflow-hidden">
              <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-muted/20">
                <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2">
                  <Layers className="size-4 text-primary" />
                  <span>Bộ thẻ liên quan khác</span>
                </CardTitle>
                <CardDescription className="text-xs">
                  Khám phá thêm các bộ thẻ cùng chủ đề trên Flama Marketplace
                </CardDescription>
              </CardHeader>
              <CardContent className="p-4 sm:p-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {deck.related_items.map((item) => (
                    <Link
                      key={item.id}
                      to={`/marketplace/decks/${item.id}`}
                      className="group block rounded-xl border border-border/80 bg-card p-3.5 hover:bg-muted/30 hover:border-primary/40 transition-all shadow-2xs"
                    >
                      <div className="font-bold text-xs sm:text-sm text-foreground group-hover:text-primary transition-colors line-clamp-1">
                        {item.title || item.name || 'Bộ thẻ liên quan'}
                      </div>
                      <div className="flex items-center justify-between text-xs text-muted-foreground mt-2">
                        <span className="font-bold text-primary">
                          {item.price_display || 'Miễn phí'}
                        </span>
                        <span className="flex items-center gap-1 font-bold text-amber-500">
                          <Star className="size-3.5 fill-amber-400" />
                          {(item.rating_avg || 0).toFixed(1)}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>

        {/* Redeem Deck Key Modal */}
        <RedeemDeckKeyModal
          isOpen={isRedeemModalOpen}
          onClose={() => setIsRedeemModalOpen(false)}
          initialKey={urlCode}
          deckItemId={id}
        />
      </Page>
  )
}

