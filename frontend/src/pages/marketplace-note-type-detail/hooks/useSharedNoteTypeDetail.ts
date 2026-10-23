import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { noteTypeDetailApi } from '../api/noteTypeDetailApi'
import { canonicalTemplateId, templateOccurrenceId } from '../model/types'

export function useSharedNoteTypeDetail() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { t, i18n } = useTranslation('marketplace')
  const numberLocale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  const [previewSide, setPreviewSide] = useState<'front' | 'back'>('front')
  const [selectedApplicationId, setSelectedApplicationId] = useState<string>('')
  const [isCopied, setIsCopied] = useState(false)
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => { if (copyTimer.current) clearTimeout(copyTimer.current) }, [])

  // Rating state
  const [ratingScore, setRatingScore] = useState<number>(5)
  const [hoverScore, setHoverScore] = useState<number | null>(null)
  const [ratingComment, setRatingComment] = useState<string>('')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null)

  const noteTypeQuery = useQuery({
    queryKey: ['shared-note-type-detail', id],
    queryFn: () => noteTypeDetailApi.detail(id!),
    enabled: Boolean(id),
  })

  const noteType = noteTypeQuery.data
  const templates = noteType?.templates || []
  const firstApplicationId = templates[0] ? templateOccurrenceId(templates[0]) : ''
  const selectedTemplate = templates.find((template) => templateOccurrenceId(template) === selectedApplicationId)

  useEffect(() => {
    if (firstApplicationId && !selectedTemplate) {
      setSelectedApplicationId(firstApplicationId)
    }
  }, [firstApplicationId, selectedTemplate])

  // Template Preview Query
  const previewQuery = useQuery({
    queryKey: ['shared-note-type-preview', id, selectedApplicationId, selectedTemplate ? canonicalTemplateId(selectedTemplate) : ''],
    // The preview endpoint renders server-side and only accepts POST.
    queryFn: () =>
      noteTypeDetailApi.preview(id!, canonicalTemplateId(selectedTemplate!), selectedTemplate?.application_id),
    enabled: Boolean(id && selectedTemplate),
  })

  // Install Mutation
  const installMutation = useMutation({
    mutationFn: () => noteTypeDetailApi.install(id!),
    onSuccess: (data: any) => {
      if (data?.payment_required) {
        const checkoutUrl = data.order?.active_attempt?.checkout_url
        if (checkoutUrl) window.location.href = checkoutUrl
        else toast.error(t('bundle.checkout_unavailable'))
        return
      }
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
      queryClient.invalidateQueries({ queryKey: ['note-types'] })
      toast.success(
        t('detail.install_notetype_success', 'Cài đặt Note Type thành công! Mẫu đã được lưu vào thư viện của bạn.')
      )
    },
    onError: (err: any) => {
      toast.error(err?.message || t('common.error', 'Không thể cài đặt loại thẻ này.'))
    },
  })

  // Install Individual Template Mutation
  const [installingTemplateId, setInstallingTemplateId] = useState<string | null>(null)
  const installTemplateMutation = useMutation({
    mutationFn: (templateId: string) => {
      setInstallingTemplateId(templateId)
      return noteTypeDetailApi.installTemplate(id!, templateId)
    },
    onSuccess: (data) => {
      setInstallingTemplateId(null)
      if (data.payment_required) {
        const checkoutUrl = data.order?.active_attempt?.checkout_url
        if (checkoutUrl) window.location.href = checkoutUrl
        else toast.error(t('bundle.checkout_unavailable'))
        return
      }
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
      queryClient.invalidateQueries({ queryKey: ['card-templates'] })
      queryClient.invalidateQueries({ queryKey: ['card-templates-library'] })
      toast.success(
        t('notetype_detail.toast_template_installed', {
          defaultValue: 'Đã thêm mẫu giao diện vào thư viện của bạn!',
        })
      )
    },
    onError: (err: any) => {
      setInstallingTemplateId(null)
      toast.error(
        err?.message ||
          t('notetype_detail.error_install_template', {
            defaultValue: 'Không thể thêm mẫu giao diện vào thư viện.',
          })
      )
    },
  })

  // Save/Bookmark Mutation
  const saveMutation = useMutation({
    mutationFn: (currentlySaved: boolean) =>
      noteTypeDetailApi.save(id!, currentlySaved),
    onSuccess: (_, currentlySaved) => {
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
      toast.success(
        currentlySaved
          ? t('notetype_detail.toast_unsaved', 'Đã bỏ lưu loại thẻ')
          : t('notetype_detail.toast_saved', 'Đã lưu loại thẻ')
      )
    },
    onError: (err: any) => {
      toast.error(err?.message || t('common.error', 'Không thể cập nhật trạng thái lưu.'))
    },
  })

  // Rate Mutation
  const rateMutation = useMutation({
    mutationFn: () =>
      noteTypeDetailApi.rate(id!, {
        rating: ratingScore,
        comment: ratingComment.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
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

  // Publish Status Mutation for Creator
  const publishStatusMutation = useMutation({
    mutationFn: (newStatus: 'private' | 'published') =>
      noteTypeDetailApi.status(id!, {
        publish_status: newStatus,
      }),
    onSuccess: (_, newStatus) => {
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
      toast.success(
        newStatus === 'private'
          ? t('notetype_detail.toast_revoked', 'Đã thu hồi loại thẻ khỏi Marketplace.')
          : t('notetype_detail.toast_republished', 'Đã xuất bản lại loại thẻ lên Marketplace.')
      )
    },
    onError: (err: any) => {
      toast.error(err?.message || t('common.error', 'Không thể cập nhật trạng thái xuất bản.'))
    },
  })

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setIsCopied(true)
      toast.success(t('notetype_detail.toast_copied', 'Đã sao chép liên kết!'))
      if (copyTimer.current) clearTimeout(copyTimer.current)
      copyTimer.current = setTimeout(() => setIsCopied(false), 2000)
    } catch {
      toast.error(t('common.error', 'Không thể sao chép liên kết.'))
    }
  }

  return { id, t, numberLocale, previewSide, setPreviewSide, selectedApplicationId, setSelectedApplicationId, isCopied, ratingScore, setRatingScore, hoverScore, setHoverScore, ratingComment, setRatingComment, submitError, submitSuccess, noteTypeQuery, noteType, templates, previewQuery, installMutation, installingTemplateId, installTemplateMutation, saveMutation, rateMutation, publishStatusMutation, handleCopyLink }
}
