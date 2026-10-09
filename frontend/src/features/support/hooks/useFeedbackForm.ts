import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { compressImage, MAX_IMAGE_UPLOAD_BYTES } from '@/lib/imageCompression'
import type { FeedbackCategory, TicketItem } from '../types'
import { getCategories, resolveScreenName } from '../utils/supportHelpers'

export function useFeedbackForm(
  activeTab: 'create' | 'my-tickets',
  onTicketCreated?: () => void
) {
  const { t } = useTranslation('support')
  const queryClient = useQueryClient()

  const [category, setCategory] = useState<FeedbackCategory>('bug')
  const [urlPath, setUrlPath] = useState(
    typeof window !== 'undefined' ? window.location.href : ''
  )
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [reproduceSteps, setReproduceSteps] = useState('')
  const [attachedUrls, setAttachedUrls] = useState<string[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)

  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const resolvedScreenName = resolveScreenName(
    urlPath,
    t('feedback.unrecognized_screen'),
    t
  )
  const categories = getCategories(t)
  const activeCategoryConfig =
    categories.find((c) => c.key === category) || categories[0]

  const uploadImageFile = useCallback(
    async (file: File) => {
      if (!file.type.startsWith('image/')) {
        toast.error(t('toast.image_only'))
        return
      }

      setIsUploading(true)
      try {
        let fileToSend: File = file
        try {
          const compressed = await compressImage(file, {
            maxDimension: 1600,
            quality: 0.85,
          })
          fileToSend = compressed.file
        } catch {
          // Fall back to original file if compression fails
        }

        if (fileToSend.size > MAX_IMAGE_UPLOAD_BYTES) {
          toast.error(t('toast.image_too_large'))
          return
        }

        const formData = new FormData()
        formData.append('file', fileToSend)
        const res = await appApi.mutateFormData<{ url: string }>(
          '/tickets/upload-image',
          'POST',
          formData
        )
        if (res.url) {
          setAttachedUrls((prev) => {
            if (prev.length >= 5) {
              toast.error(t('toast.max_images'))
              return prev
            }
            return [...prev, res.url]
          })
          toast.success(t('toast.image_uploaded'))
        }
      } catch (err: any) {
        toast.error(
          err?.response?.data?.message || err?.message || t('toast.upload_failed')
        )
      } finally {
        setIsUploading(false)
      }
    },
    [t]
  )

  // Clipboard Paste Handler (Ctrl+V)
  useEffect(() => {
    if (activeTab !== 'create') return

    const handlePaste = (e: ClipboardEvent) => {
      const clipboardItems = e.clipboardData?.items
      if (!clipboardItems) return

      for (let i = 0; i < clipboardItems.length; i++) {
        const item = clipboardItems[i]
        if (item.type.startsWith('image/')) {
          const blob = item.getAsFile()
          if (blob) {
            e.preventDefault()
            toast.info(t('toast.clipboard_uploading'))
            void uploadImageFile(blob)
            break
          }
        }
      }
    }

    window.addEventListener('paste', handlePaste)
    return () => {
      window.removeEventListener('paste', handlePaste)
    }
  }, [activeTab, uploadImageFile, t])

  // Drag & drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (!files || files.length === 0) return
    Array.from(files).forEach((file) => {
      void uploadImageFile(file)
    })
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    Array.from(files).forEach((file) => {
      void uploadImageFile(file)
    })
    e.target.value = ''
  }

  // Create Ticket mutation
  const createTicketMutation = useMutation({
    mutationFn: (payload: {
      category: string
      title: string
      description: string
      reproduce_steps?: string
      screen_url?: string
      screen_name?: string
      attachment_urls?: string[]
    }) => appApi.mutate<{ item: TicketItem }>('/tickets', 'POST', payload),
    onSuccess: (data) => {
      const ticketCode = data.item?.ticket_code || 'Mới'
      toast.success(t('toast.ticket_sent', { code: ticketCode }))
      // Reset form
      setTitle('')
      setDescription('')
      setReproduceSteps('')
      setAttachedUrls([])
      void queryClient.invalidateQueries({ queryKey: ['user', 'my-tickets'] })
      onTicketCreated?.()
    },
    onError: (err: any) => {
      toast.error(
        err?.response?.data?.message || err?.message || t('toast.ticket_failed')
      )
    },
  })

  const handleSubmitTicket = (e: React.FormEvent) => {
    e.preventDefault()
    if (!description.trim()) {
      toast.error(t('feedback.step_desc'))
      return
    }

    const autoTitle =
      title.trim() ||
      `[${activeCategoryConfig.title}] ${
        resolvedScreenName !== t('feedback.unrecognized_screen')
          ? resolvedScreenName
          : 'Flama'
      }`

    createTicketMutation.mutate({
      category,
      title: autoTitle,
      description: description.trim(),
      reproduce_steps:
        category === 'bug' && reproduceSteps.trim()
          ? reproduceSteps.trim()
          : undefined,
      screen_url: urlPath.trim() || undefined,
      screen_name:
        resolvedScreenName !== t('feedback.unrecognized_screen')
          ? resolvedScreenName
          : undefined,
      attachment_urls: attachedUrls,
    })
  }

  const fillCurrentUrl = () => {
    setUrlPath(window.location.href)
    toast.success(t('toast.copied', { name: 'URL' }))
  }

  return {
    category,
    setCategory,
    urlPath,
    setUrlPath,
    title,
    setTitle,
    description,
    setDescription,
    reproduceSteps,
    setReproduceSteps,
    attachedUrls,
    setAttachedUrls,
    isUploading,
    isDragging,
    fileInputRef,
    resolvedScreenName,
    activeCategoryConfig,
    categories,
    uploadImageFile,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleFileChange,
    handleSubmitTicket,
    fillCurrentUrl,
    createTicketMutation,
  }
}
