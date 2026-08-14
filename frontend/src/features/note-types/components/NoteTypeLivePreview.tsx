import React, { useState } from 'react'
import { Eye, Loader2, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { CardDisplay } from '@/features/study/components/CardDisplay'

export interface PreviewTemplateOption {
  id: string
  name: string
}

export interface NoteTypeLivePreviewProps {
  cardId: string
  side?: 'front' | 'back'
  onSideChange?: (side: 'front' | 'back') => void
  templates?: PreviewTemplateOption[]
  selectedTemplateId?: string
  onSelectTemplate?: (id: string) => void
  frontPayload?: unknown
  backPayload?: unknown
  frontHtml?: string
  backHtml?: string
  scope?: string
  scopeId?: string
  fieldDefs?: Array<{ id: string; name: string; field_type: string; position: number }>
  isLoading?: boolean
  error?: string | null
  title?: string
  subtitle?: string
  className?: string
  containerHeightClass?: string
  showSideSelector?: boolean
}

export const NoteTypeLivePreview: React.FC<NoteTypeLivePreviewProps> = ({
  cardId,
  side: controlledSide,
  onSideChange,
  templates = [],
  selectedTemplateId,
  onSelectTemplate,
  frontPayload,
  backPayload,
  frontHtml,
  backHtml,
  scope = 'note_type_live_preview',
  scopeId,
  fieldDefs,
  isLoading = false,
  error = null,
  title = 'Live Card Preview',
  subtitle = '(Mẫu thẻ với dữ liệu mẫu)',
  className = '',
  containerHeightClass = 'h-[clamp(14rem,40vh,30rem)] min-h-[240px]',
  showSideSelector = true,
}) => {
  const [internalSide, setInternalSide] = useState<'front' | 'back'>('front')

  const activeSide = controlledSide !== undefined ? controlledSide : internalSide

  const handleSideToggle = (newSide: 'front' | 'back') => {
    if (onSideChange) {
      onSideChange(newSide)
    } else {
      setInternalSide(newSide)
    }
  }

  return (
    <Card className={`p-4 sm:p-5 border border-border/80 shadow-xs flex-1 flex flex-col rounded-2xl ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3 min-h-[32px]">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-primary/10 text-primary">
            <Eye className="size-4" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-foreground">{title}</h4>
            {subtitle && <span className="text-[10px] text-muted-foreground block">{subtitle}</span>}
          </div>
          {isLoading && (
            <span className="text-xs text-primary font-semibold animate-pulse ml-2 flex items-center gap-1">
              <Loader2 className="size-3 animate-spin" /> Đang cập nhật…
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 ml-auto">
          {templates.length > 1 && onSelectTemplate && (
            <NativeSelect
              value={selectedTemplateId || templates[0]?.id}
              onChange={(e) => onSelectTemplate(e.target.value)}
              className="h-8 text-xs font-medium w-36 rounded-xl bg-background"
            >
              {templates.map((tmpl) => (
                <NativeSelectOption key={tmpl.id} value={tmpl.id}>
                  {tmpl.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          )}

          {showSideSelector && (
            <div className="inline-flex rounded-xl border border-border/80 bg-muted/30 p-0.5 shadow-2xs">
              <Button
                size="sm"
                variant={activeSide === 'front' ? 'default' : 'ghost'}
                onClick={() => handleSideToggle('front')}
                className="h-7 px-3 text-xs font-bold rounded-lg transition-all"
              >
                Mặt trước
              </Button>
              <Button
                size="sm"
                variant={activeSide === 'back' ? 'default' : 'ghost'}
                onClick={() => handleSideToggle('back')}
                className="h-7 px-3 text-xs font-bold rounded-lg transition-all"
              >
                <RotateCcw className="size-3 mr-1" /> Mặt sau
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Rendered Viewport using CardDisplay */}
      <div className={`${containerHeightClass} w-full flex-1 overflow-hidden rounded-xl border border-border/80 bg-muted/30 dark:bg-muted/10 relative p-3`}>
        {error ? (
          <div className="flex h-full items-center justify-center p-6 text-center text-sm text-destructive">
            {error}
          </div>
        ) : frontPayload !== undefined || backPayload !== undefined || frontHtml || backHtml ? (
          <CardDisplay
            cardId={cardId}
            side={activeSide}
            frontPayload={frontPayload}
            backPayload={backPayload}
            frontHtml={frontHtml}
            backHtml={backHtml}
            scope={scope}
            scopeId={scopeId}
            fieldDefs={fieldDefs}
          />
        ) : (
          <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
            Đang chuẩn bị bản xem trước…
          </div>
        )}
      </div>
    </Card>
  )
}
