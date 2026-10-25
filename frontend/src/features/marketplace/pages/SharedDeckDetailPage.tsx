import { useEffect, useState, useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { getAutoPublishStatus, updateAutoPublishSetting } from '@/features/deck-collaboration/api'
import { DeckAccessKeysManager } from '../components/keys/DeckAccessKeysManager'
import { RedeemDeckKeyModal } from '../components/keys/RedeemDeckKeyModal'
import { DeckDetailHeader } from '../components/deck-detail/DeckDetailHeader'
import { DeckDetailOwnerBar } from '../components/deck-detail/DeckDetailOwnerBar'
import { DeckCardPreviewSection } from '../components/deck-detail/DeckCardPreviewSection'
import { DeckLessonsSection } from '../components/deck-detail/DeckLessonsSection'
import { DeckReviewsSection } from '../components/deck-detail/DeckReviewsSection'
import { DeckRelatedSection } from '../components/deck-detail/DeckRelatedSection'
import { useDeckPublishStatus } from '../hooks/useDeckPublishStatus'

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
  distribution_mode?: 'free' | 'paid' | 'course_key'
  requires_access_key?: boolean
  course_title?: string | null
  course_description?: string | null
  course_url?: string | null
  course_instructions?: string | null
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
  const { t } = useTranslation('marketplace')
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
          ? t('detail.owner_admin.auto_publish_enabled_toast', 'Đã bật chế độ tự động phát hành phiên bản mới.')
          : t('detail.owner_admin.auto_publish_disabled_toast', 'Đã tắt chế độ tự động phát hành.')
      )
    },
    onError: (err) => {
      toast.error(
        err instanceof Error ? err.message : t('common.error', 'Không thể cập nhật cấu hình tự động phát hành.')
      )
    },
  })

  // Template Preview Query
  const previewQuery = useQuery({
    queryKey: ['shared-deck-preview', id, selectedTemplateId, currentSample?.note_id],
    queryFn: () =>
      appApi.mutate<PreviewResponse>(
        `/api/shared/decks/${id}/templates/${selectedTemplateId}/preview`,
        'POST',
        { note_id: currentSample?.note_id }
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

      toast?.loading?.(t('detail.install_toast_loading', 'Đang khởi tạo và cài đặt bộ thẻ…'), {
        id: 'shared-deck-install',
        description: countSummary
          ? t('detail.install_toast_desc', {
              summary: countSummary,
              defaultValue: `Đang thiết lập ${countSummary} vào thư viện của bạn. Vui lòng không đóng trình duyệt!`,
            })
          : undefined,
      })
    },
    onSuccess: (data) => {
      toast?.dismiss?.('shared-deck-install')
      if (data?.payment_required && data?.order?.active_attempt?.checkout_url) {
        window.location.href = data.order.active_attempt.checkout_url
        return
      }
      queryClient.invalidateQueries({ queryKey: ['shared-deck-detail', id] })
      queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
      queryClient.invalidateQueries({ queryKey: ['deck-tree'] })

      toast.success(
        t('detail.install_toast_success', 'Cài đặt bộ thẻ thành công! Bạn có thể bắt đầu ôn luyện ngay.'),
        {
          action: data?.installed_deck_id
            ? {
                label: t('detail.btn_study_now', 'Học ngay'),
                onClick: () => navigate(`/study?deck_id=${data.installed_deck_id}`),
              }
            : undefined,
        }
      )
    },
    onError: (err: any) => {
      toast?.dismiss?.('shared-deck-install')
      toast.error(err?.message || t('common.error', 'Không thể cài đặt bộ thẻ.'))
    },
  })

  // Save/Bookmark Mutation
  const saveMutation = useMutation({
    mutationFn: (currentlySaved: boolean) =>
      appApi.mutate(
        `/api/shared/decks/${id}/save`,
        currentlySaved ? 'DELETE' : 'POST'
      ),
    onSuccess: (_, currentlySaved) => {
      queryClient.invalidateQueries({ queryKey: ['shared-deck-detail', id] })
      toast.success(
        currentlySaved
          ? t('detail.toast_unsaved', 'Đã bỏ lưu bộ deck')
          : t('detail.toast_saved', 'Đã lưu bộ deck vào danh sách yêu thích')
      )
    },
    onError: (err: any) => {
      toast.error(err?.message || t('common.error', 'Không thể cập nhật trạng thái lưu.'))
    },
  })

  // Rate Mutation
  const rateMutation = useMutation({
    mutationFn: () =>
      appApi.mutate(`/api/shared/decks/${id}/rate`, 'POST', {
        rating: ratingScore,
        comment: ratingComment.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shared-deck-detail', id] })
      setSubmitSuccess(
        t('detail.reviews.success_toast', 'Đã gửi đánh giá thành công! Cảm ơn đóng góp của bạn.')
      )
      setSubmitError(null)
      setRatingComment('')
    },
    onError: (err: any) => {
      setSubmitError(err?.message || t('common.error', 'Không thể gửi đánh giá. Vui lòng thử lại.'))
    },
  })

  const publishStatusMutation = useDeckPublishStatus(id)

  const handlePrevSample = () => {
    if (!samples.length) return
    setActiveSampleIndex((prev) => (prev > 0 ? prev - 1 : samples.length - 1))
  }

  const handleNextSample = () => {
    if (!samples.length) return
    setActiveSampleIndex((prev) => (prev < samples.length - 1 ? prev + 1 : 0))
  }

  if (deckQuery.isLoading) {
    return (
      <Page>
        <PageLoading label={t('detail.loading', 'Đang tải thông tin bộ thẻ…')} />
      </Page>
    )
  }

  if (deckQuery.isError || !deck) {
    return (
      <Page>
        <PageError
          error={deckQuery.error || new Error(t('detail.error_load', 'Không thể tải thông tin bộ thẻ này.'))}
        />
      </Page>
    )
  }

  const effectiveStar = hoverScore ?? ratingScore
  const deckTitle = deck.title || t('card.no_title', 'Bộ thẻ không tên')
  const authorName =
    deck.author?.username ||
    deck.author_profile?.account_name ||
    deck.author_profile?.username ||
    t('card.community_author', 'Cộng đồng Flama')
  const tagsList = deck.display_tags || deck.tags || []

  return (
    <Page className="max-w-6xl mx-auto space-y-6 px-3 sm:px-6 py-4 sm:py-6">
      <AmbientBackground intensity="subtle" />

      {/* Main Hero Header Card */}
      <DeckDetailHeader
        id={id!}
        deck={deck}
        authorName={authorName}
        deckTitle={deckTitle}
        tagsList={tagsList}
        sampleLength={samples.length}
        onSave={() => saveMutation.mutate(deck.is_saved)}
        isSavePending={saveMutation.isPending}
        onInstall={() => installMutation.mutate()}
        isInstallPending={installMutation.isPending}
        onOpenRedeemModal={() => setIsRedeemModalOpen(true)}
        ownerBarNode={
          <DeckDetailOwnerBar
            id={id!}
            deckSourceDeckId={deck.source_deck_id}
            version={deck.version}
            publishStatus={deck.publish_status}
            showKeyManager={showKeyManager}
            setShowKeyManager={setShowKeyManager}
            onUpdatePublishStatus={(st) => publishStatusMutation.mutate(st)}
            isPublishStatusPending={publishStatusMutation.isPending}
            autoPublishData={autoPublishQuery.data}
            autoPublishMutation={autoPublishMutation}
          />
        }
      />

      {/* Creator Access Keys Management Section */}
      {deck.is_owner && showKeyManager && (
        <div className="animate-in fade-in slide-in-from-top-4 duration-300">
          <DeckAccessKeysManager deckItemId={id!} deckTitle={deck.title || ''} />
        </div>
      )}

      {/* Section 1: Interactive Sample & Live Previewer */}
      <DeckCardPreviewSection
        id={id!}
        sourceNoteType={sourceNoteType}
        templates={templates}
        selectedTemplateId={selectedTemplateId}
        setSelectedTemplateId={setSelectedTemplateId}
        previewSide={previewSide}
        setPreviewSide={setPreviewSide}
        samples={samples}
        activeSampleIndex={activeSampleIndex}
        setActiveSampleIndex={setActiveSampleIndex}
        handlePrevSample={handlePrevSample}
        handleNextSample={handleNextSample}
        currentSample={currentSample}
        previewQuery={previewQuery}
      />

      {/* Section 2: Deck Lessons & Word Counts Breakdown */}
      <DeckLessonsSection
        lessons={deck.lessons}
        lessonCount={deck.lesson_count}
        noteCount={deck.note_count}
        sampleLength={samples.length}
        lessonSearch={lessonSearch}
        setLessonSearch={setLessonSearch}
        displayLessons={displayLessons}
      />

      {/* Section 3: Community Reviews */}
      <DeckReviewsSection
        canRate={deck.can_rate}
        ratingScore={ratingScore}
        setRatingScore={setRatingScore}
        hoverScore={hoverScore}
        setHoverScore={setHoverScore}
        effectiveStar={effectiveStar}
        ratingComment={ratingComment}
        setRatingComment={setRatingComment}
        submitError={submitError}
        submitSuccess={submitSuccess}
        rateMutation={rateMutation}
        myReview={deck.my_review}
        recentReviews={deck.recent_reviews}
      />

      {/* Section 4: Related Items */}
      <DeckRelatedSection relatedItems={deck.related_items} />

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
