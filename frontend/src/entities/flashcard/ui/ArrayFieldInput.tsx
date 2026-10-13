import '@/shared/config/i18n'
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  AlertCircle,
  AlignLeft,
  Check,
  Code2,
  Copy,
  Eye,
  List,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  arrayNeedsCodeEditor,
  fieldValueEditorText,
  isValidArrayJson,
  parseArrayValue,
  parseArrayItems,
} from '@/lib/arrayField'

export type ArrayViewMode = 'preview' | 'normal' | 'code'

export interface ArrayFieldInputProps {
  fieldName: string
  value: unknown
  onChange: (value: string) => void
  onValidityChange?: (valid: boolean) => void
  required?: boolean
  /** View mode: 'preview' (items badges) | 'normal' (lines) | 'code' (JSON array) */
  mode?: ArrayViewMode
  /** Optional callback when user changes mode */
  onModeChange?: (newMode: ArrayViewMode) => void
  label?: string
  placeholderNormal?: string
  placeholderCode?: string
  className?: string
  disabled?: boolean
}

export function ArrayFieldInput({
  fieldName,
  value,
  onChange,
  onValidityChange,
  required = false,
  mode: externalMode,
  onModeChange,
  label,
  placeholderNormal,
  placeholderCode,
  className = '',
  disabled = false,
}: ArrayFieldInputProps) {
  const { t } = useTranslation('browse')
  const [internalMode, setInternalMode] = useState<ArrayViewMode>('normal')
  const [copied, setCopied] = useState(false)

  const [draftValue, setDraftValue] = useState<unknown>(value)
  const [editedMode, setEditedMode] = useState<ArrayViewMode | null>(null)
  const lastValuePropRef = useRef<unknown>(value)
  const lastReportedValueRef = useRef<unknown>(value)

  // Sync external value changes when parent changes value
  useEffect(() => {
    if (value !== lastValuePropRef.current) {
      lastValuePropRef.current = value
      if (value !== lastReportedValueRef.current) {
        setDraftValue(value)
        setEditedMode(null)
        lastReportedValueRef.current = value
      }
    }
  }, [value])

  const needsCode = arrayNeedsCodeEditor(draftValue)
  const requestedMode = externalMode ?? internalMode
  const hasInvalidCodeDraft = editedMode === 'code' && typeof draftValue === 'string' && !isValidArrayJson(draftValue)
  const effectiveMode = hasInvalidCodeDraft || (requestedMode === 'normal' && needsCode) ? 'code' : requestedMode
  const currentText = effectiveMode === 'code'
    ? editedMode === 'code' && typeof draftValue === 'string'
      ? draftValue
      : JSON.stringify(parseArrayValue(draftValue), null, 2)
    : typeof draftValue === 'string' && !isValidArrayJson(draftValue)
      ? draftValue
      : fieldValueEditorText(parseArrayValue(draftValue))

  // Items parsed from currentText for Preview and count indicators
  const items = useMemo(() => parseArrayItems(draftValue), [draftValue])

  // Validation: only checked in code mode
  const isInvalidJson = useMemo(() => {
    if (effectiveMode !== 'code') return false
    const trimmed = currentText.trim()
    return !isValidArrayJson(trimmed)
  }, [effectiveMode, currentText])

  useEffect(() => {
    onValidityChange?.(!isInvalidJson)
  }, [isInvalidJson, onValidityChange])

  // Mode switching
  const handleSetMode = useCallback(
    (targetMode: ArrayViewMode) => {
      if (disabled || isInvalidJson || targetMode === effectiveMode || (targetMode === 'normal' && needsCode)) return

      setInternalMode(targetMode)
      onModeChange?.(targetMode)
    },
    [disabled, isInvalidJson, effectiveMode, needsCode, onModeChange],
  )

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const next = e.target.value
      setDraftValue(next)
      setEditedMode(effectiveMode)
      if (externalMode === undefined) setInternalMode(effectiveMode)
      lastReportedValueRef.current = next
      onChange(next)
    },
    [onChange, effectiveMode, externalMode],
  )

  const handleCopyJson = useCallback(() => {
    const textToCopy =
      effectiveMode === 'code' ? currentText : JSON.stringify(parseArrayValue(draftValue), null, 2)
    if (!textToCopy) return
    navigator.clipboard
      .writeText(textToCopy)
      .then(() => {
        setCopied(true)
        toast.success(t('editor.copied_json_success', 'Đã sao chép mã JSON vào clipboard!'))
        setTimeout(() => setCopied(false), 2000)
      })
      .catch(() => {
        toast.error(t('editor.copy_failed', 'Không thể sao chép.'))
      })
  }, [effectiveMode, currentText, draftValue, t])

  return (
    <div className={`space-y-1.5 ${className}`}>
      {/* Header toolbar with 3 view modes matching MediaFieldPreview */}
      <div className="flex items-center justify-between">
        <label htmlFor={`array-field-${fieldName}`} className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
          <List className="size-3 opacity-60" />
          <span>{label || fieldName}</span>
          {required && <span className="text-destructive">*</span>}
          <Badge
            variant="outline"
            className="text-[9px] px-1 py-0 font-mono text-muted-foreground/80 uppercase"
          >
            array
          </Badge>
        </label>
        <div className="flex items-center gap-0.5 bg-muted/40 p-0.5 rounded-lg border border-border/40">
          <Button
            type="button"
            variant={effectiveMode === 'preview' ? 'secondary' : 'ghost'}
            size="icon"
            className="h-6 w-6 rounded"
            onClick={() => handleSetMode('preview')}
            disabled={disabled || isInvalidJson}
            title={t('editor.view_mode_preview_tooltip', 'Xem trước danh sách (preview)')}
            aria-label={`Xem trước ${fieldName}`}
          >
            <Eye className="size-3" />
          </Button>
          <Button
            type="button"
            variant={effectiveMode === 'normal' ? 'secondary' : 'ghost'}
            size="icon"
            className="h-6 w-6 rounded"
            onClick={() => handleSetMode('normal')}
            disabled={disabled || isInvalidJson || needsCode}
            title={t('editor.view_mode_normal_tooltip', 'Chế độ xem thường (mỗi dòng một phần tử)')}
            aria-label={`Nhập thường ${fieldName}`}
          >
            <AlignLeft className="size-3" />
          </Button>
          <Button
            type="button"
            variant={effectiveMode === 'code' ? 'secondary' : 'ghost'}
            size="icon"
            className="h-6 w-6 rounded"
            onClick={() => handleSetMode('code')}
            disabled={disabled}
            title={t('editor.view_mode_code_tooltip', 'Chế độ xem code mảng JSON')}
            aria-label={`Xem code ${fieldName}`}
          >
            <Code2 className="size-3" />
          </Button>
        </div>
      </div>

      {/* Mode 1: Preview (Pills / Badges view) */}
      {effectiveMode === 'preview' && (
        <div className="rounded-xl border border-border/60 bg-muted/30 p-3 space-y-2.5">
          {items.length === 0 ? (
            <div
              onClick={() => handleSetMode('normal')}
              className="flex flex-col items-center justify-center py-5 text-center cursor-pointer select-none group"
              title={t('editor.click_to_edit', 'Bấm để chỉnh sửa')}
            >
              <List className="size-5 text-muted-foreground/40 mb-1.5 group-hover:text-primary transition-colors" />
              <p className="text-[11px] font-medium text-muted-foreground group-hover:text-foreground transition-colors">
                {t('editor.empty_array_preview', 'Chưa có phần tử nào.')}
              </p>
              <p className="text-[10px] text-muted-foreground/70 mt-0.5">
                {t('editor.empty_array_preview_hint', 'Chuyển sang chế độ Thường hoặc Code để nhập nội dung.')}
              </p>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto p-0.5">
                {items.map((item, idx) => (
                  <span
                    key={`${idx}-${item}`}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-background/90 border border-border/60 text-foreground font-medium shadow-2xs"
                  >
                    <span className="text-[10px] text-muted-foreground font-mono font-semibold">
                      {idx + 1}.
                    </span>
                    <span>{item}</span>
                  </span>
                ))}
              </div>
              <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/30">
                <span>{t('editor.items_count', '{{count}} phần tử', { count: items.length })}</span>
                <button
                  type="button"
                  disabled={disabled || needsCode}
                  onClick={() => handleSetMode('normal')}
                  className="text-primary hover:underline font-medium"
                >
                  {t('editor.edit_list', 'Chỉnh sửa')}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Mode 2: Normal (Line-by-line Textarea) */}
      {effectiveMode === 'normal' && (
        <div className="space-y-1.5">
          <Textarea
            id={`array-field-${fieldName}`}
            aria-label={fieldName}
            value={currentText}
            onChange={handleChange}
            disabled={disabled}
            placeholder={placeholderNormal || t('editor.array_placeholder', 'Mỗi dòng một phần tử')}
            className="min-h-20 text-xs sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50 focus:bg-background transition-colors"
          />
          <div className="flex items-center justify-between text-[10px] text-muted-foreground px-0.5">
            <span>{t('editor.array_line_hint', 'Mỗi dòng một phần tử (tự động lưu mảng).')}</span>
            {items.length > 0 && (
              <span>{t('editor.items_count', '{{count}} phần tử', { count: items.length })}</span>
            )}
          </div>
        </div>
      )}

      {/* Mode 3: Code (JSON Array Code Editor) */}
      {effectiveMode === 'code' && (
        <div className="space-y-1.5">
          <div className="rounded-xl border border-border/60 bg-muted/30 overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-3 py-1.5 bg-muted/60 border-b border-border/40">
              <span className="text-[10px] text-muted-foreground font-mono">
                JSON Array ({items.length} {t('editor.items_label', 'phần tử')})
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-[10px] gap-1 rounded hover:bg-muted font-medium"
                onClick={handleCopyJson}
                disabled={!currentText}
                title={t('editor.copy_json', 'Sao chép JSON')}
              >
                {copied ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                <span>{copied ? t('editor.copied', 'Đã chép') : t('editor.copy', 'Sao chép')}</span>
              </Button>
            </div>
            <Textarea
              id={`array-field-${fieldName}`}
              aria-label={fieldName}
              aria-invalid={isInvalidJson || undefined}
              aria-describedby={isInvalidJson ? `array-field-${fieldName}-error` : undefined}
              value={currentText}
              onChange={handleChange}
              disabled={disabled}
              placeholder={placeholderCode || '[\n  "item 1",\n  "item 2"\n]'}
              className={`min-h-24 text-xs font-mono rounded-none border-0 leading-relaxed resize-y bg-transparent text-foreground focus-visible:ring-0 shadow-none ${
                isInvalidJson ? 'text-destructive' : ''
              }`}
            />
          </div>
          {isInvalidJson && (
            <div id={`array-field-${fieldName}-error`} role="alert" className="flex items-center gap-1 text-[11px] text-destructive font-medium animate-in fade-in slide-in-from-top-1 px-1">
              <AlertCircle className="size-3 shrink-0" />
              <span>
                {t(
                  'editor.invalid_array_json',
                  'Cú pháp JSON Array không hợp lệ (ví dụ: ["mục 1", "mục 2"])',
                )}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
