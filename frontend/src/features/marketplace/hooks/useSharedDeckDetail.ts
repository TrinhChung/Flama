import { useEffect, useState, useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { apiJson, apiRequest } from '@/shared/api/client'
import { getAutoPublishStatus, updateAutoPublishSetting } from '@/entities/deck-publication'
import { useDeckPublishStatus } from './useDeckPublishStatus'
import type { SharedDeckDetail, PreviewResponse } from '../model/sharedDeckDetailTypes'

export function useSharedDeckDetail() {
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
    queryFn: () => apiRequest<SharedDeckDetail>(`/api/shared/decks/${id}`),
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
      apiJson<PreviewResponse>(
        `/api/shared/decks/${id}/templates/${selectedTemplateId}/preview`,
        'POST',
        { note_id: currentSample?.note_id }
      ),
    enabled: Boolean(id && selectedTemplateId),
  })

  // Install Mutation
  const installMutation = useMutation({
    mutationFn: async () => {
      return apiJson<{
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
      apiJson(
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
      apiJson(`/api/shared/decks/${id}/rate`, 'POST', {
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

  return { id, t, urlCode, isRedeemModalOpen, setIsRedeemModalOpen, showKeyManager, setShowKeyManager, activeSampleIndex, setActiveSampleIndex, selectedTemplateId, setSelectedTemplateId, previewSide, setPreviewSide, lessonSearch, setLessonSearch, ratingScore, setRatingScore, hoverScore, setHoverScore, ratingComment, setRatingComment, submitError, submitSuccess, deckQuery, deck, samples, currentSample, sourceNoteType, templates, displayLessons, autoPublishQuery, autoPublishMutation, previewQuery, installMutation, saveMutation, rateMutation, publishStatusMutation, handlePrevSample, handleNextSample }
}
