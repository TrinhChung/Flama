import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  AlertCircle,
  Check,
  Copy,
  Eye,
  LoaderCircle,
  Sparkles,
} from 'lucide-react'
import type { GenerateStrokesResponse } from '@/entities/stroke'
import { resolveBackendUrl, resolveMediaUrl } from '@/shared/config/env'

export interface BrowseStrokeSinglePreviewProps {
  sourceField: string
  targetField: string
  sampleText: string
  setSampleText: (text: string) => void
  previewQuery: {
    isFetching: boolean
    data?: GenerateStrokesResponse
  }
  copiedCode: boolean
  handleCopyCode: () => void
}

export function BrowseStrokeSinglePreview({
  sourceField,
  targetField,
  sampleText,
  setSampleText,
  previewQuery,
  copiedCode,
  handleCopyCode,
}: BrowseStrokeSinglePreviewProps) {
  const { t } = useTranslation('browse')

  return (
    <div className="space-y-2 pt-2 border-t border-border/60">
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
          <Eye className="size-3.5 text-primary" />
          <span>{t('stroke_modal.preview_title', { field: sourceField })}</span>
        </span>
        {previewQuery.isFetching && (
          <span className="text-[11px] text-primary flex items-center gap-1 font-medium">
            <LoaderCircle className="size-3 animate-spin" /> {t('stroke_modal.loading')}
          </span>
        )}
      </div>

      <div className="space-y-1">
        <Input
          value={sampleText}
          onChange={(e) => setSampleText(e.target.value)}
          placeholder={t('stroke_modal.input_placeholder', { field: sourceField })}
          className="h-8 text-xs bg-muted/40 font-medium"
        />
        {!sampleText && (
          <p className="text-[11px] text-muted-foreground italic">
            {t('stroke_modal.empty_source_hint', { field: sourceField })}
          </p>
        )}
      </div>

      {/* Extracted characters badges */}
      {previewQuery.data?.characters && previewQuery.data.characters.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
          <span className="text-[11px] text-muted-foreground mr-0.5">
            {t('stroke_modal.kanji_found_count', { count: previewQuery.data.characters.length })}
          </span>
          {previewQuery.data.characters.map((c) => (
            <Badge
              key={c}
              variant="secondary"
              className="text-xs font-bold px-2 py-0.5 bg-primary/10 text-primary border-primary/20"
            >
              {c}
            </Badge>
          ))}
        </div>
      )}

      {/* Rendered SVG Preview */}
      <div className="p-3.5 rounded-xl bg-card border border-border/80 min-h-28 flex items-center justify-center shadow-xs">
        {previewQuery.data?.items && previewQuery.data.items.length > 0 ? (
          <div className="flex flex-wrap gap-3.5 justify-center items-center">
            {previewQuery.data.items.map((item) => (
              <div
                key={item.hex}
                className="w-20 h-20 sm:w-24 sm:h-24 rounded-xl bg-white dark:bg-zinc-950 border border-border/70 p-1 flex items-center justify-center overflow-hidden shadow-2xs hover:border-primary/50 transition-all shrink-0"
              >
                <img
                  src={resolveMediaUrl(item.url)}
                  alt={item.char}
                  title={t('stroke_modal.stroke_order_title', { char: item.char })}
                  className="w-full h-full object-contain"
                  loading="lazy"
                  onError={(e) => {
                    const target = e.target as HTMLImageElement
                    target.onerror = null
                    target.src = resolveBackendUrl('/static/images/image-library-fallback.svg')
                  }}
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-muted-foreground text-xs py-3">
            <AlertCircle className="size-5 mx-auto mb-1 opacity-50" />
            <span>{t('stroke_modal.no_kanji_found')}</span>
          </div>
        )}
      </div>

      {/* Output Code / Text Preview */}
      {previewQuery.data?.output && (
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1 font-medium">
              <Sparkles className="size-3 text-primary" />
              <span>{t('stroke_modal.link_saved_to', { field: targetField })}</span>
            </span>
            <button
              type="button"
              onClick={handleCopyCode}
              className="flex items-center gap-1 text-primary hover:underline font-semibold"
            >
              {copiedCode ? <Check className="size-3" /> : <Copy className="size-3" />}
              <span>{copiedCode ? t('stroke_modal.copied') : t('stroke_modal.copy')}</span>
            </button>
          </div>
          <div className="p-2.5 rounded-lg bg-muted/60 border border-border/60 font-mono text-[11px] text-foreground overflow-x-auto whitespace-pre-wrap break-all max-h-20 select-all">
            {previewQuery.data.output}
          </div>
        </div>
      )}
    </div>
  )
}
