import { useCallback, useEffect, useRef, useState, type ClipboardEvent } from 'react'
import { toast } from 'sonner'
import { stageNoteMedia } from '../api/media'
import { copiedImageLink } from '../lib/copiedImageLink'

type Options = {
  fieldName: string
  fieldType: 'image' | 'audio' | 'diagram'
  value: string
  onChange: (value: string) => void
  uploadDisabled: boolean
  derivedHtml: string
}

export function useMediaFieldPreview({ fieldName, fieldType, value, onChange, uploadDisabled, derivedHtml }: Options) {
  const [viewMode, setViewMode] = useState<'preview' | 'url' | 'code'>('preview')
  const [isUploading, setIsUploading] = useState(false)
  const [copied, setCopied] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const uploadRef = useRef<AbortController | null>(null)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const valueRef = useRef(value)
  valueRef.current = value

  useEffect(() => {
    setIsUploading(false)
    return () => {
      uploadRef.current?.abort()
      uploadRef.current = null
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
    }
  }, [fieldName])

  const appendUrl = useCallback((url: string) => {
    const current = valueRef.current.trim()
    onChange(current ? `${current}\n${url}` : url)
  }, [onChange])

  const handleCopyCode = useCallback(() => {
    if (!derivedHtml) return
    navigator.clipboard.writeText(derivedHtml).then(() => {
      setCopied(true)
      toast.success('Đã sao chép mã HTML vào clipboard!')
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
      copyTimerRef.current = setTimeout(() => setCopied(false), 2000)
    }).catch(() => toast.error('Không thể sao chép mã.'))
  }, [derivedHtml])

  const handlePaste = useCallback(async (event: ClipboardEvent<HTMLDivElement>) => {
    const clipboard = event.clipboardData
    let imageFile: File | null = null
    for (const item of Array.from(clipboard?.items || [])) {
      if (item.type.startsWith('image/')) {
        imageFile = item.getAsFile()
        if (imageFile) break
      }
    }
    imageFile ||= Array.from(clipboard?.files || []).find((file) => file.type.startsWith('image/')) || null

    if (imageFile) {
      event.preventDefault()
      event.stopPropagation()
      if (fieldType === 'audio') {
        toast.error('Trường âm thanh không thể dán hình ảnh.')
        return
      }
      if (uploadDisabled) {
        const link = copiedImageLink(clipboard)
        if (link) {
          appendUrl(link)
          toast.success('Thẻ này không tải ảnh lên được nên đã dán link của ảnh.')
        } else {
          toast.error('Thẻ này không hỗ trợ tải ảnh lên. Hãy dán link ảnh.')
        }
        return
      }
      if (uploadRef.current) return
      const controller = new AbortController()
      uploadRef.current = controller
      setIsUploading(true)
      try {
        // Resize, re-encoding and security inspection belong to Go on the worker.
        const staged = await stageNoteMedia(imageFile, imageFile.name, {}, controller.signal)
        if (!controller.signal.aborted) {
          appendUrl(staged.url)
          toast.success('Đã tải và tối ưu ảnh thành công!')
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          toast.error(`Không thể dán ảnh: ${error instanceof Error ? error.message : 'Lỗi không xác định khi xử lý ảnh.'}`)
        }
      } finally {
        if (uploadRef.current === controller) {
          uploadRef.current = null
          setIsUploading(false)
        }
      }
      return
    }

    const text = clipboard?.getData('text')?.trim()
    if (text && /^(?:https?:\/\/|\/media\/|\/store\/)/.test(text)) {
      event.preventDefault()
      event.stopPropagation()
      appendUrl(text)
      toast.success('Đã dán liên kết media!')
    }
  }, [fieldType, uploadDisabled, appendUrl])

  return { viewMode, setViewMode, isUploading, copied, containerRef, handleCopyCode, handlePaste }
}
