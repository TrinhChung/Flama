import React, { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Database,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  Info,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { toast } from 'sonner'
import type { NoteTypeMeta, WorksheetFieldMapping } from '../types'
import { loadWorksheetPreset, saveWorksheetPreset } from '../utils/worksheetStorage'

export interface WorksheetFieldMappingStepProps {
  noteType: NoteTypeMeta
  deckName: string
  totalNotes: number
  suggestedMappings: Record<string, string>
  initialMapping?: WorksheetFieldMapping
  onConfirmMapping: (mapping: WorksheetFieldMapping) => void
  onBack: () => void
  className?: string
}

interface MappingFieldConfig {
  key: string
  label: string
  description: string
  required?: boolean
  fallbackCandidateKeys: string[]
}

export const WorksheetFieldMappingStep: React.FC<WorksheetFieldMappingStepProps> = ({
  noteType,
  deckName,
  totalNotes,
  suggestedMappings,
  initialMapping,
  onConfirmMapping,
  onBack,
  className = '',
}) => {
  const { t } = useTranslation('worksheets')
  const [fieldMapping, setFieldMapping] = useState<WorksheetFieldMapping>({})
  const [hasLoadedSavedPreset, setHasLoadedSavedPreset] = useState<boolean>(false)

  const commonMappingSlots: MappingFieldConfig[] = useMemo(
    () => [
      {
        key: 'kanji',
        label: t('mapping.slots.kanji.label', 'Chữ Hán / Từ vựng chính (Kanji / Word)'),
        description: t('mapping.slots.kanji.desc', 'Trường chứa từ vựng hoặc chữ Hán để in ra ô luyện viết tay.'),
        required: true,
        fallbackCandidateKeys: ['expression', 'kanji', 'word', 'vocab', 'front', 'hanzi'],
      },
      {
        key: 'reading',
        label: t('mapping.slots.reading.label', 'Cách đọc (Furigana / Pinyin / Kana)'),
        description: t('mapping.slots.reading.desc', 'Trường cách đọc phiên âm trên đầu chữ hoặc trong cột hướng dẫn.'),
        required: false,
        fallbackCandidateKeys: ['reading', 'furigana', 'kana', 'pinyin', 'pronunciation'],
      },
      {
        key: 'meaning',
        label: t('mapping.slots.meaning.label', 'Ý nghĩa / Dịch nghĩa (Meaning)'),
        description: t('mapping.slots.meaning.desc', 'Nghĩa tiếng Việt hoặc giải thích để in vào cột gợi ý hoặc thẻ nhớ.'),
        required: false,
        fallbackCandidateKeys: ['meaning', 'definition', 'vietnamese', 'hanviet', 'back', 'nghia'],
      },
      {
        key: 'sentence',
        label: t('mapping.slots.sentence.label', 'Câu ví dụ (Example Sentence)'),
        description: t('mapping.slots.sentence.desc', 'Dùng cho mẫu bài tập luyện viết cả câu hoặc điền ngữ pháp.'),
        required: false,
        fallbackCandidateKeys: ['sentence', 'example', 'sample'],
      },
    ],
    [t]
  )

  // Initialize field mapping on mount
  useEffect(() => {
    // 1. Try loading preset from localStorage for this specific noteTypeId
    const savedPreset = loadWorksheetPreset(noteType.id)
    if (savedPreset && savedPreset.fieldMapping && Object.keys(savedPreset.fieldMapping).length > 0) {
      setFieldMapping(savedPreset.fieldMapping)
      setHasLoadedSavedPreset(true)
      return
    }

    // 2. Otherwise use initialMapping or suggestedMappings with media filtering
    const initial: WorksheetFieldMapping = {
      ...(initialMapping || {}),
    }

    const available = noteType.fields || []
    const isMediaOrId = (f: string) => {
      const lower = f.toLowerCase()
      return ['audio', 'sound', 'voice', 'mp3', 'id', 'guid', 'time', 'date'].some((k) =>
        lower.includes(k),
      )
    }

    commonMappingSlots.forEach((slot) => {
      if (initial[slot.key]) return

      // Check suggestedMappings first if not media
      const suggested = suggestedMappings[slot.key]
      if (suggested && available.includes(suggested) && !isMediaOrId(suggested)) {
        initial[slot.key] = suggested
        return
      }

      // Fallback matching
      for (const cand of slot.fallbackCandidateKeys) {
        const foundExact = available.find(
          (f) => f.toLowerCase() === cand.toLowerCase() && !isMediaOrId(f),
        )
        if (foundExact) {
          initial[slot.key] = foundExact
          return
        }
      }

      for (const cand of slot.fallbackCandidateKeys) {
        const foundSub = available.find(
          (f) => f.toLowerCase().includes(cand.toLowerCase()) && !isMediaOrId(f),
        )
        if (foundSub) {
          initial[slot.key] = foundSub
          return
        }
      }

      // If required slot (e.g. kanji) still has no value, pick first non-media field
      if (slot.required && !initial[slot.key]) {
        const firstClean = available.find((f) => !isMediaOrId(f))
        if (firstClean) {
          initial[slot.key] = firstClean
        }
      }
    })

    setFieldMapping(initial)
  }, [noteType.id, noteType.fields, suggestedMappings, initialMapping, commonMappingSlots])

  // Sample values from the first note of this NoteType
  const sampleValues = useMemo(() => {
    return noteType.sample_values || {}
  }, [noteType])

  const handleFieldChange = (slotKey: string, fieldName: string) => {
    setFieldMapping((prev) => {
      const updated = { ...prev, [slotKey]: fieldName }
      // If kanji changed, mirror to word as well
      if (slotKey === 'kanji') {
        updated.word = fieldName
      }
      if (slotKey === 'reading') {
        updated.prompt_reading = fieldName
      }
      if (slotKey === 'meaning') {
        updated.prompt_meaning = fieldName
        updated.meaning_usage = fieldName
      }
      return updated
    })
  }

  const handleResetDefaults = () => {
    const fresh: WorksheetFieldMapping = {}
    const available = noteType.fields || []
    commonMappingSlots.forEach((slot) => {
      const s = suggestedMappings[slot.key]
      if (s && available.includes(s)) {
        fresh[slot.key] = s
      }
    })
    setFieldMapping(fresh)
    setHasLoadedSavedPreset(false)
    toast.info(t('mapping.toast_reset', 'Đã khôi phục ánh xạ gợi ý ban đầu'))
  }

  const canProceed = Boolean(fieldMapping.kanji || fieldMapping.word)

  const handleSubmit = () => {
    if (!canProceed) {
      toast.error(t('mapping.toast_error_required', 'Vui lòng chọn trường chứa Từ vựng / Chữ Hán chính!'))
      return
    }

    // Save preset to localStorage for instant reuse next time
    saveWorksheetPreset(noteType.id, {
      fieldMapping,
    })

    onConfirmMapping(fieldMapping)
  }

  return (
    <div className={`flex flex-col h-full overflow-hidden ${className}`}>
      {/* Step Header */}
      <div className="p-4 border-b border-border/70 bg-card/60 shrink-0">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                <Database className="size-4 text-primary" />
                <span>{t('mapping.header_title_deck', 'Bước 2: Ánh xạ trường dữ liệu từ thẻ học')}</span>
              </h3>
              {hasLoadedSavedPreset && (
                <Badge variant="outline" className="text-[10px] bg-primary/10 text-primary border-primary/20 flex items-center gap-1 font-semibold">
                  <Sparkles className="size-3" />
                  <span>{t('mapping.preset_loaded', 'Đã nạp thiết lập đã lưu')}</span>
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {deckName
                ? t('mapping.header_desc_deck', {
                    deck: deckName,
                    notes: totalNotes,
                    noteType: noteType.name,
                    defaultValue: `Chọn đúng các trường trong bộ thẻ ${deckName} (${totalNotes} thẻ, mẫu thẻ: ${noteType.name}).`,
                  })
                : t('mapping.header_desc', 'Xác nhận các trường từ vựng, cách đọc, ý nghĩa để hệ thống hiển thị chính xác vào mẫu bài tập.')}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleResetDefaults}
              className="h-8 text-xs text-muted-foreground hover:text-foreground"
              title={t('mapping.reset_button_title', 'Khôi phục ánh xạ mặc định')}
            >
              <RotateCcw className="size-3 mr-1" />
              <span>{t('mapping.reset_button', 'Gợi ý ban đầu')}</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Info Banner */}
        <div className="p-3.5 rounded-xl border border-border/70 bg-card text-xs space-y-1 shadow-2xs">
          <div className="font-semibold text-foreground flex items-center gap-1.5">
            <Info className="size-3.5 text-primary" />
            <span>{t('mapping.banner_title', 'Xác nhận nội dung trường nguồn')}</span>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            {t('mapping.banner_desc', 'Hệ thống hiển thị giá trị mẫu thực tế từ thẻ học để bạn kiểm tra. Hãy đảm bảo không chọn nhầm trường chứa file âm thanh (Audio) hay mã định danh để bài tập hiển thị chuẩn xác nhất.')}
          </p>
        </div>

        {/* Field Slots List */}
        <div className="space-y-3">
          {commonMappingSlots.map((slot) => {
            const currentValue = (fieldMapping[slot.key] as string) || ''
            const sampleText = currentValue ? sampleValues[currentValue] : ''
            const isLikelyMedia =
              Boolean(sampleText && (sampleText.includes('[sound:') || sampleText.endsWith('.mp3'))) ||
              Boolean(currentValue && currentValue.toLowerCase().includes('audio'))

            return (
              <div
                key={slot.key}
                className={`p-3.5 rounded-xl border transition-all ${
                  currentValue
                    ? 'border-border/90 bg-card shadow-2xs'
                    : slot.required
                    ? 'border-destructive/40 bg-destructive/5'
                    : 'border-border/60 bg-muted/20'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <span>{slot.label}</span>
                    {slot.required ? (
                      <Badge
                        variant="outline"
                        className="text-[9.5px] px-1.5 py-0 bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20 font-bold"
                      >
                        {t('mapping.required_badge', 'Bắt buộc')}
                      </Badge>
                    ) : (
                      <Badge
                        variant="outline"
                        className="text-[9.5px] px-1.5 py-0 text-muted-foreground border-border font-normal"
                      >
                        {t('mapping.optional_badge', 'Tùy chọn')}
                      </Badge>
                    )}
                  </Label>

                  {currentValue && !slot.required && (
                    <button
                      type="button"
                      onClick={() => handleFieldChange(slot.key, '')}
                      className="text-[10.5px] font-semibold text-muted-foreground hover:text-rose-500 transition-colors"
                    >
                      {t('mapping.skip_field', 'Bỏ qua trường này')}
                    </button>
                  )}
                </div>

                <p className="text-[11px] text-muted-foreground mb-2">
                  {slot.description}
                </p>

                {/* Dropdown Field Picker */}
                <NativeSelect
                  value={currentValue}
                  onChange={(e) => handleFieldChange(slot.key, e.target.value)}
                  className={`h-9 text-xs font-medium ${
                    !currentValue && slot.required ? 'border-destructive text-destructive' : ''
                  }`}
                >
                  <option value="">
                    {slot.required
                      ? t('mapping.select_required_field', '-- Bắt buộc: Hãy chọn trường chứa chữ Hán/từ vựng --')
                      : t('mapping.none_option', '-- Không sử dụng trường này --')}
                  </option>
                  {noteType.fields.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </NativeSelect>

                {/* Sample Value Chip */}
                {currentValue && (
                  <div className="mt-2 flex items-center gap-2 flex-wrap text-[11px]">
                    <span className="text-muted-foreground font-medium">
                      {t('mapping.sample_value_label', 'Giá trị mẫu trên thẻ:')}
                    </span>
                    {isLikelyMedia ? (
                      <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30 font-mono text-[10.5px]">
                        <AlertCircle className="size-3 text-amber-600 shrink-0" />
                        <span>
                          {t('mapping.warning_media', 'Cảnh báo: Trường này có vẻ là file âm thanh ({{val}})', { val: sampleText || currentValue })}
                        </span>
                      </div>
                    ) : sampleText ? (
                      <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-muted text-foreground border border-border/80 font-mono text-[10.5px]">
                        <CheckCircle2 className="size-3 text-emerald-600 shrink-0" />
                        <span className="truncate max-w-[280px]">"{sampleText}"</span>
                      </div>
                    ) : (
                      <span className="text-muted-foreground italic">
                        {t('mapping.sample_empty', '(Giá trị rỗng trong thẻ mẫu)')}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Footer Navigation */}
      <div className="p-3.5 border-t border-border/80 bg-muted/30 flex items-center justify-between gap-2 shrink-0">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onBack}
          className="h-9 px-3 text-xs gap-1.5 font-semibold"
        >
          <ArrowLeft className="size-3.5" />
          <span>{t('mapping.back_button', 'Quay lại')}</span>
        </Button>

        <Button
          type="button"
          size="sm"
          disabled={!canProceed}
          onClick={handleSubmit}
          className="h-9 px-4 text-xs font-bold gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground shadow-xs"
        >
          <span>{t('mapping.next_button', 'Tiếp tục: Chọn mẫu bài tập')}</span>
          <ArrowRight className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}
