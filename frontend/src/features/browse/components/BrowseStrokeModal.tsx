import { useState, useEffect, useMemo } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import {
  AlertCircle,
  AlertTriangle,
  Check,
  Clock,
  Copy,
  Eye,
  Languages,
  Layers,
  LoaderCircle,
  PenTool,
  Sparkles,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi, type GenerateStrokesResponse } from '@/app/api'
import { resolveBackendUrl } from '@/config/env'
import { cn } from '@/lib/utils'
import {
  loadStoredStrokeSettings,
  saveStoredStrokeSettings,
} from '../services/strokeStorage'
import type { useBrowseState, CardDetailResponse } from '../hooks/useBrowseState'

export interface BrowseStrokeModalProps {
  browse?: ReturnType<typeof useBrowseState>
  isOpen: boolean
  onClose: () => void
  mode?: 'single' | 'batch'
  cardId?: string | null
  fields?: Array<{ name: string; field_type?: string }>
  fieldValues?: Record<string, string>
  deckName?: string | null
  onApply?: (targetField: string, value: string) => void
}

export function BrowseStrokeModal({
  browse,
  isOpen,
  onClose,
  mode = 'batch',
  cardId,
  fields,
  fieldValues,
  deckName,
  onApply,
}: BrowseStrokeModalProps) {
  const defaultQueryClient = useQueryClient()
  const {
    selectedCards = [],
    selectedDeckId,
    activeCardId,
    cards = [],
    decksQuery,
    cardDetailQuery,
    editFieldValues: browseEditFieldValues,
    setEditFieldValues,
    queryClient: browseQueryClient,
  } = browse || {}

  const queryClient = browseQueryClient || defaultQueryClient
  const editFieldValues = browseEditFieldValues || fieldValues || {}

  // Determine target card ID to resolve actual Note Type fields
  const targetCardId =
    cardId || activeCardId || (selectedCards.length > 0 ? selectedCards[0] : cards[0]?.card_id)

  // Fetch card detail for target card if not already active in cardDetailQuery
  const targetCardQuery = useQuery({
    queryKey: ['browse', 'stroke-modal-card-detail', targetCardId],
    queryFn: () => appApi.get<CardDetailResponse>(`/browse/cards/${targetCardId}`),
    enabled: isOpen && Boolean(targetCardId) && cardDetailQuery?.data?.card?.card_id !== targetCardId,
    staleTime: 1000 * 60 * 5,
  })

  // Extract actual fields of the Note Type currently in use
  const actualNoteFields = useMemo(() => {
    if (fields && fields.length > 0) {
      return fields
    }
    if (cardDetailQuery?.data?.card?.card_id === targetCardId && cardDetailQuery.data?.fields?.length) {
      return cardDetailQuery.data.fields
    }
    if (targetCardQuery.data?.fields?.length) {
      return targetCardQuery.data.fields
    }
    if (cardDetailQuery?.data?.fields?.length) {
      return cardDetailQuery.data.fields
    }
    return []
  }, [fields, cardDetailQuery?.data, targetCardQuery.data, targetCardId])

  const noteFieldNames = useMemo(() => {
    const names = actualNoteFields.map((f) => f.name).filter(Boolean)
    if (names.length > 0) return names
    return ['Expression', 'Reading', 'Meaning', 'StrokeDiagram']
  }, [actualNoteFields])

  const mediaTargetFieldNames = useMemo(
    () =>
      actualNoteFields
        .filter((field) => {
          const type = String(field.field_type || '').toLowerCase()
          if (['image', 'diagram'].includes(type)) return true
          const name = field.name.toLowerCase()
          return [
            'diagram',
            'strokediagram',
            'stroke_diagram',
            'kanjistrokes',
            'strokes',
            'kanji_strokes',
            'stroke',
          ].includes(name)
        })
        .map((field) => field.name)
        .filter(Boolean),
    [actualNoteFields],
  )

  // Smart defaults based strictly on actual note fields
  const defaultSource = useMemo(() => {
    return (
      noteFieldNames.find((f) =>
        ['expression', 'word', 'kanji', 'hanzi', 'vocab', 'vocabulary', 'term', 'front'].includes(
          f.toLowerCase(),
        ),
      ) ||
      noteFieldNames[0] ||
      'Expression'
    )
  }, [noteFieldNames])

  const defaultTarget = useMemo(() => {
    return (
      mediaTargetFieldNames.find((f) =>
        ['diagram', 'strokediagram', 'stroke_diagram', 'kanjistrokes', 'strokes', 'kanji_strokes', 'stroke'].includes(
          f.toLowerCase(),
        ),
      ) ||
      (mediaTargetFieldNames.includes('StrokeDiagram')
        ? 'StrokeDiagram'
        : mediaTargetFieldNames[0]) ||
      noteFieldNames.find((f) =>
        ['diagram', 'strokediagram', 'stroke_diagram', 'kanjistrokes', 'strokes', 'kanji_strokes', 'stroke'].includes(
          f.toLowerCase(),
        ),
      ) ||
      ''
    )
  }, [mediaTargetFieldNames, noteFieldNames])

  const [sourceField, setSourceField] = useState(defaultSource)
  const [targetField, setTargetField] = useState(defaultTarget)

  // Sync state when defaults change
  useEffect(() => {
    if (defaultSource && !noteFieldNames.includes(sourceField)) {
      setSourceField(defaultSource)
    }
    if (defaultTarget && (!targetField || (!mediaTargetFieldNames.includes(targetField) && !noteFieldNames.includes(targetField)))) {
      setTargetField(defaultTarget)
    }
  }, [defaultSource, defaultTarget, noteFieldNames, mediaTargetFieldNames, sourceField, targetField])

  // Resolve actual text content from the selected sourceField across active/target card data
  const resolvedSourceValue = useMemo(() => {
    // 1. From active sidebar edits
    if (
      editFieldValues[sourceField] !== undefined &&
      editFieldValues[sourceField] !== null &&
      String(editFieldValues[sourceField]).trim()
    ) {
      return String(editFieldValues[sourceField]).trim()
    }
    // 2. From active card note field_values
    if (
      cardDetailQuery?.data?.note?.field_values?.[sourceField] !== undefined &&
      cardDetailQuery.data.note.field_values[sourceField] != null &&
      String(cardDetailQuery.data.note.field_values[sourceField]).trim()
    ) {
      return String(cardDetailQuery.data.note.field_values[sourceField]).trim()
    }
    // 3. From target card query note field_values
    if (
      targetCardQuery.data?.note?.field_values?.[sourceField] !== undefined &&
      String(targetCardQuery.data.note.field_values[sourceField]).trim()
    ) {
      return String(targetCardQuery.data.note.field_values[sourceField]).trim()
    }
    // 4. Fallback from card row
    const matchingCard = cards.find((c) => c.card_id === targetCardId) || cards[0]
    if (matchingCard) {
      const lower = sourceField.toLowerCase()
      if (
        ['expression', 'word', 'kanji', 'hanzi', 'vocab', 'vocabulary', 'front'].includes(lower) &&
        matchingCard.word
      ) {
        return matchingCard.word.trim()
      }
      if (['reading', 'kana', 'pinyin'].includes(lower) && matchingCard.reading) {
        return matchingCard.reading.trim()
      }
      if (['meaning', 'vietnamese', 'definition', 'back'].includes(lower) && matchingCard.meaning) {
        return matchingCard.meaning.trim()
      }
    }
    return ''
  }, [
    sourceField,
    editFieldValues,
    cardDetailQuery?.data,
    targetCardQuery.data,
    cards,
    targetCardId,
  ])

  // Auto-detect initial locale based on deck name or character composition
  const detectedLocale = useMemo(() => {
    const effectiveDeckName = (
      deckName ||
      decksQuery?.data?.decks?.find((d) => d.id === selectedDeckId)?.name ||
      cardDetailQuery?.data?.note?.deck_name ||
      cards.find((c) => c.card_id === targetCardId)?.deck_name ||
      ''
    ).toLowerCase()
    if (/hsk|trung|chinese|hán|zh/i.test(effectiveDeckName)) {
      return 'zh-CN'
    }
    if (/kanji|n[1-5]|nhật|japanese|ja/i.test(effectiveDeckName)) {
      return 'ja'
    }
    if (/[汉语话书买卖时间门关开钱鸡车电习爱国难易简单红蓝绿颜]/i.test(resolvedSourceValue)) {
      return 'zh-CN'
    }
    if (/[漢語話書買賣門關開錢雞車電習愛國學問題幫讓歲還過難練結發經動歡館銀飛機紅藍綠認識邊遠進鐘點課運遊體會讀寫聽說對應當從義號樣這裡頭視後廣風傳節圖與計劃網東長變報選請導備準確龍鳳華歷歸業農種標環構營製質達議組務調設實際處積極績術複雜職]/.test(resolvedSourceValue)) {
      return 'zh-TW'
    }
    return 'ja'
  }, [deckName, decksQuery?.data?.decks, cardDetailQuery?.data, cards, selectedDeckId, targetCardId, resolvedSourceValue])

  const [locale, setLocale] = useState<'ja' | 'zh-CN' | 'zh-TW'>(() => {
    return loadStoredStrokeSettings().locale
  })

  // Always auto-detect locale based on current deck/card content when modal opens
  // This ensures Chinese decks use Chinese SVGs even if user previously used Japanese locale
  useEffect(() => {
    if (detectedLocale) {
      setLocale(detectedLocale as 'ja' | 'zh-CN' | 'zh-TW')
    }
  }, [detectedLocale])

  const [overwrite, setOverwrite] = useState(() => {
    return loadStoredStrokeSettings().overwrite
  })
  const [maxChars] = useState(15)
  const [copiedCode, setCopiedCode] = useState(false)

  const [sampleText, setSampleText] = useState(resolvedSourceValue)

  // Automatically update sampleText whenever sourceField, target card, or card data changes
  useEffect(() => {
    setSampleText(resolvedSourceValue)
  }, [resolvedSourceValue, sourceField])

  // Stroke preview query
  const previewQuery = useQuery<GenerateStrokesResponse>({
    queryKey: ['stroke-preview', sampleText, locale, maxChars],
    queryFn: () =>
      appApi.generateStrokes({
        text: sampleText,
        locale,
        format: 'raw',
        max_characters: maxChars,
      }),
    enabled: isOpen && Boolean(sampleText.trim()),
    staleTime: 1000 * 60 * 5,
  })

  const targetCardIds = mode === 'single' && cardId ? [cardId] : selectedCards

  // Estimate batch workload query
  const estimateQuery = useQuery({
    queryKey: [
      'stroke-estimate',
      mode,
      targetCardIds,
      selectedDeckId,
      sourceField,
      targetField,
      locale,
      overwrite,
      maxChars,
    ],
    queryFn: () =>
      appApi.estimateBatchStrokes({
        source_field: sourceField,
        target_field: targetField,
        locale,
        deck_id: !targetCardIds.length && selectedDeckId ? selectedDeckId : undefined,
        card_ids: targetCardIds.length ? targetCardIds : undefined,
        overwrite,
        max_characters: maxChars,
      }),
    enabled: isOpen && mode !== 'single' && Boolean(sourceField.trim() && targetField.trim()),
    staleTime: 1000 * 30,
  })

  // Batch generate mutation
  const batchMutation = useMutation({
    mutationFn: () => {
      if (!sourceField.trim()) {
        throw new Error('Vui lòng chọn hoặc nhập trường nguồn.')
      }
      if (!targetField) {
        throw new Error('Vui lòng chọn hoặc nhập trường lưu kết quả.')
      }

      return appApi.batchGenerateStrokes({
        source_field: sourceField,
        target_field: targetField,
        locale,
        deck_id: !targetCardIds.length && selectedDeckId ? selectedDeckId : undefined,
        card_ids: targetCardIds.length ? targetCardIds : undefined,
        format: 'raw',
        overwrite,
        max_characters: maxChars,
      })
    },
    onSuccess: (res) => {
      const updatedText =
        res.updated > 0
          ? `Đã thêm nét vẽ cho ${res.updated} thẻ thành công!`
          : 'Đã hoàn tất kiểm tra các thẻ!'
      const skippedNote = res.skipped > 0 ? ` (${res.skipped} thẻ đã có sẵn hoặc bỏ qua)` : ''
      toast.success(`${updatedText}${skippedNote}`)
      void queryClient.invalidateQueries({ queryKey: ['browse-cards'] })
      void queryClient.invalidateQueries({ queryKey: ['card-detail'] })
      onClose()
    },
    onError: (err: any) => {
      toast.error(
        err?.message || 'Không thể tạo sơ đồ nét lúc này. Bạn vui lòng thử lại sau nhé.',
      )
    },
  })

  const handleApplySingle = () => {
    if (!targetField) {
      toast.error('Vui lòng chọn hoặc nhập trường lưu kết quả.')
      return
    }
    if (previewQuery.data?.output) {
      const canonicalUrls = (previewQuery.data.items || [])
        .map((item) => String(item.url || '').trim())
        .filter(Boolean)
        .join('\n')
      if (onApply) {
        onApply(targetField, canonicalUrls)
      } else if (setEditFieldValues) {
        setEditFieldValues((prev) => ({
          ...prev,
          [targetField]: canonicalUrls,
        }))
      }
      toast.success(`Đã điền nét vẽ vào trường "${targetField}". Bấm "Lưu thẻ" để hoàn tất nhé!`)
      onClose()
    } else {
      toast.warning('Không tìm thấy ký tự chữ Hán nào trong nội dung nguồn.')
    }
  }

  const handleCopyCode = async () => {
    if (!previewQuery.data?.output) return
    try {
      await navigator.clipboard.writeText(previewQuery.data.output)
      setCopiedCode(true)
      toast.success('Đã sao chép liên kết nét vẽ vào bộ nhớ tạm!')
      setTimeout(() => setCopiedCode(false), 2000)
    } catch {
      toast.error('Không thể sao chép.')
    }
  }

  const isDeckScope = mode === 'batch' && selectedCards.length === 0 && Boolean(selectedDeckId)
  const selectedDeck = browse?.selectedDeck
  const isMixedNoteTypes =
    isDeckScope &&
    (Boolean(selectedDeck?.has_mixed_note_types) || Boolean(estimateQuery.data?.has_mixed_note_types))

  const targetCount =
    mode === 'single'
      ? 1
      : selectedCards.length > 0
        ? selectedCards.length
        : selectedDeck
          ? `Cả bộ deck "${selectedDeck.name}" (${selectedDeck.counts?.total ?? 'tất cả'} thẻ)`
          : 'Tất cả thẻ trong Deck'

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[95vw] sm:max-w-xl max-h-[92vh] flex flex-col overflow-hidden p-0 rounded-2xl border-border/60 shadow-2xl">
        <DialogHeader className="px-5 py-4 border-b bg-muted/20 text-left shrink-0">
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
            <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
              <PenTool className="size-4.5 shrink-0" />
            </div>
            <span>Tạo sơ đồ thứ tự nét Kanji & Hanzi</span>
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground mt-0.5">
            Tự động trích xuất chữ Hán từ trường nguồn và sinh hình ảnh động/tĩnh minh họa thứ tự nét chuẩn xác.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 text-xs">
          {/* Target summary badge */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-muted/50 border border-border/60">
            <span className="text-muted-foreground flex items-center gap-1.5 font-medium">
              <Layers className="size-3.5 text-primary" />
              <span>Phạm vi áp dụng:</span>
            </span>
            <Badge variant="secondary" className="font-bold text-xs">
              {typeof targetCount === 'number' ? `${targetCount} thẻ` : targetCount}
            </Badge>
          </div>

          {/* Mixed Note Types Warning Banner */}
          {isMixedNoteTypes && (
            <div className="p-3.5 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-2.5 text-amber-800 dark:text-amber-200">
              <AlertTriangle className="size-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs space-y-0.5">
                <p className="font-bold">
                  Bộ deck đang chọn chứa nhiều note type nên không thể thực hiện thao tác.
                </p>
                <p className="text-[11px] text-amber-700/90 dark:text-amber-300/90">
                  {selectedDeck?.note_type_names?.length
                    ? `Các Note Type phát hiện: ${selectedDeck.note_type_names.join(', ')}.`
                    : ''}{' '}
                  Vui lòng chọn từng thẻ cụ thể hoặc chọn thư mục con có cùng một bộ Note Type để tạo sơ đồ nét đồng loạt.
                </p>
              </div>
            </div>
          )}

          {/* Form grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            {/* Source field */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Trường nguồn (chứa từ vựng)
              </Label>
              <NativeSelect
                value={sourceField}
                onChange={(e) => setSourceField(e.target.value)}
                className="h-9 text-xs rounded-lg bg-background"
              >
                {noteFieldNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </NativeSelect>
            </div>

            {/* Target field */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Trường lưu nét vẽ (Target Field)
              </Label>
              <NativeSelect
                value={targetField}
                onChange={(e) => setTargetField(e.target.value)}
                disabled={mediaTargetFieldNames.length === 0}
                className="h-9 text-xs rounded-lg bg-background"
              >
                {mediaTargetFieldNames.length === 0 ? (
                  <option value="">Loại thẻ này chưa có trường hình ảnh/sơ đồ</option>
                ) : (
                  <optgroup label="Các trường hình ảnh/sơ đồ của loại thẻ">
                    {mediaTargetFieldNames.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </optgroup>
                )}
              </NativeSelect>
            </div>

            {/* Locale */}
            <div className="space-y-1.5 sm:col-span-2">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                <Languages className="size-3.5" />
                <span>Quy tắc nét / Ngôn ngữ</span>
              </Label>
              <NativeSelect
                value={locale}
                onChange={(e) => {
                  const nextLocale = e.target.value as 'ja' | 'zh-CN' | 'zh-TW'
                  setLocale(nextLocale)
                  saveStoredStrokeSettings({ locale: nextLocale })
                }}
                className="h-9 text-xs rounded-lg bg-background"
              >
                <option value="ja">Tiếng Nhật (Kanji - Chuẩn KanjiVG)</option>
                <option value="zh-CN">Tiếng Trung Giản thể (zh-CN - Chuẩn Hán ngữ hiện đại)</option>
                <option value="zh-TW">Tiếng Trung Phồn thể (zh-TW - Chuẩn Đài Loan / Hồng Kông)</option>
              </NativeSelect>
            </div>
          </div>

          {/* Overwrite option */}
          <div className="flex items-center space-x-2 pt-0.5">
            <Checkbox
              id="overwrite-strokes"
              checked={overwrite}
              onCheckedChange={(c) => {
                const nextOverwrite = Boolean(c)
                setOverwrite(nextOverwrite)
                saveStoredStrokeSettings({ overwrite: nextOverwrite })
              }}
            />
            <Label
              htmlFor="overwrite-strokes"
              className="text-xs font-medium cursor-pointer select-none text-foreground"
            >
              Ghi đè nếu thẻ đã có sẵn nét vẽ trước đó
            </Label>
          </div>

          {/* Batch ETA & Workload Estimation Card */}
          {mode !== 'single' && Boolean(targetField) && (
            <div
              className={cn(
                'p-3.5 rounded-xl border transition-all text-xs space-y-2',
                estimateQuery.data?.is_heavy_task
                  ? 'bg-amber-500/10 border-amber-500/30 text-amber-950 dark:text-amber-200'
                  : 'bg-muted/40 border-border/80 text-foreground',
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold flex items-center gap-1.5 text-xs">
                  <Clock
                    className={cn(
                      'size-4 shrink-0',
                      estimateQuery.data?.is_heavy_task
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-primary',
                    )}
                  />
                  <span>Thời gian dự kiến hoàn thành:</span>
                </span>
                {estimateQuery.isLoading ? (
                  <span className="text-[11px] text-muted-foreground flex items-center gap-1 font-medium">
                    <LoaderCircle className="size-3 animate-spin text-primary" /> Đang tính toán...
                  </span>
                ) : estimateQuery.data ? (
                  <Badge
                    variant={estimateQuery.data.is_heavy_task ? 'default' : 'secondary'}
                    className={cn(
                      'font-bold text-xs px-2 py-0.5',
                      estimateQuery.data.is_heavy_task &&
                        'bg-amber-600 hover:bg-amber-700 text-white',
                    )}
                  >
                    {estimateQuery.data.estimated_human}
                  </Badge>
                ) : null}
              </div>

              {estimateQuery.data && (
                <div className="space-y-1.5 pt-1 text-[11px] text-muted-foreground border-t border-border/50">
                  <div className="flex flex-wrap items-center justify-between gap-1">
                    <span>Khối lượng cần xử lý:</span>
                    <span className="font-medium text-foreground">
                      {estimateQuery.data.notes_to_update} thẻ cần cập nhật (bỏ qua {estimateQuery.data.notes_skipped} thẻ)
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-1">
                    <span>Số lượng chữ Hán:</span>
                    <span className="font-medium text-foreground">
                      {estimateQuery.data.unique_characters} chữ ({estimateQuery.data.cached_characters} chữ có sẵn, {estimateQuery.data.new_characters} chữ mới)
                    </span>
                  </div>

                  {estimateQuery.data.is_heavy_task && (
                    <div className="flex items-start gap-1.5 pt-1 text-[11px] text-amber-700 dark:text-amber-300 font-medium">
                      <AlertTriangle className="size-3.5 shrink-0 mt-0.5" />
                      <span>
                        Tác vụ có {estimateQuery.data.new_characters} nét chữ mới cần chuẩn bị lần đầu. Bạn vui lòng giữ màn hình trong lúc hệ thống thực hiện nhé!
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Live Preview Area */}
          <div className="space-y-2 pt-2 border-t border-border/60">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Eye className="size-3.5 text-primary" />
                <span>Xem trước nét vẽ từ trường "{sourceField}"</span>
              </span>
              {previewQuery.isFetching && (
                <span className="text-[11px] text-primary flex items-center gap-1 font-medium">
                  <LoaderCircle className="size-3 animate-spin" /> Đang tải…
                </span>
              )}
            </div>

            <div className="space-y-1">
              <Input
                value={sampleText}
                onChange={(e) => setSampleText(e.target.value)}
                placeholder={`Nhập chữ hoặc văn bản của trường "${sourceField}"...`}
                className="h-8 text-xs bg-muted/40 font-medium"
              />
              {!sampleText && (
                <p className="text-[11px] text-muted-foreground italic">
                  Trường "{sourceField}" của thẻ đang chọn chưa có nội dung. Bạn có thể gõ chữ trực tiếp vào ô trên để xem thử nét vẽ nhé.
                </p>
              )}
            </div>

            {/* Extracted characters badges */}
            {previewQuery.data?.characters && previewQuery.data.characters.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                <span className="text-[11px] text-muted-foreground mr-0.5">
                  Chữ Hán tìm thấy ({previewQuery.data.characters.length}):
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
                        src={resolveBackendUrl(item.url)}
                        alt={item.char}
                        title={`${item.char} - Thứ tự nét`}
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
                  <span>Chưa tìm thấy chữ Hán nào để vẽ nét. Hãy thử gõ một chữ Hán vào ô trên nhé!</span>
                </div>
              )}
            </div>

            {/* Output Code / Text Preview */}
            {previewQuery.data?.output && (
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span className="flex items-center gap-1 font-medium">
                    <Sparkles className="size-3 text-primary" />
                    <span>Liên kết nét vẽ lưu vào trường &quot;{targetField}&quot;:</span>
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyCode}
                    className="flex items-center gap-1 text-primary hover:underline font-semibold"
                  >
                    {copiedCode ? <Check className="size-3" /> : <Copy className="size-3" />}
                    <span>{copiedCode ? 'Đã sao chép' : 'Sao chép'}</span>
                  </button>
                </div>
                <div className="p-2.5 rounded-lg bg-muted/60 border border-border/60 font-mono text-[11px] text-foreground overflow-x-auto whitespace-pre-wrap break-all max-h-20 select-all">
                  {previewQuery.data.output}
                </div>
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="px-5 py-3 border-t bg-muted/20 flex flex-row items-center justify-end gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={onClose} className="h-9 text-xs rounded-xl">
            Đóng
          </Button>

          {mode === 'single' ? (
            <Button
              size="sm"
              onClick={handleApplySingle}
              disabled={!targetField || !previewQuery.data?.items?.length}
              className="h-9 text-xs font-bold rounded-xl gap-1.5 shadow-xs"
            >
              <Check className="size-3.5" />
              <span>Thêm vào thẻ</span>
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => batchMutation.mutate()}
              disabled={!targetField || batchMutation.isPending || isMixedNoteTypes}
              className="h-9 text-xs font-bold rounded-xl gap-1.5 shadow-xs"
            >
              {batchMutation.isPending ? (
                <>
                  <LoaderCircle className="size-3.5 animate-spin" />
                  <span>
                    Đang tạo nét...{' '}
                    {estimateQuery.data?.estimated_human
                      ? `(${estimateQuery.data.estimated_human})`
                      : ''}
                  </span>
                </>
              ) : (
                <>
                  <PenTool className="size-3.5" />
                  <span>
                    Tạo cho {typeof targetCount === 'number' ? `${targetCount} thẻ` : targetCount}
                  </span>
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
