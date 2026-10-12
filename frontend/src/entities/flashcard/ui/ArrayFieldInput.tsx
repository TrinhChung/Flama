import '@/shared/config/i18n'
import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { AlignLeft, Code, AlertCircle } from 'lucide-react'
import {
  arrayCodeToLines,
  arrayLinesToCode,
  fieldValueEditorText,
  isValidArrayJson,
} from '@/lib/arrayField'

export type ArrayViewMode = 'normal' | 'code'

export interface ArrayFieldInputProps {
  fieldName: string
  value: unknown
  onChange: (value: string) => void
  required?: boolean
  /** Inherited or external view mode: 'normal' (lines) | 'code' (JSON array) */
  mode?: ArrayViewMode
  /** Optional callback when user toggles mode */
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

  const effectiveMode = externalMode ?? internalMode

  // Sync internal mode if externalMode is updated
  useEffect(() => {
    if (externalMode !== undefined) {
      setInternalMode(externalMode)
    }
  }, [externalMode])

  // Get raw string representation
  const rawString = useMemo(() => {
    if (typeof value === 'string') return value
    return fieldValueEditorText(value)
  }, [value])

  // Determine current display value based on effectiveMode
  const displayValue = useMemo(() => {
    if (effectiveMode === 'code') {
      // If already a JSON array or user typed array syntax like `[...`, show as-is
      if (rawString.trim().startsWith('[')) {
        return rawString
      }
      return arrayLinesToCode(rawString)
    }
    // Normal mode: lines
    if (isValidArrayJson(rawString)) {
      return arrayCodeToLines(rawString)
    }
    return rawString
  }, [effectiveMode, rawString])

  const [draftValue, setDraftValue] = useState<string>(displayValue)

  useEffect(() => {
    setDraftValue(displayValue)
  }, [displayValue])

  const handleToggleMode = useCallback(() => {
    const nextMode: ArrayViewMode = effectiveMode === 'normal' ? 'code' : 'normal'
    if (nextMode === 'code') {
      // Switching from normal lines to code array
      const code = arrayLinesToCode(draftValue)
      setDraftValue(code)
      onChange(code)
    } else {
      // Switching from code array to normal lines
      if (isValidArrayJson(draftValue)) {
        const lines = arrayCodeToLines(draftValue)
        setDraftValue(lines)
        onChange(lines)
      } else {
        // If draft is not valid JSON, leave as is to avoid destroying input
        setDraftValue(draftValue)
      }
    }
    setInternalMode(nextMode)
    onModeChange?.(nextMode)
  }, [effectiveMode, draftValue, onChange, onModeChange])

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const next = e.target.value
      setDraftValue(next)
      onChange(next)
    },
    [onChange],
  )

  const isInvalidJson = useMemo(() => {
    if (effectiveMode !== 'code') return false
    const trimmed = draftValue.trim()
    if (!trimmed) return false
    return !isValidArrayJson(trimmed)
  }, [effectiveMode, draftValue])

  return (
    <div className={`space-y-1.5 ${className}`}>
      {/* Field Header with Label and Mode Toggle */}
      <div className="flex items-center justify-between gap-2">
        <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
          <span>{label || fieldName} {required && <span className="text-destructive">*</span>}</span>
          <Badge variant="outline" className="text-[9px] px-1 py-0 font-mono text-muted-foreground/80 uppercase">
            array
          </Badge>
        </Label>
        <button
          type="button"
          onClick={handleToggleMode}
          disabled={disabled}
          className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1 px-1.5 py-0.5 rounded-md hover:bg-muted/80 transition-colors font-medium border border-border/40"
          title={
            effectiveMode === 'normal'
              ? t('editor.switch_to_code', 'Chuyển sang xem code')
              : t('editor.switch_to_normal', 'Chuyển sang xem thường')
          }
        >
          {effectiveMode === 'code' ? (
            <>
              <Code className="size-3 text-primary" />
              <span className="font-mono text-primary font-semibold">
                {t('editor.view_mode_code', 'Code (Array)')}
              </span>
            </>
          ) : (
            <>
              <AlignLeft className="size-3" />
              <span>{t('editor.view_mode_normal', 'Thường')}</span>
            </>
          )}
        </button>
      </div>

      {/* Editor Textarea */}
      {effectiveMode === 'code' ? (
        <Textarea
          value={draftValue}
          onChange={handleChange}
          disabled={disabled}
          placeholder={placeholderCode || '[\n  "item 1",\n  "item 2"\n]'}
          className={`min-h-24 text-xs font-mono rounded-xl leading-relaxed resize-y bg-muted/65 text-foreground border-border/80 focus:border-primary/80 transition-colors ${
            isInvalidJson ? 'border-destructive/80 focus:border-destructive ring-1 ring-destructive/30' : ''
          }`}
        />
      ) : (
        <Textarea
          value={draftValue}
          onChange={handleChange}
          disabled={disabled}
          placeholder={placeholderNormal || t('editor.array_placeholder', 'Mỗi dòng một phần tử')}
          className="min-h-20 text-xs sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50 focus:bg-background transition-colors"
        />
      )}

      {/* Syntax Error Hint in Code Mode */}
      {isInvalidJson && (
        <div className="flex items-center gap-1 text-[11px] text-destructive font-medium animate-in fade-in slide-in-from-top-1">
          <AlertCircle className="size-3 shrink-0" />
          <span>{t('editor.invalid_array_json', 'Cú pháp JSON Array không hợp lệ (ví dụ: ["mục 1", "mục 2"])')}</span>
        </div>
      )}
    </div>
  )
}
