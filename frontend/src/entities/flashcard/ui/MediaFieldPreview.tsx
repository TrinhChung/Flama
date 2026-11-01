import { useMemo, useState, useCallback, useRef } from 'react'
import { resolveBackendUrl } from '@/config/env'
import { apiRequest } from '@/shared/api/client'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  AlertCircle,
  Check,
  Code2,
  Copy,
  Eye,
  FileImage,
  ImageIcon,
  Link2,
  LoaderCircle,
  Music,
} from 'lucide-react'
import { toast } from 'sonner'
import { compressImage, MAX_IMAGE_UPLOAD_BYTES } from '@/lib/imageCompression'
import { copiedImageLink } from '../lib/copiedImageLink'

export interface MediaFieldPreviewProps {
  fieldName: string
  fieldType: 'image' | 'audio' | 'diagram'
  value: string
  onChange: (value: string) => void
  required?: boolean
  resolveUrl?: (raw: string) => string | undefined
  /** Block pasting image files (e.g. cloned cards, where the backend rejects uploads); links still work. */
  uploadDisabled?: boolean
}

export function resolveDisplayUrl(
  raw: unknown,
  customResolver?: (raw: string) => string | undefined,
): string {
  if (typeof raw !== 'string') return ''
  let value = raw.trim()
  const soundMatch = /^\[sound:(.+)\]$/i.exec(value)
  if (soundMatch) {
    value = soundMatch[1].trim()
  }
  if (customResolver) {
    const resolved = customResolver(value)
    if (resolved) return resolved
  }
  if (/^https:\/\/[^\s"'<>]+$/i.test(value)) return value
  if (/^http:\/\/(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?\/[^\s"'<>]*$/i.test(value)) return value
  if (/^\/(?:media\/)?(?:store|proxy)\/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value)) return resolveBackendUrl(value)
  if (/^\/media\/staged\/[A-Za-z0-9_-]{8,64}$/.test(value)) return resolveBackendUrl(value)
  if (/^\/media\/asset\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(value)) return resolveBackendUrl(value)
  if (/^\/media\/library\/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value)) return resolveBackendUrl(value)
  if (/^\/static\/strokes\/[A-Za-z0-9_-]+\/[A-Fa-f0-9]+\.svg$/.test(value)) return resolveBackendUrl(value)
  return ''
}

function parseMediaValues(value: unknown): string[] {
  if (typeof value !== 'string') return []
  return value
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

const IMAGE_EXTENSIONS = new Set(['avif', 'bmp', 'gif', 'jpeg', 'jpg', 'png', 'svg', 'webp'])
const AUDIO_EXTENSIONS = new Set(['aac', 'flac', 'm4a', 'mp3', 'oga', 'ogg', 'opus', 'wav', 'webm'])

function mediaFamilyFromUrl(raw: string): 'image' | 'audio' | null {
  try {
    const path = new URL(raw, window.location.origin).pathname
    if (path.includes('/stroke_')) return 'image'
    const extension = path.split('/').pop()?.split('.').pop()?.toLowerCase() || ''
    if (IMAGE_EXTENSIONS.has(extension)) return 'image'
    if (AUDIO_EXTENSIONS.has(extension)) return 'audio'
  } catch {
    return null
  }
  return null
}

function isValidForField(
  raw: string,
  fieldType: MediaFieldPreviewProps['fieldType'],
  customResolver?: (raw: string) => string | undefined,
): boolean {
  const displayUrl = resolveDisplayUrl(raw, customResolver)
  if (!displayUrl) return false
  const detectedFamily = mediaFamilyFromUrl(displayUrl)
  const expectedFamily = fieldType === 'audio' ? 'audio' : 'image'
  return detectedFamily === null || detectedFamily === expectedFamily
}

function escapeHtmlAttribute(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
}

function buildDerivedHtml(
  urls: string[],
  fieldType: MediaFieldPreviewProps['fieldType'],
  fieldName: string,
  customResolver?: (raw: string) => string | undefined,
): string {
  const tags = urls
    .map((url) => resolveDisplayUrl(url, customResolver))
    .filter(Boolean)
    .map((url) =>
      fieldType === 'audio'
        ? `<audio controls src="${escapeHtmlAttribute(url)}"></audio>`
        : `<img src="${escapeHtmlAttribute(url)}" class="flama-media-image" alt="${escapeHtmlAttribute(fieldName)}">`
    )
  if (tags.length <= 1) return tags[0] || ''
  return `<div class="flama-media-gallery">\n  ${tags.join('\n  ')}\n</div>`
}

export function MediaFieldPreview({
  fieldName,
  fieldType,
  value,
  onChange,
  required,
  resolveUrl,
  uploadDisabled = false,
}: MediaFieldPreviewProps) {
  const [viewMode, setViewMode] = useState<'preview' | 'url' | 'code'>('preview')
  const [isUploading, setIsUploading] = useState(false)
  const [copied, setCopied] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)

  const values = useMemo(() => parseMediaValues(value), [value])
  const validUrls = useMemo(
    () => values.filter((item) => isValidForField(item, fieldType, resolveUrl)),
    [values, fieldType, resolveUrl],
  )
  const invalidCount = values.length - validUrls.length
  const derivedHtml = useMemo(
    () => buildDerivedHtml(validUrls, fieldType, fieldName, resolveUrl),
    [validUrls, fieldType, fieldName, resolveUrl],
  )
  const FieldIcon = fieldType === 'audio' ? Music : fieldType === 'diagram' ? FileImage : ImageIcon

  const handleCopyCode = useCallback(() => {
    if (!derivedHtml) return
    navigator.clipboard.writeText(derivedHtml).then(() => {
      setCopied(true)
      toast.success('Đã sao chép mã HTML vào clipboard!')
      setTimeout(() => setCopied(false), 2000)
    }).catch(() => {
      toast.error('Không thể sao chép mã.')
    })
  }, [derivedHtml])

  const handlePaste = useCallback(
    async (e: React.ClipboardEvent<HTMLDivElement>) => {
      // 1. Check for image files in clipboard
      const items = e.clipboardData?.items
      let imageFile: File | null = null

      if (items) {
        for (let i = 0; i < items.length; i++) {
          if (items[i].type.startsWith('image/')) {
            const blob = items[i].getAsFile()
            if (blob) {
              imageFile = blob
              break
            }
          }
        }
      }

      if (!imageFile && e.clipboardData?.files?.length > 0) {
        for (let i = 0; i < e.clipboardData.files.length; i++) {
          if (e.clipboardData.files[i].type.startsWith('image/')) {
            imageFile = e.clipboardData.files[i]
            break
          }
        }
      }

      if (imageFile) {
        e.preventDefault()
        e.stopPropagation()

        if (fieldType === 'audio') {
          toast.error('Trường âm thanh không thể dán hình ảnh.')
          return
        }

        if (uploadDisabled) {
          // Chrome's "Copy image" also carries the image's address; use it when uploads are off.
          const link = copiedImageLink(e.clipboardData)
          if (link) {
            const trimmedVal = value.trim()
            onChange(trimmedVal ? `${trimmedVal}\n${link}` : link)
            toast.success('Thẻ này không tải ảnh lên được nên đã dán link của ảnh.')
            return
          }
          toast.error('Thẻ này không hỗ trợ tải ảnh lên. Hãy dán link ảnh.')
          return
        }

        setIsUploading(true)
        try {
          let fileToSend: File = imageFile
          try {
            const compressed = await compressImage(imageFile, {
              maxDimension: 1600,
              quality: 0.85,
            })
            fileToSend = compressed.file
          } catch {
            // Fall back to original file if compression fails
          }

          if (fileToSend.size > MAX_IMAGE_UPLOAD_BYTES) {
            toast.error('Dung lượng ảnh vượt quá 2MB. Vui lòng chọn ảnh nhỏ hơn.')
            return
          }

          const formData = new FormData()
          formData.append('file', fileToSend)

          const data = await apiRequest<{ url: string }>(
            '/api/browse/media/stage-paste',
            {
              method: 'POST',
              body: formData,
            },
          )

          const newUrl = data.url
          if (newUrl) {
            const trimmedVal = value.trim()
            const updated = trimmedVal ? `${trimmedVal}\n${newUrl}` : newUrl
            onChange(updated)
            toast.success('Đã dán và tối ưu ảnh WebP thành công!')
          }
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : 'Lỗi không xác định khi xử lý ảnh.'
          toast.error(`Không thể dán ảnh: ${msg}`)
        } finally {
          setIsUploading(false)
        }
        return
      }

      // 2. Check for plain text URL in clipboard
      const text = e.clipboardData?.getData('text')?.trim()
      if (text && (text.startsWith('http://') || text.startsWith('https://') || text.startsWith('/media/') || text.startsWith('/store/'))) {
        e.preventDefault()
        e.stopPropagation()
        const trimmedVal = value.trim()
        const updated = trimmedVal ? `${trimmedVal}\n${text}` : text
        onChange(updated)
        toast.success('Đã dán liên kết media!')
      }
    },
    [fieldType, uploadDisabled, value, onChange],
  )

  return (
    <div className="space-y-1.5">
      {/* Header toolbar with 3 view modes */}
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
          <FieldIcon className="size-3 opacity-60" />
          {fieldName}
          {required && <span className="text-destructive">*</span>}
        </label>
        <div className="flex items-center gap-0.5 bg-muted/40 p-0.5 rounded-lg border border-border/40">
          <Button
            type="button"
            variant={viewMode === 'preview' ? 'secondary' : 'ghost'}
            size="icon"
            className="h-6 w-6 rounded"
            onClick={() => setViewMode('preview')}
            title="Xem trước (hỗ trợ Ctrl+V dán ảnh/link)"
            aria-label={`Xem trước ${fieldName}`}
          >
            <Eye className="size-3" />
          </Button>
          <Button
            type="button"
            variant={viewMode === 'url' ? 'secondary' : 'ghost'}
            size="icon"
            className="h-6 w-6 rounded"
            onClick={() => setViewMode('url')}
            title="Đường dẫn URL gốc"
            aria-label={`Đường dẫn URL ${fieldName}`}
          >
            <Link2 className="size-3" />
          </Button>
          <Button
            type="button"
            variant={viewMode === 'code' ? 'secondary' : 'ghost'}
            size="icon"
            className="h-6 w-6 rounded"
            onClick={() => setViewMode('code')}
            title="Mã HTML (chỉ xem)"
            aria-label={`Xem mã HTML ${fieldName}`}
          >
            <Code2 className="size-3" />
          </Button>
        </div>
      </div>

      {/* Mode 1: Preview */}
      {viewMode === 'preview' && (
        <div
          ref={containerRef}
          tabIndex={0}
          onPaste={handlePaste}
          className="relative rounded-xl border border-border/60 bg-muted/30 overflow-hidden focus:outline-none focus:ring-1 focus:ring-primary/40 transition-all cursor-pointer select-none group"
          title={uploadDisabled
            ? 'Bấm vào đây rồi nhấn Ctrl+V để dán link trực tiếp'
            : 'Bấm vào đây rồi nhấn Ctrl+V để dán ảnh hoặc link trực tiếp'}
        >
          {isUploading && (
            <div className="absolute inset-0 z-20 bg-background/80 backdrop-blur-xs flex flex-col items-center justify-center p-4 text-center">
              <LoaderCircle className="size-6 text-primary animate-spin mb-2" />
              <p className="text-xs font-semibold text-foreground">Đang tối ưu WebP & quét an toàn...</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">Vui lòng đợi trong giây lát</p>
            </div>
          )}

          {validUrls.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-6 px-4 text-center">
              <FieldIcon className="size-6 text-muted-foreground/40 mb-1.5" />
              <p className="text-[11px] font-medium text-muted-foreground">
                Chưa có {fieldType === 'audio' ? 'âm thanh' : 'ảnh'}.
              </p>
              <p className="text-[10px] text-muted-foreground/70 mt-1 max-w-xs">
                {fieldType === 'audio'
                  ? 'Chuyển sang tab URL để dán link âm thanh.'
                  : uploadDisabled
                    ? 'Thẻ này không hỗ trợ tải ảnh lên. Chuyển sang tab URL để nhập link ảnh.'
                    : 'Bấm vào đây và nhấn Ctrl+V để dán ảnh trực tiếp, hoặc chuyển sang tab URL để nhập link.'}
              </p>
            </div>
          ) : fieldType === 'audio' ? (
            <div className="p-3 space-y-2">
              {validUrls.map((rawUrl, index) => (
                <audio
                  key={`${rawUrl}-${index}`}
                  controls
                  src={resolveDisplayUrl(rawUrl, resolveUrl)}
                  className="w-full h-8 rounded"
                  preload="metadata"
                />
              ))}
              <p className="text-[10px] text-muted-foreground/60 text-right pr-1 italic">
                Bấm vào đây rồi nhấn Ctrl+V để dán thêm link
              </p>
            </div>
          ) : (
            <div className="p-2 space-y-1.5">
              <div className={validUrls.length === 1 ? 'w-full' : 'grid gap-2 grid-cols-2 sm:grid-cols-3'}>
                {validUrls.map((rawUrl, index) => (
                  <img
                    key={`${rawUrl}-${index}`}
                    src={resolveDisplayUrl(rawUrl, resolveUrl)}
                    alt={`${fieldName} ${index + 1}`}
                    className="w-full rounded-lg object-contain max-h-40 bg-background border border-border/40"
                    loading="lazy"
                  />
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground/60 text-right pr-1 italic">
                {uploadDisabled
                  ? 'Bấm vào đây rồi nhấn Ctrl+V để dán thêm link'
                  : 'Bấm vào đây rồi nhấn Ctrl+V để dán thêm ảnh/link'}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Mode 2: URL Edit */}
      {viewMode === 'url' && (
        <div className="space-y-1.5">
          <Textarea
            aria-label={`URL nguồn ${fieldName}`}
            placeholder={`Dán URL ${fieldType === 'audio' ? 'âm thanh' : 'ảnh'} — mỗi dòng một URL`}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            className="min-h-20 text-xs sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50 font-mono"
            autoFocus
          />
          <div className="flex items-center justify-between text-[10px] text-muted-foreground px-0.5">
            <span>Mỗi dòng 1 URL hợp lệ (HTTPS hoặc media hệ thống).</span>
            {values.length > 0 && <span>{validUrls.length}/{values.length} URL hợp lệ</span>}
          </div>
          {invalidCount > 0 && (
            <p className="flex items-center gap-1 text-[11px] text-destructive">
              <AlertCircle className="size-3" />
              {invalidCount} dòng không phải URL media hợp lệ và sẽ không được lưu.
            </p>
          )}
        </div>
      )}

      {/* Mode 3: Code View (Read-Only) */}
      {viewMode === 'code' && (
        <div className="rounded-xl border border-border/60 bg-muted/30 overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-3 py-1.5 bg-muted/60 border-b border-border/40">
            <span className="text-[10px] text-muted-foreground font-mono">HTML Preview (Read-only)</span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-[10px] gap-1 rounded hover:bg-muted font-medium"
              onClick={handleCopyCode}
              disabled={!derivedHtml}
              title="Sao chép mã HTML"
            >
              {copied ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
              <span>{copied ? 'Đã chép' : 'Sao chép'}</span>
            </Button>
          </div>
          <pre className="min-h-16 max-h-52 overflow-auto whitespace-pre-wrap break-all p-3 text-[11px] leading-relaxed font-mono text-foreground select-all">
            {derivedHtml || '<!-- Chưa có media hợp lệ -->'}
          </pre>
          <div className="px-3 py-1.5 bg-muted/40 border-t border-border/40 text-[10px] text-muted-foreground">
            Mã HTML do Flama tự động sinh ra khi render thẻ. Dùng để tham khảo khi tùy biến mẫu thẻ.
          </div>
        </div>
      )}
    </div>
  )
}
