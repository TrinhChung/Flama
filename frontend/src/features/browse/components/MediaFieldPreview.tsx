import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { AlertCircle, Code2, Eye, FileImage, ImageIcon, Music } from 'lucide-react'

interface MediaFieldPreviewProps {
  fieldName: string
  fieldType: 'image' | 'audio' | 'diagram'
  value: string
  onChange: (value: string) => void
  required?: boolean
}

function resolveDisplayUrl(raw: string): string {
  const value = raw.trim()
  if (/^https:\/\/[^\s"'<>]+$/i.test(value)) return value
  if (/^http:\/\/(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?\/[^\s"'<>]*$/i.test(value)) return value
  if (/^\/media\/proxy\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(value)) return value
  if (/^\/media\/library\/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value)) return value
  if (/^\/static\/strokes\/[A-Za-z0-9_-]+\/[A-Fa-f0-9]+\.svg$/.test(value)) return value
  return ''
}

function parseMediaValues(value: string): string[] {
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
    const extension = path.split('/').pop()?.split('.').pop()?.toLowerCase() || ''
    if (IMAGE_EXTENSIONS.has(extension)) return 'image'
    if (AUDIO_EXTENSIONS.has(extension)) return 'audio'
  } catch {
    return null
  }
  return null
}

function isValidForField(raw: string, fieldType: MediaFieldPreviewProps['fieldType']): boolean {
  const displayUrl = resolveDisplayUrl(raw)
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
): string {
  const tags = urls
    .map(resolveDisplayUrl)
    .filter(Boolean)
    .map((url) => fieldType === 'audio'
      ? `<audio controls src="${escapeHtmlAttribute(url)}"></audio>`
      : `<img src="${escapeHtmlAttribute(url)}" class="flama-media-image" alt="${escapeHtmlAttribute(fieldName)}">`)
  if (tags.length <= 1) return tags[0] || ''
  return `<div class="flama-media-gallery">\n  ${tags.join('\n  ')}\n</div>`
}

export function MediaFieldPreview({
  fieldName,
  fieldType,
  value,
  onChange,
  required,
}: MediaFieldPreviewProps) {
  const [viewMode, setViewMode] = useState<'preview' | 'code'>('preview')
  const values = useMemo(() => parseMediaValues(value), [value])
  const validUrls = useMemo(
    () => values.filter((item) => isValidForField(item, fieldType)),
    [values, fieldType],
  )
  const invalidCount = values.length - validUrls.length
  const derivedHtml = useMemo(
    () => buildDerivedHtml(validUrls, fieldType, fieldName),
    [validUrls, fieldType, fieldName],
  )
  const FieldIcon = fieldType === 'audio' ? Music : fieldType === 'diagram' ? FileImage : ImageIcon

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
          <FieldIcon className="size-3 opacity-60" />
          {fieldName}
          {required && <span className="text-destructive">*</span>}
        </label>
        <div className="flex items-center gap-0.5">
          <Button
            type="button"
            variant={viewMode === 'preview' ? 'secondary' : 'ghost'}
            size="icon"
            className="h-6 w-6 rounded"
            onClick={() => setViewMode('preview')}
            title="Xem trước"
            aria-label={`Xem trước ${fieldName}`}
          >
            <Eye className="size-3" />
          </Button>
          <Button
            type="button"
            variant={viewMode === 'code' ? 'secondary' : 'ghost'}
            size="icon"
            className="h-6 w-6 rounded"
            onClick={() => setViewMode('code')}
            title="Xem mã HTML"
            aria-label={`Xem mã HTML ${fieldName}`}
          >
            <Code2 className="size-3" />
          </Button>
        </div>
      </div>

      <div className="rounded-xl border border-border/60 bg-muted/30 overflow-hidden">
        {viewMode === 'code' ? (
          <pre className="min-h-16 max-h-52 overflow-auto whitespace-pre-wrap break-all p-3 text-[11px] leading-relaxed font-mono text-foreground">
            {derivedHtml || '<!-- Chưa có media hợp lệ -->'}
          </pre>
        ) : validUrls.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-6 px-4 text-center">
            <FieldIcon className="size-6 text-muted-foreground/40 mb-1.5" />
            <p className="text-[11px] text-muted-foreground">
              Chưa có {fieldType === 'audio' ? 'âm thanh' : 'ảnh'} hợp lệ.
            </p>
          </div>
        ) : fieldType === 'audio' ? (
          <div className="p-3 space-y-2">
            {validUrls.map((rawUrl, index) => (
              <audio
                key={`${rawUrl}-${index}`}
                controls
                src={rawUrl}
                className="w-full h-8 rounded"
                preload="metadata"
              />
            ))}
          </div>
        ) : (
          <div className={validUrls.length === 1 ? 'p-2' : 'p-2 grid gap-2 grid-cols-2 sm:grid-cols-3'}>
            {validUrls.map((rawUrl, index) => (
              <img
                key={`${rawUrl}-${index}`}
                src={rawUrl}
                alt={`${fieldName} ${index + 1}`}
                className="w-full rounded-lg object-contain max-h-40 bg-background border border-border/40"
                loading="lazy"
              />
            ))}
          </div>
        )}
      </div>

      <Textarea
        aria-label={`URL nguồn ${fieldName}`}
        placeholder={`Dán URL ${fieldType === 'audio' ? 'âm thanh' : 'ảnh'} — mỗi dòng một URL`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-16 text-xs sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50 font-mono"
      />
      {invalidCount > 0 && (
        <p className="flex items-center gap-1 text-[11px] text-destructive">
          <AlertCircle className="size-3" />
          {invalidCount} dòng không phải URL media hợp lệ và sẽ không được lưu.
        </p>
      )}
    </div>
  )
}
